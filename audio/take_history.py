"""Versions validées d'un segment, indépendantes des modèles et du lecteur."""
import json
import os
from pathlib import Path
import re
import shutil

from audio.tts_batch import atomic_json, digest, file_hash, receipt_matches, receipt_path


HISTORY_LIMIT = 10


def history_directory(cache_dir, identity):
    if not isinstance(identity,str) or not re.fullmatch('[0-9a-f]{64}',identity):
        raise ValueError('Identité de prise invalide.')
    return Path(cache_dir)/'previous_versions'/identity


def read_take(cache_dir, identity, key):
    if not isinstance(key,str) or not re.fullmatch('[0-9a-f]{64}',key):
        raise ValueError('Identifiant de prise invalide.')
    directory = history_directory(cache_dir,identity).resolve()
    path = directory/(key+'.wav')
    if path.resolve().parent != directory or receipt_path(path).resolve().parent != directory:
        raise ValueError('La prise sort de son dossier historique.')
    proof = json.loads(receipt_path(path).read_text(encoding='utf-8'))
    if (not isinstance(proof,dict) or not isinstance(proof.get('verification'),dict) or
            not proof['verification'].get('passed') or not receipt_matches(path,identity)):
        raise ValueError('Prise historique absente, corrompue ou non validée.')
    return path,proof


def take_key(proof):
    return digest(dict(sha256=proof['sha256'],request=proof.get('regeneration_request'),
                       rounds=proof.get('span_rounds'),round=proof.get('round')))


def archive_take(cache_dir, target, identity, proof):
    """Idempotent : une reprise ne crée pas de doublon dans l'historique."""
    if not proof.get('verification',{}).get('passed') or not receipt_matches(target,identity):
        raise ValueError('Seule une prise intègre et validée peut être archivée.')
    key = take_key(proof)
    archive = history_directory(cache_dir,identity)/(key+'.wav')
    archive.parent.mkdir(parents=True,exist_ok=True)
    if archive.is_file():
        try:
            read_take(cache_dir,identity,key)
            return key
        except (OSError,ValueError,KeyError,TypeError):
            pass
    temporary = Path(str(archive)+'.partial')
    shutil.copyfile(target,temporary)
    if file_hash(temporary) != proof['sha256']:
        raise ValueError('La prise a changé pendant son archivage.')
    os.replace(temporary,archive)
    atomic_json(receipt_path(archive),dict(proof,history_saved_at=proof.get('created_at',Path(target).stat().st_mtime)))
    return key


def list_takes(cache_dir, target, identity):
    directory = history_directory(cache_dir,identity)
    unique = {}
    for path in directory.glob('*.wav'):
        try:
            wav,proof = read_take(cache_dir,identity,path.stem)
            canonical = take_key(proof)
            if canonical not in unique or path.stem == canonical:
                unique[canonical] = dict(key=path.stem,file=str(wav),proof=proof,
                                        time=proof.get('history_saved_at',wav.stat().st_mtime),current=False)
        except (OSError,ValueError,KeyError,TypeError):
            continue
    versions = list(unique.values())
    try:
        proof = json.loads(receipt_path(target).read_text(encoding='utf-8'))
        if isinstance(proof,dict) and isinstance(proof.get('verification'),dict) and proof['verification'].get('passed') and receipt_matches(target,identity):
            key = take_key(proof)
            # Les anciens historiques nommés par SHA sont également reconnus.
            versions = [v for v in versions if take_key(v['proof']) != key]
            versions.append(dict(key=key,file=str(target),proof=proof,
                                 time=proof.get('created_at',Path(target).stat().st_mtime),current=True))
    except (OSError,ValueError,KeyError,TypeError):
        pass
    return sorted(versions,key=lambda v:(v['current'],v['time']),reverse=True)


def prune_takes(cache_dir, target, identity):
    """Limiter les WAV historiques ; ne jamais effacer les composants partagés."""
    versions = list_takes(cache_dir,target,identity)
    keep = {v['key'] for v in versions[:HISTORY_LIMIT]}
    directory = history_directory(cache_dir,identity).resolve()
    for path in directory.glob('*.wav'):
        if path.stem in keep:
            continue
        try:
            read_take(cache_dir,identity,path.stem)
            path.unlink()
            receipt_path(path).unlink(missing_ok=True)
        except (OSError,ValueError,KeyError,TypeError):
            continue
