-- L'Assemblée distingue nonVotants et nonVotantsVolontaires : on rapporte les deux tels quels.
alter table concordance.group_positions add column non_votants_volontaires int;
