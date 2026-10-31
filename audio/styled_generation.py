"""Production émotionnelle reprenable : prises, assemblage et publication atomique."""
import copy
import json
from pathlib import Path
import time
import uuid

from audio.speech_verification import IncompleteSpeech, compare_transcript
from audio.take_history import archive_take, prune_takes, read_take
from audio.take_tones import effective_spans, effective_profile, receipt_tones
from audio.tts_batch import (Batch, PCM, ModelLoadError, atomic_json, atomic_wave, batch_lock,
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
                 attempts=3, progress=print, recheck_only=False, regenerate_ids=None, regeneration_id=None,
                 regenerate_spans=None, restore_take=None, emotion=None, palette=None):
        self.cache_dir,self.output_dir,self.report = map(Path,(cache_dir,output_dir,report))
        self.voice_sha,self.model,self.environment = voice_sha,model,environment
        self.threads,self.attempts = threads,attempts
        self.recheck_only = recheck_only
        self.regenerate_ids = set(regenerate_ids or [])
        self.regeneration_id = regeneration_id
        self.regenerate_spans = set(regenerate_spans) if regenerate_spans is not None else None
        self.restore_take = restore_take
        self.emotion,self.palette = emotion,palette or {}
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
        if self.regenerate_spans is not None:
            if (not self.regenerate_spans or len(plans)!=1 or not self.regenerate_ids or self.recheck_only
                    or any(type(n) is not int or not 0 <= n < len(plans[0]['spans']) for n in self.regenerate_spans)):
                raise ValueError('Sélection de portions invalide pour cette nouvelle prise.')
        if self.restore_take and (len(plans)!=1 or self.regenerate_ids or self.recheck_only):
            raise ValueError('La restauration exige un seul segment, sans synthèse ni réécoute seule.')
        if self.emotion is not None and (self.regenerate_spans is None or self.emotion not in ('default',*self.palette)):
            raise ValueError('Choisir un ton approuvé et les portions à reprendre.')
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
            if isinstance(receipt,dict):
                receipt_tones(plan,receipt,self.palette)
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

    def verify_full(self, base, pcm, tail_frames, intro_frames=None, narration_tail_frames=None):
        verifier = self.speech_verifier()
        cached = None
        if base['spans'][-1].get('role') == 'choix':
            profile,_ = self.identity(base)
            for path in (self.cache_dir/profile/'rejected_full').glob('*.wav.json'):
                proof = load_optional(path) or {}
                wav = path.with_suffix('')
                try:
                    compare_transcript(base['text'],proof.get('verification',{}).get('transcript',''))
                except IncompleteSpeech as doubt:
                    whole_doubt = self.choice_only_doubt(doubt.report)
                else:
                    whole_doubt = False
                if (proof.get('policy') == self.policy and proof.get('text') == base['text']
                        and whole_doubt and self.choice_only_doubt(proof.get('verification',{})) and wav.is_file()
                        and proof.get('sha256') == file_hash(wav) and read_wave(wav) == pcm):
                    cached = proof['verification']
                    break
        try:
            if cached is not None:
                raise IncompleteSpeech(cached)
            if hasattr(verifier,'verify_complete'):
                check = verifier.verify_complete(base['text'],pcm,
                          tail_text=base['spans'][-1]['text'],tail_frames=tail_frames)
            else:
                check = verifier.verify(base['text'],pcm,vad_filter=True)
        except IncompleteSpeech as exc:
            if not self.choice_only_doubt(exc.report) or base['spans'][-1].get('role') != 'choix':
                raise
            last = base['spans'][-1]['text']
            if not base['text'].endswith(last) or not 0 < tail_frames < len(pcm.frames):
                raise ValueError('Découpage des annonces incorrect.')
            reviewer = verifier.reviewer() if hasattr(verifier,'reviewer') else verifier
            head_text = base['text'][:-len(last)].strip()
            head_pcm = PCM(pcm.sample_rate,pcm.frames[:-tail_frames])
            try:
                head_check = reviewer.verify(head_text,head_pcm,vad_filter=True)
            except IncompleteSpeech as head_error:
                if head_error.report.get('reasons') != ['fin du texte non retrouvée'] or not narration_tail_frames:
                    head_error.report.update(scope='narration')
                    raise
                # Le WAV narratif se termine par la pause avant les choix.
                # Relire sa vraie dernière portion, pause comprise, sans enlever
                # de mots de la transcription ni toucher aux seuils.
                frames = narration_tail_frames+pcm.sample_rate*2*base['pause_ms']//1000
                if not 0 < frames <= len(head_pcm.frames):
                    raise ValueError('Découpage de la fin narrative invalide.')
                try:
                    head_tail = reviewer.verify(base['spans'][-2]['text'],
                                               PCM(pcm.sample_rate,head_pcm.frames[-frames:]),vad_filter=True)
                except IncompleteSpeech as tail_error:
                    tail_error.report.update(scope='narration_tail',affected_spans=[len(base['spans'])-2])
                    raise
                head_check = dict(head_error.report,passed=True,reasons=[],tail_matched=True,
                                  method='full-and-tail',global_check=head_error.report,tail_check=head_tail,tail_frames=frames)
            try:
                tail_check = reviewer.verify(last,PCM(pcm.sample_rate,pcm.frames[-tail_frames:]),vad_filter=True)
            except IncompleteSpeech as tail_error:
                tail_error.report.update(scope='choices',affected_spans=[len(base['spans'])-1])
                raise
            check = dict(exc.report,passed=True,reasons=[],choices_matched=True,tail_matched=True,
                         method='full-and-choices',global_check=exc.report,head_check=head_check,
                         tail_check=tail_check,tail_frames=tail_frames,head_frames=len(pcm.frames)-tail_frames,
                         final_review_required=True)
            if head_check.get('method') == 'full-and-tail':
                check.update(head_tail_text=base['spans'][-2]['text'],head_tail_frames=head_check['tail_frames'])
        if check.get('passed') is not True:
            raise ModelLoadError('Le contrôle complet ne fournit pas de preuve valide.')
        if base['spans'][0].get('role') == 'introduction':
            if not intro_frames:
                raise ModelLoadError('Échantillons de l’introduction absents.')
            start = pcm.sample_rate*2
            reviewer = verifier.reviewer() if hasattr(verifier,'reviewer') else verifier
            try:
                intro_check = reviewer.verify(base['spans'][0]['text'],PCM(pcm.sample_rate,pcm.frames[start:start+intro_frames]))
            except IncompleteSpeech as exc:
                exc.report.update(scope='introduction',affected_spans=[0])
                raise
            check['introduction_verification'] = intro_check
        check.update(policy=self.policy,method=check.get('method','faster-whisper-full-segment-vad'))
        return check

    @staticmethod
    def choice_only_doubt(check):
        reason = 'annonce des choix absente, répétée ou dans le mauvais ordre'
        return (reason in check.get('reasons',[]) and check.get('word_error_rate',1) <= .15
                and set(check['reasons']).issubset({reason,'fin du texte non retrouvée'}))

    def component(self, span, plan, round_number):
        parameters = span['parameters']
        rules = span.get('pronunciations',[])
        def backend_factory():
            if self.backend is None:
                self.progress('Initialisation de la synthèse Chatterbox Multilingual V3…')
                self.backend = self.backend_factory(parameters)
            self.backend.parameters = parameters
            if rules:
                from audio.pronunciation import PronouncingBackend
                return PronouncingBackend(self.backend,rules)
            return self.backend
        recipe = dict(voice_sha256=self.voice_sha,language='fr',model=self.model,
                      environment=self.environment,device='cpu',parameters=parameters,
                      torch_threads=self.threads,palette_sha256=plan['palette_sha256'])
        if rules:
            from audio.pronunciation import pronunciation_identity
            recipe['pronunciation'] = pronunciation_identity(rules)
        intro = span.get('role') == 'introduction'
        def component_verifier():
            verifier = self.speech_verifier()
            if intro and hasattr(verifier,'reviewer'):
                class IntroReviewer:
                    def verify(self, expected, pcm, **options):
                        return verifier.reviewer().verify(expected,pcm,**options)
                return IntroReviewer()
            return verifier
        validation = dict(controller=self.verifier_identity,scope='introduction-medium-v1') if intro else self.verifier_identity
        batch = Batch(self.cache_dir,recipe,backend_factory,max_chars=plan['chunk_chars'],
                      pause_ms=plan['pause_ms'],seed=(plan['seed']+round_number*104729)%(2**31),
                      attempts=self.attempts,splitter='linguistic-v1',
                      verifier_factory=component_verifier,verifier_identity=validation,
                      progress=self.progress,allow_synthesis=not self.recheck_only)
        key = digest(dict(text=span['text'],profile=batch.profile))
        target = self.cache_dir/batch.profile/'components'/(key+'.wav')
        stats = batch.run([dict(segment_id=key,scene_id=plan['scene_id'],text=span['text'],target=target)])
        if stats['failed']:
            if self.recheck_only:
                raise ValueError('Réécoute seule : cette portion n’a aucune prise validée en cache ; une synthèse reste nécessaire.')
            raise ValueError('Prise refusée après les essais et les découpages de secours ; reprise possible.')
        pcm = read_wave(target)
        return pcm,dict(component=str(target),sha256=file_hash(target),profile=batch.profile,
                        seconds=len(pcm.frames)/2/pcm.sample_rate,stats=stats)

    def generate(self, base, record):
        profile,identity = self.identity(base)
        target = Path(base['output_file'])
        existing = load_optional(receipt_path(target))
        if self.restore_take:
            return self.restore(base,record,existing)
        counter = self.cache_dir/'story_attempts'/(identity+'.json')
        previous = load_optional(counter) or {}
        forced = base['segment_id'] in self.regenerate_ids
        requested = self.regeneration_id or (previous.get('regeneration_request') if previous.get('status') != 'ready' else None)
        if forced and requested and existing and existing.get('regeneration_request') == requested:
            forced = False
        if not forced and receipt_matches(target,identity) and existing.get('verification',{}).get('passed') is True:
            pcm = read_wave(target)
            if pcm.frames[:pcm.sample_rate*2] != b'\0'*(pcm.sample_rate*2):
                raise ValueError('Le fichier annoncé prêt ne contient pas la seconde de silence.')
            same_policy = existing['verification'].get('policy') == self.policy
            has_intro = base['spans'][0].get('role') == 'introduction'
            valid = same_policy and (not has_intro or existing['verification'].get('introduction_verification',{}).get('passed') is True)
            if not same_policy:
                self.progress('Audio intègre déjà produit : nouvelle vérification du fichier original, sans le resynthétiser.')
                last = (existing.get('components') or [])[-1:]
                tail_frames = len(pcm.frames)
                if last:
                    component = Path(last[0]['file'])
                    if component.is_file() and file_hash(component) == last[0]['sha256']:
                        tail = read_wave(component)
                        if pcm.frames.endswith(tail.frames):
                            tail_frames = len(tail.frames)
                try:
                    intro_frames = len(read_wave(existing['components'][0]['file']).frames) if has_intro else None
                    narration_frames = None
                    components = existing.get('components',[])
                    if len(components)>1:
                        previous_part = components[-2]
                        path = Path(previous_part['file'])
                        if path.is_file() and file_hash(path)==previous_part['sha256']:
                            narration_frames = len(read_wave(path).frames)
                    check = self.verify_full(base,pcm,tail_frames,intro_frames,narration_frames)
                except IncompleteSpeech as exc:
                    record['reverification_rejection'] = exc.report
                else:
                    existing['previous_verification'] = existing['verification']
                    existing['verification'] = check
                    atomic_json(receipt_path(target),existing)
                    valid = True
            if valid:
                record.update(status='ready',reused=True,sha256=existing['sha256'],
                              seconds=existing['seconds'],verification=existing['verification'],
                              span_rounds=existing.get('span_rounds',[]))
                self.progress('Validé : fichier original conservé.')
                self.save()
                return
        # La présence du reçu seul ne vaut jamais preuve si la revalidation échoue.
        if not forced and existing and existing.get('identity') == identity:
            existing['verification'] = dict(passed=False,policy=self.policy,method='recheck-required')
            atomic_json(receipt_path(target),existing)
        start_round = previous.get('round',0)
        old_records = {r['segment_id']:r for r in getattr(self,'previous_state',{}).get('segments',[])}
        if previous.get('policy') != self.policy:
            # Réécouter les dernières prises sauvegardées avant de demander une
            # nouvelle voix : un changement de contrôleur n'invalide pas le TTS.
            start_round = old_records.get(base['segment_id'],{}).get('round',(existing or {}).get('round',0))
            span_rounds = (old_records.get(base['segment_id'],{}).get('span_rounds')
                           or (existing or {}).get('span_rounds') or [start_round]*len(base['spans']))
        else:
            span_rounds = previous.get('span_rounds',[start_round]*len(base['spans']))
        regeneration = {}
        source_parts = None
        tones = receipt_tones(base,existing,self.palette) if existing else {}
        if self.emotion is not None:
            for number in self.regenerate_spans:
                if self.emotion=='default' or self.emotion==base['spans'][number]['emotion']:
                    tones.pop(str(number),None)
                else:
                    tones[str(number)] = self.emotion
        if forced:
            requested = requested or uuid.uuid4().hex
            continuing = previous.get('regeneration_request') == requested
            selected = sorted(self.regenerate_spans) if self.regenerate_spans is not None else None
            if continuing and previous.get('regenerated_spans') != selected:
                raise ValueError('Cette demande interrompue portait sur une autre sélection de portions.')
            if not continuing:
                used = [start_round,(existing or {}).get('round',0),*(existing or {}).get('span_rounds',[]),
                        *previous.get('span_rounds',[])]
                start_round = max(used)+1
                span_rounds = [start_round]*len(base['spans'])
            regeneration = dict(regeneration_request=requested)
            if continuing:
                if previous.get('requested_emotion') != self.emotion:
                    raise ValueError('Cette demande interrompue utilisait un autre ton.')
                tones = previous.get('tone_overrides',{})
            regeneration.update(tone_overrides=tones,requested_emotion=self.emotion)
            if selected is not None:
                if continuing:
                    source_key = previous.get('regeneration_source')
                else:
                    if not existing or not receipt_matches(target,identity):
                        raise ValueError('Une reprise partielle exige un segment actuel intègre et validé.')
                    source_key = archive_take(self.cache_dir,target,identity,existing)
                source_path,source = read_take(self.cache_dir,identity,source_key)
                source_parts = self.cached_components(base,source)
                if read_wave(source_path) != assemble([part[0] for part in source_parts],base['lead_in_ms'],base['pause_ms']):
                    raise ValueError('Les composants ne reproduisent pas la version actuellement en service.')
                if not continuing:
                    old_rounds = source.get('span_rounds',[source.get('round',0)]*len(base['spans']))
                    span_rounds = [start_round if n in self.regenerate_spans else old_rounds[n]
                                   for n in range(len(base['spans']))]
                regeneration.update(regenerated_spans=selected,regeneration_source=source_key)
            record['regeneration_request'] = requested
            self.progress('Nouvelle prise demandée ; la version actuelle reste disponible jusqu’à validation.')
        for round_number in range(start_round,start_round+self.attempts):
            # Un crash garde ce même numéro ; seul un refus ASR complet l'avance.
            atomic_json(counter,dict(round=round_number,status='active',policy=self.policy,span_rounds=span_rounds,**regeneration))
            record.update(status='generating',stage='portions',round=round_number,span_rounds=list(span_rounds),
                          spans=effective_spans(base,tones,self.palette))
            self.save()
            parts = []
            for number,span in enumerate(record['spans'],1):
                kept = source_parts is not None and number-1 not in self.regenerate_spans
                span['status'] = 'kept' if kept else 'generating'
                record['active_portion'] = number-1
                self.save()
                self.progress(f"  Portion {number}/{len(record['spans'])} | {span['speaker']} | {span['emotion']}")
                if kept:
                    pcm,details = source_parts[number-1]
                    self.progress('    Portion conservée à l’identique.')
                else:
                    try:
                        pcm,details = self.component(span,base,span_rounds[number-1])
                    except Exception as exc:
                        span.update(status='failed',error=str(exc))
                        self.save()
                        raise
                parts.append(pcm)
                span.update(details)
                span['status'] = 'kept' if kept else 'generated'
                self.save()
            pcm = assemble(parts,base['lead_in_ms'],base['pause_ms'])
            record.update(stage='verification',active_portion=None)
            for span in record['spans']:
                if span['status']=='generated':
                    span['status'] = 'checking'
            self.save()
            self.progress('  Contrôle du segment entier, question et deux choix compris…'
                          if any(s.get('role') == 'choix' for s in base['spans'])
                          else '  Contrôle de la narration complète…')
            try:
                check = self.verify_full(base,pcm,len(parts[-1].frames),len(parts[0].frames),
                                         len(parts[-2].frames) if len(parts)>1 else None)
            except IncompleteSpeech as exc:
                rejected = self.cache_dir/profile/'rejected_full'/f'round_{round_number}_{self.policy[:12]}.wav'
                atomic_wave(rejected,pcm)
                atomic_json(receipt_path(rejected),dict(sha256=file_hash(rejected),
                            text=base['text'],verification=exc.report,policy=self.policy))
                record.update(verification=exc.report,rejected_file=str(rejected))
                for span in record['spans']:
                    if span.get('status')=='checking':
                        span['status'] = 'assembly_failed'
                self.event(segment_id=base['segment_id'],status='full-rejected',round=round_number,
                           reasons=exc.report['reasons'])
                self.save()
                self.progress('  Contrôle global refusé : '+ '; '.join(exc.report['reasons']))
                if exc.report.get('affected_spans'):
                    affected = exc.report['affected_spans']
                elif exc.report['reasons'] == ['fin du texte non retrouvée'] and exc.report.get('scope') != 'narration':
                    affected = [len(parts)-1]
                else:
                    affected = []
                    for number,(span,part) in enumerate(zip(record['spans'],parts)):
                        try:
                            self.speech_verifier().verify(span['text'],part,vad_filter=True)
                        except IncompleteSpeech:
                            affected.append(number)
                    if not affected:
                        raise ValueError('Contrôle global incertain : toutes les portions isolées sont validées. '
                                         'Prises conservées pour réécoute ; aucune régénération intégrale automatique.')
                for number in affected:
                    if source_parts is not None and number not in self.regenerate_spans:
                        raise ValueError('Le contrôle réclame une portion hors sélection. Aucun remplacement publié ; '
                                         'élargir la sélection ou réécouter le segment actuel.')
                    span_rounds[number] += 1
                atomic_json(counter,dict(round=round_number+1,status='retry-required',
                                         policy=self.policy,span_rounds=span_rounds,**regeneration))
                self.progress('  Nouvelle prise seulement pour la ou les portions '+
                              ', '.join(str(i+1) for i in affected)+'. Les autres sont conservées.')
                continue
            check.update(policy=self.policy,method=check.get('method','faster-whisper-small-full-segment-vad'))
            self.publish_take(base,record,pcm,check,existing,
                              dict(round=round_number,span_rounds=list(span_rounds),created_at=time.time(),
                                   effective_profile=effective_profile(profile,tones),tone_overrides=tones,
                                   **{k:v for k,v in regeneration.items() if k!='tone_overrides'}))
            if forced:
                atomic_json(counter,dict(round=round_number,status='ready',policy=self.policy,
                                         span_rounds=span_rounds,**regeneration))
            record.update(status='ready',reused=False,sha256=file_hash(target),verification=check,
                          seconds=len(pcm.frames)/2/pcm.sample_rate)
            for span in record['spans']:
                span['status'] = 'ready'
            self.event(segment_id=base['segment_id'],status='ready',file=str(target))
            self.save()
            return
        raise ValueError('Contrôle intégral refusé après les reprises automatiques ; voir les transcriptions enregistrées.')

    def cached_components(self, base, proof):
        """Lire les octets de la version choisie, sans synthèse de remplacement."""
        if proof.get('identity') != self.identity(base)[1] or len(proof.get('components',[])) != len(base['spans']):
            raise ValueError('La prise source ne correspond pas au découpage de ce segment.')
        result = []
        spans = effective_spans(base,receipt_tones(base,proof,self.palette),self.palette)
        for span,part in zip(spans,proof['components']):
            path = Path(part['file'])
            if not path.resolve().is_relative_to(self.cache_dir.resolve()):
                raise ValueError('Un composant sort du cache de ce conte.')
            component = load_optional(receipt_path(path)) or {}
            recipe = load_optional(path.parent.parent/'recipe.json') or {}
            if (not component.get('verification',{}).get('passed') or
                    not receipt_matches(path,component.get('identity')) or file_hash(path) != part['sha256'] or
                    digest(recipe) != path.parent.parent.name or component.get('profile') != path.parent.parent.name or
                    any(recipe.get(k)!=v for k,v in dict(voice_sha256=self.voice_sha,model=self.model,
                        environment=self.environment,torch_threads=self.threads,parameters=span['parameters'],palette_sha256=base['palette_sha256']).items()) or
                    part['emotion'] != span['emotion'] or part['parameters'] != span['parameters'] or
                    path.stem != digest(dict(text=span['text'],profile=component.get('profile')))):
                raise ValueError('Composant absent, modifié ou incompatible ; reprise partielle refusée sans refaire le reste.')
            pcm = read_wave(path)
            result.append((pcm,dict(component=str(path),sha256=part['sha256'],profile=component['profile'],
                                    seconds=len(pcm.frames)/2/pcm.sample_rate,reused=True)))
        return result

    def publish_take(self, base, record, pcm, check, existing, metadata):
        profile,identity = self.identity(base)
        target = Path(base['output_file'])
        if base['lead_in_ms'] != 1000 or pcm.frames[:pcm.sample_rate*2] != b'\0'*(pcm.sample_rate*2):
            raise ValueError('La seconde de silence initial n’est pas conforme.')
        if existing and existing.get('verification',{}).get('passed') and receipt_matches(target,identity):
            archive_take(self.cache_dir,target,identity,existing)
        pending = Path(str(target)+'.pending.json')
        atomic_json(pending,dict(identity=identity,profile=profile))
        atomic_wave(target,pcm)
        write_receipt(target,identity,pcm,profile=profile,segment_id=base['segment_id'],
                      text=base['text'],lead_in_ms=1000,verification=check,voice_sha256=self.voice_sha,**metadata,
                      components=[dict(file=s['component'],sha256=s['sha256'],emotion=s['emotion'],
                                       parameters=s['parameters']) for s in record['spans']])
        pending.unlink(missing_ok=True)
        archive_take(self.cache_dir,target,identity,load_optional(receipt_path(target)))
        prune_takes(self.cache_dir,target,identity)

    def restore(self, base, record, existing):
        _,identity = self.identity(base)
        path,proof = read_take(self.cache_dir,identity,self.restore_take)
        parts = self.cached_components(base,proof)
        pcm = read_wave(path)
        if pcm != assemble([p[0] for p in parts],base['lead_in_ms'],base['pause_ms']):
            raise ValueError('La prise historique ne correspond pas à ses portions.')
        self.progress('Restauration : nouveau contrôle intégral de la prise historique, sans synthèse.')
        check = self.verify_full(base,pcm,len(parts[-1][0].frames),len(parts[0][0].frames),
                                 len(parts[-2][0].frames) if len(parts)>1 else None)
        spans = effective_spans(base,receipt_tones(base,proof,self.palette),self.palette)
        record['spans'] = [dict(span,**part[1],status='ready') for span,part in zip(spans,parts)]
        metadata = {key:proof[key] for key in ('round','span_rounds','regeneration_request','regenerated_spans','created_at','tone_overrides','effective_profile') if key in proof}
        metadata.update(restored_from=self.restore_take,restored_at=time.time())
        self.publish_take(base,record,pcm,check,existing,metadata)
        record.update(status='ready',reused=False,sha256=file_hash(base['output_file']),verification=check,
                      seconds=len(pcm.frames)/2/pcm.sample_rate)
        self.event(segment_id=base['segment_id'],status='restored',take=self.restore_take)
        self.save()

    def run(self, plans):
        with batch_lock(self.cache_dir/'.story.lock'),batch_lock(self.output_dir/'.story-output.lock'):
            self.preflight(plans)
            self.previous_state = load_optional(self.report) or {}
            if self.previous_state.get('policy') and self.previous_state['policy'] != self.policy:
                backup = self.report.with_name('generation_before_'+self.previous_state['policy'][:12]+'.json')
                if not backup.exists():
                    atomic_json(backup,self.previous_state)
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
                        record.update(status='needs_synthesis' if self.recheck_only else 'failed',error=str(exc))
                        self.event(segment_id=base['segment_id'],status='failed',error=str(exc))
                        self.progress(('À compléter : ' if self.recheck_only else 'ÉCHEC : ')+str(exc))
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
