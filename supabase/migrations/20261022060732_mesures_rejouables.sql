-- Chargement rejouable des candidats et des mesures depuis les fichiers relus dans donnees/.
alter table concordance.candidate_events
    add constraint candidate_events_unique unique (candidate_id, event, event_date);

-- Une mesure est identifiée par son candidat, sa source et sa citation exacte.
alter table concordance.measures
    add column cle text generated always as (md5(candidate_id::text || '|' || source_url || '|' || citation)) stored,
    add constraint measures_cle_unique unique (cle);
