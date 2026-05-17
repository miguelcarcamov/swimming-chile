# Plan de Implementación Definitivo: Natación Chile (Cadena Oficial Auditable)

Este plan establece la hoja de ruta para evolucionar los scripts actuales hacia una plataforma de datos operable, confiable e idempotente. El foco principal es **primero blindar, después automatizar, después exponer producto**.

---

## Fase 0: Decisiones De Proyecto (Iniciación)
*Reglas básicas de orden e higiene.*

*   Confirmar estructura de datos ignorados por git (actualizar reglas).
*   Definir estructura de directorios estandarizada (`data/raw`, `data/staging/csv`, `tests/fixtures`, etc).
*   Documentar y aceptar que PostgreSQL será la fuente final de verdad.
*   Acuerdo establecido: Los CSVs completos NO se versionan.

## Fase 1: Blindaje Del Flujo Actual
*Crear una red de seguridad antes de tocar la arquitectura interna.*

*   Crear `requirements.txt` o `pyproject.toml` para fijar dependencias.
*   Agregar tests unitarios básicos:
    - Normalización de tiempos, géneros, estilos y status.
    - Parsing de líneas críticas.
*   Crear **golden fixtures**: pequeños archivos de prueba (no CSVs históricos completos) extraídos de PDFs reales para prevenir regresiones.
*   Documentar formalmente los contratos de entrada/salida del parser.
*   Limpiar la documentación desfasada (ej. actualizar `schema.md` sobre el estado real de los relevos).

## Fase 2: Trazabilidad e Idempotencia
*Sin esto, automatizar PDFs puede llenar la base de duplicados o datos dudosos.*

*   Crear tablas operativas en DB: `source_document`, `load_run`, `validation_issue`.
*   Registrar para cada ingesta: versión del parser, checksum del PDF, conteos y errores.
*   **Idempotencia**: Definir reglas estrictas de recarga (ej. si se vuelve a procesar el mismo PDF, se ignoran duplicados pero se actualizan cambios).
*   Configurar constraints/índices únicos mínimos obligatorios para pruebas, resultados y relevos.

## Fase 3: Modularización Controlada
*Refactorizar el monolito apoyados en la red de seguridad de la Fase 1.*

*   Extraer únicamente lógica compartida de bajo riesgo (normalización de strings, tiempos, género, estilos, matching de clubes) hacia módulos comunes (`natacion_chile/domain/`).
*   Mantener el CLI actual (`parse_results_pdf.py`, `run_pipeline_results.py`) compatible.
*   Avanzar en pasos pequeños y probados.

## Fase 4: Scraper y Batch Runner (Compuertas de Calidad)
*Automatización con compuerta, no ciega.*

*   Construir Scraper de apuntamiento a FCHMN (`scrape_fchmn.py`).
*   Descarga inteligente: URLs, checksums, detección de PDFs nuevos/modificados.
*   **Batch Runner con Estados**: Flujo de ejecución -> [Descargado -> Parseado -> Validado].
*   Si una validación arroja una alerta de calidad (ej. layout roto, 20% de dropped rows), se detiene la carga a Core y queda en estado *Requiere Revisión*.

## Fase 5: Curaduría de Identidad de Atletas
*Tratar la identidad como un flujo probabilístico, no rígido.*

*   Implementar matching basado en puntajes (*confidence scores*) a partir de: Nombre normalizado + Género + Año Estimado + Reforzador de Club.
*   Matches de alta confianza se unifican.
*   Las ambigüedades generan "candidatos dudosos" que se guardan para revisión manual.

## Fase 6: Producto de Datos
*Exposición limpia mediante contratos estables analíticos.*

*   Crear vistas SQL robustas o queries estables para consumo.
*   Levantar API transaccional mínima.
*   Desarrollo de WebApp Dinámica enfocada en:
    - Búsqueda e historial competitivo por Atleta / Club.
    - Mejores Marcas.
    - Rankings (temporada/categoría).
