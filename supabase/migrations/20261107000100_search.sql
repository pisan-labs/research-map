-- Record-level hybrid search, mirroring web/search.js: each record scores
-- alpha * meaning + (1 - alpha) * keyword (both scaled to the best record for
-- the query), times a weight per record kind; a person's score is their best
-- 8 records with weights 1, 0.7, 0.49, ...; the top 3 records are evidence.
-- p_qvec: the query embedded with gte-small (normalised); null = keywords only.
create or replace function search_people(
  p_unit text,
  p_query text,
  p_qvec vector(384) default null,
  p_alpha real default 0.5,
  p_limit int default 20,
  p_use_listed boolean default true
)
returns table (person_id text, score real, evidence jsonb)
language sql stable
as $$
  with q as (
    -- OR of the query's terms: long project descriptions should not require every word.
    select nullif(replace(plainto_tsquery('english', p_query)::text, '&', '|'), '')::tsquery as tsq,
           coalesce(array_length(regexp_split_to_array(plainto_tsquery('english', p_query)::text, ' & '), 1), 0) as nterms
  ),
  pool as (
    select r.* from search_records r
    where r.unit_slug = p_unit and (p_use_listed or r.kind <> 'listed')
  ),
  kw as (
    select p.id,
           ts_rank_cd(p.tsv, q.tsq, 1)
             -- coverage: share of query terms present, squared for short queries
             * power(
                 (select count(*) from unnest(tsvector_to_array(p.tsv)) t
                   where t = any(tsvector_to_array(to_tsvector('english', p_query))))::real
                 / greatest(q.nterms, 1),
                 case when q.nterms <= 3 then 2 when q.nterms <= 8 then 1 else 0 end) as bm
    from pool p, q
    where q.tsq is not null and p.tsv @@ q.tsq
  ),
  sem as (
    select p.id, greatest(0, 1 - (p.embedding <=> p_qvec) - 0.25) as sem
    from pool p
    where p_qvec is not null and p.embedding is not null
    order by p.embedding <=> p_qvec
    limit 500
  ),
  joined as (
    select coalesce(kw.id, sem.id) as id, coalesce(kw.bm, 0) as bm, coalesce(sem.sem, 0) as sem
    from kw full outer join sem on kw.id = sem.id
  ),
  scaled as (
    select j.id,
           -- coalesce: with no query vector every meaning score is 0, and 0/null must not erase the keyword part
           coalesce((case when p_qvec is null then 1 else 1 - p_alpha end) * j.bm / nullif(max(j.bm) over (), 0), 0)
           + coalesce((case when p_qvec is null then 0 else p_alpha end) * j.sem / nullif(max(j.sem) over (), 0), 0) as s
    from joined j
  ),
  weighted as (
    select r.person_id, r.kind, r.text, r.year, r.venue, r.url,
           coalesce(s.s, 0) * case r.kind when 'keywords' then 1.3 when 'interests' then 1.2 when 'topic' then 0.8
                                          when 'bio' then 0.5 else 1.0 end as s
    from scaled s join search_records r on r.id = s.id
  ),
  ranked as (
    select w.*, row_number() over (partition by w.person_id order by w.s desc) as k from weighted w where w.s > 0
  )
  select person_id,
         sum(s * power(0.7, k - 1))::real as score,
         jsonb_agg(jsonb_build_object('kind', kind, 'text', text, 'year', year, 'venue', venue, 'url', url)
                   order by k) filter (where k <= 3) as evidence
  from ranked
  where k <= 8
  group by person_id
  order by score desc
  limit p_limit
$$;

grant execute on function search_people(text, text, vector, real, int, boolean) to anon, authenticated;
