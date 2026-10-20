# Concordance

> Ce qu'ils promettent, ce qu'ils votent.

Outil citoyen, local-first et open source, qui relie chaque promesse des programmes présidentiels 2027 aux votes réels des groupes parlementaires (Assemblée nationale, Sénat, Parlement européen), avec leurs explications de vote citées mot pour mot.

Concordance ne donne **ni note, ni classement, ni consigne de vote**. Il produit des **fiches de preuve** : la promesse, les votes liés, la position de chaque groupe, son explication, un verdict justifié (`dans le sens`, `contraire`, `ambigu`, `hors sujet`) et le lien vers la source officielle. Le lecteur juge.

*Nom de travail, facile à changer.*

---

## Pourquoi

Les programmes disent une chose, les réseaux sociaux en disent une autre. Les votes, eux, sont publics, datés et nominatifs. Des projets existants rassemblent déjà programmes et votes côte à côte (2027etmoi, Datan, HowTheyVote.eu), mais aucun ne fait le lien promesse par promesse, avec le pourquoi du vote. C'est la couche que Concordance ajoute.

## Principes de neutralité (non négociables)

1. **Même traitement pour tous** : un seul pipeline, un seul prompt, aucune règle propre à un candidat ou un parti.
2. **Juge aveugle** : le modèle qui évalue la cohérence ne voit jamais le nom du groupe ni du candidat. Les groupes deviennent `Groupe A`, `Groupe B`... avec un tirage aléatoire à chaque jugement, et les noms de personnes et de partis sont retirés des textes.
3. **Double juge** : deux modèles de familles différentes jugent chaque paire. Accord : verdict publié. Désaccord : file de revue humaine.
4. **Preuve obligatoire** : chaque verdict cite le passage exact de la mesure, du scrutin et de l'explication de vote, avec l'URL officielle. Pas de source, pas de verdict.
5. **"Ambigu" est une réponse légitime** : un vote contre un budget n'est pas un vote contre chaque mesure qu'il contient.
6. **Groupe n'est pas candidat** : chaque fiche précise si le candidat a voté lui-même, s'il appartient au groupe, ou s'il ne siège pas.
7. **Transparence totale** : prompts, versions des modèles, jeux de test et biais mesurés sont publiés dans le dépôt.

## Les pièges connus

| Piège | Exemple | Traitement |
|---|---|---|
| Texte composite | Un budget ou une loi fourre-tout | `nature_du_vote` renseignée, verdict souvent `ambigu` |
| Pas de vote direct | Réforme des retraites 2023 adoptée par 49.3 à l'Assemblée : le seul vote est la motion de censure du 20 mars 2023 | Signalé comme vote indirect |
| Vote contre le gouvernement | Motion de censure, motion de rejet | Distingué d'un vote sur le fond |
| Abstention, absence | Groupe divisé ou non-votant | Rapporté, jamais interprété |
| Candidat non parlementaire | Philippe est maire, Retailleau a surtout siégé au Sénat puis été ministre | On compare le groupe, avec mention explicite |
| Candidature incertaine | Le Pen : pourvoi en cassation, Bardella candidat de recours | Le programme RN reste le même objet |

## Architecture

```
 Sources officielles            Stockage                 Traitement local (RTX 4090)
 ─────────────────────          ─────────────            ───────────────────────────
 Assemblée nationale  ─┐                                  
 Sénat                 ├─ n8n ─▶ Supabase / Postgres ─▶ 1. Mesures atomiques
 Parlement européen   ─┤  cron   + pgvector             2. Embeddings (Ollama)
 Programmes           ─┘                                 3. Recherche hybride mesure ↔ scrutins
                                                         4. Anonymisation + test de fuite
                                                         5. Double juge LLM (Ollama)
                                                         6. Revue humaine des désaccords
                                                                    │
                                                                    ▼
                                                         Fiches de preuve (HTML statique)
```

### Stack

- **Orchestration** : n8n auto-hébergé (crons d'ingestion, enchaînement des étapes)
- **Traitements** : Python 3.12, géré avec `uv`
- **Base** : Supabase auto-hébergé (Postgres + pgvector + recherche plein texte en français), tables dans un schéma dédié `concordance`
- **IA locale** : Ollama
  - embeddings multilingues (ex. `bge-m3`)
  - deux juges de familles différentes, dimensionnés pour 24 Go de VRAM (ex. un Qwen et un Mistral quantifiés), choix final après évaluation
- **Sortie** : site statique généré, aucun tracking

### Sources de données

| Source | Contenu utile | Point d'entrée |
|---|---|---|
| Assemblée nationale | Scrutins publics, positions par groupe, amendements (exposés sommaires), comptes rendus de séance (explications de vote), acteurs et organes | data.assemblee-nationale.fr |
| Sénat | Scrutins, positions des groupes, comptes rendus | data.senat.fr |
| Parlement européen | Votes nominaux, groupes, eurodéputés | HowTheyVote.eu (CSV hebdomadaire, github.com/HowTheyVote/data) et portail open data du PE |
| Programmes | Mesures sourcées | Sites officiels des candidats, jeux de données de 2027etmoi (data.gouv.fr, GitHub) |
| Contrôle croisé | Positions de groupes déjà calculées | Datan (data.gouv.fr) |

URLs exactes, formats et licences à **vérifier** avant d'écrire l'ingestion. Licence de chaque jeu de données à noter dans `docs/sources.md`.

## Modèle de données (première version)

- `candidates` : candidat, parti, statut de candidature
- `parl_groups` : chambre, législature, sigle, libellé, dates (dérivé des données "organes", jamais codé en dur)
- `candidate_group_links` : lien candidat ↔ groupe (membre, allié, ne siège pas)
- `measures` : mesure atomique, thème, texte, citation source, URL, date de récupération, embedding
- `ballots` : scrutin, chambre, date, intitulé, nature (texte entier, article, amendement, motion), dossier, embedding
- `group_positions` : scrutin × groupe : pour, contre, abstention, non-votants, position majoritaire
- `vote_explanations` : scrutin × groupe : orateur, texte, URL et ancre du compte rendu
- `judgments` : mesure × scrutin × groupe × modèle : relation, justification, citations (jsonb), confiance, version du prompt, texte anonymisé envoyé au juge, mapping d'anonymisation
- `reviews` : verdict humain final sur les désaccords

## Prototype : les retraites

Premier thème choisi parce qu'il est très voté depuis 2023 et que les positions sont tranchées.

Candidats couverts : tous les candidats à la présidentielle 2027, selon la règle d'inclusion de [docs/methodologie.md](docs/methodologie.md). La liste n'est jamais codée en dur.

### Premières mesures repérées (à revérifier à la source, liste non exhaustive)

| Candidat | Mesures |
|---|---|
| Mélenchon (LFI) | Retour à 60 ans avec 40 annuités · pensions de carrière complète au niveau du SMIC revalorisé · cotisation retraite +0,25 point par an, étendue aux revenus financiers |
| Philippe (Horizons) | 65 ans progressivement et 45 annuités, un tiers des salariés exemptés · part de capitalisation collective type Agirc-Arrco |
| Retailleau (LR) | Âge légal à 65 ans · compte d'épargne retraite pour chaque actif en plus de la répartition · cumul emploi-retraite sans cotisations |
| Le Pen (RN) | Refuser tout recul de l'âge · 60 ans pour qui a commencé avant 20 ans avec 40 annuités · minimum vieillesse à 1 000 €, pensions réindexées sur l'inflation |

Sources : melenchon2027.fr/programme2025/livre, edouardphilippe.fr, republicains.fr/qrtravail, rassemblementnational.fr/22-mesures, Euronews (9 oct. 2026) pour les annonces de Philippe, LCP (19 juin 2026) pour la synthèse.

### Scrutins à identifier dans les données

- Réforme 2023 : votes du Sénat sur le texte, motion de censure du 20 mars 2023 à l'Assemblée (vote indirect)
- Propositions de loi d'abrogation déposées depuis 2024 (à retrouver, vérifier ce qui a réellement été voté)
- Suspension de la réforme dans le budget de la Sécurité sociale, automne 2025 (article ou amendement à identifier)
- Parlement européen : peu de votes attendus, la retraite est une compétence nationale

### Critère de réussite du prototype

- Jeu de référence d'au moins 30 paires mesure ↔ scrutin annotées à la main, équilibré entre les groupes concernés
- Accord juge/humain mesuré, accord entre les deux juges (kappa de Cohen)
- Votes des trois chambres ingérés (Assemblée nationale, Sénat, Parlement européen)
- Test de fuite : l'anonymiseur ne laisse pas deviner le groupe mieux qu'une anonymisation faite à la main (voir [docs/methodologie.md](docs/methodologie.md))
- Test contrefactuel : permuter les étiquettes anonymes ne change pas les verdicts
- Répartition des verdicts par groupe publiée pour repérer un biais systématique
- Une fiche de preuve HTML par candidat

## Démarrage

```bash
cp .env.example .env          # Postgres (Supabase), Ollama
uv sync
uv run python -m concordance.ingest.an --legislatures 16 17
uv run python -m concordance.pipeline.run --theme retraites
uv run python -m concordance.eval.run --gold eval/gold_retraites.csv
```

*(Commandes cibles, à créer lors de la première session.)* n8n et Supabase tournent déjà sur un serveur auto-hébergé : pas de `docker-compose.yml` dans ce dépôt.

## Arborescence prévue

```
concordance/
├── README.md
├── CLAUDE.md
├── .env.example
├── pyproject.toml
├── supabase/migrations/
├── src/concordance/
│   ├── ingest/        # an.py, senat.py, pe.py, programmes.py
│   ├── pipeline/      # measures.py, embed.py, retrieve.py, anonymize.py, judge.py, run.py
│   ├── publish/       # génération des fiches HTML
│   └── eval/          # run.py, leakage.py, bias.py
├── prompts/           # judge_v1.md, split_measures_v1.md (versionnés)
├── n8n/workflows/     # exports JSON
├── eval/              # gold_retraites.csv
├── docs/              # methodologie.md, sources.md
└── tests/
```

## Licence

Code sous AGPL-3.0 pour que toute version publique reste ouverte. Chaque jeu de données garde sa licence d'origine (Licence Ouverte Etalab pour les données publiques françaises, à vérifier pour les autres).
