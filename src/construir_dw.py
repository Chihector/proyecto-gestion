"""Construye el DW en estrella (DuckDB) a partir de la capa limpia.

Modelo (grano: territorio canónico × día):

    dim_fecha       fecha (PK), año, mes, nombre_mes, trimestre, semana_iso,
                    día_semana, es_fin_de_semana
    dim_territorio  territorio_id (PK), territorio_key, nivel (pais /
                    region_estado / condado / especial), iso3, iso2,
                    pais_iso3 (país lógico para agregados), uid, población,
                    lat, long, claves_fusionadas (cuántas claves crudas
                    enrutaron a este territorio), match_uid
    fact_covid      territorio_id, fecha, confirmed/deaths/recovered/active
                    (acumulados), new_confirmed/new_deaths/new_recovered
                    (diferencias por primer reporte: NULL), retroceso_confirmed
                    / retroceso_deaths (baja del acumulado: se MARCA, no se
                    borra ni se convierte en 0), incident_rate,
                    case_fatality_ratio, etapa_esquema, clave_raw (linaje:
                    con fecha identifica archivo y fila de origen)
    vacunacion      iso3, fecha, métricas de vacunación OWID (`OWID_*` =
                    agregados regionales/mundiales, excluir de cruces por país)
    restricciones   respuesta de política OxCGRT (país-día 2020-01-01 a
                    2022-12-31): índices stringency/containment y medidas
                    C/H seleccionadas; Kosovo RKS→XKS homologado al cargar

Territorio canónico: las claves empatadas a la misma UID se fusionan
(`Taiwan` y `Taiwan*` quedan en una sola serie). Las `sin_match` conservan su
propia clave. Los países reales quedan con grano de país; Chile desde
2020-05-20 aparece por sus 16 regiones + `Unknown` (nivel region_estado).

Misma fecha, misma UID: en días de transición de nombre JHU publicó dos
filas del mismo territorio (`Aruba` y `Aruba, Netherlands`). El DW exige una
fila por territorio×día, así que se conserva la de mayor acumulado y se
cueta el total de filas fusionadas en el informe de controles.

Vistas:

    v_nacional_acum  agregado por país lógico y día; si existen filas de
                     nivel país para ese día se usan ELLAS (no se suman las
                     subnacionales: doble conteo); si no, se suma lo
                     subnacional. Columna `granularidad` indica cuál.
    v_nacional_dia   v_nacional_acum + new_confirmed/new_deaths por país.
    vl_chile_regiones  detalle por región de Chile (pais_iso3 = 'CHL').

Uso:  python src/construir_dw.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

PARQUET = Path("data/clean/daily_reports.parquet")
TERRITORIOS = Path("data/clean/territorios.parquet")
OWID = Path("data/raw/owid_vaccinations.csv")
OXCGRT = Path("data/raw/oxcgrt_restricciones.csv")
DW = Path("data/dw/covid.duckdb")


def crear_esquema(con: duckdb.DuckDBPyConnection, parquet: Path, territorios: Path) -> None:
    con.execute("""
        CREATE OR REPLACE TABLE dim_territorio AS
        WITH r AS (
            SELECT DISTINCT
                CASE WHEN match_uid THEN clave_uid_resuelta ELSE clave_raw END AS territorio_key,
                clave_raw, nivel, iso3, iso2, pais_iso3, uid, population, lat, long, match_uid
            FROM read_parquet(?)
        )
        SELECT
            row_number() OVER (ORDER BY territorio_key) AS territorio_id,
            territorio_key,
            -- Regla DETERMINISTA de desempate. `any_value()` es no determinista
            -- en DuckDB: con claves fusionadas (p. ej. 'Saint Barthelemy, France'
            -- y 'Saint Barthelemy') elegia una fila u otra segun el plan de
            -- ejecucion, y dos builds del mismo codigo daban paises distintos
            -- (210 vs 208 en v_nacional_acum). Aqui se ordena de forma explicita:
            -- 1) la fila de nivel 'pais' (el territorio como pais en si mismo),
            -- 2) la fila que hizo match con la UID,
            -- 3) orden alfabetico de clave_raw como ultimo desempate.
            first(nivel      ORDER BY (CASE WHEN nivel = 'pais' THEN 0 ELSE 1 END),
                                        (CASE WHEN match_uid THEN 0 ELSE 1 END), clave_raw) AS nivel,
            first(iso3       ORDER BY (CASE WHEN nivel = 'pais' THEN 0 ELSE 1 END),
                                        (CASE WHEN match_uid THEN 0 ELSE 1 END), clave_raw) AS iso3,
            first(iso2       ORDER BY (CASE WHEN nivel = 'pais' THEN 0 ELSE 1 END),
                                        (CASE WHEN match_uid THEN 0 ELSE 1 END), clave_raw) AS iso2,
            first(pais_iso3  ORDER BY (CASE WHEN nivel = 'pais' THEN 0 ELSE 1 END),
                                        (CASE WHEN match_uid THEN 0 ELSE 1 END), clave_raw) AS pais_iso3,
            first(uid        ORDER BY (CASE WHEN nivel = 'pais' THEN 0 ELSE 1 END),
                                        (CASE WHEN match_uid THEN 0 ELSE 1 END), clave_raw) AS uid,
            first(population ORDER BY (CASE WHEN nivel = 'pais' THEN 0 ELSE 1 END),
                                        (CASE WHEN match_uid THEN 0 ELSE 1 END), clave_raw) AS population,
            first(lat        ORDER BY (CASE WHEN nivel = 'pais' THEN 0 ELSE 1 END),
                                        (CASE WHEN match_uid THEN 0 ELSE 1 END), clave_raw) AS lat,
            first(long       ORDER BY (CASE WHEN nivel = 'pais' THEN 0 ELSE 1 END),
                                        (CASE WHEN match_uid THEN 0 ELSE 1 END), clave_raw) AS long,
            bool_or(match_uid)    AS match_uid,
            count(*)              AS claves_fusionadas
        FROM r
        GROUP BY territorio_key
        ORDER BY territorio_key
    """, [str(territorios)])

    con.execute("""
        CREATE OR REPLACE TABLE dim_fecha AS
        WITH rango AS (
            SELECT min(report_date) AS ini, max(report_date) AS fin
            FROM read_parquet(?)
        )
        SELECT
            d AS fecha,
            year(d) AS anio,
            month(d) AS mes,
            strftime(d, '%B') AS nombre_mes,
            quarter(d) AS trimestre,
            isodow(d) AS dia_iso,
            strftime(d, '%A') AS dia_semana,
            weekofyear(d) AS semana_iso,
            (isodow(d) IN (6, 7)) AS es_fin_de_semana
        FROM rango, generate_series(ini, fin, INTERVAL 1 DAY) AS t(d)
        ORDER BY d
    """, [str(parquet)])

    # Mapa clave_raw -> territorio_id (recalculado desde el mismo criterio de fusión).
    con.execute("""
        CREATE OR REPLACE TABLE mapa_clave AS
        WITH r AS (
            SELECT clave_raw,
                   CASE WHEN match_uid THEN clave_uid_resuelta ELSE clave_raw END AS territorio_key
            FROM read_parquet(?)
        )
        SELECT DISTINCT r.clave_raw, d.territorio_id
        FROM r JOIN dim_territorio d USING (territorio_key)
    """, [str(territorios)])

    con.execute("""
        CREATE OR REPLACE TABLE fact_covid AS
        WITH marcado AS (
            SELECT
                m.territorio_id,
                r.report_date AS fecha,
                r.confirmed, r.deaths, r.recovered, r.active,
                r.incident_rate, r.case_fatality_ratio,
                r.etapa_esquema,
                r.clave_raw,
                row_number() OVER (
                    PARTITION BY m.territorio_id, r.report_date
                    ORDER BY coalesce(r.confirmed, -1) DESC,
                             coalesce(r.deaths, -1) DESC,
                             r.clave_raw
                ) AS rn
            FROM read_parquet(?) r
            JOIN mapa_clave m USING (clave_raw)
        )
        SELECT
            territorio_id, fecha,
            confirmed, deaths, recovered, active,
            incident_rate, case_fatality_ratio, etapa_esquema, clave_raw,
            confirmed - lag(confirmed) OVER w AS new_confirmed,
            deaths    - lag(deaths)    OVER w AS new_deaths,
            recovered - lag(recovered) OVER w AS new_recovered,
            (confirmed - lag(confirmed) OVER w) < 0 AS retroceso_confirmed,
            (deaths    - lag(deaths)    OVER w) < 0 AS retroceso_deaths
        FROM marcado
        WHERE rn = 1
        WINDOW w AS (PARTITION BY territorio_id ORDER BY fecha)
    """, [str(parquet)])


def crear_vacunacion(con: duckdb.DuckDBPyConnection, owid: Path) -> None:
    con.execute("""
        CREATE OR REPLACE TABLE vacunacion AS
        SELECT
            iso_code AS iso3,
            CAST(date AS DATE) AS fecha,
            location,
            (iso_code LIKE 'OWID%') AS es_agregado,
            total_vaccinations, people_vaccinated, people_fully_vaccinated,
            total_boosters, daily_vaccinations_raw, daily_vaccinations,
            total_vaccinations_per_hundred, people_vaccinated_per_hundred,
            people_fully_vaccinated_per_hundred, total_boosters_per_hundred,
            daily_vaccinations_per_million, daily_people_vaccinated
        FROM read_csv_auto(?, header=true)
    """, [str(owid)])


def crear_restricciones(con: duckdb.DuckDBPyConnection, oxcgrt: Path) -> None:
    """Carga el panel país-día de política de Oxford OxCGRT.

    Kosovo: OxCGRT publica `RKS` y JHU usa `XKS`; se homologa para que el
    cruce por ISO3 funcione. El archivo nacional solo trae la jurisdicción
    `NAT_TOTAL` (se filtra por si acaso). Cobertura: 2020-01-01 a 2022-12-31.
    """
    con.execute("""
        CREATE OR REPLACE TABLE restricciones AS
        SELECT
            CASE WHEN CountryCode = 'RKS' THEN 'XKS' ELSE CountryCode END AS iso3,
            strptime(CAST(Date AS VARCHAR), '%Y%m%d')::DATE AS fecha,
            CountryName AS location,
            StringencyIndex_Average         AS stringency_index,
            GovernmentResponseIndex_Average AS government_response_index,
            ContainmentHealthIndex_Average  AS containment_health_index,
            EconomicSupportIndex            AS economic_support_index,
            "C1M_School closing"                    AS c1_cierre_escuelas,
            "C2M_Workplace closing"                 AS c2_cierre_trabajo,
            "C3M_Cancel public events"              AS c3_eventos,
            "C4M_Restrictions on gatherings"        AS c4_reuniones,
            "C5M_Close public transport"            AS c5_transporte,
            "C6M_Stay at home requirements"         AS c6_quedarse_en_casa,
            "C7M_Restrictions on internal movement" AS c7_movilidad_interna,
            "C8EV_International travel controls"    AS c8_viajes_internacionales,
            "H6M_Facial Coverings"                  AS h6_mascarillas
        FROM read_csv_auto(?, header=true)
        WHERE Jurisdiction = 'NAT_TOTAL'
    """, [str(oxcgrt)])


def crear_vistas(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("""
        CREATE OR REPLACE VIEW v_nacional_acum AS
        WITH ref AS (
            -- Población de referencia constante por país: la nacional si hubo
            -- fila de nivel país; si no, la suma de subnacionales (p. ej. EE.UU.).
            SELECT pais_iso3,
                   coalesce(max(CASE WHEN nivel = 'pais' THEN population END),
                            sum(CASE WHEN nivel <> 'pais' THEN population END)) AS poblacion_ref
            FROM dim_territorio
            WHERE pais_iso3 IS NOT NULL
            GROUP BY 1
        ),
        x AS (
            SELECT t.pais_iso3, f.fecha,
                   sum(CASE WHEN t.nivel = 'pais' THEN f.confirmed END) AS nac_conf,
                   sum(CASE WHEN t.nivel <> 'pais' THEN f.confirmed END) AS sub_conf,
                   sum(CASE WHEN t.nivel = 'pais' THEN f.deaths    END) AS nac_def,
                   sum(CASE WHEN t.nivel <> 'pais' THEN f.deaths    END) AS sub_def,
                   sum(CASE WHEN t.nivel = 'pais' THEN f.recovered  END) AS nac_rec,
                   sum(CASE WHEN t.nivel <> 'pais' THEN f.recovered  END) AS sub_rec
            FROM fact_covid f JOIN dim_territorio t USING (territorio_id)
            WHERE t.pais_iso3 IS NOT NULL
            GROUP BY 1, 2
        )
        SELECT x.pais_iso3, x.fecha,
               coalesce(x.nac_conf, x.sub_conf) AS confirmed,
               coalesce(x.nac_def,  x.sub_def)  AS deaths,
               coalesce(x.nac_rec,  x.sub_rec)  AS recovered,
               r.poblacion_ref                  AS poblacion,
               CASE WHEN x.nac_conf IS NOT NULL THEN 'nacional'
                    ELSE 'subnacional_sumada' END AS granularidad
        FROM x JOIN ref r USING (pais_iso3)
    """)
    con.execute("""
        CREATE OR REPLACE VIEW v_nacional_dia AS
        SELECT pais_iso3, fecha, confirmed, deaths, recovered, poblacion, granularidad,
               confirmed - lag(confirmed) OVER (PARTITION BY pais_iso3 ORDER BY fecha) AS new_confirmed,
               deaths    - lag(deaths)    OVER (PARTITION BY pais_iso3 ORDER BY fecha) AS new_deaths
        FROM v_nacional_acum
    """)
    con.execute("""
        CREATE OR REPLACE VIEW vl_chile_regiones AS
        SELECT t.territorio_key AS region, f.fecha, f.confirmed, f.deaths,
               f.recovered, f.active, f.new_confirmed, f.new_deaths,
               f.retroceso_confirmed, f.retroceso_deaths,
               t.population, t.lat, t.long
        FROM fact_covid f JOIN dim_territorio t USING (territorio_id)
        WHERE t.pais_iso3 = 'CHL' AND t.nivel <> 'pais'
    """)


def controles(con: duckdb.DuckDBPyConnection) -> None:
    print("== Controles del DW ==")
    for nombre in ["dim_fecha", "dim_territorio", "fact_covid", "vacunacion", "restricciones"]:
        n = con.execute(f"SELECT count(*) FROM {nombre}").fetchone()[0]
        print(f"  {nombre:15} {n:>12,} filas")
    r_paises = con.execute("SELECT count(DISTINCT iso3) FROM restricciones").fetchone()[0]
    r_cruz = con.execute(
        "SELECT count(DISTINCT r.iso3) FROM restricciones r JOIN "
        "(SELECT DISTINCT pais_iso3 FROM dim_territorio WHERE pais_iso3 IS NOT NULL) t "
        "ON t.pais_iso3 = r.iso3").fetchone()[0]
    print(f"  restricciones: {r_paises} países OxCGRT; {r_cruz} cruzan con el DW")
    dup = con.execute(
        "SELECT count(*) FROM (SELECT territorio_id, fecha FROM fact_covid "
        "GROUP BY 1, 2 HAVING count(*) > 1)").fetchone()[0]
    filas_fact = con.execute("SELECT count(*) FROM fact_covid").fetchone()[0]
    filas_fuente = con.execute(
        "SELECT count(*) FROM read_parquet(?)", [str(PARQUET)]).fetchone()[0]
    fusionadas = filas_fuente - filas_fact
    print(f"  duplicados (territorio, fecha): {dup}"
          f"  ({fusionadas} filas fusionadas por misma fecha/territorio,"
          f" se conserva la de mayor acumulado)")
    huerfanos = con.execute(
        "SELECT count(*) FROM fact_covid f LEFT JOIN dim_fecha d USING (fecha) "
        "WHERE d.fecha IS NULL").fetchone()[0]
    print(f"  duplicados (territorio, fecha): {dup}")
    print(f"  fechas sin dim_fecha:           {huerfanos}")
    retro_c = con.execute("SELECT count(*) FROM fact_covid WHERE retroceso_confirmed").fetchone()[0]
    retro_d = con.execute("SELECT count(*) FROM fact_covid WHERE retroceso_deaths").fetchone()[0]
    terr_retro = con.execute(
        "SELECT count(DISTINCT territorio_id) FROM fact_covid "
        "WHERE retroceso_confirmed OR retroceso_deaths").fetchone()[0]
    print(f"  retrocesos de acumulado: confirmed={retro_c}, deaths={retro_d} "
          f"(en {terr_retro} territorios)")
    rango = con.execute("SELECT min(fecha), max(fecha) FROM fact_covid").fetchone()
    print(f"  rango fechas: {rango[0]} a {rango[1]}")
    print("\n  Ejemplo nacional (Chile, últimas 3 filas):")
    print(con.execute(
        "SELECT * FROM v_nacional_dia WHERE pais_iso3='CHL' ORDER BY fecha DESC LIMIT 3"
    ).df().to_string(index=False))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parquet", type=Path, default=PARQUET)
    parser.add_argument("--territorios", type=Path, default=TERRITORIOS)
    parser.add_argument("--owid", type=Path, default=OWID)
    parser.add_argument("--oxcgrt", type=Path, default=OXCGRT)
    parser.add_argument("--dw", type=Path, default=DW)
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for ruta in (args.parquet, args.territorios, args.owid, args.oxcgrt):
        if not ruta.exists():
            print(f"Falta el insumo: {ruta}", file=sys.stderr)
            return 1

    args.dw.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(args.dw))
    crear_esquema(con, args.parquet, args.territorios)
    crear_vacunacion(con, args.owid)
    crear_restricciones(con, args.oxcgrt)
    crear_vistas(con)
    controles(con)
    con.execute("CHECKPOINT")
    con.close()
    print(f"\nDW escrito en {args.dw}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
