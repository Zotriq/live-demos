-- Job Radar schema for PostgreSQL / Supabase.
-- The app creates these tables automatically; this file is for review and for
-- running by hand in the Supabase SQL editor.

create table if not exists runs (
    id            bigserial primary key,
    started_at    timestamptz not null,
    finished_at   timestamptz,
    mode          varchar(16),
    profile       varchar(200),
    fetched       int default 0,
    new           int default 0,
    duplicates    int default 0,
    updated       int default 0,
    closed        int default 0,
    scored_llm    int default 0,
    scored_rules  int default 0,
    alerts        int default 0,
    errors        jsonb
);

create table if not exists jobs (
    id              bigserial primary key,
    fingerprint     varchar(32) not null unique,          -- dedup key: company + role + location
    source          varchar(32) not null,                 -- greenhouse | lever | ashby | remotive
    source_id       varchar(128) not null,
    board           varchar(128),
    seen_on         jsonb,                                -- every source/board the job appeared on
    title           varchar(300) not null,
    company         varchar(200) not null,
    location        varchar(300),
    remote          boolean default false,
    department      varchar(200),
    employment_type varchar(64),
    salary          varchar(120),
    url             text,
    description     text,
    posted_at       timestamptz,
    content_hash    varchar(32),                          -- detects changes to a posting
    score           int,
    rule_score      int,
    score_reason    text,
    score_engine    varchar(16),                          -- llm | rules
    matched_skills  jsonb,
    is_active       boolean default true,
    first_seen      timestamptz,
    last_seen       timestamptz,
    first_run_id    bigint,
    alerted_at      timestamptz,
    constraint uq_source_id unique (source, source_id)
);
create index if not exists ix_jobs_score on jobs (score desc);
create index if not exists ix_jobs_company on jobs (company);

create table if not exists job_history (
    id          bigserial primary key,
    job_id      bigint not null references jobs(id) on delete cascade,
    run_id      bigint,
    changed_at  timestamptz not null,
    event       varchar(16),                              -- created | updated | closed | reopened
    changes     jsonb                                     -- {"salary": ["old", "new"], ...}
);

create table if not exists alerts (
    id          bigserial primary key,
    job_id      bigint references jobs(id) on delete cascade,
    run_id      bigint,
    channel     varchar(80),
    kind        varchar(16),                              -- job | digest | test
    status      varchar(16),                              -- sent | preview | failed
    detail      text,
    payload     jsonb,
    created_at  timestamptz not null
);

-- Next milestones add: candidates, matches, companies, recruiter_leads, applications.
