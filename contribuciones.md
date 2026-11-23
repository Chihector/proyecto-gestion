# contribuciones.md — Sala de crisis COVID-19

**Proyecto:** Proyecto semestral IN1232C · Gestión de Datos · 2026-2
**Fecha:** 4-nov-2026 (entrega final: 25-nov-2026, 23:59)

## 1. Equipo y reparto de frentes

| Integrante | Rol principal | Revisado por |
|---|---|---|
| (Nombre 1) — **PENDIENTE** | Ingesta y DW (`src/descargar_reportes.py`, `src/ingesta.py`, `src/territorios.py`, `src/construir_dw.py`, `src/calidad.py`) | (Nombre 2) |
| (Nombre 2) — **PENDIENTE** | Calidad y gobierno (`docs/diccionario_datos.md`, `reports/calidad_*.json/csv`, reglas R2, índice por país) | (Nombre 1) |
| (Nombre 3) — **PENDIENTE** | Análisis y modelos (`src/analisis_p1_p6.py`, `src/modelos.py`, `src/p7_vacunacion.py`, backtesting, alerta) | (Nombre 4) |
| (Nombre 4) — **PENDIENTE** | Tablero e informes (`dashboard/app.py`, capturas, `docs/informe_tecnico.pdf`, `docs/informe_comite.pdf`, este archivo) | (Nombre 3) |

> Completar los nombres antes de la entrega. Regla del curso: **todos** deben poder explicar y ejecutar cualquier parte (el Comité pregunta a cualquiera); todos revisan el trabajo de todos.

## 2. Aportes por entregable

- **R1 Ingesta y arquitectura:** descarga reproducible (1.143 reportes + 5 series + tabla UID + OWID + OxCGRT; reutiliza lo descargado; errores explícitos y código de salida 1); capa limpia Parquet (109 MB vs 587 MB CSV; lectura 8,2× más rápida); DW DuckDB en estrella con grano declarado territorio×día; motor justificado en el informe técnico; equivalente en la nube con estimación de costo en el informe.
- **R2 Calidad y gobierno:** diccionario de datos completo; reglas ejecutables en las seis dimensiones (5 ok / 10 warn / 1 fail); problemas cuantificados (44.587 retrocesos; 2022-05-23: 1.097.163 casos retirados; 7 acumulados negativos); índice de calidad por país; decisiones corregir/marcar/excluir documentadas; **linaje** archivo→fila→fila→DW→tablero.
- **R3 DW e integración:** modelo estrella (dim_fecha 1.143 · dim_territorio 4.284 · fact_covid 4.287.374); OLAP (roll-up, drill-down, slice, dice) sobre el DW; OWID vacunación cruza **201/218 países (92,2 %)** y OxCGRT **182/218 (83,5 %)** por ISO3; coberturas y códigos sin cruce documentados en el diccionario.
- **R4 Análisis histórico:** P1–P6 respondidas con número, gráfico e interpretación (`reports/hallazgos_p1_p6.md`; figuras `reports/fig_*.png`); tasas por 100.000; medias móviles 7 días; hallazgos no evidentes (p. ej. la forma de las curvas es globalmente homogénea — todas convergen en ómicron).
- **Análisis extra OxCGRT:** respuesta política «de jure» frente a olas en Chile, Perú, EE.UU. y Brasil (`src/analisis_restricciones.py` → `reports/hallazgos_restricciones.md` y figura); asociación descriptiva, no causal.
- **R5 Minería y predicción:** segmentación KMeans (k=3, silueta 0,325; Chile en el grupo 0); `pronosticar(territorio, fecha_corte, horizonte=14)` con 2 modelos y backtesting en 3 cortes (MAE/MAPE); `alerta(territorio, fecha)` evaluada en la historia de Chile: **5/5 olas detectadas (39–100 días; mediana 48); 1 falsa alarma estricta**; fuga de datos descartada por diseño (todo usa solo datos ≤ corte).
- **R6 Protección y ética:** Ley 19.628 y Ley 21.719 (análisis en informe técnico §15); supresión de conteos 1–4 aplicada en el tablero (317 condados de EE.UU. con <5.000 hab.); advertencias de letalidad aparente y de comparación internacional visibles.
- **R7 Tablero:** Streamlit (`dashboard/app.py`); KPIs, tendencia MA7, ranking con supresión, mapa georreferenciado mundial y regional de Chile, alerta con umbral visible, fecha de corte y advertencias; pestaña «Desafío en vivo» que ejecuta el pronóstico y el estado de la alerta a la fecha sorteada; capturas en `dashboard/capturas/`.
- **R8 Informe al Comité:** `docs/informe_comite.pdf` (2 páginas; 3 recomendaciones con evidencia, indicador y responsable).

## 3. Uso de IA generativa (declaración)

El equipo utilizó **OpenCode con un modelo de IA generativa (Pulse Alpha Free)** como copiloto de ingeniería y redacción. Uso concreto y verificación asociada:

- Generación y revisión de código de ingesta, DW, calidad, modelos y tablero; **todo el código fue ejecutado y sus salidas verificadas contra los datos** (p. ej., un error de construcción de `pais_iso3` que excluía las filas nacionales fue detectado por control de cobertura y corregido; otro en la inferencia de país Francia→BLM se halló por inspección de casos y se reemplazó por mapa explícito).
- Redacción de documentación técnica y de los informes a partir de los números generados por el pipeline; **ninguna cifra fue tecleada a mano**: todas salen de consultas ejecutadas y de los informes de validación.
- Verificación del tablero en navegador headless (carga, pestañas, sin errores de consola).
- Formulación y corrección de la metodología de evaluación de la alerta (protocolo explícito: búsqueda ≤100 días antes del pico; falsa alarma = sin alza ≥40 % en 42 días).

Responsabilidad final: **el equipo es responsable de todo lo entregado**. Lo que no podamos explicar en la sesión del Comité se considera no realizado. No se compartió ningún dato personal ni credencial con herramientas externas; las fuentes son públicas.

## 4. Declaraciones

- Los datos crudos (`data/raw/`) y el DW generado (`data/dw/`) **no se versionan**; se regeneran con los comandos del README.
- Las verificaciones de reproducibilidad se hicieron desde un entorno limpio (`.venv`) en Windows; tiempo total < 15 minutos (la descarga domina).
- Las capturas del tablero corresponden a la versión final del código en este repositorio.
