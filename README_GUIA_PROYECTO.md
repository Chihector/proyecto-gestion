# README Guía — Sala de crisis COVID-19 (Gestión de Datos · IN1232C)

Guía rápida: **qué** pide el profesor, **dónde** está cada cosa y **cómo** ejecutarla.

---

## 1. Lo que pide el profe (y dónde está)

### 1.1 Entregables del proyecto (repositorio + .zip en EVA, hasta 25-nov a 23:59)

| Lo que pide el profe | Dónde está |
|---|---|
| `README.md` con pasos reproducibles | `README.md` |
| Ingesta, calidad, DW, análisis, minería y predicción | `src/` (véase 1.3) |
| Notebooks ejecutables: Hito 1, Hito 2, Hito 3, proyecto completo | `notebooks/` |
| Capa limpia y DW: `data/clean/` (Parquet) y `data/dw/` (DuckDB) | `data/` |
| Datos crudos: no se suben al repo; se descargan con el código | `data/raw/` (excluido de Git) |
| `docs/diccionario_datos.md` (diccionario R2) | `docs/diccionario_datos.md` |
| `docs/informe_tecnico.pdf` (≤15 páginas) | `docs/informe_tecnico.pdf` |
| `docs/informe_comite.pdf` (≤2 páginas, sin código) | `docs/informe_comite.pdf` |
| Tablero a elección (Streamlit por defecto) + capturas | `dashboard/app.py`, `dashboard/capturas/` |
| `contribuciones.md`: quién hizo qué + declaración de IA | `contribuciones.md` |
| Roadmap y estado de hitos | `ROADMAP.md`, `docs/guia_proyecto.md` |
| Presentación para la Sesión del Comité | `PPT_Comite_Sala_de_Crisis.pptx` + `build_ppt_comite.py` |

### 1.2 Sesión del Comité (24-nov, 15 min por equipo) — "Rúbrica B"

El profe expone tras 20 minutos y los estudiantes tienen 15 min:

| Bloque | Tiempo | Qué debe mostrar | Dónde está / cómo verificar |
|---|---|---|---|
| Relato y hallazgos | 7 min | P1–P7 respondidas con número, gráfico e interpretación; 3 recomendaciones con indicador y responsable | `reports/hallazgos_p1_p6.md`, `reports/hallazgos_restricciones.md`; `PPT_Comite_Sala_de_Crisis.pptx` (diapositiva "Relato y hallazgos") |
| Demostración del tablero en vivo | 4 min | Filtrar por territorio y fecha, mapa georreferenciado, alerta con umbral visible | Tablero: `dashboard/app.py` → http://localhost:8501 |
| Ejecución de código y prueba de pronóstico | 4 min | Ejecutar `alerta()` y `pronosticar(territorio, fecha_corte, 14)` en vivo y comparar con lo real | `src/modelos.py` (CLI: `python src/modelos.py pronosticar CHL --fecha-corte ...`) |
| Desafío en vivo | (incluido en el relato) | KPIs a la fecha de corte sorteada, alerta estado, ejecutar pronóstico | `PPT_Comite_Sala_de_Crisis.pptx` (diapositiva "Desafío en vivo") |
| Preguntas | 4 min | Preguntas del Comité a cualquier integrante | — |

### 1.3 Componentes R1–R8 → `src/`

| R | Qué pide el profe | Script |
|---|---|---|
| R1 Ingesta y arquitectura | 1.143 reportes, 5 esquemas unificados, 3 capas, motor justificado | `src/descargar_reportes.py`, `src/ingesta.py`, `src/territorios.py`, `src/construir_dw.py` |
| R2 Calidad y gobierno | Diccionario, reglas ejecutables 6 dimensiones, índice por país, decisiones | `src/calidad.py` (salida: `reports/calidad_reglas.json`, `reports/calidad_pais.csv`) |
| R3 DW en estrella + integraciones | Grano territorio×día, OLAP, OWID y OxCGRT por ISO3 | `src/construir_dw.py`, `src/consultas_olap.py` → `reports/olap_consultas.txt` |
| R4 Análisis histórico | P1–P6 con números, gráficos, interpretación | `src/analisis_p1_p6.py` → `reports/hallazgos_p1_p6.md`, figuras `reports/fig_*.png` |
| R5 Minería y predicción | Segmentación, pronóstico sin fuga de datos, alerta evaluada | `src/modelos.py`, `src/analisis_p1_p6.py` (P5) |
| R6 Protección y ética | Ley 19.628 / 21.719, supresión 1–4 | (ver en informes) |
| R7 Tablero | KPI, mapas, alerta visible, supresión <5 | `dashboard/app.py` |
| R8 Informe al Comité | ≤2 páginas, sin código, 3 recomendaciones con indicador | `docs/informe_comite.pdf` |

---

## 2. Cómo ejecutar todo

### 2.1 Entorno (Windows PowerShell)

```powershell
# En la raíz del proyecto
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
```

Si PowerShell está restringido, abrir directamente con:
`.\.venv\Scripts\python.exe -c "..."`

### 2.2 Pipeline reproducible (README: sección "Reproducir todo desde cero", menos de 15 min)

Ejecutar en PowerShell, desde `C:\Users\hecto\OneDrive\Escritorio\u\gestion de datos\Proyecto`:

```powershell
python src\descargar_reportes.py      # 1. Datos: 1.143 reportes + OWID + OxCGRT
python src\ingesta.py                 # 2. Unificación de esquemas → data\clean\daily_reports.parquet
python src\territorios.py             # 3. Identidad territorial → data\clean\territorios.parquet
python src\construir_dw.py            # 4. DW estrella DuckDB → data\dw\covid.duckdb
python src\calidad.py                 # 5. Reglas R2 + índice por país
python src\consultas_olap.py          # 6. Consultas OLAP de verificación
python src\analisis_p1_p6.py          # 7. P1–P6 → reports\hallazgos_p1_p6.md
python src\p7_vacunacion.py           # 8. P7: OWID × JHU → reports\fig_p7_vacunacion.png
python src\analisis_restricciones.py  # 9. Extra OxCGRT (asociación descriptiva)
```

OJO: `python` aparece como `py` en Windows; usar `py src\descargar_reportes.py` si `python` no existe.

### 2.3 Tablero en vivo (R7)

```powershell
.\.venv\Scripts\python.exe -m streamlit run dashboard\app.py
```

→ http://localhost:8501

Filtros: "Territorio" (país del mundo o región de Chile) y "Fecha de corte"; KPIs por 100.000; mapa mundial y regional de Chile; alerta con umbral visible; supresión «<5».

### 2.4 Prueba de pronóstico y alerta en vivo

```powershell
# Pronóstico: Chile, fecha de corte antes de la ola de ómicron (tipo que usa el Comité)
.\.venv\Scripts\python.exe src\modelos.py pronosticar CHL --fecha-corte 2021-12-01 --horizonte 14

# Alerta temporal:
.\.venv\Scripts\python.exe src\modelos.py alerta CHL --fecha-corte 2021-12-01

# Backtesting (cortes y métricas MAE/MAPE):
.\.venv\Scripts\python.exe src\modelos.py backtest CHL --cortes 2020-09-15,2021-03-15,2021-12-01
```

Usa solo datos ≤ fecha de corte: no hay fuga de datos.

### 2.5 Presentación para el Comité

```powershell
.\.venv\Scripts\python.exe build_ppt_comite.py
```

Regenera `PPT_Comite_Sala_de_Crisis.pptx` desde `Plantilla PPT Institucional.pptx`, con datos reales de `reports/` y capturas de `dashboard/capturas/`.

---

## 3. Calendario vigente (para no atrasarse)

| Cuándo | Hito | Por qué: |
|---|---|---|
| 10-nov | Hito 1 — notebook `notebooks\00_exploracion.ipynb` + P7 propuesta | Antes de la sesión del Comité |
| 17-nov | Hito 2 — ingesta y DW con fuentes externas | Compromiso del enunciado |
| 18-nov | Hito 3 — P1–P6, pronóstico sin fuga, tablero v1 | Antes del Comité |
| 24-nov | Sesión del Comité (15 min/equipo, desafío en vivo) | Entregable Rúbrica B (30%) |
| 25-nov 23:59 | Entrega final: repositorio + `.rar` en EVA | `Proyecto_Sala_de_Crisis_2026-2.rar` (excluye crudos, incluye `data/clean/`) |

---

## 4. Referencias rápidas

- Diccionario de datos: `docs/diccionario_datos.md`
- Hallazgos P1–P6: `reports/hallazgos_p1_p6.md`
- Hallazgos restricciones: `reports/hallazgos_restricciones.md`
- Informe técnico (14 páginas): `docs/informe_tecnico.pdf`
- Informe al Comité (2 páginas): `docs/informe_comite.pdf`
- Tablero: http://localhost:8501
- Presentación del Comité: `PPT_Comite_Sala_de_Crisis.pptx`

Guarde esta guía: `README_GUIA_PROYECTO.md`.
