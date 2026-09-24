-- =====================================================================
-- Migrates data from the OLD phone/laptop/headphone tables (three
-- bespoke tables, one per category -- the schema this project used
-- before it scaled to "sell everything a store like this carries") into
-- the NEW generic `products` table (one table, a `category` column, and
-- a JSON `attributes` column for whatever specs that category has).
--
-- See backend/DATABASE/SQL_CONNECTOR.py's module docstring for why the
-- schema changed, and sample_data_products.sql for the `products`
-- CREATE TABLE statement (run that file's CREATE TABLE block first, or
-- run this after it).
--
-- This assumes your phone/laptop/headphone tables already have the
-- optional enrichment columns from the old sample_data_300.sql
-- (mrp/units_available/rating/online_link/offline_availability). If you
-- never ran that file, those columns won't exist -- delete the
-- corresponding lines from the SELECTs below (MySQL will error "Unknown
-- column" otherwise) and the equivalent fields simply won't be set on
-- the migrated rows, same as when a real catalog doesn't track them
-- (see WORKFLOW/recommendations.py's module docstring).
--
-- Safe to run once against a fresh `products` table. Running it twice
-- will duplicate every row -- TRUNCATE TABLE products first if you need
-- to re-run it.
--
--   mysql -u <username> -p retail_shop < migrate_to_products_table.sql
--
-- After it lands, restart the backend once (or delete
-- WORKFLOW/chroma_db/) so the row-count sync in SQL_CONNECTOR.py notices
-- the migrated rows and embeds them into Chroma.
-- =====================================================================

INSERT INTO products (
    category, name, brand, price, mrp, units_available, rating,
    online_link, offline_availability, attributes
)
SELECT
    'Mobile',
    name,
    brand,
    price,
    mrp,
    units_available,
    rating,
    online_link,
    offline_availability,
    JSON_OBJECT(
        'ram', ram,
        'storage', storage,
        'processor', processor,
        'color', color
    )
FROM phone;

INSERT INTO products (
    category, name, brand, price, mrp, units_available, rating,
    online_link, offline_availability, attributes
)
SELECT
    'Laptop',
    name,
    brand,
    price,
    mrp,
    units_available,
    rating,
    online_link,
    offline_availability,
    JSON_OBJECT(
        'ram', ram,
        'storage', storage,
        'processor', processor,
        'color', color
    )
FROM laptop;

INSERT INTO products (
    category, name, brand, price, mrp, units_available, rating,
    online_link, offline_availability, attributes
)
SELECT
    'Headphone',
    name,
    brand,
    price,
    mrp,
    units_available,
    rating,
    online_link,
    offline_availability,
    JSON_OBJECT(
        'type', type,
        'quality', quality,
        'color', color
    )
FROM headphone;

-- Optional cleanup once you've verified the migrated rows in `products`
-- look right (SELECT category, COUNT(*) FROM products GROUP BY category):
--
--   DROP TABLE phone, laptop, headphone;
