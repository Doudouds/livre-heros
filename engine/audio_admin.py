"""Catalogue et tâches du panneau PC, sans charger les modèles de voix."""
import copy
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid

from audio.tts_batch import atomic_json, batch_lock, digest, file_hash, read_wave, receipt_matches, receipt_path
from audio.take_history import HISTORY_LIMIT, list_takes
from engine.content import Content, ROOT
from tools.generate_story_audio import parser, plans_for_book


def read_optional(path):
    try:
        value = Content.read(path)
        return value if isinstance(value,dict) else {}
    except (OSError,ValueError):
        return {}


def within(root, path):
    result = Path(path).resolve()
    if not result.is_relative_to(Path(root).resolve()):
        raise ValueError('Ce chemin sort du projet.')
    return result


class AudioInventory:
    def __init__(self, root=ROOT):
        self.root = Path(root).resolve()
        self.cache = {}

    def books(self):
        return {key:book for key,book in Content(self.root).books.items() if book.get('audio_tagged_version') == 1}

    def rows(self, book_id, automatic=False):
        content = Content(self.root)
        if book_id not in self.books():
            raise ValueError('Ce conte doit d’abord être préparé et balisé.')
        args = parser().parse_args(['--book',book_id]+(['--automatic'] if automatic else []))
        configured = content.config.get('book_audio_roots',{}).get(book_id)
        if not configured:
            raise ValueError('Le dossier audio de ce conte n’est pas configuré.')
        args.output_dir = within(self.root,self.root/configured)
        voice = file_hash(self.root/'chatterbox/Recording.wav')
        state = read_optional(self.root/'reports'/book_id/('automatic/generation_status.json' if automatic else 'generation_status.json'))
        records = {r['segment_id']:r for r in state.get('segments',[])}
        latest = read_optional(self.root/'reports/admin/last_job.json')
        if latest.get('intent',{}).get('book_id') == book_id:
            for spec in latest.get('commands',[]):
                if ('--automatic' in spec.get('command',[])) != automatic or not spec.get('report'):
                    continue
                try:
                    targeted = read_optional(within(self.root,spec['report']))
                    records.update({r['segment_id']:r for r in targeted.get('segments',[])})
                except ValueError:
                    continue
        result = []
        for plan in plans_for_book(args,content):
            scene = next(s for s in content.books[book_id]['scenes'] if s['id'] == plan['scene_id'])
            variant = 'Début du conte' if scene['rank'] == 1 else 'Choix 1'
            if not automatic and scene['rank'] > 1:
                previous = content.books[book_id]['scenes'][scene['rank']-2]
                variant = next(('Après le choix '+str(i+1) for i,c in enumerate(previous['choices'])
                                if plan['text'].startswith(c['consequence'])),'Variante')
            elif automatic:
                variant = 'Sans choix'
            status,reason,seconds = self.inspect(plan,voice)
            record = records.get(plan['segment_id'],{})
            if status == 'missing' and record.get('status') in ('failed','needs_synthesis'):
                status,reason = 'failed',record.get('error','Dernière tentative refusée.')
            elif status == 'ready' and record.get('status') == 'failed':
                reason += ' Dernière tentative refusée ; la prise actuelle est conservée.'
            result.append(dict(plan=plan,rank=scene['rank'],variant=variant,status=status,
                               reason=reason,seconds=seconds,automatic=automatic))
        return result

    def inspect(self, plan, voice):
        target = within(self.root,plan['output_file'])
        if not target.is_file():
            return 'missing','Aucun audio produit pour cette variante.',0
        proof_path = receipt_path(target)
        try:
            signature = (target.stat().st_mtime_ns,target.stat().st_size,proof_path.stat().st_mtime_ns,
                         voice,digest(plan))
        except OSError:
            return 'invalid','Reçu de vérification absent.',0
        if self.cache.get(str(target),())[0:1] == (signature,):
            return self.cache[str(target)][1]
        try:
            proof = Content.read(proof_path)
            if not receipt_matches(target,proof['identity']):
                raise ValueError('Fichier audio incomplet ou empreinte différente du reçu.')
            if proof.get('voice_sha256') != voice or proof.get('text') != plan['text']:
                raise ValueError('La référence vocale ou le texte a changé : cette série doit être vérifiée.')
            check = proof.get('verification',{})
            if not check.get('passed') or not check.get('final_review_required') or check.get('review_verifier') != 'Whisper Medium':
                raise ValueError('Vérification finale des paroles requise.')
            if plan['spans'][0].get('role') == 'introduction' and not check.get('introduction_verification',{}).get('passed'):
                raise ValueError('Annonce du titre et de l’auteur à vérifier.')
            parts = proof.get('components',[])
            if len(parts) != len(plan['spans']):
                raise ValueError('Découpage vocal différent du texte actuel.')
            recipes = []
            for span,part in zip(plan['spans'],parts):
                component = within(self.root,part['file'])
                recipe = Content.read(component.parent.parent/'recipe.json')
                if recipe['palette_sha256'] != plan['palette_sha256'] or recipe['parameters'] != span['parameters'] or part['emotion'] != span['emotion']:
                    raise ValueError('Les profils émotionnels ont changé.')
                recipes.append(recipe)
            recipe = recipes[0]
            profile = digest(dict(plan=plan,voice=voice,model=recipe['model'],environment=recipe['environment'],
                                  threads=recipe['torch_threads'],pipeline='faithful-styled-v1'))
            identity = digest(dict(profile=profile,text=plan['text'],segment_id=plan['segment_id']))
            if proof['identity'] != identity:
                raise ValueError('Voix ou réglages différents de cette variante.')
            pcm = read_wave(target)
            if pcm.frames[:pcm.sample_rate*2] != b'\0'*(pcm.sample_rate*2):
                raise ValueError('Seconde de silence initial absente.')
            result = 'ready','Audio vérifié et prêt à écouter.',proof['seconds']
        except (OSError,ValueError,KeyError,TypeError,AttributeError) as exc:
            result = 'invalid',str(exc),0
        self.cache[str(target)] = signature,result
        return result

    def approve_previews(self, book_id):
        first = [self.rows(book_id,mode)[0] for mode in (False,True)]
        if any(row['status']!='ready' for row in first):
            raise ValueError('Les premiers audios des deux modes doivent être générés et vérifiés.')
        proof = dict(book=digest(Content(self.root).books[book_id]),
                     voice=file_hash(self.root/'chatterbox/Recording.wav'),
                     palette=file_hash(self.root/'audio/emotion_profiles.json'),
                     files={row['plan']['output_file']:file_hash(row['plan']['output_file']) for row in first})
        atomic_json(self.root/'reports/admin/approvals'/(book_id+'.json'),proof)

    def previous_versions(self, plan):
        return [Path(v['file']) for v in self.takes(plan) if not v['current']]

    def takes(self, plan):
        current = read_optional(receipt_path(plan['output_file']))
        identity = current.get('identity','')
        if not identity or len(identity)!=64 or any(c not in '0123456789abcdef' for c in identity):
            return []
        cache = self.root/'audio/experiments'/plan['book']/'cache'
        return list_takes(cache,plan['output_file'],identity)[:HISTORY_LIMIT]

    def portion_file(self, plan, number):
        proof = read_optional(receipt_path(plan['output_file']))
        if not receipt_matches(plan['output_file'],proof.get('identity')) or not 1 <= number <= len(proof.get('components',[])):
            raise ValueError('Ce segment ou cette portion n’est plus disponible.')
        part = proof['components'][number-1]
        path = within(self.root,part['file'])
        component = read_optional(receipt_path(path))
        if (file_hash(path)!=part['sha256'] or not component.get('verification',{}).get('passed') or
                not receipt_matches(path,component.get('identity'))):
            raise ValueError('La portion a changé ou son reçu est absent.')
        return path

    def preview_approved(self, book_id):
        book = Content(self.root).books[book_id]
        if not book.get('admin_preview_required'):
            return True
        proof = read_optional(self.root/'reports/admin/approvals'/(book_id+'.json'))
        try:
            return bool(proof.get('book')==digest(book) and proof.get('files') and
                        proof.get('voice')==file_hash(self.root/'chatterbox/Recording.wav') and
                        proof.get('palette')==file_hash(self.root/'audio/emotion_profiles.json') and
                        all(within(self.root,path).is_file() and file_hash(path)==sha for path,sha in proof['files'].items()))
        except (OSError,ValueError,AttributeError):
            return False


def codex_executable():
    found = shutil.which('codex') or shutil.which('codex.exe')
    if found:
        return found
    base = Path(os.environ.get('LOCALAPPDATA',''))/'OpenAI/Codex/bin'
    choices = list(base.glob('*/codex.exe')) if base.is_dir() else []
    return str(max(choices,key=lambda p:p.stat().st_mtime)) if choices else None


def hidden_process_options():
    return dict(creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP) if os.name == 'nt' else dict(start_new_session=True)


class AdminJobs:
    """Un seul travail à la fois ; aucune attente ni inférence sur le thread Tk."""
    def __init__(self, root=ROOT, popen=None):
        self.root = Path(root).resolve()
        self.folder = self.root/'reports/admin'
        self.popen = popen or subprocess.Popen
        self.lock = threading.RLock()
        self.process = None
        self.thread = None
        self.cancelled = threading.Event()
        self.current = read_optional(self.folder/'last_job.json')

    @property
    def busy(self):
        return bool(self.thread and self.thread.is_alive())

    def snapshot(self):
        with self.lock:
            value = copy.deepcopy(self.current)
        if not self.busy and value.get('status') == 'running':
            value['status'] = 'interrupted'
        return value

    def _save(self):
        atomic_json(self.folder/'last_job.json',self.current)
        atomic_json(Path(self.current['folder'])/'job.json',self.current)

    def start_audio(self, book_id, automatic=False, segment_id=None, regenerate=False, both=False, first=False,
                    regeneration_id=None, spans=None, restore_take=None):
        inventory = AudioInventory(self.root)
        if regenerate and not segment_id:
            raise ValueError('Sélectionner un audio pour demander une nouvelle prise.')
        modes = [False,True] if both or first else [automatic]
        rows = {mode:inventory.rows(book_id,mode) for mode in modes}
        if segment_id and not any(r['plan']['segment_id']==segment_id for r in rows[automatic]):
            raise ValueError('La sélection n’appartient pas au conte courant.')
        selected = next((r for r in rows[automatic] if r['plan']['segment_id']==segment_id),None)
        if spans is not None:
            if (not regenerate or not selected or selected['status']!='ready' or not spans or both or first or
                    any(type(n) is not int or not 1 <= n <= len(selected['plan']['spans']) for n in spans)):
                raise ValueError('Sélectionner des portions d’un segment prêt pour cette nouvelle prise.')
            spans = sorted(set(spans))
        if restore_take and (regenerate or not selected or both or first or
                             not any(v['key']==restore_take and not v['current'] for v in inventory.takes(selected['plan']))):
            raise ValueError('Sélectionner une ancienne prise validée de ce segment.')
        if not first and not inventory.preview_approved(book_id):
            first_ids = {values[0]['plan']['segment_id'] for values in rows.values()}
            if not segment_id or segment_id not in first_ids:
                raise ValueError('Écouter puis valider les premiers audios des deux modes avant de compléter ce conte.')
        token = regeneration_id or uuid.uuid4().hex
        intent = dict(kind='audio',book_id=book_id,automatic=automatic,segment_id=segment_id,
                      regenerate=regenerate,both=both,first=first,regeneration_id=token,spans=spans,restore_take=restore_take)
        def specifications(folder):
            specs = []
            for mode in modes:
                command = [sys.executable,str(self.root/'generer_audio_conte.py'),'--book',book_id]
                if mode:
                    command.append('--automatic')
                if segment_id:
                    command += ['--segment-id',segment_id]
                elif first:
                    command += ['--segment','1']
                if regenerate:
                    command += ['--regenerate','--regeneration-id',token]
                for number in spans or []:
                    command += ['--span',str(number)]
                if restore_take:
                    command += ['--restore-take',restore_take]
                report = folder/('automatic' if mode else 'interactive')/'generation_status.json'
                # Une action ciblée ne remplace pas le rapport du lot complet.
                if segment_id or first:
                    command += ['--report',str(report)]
                else:
                    report = self.root/'reports'/book_id/('automatic/generation_status.json' if mode else 'generation_status.json')
                specs.append(dict(command=command,report=str(report)))
            return specs
        label = 'Génération audio'
        if regenerate:
            label = 'Nouvelle prise partielle' if spans else 'Nouvelle prise'
        if restore_take:
            label = 'Restauration d’une prise'
        return self.start(label,intent,specifications)

    def start(self, label, intent, specifications, finish=None):
        if self.busy:
            raise ValueError('Une tâche est déjà en cours.')
        guard = batch_lock(self.folder/'.jobs.lock')
        guard.__enter__()
        try:
            folder = self.folder/'jobs'/uuid.uuid4().hex
            folder.mkdir(parents=True,exist_ok=True)
            specs = specifications(folder)
        except Exception:
            guard.__exit__(*sys.exc_info())
            raise
        self.cancelled.clear()
        self.current = dict(label=label,intent=intent,folder=str(folder),status='running',started=time.time(),
                            commands=specs,command_index=0,log=str(folder/'journal.log'),error='')
        try:
            self._save()
            self.thread = threading.Thread(target=self._run,args=(guard,finish),daemon=True,name='story-admin-job')
            self.thread.start()
        except Exception:
            guard.__exit__(*sys.exc_info())
            raise
        return self.current

    def _run(self, guard, finish):
        failed = []
        try:
            environment = dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONUNBUFFERED='1')
            with Path(self.current['log']).open('ab') as log:
                for index,spec in enumerate(self.current['commands']):
                    if self.cancelled.is_set():
                        break
                    with self.lock:
                        self.current['command_index'] = index
                        self._save()
                    source = open(spec['stdin'],'rb') if spec.get('stdin') else subprocess.DEVNULL
                    try:
                        with self.lock:
                            if self.cancelled.is_set():
                                break
                            self.process = self.popen(spec['command'],cwd=self.root,stdin=source,stdout=log,
                                                      stderr=subprocess.STDOUT,env=environment,**hidden_process_options())
                        code = self.process.wait()
                    finally:
                        if hasattr(source,'close'):
                            source.close()
                    if code:
                        failed.append(f'Tâche {index+1} terminée avec le code {code}. Voir le journal.')
                if self.cancelled.is_set():
                    status = 'stopped'
                elif failed:
                    status = 'failed'
                else:
                    if finish:
                        finish()
                    status = 'succeeded'
            with self.lock:
                self.current.update(status=status,error='\n'.join(failed),finished=time.time())
                self._save()
        except Exception as exc:
            with self.lock:
                self.current.update(status='stopped' if self.cancelled.is_set() else 'failed',error=str(exc),finished=time.time())
                self._save()
        finally:
            self.process = None
            guard.__exit__(None,None,None)

    def stop(self):
        self.cancelled.set()
        with self.lock:
            process = self.process
            if process is not None and process.poll() is None:
                if os.name == 'nt':
                    # Le Python du venv est un redirecteur : arrêter aussi son enfant.
                    subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL,check=False,creationflags=subprocess.CREATE_NO_WINDOW)
                else:
                    os.killpg(process.pid,signal.SIGTERM)

    def resume(self):
        intent = self.snapshot().get('intent',{})
        if intent.get('kind') == 'audio':
            return self.start_audio(**{key:value for key,value in intent.items() if key!='kind'})
        if intent.get('kind') == 'import':
            from engine.story_import import StoryImports
            return StoryImports(self.root).prepare(self,intent['draft'])
        raise ValueError('Aucune tâche à reprendre.')

    def log_tail(self, limit=16000):
        path = self.snapshot().get('log')
        if not path:
            return ''
        try:
            with within(self.root,path).open('rb') as stream:
                stream.seek(max(0,stream.seek(0,2)-limit))
                raw = stream.read().decode('utf-8',errors='replace')
            lines = []
            for line in raw.splitlines():
                try:
                    event = json.loads(line)
                    item = event.get('item',{})
                    line = item.get('text') or event.get('message') or ''
                except (ValueError,AttributeError):
                    pass
                if line and not line.startswith('Sampling:'):
                    lines.append(line)
            return '\n'.join(lines[-100:])
        except OSError:
            return ''
