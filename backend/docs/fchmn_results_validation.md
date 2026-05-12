# Runbook: Validación automatizada de resultados FCHMN

Este runbook documenta la cadena operativa controlada para resultados FCHMN. Mantiene
separadas las responsabilidades: descubrir URLs, descargar PDFs, parsear,
validar y cargar a core solo cuando se pida explícitamente.

## Principios

- No ejecutar carga a core en pruebas de discovery o descarga.
- No usar `--load` salvo pedido explícito.
- No crear tablas nuevas ni migraciones para esta operación.
- No versionar PDFs, CSVs completos, Excels ni summaries generados.
- Guardar evidencia auditable en `backend/data/raw/batch_summaries/`.
- Si un documento queda `failed` o `requires_review`, no cargarlo a core.

---

## Estado post-load vigente: 2026-05-12

Auditoría realizada sobre la carga core generada desde el manifest curado
`backend/data/raw/manifests/fchmn_historical_2022_2026_frozen_local_parser020_tracefixed_curated_20260512_identity_fix.jsonl`.
El parser vigente de esa materialización es `0.1.20`.

Evidencia local no versionada:

- `backend/data/raw/batch_summaries/fchmn_core_postload_tracefixed_curated_20260512_identity_fix_audit_20260512_summary.json`
- `backend/data/raw/batch_summaries/fchmn_core_postload_tracefixed_curated_20260512_identity_fix_audit_20260512_*.csv`

Resultado operativo:

- 62 documentos esperados y 62 `load_run` completados.
- 0 documentos faltantes en core.
- 0 diferencias de checksum.
- 0 `validation_issue`.
- 0 atletas huérfanos.
- 0 inconsistencias de evento contra género/edad.
- 0 tiempos individuales sospechosos.
- 0 tiempos de relevo sospechosos.

Excepciones conocidas:

- El único duplicado exacto detectado en `core.athlete` es `Torres, Sergio`
  (`male`, `birth_year=1994`). Es un homónimo confirmado y debe mantenerse
  separado. La decisión queda versionada en
  `backend/data/reference/athlete_accepted_homonyms.csv`.
- Persisten relevos con 0, 2 o 3 integrantes cuando la fuente oficial no trae
  la nómina completa o el formato no permite reconstruirla con seguridad.
  Estos casos se auditan, pero no bloquean la carga si el resultado del relevo
  es oficial.
- Persisten diferencias entre puntos de fuente y puntos calculados por regla
  esperada. La política vigente es conservar los puntos publicados por la
  fuente y exponer la diferencia como auditoría, no sobrescribirla.

---

## 1. Discovery desde página de resultados FCHMN

Este comando descubre PDFs de resultados desde la página real de resultados y
emite un manifest JSONL local. **No descarga, no parsea y no carga.**
Por defecto no filtra por keyword: FCHMN puede publicar resultados con typos en
la URL (ej. `resutados`). La separacion entre resultados y convocatorias debe
resolverse en el manifest curado, no como compuerta final del scraper.

```powershell
backend\.venv\Scripts\python.exe backend\scripts\scrape_fchmn.py `
  --url https://fchmn.cl/resultados/ `
  --url https://fchmn.cl/sudamericanos-master/ `
  --manifest backend\data\raw\manifests\fchmn_resultados_e2e_YYYYMMDD.jsonl `
  --pdf-dir backend\data\raw\results_pdf\fchmn_resultados_e2e `
  --out-dir-root backend\data\raw\results_csv\fchmn_resultados_e2e `
  --limit 5 `
  --json
```

**Salida esperada:**
- `state`: `discovered`
- `documents`: cantidad de PDFs incluidos en el manifest
- manifest JSONL generado.

---

## 2. Download separado

Este comando lee el manifest y descarga los PDFs declarados. **No parsea, no valida y no carga.**

```powershell
backend\.venv\Scripts\python.exe backend\scripts\download_manifest_pdfs.py `
  --manifest backend\data\raw\manifests\fchmn_resultados_e2e_YYYYMMDD.jsonl `
  --summary-json backend\data\raw\batch_summaries\fchmn_resultados_e2e_YYYYMMDD_download.json `
  --json
```

**Salida esperada:**
- `state`: `downloaded` (si hay descargas nuevas), `skipped` (si ya existían y no hay `--overwrite`), o `failed`.
- Por documento: bytes descargados y `pdf_sha256`.

---

## 3. Batch validation sin carga

Este comando parsea cada PDF del manifest, evalúa compuertas y escribe un
resumen auditable. **No carga a core porque no usa `--load`.**

```powershell
backend\.venv\Scripts\python.exe backend\scripts\run_results_batch.py `
  --manifest backend\data\raw\manifests\fchmn_resultados_e2e_YYYYMMDD.jsonl `
  --summary-json backend\data\raw\batch_summaries\fchmn_resultados_e2e_YYYYMMDD_batch.json `
  --json
```

**Salida esperada para un batch sano:**
- manifest `state`: `validated`
- cada documento `state`: `validated`
- `issues`: vacío
- `commands.load`: `null`

---

## 4. Automatización segura sin carga

Este comando encadena discovery, download y batch validation. **No carga a core** y
falla si el resultado final no queda `validated`. Es ideal para smoke tests.

```powershell
backend\.venv\Scripts\python.exe backend\scripts\run_fchmn_results_validation.py `
  --url https://fchmn.cl/resultados/ `
  --url https://fchmn.cl/sudamericanos-master/ `
  --run-id fchmn_resultados_YYYYMMDD `
  --limit 5 `
  --json
```

---

## 5. Manifest congelado para carga

Después de revisar un summary de batch, generar un archivo de URLs curadas con
una `source_url` local por línea. Luego crear el manifest congelado:

```powershell
backend\.venv\Scripts\python.exe backend\scripts\freeze_validated_manifest.py `
  --batch-summary backend\data\raw\batch_summaries\fchmn_resultados_e2e_YYYYMMDD_batch.json `
  --manifest backend\data\raw\manifests\fchmn_resultados_e2e_YYYYMMDD_frozen_local.jsonl `
  --competition-scope fchmn_local `
  --allow-source-url-file backend\data\raw\manifests\fchmn_resultados_e2e_YYYYMMDD_allowed_urls.txt `
  --json
```

El freezer no descarga, no parsea, no valida y no carga. Solo copia documentos
`validated`, excluye `requires_review`/`failed` y agrega `competition_scope`.

---

## 6. Curaduría de nombres de atletas (Pre-load)

Cuando el parser ya no reduce más ruido sin meter heurísticas frágiles,
consolidar variantes OCR en una etapa separada y auditable, antes del load:

```powershell
backend\.venv\Scripts\python.exe backend\scripts\curate_athlete_names.py `
  --manifest backend\data\raw\manifests\fchmn_historical_frozen_local_preview.jsonl `
  --summary-json backend\data\raw\batch_summaries\fchmn_historical_athlete_name_curation.json `
  --review-csv backend\data\raw\batch_summaries\fchmn_historical_athlete_name_curation.csv `
  --json
```

Esta etapa no modifica el parser ni carga a core. Sirve para consolidar
variantes tipo `Goámez/Goémez -> Gomez` antes de una recarga. La semejanza nominal no se
usa sola: requiere mismo `birth_year`, mismo `club_key` y mismo género.

La materialización vigente 20260512 agrega decisiones manuales de identidad
fuzzy revisadas, exclusiones de resultados revisadas y homónimos aceptados
versionados. Solo se aplican filas con `decision=merge`; las filas en blanco o
marcadas como mantener separadas no se fusionan. El manifest resultante es
`backend/data/raw/manifests/fchmn_historical_2022_2026_frozen_local_parser020_tracefixed_curated_20260512_identity_fix.jsonl`
y valida 62/62 sin `--load`.

Decisiones de referencia versionadas:

- `backend/data/reference/athlete_accepted_homonyms.csv`: homónimos confirmados
  que no deben reabrirse como duplicados pendientes.

Si una nueva carga muestra candidatos de identidad, la siguiente iteración debe
incluir una bandeja ampliada:

```powershell
backend\.venv\Scripts\python.exe backend\scripts\audit_expected_athlete_identity.py `
  --input-csv backend\data\raw\batch_summaries\fchmn_historical_2022_2026_expected_core_athlete_after_partial_decisions_iter2_20260424.csv `
  --review-csv backend\data\raw\batch_summaries\fchmn_historical_2022_2026_expected_core_same_name_review_expanded.csv `
  --summary-json backend\data\raw\batch_summaries\fchmn_historical_2022_2026_expected_core_expanded_identity.json `
  --expanded-identity-candidates-csv backend\data\raw\batch_summaries\fchmn_historical_2022_2026_expanded_identity_candidates.csv `
  --json
```

Esa salida es solo diagnóstico/revisión: captura variantes como segundo
apellido omitido, segundo nombre omitido, inicial final y candidatos con
`birth_year` +/-1. No debe cargarse ni aplicarse sin revisión manual.

---

## 7. Carga a BD (Load Explicito)

Una vez que el manifest curado está validado, se ejecuta la carga usando la flag `--load`.
**Importante:** Asegúrate de seguir `backend/docs/pre_load_checklist.md` antes de este paso.

```powershell
backend\.venv\Scripts\python.exe backend\scripts\run_results_batch.py `
  --manifest backend\data\raw\manifests\fchmn_historical_frozen_local_curated.jsonl `
  --load `
  --user postgres `
  --password ******* `
  --summary-json backend\data\raw\batch_summaries\fchmn_historical_load_summary.json `
  --json
```
