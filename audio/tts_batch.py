"""Production reprenable de WAV. Bibliothèque standard ; aucun modèle au runtime du jeu."""
import hashlib
import json
import os
import re
import time
import wave
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path

from engine.content import segment_id

PIPELINE_VERSION = 1


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode('utf-8')).hexdigest()


def file_hash(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.partial')
    with temporary.open('w', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def split_text(text, max_chars=380):
    """Garder les paragraphes et les phrases ; découper une phrase longue aux mots."""
    if type(max_chars) is not int or not 80 <= max_chars <= 1000:
        raise ValueError('La taille des passages doit être comprise entre 80 et 1000 caractères.')
    chunks = []
    for paragraph in re.split(r'\n\s*\n', text.strip()):
        paragraph = ' '.join(paragraph.split())
        current = ''
        for sentence in re.split(r'(?<=[.!?])\s+', paragraph):
            words = sentence.split()
            pieces, part = [], ''
            for word in words:
                if len(word) > max_chars:
                    raise ValueError('Un mot dépasse la limite d’un passage TTS.')
                if len(part) + len(word) + bool(part) > max_chars:
                    pieces.append(part)
                    part = ''
                part += (' ' if part else '') + word
            if part:
                pieces.append(part)
            for piece in pieces:
                if current and len(current) + 1 + len(piece) > max_chars:
                    chunks.append(current)
                    current = ''
                current += (' ' if current else '') + piece
        if current:
            chunks.append(current)
    if not chunks:
        raise ValueError('Texte vide.')
    return chunks


def split_linguistic(text, max_chars=300):
    """Phrases d'abord, puis ;/: et enfin espaces ; aucun mot supprimé.

    Les paragraphes appartiennent au même texte logique. La limite est stricte,
    donc une phrase indivisible trop longue doit exceptionnellement être coupée.
    """
    split_text('Validation.', max_chars)
    text = ' '.join(text.split())
    if not text:
        raise ValueError('Texte vide.')
    endings = re.compile(r'[.!?…]+(?:\s*[»”"\)\]])*(?=\s|$)')
    abbreviations = {'m', 'mme', 'mlle', 'dr', 'pr', 'st', 'ste', 'etc', 'cf', 'ex'}
    sentences, start = [], 0
    for match in endings.finditer(text):
        if match.group() == '.':
            last_word = re.search(r'(\w+)$', text[:match.start()])
            if last_word and (last_word[1].lower() in abbreviations or
                              (len(last_word[1]) == 1 and last_word[1].isupper())):
                continue
        sentences.append(text[start:match.end()].strip())
        start = match.end()
    if text[start:].strip():
        sentences.append(text[start:].strip())
    chunks, current = [], ''
    for sentence in sentences:
        pieces = []
        while len(sentence) > max_chars:
            # Garder ; et : avec la proposition qu'ils terminent. Ne pas
            # confondre une ponctuation interne (URL, heure) avec une frontière.
            soft = list(re.finditer(r'[;:](?=\s)', sentence[:max_chars + 1]))
            boundary = soft[-1].end() if soft and soft[-1].end() <= max_chars else sentence.rfind(' ', 0, max_chars + 1)
            if boundary <= 0:
                raise ValueError('Un mot dépasse la limite d’un passage TTS.')
            pieces.append(sentence[:boundary].strip())
            sentence = sentence[boundary:].strip()
        if sentence:
            pieces.append(sentence)
        for piece in pieces:
            if current and len(current) + 1 + len(piece) > max_chars:
                chunks.append(current)
                current = ''
            current += (' ' if current else '') + piece
    if current:
        chunks.append(current)
    if ' '.join(chunks) != text:
        raise ValueError('Le découpage a altéré le texte.')
    return chunks


def whole_text(text, max_chars):
    """Témoin expérimental : un seul appel, volontairement sans limite."""
    text = ' '.join(text.split())
    if not text:
        raise ValueError('Texte vide.')
    return [text]


SPLITTERS = {'paragraph-sentence-v1': split_text,
             'linguistic-v1': split_linguistic, 'whole-text-v1': whole_text}


def recovery_parts(text):
    """Couper à une vraie frontière de phrase/proposition, jamais au nombre de caractères."""
    text = ' '.join(text.split())
    dangling = {'de','du','des','à','au','aux','et','ou','ni','que','qui','dont','si',
                'quand','comme','un','une','le','la','les','son','sa','ses','leur','leurs',
                'pour','sans','avec','dans','sur','sous','en'}
    candidates = []
    for match in re.finditer(r'[.!?…;:]+(?:\s*[»”"\)\]])*(?=\s|$)',text):
        left,right = text[:match.end()].strip(),text[match.end():].strip()
        if not right:
            continue
        punctuation = match.group()[0]
        minimum_right = 6 if punctuation in '.!?…' or right.startswith(('«','“','"')) else 8
        minimum_left = 6 if punctuation in '.!?…' else 8
        if len(left.split()) < minimum_left or len(right.split()) < minimum_right:
            continue
        last = re.search(r"([\w’']+)[^\w]*$",left)
        if last and (last[1].lower() in dangling or last[1].lower() in {'m','mme','mlle','dr','etc'}):
            continue
        candidates.append((abs(len(left)-len(right))+(0 if punctuation in '.!?…' else 50),left,right))
    if not candidates:
        return [text]
    _,left,right = min(candidates,key=lambda item:item[0])
    if left+' '+right != text:
        raise ValueError('Le découpage de secours a modifié les paroles.')
    return [left,right]


def read_manifest(path, project_root, output_dir=None):
    root = Path(project_root).resolve()
    output_root = Path(output_dir).resolve() if output_dir else root
    records, seen = [], {}
    with Path(path).open(encoding='utf-8-sig') as stream:
        for line_number, line in enumerate(stream, 1):
            try:
                record = json.loads(line)
                text = record['text']
                key = record['segment_id']
                if not isinstance(text, str) or not text.strip() or '{' in text or '}' in text:
                    raise ValueError('Texte vide ou substitution non résolue.')
                if key != segment_id(record['scene_id'], record['role'], text):
                    raise ValueError('Identifiant incohérent avec le texte ; réexporter le manifeste.')
                if not re.fullmatch(r'[A-Za-z0-9_-]+', key):
                    raise ValueError('Identifiant audio non sûr.')
                target = (output_root / (key + '.wav') if output_dir else root / record['output_file']).resolve()
                if not target.is_relative_to(output_root) or target.name != key + '.wav':
                    raise ValueError('Le fichier audio doit rester dans le dossier prévu avec le nom du segment.')
                if target in seen:
                    if seen[target] != text:
                        raise ValueError('Deux textes différents visent le même WAV.')
                    continue
                seen[target] = text
                records.append({**record, 'target': target})
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f'Manifeste, ligne {line_number} : {exc}') from exc
    if not records:
        raise ValueError('Le manifeste ne contient aucun segment.')
    return records


@dataclass(frozen=True)
class PCM:
    sample_rate: int
    frames: bytes

    def validate(self):
        if type(self.sample_rate) is not int or not 8000 <= self.sample_rate <= 192000:
            raise ValueError('Fréquence WAV invalide.')
        if not isinstance(self.frames, bytes) or len(self.frames) % 2 or len(self.frames) < self.sample_rate // 10:
            raise ValueError('Audio mono PCM16 vide ou trop court.')


def atomic_wave(path, pcm):
    pcm.validate()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.partial')
    with temporary.open('wb') as stream:
        with wave.open(stream, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(pcm.sample_rate)
            wav.writeframes(pcm.frames)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def read_wave(path):
    with wave.open(str(path), 'rb') as wav:
        if wav.getnchannels() != 1 or wav.getsampwidth() != 2 or wav.getcomptype() != 'NONE':
            raise ValueError('Format attendu : mono PCM16 sans compression.')
        count = wav.getnframes()
        pcm = PCM(wav.getframerate(), wav.readframes(count))
        if len(pcm.frames) != count * 2:
            raise ValueError('WAV tronqué.')
    pcm.validate()
    return pcm


def receipt_path(path):
    return Path(str(path) + '.json')


def receipt_matches(path, expected):
    try:
        receipt = json.loads(receipt_path(path).read_text(encoding='utf-8'))
        if not isinstance(receipt, dict) or receipt.get('identity') != expected or receipt.get('sha256') != file_hash(path):
            return False
        read_wave(path)
        return True
    except (OSError, ValueError, EOFError, wave.Error):
        return False


def write_receipt(path, identity, pcm, **extra):
    atomic_json(receipt_path(path), dict(identity=identity, sha256=file_hash(path),
                                        sample_rate=pcm.sample_rate, frames=len(pcm.frames)//2,
                                        seconds=round(len(pcm.frames)/2/pcm.sample_rate, 3), **extra))


@contextmanager
def batch_lock(path):
    """Verrou système libéré même si Python est tué ; pas de verrou PID périmé."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = path.open('a+b')
    locked = False
    try:
        if stream.seek(0, 2) == 0:
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
        except OSError as exc:
            raise RuntimeError('Une autre génération utilise ce dossier. Attendre sa fin.') from exc
        yield
    finally:
        if locked:
            stream.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        stream.close()


class ModelLoadError(RuntimeError):
    pass


class Batch:
    def __init__(self, cache_dir, recipe, synthesizer_factory, *, max_chars=380,
                 pause_ms=160, seed=20261003, overwrite=False, progress=print,
                 verifier_factory=None, verifier_identity=None, attempts=3,
                 splitter='paragraph-sentence-v1', allow_synthesis=True):
        if type(pause_ms) is not int or not 0 <= pause_ms <= 3000:
            raise ValueError('Pause invalide.')
        split_text('Validation.', max_chars)
        if type(attempts) is not int or not 1 <= attempts <= 10:
            raise ValueError('Prévoir entre 1 et 10 tentatives par passage.')
        if verifier_factory is not None and not verifier_identity:
            raise ValueError('Le contrôleur des paroles doit avoir une identité de validation.')
        if splitter not in SPLITTERS:
            raise ValueError('Méthode de découpage inconnue.')
        self.splitter = SPLITTERS[splitter]
        self.cache_dir = Path(cache_dir)
        self.recipe = {**recipe, 'pipeline': PIPELINE_VERSION, 'splitter': splitter,
                       'max_chars': max_chars, 'pause_ms': pause_ms, 'seed': seed, 'pcm': 'mono-s16le'}
        self.profile = digest(self.recipe)
        self.factory, self.synthesizer = synthesizer_factory, None
        self.verifier_factory, self.verifier = verifier_factory, None
        self.verifier_identity = verifier_identity
        self.validation_id = digest(verifier_identity) if verifier_factory else None
        self.attempts = attempts
        self.allow_synthesis = allow_synthesis
        self.failed_chunks = {}
        self.overwrite, self.progress = overwrite, progress
        self.stats = {'generated': 0, 'skipped': 0, 'failed': 0, 'chunks_generated': 0, 'chunks_reused': 0,
                      'retry_attempts':0, 'fallback_splits':0, 'speech_checks':0}

    def identity(self, record):
        return digest({'profile': self.profile, 'text': record['text'], 'segment_id': record['segment_id']})

    def preflight(self, records):
        # Refuser le mélange de voix avant de modifier le premier fichier.
        for record in records:
            path = record['target']
            try:
                receipt = json.loads(receipt_path(path).read_text(encoding='utf-8'))
            except (OSError, ValueError):
                receipt = None
            if not isinstance(receipt, dict):
                receipt = None
            try:
                pending = json.loads(Path(str(path) + '.pending.json').read_text(encoding='utf-8'))
            except (OSError, ValueError):
                pending = None
            managed_pending = isinstance(pending, dict) and pending.get('identity') == self.identity(record) and pending.get('profile') == self.profile
            if receipt and receipt.get('profile') != self.profile and not self.overwrite:
                raise ValueError(f'Voix/modèle/réglages différents : {path.name}. Employer un autre --output-dir ou --overwrite explicitement.')
            if path.exists() and receipt is None and not managed_pending and not self.overwrite:
                raise ValueError(f'WAV sans reçu vérifiable : {path.name}. Employer --overwrite pour le reconstruire depuis le cache.')

    def backend(self):
        if not self.allow_synthesis:
            raise ValueError('Réécoute seule : aucune prise du cache ne passe le contrôle ; synthèse désactivée.')
        if self.synthesizer is None:
            try:
                self.synthesizer = self.factory()
            except Exception as exc:
                raise ModelLoadError(f'Chargement Chatterbox impossible : {exc}') from exc
        return self.synthesizer

    def speech_checked(self, path):
        if self.verifier_factory is None:
            return True  # Essai sans ASR : intégrité seule, aucune preuve des paroles.
        try:
            receipt = json.loads(receipt_path(path).read_text(encoding='utf-8'))
            check = receipt.get('verification')
            return isinstance(check,dict) and check.get('passed') is True and check.get('policy') == self.validation_id
        except (OSError,ValueError,AttributeError):
            return False

    def verify(self, text, pcm):
        pcm.validate()
        if self.verifier_factory is None:
            return None
        if self.verifier is None:
            try:
                self.verifier = self.verifier_factory()
            except Exception as exc:
                raise ModelLoadError(f'Chargement du contrôle des paroles impossible : {exc}') from exc
        check = self.verifier.verify(text,pcm)
        if not isinstance(check,dict) or check.get('passed') is not True:
            raise ModelLoadError('Le contrôle des paroles n’a pas fourni de résultat validé.')
        self.stats['speech_checks'] += 1
        return {**check,'policy':self.validation_id}

    def reject(self, identity, text, attempt, error, pcm=None):
        directory = self.cache_dir / self.profile / 'rejected' / identity
        report = dict(text=text, attempt=attempt, policy=self.validation_id, error=str(error),
                      verification=getattr(error,'report',None))
        if pcm is not None:
            try:
                atomic_wave(directory / f'attempt_{attempt}.wav',pcm)
                report['sha256'] = file_hash(directory / f'attempt_{attempt}.wav')
            except ValueError:
                pass
        atomic_json(directory / f'attempt_{attempt}.json',report)

    def recover_rejected(self, identity, text, target):
        """Une nouvelle politique peut sauver une prise, après une vraie réécoute ASR."""
        if self.verifier_factory is None:
            return None
        candidates = []
        for report_path in (self.cache_dir/self.profile/'rejected'/identity).glob('attempt_*.json'):
            try:
                report = json.loads(report_path.read_text(encoding='utf-8'))
                wav = report_path.with_suffix('.wav')
                if report.get('policy') == self.validation_id or report.get('text') != text or not wav.is_file():
                    continue
                if report.get('sha256') and file_hash(wav) != report['sha256']:
                    continue
                score = (report.get('verification') or {}).get('word_error_rate',1)
                candidates.append((score,report_path,wav,report))
            except (OSError,ValueError,TypeError):
                continue
        for _,report_path,wav,report in sorted(candidates,key=lambda item:(item[0],str(item[1])))[:3]:
            try:
                pcm = read_wave(wav)
                check = self.verify(text,pcm)
            except ModelLoadError:
                raise
            except (ValueError,RuntimeError,OSError,EOFError,wave.Error):
                continue
            atomic_wave(target,pcm)
            write_receipt(target,identity,pcm,profile=self.profile,text=text,seed=None,
                          verification=check,recovered_from=str(wav),source_sha256=file_hash(wav))
            self.stats['chunks_reused'] += 1
            self.progress('Prise précédemment refusée : réécoute ASR réussie, audio conservé.')
            return pcm
        return None

    def chunk(self, text, depth=0):
        from .speech_verification import IncompleteSpeech
        identity = digest({'profile': self.profile, 'text': text})
        path = self.cache_dir / self.profile / 'chunks' / (identity + '.wav')
        if identity in self.failed_chunks:
            raise ValueError(self.failed_chunks[identity])
        if receipt_matches(path, identity):
            pcm = read_wave(path)
            if self.speech_checked(path):
                self.stats['chunks_reused'] += 1
                return pcm
            # Un nouveau contrôleur peut revalider la voix existante sans refaire
            # le TTS. Son identité est séparée du profil de synthèse.
            try:
                check = self.verify(text,pcm)
                old = json.loads(receipt_path(path).read_text(encoding='utf-8'))
                write_receipt(path,identity,pcm,profile=self.profile,text=text,seed=old.get('seed'),verification=check)
                self.stats['chunks_reused'] += 1
                return pcm
            except IncompleteSpeech as exc:
                self.reject(identity,text,'cached',exc,pcm)
        recovered = self.recover_rejected(identity,text,path)
        if recovered is not None:
            return recovered
        counter_path = self.cache_dir / self.profile / 'attempts' / (identity + '.json')
        try:
            count = json.loads(counter_path.read_text(encoding='utf-8'))['count']
        except (OSError,ValueError,KeyError):
            count = 0
        backend = self.backend()
        last_error = None
        for attempt in range(self.attempts):
            number = count + attempt
            seed = (self.recipe['seed'] + int(identity[:12],16) + number*104729) % (2**31)
            # Sauvé avant l'appel : une reprise essaiera une autre graine, même
            # après la mort du processus au milieu d'une tentative.
            atomic_json(counter_path,{'count':number+1})
            if attempt:
                self.stats['retry_attempts'] += 1
                self.progress(f'Nouvel essai {attempt+1}/{self.attempts} pour la prise non validée.')
            pcm = None
            try:
                pcm = backend.synthesize(text,seed)
                check = self.verify(text,pcm)
                atomic_wave(path,pcm)
                write_receipt(path,identity,pcm,profile=self.profile,text=text,seed=seed,verification=check)
                self.stats['chunks_generated'] += 1
                return pcm
            except (ModelLoadError,MemoryError):
                raise
            except (ValueError,RuntimeError) as exc:
                last_error = exc
                self.reject(identity,text,number+1,exc,pcm)
                self.progress(f'Contrôle refusé : {exc}')
                # Les rapports ne doivent pas garder les poids ASR/TTS vivants
                # via les frames d'une exception entre deux tentatives.
                exc.__traceback__ = None
                exc.__context__ = None
                exc.__cause__ = None
        # Une phrase trop longue pour une génération stable devient plusieurs
        # passages, chacun contrôlé et sauvegardé séparément. Profondeur bornée.
        if self.verifier_factory and self.recipe['splitter'] != 'whole-text-v1' and depth < 2:
            shorter = recovery_parts(text)
            if len(shorter) > 1:
                self.stats['fallback_splits'] += 1
                self.progress('Le passage reste suspect : découpage en passages plus courts et nouveaux contrôles.')
                try:
                    parts = [self.chunk(part,depth+1) for part in shorter]
                except (ModelLoadError,MemoryError):
                    raise
                except ValueError as exc:
                    self.failed_chunks[identity] = str(exc)
                    raise
                rate = parts[0].sample_rate
                if any(part.sample_rate != rate for part in parts):
                    raise ValueError('Fréquences différentes entre sous-passages.')
                silence = b'\0\0' * (rate*self.recipe['pause_ms']//1000)
                pcm = PCM(rate,silence.join(part.frames for part in parts))
                check = dict(passed=True,policy=self.validation_id,method='verified-parts',
                             parts=[digest({'profile':self.profile,'text':part}) for part in shorter])
                atomic_wave(path,pcm)
                write_receipt(path,identity,pcm,profile=self.profile,text=text,seed=None,verification=check)
                self.stats['chunks_generated'] += 1
                return pcm
        message = f'Passage non validé après {self.attempts} essais : {last_error}. Voir {self.cache_dir / self.profile / "rejected" / identity}'
        self.failed_chunks[identity] = message
        raise ValueError(message)

    def event(self, **event):
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        name = 'chunk_events.jsonl' if event.get('type') == 'chunk' else 'events.jsonl'
        with (self.cache_dir / name).open('a', encoding='utf-8', newline='\n') as stream:
            stream.write(json.dumps(dict(time=time.time(), profile=self.profile, **event), ensure_ascii=False) + '\n')
            stream.flush()
            os.fsync(stream.fileno())

    def run(self, records):
        with ExitStack() as locks:
            # Le verrou des sorties protège aussi contre deux caches différents.
            for directory in sorted({r['target'].parent for r in records}, key=str):
                locks.enter_context(batch_lock(directory / '.tts-output.lock'))
            locks.enter_context(batch_lock(self.cache_dir / '.batch.lock'))
            self.preflight(records)
            atomic_json(self.cache_dir / self.profile / 'recipe.json', self.recipe)
            if self.validation_id:
                atomic_json(self.cache_dir / self.profile / ('verification_'+self.validation_id+'.json'),self.verifier_identity)
            for index, record in enumerate(records, 1):
                path, identity = record['target'], self.identity(record)
                integrity_ok = receipt_matches(path, identity)
                if integrity_ok and self.speech_checked(path):
                    self.stats['skipped'] += 1
                    if index == 1 or index % 100 == 0 or index == len(records):
                        state = 'déjà vérifié' if self.verifier_factory else 'déjà présent et intègre'
                        self.progress(f'[{index}/{len(records)}] {state} ; conservé.')
                    continue
                try:
                    if integrity_ok and self.verifier_factory:
                        # L'audit ne doit pas continuer à accepter une ancienne
                        # preuve si le nouveau contrôle échoue ou est interrompu.
                        receipt = json.loads(receipt_path(path).read_text(encoding='utf-8'))
                        receipt['verification'] = dict(passed=False,policy=self.validation_id,
                                                       method='recheck-required')
                        atomic_json(receipt_path(path),receipt)
                    chunks = self.splitter(record['text'], self.recipe['max_chars'])
                    parts, rate = [], None
                    for number, text in enumerate(chunks, 1):
                        preview = ' '.join(text.split())[:90]
                        self.progress(f'[{index}/{len(records)}] Chunk {number}/{len(chunks)} | {len(text)} caractères | {preview}')
                        started = time.perf_counter()
                        reused_before = self.stats['chunks_reused']
                        details = dict(type='chunk', segment_id=record['segment_id'],
                                       chunk=number, chunk_count=len(chunks), characters=len(text), preview=preview)
                        try:
                            pcm = self.chunk(text)
                        except BaseException as exc:
                            self.event(**details, status='failed', error=str(exc) or type(exc).__name__,
                                       generation_seconds=round(time.perf_counter()-started, 3))
                            self.progress(f'Chunk {number}/{len(chunks)} | ÉCHEC : {exc or type(exc).__name__}')
                            raise
                        duration = len(pcm.frames)/2/pcm.sample_rate
                        elapsed = time.perf_counter()-started
                        reused = self.stats['chunks_reused'] > reused_before
                        self.event(**details, status='done', audio_seconds=round(duration, 3),
                                   generation_seconds=round(elapsed, 3), reused=reused)
                        self.progress(f'Chunk {number}/{len(chunks)} | SUCCÈS | audio {duration:.2f} s | calcul {elapsed:.2f} s' + (' | cache' if reused else ''))
                        if rate is not None and pcm.sample_rate != rate:
                            raise ValueError('Fréquences différentes entre passages ; cache incohérent.')
                        rate = pcm.sample_rate
                        if parts:
                            parts.append(b'\0\0' * (rate * self.recipe['pause_ms']//1000))
                        parts.append(pcm.frames)
                    pcm = PCM(rate, b''.join(parts))
                    pending = Path(str(path) + '.pending.json')
                    atomic_json(pending, dict(identity=identity, profile=self.profile))
                    atomic_wave(path, pcm)
                    write_receipt(path, identity, pcm, profile=self.profile,
                                  segment_id=record['segment_id'], chunk_count=len(chunks),
                                  verification=dict(passed=True,policy=self.validation_id,method='verified-chunks') if self.validation_id else None)
                    pending.unlink(missing_ok=True)
                    self.stats['generated'] += 1
                    self.event(status='done', segment_id=record['segment_id'], file=str(path))
                except (ModelLoadError, MemoryError):
                    raise
                except Exception as exc:
                    self.stats['failed'] += 1
                    self.event(status='failed', segment_id=record['segment_id'], error=str(exc))
                    self.progress(f'ÉCHEC de ce segment : {exc}. Les autres fichiers restent conservés.')
        return dict(self.stats)
