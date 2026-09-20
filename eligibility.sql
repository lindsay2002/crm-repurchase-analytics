-- CRM repurchase analytics, step 2: Recommendation eligibility
-- Candidate pool starts from the full catalogue, not from wishlist.

WITH members AS (
    SELECT DISTINCT member_id FROM orders
),
hard_eligible AS (
    SELECT *
    FROM catalogue
    -- 515 items (29%): customer clicks through to a sold or delisted page.
    WHERE stock_status = 'in_stock'
      -- 97 items: the email card renders as a broken image.
      AND image_url IS NOT NULL
      AND TRIM(image_url) <> ''
      -- 55 items: a grey placeholder sits next to a price and reads as a bug.
      AND LOWER(image_url) NOT LIKE '%placeholder%'
      -- 0 items today; guards against a feed break rendering an empty title.
      AND product_title IS NOT NULL
      AND TRIM(product_title) <> ''
      -- 0 items today; guards against a null or zero price reaching a send.
      AND price_hkd > 0
),
deleted_wishlist AS (
    SELECT DISTINCT member_id, product_id
    FROM wishlist
    WHERE deleted_at IS NOT NULL
),
active_wishlist AS (
    SELECT DISTINCT member_id, product_id
    FROM wishlist
    WHERE deleted_at IS NULL
)
SELECT
    m.member_id,
    h.product_id,
    h.product_title,
    h.category_l0,
    h.brand,
    h.price_hkd,
    h.image_url,
    CASE WHEN a.product_id IS NOT NULL THEN 1 ELSE 0 END AS is_active_wishlist
FROM members m
CROSS JOIN hard_eligible h
LEFT JOIN deleted_wishlist d
    ON d.member_id = m.member_id AND d.product_id = h.product_id
LEFT JOIN active_wishlist a
    ON a.member_id = m.member_id AND a.product_id = h.product_id
-- 4,181 of 4,477,440 member-product combinations (0.09%): without this we
-- recommend an item the member manually removed. Small volume, but the
-- customer sees it.
WHERE d.product_id IS NULL;

-- Production rule not implementable reliably with the available data:
-- Exclude a recently purchased same SKU / equivalent product.
-- orders.csv has no catalogue product_id, so historical purchases cannot be
-- mapped reliably to specific catalogue SKUs.
