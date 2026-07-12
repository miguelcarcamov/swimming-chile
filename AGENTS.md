# Proyecto: SwimStats Chile

## Rol de este archivo
`AGENTS.md` contiene **reglas operativas estáticas y directivas** para agentes de IA que trabajan en este repositorio. Debe ser corto, imperativo y orientado a ejecución.

Para metodología de trabajo, estado actual a alto nivel y prompt sugerido, lee `backend/docs/ai_workflow.md`.
Para reglas en inglés (Cursor / agentes internacionales), lee `conventions/AGENTS.en.md` y `conventions/ai_workflow.en.md`.
Reglas y skills de Cursor en el repo: `.cursor/README.md`.
Para decisiones históricas y versiones previas, lee `backend/docs/CHANGELOG.md`.

## Objetivo Principal
Construir SwimStats Chile como plataforma de datos: extraer resultados de competencias master desde PDFs públicos, normalizarlos, curar su calidad (identidades) y cargarlos a PostgreSQL.

## Flujo Operativo (Separación de Responsabilidades)

El proceso está estrictamente desacoplado para asegurar calidad e idempotencia:

1. **Scraping** (`scrape_fchmn.py`): Descubre URLs y genera un JSONL. No descarga, no parsea, no carga.
2. **Download** (`download_manifest_pdfs.py`): Descarga PDFs y genera hashes. No parsea, no carga.
3. **Parseo** (`parse_results_pdf.py`): Convierte PDFs (HY-TEK / Swim It Up) a CSVs Raw (`club.csv`, `athlete.csv`, `result.csv`, etc.). No decide qué cargar.
4. **Curaduría local/OCR** (`curate_athlete_names.py`): Resuelve variantes OCR y consolida alias de atletas pre-load sobre los CSVs, incluyendo decisiones manuales de identidad fuzzy revisadas con `decision=merge`.
5. **Auditoría DB-aware de identidad** (`audit_expected_athlete_identity.py --core-aware-manifest`): Antes de validar/cargar, compara el manifest curado contra `core.athlete`, `core.athlete_current_club` y clubes históricos. Propone completitud de nombres cross-club solo cuando género/año coinciden y el club fuente coincide con club actual o histórico; si no hay evidencia contextual de club, deja el caso en revisión.
6. **Materialización de decisiones** (`curate_athlete_names.py`): Solo aplica decisiones humanas `decision=merge` desde las bandejas revisadas. No auto-mergea candidatos DB-aware sin revisión.
7. **Validación** (`run_results_batch.py` sin `--load`): Revisa CSVs y aplica compuertas de calidad. Genera un Summary.
8. **Carga a Core** (`run_results_batch.py --load`): Solo inserta a la BD PostgreSQL si el lote de validación (`manifest.jsonl`) está congelado y `validated`, y el `competition_scope` coincide.

## Canon de datos
### event.gender
- `women`
- `men`
- `mixed`

### athlete.gender
- `female`
- `male`

### event.stroke
- `freestyle`
- `backstroke`
- `breaststroke`
- `butterfly`
- `individual_medley`
- `medley_relay`
- `freestyle_relay`

## Reglas Críticas para la IA

- **Identidad de Atletas**: No uses el club como identidad rígida del atleta a largo plazo. Un atleta puede cambiar de club.
- **Curaduría contra Core**: Para nombres parciales vs completos, no bloquees por `core.athlete.club_id`; usa `core.athlete_current_club` y clubes históricos como evidencia contextual. Si el club fuente no aparece como actual/histórico, manda a revisión.
- **Edad Contextual**: `age_at_event` es contextual al evento. `birth_year_estimated = competition_year - age_at_event`.
- **Limpieza Genérica**: El pipeline (`run_pipeline_results.py`) debe hacer solo limpieza genérica y cruce de datos. Las heurísticas frágiles (OCR quirks) deben manejarse en el Parser o en el script de Curaduría de nombres.
- **Tolerancia a Errores**: Si `run_results_batch.py` devuelve `requires_review` para un documento, ese documento no se debe cargar a core. Un error en un documento no contamina los demás del manifest.
- **Compuerta de Carga**: `--load` exige que el lote tenga un `competition_scope` explícito (ej. `fchmn_local`). Eventos internacionales (ej. Sudamericanos) son un flujo separado.
- **Passwords**: Nunca guardes passwords en resúmenes auditables, logs ni código.
- **Frontend**: `frontend/` existe como área planificada. Actualmente, el trabajo se concentra en el pipeline de datos (Backend).

## Forma de trabajar

1. **No renombres archivos innecesariamente.**
2. **Haz cambios mínimos y localizados.**
3. **Explica siempre tu diagnóstico** y tu *patch* antes de editar el código.
4. **Si cambias una regex o lógica de parseo**, agrega un comentario breve en el código explicando por qué.
5. **Mantén compatibilidad** con PDFs que ya pasan las pruebas (ejecuta siempre `pytest` o re-valida localmente).
6. Después de ejecutar cambios, revisa `git status` y propón el mensaje de commit.
