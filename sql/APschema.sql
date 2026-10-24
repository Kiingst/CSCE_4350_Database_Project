DROP DATABASE IF EXISTS autoparts;
CREATE DATABASE IF NOT EXISTS autoparts;
USE autoparts;

CREATE TABLE Store (
  store_id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  address VARCHAR(200) NOT NULL,
  phone VARCHAR(20)
);

CREATE TABLE Customer (
  customer_id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  phone VARCHAR(20),
  address VARCHAR(200) NOT NULL,
  email VARCHAR(100) UNIQUE,
  username VARCHAR(50) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  pref_store_id INT NULL,
  pref_payment_method VARCHAR(30),
  FOREIGN KEY (pref_store_id) REFERENCES Store(store_id) ON DELETE SET NULL
);

CREATE TABLE Employee (
  employee_id INT AUTO_INCREMENT PRIMARY KEY,
  store_id INT NOT NULL,
  name VARCHAR(100) NOT NULL,
  department VARCHAR(50),
  role VARCHAR(30) NOT NULL,
  username VARCHAR(50) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  FOREIGN KEY (store_id) REFERENCES Store(store_id)
);

CREATE TABLE Part (
  part_id INT AUTO_INCREMENT PRIMARY KEY,
  part_name VARCHAR(100) NOT NULL,
  description TEXT,
  category VARCHAR(50),
  brand VARCHAR(50),
  part_condition ENUM('New','Rebuilt') NOT NULL DEFAULT 'New',
  price DECIMAL(10,2) NOT NULL CHECK (price >= 0)
);

CREATE TABLE Inventory (
  store_id INT NOT NULL,
  part_id INT NOT NULL,
  amount_stocked INT NOT NULL DEFAULT 0 CHECK (amount_stocked >= 0),
  reorder_level INT NOT NULL DEFAULT 5 CHECK (reorder_level >= 0),
  PRIMARY KEY (store_id, part_id),
  FOREIGN KEY (store_id) REFERENCES Store(store_id),
  FOREIGN KEY (part_id) REFERENCES Part(part_id)
);

CREATE TABLE Customer_Orders (
  customer_order_id INT AUTO_INCREMENT PRIMARY KEY,
  store_id INT NOT NULL,
  customer_id INT NOT NULL,
  placement_date DATE NOT NULL,
  delivery_date DATE NULL,
  delivery_status ENUM('Pending','Shipped','Delivered','Cancelled') NOT NULL DEFAULT 'Pending',
  payment VARCHAR(30) NOT NULL,
  FOREIGN KEY (store_id) REFERENCES Store(store_id),
  FOREIGN KEY (customer_id) REFERENCES Customer(customer_id),
  CHECK (delivery_date IS NULL OR delivery_date >= placement_date)
);

CREATE TABLE Customer_Order_Item (
  customer_order_id INT NOT NULL,
  part_id INT NOT NULL,
  price DECIMAL(10,2) NOT NULL CHECK (price >= 0),
  quantity INT NOT NULL CHECK (quantity > 0),
  PRIMARY KEY (customer_order_id, part_id),
  FOREIGN KEY (customer_order_id) REFERENCES Customer_Orders(customer_order_id) ON DELETE CASCADE,
  FOREIGN KEY (part_id) REFERENCES Part(part_id)
);

CREATE TABLE Store_Orders (
  store_order_id INT AUTO_INCREMENT PRIMARY KEY,
  store_id INT NOT NULL,
  placement_date DATE NOT NULL,
  delivery_date DATE NULL,
  delivery_status ENUM('Pending','Shipped','Delivered','Cancelled') NOT NULL DEFAULT 'Pending',
  cost DECIMAL(10,2) NOT NULL CHECK (cost >= 0),
  FOREIGN KEY (store_id) REFERENCES Store(store_id),
  CHECK (delivery_date IS NULL OR delivery_date >= placement_date)
);

CREATE TABLE Store_Orders_Item (
  store_order_id INT NOT NULL,
  part_id INT NOT NULL,
  cost DECIMAL(10,2) NOT NULL CHECK (cost >= 0),
  quantity INT NOT NULL CHECK (quantity > 0),
  PRIMARY KEY (store_order_id, part_id),
  FOREIGN KEY (store_order_id) REFERENCES Store_Orders(store_order_id) ON DELETE CASCADE,
  FOREIGN KEY (part_id) REFERENCES Part(part_id)
);