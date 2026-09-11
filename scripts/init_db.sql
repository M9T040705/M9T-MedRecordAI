-- MySQL 建表脚本（项目二）
-- 用法：mysql -u root -p < scripts/init_db.sql
CREATE DATABASE IF NOT EXISTS medical_platform DEFAULT CHARSET utf8mb4;
USE medical_platform;

CREATE TABLE IF NOT EXISTS extraction_records (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    doc_name    VARCHAR(255) NOT NULL,
    department  VARCHAR(64)  NOT NULL,
    fields_json JSON,
    icd_json    JSON,
    mode        VARCHAR(32) DEFAULT 'rule',
    confidence  FLOAT DEFAULT 0,
    status      VARCHAR(16) DEFAULT 'done',
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    KEY idx_department (department),
    KEY idx_created (created_at)
) DEFAULT CHARSET = utf8mb4;
