-- Consigne judge_v2 : le juge établit l'effet du texte voté avant la relation, qui doit en découler.
alter table concordance.judgments
    add column effet_du_texte text check (effet_du_texte in ('rapproche', 'eloigne', 'ambigu', 'hors_sujet'));
