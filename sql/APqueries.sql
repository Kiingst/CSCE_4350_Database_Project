SHOW TABLES;
DESCRIBE Inventory;
DESCRIBE Customer_Orders;
SELECT * FROM Part;
SELECT * FROM Inventory;

-- low stock
SELECT s.name AS store, p.part_name, i.amount_stocked, i.reorder_level
FROM Inventory i
JOIN Store s ON s.store_id = i.store_id
JOIN Part p ON p.part_id = i.part_id
WHERE i.amount_stocked <= i.reorder_level;

--  a customers order history
SELECT o.customer_order_id,
       DATE_FORMAT(o.placement_date, '%Y-%m-%d') AS placement_date,
       o.delivery_status, p.part_name, oi.quantity, oi.price
FROM Customer_Orders o
JOIN Customer_Order_Item oi ON oi.customer_order_id = o.customer_order_id
JOIN Part p ON p.part_id = oi.part_id
WHERE o.customer_id = 1;

-- Checking constraints, expected to fail
-- INSERT INTO Part (part_name, price) VALUES ('Bad Part', -5);