---------------------------------------------------
-- Aggregate academic origin
---------------------------------------------------

-- Add aggregated country column

ALTER TABLE authors_powerbi
ADD COLUMN academic_origin_agg VARCHAR(255);

-- Count authors by academic origin

WITH country_counts AS (
    SELECT
        academic_origin,
        COUNT(*) AS n_authors
    FROM authors_powerbi
    GROUP BY academic_origin
),

-- Calculate the share of authors for each country

country_shares AS (
    SELECT
        academic_origin,
        n_authors,
        n_authors::FLOAT / SUM(n_authors) OVER () AS share
    FROM country_counts
)

-- Recode countries with less than 5% of authors as "other"

UPDATE authors_powerbi
SET academic_origin_agg =
    CASE
        WHEN country_shares.share < 0.05 THEN 'other'
        ELSE authors_powerbi.academic_origin
    END
FROM country_shares
WHERE authors_powerbi.academic_origin = country_shares.academic_origin;