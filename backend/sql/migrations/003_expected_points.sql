-- Store calculated expected scoring next to official source points.
-- The loader populates these columns from rank_position; it does not overwrite source points.

SET search_path TO core, public;

ALTER TABLE result
    ADD COLUMN IF NOT EXISTS expected_points NUMERIC(10,2);

ALTER TABLE relay_result
    ADD COLUMN IF NOT EXISTS expected_points NUMERIC(10,2);

UPDATE result
SET expected_points = CASE rank_position
    WHEN 1 THEN 9.00
    WHEN 2 THEN 7.00
    WHEN 3 THEN 6.00
    WHEN 4 THEN 5.00
    WHEN 5 THEN 4.00
    WHEN 6 THEN 3.00
    WHEN 7 THEN 2.00
    WHEN 8 THEN 1.00
    ELSE NULL
END::NUMERIC(10,2);

UPDATE relay_result
SET expected_points = CASE rank_position
    WHEN 1 THEN 18.00
    WHEN 2 THEN 14.00
    WHEN 3 THEN 12.00
    WHEN 4 THEN 10.00
    WHEN 5 THEN 8.00
    WHEN 6 THEN 6.00
    WHEN 7 THEN 4.00
    WHEN 8 THEN 2.00
    ELSE NULL
END::NUMERIC(10,2);
