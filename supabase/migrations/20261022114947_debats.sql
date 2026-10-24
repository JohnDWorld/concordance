-- Débat qui précède chaque scrutin dans le compte rendu intégral (depuis le résultat précédent).
-- L'intitulé d'un scrutin dit rarement son sujet ; le débat, si (docs/methodologie.md).
alter table concordance.ballots add column debat text;
