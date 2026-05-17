# Metodología de trabajo con IA

Este documento permite retomar el proyecto en otra conversación sin depender del historial del chat. Resume la forma de trabajo acordada para Natación Chile.

## Fuentes de verdad

- **Arquitectura y Uso**: `backend/README.md`
- **Hoja de ruta**: `docs/plans/implementation_plan.md`
- **Reglas operativas para agentes**: `AGENTS.md`
- **Política de artefactos**: `backend/docs/data_artifacts.md`
- **Contratos del parser**: `backend/docs/parser_contracts.md`
- **Contrato del batch runner**: `backend/docs/batch_runner_contract.md`
- **Validación automatizada**: `backend/docs/fchmn_results_validation.md`
- **Checklist pre-carga/full reload**: `backend/docs/pre_load_checklist.md`
- **Modelo de Datos vigente**: `backend/docs/schema.md`
- **Trazabilidad e idempotencia**: `backend/docs/traceability_idempotency.md`
- **Historial de Decisiones (Log)**: `backend/docs/CHANGELOG.md`

## Principio central

El aprendizaje con IA debe avanzar junto con el plan real del proyecto. Cada sesión debe empujar una fase del producto y explicar el dónde, por qué y para qué de los cambios.

`AGENTS.md` y este documento se complementan:
- `AGENTS.md`: reglas cortas e imperativas para actuar dentro del repo.
- `ai_workflow.md`: memoria metodológica y continuidad entre conversaciones.
- Los contratos técnicos viven en docs específicas. Evitar duplicar detalles largos.

**Orden actual del proyecto:**
1. Blindar.
2. Trazabilidad e idempotencia.
3. Modularizar.
4. Automatizar con compuertas (Fase Actual).
5. Curar identidad de atletas.
6. Exponer producto de datos.

## Flujo obligatorio por cambio

1. **Diagnóstico**:
   - Revisar `git status`.
   - Leer archivos relevantes antes de proponer cambios.
   - Identificar cambios locales del usuario y no sobrescribirlos.
2. **Propuesta corta**:
   - Explicar el patch antes de editar.
   - Mantener cambios mínimos y localizados.
3. **Implementación**:
   - Seguir patrones existentes.
   - Si cambia regex o parseo, agregar comentario breve.
4. **Verificación**:
   - Ejecutar tests relevantes.
   - Ejecutar `py_compile` si se modifican scripts Python.
5. **Cierre**:
   - Revisar `git status`.
   - Resumir diagnóstico, cambios y verificación.
   - Proponer mensaje de commit.

## Regla de sincronización documental

Si cambia el comportamiento o el contrato:
1. Actualizar tests.
2. Actualizar el contrato técnico correspondiente.
3. Actualizar `README.md` si afecta uso humano.
4. Actualizar `AGENTS.md` solo si cambia una regla operativa.
5. Registrar cambios de gran envergadura o decisiones arquitectónicas en `CHANGELOG.md`.

## Estado actual

- **Fase activa**: Fase 4, scraper y batch runner con compuertas de calidad.
- El parser soporta PDFs HY-TEK y Swim It Up, generando CSVs que pasan compuertas estrictas.
- El proceso ELT (Extract, Load, Transform) está separado y asegurado mediante manifests `.jsonl`.
- `run_fchmn_results_validation.py` automatiza discovery -> download -> batch validation sin usar `--load` automáticamente.

## Prompt recomendado para retomar

Usar este texto al iniciar una nueva conversación:

```text
Lee primero docs/plans/implementation_plan.md, backend/README.md, backend/docs/ai_workflow.md y AGENTS.md.
Luego revisa git status y los scripts relevantes antes de proponer cambios.
Continúa según la metodología acordada: diagnóstico, propuesta corta, patch mínimo, tests, git status y propuesta de commit.
Si hay cambios locales del usuario, respétalos y trabaja alrededor de ellos.
Explica el qué, el por qué, el dónde y lo aprendido de cada cambio.
Fase activa: Fase 4. No cargues a core ni uses --load salvo pedido explícito.

Si la conversación retoma una carga o recarga, sigue backend/docs/pre_load_checklist.md sin saltar backup, wipe controlado y validación post-load.
```

## Siguiente paso sugerido

- Si se retoma una carga explícita, seguir `backend/docs/pre_load_checklist.md`: verificar estado real, ejecutar `--load` con summary auditable y validar duplicados.
- En identidad de atletas, priorizar la etapa post-parser/pre-load `curate_athlete_names.py` antes de seguir agregando heurísticas puntuales al parser.
- Las incoherencias `event_name` vs genero/edad deben bloquear la validacion,
  pero no borrar resultados reales automaticamente. Si el caso evidencia mala
  lectura de columnas, corregir/reclasificar el evento en la materializacion
  pre-load y dejar evidencia auditable.
- La materialización vigente para FCHMN local 2022-2026 es
  `backend/data/raw/manifests/fchmn_historical_2022_2026_frozen_local_parser020_tracefixed_curated_20260512_identity_fix.jsonl`.
  Usa parser `0.1.20`, incluye 62 documentos, decisiones manuales fuzzy con
  `decision=merge`, exclusiones revisadas, homónimos aceptados versionados y
  valida 62/62 sin `--load`.
- Antes de cerrar una nueva recarga, generar y revisar la bandeja ampliada de
  identidad con `audit_expected_athlete_identity.py --expanded-identity-candidates-csv`.
  Esta bandeja cubre segundo apellido/segundo nombre omitido e indicios de
  `birth_year` +/-1; solo las filas revisadas como `merge` deben pasar luego a
  `curate_athlete_names.py`.
- Diseñar automatización futura para detectar PDFs nuevos o cambios de checksum, validar y reportar sin cargar automáticamente.
- No crear tablas nuevas sin una migración explícita.
