# Biais des juges (2026-10-26)

Consigne `judge_v2`, juges : `qwen3-30b-a3b`, `llama3.2`.

## Répartition des verdicts publiés par groupe

Verdict publié : accord des deux juges ou relecture humaine. Les écarts entre groupes reflètent d'abord leurs votes ; ce tableau sert à repérer un groupe pour lequel les juges seraient plus souvent en désaccord ou rejetés.

| Groupe | dans_le_sens | contraire | ambigu | hors_sujet | désaccord | rejet ou manquant |
|---|---|---|---|---|---|---|
| CRCE-K (senat) | 0 | 0 | 0 | 0 | 2 | 7 |
| DR (an 17) | 0 | 1 | 0 | 0 | 5 | 49 |
| Dem (an 16) | 2 | 0 | 0 | 0 | 2 | 5 |
| Dem (an 17) | 0 | 4 | 0 | 0 | 4 | 56 |
| EPR (an 17) | 2 | 3 | 0 | 0 | 8 | 50 |
| EcoS (an 17) | 0 | 2 | 0 | 0 | 2 | 64 |
| Ecolo - NUPES (an 16) | 0 | 0 | 0 | 0 | 3 | 7 |
| GDR (an 17) | 0 | 3 | 0 | 0 | 6 | 48 |
| GDR - NUPES (an 16) | 1 | 0 | 0 | 0 | 3 | 6 |
| GEST (senat) | 0 | 1 | 0 | 0 | 0 | 8 |
| HOR (an 16) | 1 | 1 | 0 | 1 | 0 | 6 |
| HOR (an 17) | 1 | 2 | 0 | 0 | 7 | 57 |
| LFI - NUPES (an 16) | 0 | 1 | 0 | 0 | 3 | 6 |
| LFI-NFP (an 17) | 0 | 1 | 0 | 0 | 8 | 56 |
| LIOT (an 16) | 0 | 0 | 0 | 0 | 0 | 6 |
| LIOT (an 17) | 0 | 0 | 0 | 0 | 6 | 36 |
| LR (an 16) | 0 | 0 | 0 | 0 | 0 | 8 |
| Les Indépendants (senat) | 0 | 0 | 0 | 0 | 1 | 7 |
| Les Républicains (senat) | 0 | 1 | 0 | 0 | 1 | 7 |
| NI (an 16) | 0 | 0 | 0 | 1 | 1 | 4 |
| NI (an 17) | 0 | 1 | 0 | 0 | 1 | 36 |
| NI (senat) | 0 | 0 | 0 | 0 | 2 | 2 |
| RDPI (senat) | 0 | 0 | 0 | 0 | 0 | 9 |
| RDSE (senat) | 0 | 0 | 0 | 1 | 0 | 6 |
| RE (an 16) | 0 | 1 | 0 | 0 | 0 | 8 |
| RN (an 16) | 0 | 0 | 0 | 0 | 2 | 3 |
| RN (an 17) | 4 | 0 | 0 | 0 | 5 | 56 |
| SER (senat) | 0 | 1 | 0 | 0 | 2 | 6 |
| SOC (an 16) | 0 | 1 | 0 | 0 | 1 | 6 |
| SOC (an 16) | 0 | 0 | 0 | 0 | 0 | 1 |
| SOC (an 17) | 1 | 1 | 0 | 0 | 5 | 60 |
| UCI (senat) | 0 | 0 | 0 | 0 | 1 | 8 |
| UDR (an 17) | 0 | 0 | 0 | 0 | 3 | 24 |
| UDR (an 17) | 0 | 1 | 0 | 0 | 1 | 19 |

## Test contrefactuel : autres lettres, même paire

`qwen3-30b-a3b` : 28 paires comparées, verdict identique pour 22 (79%), rejet au second passage : 10, message inchangé (même lettre, pas un test) : 2.

- mesure 12, scrutin 22380, DR (an 17) : ambigu -> contraire
- mesure 11, scrutin 15733, LR (an 16) : ambigu -> contraire
- mesure 11, scrutin 15733, NI (an 16) : hors_sujet -> contraire
- mesure 2, scrutin 16699, HOR (an 16) : dans_le_sens -> ambigu
- mesure 10, scrutin 14783, LIOT (an 16) : ambigu -> hors_sujet
- mesure 8, scrutin 22380, RN (an 17) : ambigu -> dans_le_sens

`llama3.2` : 18 paires comparées, verdict identique pour 13 (72%), rejet au second passage : 21, message inchangé (même lettre, pas un test) : 1.

- mesure 2, scrutin 16901, NI (an 16) : contraire -> dans_le_sens
- mesure 18, scrutin 24450, HOR (an 17) : contraire -> dans_le_sens
- mesure 7, scrutin 18292, Dem (an 17) : dans_le_sens -> contraire
- mesure 1, scrutin 13753, Dem (an 16) : dans_le_sens -> contraire
- mesure 18, scrutin 24450, RN (an 17) : contraire -> dans_le_sens

