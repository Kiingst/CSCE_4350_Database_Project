USE autoparts;
ALTER TABLE Customer_Orders
  ADD fulfillment_method ENUM('Pickup','Delivery') NOT NULL DEFAULT 'Pickup',
  ADD delivery_address VARCHAR(200),
  ADD submission_token VARCHAR(64),
  ADD UNIQUE KEY customer_submission (customer_id, submission_token);
CREATE TABLE Payment (
  payment_id INT AUTO_INCREMENT PRIMARY KEY,
  customer_order_id INT NOT NULL UNIQUE,
  method VARCHAR(30) NOT NULL,
  amount DECIMAL(10,2) NOT NULL CHECK(amount >= 0),
  billing_address VARCHAR(200) NOT NULL,
  card_type VARCHAR(30), last_four CHAR(4), expiry VARCHAR(7),
  FOREIGN KEY(customer_order_id) REFERENCES Customer_Orders(customer_order_id)
);
CREATE TABLE Supplier (
  supplier_id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL, phone VARCHAR(30), address VARCHAR(200)
);
CREATE TABLE Supplier_Part (
  supplier_id INT NOT NULL, part_id INT NOT NULL,
  unit_cost DECIMAL(10,2) NOT NULL CHECK(unit_cost >= 0),
  PRIMARY KEY(supplier_id,part_id),
  FOREIGN KEY(supplier_id) REFERENCES Supplier(supplier_id),
  FOREIGN KEY(part_id) REFERENCES Part(part_id)
);
ALTER TABLE Store_Orders ADD supplier_id INT,
  ADD FOREIGN KEY(supplier_id) REFERENCES Supplier(supplier_id);
CREATE TABLE Customer_Vehicle (
  vehicle_id INT AUTO_INCREMENT PRIMARY KEY,
  customer_id INT NOT NULL, make VARCHAR(60) NOT NULL,
  model VARCHAR(60) NOT NULL, year INT NOT NULL CHECK(year BETWEEN 1886 AND 2100),
  FOREIGN KEY(customer_id) REFERENCES Customer(customer_id)
);
CREATE TABLE Part_Compatibility (
  part_id INT NOT NULL, make VARCHAR(60) NOT NULL, model VARCHAR(60) NOT NULL,
  year INT NOT NULL CHECK(year BETWEEN 1886 AND 2100),
  PRIMARY KEY(part_id,make,model,year), FOREIGN KEY(part_id) REFERENCES Part(part_id)
);
CREATE TABLE Customer_Return (
  return_id INT AUTO_INCREMENT PRIMARY KEY, customer_order_id INT NOT NULL,
  return_date DATE NOT NULL,
  UNIQUE KEY return_order (return_id,customer_order_id),
  FOREIGN KEY(customer_order_id) REFERENCES Customer_Orders(customer_order_id)
);
CREATE TABLE Return_Item (
  return_id INT NOT NULL, customer_order_id INT NOT NULL, part_id INT NOT NULL,
  quantity INT NOT NULL CHECK(quantity > 0), reason VARCHAR(200) NOT NULL,
  restock BOOLEAN NOT NULL, refund_amount DECIMAL(10,2) NOT NULL CHECK(refund_amount >= 0),
  PRIMARY KEY(return_id,part_id),
  FOREIGN KEY(return_id,customer_order_id) REFERENCES Customer_Return(return_id,customer_order_id),
  FOREIGN KEY(customer_order_id,part_id) REFERENCES Customer_Order_Item(customer_order_id,part_id)
);
UPDATE Inventory SET reorder_level=5;
INSERT INTO Supplier VALUES (1,'Metro Parts Supply','555-2000','50 Supply Road');
INSERT INTO Supplier_Part SELECT 1,part_id,ROUND(price*0.6,2) FROM Part;
UPDATE Store_Orders SET supplier_id=1;
INSERT INTO Customer_Vehicle(customer_id,make,model,year) VALUES(1,'Toyota','Camry',2020);
INSERT INTO Part_Compatibility VALUES(1,'Toyota','Camry',2020),(3,'Toyota','Camry',2020);
INSERT INTO Payment(customer_order_id,method,amount,billing_address,card_type,last_four,expiry)
SELECT o.customer_order_id,o.payment,SUM(i.price*i.quantity),c.address,'Demo','4242','2030-12'
FROM Customer_Orders o JOIN Customer_Order_Item i USING(customer_order_id)
JOIN Customer c USING(customer_id) GROUP BY o.customer_order_id,o.payment,c.address;
