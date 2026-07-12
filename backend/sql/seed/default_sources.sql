-- Reference rows required before pipeline load (default_source_id=1).
SET search_path TO core, public;

INSERT INTO source (id, name, source_type, base_url, notes)
SELECT
    1,
    'FCHMN',
    'results_website',
    'https://fchmn.cl/resultados/',
    'Federación Chilena de Natación Master — public result PDFs'
WHERE NOT EXISTS (SELECT 1 FROM source WHERE id = 1);

SELECT setval(
    pg_get_serial_sequence('source', 'id'),
    (SELECT COALESCE(MAX(id), 1) FROM source),
    true
);
