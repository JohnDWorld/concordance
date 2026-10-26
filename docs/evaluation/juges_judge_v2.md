# Évaluation des juges (2026-10-26)

Consigne `judge_v2`. Jeu de référence : 120 paires (eval/gold_retraites.csv), annotation : claude-provisoire (cohérence) (32), claude-provisoire (79), claude-provisoire (arbitrage) (9).

| Juge | Paires jugées | Rejetées | Accord avec l'annotation |
|---|---|---|---|
| `qwen3-30b-a3b` | 120 | 36 | 33/84 (39%) |
| `llama3.2` | 120 | 86 | 4/34 (12%) |

Kappa entre les deux juges : 0.10 sur 26 paires jugées par les deux.
Verdict publié (accord des deux juges ou relecture) : 7 paires, dont 1 conformes à l'annotation (14%).

## Matrice de confusion (lignes : annotation, colonnes : juge)

`qwen3-30b-a3b`

| | dans_le_sens | contraire | ambigu | hors_sujet |
|---|---|---|---|---|
| dans_le_sens | 1 | 1 | 2 | 2 |
| contraire | 1 | 3 | 1 | 1 |
| ambigu | 13 | 6 | 12 | 16 |
| hors_sujet | 2 | 5 | 1 | 17 |

`llama3.2`

| | dans_le_sens | contraire | ambigu | hors_sujet |
|---|---|---|---|---|
| dans_le_sens | 1 | 1 | 0 | 0 |
| contraire | 0 | 3 | 0 | 0 |
| ambigu | 3 | 16 | 0 | 5 |
| hors_sujet | 2 | 3 | 0 | 0 |

## Accord par groupe

Un juge biaisé se tromperait plus souvent pour certains groupes.

| Groupe | Paires | `qwen3-30b-a3b` | `llama3.2` |
|---|---|---|---|
| CRCE-K | 3 | 1/2 | 0/1 |
| DR | 4 | 2/3 | - |
| Dem | 8 | 2/5 | 2/6 |
| EPR | 4 | 0/4 | 0/1 |
| EcoS | 4 | 3/3 | - |
| Ecolo - NUPES | 3 | 1/2 | 0/2 |
| GDR | 4 | 0/1 | 0/1 |
| GDR - NUPES | 4 | 1/3 | 1/4 |
| GEST | 3 | 0/1 | - |
| HOR | 7 | 1/6 | 0/3 |
| LFI - NUPES | 4 | 1/3 | 1/2 |
| LFI-NFP | 4 | 2/3 | - |
| LIOT | 8 | 1/6 | - |
| LR | 4 | 2/4 | - |
| Les Indépendants | 3 | 1/3 | - |
| Les Républicains | 3 | 1/2 | 0/2 |
| NI | 10 | 1/7 | 0/3 |
| RDPI | 3 | 1/2 | - |
| RDSE | 3 | 0/1 | 0/1 |
| RE | 4 | 0/4 | - |
| RN | 8 | 3/5 | 0/3 |
| SER | 3 | 2/3 | 0/1 |
| SOC | 8 | 4/5 | 0/1 |
| UCI | 3 | 0/1 | 0/1 |
| UDR | 8 | 3/5 | 0/2 |
