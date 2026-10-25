"""Deux lecteurs ASR et gestion mémoire : contrôle rapide, arbitrage, validation finale."""
import gc
from pathlib import Path

from .speech_verification import IncompleteSpeech, SpeechVerifier, local_model_directory
from .tts_batch import file_hash


REVIEW_DECODING = dict(word_timestamps=True,hallucination_silence_threshold=1.0)


def review_identity(primary, review):
    return dict(controller='independent-review-v1',primary=primary,review=review,
                final_review_required=True,review_decoding=REVIEW_DECODING,
                controller_source_sha256=file_hash(Path(__file__)))


class TimedReviewVerifier(SpeechVerifier):
    """Les silences sont repérés par l'ASR, sans retirer une phrase à la main."""
    def __init__(self, directory, *, threads=8):
        from faster_whisper import WhisperModel
        model = WhisperModel(str(local_model_directory(directory)),device='cpu',
                             compute_type='int8',cpu_threads=threads,local_files_only=True)
        class TimedModel:
            def transcribe(self, stream, **options):
                return model.transcribe(stream,**dict(options,**REVIEW_DECODING))
        self.model = TimedModel()

    def verify(self, expected, pcm, **options):
        try:
            report = super().verify(expected,pcm,**options)
        except IncompleteSpeech as exc:
            exc.report.update(review_decoding=dict(REVIEW_DECODING),review_verifier='Whisper Medium')
            raise
        report.update(review_decoding=dict(REVIEW_DECODING),review_verifier='Whisper Medium')
        return report


class ReviewingSpeechVerifier:
    def __init__(self, primary_factory, review_factory, *, before_review=None, progress=print):
        self.primary_factory,self.review_factory = primary_factory,review_factory
        self.before_review,self.progress = before_review,progress
        self.primary,self.review = None,None

    def reviewer(self):
        if self.review is None:
            if self.before_review:
                self.before_review()
            self.progress('  Chargement de Whisper Medium pour une vérification indépendante…')
            self.review = self.review_factory()
        return self.review

    def release_review(self):
        if self.review is not None:
            # Une exception conservée pour le journal peut encore référencer
            # l'objet vérificateur : détacher aussi les poids de cet objet.
            if hasattr(self.review,'model'):
                self.review.model = None
            self.review = None
            gc.collect()

    def verify(self, expected, pcm, **options):
        if self.primary is None:
            self.primary = self.primary_factory()
        try:
            return self.primary.verify(expected,pcm,**options)
        except IncompleteSpeech as exc:
            first = exc.report
            self.progress('  Reconnaissance Small incertaine : contre-vérification par Medium, mêmes critères.')
            try:
                check = self.reviewer().verify(expected,pcm,**options)
            except IncompleteSpeech as second:
                second.report['primary_rejection'] = first
                raise
            check['primary_rejection'] = first
            check['independent_review'] = True
            return check

    def verify_complete(self, expected, pcm, *, tail_text, tail_frames):
        # Le petit modèle ne peut pas approuver seul un fichier final.
        check = self.reviewer().verify_complete(expected,pcm,tail_text=tail_text,tail_frames=tail_frames)
        check.update(final_review_required=True,review_verifier='Whisper Medium')
        check.setdefault('method','faster-whisper-medium-full-segment')
        return check


class EvictableBackend:
    """Même adaptateur Chatterbox ; éviter de le garder avec le modèle d'arbitrage."""
    def __init__(self, factory, parameters, *, before_load=None, progress=print):
        self.factory,self.before_load,self.progress = factory,before_load,progress
        self._parameters = parameters
        self.delegate = None

    @property
    def parameters(self):
        return self._parameters

    @parameters.setter
    def parameters(self, value):
        self._parameters = value
        if self.delegate is not None:
            self.delegate.parameters = value

    def release(self):
        if self.delegate is not None:
            if hasattr(self.delegate,'model'):
                self.delegate.model = None
            self.delegate = None
            gc.collect()

    def synthesize(self, text, seed):
        if self.delegate is None:
            if self.before_load:
                self.before_load()
            self.progress('  Chargement de Chatterbox, avec les mêmes poids, voix et paramètres…')
            self.delegate = self.factory(self.parameters)
        return self.delegate.synthesize(text,seed)
