-- Parlement européen : un parti français n'est qu'une délégation dans un groupe européen.
-- La délégation (eurodéputés français d'un même parti au jour du vote) a ses propres positions,
-- affichées à côté de celles du groupe, sans jamais les confondre.
alter table concordance.parl_groups
    add column categorie text not null default 'groupe' check (categorie in ('groupe', 'delegation_nationale'));
