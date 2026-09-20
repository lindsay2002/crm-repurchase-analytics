# CRM Repurchase Analytics Findings

## Executive Summary

Eight product types show consistent replenishment behaviour and are suitable
for initial CRM trigger configuration. Together they reach **2,942 of 3,840
members (76.6%)**.

The constraint is on the other side. Repurchase behaviour is measurable at
product-type level, but the current data does not support a reliable mapping
from that behaviour to specific catalogue SKUs. Timing can be configured;
reliably matching the right catalogue SKU to that timing cannot yet be done
with the available data.

---

## 1. Product Types with Repeat Behaviour

Selection rule: at least 100 buyers, a repeat rate of 40% or more over a fixed
150-day window, and a median purchase gap of 60 days or less.

| Product type | Buyers | Repeat rate (150d) | Median gap | 75th pct | Trigger |
|---|---:|---:|---:|---:|---:|
| Snacks | 800 | 57.4% | 20d | 31d | Day 14 |
| Tea | 420 | 53.7% | 25d | 38d | Day 14 |
| Pet supplies | 130 | 62.2% | 28d | 39d | Day 14 |
| Coffee | 470 | 57.8% | 31d | 48d | Day 21 |
| Skincare | 900 | 55.1% | 27d | 43d | Day 21 |
| Supplements | 1,150 | 52.7% | 28d | 42d | Day 21 |
| Haircare | 410 | 53.7% | 39d | 59d | Day 28 |
| Contact lenses (30-pack) | 282 | 50.6% | 56d | 80d | Day 35 |

Gaps are right-skewed, so the 75th percentile is the more useful number for the
other end of the campaign: past it, a customer looks lapsed rather than due,
and a different message applies.

Timing uses the P25 purchase gap — by that point roughly a quarter of repeat
purchases have happened, so we arrive before most customers rebuy — rounded to
whole weeks. Rankings hold under both a 90-day and a 150-day window.

These are hypotheses drawn from historical behaviour, not estimates of optimal
send time, and should be validated through controlled testing.

---

## 2. Additional Behavioural Signals

**Baby diapers** — 35 buyers, median gap 14 days. The shortest and tightest
cycle in the dataset, exactly the pattern this campaign is built for, but too
small a base to commit to.

**Protein powder** — 80 buyers. The signal becomes more visible under the
150-day window, but the sample remains below the activation threshold.

**Pet supplies** qualifies on all three rules and has the highest repeat rate
in the set, but the result is based on only 130 buyers. Additional observations
would improve confidence before wider activation.

---

## 3. Which Items May Appear in Recommendations

A member-product recommendation may appear if the item is in stock, has a real
image, title and price, and that member has not previously deleted it from
their wishlist. Active wishlist items can be used as a ranking signal, with
remaining recommendations filled from the eligible catalogue.

Candidates start from the full catalogue, not wishlist items. Only 1,500 of
3,840 members have any wishlist activity, so a wishlist-sourced pool would
leave 61% of the base unreachable.

| Rule | What goes wrong without it |
|---|---|
| Only in-stock items | The customer clicks through to a sold or delisted page |
| Valid image required | The card renders broken, or shows a grey placeholder beside a price |
| Non-empty product title | A blank card goes out with a price next to it |
| Positive price | A zero or missing price reaches a live send |
| Exclude deleted wishlist items | We push back an item the member manually removed |
| Active wishlist ranks, does not filter | Gating on it silences most of the audience |

- Total catalogue items: **1,800**
- Removed as not in stock: **515**
- Of the remainder, removed for a missing or placeholder image: **119**
- Eligible: **1,166**

The title and price guards match nothing in this dataset. They stay in because
a broken catalogue feed fails quietly, and the cost of catching it here is zero.

The deleted-wishlist rule removes **4,181 of 4,477,440** member-product
combinations (0.09%). Small volume, but it is the one exclusion the customer
would personally notice.

---

## 4. The Main Blocker

**The current data supports category-level repurchase timing, but not a
reliable mapping from that behaviour to specific catalogue SKUs.**

- Historical orders and catalogue data do not share a reliable product-level
  identifier, and not a single order item name matches a catalogue product
  title exactly.
- **1,076 of the 1,166 eligible items (92%) are Games & Toys**, while every
  replenishment category above is a consumable.

Without this link, historical repurchase behaviour cannot determine which
current catalogue items should be recommended.

The campaign timing can be configured correctly, but SKU-level recommendations
cannot yet be reliably generated from the available data. In the meantime the
timing segments remain usable for wishlist-based and category-level sends.

---

## 5. Analytical Limitations

- The product taxonomy is my own, derived from item names rather than a source
  hierarchy. `item_category` was tested and found unreliable for behavioural
  analysis: 4,600 of 16,036 distinct item names appear under more than one
  category, and "nature made multivitamin 200ct" (685 rows) is filed under
  Fashion, Toys & Hobby and Food & Grocery among others. Some boundaries in my
  replacement are judgement calls — splitting contact lenses by pack size moved
  that category's median cycle by 37 days, so these choices have real
  consequences.

- 44.7% of order rows were excluded as generic placeholders ("misc lot",
  "gift set", "福袋"). They carry no product semantics, so no replenishment
  cycle can be assigned. If they encode real products in a way I could not
  decode, the category picture shifts.

- Repeat rates move with the observation window. Contact lenses read 40.8% at
  90 days and 50.6% at 150. Rankings are stable; absolute levels are not.

- Pet supplies clears every rule, but on the smallest qualifying sample. More
  observations would improve confidence before committing budget.

---

## 6. Recommended Next Steps

1. Build the order-to-catalogue mapping layer, ideally as a maintained product
   table that can be reviewed and extended. Without it, personalised item
   recommendations cannot reflect what customers actually repurchase.
2. A/B test trigger timing against an earlier and a later send, measuring
   conversion, repeat rate, unsubscribes and incremental revenue.
3. Collect more observations on Baby diapers and Protein powder.

---

## 7. AI Usage

I used ChatGPT, Codex and Claude throughout the project for drafting and
reviewing code, debugging, and pressure-testing analytical decisions. The
most valuable use was challenging whether `item_category` carried a reliable
product identity signal. The analysis showed that it was not suitable for
behavioural analysis, and that redirected the whole approach. I defined the
taxonomy, business rules and SQL logic myself, and checked every output
against the raw data, so each classification is explainable and reproducible.
