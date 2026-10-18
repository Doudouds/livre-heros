"""Vérifier les paroles, indépendamment de l'intégrité du conteneur WAV."""
import io
import json
import re
import unicodedata
import wave
from importlib import metadata
from pathlib import Path

from .tts_batch import ModelLoadError, atomic_json, batch_lock, file_hash

CHECK_VERSION = 2
NUMBER_WORDS = dict(zip(map(str, range(0, 13)),
                       ('zero','un','deux','trois','quatre','cinq','six','sept','huit','neuf','dix','onze','douze')))


class IncompleteSpeech(ValueError):
    def __init__(self, report):
        self.report = report
        super().__init__('Paroles incomplètes ou différentes : ' + '; '.join(report['reasons']))


def tokens(text):
    text = unicodedata.normalize('NFKD', text.lower().replace('œ','oe').replace('æ','ae'))
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return [NUMBER_WORDS.get(word, word) for word in re.findall(r'[a-z]+|\d+', text)]


def distance(expected, heard):
    row = list(range(len(heard) + 1))
    for i, word in enumerate(expected, 1):
        updated = [i]
        for j, actual in enumerate(heard, 1):
            updated.append(min(updated[-1]+1, row[j]+1, row[j-1]+(word != actual)))
        row = updated
    return row[-1]


def compare_transcript(expected, transcript, max_wer=0.15):
    reference, actual = tokens(expected), tokens(transcript)
    # Whisper peut écrire le verbe « chois » pour le nom homophone « choix ».
    # Cette équivalence ne vaut que devant le numéro d'une annonce ; aucun
    # numéro ni mot absent n'est ajouté, et leur ordre reste contrôlé ensuite.
    homophones = 0
    for index in range(len(actual)-1):
        if actual[index] == 'chois' and actual[index+1] in ('un','deux'):
            actual[index] = 'choix'
            homophones += 1
    if not reference:
        raise ValueError('Texte attendu vide.')
    errors = distance(reference, actual)
    wer = errors / len(reference)
    # Exiger les trois derniers mots exacts : une bonne couverture globale
    # pourrait sinon masquer la disparition d'une fin de phrase ou du choix 2.
    end_length = min(3, len(reference))
    tail_ok = len(actual) >= end_length and reference[-end_length:] == actual[-end_length:]
    tail_length = min(8, len(reference))
    tail_distance = distance(reference[-tail_length:], actual[-tail_length:])
    reasons = []
    if not actual:
        reasons.append('aucune parole reconnue')
    if wer > max_wer:
        reasons.append(f'écart au texte {wer:.0%}, maximum {max_wer:.0%}')
    if not tail_ok or tail_distance > 1:
        reasons.append('fin du texte non retrouvée')
    # Les deux annonces et leur ordre sont vérifiés, même si la première a
    # disparu d'un passage relativement long qui respecterait encore le WER.
    expected_choices = [reference[i+1] for i, word in enumerate(reference[:-1])
                        if word == 'choix' and reference[i+1] in ('un','deux')]
    actual_choices = [actual[i+1] for i, word in enumerate(actual[:-1])
                      if word == 'choix' and actual[i+1] in ('un','deux')]
    if expected_choices != actual_choices:
        reasons.append('annonce des choix absente, répétée ou dans le mauvais ordre')
    report = dict(passed=not reasons, transcript=transcript, expected_words=len(reference),
                  recognized_words=len(actual), word_error_rate=round(wer,4),
                  tail_matched=tail_ok and tail_distance <= 1,
                  choices_matched=expected_choices == actual_choices, reasons=reasons,
                  choice_homophones_normalized=homophones)
    if reasons:
        raise IncompleteSpeech(report)
    return report


def local_model_directory(directory):
    directory = Path(directory).resolve()
    required = ('model.bin','config.json','tokenizer.json')
    missing = [name for name in required if not (directory / name).is_file()]
    if missing:
        raise ValueError('Modèle faster-whisper local incomplet : ' + ', '.join(missing) +
                         '. Le tokenizer local est obligatoire pour éviter un téléchargement implicite.')
    return directory


def prepare_asr(cache_dir, model='small', model_dir=None):
    """Poids de reconnaissance figés, téléchargés une fois, puis locaux."""
    directory = local_model_directory(model_dir) if model_dir else None
    import faster_whisper.transcribe as module
    from huggingface_hub import HfApi, snapshot_download
    identity = {'checker_version':CHECK_VERSION, 'method':'faster-whisper', 'language':'fr',
                'max_wer':0.15, 'exact_last_words':3, 'tail_words':8,
                'versions':{n:metadata.version(n) for n in ('faster-whisper','ctranslate2')},
                'checker_source_sha256':file_hash(Path(__file__)),
                'asr_source_sha256':file_hash(Path(module.__file__))}
    if model_dir:
        identity['model'] = {'files_sha256':{p.name:file_hash(p) for p in sorted(directory.iterdir()) if p.is_file()}}
        return directory, identity
    if model not in ('small','medium','large-v3'):
        raise ValueError('Modèle de reconnaissance attendu : small, medium ou large-v3.')
    repo = 'Systran/faster-whisper-' + model
    lock = Path(cache_dir) / ('asr_revision_' + model + '.json')
    with batch_lock(Path(cache_dir) / '.asr-model.lock'):
        if lock.is_file():
            info = json.loads(lock.read_text(encoding='utf-8'))
            if info.get('repo') != repo:
                raise ValueError('Révision ASR incompatible dans le cache.')
        else:
            info = {'repo':repo,'revision':HfApi().model_info(repo).sha}
            atomic_json(lock,info)
        patterns = ['config.json','model.bin','tokenizer.json','vocabulary.*','preprocessor_config.json']
        try:
            directory = snapshot_download(repo,revision=info['revision'],allow_patterns=patterns,local_files_only=True)
        except Exception:
            directory = snapshot_download(repo,revision=info['revision'],allow_patterns=patterns)
    identity['model'] = info
    return local_model_directory(directory), identity


class SpeechVerifier:
    def __init__(self, directory):
        from faster_whisper import WhisperModel
        # La reconnaissance reste sur CPU pour laisser la mémoire GPU au TTS.
        self.model = WhisperModel(str(local_model_directory(directory)),device='cpu',compute_type='int8',local_files_only=True)

    def verify(self, expected, pcm, *, vad_filter=False):
        pcm.validate()
        stream = io.BytesIO()
        with wave.open(stream,'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(pcm.sample_rate)
            wav.writeframes(pcm.frames)
        stream.seek(0)
        try:
            # Ne pas fournir le texte attendu en prompt : cela pourrait aider
            # le reconnaisseur à inventer une fin qui n'a pas été prononcée.
            segments, _ = self.model.transcribe(stream,language='fr',beam_size=5,
                                               temperature=0,condition_on_previous_text=False,
                                               vad_filter=vad_filter)
            transcript = ' '.join(segment.text.strip() for segment in segments)
        except Exception as exc:
            raise ModelLoadError(f'Contrôle des paroles indisponible : {exc}') from exc
        report = compare_transcript(expected,transcript)
        report['vad_filter'] = vad_filter
        return report
