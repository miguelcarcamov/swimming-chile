# Changelog Histórico (Natación Chile)

Este documento condensa los hitos y auditorías relevantes durante el desarrollo y carga de datos históricos (Fase 4 y Fase 5). La evidencia detallada original fue consolidada para mantener la documentación operativa limpia.

## Abril - Mayo 2026 (Consolidación de Pipeline FCHMN 2022-2026)

### Estado operativo vigente
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

### Parser Updates
- **0.1.12**: Soporte para layout brasileño "Swim It Up" (ej. Sudamericano Recife).
- **0.1.13**: Soporte para Quadathlon (conversión a 4 pruebas de 50m), sufijos de récords, encabezados OCR "E vento" y layouts HY-TEK multi-columna.
- **0.1.15**: Corrección de bugs en layouts HY-TEK de dos columnas y fragmentación OCR. Reparación conservadora de textos como `Rojas, 2 20 Escuela...` sin aplicar aliases.
- **0.1.16**: Correcciones menores en nombres de atletas y relevos, validado sobre 97k filas de atletas con sobreescribimientos específicos.
- **0.1.17**: Corrección de tiempos imposibles en HY-TEK (menores a 10s) que leían los puntos como tiempo o no traían seed real. Bloqueos estrictos para `result.csv` y `relay_team.csv`.
- **0.1.18**: Deduplicacion operacional de filas exactas de relevos repetidas por paginas duplicadas del PDF y compuerta pre-load para `relay_team.csv`/`relay_swimmer.csv`.
- **0.1.19**: Soporte para integrantes de relevo en continuaciones posicionales de layouts HY-TEK multicolumna, validado con III Copa LQBLO 2023.
- **0.1.20**: Lectura HY-TEK multicolumna por columna logica completa para preservar el contexto correcto de evento antes de avanzar a otra columna, evitando resultados asignados a pruebas/generos/edades incorrectos.

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
