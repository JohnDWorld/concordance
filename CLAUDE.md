# CLAUDE.md - Concordance

Contexte complet, sources et architecture : voir `README.md`. Ce fichier fixe les règles de travail.

## Le projet en une phrase

Relier chaque promesse des programmes présidentiels 2027 aux votes réels des groupes parlementaires, avec explications de vote citées, sous forme de fiches de preuve neutres. Aucun score, aucun classement, aucune consigne de vote.

## Communication

- Toujours en français.
- Jamais de tiret cadratin ni demi-cadratin, uniquement le tiret simple `-`.
- Contredis-moi quand une idée est mauvaise et dis pourquoi. Pose une question quand une demande est ambiguë au lieu de deviner.
- Réponses courtes, sans préambule.

## Règles de neutralité (priorité absolue, au-dessus de la vitesse)

1. **Aucune règle propre à un candidat ou un parti** dans le code ou les prompts. Si un cas particulier semble nécessaire, il devient une règle générale documentée dans `docs/methodologie.md`.
2. **Juge aveugle** : avant tout appel au juge, `pipeline/anonymize.py` remplace les groupes par `Groupe A/B/C...` (tirage aléatoire par jugement, mapping stocké dans `judgments`) et retire noms de personnes, de partis et termes identifiants (dictionnaire construit depuis les données acteurs et organes, plus une liste de termes comme "insoumis", "lepéniste", "macroniste"). Toute fonction qui envoie du texte au juge sans passer par l'anonymiseur est un bug bloquant.
3. **Double juge** : deux modèles de familles différentes. Désaccord = file `reviews`, jamais de vote à la majorité automatique.
4. **Pas de source, pas de verdict** : chaque citation est vérifiée par correspondance exacte de chaîne contre le texte source. Citation introuvable = jugement rejeté.
5. **Ne jamais inventer de données** : URL, format de fichier, identifiant de scrutin, nom de groupe. Si tu ne l'as pas vérifié dans les données ou la doc officielle, écris `TODO: vérifier` et dis-le moi.
6. **Noms de groupes jamais codés en dur** : ils changent d'une législature à l'autre. Les dériver des données "organes".
7. **Groupe n'est pas candidat** : toute sortie précise le lien (membre, allié, ne siège pas).

## Contrat du juge

Entrée (anonymisée) : une mesure de programme, un scrutin (intitulé, nature, date, objet), la position d'un `Groupe X` (pour, contre, abstention, non-votant, chiffres), son explication de vote si elle existe.

Sortie JSON stricte, validée par Pydantic :

```json
{
  "relation": "dans_le_sens | contraire | ambigu | hors_sujet",
  "nature_du_vote": "texte_entier | article | amendement | motion | autre",
  "justification": "80 mots maximum, factuelle, sans adjectif de jugement",
  "citations": [
    {"source": "mesure | scrutin | explication", "extrait": "copie exacte"}
  ],
  "confiance": 0.0
}
```

Règles du prompt :
- `ambigu` dès que le texte voté mélange plusieurs sujets ou que le vote porte sur le gouvernement plutôt que sur le fond (motion de censure, motion de rejet).
- Abstention et non-vote : décrire, ne pas interpréter.
- Prompts versionnés dans `prompts/` (`judge_v1.md`, `judge_v2.md`...). Ne jamais modifier une version publiée, en créer une nouvelle. La version est stockée avec chaque jugement.

## Évaluation (à lancer après toute modification du prompt, du modèle ou de l'anonymiseur)

- `eval/gold_retraites.csv` : paires annotées à la main, équilibrées entre groupes.
- Accord juge/humain et kappa entre les deux juges.
- **Test de fuite** (`eval/leakage.py`) : un modèle tente de deviner le groupe depuis le texte anonymisé. Au-dessus du hasard + marge = l'anonymisation fuit, à corriger avant tout le reste.
- **Biais** (`eval/bias.py`) : répartition des verdicts par groupe, et test contrefactuel en permutant les étiquettes anonymes. Résultats publiés dans `docs/`.

## Stack et conventions

- Python 3.12 avec `uv`, typage strict, Pydantic pour tous les schémas, `pytest`.
- Supabase : schéma uniquement via migrations dans `supabase/migrations/`, jamais de modification à la main.
- Ollama en local (RTX 4090, 24 Go) : embeddings multilingues, deux juges choisis après benchmark sur le jeu de référence. Aucun appel à une API d'IA externe dans le pipeline.
- n8n orchestre (crons, enchaînements) et appelle les scripts Python. La logique métier reste en Python, testable hors n8n. Workflows exportés en JSON dans `n8n/workflows/`.
- Secrets dans `.env` uniquement, `.env.example` tenu à jour.
- Données brutes téléchargées dans `data/raw/` (ignoré par git), avec date et URL d'origine consignées.

## Ordre de travail pour la première session

1. Initialiser le dépôt : arborescence du README, `pyproject.toml`, `docker-compose.yml`, `.env.example`, `.gitignore`.
2. Vérifier sur les sites officiels les URLs, formats et licences des jeux de données (Assemblée, Sénat, HowTheyVote). Consigner dans `docs/sources.md`. Me signaler tout ce qui diffère du README.
3. Migrations Supabase du modèle de données (voir README).
4. Ingestion Assemblée nationale : scrutins des 16e et 17e législatures, positions par groupe, organes.
5. Saisie des mesures retraites des 4 candidats depuis leurs sources officielles (citation exacte + URL).
6. Recherche hybride mesure ↔ scrutins (pgvector + plein texte français), revue manuelle des résultats avec moi.
7. Anonymiseur + test de fuite, avant d'écrire le moindre prompt de juge.
8. Prompt `judge_v1`, double juge, évaluation sur le jeu de référence.
9. Première fiche de preuve HTML.

Valide chaque étape avec moi avant de passer à la suivante. Commits petits et fréquents.

## À ne pas faire

- Calculer un score global, un pourcentage de "tenue des promesses" ou un classement.
- Résumer une explication de vote à la place de la citer.
- Ajouter du tracking ou de l'analytics au site publié.
- Élargir à d'autres thèmes avant que le prototype retraites passe l'évaluation.
