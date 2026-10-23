USE autoparts;

INSERT INTO Store VALUES
(1,'Main Street Store','100 Main St','555-0101'),
(2,'Northside Store','250 North Ave','555-0102');

INSERT INTO Customer VALUES
(1,'Lex Luthor','555-1001','lex@example.com','lluthor','demo_hash_1',1,'Credit Card'),
(2,'Clark Kent','555-1002','clark@example.com','ckent','demo_hash_2',2,'Credit Card');

INSERT INTO Employee VALUES
(1,1,'Bruce Wayne','Sales','Clerk','bwayne','demo_hash_3'),
(2,1,'Tim Drake','Management','Manager','tdrake','demo_hash_4'),
(3,2,'Barry Allen','Sales','Clerk','ballen','demo_hash_5');

INSERT INTO Part VALUES
(1,'Brake Pad Set','Front ceramic brake pads','Brakes','AcmeBrake','New',49.99),
(2,'Alternator','12V 120A alternator','Electrical','VoltPro','Rebuilt',129.50),
(3,'Oil Filter','Spin-on oil filter','Filters','FilterCo','New',8.99),
(4,'Spark Plug','Iridium spark plug','Ignition','SparkTech','New',12.49),
(5,'Air Filter','Engine air filter','Filters','FilterCo','New',15.75);

INSERT INTO Inventory VALUES
(1,1,20,5),(1,2,3,5),(1,3,50,10),
(2,1,8,5),(2,4,4,10),(2,5,25,5);

INSERT INTO Customer_Orders VALUES
(1,1,1,'2026-10-10','2026-10-14','Delivered','Credit Card'),
(2,2,2,'2026-10-18',NULL,'Pending','Credit Card');

INSERT INTO Customer_Order_Item VALUES
(1,1,49.99,1),(1,3,8.99,2),
(2,4,12.49,4);

INSERT INTO Store_Orders VALUES
(1,1,'2026-10-05','2026-10-09','Delivered',900.00);

INSERT INTO Store_Orders_Item VALUES
(1,1,30.00,20),(1,3,6.00,50);