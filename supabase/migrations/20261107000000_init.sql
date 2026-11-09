-- Research map data store. Public, read-only for the anon role (all data is
-- from public directories and OpenAlex); writes only with the service role
-- used by the pipeline.
--
-- Lives in the shared HintWise Supabase project (arktxlrlyceffyozdwhq), so
-- everything is additive and stays inside schema app_research_map (one schema
-- per app, pisanuw/claude-built-apps docs/platform.md section 1). Nothing here
-- touches public or any other app's schema.

create schema if not exists app_research_map;
create extension if not exists vector with schema extensions;
-- Unqualified names below are created in app_research_map; vector resolves from extensions.
set search_path = app_research_map, extensions;

create table units (
  slug text primary key,
  name text not null,
  university text not null,
  openalex_institution text,
  as_of date not null,
  people_count int not null default 0,
  works_count int not null default 0,
  meta jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create table people (
  unit_slug text not null references units(slug) on delete cascade,
  id text not null,
  name text not null,
  title text,
  department text,
  program text,
  keywords text,
  interests text,
  bio text,
  profile_url text,
  orcid text,
  openalex_ids text[] not null default '{}',
  x real, y real,
  area int, topic int,
  sparse boolean not null default false,
  off_map boolean not null default false,
  terms text[] not null default '{}',
  primary key (unit_slug, id)
);

create table works (
  id text primary key,            -- OpenAlex work id (W...)
  title text not null,
  year int,
  venue text,
  url text
);

create table person_works (
  unit_slug text not null,
  person_id text not null,
  work_id text not null references works(id) on delete cascade,
  primary key (unit_slug, person_id, work_id),
  foreign key (unit_slug, person_id) references people(unit_slug, id) on delete cascade
);

create table areas (
  unit_slug text not null references units(slug) on delete cascade,
  level text not null check (level in ('area', 'topic')),
  cluster int not null,
  label text not null,
  x real, y real,
  n int not null,
  primary key (unit_slug, level, cluster)
);

create table neighbours (
  unit_slug text not null,
  person_id text not null,
  other_id text not null,
  rank int not null,
  score real not null,
  shared text[] not null default '{}',
  primary key (unit_slug, person_id, other_id),
  foreign key (unit_slug, person_id) references people(unit_slug, id) on delete cascade
);

-- Search records: the same records web/search.js builds (titles, keywords,
-- interests, bio, topics, listed areas), with full-text and vector indexes
-- for the search Edge Function. embedding: gte-small (384 dims, normalised).
create table search_records (
  id bigint generated always as identity primary key,
  unit_slug text not null,
  person_id text not null,
  kind text not null check (kind in ('title', 'keywords', 'interests', 'bio', 'topic', 'listed')),
  text text not null,
  year int,
  venue text,
  url text,
  tsv tsvector generated always as (to_tsvector('english', text)) stored,
  embedding extensions.vector(384),
  foreign key (unit_slug, person_id) references people(unit_slug, id) on delete cascade
);
create index search_records_unit on search_records (unit_slug);
create index search_records_tsv on search_records using gin (tsv);
create index search_records_embedding on search_records using hnsw (embedding extensions.vector_cosine_ops);

-- Corrections that today live in config files (OpenAlex overrides, area names, opt-outs).
create table overrides (
  id bigint generated always as identity primary key,
  unit_slug text not null references units(slug) on delete cascade,
  kind text not null check (kind in ('openalex', 'label', 'opt_out')),
  person_id text,
  value jsonb not null,
  note text,
  created_at timestamptz not null default now(),
  created_by uuid
);

-- Row-level security: anyone may read; only the service role writes.
alter table units enable row level security;
alter table people enable row level security;
alter table works enable row level security;
alter table person_works enable row level security;
alter table areas enable row level security;
alter table neighbours enable row level security;
alter table search_records enable row level security;
alter table overrides enable row level security;

create policy "public read" on units for select using (true);
create policy "public read" on people for select using (true);
create policy "public read" on works for select using (true);
create policy "public read" on person_works for select using (true);
create policy "public read" on areas for select using (true);
create policy "public read" on neighbours for select using (true);
create policy "public read" on search_records for select using (true);
-- overrides: no public policy (read and written by the pipeline and, later, signed-in editors).

-- Data API access: read-only for anon and authenticated (RLS above still
-- applies); the schema must also be appended to the project's exposed schemas.
grant usage on schema app_research_map to anon, authenticated, service_role;
grant select on all tables in schema app_research_map to anon, authenticated;
grant all on all tables in schema app_research_map to service_role;
grant usage, select on all sequences in schema app_research_map to service_role;
alter default privileges in schema app_research_map grant select on tables to anon, authenticated;
alter default privileges in schema app_research_map grant all on tables to service_role;
alter default privileges in schema app_research_map grant usage, select on sequences to service_role;
alter default privileges in schema app_research_map grant execute on functions to anon, authenticated, service_role;
