"""End-to-end smoke test of the recommender loop against localhost:8000."""
import json
import sys
import urllib.request

BASE = "http://localhost:8000"


def req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    r = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(r) as resp:
        raw = resp.read().decode()
        return json.loads(raw) if raw else None


def show(label, recs):
    print(f"\n== {label} ==")
    for r in recs:
        m = r["metadata"]
        print(
            f"  {r['article_id']}  sim={r['similarity']:.4f}  "
            f"{m.get('prod_name')} | {m.get('product_type_name')} | {m.get('index_group_name')}"
        )


def main():
    prof = req("POST", "/profiles/fork?category=Menswear")
    pid = prof["id"]
    print(f"PID = {pid}")

    init = req("GET", f"/profiles/{pid}/recommendations?limit=5")
    show("Initial recs", init)
    init_ids = [r["article_id"] for r in init]

    like_id = init_ids[0]
    print(f"\n>> like {like_id}")
    req("POST", f"/profiles/{pid}/interactions", {"article_id": like_id, "type": "like"})

    after_like = req("GET", f"/profiles/{pid}/recommendations?limit=5")
    show("After like", after_like)
    after_like_ids = [r["article_id"] for r in after_like]
    print(f"  shifted? {init_ids != after_like_ids}")

    cart_id = after_like_ids[1]  # pick 2nd so cart != like, more visible
    print(f"\n>> cart {cart_id}")
    req("POST", f"/profiles/{pid}/interactions", {"article_id": cart_id, "type": "cart"})

    after_cart = req("GET", f"/profiles/{pid}/recommendations?limit=5")
    show(f"After cart ({cart_id} should be absent)", after_cart)
    print(f"  {cart_id} excluded? {cart_id not in [r['article_id'] for r in after_cart]}")

    prof_state = req("GET", f"/profiles/{pid}")
    print(f"\n== Profile state ==\n  {prof_state}")

    reset = req("POST", f"/profiles/{pid}/reset")
    print(f"\n>> reset -> interaction_count={reset['interaction_count']}")

    after_reset = req("GET", f"/profiles/{pid}/recommendations?limit=5")
    show("After reset (should match initial)", after_reset)
    after_reset_ids = [r["article_id"] for r in after_reset]
    print(f"  matches initial? {init_ids == after_reset_ids}")

    req("DELETE", f"/profiles/{pid}")
    print("\n>> deleted profile. done.")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode()}", file=sys.stderr)
        sys.exit(1)
