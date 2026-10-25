-- Lien entre un scrutin sur un amendement et l'amendement lui-même (dispositif, exposé sommaire) :
-- l'intitulé du scrutin ne dit pas ce que propose l'amendement.
alter table concordance.amendments add column date_sort date;
alter table concordance.ballots add column amendment_id bigint references concordance.amendments;
