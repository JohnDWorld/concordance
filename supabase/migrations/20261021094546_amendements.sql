-- Amendements et leurs mesures (docs/methodologie.md, section Amendements), calculées par concordance.rules.
create table concordance.amendments (
    id bigint generated always as identity primary key,
    chamber text not null check (chamber in ('an', 'senat')),
    legislature int,
    external_id text not null unique,  -- AN : uid AMANR5L...
    dossier_ref text not null,
    texte_ref text not null,           -- texte amendé : les mesures « identique » et « série » s'y comparent
    numero text not null,
    organe_examen text not null,       -- AN : « AN » = séance publique, sinon la commission (CION-SOC...)
    auteur_type text not null,         -- Député, Gouvernement, Rapporteur...
    auteur_ref text,
    group_id bigint references concordance.parl_groups,  -- groupe de l'auteur au dépôt, null hors député
    date_depot date,
    etat text,
    sous_etat text,
    sort text,
    division text,
    dispositif text,                   -- null si non publié (irrecevable, retiré avant publication...)
    expose_sommaire text,
    identique boolean not null,        -- même dispositif qu'un autre amendement sur le même texte
    serie boolean not null,            -- même dispositif à un nombre près, sans être identique
    suppression boolean,               -- null si dispositif non publié
    forme boolean,
    mots_ajoutes int,
    source_url text not null
);
create index on concordance.amendments (texte_ref);

create table concordance.amendment_cosignatures (
    amendment_id bigint not null references concordance.amendments,
    group_id bigint not null references concordance.parl_groups,
    cosignataires int not null,
    primary key (amendment_id, group_id)
);

alter table concordance.amendments enable row level security;
alter table concordance.amendment_cosignatures enable row level security;
