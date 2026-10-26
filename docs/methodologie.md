# Méthodologie

## Inclusion des candidats

Une seule règle, appliquée à tous les candidats sans exception :

1. Tant que le Conseil constitutionnel n'a pas publié la liste officielle des candidats à l'élection présidentielle de 2027, est inclus tout candidat ayant déclaré publiquement sa candidature.
2. Les mesures sont saisies uniquement depuis les sources officielles du candidat, avec citation exacte et URL. Un candidat déclaré sans programme publié figure avec la mention « programme non publié ».
3. À la publication de la liste officielle, elle remplace la règle 1. Les candidats déclarés qui n'y figurent pas sont archivés : leurs fiches restent consultables avec la mention « absent de la liste officielle », rien n'est supprimé.
4. Un candidat à une primaire est inclus tant qu'il est en lice. S'il est battu, il est archivé comme à la règle 3.
5. Chaque entrée ou sortie de la liste est datée et sourcée (déclaration de candidature, résultat de primaire, retrait, publication officielle).

## Mesures des programmes

- **Candidats retenus** : seule une déclaration de candidature confirmée et datée par une source (primaire de préférence, sinon presse) fait entrer un candidat. Une déclaration non confirmée ou sans date reste en attente, signalée, jamais devinée.
- **Sources** : uniquement les sources officielles du candidat (site de campagne, site du parti, programme publié, communiqué). Ni agrégateur, ni résumé de presse, ni programme d'une élection antérieure. Quand la page officielle n'est plus en ligne, une archive datée de cette page (Wayback Machine) est acceptée, et c'est son adresse qui est citée.
- **Mesure retraites** : un passage qui porte explicitement sur les retraites (âge de départ, durée de cotisation, montant ou indexation des pensions, minimum vieillesse, financement, cumul emploi-retraite, pénibilité, carrières longues, capitalisation, organismes de retraite).
- **Citation** : copie exacte d'un passage contigu, la ou les phrases complètes les plus courtes qui expriment la mesure, jamais une phrase coupée.
- **Vérification** : à chaque chargement, la source est retéléchargée et la citation doit s'y trouver caractère pour caractère, espaces ignorés (la conversion d'une page en texte ajoute ou retire des espaces). Sinon, la mesure est rejetée.
- **Relecture** : candidats et mesures vivent dans des fichiers du dépôt (`donnees/`), relus avant chargement ; toute correction est tracée.

## Recherche des scrutins liés à une mesure

L'intitulé d'un scrutin dit rarement son sujet (« l'amendement n° 7 de M. X après l'article 2 de la proposition de loi... »), et une motion de censure ne nomme pas le texte qu'elle vise. Les explications de vote et le débat qui précède le vote, eux, en parlent. Le **débat** d'un scrutin est le texte du compte rendu intégral depuis le résultat précédent ; s'il fait moins de 3 000 caractères (votes enchaînés sur un même article), il remonte jusqu'à 3 000 caractères. La recherche se fait donc en deux temps, avec la même règle pour toutes les mesures :

1. **Périmètre du thème** : un scrutin relève du thème si son intitulé ou son dossier contient un mot du thème (recherche plein texte en français ; anglais pour le Parlement européen), ou si ses explications de vote, ou son débat, le mentionnent au moins 3 fois, ou si l'amendement voté (dispositif et exposé sommaire, texte court d'un seul sujet) le mentionne au moins une fois. Mots du thème « retraites » : retraite, pension, vieillesse, âge légal, âge de départ ; retirement, old-age. Mentions comptées dans les explications et le débat : mots commençant par « retraite » ou « pension » (« suspension » ne compte pas).
2. **Classement** : dans ce périmètre, les scrutins sont classés par proximité de sens avec la mesure (embeddings du modèle local `qwen3-embedding:0.6b`). Le texte d'un scrutin réunit son intitulé, son dossier, le début de l'amendement voté, le début de l'explication de chaque groupe et le début de son débat. Un scrutin est relié à l'amendement voté par son numéro (sans le préfixe « I- » des lois de finances), examiné en séance, avec un sort daté du jour du scrutin ; seule une correspondance unique est retenue.

Les scrutins retenus ne sont que des candidats : le juge dit ensuite si le vote est lié à la mesure (`hors_sujet` sinon), et les résultats sont relus avant toute publication.

Limite connue : un vote sur un amendement dont la discussion a eu lieu bien avant le scrutin peut échapper au périmètre (exemple : l'amendement n° 2686 du Gouvernement à l'article 45 bis du budget de la Sécurité sociale 2026, alors que le vote sur l'article lui-même est retenu). Le contenu des amendements (dispositif, exposé sommaire) comble ce manque : il est chargé pour la 17e législature ; pour la 16e, l'archive de l'Assemblée est inaccessible (docs/sources.md).

## Anonymisation et test de fuite

Le juge ne voit ni nom de groupe, ni nom de personne, ni nom de parti. Mais le fond d'une mesure ou d'une explication de vote suffit souvent à situer un bord politique, et aucun anonymiseur ne peut l'effacer sans détruire le texte. Viser « pas mieux que le hasard » serait donc un objectif impossible.

Le test compare deux taux de devinette du groupe, sur les mêmes textes du jeu de référence :

- **référence** : textes anonymisés à la main, ce que le fond trahit à lui seul ;
- **anonymiseur** : textes produits par l'anonymiseur automatique.

L'anonymiseur est accepté si son taux ne dépasse pas la référence au-delà d'une marge fixée à l'avance. Sinon, il laisse passer des identifiants et doit être corrigé avant toute autre étape.

Le garde-fou principal contre le biais est le test contrefactuel : on permute les étiquettes `Groupe A`, `Groupe B`... et le verdict ne doit pas changer.

**Anonymiseur** (`src/concordance/pipeline/anonymize.py`) : le groupe jugé devient « Groupe X » (lettre tirée au hasard à chaque jugement), chaque autre groupe cité une autre lettre (un nom porté par plusieurs groupes, comme « LIOT » en 16e et 17e législature, prend la lettre du groupe jugé s'il le désigne), les partis « [parti] », les personnes « [personne] », les termes partisans « [terme partisan] ». Le dictionnaire vient des données : personnes d'AMO30, sénateurs, eurodéputés, candidats, libellés et sigles de tous les groupes, partis des candidats et partis nationaux. S'y ajoutent deux courtes listes publiées dans le code : personnalités absentes des données parlementaires (présidents de la République, Jean-Marie Le Pen) et termes partisans (insoumis, macroniste, lepéniste, anciens noms de partis...). Un nom de famille seul, avec sa majuscule, est masqué partout, sauf s'il est aussi un mot courant du français (liste de mots du paquet `wfrench`, `/usr/share/dict/french`) : « Macron » ou « Le Pen » sont masqués seuls ; « Petit », « Blanc » ou « Le Maire » ne le sont qu'après une civilité ou un mot qui désigne une personne (« loi Duplomb », « famille »). Les mots formés sur un nom masqué le sont aussi (« Macronie », « macronisme », « mélenchoniste »), y compris après un trait d'union (« socialo-macronisme »). Limite connue : un nom de famille qui est aussi un nom de lieu est masqué même quand il désigne le lieu (« Marseille », nom d'un sénateur) ; un nom de personne absent des données (journaliste, économiste) n'est pas masqué. Les noms de groupe courts sont sensibles à la casse (« À Droite » n'est pas « à droite »).

**Protocole du test** (`src/concordance/eval/leakage.py`) : 101 explications de vote de l'Assemblée (17e législature), 8 par groupe tirées au hasard (graine 2027 ; 5 pour les non-inscrits), coupées à environ 1 500 caractères (`eval/fuite_echantillon.jsonl`). Référence (`eval/fuite_reference.jsonl`) : chaque texte relu en entier, seuls les noms de groupes, de partis, de personnes politiques actives depuis 2017 et les termes partisans remplacés ; un contrôle automatique vérifie que rien d'autre n'a changé. Devineur : `qwen3-30b-a3b` (local), qui choisit le groupe parmi les 12 de la législature. Marge fixée avant le test : 5 points. Résultats datés dans `docs/evaluation/fuite.md`.

Limite : sur 101 textes, l'incertitude est d'environ ±8 points ; le test sera refait sur un échantillon plus large avant publication.

## Données de vote

- **Chiffres rapportés tels quels** : pour, contre, abstention, non-votants et, à l'Assemblée, non-votants volontaires, sans regroupement ni interprétation.
- **Position majoritaire** : calculée de la même façon dans les trois chambres, à partir des chiffres : la position qui a le plus de voix entre pour, contre et abstention, vide en cas d'égalité en tête ou sans vote exprimé. Exemple : sur une motion de censure, seuls les votes « pour » sont décomptés ; un groupe qui ne la vote pas n'est ni « pour » ni « contre ». Le champ `positionMajoritaire` de l'Assemblée n'est pas repris : il contredit souvent les chiffres du même groupe (vérifié le 2026-10-26 : 2 789 positions « pour » avec autant ou moins de voix pour que contre ; exemple VTANR5L17V1819, SOC, 2 pour, 16 contre, « pour »).
- **Groupes du Sénat** : libellé actuel de l'export officiel des sénateurs. Un changement de nom en cours de période (« Union Centriste » devenu « Union Centriste et Indépendants ») n'est pas historisé ; le code du groupe, lui, ne change pas.
- **Nature du scrutin** (Assemblée et Sénat, dont l'intitulé commence par « sur ») : déduite du début de l'intitulé, par une règle unique pour tous. Motion de censure ou intitulé commençant par « la motion » : `motion`. « l'amendement », « le sous-amendement », « les amendements » : `amendement`. « l'article » : `article`. « l'ensemble » : `texte_entier`. Sinon, nature non renseignée plutôt que devinée.
- **Parlement européen** : la position d'un groupe est agrégée depuis les votes individuels des eurodéputés (groupe au jour du vote). Nature : vote sur un amendement si un numéro d'amendement est renseigné, `texte_entier` pour le vote principal d'une procédure, sinon non renseignée. Les législatures sont datées depuis les appartenances aux groupes, jamais par une date codée en dur.
- **Délégations nationales françaises** (Parlement européen) : un parti français n'est qu'une délégation au sein d'un groupe européen. Sa position est calculée de la même façon, sur les seuls eurodéputés français rattachés à ce parti au jour du vote. Elle est affichée à côté de celle du groupe européen, chacune nommée comme telle, jamais l'une à la place de l'autre. Les libellés « Sans parti » et « Indépendant » de la source regroupent des élus sans parti : ils sont présentés ainsi, pas comme des partis.
- **Congrès** : les scrutins du Parlement réuni en Congrès ne sont pas rattachés à l'Assemblée seule.

## Explications de vote

- Source : le compte rendu **intégral** (mot à mot), jamais un compte rendu analytique ou résumé.
- **Sénat** : une explication de vote est l'intervention d'un sénateur à qui la présidence donne la parole « pour explication de vote » ou « pour le groupe ... ». Elle réunit tous ses tours de parole jusqu'à ce que la présidence reprenne la parole. Les interruptions d'autres orateurs en sont exclues et remplacées par « […] ». L'orateur doit porter le nom annoncé par la présidence.
- **Assemblée** : sont retenues les interventions des orateurs que le sommaire officiel du compte rendu liste sous une section « Explication(s) de vote », « Motion(s) de censure », « Motion de rejet préalable » ou « Vote sur l'ensemble ». Une séance de motion de censure n'a pas de section « Explications de vote » : les orateurs de la discussion de la motion, listés au sommaire, en tiennent lieu. Les orateurs listés avec une fonction (« ..., ministre », « ..., rapporteur ») sont exclus : ils ne parlent pas au nom d'un groupe.
- L'explication est rattachée au premier scrutin public annoncé ensuite. Si un vote à main levée intervient avant, elle n'est rattachée à aucun scrutin : elle concerne un vote sans décompte par groupe. À l'Assemblée, elle est aussi rattachée aux scrutins suivants tant qu'aucun débat ne reprend entre deux résultats (motions de censure discutées ensemble, projet de loi et loi organique votés à la suite). Le numéro du scrutin n'étant pas lu en séance, il est reconnu par la séance et les chiffres annoncés.
- Le groupe de l'orateur est son appartenance officielle à la date de la séance, pas le groupe cité oralement.
- Le texte est copié tel quel, y compris les indications de séance entre parenthèses (« Applaudissements sur les travées du groupe... »).
- Plusieurs orateurs d'un même groupe peuvent s'exprimer : toutes leurs explications sont conservées.

## Explication de vote absente

Quand aucune explication de vote n'est disponible pour un groupe (pas d'intervention, source non exploitable), la fiche l'indique : « explication non disponible ». Elle n'est jamais remplacée par un résumé, une déduction ou un autre texte.

## Vérification des citations

Chaque citation du juge est vérifiée par correspondance exacte avec le texte qui lui a été envoyé, c'est-à-dire le texte anonymisé. Une citation introuvable entraîne le rejet du jugement. Les vrais noms ne sont rétablis qu'à la publication, à partir de la correspondance entre étiquettes et groupes conservée avec chaque jugement.

## Jugement

Le juge répond à une question : le vote d'un groupe sur un scrutin va-t-il dans le sens d'une mesure (`dans_le_sens`, `contraire`, `ambigu`, `hors_sujet`) ? La consigne en cours est `prompts/judge_v2.md` (`judge_v1.md` reste dans le dépôt avec son évaluation), le code `src/concordance/pipeline/judge.py`.

- **Paires jugées** : pour chaque mesure, les 5 scrutins les mieux classés par la recherche ; pour chacun, chaque groupe dont la position majoritaire est « pour » ou « contre ». Au Parlement européen, les délégations nationales françaises. Quand la position majoritaire est l'abstention, le non-vote ou un partage à égalité, aucun juge n'est appelé : la fiche décrit les chiffres sans interprétation.
- **Ce que voit le juge** : la mesure (citation exacte), le scrutin (chambre, date, intitulé, nature, objet, dossier, résultat et, s'il est relié, le dispositif et l'exposé sommaire de l'amendement voté, 3 000 caractères au plus chacun), les chiffres du groupe et son explication de vote si elle existe. Tout passe par l'anonymiseur. Avant, apostrophes typographiques et espaces insécables sont remplacés par leurs équivalents simples, que les modèles recopient ; ce texte est celui envoyé et conservé, et c'est contre lui que les citations sont vérifiées : chaque extrait doit y figurer mot pour mot. La section que le juge indique (mesure, scrutin, explication) n'est pas contrôlée ; la fiche publie les textes d'origine, jamais les extraits du juge.
- **Étiquettes** : tirées au hasard pour chaque paire et chaque juge (tirage reproductible à partir de la paire et du nom du juge) et conservées avec le jugement.
- **Effet du texte, puis relation** (`judge_v2`) : le juge dit d'abord ce que changeait le texte voté par rapport à la mesure (`rapproche`, `eloigne`, `ambigu`, `hors_sujet`), puis la relation, qui doit en découler avec la position du groupe : voter pour un texte qui rapproche, ou contre un texte qui éloigne, va dans le sens de la mesure ; un groupe partagé (aucune position au-dessus de la moitié de ses votants) donne `ambigu`. Un article ou un amendement dont le contenu n'est pas fourni n'emprunte pas le sens du titre de son texte : `ambigu`. Avec `judge_v1`, les juges ne répondaient jamais `ambigu` et se trompaient sur les doubles négations (voter contre un texte qui éloigne de la mesure) : `docs/evaluation/juges_judge_v1.md`.
- **Contrôles** : sortie JSON validée (valeurs permises, au moins une citation, confiance entre 0 et 1, justification de 80 mots au plus), citations présentes mot pour mot, relation conforme à l'effet du texte et au vote. Sinon, le jugement est rejeté ; il est conservé avec son motif.
- **Deux juges** : `qwen3-30b-a3b` (famille Qwen, Alibaba) et `llama3.2` (3 milliards de paramètres, famille Llama, Meta), servis en local par llama.cpp. Ce sont les deux seules familles de modèles présentes sur la machine. Le second juge est trop petit : sur le jeu de référence, la plupart de ses réponses sont rejetées (`docs/evaluation/juges_judge_v2.md`) ; il faut en installer un plus solide, d'une autre famille que Qwen.
- **Verdict publié** : seulement si les deux juges valides donnent la même relation, ou après relecture humaine (table `reviews`). Sinon, la paire attend une relecture : désaccord, jugement rejeté ou manquant. Jamais de vote à la majorité automatique.

## Jeu de référence

`eval/gold_retraites.csv` : 120 paires tirées parmi les paires à juger des 2 scrutins les mieux classés de chaque mesure, tour à tour dans chaque groupe pour qu'aucun ne soit sur-représenté (graine 0). Annotation provisoire, faite à l'aveugle sur le texte anonymisé avec la fin du débat qui précède le vote : deux annotateurs indépendants (Claude), un arbitrage en cas de désaccord, colonne `annotation` à `claude-provisoire`. Elle doit être relue par un humain avant de servir de référence publiée. Contrôle de cohérence : pour une même mesure et un même scrutin, le sens du texte voté est le même pour tous les groupes ; les 9 ensembles annotés de façon incohérente d'un lot à l'autre ont été tranchés une seule fois (deux avis indépendants, arbitrage si besoin), et la relation de chaque groupe en a été déduite (14 paires modifiées). Limite : 88 % des paires sont `ambigu` ou `hors_sujet`, surtout parce que le contenu des amendements de la 16e législature et du Sénat manque ; l'accord sur `dans_le_sens` et `contraire` repose sur peu de paires. Code : `src/concordance/eval/run.py` (tirage, jugement des paires de référence avec `--juger`, mesures d'accord ; rapport `docs/evaluation/juges_<consigne>.md`), `src/concordance/eval/bias.py` (répartition par groupe, test contrefactuel).

**Publication** : tant que l'évaluation ne montre pas un accord suffisant avec la référence relue, les fiches restent des prototypes et le disent en tête de page. Seuil d'accord pour publier : TODO: vérifier (à fixer avec John, avant de lire les résultats d'une nouvelle consigne).

## Présentation

- Le rendu doit être lisible par quelqu'un qui ne suit pas la politique : une phrase simple, les chiffres complets, la source officielle à un clic, chaque terme technique expliqué (amendement, motion de censure, commission mixte paritaire...).
- Toute l'information est montrée, jamais une partie choisie.
- Chaque groupe est désigné par un badge identique pour tous : sigle et nom complet, sans logo ni couleur. Un logo est un élément de communication, protégé et chargé d'émotion ; une couleur oriente la lecture avant les chiffres.
- Au Parlement européen, les noms de groupes et les intitulés des scrutins sont repris tels quels de la source, en anglais, avec la mention « intitulé d'origine, en anglais ». Aucune traduction n'est ajoutée à une donnée.
- Lien candidat-groupe : une absence de donnée n'est jamais présentée comme une absence de groupe. La fiche distingue trois cas : homonymes, candidat absent des données, candidat sans groupe à la date du scrutin.
- Non-votants volontaires (Assemblée) : le chiffre est rapporté tel quel et la fiche note qu'il est égal aux abstentions dans la source (voir docs/sources.md).

## Amendements

Prototype : amendements déposés à l'Assemblée sur la réforme des retraites de 2023.

- Mêmes mesures pour tous les groupes, calculées par une règle unique et publiée.
- Uniquement des faits mesurés : aucune qualification de l'intention (« obstruction », « travail sérieux »...). Le lecteur juge.
- Aucun classement : un tableau identique pour chaque groupe, dans un ordre neutre.
- Mesures prévues : nombre d'amendements déposés, sort (adopté, rejeté, tombé, non soutenu, retiré, non examiné), amendements identiques ou en série, ampleur de la modification proposée. Définitions précises : `TODO: vérifier` sur les données, à valider avant publication.
