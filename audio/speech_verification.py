"""Vérifier les paroles, indépendamment de l'intégrité du conteneur WAV."""
import io
import json
import re
import unicodedata
import wave
from importlib import metadata
from pathlib import Path

from .tts_batch import ModelLoadError, atomic_json, batch_lock, file_hash

CHECK_VERSION = 3
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


# Équivalences de prononciation explicites : aucune suppression générale de
# suffixe, qui confondrait par exemple « parle » et « parler ».
HOMOPHONES = {}
for name, spellings in {
    'delivre_e': ('délivré','délivrée','délivrés','délivrées','délivrer'),
    'seche_e': ('séché','séchée','séchés','séchées','sécher'),
    'fer': ('fer','faire'), 'henri': ('henri','henry'),
    'cher': ('cher','chère','chers','chères'),
    'excuse': ('excuse','excuses'), 'autre': ('autre','autres'),
    'moyen': ('moyen','moyens'), 'jeu': ('jeu','jeux'),
}.items():
    HOMOPHONES.update({word:name for word in spellings})


def spoken_tokens(text):
    text = unicodedata.normalize('NFC',text.lower())
    # Cas contextuels : conserver notamment la distinction il/ils avec liaison.
    text = re.sub(r'\b(?:il|ils)\s+(?:partirait|partiraient)\b','il partirait',text)
    text = re.sub(r'\b(?:seul|seule|seuls|seules)\s+(?:pouvait|pouvaient)\b','seul pouvait',text)
    text = re.sub(r'\bcherche\s+à\b','chercha',text)
    words = re.findall(r'[^\W\d_]+|\d+',text)
    return [HOMOPHONES.get(word) or tokens(word)[0] for word in words if tokens(word)]


def repair_boundaries(reference, actual):
    """Réparer seulement les fusions/séparations dont les lettres sont identiques.

    « tabale » et « ta balle » ont la même suite de lettres après réduction des
    consonnes doubles. Aucun mot manquant ou mot différent n'est inventé.
    """
    def compact(words):
        # « balle / bale », mais pas « fille / file » ou des voyelles doubles.
        return re.sub(r'(?<=[aàâ])ll','l',''.join(words))
    joined = {}
    for left,right in zip(reference,reference[1:]):
        if left.isalpha() and right.isalpha():
            joined.setdefault(compact((left,right)),set()).add((left,right))
    result,repairs,index = [],[],0
    while index < len(actual):
        word = actual[index]
        options = joined.get(compact([word]),set()) if word not in reference else set()
        if len(options) == 1:
            replacement = next(iter(options))
            result.extend(replacement)
            repairs.append(dict(heard=[word],compared_as=list(replacement)))
        elif index+1 < len(actual) and (word not in reference or actual[index+1] not in reference):
            pair = actual[index:index+2]
            matches = {r for r in reference if r.isalpha() and compact([r]) == compact(pair)}
            if len(matches) == 1:
                replacement = next(iter(matches))
                result.append(replacement)
                repairs.append(dict(heard=pair,compared_as=[replacement]))
                index += 1
            else:
                result.append(word)
        else:
            result.append(word)
        index += 1
    return result,repairs


def compare_transcript(expected, transcript, max_wer=0.15):
    raw_reference,raw_actual = tokens(expected),tokens(transcript)
    reference, actual = spoken_tokens(expected),spoken_tokens(transcript)
    actual,boundary_repairs = repair_boundaries(reference,actual)
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
    report = dict(passed=not reasons, transcript=transcript, expected_words=len(raw_reference),
                  recognized_words=len(raw_actual), word_error_rate=round(wer,4),
                  orthographic_word_error_rate=round(distance(raw_reference,raw_actual)/len(raw_reference),4),
                  word_boundary_repairs=boundary_repairs,comparison='french-spoken-v1',
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
                'comparison':'french-spoken-v1','asr_attempts':2,
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
        attempts = []
        for number in range(2):
            # Ne pas fournir le texte attendu en prompt : cela pourrait aider
            # le reconnaisseur à inventer une fin qui n'a pas été prononcée.
            stream.seek(0)
            options = dict(language='fr',beam_size=5 if number == 0 else 8,
                           temperature=0,condition_on_previous_text=False,
                           vad_filter=vad_filter if number == 0 else True)
            if number:
                options['patience'] = 2
            try:
                segments, _ = self.model.transcribe(stream,**options)
                transcript = ' '.join(segment.text.strip() for segment in segments)
            except Exception as exc:
                raise ModelLoadError(f'Contrôle des paroles indisponible : {exc}') from exc
            try:
                report = compare_transcript(expected,transcript)
            except IncompleteSpeech as exc:
                report = exc.report
                attempts.append(dict(options=options,verification=report.copy()))
                continue
            attempts.append(dict(options=options,verification=report.copy()))
            report.update(vad_filter=options['vad_filter'],asr_attempts=attempts)
            return report
        report['asr_attempts'] = attempts
        raise IncompleteSpeech(report)

    def verify_complete(self, expected, pcm, *, tail_text, tail_frames):
        """Contre-vérifier une fin douteuse sur les échantillons du WAV complet."""
        try:
            return self.verify(expected,pcm,vad_filter=True)
        except IncompleteSpeech as exc:
            global_check = exc.report
            if global_check['reasons'] != ['fin du texte non retrouvée']:
                raise
            from .tts_batch import PCM
            if not 0 < tail_frames <= len(pcm.frames):
                raise ValueError('Découpage de la fin invalide.')
            tail = PCM(pcm.sample_rate,pcm.frames[-tail_frames:])
            tail_check = self.verify(tail_text,tail,vad_filter=True)
            return dict(global_check,passed=True,reasons=[],tail_matched=True,
                        method='full-and-tail',global_check=global_check,tail_check=tail_check,
                        tail_frames=tail_frames)
