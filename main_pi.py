"""Point d'entrée réservé au futur portage GPIO, sans réécriture du moteur."""
from engine import Content, StoryEngine
from audio.audio_player import LocalAudioPlayer


def create_runtime(hero, location, item, seed=None):
    content = Content()
    engine = StoryEngine(content, hero, location, item, seed)
    audio = LocalAudioPlayer(content.root, content.config["audio_root"],
                             lead_in_ms=content.config.get("audio_lead_in_ms", 800))
    return engine, audio, dict(content.config["gpio"])


if __name__ == "__main__":
    raise SystemExit("Le prototype PC est prêt. Le backend GPIO sera ajouté après validation sur PC.")
