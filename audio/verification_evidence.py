"""Relire les preuves ASR enregistrées, y compris la contre-vérification de fin."""
from .speech_verification import IncompleteSpeech, compare_transcript


def validate_evidence(expected, proof, pcm, *, tail_text=None, tail_pcm=None):
    if proof.get('passed') is not True:
        raise ValueError('Preuve ASR non validée.')
    try:
        return compare_transcript(expected,proof['transcript'])
    except IncompleteSpeech as exc:
        if (exc.report['reasons'] != ['fin du texte non retrouvée']
                or proof.get('method') != 'full-and-tail'):
            raise
        if not tail_text or tail_pcm is None or not expected.strip().endswith(tail_text.strip()):
            raise ValueError('La fin contre-vérifiée ne correspond pas au texte attendu.')
        if proof.get('tail_frames') != len(tail_pcm.frames) or pcm.frames[-len(tail_pcm.frames):] != tail_pcm.frames:
            raise ValueError('La preuve de fin ne correspond pas aux échantillons du fichier final.')
        tail_proof = proof.get('tail_check',{})
        if tail_proof.get('passed') is not True:
            raise ValueError('La fin contre-vérifiée n’est pas validée.')
        return compare_transcript(tail_text,tail_proof['transcript'])
