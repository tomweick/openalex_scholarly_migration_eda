---------------------------------------------------
-- Authors table
---------------------------------------------------

-- Add column has_status

ALTER TABLE authors
ADD COLUMN has_status BOOLEAN;

UPDATE authors
SET has_status =
    CASE
        WHEN mobility_status = 'unknown' THEN FALSE
        ELSE TRUE
    END;

-- Create Power BI analysis table

DROP TABLE IF EXISTS authors_powerbi;

CREATE TABLE authors_powerbi AS
SELECT *
FROM authors
WHERE has_status = TRUE;

ALTER TABLE authors_powerbi
DROP COLUMN has_status;

-- Select 20 authors for review

SELECT *
FROM authors_powerbi
LIMIT 20;