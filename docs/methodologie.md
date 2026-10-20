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

## Vérification des citations

Chaque citation du juge est vérifiée par correspondance exacte avec le texte qui lui a été envoyé, c'est-à-dire le texte anonymisé. Une citation introuvable entraîne le rejet du jugement. Les vrais noms ne sont rétablis qu'à la publication, à partir de la correspondance entre étiquettes et groupes conservée avec chaque jugement.
