import math, re
from typing import List, Dict, Any, Optional

WEIGHTS = dict(quality=0.40, delivery=0.30, value=0.20, match=0.10)

def _safe(v, d=0.0):
    try: return float(v)
    except Exception: return d

def _quality(rating: Optional[float], reviews: Optional[int]) -> float:
    r = _safe(rating, 0.0)
    n = max(int(_safe(reviews, 0)), 0)
    return max(0.0, min(1.0, (r/5.0) * (math.log10(n+1)/math.log10(10000))))

def _delivery(delivery_days: Optional[int]) -> float:
    if delivery_days is None: return 0.5
    if delivery_days <= 0: return 1.0
    if delivery_days == 1: return 0.85
    if delivery_days == 2: return 0.70
    if delivery_days == 3: return 0.55
    return max(0.1, 0.55 - 0.1*(delivery_days-3))

def _value(price: Optional[float], prices: List[Optional[float]]) -> float:
    valid = [p for p in prices if p is not None and p > 0]
    if not valid or price is None or price <= 0: return 0.5
    pmin, pmax = min(valid), max(valid)
    if pmax == pmin: return 0.7
    return max(0.1, 1.0 - (price - pmin)/(pmax - pmin) * 0.9)

def _match(title: str, query: str) -> float:
    if not title or not query: return 0.5
    q = query.lower(); t = title.lower()
    tokens = set(re.findall(r"[a-z0-9]+", q))
    hits = sum(1 for tok in tokens if tok in t)
    return max(0.1, min(1.0, hits/max(1, len(tokens))))

def score_products(candidates: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
    prices = [c.get("price") for c in candidates]
    scored = []
    for c in candidates:
        s_quality = _quality(c.get("rating"), c.get("reviews"))
        s_delivery= _delivery(c.get("delivery_days"))
        s_value   = _value(c.get("price"), prices)
        s_match   = _match(c.get("title",""), query)
        total = (WEIGHTS["quality"]*s_quality +
                 WEIGHTS["delivery"]*s_delivery +
                 WEIGHTS["value"]  *s_value +
                 WEIGHTS["match"]  *s_match)
        c_out = dict(c)
        c_out["scores"] = {
            "quality": round(s_quality, 3),
            "delivery": round(s_delivery, 3),
            "value": round(s_value, 3),
            "match": round(s_match, 3),
            "total": round(total, 3)
        }
        scored.append(c_out)
    scored.sort(key=lambda x: x["scores"]["total"], reverse=True)
    return scored