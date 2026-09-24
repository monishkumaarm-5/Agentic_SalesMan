-- =====================================================================
-- Run this FIRST, then re-run the INSERT statements that failed
-- (sample_data_300.sql / sample_data_300_batch2.sql).
--
-- Cause: your `type` column (and possibly others) was created narrower
-- than the sample data's longest values -- e.g. "Active Noise
-- Cancelling Over-Ear Wireless" is 42 characters, which overflows a
-- VARCHAR(20)/VARCHAR(30) column and MySQL's strict mode turns that
-- into error 1406 instead of silently truncating it.
--
-- This widens every free-text column on all three tables to a size
-- that comfortably fits the sample data (and any real catalog data
-- later). MODIFY COLUMN keeps existing data and constraints (NOT NULL
-- etc.) -- it only changes the max length, so it's safe to run even if
-- a table already has rows in it.
--
-- If a column below doesn't exist yet on your table, comment out that
-- one line (MySQL will error "Unknown column" for it) and re-run the
-- rest.
-- =====================================================================

ALTER TABLE phone
    MODIFY COLUMN name      VARCHAR(255) NOT NULL,
    MODIFY COLUMN brand     VARCHAR(100) NOT NULL,
    MODIFY COLUMN processor VARCHAR(150) NULL,
    MODIFY COLUMN ram       VARCHAR(30)  NULL,
    MODIFY COLUMN storage   VARCHAR(30)  NULL,
    MODIFY COLUMN color     VARCHAR(100) NULL;

ALTER TABLE laptop
    MODIFY COLUMN name      VARCHAR(255) NOT NULL,
    MODIFY COLUMN brand     VARCHAR(100) NOT NULL,
    MODIFY COLUMN processor VARCHAR(150) NULL,
    MODIFY COLUMN ram       VARCHAR(30)  NULL,
    MODIFY COLUMN storage   VARCHAR(30)  NULL,
    MODIFY COLUMN color     VARCHAR(100) NULL;

ALTER TABLE headphone
    MODIFY COLUMN name      VARCHAR(255) NOT NULL,
    MODIFY COLUMN brand     VARCHAR(100) NOT NULL,
    MODIFY COLUMN type      VARCHAR(150) NULL,
    MODIFY COLUMN quality   VARCHAR(150) NULL,
    MODIFY COLUMN color     VARCHAR(100) NULL;

-- The enrichment columns (if you already added them from sample_data_300.sql)
-- widened too, just in case:
ALTER TABLE phone     MODIFY COLUMN online_link VARCHAR(500) NULL, MODIFY COLUMN offline_availability VARCHAR(255) NULL;
ALTER TABLE laptop    MODIFY COLUMN online_link VARCHAR(500) NULL, MODIFY COLUMN offline_availability VARCHAR(255) NULL;
ALTER TABLE headphone MODIFY COLUMN online_link VARCHAR(500) NULL, MODIFY COLUMN offline_availability VARCHAR(255) NULL;
