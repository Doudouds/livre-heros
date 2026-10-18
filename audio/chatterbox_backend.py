"""Adaptateur facultatif pour la préparation sur PC, jamais importé par le jeu."""
import inspect
import json
from importlib import metadata
from pathlib import Path

from .tts_batch import PCM, atomic_json, batch_lock, file_hash

REPO = 'ResembleAI/chatterbox'
MODEL_FILES = ('ve.pt', 't3_mtl23ls_v3.safetensors', 's3gen.pt',
               'grapheme_mtl_merged_expanded_v1.json', 'conds.pt', 'Cangjie5_TC.json')


def prepare_model(cache_dir, model_dir=None, revision=None):
    """Figer une révision HF la première fois et la conserver aux reprises."""
    if model_dir:
        directory = Path(model_dir).resolve()
        fingerprints = {}
        for name in MODEL_FILES:
            path = directory / name
            if not path.is_file():
                raise ValueError(f'Fichier V3 absent du dossier du modèle : {name}')
            fingerprints[name] = file_hash(path)
        return directory, {'repo': REPO, 'variant': 'v3', 'files_sha256': fingerprints}
    from huggingface_hub import HfApi, snapshot_download
    lock = Path(cache_dir) / 'model_revision.json'
    with batch_lock(Path(cache_dir) / '.model.lock'):
        if revision is None and lock.is_file():
            info = json.loads(lock.read_text(encoding='utf-8'))
            if info.get('repo') != REPO or info.get('variant') != 'v3':
                raise ValueError('Révision du modèle incompatible dans le cache.')
            resolved = info['revision']
        else:
            resolved = HfApi().model_info(REPO, revision=revision or 'main').sha
            info = {'repo': REPO, 'variant': 'v3', 'revision': resolved}
            atomic_json(lock, info)
        try:
            directory = snapshot_download(REPO, revision=resolved, allow_patterns=list(MODEL_FILES), local_files_only=True)
        except Exception:
            directory = snapshot_download(REPO, revision=resolved, allow_patterns=list(MODEL_FILES))
    for name in MODEL_FILES:
        if not (Path(directory) / name).is_file():
            raise ValueError(f'Le dépôt ne contient pas les poids Multilingual V3 attendus : {name}')
    return Path(directory), info


def environment_identity():
    import chatterbox.mtl_tts as module
    cls = module.ChatterboxMultilingualTTS
    if 't3_model' not in inspect.signature(cls.from_local).parameters:
        raise ValueError('Cette installation ne sélectionne pas V3. Installer la version officielle récente ; voir docs/chatterbox_v3.md.')
    return {'versions': {name: metadata.version(name) for name in
                         ('chatterbox-tts','torch','torchaudio','transformers','numpy')},
            'adapter_source_sha256': file_hash(Path(__file__)),
            'chatterbox_source_sha256': file_hash(Path(module.__file__))}


def choose_device(value):
    import torch
    if value == 'auto':
        return 'cuda' if torch.cuda.is_available() else 'cpu'
    if value == 'cuda' and not torch.cuda.is_available():
        raise ValueError('CUDA indisponible dans cet environnement. Utiliser --device cpu ou une installation PyTorch adaptée.')
    return value


class ChatterboxBackend:
    def __init__(self, directory, voice, device, parameters):
        import torch
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS
        self.torch, self.parameters = torch, parameters
        self.model = ChatterboxMultilingualTTS.from_local(directory, device, t3_model='v3')
        self.model.prepare_conditionals(str(voice), exaggeration=parameters['exaggeration'])

    def synthesize(self, text, seed):
        import random
        import numpy as np
        random.seed(seed)
        np.random.seed(seed)
        self.torch.manual_seed(seed)
        if self.torch.cuda.is_available():
            self.torch.cuda.manual_seed_all(seed)
        try:
            with self.torch.inference_mode():
                waveform = self.model.generate(text, language_id='fr', **self.parameters)
        except self.torch.cuda.OutOfMemoryError as exc:
            raise MemoryError('Mémoire GPU insuffisante. Les passages terminés sont conservés ; réduire --chunk-chars ou reprendre sur CPU dans un dossier séparé.') from exc
        samples = waveform.detach().cpu().float().numpy().reshape(-1)
        if not np.isfinite(samples).all():
            raise ValueError('Chatterbox a produit des valeurs audio invalides.')
        frames = (np.clip(samples, -1, 1) * 32767).astype('<i2').tobytes()
        return PCM(self.model.sr, frames)
