-- SQL migrations for the recommender loop.
-- Run these in the Supabase SQL editor in order.

-- 1. category_averages table (for cold-start-by-category).
create table if not exists category_averages (
  index_group_name text primary key,
  avg_vector       vector(384),
  item_count       int
);

-- Populate / refresh it. Safe to re-run after backfill_metadata.py.
insert into category_averages (index_group_name, avg_vector, item_count)
select
  metadata->>'index_group_name' as index_group_name,
  avg(embedding)::vector(384)   as avg_vector,
  count(*)                      as item_count
from products
where metadata->>'index_group_name' is not null
group by metadata->>'index_group_name'
on conflict (index_group_name) do update
  set avg_vector = excluded.avg_vector,
      item_count = excluded.item_count;

-- 2. match_products with optional exclude list (cart items).
--    NULL/empty exclude_ids must short-circuit for the planner to use the
--    vector index (otherwise the query hits a statement timeout).
create or replace function match_products(
  query_vector vector(384),
  match_count  int default 20,
  exclude_ids  bigint[] default '{}'
)
returns table (
  article_id bigint,
  similarity float,
  metadata   jsonb
)
language sql stable
as $$
  select
    p.article_id,
    1 - (p.embedding <=> query_vector) as similarity,
    p.metadata
  from products p
  where exclude_ids is null
     or array_length(exclude_ids, 1) is null
     or not (p.article_id = any(exclude_ids))
  order by p.embedding <=> query_vector
  limit match_count;
$$;

-- Ensure vector index exists so match_products doesn't full-scan.
create index if not exists products_embedding_idx
  on products using ivfflat (embedding vector_cosine_ops) with (lists = 100);

-- 3. Nudge a profile's preference vector toward a product's embedding.
--    Atomic read-modify-write. beta = nudge strength in [0, 1].
--    pgvector has no scalar*vector operator, so we build constant vectors
--    and use element-wise multiplication.
create or replace function nudge_profile_vector(
  p_profile_id uuid,
  p_article_id bigint,
  p_beta       float
)
returns void
language plpgsql
as $$
declare
  item_vec vector(384);
  b real := p_beta::real;
  beta_vec vector(384) := array_fill(b,            array[384])::vector(384);
  keep_vec vector(384) := array_fill(1::real - b,  array[384])::vector(384);
begin
  select embedding into item_vec from products where article_id = p_article_id;
  if item_vec is null then
    raise exception 'Unknown article_id: %', p_article_id;
  end if;

  update profiles
  set preference_vector =
        (keep_vec * preference_vector + beta_vec * item_vec)::vector(384),
      interaction_count = interaction_count + 1
  where id = p_profile_id and coalesce(is_preset, false) = false;
end;
$$;

-- 4. Nudge the global average vector using an online mean update.
--    new_avg = (avg * n + item) / (n + 1)
create or replace function nudge_global_vector(
  p_article_id bigint
)
returns void
language plpgsql
as $$
declare
  item_vec vector(384);
  n int;
  n_vec   vector(384);
  inv_vec vector(384);
begin
  select embedding into item_vec from products where article_id = p_article_id;
  if item_vec is null then
    raise exception 'Unknown article_id: %', p_article_id;
  end if;

  select total_count into n from global_state where id = 1;
  n_vec   := array_fill(n::real,               array[384])::vector(384);
  inv_vec := array_fill(1::real / (n + 1)::real, array[384])::vector(384);

  update global_state
  set avg_vector  = ((avg_vector * n_vec + item_vec) * inv_vec)::vector(384),
      total_count = n + 1
  where id = 1;
end;
$$;

-- Widen vector columns to vector(384) so scalar/vector ops resolve properly
-- and indexes can be created.
alter table profiles     alter column preference_vector type vector(384);
alter table global_state alter column avg_vector        type vector(384);

-- 5. Fork a profile from a seed vector in one atomic call. Returns new id.
create or replace function fork_profile(
  p_seed_vector vector(384),
  p_seed_source text,
  p_forked_from uuid default null,
  p_name        text default null
)
returns uuid
language plpgsql
as $$
declare
  new_id uuid;
begin
  insert into profiles (preference_vector, seed_source, forked_from, name, interaction_count)
  values (p_seed_vector, p_seed_source, p_forked_from, p_name, 0)
  returning id into new_id;
  return new_id;
end;
$$;
