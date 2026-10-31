"""Tons d'une prise : palette approuvée, texte canonique et identité conservés."""
import copy

from audio.tts_batch import digest


def validated_tones(plan, tones, palette):
    if not isinstance(tones,dict):
        raise ValueError('Liste des tons de la prise invalide.')
    result = {}
    for key,emotion in tones.items():
        if (not isinstance(key,str) or not key.isdecimal() or str(int(key))!=key or
                not 0 <= int(key) < len(plan['spans']) or emotion not in palette):
            raise ValueError('Ton ou portion absent de la palette approuvée.')
        if emotion != plan['spans'][int(key)]['emotion']:
            result[key] = emotion
    return result


def effective_spans(plan, tones, palette):
    tones = validated_tones(plan,tones,palette)
    spans = copy.deepcopy(plan['spans'])
    for key,emotion in tones.items():
        spans[int(key)].update(emotion=emotion,parameters=copy.deepcopy(palette[emotion]))
    return spans


def effective_profile(profile, tones):
    return digest(dict(canonical_profile=profile,tone_overrides=tones))


def receipt_tones(plan, proof, palette):
    tones = validated_tones(plan,proof.get('tone_overrides',{}),palette)
    if tones or 'effective_profile' in proof:
        if proof.get('effective_profile') != effective_profile(proof['profile'],tones):
            raise ValueError('L’identité des tons ne correspond pas à cette prise.')
    return tones
