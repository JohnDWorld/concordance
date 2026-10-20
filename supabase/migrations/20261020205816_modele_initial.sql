-- Modèle de données initial (README.md, section « Modèle de données »).
-- Instance Supabase partagée : tout vit dans le schéma concordance.
-- Pas de suppression en cascade : rien n'est supprimé sans le vouloir (docs/methodologie.md).
-- Embeddings et plein texte : migration de l'étape 6, une fois le modèle et sa dimension choisis.

create schema concordance;

create table concordance.candidates (
    id bigint generated always as identity primary key,
    full_name text not null unique,
    party text
);

-- Règles d'inclusion : chaque entrée ou sortie de la liste est datée et sourcée.
create table concordance.candidate_events (
    id bigint generated always as identity primary key,
    candidate_id bigint not null references concordance.candidates,
    event text not null check (event in (
        'declaration', 'retrait', 'battu_primaire', 'liste_officielle', 'absent_liste_officielle'
    )),
    event_date date not null,
    source_url text not null
);

-- Dérivé des données « organes » (AN), ODSEN (Sénat), HowTheyVote (PE). Jamais codé en dur.
create table concordance.parl_groups (
    id bigint generated always as identity primary key,
    chamber text not null check (chamber in ('an', 'senat', 'pe')),
    legislature int,          -- AN : 16, 17 ; PE : 9, 10 ; Sénat : null
    external_id text not null, -- AN : uid PO... ; Sénat : code ODSEN ; PE : group_code
    sigle text,
    libelle text not null,
    start_date date,
    end_date date,
    unique nulls not distinct (chamber, legislature, external_id)
);

create table concordance.candidate_group_links (
    candidate_id bigint not null references concordance.candidates,
    group_id bigint not null references concordance.parl_groups,
    link text not null check (link in ('membre', 'allie', 'ne_siege_pas')),
    source_url text not null,
    primary key (candidate_id, group_id)
);

create table concordance.measures (
    id bigint generated always as identity primary key,
    candidate_id bigint not null references concordance.candidates,
    theme text not null,
    texte text not null,    -- mesure atomique
    citation text not null, -- copie exacte de la source officielle
    source_url text not null,
    retrieved_at timestamptz not null
);

create table concordance.ballots (
    id bigint generated always as identity primary key,
    chamber text not null check (chamber in ('an', 'senat', 'pe')),
    legislature int,
    external_id text not null, -- AN : VTANR5L... ; Sénat : scr2022-251 ; PE : id HowTheyVote
    ballot_date date not null,
    intitule text not null,
    objet text,
    nature text check (nature in ('texte_entier', 'article', 'amendement', 'motion', 'autre')),
    sort text,
    dossier text,
    seance_ref text,           -- AN : seanceRef, jointure avec les comptes rendus
    source_url text not null,
    unique (chamber, external_id)
);

create table concordance.group_positions (
    ballot_id bigint not null references concordance.ballots,
    group_id bigint not null references concordance.parl_groups,
    membres int,
    pour int not null,
    contre int not null,
    abstention int not null,
    non_votants int not null,
    position_majoritaire text check (position_majoritaire in ('pour', 'contre', 'abstention', 'non_votant')),
    primary key (ballot_id, group_id)
);

-- Groupe n'est pas candidat : vote personnel du candidat parlementaire, s'il existe.
create table concordance.candidate_votes (
    candidate_id bigint not null references concordance.candidates,
    ballot_id bigint not null references concordance.ballots,
    position text not null check (position in ('pour', 'contre', 'abstention', 'non_votant')),
    primary key (candidate_id, ballot_id)
);

create table concordance.vote_explanations (
    id bigint generated always as identity primary key,
    ballot_id bigint not null references concordance.ballots,
    group_id bigint not null references concordance.parl_groups,
    orateur text not null,
    orateur_external_id text,  -- AN : PA... ; Sénat : matricule
    texte text not null,       -- copie exacte de la source publique
    source_url text not null,  -- URL publique avec l'ancre du paragraphe
    unique (ballot_id, group_id, source_url)
);

-- Contrat du juge (CLAUDE.md). Plusieurs jugements possibles par paire (deux juges, relances).
create table concordance.judgments (
    id bigint generated always as identity primary key,
    measure_id bigint not null references concordance.measures,
    ballot_id bigint not null references concordance.ballots,
    group_id bigint not null references concordance.parl_groups,
    model text not null,
    prompt_version text not null,
    relation text check (relation in ('dans_le_sens', 'contraire', 'ambigu', 'hors_sujet')),
    nature_du_vote text check (nature_du_vote in ('texte_entier', 'article', 'amendement', 'motion', 'autre')),
    justification text,
    citations jsonb,
    confiance real check (confiance between 0 and 1),
    texte_anonymise text not null,        -- texte exact envoyé au juge
    mapping_anonymisation jsonb not null, -- étiquette Groupe X -> groupe réel
    rejet text,                           -- null = jugement valide
    created_at timestamptz not null default now(),
    check (rejet is not null or (
        relation is not null and nature_du_vote is not null and justification is not null
        and citations is not null and confiance is not null
    ))
);
create index on concordance.judgments (measure_id, ballot_id, group_id);

-- Verdict humain final sur les désaccords entre juges.
create table concordance.reviews (
    measure_id bigint not null references concordance.measures,
    ballot_id bigint not null references concordance.ballots,
    group_id bigint not null references concordance.parl_groups,
    relation text not null check (relation in ('dans_le_sens', 'contraire', 'ambigu', 'hors_sujet')),
    justification text not null,
    reviewer text not null,
    reviewed_at timestamptz not null default now(),
    primary key (measure_id, ballot_id, group_id)
);

-- Aucune API publique sur ce schéma : RLS sans politique, seul le pipeline (propriétaire) écrit.
alter table concordance.candidates enable row level security;
alter table concordance.candidate_events enable row level security;
alter table concordance.parl_groups enable row level security;
alter table concordance.candidate_group_links enable row level security;
alter table concordance.measures enable row level security;
alter table concordance.ballots enable row level security;
alter table concordance.group_positions enable row level security;
alter table concordance.candidate_votes enable row level security;
alter table concordance.vote_explanations enable row level security;
alter table concordance.judgments enable row level security;
alter table concordance.reviews enable row level security;
