"""Préparer le second modèle ASR local, sans modifier les voix ni produire de son."""
import argparse
import json
import os
from pathlib import Path

from audio.tts_batch import atomic_json, file_hash
from engine.content import Content, ROOT


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline',action='store_true')
    args = parser.parse_args(argv)
    os.environ['HF_HUB_DISABLE_XET'] = '1'
    from huggingface_hub import HfApi, snapshot_download
    directory = ROOT/'audio/runtime/asr_models'
    lock = directory/'medium_revision.json'
    directory.mkdir(parents=True,exist_ok=True)
    if lock.exists():
        info = Content.read(lock)
    else:
        if args.offline:
            raise ValueError('Whisper Medium n’est pas encore préparé localement.')
        model = HfApi(token=False).model_info('Systran/faster-whisper-medium')
        info = dict(repo='Systran/faster-whisper-medium',revision=model.sha)
        atomic_json(lock,info)
    print('Préparation du vérificateur indépendant Whisper Medium…',flush=True)
    path = snapshot_download(info['repo'],revision=info['revision'],cache_dir=str(directory),
                             allow_patterns=['config.json','model.bin','tokenizer.json','vocabulary.*','preprocessor_config.json'],
                             local_files_only=args.offline,token=False)
    required = ('config.json','model.bin','tokenizer.json')
    if any(not (Path(path)/name).is_file() for name in required):
        raise ValueError('Modèle de vérification incomplet.')
    info.update(path=str(Path(path).relative_to(ROOT)),
                files_sha256={p.name:file_hash(p) for p in Path(path).iterdir() if p.is_file()})
    atomic_json(lock,info)
    settings = Content.read(ROOT/'audio/generation_settings.json')
    settings['asr_review_model'] = info['path']
    settings['asr_review_required'] = True
    atomic_json(ROOT/'audio/generation_settings.json',settings)
    print(json.dumps(dict(model=info['repo'],revision=info['revision'],path=path),ensure_ascii=False),flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
