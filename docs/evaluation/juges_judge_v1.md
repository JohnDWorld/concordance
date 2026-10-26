# Évaluation des juges (2026-10-26)

Consigne `judge_v1`. Jeu de référence : 120 paires (eval/gold_retraites.csv), annotation : claude-provisoire (cohérence) (32), claude-provisoire (79), claude-provisoire (arbitrage) (9).

| Juge | Paires jugées | Rejetées | Accord avec l'annotation |
|---|---|---|---|
| `qwen3-30b-a3b` | 68 | 17 | 17/51 (33%) |
| `llama3.2` | 120 | 26 | 13/94 (14%) |

Kappa entre les deux juges : 0.32 sur 43 paires jugées par les deux.
Verdict publié (accord des deux juges ou relecture) : 24 paires, dont 6 conformes à l'annotation (25%).

## Matrice de confusion (lignes : annotation, colonnes : juge)

`qwen3-30b-a3b`

| | dans_le_sens | contraire | ambigu | hors_sujet |
|---|---|---|---|---|
| dans_le_sens | 0 | 2 | 0 | 0 |
| contraire | 0 | 3 | 0 | 0 |
| ambigu | 12 | 14 | 0 | 0 |
| hors_sujet | 1 | 5 | 0 | 14 |

`llama3.2`

| | dans_le_sens | contraire | ambigu | hors_sujet |
|---|---|---|---|---|
| dans_le_sens | 1 | 4 | 0 | 2 |
| contraire | 2 | 2 | 0 | 3 |
| ambigu | 12 | 21 | 0 | 21 |
| hors_sujet | 5 | 11 | 0 | 10 |

## Accord par groupe

Un juge biaisé se tromperait plus souvent pour certains groupes.

| Groupe | Paires | `qwen3-30b-a3b` | `llama3.2` |
|---|---|---|---|
| CRCE-K | 3 | 0/1 | 0/1 |
| DR | 4 | 1/2 | 1/3 |
| Dem | 8 | 1/6 | 1/7 |
| EPR | 4 | 1/3 | 0/2 |
| EcoS | 4 | 2/2 | 1/2 |
| Ecolo - NUPES | 3 | - | 0/1 |
| GDR | 4 | 2/2 | 2/4 |
| GDR - NUPES | 4 | 0/1 | 0/2 |
| GEST | 3 | 0/1 | 0/2 |
| HOR | 7 | 0/2 | 0/6 |
| LFI - NUPES | 4 | 0/1 | 0/4 |
| LFI-NFP | 4 | 1/2 | 0/3 |
| LIOT | 8 | 1/1 | 1/8 |
| LR | 4 | 0/2 | 0/4 |
| Les Indépendants | 3 | 1/2 | 0/1 |
| Les Républicains | 3 | 1/2 | 0/3 |
| NI | 10 | 1/5 | 1/9 |
| RDPI | 3 | 0/1 | 1/2 |
| RDSE | 3 | 0/2 | 1/3 |
| RE | 4 | 0/1 | 0/4 |
| RN | 8 | 0/2 | 0/7 |
| SER | 3 | 1/2 | 0/3 |
| SOC | 8 | 0/2 | 0/5 |
| UCI | 3 | 1/2 | 1/2 |
| UDR | 8 | 3/4 | 3/6 |
