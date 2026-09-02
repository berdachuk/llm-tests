-- 1. The table has quantity_in_stock, not qty.
SELECT
    'column_renamed' AS check_name,
    (EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'products' AND column_name = 'quantity_in_stock'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'products' AND column_name = 'qty'
    )) AS check_result;

-- 2. The view still exists.
SELECT
    'view_still_exists' AS check_name,
    (EXISTS (
        SELECT 1 FROM information_schema.views WHERE table_name = 'low_stock_products'
    )) AS check_result;

-- 3. The view still correctly reports low-stock products by their
-- original data (Widget: 3, Gizmo: 0 are < 10; Gadget: 25 is not).
SELECT
    'view_reports_correct_rows' AS check_name,
    (
        (SELECT COUNT(*) FROM low_stock_products) = 2
        AND EXISTS (SELECT 1 FROM low_stock_products WHERE name = 'Widget')
        AND EXISTS (SELECT 1 FROM low_stock_products WHERE name = 'Gizmo')
        AND NOT EXISTS (SELECT 1 FROM low_stock_products WHERE name = 'Gadget')
    ) AS check_result;
