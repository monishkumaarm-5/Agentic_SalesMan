-- =====================================================================
-- Adds ingestion-status bookkeeping to `products` (already included in
-- seed/01_products.sql for new installs). Written by the backend's catalog
-- sync (app/catalog/index.py) and checked by the Airflow DAG:
--
--   NULL       -- not synced yet
--   'complete' -- indexed with all the specs its category usually has
--   'partial'  -- indexed, but missing some common specs (listed in
--                 ingestion_missing_fields)
--   'rejected' -- not indexed: missing name, category or price
--
-- Safe to run more than once.
--   mysql -u <user> -p <db_name> < sql/migrations/add_ingestion_status.sql
-- =====================================================================

-- MySQL 8 has no `ADD COLUMN IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS`
-- (those are MariaDB extensions), so each step checks information_schema
-- first and only runs its DDL when needed.

SET @exists := (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'products' AND COLUMN_NAME = 'ingestion_status'
);
SET @ddl := IF(@exists = 0, 'ALTER TABLE products ADD COLUMN ingestion_status VARCHAR(20) NULL', 'DO 0');
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @exists := (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'products' AND COLUMN_NAME = 'ingestion_missing_fields'
);
SET @ddl := IF(@exists = 0, 'ALTER TABLE products ADD COLUMN ingestion_missing_fields JSON NULL', 'DO 0');
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @exists := (
    SELECT COUNT(*) FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'products'
      AND INDEX_NAME = 'idx_products_ingestion_status'
);
SET @ddl := IF(@exists = 0, 'CREATE INDEX idx_products_ingestion_status ON products (ingestion_status)', 'DO 0');
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
