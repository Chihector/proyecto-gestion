# Roadmap — Sala de crisis COVID-19

## Objetivo

Construir una plataforma reproducible con los datos históricos de Johns Hopkins (22-ene-2020 a 9-mar-2023) y usarla para explicar la pandemia en Chile y el mundo, evaluar qué se podía anticipar y entregar un tablero y tres recomendaciones respaldadas por evidencia.

La exploración de enero a junio de 2020 es solo el punto de partida. El grueso del proyecto está en la plataforma y la inteligencia (R1–R8); el entregable vale 70 % y la sesión del Comité, 30 %.

## Avance actual

- **Estado al 4-nov-2026:** Hito 2 (plataforma) **completo**; Hito 3 (análisis y tablero) **completo salvo el ensayo**; falta el Comité (24-nov) y la entrega (25-nov). Todo es reproducible con el README.
- **R1 Ingesta y arquitectura — completo.** Descarga automatizada (1.143 reportes + 5 series + UID + OWID + OxCGRT; reutiliza lo descargado; errores explícitos y código 1); tres capas; Parquet 109 MB vs 587 MB (18,6 %), lectura 2,63 s vs 21,58 s (8,2×); DuckDB justificado (vs SQLite/Postgres/NoSQL); equivalente en la nube con estimación (~US$35–50/mes).
- Capa limpia (`data/clean/daily_reports.parquet`, 4.287.473 × 17 cols) y `etapa_esquema` detectada por columnas crudas (etapa_1 hasta 2020-02-29 · etapa_2 03-01→03-21 · etapa_3 03-22→05-28 · etapa_4 05-29→11-08 · etapa_5 desde 2020-11-09, renombra Incident_Rate/Case_Fatality_Ratio). `recovered`/`active` nulos en 66 % (JHU discontinuó desde 2021-03; ~100 % desde 2021-10). Ningún archivo quedó con esquema desconocido; cotejo series↔reportes al cierre: Δ=0 (676.570.149 exacto).
- **Identidad territorial resuelta** (`src/territorios.py`): 4.410 claves crudas → **4.284 territorios canónicos**; **99,95 % de las filas empatan con la UID** (99,90 % con iso3); Chile pasa a reporte regional el **2020-05-20**; alias documentados (erratas JHU, censos EE.UU., territorios bajo país administrador); especiales (barcos/eventos) marcados; linaje `clave_raw`+`fecha` → archivo y fila.
- **DW estrella DuckDB** (`data/dw/covid.duckdb`): `dim_fecha` (1.143), `dim_territorio` (4.284), `fact_covid` (**4.287.374**; 99 pares mismo territorio/fecha fusionados conservando el mayor acumulado; 0 duplicados y 0 fechas huérfanas), `vacunacion` OWID (196.246 filas) y `restricciones` OxCGRT (202.760 filas país-día). Vistas `v_nacional_acum` (anti doble conteo; `granularidad` actúa como testigo), `v_nacional_dia` (nuevos por país) y `vl_chile_regiones`. Población de referencia constante por país.
- **R2 Calidad — completo.** Reglas ejecutables 6 dimensiones (5 ok / 10 warn / 1 fail). **2022-05-23: 2.496 retrocesos, 1.097.163 casos retirados** (CHL −9.827; CHL 2020-06-17 +36.179; 2020-07-17 +1.057; 2022-03-21 +11.447). **3 días chilenos de corrección y el global 2022-05-23 excluidos de medias móviles y modelos; conservados y marcados en el DW.** Índice por país (peor: USA 34,0, COL 64,1, PER 65,8). Detalle: `docs/diccionario_datos.md`, `reports/calidad_*.json/csv`.
- **R3 — completo.** OLAP sobre el DW (roll-up/drill-down/slice/dice) en `reports/olap_consultas.txt`. **OWID vacunación cruzada por ISO3: 201/218 países de `v_nacional_acum` (92,2 %)**; Kosovo no cruza automáticamente porque OWID usa `OWID_KOS`. **OxCGRT también está integrado:** 202.760 filas país-día, 185 países de origen, 2020-01-01 a 2022-12-31; cruzan 182/218 países JHU (83,5 %; Kosovo RKS→XKS). Análisis descriptivo y límites en `reports/hallazgos_restricciones.md` (no causal). Chile y EE.UU., Perú y Brasil: cobertura OWID completa al cierre 90,3 % (CHL), 84,3 % (PER), 69,5 % (USA), 81,8 % (BRA).
- **R4 Análisis (P1–P6) — completo** (`src/analisis_p1_p6.py` → `reports/hallazgos_p1_p6.md` + 8 figuras): Chile 2.º en Sudamérica (**27.162 casos/100k**; **336,2 fallecidos/100k**, tras Perú 665,8); 5 olas (2020-06-17; 2021-04-14; **2022-02-13 ómicron 35.656/día**; 2022-06-17; 2022-11-10); letal mundial-junio = 310 fall./día MA7 el 2020-07-23; **Biobío 10/16 regiones (310/100k)**; CFR Chile 2,54 % → 0,92 % post-vacunación (advert. testeo); peor calidad: USA 34,0.
- **R5 Minería y predicción — completo** (`src/modelos.py`): KMeans k=3 (sil. 0,325; Chile en el grupo 0); pronóstico sin fuga de datos (2 modelos; backtesting 3 cortes; Holt MAPE 17,2 / 23,7 / 25,7 %); **alerta temprana evaluada en Chile: 5/5 olas detectadas con 39–100 días de anticipación (mediana 48); 1 falsa alarma estricta (2020-07-26); ómicron detectada 94 días antes (2021-11-11)**.
- **R6 Protección y ética — completo.** Análisis Ley 19.628/21.719 en informe técnico §15; datos agregados no personales per se, re-identificables en celdas pequeñas → **supresión 1–4** aplicada en el tablero (317 condados USA <5.000 hab.); advertencias visibles.
- **R7 Tablero — completo.** Streamlit (`dashboard/app.py`): KPIs por 100.000, MA7, ranking con «<5», mapa mundial y regional de Chile, alerta con umbral, fecha de corte y advertencias; **«Desafío en vivo»** ejecuta `pronosticar(territorio, fecha_corte, 14)` y muestra el estado de la alerta a la fecha sorteada; capturas en `dashboard/capturas/` (verificado en navegador, sin errores).
- **R8 Informes — completos.** `docs/informe_tecnico.pdf` (14 pp) y `docs/informe_comite.pdf` (2 pp, sin código; 3 recomendaciones con indicador y responsable); `contribuciones.md` con declaración de uso de IA. **Pendiente del equipo: completar nombres.**
- La P7 quedó adoptada: vacunación vs mortalidad a 8 semanas (CHL/PER/USA/BRA; asociación ecológica; 50 % umbral: CHL 2,33→1,25; PER 6,84→0,84; USA 2,40→1,81; BRA 3,12→0,62 fall./100k/sem).
- **Extra OxCGRT — integrado y analizado** (`src/analisis_restricciones.py`): índice de respuesta política «de jure» frente a casos JHU para Chile, Perú, EE.UU. y Brasil; salida `reports/hallazgos_restricciones.md` + figura. Asociación descriptiva, no causal; OxCGRT cierra 68 días antes que JHU.
- `requirements.txt`: pandas, pyarrow, duckdb, statsmodels, scikit-learn, matplotlib, plotly, streamlit, jupyterlab, ydata-profiling. `.venv` validado en Windows.
- La carpeta aún no está conectada a un remoto GitHub; no asumir remoto ni publicar/commit sin autorización.

### Pendiente inmediato (quién continúe)

1. **Ensayo con el ayudante (18-nov):** todos filtran el tablero, explican la alerta y ejecutan el pronóstico a una fecha sorteada; practicar las respuestas del Comité (perfilado, calidad, DW, fuga de datos).
2. **Completar nombres** en `contribuciones.md`; verificar que todos puedan explicar cada parte (el Comité pregunta a cualquiera).
3. **Git/GitHub:** inicializar y subir (requiere autorización); incluir `data/clean` y `data/dw` en el ZIP o hacer que el README los regenere (documentado).
4. Confirmar en EVA los ajustes finales de la entrega (ZIP) y subir a más tardar el 25-nov 23:59.

## Fuentes de datos

- **Repositorio principal de GitHub (Johns Hopkins CSSE):** [CSSEGISandData/COVID-19](https://github.com/CSSEGISandData/COVID-19). Los reportes diarios se obtienen desde [`csse_covid_19_daily_reports/`](https://github.com/CSSEGISandData/COVID-19/tree/master/csse_covid_19_data/csse_covid_19_daily_reports); las series históricas, desde [`csse_covid_19_time_series/`](https://github.com/CSSEGISandData/COVID-19/tree/master/csse_covid_19_data/csse_covid_19_time_series); y la tabla de territorios, desde [`UID_ISO_FIPS_LookUp_Table.csv`](https://github.com/CSSEGISandData/COVID-19/blob/master/csse_covid_19_data/UID_ISO_FIPS_LookUp_Table.csv).
- **Descarga automatizada:** usar las URL `raw.githubusercontent.com` del mismo repositorio para bajar los archivos sin clonar todo el historial. El ejemplo de las diapositivas usa la ruta `https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_daily_reports/` y nombres `MM-DD-YYYY.csv`.
- **Errores encontrados y corregidos (verificación 11-nov):** `any_value()` de DuckDB en `dim_territorio` era **no determinista** (elegía una fila u otra según el plan de ejecución): dos reconstrucciones del mismo código daban países distintos (210 vs 208 en `v_nacional_acum`) y dejaban a **Francia con doble conteo** (sumaba su fila nacional más 11 filas subnacionales: 39,6 M en vez de 38,6 M). Corregido con `first(... ORDER BY ...)` y regla explícita (fila de nivel `pais` > fila con match UID > orden alfabético). Verificado que **dos reconstrucciones dan el mismo hash** (idempotente) y regenerados todos los artefactos derivados (DW, calidad, OLAP, P1–P6, P7, OxCGRT, informes y notebooks) con las cifras corregidas: 218 países, OWID 201/218 (92,2 %), OxCGRT 182/218 (83,5 %), silueta 0,325.
- **Fuentes externas — estado:** **OWID vacunación** (`iso_code` = ISO3): **201/218 países de `v_nacional_acum` cruzan (92,2 %)**. No cruzan directamente: ATA, BLM, ERI, FSM, GLP, GUF, GUM, MAF, MHL, MTQ, MYT, PLW, PRI, PRK, REU, VAT y XKS; Kosovo se excluye del cruce automático (OWID lo publica como `OWID_KOS`). **Oxford OxCGRT** ya está integrado (182/218 países JHU cruzan, 83,5 %; Kosovo RKS→XKS) y se analiza en `src/analisis_restricciones.py`. Banco Mundial (demografía/PIB) sigue como extra opcional.

## Ruta de trabajo e hitos

| Cuándo | Fase y resultado verificable | Criterio de salida |
|---|---|---|
| **4 nov** | Arranque: crear repositorio, README inicial, `.gitignore`, asignar responsables y elegir una fuente externa y una pregunta P7. Probar la descarga de enero de 2020. | El equipo puede descargar y leer un reporte; los crudos no se suben a Git. |
| **Hasta 10 nov — Hito 1** | `00_exploracion.ipynb`: inspección de `01-22-2020.csv`, nulos, nombres estandarizados, consolidación ene-jun 2020, top 10 al 30-jun, serie de Chile y perfilado con tres observaciones. Escribir la propuesta P7. | Notebook ejecutable de principio a fin y P7 vinculada a una fuente externa. |
| **11 nov** | Preparación individual del Test 3 (DW, BI y arquitectura en la nube). | Cada integrante puede explicar el modelo estrella y las decisiones técnicas del equipo. |
| **Hasta 17 nov — Hito 2: plataforma** | Descarga automatizada de los 1.143 reportes, unificación de esquemas, capa limpia Parquet, reglas iniciales de calidad, integración externa y DW estrella consultable. | Una ejecución reproducible produce datos limpios y tablas analíticas con controles básicos. |
| **Hasta 18 nov — Hito 3: análisis y ensayo** | P1–P6 avanzadas, P7 resuelta, modelos y alertas con backtesting, tablero v1 y ensayo con el ayudante. | Se pueden responder preguntas con el tablero y ejecutar el desafío sin datos posteriores al corte. |
| **24 nov — Comité** | Presentación de 15 minutos: relato (7), desafío en vivo (4), preguntas (4). | Cualquier integrante puede filtrar el tablero, explicar la alerta y ejecutar un pronóstico a 14 días. |
| **25 nov, 23:59 — entrega final** | Repositorio reproducible y ZIP en EVA, con informes, diccionario, tablero y contribuciones. | README permite regenerar resultados desde cero; entregables completos y revisados. |

**Atención al calendario:** el PDF presenta hitos con fechas anteriores; las diapositivas de la sesión del **4 de noviembre** actualizan el Hito 1 al **10 nov**, el Hito 2 al **17 nov** y el Hito 3 al **18 nov**. Confirmar cualquier ajuste final en EVA.

- **Guía de lectura rápida:** `docs/guia_proyecto.md` resume qué es el proyecto, qué se hizo en el Hito 1 (tarea por tarea) y qué sigue (pendientes con fecha y responsable).
- **Notebooks del proyecto** (`notebooks/`): `Hito 1.ipynb` (exploración de ene–jun 2020), `Hito 2.ipynb` (plataforma: ingesta, identidad territorial, DW, calidad, fuentes externas y OLAP), `Hito 3.ipynb` (P1–P7, modelos, alerta, P7, OxCGRT y desafío en vivo) y `proyecto completo.ipynb` (los tres hitos juntos, 60 celdas). Los cuatro están **en español, con tablas y gráficos rotulados en español, ejecutados de principio a fin sin errores** y con una tabla de verificación por hito (Hito 2: 8/8 OK; Hito 3: 11/11 OK).
**Estado de hitos (4-nov):** Hito 1 ✔ · Hito 2 ✔ (adelantado al 4-nov) · Hito 3 ✔ salvo ensayo (18-nov) · Comité 24-nov · entrega 25-nov.

## Secuencia técnica

Los ocho pasos se ejecutaron con el README como guía; se conservan como documentación del proceso (resultados en «Avance actual»).

1. **Acordar decisiones y alcance.** Usar fuentes externas con llave ISO3 (OWID para vacunación/P7 y OxCGRT para respuesta política descriptiva). Elegir una herramienta de tablero y un motor analítico —DuckDB es una opción sencilla para consultar Parquet—; documentar por qué. Definir desde el inicio cómo se tratarán territorios especiales y nombres no homologables.
2. **Explorar una muestra pequeña.** Completar el notebook de Hito 1 y anotar problemas de esquema, fechas, nulos, granularidad y acumulados. No iniciar los análisis finales sobre esta muestra.
3. **Implementar ingesta reproducible.** Descargar los CSV por URL raw, sin clonar el historial completo. Conservarlos en `data/raw/` ignorada por Git. En cada fila guardar `fecha_reporte` (del nombre del archivo) y `esquema`; normalizar los cinco esquemas con un diccionario de nombres y conservar nulos donde una columna aún no existía.
4. **Limpiar y medir calidad.** Calcular casos y fallecidos nuevos por territorio y fecha usando diferencias de acumulados. Marcar —no borrar ni convertir silenciosamente a cero— las revisiones negativas. Detectar faltantes, rezagos/picos, duplicados, fallecidos mayores que casos y discrepancias con las series. Crear reglas con umbral, estado, índice por país y decisión documentada (corregir, marcar o excluir), más el diccionario de datos.
5. **Construir el DW e integrar las fuentes.** Declarar el grano territorio-día. Crear una tabla de hechos con acumulados y nuevos diarios y dimensiones de fecha y territorio, incluyendo jerarquía, población y coordenadas. Cruzar OWID y OxCGRT por ISO3; reportar cobertura y límites de cada fuente. Resolver consultas OLAP sobre el DW, no directamente sobre los CSV.
6. **Responder P1–P7 y validar modelos.** Usar tasas por 100.000 y media móvil de 7 días para tendencias. Para R5, entregar segmentación interpretada, al menos dos pronósticos (uno base), evaluación en tres cortes con MAE y MAPE, y alerta evaluada en la historia de Chile (anticipación y falsas alarmas). `pronosticar(territorio, fecha_corte, horizonte=14)` y `alerta(territorio, fecha)` solo pueden usar datos disponibles hasta la fecha consultada.
7. **Cerrar ética y tablero.** Aplicar supresión a conteos pequeños (1–4) donde corresponda; explicar límites de letalidad y comparaciones internacionales. El tablero debe tener KPI, tendencia, ranking, filtros por fecha/territorio, mapas mundial y de Chile, alerta con umbral, fecha de corte y advertencias de calidad.
8. **Comunicar, reproducir y ensayar.** Redactar tres recomendaciones concretas apoyadas por resultados, idealmente con indicador y responsable. Ejecutar README desde un entorno limpio, probar un territorio/fecha de corte sorteables, revisar el ZIP y practicar respuestas técnicas con todo el equipo.

## Responsables sugeridos

En equipos de 3, combinar comunicación con análisis y tablero con modelos; en equipos de 4, asignar un responsable principal por frente. Frentes: **ingesta/DW**, **calidad y gobierno**, **análisis/modelos**, **tablero/informe y presentación**. Cada componente debe tener una persona revisora; todas las personas deben poder explicar el flujo completo porque las preguntas del Comité pueden dirigirse a cualquiera.

## Estructura mínima de entrega — estado

```text
README.md                 ✔ probado (Windows; nota Linux/Colab)
notebooks/ o src/         ✔ ingesta, calidad, DW, análisis, minería/predicción, P7
data/                     ✔ clean (Parquet) y DW generados; crudos fuera de Git; ZIP los incluye o regenera
docs/diccionario_datos.md ✔ completo (reglas, decisiones, linaje, cobertura OWID)
docs/informe_tecnico.pdf  ✔ 14 páginas (máx. 15)
docs/informe_comite.pdf   ✔ 2 páginas, sin código
dashboard/                ✔ Streamlit (app.py) + capturas/
contribuciones.md         ✔ con declaración de IA; COMPLETAR NOMBRES
```

## Riesgos que conviene controlar desde el principio

- **Acumulados no son casos diarios:** no sumar acumulados ni usarlos para medias móviles; obtener nuevos mediante diferencias.
- **Correcciones y rezagos:** conservar y etiquetar retrocesos y picos, explicando su tratamiento.
- **Esquemas y granularidad:** los nombres cambian cinco veces; Chile pasa de fila nacional a regiones desde fines de mayo de 2020. No mezclar niveles geográficos como si fueran equivalentes.
- **Fecha equivocada:** `fecha_reporte` viene del archivo; `last_update` es cuándo se actualizó la fila.
- **Fuga de información:** probar pronóstico y alerta con fechas de corte; cualquier variable posterior invalida la evaluación y el desafío en vivo.
- **Falta de reproducibilidad:** crudos fuera de Git, descargas automatizadas y README con instrucciones numeradas probadas desde cero.
- **Trabajo concentrado en una persona:** registrar aportes en Git y ensayar para que cualquiera pueda explicar y ejecutar el proyecto.

## Orden de prioridad si el tiempo aprieta

1. ~~Asegurar la ruta reproducible completa: datos → limpieza/calidad → DW.~~ **Hecho (4-nov).**
2. ~~Completar P1–P6, P7, pronóstico sin fuga de datos y alerta evaluada.~~ **Hecho (4-nov).**
3. ~~Terminar tablero funcional y los informes obligatorios.~~ **Hecho (4-nov).**
4. Extras opcionales restantes: Banco Mundial (demografía/PIB), mapa animado/coroplético y despliegue en nube (estimación ya bosquejada ~US$35–50/mes en el informe técnico §3). OxCGRT ya está integrado.
