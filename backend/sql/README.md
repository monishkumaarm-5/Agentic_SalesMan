# SQL

| Path | Purpose |
|------|---------|
| `seed/01_products.sql` | **Start here.** Creates the `products` table and seeds 96 products across 12 categories (specs in a JSON `attributes` column). |
| `seed/02_customer_feedback.sql` | Adds customer review text to the seeded products (the assistant quotes reviews when relevant). |
| `migrations/add_ingestion_status.sql` | Adds the `ingestion_status` columns to an existing `products` table created before they existed. Safe to re-run. |
| `queries.sql` | Handy queries for exploring the catalog. |
| `legacy/` | Old per-category tables (`phone`/`laptop`/`headphone`) and the script that migrates them into `products`. Only for upgrading very old installs. |

```bash
mysql -u <user> -p <db_name> < sql/seed/01_products.sql
mysql -u <user> -p <db_name> < sql/seed/02_customer_feedback.sql
```

Docker Compose runs both seed files automatically on the first start.

## Adding products

Insert rows into `products`; put category-specific specs into `attributes`
as JSON. New categories need no code changes. The backend notices catalog
changes on its next start and re-indexes. A product is indexed as long as
it has a name, category and price; specs that most products in its category
have but it lacks are filled from its description when possible, and the
row is marked `ingestion_status = 'partial'`.
