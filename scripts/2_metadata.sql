-- Create metadata table

DROP TABLE IF EXISTS metadata;

CREATE TABLE metadata (
    data_ver TEXT,
    authors_api BIGINT,
    works_api BIGINT,
    authors_powerbi BIGINT
);

INSERT INTO metadata (
    data_ver,
    authors_api,
    works_api,
    authors_powerbi
)

SELECT
    (SELECT data_ver FROM authors LIMIT 1),
    (SELECT COUNT(*) FROM authors),
    (SELECT COUNT(*) FROM works),
    (SELECT COUNT(*) FROM authors_powerbi);

-- Review data structure

SELECT * FROM metadata;