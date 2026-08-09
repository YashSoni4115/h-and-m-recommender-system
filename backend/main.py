"""FastAPI entrypoint for the H&M recommender backend."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from recommendations import router as recommendations_router
from supabase_client import get_supabase

app = FastAPI(
    title="H&M Recommender API",
    version="0.1.0",
    description="Backend service serving article recommendations.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(recommendations_router)


@app.get("/")
def root():
    return {"status": "ok", "service": "h-and-m-recommender"}


@app.get("/health")
def health():
    """Basic health check that also verifies Supabase connectivity."""
    try:
        client = get_supabase()
        res = client.table("products").select("*", count="exact").limit(1).execute()
        return {
            "status": "ok",
            "supabase": "connected",
            "products_count": res.count,
        }
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Supabase error: {exc}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
