# Diccionario de datos — Sala de crisis COVID-19

**Fecha de actualización:** 4-nov-2026 · **Alcance:** tabla unificada (capa limpia Parquet y DW en estrella, DuckDB) · **Fuentes:** Johns Hopkins CSSE (reportes diarios, series de cotejo, tabla UID), Our World in Data (vacunación) y Oxford OxCGRT (respuesta de política).

Convención de fechas: `fecha`/`report_date` = fecha del **archivo** (`MM-DD-YYYY.csv`), nunca `last_update` (momento en que JHU actualizó la fila, conservado solo como referencia).

## 1. Tabla unificada (`fact_covid` en el DW; `data/clean/daily_reports.parquet` en la capa limpia)

| Columna | Tipo | Significado y dominio | Origen / desde | Nulos |
|---|---|---|---|---|
| `territorio_id` | int64 | Clave sustituta del DW → `dim_territorio` | Derivada (DW) | 0 |
| `fecha` (Parquet: `report_date`) | date | Fecha del reporte (nombre del archivo) | JHU daily_reports · 2020-01-22→2023-03-09 | 0 |
| `confirmed` | Int64 | Casos confirmados **acumulados** (≥ 0 se espera; 7 filas crudas violan) | Todas las etapas | 28 (0,001 %) |
| `deaths` | Int64 | Fallecidos acumulados | Todas las etapas | 433 (0,01 %) |
| `recovered` | Int64 | Recuperados acumulados; **JHU dejó de publicar desde 2021-03** (66 % nulos) | Todas las etapas; completos 2020-03→2021-02 | 2.828.440 (66,0 %) |
| `active` | Int64 | Activos (metodología JHU; no reconcilia con confirmed−deaths−recovered: 3,92 % difiere ±1) | Etapas 3–5 (83 % nulos desde 2021-10) | 2.837.775 (66,2 %) |
| `incident_rate` | double | Incidencia por 100.000 hab. (denominador JHU; no confundir con tasas propias) | Etapas 4–5 (≤2,3 % nulos); etapas 1–3: 100 % nulo | 318.751 (7,4 %) |
| `case_fatality_ratio` | double | Fallecidos ÷ casos (%) aparente; ver advertencias de R6 | Etapas 4–5 (≤1,5 % nulos); etapas 1–3: 100 % nulo | 273.981 (6,4 %) |
| `fips` | string(5) | FIPS de EE.UU. con ceros a la izquierda; `NA` fuera de EE.UU. | Etapas 3–5; etapas 1–2 no existía | 786.985 (18,4 %) |
| `admin2` | string | Condado/municipio (nivel condado) | Etapas 3–5 | ~18,4 % |
| `province_state` | string | Estado/región/provincia (grano Chile y China, Australia, Canadá, RU…) | Todas las etapas (nivel país: nulo) | ver etapa |
| `country_region` | string | País o entidad que publica la fila | Todas las etapas; ver §4 nombres | 0 |
| `lat`, `long` | double | Coordenadas del territorio (tabla UID cuando aplica) | Etapas 2–5 (etapa 1: 76 filas sin coord.; 3,0 % nulos) | 98.602 (2,3 %) |
| `combined_key` | string | Clave original JHU `provincia, país` / `admin2, provincia, país` | Etapas 3–5 | etapa 1–2 |
| `clave_raw` | string | Clave canónica local (misma convención; usada para linaje y cruce con territorios) | Derivada; identifica **archivo y fila** junto con `fecha` | 0 |
| `last_update` | timestamp(UTC) | Actualización de la fila según JHU (NO usar como fecha de observación) | Todas las etapas | 0 |
| `etapa_esquema` | string | Esquema detectado por columnas crudas: `etapa_1`…`etapa_5` (`etapa_desconocida` nunca apareció) | Derivada | 0 |
| `new_confirmed`, `new_deaths`, `new_recovered` | Int64 | Diferencia del acumulado vs día anterior del mismo territorio; **primer reporte = NULL** (no se inventa 0); negativo = corrección (marcado) | Derivada (DW) | 1 por territorio |
| `retroceso_confirmed`, `retroceso_deaths` | bool | La fila **baja** del acumulado (corrección JHU). Se conserva y se MARCA; nunca se borra ni se convierte en 0 | Derivada (DW) | 0 |
| `fips`/`admin2`/`province_state` nulos en nivel país | — | Un país sin provincia/condado es un registro nacional, no un dato perdido | — | — |

**Granularidad:** territorio canónico × día. Un "territorio canónico" = claves que enrutan a la misma fila de la tabla UID (p. ej. `Taiwan` + `Taiwan*` = una serie). 4.410 claves crudas → 4.284 territorios canónicos (126 fusionadas).

**Población de referencia por país:** la fila de nivel país si existe (Chile 19.116.209); si el país siempre reportó subnacional (EE.UU., Argentina, Perú…), la **suma de subnacionales** (EE.UU. ≈ 329,5 M). `v_nacional_*` expone `poblacion` constante por país.

**Consolidación de duplicados:** 99 pares mismo territorio+fecha (JHU publicó dos grafías el mismo día en transiciones de nombre) fusionados conservando la fila de **mayor acumulado**. Nunca se suman.

## 2. Dimensiones del DW

### `dim_fecha` — 1.143 filas (2020-01-22 → 2023-03-09)
`fecha (PK)` · `anio` · `mes` · `nombre_mes` · `trimestre` · `dia_iso` (1=lunes) · `dia_semana` · `semana_iso` · `es_fin_de_semana`.

### `dim_territorio` — 4.284 filas
| Columna | Significado |
|---|---|
| `territorio_id` | PK sustituta (orden alfabético de `territorio_key`) |
| `territorio_key` | Clave UID resuelta (p. ej. `Taiwan*`, `Metropolitana, Chile`) |
| `nivel` | `pais` (204) · `region_estado` (752; incluye regiones de Chile y provincias de China) · `condado` (3.311, EE.UU.) · `especial` (17: barcos, eventos, repatriados) |
| `iso3`, `iso2` | Códigos ISO; `iso3` es `NULL` en seis entidades especiales sin país y en `Channel Islands` (sin correspondencia UID) |
| `pais_iso3` | País lógico para agregados (p. ej. `CHL` para las 16 regiones; `USA` para condados) |
| `uid` | UID de la tabla JHU; NULL en `sin_match` |
| `population` | Población JHU (2019/2020); 265 territorios sin población (barcos/especiales y algunos) |
| `lat`, `long` | Coordenadas |
| `match_uid` | `true` si empató con la UID (99,95 % de las filas del hecho) |
| `claves_fusionadas` | Cuántas claves crudas enrutaron aquí (>1 = fusión por alias/errata) |

### `vacunacion` (OWID) — 196.246 filas · cruce por `iso3` = `iso_code`
`iso3` · `fecha` · `location` · `es_agregado` (`OWID_*`: agregados regionales/mundiales — **excluir** de cruces por país) · métricas: `total_vaccinations`, `people_vaccinated`, `people_fully_vaccinated`, `total_boosters`, `daily_vaccinations_raw/daily_vaccinations`, y sus ratios `*_per_hundred` / `per_million`.

**Cobertura del cruce (países JHU↔OWID):** 201/218 países (92,2 %), calculado con los ISO3 distintos de `v_nacional_acum` y los `iso_code` distintos de OWID excluyendo agregados (`OWID_*`). No cruzan directamente: `ATA`, `BLM`, `ERI`, `FSM`, `GLP`, `GUF`, `GUM`, `MAF`, `MHL`, `MTQ`, `MYT`, `PLW`, `PRI`, `PRK`, `REU`, `VAT`, `XKS`. OWID publica Kosovo como `OWID_KOS`; no se fuerza ese mapeo. Los territorios-región (p. ej. regiones de Chile) no tienen serie nacional en OWID: el cruce es a nivel país.

> **Nota de reproducibilidad (verificación del 11-nov):** la atribución de `pais_iso3` a cada territorio se resuelve con `first(... ORDER BY ...)`, no con `any_value()`, porque `any_value()` de DuckDB es **no determinista**: dos reconstrucciones del mismo código elegían filas distintas y producían países diferentes (210 vs 208) y un doble conteo en Francia (39,6 M en vez de su fila nacional, 38,6 M). La regla vigente es: **1)** fila de nivel `pais` (el territorio como país en sí mismo), **2)** fila que hizo match con la UID, **3)** orden alfabético de `clave_raw` como último desempate. Con ella, reconstruir el DW dos veces produce el mismo hash.

### `restricciones` (Oxford OxCGRT) — 202.760 filas país-día
`iso3` · `fecha` · `location` · índices `stringency_index`, `government_response_index`, `containment_health_index`, `economic_support_index` y medidas C1–C8/H6. Se filtra la jurisdicción nacional `NAT_TOTAL`; Kosovo se homologa de `RKS` a `XKS`. Cobertura observada: 185 países, 2020-01-01 a 2022-12-31.

**Cobertura del cruce (países JHU↔OxCGRT):** 182/218 países de `v_nacional_acum` (83,5 %). Hay 36 países JHU sin panel y tres códigos OxCGRT sin país JHU correspondiente (BMU, TKM, VIR). El panel termina 68 días antes del cierre JHU. El análisis (`src/analisis_restricciones.py` → `reports/hallazgos_restricciones.md`) describe asociaciones; no demuestra causalidad y el índice mide políticas anunciadas, no cumplimiento.

## 3. Vistas

- **`v_nacional_acum`** — agregado por `pais_iso3` y fecha. **Regla anti doble conteo:** si el día tiene filas de nivel país, se usan ELLAS; si no, se suma lo subnacional. `granularidad` indica cuál.
- **`v_nacional_dia`** — `v_nacional_acum` + `new_confirmed` / `new_deaths` (lag por país). Chile solo agrega como subnacional desde 2020-05-20.
- **`vl_chile_regiones`** — detalle por región (16 regiones + `Unknown, Chile`).

## 4. Identidad territorial y nombres

Alias explícitos (ver `src/territorios.py`, comentados uno a uno): erratas JHU (`Australian Capneital…`, `Fench Guiana…`, `Doña Ana`→`Dona Ana` por normalización sin tildes), fusiones/renombrados censales de EE.UU. (Yakutat, Lake and Peninsula, Southwest Utah), y territorios listados en la UID bajo su país (Hong Kong→China, Macao→China, Aruba→Países Bajos, Puerto Rico→EE.UU., Guam→EE.UU.…). `Taiwan` (etapas 1–2) y `Taiwan*` (etapas 3–5) son **una** serie.

`' Azerbaijan'` (espacio inicial) y `'Taiwan*'` se normalizan al comparar; nunca se borran del crudo.

**Casos no empatados (169 territorios, 0,05 % de filas):** ciudades/condados de EE.UU. y Canadá de los primeros reportes (p. ej. `Los Angeles, CA, US`), `New York City…` (agregado), `Repatriated Travellers, Canada`, barcos. Se conservan con `match_uid=false`, `iso3` inferido del componente país, sin población/coordenadas.

**Entidades especiales (nivel `especial`, 17):** embarcaciones, pasajeros evacuados/repatriados y eventos como Diamond Princess, MS Zaandam y los Juegos Olímpicos. No son países; no entran en comparaciones entre países ni en tasas por 100.000. `Channel Islands` es una fila separada de nivel `pais`, pero sin ISO3 ni país lógico.

## 5. Reglas de calidad (R2) — estado al 4-nov-2026

Seis dimensiones en `src/calidad.py` (`python src/calidad.py`); detalle completo en `reports/calidad_reglas.json`.

**Resultado global:** 5 ok · 10 warn · 1 fail (`acumulados_negativos`, 7 filas del origen).

Hallazgos relevantes:

1. **2022-05-23 — corrección global masiva:** 2.496 retrocesos en un día; **1.097.163 casos retirados** (USA −241.915, BRA −47.196, JPN −67.274, CHL −9.827). Se marca y se **excluye de promedios/modelos**.
2. **Filas negativas crudas (7):** `Unknown, Colombia` 2020-11-02 (−302.844, corrección de un día; las regiones saltaban ese día 1.396.100 y el total publicado 1.093.256 — la suma con la fila correctora reproduce la cifra oficial) y `Unassigned` Carolina del Sur/Norte (−3.073/−82; −34/−6). Se conservan y marcan; no participan en diferenciación de nuevos ni en modelos.
2b. **Inserciones administrativas chilenas:** 2020-06-17 (+36.179 casos rezagados en un día; el «ajuste del 17 de junio») y 2020-07-17 (+1.057 fallecidos en un día). Misma clase que Perú 2021-06-02 (artefacto transitorio; la corrección real peruana fue **gradual abr–jul 2021**, ~1.000 fallecidos/día adicionales y Lima restatada) y Colombia 2020-11-02 (total conservado). Se excluyen del ajuste y de las medias móviles; jamás se borran del histórico.
2c. **Chile 2022-03-21 (+11.447 fallecidos):** revisión del registro (sí se sumó al total nacional). Se excluye del numerador de la CFR; se conserva en acumulados. La CFR mensual del subconjunto afectado es 3,47 % con el artefacto → 0,68 % sin él.
2d. **Días de «no actualización» (acumulado sin cambios):** son huecos de reporte, no «0 casos»; se tratan como ausentes en medias móviles y en evaluación de modelos (<20 % de la serie).
3. **`recovered`/`active` discontinuados por JHU (desde 2021-03; ~100 % nulos desde 2021-10)** — no se usan como serie completa.
4. **`deaths > confirmed` (10.777 filas):** patrón real conocido (Reino Unido jun-2020: fallecidos sin casos vinculados; Perú jun-2021: 115.600 fallecidos vs 9.963 casos el 2021-06-02 por la reconciliación oficial de ~70 mil). Se marcan; **no se corrigen**.
5. **`active` no reconcilia** (3,92 % difiere >1 donde `recovered` existe): metodología JHU; sin forzado.
6. **Cotejo series vs reportes:** al 2023-03-09 el total confirmado coincide **exacto** (676.570.149); fallecidos Δ=2. En 2020-06-30 los reportes exceden la serie en +32.807 (+0,31 %, corrección retroactiva) → la serie se usa solo como cotejo.
7. **Picos por rezago:** 166.395 territorio-días superan 3× la mediana previa de 7 días — se muestran anotados, no se suavizan.
8. **`cfr_sobre_100`:** 2.001 filas (letalidad aparente extrema por subtesteo/correcciones) — nunca comparar letalidad entre países sin esta advertencia.
9. **Gaps > 7 días a nivel país:** 4 casos; máx 44 días (p. ej. paso a reporte semanal) — no se interpola.

**Decisiones (corregir / marcar / excluir):**
- **Marcar (no borrar, no imputar):** todos los retrocesos, negativos crudos y `deaths>confirmed`. Imputar es inventar.
- **Excluir de agregados nuevos/modelos:** 2022-05-23; filas negativas.
- **No corregir:** `active`, `cfr` extremos, tasas OWID.
- **Corregido (documentado):** solo normalización de nombres/claves (sin alterar cifras).

**Índice de calidad por país (0–100):** `100 − 30·min(1, retrocesos/días) − 20·min(1, días_gap>7/días) − 20·min(1, eventos_deaths>confirmed/10) − 10·min(1, filas_negativas/5) − 10·min(1, filas_CFR>100/20)`. Peores: **USA 34,0** (54.746 retrocesos, 7.125 `deaths>confirmed`, 1.347 CFR>100 — volumen y correcciones de condados, no "datos malos" sin contexto), COL 64,1 (234 retrocesos; 508 `deaths>confirmed`), PER 65,8, BEL 69,5, PRK 70,0. El índice prioriza revisión; no castiga países con mejor documentación. Los valores se contrastan con `reports/calidad_pais.csv`.

## 6. Linaje

Toda fila del DW queda ligada a **archivo** (`MM-DD-YYYY.csv` ← `fecha`) y a **territorio** (`clave_raw` → fila de `UID_ISO_FIPS_LookUp_Table.csv` cuando `match_uid`). Ejemplo: Colombia 2023-03-09 19:xx ← `03-09-2023.csv`, filas `,Amazonas,Colombia,…` → UID #.

## 7. Fuentes y licencias

- **JHU CSSE COVID-19** (archived, público): reportes/ series/ tabla UID — datos agregados.
- **OWID COVID-19 vaccinations** (público): `public/data/vaccinations/vaccinations.csv`.
- **Oxford OxCGRT** (público): panel nacional de respuesta de política; descargado por `src/descargar_reportes.py` e integrado en `restricciones` al construir el DW.
- JHU dejó de publicar recuperados en 2021-08 (y desde 2021-03 los omitió en la mayoría de filas) — ver hallazgo 3.
- Los CSV crudos **no se versionan** (`.gitignore`); se regeneran con `src/descargar_reportes.py`.
