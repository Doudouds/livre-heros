"""Manuscrit du pilote. Écrit le graphe éditorial, sans produire d'audio.

Le jeu et build_content lisent ensuite content/authored/cages.json.
Avant d'écrire un autre conte, lire docs/memo_editorial_contes.md.
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
        "cages_stop": "au vieux pont",
    },
    "castle": {
        "cages_setting": "Lison est partie vers les mûriers de Valombre, le château abandonné. Les villageois ramassent les fruits dans son ancien verger. Depuis peu, une cheminée fume dans le logis qui borde la cour.",
        "cages_house": "le logis du château abandonné de Valombre",
        "cages_fox_way": "un trou sous le mur du verger, qui mène derrière le logis",
        "cages_merle_way": "l'allée du château, sous les fenêtres du logis",
        "cages_view": "Un logis habité borde la cour du château. Une fenêtre basse donne sur le fournil ; une chambre s'ouvre au-dessus de l'ancienne galerie.",
        "cages_back": "le passage du verger et la petite porte du rempart",
        "cages_front": "l'allée du château qui rejoint le pont principal",
        "cages_stop": "au pont du château",
    },
    "mountain": {
        "cages_setting": "À Brumecime, la montagne des dragons, les mûriers poussent près du refuge des bergers. Lison y est montée ce matin. Le sentier traverse un bois avant de rejoindre le refuge, sous les rochers du col.",
        "cages_house": "le refuge de Brumecime, sur la montagne des dragons",
        "cages_fox_way": "un passage derrière les rochers, jusqu'au jardin du refuge",
        "cages_merle_way": "le sentier des bergers, devant les fenêtres du refuge",
        "cages_view": "Le refuge se dresse sous les rochers du col. Son jardin est clos de pierres. Une fenêtre du fournil et un volet à l'étage donnent sur la pente.",
        "cages_back": "le passage des rochers et les marches des bergers",
        "cages_front": "le large sentier du refuge qui descend vers la vallée",
        "cages_stop": "aux marches des bergers",
    },
    "city": {
        "cages_setting": "Lison allait cueillir les mûres près du quai d'Auralis, la cité flottante. Une nacelle relie le bois aux jardins suspendus. La maison d'une vieille chanteuse se trouve près du quai d'arrivée.",
        "cages_house": "la maison du quai d'Auralis, dans la cité flottante",
        "cages_fox_way": "la nacelle des jardiniers, puis une ouverture dans la haie du quai",
        "cages_merle_way": "la nacelle des voyageurs, puis l'allée sous les fenêtres du quai",
        "cages_view": "La nacelle s'arrête devant une maison aux volets bleus. Un jardin borde son fournil. Les cordes du quai chantent doucement dans le vent.",
        "cages_back": "le jardin du quai et la nacelle des jardiniers",
        "cages_front": "le quai principal et la nacelle des voyageurs",
        "cages_stop": "sur le quai d'arrivée",
    },
    "ruins": {
        "cages_setting": "Les mûriers couvrent l'entrée de Nacreprofonde, des ruines souterraines oubliées. Lison les connaît bien. Sous la colline, une maison ancienne a été réparée et une lueur paraît derrière ses fenêtres.",
        "cages_house": "la maison restaurée dans les ruines de Nacreprofonde",
        "cages_fox_way": "l'escalier de service qui rejoint le jardin souterrain",
        "cages_merle_way": "le grand escalier et la rue qui passe sous les fenêtres",
        "cages_view": "La maison se dresse dans une rue souterraine éclairée par des cristaux. Son fournil ouvre sur un jardin de champignons ; une chambre donne sur l'ancien canal.",
        "cages_back": "l'escalier de service et la sortie derrière la colline",
        "cages_front": "la grande rue et les marches de l'entrée principale",
        "cages_stop": "près de l'ancien canal",
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
    "cages_promise_memory": "",
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
    « Quand la nuit descend sur les bois, le bon chemin mène chez soi », chante votre mère. Lison, ta petite sœur, préfère changer la fin : « Prends ma main, je rentre avec toi. » Elle glisse sa main dans la tienne en chantant ; elle le fait chaque fois.

    Ce matin, elle est partie cueillir des mûres avec son panier d'osier. {location_cages_setting}

    Au repas, sa chaise reste vide. Votre mère laisse refroidir son bol. « Quelqu'un l'aura vue sur la route. Je vais demander. Toi, cherche-la sur son sentier ; nous nous retrouverons à la lisière. » Sa main demeure un instant sur ton épaule.

    {hero_cages_intro} Avec du pain, une gourde et {item_name}, tu pars chercher Lison.

    Sous un noisetier, des mûres tachent la terre autour d'un panier renversé. Tu reconnais celui de Lison au fil rouge noué à son anse. Plus haut pend le ruban bleu qu'elle portait ce matin. Tu le gardes dans ta main ; il est encore humide de pluie.
""", kind="intro")
intro["next"] = "cages_1"

scene("1", 1, "Le panier et le merle", """
    Une goutte tombe du ruban sur ton poignet. Au-dessus du panier, un merle lisse son plumage, attendant visiblement que tu le regardes.

    « J'ai vu passer sur ce sentier\n    l'enfant qui portait ce panier.\n    Une vieille lui chantait un air ;\n    elles ont franchi une barrière. »

    « C'est ma sœur. Où sont-elles allées ? » Le merle baisse un peu la tête.

    « Maître Merle connaît chaque voix ;\n    mais ces volets fermés, ma foi…\n    J'ai vu la porte se fermer ;\n    j'ai préféré ne pas entrer. »

    Il désigne une maison derrière les arbres. Pour la première fois, il semble avoir oublié de se faire admirer.

    Dans la terre, de petites empreintes côtoient des pas plus profonds. Elles vont vers cette maison. Le merle attend ta question ; la pluie, elle, commence déjà à brouiller les traces.
""", [
    choice("Demander au merle de décrire la vieille femme", "cages_2", (
        "« Un manteau gris, un pas pesant ; / à sa ceinture, argent brillant. / La clef tintait quand elle marchait ; / l'enfant riait et l'écoutait. » Tu demandes au merle de te guider.",
        "Le merle décrit la clef d'argent, puis chante son propre courage. Tu l'écoutes en regardant les nuages : le jour avance.",
        "Maître Merle parle trop fort. Un volet claque au loin : quelqu'un a entendu sa voix. Tu rejoins les traces en lui demandant de baisser le ton."),
        good=effect("key_seen"), bad=effect("alert"), heroes=("keeper", "mage")),
    choice("Suivre les empreintes de Lison", "cages_2", (
        "Les empreintes rejoignent la route de la maison. Tu remarques aussi un collet tendu à son bord, sans marcher sur son lien.",
        "Tu suis les pas jusqu'à la route, mais une averse efface leur fin. Tu retiens les deux tournants déjà parcourus.",
        "Une flaque efface les dernières empreintes. Tu reviens au noisetier où tu as trouvé le panier, et Maître Merle accepte de te montrer le chemin qu'il a survolé."),
        good=effect("return_known"), heroes=("explorer", "rogue")),
], effects={"meet_characters": ["merle"], "add_allies": ["merle"]})

scene("2", 2, "Le renard qui gardait sa dignité", """
    Sur le chemin indiqué par Maître Merle, les feuilles remuent sans vent. Un renard est pris dans un collet ; une boucle de corde serre sa patte. À ton approche, il ramène sa queue autour de lui, comme pour cacher le piège.

    « Maître Renard, pour vous servir. Je réfléchissais à la manière la plus élégante de sortir d'ici. »

    « Est-ce qu'elle te fait mal ? »

    Il détourne le museau. « Seulement quand je tire. » La corde rejoint une cheville enfoncée dans le sol. Tu poses ton sac près de lui ; cette fois, il ne cache plus sa patte.

    Au nom de Lison, ses oreilles se dressent. « La femme de cette maison a tendu mon collet. Je connais un passage derrière son jardin. Libérez-moi, et nous irons chercher votre sœur. »

    Ses yeux suivent tes mains. Tu peux desserrer la boucle ou dégager la cheville ; surtout, il ne faut plus tirer sur sa patte.
""", [
    choice("{item_cages_snare}", "cages_3", (
        "{item_cages_snare_result} Maître Renard éprouve le sol sous sa patte. « Voilà une affaire réglée. Parlons de votre sœur. » Il attend que tu reprennes ton sac.",
        "{item_cages_snare_result} Maître Renard est libre, mais il boite. Il pourra guetter près du jardin ; courir lui serait trop douloureux.",
        "La boucle se resserre au premier geste. Maître Renard te demande d'arrêter avant de lui faire mal. Il t'indique le passage du jardin et t'envoie chercher Lison ; tu reviendras l'aider ensuite."),
        good=effect(allies=("fox",)), bad=effect("fox_trapped"), heroes=("mage", "rogue")),
    choice("Dégager la cheville pour détendre le collet", "cages_3", (
        "La cheville vient dans ta main ; le renard retient son souffle jusqu'à ce que la corde tombe. « Je vous montrerai mon chemin. » Il fait quelques pas, puis t'attend.",
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

    {cages_garden_offer} Le merle désigne {location_cages_merle_way}.

    « Au jardin, on voit la cuisine ;\n    moi, je vois les chambres voisines. »

    Tu cherches une voix dans cette maison. Par le jardin, tu éviterais la porte de la cuisine ; sous les fenêtres, tu pourrais mieux voir l'étage. Les deux passages se séparent devant vous.
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
    Le passage du jardin mène derrière {location_cages_house}. {location_cages_view} Contre le mur, à l'abri du regard de la cuisine, tu écoutes.

    {cages_fox_memory} Maître Merle reste assez loin des fenêtres pour ne pas se faire voir. Il te prévient d'un vers à peine soufflé :

    « Le volet bouge dans le vent ;\n    quelqu'un marche au-dedans. »

    Une cuillère tinte contre un bol.

    « Merci pour la soupe… Mais maman m'attend. Est-ce que je peux rentrer ? »

    C'est Lison. Tu connais cette petite hésitation avant une demande. La réponse de la femme se perd derrière le mur.

    Sa voix vient de la chambre au-dessus du fournil. Une caisse permettrait d'atteindre le volet, de l'autre côté des dalles découvertes. Les branches d'un arbre touchent aussi le mur ; elles te cacheraient si tu parvenais à y grimper.
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
    variant("visitor_room", flag("revelation_visitor"), {"cages_position": "« C'est de l'or, je vous assure. » À la lumière de la porte, la sorcière examine la bague de la visiteuse. Tu te glisses vers les sept cages restées dans la grande pièce."}),
    variant("departure_court", flag("revelation_departure"), {"cages_position": "Les sept cages attendent sur le chariot dans la cour. La sorcière s'occupe de sa bâche ; tu peux atteindre les serrures derrière la toile."}),
    variant("departure_road", flag("cart_road"), {"cages_position": "Le chariot est toujours arrêté {location_cages_stop}. Tandis que la sorcière renoue la courroie à l'avant, tu peux approcher les cages cachées sous la bâche."}),
]


def rescue_memory():
    return [
        variant("lison_human", flag("lison_free"), {"cages_rescue_memory": "Lison regarde ses doigts retrouvés, puis les six cages fermées. « Je vais guetter. » Sa main quitte la tienne à regret ; elle se place du côté où viendra la sorcière."}),
        variant("others_human", flag("others_free"), {"cages_rescue_memory": "Les six enfants, de nouveau humains, se serrent derrière toi. « Lison nous a promis qu'on rentrerait », dit le plus grand. Ta sœur attend toujours dans sa cage."}),
        variant("lison_bird", both(flag("lison_bird"), no(flag("lison_free"))), {"cages_rescue_memory": "Dans ton manteau, Lison reste un oiseau. Tu sens son cœur battre contre toi. Sortie de sa cage, elle cherche encore la clef du regard : l'enchantement tient."}),
    ]


def lison_choice(target="cages_11", label="Ouvrir d'abord la cage de Lison"):
    return choice(label, target, (
        "La clef tourne. Les ailes s'effacent ; Lison est là, les yeux grands ouverts. « Tu m'as entendue ? » Tu serres sa main. Derrière elle, les six autres oiseaux attendent.",
        "Lison retrouve sa forme, mais son pied heurte la cage vide. Elle la retient contre elle. Vous restez immobiles, le temps d'un souffle, à écouter si la femme a entendu.",
        "La serrure résiste à ton geste précipité. Un barreau se desserre ; Lison s'y glisse sous sa forme d'oiseau et se cache dans ton manteau. Le sort n'est pas défait."),
        good=effect("lison_free", unset=("lison_bird",)), bad=effect("lison_bird", "alert"), heroes=("mage", "keeper"),
        mods=(("Lison prête au signal", flag("lison_warned"), .08), ("Chant couvre les bruits", flag("song_cover"), .07)))


def others_choice(target="cages_11", label="Ouvrir les autres cages pendant que Lison chante"):
    return choice(label, target, (
        "À chaque serrure ouverte, un enfant retrouve sa forme. Six visages se tournent vers Lison, dont la cage reste fermée. « Venez près de moi », leur souffles-tu.",
        "Les six enfants retrouvent leur forme. « Maman ? » demande le plus jeune. Tu t'accroupis auprès de lui, un doigt sur tes lèvres ; Lison attend encore derrière ses barreaux.",
        "Le premier verrou se coince et le temps passe. Aucun des six enfants n'a encore retrouvé sa forme ; Lison reprend son chant pour vous laisser une chance."),
        good=effect("others_free"), bad=effect("alert"), heroes=("rogue", "knight"),
        mods=(("Lison couvre les bruits", flag("song_cover"), .10), ("La chambre a été observée", flag("room_known"), .06)))


scene("9_key", 9, "Le refrain derrière les barreaux", """
    {cages_position}

    « Prends ma main, je rentre avec toi… » L'oiseau brun, celui que tu as vu prendre la place de Lison, achève votre chanson. Tu réponds à voix basse. Deux coups sur le perchoir : votre signal de cache-cache, quand il fallait vous appeler sans parler.

    « Je suis là. » Lison vient contre ta main, ses petites pattes serrées sur le bois. L'anneau d'argent tremble entre tes doigts ; tu le tiens plus fermement.

    La sorcière peut vous surprendre. « Tu pourrais chanter pendant que j'ouvre… Ou me prévenir si elle approche. » Tu montres la serrure, puis le côté à surveiller.

    Lison écoute. Tu aimerais lui ouvrir aussitôt ; tu attends pourtant qu'elle ait compris.
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

    « Chante-moi quelque chose », dit la sorcière. Tu regardes la clef à sa ceinture : une belle voix lui donnerait envie d'une huitième cage.

    Tu commences la chanson de Lison, mais retiens le dernier vers.

    « Et la fin ? »

    « Elle ne me revient pas. »

    En attendant la suite, elle ouvre {cages_capture_access} avec une clef de fer. Le verrou est ordinaire ; celle d'argent reste pour les oiseaux. Ton objet pourrait dégager ce verrou.

    {cages_mouse_memory} Dehors, quelques notes du merle te répondent. Il a reconnu le refrain inachevé.

    La femme écoute aussi. Si tes compagnons la retiennent, tu pourrais prendre l'anneau ; si tu ouvres toi-même, tu chercheras la clef à couvert.
""", [
    choice("Appeler tes compagnons et tenter de prendre la clef", "cages_10", (
        "Le merle répond à ton refrain. La femme ouvre pour le faire taire ; tu prends l'anneau pendant qu'elle se retourne et rejoins les cages.",
        "La diversion te libère et tu prends la clef, mais la sorcière découvre ton passage. Elle vous cherchera près des oiseaux.",
        "La femme garde la clef en voulant saisir le merle. Elle oublie le verrou : tu peux rejoindre Lison, mais la clef d'argent reste à sa ceinture."),
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
    Lison ne quitte pas tes mains des yeux. {cages_key_memory}

    « Est-ce qu'on va rentrer ? » demande un oiseau aux plumes claires. Un autre lui touche l'aile pour le faire taire.

    « Je vais essayer. Restez près de nous. » Au mot « rentrer », tous se rapprochent des barreaux.

    {cages_key_plan}

    Le bruit de la femme s'interrompt. Lison frappe son perchoir, tout doucement. Elle te regarde, puis regarde les autres.
""", [lison_choice(), others_choice()], variants=[
    *POSITION_VARIANTS,
    variant("key_in_hand", flag("has_key"), {"cages_key_memory": "Dans ta paume, la clef d'argent est froide.", "cages_key_plan": "Rendre sa forme à Lison vous permettrait d'agir à deux. Elle pourrait aussi rester oiseau et t'aider à ouvrir les six autres cages d'abord. Vos regards passent de sa serrure à celles de ses voisins."}),
    variant("key_missing", no(flag("has_key")), choices=no_key_choices),
])

all_others = choice("Ouvrir les six autres cages avec Lison", "cages_12", (
    "Sous la garde de Lison, les six serrures cèdent. « Par ici », appelle-t-elle doucement. Les enfants retrouvent leurs jambes ; le plus grand tend la main au plus petit.",
    "Les six enfants retrouvent leur forme, mais la dernière cage heurte le sol. Lison regroupe tout le monde pendant que tu prépares le départ.",
    "La sorcière coupe l'accès aux six cages. Lison te tire vers le passage libre ; les autres prisonniers restent enfermés, et vous devrez revenir les chercher."),
    good=effect("others_free"), bad=effect("alert"), mods=(("Porte surveillée", flag("door_watched"), .08), ("Souris aide aux serrures", ally("mouse"), .06)), heroes=("rogue", "mage"))
safe_lison = choice("Préparer la sortie avec Lison avant le retour de la femme", "cages_12", (
    "Lison t'aide à dégager le passage. Vous pourrez repartir ensemble, puis montrer aux voisins où chercher les six enfants encore prisonniers.",
    "Vous dégagez le passage, mais la sorcière vous voit. Lison avance la première ; tu la suis en surveillant la femme. Les autres enfants restent prisonniers.",
    "La sorcière vous barre le passage. Lison en repère un autre, qu'elle ne surveille pas : vous vous y glissez en laissant les six cages fermées."),
    good=effect("return_known"), bad=effect("alert"), heroes=("explorer", "knight"))

finish_lison = lison_choice("cages_12", "Rejoindre Lison pendant que les enfants guettent")
finish_lison["outcomes"]["success"]["text"] = "La clef tourne. Lison retrouve sa forme. « Tu m'as entendue ? » Sa main cherche la tienne ; près de la sortie, les six enfants vous appellent doucement."
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

    {cages_witch_call} Une aile heurte le bois, puis le silence se fait. Tu écoutes ses pas, essayant de deviner combien vous en séparent encore.

    {cages_merle_watch}

    « Mon couplet ne la retient plus ;\n    partez avant qu'elle ait tout vu. »

    Ta main reste près des serrures. Il y a encore des prisonniers, et derrière toi un passage qui pourrait se refermer. Le merle attend ta réponse.
""", [lison_choice("cages_12", "Ouvrir la cage de Lison avant l'arrivée de la femme"), others_choice("cages_12", "Délivrer les six enfants pendant la dernière diversion")], variants=[
    *rescue_memory(), *animal_memory(),
    variant("witch_missing_key", flag("has_key"), {"cages_witch_call": "« Ma clef ! » La sorcière fouille sa ceinture. « Petite chanteuse, où es-tu ? » Sa voix se rapproche des cages."}),
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
    variant("company_lison", flag("lison_free"), {"cages_company": "Lison marche près de toi, de nouveau humaine. « Nous reviendrons pour eux ? » Les six autres sont encore prisonniers. Tu lui serres la main en pensant aux lanternes du village."}),
    variant("company_others", flag("others_free"), {"cages_company": "Les six enfants libérés se serrent près de toi. L'un regarde en arrière. « Et Lison ? » Elle attend dans sa cage ; au village, il faudra raconter où la chercher."}),
    variant("company_bird", both(flag("lison_bird"), no(flag("lison_free"))), {"cages_company": "Lison se serre contre ton épaule, toujours oiseau. « On rentre chez nous », lui souffles-tu. Elle enfouit son bec dans ton col. Tu aimerais pouvoir lui promettre aussi la fin du sort."}),
    variant("company_full", both(flag("lison_free"), flag("others_free")), {"cages_company": "Lison compte les six enfants près de toi. Le plus petit s'accroche à sa jupe. « Vous connaissez le chemin ? » demande-t-il. Elle lui tend la main avant de répondre : « Nous restons ensemble. »"}),
    variant("company_others_bird", both(flag("others_free"), flag("lison_bird"), no(flag("lison_free"))), {"cages_company": "Les six enfants libérés attendent près de toi. Dans ton manteau, Lison reste un oiseau. « On leur dira », murmure le plus grand. Il sait que le sort de ta sœur tient encore."}),
]

scene("12", 12, "Le chemin du retour", """
    {cages_company}

    {cages_chase} Maître Merle surveille ses mouvements et se tait quand elle regarde dans votre direction.

    {cages_promise_memory}

    Tu reconnais {location_cages_front}, large et découvert. Le retour par {location_cages_back} serait plus étroit, mais mieux caché.

    {cages_fox_memory}

    Votre mère t'attend à la lisière. Tu essaies d'imaginer sa silhouette entre les arbres, la chaleur de ses mains. Deux chemins mènent vers elle.
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
    variant("promise_return", flag("mouse_promised"), {"cages_promise_memory": "Derrière le four, les petits de Madame Souris attendent le refuge promis. Ce détour retarderait la fuite. Tu revois la miette serrée entre ses pattes : faudra-t-il lui demander d'attendre encore, puis revenir avec les voisins ?"}, choices=[
        choice("Chercher la famille de Madame Souris et prendre le passage discret", "$ending", (
            "Dans le fournil, trois museaux se lèvent. « Tous là », souffle Madame Souris. Tu accueilles sa famille dans ton sac ; le passage discret vous mène à la lisière.",
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
    variant("late_return", flag("late"), {"cages_return_memory": "La nuit est tombée quand votre mère vous retrouve à la lisière. « J'allais repartir… » Elle n'achève pas sa phrase. Son manteau sent le feu de chez vous ; elle vous ramène à la maison."}),
    variant("timely_return", no(flag("late")), {"cages_return_memory": "À la lisière, votre mère reconnaît ta voix avant de te voir. « Ici ! Je suis ici ! » Ses mains trouvent les tiennes. À la maison, le feu brûle encore."}),
    variant("mouse_at_home", flag("mouse_home"), {"cages_mouse_ending": "Près du four familial, Madame Souris compte trois petits museaux. « Vous avez tenu parole. » Elle pose enfin sa miette, au milieu d'eux."}),
    variant("mouse_promise_pending", both(flag("mouse_promised"), no(flag("mouse_home"))), {"cages_mouse_ending": "Les petits de Madame Souris attendent encore au fournil. Tu décris leur abri aux voisins et rappelles le refuge que tu leur as promis."}),
    variant("fox_free_end", ally("fox"), {"cages_fox_ending": "« Un peu d'eau suffira », dit Maître Renard quand on le remercie. Il boit lentement sur le seuil, avant de regagner le bois."}),
    variant("fox_trap_end", no(ally("fox")), {"cages_fox_ending": "Tu indiques aussi le collet où Maître Renard attend. Un voisin prend sa lanterne et part le dégager."}),
]

scene("end_full", 13, "La chanson retrouvée", """
    {cages_return_memory}

    « Tu avais froid ? » demande votre mère à Lison.

    « Surtout aux ailes. » Ta sœur regarde ses mains, puis se rapproche du feu. Les six autres enfants racontent les cages entre deux bouchées de pain. Leurs familles viennent les chercher ; des voisins repartent ensemble vers la maison de la sorcière pour l'empêcher de recommencer.

    {cages_mouse_ending} {cages_fox_ending}

    Quand la maison s'apaise, Lison cherche ta voix pour commencer la chanson. {cages_final_song} À la fenêtre, Maître Merle attend la dernière note.

    « Ce soir, je vous laisse chanter ;\n    j'aurai demain pour me vanter. »

    Lison rit. Son ruban bleu repose sur la table ; tu le lui rends. Elle le noue de travers, comme toujours, et laisse sa tête contre ton épaule.
""", kind="ending", ending="full", variants=ENDING_VARIANTS)

scene("end_lison", 13, "Une sœur et six promesses", """
    {cages_return_memory}

    Votre mère serre Lison contre elle. « Les autres sont encore là-bas », dit ta sœur, le visage dans son manteau. Elle parle des ailes qui se froissent contre les barreaux. Les voisins viennent avec leurs lanternes ; tu leur montres le chemin et Lison décrit la clef d'argent.

    {cages_mouse_ending} {cages_fox_ending}

    Au repas, Lison écoute les voix rassemblées dehors. « Ils vont retrouver le chemin ? »

    « Je les guiderai dans les bois ;\n    je connais le chemin, cette fois », répond le merle à la fenêtre.

    Quand les lanternes s'éloignent avec lui, ta sœur garde sa main dans la tienne. Sa chanson attendra le retour des six enfants.
""", kind="ending", ending="lison", variants=ENDING_VARIANTS)

scene("end_bird", 13, "Lison à la fenêtre", """
    {cages_return_memory}

    « Où est ta sœur ? » demande votre mère. Dans ton col, Lison garde la forme d'un oiseau. Tu racontes, mais les mots paraissent impossibles. Alors une petite voix chante : « Prends ma main, je rentre avec toi. »

    « Lison… » Votre mère lui tend les mains. Elle reconnaît sa fille ; il reste pourtant à défaire le sort.

    {cages_other_ending}

    Près de la fenêtre, tu prépares un perchoir. Lison préfère ton épaule. Dehors, les voisins s'assemblent pour défaire le sort ; votre mère emporte le chemin que tu as tracé sur une feuille.

    {cages_mouse_ending} {cages_fox_ending}

    « Tu peux rester là », lui souffles-tu. Ses petites pattes s'accrochent à ton col. Le merle veille à la fenêtre. Vous attendez le retour des lanternes ; de temps en temps, Lison reprend votre dernier vers, juste pour toi.
""", kind="ending", ending="bird", variants=[*ENDING_VARIANTS,
    variant("other_children_home", flag("others_free"), {"cages_other_ending": "Les six autres enfants ont retrouvé leur forme et leurs familles. Leur récit confirme le tien : ils seront des témoins pour ceux qui iront chercher la clef."}),
])

scene("end_others", 13, "Le chemin qu'il faut reprendre", """
    {cages_return_memory}

    Les six enfants retrouvent leurs familles. Votre mère les écoute, une lanterne dans les mains. « Et Lison ? » Tu baisses les yeux : sa cage est encore fermée.

    « Nous savons où elle est », dit le plus grand. Tu décris son refrain et montres la route. Les voisins préparent les cordes et les outils ; votre mère ne pose plus sa lanterne.

    {cages_mouse_ending} {cages_fox_ending}

    Maître Merle part devant eux. Un enfant reste près de toi. « Elle chantait quand on avait peur. » Tu lui demandes le dernier vers ; il le connaît déjà. Vous le reprenez doucement, les yeux sur la route. Entre vous et le feu, la chaise de Lison reste vide.
""", kind="ending", ending="others", variants=ENDING_VARIANTS)

scene("end_pending", 13, "Le secret de la maison", """
    {cages_return_memory}

    Les sept enfants sont encore prisonniers. Le ruban bleu glisse de ta main sur la table. Tu racontes la transformation de Lison ; votre mère t'écoute sans t'interrompre.

    « Tu as bien fait de revenir. Maintenant, montre-nous. » Elle noue le ruban à son poignet. Aux voisins qu'elle appelle, tu décris les accès et la clef qu'il faut rapporter.

    {cages_mouse_ending} {cages_fox_ending}

    Une à une, les lanternes s'allument. Le merle indique où se trouve la sorcière. « Garde le feu pour ta sœur », dit votre mère. Tu voudrais la suivre ; tes jambes tremblent encore.

    Le merle s'arrête à la fenêtre avant de rejoindre les voisins. Tu rapproches du foyer le bol de Lison. À son retour, elle aura peut-être faim.
""", kind="ending", ending="pending", variants=ENDING_VARIANTS)


def write_manuscript():
    defaults = {
        **DEFAULTS,
        "cages_scenario_hint": "La femme descend dans la cuisine et laisse les oiseaux dans la chambre.",
        "cages_merle_watch": "Maître Merle chante encore près d'une fenêtre, mais la femme ne l'écoute plus.",
        "cages_guide_arrival": "Tu poursuis ta recherche avec Maître Merle.",
        "cages_garden_offer": "Tu te souviens du passage du jardin indiqué par Maître Renard.",
        "cages_witch_call": "« Pourquoi ne chantez-vous plus ? » La sorcière vérifie sa clef et s'avance vers les cages.",
        "cages_key_plan": "Sans la clef, tu peux tenter de reprendre l'anneau ou dégager un barreau pour mettre Lison hors de portée. Elle resterait un oiseau : sortir de la cage ne défait pas son sort.",
        "cages_final_song": "Cette fois, tu chantes son dernier vers avec elle.",
        "cages_position": "La sorcière occupée en bas, tu gagnes l'étage par l'escalier du fournil. Derrière la porte de la chambre, les sept cages attendent, près de la fenêtre où tu as vu la transformation.",
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
    Maître Merle te mène devant {location_cages_house}. {location_cages_view} À la fenêtre, une femme au manteau gris passe une main sur sa ceinture. Une clef y brille.

    De la chambre, au-dessus du fournil, monte une chanson : « Prends ma main, je rentre avec toi. » Tu oublies un instant la femme et sa clef. Lison est là.

    « Encore, dit la vieille femme. Cette fin est jolie. »

    Le merle se penche vers toi :

    « Sa chanson monte jusqu'au toit ;\n    je peux l'écouter près de toi. »

    Il guette la porte de la cuisine pendant que tu cherches un appui pour atteindre le volet. Le treillis monte jusqu'à la chambre ; une latte se détache pourtant sous tes doigts. Le banc paraît plus solide, mais la femme pourrait te voir traverser devant sa porte.
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
    « Il faut que je rentre », dit Lison en quittant la table.

    La vieille femme demeure devant la porte. « Et qui chantera pour moi ? »

    « Je reviendrai. Si maman veut bien. »

    « Les enfants promettent, puis ils oublient. » Une clef d'argent pend à l'anneau qu'elle détache de sa ceinture. Lison recule ; la clef touche son épaule.

    Le tablier de Lison tombe sur la chaise. À la place de ta sœur, un petit oiseau brun bat des ailes. Il cherche la fenêtre. La femme le reçoit dans ses mains et l'enferme dans la seule cage vide, auprès de six autres.

    « Ici, tu ne m'oublieras pas. » La clef tourne. Derrière les barreaux, la voix de Lison murmure : « Prends ma main, je rentre avec toi. »

    Tu voudrais l'appeler. Aucun son ne vient. La sorcière remet la clef à sa ceinture avant de descendre.

    {cages_scenario_hint}

    Lison regarde la fenêtre. Ton refrain pourrait lui dire que tu es là ; ton silence te laisserait observer la chambre sans vous trahir.
""", scenario_choices["quiet"], variants=[
    variant("visitor_plot", flag("revelation_visitor"), choices=scenario_choices["visitor"]),
    variant("departure_plot", flag("revelation_departure"), choices=scenario_choices["departure"]),
    variant("quiet_hint", flag("revelation_quiet"), {"cages_scenario_hint": "En bas, une bûche craque. La femme remet sa soupe sur le feu ; le soir gagne les vitres."}),
    variant("visitor_hint", flag("revelation_visitor"), {"cages_scenario_hint": "« Ouvrez ! J'ai apporté la bague. » Une visiteuse attend au seuil. « Pour ce prix, je veux votre meilleur oiseau. »\n\n« Entrez, répond la sorcière. Vous n'avez pas encore entendu ma nouvelle chanteuse. »"}),
    variant("departure_hint", flag("revelation_departure"), {"cages_scenario_hint": "Dans la cour, un chariot attend sous une bâche. « Nous partirons avant la nuit, lance la sorcière aux oiseaux. Demain, vos familles pourront chercher : elles ne trouveront que mes murs. »"}),
], effects=effect("transformation_seen"))

MOUSE_TEXT = """
    Au bas du mur, près de la porte du fournil, une souris tient une miette entre ses pattes. Tu t'es glissé jusque-là pour chercher une entrée. « Ma sœur… », commences-tu. La souris lève les yeux.

    « Madame Souris. Parlez doucement, je vous prie. » Elle écoute, puis regarde l'étage. « J'ai vu arriver les six autres enfants aussi. L'un d'eux a dû porter du bois. La femme a ouvert sa cage avec la clef d'argent : il est redevenu un garçon. »

    « Et si je brise les barreaux ? »

    « Vous aurez un oiseau libre. Tourner la clef pour l'ouvrir défait le sort. » Elle te laisse le temps de comprendre.

    {cages_mouse_plot}

    « Elle accroche sa clef près du four pour pétrir. Je peux l'atteindre. Sa ceinture aussi. »

    Un grattement vient de derrière le four. Madame Souris se tait pour écouter. « Mes trois petits. Si elle me voit vous aider, elle nous chassera. Avez-vous une place pour nous ? » Sa miette reste intacte entre ses pattes.
"""
for plot, detail in (
    ("quiet", "Dans le fournil, la pâte attend sous un linge. « Elle fait son pain chaque soir, dit la souris. La clef sera au crochet ; la femme juste à côté. »"),
    ("visitor", "Une cage heurte le mur de l'escalier. « Elle descend les oiseaux pour la visiteuse, souffle la souris. Une voix d'enfant contre une bague d'or… »"),
    ("departure", "« Elle a une autre demeure, dit la souris. Quand le chariot partira, son crochet restera vide. » Son regard revient vers le four."),
):
    scene("6_" + plot, 6, "Madame Souris et ses petits", MOUSE_TEXT, [
        choice("Promettre un refuge à sa famille et demander son aide", "cages_7_" + plot, (
            "« Près de votre feu, même un tout petit coin. » Madame Souris te montre son nid derrière le four. Tu sauras où chercher ses petits ; elle vient se blottir dans ta manche.",
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
    Par la porte du fournil, tu vois la sorcière devant le feu. Sa soupe fume entre ses mains. « Quand la nuit descend sur les bois… » Elle s'arrête, cherche la suite. Ce silence te ramène à la chaise vide de Lison, chez vous.

    « Chante, là-haut. Je n'entends plus. »

    {cages_mouse_memory} Sur une branche, le merle attend. « Quand je lèverai la main », lui souffles-tu.

    Elle pourrait ouvrir à un enfant égaré : elle aime trop les voix nouvelles. Parler avec elle te laisserait approcher la clef. La porte du fournil offre une autre entrée, si le chant du merle la retient à la fenêtre.

    Son fauteuil grince. Tu regardes la porte, puis le merle.
""", approach_choices("quiet", "Frapper et demander un abri pour parler à la sorcière", "Entrer par le fournil pendant le chant du merle"), variants=animal_memory())

scene("7_visitor", 7, "La visiteuse au châle gris", """
    À la porte du fournil, les voix des deux femmes te parviennent de la pièce voisine. « Écoutez celui-ci, dit la sorcière. Il chante jusqu'à l'aube. »

    « Tous les oiseaux du bois chantent pareil. Faites entendre le nouveau. »

    Lison commence, s'arrête pour respirer, reprend. Tu attends avec elle chaque mot. Les deux femmes n'entendent qu'une chanson à vendre.

    {cages_mouse_memory}

    Le merle gonfle ses plumes.

    « Elle confond toutes les voix ?\n    Qu'elle m'écoute une seule fois ! »

    « Tu pourrais les occuper », murmures-tu. Le présenter à la fenêtre t'ouvrirait peut-être leur porte. L'escalier du fournil donne aussi sur leur table : derrière sa rambarde, tu pourrais observer la clef à couvert.

    « Je n'ai pas toute la soirée », dit la visiteuse. Sa bague frappe le bois de la table.
""", approach_choices("visitor", "Proposer à la fenêtre le chant de Maître Merle", "Profiter de la discussion pour entrer par l'escalier"), variants=animal_memory())

scene("7_departure", 7, "Les cages sous la bâche", """
    Derrière le mur du jardin, tu regardes les cages quitter la maison. La sorcière les cale dans la paille du chariot. Quand la bâche cache Lison, son refrain monte plus haut : elle te laisse sa voix pour la retrouver.

    « Assez chanté, dit la femme. Le voyage sera long. »

    {cages_mouse_memory}

    Elle rentre chercher son sac. Tu pourrais l'interroger sur un panier prétendument perdu : cette conversation la retiendrait dans la cour. Ou laisser partir les cages et suivre le chariot jusqu'au premier arrêt, loin des portes de la maison.

    Le merle surveille le chemin depuis les arbres. Derrière toi, les petits de Madame Souris grattent près du four. Suivre Lison, ce serait aussi t'éloigner d'eux. La femme revient ; sa main se referme sur la poignée du chariot.
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
    « Assieds-toi. D'où viens-tu ? » La sorcière pousse un bol vers toi. Tu réponds sans quitter des yeux la porte de l'étage.

    « On chante, chez vous ? »

    « Quelquefois. » Tu sens le ruban de Lison contre ta paume.

    Dehors, Maître Merle guette la fenêtre. {cages_key_help}

    Lison chante au-dessus de vous. La femme porte la main à sa clef. « Quelle voix… » Pour remuer la soupe, elle dépose l'anneau, puis le reprend. Près du four, la pâte attend : elle devra encore libérer ses mains pour pétrir.

    {item_cages_use}

    « Et toi, que sais-tu chanter ? » Le merle attend ton signal ; tu peux aussi guetter l'instant où l'anneau sera posé.
""", key_choices(), variants=key_variants())

scene("8_quiet_secret", 8, "Derrière le rideau du fournil", """
    Derrière le rideau du fournil, tu respires l'odeur du pain. La sorcière pétrit sa pâte, les yeux tournés vers le merle à la fenêtre.

    « J'ai trouvé trois grains dans la cour ;\n    demain j'y ferai un détour. »

    « Demain… », reprend la femme.

    « Demain j'irai jusqu'au verger ;\n    rien ne m'empêche de changer. »

    « Ce n'était pas cela ! Recommence. » Elle ne supporte pas qu'une chanson lui échappe. Sa clef d'argent pend au crochet près du four. Entre le rideau et ce crochet, une planche grince sous ton pied.

    {cages_key_help}

    {item_cages_use}

    Le merle attend, le bec entrouvert. La femme tourne les yeux vers le four ; le rideau effleure ta joue.
""", key_choices(), variants=key_variants("le crochet"))

scene("8_visitor_public", 8, "Le concours de chansons", """
    À la fenêtre, Maître Merle prend son temps. La visiteuse tapote la table ; tu restes près d'elle, attendant le chant que tu lui as promis.

    « Mon voisin garde son trésor ;\n    moi, je chante et je sors encore. »

    « Il se moque de vous », dit la visiteuse à la sorcière.

    « Mes oiseaux chantent mieux. »

    « Alors écoutons-les chacun leur tour », proposes-tu. La femme monte chercher la dernière cage. Quand elle revient, la clef brille toujours à sa ceinture.

    « Approchez, dit-elle à la visiteuse. Regardez celui-ci. » Pour soulever la cage, elle pose l'anneau sur la table. {cages_key_help}

    {item_cages_use}

    La bague d'or repose entre elles. Le merle te regarde, attendant la suite de ce concours.
""", key_choices(), variants=key_variants("la table"))

scene("8_visitor_secret", 8, "Une voix dans l'escalier", """
    Quelques marches au-dessus du fournil, tu vois la table à travers la rambarde. La cage de Lison a été descendue pour l'échange ; sa voix monte vers toi, si proche que tu pourrais lui répondre.

    « Voici votre oiseau », dit la sorcière. Elle pose sa clef sur la table pour soulever la cage.

    « J'ai dit que je voulais l'entendre. Pas encore l'emporter. » La visiteuse garde sa bague au doigt. La cage reste suspendue entre les mains de la femme.

    Leur désaccord te laisse du temps, mais l'anneau est au bas des marches. {cages_key_help}

    {item_cages_use}

    « Assieds-toi donc », dit la sorcière. Le fauteuil racle le sol. Sous ce bruit, tu pourrais descendre jusqu'à la clef ou faire signe à ton compagnon.
""", key_choices(), variants=key_variants("la table"))

scene("8_departure_public", 8, "La clef entre les courroies", """
    « Il avait un fil rouge à l'anse », dis-tu. Parler du panier de Lison t'aide à tenir ton mensonge.

    « Demande aux ronces. Je n'ai pas le temps. » La sorcière revient à son chariot ; tu restes à quelques pas, comme pour attendre une meilleure réponse.

    Le vent soulève la bâche. Des ailes heurtent le bois. « Doucement ! » La femme vérifie les serrures avec sa clef, puis dépose l'anneau sur le bord du chariot pour resserrer la courroie.

    Maître Merle passe au-dessus de la cour. {cages_key_help}

    {item_cages_use}

    « Tu es encore là ? » Elle ne te regarde pas : le nœud lui résiste. Ton compagnon attend ton signal ; la clef brille tout près.
""", key_choices(), variants=key_variants("le bord du chariot"))

scene("8_departure_secret", 8, "Le premier arrêt du chariot", """
    Les roues cessent de grincer {location_cages_stop}. Tu as suivi le chariot jusque-là ; une courroie desserrée oblige la sorcière à s'arrêter. Sous la bâche, les sept oiseaux se taisent aussi. Tu retiens ton souffle.

    « Je sais que vous êtes là, dit la femme aux cages. Ce silence ne vous rendra pas libres. »

    Le merle te montre une place à couvert, au pied du chariot. Pour déplacer une cage, la sorcière pose sa clef sur le bord ; elle se penche ensuite sur la courroie.

    {cages_key_help}

    {item_cages_use}

    Lison reprend enfin son refrain. Entre les plis de la bâche, tu aperçois une aile brune. La clef est à portée ; ton compagnon guette ton signe.
""", key_choices(), variants=key_variants("le bord du chariot"), effects=effect("cart_road"))

scene("8_caught", 8, "Le verrou du cellier", """
    Le cellier sent les pommes séchées. De l'autre côté de la porte, la sorcière poursuit ses préparatifs. « Nous parlerons des oiseaux tout à l'heure. Tu m'as l'air de savoir bien des choses. » Pour l'instant, elle te garde sous verrou, sans te changer.

    Ton sac pèse toujours sur ton épaule. Dans le bois de la porte, une fente permettrait d'atteindre le verrou ordinaire. À la petite fenêtre, une branche tremble ; le merle y est venu.

    « Une porte a beau se fermer,\n    un ami peut encore entrer. »

    « Ne chante pas trop fort », souffles-tu.

    {cages_mouse_memory} Le merle pourrait attirer la femme au-dehors ; ton objet pourrait aussi dégager le verrou. Une fois dans le couloir, il resterait à prendre la clef des cages.

    La poignée remue. Le merle s'immobilise sur sa branche.
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
