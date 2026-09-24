-- =====================================================================
-- Adds ingestion-status bookkeeping to the `products` table, used by
-- the RAG completeness gate in backend/DATABASE/SQL_CONNECTOR.py
-- (_product_documents / _record_incomplete) and by
-- backend/airflow/dags/catalog_sync_dag.py's verify_collection task.
--
-- A product that's missing a required field for its category (see
-- backend/TOOLS/product_schema.py's REQUIRED_FIELDS) is never embedded
-- into Chroma; this column is where that decision gets recorded so it's
-- visible from SQL, not just from the backend's logs.
--
--   NULL       -- never evaluated yet (a row from before this migration
--                 ran, or before the connector's first sync since)
--   'complete'   -- passed the gate, embedded into Chroma
--   'incomplete' -- failed the gate (even after best-effort LLM
--                   normalization); ingestion_missing_fields names why
--
-- Safe to run more than once -- every step checks whether it already ran.
--
--   mysql -u <username> -p retail_shop < add_ingestion_status.sql
--
-- After it lands, restart the backend once (or delete
-- WORKFLOW/chroma_db/) so DB_CONNECTOR's next sync populates it.
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
