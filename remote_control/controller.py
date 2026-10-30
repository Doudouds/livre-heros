"""Orchestration sans Tkinter, exécutée sur un seul fil par PlaybackService."""
import copy
import json
import os
import queue
import threading
from collections import deque
from concurrent.futures import Future, TimeoutError
from pathlib import Path

from audio.audio_player import LocalAudioPlayer
from engine import StoryEngine
from engine.book_engine import BookEngine


class StaleCommand(ValueError):
    pass


def book_segments(content, book_id, automatic=False):
    """Même parcours que BookEngine, fusion des passés sans influence future.

    Ce catalogue de lecture n'importe aucun outil de synthèse ni modèle ASR.
    Les conséquences distinctes sont conservées avant la fusion des états.
    """
    first = BookEngine(content, book_id, automatic=automatic)
    relevant, needed = {}, set()
    for scene in reversed(first.book['scenes']):
        conditions = [v.get('when', {}) for v in scene.get('variants', [])]
        choices = list(scene.get('choices', []))
        for variant in scene.get('variants', []):
            choices.extend(variant.get('choices', []))
        conditions.extend(v.get('when', {}) for c in choices for v in c.get('consequence_variants', []))
        for condition in conditions:
            for key in ('all', 'none', 'any'):
                needed.update(condition.get(key, []))
        needed.update(e['flag'] for e in scene.get('echoes', []))
        relevant[scene['id']] = frozenset(needed)
    pending, seen, expanded = deque([first]), set(), set()
    while pending:
        engine = pending.popleft()
        if engine.current['segment_id'] not in seen:
            seen.add(engine.current['segment_id'])
            yield engine.current
        key = (engine.current['id'], frozenset(engine.state.flags & relevant[engine.current['id']]))
        if engine.finished or key in expanded:
            continue
        expanded.add(key)
        for index in ((0,) if automatic else (0, 1)):
            branch = copy.copy(engine)
            branch.state = copy.deepcopy(engine.state)
            branch.journal = {**engine.journal, 'scenes': [], 'choices': []}
            branch.choose(index)
            branch.advance()
            pending.append(branch)


class PlaybackController:
    def __init__(self, content, *, audio=None, session_path=None, restore=True):
        self.content = content
        self.audio = audio or LocalAudioPlayer(content.root, content.config['audio_root'])
        self.session_path = Path(session_path) if session_path else None
        self.engine = None
        self.start_spec = None
        self.revision = 0
        self.started = False
        self.completed = False
        self.error = None
        self.stopped = False
        self._previous_state = self.audio.state
        if restore:
            self.restore()

    def audio_file(self, engine, scene):
        if isinstance(engine, BookEngine):
            directory = self.content.config.get('book_audio_roots', {}).get(engine.book['id'])
            if engine.automatic:
                # Uniquement le WAV au rôle automatic dans le dossier de ce livre.
                return f"{directory}/{scene['segment_id']}.wav" if directory else None
            return scene.get('audio_file') or (
                f"{directory}/{scene['segment_id']}.wav" if directory else None)
        return scene.get('audio_file')

    def audio_path(self, engine, scene):
        root = self.content.root.resolve()
        primary = root / self.content.config['audio_root'] / (scene['segment_id'] + '.wav')
        # Le mode automatique refuse également le répertoire audio générique.
        candidates = [] if isinstance(engine, BookEngine) and engine.automatic else [primary]
        alias = self.audio_file(engine, scene)
        if alias:
            candidates.append(root / alias.replace('{segment_id}', scene['segment_id']))
        for candidate in candidates:
            path = candidate.resolve()
            if path.is_relative_to(root) and path.is_file():
                return path
        return None

    def coverage(self, book_id, automatic):
        engine = BookEngine(self.content, book_id, automatic=automatic)
        scenes = list(book_segments(self.content, book_id, automatic))
        available = sum(self.audio_path(engine, scene) is not None for scene in scenes)
        return {'available': available, 'total': len(scenes), 'complete': available == len(scenes)}

    def library(self):
        books = []
        for book_id, book in self.content.books.items():
            modes = {'interactive': self.coverage(book_id, False)}
            if book.get('audio_tagged_version') == 1:
                modes['automatic'] = self.coverage(book_id, True)
            books.append({'id': book_id, 'title': book['title'], 'author': book.get('author', ''),
                          'description': book.get('library_description', ''), 'modes': modes})
        catalogs = {name: [{'id': key, 'label': value['label']} for key, value in catalog.items()]
                    for name, catalog in (('hero', self.content.heroes),
                                          ('location', self.content.locations), ('item', self.content.items))}
        return {'books': books, 'adventures': [{'id': arc['id'], 'title': arc['title'],
                                              'description': arc.get('description', '')}
                                             for arc in self.content.arcs.values()], 'catalogs': catalogs}

    @property
    def automatic(self):
        return isinstance(self.engine, BookEngine) and self.engine.automatic

    def selection(self):
        return self.engine.pending or self.engine.current

    def play_current(self):
        scene = self.selection()
        self.completed = False
        self.stopped = False
        lead_in = self.content.config.get('audio_lead_in_ms', 800)
        if isinstance(self.engine, BookEngine):
            lead_in = self.engine.book.get('audio_lead_in_ms', lead_in)
        self.audio.lead_in_ms = lead_in
        # Le lecteur générique privilégie audio_root : le contraindre ici en automatique.
        if self.automatic:
            directory = self.content.config.get('book_audio_roots', {}).get(self.engine.book['id'])
            self.audio.audio_root = (self.content.root / directory).resolve() if directory else self.content.root / 'audio/missing_automatic'
        else:
            self.audio.audio_root = (self.content.root / self.content.config['audio_root']).resolve()
        self.started = self.audio.play(scene['segment_id'], self.audio_file(self.engine, scene))
        self._previous_state = self.audio.state
        self.error = None if self.started else 'Audio indisponible : lecture suspendue à ce passage. Réessaie avec Lecture.'

    def start(self, spec):
        kind = spec.get('kind')
        if kind == 'book':
            book_id = spec.get('id')
            if book_id not in self.content.books:
                raise ValueError('Histoire inconnue.')
            mode = spec.get('mode', 'interactive')
            if mode not in ('interactive', 'automatic'):
                raise ValueError('Mode de lecture inconnu.')
            automatic = mode == 'automatic'
            if automatic and self.content.books[book_id].get('audio_tagged_version') != 1:
                raise ValueError('Le mode automatique n’est pas préparé pour ce livre.')
            if automatic:
                coverage = self.coverage(book_id, True)
                if not coverage['complete']:
                    raise ValueError(f"Audio automatique incomplet : {coverage['available']}/{coverage['total']} fichiers. "
                                     f"Prépare les fichiers avec generer_audio_conte.py --book {book_id} --automatic.")
            engine = BookEngine(self.content, book_id, automatic=automatic)
            spec = {'kind': 'book', 'id': book_id, 'mode': mode}
        elif kind == 'adventure':
            if spec.get('id') not in self.content.arcs:
                raise ValueError('Aventure inconnue.')
            spec = {key: spec.get(key) for key in ('kind', 'id', 'hero', 'location', 'item')}
            engine = StoryEngine(self.content, spec['hero'], spec['location'], spec['item'], arc_id=spec['id'])
        else:
            raise ValueError('Type d’histoire inconnu.')
        self.audio.stop()
        self.engine, self.start_spec = engine, spec
        self.play_current()

    def command(self, payload):
        if type(payload.get('revision')) is not int:
            raise ValueError('La révision de lecture est requise.')
        if payload['revision'] != self.revision:
            raise StaleCommand('La lecture a changé. Les commandes ont été actualisées ; réessaie.')
        action = payload.get('action')
        if action == 'start':
            self.start(payload)
        elif action == 'restart' and self.engine:
            self.start(self.start_spec)
        elif self.engine is None:
            raise ValueError('Choisis d’abord une histoire.')
        elif action == 'choose':
            if self.automatic or self.engine.pending or self.engine.finished:
                raise ValueError('Ce passage n’attend pas de choix.')
            self.engine.choose(payload.get('index'))
            if self.engine.arc.get('inline_consequences'):
                self.engine.advance()
            self.play_current()
        elif action == 'advance':
            if self.automatic:
                raise ValueError('L’écoute automatique attend la fin réelle du son.')
            self.engine.advance()
            self.play_current()
        elif action == 'pause':
            if not self.audio.pause():
                raise ValueError('Aucun son en cours à suspendre.')
        elif action == 'resume':
            if self.audio.state == 'unavailable':
                self.play_current()
            elif self.audio.resume():
                self.started, self.completed, self.stopped, self.error = True, False, False, None
            else:
                raise ValueError('Impossible de reprendre la lecture.')
        elif action == 'replay':
            # Même passage et même mode, y compris après un arrêt ou une restauration.
            self.play_current()
        elif action == 'stop':
            self.audio.stop()
            self.started, self.stopped, self.error = False, True, None
        elif action == 'volume':
            volume = payload.get('value')
            if type(volume) is not int or not 0 <= volume <= 100:
                raise ValueError('Le volume doit être compris entre 0 et 100.')
            if not getattr(self.audio, 'set_volume', lambda _: False)(volume):
                raise ValueError('Le volume se règle sur le PC avec ce périphérique.')
        else:
            raise ValueError('Commande inconnue.')
        self._previous_state = self.audio.state
        self.revision += 1
        self.save()
        return self.snapshot()

    def tick(self):
        state = self.audio.state
        if self.engine and self.started and state == 'ready':
            self.started = False
            if self.automatic and not self.engine.finished:
                self.engine.choose(0)
                self.engine.advance()
                self.play_current()
            else:
                self.completed = self.engine.finished
            self.revision += 1
            self.save()
        elif state == 'unavailable' and self._previous_state in ('playing', 'paused'):
            self.started = False
            self.error = 'Le périphérique audio est indisponible. Réessaie avec Lecture.'
            self.revision += 1
        self._previous_state = self.audio.state

    def snapshot(self):
        result = {'revision': self.revision, 'active': self.engine is not None, 'error': self.error}
        if self.engine is None:
            return result
        scene = self.selection()
        pending = self.engine.pending is not None
        state = self.audio.state
        choices = [] if self.automatic or pending else self.engine.current.get('choices', [])
        is_book = isinstance(self.engine, BookEngine)
        number = (list(self.engine.scenes).index(self.engine.current['id']) + 1 if is_book
                  else len(self.engine.journal['scenes']))
        total = len(self.engine.scenes) if is_book else self.engine.arc['decision_count'] + 2
        progress = getattr(self.audio, 'progress', lambda: None)()
        result.update(title=self.engine.arc['title'], scene_id=self.engine.current['id'],
                      scene_title='Ton chemin se dessine…' if pending else scene.get('title', ''),
                      text=scene['text'], mode='automatic' if self.automatic else 'interactive',
                      audio_state=state, completed=self.completed, stopped=self.stopped,
                      passage=number, passages=total, progress=progress,
                      choices=[{'index': i, 'text': c['text']} for i, c in enumerate(choices)],
                      question=None if self.automatic or pending else self.engine.current.get('choice_question', 'Que fais-tu ?'),
                      can_advance=not self.automatic and not self.engine.finished and
                                  (pending or self.engine.current['kind'] == 'intro'),
                      volume=getattr(self.audio, 'volume', None),
                      volume_supported=getattr(self.audio, 'volume_supported', False))
        return result

    def save(self):
        if not self.session_path or not self.engine:
            return
        path = self.session_path
        temporary = path.with_suffix('.partial')
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            self.engine.export_session(temporary)
            data = json.loads(temporary.read_text(encoding='utf-8'))
            data['remote'] = {'start': self.start_spec, 'completed': self.completed}
            with temporary.open('w', encoding='utf-8', newline='\n') as handle:
                json.dump(data, handle, ensure_ascii=False)
                handle.write('\n')
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        except OSError:
            self.error = 'La lecture continue, mais la sauvegarde locale a échoué.'
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    def restore(self):
        if not self.session_path or not self.session_path.is_file():
            return
        try:
            data = json.loads(self.session_path.read_text(encoding='utf-8'))
            engine_type = BookEngine if data.get('format') == BookEngine.JOURNAL_FORMAT else StoryEngine
            engine = engine_type.replay(self.content, self.session_path)
            spec = data['remote']['start']
            self.engine, self.start_spec = engine, spec
            self.completed = data['remote'].get('completed', False)
            self.stopped = True
        except (OSError, ValueError, KeyError, TypeError):
            self.error = 'L’ancienne session ne correspond plus au contenu. Choisis une histoire pour commencer.'


class PlaybackService:
    """Toutes les commandes audio et les transitions restent sur le même fil.

    La boucle avance sans client connecté. Le navigateur ne pilote aucun timer.
    """
    def __init__(self, factory, *, interval=0.1):
        self.jobs = queue.Queue()
        self.interval = interval
        self.ready = Future()
        self.thread = threading.Thread(target=self.run, args=(factory,), name='story-playback', daemon=True)
        self.thread.start()
        self.ready.result(timeout=10)

    def run(self, factory):
        try:
            controller = factory()
        except Exception as exc:
            self.ready.set_exception(exc)
            return
        self.ready.set_result(True)
        try:
            while True:
                try:
                    job = self.jobs.get(timeout=self.interval)
                except queue.Empty:
                    job = ()
                if job is None:
                    return
                try:
                    controller.tick()
                except Exception:
                    controller.audio.stop()
                    controller.started = False
                    controller.error = 'La lecture s’est interrompue. Réessaie avec Lecture.'
                    controller.revision += 1
                if job:
                    operation, payload, future = job
                    if not future.set_running_or_notify_cancel():
                        continue
                    try:
                        value = (controller.command(payload) if operation == 'command' else
                                 controller.library() if operation == 'library' else controller.snapshot())
                        future.set_result(value)
                    except Exception as exc:
                        future.set_exception(exc)
        finally:
            controller.audio.stop()

    def request(self, operation, payload=None, *, timeout=10):
        future = Future()
        self.jobs.put((operation, payload, future))
        try:
            return future.result(timeout=timeout)
        except TimeoutError:
            future.cancel()
            raise

    def close(self):
        self.jobs.put(None)
        self.thread.join(timeout=5)
