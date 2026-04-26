#!/usr/bin/env python3
"""
Synthetic data generator for the Saudi Market Trends platform.

Hackathon premise: real social-media APIs are gated/expensive. This script
fabricates data that has the same SHAPE as the real thing, with deliberate
trend scenarios baked in so each engine in ARCHITECTURE.md has something to
detect.

Scenarios (see data/synthetic/README.md for details):
  Short-term  : viral cafe (cafe_nakhla, 2026-04-10), viral dance (2026-03-05)
  Long-term   : padel, EVs, healthy meals, matcha (rising); shisha (declining)
  Seasonal Hijri      : tamr, qamar al-deen (Ramadan); ihram (Hajj)
  Seasonal Gregorian  : KSA flag merch (National Day), Founding Day merch
  Noise control       : single-platform bot spike (must be filtered out)

Deterministic via SEED. Re-run any time:  python3 tools/generate_synthetic_data.py
"""

import csv
import json
import math
import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "synthetic"
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "raw").mkdir(exist_ok=True)

SEED = 42
random.seed(SEED)

START = date(2024, 1, 1)
END = date(2026, 4, 26)

SOCIAL_SOURCES = ["x", "tiktok", "instagram", "snapchat"]
SOURCE_SHARE = {"x": 0.30, "tiktok": 0.30, "instagram": 0.22, "snapchat": 0.18}

KSA_REGIONS = [
    ("Riyadh", "Riyadh", 0.35),
    ("Makkah", "Jeddah", 0.22),
    ("Makkah", "Makkah", 0.08),
    ("Eastern", "Dammam", 0.12),
    ("Eastern", "Khobar", 0.06),
    ("Madinah", "Madinah", 0.05),
    ("Asir", "Abha", 0.04),
    ("Qassim", "Buraydah", 0.04),
    ("Tabuk", "Tabuk", 0.02),
    ("Hail", "Hail", 0.02),
]

# --- Hijri approximation (synthetic-data quality, not legal-quality) ---
# Algorithm: Kuwaiti / arithmetic Hijri, good enough to tag every record.
# Real seasonal anchors below (Ramadan/Hajj windows) are hardcoded from the
# Umm al-Qura calendar so the seasonal engine will find clean patterns.
def gregorian_to_hijri(g: date) -> tuple[int, int, int]:
    jd = g.toordinal() + 1721425  # Julian day number
    jd = jd - 1948440 + 10632
    n = (jd - 1) // 10631
    jd = jd - 10631 * n + 354
    j = ((10985 - jd) // 5316) * ((50 * jd) // 17719) + (jd // 5670) * ((43 * jd) // 15238)
    jd = jd - ((30 - j) // 15) * ((17719 * j) // 50) - (j // 16) * ((15238 * j) // 43) + 29
    m = (24 * jd) // 709
    d = jd - (709 * m) // 24
    y = 30 * n + j - 30
    return y, m, d


def hijri_str(g: date) -> str:
    y, m, d = gregorian_to_hijri(g)
    return f"{y:04d}-{m:02d}-{d:02d}"


# --- KSA event windows (Gregorian; Ramadan/Hajj from Umm al-Qura) ---
EVENTS = {
    "ramadan": [
        (date(2024, 3, 11), date(2024, 4, 9)),
        (date(2025, 2, 28), date(2025, 3, 30)),
        (date(2026, 2, 18), date(2026, 3, 19)),
    ],
    # Last 10 nights + Eid week — fashion/Eid-clothing peak
    "ramadan_late": [
        (date(2024, 3, 31), date(2024, 4, 16)),
        (date(2025, 3, 20), date(2025, 4, 6)),
        (date(2026, 3, 10), date(2026, 3, 26)),
    ],
    "hajj": [
        (date(2024, 6, 14), date(2024, 6, 19)),
        (date(2025, 6, 4),  date(2025, 6, 9)),
    ],
    "national_day": [  # Sep 23, 1-week halo
        (date(2024, 9, 18), date(2024, 9, 26)),
        (date(2025, 9, 18), date(2025, 9, 26)),
    ],
    "founding_day": [  # Feb 22
        (date(2024, 2, 18), date(2024, 2, 26)),
        (date(2025, 2, 18), date(2025, 2, 26)),
        (date(2026, 2, 18), date(2026, 2, 26)),
    ],
    "riyadh_season": [  # Oct - Mar
        (date(2024, 10, 12), date(2025, 3, 15)),
        (date(2025, 10, 12), date(2026, 3, 15)),
    ],
}


@dataclass
class Entity:
    id: str
    name_ar: str
    name_en: str
    category: str
    baseline: float            # daily mentions baseline
    growth_pct_year: float     # long-term slope
    volatility: float          # noise multiplier
    seasonal_event: str | None = None  # key into EVENTS
    seasonal_lift: float = 0.0         # multiplier at peak
    seasonal_calendar: str = "none"    # 'hijri' | 'gregorian' | 'none'
    viral_event: dict | None = None    # {date, peak_multiplier, decay_days}
    bot_spike: dict | None = None      # {date, platform, peak_multiplier, decay_days}


ENTITIES: list[Entity] = [
    # --- Seasonal: Hijri / Ramadan ---
    Entity("dates_tamr", "تمر", "dates", "food", 220, 3, 0.15,
           seasonal_event="ramadan", seasonal_lift=4.5, seasonal_calendar="hijri"),
    Entity("qamar_al_deen", "قمر الدين", "qamar al-deen", "food", 60, 2, 0.20,
           seasonal_event="ramadan", seasonal_lift=8.0, seasonal_calendar="hijri"),
    Entity("eid_abaya", "عبايات العيد", "eid abaya", "fashion", 110, 6, 0.18,
           seasonal_event="ramadan_late", seasonal_lift=4.0, seasonal_calendar="hijri"),

    # --- Seasonal: Hijri / Hajj ---
    Entity("ihram", "إحرام", "ihram garments", "fashion", 35, 1, 0.20,
           seasonal_event="hajj", seasonal_lift=6.5, seasonal_calendar="hijri"),

    # --- Seasonal: Gregorian / KSA events ---
    Entity("ksa_flag_merch", "علم السعودية", "saudi flag merch", "merch", 45, 4, 0.15,
           seasonal_event="national_day", seasonal_lift=7.0, seasonal_calendar="gregorian"),
    Entity("founding_day_thobe", "ثوب التأسيس", "founding day thobe", "fashion", 25, 12, 0.20,
           seasonal_event="founding_day", seasonal_lift=6.5, seasonal_calendar="gregorian"),
    Entity("riyadh_season_tickets", "موسم الرياض", "riyadh season", "entertainment", 180, 10, 0.18,
           seasonal_event="riyadh_season", seasonal_lift=2.5, seasonal_calendar="gregorian"),

    # --- Long-term: rising ---
    Entity("padel", "بادل", "padel sports", "sports", 90, 80, 0.18),
    Entity("ev_cars", "سيارات كهربائية", "electric cars", "automotive", 70, 55, 0.20),
    Entity("healthy_meal_delivery", "وجبات صحية", "healthy meal delivery", "food", 160, 35, 0.15),
    Entity("matcha", "ماتشا", "matcha", "food", 25, 120, 0.25),
    Entity("home_workout", "تمارين بيتية", "home workout", "fitness", 80, 25, 0.20),

    # --- Long-term: declining ---
    Entity("shisha_cafe", "كافيهات شيشة", "shisha cafes", "food", 220, -15, 0.15),

    # --- Short-term: viral ---
    Entity("cafe_nakhla", "كافيه نخلة", "cafe nakhla", "food", 18, 5, 0.22,
           viral_event={"date": date(2026, 4, 10), "peak_multiplier": 28, "decay_days": 12}),
    Entity("selah_dance", "رقصة سيلة", "selah dance", "entertainment", 12, 0, 0.30,
           viral_event={"date": date(2026, 3, 5), "peak_multiplier": 45, "decay_days": 9}),

    # --- Stable noise floor ---
    Entity("milk", "حليب", "milk", "food", 480, 1, 0.10),
    Entity("rice", "أرز", "rice", "food", 540, 0, 0.10),

    # --- Single-platform bot spike (cross-platform corroboration MUST reject) ---
    Entity("spam_product_x", "منتج وهمي", "spam product", "noise", 40, 0, 0.20,
           bot_spike={"date": date(2026, 4, 1), "platform": "x",
                      "peak_multiplier": 35, "decay_days": 6}),
]


# --- Helpers ---
def in_window(d: date, windows: list[tuple[date, date]]) -> tuple[bool, float]:
    """Return (inside, position-in-window 0..1) for the first matching window."""
    for start, stop in windows:
        if start <= d <= stop:
            span = max(1, (stop - start).days)
            pos = (d - start).days / span
            return True, pos
        # Halo: 7 days before window starts adds half-strength ramp
        if start - timedelta(days=7) <= d < start:
            pos = (d - (start - timedelta(days=7))).days / 7
            return True, pos * 0.5  # ramp
    return False, 0.0


def seasonal_factor(e: Entity, d: date) -> float:
    if not e.seasonal_event:
        return 1.0
    inside, pos = in_window(d, EVENTS[e.seasonal_event])
    if not inside:
        return 1.0
    # Bell-shaped lift across the window
    bell = math.exp(-((pos - 0.5) ** 2) / 0.08)
    return 1.0 + (e.seasonal_lift - 1.0) * bell


def viral_factor(event: dict | None, d: date) -> float:
    if not event:
        return 1.0
    delta = (d - event["date"]).days
    if delta < -2 or delta > event["decay_days"] * 3:
        return 1.0
    if delta < 0:  # tiny pre-buzz
        return 1.0 + 0.15 * (delta + 2) / 2
    # Exponential decay from peak
    return 1.0 + (event["peak_multiplier"] - 1) * math.exp(-delta / event["decay_days"])


def growth_factor(e: Entity, d: date) -> float:
    years = (d - START).days / 365.25
    return (1.0 + e.growth_pct_year / 100.0) ** years


def daily_mentions(e: Entity, d: date) -> float:
    base = e.baseline * growth_factor(e, d) * seasonal_factor(e, d)
    base *= viral_factor(e.viral_event, d)
    # Weekly seasonality: Fri/Sat (KSA weekend) = +20%
    if d.weekday() in (4, 5):
        base *= 1.2
    noise = random.lognormvariate(0, e.volatility)
    return max(0.0, base * noise)


def split_across_platforms(total: float, e: Entity, d: date) -> dict[str, float]:
    out = {p: total * SOURCE_SHARE[p] for p in SOCIAL_SOURCES}
    # Single-platform bot spike injection
    if e.bot_spike:
        delta = (d - e.bot_spike["date"]).days
        if 0 <= delta <= e.bot_spike["decay_days"] * 3:
            extra = e.baseline * (e.bot_spike["peak_multiplier"] - 1) * \
                    math.exp(-delta / e.bot_spike["decay_days"])
            out[e.bot_spike["platform"]] += extra
    return out


# --- Sample post text (Saudi-dialect templates with English code-switching) ---
TEMPLATES_AR = [
    "وش رايكم في {name}؟ صراحة عجيب 🔥",
    "اليوم جربت {name} ومدري ليش الكل يحبه",
    "يا جماعة {name} صار ترند، شريتوا؟",
    "احسن {name} في {city} وين يا اخوان",
    "ما توقعت {name} بهالشكل، فعلاً يستاهل",
    "{name} مع القهوة يجنن، ينصح فيه",
    "تجربتي مع {name} اليوم خرافية",
    "اخواني نصحوني ب {name}، فيه احد جربه؟",
    "{name} رهيب والله، الكل يتكلم عنه",
    "حلو {name} بس الاسعار شوي",
]
TEMPLATES_MIX = [
    "{name} is honestly amazing, الكل يتكلم عنه",
    "Just tried {name} في {city} — must try",
    "{name} trending again 😅 وش السالفة",
    "Me and the bros at {name} وقت حلو",
    "{name} + matcha = vibes صدقوني",
]


def make_post(e: Entity, d: date, source: str, idx: int) -> dict:
    region, city, _ = random.choices(KSA_REGIONS, weights=[w for *_, w in KSA_REGIONS])[0]
    if random.random() < 0.18:
        text = random.choice(TEMPLATES_MIX).format(name=e.name_ar, city=city)
        lang = "ar-en"
    else:
        text = random.choice(TEMPLATES_AR).format(name=e.name_ar, city=city)
        lang = "ar-sa"
    likes = max(0, int(random.lognormvariate(3.5, 1.2)))
    return {
        "id": f"{source}_{e.id}_{d.isoformat()}_{idx}",
        "source": source,
        "ts_gregorian": f"{d.isoformat()}T{random.randint(8,23):02d}:{random.randint(0,59):02d}:00Z",
        "ts_hijri": hijri_str(d),
        "author_id": f"u_{random.randint(10000, 99999)}",
        "lang": lang,
        "text": text,
        "hashtags": [f"#{e.name_ar}".replace(" ", "_")],
        "engagement": {
            "likes": likes,
            "shares": int(likes * random.uniform(0.05, 0.20)),
            "comments": int(likes * random.uniform(0.02, 0.10)),
        },
        "geo": {"region": region, "city": city},
        "entity_hint": e.id,  # ground truth — what NLP/entity-linking should resolve to
    }


# --- Main generation ---
def main() -> None:
    days = [START + timedelta(days=i) for i in range((END - START).days + 1)]

    # 1) Daily signals (the time-series feed for trend engines)
    daily_path = OUT / "daily_signals.csv"
    raw_posts_path = OUT / "raw" / "posts.jsonl"
    gtrends_path = OUT / "google_trends_weekly.csv"

    print(f"Generating {len(ENTITIES)} entities × {len(days)} days × "
          f"{len(SOCIAL_SOURCES)} sources …")

    rows: list[dict] = []
    raw_posts: list[dict] = []

    for d in days:
        for e in ENTITIES:
            total = daily_mentions(e, d)
            per_source = split_across_platforms(total, e, d)
            for src, count in per_source.items():
                count_int = int(round(count))
                # Sentiment: drifts slightly with engagement; 0..1
                sent = round(0.55 + random.gauss(0, 0.10), 3)
                sent = max(0.0, min(1.0, sent))
                rows.append({
                    "date_gregorian": d.isoformat(),
                    "date_hijri": hijri_str(d),
                    "entity_id": e.id,
                    "entity_name_ar": e.name_ar,
                    "category": e.category,
                    "source": src,
                    "mentions": count_int,
                    "sentiment": sent,
                })

    # Write daily signals
    with daily_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"  wrote {daily_path.relative_to(ROOT)}  ({len(rows):,} rows)")

    # 2) Sample raw posts: ~2000 records, weighted toward higher-mention days
    weights = [r["mentions"] for r in rows]
    sample_size = 2000
    sampled = random.choices(rows, weights=weights, k=sample_size)
    seen_ids = set()
    for r in sampled:
        e = next(x for x in ENTITIES if x.id == r["entity_id"])
        d = date.fromisoformat(r["date_gregorian"])
        idx = len(seen_ids)
        post = make_post(e, d, r["source"], idx)
        if post["id"] in seen_ids:
            continue
        seen_ids.add(post["id"])
        raw_posts.append(post)

    with raw_posts_path.open("w", encoding="utf-8") as f:
        for p in raw_posts:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    print(f"  wrote {raw_posts_path.relative_to(ROOT)}  ({len(raw_posts):,} posts)")

    # 3) Google Trends-style weekly interest (0..100, normalized per entity)
    weekly: dict[tuple[str, date], float] = {}
    for r in rows:
        d = date.fromisoformat(r["date_gregorian"])
        wk_start = d - timedelta(days=d.weekday())
        key = (r["entity_id"], wk_start)
        weekly[key] = weekly.get(key, 0.0) + r["mentions"]

    # Normalize per entity to 0..100
    by_entity_max: dict[str, float] = {}
    for (eid, _wk), v in weekly.items():
        by_entity_max[eid] = max(by_entity_max.get(eid, 0), v)

    with gtrends_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["week_start", "entity_id", "geo", "interest"])
        for (eid, wk), v in sorted(weekly.items()):
            interest = round(100 * v / by_entity_max[eid], 1) if by_entity_max[eid] else 0
            w.writerow([wk.isoformat(), eid, "SA", interest])
    print(f"  wrote {gtrends_path.relative_to(ROOT)}  ({len(weekly):,} weeks)")

    # 4) Reference files: entity catalog + KSA event calendar
    with (OUT / "entities.json").open("w", encoding="utf-8") as f:
        json.dump(
            [
                {
                    "id": e.id, "name_ar": e.name_ar, "name_en": e.name_en,
                    "category": e.category,
                    "trend_profile": {
                        "baseline": e.baseline,
                        "growth_pct_year": e.growth_pct_year,
                        "volatility": e.volatility,
                        "seasonal_event": e.seasonal_event,
                        "seasonal_calendar": e.seasonal_calendar,
                        "seasonal_lift": e.seasonal_lift,
                        "viral_event": (
                            {**e.viral_event, "date": e.viral_event["date"].isoformat()}
                            if e.viral_event else None
                        ),
                        "bot_spike": (
                            {**e.bot_spike, "date": e.bot_spike["date"].isoformat()}
                            if e.bot_spike else None
                        ),
                    },
                }
                for e in ENTITIES
            ],
            f, ensure_ascii=False, indent=2,
        )
    print(f"  wrote {(OUT / 'entities.json').relative_to(ROOT)}")

    with (OUT / "events_calendar.json").open("w", encoding="utf-8") as f:
        json.dump(
            {
                k: [[s.isoformat(), e.isoformat()] for s, e in v]
                for k, v in EVENTS.items()
            },
            f, indent=2,
        )
    print(f"  wrote {(OUT / 'events_calendar.json').relative_to(ROOT)}")

    print("\nDone. Synthetic data ready under data/synthetic/.")


if __name__ == "__main__":
    main()
