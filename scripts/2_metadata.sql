-- Create metadata table

DROP TABLE IF EXISTS metadata;

CREATE TABLE metadata (
    data_ver TEXT,
    authors_api BIGINT,
    works_api BIGINT,
    authors_powerbi BIGINT,
    works_powerbi BIGINT
);

INSERT INTO metadata (
    data_ver,
    authors_api,S
    works_api,
    authors_powerbi,
    works_powerbi
)

SELECT
    (SELECT data_ver FROM authors LIMIT 1),
    (SELECT COUNT(*) FROM authors),
    (SELECT COUNT(*) FROM works),
    (SELECT COUNT(*) FROM authors_powerbi),
    (SELECT COUNT(*) FROM works_powerbi);

-- Review data structure

SELECT * FROM works_powerbi;