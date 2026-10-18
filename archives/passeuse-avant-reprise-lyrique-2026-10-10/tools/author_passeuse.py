"""Premier chapitre interactif, relu dans le PDF de l'auteur le 10 octobre 2026."""
import hashlib
import json

from engine.content import ROOT
from engine.book_engine import validate_book

SCENES = []


def option(text, consequence, *flags, variants=()):
    return {"text": text, "consequence": consequence, "flags": list(flags),
            "consequence_variants": list(variants)}


def result(when, consequence, *flags):
    return {"when": when, "consequence": consequence, "flags": list(flags)}


def passage(title, text, a=None, b=None, values=None, variants=()):
    rank = len(SCENES) + 1
    scene = {"id": f"passeuse_1_{rank:02}", "title": title,
             "kind": "decision" if a else "ending", "rank": rank,
             "text": text.strip(), "image": f"images/passeuse/ch1_{rank:02}.png",
             "image_alt": title + " — dessin réaliste en noir et blanc.",
             "source_pages": [], "choices": [], "values": values or {},
             "variants": list(variants)}
    for index, choice in enumerate((a, b)):
        if choice:
            scene["choices"].append({"id": "a" if index == 0 else "b",
                                     **choice, "next": f"passeuse_1_{rank + 1:02}"})
    SCENES.append(scene)


def fragment(name, when, **values):
    return {"id": name, "when": when, "values": values}


passage("Quelques minutes avant la sonnerie", """
Alex s'éveilla quelques minutes avant l'heure et contempla le monde encore endormi. Sa vie tenait dans cette chambre d'une dizaine de mètres carrés : un matelas grisâtre, des habits enfouis à la hâte dans les tiroirs d'un placard cartonné, une ampoule poussiéreuse pendue au plafond. Au mur, un tableau simpliste représentait une femme au travail dont elle ne savait rien. Les murs jaunis ne la dérangeaient guère. Les autres pensionnaires n'entretenaient sans doute pas mieux leur espace.

Tout cela était à elle. Elle en connaissait les formes jusque dans l'obscurité, et pourtant rien n'y annonçait une journée différente.

La grosse sonnette du couloir résonna dans le dortoir. Les cloisons en tremblèrent. Alex prit une dernière inspiration et posa les pieds nus sur le sol froid. De l'autre côté de la porte, les pensionnaires se pressaient déjà vers les douches. Les retardataires devraient attendre longtemps.

En pyjama, elle se leva. La poignée était à portée de main ; près du lit, ses vêtements étaient encore froissés dans le placard.
""",
option("Rejoindre les douches avant que la file s'allonge",
       "Alex passa aussitôt dans le couloir. Elle trouva une douche libre et put se laver sans attendre ; les minutes gagnées lui permirent ensuite de s'habiller tranquillement.", "matin_prepare"),
option("Préparer ses vêtements avant de rejoindre le couloir",
       "Alex tira ses vêtements du placard avant de sortir. Devant les douches, la file s'était allongée. Elle attendit, puis dut s'habiller rapidement pour ne pas manquer la seconde sonnerie.", "matin_presse"))

passage("Neuf étages à descendre", """
À 7 h 20, la seconde sonnerie ordonna le départ. {preparation}

Alex vivait au neuvième étage. Elle descendit par les escaliers, comme elle y était tenue. Le bas de l'immeuble accueillait les personnes âgées ou malades ; habiter en haut passait pour un signe de longévité à venir. Les ascenseurs existaient, mais ils ne lui étaient pas destinés. Petite, on lui avait expliqué que l'énergie était vitale et que ses jambes entretiendraient sa santé. Le matin, les marches lui pesaient peu. Le soir, davantage.

Elle avait une vingtaine d'années, sans connaître précisément la date de sa naissance. L'enseignement s'était achevé dix ans auparavant : lire, écrire, calculer, quelques leçons d'histoire. Avant la ville, disait-on, les Hommes étaient désorganisés et mouraient sans avoir trouvé le bonheur. Désormais, leur travail comblait tous leurs besoins.

À quoi bon s'intéresser à ce passé imparfait ? Le présent occupait suffisamment les esprits. Les pensionnaires descendaient devant elle. Entre deux groupes, un espace se libérait sur le palier.
""",
option("Rester dans le groupe jusqu'au bas de l'escalier",
       "Alex conserva sa place entre les autres pensionnaires. Elle gagna la rue sans se presser et rejoignit une file à l'abri de la façade.", "file_abritee"),
option("Profiter de l'espace libre pour avancer plus vite",
       "Alex descendit plus vite dans l'espace laissé entre deux groupes. Elle atteignit la rue avant eux, mais la file disponible la plaça du côté des sentinelles.", "file_exposee"),
values={"preparation": "Le rituel matinal était terminé ; il ne restait qu'à partir."},
variants=(
fragment("matin_calme", {"all": ["matin_prepare"]}, preparation="Ses vêtements étaient en place et ses cheveux attachés ; elle avait même eu quelques minutes de repos."),
fragment("matin_hatif", {"all": ["matin_presse"]}, preparation="Elle achevait encore de retenir ses cheveux quand les autres sortirent. Elle les rejoignit sans avoir profité des dernières minutes de repos.")))

passage("Les lignes de la ville", """
Dans la rue, il était inutile de se hâter. Les files avançaient lentement dans les tracés peints au sol. Imaginer un autre chemin semblait inconcevable. {position}

Les sentinelles jalonnaient le trajet. Leurs pièces mécaniques tranchantes suffisaient à décourager les resquilleurs. Elles roulaient plus vite qu'un Homme ne pouvait courir. Sous l'ombre du casque métallique, des rouages dessinaient un visage : une bouche triste, impassible, et de petits yeux rouges à la recherche d'une erreur.

Le moindre faux pas entraînait une terrible punition. Chacun avait déjà vu l'horreur ; la rigueur régnait dans la ville.

Alex demeura sur sa ligne. Une machine passa près du groupe, puis tourna la tête vers la file suivante. Pendant ce bref mouvement, ses yeux quittèrent les premiers pensionnaires. Alex sentit ses épaules se raidir. Le visage revint, les roues repartirent.

La foule se remettait en marche. Elle pouvait conserver toute son attention sur le tracé, ou profiter de ce trajet obligé pour comprendre comment les sentinelles promenaient leurs regards.
""",
option("Garder les yeux sur le tracé et suivre la file",
       "Alex suivit la bande au sol. Elle traversa le passage sans attirer l'attention, mais ne sut pas à quel moment la machine avait cessé de regarder son groupe.", "regard_baisse"),
option("Observer discrètement le déplacement des regards",
       "Sans tourner franchement la tête, Alex suivit les yeux rouges. Elle remarqua qu'à chaque changement de direction, la machine abandonnait un instant la portion de rue derrière elle.", "patrol"),
values={"position": "Alex prit sa place dans le groupe."},
variants=(
fragment("file_pres_du_mur", {"all": ["file_abritee"]}, position="Près de la façade, d'autres épaules la séparaient des machines. Elle pouvait les regarder sans se trouver au premier rang."),
fragment("file_pres_des_roues", {"all": ["file_exposee"]}, position="Du côté extérieur de la file, elle entendait chaque roue approcher. Elle rentra ses mains contre elle quand le premier casque passa.")))

passage("Le chemin appris par cœur", """
Tous les jours, un unique chemin et les mêmes immeubles. Pour patienter, Alex regardait les habitants descendre et comptait les clignotements des néons. Elle pouvait prédire combien d'oscillations chaque tube produirait avant d'être dépassé. Souvent, elle espérait une surprise. Rien ne venait.

Elle passa devant la stèle des règles. Les habitants les connaissaient par cœur : être debout à la sonnerie ; ne sortir que pour travailler ; ne jamais quitter les lignes de circulation ; rentrer chez soi le soir. Simples et implacables.

À l'usine, elle retrouva son établi. Elle façonnait le bois, comme tous ceux qui l'entouraient. D'autres travaillaient ailleurs à d'autres tâches, sans doute ; elle ignorait lesquelles. Le plan et le type d'arbre étaient choisis à l'avance. Il ne restait qu'à exécuter.

Alex attacha ses longs cheveux bruns et rassembla ses outils de découpe et d'assemblage. Les besoins variaient d'un jour à l'autre. Le dessin du matin montrait une pièce rectangulaire aux extrémités travaillées, avec deux encoches. La première planche attendait devant elle.
""",
option("Étudier les mesures avant de commencer",
       "Alex relut le plan et vérifia la place des deux encoches. Une fois la scie en main, elle n'eut plus besoin de s'interrompre pour chercher une mesure.", "plan_etudie"),
option("Commencer avec les gestes habituels",
       "Alex saisit la scie et se fia à l'habitude. La première découpe fut rapide, mais elle dut revenir au plan pour retrouver la profondeur exacte des encoches.", "plan_rapide"))

passage("Le bois sous ses mains", """
Elle guida la planche devant ses mains aguerries. La scie trancha le bois ; le rabot reprit les extrémités, et deux encoches furent produites au ciseau. {mesures}

Alex était douée, sans être la meilleure. Comment rivaliser avec ceux qui exerçaient ce métier depuis des dizaines d'années ? Elle savait qu'elle s'adonnerait toute sa vie à cette unique besogne sans pouvoir montrer son mécontentement. La tâche était répétitive, nullement passionnante. On lui avait maintes fois expliqué qu'elle constituait la manière d'être heureux.

Partout, les sentinelles roulaient autour de leurs protégés, veillant à ce qu'ils demeurent attelés à l'exercice de leur bonheur. Les grands yeux verts d'Alex parcouraient parfois la salle, brièvement, sans se faire surprendre.

Au-delà de son établi, un ouvrier expérimenté travaillait à un petit montage différent. Alex en aperçut les roues. Elle revint à sa pièce : une encoche demandait encore à être reprise. Le tapis roulant attendait les ouvrages ; l'essai de la maquette allait bientôt commencer.
""",
option("Terminer soigneusement l'encoche avant de regarder ailleurs",
       "Alex reprit l'encoche et contrôla les extrémités. Elle déposa une pièce conforme sur le tapis, au prix de l'instant où l'ouvrier voisin fixait ses premières roues.", "piece_soignee"),
option("Envoyer la pièce pour suivre l'essai de la maquette",
       "Alex posa sa pièce sur le tapis et tourna discrètement les yeux vers la maquette. Elle vit les roues s'aligner, mais la petite irrégularité de son encoche partit avec l'ouvrage.", "piece_hative"),
values={"mesures": "Elle vérifia le résultat avant de poursuivre."},
variants=(
fragment("decoupe_reguliere", {"all": ["plan_etudie"]}, mesures="Les mesures retenues le matin guidèrent le ciseau. Elle posa la première pièce à terre, satisfaite, puis recommença."),
fragment("mesure_retrouvee", {"all": ["plan_rapide"]}, mesures="Elle dut comparer une encoche au dessin, retirer encore un peu de bois, puis posa la première pièce à terre. Les suivantes vinrent plus facilement.")))

passage("Quatre petites roues", """
Sur de petits rectangles de bois, quatre roues étaient accrochées. Pour essayer, l'ouvrier envoyait l'engin promener sur l'établi. Par trois fois, Alex remarqua ce montage confié aux plus expérimentés. Son regard, discret mais fasciné, suivit le rectangle qui poursuivait seul son mouvement.

Les ouvrages passaient entre des tiges articulées qui analysaient chaque partie pour attribuer une note. Une bonne appréciation pouvait valoir des confiseries ; une mauvaise, des remontrances. Trop de remontrances menaient au cachot. Après trop de séjours au cachot, plus personne ne parlait du fautif : il disparaissait de la société, sans que nul puisse être certain de son sort.

{controle}

Alex rapprocha la planche suivante. Le ciseau était dans sa main, la voiture venait de revenir près de l'ouvrier. Elle n'avait pas assez de temps pour suivre tout l'essai et reprendre toutes les mesures de ce nouvel ouvrage. Le roulement des petites roues se mêlait aux scies.
""",
option("Contrôler la nouvelle pièce avant de continuer",
       "Alex contrôla une à une les mesures de la nouvelle pièce. Les tiges ne s'y attardèrent pas. Elle avait laissé passer le nouvel essai des roues, mais évité un défaut de plus.", "controle_fait"),
option("Suivre encore l'essai des quatre roues",
       "Alex regarda la voiture rouler et dut se hâter ensuite pour retrouver le rythme des outils. Le mouvement l'avait enchantée, mais son ouvrage suivant demanda une nouvelle reprise.", "toy"),
values={"controle": "Les tiges approchaient de sa dernière pièce."},
variants=(
fragment("bonne_appreciation", {"all": ["piece_soignee"]}, controle="Les tiges examinèrent ses deux encoches, puis libérèrent la pièce. L'appréciation fut bonne ; Alex desserra un peu les épaules."),
fragment("remontrance", {"all": ["piece_hative"]}, controle="Les tiges s'attardèrent sur l'encoche imparfaite. Une remontrance lui fut adressée. Alex reprit la pièce sous le regard d'une sentinelle ; les petites roues n'avaient pas disparu, mais leur vue lui coûta ce rappel à l'ordre.")))

passage("Ce qu'on appelait le bonheur", """
Quatre pauses de longueur variable maintenaient une vie sociale. Celles de midi et du soir étaient réservées aux repas, sommaires mais suffisants, équilibrés pour ne manquer de rien. Les excès et les irrégularités étaient proscrits.

Les conversations étaient autorisées. Les non-dits, eux, restaient partout. Les robots ne quittaient jamais leur service ; près d'un casque métallique, une phrase s'achevait plus vite. {repas}

En fin de journée, Alex retrouva la stèle, les néons, son bâtiment. Les neuf étages lui coûtèrent davantage qu'au matin. Dans le couloir, les ampoules perdaient peu à peu leur luminosité, puis s'éteignaient, appelant les pensionnaires à un repos bien mérité.

C'était en cela que se constituait le bonheur : être nourrie, travailler, retrouver son lit. Alex s'allongea sans parvenir à se reconnaître dans ce mot. Depuis quelque temps, le sommeil lui venait difficilement.

Un dernier froissement passa derrière sa porte. Elle pouvait tenter de dormir aussitôt ou attendre que le couloir et les lumières s'apaisent entièrement.
""",
option("Chercher le sommeil dès qu'elle fut couchée",
       "Alex ferma les yeux. Elle s'assoupit par instants, puis s'éveilla en pleine nuit. Ses jambes étaient moins lourdes, mais l'envie de retrouver le toit la tira du lit.", "premier_repos"),
option("Attendre le silence complet avant de fermer les yeux",
       "Alex écouta s'éteindre les pas. Lorsqu'elle finit par s'assoupir, une partie de la nuit était déjà passée. Elle s'éveilla peu après, fatiguée et impatiente de retrouver le toit.", "premiere_fatigue"),
values={"repas": "Elle mangea en écoutant les quelques paroles qui circulaient."},
variants=(
fragment("repas_apres_remontrance", {"all": ["piece_hative"]}, repas="Alex parla peu. La remontrance revenait dès qu'une machine passait. Elle ne risquait pas le cachot pour cette seule faute, mais connaissait la suite des sanctions."),
fragment("repas_sans_reproche", {"all": ["piece_soignee"]}, repas="Alex prit le temps de manger. Aucune remontrance ne lui avait été adressée ; pourtant, elle guettait comme les autres les machines qui ne s'arrêtaient jamais.")))

passage("Le passage secret", """
En pleine nuit, Alex poussa discrètement la porte. Les rayons de lune traversaient les fenêtres du couloir. Elle s'arrêta, examina les environs, puis rejoignit le mur opposé. La plaque métallique de la ventilation se souleva entre ses doigts.

Petite, peut-être la plus petite des pensionnaires qu'elle côtoyait, et agile, elle se hissa sans peine dans l'étroite ouverture. Elle avait découvert ce chemin l'année passée. Depuis, elle le parcourait chaque soir, sans craindre de se perdre. Ce qu'elle trouvait au bout lui semblait valoir les peines encourues.

{fatigue}

Le conduit formait un dédale qu'elle connaissait par les mains et les genoux. Chaque coude la rapprochait de l'ouverture habituelle. Le métal portait le moindre mouvement, et le couloir, derrière elle, était silencieux.

Elle sentit l'air plus froid qui venait du toit. La dernière portion était étroite ; avancer vite lui rendrait quelques minutes de nuit, mais ses appuis risquaient de faire résonner les tôles.
""",
option("Avancer en ménageant chaque appui",
       "Alex répartit son poids et s'arrêta dès qu'une tôle vibrait. Elle atteignit le toit sans bruit, plus tard qu'elle ne l'aurait voulu.", "conduit_prudent"),
option("Gagner rapidement l'ouverture du toit",
       "Alex franchit le dernier coude d'un mouvement vif. Une tôle claqua sous son genou. Sur le toit, elle resta basse un moment avant d'oser s'approcher du bord.", "conduit_bruyant"),
values={"fatigue": "Elle prit appui contre les tôles pour avancer."},
variants=(
fragment("premiere_nuit_reposee", {"all": ["premier_repos"]}, fatigue="Le peu de sommeil obtenu lui avait rendu des gestes plus sûrs. Elle progressa sans hésiter."),
fragment("premiere_nuit_fatiguee", {"all": ["premiere_fatigue"]}, fatigue="Ses jambes gardaient le poids des neuf étages. Elle déplaça un genou engourdi, puis reprit sa progression.")))

passage("La frontière des rêves", """
Elle déboucha sur le toit et retrouva sa place préférée. Assise au bord du vide, les pieds flottant dans la nuit, elle avait devant elle le plus beau panorama du monde.

Les bâtiments portaient les néons du trajet matinal. Leurs couleurs se perdaient et résonnaient dans le ciel. Les étoiles, la lune, le vent dans ses longs cheveux bruns : c'était sa joie et sa liberté.

En dessous, les rues s'éclairaient par endroits. Quelques patrouilles poursuivaient leur excursion incessante. Alex en observait les dangers, puis ses craintes s'effaçaient. Dans la solitude, ses rêves l'accompagnaient. Elle courait par la pensée là où naissaient les tempêtes, là où le soleil disparaissait, là d'où le vent venait. Elle ne savait rien, mais avait déjà tout vu.

Elle restait à cette frontière jusqu'à l'aurore, se reprochait ensuite d'avoir engagé sa vie pour un songe, et recommençait le lendemain. Une seule règle demeurait absolue : retrouver son lit avant la première sonnerie. Cette nuit encore, des roues passaient au-dessous des étoiles.
""",
option("Laisser ses pensées suivre les étoiles",
       "Alex leva les yeux et oublia un moment les rues. Lorsqu'un roulement la ramena au toit, elle ne sut plus où la patrouille se trouvait.", "stars"),
option("Suivre la patrouille avant de reprendre ses rêves",
       "Alex regarda la machine disparaître entre deux bâtiments. Elle reconnut son roulement et retint le détour qu'elle venait de faire, puis laissa les étoiles reprendre leur place.", "ronde_toit"))

passage("Un caillou dans la nuit", """
Le monde était superbe. Mais quel intérêt de le concevoir ainsi, si sa vie ne devait jamais dépasser le bout de son commencement ? Alex aurait dû être heureuse. Elle était triste.

Ce soir-là, par dépit, elle lança un caillou vers les rues vides. L'ombre d'une sentinelle se propagea sous un néon. La lumière rouge, vive, foudroyante, se tourna vers le toit.

L'avait-elle remarquée ? À cette distance, pouvait-elle seulement la voir ? Alex sentit son cœur battre plus fort que le bruit de ses pas. Toute la ville qui, un instant auparavant, accueillait ses rêves sembla se refermer autour de ce regard.

L'ouverture de la ventilation était derrière elle. Il fallait la rejoindre, rentrer, replacer la plaque, retrouver la chambre avant qu'une présence ne trouble le couloir. La surface du toit la laissait exposée. Le rebord pouvait cacher son visage le temps de reculer, mais ce détour lui ferait perdre quelques secondes.

Les yeux rouges demeuraient là. Alex ne savait pas s'ils voyaient une silhouette ou regardaient seulement dans sa direction.
""",
option("Rejoindre la ventilation sans s'arrêter",
       "Alex se précipita dans l'ouverture. Sa paume frotta contre le bord métallique ; une éraflure lui brûla la main. Elle continua, portée par la peur, jusqu'à la grille du couloir.", "main_eraflee"),
option("Se retirer derrière le rebord avant de rejoindre le conduit",
       "Alex s'abaissa et recula à couvert. Lorsqu'elle gagna enfin le conduit, le détour lui avait coûté du temps : elle traversa les dernières tôles trop vite, les faisant vibrer.", "retour_resonnant"))

passage("Les yeux qui restaient", """
Ses doigts anxieux peinèrent à remettre la plaque en place. Enfin, le clic du verrouillage fut aussi libérateur que bruyant. Elle regarda le couloir : personne. Derrière la porte de sa chambre, personne non plus.

Blottie sous sa couverture, elle se tourna et se retourna. La flamme rouge ne cessait de la poursuivre. {main}

La première sonnerie contracta tout son corps. Assise sur son matelas, désespérée de n'avoir pas trouvé le sommeil, elle fut rassurée de se découvrir seule dans la chambre dénudée. Rien n'avait changé.

Elle tira lentement la poignée. Déjà en retard, elle fut bousculée par un voisin impatient, guère plus aimable qu'à l'habitude. Devant les douches, elle s'adossa aux carreaux blancs et graisseux. Deux points rouges surgirent dans sa somnolence, puis s'effacèrent.

Elle sursauta et reprit ses esprits. Quelle idiote : son imagination seulement. Son crâne la torturait. Les autres ne semblaient rien avoir remarqué. La file avançait ; elle devait retrouver des gestes ordinaires.
""",
option("Se concentrer sur les gestes familiers du matin",
       "Alex se lava et s'habilla dans l'ordre habituel. Les gestes l'aidèrent à reprendre pied ; elle rejoignit la rue avec le groupe, malgré son mal de tête.", "matin_maitrise"),
option("Rester immobile un instant pour calmer sa respiration",
       "Alex attendit que sa respiration se calme. Elle rejoignit ensuite les derniers pensionnaires et dut descendre plus vite pour rattraper la file.", "matin_retarde"),
values={"main": "Même sous la couverture, elle croyait encore voir les yeux rouges."},
variants=(
fragment("paume_douloureuse", {"all": ["main_eraflee"]}, main="L'éraflure la piquait dès qu'elle serrait la couverture. Elle changea sa main de place, sans parvenir à chasser la lumière rouge."),
fragment("echo_du_retour", {"all": ["retour_resonnant"]}, main="Au souvenir des yeux se mêlait le bruit de son retour. Avait-on entendu les tôles ? La question lui interdisait le sommeil.")))

passage("Une journée sans incident", """
Dans la rue, elle risqua un regard vers une sentinelle. Un frémissement glacé lui traversa les entrailles, sans qu'elle puisse en déterminer l'origine. La file poursuivit pourtant sa marche.

Le travail, le déjeuner, le retour à la chambre : l'incessant manège de l'heureuse marionnette perdura sans embarras. {travail} La journée ordinaire lui rendit confiance. Rien ne s'était produit ; peu avant minuit, elle se réveilla avec un sourire, abattant le reste de ses craintes.

Quel plaisir de défier impunément les règles ! À quoi bon la prudence et la raison ? Elle reprit le chemin des nuages avec un surcroît de discrétion. Sur le toit seulement, un bruit répété attira son attention.

Quelqu'un approchait dans la rue. Les machines traversaient rarement ce coin à cette heure. Le roulement se mêlait à des cliquetis. Alex se tint près du dernier rebord, oubliant déjà les leçons de la veille. {ronde}
""",
option("Écouter pour situer le roulement avant de regarder",
       "Alex suivit le bruit vers l'entrée de son immeuble. Elle s'approcha du bord en restant basse et regarda seulement quand les roues furent tout près de la porte.", "approche_ecoutee"),
option("Regarder aussitôt par-dessus le rebord",
       "Alex passa la tête au-dessus du rebord. La scène lui apparut immédiatement, mais elle demeura exposée jusqu'à ce que la peur la fasse se retirer.", "approche_vue"),
values={"travail": "Les mêmes pièces occupèrent ses mains jusqu'au soir.",
        "ronde": "Elle ne reconnaissait pas ce passage inhabituel."},
variants=(
fragment("travail_main_eraflee", {"all": ["main_eraflee"]}, travail="La paume éraflée la gêna sur le rabot. Elle changea sa prise et acheva néanmoins les pièces demandées."),
fragment("ronde_reconnue", {"all": ["ronde_toit"]}, ronde="Elle reconnaissait le roulement, mais pas ce trajet : la ronde observée la veille contournait le bâtiment au lieu de s'y arrêter.")))

passage("Trois sentinelles", """
Trois sentinelles franchissaient la porte d'entrée, anormalement ouverte. Alex les vit disparaître à l'intérieur de son immeuble.

Elle voulut déguerpir du toit et regagner sa chambre au plus vite. Qu'adviendrait-il d'elle si on la trouvait ici ? La liberté éprouvée un instant auparavant n'était plus qu'une distance terrible entre elle et son lit.

{recul}

Elle ignorait encore à qui les robots rendaient visite. Cela ne changeait rien au danger de rester sur le toit. Le conduit débouchait au neuvième étage, près de sa porte. Les ascenseurs, eux, étaient réservés aux machines aussi sûrement qu'ils lui étaient refusés.

Le dernier casque venait de disparaître derrière l'entrée. Alex pouvait commencer aussitôt la traversée du dédale, au risque de heurter les tôles, ou prendre le temps de retrouver les appuis qu'elle connaissait. Elle ne pouvait plus attendre de savoir ce que les robots cherchaient. Le chemin familier la séparait maintenant de ce qu'elle espérait être encore un refuge.
""",
option("Reprendre immédiatement le conduit",
       "Alex se glissa dans le conduit sans attendre. Elle gagna vite les premiers mètres, mais un de ses genoux fit vibrer une plaque ; elle dut s'immobiliser avant de continuer.", "retour_hatif"),
option("Reprendre le passage en contrôlant ses appuis",
       "Alex retrouva la position qui lui permettait de ramper sans heurter les tôles. Elle avança moins vite, mais conserva assez de calme pour distinguer les bruits de l'immeuble.", "retour_controle"),
values={"recul": "Elle recula brusquement vers l'ouverture."},
variants=(
fragment("recul_deja_abrite", {"all": ["approche_ecoutee"]}, recul="Déjà basse derrière le rebord, elle put se retirer sans relever son visage."),
fragment("recul_a_decouvert", {"all": ["approche_vue"]}, recul="Elle s'abaissa si brusquement que ses mains cherchèrent le sol. Elle ne sut pas si un regard s'était levé vers elle.")))

passage("L'ascenseur montait", """
Le retour dans la ventilation devint un formidable cauchemar. Le moindre faux pas engendrait un écho qui semblait résonner au plus profond du bâtiment. Les doigts d'Alex se raidirent sur le métal.

Un bruit nouveau monta vers elle : des cliquetis, des engrenages, la vibration d'une mécanique en mouvement. C'était l'ascenseur. Les robots étaient en train de monter.

{avance}

La sortie du conduit était proche. Alex distinguait les ouvertures de la grille, le peu de lumière qui traversait le couloir. Elle voulut gagner les derniers mètres et se retrouver de l'autre côté. Son lit n'était qu'à quelques pas, mais le bruit de l'ascenseur semblait déjà l'avoir atteinte.

Il fallait regarder avant de sortir. Elle pouvait rester un instant dans le conduit pour écouter l'arrêt de la cabine, ou profiter des derniers bruits mécaniques pour dépasser la grille. Les mêmes tôles qui l'avaient conduite chaque soir vers sa liberté lui paraissaient maintenant trop étroites pour contenir sa peur.
""",
option("Écouter l'arrêt de l'ascenseur avant de sortir",
       "Alex attendit le changement du bruit, puis écarta la grille. Elle sut que la cabine avait atteint l'étage ; elle sortit en restant tout près de la cloison.", "ascenseur_repere"),
option("Sortir pendant que la mécanique couvrait ses mouvements",
       "Alex dépassa la grille sans attendre. Les engrenages couvrirent le frottement de la plaque, mais elle se retrouva dans le couloir sans savoir où la cabine s'était arrêtée.", "sortie_rapide"),
values={"avance": "Elle reprit sa progression vers la grille."},
variants=(
fragment("retour_heurte", {"all": ["retour_hatif"]}, avance="Une nouvelle vibration sous son genou lui fit retenir son souffle. Elle avait avancé vite, sans réussir à faire taire le métal."),
fragment("retour_ecoute", {"all": ["retour_controle"]}, avance="Ses appuis plus mesurés lui permirent de suivre la montée de la mécanique. Ce bruit ne venait pas de ses mouvements.")))

passage("Devant sa chambre", """
La lune, cachée par les nuages, ne dévoilait qu'une partie du couloir. Les yeux rouges suffirent à révéler le reste. Les trois robots étaient devant la porte de sa chambre.

C'était pour elle qu'ils étaient venus.

Alex recula d'un pas et son dos percuta la cloison. Ses muscles pétrifiés semblaient sur le point de rompre, mais l'ombre la cachait encore. La première machine déplia un bras articulé terminé par un fusil et disparut dans la pièce. Alex la vit ensuite ressortir. Ces êtres insensibles ne laissaient rien trahir.

{position}

Elle respira longuement et reprit un peu de sang-froid. L'escalier n'était pas loin. C'était l'unique échappatoire possible.

Elle rejoignit le lourd battant métallique et posa les doigts sur la poignée. Retenir la porte pouvait ralentir son passage ; la pousser franchement ferait gagner du temps, mais risquait de la faire retomber. Dans le couloir, les machines demeuraient près du lit vide.
""",
option("Retenir le battant après l'avoir franchi",
       "Alex accompagna la porte. Une charnière grinça malgré elle ; les rouages virèrent vers le bruit. Elle courut, mais eut le temps de gagner la première volée avant leur mouvement.", "avance_escalier"),
option("Franchir la porte et la laisser retomber",
       "Alex poussa le battant et s'élança. Il grinça en retombant ; les robots réagirent aussitôt. Elle entendit leurs roues avant d'avoir quitté le premier palier.", "poursuite_proche"),
values={"position": "Elle demeura contre le mur, à l'écart de la lumière."},
variants=(
fragment("sortie_contre_cloison", {"all": ["ascenseur_repere"]}, position="En sortant près de la cloison, elle avait trouvé l'ombre immédiatement. Elle put attendre le retour du bras armé sans se déplacer."),
fragment("sortie_recul", {"all": ["sortie_rapide"]}, position="Il lui fallut se décaler pour échapper à la lumière pâle du couloir. Son épaule frotta le mur ; elle resta ensuite immobile.")))

passage("Neuf paliers, une sortie", """
La cage d'escalier formait un large carré. Des vitres dispersées aux étages laissaient percer la lune, mais une même obscurité régnait sur les paliers. Tout en bas, la porte ouverte livrait un bras de lumière.

Alex osa un regard par-dessus la rambarde. La voie semblait dégagée. Elle dévala les marches deux par deux. Neuf paliers la séparaient de la sortie. Par trois fois, elle fut proche de chuter sans modérer sa course.

{poursuite}

Le bruit mécanique de l'ascenseur se fit de nouveau entendre. Les sentinelles descendaient pour la coincer en bas. Son cœur battait si fort que l'adrénaline sembla lui donner les ailes manquantes.

La lumière du perron grandissait entre deux volées. Les appuis devenaient moins sûrs à mesure que ses jambes se précipitaient. Une main sur la rampe pouvait la retenir ; se concentrer seulement sur les marches lui permettrait de conserver toute sa vitesse. Il restait encore des étages, et l'ascenseur poursuivait sa descente.
""",
option("S'aider de la rampe pour assurer les derniers appuis",
       "Alex garda une main sur la rampe. Elle rattrapa un déséquilibre sans tomber et atteignit le perron, le souffle court.", "descente_assuree",
       variants=(result({"all": ["main_eraflee"]}, "Alex serra la rampe malgré la brûlure de sa paume. Elle rattrapa son déséquilibre et atteignit le perron ; sa main la lançait davantage."),)),
option("Conserver sa vitesse sans s'appuyer sur la rampe",
       "Alex concentra ses regards sur les marches et conserva sa vitesse. Dans un déséquilibre, son genou heurta le bord du palier. Elle poursuivit sans tomber, mais la douleur l'accompagna jusqu'au perron.", "genou_heurte"),
values={"poursuite": "Elle ne se retourna pas."},
variants=(
fragment("quelques_marches_avance", {"all": ["avance_escalier"]}, poursuite="Les premières marches gagnées lui permirent de reprendre un appui avant de repartir."),
fragment("roues_tout_pres", {"all": ["poursuite_proche"]}, poursuite="Des roues résonnèrent derrière le battant. Alex accéléra encore, bien que ses pieds commencent à lui échapper.")))

passage("Au-delà du chemin autorisé", """
La lune, dégagée de tout nuage, éclairait le perron. Alex chercha l'ascenseur des yeux. Non, il n'était pas encore arrivé : le monte-charge poursuivait sa lente descente.

Elle observa l'immeuble d'en face, hésita une seconde, puis se précipita sur les routes habituelles. À peine quelques mètres plus loin, une porte coulissante résonna. Elle dépassa les néons, la stèle et parvint à l'usine sans rencontrer de machine.

{douleur}

La voie principale se prolongeait. Des rues plus petites pointaient ailleurs. Alex n'avait jamais dépassé l'extrémité de la frontière imposée. Choisir une direction lui parut presque impossible, à elle qui n'avait jamais eu de jugement à rendre.

Derrière elle, le trajet familier pouvait mener les robots aussi sûrement qu'il l'avait menée. Une rue parallèle quittait l'artère centrale près de l'usine ; plus loin, un autre passage rejoignait le même quartier. Elle devait s'écarter du seul chemin que la ville lui avait appris.
""",
option("Prendre immédiatement la rue parallèle",
       "Alex quitta l'artère centrale au premier passage. Sa course se prolongea dans une rue inconnue avant qu'elle ose enfin ralentir.", "rue_directe"),
option("Longer l'usine avant de quitter la voie principale",
       "Alex longea l'usine et reprit un peu de souffle à l'abri de son mur. Elle gagna ensuite le passage suivant ; les voix et les machines du travail restèrent derrière elle.", "detour_usine"),
values={"douleur": "Son souffle ne se calmait pas encore."},
variants=(fragment("genou_pendant_fuite", {"all": ["genou_heurte"]},
                   douleur="Son genou la lançait à chaque enjambée. Elle pouvait continuer, mais ne pourrait pas courir ainsi toute la nuit."),))

passage("Une réplique imparfaite", """
Le dépaysement fut de courte durée. Chaque parcelle semblait la copie de la précédente. L'horizon libre de danger, Alex marcha plutôt que de courir pour réduire le bruit de ses pas.

Une stèle la fit s'arrêter. Les mêmes mots, les mêmes marques d'usure, la même disposition. Était-elle revenue sur ses pas ? Elle imagina les robots profitant de sa distraction pour la rattraper. La panique la fit tourner sur elle-même.

{souffle}

Elle regarda de nouveau. Il fallait comprendre avant de repartir au hasard. La rue lui paraissait plus étroite que celle du trajet matinal ; plus loin, les néons éclairaient autrement les façades. Deux détails minces dans un monde qui répétait obstinément ses formes.

Ces bâtiments qu'elle ne connaissait pas étaient pourtant enracinés en elle. Si elle pouvait distinguer une copie du lieu véritable, cette familiarité lui donnerait un répit. Au bout de la perspective, une masse sombre interrompait la rue.
""",
option("Comparer la largeur de la rue à celle du trajet habituel",
       "Alex constata que les façades étaient plus proches. Elle n'était pas revenue chez elle. Elle passa la stèle, vérifia la nouvelle couleur des néons et continua jusqu'à l'immense mur de béton.", "repere_rue"),
option("Examiner les néons pour distinguer les deux quartiers",
       "Alex suivit les clignotements familiers, mais leur couleur était différente. Cette certitude la remit en marche ; la rue plus étroite confirma ensuite qu'elle avançait vers un quartier inconnu.", "new_neons"),
values={"souffle": "Elle essaya de calmer sa respiration."},
variants=(
fragment("course_encore_presente", {"all": ["rue_directe"]}, souffle="L'effort de la course brouillait encore son regard. Elle posa les mains contre ses cuisses le temps de reprendre son souffle."),
fragment("souffle_repris_usine", {"all": ["detour_usine"]}, souffle="Le souffle repris près de l'usine lui permit de rester un instant immobile, malgré la peur de voir revenir les yeux rouges.")))

passage("Quand le jour revenait", """
Alex longea l'opaque muraille. La pénombre se dissipait ; la rougeur du soleil levant apparaissait au sommet des toits. Avec elle, la liberté d'aller et venir disparaissait.

La première sonnerie ne tarderait pas. Manquer au devoir rituel lui semblait une lâcheté. L'envie de retourner travailler devint si forte qu'elle voulut retrouver son lit et effacer la nuit. Elle regrettait la vie qu'elle avait longuement détestée. Là, au moins, le chemin était connu.

Le retour demeurait impossible. Elle se sentit perdue, abandonnée, et pleura. C'était de sa faute, pensait-elle ; elle n'avait jamais réussi à saisir le bonheur qui s'acharnait à la rendre heureuse.

Son instinct finit par la relever. Pour survivre, il fallait se cacher. Elle aperçut une étroite fenêtre au sous-sol du bâtiment adjacent. Le cadre semblait trop petit pour une personne de corpulence normale, mais sa petite taille lui permettrait de passer. La fenêtre n'était pas verrouillée. Derrière, des tuyaux occupaient la pénombre.
""",
option("Examiner le local avant d'y entrer doucement",
       "Alex vérifia qu'aucun mouvement ne troublait le sous-sol, puis passa une épaule et se laissa descendre en retenant son poids. Le cadre ne reçut qu'un frottement.", "entree_discrete"),
option("Se mettre immédiatement à l'abri dans le sous-sol",
       "Alex se glissa dans le cadre sans attendre. En descendant, elle heurta un tuyau ; le métal résonna et elle se recroquevilla aussitôt dans le coin le plus sombre.", "entree_heurtee"))

passage("Le refuge brûlant", """
Le local était exigu et paraissait délaissé. Les canalisations d'eau du bâtiment le traversaient ; les longs tuyaux de chauffage rendaient la température difficilement supportable. {entree}

La première sonnerie retentit. Alex sentit aussitôt vibrer les mouvements des habitants. Une secousse uniforme et méthodique prit naissance au-dessus d'elle, puis s'estompa. Le second ordre de ralliement relança le rythme. Enfin, le départ des troupes résonna comme un coup de tonnerre dans la cave.

Peu à peu, les derniers bruits se dissipèrent. Le silence devint écrasant. Un filet d'eau tombait d'une canalisation défectueuse. Il pourrait la désaltérer ; pour manger, elle n'apercevait pas la moindre miette.

Elle devait tenir jusqu'au soir dans cette chaleur, après la nuit sans sommeil et la course. Le coin le plus éloigné des conduites offrait un peu d'espace. D'autres recoins, près des longs tuyaux, restaient à examiner. Elle regarda l'eau tomber, puis son refuge.
""",
option("Boire et chercher la place la moins chaude pour attendre",
       "Alex but au filet d'eau, examina le sol sans y trouver de nourriture, puis s'installa loin des conduites chaudes. La chaleur persistait, mais elle n'avait plus à la supporter contre son dos.", "repos_menage"),
option("Fouiller d'abord les recoins près des conduites",
       "Alex explora jusqu'aux recoins les plus chauds, sans trouver une miette. Elle revint boire et se replia enfin ; l'effort dans cette chaleur avait ajouté un vertige à sa fatigue.", "chaleur_subie"),
values={"entree": "Elle se cala dans un coin."},
variants=(
fragment("cave_entree_prudente", {"all": ["entree_discrete"]}, entree="Elle put choisir son coin sans bouger brusquement les tuyaux."),
fragment("cave_entree_inquiete", {"all": ["entree_heurtee"]}, entree="L'écho du tuyau la retint longtemps immobile. Elle n'osa changer de place qu'au bruit de la première sonnerie.")))

passage("Une journée sous les tuyaux", """
Le bruit des gouttes, d'abord presque imperceptible, devint irritant. Il se mêla à la chaleur et aux cauchemars d'Alex lorsqu'elle trouva le sommeil.

Que pensaient-ils d'elle au travail ? Son établi vide attirait-il des regards que chacun feignait de détourner ? Raconterait-on des histoires sur sa disparition ? Les sentinelles la cherchaient-elles encore ?

Les questions tournaient, gagnaient de l'ampleur dans ses rêves. Elle se réveillait sans avoir recouvré d'énergie, puis refermait les yeux en attendant le soir. {chaleur}

Elle voulait quitter l'isolement de cette cave, mais devait attendre que les travailleurs soient couchés et la pénombre revenue. Enfin, les pas cadencés du retour se firent entendre. La délivrance approchait.

Alex se cramponna à la fenêtre. Le soleil menaçait de disparaître entièrement ; au-dessus d'elle, les derniers mouvements n'avaient pas encore tous cessé. Elle pouvait attendre leur silence ou quitter son refuge dès que la lumière serait effacée.
""",
option("Attendre que les derniers pas se taisent",
       "Alex attendit le silence complet, puis quitta la cave. Une part de la nuit était déjà passée, mais aucun mouvement d'habitant ne l'accueillit dans la rue.", "sortie_tardive"),
option("Sortir dès que le soleil eut disparu",
       "Alex sortit dès la disparition du soleil. Un dernier bruit de porte la fit se retirer à l'abri d'une façade ; elle attendit là que le calme revienne avant de marcher.", "sortie_precoce"),
values={"chaleur": "Les tuyaux lui rappelaient le lieu à chaque réveil."},
variants=(
fragment("repos_loin_des_tuyaux", {"all": ["repos_menage"]}, chaleur="Elle demeurait épuisée, mais pouvait étendre les jambes sans toucher les conduites brûlantes."),
fragment("malaise_apres_recherche", {"all": ["chaleur_subie"]}, chaleur="Le vertige revint chaque fois qu'elle tentait de se lever trop vite. Elle resta assise avant de reprendre appui sur la fenêtre.")))

passage("Une forme nouvelle", """
Lasse de ses cauchemars, Alex reprit sa route vagabonde. Les robots se faisaient entendre de loin ; au moindre danger, elle se réfugiait dans des recoins qui lui semblaient déjà rencontrés cent fois.

Elle n'avait ni but ni espoir. Le monde n'était-il qu'un paysage répété à l'infini ? La faim la terrassait. Un instant, elle s'imagina périr de solitude : elle avait refusé les offrandes de la ville, qui l'avait rejetée à son tour.

La lune guida ses pas vers une immense grue dressée face aux tours. Ce paysage nouveau prouvait son avancée. Elle avait aperçu des machines semblables depuis son toit, jamais d'aussi près.

Le souvenir du panorama la poussa vers l'échelle adossée aux bandes métalliques. Avant de quitter l'ombre des façades, elle entendit un roulement plus loin. {patrouille} La grue était accessible par une traversée directe, ou en longeant plus longtemps les bâtiments. Elle ne pouvait y gagner son ancien toit, mais peut-être retrouver le regard qu'elle y posait sur la ville.
""",
option("Attendre que le roulement s'éloigne avant de traverser",
       "Alex resta à l'abri jusqu'à ce que le roulement s'efface. Elle rejoignit l'échelle sans nouvel arrêt, mais avait laissé passer de précieuses minutes de nuit.", "grue_prudente"),
option("Rejoindre la grue par le trajet le plus court",
       "Alex quitta la façade. Le bruit d'une machine la contraignit à se retirer dans un recoin ; lorsqu'il s'éloigna, elle put enfin gagner l'échelle.", "grue_directe",
       variants=(result({"any": ["patrol", "ronde_toit"]},
                        "Alex attendit le changement de direction qu'elle avait déjà observé chez les machines, puis traversa pendant que le regard quittait la rue. Elle atteignit l'échelle sans devoir se cacher de nouveau.", "traversee_calculee"),)),
values={"patrouille": "Elle ne savait pas si la machine allait revenir dans cette rue."},
variants=(fragment("mouvement_connu", {"any": ["patrol", "ronde_toit"]},
                   patrouille="Elle reconnut le moment où les roues changeaient de direction. Il laissait derrière la machine ce bref espace qu'elle avait déjà observé."),))

passage("Les barreaux dans les nuages", """
Elle s'accrocha à l'échelle et monta. L'humidité rendait les barreaux glissants. Les nuages effleurèrent les parcelles découvertes de sa peau ; chaque mètre engageait sa vie.

Alex s'entêtait. Elle ne considérait pas cette ascension nécessaire : elle espérait seulement contempler encore la ville par les yeux enchantés d'autrefois. {genou}

Un instant, elle se sentit revenue dans son existence passée. Non, ce n'était plus la même. Dans la tristesse demeurait cet élan d'aventure et de liberté dont elle avait toujours rêvé. La pensée lui rendit du courage. Pour la première fois, elle pourrait rejoindre les lumières autrefois seulement aperçues au loin.

Une plateforme se dessinait au-dessus d'elle. Ses mains serraient le métal humide, ses bras supportaient les arrêts aussi bien que les mouvements. Reprendre un appui à chaque barreau ralentirait l'ascension ; continuer sans pause la conduirait plus vite en haut. Le vent passait dans ses vêtements, et la ville était maintenant loin sous ses pieds.
""",
option("Reprendre soigneusement chaque prise avant de monter",
       "Alex vérifia ses prises et ménagea ses bras. Elle atteignit la plateforme lentement ; lorsqu'elle relâcha enfin le métal, ses doigts demeuraient assez sûrs pour la retenir.", "prises_menagees"),
option("Continuer sans pause jusqu'à la plateforme",
       "Alex accéléra malgré les barreaux glissants. Une prise lui échappa ; elle se rattrapa et gagna la plateforme, mais ses bras tremblaient longtemps après l'effort.", "bras_epuises"),
values={"genou": "Elle cherchait chaque nouvel appui avant de lâcher le précédent."},
variants=(fragment("genou_pendant_montee", {"all": ["genou_heurte"]},
                   genou="Son genou heurté dans l'escalier se rappela à elle. Elle dut se hisser davantage avec les bras pour soulager cette jambe."),))

passage("Derrière le mur", """
Un sourire inexplicable éclaira son visage malheureux. Tout n'était pas à jeter. Tout était à refaire.

Alex regarda les immeubles sortir de la terre qui les avait vus pousser. Son regard suivit le sommet du mur rencontré. À perte de vue, la ville étendait sa monotonie. Mais derrière cette façade, rien ne dépassait : aucune trace des vieilles tours.

Elle en était certaine. De l'autre côté se dressait un territoire imprévisible, un nouveau monde qu'il lui fallait rejoindre.

L'hésitation fut longue. Les heures avaient défilé et le ciel commençait à changer. Se faire attraper maintenant n'en valait pas la peine. La raison l'emporta sur l'envie : elle attendrait la prochaine nuit.

Dehors, le froid rongeait son corps mal couvert. {bras} Avant de se laisser prendre par le sommeil, elle pouvait observer les façades pour mémoriser le chemin vers le mur, ou se recroqueviller sans attendre pour conserver le peu de chaleur de ses vêtements.
""",
option("Repérer les façades qui conduisaient au mur",
       "Alex relia le mur aux façades et aux lumières voisines. Elle s'attarda dans le froid, puis s'endormit avec un trajet en tête.", "wall_route"),
option("Se replier immédiatement à l'abri de la plateforme",
       "Alex se recroquevilla pour soustraire son corps au vent. Le sommeil finit par la prendre ; elle n'avait pas préparé de trajet, mais conservait un peu mieux sa chaleur.", "abri_grue"),
values={"bras": "Elle replia ses bras contre elle."},
variants=(
fragment("bras_apres_effort", {"all": ["bras_epuises"]}, bras="Ses bras continuaient de trembler quand elle essayait de les ramener contre elle."),
fragment("prises_encore_sures", {"all": ["prises_menagees"]}, bras="Elle put se déplacer jusqu'à une position moins exposée sans craindre de lâcher la rambarde.")))

passage("Les colonnes vivantes", """
Les sonneries successives tirèrent Alex de son fragile sommeil. Les portes s'ouvrirent aux artères ; des fantômes sans visage et sans nom sortirent comme chaque matin.

Les colonnes vivantes emplirent les rues désertes avec une parfaite symétrie. Les formes se confondaient à mesure qu'elles avançaient, entre habitants et robots. Alex avait été l'un de ces êtres, une âme au désir enlevé, dont l'espoir tenait au retour au lit. Dans sa douleur physique et morale, elle revêtait pour la première fois une apparence humaine.

{froid}

Le soir, les allées et venues s'exécutèrent de nouveau, puis le calme revint brutalement. Il était temps de descendre.

L'échelle humide se perdait dans le vide. Chaque pas mal assuré serait une nouvelle angoisse. {descente} La rue l'attendait au-dessous ; au-delà des façades, le mur demeurait l'endroit où tout devait commencer.
""",
option("Assurer les prises et les appuis pendant la descente",
       "Alex descendit en vérifiant ses prises. Elle sauta les trois derniers échelons, atterrit dans la rue et repartit sans devoir s'immobiliser.", "descente_menagee",
       variants=(result({"all": ["genou_heurte"]}, "Alex descendit de côté pour ménager son genou, puis sauta les trois derniers échelons. Elle amortit sur l'autre jambe et dut marcher quelques pas avant de retrouver un rythme."),)),
option("Descendre rapidement pour profiter du calme",
       "Alex se pressa sur l'échelle, sauta les trois derniers échelons et atterrit lourdement. Elle reprit son souffle contre la grue avant de repartir.", "descente_lourde",
       variants=(result({"all": ["genou_heurte"]},
                        "Alex descendit vite et sauta les trois derniers échelons. La réception réveilla brutalement son genou ; elle dut attendre que la douleur diminue avant de quitter la grue.", "genou_aggrave"),)),
values={"froid": "Le froid et la faim rendirent la journée interminable.",
        "descente": "Elle plaça les mains sur les montants."},
variants=(
fragment("abri_du_vent", {"all": ["abri_grue"]}, froid="L'abri choisi avait limité le vent, sans lui rendre un vrai repos. Elle attendit le soir dans le froid et la faim."),
fragment("attente_apres_reperage", {"all": ["wall_route"]}, froid="Le trajet mémorisé occupait ses pensées quand le froid la faisait trembler. Elle attendit le soir sans perdre cette direction."),
fragment("descente_genou_douloureux", {"all": ["genou_heurte"]}, descente="Son genou douloureux lui interdisait de se laisser tomber trop lourdement sur chaque nouvel appui.")))

passage("La rivière sous le béton", """
{chemin}

Une envie d'explorer, de trouver, de croire la portait. Cette anxiété n'était plus la peur de mourir malheureuse, mais le vertige d'une nouvelle vie.

Au pied du mur, Alex contempla sa hauteur infranchissable. Un tel ouvrage devait pourtant abriter une faille. Elle le longea lentement, cherchant un passage, même une fissure. Son optimisme diminuait avec le trajet.

Puis une rivière apparut. Elle prenait source de son côté, plongeait sous le béton et prolongeait son chemin. Alex la contempla comme un trésor.

La température était basse. Elle n'hésita pourtant guère. L'ouverture sous le mur était si basse qu'elle devrait s'immerger entièrement pour la franchir. {jambe}

Elle s'approcha du courant. Près de la rive, elle pouvait garder un appui le temps d'entrer ; au milieu, l'eau l'emporterait plus vite vers l'ouverture. Le passage visible n'en révélait pas l'intérieur.
""",
option("Entrer près de la rive en conservant un appui",
       "Alex entra près de la berge et garda un appui jusqu'à l'approche du mur. Quand elle dut s'immerger, le courant la surprit et l'arracha à cet appui.", "appui_berge"),
option("Se laisser porter directement vers l'ouverture",
       "Alex gagna le courant pour rejoindre l'ouverture au plus vite. La puissance de l'eau la surprit ; elle fut entraînée sans pouvoir reprendre appui avant le mur.", "courant_direct"),
values={"chemin": "Alex retrouva le mur en reconnaissant les façades qu'elle avait traversées.",
        "jambe": "Elle s'accroupit au bord de l'eau."},
variants=(
fragment("trajet_prepare", {"all": ["wall_route"]}, chemin="Les façades repérées du haut de la grue la conduisirent au mur sans détour supplémentaire."),
fragment("trajet_neons", {"all": ["new_neons"], "none": ["wall_route"]}, chemin="Elle chercha les néons dont la couleur lui avait révélé la copie du quartier. Elle dut retrouver plusieurs rues avant de rejoindre le mur."),
fragment("genou_apres_reception", {"all": ["genou_aggrave"]}, jambe="Son genou la retint un instant quand elle voulut s'accroupir. Elle déplaça son poids sur l'autre jambe pour atteindre l'eau.")))

passage("La grille", """
Le courant propulsa Alex contre des barreaux rouillés. Le choc fut violent. L'eau la maintint coincée sous le mur, sans possibilité de repartir. {choc}

Retenant sa respiration, elle frappa la barrière. Aucun succès. Une substance gluante effleura ses doigts : du sang coulait de ses mains meurtries. Elle agrippa les barreaux emprisonnés dans la paroi et les agita.

Les vibrations commencèrent à élargir les fissures naturelles. La grille avait du jeu, si peu qu'elle aurait pu croire l'inventer. Ses yeux s'embrumaient. Sa poitrine réclamait de l'air.

{effort}

Il fallait reprendre les secousses avant que ses doigts ne lâchent. Tirer de tout son poids sur les barreaux centraux ferait vibrer l'ensemble ; concentrer le mouvement près d'une fixation attaquerait un point déjà fissuré. Elle ne pouvait plus frapper au hasard. De l'autre côté, l'eau poursuivait son chemin, indifférente à l'obstacle qui la retenait.
""",
option("Faire vibrer toute la grille avec son poids",
       "Alex se cramponna au milieu et tira de tout son poids. Les fissures s'élargirent, une ultime secousse arracha la grille. Le courant l'emporta avec elle ; ses bras n'avaient presque plus de force.", "arrachement_epuisant",
       variants=(result({"all": ["bras_epuises"]}, "Alex tira malgré ses bras épuisés depuis la grue. Une première secousse échoua ; la suivante arracha enfin la grille. Elle fut emportée, à la limite de ce que ses mains pouvaient encore retenir."),)),
option("Concentrer les secousses sur une fixation fissurée",
       "Alex rapprocha ses mains d'une fixation et répéta le mouvement. La fissure s'ouvrit ; la grille céda et fut emportée avec elle. Elle put conserver une prise quelques instants pendant leur sortie.", "arrachement_cible"),
values={"choc": "Elle chercha aussitôt à se dégager.",
        "effort": "Elle rassembla ce qui lui restait de force."},
variants=(
fragment("choc_apres_appui", {"all": ["appui_berge"]}, choc="Arrachée à son dernier appui, elle avait heurté la grille de l'épaule. Elle chercha les barreaux à portée de ses mains."),
fragment("choc_plein_courant", {"all": ["courant_direct"]}, choc="Entraînée sans appui, elle avait reçu le choc de face. Elle dut retrouver ses prises pendant que l'eau lui plaquait les bras contre le métal."),
fragment("bras_grue_sous_eau", {"all": ["bras_epuises"]}, effort="Les bras qui avaient tremblé sur la grue retrouvaient leur épuisement. Elle resserra ses mains meurtries et chercha à faire travailler le métal plutôt qu'à frapper encore."),
fragment("paume_sous_eau", {"all": ["main_eraflee"], "none": ["bras_epuises"]}, effort="L'éraflure du conduit se mêlait aux nouvelles blessures de ses mains. Elle dut modifier sa prise pour ne pas laisser ses doigts glisser.")))

passage("De l'autre côté", """
Emportée au-delà du mur, Alex gesticula désespérément. {courant}

Elle put se cramponner à la racine d'un arbre qui passait à portée. Le courant tirait sur ses jambes. Elle serra le bois, chercha la berge avec un pied et usa de ses dernières forces pour soulever son corps. Un genou trouva la rive, puis l'autre.

{rive}

Elle demeura sur la terre, trempée, les mains meurtries. Derrière elle, l'eau avait franchi ce qu'elle croyait infranchissable. Aucun lit ne l'attendait, aucun repas ne viendrait à la pause suivante. Elle n'avait pas découvert encore ce que cachait ce territoire ; il lui suffisait, pour cet instant, d'être sortie du courant.

Elle était exténuée, mais bien vivante. Une allégresse naissante traversa sa fatigue. Elle ne pouvait effacer ce qu'elle venait de vivre, ni retrouver l'insouciance du toit. Elle pouvait seulement rester accrochée à cette rive nouvelle, respirer et sentir que la nuit avait enfin un autre bord.
""",
values={"courant": "Ses mains cherchèrent quelque chose qui l'arrêterait.",
        "rive": "Elle se hissa enfin hors de l'eau."},
variants=(
fragment("sortie_bras_vides", {"all": ["arrachement_epuisant"]}, courant="L'arrachement de la grille avait vidé ses bras. Elle ne put diriger sa nage ; ses doigts cherchèrent ce qui se présentait dans le flot."),
fragment("sortie_prise_conservee", {"all": ["arrachement_cible"]}, courant="La prise conservée sur le métal l'avait tenue un instant dans le flot. Quand elle le lâcha, elle put tendre une main vers la berge."),
fragment("rive_genou_douloureux", {"all": ["genou_heurte"]}, rive="Le genou heurté dans l'escalier protesta contre la terre. Alex se tira avec les bras jusqu'à dégager sa jambe de l'eau."),
fragment("rive_sans_genou_heurte", {"none": ["genou_heurte"]}, rive="Ses deux jambes purent prendre appui sur la rive. Elle se hissa enfin hors de l'eau.")))

SOURCE_PAGES = [(5, 5), (5, 6), (6, 7), (7, 8), (7, 8), (8, 9), (9, 9), (9, 9),
                (9, 10), (10, 10), (10, 11), (11, 11), (11, 12), (12, 12), (12, 12),
                (13, 13), (13, 13), (14, 14), (14, 15), (15, 15), (15, 16), (16, 16),
                (16, 17), (17, 17), (17, 18), (18, 18), (18, 19), (19, 19)]
for scene, bounds in zip(SCENES, SOURCE_PAGES):
    scene["source_pages"] = list(range(bounds[0], bounds[1] + 1))
for rank in (19, 21):
    SCENES[rank - 1]["image"] = f"images/passeuse/ch1_{rank:02}-v2.png"

BOOK = {"id": "passeuse_ch1", "title": "La petite passeuse d'étoile", "author": "Edouard Bonguet",
        "chapter": 1, "chapter_title": "Le premier pas hors des lignes", "decision_count": 27,
        "choice_question": "Que doit choisir Alex ?", "narrative_person": 3,
        "start": SCENES[0]["id"], "scenes": SCENES,
        "source": {"file": "La petite passeuse d'étoile.pdf", "pages": [5, 19]},
        "revision": "2026-10-10 — reprise directe du PDF, narration au passé et conséquences persistantes",
        "scope": "Premier chapitre uniquement ; arrêt après la racine et la sortie de l'eau."}


def main():
    source = ROOT / BOOK["source"]["file"]
    BOOK["source"]["sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    validate_book(BOOK)
    folder = ROOT / "content/books"
    folder.mkdir(exist_ok=True)
    (folder / "passeuse_ch1.json").write_text(json.dumps(BOOK, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Chapitre relu dans le PDF : {len(SCENES)} passages, {BOOK['decision_count']} décisions.")


if __name__ == "__main__":
    main()
