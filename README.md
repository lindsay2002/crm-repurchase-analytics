# CRM Repurchase Analytics

An end-to-end CRM analytics project for identifying repeat-purchase opportunities, defining repurchase timing, and generating customer-product eligibility rules using Python and SQL.

## Overview

This project analyzes customer purchase behavior to support targeted CRM campaigns.

The workflow focuses on three main questions:

1. Which product categories show meaningful repeat-purchase behavior?
2. When are customers most likely to repurchase?
3. Which customers and products should be eligible for CRM targeting?

The project combines data auditing, product taxonomy design, repeat-purchase analysis, customer eligibility logic, and SQL-based campaign targeting.

## Project Workflow

### 1. Data Audit

The raw dataset was reviewed for data quality and usability issues, including:

- Duplicate and inconsistent product names
- Placeholder item descriptions
- Inconsistent product categories
- Incomplete product metadata
- Order and purchase-event duplication

This step ensured that downstream repurchase metrics were calculated on reliable purchase events.

### 2. Product Taxonomy

Raw product names were normalized and mapped into a structured product taxonomy.

The taxonomy process included:

- Product-name deduplication and normalization
- Grouping spelling and multilingual variations
- Defining commercially meaningful product categories
- Validating category boundaries using observed repurchase behavior

The final taxonomy covered all identifiable product records with no unmapped items.

### 3. Repeat-Purchase Analysis

Customer purchase events were reconstructed at the customer-product level.

For each product category, the analysis calculated:

- Number of buyers
- Repeat-purchase rate
- Time to second purchase
- P25 repurchase interval
- Median repurchase interval
- P75 repurchase interval

These metrics were used to identify categories with sufficiently strong and consistent repeat-purchase behavior.

### 4. Repurchase Trigger Design

Rather than using a fixed repurchase window for every product category, the project uses observed purchase behavior to define category-specific timing.

The lower quartile of repeat-purchase timing was used as a candidate trigger point, allowing CRM campaigns to reach customers before the median repurchase window.

Categories also required a minimum buyer base to reduce instability caused by small samples.

### 5. CRM Eligibility Logic

The targeting logic starts from the full product catalogue rather than only wishlist items.

Eligible products are filtered by:

- Stock availability
- Valid product image
- Purchase history
- Negative customer intent
- Product-category eligibility

Wishlist information is treated as an additional preference signal rather than the primary source of candidate products.

### 6. SQL Delivery

The final SQL logic translates the analytical findings into campaign-ready eligibility rules.

The SQL layer is designed to identify:

- Eligible customers
- Eligible product categories
- Repurchase timing
- Exclusion conditions
- CRM-ready targeting records

## Key Findings

One example of category-level validation was contact lenses:

| Product Type | Buyers | Repeat Rate | P25 | Median | P75 |
|---|---:|---:|---:|---:|---:|
| 30-pack contact lenses | 282 | 42.9% | 38 days | 56 days | 80 days |
| 90-pack contact lenses | 115 | 20.9% | 48 days | 93 days | 127 days |

The large difference in repeat rate and repurchase timing supports treating the two pack sizes as separate product categories rather than combining them.

## Tech Stack

- Python
- pandas
- SQL
- Data validation
- Customer analytics
- CRM targeting logic
- Product taxonomy
- Repurchase modelling

## Repository Structure

```text
crm-repurchase-analytics/
├── analysis.py
├── eligibility.sql
├── findings.md
└── README.md
```

## Business Impact

The project demonstrates how customer transaction data can be translated into operational CRM rules.

Instead of relying on generic campaign timing or wishlist-only targeting, the approach uses observed customer behavior and catalogue-level filtering to create more robust repurchase opportunities.

## Skills Demonstrated

- Data quality auditing
- SQL-based targeting logic
- Python data analysis
- Customer lifecycle analysis
- Product taxonomy design
- Business-rule implementation
- Translating analytical findings into operational CRM workflows
