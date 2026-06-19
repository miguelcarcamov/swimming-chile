# Contrato del batch runner y compuertas

Este documento inicia la Fase 4. Define el contrato minimo antes de implementar
scraper, descarga automatica o compuertas duras.

La meta es automatizar con control: descubrir o recibir PDFs, parsearlos,
validarlos y solo cargar a core cuando el lote cumple condiciones minimas de
calidad.

## Alcance inicial

El batch runner debe orquestar componentes existentes:

- `backend/scripts/parse_results_pdf.py` para transformar PDF a CSVs.
- `backend/scripts/run_pipeline_results.py` para cargar CSVs ya validados.
- `source_document`, `load_run` y `validation_issue` para trazabilidad en DB.

El scraper de FCHMN es una pieza separada. Puede alimentar el batch runner con
URLs y rutas locales, pero no debe mezclarse con la logica de parseo, validacion
o carga.

## Entradas

Una unidad de trabajo representa un PDF de resultados o una carpeta ya parseada.

Campos minimos esperados:

- `source_id`: origen del documento.
- `source_url`: URL original cuando exista.
- `pdf_path`: ruta local del PDF cuando se vaya a parsear.
- `input_dir`: carpeta de CSVs cuando el parseo ya exista.
- `competition_id` o metadata suficiente para resolver/crear competencia.
- `default_source_id`: source por defecto para filas generadas.

Reglas:

- Si existe PDF, la identidad preferida es `pdf_sha256`.
- Si no existe PDF, se usa `source_url` cuando este disponible.
- Si no hay checksum ni URL, el lote se considera manual y no idempotente a nivel documental.

### Manifest JSONL local

Antes del scraper, el formato estable para lotes locales es JSONL: una unidad de
trabajo por linea, sin envolver el archivo en un arreglo JSON. Las lineas vacias
y las lineas que empiezan con `#` se ignoran. Los manifests se leen como UTF-8 y
tambien toleran BOM UTF-8 generado por herramientas de Windows.

Cada entrada debe usar exactamente una de estas formas:

```json
{"input_dir": "backend/data/raw/results_csv/competencia_x", "competition_id": 1, "default_source_id": 1}
```

```json
{"pdf": "backend/data/raw/results_pdf/competencia_x.pdf", "out_dir": "backend/data/raw/results_csv/competencia_x", "competition_id": 1, "default_source_id": 1}
```

Campos por entrada:

- `input_dir`: carpeta ya parseada con CSVs operativos.
- `source_url`: URL original del documento cuando exista; el downloader la usa
  para descargar y el batch runner la conserva para trazabilidad al cargar.
- `pdf`: PDF local a parsear antes de validar. `pdf_path` se acepta como alias
  compatible con el nombre conceptual del contrato.
- `out_dir`: carpeta donde el parser escribira CSVs; requerido con `pdf` o
  `pdf_path`.
- `competition_id`: opcional si viene por CLI; el valor de la entrada tiene
  prioridad sobre el valor global.
- `competition_scope`: opcional en validacion; requerido para cargar a core. La
  primera compuerta implementada permite `--load` solo cuando el scope curado
  coincide con `fchmn_local` por defecto. El valor se persiste en
  `competition.competition_scope` al cargar para permitir filtros posteriores
  por circuito/ambito curado.
- `governing_body_code` y `governing_body_name`: opcionales; se propagan al
  loader y se persisten en `competition.governing_body_*`. Representan el
  organismo deportivo rector (`fchmn`, `consada`, `fechida`) y no reemplazan a
  `source_id` ni a `organizer`.
- `default_source_id`: opcional; hereda el valor global cuando no se declara.
- `excel_name`: opcional; hereda el valor global cuando no se declara.

Los manifests generados por el scraper deben agrupar `pdf` y `out_dir` por año:
`backend/data/raw/results_pdf/fchmn/<año>/...` y
`backend/data/raw/results_csv/fchmn/<año>/...`. El año se infiere desde la URL
del PDF cuando es posible y puede forzarse con `--year`.
Si dos PDFs generan el mismo slug, el scraper solo agrega sufijos dentro del
mismo año/carpeta destino; el mismo nombre puede repetirse en años distintos sin
colisionar.

Las rutas relativas declaradas en `input_dir`, `pdf`, `pdf_path` y `out_dir` se
resuelven desde la raiz del proyecto, no desde el directorio actual del proceso.
Esto permite ejecutar tests y comandos desde subcarpetas sin cambiar el
significado del manifest.

Cada documento se procesa de forma aislada. Un documento en `requires_review`
debe quedar reportado en el resumen del manifest, pero no debe impedir que los
otros documentos del mismo manifest se validen con su propio estado.

## Salidas esperadas

Por cada unidad procesada:

- PDF almacenado localmente, si aplica.
- CSVs operativos del parser en una carpeta estable.
- `metadata.json` con `pdf_name`, `pdf_sha256` y `parser_version` cuando exista PDF.
- Estado final del batch.
- Evidencia de issues de validacion.
- Carga a core solo si las compuertas lo permiten.

Por cada manifest procesado:

- Estado agregado del manifest.
- `state_counts` con cantidad de documentos por estado.
- Detalle por documento para auditoria.
- Un manifest sin documentos queda `failed`; validar cero unidades no entrega
  evidencia operativa.

Los PDFs, CSVs completos y Excels generados siguen sin versionarse.

## Estados del batch

Estados canonicos propuestos:

- `discovered`: el documento fue encontrado por scraper o manifest, pero aun no se descargo.
- `downloaded`: el PDF esta disponible localmente y tiene checksum calculable.
- `parsed`: el parser genero salidas operativas.
- `validated`: las salidas pasaron compuertas minimas y pueden cargarse.
- `requires_review`: existen alertas bloqueantes o ambiguas; no se carga a core.
- `loaded`: la carga a staging/core termino correctamente.
- `failed`: hubo error tecnico que impidio completar la etapa.

Relacion con `load_run`:

- `load_run` sigue describiendo la ejecucion del pipeline de carga.
- El estado del batch describe la orquestacion previa y posterior a la carga.
- No se debe ampliar `load_run.status` sin una migracion explicita.

## Compuertas minimas antes de cargar

Las compuertas duras ocurren antes de ejecutar `run_pipeline_results.py`.

Bloquean la carga y dejan el lote en `requires_review`:

- Falta un CSV operativo obligatorio: `club.csv`, `event.csv`, `athlete.csv` o `result.csv`.
- Falta `metadata.json` para un PDF parseado.
- Falta `pdf_sha256` en metadata cuando la entrada fue un PDF.
- El parser no encontro eventos.
- El parser no encontro resultados individuales ni relevos.
- `debug_unparsed_lines.csv` supera el umbral permitido.
- `debug_unparsed_lines.csv` conserva encabezados de relevos sin parsear, aunque
  el ratio global de debug sea bajo.
- Hay valores fuera del canon documentado para genero, estilo o status.
- Hay filas de resultado sin `event_name` o sin identidad observable de atleta/equipo.
- `result.csv` trae resultados individuales cuya `age_at_event` no calza con
  el rango etario del `event_name`. Esto bloquea la carga porque suele indicar
  una mala asignacion de columna/evento del parser; el resultado no debe
  descartarse automaticamente, debe reclasificarse o revisarse.
- `result.csv` trae resultados individuales cuyo atleta curado tiene genero
  contrario al genero del `event_name`. Esto bloquea la carga salvo que exista
  una correccion pre-load revisada.
- Hay residuos conocidos de OCR en nombres de atletas de `athlete.csv`,
  `result.csv` o `relay_swimmer.csv`, como vocal seguida de vocal acentuada
  (`Goámez`, `AÁlvarez`, `Lucíá`, `Muüller`) o ene/eñe separada (`Yañ ñez`).
- `athlete.csv` trae nombres sin formato `Apellido, Nombre`; estos deben
  canonizarse en la etapa pre-load si la fuente viene como `Nombre Apellido`.
- `result.csv` o `relay_team.csv` traen filas `valid` con `result_time_ms` bajo
  10000. Esos valores son imposibles para el circuito master y suelen indicar
  puntos interpretados como tiempo o split OCR incompleto.
- En `relay_team.csv`, el umbral minimo es mas estricto: un relevo `valid` bajo
  25000 ms queda bloqueado, porque suele indicar puntos dobles de relevo
  (`18`, `14`, `12`, `10`) interpretados como tiempo.
- `result.csv` o `relay_team.csv` traen `seed_time_ms` bajo 25000 en pruebas de
  100m o mas. En esos casos el seed queda como evidencia sospechosa de columna
  corrida u OCR y debe corregirse o limpiarse antes de cargar.
- `points` aparece en filas sin `rank_position`, o supera el maximo de puntaje
  esperable por fila: 9 en individuales y 18 en relevos. Esto captura tiempos
  post-DQ o marcas de exhibicion que el parser no debe tratar como puntaje.
- `expected_points` no viene desde el parser: lo calcula el loader al insertar
  en core usando `rank_position`. Individuales usan 9/7/6/5/4/3/2/1 y relevos
  el doble. Este valor permite auditar la fuente sin modificar `points`.
- `relay_team.csv` o `relay_swimmer.csv` traen filas duplicadas exactas de
  relevos. Esto bloquea la carga porque puede producir equipos con integrantes
  repetidos en `core.relay_result_member`.
- `relay_swimmer.csv` trae `leg_order` vacio o fuera del rango 1..4. Esto
  bloquea la carga antes de PostgreSQL porque `core.relay_result_member` solo
  admite cuatro postas por relevo.
- `athlete.csv`, `result.csv` o `relay_swimmer.csv` traen nombres con residuos
  estructurales de solapamiento, como encabezados, parentesis o marcadores de
  posta incrustados. Toda entrada capaz de crear atletas debe pasar la misma
  compuerta antes de cargar.
- Los nombres de club literales confirmados contra la fuente que requieran
  limpieza deben resolverse mediante `backend/data/reference/club_alias.csv` a
  una forma canonica limpia; no se permite almacenar el residuo en core.
- Se intenta cargar con `--load` sin `competition_scope=fchmn_local` o sin el
  scope requerido por `--required-competition-scope`.

Umbral inicial:

- `debug_unparsed_lines / lineas_relevantes_parseadas > 0.20` requiere revision.
- Cualquier encabezado `Event|Evento ... Relay|Relevo` remanente en debug
  requiere revision: puede evidenciar una perdida completa o parcial de relevos.

Este umbral es conservador y debe validarse con fixtures antes de automatizar
cargas masivas.

## Validaciones no bloqueantes iniciales

Estas alertas se registran, pero no bloquean por defecto:

- Puntos ausentes.
- Diferencias finas de puntaje por empates o reglas especiales de reparto,
  siempre que el valor no supere el maximo y exista posicion observada.
- `seed_time` ausente.
- Club inferido para relevos.
- `birth_year_estimated` ausente cuando no hay edad.
- Diferencias menores de nombres de clubes cubiertas por aliases manuales.

## Separacion de responsabilidades

Scraper:

- Descubre URLs.
- Incluye todos los PDFs por defecto. Si se necesita una exploracion acotada,
  puede filtrarse con `--include-keyword`, pero ese filtro no debe usarse como
  compuerta final porque FCHMN puede publicar resultados con typos en la URL
  (por ejemplo `resutados`).
- Emite manifest JSONL con `source_url`, ruta local esperada del PDF y `out_dir`.
- Puede recorrer paginas WordPress con `--crawl-pages`, deduplicando URLs de PDF
  entre paginas y deteniendose cuando una pagina paginada devuelve 404.
  Este modo es para backfill historico one-shot; la automatizacion recurrente
  debe enfocarse en resultados recientes y cambios de checksum.
- Mantiene la descarga de PDFs como paso separado y explicito.
- No parsea ni carga a DB.

Downloader:

- Lee un manifest JSONL con `source_url` y `pdf` o `pdf_path`.
- Usa la misma lectura JSONL que el batch runner y falla si el manifest no
  contiene documentos.
- Descarga cada PDF hacia su ruta local esperada.
- No reemplaza PDFs existentes salvo `--overwrite`.
- Calcula `pdf_sha256` para el resumen auditable cuando el PDF existe localmente.
- Con `--overwrite`, compara el checksum anterior y el nuevo para reportar
  `updated` si cambio o `unchanged` si el contenido era identico.
- Produce resumen de manifest con `state_counts`.
- No parsea, no valida CSVs y no carga a DB.

Orquestador de validacion FCHMN:

- `backend/scripts/run_fchmn_results_validation.py` encadena scraper, downloader y batch
  validation.
- No acepta ni pasa `--load`; la carga a core queda en un paso manual explicito.
- Acepta varias opciones `--url` para consolidar discovery desde paginas de menu,
  resultados y nacionales en un unico manifest deduplicado.
- Escribe manifest, resumen de descarga y resumen de batch en rutas auditables.
- Reporta `discovered_documents` y falla antes de descargar si discovery no
  encuentra documentos.
- Termina con codigo distinto de cero si la cadena no queda `validated`.

Batch runner:

- Decide si un documento se debe procesar o saltar.
- Ejecuta parser.
- Si el parser falla para un documento del manifest, marca ese documento como
  `failed` y continua con los demas.
- Evalua compuertas.
- Conserva `source_url` desde el manifest y la pasa al pipeline como
  `--competition-source-url` cuando se ejecuta `--load`.
- Conserva `competition_scope` desde el manifest y la pasa al pipeline como
  `--competition-scope` cuando se ejecuta `--load`.
- Conserva `governing_body_code` y `governing_body_name` desde el manifest y los
  pasa al pipeline como `--governing-body-code` y `--governing-body-name` cuando
  se ejecuta `--load`.
- Por defecto, si el pipeline resuelve una competencia ya cargada y el PDF
  entrante tiene checksum/URL distinta a la fuente existente, la carga se
  bloquea. Una revisión oficial debe tratarse como reemplazo controlado y solo
  puede saltar la compuerta con `--allow-competition-source-revision`.
- Antes de crear una competencia nueva, el pipeline debe intentar reutilizar una
  competencia planificada sin resultados ni `load_run` cuando pertenezca a la
  misma temporada y tenga nombre similar. La fecha y el curso inferido desde los
  eventos del PDF reemplazan los valores planificados si el calendario quedó
  desactualizado.
- Ejecuta pipeline solo si el lote esta validado.
- Si se usa `--load`, exige que cada documento tenga un `competition_scope`
  curado que coincida con `--required-competition-scope` (`fchmn_local` por
  defecto). Los documentos sin scope o con scope distinto quedan
  `requires_review`.
- Produce resumen auditable con `state_counts`.

Manifest freezer:

- `backend/scripts/freeze_validated_manifest.py` lee un summary JSON de
  `run_results_batch.py` y escribe un manifest JSONL congelado.
- Puede recibir varios `--batch-summary` para consolidar evidencias ya revisadas
  en un unico manifest congelado.
- Incluye solo documentos con estado `validated`.
- Excluye documentos `failed` y `requires_review`.
- Agrega `competition_scope` curado a cada entrada incluida. Tambien puede
  agregar `governing_body_code` y `governing_body_name` cuando el flujo curado
  distingue organismo rector.
- Requiere una lista curada de `source_url` permitidas, salvo que se use
  `--allow-all-validated` de forma explicita.
- Deduplica documentos repetidos por `source_url`.
- No descarga, no parsea, no valida CSVs y no carga a DB.

Parser:

- Contiene heuristicas PDF.
- Genera CSVs y debug.
- No decide si se carga a core.

Pipeline:

- Hace limpieza generica y carga.
- Aplica `club_alias.csv` colapsando cadenas transitivas de aliases antes de
  cargar. Si existe `A -> B -> C`, `A` y `B` deben resolver al canonical final
  `C`, no a un canonical intermedio.
- Al transformar `relay_team.csv` + `relay_swimmer.csv`, usa `relay_team.club_name` cuando venga informado y conserva la inferencia desde `club.csv` solo como fallback compatible. Si una fuente repite el mismo `event_name` + `club_name` + `relay_team_name`, conserva `relay_rank_position` y `relay_result_time_ms` en staging para enlazar cada integrante al resultado de relevo correcto. El batch no debe crear clubes genéricos desde relevos: los cortes de línea conocidos, como ADAIP en Sudamericano 2026, se corrigen antes en la materialización curada.
- Deduplica atletas dentro de cada carga por nombre normalizado, genero, año de
  nacimiento y club observado para evitar variantes OCR/acento equivalentes en
  un mismo `INSERT`.
- Usa la misma clave normalizada de atleta para actualizar años de nacimiento y
  enlazar `result`/`relay_result_member` contra `core.athlete`; las decisiones
  manuales materializadas en CSVs curados no deben perderse por diferencias de
  acento o puntuacion entre documentos.
- Las copias curadas pueden canonizar nombres en orden `Nombre Apellido` a
  `Apellido, Nombre` como etapa pre-load auditable. El pipeline consume ese
  resultado materializado, no vuelve a inferir decisiones manuales.
- Las copias curadas tambien pueden resolver cadenas de merges manuales y
  reglas de identidad univocas antes de cargar. El pipeline debe honrar esos
  CSVs; no debe reconstruir merges parciales desde cero durante la carga.
- La materializacion pre-load puede descartar filas de `result.csv` cuando el
  genero inferido del evento contradice la identidad de atleta ya curada, o
  cuando la misma identidad aparece en ambos generos y la fila sospechosa trae
  un tiempo de distancia larga claramente recortado por layout/OCR.
- La materializacion pre-load puede reclasificar `event_name` de filas de
  `result.csv` mediante decisiones revisadas cuando el PDF contiene resultados
  reales, pero el parser los asigno al evento equivocado por continuidad de
  columnas. Esta correccion debe mover la fila al evento correcto; no debe
  eliminar el resultado real.
- Persiste `--competition-scope` en `competition.competition_scope` cuando crea
  o reutiliza una competencia.
- Persiste `--governing-body-code` y `--governing-body-name` en
  `competition.governing_body_code` y `competition.governing_body_name` cuando
  crea o reutiliza una competencia.
- Registra `source_document`, `load_run` y `validation_issue`.
- No debe implementar heuristicas agresivas del PDF.

## Contrato de idempotencia

- Si el mismo `pdf_sha256` ya fue procesado y cargado, el batch runner puede saltar la carga.
- Si el mismo checksum aparece con nueva URL, se actualiza trazabilidad del documento, no se duplica core.
- Si cambia el checksum o la URL para una competencia ya cargada, no se carga
  automáticamente sobre core. El caso queda como revisión de fuente y requiere
  decisión humana: conservar versión previa, reemplazarla o habilitar
  explícitamente `--allow-competition-source-revision` junto con limpieza
  controlada.
- Si el parser cambia de version, se permite reprocesar, pero la carga a core debe seguir siendo idempotente.

## Fuera de alcance de este primer paso

- Implementar scraper real contra FCHMN.
- Crear tablas nuevas de batch state.
- Cambiar estados de `load_run`.
- Bloquear el pipeline manual existente.
- Resolver identidad probabilistica de atletas.
- Curar aliases automaticamente.

## Siguiente implementacion sugerida

Extender `backend/scripts/run_results_batch.py` para que:

1. Soporte entradas `pdf` en manifest con fixtures controlados.
2. Escriba resumen agregado y por documento en formato estable.
3. Mantenga scraper FCHMN separado del parseo, validacion y carga.
4. Use estados persistentes cuando exista una tabla operativa de batch.

Primer scraper de apuntamiento:

- `backend/scripts/scrape_fchmn.py` descubre enlaces PDF desde una URL o HTML
  local.
- Escribe un manifest JSONL para el batch runner.
- No descarga PDFs, no parsea, no valida y no carga a core.
- `backend/scripts/download_manifest_pdfs.py` descarga los PDFs declarados en el
  manifest como paso separado y genera un resumen con checksum.
