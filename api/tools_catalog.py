import os, re, requests, json, time
from typing import List, Dict, Any, Optional
from datetime import date, datetime

class CatalogError(Exception): ...

# ── Simple file cache to save free calls ────────────────────────────────────────
_CACHE_DIR = "data/.cache_catalog"
_CACHE_TTL_SEC = int(os.getenv("CATALOG_CACHE_TTL_SEC", "86400"))  # 24h default

def _ensure_cache_dir():
    try:
        os.makedirs(_CACHE_DIR, exist_ok=True)
    except Exception:
        pass

def _cache_key(provider: str, q: str, budget: Optional[float], deadline_iso: Optional[str],
               prime_only: bool, zip_code: Optional[str]) -> str:
    return re.sub(r"[^a-z0-9._-]+", "_", f"{provider}|{q}|{budget}|{deadline_iso}|{prime_only}|{zip_code}").lower()

def _cache_get(key: str) -> Optional[List[Dict[str, Any]]]:
    _ensure_cache_dir()
    path = os.path.join(_CACHE_DIR, key + ".json")
    if not os.path.exists(path):
        return None
    try:
        if time.time() - os.path.getmtime(path) > _CACHE_TTL_SEC:
            return None
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return None

def _cache_set(key: str, value: List[Dict[str, Any]]):
    _ensure_cache_dir()
    path = os.path.join(_CACHE_DIR, key + ".json")
    try:
        with open(path, "w") as f:
            json.dump(value, f)
    except Exception:
        pass
# ───────────────────────────────────────────────────────────────────────────────

def _norm_price(s: Any) -> Optional[float]:
    if s is None: return None
    if isinstance(s, (int, float)): return float(s)
    m = re.search(r"(\d+(?:\.\d+)?)", str(s).replace(",", ""))
    return float(m.group(1)) if m else None

def _days_until(deadline_iso: Optional[str]) -> Optional[int]:
    if not deadline_iso: return None
    try:
        y, m, d = map(int, deadline_iso.split("-"))
        return max((date(y, m, d) - date.today()).days, 0)
    except Exception:
        return None

def _delivery_days_from_est(d: Optional[str]) -> Optional[int]:
    if not d: return None
    try:
        if "T" in d:
            dt = datetime.fromisoformat(d.replace("Z", ""))
            return max((dt.date() - date.today()).days, 0)
        y, m, dd = map(int, d.split("-"))
        return max((date(y, m, dd) - date.today()).days, 0)
    except Exception:
        return None

def search_products(query: str,
                    budget: Optional[float] = None,
                    deadline_iso: Optional[str] = None,
                    prime_only: bool = True,
                    provider: Optional[str] = None,
                    zip_code: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Rainforest API → normalized list:
    {asin,title,price,prime,delivery_days,rating,reviews,image,url}
    """
    provider = "rainforest"  # locked to Rainforest for your build
    key = os.getenv("RAINFOREST_API_KEY")
    if not key:
        raise CatalogError("missing_rainforest_key")

    # cache guard
    cache_k = _cache_key(provider, query, budget, deadline_iso, prime_only, zip_code)
    cached = _cache_get(cache_k)
    if cached is not None:
        return cached

    # call Rainforest
    params = {
        "api_key": key,
        "type": "search",
        "amazon_domain": "amazon.com",
        "search_term": query,
    }
    r = requests.get("https://api.rainforestapi.com/request", params=params, timeout=12)
    if r.status_code != 200:
        raise CatalogError(f"rainforest_http_{r.status_code}")
    data = r.json()

    deadline_days = _days_until(deadline_iso)
    results = (data.get("search_results") or [])[:25]
    items: List[Dict[str, Any]] = []

    for it in results:
        asin  = it.get("asin")
        title = it.get("title")
        url   = it.get("link")
        img   = (it.get("image") or {}).get("link") if isinstance(it.get("image"), dict) else it.get("image")

        # --- price with fallbacks ---
        price = None
        # preferred
        if isinstance(it.get("prices"), list) and it["prices"]:
            p0 = it["prices"][0]
            if isinstance(p0, dict):
                price = p0.get("value")
        if price is None:
            price = it.get("price")
        # buybox fallback
        if price is None and isinstance(it.get("buybox_winner"), dict):
            bb = it["buybox_winner"]
            price = (bb.get("price", {}) or {}).get("value") if isinstance(bb.get("price"), dict) else bb.get("price")
        # offers fallback
        if price is None and isinstance(it.get("offers"), list) and it["offers"]:
            off0 = it["offers"][0]
            if isinstance(off0, dict):
                pval = off0.get("price", {}).get("value") if isinstance(off0.get("price"), dict) else off0.get("price")
                price = pval if pval is not None else price

        rating  = it.get("rating")
        reviews = it.get("ratings_total") or 0
        prime   = bool(it.get("is_prime") or it.get("is_prime_delivery", False))

        # --- delivery ETA days ---
        delivery_days = None
        delivery_info = it.get("delivery") or {}
        est_date = None
        if isinstance(delivery_info, dict):
            for k in ("estimated_delivery_date", "estimated_arrival_date", "expected_delivery_date"):
                if delivery_info.get(k):
                    est_date = delivery_info.get(k)
                    break
        delivery_days = _delivery_days_from_est(est_date)

        # heuristic only if we *have* a deadline and no ETA days were given
        if delivery_days is None and deadline_days is not None:
            delivery_days = 1 if prime else 4

        if not title or not url:
            continue

        items.append({
            "asin": str(asin) if asin else "",
            "title": title,
            "price": _norm_price(price),
            "prime": prime,
            "delivery_days": delivery_days,
            "rating": _norm_price(rating),
            "reviews": int(_norm_price(reviews) or 0),
            "image": img,
            "url": url
        })

    # ── filters (be permissive with unknowns) ───────────────────────────────────
    out: List[Dict[str, Any]] = []
    for p in items:
        # only filter by budget if we *have* a numeric price
        if budget is not None and (p["price"] is not None) and (p["price"] > budget):
            continue
        if prime_only and not p["prime"]:
            continue
        # only drop for deadline if we *know* delivery_days and it's too slow
        if deadline_days is not None and (p["delivery_days"] is not None) and (p["delivery_days"] > deadline_days):
            continue
        out.append(p)

    # de-dup by ASIN/title
    dedup: Dict[str, Dict[str, Any]] = {}
    for p in out:
        key_ = p["asin"] or p["title"]
        if key_ not in dedup:
            dedup[key_] = p

    final = list(dedup.values())[:20]
    _cache_set(cache_k, final)
    return final