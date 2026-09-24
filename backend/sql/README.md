# SQL Files

| File | Purpose |
|------|---------|
| `sample_data_products.sql` | **Start here.** Creates the `products` table and inserts ~96 products across 12 categories (Mobile, Laptop, TV, Headphone, etc.) with JSON attributes. |
| `sample_queries.sql` | Ready-to-run queries for browsing, filtering, price analysis, stock checks, and JSON attribute lookups — useful for debugging and exploration. |
| `sample_data_300.sql` | Legacy: 300 rows across the old `phone`/`laptop`/`headphone` tables. Only needed if you want to test the migration script. |
| `sample_data_300_batch2.sql` | Legacy: Second batch of 300 rows for the old tables. |
| `migrate_to_products_table.sql` | Migrates rows from the old per-category tables into the unified `products` table. Run after both `sample_data_300*.sql` files. |
| `fix_column_widths.sql` | One-time column width adjustments for the old tables. |

## Quick Start

```bash
# 1. Create the products table and seed it
mysql -u root -p retail_shop < sql/sample_data_products.sql

# 2. (Optional) Explore with sample queries
mysql -u root -p retail_shop < sql/sample_queries.sql
```
