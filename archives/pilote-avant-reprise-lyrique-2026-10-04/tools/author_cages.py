"""Manuscrit du pilote. Écrit le graphe éditorial, sans produire d'audio.

Le jeu et build_content lisent ensuite content/authored/cages.json.
"""
import json
from pathlib import Path
from textwrap import dedent

ROOT = Path(__file__).resolve().parents[1]
SCENES = []


def prose(value):
    return dedent(value).strip()


def flag(name):
    return {"flag": name}


def ally(name):
    return {"ally": name}


def no(condition):
    return {"not": condition}


def both(*conditions):
    return {"all": list(conditions)}


def effect(*flags, allies=(), inventory=(), unset=()):
    result = {}
    if flags:
        result["set_flags"] = list(flags)
    if allies:
        result["add_allies"] = list(allies)
    if inventory:
        result["add_inventory"] = list(inventory)
    if unset:
        result["unset_flags"] = list(unset)
    return result


def choice(label, target, results, good=None, bad=None, always=None, heroes=(), mods=(), base=.72):
    outcomes = {}
    for index, category in enumerate(("success", "complication", "failure")):
        destination = target[index] if isinstance(target, tuple) else target
        outcomes[category] = {"text": prose(results[index]), "next": destination,
                              "effects": dict((bad if index == 2 else good) or {}),
                              "audio_file": "audio/files/{segment_id}.wav"}
    modifiers = [{"label": "Talent du héros", "when": {"hero": h}, "delta": .08} for h in heroes]
    modifiers += [{"label": name, "when": condition, "delta": delta} for name, condition, delta in mods]
    return {"id": "", "text": label, "base_success": base, "complication_share": .22,
            "effects": always or {}, "modifiers": modifiers, "outcomes": outcomes}


def variant(name, when, values=None, choices=None, text=None, effects=None):
    result = {"id": name, "when": when}
    for key, value in (("values", values), ("choices", choices), ("text", text), ("effects", effects)):
        if value is not None:
            result[key] = value
    return result


def scene(suffix, rank, title, text, choices=None, variants=(), effects=None, kind="decision", ending=None):
    record = {"id": "cages_" + suffix, "arc": "cages", "kind": kind, "rank": rank,
              "act": min(5, 1 + max(0, rank-1)//3), "title": title, "text": prose(text),
              "variants": list(variants), "conditions": {}, "effects": effects or {},
              "audio_file": "audio/files/{segment_id}.wav"}
    if choices is not None:
        record["choices"] = choices
    if ending:
        record["ending"] = ending
    SCENES.append(record)
    return record


def identify_choices():
    for record in SCENES:
        sets = [("base", record.get("choices", []))]
        sets += [(v["id"], v.get("choices", [])) for v in record["variants"]]
        for group, choices in sets:
            for index, entry in enumerate(choices):
                entry["id"] = f"{record['id']}_{group}_{index}"
                additions = []
                if record["rank"] == 5:
                    additions.append(("Vue rapprochée" if index == 0 else "Approche discrète",
                                      flag("close_view" if index == 0 else "quiet_approach"), .06))
                if 7 <= record["rank"] <= 11:
                    additions.append(("Sorcière avertie", flag("alert"), -.06))
                if record["rank"] == 8:
                    additions.extend((("Clef reconnue", flag("key_seen"), .04),
                                      ("Approche discrète", flag("quiet_approach"), .04)))
                for name, condition, delta in additions:
                    modifier = {"label": name, "when": condition, "delta": delta}
                    if modifier not in entry["modifiers"]:
                        entry["modifiers"].append(modifier)


LOCATIONS = {
    "forest": {
        "cages_setting": "Le chemin des mûres traverse la forêt des Murmures. Lison y connaît chaque noisetier. Au-delà du vieux pont, pourtant, les hêtres cachent une maison dont vous n'avez jamais vu les fenêtres ouvertes.",
        "cages_house": "la maison au fond de la forêt des Murmures",
        "cages_fox_way": "un passage sous la haie du jardin, derrière la maison",
        "cages_merle_way": "le sentier des grands hêtres, qui longe les fenêtres de l'étage",
        "cages_view": "Les hêtres entourent une cour pavée. Une fenêtre basse donne sur le fournil ; à l'étage, un volet entrouvert laisse voir une chambre.",
        "cages_back": "la haie et le petit pont du bois",
        "cages_front": "le grand sentier qui descend jusqu'à la lisière",
        "cages_landmark": "le vieux pont",
    },
    "castle": {
        "cages_setting": "Lison est partie vers les mûriers de Valombre, le château abandonné. Les villageois ramassent les fruits dans son ancien verger. Depuis peu, une cheminée fume dans le logis qui borde la cour.",
        "cages_house": "le logis du château abandonné de Valombre",
        "cages_fox_way": "un trou sous le mur du verger, qui mène derrière le logis",
        "cages_merle_way": "l'allée du château, sous les fenêtres du logis",
        "cages_view": "Un logis habité borde la cour du château. Une fenêtre basse donne sur le fournil ; une chambre s'ouvre au-dessus de l'ancienne galerie.",
        "cages_back": "le passage du verger et la petite porte du rempart",
        "cages_front": "l'allée du château qui rejoint le pont principal",
        "cages_landmark": "le pont du château",
    },
    "mountain": {
        "cages_setting": "À Brumecime, la montagne des dragons, les mûriers poussent près du refuge des bergers. Lison y est montée ce matin. Le sentier traverse un bois avant de rejoindre le refuge, sous les rochers du col.",
        "cages_house": "le refuge de Brumecime, sur la montagne des dragons",
        "cages_fox_way": "un passage derrière les rochers, jusqu'au jardin du refuge",
        "cages_merle_way": "le sentier des bergers, devant les fenêtres du refuge",
        "cages_view": "Le refuge se dresse sous les rochers du col. Son jardin est clos de pierres. Une fenêtre du fournil et un volet à l'étage donnent sur la pente.",
        "cages_back": "le passage des rochers et les marches des bergers",
        "cages_front": "le large sentier du refuge qui descend vers la vallée",
        "cages_landmark": "les marches des bergers",
    },
    "city": {
        "cages_setting": "Lison allait cueillir les mûres près du quai d'Auralis, la cité flottante. Une nacelle relie le bois aux jardins suspendus. La maison d'une vieille chanteuse se trouve près du quai d'arrivée.",
        "cages_house": "la maison du quai d'Auralis, dans la cité flottante",
        "cages_fox_way": "la nacelle des jardiniers, puis une ouverture dans la haie du quai",
        "cages_merle_way": "la nacelle des voyageurs, puis l'allée sous les fenêtres du quai",
        "cages_view": "La nacelle s'arrête devant une maison aux volets bleus. Un jardin borde son fournil. Les cordes du quai chantent doucement dans le vent.",
        "cages_back": "le jardin du quai et la nacelle des jardiniers",
        "cages_front": "le quai principal et la nacelle des voyageurs",
        "cages_landmark": "le quai d'arrivée",
    },
    "ruins": {
        "cages_setting": "Les mûriers couvrent l'entrée de Nacreprofonde, des ruines souterraines oubliées. Lison les connaît bien. Sous la colline, une maison ancienne a été réparée et une lueur paraît derrière ses fenêtres.",
        "cages_house": "la maison restaurée dans les ruines de Nacreprofonde",
        "cages_fox_way": "l'escalier de service qui rejoint le jardin souterrain",
        "cages_merle_way": "le grand escalier et la rue qui passe sous les fenêtres",
        "cages_view": "La maison se dresse dans une rue souterraine éclairée par des cristaux. Son fournil ouvre sur un jardin de champignons ; une chambre donne sur l'ancien canal.",
        "cages_back": "l'escalier de service et la sortie derrière la colline",
        "cages_front": "la grande rue et les marches de l'entrée principale",
        "cages_landmark": "l'ancien canal",
    },
}
HEROES = {
    "knight": {"cages_intro": "Ton apprentissage de la chevalerie t'a préparé à secourir les autres. Cette fois, c'est ta petite sœur qui a besoin de toi."},
    "mage": {"cages_intro": "Tu connais quelques sortilèges, mais aucun ne te dira où Lison se trouve. Il faut partir sur ses traces."},
    "explorer": {"cages_intro": "Tu connais les chemins du village. Ta carte t'aidera à chercher Lison sans risquer de t'égarer à ton tour."},
    "keeper": {"cages_intro": "Les animaux du village te connaissent : tu les soignes lorsqu'ils sont blessés. Peut-être l'un d'eux a-t-il aperçu Lison."},
    "rogue": {"cages_intro": "Tu sais reconnaître les traces et te déplacer sans bruit. Tu comptes sur ces talents pour retrouver Lison."},
}
ITEMS = {
    "sword": {"cages_snare": "Glisser ton épée sous le lien du collet pour le couper", "cages_use": "Tu gardes ton épée basse. Sa pointe pourrait accrocher l'anneau sans que tu avances la main jusqu'à la sorcière."},
    "book": {"cages_snare": "Lire le sort qui desserre les attaches du collet", "cages_use": "Tu retrouves dans ton livre le sort qui desserre les attaches. Il pourrait faire glisser l'anneau jusqu'à ta main."},
    "amulet": {"cages_snare": "Protéger ta main avec l'amulette pour desserrer la boucle", "cages_use": "Ton amulette protégera ta main pendant quelques respirations. Tu la gardes prête pour un geste près de la femme."},
    "compass": {"cages_snare": "Faire chercher à la boussole la cheville enfouie du collet", "cages_use": "Tu demandes à ta boussole de chercher la clef d'argent. Son aiguille suit les mouvements de l'anneau."},
    "key": {"cages_snare": "Employer ta clé comme levier sous la cheville du collet", "cages_use": "Ta clé ouvre les portes ordinaires. Celle de la sorcière appartient au sort des cages."},
}
for item, label, success, complication in (
    ("sword", "Tirer l'anneau vers toi avec la pointe de ton épée", "Tu glisses la pointe sous l'anneau et ramènes la clef d'argent dans ta main.", "La pointe accroche l'anneau. Il tinte contre la lame, mais tu le retiens avant sa chute."),
    ("book", "Murmurer le sort du livre pour faire glisser la clef", "Tu murmures le sort des attaches. L'anneau glisse vers ta main sans heurter son support.", "Ton sort tire l'anneau, mais les clefs tintent. Tu le prends avant que la femme ne se retourne."),
    ("amulet", "Prendre la clef avec la protection de ton amulette", "L'amulette protège ta main du geste de la sorcière. Tu prends l'anneau et recules derrière les cages.", "La femme aperçoit ta main. L'amulette la protège le temps de prendre l'anneau, puis sa chaleur s'éteint."),
    ("compass", "Suivre l'aiguille pour saisir la clef au moment où elle est posée", "L'aiguille suit l'anneau jusque derrière les objets qui le cachent. Tu le prends pendant que la femme se retourne.", "La boussole indique l'anneau sous un pli du linge. Tu le tires, mais le linge bouge : tu dois reculer aussitôt."),
    ("key", "Accrocher l'anneau avec ta clé ancienne", "Tu accroches l'anneau avec l'extrémité dentée de ta clé et le tires hors de portée de la femme.", "Ta clé accroche l'anneau, mais les deux clefs tintent. Tu les serres dans ta paume avant de reculer."),
): 
    ITEMS[item].update(cages_take=label, cages_take_success=success, cages_take_complication=complication)
for item, label, escaped in (
    ("sword", "Glisser la lame dans la fente pour soulever le verrou", "Tu glisses la lame dans la fente et soulèves le verrou de l'autre côté."),
    ("book", "Murmurer le sort du livre pour faire glisser le verrou", "Tu murmures la formule des attaches. Le verrou glisse doucement dans sa rainure."),
    ("amulet", "Protéger ta main avec l'amulette pour déloger le verrou", "L'amulette protège ta main des éclats de bois. Tu fais céder la petite planche qui retient le verrou."),
    ("compass", "Chercher avec la boussole l'attache du verrou à desserrer", "L'aiguille t'indique une cheville mal enfoncée. Tu la retires et la pièce qui retient le verrou se détache."),
    ("key", "Ouvrir le verrou ordinaire avec ta clé ancienne", "Tu glisses ta clé dans la serrure. Le verrou est ordinaire : ta clé ancienne l'ouvre sans difficulté."),
):
    ITEMS[item].update(cages_escape=label, cages_escaped=escaped)
for item, action in (
    ("sword", "Tu glisses la lame sous la corde et la coupes sans toucher la patte."),
    ("book", "Tu murmures le sort des attaches. La boucle se détend autour de la patte."),
    ("amulet", "L'amulette protège tes doigts pendant que tu défais le nœud qui retient la boucle."),
    ("compass", "L'aiguille te montre où la cheville est enterrée. Tu la dégages, puis détends la corde."),
    ("key", "Tu glisses ta clé sous la cheville et la soulèves. La corde se détend."),
):
    ITEMS[item]["cages_snare_result"] = action

DEFAULTS = {
    "cages_mouse_memory": "Madame Souris est restée auprès de ses petits ; tu devras compter sur le merle pour distraire la femme.",
    "cages_fox_memory": "Maître Renard est resté près du collet. Personne ne peut surveiller le jardin pour toi.",
    "cages_merle_memory": "Maître Merle surveille une branche proche, prêt à te prévenir.",
    "cages_lison_memory": "En t'entendant, elle cesse de trembler et se rapproche des barreaux.",
    "cages_key_memory": "La clef d'argent manque encore. Tu dois choisir ce que tu peux tenter sans elle.",
    "cages_rescue_memory": "Les sept cages restent fermées et les oiseaux regardent tes mains.",
    "cages_promise_memory": "Tu n'as pas demandé à Madame Souris de quitter son abri.",
    "cages_return_memory": "Vous rejoignez la maison familiale après la tombée du jour.",
}


def animal_memory():
    return [
        variant("fox_here", ally("fox"), {"cages_fox_memory": "Maître Renard garde le jardin et surveille le chemin derrière vous."}),
        variant("fox_limp", both(ally("fox"), flag("fox_limp")), {"cages_fox_memory": "Maître Renard guette malgré sa patte douloureuse. Il ne pourra pas courir longtemps."}),
        variant("mouse_here", ally("mouse"), {"cages_mouse_memory": "Madame Souris s'abrite dans ta manche pour t'accompagner sans être vue."}),
        variant("lison_warned", flag("lison_warned"), {"cages_lison_memory": "Lison sait que tu viens et attend ton signal."}),
        variant("fox_cart", both(ally("fox"), flag("cart_road")), {"cages_fox_memory": "Maître Renard a suivi les roues jusqu'à l'arrêt et guette le chemin du retour."}),
        variant("fox_cart_limp", both(ally("fox"), flag("cart_road"), flag("fox_limp")), {"cages_fox_memory": "Maître Renard a rejoint l'arrêt plus lentement. Sa patte l'empêche de courir devant le chariot."}),
    ]


intro = scene("intro", 0, "La Maison aux Sept Cages", """
    Lison, ta petite sœur, aime changer la fin des chansons. Quand votre mère chante « Quand la nuit descend sur les bois, le bon chemin mène chez soi », Lison remplace le dernier vers par « Je garde une étoile pour toi », en te regardant.

    Ce matin, elle est partie cueillir des mûres avec son panier d'osier. {location_cages_setting}

    Lison n'est pas rentrée pour le repas. Votre mère s'inquiète et vous décidez de partir la chercher. Elle prend la route pour interroger les passants ; de ton côté, tu suis le sentier emprunté par Lison. Vous vous donnez rendez-vous à la lisière du bois.

    {hero_cages_intro} Tu glisses du pain et une gourde dans ton sac, puis tu emportes {item_name}.

    Un panier d'osier gît sous un noisetier, entouré de mûres. Tu reconnais celui de Lison au fil rouge noué à son anse. Le ruban bleu qu'elle portait ce matin pend à une branche ; tu le décroches et le gardes.
""", kind="intro")
intro["next"] = "cages_1"

scene("1", 1, "Le panier et le merle", """
    Tandis que tu examines le panier de Lison, un merle se pose sur une branche basse. Au lieu de s'envoler quand tu t'approches, il lisse une plume et prend la parole :

    « J'ai vu passer sur ce sentier\n    l'enfant qui portait ce panier.\n    Une vieille lui chantait un air ;\n    elles ont franchi une barrière. »

    L'oiseau se présente sous le nom de Maître Merle. Tu lui demandes où la vieille femme a emmené ta sœur. Il les a suivies jusqu'à une maison, mais ses volets étaient fermés. Il n'a pas osé s'approcher davantage, bien qu'il se vante de connaître toutes les voix du voisinage.

    Au-delà du panier, deux séries de pas s'éloignent vers le bois : de petites empreintes et d'autres plus profondes. Elles confirment le récit du merle. Tu peux lui demander de décrire la femme, ou suivre les traces avant que la pluie ne les efface.
""", [
    choice("Demander au merle de décrire la vieille femme", "cages_2", (
        "Maître Merle décrit le manteau gris de la femme et la clef d'argent à sa ceinture. Tu lui proposes de venir te montrer la maison.",
        "Le merle décrit la clef d'argent, puis s'égare dans un couplet sur son courage. Tu gardes ce renseignement, mais le jour avance.",
        "Maître Merle parle trop fort. Un volet claque au loin : quelqu'un a entendu sa voix. Tu rejoins les traces en lui demandant de baisser le ton."),
        good=effect("key_seen"), bad=effect("alert"), heroes=("keeper", "mage")),
    choice("Suivre les empreintes de Lison", "cages_2", (
        "Les empreintes rejoignent la route de la maison. Tu remarques aussi un collet tendu à son bord, sans marcher sur son lien.",
        "Tu suis les pas jusqu'à la route, mais une averse efface leur fin. Tu retiens les deux tournants déjà parcourus.",
        "Une flaque efface les dernières empreintes. Tu reviens au noisetier où tu as trouvé le panier, et Maître Merle accepte de te montrer le chemin qu'il a survolé."),
        good=effect("return_known"), heroes=("explorer", "rogue")),
], effects={"meet_characters": ["merle"], "add_allies": ["merle"]})

scene("2", 2, "Le renard qui gardait sa dignité", """
    En suivant le chemin indiqué par Maître Merle, tu entends remuer les feuilles au bord de la route. Un renard y est retenu par un collet : une boucle de corde serre sa patte. Il ramène sa queue autour de lui et redresse le museau à ton approche.

    « Je réfléchissais à la manière la plus élégante de sortir d'ici. » Maître Merle ouvre le bec, mais tu lui fais signe de se taire. Le renard se présente comme Maître Renard et te montre le piège : plus il tire, plus la boucle se resserre. La corde est fixée à une cheville enfoncée dans le sol.

    Quand tu lui parles de Lison, Maître Renard reconnaît la maison décrite par le merle. Sa propriétaire a tendu ce collet. Il connaît un passage derrière son jardin et pourra t'y conduire si tu parviens à le libérer.

    Tu poses ton sac et examines la boucle. Il faut la desserrer ou dégager la cheville sans forcer sur la patte du renard.
""", [
    choice("{item_cages_snare}", "cages_3", (
        "{item_cages_snare_result} Maître Renard peut poser sa patte au sol. Il fait deux pas prudents et accepte de te guider.",
        "{item_cages_snare_result} Maître Renard est libre, mais il boite. Il pourra guetter près du jardin ; courir lui serait trop douloureux.",
        "La boucle se resserre au premier geste. Maître Renard te demande d'arrêter avant de lui faire mal. Il t'indique le passage du jardin et t'envoie chercher Lison ; tu reviendras l'aider ensuite."),
        good=effect(allies=("fox",)), bad=effect("fox_trapped"), heroes=("mage", "rogue")),
    choice("Dégager la cheville pour détendre le collet", "cages_3", (
        "Tu retires la cheville pendant que Maître Renard cesse de tirer. La boucle se desserre. Il peut marcher et vous partez ensemble.",
        "La terre retient la cheville. Tu la dégages enfin, mais la patte du renard reste douloureuse. Il propose de surveiller plutôt que de courir.",
        "Une racine bloque la cheville. Maître Renard n'arrive pas à tourner sa patte ; il refuse que tu forces davantage et t'indique la route de la maison."),
        good=effect(allies=("fox",)), bad=effect("fox_trapped"), heroes=("knight", "keeper", "explorer")),
], effects={"meet_characters": ["fox"]})
# A complication really limits the fox's later role.
for entry in SCENES[-1]["choices"]:
    entry["outcomes"]["complication"]["effects"]["set_flags"] = ["fox_limp"]

fox_route = choice("Suivre Maître Renard par le jardin", "cages_4_fox", (
    "Maître Renard te conduit vers le passage du jardin. Maître Merle part surveiller la route et promet de prévenir si la femme sort.",
    "Vous choisissez le jardin. Une branche accroche ton manteau ; le renard t'attend tandis que le merle gagne son poste sur la route.",
    "Le passage du jardin est plus étroit que prévu. Tu y avances lentement derrière le renard, qui renonce à chercher une autre entrée."),
    always=effect("garden_route"), heroes=("rogue", "keeper"))
merle_route = choice("Suivre Maître Merle sous les fenêtres", "cages_4_merle", (
    "Maître Merle passe de branche en branche et te montre la route des fenêtres. Tu peux suivre sans perdre la maison de vue.",
    "Le merle gagne les fenêtres, mais t'attend après chaque tournant. Tu prends le temps de retenir les repères qu'il survole.",
    "Maître Merle va trop vite. Tu l'appelles doucement ; il revient te guider, mais vous devez suivre le chemin découvert, où la vieille femme pourrait vous apercevoir."),
    always=effect("window_route"), bad=effect("alert"), heroes=("explorer", "mage"))
scene("3", 3, "Deux guides, deux chemins", """
    {cages_guide_arrival} Maître Merle se pose sur une borne pour observer les abords de la maison.

    « Les fenêtres, c'est mon affaire ;\n    d'en haut, le monde est bien plus clair. »

    {cages_garden_offer} Maître Merle préfère {location_cages_merle_way}, pour observer la chambre avant d'entrer.

    Le jardin permet d'approcher la cuisine sans passer devant la porte ; les fenêtres donnent une meilleure vue de l'intérieur. Tu choisis par où poursuivre ta recherche.
""", [fox_route, merle_route], variants=[
    *animal_memory(),
    variant("fox_beside_you", ally("fox"), {"cages_guide_arrival": "Maître Renard te conduit jusqu'au dernier tournant. De là, vous apercevez la fumée de la cheminée.", "cages_garden_offer": "Maître Renard te montre {location_cages_fox_way}. Si tu pars avec le merle, il gardera le jardin pour votre retour."}),
    variant("fox_beside_limp", both(ally("fox"), flag("fox_limp")), {"cages_guide_arrival": "Maître Renard marche près de toi en ménageant sa patte. Au dernier tournant, vous apercevez la fumée de la cheminée."}),
    variant("fox_left_behind", no(ally("fox")), {"cages_guide_arrival": "Tu laisses Maître Renard près du collet et poursuis ton chemin avec le merle.", "cages_garden_offer": "Avant ton départ, le renard t'a indiqué {location_cages_fox_way}."}),
    variant("no_fox_route", no(ally("fox")), choices=[
        choice("Prendre le passage du jardin indiqué par le renard", "cages_4_fox", (
            "Tu suis les indications données près du collet. Maître Merle te rejoint au-dessus du jardin pour surveiller la maison.",
            "Tu trouves le jardin après un détour. Le merle reste près de toi : aucun renard libre ne peut garder la route derrière vous.",
            "Les indications ne suffisent pas au dernier tournant. Tu observes la fumée de la cheminée et rejoins le jardin par un passage plus visible."),
            always=effect("garden_route"), bad=effect("alert"), heroes=("explorer", "rogue")),
        merle_route,
    ]),
])

scene("4_fox", 4, "Le jardin de la maison", """
    En contournant le jardin, tu arrives derrière {location_cages_house}. {location_cages_view} Tu restes près du mur, hors de vue de la porte de la cuisine.

    {cages_fox_memory} Maître Merle reste assez loin des fenêtres pour ne pas se faire voir. Il te prévient d'un vers à peine soufflé :

    « Le volet bouge dans le vent ;\n    quelqu'un marche au-dedans. »

    Tu entends une cuillère heurter un bol, puis la voix de Lison. Elle remercie une femme pour la soupe et demande quand elle pourra rentrer. La réponse est trop basse pour parvenir jusqu'à toi.

    La voix vient de la chambre, au-dessus du fournil où l'on cuit le pain. Pour voir Lison, tu pourrais monter sur une caisse placée sous le volet. Il faudrait toutefois traverser les dalles devant la cuisine. Un arbre pousse contre le mur : ses branches te cacheraient, mais il faut y grimper.
""", [
    choice("Gagner la caisse pour regarder par le volet", "cages_5", (
        "Tu traverses les dalles et montes sur la caisse. Le volet entrouvert te laisse voir Lison assise près d'une table.",
        "La caisse craque sous ton pied. Tu atteins le volet, mais la femme tourne un instant la tête vers le jardin.",
        "Une dalle bascule et fait du bruit. Tu te caches derrière la caisse ; à travers l'ouverture, tu aperçois tout de même Lison près de la table."),
        good=effect("close_view"), bad=effect("alert"), heroes=("rogue", "knight")),
    choice("Monter dans l'arbre qui borde la chambre", "cages_5", (
        "Une branche solide te porte jusqu'au volet. Derrière le feuillage, tu vois Lison près de la table sans attirer son hôtesse.",
        "Tu atteins le volet, mais une brindille se casse. Lison regarde dehors ; la femme lui demande de se retourner.",
        "La première branche cède. Tu redescends, puis te places derrière le tronc ; le volet bat assez pour te montrer la chambre."),
        good=effect("quiet_approach"), bad=effect("alert"), heroes=("explorer", "keeper")),
], variants=animal_memory())

# The following scenes are shared only after the plan has left a visible trace.
POSITION_VARIANTS = [
    variant("visitor_room", flag("revelation_visitor"), {"cages_position": "La sorcière a réuni les sept cages dans la grande pièce pour l'échange. La visiteuse discute avec elle près de la porte ; tu arrives du côté de l'escalier."}),
    variant("departure_court", flag("revelation_departure"), {"cages_position": "Les sept cages attendent sur le chariot dans la cour. La sorcière s'occupe de sa bâche ; tu peux atteindre les serrures derrière la toile."}),
    variant("departure_road", flag("cart_road"), {"cages_position": "Le chariot est toujours arrêté près de {location_cages_landmark}. Tandis que la sorcière renoue la courroie à l'avant, tu peux approcher les cages cachées sous la bâche."}),
]


def rescue_memory():
    return [
        variant("lison_human", flag("lison_free"), {"cages_rescue_memory": "Lison serre ta main, encore étourdie d'avoir retrouvé sa forme humaine. En voyant les six cages fermées, elle se place près de toi pour guetter la sorcière."}),
        variant("others_human", flag("others_free"), {"cages_rescue_memory": "Les six autres enfants ont retrouvé leur forme. Ils se regroupent derrière toi, mais Lison reste dans sa cage : il faut encore aller la chercher."}),
        variant("lison_bird", both(flag("lison_bird"), no(flag("lison_free"))), {"cages_rescue_memory": "Lison s'est glissée entre les barreaux et reste un oiseau. Elle se cache contre ton manteau. Tu as pu la sortir de sa cage, mais l'enchantement tient encore."}),
    ]


def lison_choice(target="cages_11", label="Ouvrir d'abord la cage de Lison"):
    return choice(label, target, (
        "La clef tourne et le sort se défait. Les ailes de Lison disparaissent ; tu retrouves ta sœur devant toi. Elle te prend la main, puis désigne les six autres prisonniers.",
        "Lison retrouve sa forme, mais son pied heurte la cage vide. Elle la retient avant sa chute et te rejoint : vous devez aller plus vite désormais.",
        "La serrure résiste à ton geste précipité. Un barreau se desserre ; Lison s'y glisse sous sa forme d'oiseau et se cache dans ton manteau. Le sort n'est pas défait."),
        good=effect("lison_free", unset=("lison_bird",)), bad=effect("lison_bird", "alert"), heroes=("mage", "keeper"),
        mods=(("Lison prête au signal", flag("lison_warned"), .08), ("Chant couvre les bruits", flag("song_cover"), .07)))


def others_choice(target="cages_11", label="Ouvrir les autres cages pendant que Lison chante"):
    return choice(label, target, (
        "Tu passes la clef de serrure en serrure. Les six autres enfants retrouvent leur forme et se regroupent au signal de Lison. Sa propre cage reste à ouvrir.",
        "Les six enfants retrouvent leur forme. Le plus jeune se met à appeler sa mère ; tu t'accroupis pour le rassurer avant que la sorcière ne l'entende.",
        "Le premier verrou se coince et le temps passe. Aucun des six enfants n'a encore retrouvé sa forme ; Lison reprend son chant pour vous laisser une chance."),
        good=effect("others_free"), bad=effect("alert"), heroes=("rogue", "knight"),
        mods=(("Lison couvre les bruits", flag("song_cover"), .10), ("La chambre a été observée", flag("room_known"), .06)))


scene("9_key", 9, "Le refrain derrière les barreaux", """
    {cages_position}

    Avant d'employer la clef, tu cherches l'oiseau brun que tu as vu prendre la place de Lison. Parmi les sept chanteurs, l'un termine son refrain par « Je garde une étoile pour toi ». Tu lui réponds à voix basse. Il frappe deux fois son perchoir : c'est le signal que vous utilisez à cache-cache pour vous appeler sans parler.

    Tu lui montres la clef. Lison serre les barreaux avec ses pattes et vient contre ta main.

    Tu n'as plus de doute : cet oiseau est bien ta sœur. Mais la sorcière peut revenir à tout instant. Lison pourrait couvrir le bruit des serrures en chantant, ou guetter la femme pour te prévenir de son approche.

    Tu montres la serrure, puis la direction de la femme. Lison attend ton signal.
""", [
    choice("Demander à Lison de chanter pour couvrir les serrures", "cages_10", (
        "Lison reprend sa chanson à pleine voix. Son refrain couvre les petits bruits de la clef pendant que les autres oiseaux guettent la sorcière.",
        "La voix de Lison tremble. Maître Merle chante avec elle depuis sa cachette ; ensemble, ils couvrent encore les bruits de la serrure.",
        "La sorcière remarque que la chanson recommence trop souvent. Lison continue, mais vous avez moins de temps avant son retour."),
        always=effect("lison_warned"), good=effect("song_cover"), bad=effect("alert"), heroes=("keeper", "mage")),
    choice("Demander à Lison de guetter le retour de la sorcière", "cages_10", (
        "Lison se tourne vers le passage et fait le signal convenu quand un pas approche. Tu peux regarder les serrures sans perdre cet avertissement.",
        "Une cage voisine masque la vue de Lison. Elle se déplace sur son perchoir ; tu attends son signal avant de toucher aux serrures.",
        "La sorcière traverse trop vite pour que Lison te prévienne. Tu dois interrompre ton geste et rester caché jusqu'à son passage."),
        always=effect("lison_warned"), good=effect("door_watched"), bad=effect("alert"), heroes=("explorer", "rogue")),
], variants=[*POSITION_VARIANTS, *animal_memory()], effects=effect("lison_known"))

scene("9_caught", 9, "Une voix pour gagner du temps", """
    {cages_capture_position}

    La sorcière te demande de chanter. Tu comprends ce qu'elle prépare : si ta voix lui plaît, elle voudra une cage de plus. Tu réponds avec le refrain de Lison, mais tu t'arrêtes avant le dernier vers pour lui donner envie de réclamer la suite.

    Pendant qu'elle attend la suite de la chanson, tu examines {cages_capture_access}. La femme en ouvre le verrou avec une petite clef de fer. Celle d'argent reste à sa ceinture : la porte de ta prison ne porte donc pas le même enchantement que les cages.

    {cages_mouse_memory} Dehors, Maître Merle peut attirer la femme par son chant.

    Tu peux tenter de prendre l'anneau pendant leur intervention. Ou dégager le verrou avec ton objet, puis chercher la clef à couvert.
""", [
    choice("Appeler tes compagnons et tenter de prendre la clef", "cages_10", (
        "Le merle répond à ton refrain. La femme ouvre pour le faire taire ; tu prends l'anneau pendant qu'elle se retourne et rejoins les cages.",
        "La diversion te libère et tu prends la clef, mais la sorcière découvre ton passage. Elle vous cherchera près des oiseaux.",
        "La femme garde la clef en voulant saisir le merle. Elle oublie de refermer le verrou : tu sors, mais la clef d'argent reste à sa ceinture."),
        good=effect("has_key", inventory=("silver_key",)), bad=effect("alert"), mods=(("Souris prête à intervenir", ally("mouse"), .10),), heroes=("keeper", "knight")),
    choice("{item_cages_escape}", "cages_10", (
        "{item_cages_escaped} Tu sors à couvert et suis la femme jusqu'à l'endroit où elle pose l'anneau. Tu le prends avant de rejoindre les oiseaux.",
        "{item_cages_escaped} Tu récupères la clef, mais la femme entend ton pas. Tu rejoins les oiseaux par le côté qu'elle ne surveille pas.",
        "Tu parviens à dégager le verrou, mais la sorcière revient avant que tu prennes la clef. Tu profites du chant du merle pour gagner les cages sans elle."),
        good=effect("has_key", inventory=("silver_key",)), bad=effect("alert"), heroes=("rogue", "mage", "explorer")),
], variants=[*animal_memory(),
    variant("cart_capture", flag("cart_road"), {"cages_capture_position": "La femme t'a enfermé dans le grand coffre de provisions du chariot. Elle soulève son couvercle pour te questionner ; les oiseaux sont sous la bâche, tout près.", "cages_capture_access": "le couvercle"}),
], effects=effect("lison_known"))

no_key_choices = [
    choice("Écarter un barreau pour sortir Lison sous sa forme d'oiseau", "cages_11", (
        "Tu soulèves un barreau de bois. Lison passe entre les deux montants et se cache dans ton manteau. Elle est hors de la cage, mais reste un oiseau.",
        "Le barreau se fend avec un bruit sec. Lison sort et gagne ton manteau ; la sorcière a entendu le bois craquer.",
        "Le barreau ne bouge pas assez. Lison reste dans la cage et la femme approche : il faudra profiter de sa venue pour tenter encore la clef."),
        good=effect("lison_bird"), bad=effect("alert"), heroes=("knight", "rogue")),
    choice("Faire diversion pour reprendre la clef avant d'ouvrir une cage", "cages_11", (
        "Tu fais reprendre le chant à tes compagnons et approches l'anneau une seconde fois. Cette fois, la clef tombe dans ta main ; les cages restent à ouvrir.",
        "Tu récupères la clef, mais la diversion ne durera plus longtemps. Tu dois choisir la première cage tout de suite.",
        "La femme serre l'anneau contre elle. Tu reviens près des cages sans la clef ; elle connaît maintenant ton intention de délivrer les oiseaux."),
        good=effect("has_key", inventory=("silver_key",)), bad=effect("alert"),
        mods=(("Aide de la souris", ally("mouse"), .10), ("La porte est surveillée", flag("door_watched"), .06)), heroes=("keeper", "mage")),
]

scene("10", 10, "La première cage", """
    Auprès des cages, tu retrouves l'oiseau brun. Lison serre les barreaux en te regardant préparer ton geste. {cages_key_memory}

    Un oiseau aux plumes claires veut appeler sa mère ; un autre lui fait signe de se taire. Tu leur montres doucement le passage du retour.

    {cages_key_plan}

    La sorcière interrompt son activité. Lison frappe doucement son perchoir pour réclamer ton attention.
""", [lison_choice(), others_choice()], variants=[
    *POSITION_VARIANTS,
    variant("key_in_hand", flag("has_key"), {"cages_key_memory": "La clef d'argent est prête dans ta main.", "cages_key_plan": "Tu peux rendre sa forme à Lison pour agir à deux. Ou commencer par les six autres pendant que son chant couvre encore les bruits. Elle suit du regard les cages de ses voisins."}),
    variant("key_missing", no(flag("has_key")), choices=no_key_choices),
])

all_others = choice("Ouvrir les six autres cages avec Lison", "cages_12", (
    "Lison garde la porte pendant que tu ouvres les six cages. Les enfants retrouvent leur forme et suivent son signal pour rejoindre la sortie.",
    "Les six enfants retrouvent leur forme, mais la dernière cage heurte le sol. Lison regroupe tout le monde pendant que tu prépares le départ.",
    "La sorcière coupe l'accès aux six cages. Lison te tire vers le passage libre ; les autres prisonniers restent enfermés, et vous devrez revenir les chercher."),
    good=effect("others_free"), bad=effect("alert"), mods=(("Porte surveillée", flag("door_watched"), .08), ("Souris aide aux serrures", ally("mouse"), .06)), heroes=("rogue", "mage"))
safe_lison = choice("Préparer la sortie avec Lison avant le retour de la femme", "cages_12", (
    "Lison t'aide à dégager le passage. Vous pourrez repartir ensemble, puis montrer aux voisins où chercher les six enfants encore prisonniers.",
    "Vous dégagez le passage, mais la sorcière vous voit. Lison avance la première ; tu la suis en surveillant la femme. Les autres enfants restent prisonniers.",
    "La sorcière vous barre le passage. Lison en repère un autre, qu'elle ne surveille pas : vous vous y glissez en laissant les six cages fermées."),
    good=effect("return_known"), bad=effect("alert"), heroes=("explorer", "knight"))

finish_lison = lison_choice("cages_12", "Rejoindre Lison pendant que les enfants guettent")
finish_lison["outcomes"]["success"]["text"] = "La clef tourne. Lison retrouve sa forme et te prend la main. Les six enfants font signe depuis la sortie : vous pouvez les rejoindre."
finish_lison["outcomes"]["complication"]["text"] = "Lison retrouve sa forme, mais son pied heurte la cage vide. Elle la retient, puis vous rejoignez les six enfants qui guettent près de la sortie."
only_others = choice("Faire sortir les six enfants et demander une aide pour Lison", "cages_12", (
    "Tu conduis les six enfants jusqu'au passage de retour. Lison reste dans sa cage ; tu promets devant eux de revenir avec une aide qui ne laissera personne derrière.",
    "Les six enfants sortent, mais l'un doit attendre à couvert. Lison n'est pas délivrée ; les témoins qui t'accompagnent savent désormais où venir la chercher.",
    "Le groupe doit se cacher près de la sortie. Lison reste prisonnière : tu gardes les enfants ensemble avant d'organiser le retour et l'appel à l'aide."),
    good=effect("return_known"), bad=effect("late"), heroes=("knight", "explorer"))

bird_finish = choice("Reprendre la clef et rendre sa forme à Lison", "cages_12", (
    "Au signal de Lison, tu reprends l'anneau et ouvres sa cage vide. Le sort se défait : ta sœur retrouve sa forme ; les six autres prisonniers restent à délivrer.",
    "Tu reprends la clef et défais le sort de Lison, mais la femme vous voit. Les six autres cages restent fermées tandis que vous cherchez le passage libre.",
    "Tu ne parviens pas à reprendre l'anneau. Lison reste un oiseau dans ton manteau ; vous devez maintenant sortir avant que la femme vous sépare."),
    good=effect("lison_free", "has_key", unset=("lison_bird",), inventory=("silver_key",)), bad=effect("alert"),
    mods=(("Aide de la souris", ally("mouse"), .10),), heroes=("mage", "rogue"))
bird_escape = choice("Mettre Lison à l'abri et chercher de l'aide pour le sort", "cages_12", (
    "Tu gardes Lison dans ton manteau et rejoins l'accès du retour. Elle reste un oiseau, mais la sorcière ne peut plus la remettre dans sa cage.",
    "Lison sort avec toi sous sa forme d'oiseau. Elle doit se cacher quand la femme regarde la sortie ; les autres cages restent dans la maison.",
    "La femme vous cherche au seuil. Tu te caches jusqu'à ce qu'elle passe, avec Lison toujours oiseau contre ton épaule."),
    good=effect("return_known"), bad=effect("late"), heroes=("keeper", "explorer"))
bird_with_key = choice("Achever d'ouvrir la cage pour rendre sa forme à Lison", "cages_12", (
    "Tu reprends la serrure avec la clef que tu as gardée. Elle tourne enfin : Lison retrouve sa forme et te rejoint. Les six autres cages restent fermées.",
    "La serrure cède et le sort de Lison se défait. Ta sœur retrouve sa forme, mais la sorcière vous aperçoit avant que vous puissiez ouvrir les six autres cages.",
    "Le verrou reste bloqué et la sorcière approche. Lison reste un oiseau ; tu gardes la clef et l'emportes avec ta sœur à couvert."),
    good=effect("lison_free", unset=("lison_bird",)), bad=effect("alert"), heroes=("mage", "rogue"))

scene("11", 11, "Le dernier bruit de la serrure", """
    {cages_rescue_memory}

    {cages_witch_call} Les oiseaux se taisent à sa voix. Tu n'as plus que quelques instants avant qu'elle atteigne les cages.

    {cages_merle_watch}

    « Mon couplet ne la retient plus ;\n    partez avant qu'elle ait tout vu. »

    La dernière diversion s'achève. Tu peux poursuivre la délivrance ou garder libre le passage du retour ; ceux qui peuvent marcher attendent ton signal.
""", [lison_choice("cages_12", "Ouvrir la cage de Lison avant l'arrivée de la femme"), others_choice("cages_12", "Délivrer les six enfants pendant la dernière diversion")], variants=[
    *rescue_memory(), *animal_memory(),
    variant("witch_missing_key", flag("has_key"), {"cages_witch_call": "La sorcière porte la main à sa ceinture et découvre que la clef a disparu. Elle appelle sa chanteuse, puis s'avance vers les cages."}),
    variant("lison_first", flag("lison_free"), choices=[all_others, safe_lison]),
    variant("others_first", both(flag("others_free"), no(flag("lison_free"))), choices=[finish_lison, only_others]),
    variant("bird_first", both(flag("lison_bird"), no(flag("lison_free"))), choices=[bird_finish, bird_escape]),
    variant("bird_with_key", both(flag("lison_bird"), no(flag("lison_free")), flag("has_key")), choices=[bird_with_key, bird_escape]),
    variant("merle_on_road", flag("cart_road"), {"cages_merle_watch": "Maître Merle chante depuis un arbre, mais la sorcière ne l'écoute plus."}),
    variant("still_no_key", both(no(flag("has_key")), no(flag("lison_bird"))), choices=[
        choice("Sortir Lison par un barreau sans défaire son sort", "cages_12", (
            "Tu dégages un barreau pendant la diversion. Lison s'y glisse et gagne ton manteau. Elle reste un oiseau, mais tu peux l'emporter hors de portée.",
            "Le barreau se fend. Lison passe sous sa forme d'oiseau pendant que le merle couvre le bruit ; il faut rejoindre la sortie immédiatement.",
            "La femme approche avant que le barreau ne cède. Lison reste prisonnière. Tu dois sortir avec ce que tu sais et chercher une autre aide."),
            good=effect("lison_bird"), bad=effect("alert"), heroes=("knight", "rogue")),
        choice("Quitter les cages pour guider une intervention du village", "cages_12", (
            "Tu retiens les accès et les habitudes de la femme. Les sept prisonniers sont encore dans leurs cages ; tu peux montrer le chemin à une aide extérieure.",
            "Tu rejoins la sortie en laissant les cages fermées. Tu as vu la transformation et sais où venir chercher Lison avec une aide préparée.",
            "La femme coupe le passage principal. Tu te caches près du fournil avant de gagner le retour ; aucun prisonnier n'a encore été délivré."),
            good=effect("return_known"), bad=effect("late"), heroes=("explorer", "keeper")),
    ]),
])

COMPANY_VARIANTS = [
    variant("company_lison", flag("lison_free"), {"cages_company": "Lison avance près de toi, de nouveau humaine. Les six autres enfants sont encore prisonniers ; vous devrez raconter ce qu'il reste à accomplir."}),
    variant("company_others", flag("others_free"), {"cages_company": "Les six enfants libérés se regroupent près de toi. Lison attend encore dans sa cage ; vous devez donner au village les moyens de venir la chercher."}),
    variant("company_bird", both(flag("lison_bird"), no(flag("lison_free"))), {"cages_company": "Lison se serre contre ton épaule sous sa forme d'oiseau. Tu peux la ramener chez vous, mais il faudra encore défaire son enchantement."}),
    variant("company_full", both(flag("lison_free"), flag("others_free")), {"cages_company": "Lison et les six autres enfants sont libres. Vous devez les faire sortir ensemble sans perdre les plus petits dans le passage."}),
    variant("company_others_bird", both(flag("others_free"), flag("lison_bird"), no(flag("lison_free"))), {"cages_company": "Les six enfants libérés suivent ton signal. Lison reste un oiseau dans ton manteau ; vous devrez obtenir de l'aide pour défaire son sort."}),
]

scene("12", 12, "Le chemin du retour", """
    {cages_company}

    {cages_chase} Maître Merle surveille ses mouvements et se tait quand elle regarde dans votre direction.

    {cages_promise_memory}

    Tu reconnais {location_cages_front}, assez large pour marcher ensemble, et {location_cages_back}, plus discret mais étroit.

    {cages_fox_memory}

    C'est à la lisière que tu as promis de retrouver votre mère. Tu choisis le chemin qui permettra d'y arriver sans laisser personne derrière.
""", [
    choice("Prendre le chemin large pour garder tout le monde ensemble", "$ending", (
        "Tu gardes les voyageurs près de toi sur le chemin large. Maître Merle annonce la lisière ; vous rejoignez votre mère avant qu'elle ne reparte vers la maison.",
        "Vous prenez le chemin large, mais devez attendre à couvert pendant le passage de la sorcière. Vous rejoignez la lisière après la tombée du jour.",
        "La sorcière vous voit sur le chemin large. Tu gardes tout le monde à couvert jusqu'à ce qu'elle renonce à avancer vers les voix du village ; le retour prend une longue attente."),
        good=effect("home"), bad=effect("home", "late"), heroes=("knight", "explorer"),
        mods=(("Chemin reconnu", flag("return_known"), .08), ("Les oiseaux ont été avertis", flag("door_watched"), .04))),
    choice("Reprendre le passage discret en aidant les plus petits", "$ending", (
        "Tu fais passer chacun avant de quitter le passage discret. Vous retrouvez la lisière sans que la sorcière puisse suivre vos pas.",
        "Le passage vous cache, mais le dernier appui ralentit le groupe. Tu attends les plus petits et vous rentrez après la tombée du jour.",
        "Le passage discret est trop difficile pour avancer vite. Tu regroupes les voyageurs et attends le silence avant de finir le trajet ; votre mère vous retrouve tard à la lisière."),
        good=effect("home"), bad=effect("home", "late"), heroes=("rogue", "keeper"),
        mods=(("Renard peut guider", both(ally("fox"), no(flag("fox_limp"))), .10), ("Chemin reconnu", flag("return_known"), .06))),
], variants=[
    *COMPANY_VARIANTS, *animal_memory(),
    variant("road_chase", flag("cart_road"), {"cages_chase": "La sorcière rabat la bâche et cherche vos traces autour du chariot. Elle saisit un bâton : il faut sortir de sa portée."}),
    variant("no_children_out", both(no(flag("lison_free")), no(flag("lison_bird")), no(flag("others_free"))), choices=[
        choice("Rejoindre le village par le grand chemin", "$ending", (
            "Tu prends le grand chemin pendant que Maître Merle guette. Tu rejoins votre mère et lui demandes de prévenir les autres familles.",
            "La sorcière paraît sur le chemin. Tu attends à couvert avec le merle, puis rejoins votre mère après la tombée du jour.",
            "La sorcière suit tes pas. Tu restes caché jusqu'à ce qu'elle renonce à s'approcher des voix du village, puis tu rejoins votre mère."),
            good=effect("home"), bad=effect("home", "late"), heroes=("knight", "explorer"),
            mods=(("Chemin reconnu", flag("return_known"), .08),)),
        choice("Revenir à couvert par le passage du jardin", "$ending", (
            "Tu reprends le passage discret et rejoins la lisière. Votre mère t'attend : tu peux lui raconter où Lison est retenue.",
            "Le passage te cache, mais tu dois attendre que la femme s'éloigne. Tu rejoins la lisière après la tombée du jour.",
            "La sorcière te cherche près du jardin. Tu attends sans bouger, puis termines le trajet quand le merle t'annonce qu'elle est repartie."),
            good=effect("home"), bad=effect("home", "late"), heroes=("rogue", "keeper"),
            mods=(("Renard peut guider", both(ally("fox"), no(flag("fox_limp"))), .10),)),
    ]),
    variant("promise_return", flag("mouse_promised"), {"cages_promise_memory": "Les petits de Madame Souris attendent derrière le four. Il faut les emmener pour tenir ta promesse, mais ce détour retarderait votre fuite. Tu peux aussi gagner le village d'abord et revenir les chercher avec les voisins."}, choices=[
        choice("Chercher la famille de Madame Souris et prendre le passage discret", "$ending", (
            "Tu rejoins le fournil à couvert et emportes Madame Souris et ses petits dans ton sac. Vous gagnez la lisière par le passage discret.",
            "Tu emportes la famille de Madame Souris, mais le détour ralentit le retour. Vous rejoignez votre mère après la tombée du jour.",
            "La sorcière vous empêche de rejoindre le fournil. Tu dois gagner la lisière avec ceux qui sont près de toi ; les petits de Madame Souris attendent encore ton retour."),
            good=effect("home", "mouse_home"), bad=effect("home", "late"), heroes=("keeper", "rogue"),
            mods=(("Renard peut guider", both(ally("fox"), no(flag("fox_limp"))), .08), ("Chemin reconnu", flag("return_known"), .06))),
        choice("Rejoindre le village avant de revenir chercher la famille de la souris", "$ending", (
            "Tu conduis ceux qui sont près de toi jusqu'à la lisière. Tu préviens votre mère que les petits de Madame Souris attendent encore le refuge promis.",
            "Vous rejoignez le village après une attente à couvert. Les petits de Madame Souris sont restés au fournil ; tu devras repartir pour tenir ta promesse.",
            "Le retour prend une longue attente. À la lisière, tu préviens votre mère que les petits de Madame Souris sont encore dans la maison : il faudra retourner les chercher."),
            good=effect("home"), bad=effect("home", "late"), heroes=("knight", "explorer")),
    ]),
], effects={"events": ["cages:return"]})

ENDING_VARIANTS = [
    variant("late_return", flag("late"), {"cages_return_memory": "Le retour a pris une longue attente. Votre mère vous retrouve tard à la lisière et vous enveloppe dans son manteau avant de rentrer."}),
    variant("timely_return", no(flag("late")), {"cages_return_memory": "Votre mère vous retrouve à la lisière. Elle serre ceux qui reviennent contre elle, puis vous accompagne jusqu'à la maison familiale."}),
    variant("mouse_at_home", flag("mouse_home"), {"cages_mouse_ending": "Votre mère fait une place à Madame Souris et à ses petits près du four. La souris vérifie que chacun est installé, puis te remercie d'avoir tenu parole."}),
    variant("mouse_promise_pending", both(flag("mouse_promised"), no(flag("mouse_home"))), {"cages_mouse_ending": "Les petits de Madame Souris attendent encore au fournil. Tu décris leur abri aux voisins et rappelles le refuge que tu leur as promis."}),
    variant("fox_free_end", ally("fox"), {"cages_fox_ending": "Maître Renard refuse les acclamations, accepte un peu d'eau et repart vers le bois."}),
    variant("fox_trap_end", no(ally("fox")), {"cages_fox_ending": "Tu indiques aussi le collet où Maître Renard attend. Un voisin prend sa lanterne et part le dégager."}),
]

scene("end_full", 13, "La chanson retrouvée", """
    {cages_return_memory}

    Lison et les six autres enfants racontent la chambre, les cages et la clef d'argent. Votre mère les écoute en leur servant du pain. Les familles viennent les chercher ; plusieurs voisins repartent ensemble pour empêcher la sorcière de recommencer.

    {cages_mouse_ending} {cages_fox_ending}

    Quand la maison s'apaise, Lison reprend votre chanson. {cages_final_song} Maître Merle, à la fenêtre, écoute jusqu'au bout avant de répondre :

    « Ce soir, je vous laisse chanter ;\n    j'aurai demain pour me vanter. »

    Tu ris avec Lison. Votre mère pose deux bols chauds devant vous, puis vous fait une place près du feu. Pour ce soir, vous avez assez couru.
""", kind="ending", ending="full", variants=ENDING_VARIANTS)

scene("end_lison", 13, "Une sœur et six promesses", """
    {cages_return_memory}

    Votre mère serre Lison dans ses bras. Ta sœur lui raconte les six enfants encore prisonniers et les barreaux contre lesquels leurs ailes se froissent. Les voisins viennent avec leurs lanternes ; Lison leur décrit la clef et tu leur montres le chemin.

    {cages_mouse_ending} {cages_fox_ending}

    Lison reste près de toi au repas. Elle ne finit pas sa chanson : elle écoute les voix qui se rassemblent dehors. Maître Merle attend à la fenêtre sans réclamer d'applaudissements. Quand les lanternes s'éloignent, ta sœur garde sa main dans la tienne. Vous attendez le retour des voisins et des six enfants.
""", kind="ending", ending="lison", variants=ENDING_VARIANTS)

scene("end_bird", 13, "Lison à la fenêtre", """
    {cages_return_memory}

    Lison revient sous la forme d'un oiseau. Lorsque tu racontes sa transformation, votre mère te regarde sans comprendre. Alors Lison chante « Je garde une étoile pour toi ». Votre mère reconnaît la voix de sa fille et lui tend les mains. Les barreaux ne la retiennent plus, mais il faut encore défaire le sort.

    {cages_other_ending}

    Tu fixes un perchoir près de la fenêtre. Lison s'y pose, puis revient contre ton épaule. Dehors, les voisins préparent leur départ pour défaire le sort. Tu traces le chemin sur une feuille et votre mère l'emporte avec elle.

    {cages_mouse_ending} {cages_fox_ending}

    Le soir, tu reprends doucement la chanson. Lison ajoute la fin que tu connais. Maître Merle lui fait une place près de lui, mais ta sœur préfère ton épaule. Ses petites pattes s'accrochent à ton col. Tu attends avec elle que les lanternes reparaissent au bout du chemin.
""", kind="ending", ending="bird", variants=[*ENDING_VARIANTS,
    variant("other_children_home", flag("others_free"), {"cages_other_ending": "Les six autres enfants ont retrouvé leur forme et leurs familles. Leur récit confirme le tien : ils seront des témoins pour ceux qui iront chercher la clef."}),
])

scene("end_others", 13, "Le chemin qu'il faut reprendre", """
    {cages_return_memory}

    Les six enfants libérés rejoignent leurs familles. Lison reste dans sa cage. Votre mère écoute leur récit, puis prend une lanterne. Tu lui montres où chercher ta sœur et comment reconnaître son refrain. Les voisins arrivent avec des cordes et des outils ; aucun ne veut la laisser seule là-bas.

    {cages_mouse_ending} {cages_fox_ending}

    Maître Merle repart devant les lanternes pour surveiller la sorcière. L'un des enfants s'assied près de toi et te raconte comment Lison chantait pour rassurer les plus petits. Tu lui demandes de reprendre le dernier vers. Vous le chantez ensemble, doucement, en gardant les yeux sur la route. La chaise de Lison reste vide.
""", kind="ending", ending="others", variants=ENDING_VARIANTS)

scene("end_pending", 13, "Le secret de la maison", """
    {cages_return_memory}

    Aucun des sept enfants n'est libre. Tu poses le ruban bleu sur la table et racontes la transformation de Lison. Votre mère t'écoute sans t'interrompre. Puis elle noue le ruban à son poignet et appelle les voisins. Tu leur décris les accès et la clef qu'il faut rapporter.

    {cages_mouse_ending} {cages_fox_ending}

    Maître Merle revient à la fenêtre et indique où la sorcière se trouve encore. Une à une, les lanternes s'allument. Votre mère te demande de garder le feu pendant son absence ; elle sait maintenant où chercher Lison. Tu voudrais la suivre, mais tes jambes tremblent encore. Le merle s'arrête près de toi avant de rejoindre les voisins.
""", kind="ending", ending="pending", variants=ENDING_VARIANTS)


def write_manuscript():
    defaults = {
        **DEFAULTS,
        "cages_scenario_hint": "La femme descend dans la cuisine et laisse les oiseaux dans la chambre.",
        "cages_merle_watch": "Maître Merle chante encore près d'une fenêtre, mais la femme ne l'écoute plus.",
        "cages_guide_arrival": "Tu poursuis ta recherche avec Maître Merle.",
        "cages_garden_offer": "Tu te souviens du passage du jardin indiqué par Maître Renard.",
        "cages_witch_call": "La sorcière a cessé de fredonner. Elle vérifie la clef à sa ceinture et s'avance vers les cages.",
        "cages_key_plan": "Sans la clef, tu peux tenter de reprendre l'anneau ou dégager un barreau pour mettre Lison hors de portée. Elle resterait un oiseau : sortir de la cage ne défait pas son sort.",
        "cages_final_song": "Cette fois, tu chantes son dernier vers avec elle.",
        "cages_position": "Les sept cages sont dans la chambre de l'étage. Tu retrouves la fenêtre où tu as vu la transformation et la porte qui donne sur le couloir.",
        "cages_capture_position": "La femme t'a enfermé dans le cellier. Elle ouvre un instant pour te questionner, tout en gardant la clef des oiseaux à sa ceinture.",
        "cages_capture_access": "la porte",
        "cages_chase": "La sorcière ferme la porte, puis cherche le bruit des pas. Elle doit vous rattraper pour vous ramener aux cages.",
        "cages_company": "Tu n'as encore pu sortir aucun prisonnier. Tu dois rentrer avec les faits que tu as vus et montrer le chemin à ceux qui viendront vous aider.",
        "cages_mouse_ending": "Madame Souris est restée auprès des siens. Tu décris son abri aux adultes pour qu'ils ne l'abîment pas en entrant dans la maison.",
        "cages_fox_ending": "Tu te souviens de Maître Renard et de son collet près de la route.",
        "cages_other_ending": "Les six autres enfants sont encore prisonniers. Tu décris leurs cages aux voisins pour qu'ils puissent les retrouver eux aussi.",
    }
    identify_choices()
    # Fragments supplied by a variant can themselves use the fixed catalogs.
    arc = {
        "id": "cages", "title": "La Maison aux Sept Cages",
        "description": "Retrouver Lison changée en oiseau, avec Maître Merle, Maître Renard et Madame Souris.",
        "decision_count": 12, "conditions": {}, "start": "cages_intro", "inline_consequences": True,
        "text_values": defaults, "hero_overrides": HEROES, "location_overrides": LOCATIONS, "item_overrides": ITEMS,
        "revelations": [
            {"id": "quiet", "actor": "la sorcière", "text": "La maison silencieuse : la sorcière garde les sept cages dans sa chambre."},
            {"id": "visitor", "actor": "la visiteuse", "text": "L'échange des voix : une visiteuse vient choisir un oiseau parmi les prisonniers."},
            {"id": "departure", "actor": "la sorcière", "text": "Le départ du chariot : la sorcière prépare le transport de ses sept cages."},
        ],
        "endings": [
            {"scene": "cages_end_full", "when": both(flag("lison_free"), flag("others_free"))},
            {"scene": "cages_end_lison", "when": flag("lison_free")},
            {"scene": "cages_end_bird", "when": flag("lison_bird")},
            {"scene": "cages_end_others", "when": flag("others_free")},
            {"scene": "cages_end_pending", "when": {}},
        ],
    }
    # Visits are recorded without putting a catalog paragraph after a choice.
    intro["variants"].extend(variant("visit_" + location, {"location": location}, effects={"visit_locations": [location]}) for location in LOCATIONS)
    source = {"format": "authored_graph", "arc": arc, "scenes": SCENES}
    path = ROOT / "content/authored/cages.json"
    path.write_text(json.dumps(source, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ROOT / "content/arcs/cages.json").write_text(json.dumps(arc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ROOT / "content/scenes/cages.json").write_text(json.dumps({"scenes": SCENES}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(SCENES)} scènes écrites pour La Maison aux Sept Cages.")


scene("4_merle", 4, "Les volets bleus", """
    En suivant Maître Merle, tu arrives devant {location_cages_house}. {location_cages_view} Par une fenêtre ouverte, tu aperçois une femme au manteau gris. Une clef brille à sa ceinture.

    Un chant te parvient de la chambre, au-dessus du fournil où l'on cuit le pain. Tu reconnais la voix de Lison, puis le dernier vers qu'elle aime changer. La vieille femme lui demande de le reprendre.

    « Sa chanson monte jusqu'au toit ;\n    je peux l'écouter près de toi. »

    Pour voir Lison, tu dois atteindre le volet entrouvert. Un treillis fixé au mur permettrait de grimper jusque-là, mais une latte se détache. Un banc offre un autre appui ; il faudrait passer devant la porte de la cuisine pour y monter. Maître Merle s'installe face à cette porte pour te prévenir si la femme sort.
""", [
    choice("Grimper au treillis jusqu'au volet", "cages_5", (
        "Tu montes jusqu'à une latte solide. Le volet laisse voir Lison, la vieille femme et une cage vide suspendue près de la table.",
        "Le treillis gémit. Tu atteins le volet, mais dois rester immobile tandis que la femme écoute le bruit du mur.",
        "Une latte se détache. Tu redescends derrière le banc et profites du volet qui bat pour voir la chambre."),
        good=effect("quiet_approach"), bad=effect("alert"), heroes=("explorer", "rogue")),
    choice("Passer par le banc pendant que le merle guette", "cages_5", (
        "Le merle attend que la porte se referme. Tu gagnes le banc et vois Lison près de la table, sans être aperçu de la cuisine.",
        "Tu rejoins le banc, mais Maître Merle laisse échapper une note. La vieille femme regarde dehors avant de revenir à Lison.",
        "La porte s'ouvre quand tu traverses. Tu te baisses derrière le banc ; la femme ne te voit pas, mais elle ferme la porte à clef."),
        good=effect("close_view"), bad=effect("alert"), heroes=("keeper", "knight")),
])

scenario_choices = {}
for name in ("quiet", "visitor", "departure"):
    scenario_choices[name] = [
        choice("Répondre au refrain pour prévenir Lison", "cages_6_" + name, (
            "Tu reprends votre dernier vers. L'oiseau se tourne vers toi et frappe deux fois le perchoir, votre ancien signal de cache-cache. Lison sait que tu es là.",
            "Lison reconnaît le refrain et te répond. La sorcière entend une seconde voix : elle referme le volet avant de descendre.",
            "Ta voix porte jusque dans la cuisine. Lison te reconnaît, mais la sorcière tend l'oreille et annonce qu'elle vérifiera le jardin."),
            always=effect("lison_warned"), bad=effect("alert"), heroes=("keeper", "mage")),
        choice("Rester à couvert et observer la chambre", "cages_6_" + name, (
            "Tu retiens la place de la cage et celle de la porte. La sorcière range la clef à sa ceinture sans soupçonner ta présence.",
            "Tu observes la chambre jusqu'à ce que la sorcière approche du volet. Tu recules en gardant le trajet de la porte en mémoire.",
            "Le volet se referme avant que tu voies la serrure. Tu as vu la transformation, mais Lison ignore encore que tu viens la chercher."),
            good=effect("room_known"), heroes=("explorer", "rogue")),
    ]

scene("5", 5, "La transformation de Lison", """
    Dans la chambre, Lison se lève de table et demande à rentrer chez vous. La vieille femme lui barre le passage : elle veut garder cette belle voix auprès d'elle. Ta sœur recule. La femme détache de sa ceinture un anneau portant une clef d'argent et en touche l'épaule de Lison.

    Le tablier de Lison tombe sur la chaise. À la place de ta sœur, un petit oiseau brun bat des ailes. Sept cages sont alignées contre le mur, dont une vide. La femme y enferme l'oiseau et tourne la clef dans la serrure. Derrière les barreaux, une voix tremblante achève votre chanson : « Je garde une étoile pour toi. »

    Tu retiens un cri. La sorcière remet la clef à sa ceinture, puis quitte la chambre.

    {cages_scenario_hint}

    Lison reste derrière les barreaux. Tu peux reprendre votre refrain pour lui faire savoir que tu viens, ou observer encore l'accès à la chambre sans révéler ta présence.
""", scenario_choices["quiet"], variants=[
    variant("visitor_plot", flag("revelation_visitor"), choices=scenario_choices["visitor"]),
    variant("departure_plot", flag("revelation_departure"), choices=scenario_choices["departure"]),
    variant("quiet_hint", flag("revelation_quiet"), {"cages_scenario_hint": "En bas, la femme remet sa soupe sur le feu. La maison sera bientôt plongée dans le silence du soir."}),
    variant("visitor_hint", flag("revelation_visitor"), {"cages_scenario_hint": "Une voix l'appelle du seuil : sa visiteuse vient choisir un oiseau. La sorcière lui promet de faire entendre sa nouvelle chanteuse."}),
    variant("departure_hint", flag("revelation_departure"), {"cages_scenario_hint": "Dans la cour, un chariot attend sous une bâche. La sorcière annonce qu'elle emportera ses oiseaux avant que les villageois viennent les chercher."}),
], effects=effect("transformation_seen"))

MOUSE_TEXT = """
    Tu quittes ta cachette et contournes la maison jusqu'à la porte du fournil. Une souris apparaît sur le seuil, une miette entre les pattes. Tu t'accroupis et lui parles de Lison.

    Elle se présente comme Madame Souris et écoute ton récit sans lâcher sa miette. Les six autres oiseaux étaient des enfants, eux aussi : elle les a vus arriver ici. Un jour, la femme a ouvert une cage avec la clef d'argent pour faire porter du bois à son prisonnier ; il a aussitôt retrouvé sa forme humaine. Briser un barreau laisse sortir un oiseau ; tourner cette clef dans la serrure pour l'ouvrir défait le sort.

    {cages_mouse_plot}

    Elle connaît un crochet près du four, où la femme pose sa clef pour pétrir le pain. Elle pourrait aussi la décrocher de sa ceinture.

    « Si elle me voit vous aider, elle nous chassera. Mes trois petits sont derrière le four. Pouvez-vous nous accueillir chez vous ? » Tu peux promettre un refuge à sa famille, ou lui demander seulement des renseignements.
"""
for plot, detail in (
    ("quiet", "D'après Madame Souris, la femme prépare son pain chaque soir. Elle retirera alors sa clef, mais restera près du crochet."),
    ("visitor", "La visiteuse veut emporter un oiseau contre une bague d'or. La sorcière descend les cages dans la grande pièce."),
    ("departure", "La vieille femme emporte ses cages sur le chariot. Madame Souris l'a entendue parler d'une autre demeure. Si elle part, son crochet à clefs restera vide."),
):
    scene("6_" + plot, 6, "Madame Souris et ses petits", MOUSE_TEXT, [
        choice("Promettre un refuge à sa famille et demander son aide", "cages_7_" + plot, (
            "Madame Souris accepte. Elle montre la sortie de son nid et vient près de toi : tu sais maintenant où chercher ses petits avant de partir.",
            "Elle accepte ta promesse, mais hésite à quitter ses petits. Elle t'accompagne en longeant les murs et te demande de ne pas la faire courir devant la sorcière.",
            "Madame Souris entend la femme approcher et retourne à son nid. Elle ne participera pas au vol de la clef, mais ta promesse de refuge reste faite."),
            always=effect("mouse_promised"), good=effect(allies=("mouse",)), bad=effect("mouse_afraid"), heroes=("keeper", "knight")),
        choice("Lui demander les habitudes de la sorcière sans l'exposer", "cages_7_" + plot, (
            "Madame Souris décrit le crochet de la clef et la porte de la chambre. Elle te confie ces renseignements, puis reste auprès de ses petits.",
            "Elle explique où trouver le crochet, mais un bruit l'interrompt avant la fin. Tu sais quand la clef peut être posée ; tu devras vérifier le chemin toi-même.",
            "La sorcière revient près du four. Madame Souris se cache avant de te décrire le crochet. Tu gardes son explication sur la clef, mais tu dois observer les habitudes de la femme."),
            good=effect("key_schedule"), heroes=("explorer", "mage", "rogue")),
    ], variants=[variant("plot_detail", {}, {"cages_mouse_plot": detail})], effects={"meet_characters": ["mouse"]})


def approach_choices(plot, public_label, secret_label):
    public_results = {
        "quiet": (
            "Tu frappes et demandes un abri pour la nuit. La sorcière ouvre, intriguée par ta voix, et t'invite à entrer.",
            "La femme te laisse entrer, mais verrouille la porte derrière toi. Tu remarques l'accès au fournil : il faudra revenir par là.",
            "La femme remarque que tu regardes vers l'étage. Elle te saisit par le manteau et t'enferme dans le cellier."),
        "visitor": (
            "Tu proposes de faire entendre Maître Merle. La visiteuse accepte ; la sorcière te fait entrer pour que tu lui présentes ton chanteur.",
            "La visiteuse réclame le chant du merle. La sorcière te laisse entrer à contrecœur et ferme la porte pour te garder près d'elle.",
            "En parlant, tu regardes trop souvent les cages. La sorcière comprend ce qui t'intéresse et t'enferme dans le cellier."),
        "departure": (
            "Tu inventes l'histoire d'un panier perdu et interpelles la sorcière. Elle s'arrête pour te répondre ; tu avances dans la cour pendant qu'elle parle.",
            "La femme répond avec impatience à ta question sur le panier. Tu t'approches du chariot, mais elle garde un œil sur toi.",
            "La sorcière surprend ton regard vers les cages. Elle te saisit par le manteau et te ramène dans la maison pour t'enfermer dans le cellier."),
    }
    secret_results = {
        "quiet": (
            "Au signal que tu lui donnes, Maître Merle chante à la fenêtre. La femme se tourne vers lui et tu passes la porte du fournil.",
            "Tu entres dans le fournil, mais la femme se retourne trop tôt. Le merle prolonge son chant pour t'éviter d'être découvert.",
            "La porte du fournil grince. La sorcière te découvre, t'attrape par le manteau et t'enferme dans le cellier."),
        "visitor": (
            "Tu passes la porte du fournil tandis que les deux femmes discutent. Sans faire de bruit, tu gagnes le pied de l'escalier.",
            "Tu entres, mais une marche grince. Tu attends que la visiteuse reprenne la parole avant de poursuivre vers l'escalier.",
            "La sorcière t'aperçoit au pied de l'escalier et te barre le passage. Elle t'enferme dans le cellier."),
        "departure": (
            "Tu attends derrière le mur que la sorcière pousse son chariot sur le chemin. Le merle vole au-dessus des cages ; tu les suis à couvert.",
            "Le chariot quitte la cour. Tu te caches à chaque fois que la femme se retourne, en suivant le merle pour ne pas perdre les cages.",
            "Avant de partir, la sorcière te découvre près de la bâche. Elle te ramène dans la maison et t'enferme dans le cellier."),
    }
    return [
        choice(public_label, ("cages_8_" + plot + "_public", "cages_8_" + plot + "_public", "cages_8_caught"), public_results[plot],
            always=effect("public_plan"), good=effect("sorceress_distracted"), bad=effect("caught", "alert"), heroes=("knight", "keeper")),
        choice(secret_label, ("cages_8_" + plot + "_secret", "cages_8_" + plot + "_secret", "cages_8_caught"), secret_results[plot],
            always=effect("secret_plan"), good=effect("quiet_approach"), bad=effect("caught", "alert"), heroes=("rogue", "explorer")),
    ]

scene("7_quiet", 7, "Une place près du feu", """
    À travers la porte du fournil, tu vois la sorcière s'installer près du feu avec sa soupe. Elle fredonne la chanson de Lison, mais bute sur le dernier vers. Elle veut l'entendre encore : il te faudra détourner son attention avant qu'elle remonte vers les cages.

    {cages_mouse_memory} Maître Merle te rejoint sur une branche proche. Tu lui demandes d'attendre que tu lèves la main avant de chanter.

    Si tu frappes à la porte en te présentant comme un enfant égaré, elle voudra sans doute écouter ta voix. Tu pourrais ainsi l'occuper en parlant. Tu peux aussi entrer par le fournil pendant que le merle l'attire à la fenêtre, puis prendre la clef sans te présenter.

    La sorcière pose son bol et se lève. Tu attends son prochain pas pour choisir où te placer.
""", approach_choices("quiet", "Frapper et demander un abri pour parler à la sorcière", "Entrer par le fournil pendant le chant du merle"), variants=animal_memory())

scene("7_visitor", 7, "La visiteuse au châle gris", """
    De la porte du fournil, tu entends les deux femmes discuter dans la pièce voisine. La visiteuse veut emporter le meilleur chanteur. La sorcière lui présente ses oiseaux un à un, comme s'ils étaient des bijoux.

    « Celui-ci hésite, dit la visiteuse. Faites chanter le nouveau. » Lison commence son refrain. Tu entends sa voix trembler, puis reprendre le dernier vers plus fermement. Elle essaie de gagner du temps entre deux chansons.

    {cages_mouse_memory}

    Maître Merle s'agite quand la visiteuse prétend que tous les oiseaux du bois chantent pareil. Tu pourrais lui proposer de chanter à la fenêtre, puis frapper pour le présenter aux deux femmes. Elles s'intéresseraient à sa voix pendant que tu approcherais la clef. L'escalier du fournil offre une autre possibilité : sa rambarde donne sur leur table, où tu pourrais observer la clef sans être vu.

    La visiteuse pose son manteau. L'échange n'est pas encore conclu : tu peux te présenter ou entrer à couvert.
""", approach_choices("visitor", "Proposer à la fenêtre le chant de Maître Merle", "Profiter de la discussion pour entrer par l'escalier"), variants=animal_memory())

scene("7_departure", 7, "Les cages sous la bâche", """
    La sorcière porte deux cages à la fois dans la cour. Elle les pose sur le chariot, cale les pieds avec de la paille et tend une bâche contre le vent. Lison chante dès que le linge passe devant sa cage, comme pour laisser sa voix dans la maison.

    Tu restes derrière le mur du jardin pour suivre ses préparatifs. {cages_mouse_memory}

    La femme retourne chercher son sac en laissant le chariot dans la cour. Tu pourrais prétendre qu'un voisin cherche son panier et lui demander si elle l'a trouvé : cette conversation retarderait son départ. Ou attendre qu'elle parte, puis suivre le chariot sans te montrer pour reprendre la clef au premier arrêt.

    Maître Merle pourra te guider depuis les arbres. Si les cages quittent la cour, cependant, tu devras t'éloigner de la maison où vivent les petits de Madame Souris. Tu décides avant que la femme reprenne les poignées du chariot.
""", approach_choices("departure", "Retenir la sorcière dans la cour en parlant du panier", "Suivre le chariot à couvert jusqu'à son premier arrêt"), variants=animal_memory())


def key_choices(next_scene="cages_9_key"):
    return [
        choice("Demander à Maître Merle de distraire la sorcière", (next_scene, next_scene, "cages_9_caught"), (
            "Tu fais signe à Maître Merle de chanter. La sorcière tourne la tête vers lui ; tu saisis la clef d'argent et la retiens dans ta paume.",
            "Tu prends la clef, mais son anneau tinte. La sorcière se retourne ; tu rejoins les cages pendant que le chant continue de l'occuper.",
            "La sorcière voit ta main près de la clef et la reprend. Elle te met à l'écart sous un verrou ordinaire : tu n'as pas la clef des oiseaux."),
            good=effect("has_key", inventory=("silver_key",)), bad=effect("caught", "alert"),
            mods=(("Madame Souris participe", ally("mouse"), .10), ("Merle a été averti", flag("lison_warned"), .04)), heroes=("keeper", "rogue")),
        choice("{item_cages_take}", (next_scene, next_scene, "cages_9_caught"), (
            "{item_cages_take_success}",
            "{item_cages_take_complication}",
            "La sorcière revient avant ton geste. Elle garde la clef et t'enferme à l'écart ; ton objet reste avec toi, mais la délivrance est retardée."),
            good=effect("has_key", inventory=("silver_key",)), bad=effect("caught", "alert"),
            mods=(("Habitudes connues", flag("key_schedule"), .10),), heroes=("mage", "explorer")),
    ]

def key_variants(support="ceinture"):
    if support == "ceinture":
        label = "Faire décrocher la clef par Madame Souris pendant ta diversion"
        success = "Tu poses une question à la sorcière. Madame Souris longe sa ceinture et décroche la clef ; elle la fait glisser dans ta main, puis rejoint ta manche."
        complication = "La souris décroche la clef, mais la femme sent ses pattes. Tu récupères l'anneau tandis que Madame Souris se cache sous ton manteau."
        failure = "La femme chasse la souris de sa ceinture et garde la clef. Madame Souris se cache ; la sorcière t'enferme après avoir découvert ta diversion."
    else:
        label = "Faire prendre la clef par Madame Souris pendant ta diversion"
        success = f"Tu attires le regard de la sorcière. Madame Souris rejoint {support}, prend l'anneau et le fait glisser dans ta main."
        complication = f"Madame Souris prend l'anneau sur {support}, mais une clef tinte. Tu la recueilles tandis qu'elle se cache dans ta manche."
        failure = "La sorcière aperçoit Madame Souris près de la clef et reprend l'anneau. Elle te voit faire signe à la souris et t'enferme à l'écart."
    return animal_memory() + [
    variant("merle_key_help", {}, {"cages_key_help": "Tu peux demander à Maître Merle d'attirer le regard de la sorcière par son chant. Tu prendrais la clef pendant qu'elle l'écoute."}),
    variant("mouse_active_choice", ally("mouse"), values={"cages_key_help": "Madame Souris attend dans ta manche. Elle prendra la clef dès que tu auras détourné l'attention de la sorcière."}, choices=[
        choice(label, ("cages_9_key", "cages_9_key", "cages_9_caught"), (success, complication, failure),
            good=effect("has_key", inventory=("silver_key",)), bad=effect("caught", "alert"), heroes=("keeper", "rogue")),
        key_choices()[1],
    ]),
    ]

scene("8_quiet_public", 8, "La soupe et la clef", """
    La sorcière te fait asseoir à table. Elle demande d'où tu viens et si tu connais une chanson. Entre deux réponses, tu regardes la porte de l'étage.

    Dans le jardin, Maître Merle guette la fenêtre. {cages_key_help}

    La sorcière pose un instant sa clef pour remuer la soupe, puis la reprend en entendant les oiseaux. Près du four, une boule de pâte attend. Quand elle pétrira son pain, elle devra de nouveau libérer ses mains : tu pourrais saisir l'anneau à ce moment-là.

    {item_cages_use}

    Lison chante au-dessus de vous. Tu peux lancer la diversion ou attendre que la femme pose sa clef.
""", key_choices(), variants=key_variants())

scene("8_quiet_secret", 8, "Derrière le rideau du fournil", """
    Tu passes derrière le rideau du fournil. La sorcière est de l'autre côté, près de sa pâte. Elle regarde la fenêtre : Maître Merle y chante une chanson qu'elle essaie de retenir. Il change une rime chaque fois qu'elle croit l'avoir apprise.

    « J'ai trouvé trois grains dans la cour ;\n    demain j'y ferai un détour. »

    Chaque fois que la femme croit retenir sa chanson, le merle en change la fin et elle lui demande de recommencer. Tu aperçois alors la clef d'argent : elle est posée sur un crochet près du four. Une planche grinçante te sépare de ce crochet.

    {cages_key_help}

    {item_cages_use}

    La femme réclame un couplet, puis regarde le four. Tu choisis à quel moment quitter le rideau.
""", key_choices(), variants=key_variants("le crochet"))

scene("8_visitor_public", 8, "Le concours de chansons", """
    Maître Merle chante devant la fenêtre. La visiteuse veut entendre la fin ; la sorcière veut surtout prouver que ses oiseaux chantent mieux. Tu restes entre elles, comme si tu cherchais seulement à savoir qui gagnera leur discussion.

    « Mon voisin garde son trésor ;\n    moi, je chante et je sors encore. »

    Le merle insiste sur le dernier mot. La visiteuse lui demande de se taire pour écouter Lison. Tu proposes de faire chanter chacun à son tour. La sorcière monte chercher une dernière cage, puis revient avec la clef à la ceinture.

    Pour montrer un oiseau à la visiteuse, la sorcière pose sa clef sur la table et soulève sa cage. Les deux femmes regardent le chanteur. {cages_key_help}

    {item_cages_use}

    La visiteuse montre sa bague d'or. Les deux femmes se penchent : tu peux agir.
""", key_choices(), variants=key_variants("la table"))

scene("8_visitor_secret", 8, "Une voix dans l'escalier", """
    Tu montes quelques marches pendant que les femmes discutent. De là, tu vois leur table entre les barreaux de la rambarde. La voix de Lison te parvient de la pièce du bas : sa cage y a été descendue pour l'échange.

    À travers la rambarde, tu vois la sorcière poser sa clef sur la table pour soulever une cage. La visiteuse proteste : elle veut entendre les voix avant de promettre quoi que ce soit. Leur désaccord te laisse quelques instants, mais tu dois descendre pour atteindre l'anneau.

    {cages_key_help} Tu repères le chemin entre la table et l'escalier pour pouvoir repartir avec la clef.

    {item_cages_use}

    La sorcière avance un fauteuil. L'anneau reste hors de sa main ; tu peux lancer la diversion ou atteindre toi-même la table.
""", key_choices(), variants=key_variants("la table"))

scene("8_departure_public", 8, "La clef entre les courroies", """
    Tu continues de poser des questions sur le panier prétendument perdu. En te répondant, la sorcière revient près de son chariot. Tu la suis, comme si tu attendais qu'elle te donne une indication.

    La femme tire sur une courroie. La bâche se replie ; tu entends plusieurs oiseaux battre des ailes. Elle décroche sa clef pour vérifier les cages avant le départ, puis pose l'anneau sur le bord du chariot pendant qu'elle retend la corde.

    Maître Merle passe au-dessus de la cour. {cages_key_help}

    {item_cages_use}

    La sorcière reprend la courroie. Tu choisis une diversion ou un geste à couvert avant qu'elle ne récupère l'anneau.
""", key_choices(), variants=key_variants("le bord du chariot"))

scene("8_departure_secret", 8, "Le premier arrêt du chariot", """
    En suivant le chariot, tu arrives près de {location_cages_landmark}. Une courroie se desserre et la sorcière s'arrête pour la renouer. Sous la bâche, tu entends toujours les sept oiseaux.

    Maître Merle vole jusqu'à une branche au-dessus de l'arrêt. Il te montre le pied du chariot, où tu peux rester hors du regard de la femme. Elle pose la clef près d'elle pour déplacer une cage avant de renouer la courroie.

    {cages_key_help}

    {item_cages_use}

    Lison reprend son refrain sous la bâche. La femme se penche sur la courroie : la clef est à portée, mais il faut agir avant qu'elle se retourne.
""", key_choices(), variants=key_variants("le bord du chariot"), effects=effect("cart_road"))

scene("8_caught", 8, "Le verrou du cellier", """
    Le cellier sent les pommes séchées. La sorcière t'y a enfermé après avoir compris que tu cherchais les oiseaux. Elle n'a pas encore essayé de te changer : elle veut d'abord savoir ce que tu as entendu et termine ses préparatifs derrière la porte.

    Ton sac est resté sur ton épaule. Le verrou de ce cellier est ordinaire ; il ne porte pas l'enchantement des cages. Une petite fenêtre laisse passer une branche, et une fente sous la porte rejoint le couloir. Tu entends Maître Merle près de la fenêtre.

    « Une porte a beau se fermer,\n    un ami peut encore entrer. »

    {cages_mouse_memory} Tu peux lui demander d'attirer la femme pendant que tu gagnes le couloir. Tu peux aussi te servir de ton objet pour dégager le verrou ou la fenêtre, puis observer où elle pose la clef.

    Tu entends sa main se poser sur la porte.
""", [
    choice("Faire chanter le merle pour attirer la sorcière au-dehors", ("cages_9_key", "cages_9_key", "cages_9_caught"), (
        "Le merle chante à la fenêtre. La femme ouvre pour te demander si tu le connais. Quand elle se détourne vers lui, tu prends la clef à sa ceinture et sors.",
        "La femme sort écouter le merle. Tu prends la clef, mais la porte du cellier claque après ton passage : elle sait maintenant que tu es dehors.",
        "La femme entend le merle mais ne quitte pas la cuisine. Tu restes dans le cellier ; elle serre la clef et vient vérifier ta porte."),
        good=effect("has_key", inventory=("silver_key",)), bad=effect("alert"), heroes=("keeper", "rogue")),
    choice("{item_cages_escape}", ("cages_9_key", "cages_9_key", "cages_9_caught"), (
        "{item_cages_escaped} Dans la cuisine, la femme a posé sa clef pour déplacer une cage. Tu la prends avant de rejoindre les oiseaux.",
        "{item_cages_escaped} Le bois craque à ton passage. Tu prends la clef pendant que la femme cherche l'origine du bruit près de la fenêtre.",
        "Tu ouvres seulement un espace trop étroit pour passer. La femme approche avec la clef encore en main ; tu dois tenter autre chose depuis le cellier."),
        good=effect("has_key", inventory=("silver_key",)), bad=effect("alert"), heroes=("mage", "explorer")),
], variants=animal_memory())


if __name__ == "__main__":
    write_manuscript()
