# Méthodologie

## Inclusion des candidats

Une seule règle, appliquée à tous les candidats sans exception :

1. Tant que le Conseil constitutionnel n'a pas publié la liste officielle des candidats à l'élection présidentielle de 2027, est inclus tout candidat ayant déclaré publiquement sa candidature.
2. Les mesures sont saisies uniquement depuis les sources officielles du candidat, avec citation exacte et URL. Un candidat déclaré sans programme publié figure avec la mention « programme non publié ».
3. À la publication de la liste officielle, elle remplace la règle 1. Les candidats déclarés qui n'y figurent pas sont archivés : leurs fiches restent consultables avec la mention « absent de la liste officielle », rien n'est supprimé.
4. Un candidat à une primaire est inclus tant qu'il est en lice. S'il est battu, il est archivé comme à la règle 3.
5. Chaque entrée ou sortie de la liste est datée et sourcée (déclaration de candidature, résultat de primaire, retrait, publication officielle).

## Anonymisation et test de fuite

Le juge ne voit ni nom de groupe, ni nom de personne, ni nom de parti. Mais le fond d'une mesure ou d'une explication de vote suffit souvent à situer un bord politique, et aucun anonymiseur ne peut l'effacer sans détruire le texte. Viser « pas mieux que le hasard » serait donc un objectif impossible.

Le test compare deux taux de devinette du groupe, sur les mêmes textes du jeu de référence :

- **référence** : textes anonymisés à la main, ce que le fond trahit à lui seul ;
- **anonymiseur** : textes produits par l'anonymiseur automatique.

L'anonymiseur est accepté si son taux ne dépasse pas la référence au-delà d'une marge fixée à l'avance. Sinon, il laisse passer des identifiants et doit être corrigé avant toute autre étape.

Le garde-fou principal contre le biais est le test contrefactuel : on permute les étiquettes `Groupe A`, `Groupe B`... et le verdict ne doit pas changer.

## Données de vote

- **Chiffres rapportés tels quels** : pour, contre, abstention, non-votants et, à l'Assemblée, non-votants volontaires, sans regroupement ni interprétation.
- **Position majoritaire** : reprise de la source, sauf quand le groupe n'a exprimé aucun vote (ni pour, ni contre, ni abstention). Elle reste alors vide. Exemple : sur une motion de censure, seuls les votes « pour » sont décomptés ; un groupe qui ne la vote pas n'est ni « pour » ni « contre ».
- **Nature du scrutin** (Assemblée) : déduite du début de l'intitulé, par une règle unique pour tous. Motion de censure ou intitulé commençant par « la motion » : `motion`. « l'amendement », « le sous-amendement », « les amendements » : `amendement`. « l'article » : `article`. « l'ensemble » : `texte_entier`. Sinon, nature non renseignée plutôt que devinée.
- **Congrès** : les scrutins du Parlement réuni en Congrès ne sont pas rattachés à l'Assemblée seule.

## Explication de vote absente

Quand aucune explication de vote n'est disponible pour un groupe (pas d'intervention, source non exploitable), la fiche l'indique : « explication non disponible ». Elle n'est jamais remplacée par un résumé, une déduction ou un autre texte.

## Vérification des citations

Chaque citation du juge est vérifiée par correspondance exacte avec le texte qui lui a été envoyé, c'est-à-dire le texte anonymisé. Une citation introuvable entraîne le rejet du jugement. Les vrais noms ne sont rétablis qu'à la publication, à partir de la correspondance entre étiquettes et groupes conservée avec chaque jugement.

## Présentation

- Le rendu doit être lisible par quelqu'un qui ne suit pas la politique : une phrase simple, les chiffres complets, la source officielle à un clic, chaque terme technique expliqué (amendement, motion de censure, commission mixte paritaire...).
- Toute l'information est montrée, jamais une partie choisie.
- Chaque groupe est désigné par un badge identique pour tous : sigle et nom complet, sans logo ni couleur. Un logo est un élément de communication, protégé et chargé d'émotion ; une couleur oriente la lecture avant les chiffres.

## Amendements

Prototype : amendements déposés à l'Assemblée sur la réforme des retraites de 2023.

- Mêmes mesures pour tous les groupes, calculées par une règle unique et publiée.
- Uniquement des faits mesurés : aucune qualification de l'intention (« obstruction », « travail sérieux »...). Le lecteur juge.
- Aucun classement : un tableau identique pour chaque groupe, dans un ordre neutre.
- Mesures prévues : nombre d'amendements déposés, sort (adopté, rejeté, tombé, non soutenu, retiré, non examiné), amendements identiques ou en série, ampleur de la modification proposée. Définitions précises : `TODO: vérifier` sur les données, à valider avant publication.
