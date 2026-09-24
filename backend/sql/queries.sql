-- =====================================================================
-- Sample Database Queries for Agentic SalesMan
-- =====================================================================
-- Useful queries for exploring, debugging, and managing the product
-- catalog in the `retail_shop` database.
--
-- Prerequisite: run sql/seed/01_products.sql first.
-- =====================================================================


-- ─── Overview ──────────────────────────────────────────────────────────

-- Total product count
SELECT COUNT(*) AS total_products FROM products;

-- Products per category
SELECT category, COUNT(*) AS count
FROM products
GROUP BY category
ORDER BY count DESC;

-- All distinct categories
SELECT DISTINCT category FROM products ORDER BY category;

-- All distinct brands
SELECT DISTINCT brand FROM products ORDER BY brand;


-- ─── Browsing Products ─────────────────────────────────────────────────

-- List all products (name, brand, price, category)
SELECT id, category, name, brand, price
FROM products
ORDER BY category, price;

-- Products in a specific category
SELECT id, name, brand, price, rating
FROM products
WHERE category = 'Mobile'
ORDER BY price;

-- Search products by name (fuzzy)
SELECT id, category, name, brand, price
FROM products
WHERE name LIKE '%Samsung%'
ORDER BY price;

-- Products by brand
SELECT id, category, name, price, rating
FROM products
WHERE brand = 'Apple'
ORDER BY category, price;


-- ─── Price Analysis ────────────────────────────────────────────────────

-- Price range per category
SELECT
    category,
    MIN(price) AS min_price,
    MAX(price) AS max_price,
    ROUND(AVG(price), 2) AS avg_price,
    COUNT(*) AS count
FROM products
GROUP BY category
ORDER BY avg_price DESC;

-- Products under a budget
SELECT id, category, name, brand, price
FROM products
WHERE price <= 50000
ORDER BY price DESC;

-- Top 10 most expensive products
SELECT id, category, name, brand, price
FROM products
ORDER BY price DESC
LIMIT 10;

-- Top 10 cheapest products
SELECT id, category, name, brand, price
FROM products
ORDER BY price ASC
LIMIT 10;

-- Products with highest discount (MRP vs price)
SELECT
    id, category, name, brand, price, mrp,
    ROUND((mrp - price) / mrp * 100, 1) AS discount_pct
FROM products
WHERE mrp IS NOT NULL AND mrp > price
ORDER BY discount_pct DESC
LIMIT 10;


-- ─── Ratings & Stock ──────────────────────────────────────────────────

-- Top-rated products per category
SELECT category, name, brand, price, rating
FROM products
WHERE rating IS NOT NULL
ORDER BY rating DESC, price ASC
LIMIT 15;

-- Low-stock products (fewer than 5 units)
SELECT id, category, name, brand, units_available
FROM products
WHERE units_available IS NOT NULL AND units_available < 5
ORDER BY units_available;

-- Out-of-stock products
SELECT id, category, name, brand
FROM products
WHERE units_available IS NOT NULL AND units_available = 0;

-- Average rating per category
SELECT
    category,
    ROUND(AVG(rating), 2) AS avg_rating,
    COUNT(rating) AS rated_count
FROM products
WHERE rating IS NOT NULL
GROUP BY category
ORDER BY avg_rating DESC;


-- ─── JSON Attributes (category-specific specs) ────────────────────────

-- Mobile phones with their specs
SELECT
    name, brand, price,
    JSON_UNQUOTE(JSON_EXTRACT(attributes, '$.ram')) AS ram,
    JSON_UNQUOTE(JSON_EXTRACT(attributes, '$.storage')) AS storage,
    JSON_UNQUOTE(JSON_EXTRACT(attributes, '$.processor')) AS processor
FROM products
WHERE category = 'Mobile'
ORDER BY price;

-- Laptops by RAM size
SELECT
    name, brand, price,
    JSON_UNQUOTE(JSON_EXTRACT(attributes, '$.ram')) AS ram,
    JSON_UNQUOTE(JSON_EXTRACT(attributes, '$.processor')) AS processor
FROM products
WHERE category = 'Laptop'
ORDER BY price;

-- Headphones by type
SELECT
    name, brand, price,
    JSON_UNQUOTE(JSON_EXTRACT(attributes, '$.type')) AS type,
    JSON_UNQUOTE(JSON_EXTRACT(attributes, '$.noise_cancellation')) AS noise_cancellation
FROM products
WHERE category = 'Headphone'
ORDER BY price;

-- Search by a specific attribute value
SELECT name, brand, price, category
FROM products
WHERE JSON_UNQUOTE(JSON_EXTRACT(attributes, '$.color')) = 'Black'
ORDER BY category, price;

-- Products with a specific processor
SELECT name, brand, price, category
FROM products
WHERE JSON_SEARCH(attributes, 'one', '%Snapdragon%') IS NOT NULL
ORDER BY price;


-- ─── Inventory & Availability ──────────────────────────────────────────

-- Total inventory value per category
SELECT
    category,
    SUM(price * COALESCE(units_available, 0)) AS inventory_value,
    SUM(COALESCE(units_available, 0)) AS total_units
FROM products
GROUP BY category
ORDER BY inventory_value DESC;

-- Products available online (have a link)
SELECT id, category, name, brand, price, online_link
FROM products
WHERE online_link IS NOT NULL AND online_link != ''
ORDER BY category, price;

-- Products available in offline stores
SELECT id, category, name, brand, offline_availability
FROM products
WHERE offline_availability IS NOT NULL AND offline_availability != ''
ORDER BY category;


-- ─── Maintenance & Debugging ──────────────────────────────────────────

-- Check for products with missing critical fields
SELECT id, category, name, brand, price
FROM products
WHERE name IS NULL OR brand IS NULL OR price IS NULL;

-- Check for duplicate product names within a category
SELECT category, name, COUNT(*) AS duplicates
FROM products
GROUP BY category, name
HAVING COUNT(*) > 1;

-- Full product detail (all columns + parsed attributes)
SELECT
    p.*,
    JSON_KEYS(attributes) AS attribute_keys
FROM products p
WHERE id = 1;

-- Table structure reference
DESCRIBE products;
