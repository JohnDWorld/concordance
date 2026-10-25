-- Recherche hybride mesure ↔ scrutins (docs/methodologie.md) : sens (embeddings) et mots (plein texte français).
-- Dimension 1024 : modèle d'embeddings qwen3-embedding:0.6b (Ollama). Changer de modèle = nouvelle migration.
create extension if not exists vector;

alter table concordance.ballots
    add column embedding vector(1024),
    add column recherche tsvector generated always as (
        to_tsvector('french', coalesce(intitule, '') || ' ' || coalesce(objet, '') || ' ' || coalesce(dossier, ''))
    ) stored;
alter table concordance.measures add column embedding vector(1024);

create index on concordance.ballots using gin (recherche);
create index on concordance.ballots using hnsw (embedding vector_cosine_ops);
