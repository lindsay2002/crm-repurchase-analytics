from pathlib import Path
import re
import pandas as pd

DATA_DIR = Path("data")

ORDERS_PATH = DATA_DIR / "orders.csv"
CATALOGUE_PATH = DATA_DIR / "catalogue.csv"
WISHLIST_PATH = DATA_DIR / "wishlist.csv"

PLACEHOLDER_PREFIXES = [
    "assorted goods",
    "misc lot",
    "spare parts kit",
    "oem item",
    "福袋",
    "accessory pack",
    "限定版 套裝",
    "gift set",
    "sample bundle",
    "雑貨 セット",
    "replacement unit",
    "no brand item",
    "配件 一套",
]


def load_data():
    orders = pd.read_csv(ORDERS_PATH)
    catalogue = pd.read_csv(CATALOGUE_PATH)
    wishlist = pd.read_csv(WISHLIST_PATH)

    orders["order_date"] = pd.to_datetime(orders["order_date"])
    catalogue["listed_date"] = pd.to_datetime(catalogue["listed_date"])
    wishlist["created_at"] = pd.to_datetime(wishlist["created_at"])
    wishlist["deleted_at"] = pd.to_datetime(wishlist["deleted_at"], errors="coerce")

    return orders, catalogue, wishlist


def normalize_item_name(series: pd.Series) -> pd.Series:
    """Basic deterministic normalization before manual product-type mapping."""
    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .str.replace(r"\s+", " ", regex=True)
    )


def derive_base_item_name(series: pd.Series) -> pd.Series:
    """Collapse only known placeholders with an optional numeric suffix."""
    prefixes = "|".join(re.escape(prefix) for prefix in PLACEHOLDER_PREFIXES)
    pattern = rf"\A({prefixes})(?:\s+\d+)?(?:\s+#\d+)?\Z"
    return series.str.replace(pattern, r"\1", regex=True)


def audit_orders(orders: pd.DataFrame) -> None:
    """Step 1: audit only the issues that materially affect the analysis."""

    print("\n=== BASIC STRUCTURE ===")
    print("orders rows:", len(orders))
    print("unique members:", orders["member_id"].nunique())
    print("unique occasions:", orders["occasion_id"].nunique())
    print("date range:", orders["order_date"].min(), "->", orders["order_date"].max())

    # Normalize names
    orders = orders.copy()
    orders["normalized_item_name"] = normalize_item_name(orders["item_name"])
    orders["base_item_name"] = derive_base_item_name(orders["normalized_item_name"])
    orders["is_placeholder"] = orders["base_item_name"].isin(PLACEHOLDER_PREFIXES)

    placeholder_names = orders.loc[orders["is_placeholder"], "base_item_name"]
    assert placeholder_names.notna().all(), "Placeholder rows have missing base_item_name"
    assert placeholder_names.isin(PLACEHOLDER_PREFIXES).all(), "Unknown placeholder base name"

    print("\n=== BASE ITEM AUDIT ===")
    print("unique base item names:", orders["base_item_name"].nunique())
    print("placeholder row count:", orders["is_placeholder"].sum())
    print("placeholder share:", f"{orders['is_placeholder'].mean():.1%}")
    print("identifiable row count:", (~orders["is_placeholder"]).sum())

    print("\n=== PLACEHOLDER COUNTS ===")
    print(
        placeholder_names.value_counts()
        .reindex(PLACEHOLDER_PREFIXES, fill_value=0)
        .to_string()
    )

    print("\n=== ITEM CATEGORY DISTRIBUTION ===")
    print(
        orders["item_category"]
        .value_counts(dropna=False)
        .to_string()
    )

    # Check whether the same item name is consistently assigned to one category
    item_category_counts = (
        orders.groupby("normalized_item_name")["item_category"]
        .nunique()
        .sort_values(ascending=False)
    )

    print("\n=== CATEGORY CONSISTENCY CHECK ===")
    print("unique normalized item names:", orders["normalized_item_name"].nunique())
    print(
        "item names appearing in >1 item_category:",
        (item_category_counts > 1).sum()
    )

    # Show the most frequent item names that appear across multiple categories
    multi_category_items = item_category_counts[item_category_counts > 1].index

    examples = (
        orders[orders["normalized_item_name"].isin(multi_category_items)]
        .groupby("normalized_item_name")
        .agg(
            rows=("normalized_item_name", "size"),
            category_count=("item_category", "nunique")
        )
        .sort_values(["rows", "category_count"], ascending=False)
        .head(10)
    )

    print("\n=== HIGH-FREQUENCY MULTI-CATEGORY EXAMPLES ===")
    print(examples.to_string())

    # Print detailed category distribution for the top example
    if len(examples) > 0:
        example_name = examples.index[0]

        print(f"\n=== CATEGORY SPLIT FOR: {example_name} ===")
        print(
            orders.loc[
                orders["normalized_item_name"] == example_name,
                "item_category"
            ]
            .value_counts()
            .to_string()
        )

    print("\n=== SHOP ITEM NAME USABILITY ===")

    shop_name = (
        orders["shop_item_name"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    unknown_mask = shop_name.isin(
        ["unknown", "", "nan", "none"]
    )

    print("unknown/unusable shop_item_name rows:", unknown_mask.sum())
    print(
        "unknown/unusable share:",
        f"{unknown_mask.mean():.1%}"
    )



# -------------------------------------------------------------------
# Step 2: Deterministic replenishment-based taxonomy
# -------------------------------------------------------------------

# Explicit name cues for this dataset; no category or shop-name inputs.
# Lens rules require both a lens name and a pack quantity with a piece unit.
# Product numbers and suffixes remain intact in base_item_name.
PRODUCT_TYPE_RULES = {
    "Supplements": r"^(?:nature made multivitamin|naturemade multi vitamin|維他命|vitamin d3|omega 3 fish oil|ビタミンc サプリメント)",
    "Trading cards": r"^(?:psa 10 charizard|pokemon card|ポケモンカード|寶可夢 卡牌|weiss schwarz|one piece card)",
    "Skincare": r"^(?:化粧水|hada labo lotion|sk-ii facial treatment essence|skii fte|面霜|精華)",
    "Snacks": r"^(?:kitkat|kit kat|零食|お菓子|calbee jagabee|薯片)",
    "Coffee": r"^(?:nespresso arpeggio|咖啡膠囊|blue bottle whole bean|ドリップコーヒー|掛耳咖啡)",
    "Tea": r"^(?:lupicia sakura|茶包|烏龍茶|お茶)",
    "Haircare": r"^(?:洗頭水|シャンプー|kerastase bain|護髮素)",
    "Contact lenses (30-pack)": r"^(?=.*(?:隱形眼鏡|コンタクトレンズ|\bacuvue\b))(?=.*(?<![\d#])30\s*-?\s*(?:pcs\b|pieces?\b|pack\b|p\b|片|枚)).*$",
    "Contact lenses (90-pack)": r"^(?=.*(?:隱形眼鏡|コンタクトレンズ|\bacuvue\b))(?=.*(?<![\d#])90\s*-?\s*(?:pcs\b|pieces?\b|pack\b|p\b|片|枚)).*$",
    "Figures": r"^(?:funko pop|nendoroid|figma 初音ミク)",
    "Apparel": r"^(?:hoodie|衛衣|gu ワイドパンツ|uniqlo u crew neck)",
    "Gacha": r"^(?:一番賞|bandai ichiban kuji)",
    "Pet supplies": r"^(?:royalcanin|royal canin|狗糧|キャットフード|貓砂|cat litter)",
    "Shoes": r"^(?:nike dunk|スニーカー|new balance 990v6|波鞋)",
    "Protein powder": r"^(?:optimum nutrition gold standard|on gold standard whey|蛋白粉|プロテイン)",
    "Bags": r"^(?:手袋|coach tabby|porter tanker shoulder bag|リュック)",
    "Electronics": r"^(?:モバイルバッテリー|anker powercore|sony wh-1000xm|藍牙耳機)",
    "Baby diapers": r"^(?:紙おむつ|merries|尿片)",
    "Baby formula": r"^(?:嬰兒奶粉|aptamil|粉ミルク|奶粉)",
}


def derive_product_type(base_item_name: pd.Series) -> pd.Series:
    """Assign a label only after checking all rules for overlapping matches."""
    matches = pd.DataFrame({
        label: base_item_name.str.contains(pattern, regex=True, na=False)
        for label, pattern in PRODUCT_TYPE_RULES.items()
    })
    match_count = matches.sum(axis=1)
    conflicts = match_count.gt(1)
    if conflicts.any():
        details = matches.loc[conflicts].copy()
        details.insert(0, "base_item_name", base_item_name.loc[conflicts])
        print("multi-match conflicts:")
        print(details.drop_duplicates().to_string(index=False))
    assert not conflicts.any(), "Item names match multiple product-type rules"

    product_type = pd.Series(pd.NA, index=base_item_name.index, dtype="string")
    for label in PRODUCT_TYPE_RULES:
        product_type.loc[matches[label]] = label

    placeholders = base_item_name.isin(PLACEHOLDER_PREFIXES)
    assert product_type.loc[placeholders].isna().all(), "Placeholder received a product type"
    return product_type


def map_product_types(orders: pd.DataFrame) -> pd.DataFrame:
    out = orders.copy()
    out["normalized_item_name"] = normalize_item_name(out["item_name"])
    out["base_item_name"] = derive_base_item_name(out["normalized_item_name"])
    out["is_placeholder"] = out["base_item_name"].isin(PLACEHOLDER_PREFIXES)

    print("\n=== PRODUCT TYPE MAPPING QA ===")
    out["product_type"] = derive_product_type(out["base_item_name"])

    identifiable = ~out["is_placeholder"]
    mapped = identifiable & out["product_type"].notna()
    unmapped = identifiable & out["product_type"].isna()
    type_count = out.loc[identifiable, "product_type"].nunique()
    print("identifiable rows:", identifiable.sum())
    print("mapped rows:", mapped.sum())
    print("unmapped rows:", unmapped.sum())
    print("number of product types:", type_count)
    print("row count and unique base item names by product type:")
    print(
        out.loc[mapped].groupby("product_type")
        .agg(rows=("base_item_name", "size"),
             unique_item_names=("base_item_name", "nunique"))
        .reindex(PRODUCT_TYPE_RULES, fill_value=0)
        .to_string()
    )
    print("unmapped item names:", out.loc[unmapped, "base_item_name"].unique().tolist())
    print("multi-match conflicts: none")

    assert out.loc[out["is_placeholder"], "product_type"].isna().all(), "Placeholder received a product type"
    assert unmapped.sum() == 0, "Unmapped identifiable rows remain"
    # derive_product_type already verifies at most one rule per row.
    assert out.loc[identifiable, "product_type"].notna().all(), "Identifiable row lacks exactly one product type"
    assert type_count == 19, f"Expected 19 product types, found {type_count}"

    return out


def build_purchase_events(mapped_orders: pd.DataFrame) -> pd.DataFrame:
    """Step 3: one event per member x product type x occasion x date."""
    grain = ["member_id", "product_type", "occasion_id", "order_date"]
    identifiable_mapped = (
        ~mapped_orders["is_placeholder"] & mapped_orders["product_type"].notna()
    )
    events = (
        mapped_orders.loc[identifiable_mapped, grain]
        .drop_duplicates(subset=grain)
        .sort_values(["member_id", "product_type", "order_date", "occasion_id"])
        .reset_index(drop=True)
    )
    duplicates = events.duplicated(subset=grain, keep=False)
    print("\n=== PURCHASE EVENT QA ===")
    print("identifiable mapped order rows:", identifiable_mapped.sum())
    print("purchase-event rows after deduplication:", len(events))
    print("unique members in purchase-event table:", events["member_id"].nunique())
    print("number of product types:", events["product_type"].nunique())
    print("duplicate rows remaining at the analytical grain:", duplicates.sum())
    assert not duplicates.any(), (
        "Duplicate purchase events:\n" + events.loc[duplicates].to_string(index=False)
    )
    return events


def raw_repeat_summary(events: pd.DataFrame) -> pd.DataFrame:
    """Step 4: buyers, repeat buyers, repeat rate, and sequential gap distribution."""
    counts = (
        events.groupby(["product_type", "member_id"])["occasion_id"]
        .nunique()
        .rename("purchase_events")
        .reset_index()
    )

    summary = (
        counts.groupby("product_type")
        .agg(
            buyers=("member_id", "nunique"),
            repeat_buyers=("purchase_events", lambda s: (s >= 2).sum()),
        )
        .reset_index()
    )
    summary["raw_repeat_rate"] = summary["repeat_buyers"] / summary["buyers"]

    gap_events = events.sort_values(
        ["member_id", "product_type", "order_date", "occasion_id"]
    ).copy()
    gap_events["prev_order_date"] = (
        gap_events.groupby(["member_id", "product_type"])["order_date"].shift(1)
    )
    gap_events["gap_days"] = (
        gap_events["order_date"].dt.normalize()
        - gap_events["prev_order_date"].dt.normalize()
    ).dt.days

    gaps = gap_events.dropna(subset=["gap_days"])

    gap_summary = (
        gaps.groupby("product_type")["gap_days"]
        .agg(
            p25_gap=lambda s: s.quantile(0.25),
            median_gap="median",
            p75_gap=lambda s: s.quantile(0.75),
        )
        .reset_index()
    )

    summary = (
        summary.merge(gap_summary, on="product_type", how="left")
        .sort_values("raw_repeat_rate", ascending=False)
        .reset_index(drop=True)
    )
    print("\n=== RAW REPEAT SUMMARY ===")
    print(summary.to_string(index=False, formatters={
        "raw_repeat_rate": "{:.1%}".format,
        "p25_gap": "{:.1f}".format,
        "median_gap": "{:.1f}".format,
        "p75_gap": "{:.1f}".format,
    }))

    negative = gaps["gap_days"].lt(0)
    print("\n=== RAW GAP QA ===")
    print("total sequential repeat gaps:", len(gaps))
    print("minimum gap:", gaps["gap_days"].min())
    print("maximum gap:", gaps["gap_days"].max())
    print("zero-day gap count:", gaps["gap_days"].eq(0).sum())
    print("negative-gap count:", negative.sum())

    assert not negative.any(), (
        "Negative sequential gaps:\n" + gaps.loc[negative].to_string(index=False)
    )
    invalid_buyers = summary["repeat_buyers"].gt(summary["buyers"])
    assert not invalid_buyers.any(), (
        "Repeat buyers exceed buyers:\n"
        + summary.loc[invalid_buyers].to_string(index=False)
    )
    invalid_rates = ~summary["raw_repeat_rate"].between(0, 1)
    assert not invalid_rates.any(), (
        "Raw repeat rates outside [0, 1]:\n"
        + summary.loc[invalid_rates].to_string(index=False)
    )
    actual_types = set(summary["product_type"])
    expected_types = set(PRODUCT_TYPE_RULES)
    assert len(actual_types) == 19 and actual_types == expected_types, (
        f"Product-type mismatch: missing={sorted(expected_types - actual_types)}, "
        f"unexpected={sorted(actual_types - expected_types)}, count={len(actual_types)}"
    )
    return summary


def standardized_repeat_rate(events: pd.DataFrame, window_days: int) -> pd.DataFrame:
    """Step 6: fixed follow-up window to reduce right-censoring bias."""
    data_end = events["order_date"].max()

    first_purchase = (
        events.groupby(["member_id", "product_type"], as_index=False)["order_date"]
        .min()
        .rename(columns={"order_date": "first_purchase_date"})
    )

    eligible = first_purchase[
        first_purchase["first_purchase_date"]
        <= data_end - pd.Timedelta(days=window_days)
    ].copy()

    merged = events.merge(
        eligible,
        on=["member_id", "product_type"],
        how="inner",
    )
    merged["days_from_first"] = (
        merged["order_date"] - merged["first_purchase_date"]
    ).dt.days
    negative = merged["days_from_first"].lt(0)
    assert not negative.any(), (
        f"Negative days from first purchase ({window_days}d):\n"
        + merged.loc[negative].to_string(index=False)
    )

    repeat_within_window = (
        merged[
            (merged["days_from_first"] > 0)
            & (merged["days_from_first"] <= window_days)
        ]
        .groupby(["member_id", "product_type"])
        .size()
        .rename("repeat_events")
        .reset_index()
    )

    member_level = eligible.merge(
        repeat_within_window,
        on=["member_id", "product_type"],
        how="left",
    )
    member_level["repeated"] = member_level["repeat_events"].fillna(0).gt(0)

    result = (
        member_level.groupby("product_type")
        .agg(
            eligible_buyers=("member_id", "nunique"),
            repeat_buyers=("repeated", "sum"),
        )
        .reset_index()
    )
    result["repeat_rate"] = result["repeat_buyers"] / result["eligible_buyers"]
    result["window_days"] = window_days

    invalid_buyers = result["eligible_buyers"].le(0)
    assert not invalid_buyers.any(), (
        f"Nonpositive eligible buyers ({window_days}d):\n"
        + result.loc[invalid_buyers].to_string(index=False)
    )
    invalid_rates = ~result["repeat_rate"].between(0, 1)
    assert not invalid_rates.any(), (
        f"Repeat rates outside [0, 1] ({window_days}d):\n"
        + result.loc[invalid_rates].to_string(index=False)
    )
    expected_types = set(eligible["product_type"])
    actual_types = set(result["product_type"])
    assert actual_types == expected_types, (
        f"Eligible product-type mismatch ({window_days}d): "
        f"missing={sorted(expected_types - actual_types)}, "
        f"unexpected={sorted(actual_types - expected_types)}"
    )

    return result


def crm_trigger_candidates(raw: pd.DataFrame, rr150: pd.DataFrame) -> pd.DataFrame:
    """Calculate timing candidates from existing raw gaps and 150-day rates."""
    combined = raw.merge(
        rr150[["product_type", "repeat_rate"]].rename(
            columns={"repeat_rate": "repeat_rate_150d"}
        ),
        on="product_type", how="left", validate="one_to_one",
    )
    candidates = combined.loc[
        combined["buyers"].ge(100)
        & combined["repeat_rate_150d"].ge(0.4)
        & combined["median_gap"].le(60),
        ["product_type", "buyers", "repeat_rate_150d", "median_gap", "p25_gap"],
    ].copy()
    # Behavioural anchor is the P25 gap: by that point ~25% of repeat purchases
    # have already happened, so we reach customers before most of them rebuy.
    # Rounded to whole weeks to keep CRM configuration manageable.
    candidates["trigger_day"] = (
        (candidates["p25_gap"] / 7).round().astype(int) * 7
    )
    candidates = candidates.sort_values(
        ["trigger_day", "product_type"]
    ).reset_index(drop=True)

    checks = {
        "buyers must be >= 100": candidates["buyers"].ge(100),
        "150d repeat rate must be >= 0.4": candidates["repeat_rate_150d"].ge(0.4),
        "median gap must be <= 60": candidates["median_gap"].le(60),
        "trigger day must be > 0": candidates["trigger_day"].gt(0),
    }
    for message, valid in checks.items():
        assert valid.all(), message + "\n" + candidates.loc[~valid].to_string(index=False)

    print("\n=== CRM CANDIDATE TYPES ===")
    print(candidates.to_string(index=False, formatters={
        "repeat_rate_150d": "{:.1%}".format,
        "median_gap": "{:.1f}".format,
        "p25_gap": "{:.1f}".format,
    }))

    print("\n=== CRM TRIGGER GROUPS ===")
    for day, grp in candidates.groupby("trigger_day"):
        print(f"Day {day}: {', '.join(grp['product_type'])}")
    return candidates


def catalogue_eligibility_masks(catalogue: pd.DataFrame) -> pd.DataFrame:
    """Content checks only; image URLs are not fetched or availability-tested."""
    images = catalogue["image_url"].astype("string").str.strip().str.lower()
    names = catalogue["product_title"].astype("string").str.strip()
    return pd.DataFrame({
        "in_stock": catalogue["stock_status"].eq("in_stock").fillna(False),
        "missing_image": images.isna() | images.eq("").fillna(False),
        "placeholder_image": images.str.contains("placeholder", regex=False, na=False),
        "missing_name": names.isna() | names.eq("").fillna(False),
    })


def audit_recommendation_inputs(catalogue: pd.DataFrame, wishlist: pd.DataFrame) -> None:
    masks = catalogue_eligibility_masks(catalogue)
    print("\n=== CATALOGUE AUDIT ===")
    print("row count:", len(catalogue))
    print("unique item ids:", catalogue["product_id"].nunique())
    print("duplicate item ids (rows beyond first):", catalogue.duplicated("product_id").sum())
    print("stock status distribution:")
    print(catalogue["stock_status"].value_counts(dropna=False).to_string())
    print("missing image_url count:", masks["missing_image"].sum())
    print("placeholder image count:", masks["placeholder_image"].sum())
    print("missing product name count:", masks["missing_name"].sum())

    print("\n=== WISHLIST AUDIT ===")
    print("row count:", len(wishlist))
    print("unique members:", wishlist["member_id"].nunique())
    print("unique item ids:", wishlist["product_id"].nunique())
    print("duplicate member-item pairs (rows beyond first):",
          wishlist.duplicated(["member_id", "product_id"]).sum())
    print("wishlist status distribution (derived from deleted_at):")
    print(wishlist["deleted_at"].notna().map(
        {True: "deleted", False: "active"}
    ).value_counts().to_string())


def derive_eligible_recommendations(
    catalogue: pd.DataFrame, wishlist: pd.DataFrame, orders: pd.DataFrame
) -> pd.DataFrame:
    """Return member-product candidates with intent flags for all order members.

    All catalogue products are considered for every member in the analysis audience.
    Any deleted wishlist record excludes that pair, even if an active record exists.
    Members absent from wishlist can use the same catalogue pool without exclusions.
    """
    assert catalogue["product_id"].notna().all(), "Missing catalogue product ids"
    assert not catalogue["product_id"].duplicated().any(), "Duplicate catalogue product ids"
    masks = catalogue_eligibility_masks(catalogue)
    bad_stock = ~masks["in_stock"]
    bad_image = masks["missing_image"] | masks["placeholder_image"]
    # Sequential removals keep product-level counts additive.
    removed_image = ~bad_stock & bad_image
    removed_name = ~bad_stock & ~bad_image & masks["missing_name"]
    valid = ~bad_stock & ~bad_image & ~masks["missing_name"]
    pool = catalogue.loc[valid, ["product_id"]]

    keys = ["member_id", "product_id"]
    signals = wishlist.assign(
        is_deleted=wishlist["deleted_at"].notna(),
        is_active_wishlist=wishlist["deleted_at"].isna(),
    ).groupby(keys, as_index=False)[["is_deleted", "is_active_wishlist"]].any()
    members = orders[["member_id"]].dropna().drop_duplicates()
    # Full cross join is for demonstration on this dataset only. Production would
    # generate candidates per member at send time rather than materialise the grid.
    pairs = pool.merge(members, how="cross").merge(
        signals, on=keys, how="left", validate="one_to_one"
    )
    deleted = pairs["is_deleted"].eq(True)
    eligible = pairs.loc[~deleted, keys + ["is_active_wishlist"]].copy()
    eligible["is_active_wishlist"] = eligible["is_active_wishlist"].eq(True)
    eligible = eligible.reset_index(drop=True)

    print("\n=== ELIGIBILITY QA ===")
    print("catalogue rows before filtering:", len(catalogue))
    print("removed by stock (catalogue rows):", bad_stock.sum())
    print("removed by image (remaining catalogue rows):", removed_image.sum())
    print("removed by missing name (remaining catalogue rows):", removed_name.sum())
    print("eligible catalogue products before member exclusions:", len(pool))
    print("eligible pool by category_l0:")
    print(catalogue.loc[valid, "category_l0"].value_counts().to_string())
    print("analysis audience members (from orders):", len(members))
    print("member-product rows before wishlist exclusion:", len(pairs))
    print("removed by deleted wishlist exclusion (member-product rows):", deleted.sum())
    print("eligible rows after filtering (member-product rows):", len(eligible))
    print("eligible rows with active wishlist intent:", eligible["is_active_wishlist"].sum())

    selected = catalogue["product_id"].isin(eligible["product_id"].unique())
    assert masks.loc[selected, "in_stock"].all(), "Eligible item is not in stock"
    assert not bad_image.loc[selected].any(), "Eligible item has missing/placeholder image"
    assert not masks.loc[selected, "missing_name"].any(), "Eligible item has missing name"
    deleted_keys = pd.MultiIndex.from_frame(signals.loc[signals["is_deleted"], keys])
    assert not pd.MultiIndex.from_frame(eligible[keys]).isin(deleted_keys).any(), (
        "Deleted wishlist member-product pairs remain eligible"
    )
    return eligible


def main():
    orders, catalogue, wishlist = load_data()

    audit_orders(orders)

    mapped_orders = map_product_types(orders)
    events = build_purchase_events(mapped_orders)
    occasion_dates = orders.groupby("occasion_id")["order_date"].nunique()
    events_without_date = events.drop_duplicates(
        subset=["member_id", "product_type", "occasion_id"]
    )
    print("\n=== OCCASION DATE QA ===")
    print("max unique order dates per occasion:", occasion_dates.max())
    print("occasions spanning >1 date:", occasion_dates.gt(1).sum())
    print("purchase events excluding order_date from grain:", len(events_without_date))
    print("purchase events at current grain:", len(events))
    print("difference:", len(events) - len(events_without_date))
    raw = raw_repeat_summary(events)
    rr90 = standardized_repeat_rate(events, 90)
    rr150 = standardized_repeat_rate(events, 150)

    print("\n=== CENSORING ANALYSIS ===")
    censoring = pd.concat([rr90, rr150], ignore_index=True).sort_values(
        ["window_days", "product_type"]
    )
    print(censoring.to_string(
        index=False, formatters={"repeat_rate": "{:.1%}".format}
    ))

    comparison = (
        raw[["product_type", "raw_repeat_rate"]]
        .merge(
            rr90[["product_type", "repeat_rate"]].rename(
                columns={"repeat_rate": "repeat_rate_90d"}
            ),
            on="product_type", how="left", validate="one_to_one",
        )
        .merge(
            rr150[["product_type", "repeat_rate"]].rename(
                columns={"repeat_rate": "repeat_rate_150d"}
            ),
            on="product_type", how="left", validate="one_to_one",
        )
        .sort_values("product_type")
    )
    print("\n=== WINDOW COMPARISON ===")
    print(comparison.to_string(index=False, na_rep="N/A", formatters={
        column: "{:.1%}".format
        for column in ["raw_repeat_rate", "repeat_rate_90d", "repeat_rate_150d"]
    }))

    candidates = crm_trigger_candidates(raw, rr150)
    trigger_category_members = events.loc[
        events["product_type"].isin(candidates["product_type"]), "member_id"
    ].nunique()
    total_members = orders["member_id"].nunique()
    reach_rate = trigger_category_members / total_members if total_members else 0.0
    print("\n=== CRM REACH QA ===")
    print("trigger category members:", trigger_category_members)
    print("total members:", total_members)
    print("reach rate:", f"{reach_rate:.1%}")
    audit_recommendation_inputs(catalogue, wishlist)
    print("\n=== ORDERS TO CATALOGUE JOIN ===")
    shared = set(orders.columns) & set(catalogue.columns)
    print("shared columns:", shared if shared else "none")
    order_names = set(orders["item_name"].astype(str).str.strip().str.lower())
    catalogue_names = set(
        catalogue["product_title"].astype(str).str.strip().str.lower()
    )
    print("distinct order item names:", len(order_names))
    print("distinct catalogue product titles:", len(catalogue_names))
    print("exact item_name = product_title matches:", len(order_names & catalogue_names))
    derive_eligible_recommendations(catalogue, wishlist, orders)


if __name__ == "__main__":
    main()
