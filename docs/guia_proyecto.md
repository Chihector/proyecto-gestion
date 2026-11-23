# Guía del proyecto — Sala de crisis COVID-19

> Documento de guía para el equipo: **qué es este proyecto**, **qué se ha hecho en cada hito** y **qué debería seguir**.
> Cubre los **tres hitos** (exploración, plataforma y análisis). El notebook que lo demuestra todo en un solo lugar es
> Los **cuatro notebooks** de `notebooks/` cubren los tres hitos: `Hito 1.ipynb`, `Hito 2.ipynb`, `Hito 3.ipynb` y **`proyecto completo.ipynb`** (los tres hitos juntos, 60 celdas). Todos están en español y ejecutados de principio a fin sin errores.
> Fuentes: `README.md`, `ROADMAP.md`, `docs/diccionario_datos.md`, `contribuciones.md`, `notebooks/Hito 1.ipynb`.

---

## 1. ¿Qué es exactamente este proyecto?

**En una frase:** un proyecto semestral del curso *Gestión de Datos (IN1232C)* que simula una **sala de crisis**: ante el registro histórico de COVID-19 de Johns Hopkins CSSE hay que responder **qué pasó** en Chile y en el mundo, **qué se podía anticipar** y **qué habría que hacer** en la próxima pandemia.

**No es un análisis suelto:** el entregable es una **plataforma reproducible** (datos → limpieza → almacén → análisis → tablero) más informes y defensa oral. La nota se reparte **70 % entregable + 30 % sesión del Comité**.

### 1.1 Fuentes de datos (todo se descarga por código, nada a mano)

| Fuente | Contenido | Rol en el proyecto |
|---|---|---|
| **Johns Hopkins CSSE** | 1.143 reportes diarios `MM-DD-YYYY.csv` (22-ene-2020 → 9-mar-2023), 5 series de cotejo, tabla de territorios UID | Fuente principal |
| **Our World in Data** | Vacunación (196.246 filas) | **Fuente externa** para la pregunta P7; cruza por `iso_code` = ISO3 (201/218 países, 92,2 %) |
| **Oxford OxCGRT** | Respuesta política «de jure», 202.760 filas país-día | Fuente externa extra (asociación descriptiva); cruza 182/218 países (83,5 %) |

### 1.2 Las tres capas (esto es lo que hace que sea "reproducible")

```text
data/raw/    651 MB  crudo tal cual, NO versionado; se regenera con src/descargar_reportes.py
data/clean/  111 MB  capa limpia Parquet: daily_reports.parquet (4.287.473 filas x 17 cols)
data/dw/     212 MB  almacén en estrella DuckDB: covid.duckdb
```

El **DW en estrella** declara su grano (territorio × día):

- `dim_fecha` — 1.143 fechas (2020-01-22 → 2023-03-09)
- `dim_territorio` — 4.284 territorios canónicos (99,95 % empatan con la UID)
- `fact_covid` — **4.287.374** hechos (acumulados y nuevos diarios)
- `vacunacion` (OWID) y `restricciones` (OxCGRT) — dimensiones de integración
- Vistas: `v_nacional_acum` (anti doble conteo), `v_nacional_dia` (nuevos por país), `vl_chile_regiones`

### 1.3 Los ocho requisitos del enunciado (R1–R8) y su estado

| Requisito | Qué exige | Estado al 4-nov-2026 |
|---|---|---|
| **R1** Ingesta y arquitectura | Descarga automatizada, 3 capas, motor justificado | ✔ completo |
| **R2** Calidad y gobierno | Diccionario, reglas ejecutables (6 dimensiones), índice por país | ✔ completo |
| **R3** DW en estrella + fuentes externas | Modelo estrella consultable, cruces por ISO3, OLAP | ✔ completo |
| **R4** Análisis histórico P1–P6 | Cifras, gráficos e interpretación | ✔ completo |
| **R5** Minería y predicción | KMeans, pronóstico sin fuga de datos, alerta evaluada | ✔ completo |
| **R6** Protección y ética | Ley 19.628 / 21.719, supresión de conteos pequeños (1–4) | ✔ completo |
| **R7** Tablero | KPIs, mapas, alerta con umbral, filtros, «Desafío en vivo» | ✔ completo |
| **R8** Informes | Informe técnico (≤15 pp) + informe al Comité (≤2 pp) | ✔ completos, **faltan nombres** |

### 1.4 Calendario vigente

| Cuándo | Hito | Estado |
|---|---|---|
| 4-nov | Arranque, fuente externa y pregunta P7 elegidas | ✔ |
| **10-nov** | **Hito 1 — exploración inicial** | ✔ (este documento) |
| 11-nov | Preparación individual del Test 3 (DW, BI, arquitectura en la nube) | pendiente |
| 17-nov | Hito 2 — plataforma (ingesta, calidad, DW, fuentes externas) | ✔ adelantado |
| 18-nov | Hito 3 — análisis, modelos, tablero v1 y **ensayo con el ayudante** | ✔ salvo ensayo |
| 24-nov | **Sesión del Comité** (relato 7 min + desafío en vivo 4 min + preguntas 4 min) | pendiente |
| 25-nov 23:59 | **Entrega final** en EVA | pendiente |

> Ojo con las fechas: el PDF del enunciado tiene hitos con fechas anteriores; las diapositivas de la sesión del 4-nov actualizaron Hito 1 → 10 nov, Hito 2 → 17 nov, Hito 3 → 18 nov. Confirmar cualquier ajuste final en EVA.

---

## 2. ¿Qué es el Hito 1 y para qué sirve?

El Hito 1 es **el punto de partida, no el proyecto**. Su objetivo es *explorar una muestra pequeña con rigor antes de construir nada* y dejar documentados los problemas de esquema, fechas, nulos, granularidad y acumulados que condicionan todo lo demás.

**Criterio de salida del enunciado:** notebook ejecutable de principio a fin **+** propuesta de la pregunta P7 vinculada a una fuente externa.

> **Trampa conceptual muy frecuente:** el Hito 1 usa **ene–jun 2020** (161 reportes) y el proyecto completo usa los **1.143 reportes** hasta marzo de 2023. El Hito 1 no se "agranda" después: su valor es **fijar las reglas** (fecha desde el nombre del archivo, nulos ≠ ceros, regla anti doble conteo) que después se implementan en `src/`.

---

## 3. Qué se hizo exactamente en el Hito 1 (tarea por tarea)

**Notebook:** `Proyecto/notebooks/Hito 1.ipynb` (copia idéntica en `notebooks/00_exploracion.ipynb`, que es el nombre que pide el enunciado).
**Además:** `notebooks/00_proyecto_completo.ipynb` recorre los **tres hitos** (exploración, plataforma y análisis) en un solo notebook, con tablas y gráficos rotulados en español.
**Estado:** ejecutado de punta a punta **sin errores** (`jupyter nbconvert --execute` → exit 0, sin outputs de error), 15 celdas (9 markdown + 6 código).

| # | Tarea del enunciado | Dónde está en el notebook | Resultado |
|---|---|---|---|
| 1 | Preparar los datos del período | Celda de preparación | **161 reportes** disponibles (22-ene → 30-jun-2020) |
| 2 | Inspeccionar `01-22-2020.csv` | «1. Inspección del primer reporte» | **76 filas × 6 columnas**, tipos y nulos por columna |
| 3 | Explicar los nulos | Markdown «¿Cómo interpretar los nulos del primer día?» | Nulo geográfico ≠ dato perdido; nulo de conteo ≠ 0 |
| 4 | Estandarizar nombres y fecha | «2. Estandarización y consolidación enero – junio» | `snake_case`, `last_update` → `AAAA-MM-DD`, `report_date` desde el nombre del archivo |
| 5 | Consolidar el período | Misma celda | **350.945 filas × 15 columnas**, 161 fechas, 4 esquemas |
| 6 | Top 10 al 30-jun + serie de Chile | «3. Top 10 al 30 de junio y evolución de Chile» | EE.UU. 2.653.658 · Chile 279.393 (7.º) + gráfico |
| 7 | Perfilado automático + 3 observaciones | «4. Perfilado automático y tres observaciones» | `reports/perfil_enero_junio_2020.html` + 3 observaciones calculadas |
| 8 | Propuesta P7 | Markdown «Propuesta P7 – fuente externa» | ¿Cómo se relaciona la cobertura de vacunación con la mortalidad reportada en las ocho semanas siguientes en Chile, Perú, EE.UU. y Brasil? → fuente OWID, cruce por ISO3 |

### Los notebooks del proyecto

| Notebook | Qué cubre | Celdas | Estado |
|---|---|---|---|
| `notebooks/Hito 1.ipynb` (idéntico a `00_exploracion.ipynb`) | Exploración de ene–jun 2020: inspección, nulos, estandarización, consolidación, top 10, serie de Chile, perfilado y tres observaciones | 15 | ✔ ejecutado, sin errores |
| `notebooks/Hito 2.ipynb` | Plataforma: estado de las capas, los cinco esquemas de JHU, capa limpia, identidad territorial, modelo estrella, reglas de calidad, cobertura de OWID/OxCGRT y consultas OLAP | 23 | ✔ ejecutado, sin errores (8/8 verificaciones OK) |
| `notebooks/Hito 3.ipynb` | Análisis y modelos: P1–P7, segmentación, pronóstico y backtesting, alerta evaluada, P7 con OWID, OxCGRT y el desafío en vivo | 29 | ✔ ejecutado, sin errores (11/11 verificaciones OK) |
| `notebooks/proyecto completo.ipynb` | Los tres hitos en un solo documento, con verificación conjunta | 60 | ✔ ejecutado, sin errores (8/8 verificaciones OK) |

> Cada notebook se puede abrir y ejecutar **por separado**: el Hito 2 abre el almacén y el Hito 3 abre el almacén y el índice de calidad por su cuenta, de modo que ninguno depende de haber corrido el anterior.

### 3.1 Las etapas de esquema que deja visibles el consolidado

| Etapa | Reportes | Desde | Hasta |
|---|---|---|---|
| 1 | 39 | 2020-01-22 | 2020-02-29 |
| 2 | 21 | 2020-03-01 | 2020-03-21 |
| 3 | 68 | 2020-03-22 | 2020-05-28 |
| 4 | 33 | 2020-05-29 | 2020-06-30 |

En el proyecto completo son **cinco** etapas: la quinta aparece el **2020-11-09** (fuera del rango del Hito 1) y es la que renombra `Incident_Rate` / `Case_Fatality_Ratio`.

### 3.2 Los hallazgos del Hito 1 (lo que hay que saber explicar)

1. **Acumulados ≠ casos diarios.** `confirmed` es acumulado; los "nuevos" se obtienen por diferencias entre fechas.
2. **La fecha de la observación es el nombre del archivo**, no `Last Update` (que indica cuándo JHU actualizó esa fila).
3. **Cambio de granularidad:** Chile pasa de 1 fila nacional a 17 filas regionales (16 regiones + 1 registro `Unknown`) el **20-may-2020**. No se pueden mezclar niveles geográficos como si fueran equivalentes.
4. **Regla anti doble conteo:** si existe fila nacional se usa esa; si no, se suman las subnacionales. Sin esta regla Chile aparecería duplicado (nacional + regiones).
5. **Los nulos tienen significado:** en el primer reporte, `Deaths` y `Recovered` vienen 48,7 % nulos; `incident_rate` y `case_fatality_ratio` aparecen más tarde (~65 % nulo en el período) y **no se imputan**.
6. **La granularidad de las filas crece con el tiempo:** de 76 filas el primer día a 3.824 filas diarias cerca del corte.

### 3.3 Las tres observaciones que pide el enunciado (ya están calculadas en el notebook)

| Observación | Contenido |
|---|---|
| **1 – Primer reporte** | 76 filas × 6 columnas; nulos destacados en `Province/State` (12), `Confirmed` (10), `Deaths` (37), `Recovered` (37) |
| **2 – Esquema y completitud** | 350.945 filas en 161 días y 4 esquemas; los reportes diarios van de 76 a 3.824 filas |
| **3 – Cambio de granularidad en Chile** | De 1 fila nacional (03-mar-2020) a 17 filas regionales = 16 regiones + 1 `Unknown` (20-may-2020); 279.393 casos acumulados al 30-jun-2020 con la regla anti doble conteo |

---

## 4. Cuatro trampas conceptuales que el Comité suele preguntar

1. **¿Sumaste acumulados?** No. Para obtener casos nuevos hay que diferenciar acumulados consecutivos.
2. **¿De dónde sale la fecha?** Del nombre del archivo. `Last Update` es la fecha de actualización de la fila.
3. **¿Mezclaste granularidades?** No: nacional > subnacional, y la serie chilena respeta el cambio de nivel de mayo.
4. **¿Es causal?** No. P7 (vacunación vs mortalidad) y el análisis OxCGRT son **asociaciones ecológicas descriptivas**, no causalidad.

---

## 5. ¿Qué debería seguir? (en orden y con responsable)

### 5.1 Lo que ya está hecho (no rehacerlo)

- **Hito 2 — plataforma:** descarga de los 1.143 reportes + series + UID + OWID + OxCGRT, capa limpia Parquet, reglas de calidad, DW en estrella y consultas OLAP de verificación.
- **Hito 3 — análisis:** P1–P6 respondidas con número, gráfico e interpretación; P7 resuelta; KMeans, pronóstico sin fuga de datos, alerta evaluada en la historia de Chile (5/5 olas detectadas, mediana 48 días de anticipación); tablero Streamlit con «Desafío en vivo»; informes técnico (14 pp) y de Comité (2 pp).

### 5.2 Los pendientes que bloquean la entrega

| # | Pendiente | Quién | Antes de |
|---|---|---|---|
| 1 | **Ensayo con el ayudante**: todos filtran el tablero, explican la alerta y ejecutan el pronóstico a una fecha sorteada; practicar respuestas del Comité (perfilado, calidad, DW, fuga de datos) | Todo el equipo | 18-nov |
| 2 | **Completar los nombres** de los 4 integrantes en `contribuciones.md` y en los informes | Frontes asignados | 24-nov |
| 3 | **Preparación individual del Test 3**: que cada quien pueda explicar el modelo estrella y las decisiones técnicas (DW, BI, arquitectura en la nube) | Cada integrante | 11-nov |
| 4 | **Git/GitHub**: la carpeta **hoy no tiene remoto**. Inicializar y subir **requiere autorización**; decidir si `data/clean` y `data/dw` van dentro del ZIP o se regeneran con el README (hoy el README las regenera) | Responsable del repo | 24-nov |
| 5 | **Confirmar en EVA** el formato final (ZIP) y subirlo | Responsable de entrega | 25-nov 23:59 |

### 5.3 Opcionales si sobra tiempo

- Banco Mundial (demografía / PIB) como tercera fuente externa.
- Mapa animado o coroplético adicional en el tablero.
- Despliegue en la nube (estimación ya bosquejada: **~US$35–50/mes**, informe técnico §3).

### 5.4 Regla del curso que hay que respetar

> Todos deben poder **explicar y ejecutar** cualquier parte (el Comité puede preguntar a cualquiera) y todos revisan el trabajo de todos. Por eso el ensayo del 18-nov no es opcional: cada integrante tiene que poder filtrar el tablero, explicar la alerta y ejecutar el pronóstico a 14 días.

---

## 6. Cómo reproducir el Hito 1 (o el proyecto entero)

```powershell
# Hito 1: ejecutar el notebook completo (tarda ~1 min con los datos ya descargados)
.\.venv\Scripts\python.exe -m jupyter nbconvert --to notebook --execute --inplace "notebooks\Hito 1.ipynb"

# Proyecto completo, en orden (desde la raíz de Proyecto\)
.\.venv\Scripts\python.exe src\descargar_reportes.py     # 1.143 reportes + series + UID + OWID + OxCGRT
.\.venv\Scripts\python.exe src\ingesta.py                 # 2. capa limpia Parquet + validación
.\.venv\Scripts\python.exe src\territorios.py             # 3. identidad territorial (UID / iso3)
.\.venv\Scripts\python.exe src\construir_dw.py             # 4. DW estrella DuckDB + controles
.\.venv\Scripts\python.exe src\calidad.py                 # 5. reglas de calidad (6 dimensiones)
.\.venv\Scripts\python.exe src\consultas_olap.py          # 6. consultas OLAP de verificación
.\.venv\Scripts\python.exe src\analisis_p1_p6.py          # 7. análisis P1–P6
.\.venv\Scripts\python.exe src\p7_vacunacion.py           # 8. P7 (OWID x JHU)
.\.venv\Scripts\python.exe src\analisis_restricciones.py  # 9. extra OxCGRT
.\.venv\Scripts\python.exe -m streamlit run dashboard\app.py   # tablero -> http://localhost:8501
```

---

## 7. Mapa de archivos: dónde está cada cosa

```text
notebooks/Hito 1.ipynb          # Hito 1 ejecutado (copia idéntica: 00_exploracion.ipynb)
notebooks/Hito 2.ipynb          # Hito 2: plataforma reproducible (en español)
notebooks/Hito 3.ipynb          # Hito 3: análisis, modelos, alertas y tablero (en español)
notebooks/proyecto completo.ipynb # Los tres hitos en un solo notebook (en español)
src/descargar_reportes.py       # descarga reproducible (JHU + OWID + OxCGRT)
src/ingesta.py                  # unificación de esquemas -> Parquet
src/territorios.py              # identidad territorial (UID / iso3)
src/construir_dw.py             # DW en estrella DuckDB + vistas
src/calidad.py                  # reglas R2 + índice de confiabilidad por país
src/consultas_olap.py           # OLAP (roll-up, drill-down, slice, dice)
src/analisis_p1_p6.py           # P1–P6 -> reports/hallazgos_p1_p6.md + figuras
src/modelos.py                  # R5: KMeans, pronosticar(), alerta(), backtest
src/p7_vacunacion.py            # P7: vacunación OWID x mortalidad JHU
src/analisis_restricciones.py   # extra OxCGRT x JHU
dashboard/app.py                # tablero Streamlit (+ capturas/)
docs/diccionario_datos.md       # diccionario, reglas, linaje, cobertura OWID
docs/informe_tecnico.pdf        # informe técnico (14 pp)
docs/informe_comite.pdf         # informe al Comité (2 pp, sin código)
docs/guia_proyecto.md           # ESTE documento
reports/perfil_enero_junio_2020.html  # perfilado del Hito 1
reports/hallazgos_*.md          # hallazgos de análisis
ROADMAP.md                      # avance, hitos, riesgos
contribuciones.md               # aportes del equipo (FALTAN NOMBRES)
```

---

## 8. Checklist de preparación: preguntas que seguro hará el Comité sobre el Hito 1

- [ ] ¿Por qué la fecha de observación sale del **nombre del archivo** y no de `Last Update`?
- [ ] ¿Qué pasa al concatenar un **esquema nuevo**? pandas crea la columna y deja `NaN` donde aún no existía.
- [ ] ¿Cómo evitaste **contar dos veces Chile** (fila nacional + 16 regiones)?
- [ ] ¿Qué es un **acumulado** y cómo se obtienen los casos nuevos? (diferencias)
- [ ] ¿Qué dijo el **perfilado automático** y cuáles son las tres observaciones?
- [ ] ¿Cuál es la **pregunta P7**, con qué fuente externa y por qué **no es causal**?
- [ ] ¿Por qué los nulos **no se rellenan con cero**?
- [ ] ¿Qué pasa con la granularidad después del 20-may-2020 y cómo se comparan Chile y los demás países?

---

*Documento generado el 10-nov-2026 a partir del estado real del repositorio. Si el README o el ROADMAP cambian, actualizar esta guía.*
