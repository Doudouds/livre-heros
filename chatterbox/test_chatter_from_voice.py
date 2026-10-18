import time
import torchaudio as ta

from chatterbox.mtl_tts import ChatterboxMultilingualTTS


# --------------------------------------------------
# Configuration
# --------------------------------------------------

device = "cpu"

AUDIO_PROMPT = r"D:\machine_audio\Recording.wav"

texte = """
Ayant pour habitude de s'éveiller quelques minutes avant l'heure, elle contempla le monde encore endormi. Sa vie se résumait à cette chambre, une dizaine de mètres carrés couronnée d'une ampoule poussiéreuse pendue au plafond. Tout cela était à elle : ce matelas grisâtre sur lequel elle était étendue, ces habits enfouis à la hâte dans les tiroirs du placard cartonné et ce tableau simpliste qui dessinait les traits d'une femme au travail dont elle ne savait rien. Les murs, jaunis par les années, ne la dérangeaient pas réellement ; ses voisins n'entretenaient guère mieux leur sphère personnelle.
"""


# --------------------------------------------------
# Chargement du modèle V3
# --------------------------------------------------

print("Chargement de Chatterbox Multilingual V3...")

model = ChatterboxMultilingualTTS.from_pretrained(
    device=device,
    t3_model="v3"
)

print("Modèle chargé.")
print()


# --------------------------------------------------
# Réglages à comparer
# --------------------------------------------------

tests = [
    {
        "nom": "lent",
        "cfg_weight": 0.30,
        "exaggeration": 0.40,
    }#,
    #{
    #    "nom": "tres_lent",
    #    "cfg_weight": 0.18,
    #    "exaggeration": 0.30,
    #}
]


# --------------------------------------------------
# Génération
# --------------------------------------------------

for test in tests:

    nom = test["nom"]
    cfg_weight = test["cfg_weight"]
    exaggeration = test["exaggeration"]

    print("=" * 60)
    print(f"Génération : {nom}")
    print(f"cfg_weight   : {cfg_weight}")
    print(f"exaggeration : {exaggeration}")

    debut = time.time()

    wav = model.generate(
        texte,
        language_id="fr",
        audio_prompt_path=AUDIO_PROMPT,
        cfg_weight=cfg_weight,
        exaggeration=exaggeration
    )

    temps_generation = time.time() - debut

    duree_audio = wav.shape[-1] / model.sr
    rtf = temps_generation / duree_audio

    fichier = f"chatterbox_v3_{nom}.wav"

    ta.save(
        fichier,
        wav,
        model.sr
    )

    print()
    print(f"Fichier créé : {fichier}")
    print(f"Durée audio : {duree_audio:.1f} s")
    print(f"Temps génération : {temps_generation:.1f} s")
    print(f"RTF : {rtf:.2f}")
    print(f"Estimation pour 10 h : {rtf * 10:.1f} h")
    print()


print("=" * 60)
print("Terminé.")