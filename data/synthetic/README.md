# Synthetic dataset

Hackathon stand-in for the real ingestion sources described in [`ARCHITECTURE.md`](../../ARCHITECTURE.md).
Same shape as real data; deliberately seeded so each engine in the architecture has something to detect.

Regenerate any time:

```bash
python3 tools/generate_synthetic_data.py
```

Deterministic — same SEED produces identical files.

## Files

| File | Shape | Purpose |
|---|---|---|
| `daily_signals.csv` | `date_gregorian, date_hijri, entity_id, entity_name_ar, category, source, mentions, sentiment` | Time-series feed for the three trend engines. ~61k rows over 2024-01-01 → 2026-04-26, 18 entities × 4 social sources × 847 days. |
| `raw/posts.jsonl` | One social post per line (X/TikTok/IG/Snap) — Arabic + Saudi-dialect text, code-switching, geo, engagement | Sample input for the NLP / entity-linking layer. ~2k posts, weighted toward high-mention days. |
| `google_trends_weekly.csv` | `week_start, entity_id, geo, interest (0..100)` | KSA-scoped weekly interest, normalized per entity (Google Trends-style). |
| `entities.json` | Entity catalog with trend profile (baseline, growth, seasonality, viral/bot config) | Ground truth — lets evaluation compare what the engines find vs. what was injected. |
| `events_calendar.json` | KSA event windows (Ramadan, Hajj, National Day, Founding Day, Riyadh Season) | Anchors for the seasonal engine. Ramadan / Hajj from Umm al-Qura. |

## Baked-in scenarios

Each scenario maps to one component of the architecture. If an engine can't surface its scenario, that engine has a bug.

### Short-term (engine: z-score / EWMA + cross-platform corroboration)

| Entity | Peak date | Profile |
|---|---|---|
| `cafe_nakhla` (كافيه نخلة) | 2026-04-10 | 25 → ~1000 mentions/day, decay over ~2 weeks. **Should fire across X + TikTok + IG + Snapchat.** |
| `selah_dance` (رقصة سيلة) | 2026-03-05 | 12 → ~500 mentions/day, sharp 9-day decay. |

### Long-term (engine: STL / Mann-Kendall slope)

| Entity | Direction | Profile |
|---|---|---|
| `padel`, `ev_cars`, `matcha`, `healthy_meal_delivery`, `home_workout` | rising | +25% to +120% YoY |
| `shisha_cafe` | declining | −15% YoY |

### Seasonal — Hijri calendar (engine: dual-axis decomposition)

The seasonal engine MUST run STL on the Hijri axis to find these cleanly — they smear when only Gregorian is used because Ramadan moves ~10 days/year.

| Entity | Anchor | Lift |
|---|---|---|
| `dates_tamr` (تمر) | Ramadan | ~4.5× baseline at peak |
| `qamar_al_deen` (قمر الدين) | Ramadan | ~8× |
| `eid_abaya` (عبايات العيد) | Ramadan last 10 nights + Eid week | ~4× |
| `ihram` (إحرام) | Hajj | ~6.5× |

### Seasonal — Gregorian / KSA events (engine: same, Gregorian axis)

| Entity | Anchor | Lift |
|---|---|---|
| `ksa_flag_merch` (علم السعودية) | Sep 23 (National Day) | ~7× |
| `founding_day_thobe` (ثوب التأسيس) | Feb 22 (Founding Day) | ~6.5× |
| `riyadh_season_tickets` (موسم الرياض) | Oct–Mar (Riyadh Season) | ~2.5× sustained |

### Noise / control

| Entity | Purpose |
|---|---|
| `milk`, `rice` | Stable noise floor — should NOT trigger any trend. |
| `spam_product_x` | **Single-platform bot spike** (X-only, ~1300 mentions/day for ~6 days, while TikTok/IG/Snap stay ~10). Cross-platform corroboration MUST reject this — if your short-term engine fires on it, the corroboration check is broken. |

## What's intentionally NOT real

- Hijri timestamps use an arithmetic (Kuwaiti) Hijri calculation — synthetic-quality, not legal-quality. The hardcoded Ramadan/Hajj windows themselves are from Umm al-Qura.
- Post text comes from ~15 Saudi-dialect templates with the entity name slotted in. Realistic enough to test dialect normalization and entity linking, not to train a model.
- Engagement counts are log-normal samples, not platform-accurate.
- Author IDs are random integers; no real users.

## Suggested validation checks

Once the trend engines exist, sanity-test against this dataset:

1. **Short-term**: scan 2026-04-05 → 2026-04-20 — `cafe_nakhla` and `selah_dance` should be in the top short-term trends. `spam_product_x` should NOT be (single-platform).
2. **Long-term**: rank by 12-month slope — top 5 should be `matcha`, `padel`, `ev_cars`, `healthy_meal_delivery`, `home_workout`. Bottom should include `shisha_cafe`.
3. **Seasonal — Hijri**: decompose `dates_tamr` on Hijri axis — peak should land in Ramadan month every year, with low residual variance.
4. **Seasonal — Gregorian**: `ksa_flag_merch` should peak the week of Sep 23 every year.
5. **Discovery score**: `padel` and `matcha` should rank high (rising long-term + low/medium competition); `cafe_nakhla` should rank as a short-term spike opportunity for fast-movers.
