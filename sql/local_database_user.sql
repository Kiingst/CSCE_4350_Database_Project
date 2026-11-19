CREATE USER IF NOT EXISTS 'autoparts'@'localhost' IDENTIFIED BY 'local-demo-only';
GRANT ALL ON autoparts.* TO 'autoparts'@'localhost';
GRANT ALL ON `autoparts_test_%`.* TO 'autoparts'@'localhost';
