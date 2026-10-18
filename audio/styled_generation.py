"""Production émotionnelle reprenable : prises, assemblage et publication atomique."""
import copy
import json
from pathlib import Path
import time

from audio.speech_verification import IncompleteSpeech
from audio.tts_batch import (Batch, ModelLoadError, atomic_json, atomic_wave, batch_lock,
                            digest, file_hash, read_wave, receipt_matches, receipt_path,
                            write_receipt)
from tools.generate_faithful_audio import assemble


def load_optional(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError,ValueError):
        return None


class StyledRun:
    def __init__(self, *, cache_dir, output_dir, report, voice_sha, model, environment,
                 threads, backend_factory, verifier_factory, verifier_identity,
                 attempts=3, progress=print):
        self.cache_dir,self.output_dir,self.report = map(Path,(cache_dir,output_dir,report))
        self.voice_sha,self.model,self.environment = voice_sha,model,environment
        self.threads,self.attempts = threads,attempts
        self.backend_factory,self.verifier_factory = backend_factory,verifier_factory
        self.verifier_identity = verifier_identity
        self.policy = digest(verifier_identity)
        self.backend,self.verifier = None,None
        self.progress = progress
        self.state = None

    def identity(self, plan):
        # Compatible avec la prise du premier passage déjà approuvée.
        profile = digest(dict(plan=plan,voice=self.voice_sha,model=self.model,
                              environment=self.environment,threads=self.threads,
                              pipeline='faithful-styled-v1'))
        return profile,digest(dict(profile=profile,text=plan['text'],segment_id=plan['segment_id']))

    def preflight(self, plans):
        """Vérifier toutes les sorties avant la première génération."""
        for plan in plans:
            profile,identity = self.identity(plan)
            target = Path(plan['output_file'])
            if target.parent.resolve() != self.output_dir.resolve():
                raise ValueError('Une sortie sort du dossier audio prévu.')
            receipt = load_optional(receipt_path(target))
            pending = load_optional(Path(str(target)+'.pending.json'))
            if isinstance(receipt,dict) and receipt.get('profile') != profile:
                raise ValueError(f"Voix, texte balisé ou réglages différents : {target.name}. "
                                 'Conserver cette série et employer un autre --output-dir.')
            managed = isinstance(pending,dict) and pending.get('identity') == identity
            if target.exists() and not isinstance(receipt,dict) and not managed:
                raise ValueError(f'WAV sans reçu vérifiable : {target.name}. Le déplacer avant de reprendre.')

    def save(self):
        self.state['updated_at'] = time.time()
        atomic_json(self.report,self.state)

    def event(self, **event):
        path = self.cache_dir/'story_events.jsonl'
        with path.open('a',encoding='utf-8') as stream:
            stream.write(json.dumps(dict(time=time.time(),**event),ensure_ascii=False)+'\n')
            stream.flush()

    def speech_verifier(self):
        if self.verifier is None:
            self.verifier = self.verifier_factory()
        return self.verifier

    def component(self, span, plan, round_number):
        parameters = span['parameters']
        def backend_factory():
            if self.backend is None:
                self.progress('Chargement unique de Chatterbox Multilingual V3…')
                self.backend = self.backend_factory(parameters)
            self.backend.parameters = parameters
            return self.backend
        recipe = dict(voice_sha256=self.voice_sha,language='fr',model=self.model,
                      environment=self.environment,device='cpu',parameters=parameters,
                      torch_threads=self.threads,palette_sha256=plan['palette_sha256'])
        batch = Batch(self.cache_dir,recipe,backend_factory,max_chars=plan['chunk_chars'],
                      pause_ms=plan['pause_ms'],seed=(plan['seed']+round_number*104729)%(2**31),
                      attempts=self.attempts,splitter='linguistic-v1',
                      verifier_factory=self.speech_verifier,verifier_identity=self.verifier_identity,
                      progress=self.progress)
        key = digest(dict(text=span['text'],profile=batch.profile))
        target = self.cache_dir/batch.profile/'components'/(key+'.wav')
        stats = batch.run([dict(segment_id=key,scene_id=plan['scene_id'],text=span['text'],target=target)])
        if stats['failed']:
            raise ValueError('Prise refusée après les essais et les découpages de secours ; reprise possible.')
        pcm = read_wave(target)
        return pcm,dict(component=str(target),sha256=file_hash(target),profile=batch.profile,
                        seconds=len(pcm.frames)/2/pcm.sample_rate,stats=stats)

    def generate(self, base, record):
        profile,identity = self.identity(base)
        target = Path(base['output_file'])
        existing = load_optional(receipt_path(target))
        if receipt_matches(target,identity) and existing.get('verification',{}).get('passed') is True \
                and existing['verification'].get('policy') == self.policy:
            pcm = read_wave(target)
            if pcm.frames[:pcm.sample_rate*2] != b'\0'*(pcm.sample_rate*2):
                raise ValueError('Le fichier annoncé prêt ne contient pas la seconde de silence.')
            record.update(status='ready',reused=True,sha256=existing['sha256'],
                          seconds=existing['seconds'],verification=existing['verification'])
            self.progress('Déjà validé : conservé.')
            self.save()
            return
        # La présence du reçu seul ne vaut jamais preuve si la revalidation échoue.
        if existing and existing.get('identity') == identity:
            existing['verification'] = dict(passed=False,policy=self.policy,method='recheck-required')
            atomic_json(receipt_path(target),existing)
        counter = self.cache_dir/'story_attempts'/(identity+'.json')
        previous = load_optional(counter) or {}
        start_round = previous.get('round',0)
        for round_number in range(start_round,start_round+self.attempts):
            # Un crash garde ce même numéro ; seul un refus ASR complet l'avance.
            atomic_json(counter,dict(round=round_number,status='active'))
            record.update(status='generating',round=round_number,spans=copy.deepcopy(base['spans']))
            self.save()
            parts = []
            for number,span in enumerate(record['spans'],1):
                self.progress(f"  Portion {number}/{len(record['spans'])} | {span['speaker']} | {span['emotion']}")
                pcm,details = self.component(span,base,round_number)
                parts.append(pcm)
                span.update(details)
                self.save()
            pcm = assemble(parts,base['lead_in_ms'],base['pause_ms'])
            self.progress('  Contrôle du segment entier, question et deux choix compris…')
            try:
                check = self.speech_verifier().verify(base['text'],pcm,vad_filter=True)
                if check.get('passed') is not True:
                    raise ModelLoadError('Le contrôle complet ne fournit pas de preuve valide.')
            except IncompleteSpeech as exc:
                rejected = self.cache_dir/profile/'rejected_full'/f'round_{round_number}.wav'
                atomic_wave(rejected,pcm)
                atomic_json(receipt_path(rejected),dict(sha256=file_hash(rejected),
                            text=base['text'],verification=exc.report,policy=self.policy))
                atomic_json(counter,dict(round=round_number+1,status='retry-required'))
                record.update(verification=exc.report,rejected_file=str(rejected))
                self.event(segment_id=base['segment_id'],status='full-rejected',round=round_number,
                           reasons=exc.report['reasons'])
                self.save()
                self.progress('  Segment refusé : nouvelles prises avec une autre graine ; les autres segments sont conservés.')
                continue
            check.update(policy=self.policy,method='faster-whisper-small-full-segment-vad')
            if base['lead_in_ms'] != 1000 or pcm.frames[:pcm.sample_rate*2] != b'\0'*(pcm.sample_rate*2):
                raise ValueError('La seconde de silence initial n’est pas conforme.')
            pending = Path(str(target)+'.pending.json')
            atomic_json(pending,dict(identity=identity,profile=profile))
            atomic_wave(target,pcm)
            write_receipt(target,identity,pcm,profile=profile,segment_id=base['segment_id'],
                          text=base['text'],lead_in_ms=1000,verification=check,
                          voice_sha256=self.voice_sha,round=round_number,
                          components=[dict(file=s['component'],sha256=s['sha256'],emotion=s['emotion'],
                                           parameters=s['parameters']) for s in record['spans']])
            pending.unlink(missing_ok=True)
            record.update(status='ready',reused=False,sha256=file_hash(target),verification=check,
                          seconds=len(pcm.frames)/2/pcm.sample_rate)
            self.event(segment_id=base['segment_id'],status='ready',file=str(target))
            self.save()
            return
        raise ValueError('Contrôle intégral refusé après les reprises automatiques ; voir les transcriptions enregistrées.')

    def run(self, plans):
        with batch_lock(self.cache_dir/'.story.lock'),batch_lock(self.output_dir/'.story-output.lock'):
            self.preflight(plans)
            atomic_json(self.report.with_name('audio_plan.json'),dict(segments=plans,
                        dry_run=False,voice_sha256=self.voice_sha,policy=self.policy))
            self.state = dict(status='generating',voice_sha256=self.voice_sha,policy=self.policy,
                              segments=[dict(segment_id=p['segment_id'],scene_id=p['scene_id'],
                                             output_file=p['output_file'],status='pending') for p in plans])
            self.save()
            try:
                for number,(base,record) in enumerate(zip(plans,self.state['segments']),1):
                    self.progress(f"\nSegment {number}/{len(plans)} | {base['title']} | {base['segment_id']}")
                    try:
                        self.generate(base,record)
                    except (ModelLoadError,MemoryError):
                        raise
                    except (ValueError,RuntimeError) as exc:
                        record.update(status='failed',error=str(exc))
                        self.event(segment_id=base['segment_id'],status='failed',error=str(exc))
                        self.progress(f'ÉCHEC : {exc}')
                        self.save()
                failed = sum(s['status'] != 'ready' for s in self.state['segments'])
                self.state.update(status='failed' if failed else 'ready',failed=failed,
                                  ready=len(plans)-failed)
                self.save()
                return 1 if failed else 0
            except KeyboardInterrupt:
                self.state['status'] = 'interrupted'
                self.save()
                raise
            except Exception as exc:
                self.state.update(status='failed',error=str(exc))
                self.save()
                raise
