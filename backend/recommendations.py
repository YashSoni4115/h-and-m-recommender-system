"""Profile + recommendation endpoints.

All vector math (nudges) happens as atomic Supabase RPC calls, not
read-modify-write in Python — see backend/sql/002_recommender_rpcs.sql.
"""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from config import BETA, DEFAULT_REC_LIMIT, MAX_REC_LIMIT
from supabase_client import get_supabase

router = APIRouter()


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #


class InteractionIn(BaseModel):
    article_id: int
    type: Literal["like", "cart", "dislike"]


class ProfileOut(BaseModel):
    id: str
    name: Optional[str] = None
    is_preset: bool = False
    seed_source: Optional[str] = None
    forked_from: Optional[str] = None
    interaction_count: int = 0


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _get_profile_row(supabase, profile_id: str) -> dict:
    res = (
        supabase.table("profiles")
        .select("id,name,is_preset,seed_source,forked_from,interaction_count")
        .eq("id", profile_id)
        .execute()
    )
    if not res.data:
        raise HTTPException(404, f"Profile not found: {profile_id}")
    return res.data[0]


def _resolve_seed_vector(supabase, category: Optional[str], preset_id: Optional[str]):
    """Return (seed_vector, seed_source, forked_from).

    Priority: preset_id > category > global default.
    """
    if preset_id:
        res = (
            supabase.table("profiles")
            .select("preference_vector,is_preset")
            .eq("id", preset_id)
            .execute()
        )
        if not res.data or not res.data[0].get("is_preset"):
            raise HTTPException(400, f"Unknown preset: {preset_id}")
        return res.data[0]["preference_vector"], f"preset:{preset_id}", preset_id

    if category:
        res = (
            supabase.table("category_averages")
            .select("avg_vector")
            .eq("index_group_name", category)
            .execute()
        )
        if not res.data:
            raise HTTPException(400, f"Unknown category: {category}")
        return res.data[0]["avg_vector"], f"category:{category}", None

    res = supabase.table("global_state").select("avg_vector").eq("id", 1).execute()
    if not res.data:
        raise HTTPException(500, "global_state row missing")
    return res.data[0]["avg_vector"], "global", None


# --------------------------------------------------------------------------- #
# Profiles
# --------------------------------------------------------------------------- #


@router.get("/profiles/presets", response_model=list[ProfileOut])
def list_presets():
    supabase = get_supabase()
    res = (
        supabase.table("profiles")
        .select("id,name,is_preset,seed_source,forked_from,interaction_count")
        .eq("is_preset", True)
        .execute()
    )
    return res.data or []


@router.get("/profiles/categories")
def list_categories():
    """Cold-start seed options (index_group_name values with counts)."""
    supabase = get_supabase()
    res = (
        supabase.table("category_averages")
        .select("index_group_name,item_count")
        .order("item_count", desc=True)
        .execute()
    )
    return res.data or []


@router.post("/profiles/fork", response_model=ProfileOut)
def fork_profile(
    category: Optional[str] = Query(None, description="index_group_name to seed from"),
    preset_id: Optional[str] = Query(None, description="Preset profile UUID to fork"),
):
    """Create a new user profile seeded from a preset, category avg, or global avg."""
    supabase = get_supabase()
    seed_vec, seed_source, forked_from = _resolve_seed_vector(
        supabase, category, preset_id
    )

    res = supabase.rpc(
        "fork_profile",
        {
            "p_seed_vector": seed_vec,
            "p_seed_source": seed_source,
            "p_forked_from": forked_from,
            "p_name": None,
        },
    ).execute()

    new_id = res.data
    return _get_profile_row(supabase, new_id)


@router.get("/profiles/{profile_id}", response_model=ProfileOut)
def get_profile(profile_id: str):
    return _get_profile_row(get_supabase(), profile_id)


@router.delete("/profiles/{profile_id}")
def delete_profile(profile_id: str):
    supabase = get_supabase()
    row = _get_profile_row(supabase, profile_id)
    if row["is_preset"]:
        raise HTTPException(403, "Cannot delete a preset profile.")
    supabase.table("profiles").delete().eq("id", profile_id).execute()
    return {"deleted": profile_id}


@router.post("/profiles/{profile_id}/reset", response_model=ProfileOut)
def reset_profile(profile_id: str):
    """Reset preference_vector to the current value of its seed source.

    Uses seed_source ('global' | 'category:X' | 'preset:<uuid>') to look up
    the fresh seed vector, so a reset today reflects any drift since the
    profile was first forked.
    """
    supabase = get_supabase()
    row = _get_profile_row(supabase, profile_id)
    if row["is_preset"]:
        raise HTTPException(403, "Cannot reset a preset profile.")

    src: str = row.get("seed_source") or "global"
    if src.startswith("preset:"):
        seed_vec, _, _ = _resolve_seed_vector(supabase, None, src.split(":", 1)[1])
    elif src.startswith("category:"):
        seed_vec, _, _ = _resolve_seed_vector(supabase, src.split(":", 1)[1], None)
    else:
        seed_vec, _, _ = _resolve_seed_vector(supabase, None, None)

    supabase.table("profiles").update(
        {"preference_vector": seed_vec, "interaction_count": 0}
    ).eq("id", profile_id).execute()

    # Cascade wipes interactions rows via FK on delete? interactions has
    # ON DELETE CASCADE against profiles(id) but we're not deleting — clear manually.
    supabase.table("interactions").delete().eq("profile_id", profile_id).execute()

    return _get_profile_row(supabase, profile_id)


# --------------------------------------------------------------------------- #
# Interactions
# --------------------------------------------------------------------------- #


@router.post("/profiles/{profile_id}/interactions")
def add_interaction(profile_id: str, payload: InteractionIn):
    supabase = get_supabase()
    row = _get_profile_row(supabase, profile_id)
    if row["is_preset"]:
        raise HTTPException(403, "Preset profiles are immutable.")

    # 1. Log the interaction row.
    supabase.table("interactions").insert(
        {
            "profile_id": profile_id,
            "article_id": payload.article_id,
            "type": payload.type,
        }
    ).execute()

    # 2. Nudge this profile's vector (atomic).
    #    Negative beta for dislike moves the profile *away* from the item.
    signed_beta = -BETA if payload.type == "dislike" else BETA
    supabase.rpc(
        "nudge_profile_vector",
        {
            "p_profile_id": profile_id,
            "p_article_id": payload.article_id,
            "p_beta": signed_beta,
        },
    ).execute()

    # 3. Nudge the global average — only positive signals (like/cart) count.
    #    Dislikes are personal noise, not a crowd trend.
    if payload.type != "dislike":
        supabase.rpc(
            "nudge_global_vector", {"p_article_id": payload.article_id}
        ).execute()

    return {"ok": True}


# --------------------------------------------------------------------------- #
# Recommendations
# --------------------------------------------------------------------------- #


@router.get("/profiles/{profile_id}/recommendations")
def get_recommendations(
    profile_id: str,
    limit: int = Query(DEFAULT_REC_LIMIT, ge=1, le=MAX_REC_LIMIT),
):
    supabase = get_supabase()

    prof = (
        supabase.table("profiles")
        .select("preference_vector")
        .eq("id", profile_id)
        .execute()
    )
    if not prof.data:
        raise HTTPException(404, f"Profile not found: {profile_id}")
    pref_vec = prof.data[0]["preference_vector"]
    if pref_vec is None:
        raise HTTPException(500, "Profile has no preference_vector.")

    # Exclude carted and disliked items so we don't re-recommend either.
    excluded = (
        supabase.table("interactions")
        .select("article_id")
        .eq("profile_id", profile_id)
        .in_("type", ["cart", "dislike"])
        .execute()
    )
    exclude_ids = [r["article_id"] for r in (excluded.data or [])]

    res = supabase.rpc(
        "match_products",
        {
            "query_vector": pref_vec,
            "match_count": limit,
            "exclude_ids": exclude_ids,
        },
    ).execute()

    return res.data or []


# --------------------------------------------------------------------------- #
# Search (hybrid: keyword filter, then rerank by profile similarity)
# --------------------------------------------------------------------------- #


@router.get("/profiles/{profile_id}/search")
def search(
    profile_id: str,
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(DEFAULT_REC_LIMIT, ge=1, le=MAX_REC_LIMIT),
):
    """Full-text search over prod_name + detail_desc, reranked by cosine
    similarity to the profile's preference_vector."""
    supabase = get_supabase()

    prof = (
        supabase.table("profiles")
        .select("preference_vector")
        .eq("id", profile_id)
        .execute()
    )
    if not prof.data:
        raise HTTPException(404, f"Profile not found: {profile_id}")
    pref_vec = prof.data[0]["preference_vector"]

    excluded = (
        supabase.table("interactions")
        .select("article_id")
        .eq("profile_id", profile_id)
        .in_("type", ["cart", "dislike"])
        .execute()
    )
    exclude_ids = [r["article_id"] for r in (excluded.data or [])]

    res = supabase.rpc(
        "search_products",
        {
            "query": q,
            "query_vector": pref_vec,
            "match_count": limit,
            "exclude_ids": exclude_ids,
        },
    ).execute()

    return res.data or []
