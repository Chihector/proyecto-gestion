# Proyecto semestral — Sala de crisis COVID-19

Proyecto del curso Gestión de Datos (IN1232C): plataforma reproducible con el registro histórico de COVID-19 de Johns Hopkins, responder qué pasó en Chile y el mundo, evaluar qué se podía anticipar y entregar un tablero con tres recomendaciones para la próxima pandemia.

## Requisitos

- Python 3.10 o superior.
- Git.

## Preparación del entorno (Windows)

Desde la raíz del proyecto, en PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
```

Si la activación está restringida en PowerShell, ejecutar directamente `.\.venv\Scripts\python.exe`.

## Reproducir todo desde cero (< 15 minutos; la descarga domina)

En Linux/Colab el flujo es el mismo con `pip install -r requirements.txt` y `python3 src/...` en lugar de PowerShell. En Windows (PowerShell):

```powershell
# 1. Datos (1.143 reportes + 5 series + UID + OWID + OxCGRT; ~680 MB)
python src\descargar_reportes.py

# 2. Capa limpia Parquet (+ validación y medición; añadir --sin-medicion para omitir el benchmark)
python src\ingesta.py

# 3. Identidad territorial (tabla de correspondencia a la UID)
python src\territorios.py

# 4. DW en estrella (DuckDB) + controles
python src\construir_dw.py

# 5. Reglas de calidad (seis dimensiones) + índice de confiabilidad por país
python src\calidad.py

# 6. Consultas OLAP de verificación (roll-up, drill-down, slice, dice)
python src\consultas_olap.py

# 7. Análisis P1–P6 (cifras + figuras + reports/hallazgos_p1_p6.md)
python src\analisis_p1_p6.py

# 8. P7 — vacunación y mortalidad a 8 semanas (cruce OWID por ISO3)
python src\p7_vacunacion.py

# 9. Extra — restricciones OxCGRT y olas (asociación descriptiva, no causal)
python src\analisis_restricciones.py
```

El descargador obtiene JHU, vacunación OWID y el panel OxCGRT; los archivos existentes se reutilizan. Opciones: `--desde` / `--hasta`, `--destino`, `--omitir-series`, `--omitir-owid`, `--omitir-oxcgrt`. Los fallos se informan al final con URL y motivo, y el proceso termina con código 1 si hubo errores. `data/raw/`, `data/clean/` y `data/dw/` están excluidos de Git.

## Tablero (R7)

```powershell
.venv\Scripts\python.exe -m streamlit run dashboard\app.py
```

→ http://localhost:8501. Filtros por territorio (país del mundo o región de Chile) y fecha de corte; KPIs por 100.000, mapa mundial y regional de Chile, ranking con supresión «<5», alerta temprana con umbral visible, fecha de corte y advertencias de calidad. La pestaña **Desafío en vivo** ejecuta `pronosticar(territorio, fecha_corte, 14)` y muestra el estado de la alerta a la fecha sorteada. Capturas en `dashboard/capturas/`.

## Presentación al Comité (sesión 24-nov)

`PPT_Comite_Sala_de_Crisis.pptx`: relato de 15 diapositivas construido sobre `Plantilla PPT Institucional.pptx`, con las cifras y gráficos reales del proyecto (`reports/`) y capturas del tablero (`dashboard/capturas/`). Las diapositivas son visuales (KPIs, gráficos, mapas) y el relato de 7 minutos está en las **notas del exponente** de cada lámina: cadena de datos, P1–P7, extra OxCGRT, tablero en vivo, desafío con `pronosticar(territorio, fecha_corte, 14)` y tres recomendaciones con indicador y responsable.

Para regenerarla (requiere `python-pptx` y `Pillow`):

```powershell
.\.venv\Scripts\python.exe build_ppt_comite.py
```

> Completar los nombres del equipo en la portada antes de la sesión.

## Estructura

```text
data/raw/                 # Crudos (no versionados; se regeneran)
data/clean/               # Capa limpia Parquet (no versionada)
data/dw/                  # DW generado (no versionado)
notebooks/Hito 1.ipynb          # Hito 1: exploración inicial (copia idéntica: 00_exploracion.ipynb)
notebooks/Hito 2.ipynb          # Hito 2: plataforma reproducible
notebooks/Hito 3.ipynb          # Hito 3: análisis, modelos, alertas y tablero
notebooks/proyecto completo.ipynb # Los tres hitos en un solo notebook (español, ejecutado)
src/descargar_reportes.py # Descarga reproducible
src/ingesta.py            # Unificación de esquemas + Parquet
src/territorios.py        # Identidad territorial (cruce UID / iso3)
src/construir_dw.py       # DW estrella DuckDB + controles + vistas
src/calidad.py            # Reglas ejecutables R2 + índice por país
src/consultas_olap.py     # OLAP de verificación
src/analisis_p1_p6.py     # P1–P6 (cifras y figuras)
src/modelos.py            # R5: pronosticar(), alerta(), backtest
src/p7_vacunacion.py      # P7: OWID × JHU
src/analisis_restricciones.py # Extra: OxCGRT × JHU (asociación descriptiva)
build_ppt_comite.py       # Genera la PPT del Comité desde la plantilla institucional
PPT_Comite_Sala_de_Crisis.pptx # Relato de 15 láminas + notas del exponente
Plantilla PPT Institucional.pptx # Plantilla institucional UCSC
PPT_S14_Proyecto_Sala_de_Crisis.pptx # Diapositivas de la clase de lanzamiento (S14)
PPT_Preguntas_Comités_Sala_de_Crisis.pptx # Preguntas y dinámica de la sesión
dashboard/app.py          # Tablero Streamlit
docs/diccionario_datos.md # Diccionario (R2)
docs/guia_proyecto.md    # Guía del proyecto: qué es, qué se hizo (los 3 hitos) y qué sigue
docs/informe_tecnico.pdf  # Informe técnico (14 pp)
docs/informe_comite.pdf   # Informe al Comité (2 pp, sin código)
reports/hallazgos_restricciones.md # Extra OxCGRT (generado)
contribuciones.md         # Aportes y uso de IA
```

## Fuentes

- Johns Hopkins CSSE (reportes diarios, series de cotejo, tabla UID): <https://github.com/CSSEGISandData/COVID-19>
- Our World in Data — vacunación: <https://github.com/owid/covid-19-data> (`public/data/vaccinations`)
- Oxford COVID-19 Government Response Tracker (OxCGRT): <https://github.com/OxCGRT/covid-policy-dataset>
- Cruce externo por ISO3; 201/218 países de `v_nacional_acum` (92,2 %) presentes en OWID; detalle en `docs/diccionario_datos.md`.
- OxCGRT: 182/218 países de `v_nacional_acum` (83,5 %) cruzan; análisis y límites en `reports/hallazgos_restricciones.md`.

La pregunta P7 del proyecto es: **¿Cómo se relaciona la cobertura de vacunación con la mortalidad reportada en las ocho semanas siguientes en Chile y en Perú, EE.UU. y Brasil?** Asociación ecológica, no causalidad; ver análisis y advertencias en el informe técnico.

## Próximos componentes

El roadmap vigente, el diccionario y las lecciones están en [`ROADMAP.md`](ROADMAP.md) y [`docs/diccionario_datos.md`](docs/diccionario_datos.md). Los informes están entregados en `docs/`; la presentación del relato está en `PPT_Comite_Sala_de_Crisis.pptx`. El ensayo con el ayudante (18-nov) y la sesión del Comité (24-nov) usan el tablero y el desafío en vivo descritos.

## Paquete comprimido de entrega

`Proyecto_Sala_de_Crisis_2026-2.rar` contiene el proyecto listo para entregar: código, notebooks, informes, dashboard, capturas, resultados, **capa limpia Parquet** y la presentación del Comité. Se excluyen deliberadamente `data/raw/` (650 MB de crudos, se descargan con `src/descargar_reportes.py`), `.venv/` y `.git/`. El DW (`data/dw/`) tampoco se incluye: se regenera con el pipeline del README (paso 1 para las fuentes externas y pasos 3–4 para la identidad territorial y el almacén), que es justamente lo que valida la reproducibilidad. Por eso el paquete pesa una fracción del RAR antiguo (`proyecto gestion.rar`, 702 MB).

## Estado y entregas (al 4-nov-2026)

| Componente | Estado |
|---|---|
| R1 Ingesta y arquitectura (3 capas, motor justificado) | ✔ completo |
| R2 Calidad y gobierno (diccionario, reglas, índice por país) | ✔ completo |
| R3 DW en estrella + OWID y OxCGRT | ✔ completo |
| R4 P1–P6 (cifras, gráficos e interpretación) | ✔ completo |
| R5 Minería y predicción (KMeans, pronóstico, alerta evaluada) | ✔ completo |
| R6 Protección y ética (supresión 1–4; leyes 19.628/21.719) | ✔ completo |
| R7 Tablero (mapa mundial y de Chile, alerta, «Desafío en vivo») | ✔ completo |
| R8 Informes (técnico 14 pp · Comité 2 pp) y `contribuciones.md` | ✔ completo (nombres pendientes) |
| Notebooks (`Hito 1`, `Hito 2`, `Hito 3` y `proyecto completo`) | ✔ completos, en español y ejecutados sin errores |
| Presentación del Comité (15 láminas + notas, plantilla UCSC) | ✔ completa (nombres en portada pendientes) |
| `Proyecto_Sala_de_Crisis_2026-2.rar` (entrega ligera, sin crudos) | ✔ generado |

Detalle de avance, hitos y pendientes: [`ROADMAP.md`](ROADMAP.md). Errores encontrados y corregidos durante la construcción (bug de `pais_iso3` que excluía las series nacionales, artefacto chileno del 2020-06-17, inferencia de país por moda): documentados en `ROADMAP.md` y `docs/diccionario_datos.md`.

## Equipo y contribuciones

Ver [`contribuciones.md`](contribuciones.md). Completar los nombres antes de la entrega final.
