-- Full-text search column + index + hybrid search RPC.

-- 1. tsvector column derived from prod_name + detail_desc in metadata.
alter table products
  add column if not exists search_text tsvector
    generated always as (
      to_tsvector(
        'english',
        coalesce(metadata->>'prod_name', '') || ' ' ||
        coalesce(metadata->>'detail_desc', '')
      )
    ) stored;

create index if not exists products_search_idx
  on products using gin (search_text);

-- 2. Hybrid search: keyword filter, then cosine-similarity rerank against
--    the caller's profile vector. Falls back to plain ts_rank if
--    query_vector is null.
create or replace function search_products(
  query        text,
  query_vector vector(384) default null,
  match_count  int          default 20,
  exclude_ids  bigint[]     default '{}'
)
returns table (
  article_id bigint,
  similarity float,
  rank       float,
  metadata   jsonb
)
language sql stable
as $$
  select
    p.article_id,
    case when query_vector is null
         then null::float
         else 1 - (p.embedding <=> query_vector)
    end as similarity,
    ts_rank(p.search_text, websearch_to_tsquery('english', query)) as rank,
    p.metadata
  from products p
  where p.search_text @@ websearch_to_tsquery('english', query)
    and (
      exclude_ids is null
      or array_length(exclude_ids, 1) is null
      or not (p.article_id = any(exclude_ids))
    )
  order by
    case when query_vector is null then null else p.embedding <=> query_vector end
      asc nulls last,
    ts_rank(p.search_text, websearch_to_tsquery('english', query)) desc
  limit match_count;
$$;
