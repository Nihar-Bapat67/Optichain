"""
======================================================
  Williams-Sonoma Event-Driven Demand Forecasting
  Dataset Generator
======================================================
  Generates:
    1. sales_data.csv           daily SKU-level sales
    2. product_hierarchy.csv    brand -> category -> SKU
    3. events_data.csv          WS-specific events + windows
    4. customer_segments.csv    segment definitions
    5. registry_data.csv        registry signal per SKU per month
======================================================
"""

import pandas as pd
import numpy as np
from datetime import date, timedelta
import random
import os

# ---------------------------------------------
# SEED
# ---------------------------------------------
np.random.seed(42)
random.seed(42)

OUTPUT_DIR = "ws_demand_dataset"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---------------------------------------------
# 1. PRODUCT HIERARCHY
# ---------------------------------------------
print("[step] Building product hierarchy...")

products = {
    # brand_id, brand, category, subcategory, sku_id, sku_name, base_demand, price_tier
    "WS": [
        ("WS", "Williams-Sonoma", "Cookware",   "Cast Iron",     "WS-CI-001", "Le Creuset Dutch Oven 5.5qt",   30, "luxury"),
        ("WS", "Williams-Sonoma", "Cookware",   "Cast Iron",     "WS-CI-002", "Staub Cocotte 4qt",             25, "luxury"),
        ("WS", "Williams-Sonoma", "Cookware",   "Stainless",     "WS-SS-001", "All-Clad D3 10pc Set",          20, "luxury"),
        ("WS", "Williams-Sonoma", "Cookware",   "Stainless",     "WS-SS-002", "Demeyere Atlantis Skillet",     18, "luxury"),
        ("WS", "Williams-Sonoma", "Bakeware",   "Cake Pans",     "WS-BK-001", "Nordic Ware Bundt Pan",         45, "premium"),
        ("WS", "Williams-Sonoma", "Bakeware",   "Sheet Pans",    "WS-BK-002", "USA Pan Half Sheet",            60, "premium"),
        ("WS", "Williams-Sonoma", "Electrics",  "Stand Mixers",  "WS-EL-001", "KitchenAid Artisan 5qt",        35, "luxury"),
        ("WS", "Williams-Sonoma", "Electrics",  "Blenders",      "WS-EL-002", "Vitamix A3500",                 15, "luxury"),
        ("WS", "Williams-Sonoma", "Serveware",  "Platters",      "WS-SW-001", "Pillivuyt Oval Platter",        40, "premium"),
        ("WS", "Williams-Sonoma", "Serveware",  "Entertaining",  "WS-SW-002", "Juliska Berry Thread Bowl Set", 35, "premium"),
        ("WS", "Williams-Sonoma", "Cutlery",    "Knife Sets",    "WS-CU-001", "Wusthof Classic 7pc Block",     22, "luxury"),
        ("WS", "Williams-Sonoma", "Cutlery",    "Scissors",      "WS-CU-002", "Joyce Chen Unlimited Scissors", 55, "premium"),
    ],
    "PB": [
        ("PB", "Pottery Barn",    "Bedding",    "Duvet Covers",  "PB-BD-001", "Belgian Flax Linen Duvet",      28, "luxury"),
        ("PB", "Pottery Barn",    "Bedding",    "Sheet Sets",    "PB-BD-002", "Organic Sateen Sheet Set",      45, "premium"),
        ("PB", "Pottery Barn",    "Furniture",  "Sofas",         "PB-FU-001", "Comfort Square Arm Sofa",        5, "luxury"),
        ("PB", "Pottery Barn",    "Furniture",  "Accent Chairs", "PB-FU-002", "Remy Swivel Chair",              8, "luxury"),
        ("PB", "Pottery Barn",    "Decor",      "Throws",        "PB-DC-001", "Faux Fur Throw Blanket",        65, "premium"),
        ("PB", "Pottery Barn",    "Decor",      "Candles",       "PB-DC-002", "Volcano Candle Set",            80, "premium"),
        ("PB", "Pottery Barn",    "Dorm",       "Bedding",       "PB-DR-001", "Essential Dorm Bedding Bundle", 55, "premium"),
        ("PB", "Pottery Barn",    "Dorm",       "Storage",       "PB-DR-002", "Canvas Storage Bin Set",        70, "standard"),
        ("PB", "Pottery Barn",    "Lighting",   "Table Lamps",   "PB-LT-001", "Tilda Table Lamp",              20, "premium"),
        ("PB", "Pottery Barn",    "Lighting",   "Floor Lamps",   "PB-LT-002", "Callum Arc Floor Lamp",         12, "luxury"),
    ],
    "WE": [
        ("WE", "West Elm",        "Furniture",  "Sofas",         "WE-FU-001", "Andes Sofa",                     7, "premium"),
        ("WE", "West Elm",        "Furniture",  "Dining Tables", "WE-FU-002", "Emmerson Dining Table",          6, "premium"),
        ("WE", "West Elm",        "Decor",      "Pillows",       "WE-DC-001", "Velvet Lumbar Pillow Set",       75, "standard"),
        ("WE", "West Elm",        "Decor",      "Art",           "WE-DC-002", "Abstract Canvas Print",          30, "premium"),
        ("WE", "West Elm",        "Bedding",    "Duvet Covers",  "WE-BD-001", "Organic Cotton Percale Duvet",  35, "premium"),
        ("WE", "West Elm",        "Bedding",    "Quilts",        "WE-BD-002", "Stripe Organic Cotton Quilt",   28, "premium"),
        ("WE", "West Elm",        "Rugs",       "Area Rugs",     "WE-RG-001", "Jute Boucle Rug 8x10",          15, "premium"),
        ("WE", "West Elm",        "Rugs",       "Runners",       "WE-RG-002", "Carved Geo Runner",             22, "standard"),
    ],
}

# Flatten
all_products = []
for brand_skus in products.values():
    for p in brand_skus:
        all_products.append({
            "brand_id":       p[0],
            "brand_name":     p[1],
            "category":       p[2],
            "subcategory":    p[3],
            "sku_id":         p[4],
            "sku_name":       p[5],
            "base_demand":    p[6],
            "price_tier":     p[7],
        })

product_df = pd.DataFrame(all_products)
product_df.to_csv(f"{OUTPUT_DIR}/product_hierarchy.csv", index=False)
print(f"   [ok] {len(product_df)} SKUs across {product_df['brand_id'].nunique()} brands")

# ---------------------------------------------
# 2. EVENTS DATA  (WS-Specific)
# ---------------------------------------------
print("[step] Building events calendar...")

def get_thanksgiving(year):
    """4th Thursday of November"""
    nov1 = date(year, 11, 1)
    first_thursday = nov1 + timedelta(days=(3 - nov1.weekday()) % 7)
    return first_thursday + timedelta(weeks=3)

def get_mothers_day(year):
    """2nd Sunday of May"""
    may1 = date(year, 5, 1)
    first_sunday = may1 + timedelta(days=(6 - may1.weekday()) % 7)
    return first_sunday + timedelta(weeks=1)

def get_superbowl(year):
    """~2nd Sunday of February (approximate)"""
    feb1 = date(year, 2, 1)
    first_sunday = feb1 + timedelta(days=(6 - feb1.weekday()) % 7)
    return first_sunday + timedelta(weeks=1)

YEARS = [2022, 2023, 2024]

event_rows = []
for yr in YEARS:
    tg = get_thanksgiving(yr)
    events_this_year = [
        # name,              date,              pre_window, post_window, affected_brands, affected_categories
        ("Thanksgiving",     tg,                 28, 3,  "WS",       "Cookware,Bakeware,Serveware,Cutlery"),
        ("Black Friday",     tg + timedelta(1),  21, 5,  "ALL",      "ALL"),
        ("Cyber Monday",     tg + timedelta(4),  14, 3,  "ALL",      "ALL"),
        ("Christmas",        date(yr, 12, 25),   35, 10, "ALL",      "ALL"),
        ("New Year",         date(yr+1, 1, 1),   14, 5,  "ALL",      "Cookware,Decor,Bedding"),
        ("Valentines Day",   date(yr, 2, 14),    14, 3,  "WS,PB",    "Cookware,Decor,Lighting"),
        ("Mothers Day",      get_mothers_day(yr), 21, 3, "WS,PB",    "Cookware,Bakeware,Serveware"),
        ("Super Bowl",       get_superbowl(yr),  14, 2,  "WS",       "Cookware,Serveware,Electrics"),
        ("Wedding Season",   date(yr, 5, 15),    45, 14, "WS,PB",    "ALL"),
        ("Back to College",  date(yr, 8, 1),     35, 7,  "PB",       "Dorm,Bedding,Lighting"),
        ("Labor Day",        date(yr, 9, 7),     14, 3,  "WE,PB",    "Furniture,Rugs"),
    ]
    for ev in events_this_year:
        event_rows.append({
            "event_name":          ev[0],
            "event_date":          ev[1],
            "pre_impact_window":   ev[2],
            "post_impact_window":  ev[3],
            "affected_brands":     ev[4],
            "affected_categories": ev[5],
        })

events_df = pd.DataFrame(event_rows)
events_df.to_csv(f"{OUTPUT_DIR}/events_data.csv", index=False)
print(f"   [ok] {len(events_df)} event records across {len(YEARS)} years")

# ---------------------------------------------
# 3. CUSTOMER SEGMENTS
# ---------------------------------------------
print("[step] Building customer segments...")

segments = [
    ("SEG-01", "Luxury Self-Buyer",    "high",   "online",  False, False, 0.90),
    ("SEG-02", "Gift Buyer Premium",   "high",   "online",  True,  False, 0.85),
    ("SEG-03", "Registry Buyer",       "high",   "online",  True,  True,  0.95),
    ("SEG-04", "In-Store Loyalist",    "high",   "store",   False, False, 0.88),
    ("SEG-05", "Catalog Buyer",        "medium", "catalog", False, False, 0.75),
    ("SEG-06", "Aspirational Buyer",   "medium", "online",  False, False, 0.70),
    ("SEG-07", "Gift Buyer Standard",  "medium", "online",  True,  False, 0.72),
    ("SEG-08", "Dorm/College Buyer",   "low",    "online",  False, False, 0.65),
    ("SEG-09", "New Customer",         "low",    "online",  False, False, 0.60),
    ("SEG-10", "Deal Seeker",          "low",    "online",  False, False, 0.55),
]

seg_df = pd.DataFrame(segments, columns=[
    "segment_id", "segment_name", "ltv_tier",
    "channel", "is_gift_buyer", "is_registry_buyer", "conversion_rate"
])
seg_df.to_csv(f"{OUTPUT_DIR}/customer_segments.csv", index=False)
print(f"   [ok] {len(seg_df)} customer segments")

# ---------------------------------------------
# 4. REGISTRY DATA  (monthly signal per SKU)
# ---------------------------------------------
print("[step] Building registry signals...")

# Registry is mainly WS + PB SKUs
registry_skus = [p["sku_id"] for p in all_products
                 if p["brand_id"] in ("WS", "PB")]

registry_rows = []
date_range = pd.date_range("2022-01-01", "2024-12-31", freq="MS")
for sku in registry_skus:
    base = np.random.randint(5, 40)
    for dt in date_range:
        # Wedding season boost MayJul
        wedding_boost = 1.8 if dt.month in (5, 6, 7) else 1.0
        # Holiday gifting boost NovDec
        holiday_boost = 1.5 if dt.month in (11, 12) else 1.0
        noise = np.random.normal(1.0, 0.1)
        registry_rows.append({
            "sku_id":                  sku,
            "year_month":              dt.strftime("%Y-%m"),
            "active_registries":       int(base * wedding_boost * holiday_boost * noise),
            "items_fulfilled_this_month": int(base * 0.6 * wedding_boost * holiday_boost * noise),
        })

registry_df = pd.DataFrame(registry_rows)
registry_df.to_csv(f"{OUTPUT_DIR}/registry_data.csv", index=False)
print(f"   [ok] {len(registry_df)} registry records")

# ---------------------------------------------
# 5. SALES DATA  (main table)
# ---------------------------------------------
print("[step] Generating sales data (this takes a moment)...")

START_DATE = date(2022, 1, 1)
END_DATE   = date(2024, 12, 31)
all_dates  = [START_DATE + timedelta(days=i)
              for i in range((END_DATE - START_DATE).days + 1)]

# -- Helper: compute event decay for a given date --
def compute_event_effect(current_date, events_df, sku_brand, sku_category):
    """
    Correct decay model:

      PRE-EVENT buildup  (days_delta > 0, i.e. event is in the future):
        effect = exp(-days_delta / tau)
        -> Far away (~pre_win days): effect  0
        -> Event eve (days_delta=1): effect  high
        -> Peaks on event day (days_delta=0): effect = exp(0) = 1.0  [ok]

      EVENT DAY (days_delta == 0):
        Treated as pre-event with days_delta=0 -> maximum boost.
        NOT routed into post-event suppression.  [ok]

      POST-EVENT hangover (days_delta < 0, i.e. event has passed):
        Starts the day AFTER the event (days_delta = -1).
        Slight demand suppression as consumers pull back.
    """
    total_effect = 1.0
    for _, ev in events_df.iterrows():
        # Brand / category filter
        brands_affected = ev["affected_brands"]
        cats_affected   = ev["affected_categories"]
        if brands_affected != "ALL" and sku_brand not in brands_affected:
            continue
        if cats_affected != "ALL" and sku_category not in cats_affected:
            continue

        ev_date  = pd.Timestamp(ev["event_date"]).date()
        pre_win  = ev["pre_impact_window"]
        post_win = ev["post_impact_window"]

        # days_delta > 0 -> event is in the future (pre-event)
        # days_delta = 0 -> TODAY IS the event day
        # days_delta < 0 -> event has passed (post-event)
        days_delta = (ev_date - current_date).days

        # FIX 1: include event day (>=0) in pre-event buildup
        # FIX 2: use pre_win/4 as tau so decay is steeper and
        #        peak at days_delta=0 is clearly the maximum
        if 0 <= days_delta <= pre_win:
            tau    = max(pre_win / 4, 1.0)          # steeper ramp-up
            effect = np.exp(-days_delta / tau)       # = 1.0 on event day [ok]
            total_effect += effect * 1.5

        # Post-event hangover starts the day AFTER (days_delta = -1)
        elif -post_win <= days_delta < 0:
            days_after = abs(days_delta)             # 1 on day after event
            tau_post   = max(post_win / 2, 1.0)
            effect     = np.exp(-days_after / tau_post)
            total_effect -= effect * 0.3             # slight suppression

    return max(total_effect, 0.1)   # floor at 10% of base

# -- Helper: seasonality multiplier --
def get_seasonality(dt, brand_id, category):
    m = dt.month
    # Q4 is king for all WS brands
    q4_mult = {10: 1.3, 11: 1.8, 12: 2.5}.get(m, 1.0)
    # Summer dorm spike for PB
    dorm_mult = 1.5 if (brand_id == "PB" and category == "Dorm" and m in (7, 8)) else 1.0
    # Spring for furniture / rugs
    spring_mult = 1.2 if (category in ("Furniture", "Rugs") and m in (3, 4, 5)) else 1.0
    return q4_mult * dorm_mult * spring_mult

# -- Helper: day-of-week multiplier --
def get_dow_multiplier(dt):
    # Weekends slightly higher for home goods
    return {0: 1.0, 1: 0.9, 2: 0.9, 3: 0.95,
            4: 1.1, 5: 1.3, 6: 1.2}.get(dt.weekday(), 1.0)

# -- Helper: YoY growth trend --
def get_yoy_growth(dt):
    return 1.0 + (dt.year - 2022) * 0.07   # ~7% YoY growth

# -- Main sales generation loop --
sales_rows = []
segments_list = seg_df["segment_id"].tolist()
seg_weights   = seg_df["conversion_rate"].tolist()

for product in all_products:
    sku_id    = product["sku_id"]
    brand_id  = product["brand_id"]
    category  = product["category"]
    base_d    = product["base_demand"]

    for dt in all_dates:
        # Compute all multipliers
        seasonality   = get_seasonality(dt, brand_id, category)
        event_effect  = compute_event_effect(dt, events_df, brand_id, category)
        dow_mult      = get_dow_multiplier(dt)
        yoy_growth    = get_yoy_growth(dt)
        noise         = max(np.random.normal(1.0, 0.08), 0.5)

        expected_units = (base_d
                          * seasonality
                          * event_effect
                          * dow_mult
                          * yoy_growth
                          * noise)

        units_sold = max(int(round(expected_units)), 0)

        # Assign a random segment (weighted by conversion rate)
        seg_id = random.choices(segments_list, weights=seg_weights, k=1)[0]

        sales_rows.append({
            "date":            dt.isoformat(),
            "sku_id":          sku_id,
            "brand_id":        brand_id,
            "category":        category,
            "segment_id":      seg_id,
            "units_sold":      units_sold,
            "seasonality_mult": round(seasonality, 3),
            "event_effect":    round(event_effect, 3),
        })

sales_df = pd.DataFrame(sales_rows)
sales_df.to_csv(f"{OUTPUT_DIR}/sales_data.csv", index=False)
print(f"   [ok] {len(sales_df):,} sales records")
print(f"       Date range : {sales_df['date'].min()} to {sales_df['date'].max()}")
print(f"       SKUs       : {sales_df['sku_id'].nunique()}")
print(f"       Brands     : {sales_df['brand_id'].nunique()}")

# ---------------------------------------------
# 6. QUICK SANITY CHECK
# ---------------------------------------------
print("\nSanity Checks:")
print("-" * 45)

# Check: Q4 should dominate
sales_df["month"] = pd.to_datetime(sales_df["date"]).dt.month
monthly = sales_df.groupby("month")["units_sold"].sum()
print("  Monthly demand (should peak in Q4):")
for m, v in monthly.items():
    bar = "#" * int(v / monthly.max() * 20)
    print(f"  Month {m:02d}: {bar} {v:,}")

print()
print("  Brand share:")
brand_share = sales_df.groupby("brand_id")["units_sold"].sum()
for b, v in brand_share.items():
    pct = v / brand_share.sum() * 100
    print(f"  {b}: {pct:.1f}%")

print()
print("-" * 45)
print("All files saved to:", OUTPUT_DIR)
print("   sales_data.csv")
print("   product_hierarchy.csv")
print("   events_data.csv")
print("   customer_segments.csv")
print("   registry_data.csv")


"""
======================================================
  Williams-Sonoma Demand Forecasting
  Step 2: Feature Engineering Pipeline
======================================================
  Input  : ws_demand_dataset/  (from generate_dataset.py)
  Output : ws_demand_dataset/featured_data.csv

  Features built:
    GROUP A  Lag & Rolling Features
      lag_7, lag_30, lag_365
      rolling_7, rolling_30

    GROUP B  Time Features
      month, day_of_week, week_of_year
      is_weekend, quarter, is_q4

    GROUP C  Event Decay Features (pre + post)
      days_to_<event>, <event>_pre_decay, <event>_post_decay
      for: thanksgiving, blackfriday, christmas, newyear,
           mothersday, valentines, superbowl, weddingseason,
           backtocollege, laborday

    GROUP D  Event Overlap / Interaction
      bfcm_overlap        (Black Friday  Cyber Monday)
      holiday_pipeline    (Thanksgiving -> Christmas combined)

    GROUP E  Segment Features
      ltv_tier, channel, is_gift_buyer, is_registry_buyer

    GROUP F  Registry Signal
      active_registries, items_fulfilled_this_month

    GROUP G  Product Identity
      brand_id, category (label-encoded)

  TARGET : units_sold
======================================================
"""

import pandas as pd
import numpy as np
import os

# ---------------------------------------------
# PATHS
# ---------------------------------------------
DATA_DIR = "ws_demand_dataset"
SALES_PATH    = f"{DATA_DIR}/sales_data.csv"
EVENTS_PATH   = f"{DATA_DIR}/events_data.csv"
SEGMENTS_PATH = f"{DATA_DIR}/customer_segments.csv"
REGISTRY_PATH = f"{DATA_DIR}/registry_data.csv"
OUTPUT_PATH   = f"{DATA_DIR}/featured_data.csv"

print("=" * 55)
print("  WS Demand Forecasting  Feature Engineering")
print("=" * 55)

# ---------------------------------------------
# LOAD DATA
# ---------------------------------------------
print("\nLoading raw data...")

sales_df    = pd.read_csv(SALES_PATH, parse_dates=["date"])
events_df   = pd.read_csv(EVENTS_PATH, parse_dates=["event_date"])
segments_df = pd.read_csv(SEGMENTS_PATH)
registry_df = pd.read_csv(REGISTRY_PATH)

print(f"   Sales rows     : {len(sales_df):,}")
print(f"   Events         : {len(events_df)}")
print(f"   Segments       : {len(segments_df)}")
print(f"   Registry rows  : {len(registry_df):,}")

# ---------------------------------------------
# SORT  critical for correct lag computation
# ---------------------------------------------
sales_df = sales_df.sort_values(["sku_id", "date"]).reset_index(drop=True)

# ---------------------------------------------
# GROUP A  LAG & ROLLING FEATURES
# ---------------------------------------------
print("\n[step] Computing lag & rolling features...")

def add_lag_rolling(df):
    grp = df.groupby("sku_id")["units_sold"]

    # -- Lag features (exact past values) --
    df["lag_7"]   = grp.shift(7)     # same weekday last week
    df["lag_30"]  = grp.shift(30)    # approx same day last month
    df["lag_365"] = grp.shift(365)   # same day last year *

    # -- Rolling averages (smoothed signal) --
    df["rolling_7"]  = (grp.shift(1)
                           .rolling(window=7,  min_periods=3)
                           .mean()
                           .reset_index(level=0, drop=True))

    df["rolling_30"] = (grp.shift(1)
                           .rolling(window=30, min_periods=7)
                           .mean()
                           .reset_index(level=0, drop=True))

    # -- Trend ratio: are we trending up or down vs last month? --
    df["trend_ratio_7_30"] = (df["rolling_7"] / df["rolling_30"]
                               .replace(0, np.nan))

    return df

sales_df = add_lag_rolling(sales_df)

lag_nulls = sales_df[["lag_7","lag_30","lag_365"]].isna().sum()
print(f"   lag_7   NaNs : {lag_nulls['lag_7']:,}  (first 7 rows per SKU  expected)")
print(f"   lag_30  NaNs : {lag_nulls['lag_30']:,}")
print(f"   lag_365 NaNs : {lag_nulls['lag_365']:,}  (first year  will be dropped later)")

# ---------------------------------------------
# GROUP B  TIME FEATURES
# ---------------------------------------------
print("\n[step] Computing time features...")

sales_df["month"]        = sales_df["date"].dt.month
sales_df["day_of_week"]  = sales_df["date"].dt.dayofweek   # 0=Mon, 6=Sun
sales_df["week_of_year"] = sales_df["date"].dt.isocalendar().week.astype(int)
sales_df["quarter"]      = sales_df["date"].dt.quarter
sales_df["is_weekend"]   = (sales_df["day_of_week"] >= 5).astype(int)
sales_df["is_q4"]        = (sales_df["quarter"] == 4).astype(int)

# Day of month  useful for salary-cycle effects
sales_df["day_of_month"] = sales_df["date"].dt.day

print(f"   Time features added: month, dow, week, quarter, is_weekend, is_q4")

# ---------------------------------------------
# GROUP C  EVENT DECAY FEATURES
# ---------------------------------------------
print("\n[step] Computing event decay features...")

"""
For each event we compute TWO decay columns:

  pre_decay  = exp( -days_before / (pre_window/3) )
                -> 0 when far away, spikes to 1 on event day
                -> only active BEFORE the event

  post_decay = exp( -days_after  / (post_window/2) )
                -> 1 right after event, decays to 0
                -> models demand hangover / suppression
"""

def compute_decay(days_before, days_after, pre_win, post_win):
    """
    Returns (pre_decay, post_decay).
    FIX 1: days_before >= 0 includes event day -> pre_decay peaks at 1.0 on event day [ok]
    FIX 2: tau = pre_win/4 (steeper) so day-0 peak is unambiguously the maximum [ok]
    Post-hangover starts at days_after >= 1 (day AFTER event) [ok]
    """
    tau_pre  = max(pre_win  / 4, 1.0)
    tau_post = max(post_win / 2, 1.0)

    pre_decay  = np.where(
        days_before >= 0,                          # FIX 1: include event day
        np.exp(-days_before / tau_pre),            # FIX 2: steeper tau
        0.0
    )
    post_decay = np.where(
        days_after >= 1,                           # starts day AFTER event
        np.exp(-days_after / tau_post),
        0.0
    )
    return pre_decay, post_decay


# -- Define key events to model --
KEY_EVENTS = {
    "thanksgiving":   {"pre": 28, "post": 3},
    "blackfriday":    {"pre": 21, "post": 5},
    "cybermonday":    {"pre": 14, "post": 3},
    "christmas":      {"pre": 35, "post": 10},
    "newyear":        {"pre": 14, "post": 5},
    "mothersday":     {"pre": 21, "post": 3},
    "valentines":     {"pre": 14, "post": 3},
    "superbowl":      {"pre": 14, "post": 2},
    "weddingseason":  {"pre": 45, "post": 14},
    "backtocollege":  {"pre": 35, "post": 7},
    "laborday":       {"pre": 14, "post": 3},
}

# Normalize event names for matching
events_df["event_key"] = (events_df["event_name"]
                            .str.lower()
                            .str.replace(" ", "")
                            .str.replace("'", ""))

# -- Brand + category relevance checker --
def is_event_relevant(ev_row, brand_id, category):
    brands = ev_row["affected_brands"]
    cats   = ev_row["affected_categories"]
    brand_ok = (brands == "ALL") or (brand_id in brands)
    cat_ok   = (cats   == "ALL") or (category in cats)
    return brand_ok and cat_ok


# -- Build event date lookup: key -> list of (date, pre_win, post_win) --
event_lookup = {}
for key in KEY_EVENTS:
    matched = events_df[events_df["event_key"] == key]
    event_lookup[key] = list(zip(
        matched["event_date"],
        matched["pre_impact_window"],
        matched["post_impact_window"],
        matched["affected_brands"],
        matched["affected_categories"]
    ))

# -- Vectorized computation per event --
dates_np = sales_df["date"].values

for ev_key, params in KEY_EVENTS.items():
    pre_col  = f"{ev_key}_pre_decay"
    post_col = f"{ev_key}_post_decay"
    days_col = f"days_to_{ev_key}"

    pre_accum  = np.zeros(len(sales_df))
    post_accum = np.zeros(len(sales_df))
    days_accum = np.full(len(sales_df), 999.0)

    records = event_lookup.get(ev_key, [])
    if not records:
        sales_df[pre_col]  = 0.0
        sales_df[post_col] = 0.0
        sales_df[days_col] = 999
        continue

    for ev_date, pre_win, post_win, aff_brands, aff_cats in records:
        ev_np = np.datetime64(ev_date)
        delta = (ev_np - dates_np).astype("timedelta64[D]").astype(float)
        # delta > 0 -> event in future (pre)
        # delta < 0 -> event passed (post)

        days_before = np.where(delta > 0, delta, 0)
        days_after  = np.where(delta < 0, -delta, 0)

        pre_d, post_d = compute_decay(days_before, days_after, pre_win, post_win)

        # Only accumulate within valid window
        # FIX: delta >= 0 includes event day in pre-window [ok]
        # FIX: delta < 0 (strictly) keeps event day out of post-window [ok]
        in_pre_window  = (delta >= 0) & (delta <= pre_win)
        in_post_window = (delta < 0)  & (-delta <= post_win)

        pre_accum  = np.where(in_pre_window,  np.maximum(pre_accum,  pre_d),  pre_accum)
        post_accum = np.where(in_post_window, np.maximum(post_accum, post_d), post_accum)

        # Track minimum days to event (for interpretability)
        days_accum = np.where(
            np.abs(delta) < np.abs(days_accum),
            delta,
            days_accum
        )

    sales_df[pre_col]  = np.round(pre_accum,  4)
    sales_df[post_col] = np.round(post_accum, 4)
    sales_df[days_col] = days_accum.astype(int)

    nonzero_pre  = (sales_df[pre_col]  > 0.01).sum()
    nonzero_post = (sales_df[post_col] > 0.01).sum()
    print(f"   {ev_key:15s} - pre rows: {nonzero_pre:5,}  post rows: {nonzero_post:4,}")

# ---------------------------------------------
# GROUP D  EVENT OVERLAP / INTERACTION TERMS
# ---------------------------------------------
print("\n[step] Computing event overlap features...")

# Black Friday  Cyber Monday combined surge
sales_df["bfcm_overlap"] = (
    sales_df["blackfriday_pre_decay"] *
    sales_df["cybermonday_pre_decay"]
)

# Thanksgiving -> Christmas pipeline
# Captures the extended holiday shopping season as a combined signal
sales_df["holiday_pipeline"] = (
    sales_df["thanksgiving_pre_decay"] +
    sales_df["christmas_pre_decay"] +
    sales_df["blackfriday_pre_decay"]
).clip(0, 3) / 3   # normalize to [0, 1]

# Wedding + Mother's Day gifting overlap (spring gifting season)
sales_df["spring_gifting"] = (
    sales_df["mothersday_pre_decay"] *
    sales_df["weddingseason_pre_decay"]
)

print(f"   bfcm_overlap    non-zero rows : {(sales_df['bfcm_overlap']    > 0.01).sum():,}")
print(f"   holiday_pipeline non-zero rows: {(sales_df['holiday_pipeline'] > 0.01).sum():,}")
print(f"   spring_gifting  non-zero rows : {(sales_df['spring_gifting']   > 0.01).sum():,}")

# ---------------------------------------------
# GROUP E  SEGMENT FEATURES
# ---------------------------------------------
print("\n[step] Merging segment features...")

seg_features = segments_df[[
    "segment_id", "ltv_tier", "channel",
    "is_gift_buyer", "is_registry_buyer", "conversion_rate"
]]

sales_df = sales_df.merge(seg_features, on="segment_id", how="left")

# Encode categorical segment features
ltv_map     = {"low": 0, "medium": 1, "high": 2}
channel_map = {"catalog": 0, "store": 1, "online": 2}

sales_df["ltv_tier_enc"]  = sales_df["ltv_tier"].map(ltv_map)
sales_df["channel_enc"]   = sales_df["channel"].map(channel_map)

print(f"   Segment features merged. LTV tiers: {sales_df['ltv_tier'].value_counts().to_dict()}")

# ---------------------------------------------
# GROUP F  REGISTRY SIGNAL
# ---------------------------------------------
print("\n[step] Merging registry signal...")

sales_df["year_month"] = sales_df["date"].dt.strftime("%Y-%m")

registry_features = registry_df[[
    "sku_id", "year_month",
    "active_registries", "items_fulfilled_this_month"
]]

sales_df = sales_df.merge(
    registry_features,
    on=["sku_id", "year_month"],
    how="left"
)

# Fill NaN for non-registry SKUs (West Elm)
sales_df["active_registries"]          = sales_df["active_registries"].fillna(0)
sales_df["items_fulfilled_this_month"] = sales_df["items_fulfilled_this_month"].fillna(0)

print(f"   Registry signal merged. Non-zero rows: {(sales_df['active_registries'] > 0).sum():,}")

# ---------------------------------------------
# GROUP G  PRODUCT IDENTITY ENCODING
# ---------------------------------------------
print("\n[step] Encoding product identity features...")

brand_map    = {"WS": 0, "PB": 1, "WE": 2}
category_map = {c: i for i, c in enumerate(sales_df["category"].unique())}

sales_df["brand_enc"]    = sales_df["brand_id"].map(brand_map)
sales_df["category_enc"] = sales_df["category"].map(category_map)

print(f"   Brand mapping    : {brand_map}")
print(f"   Category mapping : {category_map}")

# ---------------------------------------------
# FINAL CLEANUP
# ---------------------------------------------
print("\n[step] Final cleanup...")

# Drop rows where lag_365 is NaN (first year has no year-ago reference)
before = len(sales_df)
sales_df = sales_df.dropna(subset=["lag_365"])
after  = len(sales_df)
print(f"   Dropped {before - after:,} rows (lag_365 NaN  first year warmup)")

# Fill remaining NaNs in lag_7 / lag_30 with rolling average
sales_df["lag_7"]  = sales_df["lag_7"].fillna(sales_df["rolling_7"])
sales_df["lag_30"] = sales_df["lag_30"].fillna(sales_df["rolling_30"])

# Final NaN check
nan_counts = sales_df.isnull().sum()
nan_counts = nan_counts[nan_counts > 0]
if len(nan_counts) == 0:
    print("   [ok] No NaN values remaining")
else:
    print(f"   [!] Remaining NaNs:\n{nan_counts}")

# ---------------------------------------------
# DEFINE FINAL FEATURE COLUMNS
# ---------------------------------------------
FEATURE_COLUMNS = [
    # -- Group A: Lag & Rolling --
    "lag_7", "lag_30", "lag_365",
    "rolling_7", "rolling_30",
    "trend_ratio_7_30",

    # -- Group B: Time --
    "month", "day_of_week", "week_of_year",
    "quarter", "is_weekend", "is_q4", "day_of_month",

    # -- Group C: Event Decay --
    "thanksgiving_pre_decay",  "thanksgiving_post_decay",
    "blackfriday_pre_decay",   "blackfriday_post_decay",
    "cybermonday_pre_decay",   "cybermonday_post_decay",
    "christmas_pre_decay",     "christmas_post_decay",
    "newyear_pre_decay",       "newyear_post_decay",
    "mothersday_pre_decay",    "mothersday_post_decay",
    "valentines_pre_decay",    "valentines_post_decay",
    "superbowl_pre_decay",     "superbowl_post_decay",
    "weddingseason_pre_decay", "weddingseason_post_decay",
    "backtocollege_pre_decay", "backtocollege_post_decay",
    "laborday_pre_decay",      "laborday_post_decay",

    # -- Days-to (interpretability) --
    "days_to_thanksgiving", "days_to_christmas",
    "days_to_blackfriday",  "days_to_mothersday",

    # -- Group D: Overlap / Interaction --
    "bfcm_overlap", "holiday_pipeline", "spring_gifting",

    # -- Group E: Segment --
    "ltv_tier_enc", "channel_enc",
    "is_gift_buyer", "is_registry_buyer", "conversion_rate",

    # -- Group F: Registry --
    "active_registries", "items_fulfilled_this_month",

    # -- Group G: Product Identity --
    "brand_enc", "category_enc",
]

TARGET_COLUMN = "units_sold"

# Save full featured dataframe
sales_df.to_csv(OUTPUT_PATH, index=False)

# Also save a clean ML-ready version (features + target only)
ml_df = sales_df[["date", "sku_id", "brand_id", "category"]
                 + FEATURE_COLUMNS
                 + [TARGET_COLUMN]]
ml_df.to_csv(f"{DATA_DIR}/ml_ready_data.csv", index=False)

# ---------------------------------------------
# SUMMARY REPORT
# ---------------------------------------------
print("\n" + "=" * 55)
print("  FEATURE ENGINEERING COMPLETE")
print("=" * 55)

print(f"\nDataset shape    : {ml_df.shape}")
print(f"   Total features  : {len(FEATURE_COLUMNS)}")
print(f"   Date range      : {ml_df['date'].min().date()} to {ml_df['date'].max().date()}")
print(f"   SKUs            : {ml_df['sku_id'].nunique()}")

print("\nFeature Groups:")
groups = {
    "A - Lag & Rolling":    ["lag_7","lag_30","lag_365","rolling_7","rolling_30","trend_ratio_7_30"],
    "B - Time":             ["month","day_of_week","week_of_year","quarter","is_weekend","is_q4","day_of_month"],
    "C - Event Decays":     [c for c in FEATURE_COLUMNS if "decay" in c],
    "D - Overlap":          ["bfcm_overlap","holiday_pipeline","spring_gifting"],
    "E - Segment":          ["ltv_tier_enc","channel_enc","is_gift_buyer","is_registry_buyer","conversion_rate"],
    "F - Registry":         ["active_registries","items_fulfilled_this_month"],
    "G - Product Identity": ["brand_enc","category_enc"],
}
for g, cols in groups.items():
    print(f"   Group {g:30s} -> {len(cols):2d} features")

print(f"\nFiles saved:")
print(f"   {OUTPUT_PATH}           (full enriched data)")
print(f"   {DATA_DIR}/ml_ready_data.csv  (features + target only)")

# ---------------------------------------------
# QUICK FEATURE SANITY CHECK
# ---------------------------------------------
print("\nQuick Sanity Checks:")

# Check event decay peaks correctly near Christmas
xmas_rows = ml_df[ml_df["days_to_christmas"].between(-5, 5)]
print(f"\n   Christmas window (5 days):")
print(f"   Avg christmas_pre_decay  : {xmas_rows['christmas_pre_decay'].mean():.3f}  (should be high ~0.9+)")
print(f"   Avg christmas_post_decay : {xmas_rows['christmas_post_decay'].mean():.3f}  (should be high ~0.9+)")

# Check lag_365 correlation with units_sold
corr_365 = ml_df["lag_365"].corr(ml_df["units_sold"])
corr_7   = ml_df["lag_7"].corr(ml_df["units_sold"])
corr_30  = ml_df["lag_30"].corr(ml_df["units_sold"])
print(f"\n   Correlation with units_sold:")
print(f"   lag_365 : {corr_365:.3f}  <- should be highest")
print(f"   lag_30  : {corr_30:.3f}")
print(f"   lag_7   : {corr_7:.3f}")

# Check holiday pipeline is non-zero in Q4
q4_pipe = ml_df[ml_df["is_q4"] == 1]["holiday_pipeline"].mean()
q1_pipe = ml_df[ml_df["quarter"] == 1]["holiday_pipeline"].mean()
print(f"\n   holiday_pipeline avg in Q4 : {q4_pipe:.3f}  (should be >> Q1)")
print(f"   holiday_pipeline avg in Q1 : {q1_pipe:.3f}")

print("\n" + "=" * 55)
print("  Ready for Step 3: Model Training")
print("=" * 55)

"""
======================================================
  Williams-Sonoma Demand Forecasting
  Step 3: Model Training & Selection
======================================================
  Models compared:
    1. Random Forest
    2. XGBoost
    3. LightGBM  <- expected winner

  Process:
    1. Time-based train/test split
    2. Train all 3 models
    3. Evaluate with WMAPE, RMSE, MAE
    4. Select best model
    5. Feature importance plot
    6. Prediction vs Actual plot
    7. Save best model
======================================================
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import warnings, time, joblib, os
warnings.filterwarnings("ignore")

from sklearn.ensemble         import RandomForestRegressor
from sklearn.metrics          import mean_squared_error, mean_absolute_error
from xgboost                  import XGBRegressor
from lightgbm                 import LGBMRegressor

DATA_DIR   = "ws_demand_dataset"
MODEL_DIR  = "ws_model"
os.makedirs(MODEL_DIR, exist_ok=True)

# ---------------------------------------------
# 1. LOAD & SPLIT
# ---------------------------------------------
print("=" * 58)
print("  WS Demand Forecasting  Model Training")
print("=" * 58)

print("\nLoading ml_ready_data.csv...")
if os.environ.get("OPTICHAIN_TRAINING_SOURCE", "csv").lower() == "database":
    import sys

    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, os.path.join(ROOT, "backend"))
    from app.db.engine import get_engine
    from app.db.migrations import run_migrations
    from app.db.training import load_demand_training_frame

    engine = get_engine()
    run_migrations(engine)
    df = load_demand_training_frame(engine)
    print("   Source  : validated database demand_daily")
else:
    df = pd.read_csv(f"{DATA_DIR}/ml_ready_data.csv", parse_dates=["date"])
print(f"   Shape: {df.shape}")

META_COLS   = ["date", "sku_id", "brand_id", "category"]
TARGET_COL  = "units_sold"
FEATURE_COLS = [c for c in df.columns if c not in META_COLS + [TARGET_COL]]

print(f"   Features : {len(FEATURE_COLS)}")
print(f"   Target   : {TARGET_COL}")

# Time-based split  test on holiday season
SPLIT_DATE = "2024-10-01"
train = df[df["date"] <  SPLIT_DATE].copy()
test  = df[df["date"] >= SPLIT_DATE].copy()

X_train = train[FEATURE_COLS]
y_train = train[TARGET_COL]
X_test  = test[FEATURE_COLS]
y_test  = test[TARGET_COL]

print(f"\nTrain: {train['date'].min().date()} to {train['date'].max().date()}  ({len(train):,} rows)")
print(f"   Test : {test['date'].min().date()}  to {test['date'].max().date()}  ({len(test):,} rows)")
print(f"   Test covers: Oct-Dec 2024 (holiday season [ok])")

# ---------------------------------------------
# 2. METRICS
# ---------------------------------------------
def wmape(y_true, y_pred):
    """Weighted MAPE  better than plain MAPE for demand forecasting.
    High-volume SKUs contribute more to the error score."""
    return np.sum(np.abs(y_true - y_pred)) / np.sum(np.abs(y_true)) * 100

def evaluate(name, y_true, y_pred, elapsed):
    rmse  = np.sqrt(mean_squared_error(y_true, y_pred))
    mae   = mean_absolute_error(y_true, y_pred)
    wm    = wmape(y_true, y_pred)
    r2    = 1 - np.sum((y_true - y_pred)**2) / np.sum((y_true - y_true.mean())**2)
    print(f"\n  {name}")
    print(f"  {'-'*38}")
    print(f"  WMAPE  : {wm:6.2f}%   (lower = better, <10% = good)")
    print(f"  RMSE   : {rmse:7.2f}  units")
    print(f"  MAE    : {mae:7.2f}  units")
    print(f"  R     : {r2:7.4f}  (closer to 1 = better)")
    print(f"  Time   : {elapsed:.1f}s")
    return {"model": name, "WMAPE": wm, "RMSE": rmse, "MAE": mae, "R2": r2}

# ---------------------------------------------
# 3. TRAIN ALL 3 MODELS
# ---------------------------------------------
print("\n" + "-"*58)
print("  Training Models")
print("-"*58)

results   = []
models    = {}
preds     = {}

# -- Model 1: Random Forest --
print("\n Random Forest...")
t0 = time.time()
rf = RandomForestRegressor(
    n_estimators=200,
    max_depth=12,
    min_samples_leaf=5,
    max_features=0.6,
    n_jobs=-1,
    random_state=42
)
rf.fit(X_train, y_train)
elapsed = time.time() - t0
pred_rf = rf.predict(X_test)
results.append(evaluate("Random Forest", y_test, pred_rf, elapsed))
models["Random Forest"] = rf
preds["Random Forest"]  = pred_rf

# -- Model 2: XGBoost --
print("\n XGBoost...")
t0 = time.time()
xgb = XGBRegressor(
    n_estimators=500,
    max_depth=6,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    min_child_weight=5,
    reg_alpha=0.1,
    reg_lambda=1.0,
    n_jobs=-1,
    random_state=42,
    verbosity=0
)
xgb.fit(
    X_train, y_train,
    eval_set=[(X_test, y_test)],
    verbose=False
)
elapsed = time.time() - t0
pred_xgb = xgb.predict(X_test)
results.append(evaluate("XGBoost", y_test, pred_xgb, elapsed))
models["XGBoost"] = xgb
preds["XGBoost"]  = pred_xgb

# -- Model 3: LightGBM --
print("\n LightGBM...")
t0 = time.time()
lgbm = LGBMRegressor(
    n_estimators=500,
    max_depth=8,
    learning_rate=0.05,
    num_leaves=63,
    subsample=0.8,
    colsample_bytree=0.8,
    min_child_samples=10,
    reg_alpha=0.1,
    reg_lambda=1.0,
    n_jobs=-1,
    random_state=42,
    verbose=-1
)
lgbm.fit(
    X_train, y_train,
    eval_set=[(X_test, y_test)],
    callbacks=[])
elapsed = time.time() - t0
pred_lgbm = lgbm.predict(X_test)
results.append(evaluate("LightGBM", y_test, pred_lgbm, elapsed))
models["LightGBM"] = lgbm
preds["LightGBM"]  = pred_lgbm

# ---------------------------------------------
# 4. MODEL COMPARISON & SELECTION
# ---------------------------------------------
print("\n" + "-"*58)
print("  Model Comparison")
print("-"*58)

results_df = pd.DataFrame(results).set_index("model")
print(f"\n{results_df.round(3).to_string()}")

best_name  = results_df["WMAPE"].idxmin()
best_model = models[best_name]
best_pred  = preds[best_name]
best_wmape = results_df.loc[best_name, "WMAPE"]

print(f"\n Best Model : {best_name}")
print(f"   WMAPE     : {best_wmape:.2f}%")

# ---------------------------------------------
# 5. FEATURE IMPORTANCE (best model)
# ---------------------------------------------
print("\n Computing feature importances...")

if best_name == "Random Forest":
    importances = best_model.feature_importances_
elif best_name == "XGBoost":
    importances = best_model.feature_importances_
else:  # LightGBM
    importances = best_model.feature_importances_

imp_df = pd.DataFrame({
    "feature":    FEATURE_COLS,
    "importance": importances
}).sort_values("importance", ascending=False).reset_index(drop=True)

print("\n  Top 15 Features:")
print(f"  {'Rank':<5} {'Feature':<35} {'Importance':>10}")
print(f"  {'-'*52}")
for i, row in imp_df.head(15).iterrows():
    bar = "" * int(row["importance"] / imp_df["importance"].max() * 20)
    print(f"  {i+1:<5} {row['feature']:<35} {row['importance']:>8.4f}  {bar}")

# ---------------------------------------------
# 6. PLOTS
# ---------------------------------------------
print("\n Generating plots...")

fig = plt.figure(figsize=(20, 18))
fig.patch.set_facecolor("#0f1117")
gs  = gridspec.GridSpec(3, 2, figure=fig,
                        hspace=0.45, wspace=0.35)

COLORS = {
    "Random Forest": "#4e9af1",
    "XGBoost":       "#f1c94e",
    "LightGBM":      "#4ef1a0",
    "accent":        "#ff6b6b",
    "bg":            "#1a1d27",
    "grid":          "#2a2d3a",
    "text":          "#e0e4ef",
}

def style_ax(ax, title):
    ax.set_facecolor(COLORS["bg"])
    ax.tick_params(colors=COLORS["text"], labelsize=9)
    ax.set_title(title, color=COLORS["text"], fontsize=12,
                 fontweight="bold", pad=10)
    for spine in ax.spines.values():
        spine.set_edgecolor(COLORS["grid"])
    ax.yaxis.label.set_color(COLORS["text"])
    ax.xaxis.label.set_color(COLORS["text"])
    ax.grid(color=COLORS["grid"], linestyle="--", alpha=0.5)

# -- Plot 1: Model Comparison (WMAPE) --
ax1 = fig.add_subplot(gs[0, 0])
model_names = results_df.index.tolist()
wmape_vals  = results_df["WMAPE"].tolist()
bar_colors  = [COLORS.get(n, "#888") for n in model_names]
bars = ax1.bar(model_names, wmape_vals, color=bar_colors,
               width=0.5, zorder=3)
for bar, val in zip(bars, wmape_vals):
    ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
             f"{val:.2f}%", ha="center", va="bottom",
             color=COLORS["text"], fontsize=10, fontweight="bold")
style_ax(ax1, " Model Comparison  WMAPE (lower is better)")
ax1.set_ylabel("WMAPE (%)")

# Highlight best
best_idx = model_names.index(best_name)
bars[best_idx].set_edgecolor("#ffffff")
bars[best_idx].set_linewidth(2.5)
ax1.text(best_idx, wmape_vals[best_idx]/2, "",
         ha="center", va="center", fontsize=16)

# -- Plot 2: R Comparison --
ax2 = fig.add_subplot(gs[0, 1])
r2_vals = results_df["R2"].tolist()
bars2 = ax2.bar(model_names, r2_vals, color=bar_colors,
                width=0.5, zorder=3)
for bar, val in zip(bars2, r2_vals):
    ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.002,
             f"{val:.4f}", ha="center", va="bottom",
             color=COLORS["text"], fontsize=10, fontweight="bold")
style_ax(ax2, " Model Comparison  R (higher is better)")
ax2.set_ylabel("R Score")
ax2.set_ylim(min(r2_vals)*0.98, 1.0)
bars2[best_idx].set_edgecolor("#ffffff")
bars2[best_idx].set_linewidth(2.5)

# -- Plot 3: Feature Importance (top 15) --
ax3 = fig.add_subplot(gs[1, :])
top15 = imp_df.head(15)
colors_imp = []
for feat in top15["feature"]:
    if "lag_365" in feat:              colors_imp.append("#f1c94e")
    elif "decay" in feat or "pipeline" in feat or "overlap" in feat:
                                       colors_imp.append("#4ef1a0")
    elif feat in ["month","is_q4","quarter","week_of_year"]:
                                       colors_imp.append("#4e9af1")
    elif "registry" in feat:           colors_imp.append("#ff6b6b")
    else:                              colors_imp.append("#a78bfa")

hbars = ax3.barh(top15["feature"][::-1], top15["importance"][::-1],
                 color=colors_imp[::-1], zorder=3, height=0.65)
for bar, val in zip(hbars, top15["importance"][::-1]):
    ax3.text(bar.get_width() + 0.0002, bar.get_y() + bar.get_height()/2,
             f"{val:.4f}", va="center", color=COLORS["text"], fontsize=8)
style_ax(ax3, f" Feature Importance  {best_name} (Top 15)")
ax3.set_xlabel("Importance Score")

# Legend for colors
from matplotlib.patches import Patch
legend_els = [
    Patch(facecolor="#f1c94e", label="Lag Features"),
    Patch(facecolor="#4ef1a0", label="Event Decay / Overlap"),
    Patch(facecolor="#4e9af1", label="Time Features"),
    Patch(facecolor="#ff6b6b", label="Registry Signal"),
    Patch(facecolor="#a78bfa", label="Other"),
]
ax3.legend(handles=legend_els, loc="lower right",
           facecolor=COLORS["bg"], edgecolor=COLORS["grid"],
           labelcolor=COLORS["text"], fontsize=8)

# -- Plot 4: Predicted vs Actual (best model, aggregated daily) --
ax4 = fig.add_subplot(gs[2, :])
test_plot = test.copy()
test_plot["predicted"] = best_pred
daily = test_plot.groupby("date").agg(
    actual=("units_sold", "sum"),
    predicted=("predicted", "sum")
).reset_index()

ax4.plot(daily["date"], daily["actual"],
         color="#4e9af1", linewidth=1.5, label="Actual", alpha=0.9)
ax4.plot(daily["date"], daily["predicted"],
         color="#4ef1a0", linewidth=1.5, label="Predicted",
         linestyle="--", alpha=0.9)
ax4.fill_between(daily["date"], daily["actual"], daily["predicted"],
                 alpha=0.15, color="#ff6b6b", label="Error Gap")

# Event markers
events_to_mark = {
    "Thanksgiving": pd.Timestamp("2024-11-28"),
    "Black Friday":  pd.Timestamp("2024-11-29"),
    "Christmas":     pd.Timestamp("2024-12-25"),
}
for ev_name, ev_dt in events_to_mark.items():
    if daily["date"].min() <= ev_dt <= daily["date"].max():
        ax4.axvline(ev_dt, color="#ff6b6b", linestyle=":",
                    linewidth=1.2, alpha=0.7)
        ax4.text(ev_dt, daily["actual"].max() * 0.97, ev_name,
                 color="#ff6b6b", fontsize=7, ha="center",
                 rotation=90, va="top")

style_ax(ax4, f" Predicted vs Actual Daily Demand  {best_name} (OctDec 2024)")
ax4.set_xlabel("Date")
ax4.set_ylabel("Total Units Sold")
ax4.legend(facecolor=COLORS["bg"], edgecolor=COLORS["grid"],
           labelcolor=COLORS["text"], fontsize=9)

plt.suptitle("Williams-Sonoma  |  Event-Driven Demand Forecasting",
             color=COLORS["text"], fontsize=15, fontweight="bold", y=0.99)

plot_path = f"{MODEL_DIR}/model_results.png"
plt.savefig(plot_path, dpi=150, bbox_inches="tight",
            facecolor=fig.get_facecolor())
plt.close()
print(f"   [ok] Plots saved -> {plot_path}")

# ---------------------------------------------
# 7. SAVE BEST MODEL + ARTIFACTS
# ---------------------------------------------
print("\n Saving best model...")

joblib.dump(best_model, f"{MODEL_DIR}/best_model.pkl")
joblib.dump(FEATURE_COLS, f"{MODEL_DIR}/feature_cols.pkl")

imp_df.to_csv(f"{MODEL_DIR}/feature_importance.csv", index=False)
results_df.to_csv(f"{MODEL_DIR}/model_comparison.csv")

print(f"   [ok] best_model.pkl       -> {best_name}")
print(f"   [ok] feature_cols.pkl     -> {len(FEATURE_COLS)} features")
print(f"   [ok] feature_importance.csv")
print(f"   [ok] model_comparison.csv")

# ---------------------------------------------
# 8. FINAL SUMMARY
# ---------------------------------------------
print("\n" + "="*58)
print("  TRAINING COMPLETE")
print("="*58)
print(f"\n   Best Model  : {best_name}")
print(f"   WMAPE       : {best_wmape:.2f}%")
print(f"   R          : {results_df.loc[best_name, 'R2']:.4f}")
print(f"   RMSE        : {results_df.loc[best_name, 'RMSE']:.2f} units")

print(f"\n   Top 5 Features:")
for i, row in imp_df.head(5).iterrows():
    pct = row["importance"] / imp_df["importance"].sum() * 100
    print(f"     {i+1}. {row['feature']:<35} {pct:.1f}%")

print(f"\n  [ok] Ready for Step 4: Predict Future Demand")
print("="*58)

"""
======================================================
  Williams-Sonoma Demand Forecasting
  Step 4: Model Testing & Detailed Evaluation
======================================================
  Outputs (all saved to ws_model/test_results/):
    metrics_overall.json         WMAPE, RMSE, MAE, R, MAPE per model
    metrics_by_brand.csv         breakdown by brand (WS / PB / WE)
    metrics_by_category.csv      breakdown by category
    metrics_by_sku.csv           per-SKU error table
    metrics_by_week.csv          weekly error over the test window
    residuals.csv                date, sku, actual, predicted, error, pct_error
    event_window_accuracy.csv    accuracy split: event days vs normal days
    calibration.csv              decile-level calibration (predicted vs actual)
======================================================
"""

import pandas as pd
import numpy as np
import json, os, joblib, warnings
warnings.filterwarnings("ignore")

from sklearn.metrics import mean_squared_error, mean_absolute_error

DATA_DIR   = "ws_demand_dataset"
MODEL_DIR  = "ws_model"
OUT_DIR    = f"{MODEL_DIR}/test_results"
os.makedirs(OUT_DIR, exist_ok=True)

# -- Metrics helpers ----------------------------------------------------------

def wmape(y_true, y_pred):
    return np.sum(np.abs(y_true - y_pred)) / (np.sum(np.abs(y_true)) + 1e-9) * 100

def mape(y_true, y_pred):
    mask = y_true > 0
    return np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100

def r2(y_true, y_pred):
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - y_true.mean()) ** 2)
    return 1 - ss_res / (ss_tot + 1e-9)

def metrics_dict(y_true, y_pred, name=""):
    return {
        "group":  name,
        "n":      int(len(y_true)),
        "wmape":  round(wmape(y_true, y_pred), 4),
        "mape":   round(mape(y_true, y_pred), 4),
        "rmse":   round(float(np.sqrt(mean_squared_error(y_true, y_pred))), 4),
        "mae":    round(float(mean_absolute_error(y_true, y_pred)), 4),
        "r2":     round(float(r2(y_true, y_pred)), 4),
        "bias":   round(float((y_pred - y_true).mean()), 4),   # + = over-forecast
        "p90_ae": round(float(np.percentile(np.abs(y_true - y_pred), 90)), 4),
    }

# -- Load artifacts -----------------------------------------------------------

print("Loading data and model...")
df         = pd.read_csv(f"{DATA_DIR}/ml_ready_data.csv", parse_dates=["date"])
model      = joblib.load(f"{MODEL_DIR}/best_model.pkl")
feat_cols  = joblib.load(f"{MODEL_DIR}/feature_cols.pkl")
events_df  = pd.read_csv(f"{DATA_DIR}/events_data.csv",   parse_dates=["event_date"])

SPLIT_DATE = "2024-10-01"
test = df[df["date"] >= SPLIT_DATE].copy()
X_test, y_test = test[feat_cols], test["units_sold"]

print(f"Test rows: {len(test):,}  |  date range: {test['date'].min().date()} -> {test['date'].max().date()}")

# -- Predict ------------------------------------------------------------------

test = test.copy()
test["predicted"] = np.maximum(model.predict(X_test), 0)
test["error"]     = test["predicted"] - test["units_sold"]
test["abs_error"] = test["error"].abs()
test["pct_error"] = test["abs_error"] / (test["units_sold"].replace(0, np.nan)) * 100

# -- 1. Overall metrics --------------------------------------------------------

overall = metrics_dict(test["units_sold"].values, test["predicted"].values, "overall")
with open(f"{OUT_DIR}/metrics_overall.json", "w") as f:
    json.dump(overall, f, indent=2)
print(f"\nOverall  WMAPE={overall['wmape']:.2f}%  R={overall['r2']:.4f}  Bias={overall['bias']:+.2f}")

# -- 2. By brand ---------------------------------------------------------------

brand_rows = []
for brand, grp in test.groupby("brand_id"):
    brand_rows.append(metrics_dict(grp["units_sold"].values, grp["predicted"].values, brand))
brand_df = pd.DataFrame(brand_rows)
brand_df.to_csv(f"{OUT_DIR}/metrics_by_brand.csv", index=False)
print("\nBy brand:")
print(brand_df[["group","wmape","rmse","r2","bias"]].to_string(index=False))

# -- 3. By category ------------------------------------------------------------

cat_rows = []
for cat, grp in test.groupby("category"):
    cat_rows.append(metrics_dict(grp["units_sold"].values, grp["predicted"].values, cat))
cat_df = pd.DataFrame(cat_rows).sort_values("wmape")
cat_df.to_csv(f"{OUT_DIR}/metrics_by_category.csv", index=False)
print("\nBy category (sorted by WMAPE):")
print(cat_df[["group","wmape","rmse","r2","bias"]].to_string(index=False))

# -- 4. By SKU -----------------------------------------------------------------

sku_rows = []
for sku, grp in test.groupby("sku_id"):
    row = metrics_dict(grp["units_sold"].values, grp["predicted"].values, sku)
    row["brand_id"] = grp["brand_id"].iloc[0]
    row["category"] = grp["category"].iloc[0]
    sku_rows.append(row)
sku_df = pd.DataFrame(sku_rows).sort_values("wmape")
sku_df.to_csv(f"{OUT_DIR}/metrics_by_sku.csv", index=False)

# -- 5. Weekly error trend -----------------------------------------------------

test["week"] = test["date"].dt.to_period("W").apply(lambda r: r.start_time)
week_rows = []
for wk, grp in test.groupby("week"):
    row = metrics_dict(grp["units_sold"].values, grp["predicted"].values, str(wk.date()))
    week_rows.append(row)
week_df = pd.DataFrame(week_rows)
week_df.to_csv(f"{OUT_DIR}/metrics_by_week.csv", index=False)

# -- 6. Residuals CSV (for scatter / distribution plots) -----------------------

residuals = test[["date","sku_id","brand_id","category",
                   "units_sold","predicted","error","abs_error","pct_error"]].copy()
residuals.to_csv(f"{OUT_DIR}/residuals.csv", index=False)

# -- 7. Event window accuracy --------------------------------------------------

KEY_EVENTS = {
    "thanksgiving": pd.Timestamp("2024-11-28"),
    "black_friday":  pd.Timestamp("2024-11-29"),
    "cyber_monday":  pd.Timestamp("2024-12-02"),
    "christmas":     pd.Timestamp("2024-12-25"),
}

ev_rows = []
for ev_name, ev_date in KEY_EVENTS.items():
    window = test[(test["date"] >= ev_date - pd.Timedelta(days=14)) &
                  (test["date"] <= ev_date + pd.Timedelta(days=3))]
    outside = test[~test.index.isin(window.index)]
    ev_rows.append({
        "event": ev_name,
        "event_date": ev_date.date(),
        "event_window_wmape":  round(wmape(window["units_sold"].values, window["predicted"].values), 4),
        "normal_days_wmape":   round(wmape(outside["units_sold"].values, outside["predicted"].values), 4),
        "event_window_bias":   round((window["predicted"] - window["units_sold"]).mean(), 4),
        "event_n":             len(window),
    })
ev_df = pd.DataFrame(ev_rows)
ev_df.to_csv(f"{OUT_DIR}/event_window_accuracy.csv", index=False)
print("\nEvent window vs normal days:")
print(ev_df[["event","event_window_wmape","normal_days_wmape","event_window_bias"]].to_string(index=False))

# -- 8. Calibration (decile buckets) ------------------------------------------

test["pred_decile"] = pd.qcut(test["predicted"], q=10, labels=False, duplicates="drop")
cal_rows = []
for d, grp in test.groupby("pred_decile"):
    cal_rows.append({
        "decile":         int(d) + 1,
        "mean_predicted": round(grp["predicted"].mean(), 2),
        "mean_actual":    round(grp["units_sold"].mean(), 2),
        "count":          len(grp),
    })
cal_df = pd.DataFrame(cal_rows)
cal_df["calibration_ratio"] = (cal_df["mean_predicted"] / cal_df["mean_actual"]).round(3)
cal_df.to_csv(f"{OUT_DIR}/calibration.csv", index=False)

# -- Summary -------------------------------------------------------------------

print(f"""
{'='*55}
  TEST EVALUATION COMPLETE
{'='*55}
  Overall WMAPE  : {overall['wmape']:.2f}%
  Overall MAPE   : {overall['mape']:.2f}%
  RMSE           : {overall['rmse']:.2f} units
  MAE            : {overall['mae']:.2f} units
  R             : {overall['r2']:.4f}
  Forecast bias  : {overall['bias']:+.2f} units/row
  P90 abs error  : {overall['p90_ae']:.2f} units

  Files in {OUT_DIR}/
    metrics_overall.json
    metrics_by_brand.csv
    metrics_by_category.csv
    metrics_by_sku.csv
    metrics_by_week.csv
    residuals.csv
    event_window_accuracy.csv
    calibration.csv
{'='*55}
""")
