# Sources de données

Vérifié le 2026-10-20. Tout ce qui n'a pas pu être confirmé sur la source est marqué `TODO: vérifier`.

## Assemblée nationale

- Licence : « Licence Ouverte / Open Licence », https://data.assemblee-nationale.fr/licence-ouverte-open-licence. Version : `TODO: vérifier`.
- Disponibilité : data.assemblee-nationale.fr et www.assemblee-nationale.fr répondent souvent 503 (le 2026-10-20, toute la journée pour certaines pages). Les archives zip se téléchargent. L'ingestion doit réessayer avec un délai croissant.

### Scrutins

| Législature | URL | Taille | Last-Modified |
|---|---|---|---|
| 17 | https://data.assemblee-nationale.fr/static/openData/repository/17/loi/scrutins/Scrutins.json.zip | 27,6 Mo | 2026-10-20 |
| 16 | https://data.assemblee-nationale.fr/static/openData/repository/16/loi/scrutins/Scrutins.json.zip | 10,1 Mo | 2024-06-28 (close) |

- Format : un JSON par scrutin, `json/VTANR5L{législature}V{numéro}.json`, racine `scrutin`. Les nombres sont encodés en chaînes. Version XML : `TODO: vérifier` (503).
- Champs : `uid`, `numero`, `legislature`, `dateScrutin`, `typeVote.codeTypeVote` / `libelleTypeVote`, `sort.code`, `titre`, `objet.libelle`, `demandeur.texte`, `syntheseVote.decompte` (`pour`, `contre`, `abstentions`, `nonVotants`), `syntheseVote.nbrSuffragesRequis`.
- Positions par groupe : `ventilationVotes.organe.groupes.groupe[]` avec `organeRef`, `nombreMembresGroupe`, `vote.positionMajoritaire`, `vote.decompteVoix` (`pour`, `contre`, `abstentions`, `nonVotants`, `nonVotantsVolontaires`), `vote.decompteNominatif` (`votant[]` : `acteurRef`, `mandatRef`, `causePositionVote`, `parDelegation`).
- Exemple lu : `VTANR5L16V1240` et `VTANR5L16V1241`, motions de censure du 2023-03-20 sur la réforme des retraites, rejetées (278 et 94 voix pour, 287 requises).
- URL publique d'une page de scrutin : `TODO: vérifier` (site en 503).

### Acteurs et organes

- AMO10 (députés et organes actifs) : https://data.assemblee-nationale.fr/static/openData/repository/17/amo/deputes_actifs_mandats_actifs_organes/AMO10_deputes_actifs_mandats_actifs_organes.json.zip (4,9 Mo).
- AMO30 (historique de toutes les législatures) : https://data.assemblee-nationale.fr/static/openData/repository/17/amo/tous_acteurs_mandats_organes_xi_legislature/AMO30_tous_acteurs_tous_mandats_tous_organes_historique.json.zip (13,7 Mo).
- Champs d'un organe : `uid`, `codeType` (`GP` pour un groupe politique), `libelle`, `libelleAbrev`, `viMoDe.dateDebut` / `dateFin`, `legislature`.
- Jointure vérifiée : `organeRef` d'un groupe dans un scrutin = `uid` de l'organe dans AMO. Uid et libellés changent d'une législature à l'autre.

### Amendements et comptes rendus

- Amendements (exposé sommaire) : `TODO: vérifier` (503).
- Comptes rendus de séance, source des explications de vote : `TODO: vérifier` (503). Source indispensable au projet.

## Sénat

- Licence : licence ouverte reprenant celle de data.gouv.fr, https://data.senat.fr/licence/ (PDF Etalab 2.0 : https://www.etalab.gouv.fr/wp-content/uploads/2017/04/ETALAB-Licence-Ouverte-v2.0.pdf).

### Scrutins : pas d'open data

- Uniquement en HTML. Index par session : `https://www.senat.fr/scrutin-public/scr{AAAA}.html` (2006 à 2026). Page d'un scrutin : `https://www.senat.fr/scrutin-public/{AAAA}/scr{AAAA}-{n}.html`, `AAAA` = année de début de session. Motif observé sur les pages, non documenté.
- Contenu : date, sort, décompte, « Analyse par groupes politiques » (effectif, pour, contre, abstention, non-votants par groupe), listes nominatives (noms, sans matricule). Aucune explication de vote.
- Exemples lus : scrutin 249 du 2023-03-11 (articles 9 à 20 et ensemble du PLFRSS 2023) https://www.senat.fr/scrutin-public/2022/scr2022-249.html, scrutin 251 du 2023-03-16 (texte de la CMP) https://www.senat.fr/scrutin-public/2022/scr2022-251.html. Scrutins 240 à 248 : articles et amendements du même texte.
- Fréquence de mise à jour : `TODO: vérifier`.

### Sénateurs et groupes

- Page : https://data.senat.fr/les-senateurs/ ; export complet https://data.senat.fr/data/senateurs/export_sens.zip (8,5 Mo).
- `ODSEN_HISTOGROUPES.csv` : `Matricule`, `Code du groupe politique`, `Nom court du groupe politique`, `Date de début d'appartenance`, `Date de fin d'appartenance`, etc. `ODSEN_GENERAL.csv` : `Matricule`, `Groupe politique`, etc. URL exacte des CSV : `TODO: vérifier`.
- Format : ISO-8859-1, CRLF, virgule, lignes `%` avant l'en-tête.
- Jointure avec les pages de scrutin : par libellé de groupe et nom de sénateur (pas de matricule sur les pages). Libellés variables (« Union Centriste » en 2023, « Union Centriste et Indépendants » en 2026). `TODO: vérifier` la fiabilité de cette jointure.

### Comptes rendus

- Page : https://data.senat.fr/la-base-comptes-rendus/ (depuis 2003).
- `debats.zip` (33,8 Mo, dump PostgreSQL) et `cri.zip` (545 Mo, un XML par séance `cri/dAAAAMMJJ.xml`, intervenants avec `mat` et `nom`, sans groupe). ISO-8859-1.
- Explications de vote : non localisées dans l'échantillon lu (2012). `TODO: vérifier` sur une séance récente, et la jointure `mat` / `Matricule`.

### Dossiers législatifs et amendements

- Dosleg : https://data.senat.fr/dosleg/ (`dosleg.zip` 16 Mo PostgreSQL, `dossiers-legislatifs.csv`). Pas de champ scrutin.
- Ameli : https://data.senat.fr/ameli/ (`ameli.zip` 154 Mo PostgreSQL).

## Parlement européen

### HowTheyVote.eu

- Dépôt : https://github.com/HowTheyVote/data. Une release par semaine (le vendredi), dernière le 2026-10-17. Fichiers : `https://github.com/HowTheyVote/data/releases/download/{tag}/{fichier}.csv.gz`.
- Couverture : votes du 2019-07-15 au 2026-10-08 (9e et 10e législatures).
- Fichiers utiles : `votes` (`id`, `timestamp`, `display_title`, `procedure_reference`, `procedure_title`, `count_for`, `count_against`, `count_abstention`, `count_did_not_vote`, `result`...), `member_votes` (104 Mo : `vote_id`, `member_id`, `position` = `FOR` / `AGAINST` / `ABSTENTION` / `DID_NOT_VOTE`, `group_code`, `national_party_id`...), `members`, `groups`, `group_memberships` (avec dates), `national_parties`, `national_party_memberships` (avec dates).
- Pas de table par groupe : la position d'un groupe s'agrège depuis `member_votes.group_code` (groupe au jour du vote).
- Format déclaré expérimental par HowTheyVote, il peut changer.
- Licence : ODbL 1.0 pour la base, DbCL 1.0 pour le contenu (https://howtheyvote.eu/data). Pas de fichier de licence dans le dépôt. Attribution obligatoire et **partage à l'identique** : toute base dérivée publiée doit être sous ODbL. Exceptions : photos et résumés de votes.

### Portail open data du PE

- API v2 en JSON-LD, par exemple https://data.europarl.europa.eu/api/v2/meps. Point d'accès des votes : `TODO: vérifier`. Licence : `TODO: vérifier`.

### Explications de vote

- `TODO: vérifier` : lieu de publication, format, lien avec un vote.

## Programmes et candidatures

- 2027etmoi (source collaborative, non officielle), organisation https://www.data.gouv.fr/organizations/2027etmoi/ :
  - candidatures avec statut sourcé : https://www.data.gouv.fr/datasets/candidatures-a-lelection-presidentielle-2027-statuts-sources (JSON, 51 personnalités, Licence Ouverte 2.0, mis à jour le 2026-10-14) ;
  - votes des candidats parlementaires : https://www.data.gouv.fr/datasets/votes-au-parlement-des-candidats-a-lelection-presidentielle-2027 (JSON, 188 scrutins, Licence Ouverte 2.0) ;
  - programmes : uniquement dans le dépôt https://github.com/2027etmoi/2027etmoi (`data/programmes/`, contenu `TODO: vérifier`), pas sur data.gouv.fr. Code sans licence libre.
- Usage : point de départ pour repérer candidatures et programmes. Chaque candidature et chaque mesure est recoupée avec sa source officielle (règle 2 de `methodologie.md`).
- Liste officielle : publiée par le Conseil constitutionnel après la clôture des parrainages, attendue en mars 2027 d'après la presse. `TODO: vérifier` sur le site du Conseil.

### Sources officielles citées par le README

| URL | HTTP | Constat |
|---|---|---|
| melenchon2027.fr/programme2025/livre/ | 200 | Livre programme en 18 chapitres, chapitre retraites `TODO: vérifier` |
| edouardphilippe.fr | 200 | Pages « priorités », mesures retraites `TODO: vérifier` |
| republicains.fr/qrtravail | 200 | Page « Travail », pas de mesure retraites dans le texte lu |
| rassemblementnational.fr/22-mesures | 200 | Programme de **2022**, pas de 2027 |

## Contrôle croisé

- Datan (https://www.data.gouv.fr/organizations/datan, Licence Ouverte) : députés et groupes de l'Assemblée uniquement. **Aucune position de groupe par scrutin publiée**, pas de Sénat. Inutilisable pour contrôler les positions de groupes.
