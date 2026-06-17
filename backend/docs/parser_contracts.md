# Contratos del parser PDF

Este documento fija los contratos minimos de entrada y salida del parser antes de modularizarlo. La meta es que los tests protejan el comportamiento actual y que cualquier cambio futuro pueda explicarse contra estos acuerdos.

## Entrada

- Fuente principal: PDF de resultados FCHMN/HY-TEK.
- El parser recibe un archivo PDF y parametros operativos como `--out-dir`, `--competition-id` y `--default-source-id`.
- Los layouts soportados incluyen encabezados de evento en ingles y espanol, cursos `LC/SC Meter` y `CL/CP/CC Metro`, resultados individuales y relevos.
- Desde parser `0.1.12`, tambien se soporta el layout brasileno "Swim It Up" detectado por watermark `Sistemas de Natacao Swim It Up`, con headers de evento en portugues, franjas etarias `FAIXA`, fechas tipo `13 a 17/04/2026`, individuales y relevos por columnas.
- Desde parser `0.1.13`, tambien se soportan PDFs HY-TEK con resultados en multiples columnas (`#1 Women...`) y planillas `Quadathlon`; estas ultimas se normalizan como cuatro pruebas canonicas 50m (`butterfly`, `backstroke`, `breaststroke`, `freestyle`) y no introducen un stroke nuevo.
- Desde parser `0.1.16`, los nombres de atletas y nadadores de relevo corrigen
  artefactos OCR acotados solo cuando hay evidencia de layout o respaldo de
  pruebas individuales. No se reescriben sufijos fuente como `Rojas, 2`.
- Desde parser `0.1.17`, filas HY-TEK sin seed real que terminan en puntos
  (`... 1:22,49 1,00`) deben guardar `1:22,49` como `result_time_text` y
  `1,00` como `points`, no como tiempo de 1 segundo. En Quadathlon, si un unico
  split OCR queda bajo 10 segundos y el total permite inferirlo, se reconstruye
  el split desde la suma del total. La misma version corrige desplazamientos de
  `seed_time` cuando un token numerico de club queda antes de `NT` o antes de
  dos tiempos reales; para pruebas de 100m o mas, un seed bajo 25 segundos se
  limpia en forma conservadora en vez de inferir un tiempo no observado.
- En relevos HY-TEK sin seed real, los puntos finales pueden ser dobles
  (`18,00`, `14,00`, `12,00`, `10,00`). Esos tokens deben guardarse en
  `points` y no como `result_time_text`.
- Desde parser `0.1.18`, si un PDF repite exactamente la misma tabla de relevos
  en paginas distintas, `relay_team.csv` y `relay_swimmer.csv` deben conservar
  una sola fila operacional por equipo/nadador observado.
- Desde parser `0.1.19`, los relevos HY-TEK multicolumna tambien soportan
  integrantes sin marcadores `1)`/`2)`, cuando aparecen como continuacion
  posicional del equipo en la misma columna, por ejemplo
  `Perez, Romulo M31 Correa, Carolina W31`.
- Desde parser `0.1.20`, el lector HY-TEK multicolumna procesa cada pagina por
  columna logica completa antes de pasar a la siguiente columna. Esto evita que
  una linea de una columna derecha quede asociada accidentalmente al evento de
  otra columna, como ocurria en LQBLO 2023.

## Salidas operativas

El parser debe generar CSVs con nombres estables:

- `club.csv`
- `event.csv`
- `athlete.csv`
- `result.csv`
- `relay_team.csv`
- `relay_swimmer.csv`

Tambien puede generar archivos de trazabilidad/debug:

- `raw_result.csv`
- `raw_relay_team.csv`
- `raw_relay_swimmer.csv`
- `debug_unparsed_lines.csv`
- `metadata.json`
- Excel consolidado para revision manual

## Canon esperado

- `event.gender`: `women`, `men`, `mixed`.
- `athlete.gender` y nadadores de relevo: `female`, `male`.
- `event.stroke`: `freestyle`, `backstroke`, `breaststroke`, `butterfly`, `individual_medley`, `medley_relay`, `freestyle_relay`.
- `status`: `valid`, `dns`, `dnf`, `dsq`, `scratch`, `unknown`.

## Reglas de trazabilidad

- `metadata.json` debe incluir `pdf_name`, `pdf_sha256` y `parser_version` cuando el origen sea un PDF.
- `seed_time_text` y `result_time_text` conservan la forma normalizada del tiempo o status.
- `seed_time_ms` y `result_time_ms` se derivan cuando el tiempo es comparable.
- `age_at_event` pertenece al resultado observado.
- `birth_year_estimated = competition_year - age_at_event` cuando existe anio de competencia.
- `relay_team.csv` puede incluir `club_name`. Cuando existe, representa el club observado del equipo de relevo y debe preservarse hacia la carga; cuando falta o viene vacio, el pipeline puede inferir el club desde `club.csv` y `relay_team_name`.
- Las heuristicas propias del PDF viven en el parser; el pipeline solo debe hacer limpieza generica y carga.
- El parser normaliza sufijos de categorias de edad pegados al estilo en encabezados HY-TEK, por ejemplo `Breast 40 a 99 años` o `Medley 120 a 159 años Relay`, sin cambiar el canon de `event.stroke`.
- Desde parser `0.1.21`, también reconoce relevos HY-TEK con categoría agregada
  al final del encabezado, por ejemplo
  `Event 10 Women 400 SC Meter Freestyle Relay 240 a 279`,
  `Event 7 Mixed 200 SC Meter Medley C 160 a 199 años Relay` o
  `Evento 11 Mixto 200 CL Metro Combinado 120 a 159 años Relevo`.
- Desde parser `0.1.22`, tambien reconoce encabezados Sudamericanos mixtos
  que combinan etiqueta espanola e ingles, por ejemplo
  `Evento 17 Mixed 72-99 4x50 SC Metros Combinado Relay`.
- Desde parser `0.1.24`, el flujo Sudamericanos tambien normaliza estilos
  `CI Piscina ...` / `CI Mayores ...` como `individual_medley`, acepta filas
  no rankeadas con `--`, limpia `*` inicial de nombres HY-TEK y omite lineas
  auxiliares de parciales o records que no son resultados.
- Desde parser `0.1.25`, en layouts Sudamericanos/Swim It Up se separan de
  forma conservadora los tiempos que llegan pegados al nombre de club cuando la
  columna de resultado viene vacia. Tambien se repara `(cid:976)` como `f` en
  texto extraido general, para que clubes como `Del(cid:976)ines` se materialicen
  como `Delfines` antes de las auditorias pre-load.
- Desde parser `0.1.26`, los layouts Sudamericanos/Swim It Up no deben emitir
  nadadores de relevo con `leg_order` fuera de 1..4. Las lineas posteriores al
  cuarto integrante, incluidos pies de pagina o nombres arrastrados por layout,
  no son postas cargables.
- El parser puede omitir parciales/splits de carrera en `debug_unparsed_lines.csv` cuando no son filas de resultado; esto evita bloquear la validacion por lineas auxiliares de HY-TEK.
- Si una fila con resultado tipo status deja el tiempo de seed pegado al club, por ejemplo `Club Sparta A C 49.33 DQ DQ`, el parser debe separar `club_name = Club Sparta A C`, `seed_time_text = 49,33` y `result_time_text = DQ`.
- Ningun resultado `valid` individual o de relevo debe materializarse con
  `result_time_ms` bajo el umbral minimo del batch runner; esos casos son
  evidencia de columna corrida, puntos interpretados como tiempo o OCR
  incompleto.
- Ningun `seed_time_ms` individual o de relevo bajo 25000 debe materializarse
  en pruebas de 100m o mas; si la fuente no permite reconstruirlo con evidencia
  de layout, el parser debe dejar el seed vacio.
- Las filas sin posicion (`---`) con `DQ`/`DNF`/`DNS` o marca de exhibicion `X`
  no deben conservar puntos aunque el PDF traiga un token numerico al final; ese
  token no representa puntaje cargable.
- Los relevos no deben materializar duplicados exactos. Si la misma combinacion
  de evento, equipo, posta, nadador, genero y edad aparece repetida por una
  pagina duplicada del PDF, la salida operacional conserva solo una ocurrencia.
- En layouts multicolumna, los integrantes de relevo sin marcador explicito se
  asignan solo al equipo activo de esa columna y hasta completar cuatro postas;
  no se deben arrastrar nombres desde otro equipo, otra categoria o texto
  corrido de columnas vecinas.

## Fixtures de prueba

Los fixtures versionados deben ser pequenos y representativos. No se versionan PDFs completos ni CSVs historicos completos; solo lineas o archivos minimos necesarios para prevenir regresiones.
