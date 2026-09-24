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
-- Safe to run more than once -- IF NOT EXISTS guards both columns.
--
--   mysql -u <username> -p retail_shop < add_ingestion_status.sql
--
-- After it lands, restart the backend once (or delete
-- WORKFLOW/chroma_db/) so DB_CONNECTOR's next sync populates it.
-- =====================================================================

ALTER TABLE products
    ADD COLUMN IF NOT EXISTS ingestion_status VARCHAR(20) NULL,
    ADD COLUMN IF NOT EXISTS ingestion_missing_fields JSON NULL;

CREATE INDEX IF NOT EXISTS idx_products_ingestion_status
    ON products (ingestion_status);
