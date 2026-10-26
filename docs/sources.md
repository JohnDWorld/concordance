# Sources de données

Vérifié le 2026-10-20. Tout ce qui n'a pas pu être confirmé sur la source est marqué `TODO: vérifier`.

## Assemblée nationale

- Licence : « Licence Ouverte / Open Licence » version 1.0 (Etalab), https://data.assemblee-nationale.fr/licence-ouverte-open-licence, texte : https://data.assemblee-nationale.fr/content/download/28755/file/Licence_Ouverte.pdf.
- Disponibilité : data.assemblee-nationale.fr et www.assemblee-nationale.fr ont répondu 503 une grande partie de la journée, puis 200 le soir. Les archives zip sous `/static/openData/` se téléchargent même pendant les 503. L'ingestion doit réessayer avec un délai croissant.

### Scrutins

| Législature | URL | Taille | Last-Modified |
|---|---|---|---|
| 17 | https://data.assemblee-nationale.fr/static/openData/repository/17/loi/scrutins/Scrutins.json.zip | 27,6 Mo | 2026-10-20 |
| 16 | https://data.assemblee-nationale.fr/static/openData/repository/16/loi/scrutins/Scrutins.json.zip | 10,1 Mo | 2024-06-28 (close) |

- Format : un JSON par scrutin, `json/VTANR5L{législature}V{numéro}.json`, racine `scrutin`. Les nombres sont encodés en chaînes. Version XML : `TODO: vérifier`.
- Champs : `uid`, `numero`, `legislature`, `seanceRef`, `dateScrutin`, `typeVote.codeTypeVote` / `libelleTypeVote`, `sort.code`, `titre`, `objet.libelle`, `demandeur.texte`, `syntheseVote.decompte` (`pour`, `contre`, `abstentions`, `nonVotants`), `syntheseVote.nbrSuffragesRequis`.
- Positions par groupe : `ventilationVotes.organe.groupes.groupe[]` avec `organeRef`, `nombreMembresGroupe`, `vote.positionMajoritaire`, `vote.decompteVoix` (`pour`, `contre`, `abstentions`, `nonVotants`, `nonVotantsVolontaires`), `vote.decompteNominatif` (`votant[]` : `acteurRef`, `mandatRef`, `causePositionVote`, `parDelegation`).
- Page publique : `https://www.assemblee-nationale.fr/dyn/{législature}/scrutins/{numéro}`, par exemple https://www.assemblee-nationale.fr/dyn/16/scrutins/1240.
- Exemple lu : `VTANR5L16V1240` et `VTANR5L16V1241`, motions de censure du 2023-03-20 sur la réforme des retraites, rejetées (278 et 94 voix pour, 287 requises).
- `nonVotantsVolontaires` (`decompteVoix`) : dans les fichiers sources, ce champ est égal à `abstentions` pour chaque groupe et chaque scrutin (vérifié le 2026-10-26 : 45 175 lignes de la 16e législature, 106 872 de la 17e). Le chargement est fidèle à la source ; la fiche le signale. Sa définition n'est pas confirmée : TODO: vérifier (documentation de l'open data ou question à l'Assemblée).
- `positionMajoritaire` est renseigné même pour un groupe qui n'a exprimé aucun vote (motion de censure : « pour » à 0 voix). Il n'est pas repris dans ce cas (voir `methodologie.md`).
- Défaut de la source : 146 positions de la 17e législature ont `organeRef` = `PO0` (groupe non identifié), dans 14 scrutins : n° 489 à 501 (2024-12-02, tous les groupes), 1302 et 6256 (un groupe chacun). Ces positions ne sont pas chargées, les scrutins le sont. Le groupe pourrait être retrouvé via les votants (`decompteNominatif`) : `TODO: vérifier` si nécessaire.
- Le scrutin du Congrès (16e, n° 1, 2024-03-04, `codeTypeVote` = `SSG`) contient les groupes du Sénat : non chargé.
- Le serveur peut couper un téléchargement sans erreur (fichier AMO30 reçu à 2 Mo sur 13,7 le 2026-10-21) : la taille reçue est comparée à `Content-Length`, et le téléchargement est relancé en cas d'écart.

### Acteurs et organes

- AMO10 (députés et organes actifs) : https://data.assemblee-nationale.fr/static/openData/repository/17/amo/deputes_actifs_mandats_actifs_organes/AMO10_deputes_actifs_mandats_actifs_organes.json.zip (4,9 Mo).
- AMO30 (historique de toutes les législatures) : https://data.assemblee-nationale.fr/static/openData/repository/17/amo/tous_acteurs_mandats_organes_xi_legislature/AMO30_tous_acteurs_tous_mandats_tous_organes_historique.json.zip (13,7 Mo).
- Champs d'un organe : `uid`, `codeType` (`GP` pour un groupe politique), `libelle`, `libelleAbrev`, `viMoDe.dateDebut` / `dateFin`, `legislature`.
- Jointure vérifiée : `organeRef` d'un groupe dans un scrutin = `uid` de l'organe dans AMO. Uid et libellés changent d'une législature à l'autre.
- Lien candidat-groupe (fiches) : dans AMO30, Jean-Luc Mélenchon (PA2150) n'a de mandat de groupe qu'à la 15e législature (se termine le 2022-06-21), alors que ses scrutins liés datent de 2023 à 2025. La fiche ne conclut donc pas à une absence de groupe : elle écrit que les données ne font pas apparaître de groupe. TODO: vérifier sur assemblee-nationale.fr la composition de la 17e législature. Même contrôle pour les autres candidats sans lien établi (Lisnard, Cazeneuve, Philippot, Branco, Arthaud). TODO: vérifier.

### Comptes rendus de séance (explications de vote)

- Page : https://data.assemblee-nationale.fr/travaux-parlementaires/debats. Fichiers (format XML « Syceron ») :
  - 17 : https://data.assemblee-nationale.fr/static/openData/repository/17/vp/syceronbrut/syseron.xml.zip (58,6 Mo, 631 séances)
  - 16 : https://data.assemblee-nationale.fr/static/openData/repository/16/vp/syceronbrut/syseron.xml.zip (57,6 Mo, 605 séances)
  - Piège : la page affiche le chemin `/VP/` en majuscules, qui renvoie 404. Seul `/vp/` fonctionne.
- Structure : `xml/compteRendu/CRSANR5L{lég}S{année}O1N{n}.xml`, racine `compteRendu` avec `uid`, `seanceRef`, `metadonnees` (`dateSeance`, `numSeance`, `legislature`), `contenu`. Chaque `paragraphe` porte `id_syceron`, `id_acteur` (PA...), `id_mandat` (PM...), `ordre_absolu_seance`, `roledebat`. Trier par `ordre_absolu_seance` (`id_syceron` n'est pas chronologique).
- Lien avec les scrutins : `seanceRef` du compte rendu = `seanceRef` des scrutins de la séance (vérifié sur 1240 et 1241). Le scrutin précis dans la séance se déduit du titre et de l'ordre.
- Explications de vote : aucune balise dédiée dans le corps. Le **sommaire** en tête du fichier (`titreStruct` puis `para id_syceron="..."`) liste, par section, les orateurs et l'ancre de leur intervention, avec leur groupe entre parenthèses dans certaines séances (« M. Jean-Claude Raux (Écolo-NUPES) »). Les entrées vides sont auto-fermantes (`<para .../>`).
- Chaque intervention extraite est encadrée par `interExtraction` (aussi utilisée pour les questions au Gouvernement). Paragraphes : `code_grammaire` = `PAROLE_GENERIQUE` (discours) ou `INTERRUPTION_1_10` (interruption).
- Résultat d'un scrutin : « Voici le résultat du scrutin : ... Pour l'adoption 278 » (ou « Pour l'adoption : 145 », « Pour l'approbation 372 Contre 99 »), **sans numéro de scrutin**. Rattachement par la séance (`seanceRef`) et les chiffres (`syntheseVote.decompte`).
- Contrôle : le groupe attribué (mandat officiel à la date, AMO30) concorde avec le sigle affiché par le compte rendu dans 100 % des 3 206 cas où il est affiché (écarts d'écriture seulement : « LFI-NUPES » / « LFI - NUPES »).
- Groupe de l'orateur : absent du compte rendu. À dériver soit de `vote.decompteNominatif` du scrutin (l'`acteurRef` y figure dans son groupe), soit de `id_mandat` via AMO. `TODO: vérifier` les deux jointures.
- Ancre publique : `id_syceron` = ancre HTML. `https://www.assemblee-nationale.fr/dyn/16/comptes-rendus/seance/CRSANR5L16S2023O1N182` redirige vers l'URL lisible de la séance.
- Exemple vérifié (texte identique dans le XML et la page publique) : « C’est pourquoi les députés du groupe Horizons et apparentés ne voteront pas en faveur des motions de censure. », https://www.assemblee-nationale.fr/dyn/16/comptes-rendus/seance/session-ordinaire-de-2022-2023/premiere-seance-du-lundi-20-mars-2023#3056182.

### Amendements

- Page : https://data.assemblee-nationale.fr/travaux-parlementaires/amendements/tous-les-amendements.
- 17 : https://data.assemblee-nationale.fr/static/openData/repository/17/loi/amendements_div_legis/Amendements.json.zip (344 Mo, 141 194 JSON). 16 : même chemin avec `16`.
- Champs : `uid`, `identification.numeroLong`, `signataires.auteur.acteurRef`, `signataires.auteur.groupePolitiqueRef`, `corps.contenuAuteur.exposeSommaire` (HTML), `corps.contenuAuteur.dispositif`, `cycleDeVie.dateDepot`, `cycleDeVie.sort`, `cycleDeVie.dateSort`, `seanceDiscussionRef` (souvent vide).
- Lien avec les scrutins : aucun champ direct. Le scrutin donne le numéro sans préfixe (« l'amendement n° 921 »), l'amendement le donne avec (`numeroLong` = « I-921 » pour une loi de finances, « CE198 » en commission). Rattachement retenu : même législature, examen en séance (`prefixeOrganeExamen` = « AN »), même numéro hors préfixe, `cycleDeVie.dateSort` le jour du scrutin, correspondance unique. Vérifié sur l'amendement n° 2686 du Gouvernement (article 45 bis du PLFSS 2026, scrutin du 2025-11-12).
- 17e législature : archive téléchargée le 2026-10-25 (346,8 Mo, 142 200 amendements).
- 16e législature : archive inaccessible depuis le 2026-10-21. Le téléchargement s'arrête toujours avant la fin (au mieux 70,6 Mo sur 363), y compris dans un navigateur ; au-delà, le serveur répond 206 sans contenu. Signalé à opendata@assemblee-nationale.fr. Le fichier partiel est conservé avec son ETag : le téléchargement reprendra là où il s'est arrêté.

## Sénat

- Licence : licence ouverte reprenant celle de data.gouv.fr, https://data.senat.fr/licence/ (PDF Etalab 2.0 : https://www.etalab.gouv.fr/wp-content/uploads/2017/04/ETALAB-Licence-Ouverte-v2.0.pdf).

### Scrutins : pas d'open data

- Uniquement en HTML. Index par session : `https://www.senat.fr/scrutin-public/scr{AAAA}.html` (2006 à 2026). Page d'un scrutin : `https://www.senat.fr/scrutin-public/{AAAA}/scr{AAAA}-{n}.html`, `AAAA` = année de début de session. Motif observé sur les pages, non documenté.
- Contenu : date, sort, décompte, « Analyse par groupes politiques » (effectif, pour, contre, abstention, non-votants par groupe), listes nominatives (noms, sans matricule). Aucune explication de vote.
- Exemples lus : scrutin 249 du 2023-03-11 (articles 9 à 20 et ensemble du PLFRSS 2023) https://www.senat.fr/scrutin-public/2022/scr2022-249.html, scrutin 251 du 2023-03-16 (texte de la CMP) https://www.senat.fr/scrutin-public/2022/scr2022-251.html. Scrutins 240 à 248 : articles et amendements du même texte.
- Fréquence de mise à jour : `TODO: vérifier`.
- Décision : les pages de scrutin sont récupérées et analysées. Une copie brute de chaque page est conservée dans `data/raw/` avec sa date et son URL.
- Gabarit vérifié identique d'octobre 2022 à octobre 2026 : titre `h1.page-title` (« Scrutin n°251 - séance du 16 mars 2023 »), intitulé `p.page-lead`, résultat (« Le Sénat a adopté / n'a pas adopté »), totaux, puis un bloc par groupe dont l'identifiant HTML porte le code du groupe (`accordion-scrutin-UMP`), le même que `grppolcod` dans l'export des sénateurs. Jointure par code, jamais par libellé.
- Contrôle à chaque page : la somme des « pour » et des « contre » des groupes doit égaler les totaux de la page, sinon la page n'est pas chargée et elle est signalée.
- `robots.txt` de senat.fr : `/scrutin-public/` et `/cra/` non interdits. Une page par seconde.

### Sénateurs et groupes

- Page : https://data.senat.fr/les-senateurs/ ; export complet https://data.senat.fr/data/senateurs/export_sens.zip (8,5 Mo, un dump PostgreSQL `export_sens.sql` en UTF-8, 95 tables). Table des groupes : `grppol` (`grppolcod` code, `grppolliccou` sigle, `grppollibcou` libellé, `grppoldatcre`, `grppoldatfin` ; 1899-12-31 = date inconnue). Appartenances : `memgrppol` (`senmat`, `grppolcod`, `memgrppoldatdeb`, `memgrppoldatfin`).
- https://data.senat.fr/data/senateurs/ODSEN_HISTOGROUPES.csv : `Matricule`, `Id appartenance`, `Nom`, `Code du groupe politique`, `Nom court du groupe politique`, `Date de début d'appartenance`, `Date de fin d'appartenance`, `Nom court fonction`. Plusieurs lignes par sénateur (une par période et par fonction) : filtrer par date. `ODSEN_GENERAL.csv` : `Matricule`, `Groupe politique`, etc.
- Format : ISO-8859-1, CRLF, virgule, lignes `%` avant l'en-tête.
- Codes de groupe anciens (`UMP` pour le groupe Les Républicains) et libellés variables (« Union Centriste » en 2023, « Union Centriste et Indépendants » en 2026).

### Comptes rendus (explications de vote)

- Page : https://data.senat.fr/la-base-comptes-rendus/ (depuis 2003). Fichiers :
  - https://data.senat.fr/data/debats/cri.zip (545 Mo, un XML par séance `cri/dAAAAMMJJ.xml`) ;
  - `debats.zip` (33,8 Mo, dump PostgreSQL).
- XML : namespace `http://senat.fr/schemas/thb/cri`, ISO-8859-1, **mal formé** (un parseur XML strict échoue, il faut un parseur tolérant). Intervenants : `cri:intervenant` avec `mat`, `nom`, `parid`, sans groupe.
- Explications de vote : `<divers type="2" libelle="Explications de vote sur l'ensemble">`. Le numéro de scrutin figure dans `cri:tm6` (« Adoption, par scrutin public n° 249 ») et les totaux dans `cri:scrutin1` / `cri:scrutin2` (identiques à ceux des pages de scrutin).
- Groupe de l'orateur : jointure `mat` (XML) = `Matricule` (ODSEN) vérifiée sur 4 orateurs.
- **Deux comptes rendus à ne pas confondre** (corrigé le 2026-10-21) :
  - `https://www.senat.fr/cra/s{AAAAMMJJ}/s{AAAAMMJJ}_mono.html` : compte rendu **analytique** (titre de page « Comptes rendus analytiques officiel »), qui **résume** les interventions. Inutilisable pour citer. L'extrait noté ici à l'étape 2 venait de cette version : ce n'étaient pas les mots exacts de l'oratrice.
  - `https://www.senat.fr/seances/s{AAAAMM}/s{AAAAMMJJ}/s{AAAAMMJJ}_mono.html` : compte rendu **intégral**, mot à mot, même texte que `cri.zip`. Source retenue pour les citations. Publié avec quelques semaines de délai.
- Compte rendu intégral HTML : chaque tour de parole est un bloc `div.intervenant` portant un commentaire `<!--cri:intervenant mat="10006L" nom="Catherine DEROCHE" qua="" ...-->`, donc le matricule du sénateur ; la présidence porte `qua="président de séance"`. Chaque paragraphe a une ancre `#par_{n}`. Aucun titre « Explications de vote » : la présidence annonce « La parole est à ..., pour explication de vote » ou « ..., pour le groupe ... ». Règle d'extraction dans `methodologie.md`.
- Exemple vérifié (intégral) : « Monsieur le président, messieurs les ministres, mes chers collègues, la CMP qui s’est tenue hier a marqué une étape importante », Mme Catherine Deroche, groupe Les Républicains, https://www.senat.fr/seances/s202303/s20230316/s20230316_mono.html#par_2917.
- `TODO: vérifier` : rythme de mise à jour (non documenté).

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

- Page d'un vote : `https://howtheyvote.eu/votes/{id}` (vérifiée), avec liens vers le procès-verbal officiel des votes par appel nominal (`PV-10-...-RCV_FR.xml`) et la fiche de procédure de l'Observatoire législatif.
- Constats à l'ingestion : résultat (`result`) vide pour 69 % des votes, laissé vide plutôt que déduit ; intitulés en anglais seulement (`display_title`), à traduire pour les fiches ; législatures déduites de `group_memberships` (9e depuis le 2019-07-02, 10e depuis le 2024-07-16).
- Partis nationaux : `member_votes.national_party_id` donne le parti de l'eurodéputé au jour du vote ; libellés dans `national_parties` (dont « Sans parti » et « Indépendant », qui ne sont pas des partis). 40 délégations françaises sur les 9e et 10e législatures.
- Attribution ODbL : chaque fiche qui affiche un vote du PE cite HowTheyVote.eu et sa licence.

### Portail open data du PE

- API : https://data.europarl.europa.eu/api/v2/ (description OpenAPI). Exige l'en-tête `Accept: application/ld+json` (sinon 406). Licence de l'API : CC BY 4.0.
- Routes confirmées : `/meps`, `/speeches`, `/meetings`, `/plenary-documents`, `/meetings/{id}/vote-results` (résultats de vote liés au rapport, sans vote par député).
- Le vocabulaire `ep-activities` contient `VOTE_EXPLANATION_ORAL` et `VOTE_EXPLANATION_WRITTEN`, mais `/speeches` filtré sur ces types ne renvoie aucun résultat : explications de vote non indexées dans l'API à ce jour.

### Site europarl.europa.eu

- Notice légale (https://www.europarl.europa.eu/legal-notice/en/) : réutilisation autorisée, avec la mention « © European Union, [année] - Source: European Parliament ». Une reproduction partielle doit citer l'URL de l'élément complet.
- Explications de vote : les comptes rendus in extenso (pages `doceo`, par exemple `CRE-10-2025-06-18-ITM-017`) contiennent une section « explications de vote orales », vue seulement dans des résultats de recherche. Les pages `doceo` renvoient 202 avec un corps vide aux clients automatisés (protection anti-robot).
- `TODO: vérifier` : contenu réel d'un CRE de la 10e législature, publication des explications écrites (fiches des députés ?), et si une explication est individuelle (par député) ou de groupe, ce qui change le contrat du juge.
- Décision (2026-10-20) : pour le prototype, les explications de vote du PE ne sont pas ingérées. Seuls les votes (HowTheyVote) le sont, et les fiches indiquent « explication non disponible ».

## Programmes et candidatures

- 2027etmoi (source collaborative, non officielle), organisation https://www.data.gouv.fr/organizations/2027etmoi/ :
  - candidatures avec statut sourcé : https://www.data.gouv.fr/datasets/candidatures-a-lelection-presidentielle-2027-statuts-sources (JSON, 51 personnalités, Licence Ouverte 2.0, mis à jour le 2026-10-14) ;
  - votes des candidats parlementaires : https://www.data.gouv.fr/datasets/votes-au-parlement-des-candidats-a-lelection-presidentielle-2027 (JSON, 188 scrutins, Licence Ouverte 2.0) ;
  - programmes : uniquement dans le dépôt https://github.com/2027etmoi/2027etmoi (`data/programmes/`, contenu `TODO: vérifier`), pas sur data.gouv.fr. Code sans licence libre.
- Relevé du 2026-10-22 : 54 personnalités dans le jeu, 32 « déclarées ». Après vérification à la source : 28 déclarations confirmées et datées (dont 3 datées par une recherche complémentaire : Delphine Batho, Édouard Philippe, Marine Tondelier), 4 non confirmées (Xavier Bertrand, Emmanuel Dubuisson, Anasse Kazib, Manolo Mlekuz). Plusieurs sources de 2027etmoi ne confirmaient pas la déclaration (annuaire des entreprises, article sans rapport) : la source retenue est alors une autre, vérifiée. Les champs « bloc » (classement politique) et « propositions » (résumés) du jeu ne sont pas utilisés.
- Programmes : rares à cette date. Sites injoignables ou bloquant les accès automatisés (marinetondelier.fr en 403, reconquete.fr, francelibre.fr) ; pages de chapitre du livre de melenchon2027.fr en 404, lues sur leur archive Wayback du 2026-08-29.
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

- Retenu : le jeu « votes des candidats » de 2027etmoi (voir plus haut), pour contrôler les votes personnels des candidats parlementaires. Il ne sert jamais de source : tout écart avec les données officielles est signalé, et c'est la source officielle qui fait foi. Le contrôle ne dépend donc pas de l'impartialité de 2027etmoi.
- Écarté : Datan (https://www.data.gouv.fr/organizations/datan, Licence Ouverte) : députés et groupes de l'Assemblée uniquement. **Aucune position de groupe par scrutin publiée**, pas de Sénat. Inutilisable pour contrôler les positions de groupes.
