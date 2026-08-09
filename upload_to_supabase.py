"""Upload article_embeddings.parquet into the Supabase `products` table.

Table schema (public.products):
    article_id  bigint
    embedding   vector
    metadata    jsonb
"""
import json
import os
import sys
import time
from pathlib import Path

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from dotenv import dotenv_values

ROOT = Path(__file__).parent
env = dotenv_values(ROOT / ".env")

PWD = env["supabase_pwd"].strip('"')
# Direct db.* hostname isn't resolvable from many networks (IPv6-only).
# Use Supabase Transaction/Session pooler instead.
HOST = "aws-0-ca-central-1.pooler.supabase.com"
PORT = 5432
USER = "postgres.doeusznqumkptwcjjwhj"
DB = "postgres"

PARQUET = ROOT / "article_embeddings.parquet"
ARTICLES_CSV = ROOT / "h-and-m-personalized-fashion-recommendations" / "articles.csv"

BATCH = 1000
META_COLS = [
    "prod_name",
    "product_type_name",
    "product_group_name",
    "colour_group_name",
    "department_name",
    "index_name",
    "section_name",
    "garment_group_name",
    "detail_desc",
]


def vec_literal(arr):
    # pgvector accepts a string literal like '[0.1,0.2,...]'
    return "[" + ",".join(f"{float(x):.6f}" for x in arr) + "]"


def main():
    print("Loading parquet...")
    emb = pd.read_parquet(PARQUET)
    print(f"  {len(emb):,} embedding rows, dim={len(emb['embedding'].iloc[0])}")

    print("Loading articles metadata...")
    meta = pd.read_csv(ARTICLES_CSV, usecols=["article_id", *META_COLS])
    meta = meta.set_index("article_id")

    print("Connecting to Supabase...")
    conn = psycopg2.connect(
        host=HOST, port=PORT, dbname=DB, user=USER, password=PWD, sslmode="require"
    )
    conn.autocommit = False
    cur = conn.cursor()

    # Optional: wipe existing rows to make this idempotent.
    if "--truncate" in sys.argv:
        print("Truncating public.products ...")
        cur.execute("TRUNCATE public.products")
        conn.commit()

    sql = (
        "INSERT INTO public.products (article_id, embedding, metadata) "
        "VALUES %s "
        "ON CONFLICT (article_id) DO NOTHING"
    )
    # If there's no unique constraint on article_id, ON CONFLICT will error.
    # Fall back to plain insert in that case.
    try:
        cur.execute(
            "SELECT 1 FROM pg_indexes WHERE tablename='products' "
            "AND indexdef ILIKE '%UNIQUE%article_id%'"
        )
        has_unique = cur.fetchone() is not None
    except Exception:
        has_unique = False
    if not has_unique:
        sql = (
            "INSERT INTO public.products (article_id, embedding, metadata) VALUES %s"
        )

    total = len(emb)
    start = time.time()
    inserted = 0
    rows_buf = []

    for i, row in enumerate(emb.itertuples(index=False)):
        aid = int(row.article_id)
        md_row = meta.loc[aid].to_dict() if aid in meta.index else {}
        md_row = {k: (None if pd.isna(v) else v) for k, v in md_row.items()}
        rows_buf.append((aid, vec_literal(row.embedding), json.dumps(md_row)))

        if len(rows_buf) >= BATCH:
            execute_values(cur, sql, rows_buf, template="(%s, %s::vector, %s::jsonb)")
            conn.commit()
            inserted += len(rows_buf)
            rows_buf.clear()
            elapsed = time.time() - start
            rate = inserted / elapsed
            eta = (total - inserted) / rate if rate else 0
            print(
                f"  {inserted:,}/{total:,}  ({rate:,.0f} rows/s, ETA {eta:5.0f}s)",
                flush=True,
            )

    if rows_buf:
        execute_values(cur, sql, rows_buf, template="(%s, %s::vector, %s::jsonb)")
        conn.commit()
        inserted += len(rows_buf)

    cur.execute("SELECT COUNT(*) FROM public.products")
    print(f"Done. Inserted {inserted:,}. Table row count: {cur.fetchone()[0]:,}")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
