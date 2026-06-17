# Changelog Histórico (Natación Chile)

Este documento condensa los hitos y auditorías relevantes durante el desarrollo y carga de datos históricos (Fase 4 y Fase 5). La evidencia detallada original fue consolidada para mantener la documentación operativa limpia.

## Abril - Mayo 2026 (Consolidación de Pipeline FCHMN 2022-2026)


### Documentación de producto y naming
- Se adopta **SwimStats Chile** como nombre de producto para la presentación pública del monorepo. FCHMN queda documentado como fuente/dataset cuando corresponda, no como marca principal.
- Se agrega `README.md` raíz como landing técnica del monorepo, con problema, arquitectura end-to-end, estructura, stack, estado actual, roadmap y disclaimer de datos.
- La hoja de ruta versionada se mueve a `docs/plans/implementation_plan.md` para mantener la raíz orientada a producto sin usar `.atl/` como documentación pública.
- `backend/README.md`, `frontend/README.md` y `frontend/docs/api_contracts.md` se alinean para explicar el flujo PostgreSQL/FastAPI/React y el estado transicional de contratos manuales hacia OpenAPI.

### Estado operativo vigente
- Se inicio la etapa **Sudamericanos Master + filtros reales de circuito/organismo**.
  El modelo separa `source` (origen documental), `organizer` (organizador local)
  y `competition.governing_body_code/name` (organismo rector: `fchmn`,
  `consada`, `fechida`). Se agrega migracion
  `backend/sql/migrations/005_competition_governing_body.sql`, el freezer y el
  batch runner propagan `governing_body_*` desde manifests curados, y la API/UI
  dejan de depender de un filtro hardcodeado para competencias.
- El 2026-06-02 se detecto la publicacion de VII Copa Smart Swim Team desde la
  portada FCHMN. Parser `0.1.21` agrega soporte para encabezados HY-TEK de relevo
  con categoria agregada al final (`Freestyle Relay 240 a 279`) y el batch
  bloquea cualquier encabezado de relevo remanente en debug aunque el ratio
  global sea bajo. La validacion aislada sin `--load` extrae 504 resultados
  individuales, 42 relevos y 168 integrantes con 0 lineas no parseadas.
- Parser `0.1.24` consolida el flujo Sudamericanos desde
  `https://fchmn.cl/sudamericanos-master/` para 2022-2026: soporta encabezados
  HY-TEK mixtos `Evento ... Mixed ... SC Metros ... Relay`, normaliza estilos
  `CI ...` como combinado individual, omite lineas auxiliares de splits/records
  y acepta resultados no rankeados con prefijo `--` y nombres HY-TEK marcados
  con `*`. La curaduria pre-load remueve sufijos de club/equipo entre parentesis
  antes de canonizar nombres sin coma y aplica las 11 correcciones manuales
  revisadas del Sudamericano Medellin 2022. El manifest vigente validado sin
  `--load` es
  `backend/data/raw/manifests/suda_src_2022_2026_p024_curated_reviewed_20260612.jsonl`;
  valida 5/5 con `competition_scope=sudamericano_master` y
  `governing_body_code=consada`.
- Parser `0.1.25` corrige extracciones Sudamericanos antes de continuar la
  curaduria pre-load: separa tiempos pegados al nombre de club en filas
  Swim It Up/Recife cuando la columna de resultado viene vacia, y repara
  `(cid:976)` como `f` tambien en nombres de club. El manifest curado
  `backend/data/raw/manifests/suda_src_2022_2026_p025_curated_reviewed_20260614.jsonl`
  valida 5/5 sin `--load`; las bandejas de alias/identidad deben regenerarse
  desde esta materializacion y no desde `p024`.
- Parser `0.1.26` evita que el layout Swim It Up/Recife emita integrantes de
  relevo con `leg_order` mayor a 4, y el batch runner bloquea esos residuos
  antes de llegar a la restriccion de PostgreSQL. La carga Sudamericanos debe
  ejecutarse con `--required-competition-scope sudamericano_master`.
- El loader castea explicitamente a `text` los parametros opcionales de
  metadata de competencia para evitar errores de inferencia de tipo en
  PostgreSQL al actualizar `competition_scope` y `governing_body_*`.
- La compuerta nueva expuso deuda historica en cinco PDFs 2022-2023 que antes
  pasaban por ratio global: SBDO 2023, Santiago Deporte 2023, Delfines 2022,
  LQBLO 2022 y Santiago Master 2022. Se reparsearon con `0.1.21`, recuperando
  sus relevos, y la materializacion curada ampliada valida 63/63 sin `--load`.
- El calendario FCHMN actualizado al 31/mayo/2026 movio VII Copa Smart Swim al
  31/mayo y VI Copa Santiago Deporte al 20/junio. Los resultados oficiales de
  Smart Swim traen eventos `SC Meter`, por lo que el curso real es `scm` aunque
  el calendario lo mantenga como 50m. El loader ahora puede
  reutilizar una competencia planificada vacia de la misma temporada por nombre
  similar aunque fecha o curso hayan cambiado, evitando duplicados.
- La bandeja revisada de identidad de Smart Swim
  `backend/data/raw/batch_summaries/fchmn_vii_copa_smart_swim_20260603_identity_candidates_alias.csv`
  debe aplicarse como `--fuzzy-identity-decisions-csv`: contiene decisiones
  `merge` con `birth_year` curado y formato semicolon. La materializacion
  `fchmn_parser021_reparsed_curated_identity_review_20260604` aplica 32
  consolidaciones de atleta, 116 de resultados, 31 de relevos y 2 correcciones
  de año en atletas; el manifest resultante valida 63/63 sin `--load`.
- En la prueba incremental FCHMN del 2026-05-19 se detecto que
  `resultados-ii-copa-chile.pdf` era una revision/URL alternativa de la misma
  `II Copa Chile 2026` ya cargada desde `resultados-ii-copa-chile-1.pdf`.
  La base se limpio quirurgicamente para conservar la version `-1`: se elimino
  el segundo `load_run/source_document`, 132 resultados derivados de esa carga y
  15 atletas huerfanos creados por ella. Desde ahora el pipeline bloquea por
  defecto una fuente con checksum/URL distinta para una competencia ya cargada;
  solo se puede saltar con `--allow-competition-source-revision` y reemplazo
  controlado.
- En el mismo cierre se fusiono la carga de resultados de XIII Copa Peñalolén
  Master 2026 con la competencia planificada existente del calendario
  (`competition_id=5`). La fila generada por el PDF (`competition_id=81`) quedo
  eliminada tras mover 139 eventos, 1400 resultados, 96 relevos y el `load_run`.
  El loader ahora intenta reutilizar competencias planificadas sin resultados
  por fecha exacta, curso compatible y nombre similar antes de crear una nueva.
- Los resultados HY-TEK con prefijo `X` en el tiempo se tratan como resultados
  validos de exhibición/sin puntaje cuando traen `result_time_ms`; no deben
  mostrarse como `unknown`. Esto aplica tanto a resultados individuales como a
  relevos durante la carga a core: el prefijo `X` solo deja `rank_position` nulo.
  Los estados `XDQ`/`XDNF` se normalizan a `dsq`/`dnf` y `XNS` permanece
  `unknown` porque no hay tiempo válido.
- Manifest local curado vigente para carga FCHMN 2022-2026:
  `backend/data/raw/manifests/fchmn_historical_2022_2026_frozen_local_parser020_tracefixed_curated_20260512_identity_fix.jsonl`.
- Carpeta materializada asociada:
  `backend/data/raw/results_csv/fchmn_parser020_tracefixed_curated_20260512_identity_fix/`.
- Evidencia de validacion sin carga vigente:
  `backend/data/raw/batch_summaries/fchmn_historical_2022_2026_parser020_tracefixed_curated_validation_20260512_identity_fix.json`,
  con `state_counts.validated = 62`.
- Evidencia post-load vigente:
  `backend/data/raw/batch_summaries/fchmn_core_postload_tracefixed_curated_20260512_identity_fix_audit_20260512_summary.json`.
- La carga a core debe ser explicita con `--load` y seguir
  `backend/docs/pre_load_checklist.md`: backup, wipe controlado si corresponde,
  summary auditable y validacion post-load.
- Sudamericanos se mantienen como flujo separado y no deben mezclarse con el
  manifest local principal. Copa Cordillera / Dual Internacional si pertenece al
  circuito master FCHMN y queda incluida en el manifest local curado.
- La evidencia candidata actual incluye correcciones de `result_time`,
  `seed_time` y `points`: sin resultados validos bajo 10s, sin seeds bajo 25s
  en eventos de 100m o mas, y sin `points` sin posicion o sobre maximo esperado.
- Tras la revision post-load de relevos, el parser `0.1.17` tambien reclasifica
  puntos dobles de relevo (`18`, `14`, `12`, `10`) como `points` cuando HY-TEK
  no trae seed real; el manifest curado queda sin relevos validos bajo 25s.
- Una auditoria posterior sobre `core` detecto relevos con 8 integrantes en
  Dual Internacional Copa Chile 2025. El origen era duplicacion exacta en
  `relay_team.csv` y `relay_swimmer.csv`; parser `0.1.18` deduplica esas filas
  operacionales y el batch runner las bloquea si reaparecen antes de cargar.
- La auditoria de identidad post-load detecto 4 conflictos de genero. Se agrego
  soporte de correcciones auditables por CSV en `curate_athlete_names.py` para
  resolverlos antes del load, con reglas locales revisadas para Hernandez
  Salvador, Miranda Milanch, Molero Vianny y Orrego Ariel.
- LQBLO 2023 no era un caso sin nomina de relevos: el PDF trae integrantes en
  continuaciones posicionales dentro del layout multicolumna. Parser `0.1.19`
  extrae esas postas sin mezclar nombres de otros equipos o categorias.
- La trazabilidad multicolumna de LQBLO 2023 evidencio otra raiz: leer la pagina
  por filas fisicas podia asociar resultados de una columna al evento de otra.
  Parser `0.1.20` procesa cada pagina por columna logica completa antes de pasar
  a la siguiente, evitando clasificaciones de evento/genero/edad inconsistentes
  sin reclasificar manualmente resultados reales.
- La auditoria post-load de identidad fuzzy genero una bandeja revisada:
  `backend/data/raw/batch_summaries/fchmn_core_athlete_fuzzy_identity_candidates_20260501_revas.csv`.
  `curate_athlete_names.py` aplica solo filas `decision=merge`; las filas en
  blanco quedan como pendientes. Esa materializacion historica 20260501 consolido
  esas decisiones y valido 61/61 sin `--load`; el estado vigente actual es la
  materializacion 20260512 `identity_fix` de 62 documentos.
- La recarga 20260502 evidencio una segunda familia de duplicados ya conocida
  pero no persistida completamente: nombres con segundo apellido/segundo nombre
  omitido (`Luis`/`Luis Alberto`, `Abarca`/`Abarca Ramirez`) y candidatos con
  `birth_year` +/-1. `audit_expected_athlete_identity.py` ahora puede emitir una
  bandeja ampliada con `--expanded-identity-candidates-csv` para revisar estos
  casos antes de futuras cargas; sigue sin aplicar merges automaticamente.
- La auditoria post-load 20260512 sobre la carga `identity_fix` dejo limpia la
  trazabilidad critica: 62 documentos cargados, 0 faltantes en core, 0
  diferencias de checksum, 0 atletas huerfanos, 0 inconsistencias de evento
  contra genero/edad y 0 tiempos sospechosos. El unico duplicado exacto remanente
  es `Torres, Sergio` (`male`, `birth_year=1994`), homonimo confirmado y
  versionado como `keep_separate` en
  `backend/data/reference/athlete_accepted_homonyms.csv`.
- Las diferencias de puntos frente a la regla esperada y los relevos con nomina
  incompleta quedan como auditorias de fuente/formato: se conservan los puntos
  oficiales publicados en `points`, se agrega `expected_points` como calculo
  auditable, y no se inventan integrantes de relevo cuando la fuente no los
  permite reconstruir con seguridad.
- Para producto/API, el club vigente del atleta se deriva con la vista
  `core.athlete_current_club` desde la ultima observacion competitiva en
  individuales o relevos. `core.athlete.club_id` se mantiene como ayuda
  operativa de carga/cruce y no debe usarse como verdad de club vigente.

### Parser Updates
- **0.1.12**: Soporte para layout brasileño "Swim It Up" (ej. Sudamericano Recife).
- **0.1.13**: Soporte para Quadathlon (conversión a 4 pruebas de 50m), sufijos de récords, encabezados OCR "E vento" y layouts HY-TEK multi-columna.
- **0.1.15**: Corrección de bugs en layouts HY-TEK de dos columnas y fragmentación OCR. Reparación conservadora de textos como `Rojas, 2 20 Escuela...` sin aplicar aliases.
- **0.1.16**: Correcciones menores en nombres de atletas y relevos, validado sobre 97k filas de atletas con sobreescribimientos específicos.
- **0.1.17**: Corrección de tiempos imposibles en HY-TEK (menores a 10s) que leían los puntos como tiempo o no traían seed real. Bloqueos estrictos para `result.csv` y `relay_team.csv`.
- **0.1.18**: Deduplicacion operacional de filas exactas de relevos repetidas por paginas duplicadas del PDF y compuerta pre-load para `relay_team.csv`/`relay_swimmer.csv`.
- **0.1.19**: Soporte para integrantes de relevo en continuaciones posicionales de layouts HY-TEK multicolumna, validado con III Copa LQBLO 2023.
- **0.1.20**: Lectura HY-TEK multicolumna por columna logica completa para preservar el contexto correcto de evento antes de avanzar a otra columna, evitando resultados asignados a pruebas/generos/edades incorrectos.
- **0.1.21**: Soporte para encabezados HY-TEK de relevos con categoria agregada
  al final y compuerta batch contra encabezados de relevo no parseados en debug.
- **0.1.22**: Soporte para encabezados Sudamericanos mixtos
  `Evento ... Mixed ... SC Metros ... Relay`.
- **0.1.24**: Consolidacion Sudamericanos 2022-2026 desde la pagina fuente:
  normaliza `CI ...` como combinado individual, omite lineas auxiliares
  splits/records, acepta rank `--` y limpia `*` inicial en nombres HY-TEK.
- **0.1.25**: Correccion de extraccion Sudamericanos/Swim It Up: separa
  tiempos pegados a clubes cuando el resultado queda vacio y extiende la
  limpieza `(cid:976)` -> `f` a nombres de club.
- **0.1.26**: Correccion de relevos Sudamericanos/Swim It Up: no emite postas
  fuera de `leg_order` 1..4 y agrega compuerta pre-load equivalente.

### Curaduría de Atletas y Alias de Clubes
- Se automatizó la detección pre-load de errores OCR conocidos en nombres de atletas.
- Canonización de orden de nombres (`Nombre Apellido` -> `Apellido, Nombre`).
- Implementación de alias transitivos en `run_pipeline_results.py` (ej. `A -> B -> C` resuelve directo a `C`).
- La curaduría de identidades ahora requiere comprobaciones rígidas: mismo `birth_year`, mismo club y mismo género antes de proponer alias automático. Otras variaciones cruzan hacia revisión manual (ej. nombres extendidos).

### Auditoría Histórica
- **Foco 2022-2026:** El proyecto operativizó exitosamente 62 documentos del circuito local de la FCHMN para el periodo 2022-2026. Los años anteriores quedaron catalogados como backlog (legacy).
- **Competencias Internacionales:** Se separaron explícitamente eventos como el Sudamericano en un flujo de manifest diferente, asegurando que no se mezclen sin validación estricta del `competition_scope`.
- Copa Cordillera / Dual Internacional fue catalogada como circuito local (FCHMN).

*(Fin de los registros históricos exportados)*
