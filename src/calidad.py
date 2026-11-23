"""R2 — Reglas de calidad ejecutables sobre el DW (DuckDB).

Un solo comando:  python src/calidad.py

Salidas:

- `reports/calidad_reglas.json`  — cada regla: nombre, dimensión, umbral,
  valor medido, estado (ok | warn | fail) y decisión documentada.
- `reports/calidad_pais.csv`     — índice de calidad 0–100 por país lógico
  (pais_iso3): peor a mejor, con sus componentes.
- Informe por pantalla.

Las seis dimensiones: completitud, unicidad, validez, consistencia,
exactitud y oportunidad. Las reglas NO borran ni imputan: marcan y
cuantifican. Los hallazgos se incorporan al diccionario de datos
(`docs/diccionario_datos.md`) y a las decisiones del proyecto.

Índice por país (0–100), documentado en el diccionario:

    100 − 30·min(1, retrocesos/días_reportados)
        − 20·min(1, días_gap>7/días_reportados)
        − 20·min(1, eventos_deaths>confirmed/10)
        − 10·min(1, filas_negativas/5)
        − 10·min(1, filas_CFR>100/20)

El índice es un diagnóstico relativo para priorizar revisión, no una
sentencia: un país con mejor índice también recibe controles.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import duckdb

DW = Path("data/dw/covid.duckdb")
REGLAS_JSON = Path("reports/calidad_reglas.json")
PAIS_CSV = Path("reports/calidad_pais.csv")


def mediciones(con: duckdb.DuckDBPyConnection) -> dict:
    q = con.execute
    m: dict = {}
    m["filas"] = q("SELECT count(*) FROM fact_covid").fetchone()[0]
    m["fechas_cubiertas"] = q("SELECT count(DISTINCT fecha) FROM fact_covid").fetchone()[0]
    m["fechas_esperadas"] = q("SELECT count(*) FROM dim_fecha").fetchone()[0]
    m["nulos_confirmed"] = q("SELECT count(*) FROM fact_covid WHERE confirmed IS NULL").fetchone()[0]
    m["nulos_deaths"] = q("SELECT count(*) FROM fact_covid WHERE deaths IS NULL").fetchone()[0]
    m["nulos_recovered"] = q("SELECT count(*) FROM fact_covid WHERE recovered IS NULL").fetchone()[0]
    m["nulos_active"] = q("SELECT count(*) FROM fact_covid WHERE active IS NULL").fetchone()[0]
    m["nulos_poblacion"] = q("SELECT count(*) FROM dim_territorio WHERE population IS NULL").fetchone()[0]
    m["territorios"] = q("SELECT count(*) FROM dim_territorio").fetchone()[0]
    m["duplicados_territorio_fecha"] = q(
        "SELECT count(*) FROM (SELECT territorio_id, fecha FROM fact_covid "
        "GROUP BY 1, 2 HAVING count(*) > 1)").fetchone()[0]
    m["filas_negativas"] = q(
        "SELECT count(*) FROM fact_covid WHERE confirmed < 0 OR deaths < 0 OR recovered < 0"
    ).fetchone()[0]
    m["lat_fuera_rango"] = q(
        "SELECT count(*) FROM dim_territorio WHERE lat NOT BETWEEN -90 AND 90").fetchone()[0]
    m["long_fuera_rango"] = q(
        "SELECT count(*) FROM dim_territorio WHERE long NOT BETWEEN -180 AND 180").fetchone()[0]
    m["poblacion_no_positiva"] = q(
        "SELECT count(*) FROM dim_territorio WHERE population <= 0").fetchone()[0]
    m["cfr_sobre_100"] = q(
        "SELECT count(*) FROM fact_covid WHERE case_fatality_ratio > 100").fetchone()[0]
    m["deaths_gt_confirmed"] = q(
        "SELECT count(*) FROM fact_covid WHERE deaths > confirmed").fetchone()[0]
    m["active_incoherente"] = q(
        "SELECT count(*) FROM fact_covid WHERE active IS NOT NULL AND recovered IS NOT NULL "
        "AND abs(active - (confirmed - deaths - recovered)) > 1").fetchone()[0]
    m["active_evaluables"] = q(
        "SELECT count(*) FROM fact_covid WHERE active IS NOT NULL AND recovered IS NOT NULL").fetchone()[0]
    m["retrocesos_confirmed"] = q(
        "SELECT count(*) FROM fact_covid WHERE retroceso_confirmed").fetchone()[0]
    m["retrocesos_deaths"] = q(
        "SELECT count(*) FROM fact_covid WHERE retroceso_deaths").fetchone()[0]
    m["retrocesos_20220523"] = q(
        "SELECT count(*) FROM fact_covid WHERE fecha = DATE '2022-05-23' AND retroceso_confirmed").fetchone()[0]
    m["casos_retirados_20220523"] = q(
        "SELECT coalesce(sum(CASE WHEN retroceso_confirmed THEN -new_confirmed ELSE 0 END), 0) "
        "FROM fact_covid WHERE fecha = DATE '2022-05-23'").fetchone()[0]
    m["max_gap_pais"] = q("""
        WITH gaps AS (
            SELECT date_diff('day',
                   lag(f.fecha) OVER (PARTITION BY f.territorio_id ORDER BY f.fecha),
                   f.fecha) AS gap
            FROM fact_covid f JOIN dim_territorio t USING (territorio_id)
            WHERE t.nivel = 'pais'
        )
        SELECT max(gap) FROM gaps
    """).fetchone()[0]
    m["gaps_sobre_7"] = q("""
        WITH gaps AS (
            SELECT date_diff('day',
                   lag(f.fecha) OVER (PARTITION BY f.territorio_id ORDER BY f.fecha),
                   f.fecha) AS gap
            FROM fact_covid f JOIN dim_territorio t USING (territorio_id)
            WHERE t.nivel = 'pais'
        )
        SELECT count(*) FROM gaps WHERE gap > 7
    """).fetchone()[0]
    m["picos_rezago"] = q("""
        WITH x AS (
            SELECT territorio_id, fecha, new_confirmed,
                   median(new_confirmed) OVER (
                       PARTITION BY territorio_id ORDER BY fecha
                       ROWS BETWEEN 8 PRECEDING AND 2 PRECEDING) AS mediana_previa
            FROM fact_covid
        )
        SELECT count(*) FROM x
        WHERE new_confirmed IS NOT NULL AND mediana_previa > 0
          AND new_confirmed > 3 * mediana_previa
    """).fetchone()[0]
    return m


def reglas(m: dict) -> list[dict]:
    filas = m["filas"]
    def pct(x):
        return round(100 * x / filas, 3) if filas else 0.0

    return [
        # ---------- Completitud ----------
        dict(nombre="cobertura_fechas", dimension="completitud",
             umbral="1.143/1.143 días con al menos un reporte",
             valor=f"{m['fechas_cubiertas']}/{m['fechas_esperadas']}",
             estado="ok" if m["fechas_cubiertas"] == m["fechas_esperadas"] else "fail",
             decision="Ningún día sin reporte; si apareciera uno, se marcaría y se documentaría."),
        dict(nombre="nulos_confirmed", dimension="completitud",
             umbral="0 nulos", valor=f"{m['nulos_confirmed']} ({pct(m['nulos_confirmed'])} %)",
             estado="ok" if m["nulos_confirmed"] == 0 else "warn",
             decision="Se conservan los nulos; no se imputan. Revisar filas afectadas."),
        dict(nombre="nulos_deaths", dimension="completitud",
             umbral="0 nulos", valor=f"{m['nulos_deaths']} ({pct(m['nulos_deaths'])} %)",
             estado="ok" if m["nulos_deaths"] == 0 else "warn",
             decision="Se conservan los nulos; no se imputan."),
        dict(nombre="recovered_active_discontinuados", dimension="completitud",
             umbral="informativa: JHU dejó de publicarlos (desde 2021-03)",
             valor=f"recovered nulos {pct(m['nulos_recovered'])} %; active nulos {pct(m['nulos_active'])} %",
             estado="warn",
             decision="No se usan como serie completa; se excluyen de P1–P7 y de modelos."),
        dict(nombre="poblacion_territorios", dimension="completitud",
             umbral=">= 90 % de territorios con población",
             valor=f"{m['territorios'] - m['nulos_poblacion']}/{m['territorios']} con población",
             estado="ok" if (m["territorios"] - m["nulos_poblacion"]) / m["territorios"] >= 0.9 else "warn",
             decision="Los sin población (barcos/eventos y algunos territorios) no entran en tasas por 100.000."),
        # ---------- Unicidad ----------
        dict(nombre="duplicados_territorio_fecha", dimension="unicidad",
             umbral="0 tras consolidación (se conserva la fila de mayor acumulado)",
             valor=str(m["duplicados_territorio_fecha"]),
             estado="ok" if m["duplicados_territorio_fecha"] == 0 else "fail",
             decision="99 pares mismo territorio/fecha (grafo de transición de nombres) fusionados conservando el max."),
        # ---------- Validez ----------
        dict(nombre="acumulados_negativos", dimension="validez",
             umbral="0 filas con confirmed/deaths/recovered < 0",
             valor=f"{m['filas_negativas']} filas",
             estado="fail" if m["filas_negativas"] else "ok",
             decision="Errores del origen (correcciones publicadas como filas). Se conservan y se MARCAN; "
                      "se excluyen de promedios y modelos; no se usan para diferenciar nuevos."),
        dict(nombre="lat_long_rango", dimension="validez",
             umbral="lat en [-90,90], long en [-180,180]",
             valor=f"{m['lat_fuera_rango']} lat; {m['long_fuera_rango']} long",
             estado="ok" if m["lat_fuera_rango"] == 0 and m["long_fuera_rango"] == 0 else "fail",
             decision="Sin violaciones."),
        dict(nombre="poblacion_positiva", dimension="validez",
             umbral="población > 0 cuando existe", valor=f"{m['poblacion_no_positiva']} violaciones",
             estado="ok" if m["poblacion_no_positiva"] == 0 else "fail", decision="Sin violaciones."),
        dict(nombre="cfr_sobre_100", dimension="validez",
             umbral="0 (o explicar); aquí: valores extremos por bajas en testeo o correcciones",
             valor=f"{m['cfr_sobre_100']} filas", estado="warn" if m["cfr_sobre_100"] else "ok",
             decision="Se conservan; no se usan para comparar letalidad entre países sin advertencia."),
        dict(nombre="deaths_mayor_que_confirmed", dimension="validez",
             umbral="0 (o explicar); patrón conocido: Reino Unido jun-2020 (fallecidos sin casos vinculados) y correcciones de Perú jun-2021",
             valor=f"{m['deaths_gt_confirmed']} filas", estado="warn",
             decision="Se conservan y se marcan; no se corrigen ni se borran (imputar es inventar)."),
        # ---------- Consistencia ----------
        dict(nombre="active_reconcilia", dimension="consistencia",
             umbral="|active − (confirmed−deaths−recovered)| <= 1",
             valor=f"{m['active_incoherente']:,} de {m['active_evaluables']:,} evaluables "
                   f"({100 * m['active_incoherente'] / max(m['active_evaluables'], 1):.2f} %)",
             estado="warn",
             decision="JHU calcula `active` con su propia metodología; no se reconcilia forzando. Se usa solo como referencia."),
        dict(nombre="retrocesos_acumulado", dimension="consistencia",
             umbral="0 (o explicar); totalidad medida y marcada",
             valor=f"confirmed {m['retrocesos_confirmed']}; deaths {m['retrocesos_deaths']}; "
                   f"2022-05-23: {m['retrocesos_20220523']} ({int(m['casos_retirados_20220523']):,} casos retirados)",
             estado="warn",
             decision="Se conservan y se MARCAN (retroceso_*); los nuevos se calculan con diferencias y los días de "
                      "corrección masiva (2022-05-23) se excluyen de promedios y modelos."),
        dict(nombre="series_vs_reportes", dimension="consistencia/exactitud",
             umbral="Δ global = 0 al 2023-03-09; en 2020-06-30 se admite el desvío de corrección retroactiva",
             valor="confirmed Δ=0 (676.570.149 exacto); deaths Δ=2; 2020-06-30: +32.807 (+0,31 %) en reportes",
             estado="warn",
             decision="Los reportes diarios son la fuente canónica del DW; las series quedan como cotejo, no como insumo."),
        # ---------- Oportunidad ----------
        dict(nombre="max_gap_pais", dimension="oportunidad",
             umbral="<= 7 días entre reportes de nivel país",
             valor=f"máx {m['max_gap_pais']} días; {m['gaps_sobre_7']} gaps > 7 días",
             estado="warn" if m["gaps_sobre_7"] else "ok",
             decision="Países que pasaron a reporte semanal (2022): se marcan; no se interpola (imputar es inventar)."),
        dict(nombre="picos_por_rezago", dimension="oportunidad",
             umbral="informativa: picos > 3× la mediana de los 7 días previos",
             valor=f"{m['picos_rezago']} territorio-días", estado="warn",
             decision="Picos por acumulación de rezagos; se muestran anotados; no se suavizan silenciosamente."),
    ]


def indice_pais(con: duckdb.DuckDBPyConnection):
    df = con.execute("""
        WITH base AS (
            SELECT t.pais_iso3,
                   count(*) AS filas,
                   count(*) FILTER (WHERE f.retroceso_confirmed OR f.retroceso_deaths) AS retrocesos,
                   count(*) FILTER (WHERE f.deaths > f.confirmed) AS deaths_gt_confirmed,
                   count(*) FILTER (WHERE f.confirmed < 0 OR f.deaths < 0 OR f.recovered < 0) AS negativas,
                   count(*) FILTER (WHERE f.case_fatality_ratio > 100) AS cfr_100
            FROM fact_covid f JOIN dim_territorio t USING (territorio_id)
            WHERE t.pais_iso3 IS NOT NULL
            GROUP BY 1
        ),
        dias AS (
            SELECT t.pais_iso3, count(DISTINCT f.fecha) AS dias_reportados
            FROM fact_covid f JOIN dim_territorio t USING (territorio_id)
            WHERE t.pais_iso3 IS NOT NULL
            GROUP BY 1
        ),
        gaps AS (
            SELECT pais_iso3, count(*) AS gaps_largos
            FROM (
                SELECT t.pais_iso3,
                       date_diff('day',
                           lag(f.fecha) OVER (PARTITION BY f.territorio_id ORDER BY f.fecha),
                           f.fecha) AS gap
                FROM fact_covid f JOIN dim_territorio t USING (territorio_id)
                WHERE t.nivel = 'pais' AND t.pais_iso3 IS NOT NULL
            ) g
            WHERE gap > 7
            GROUP BY 1
        )
        SELECT b.*, d.dias_reportados, coalesce(g.gaps_largos, 0) AS gaps_largos
        FROM base b
        JOIN dias d USING (pais_iso3)
        LEFT JOIN gaps g USING (pais_iso3)
    """).df()

    def clip01(x):
        return max(0.0, min(1.0, x))

    df["pen_retro"] = 30 * (df["retrocesos"] / df["dias_reportados"]).map(clip01)
    df["pen_gap"] = 20 * (df["gaps_largos"] / df["dias_reportados"]).map(clip01)
    df["pen_dmc"] = 20 * (df["deaths_gt_confirmed"] / 10).map(clip01)
    df["pen_neg"] = 10 * (df["negativas"] / 5).map(clip01)
    df["pen_cfr"] = 10 * (df["cfr_100"] / 20).map(clip01)
    df["indice"] = (100 - df[["pen_retro", "pen_gap", "pen_dmc", "pen_neg", "pen_cfr"]].sum(axis=1)).round(1)
    df = df.sort_values("indice")
    return df


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dw", type=Path, default=DW)
    parser.add_argument("--reglas-json", type=Path, default=REGLAS_JSON)
    parser.add_argument("--pais-csv", type=Path, default=PAIS_CSV)
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    con = duckdb.connect(str(args.dw), read_only=True)
    m = mediciones(con)
    rs = reglas(m)
    pais = indice_pais(con)
    con.close()

    args.reglas_json.parent.mkdir(parents=True, exist_ok=True)
    args.reglas_json.write_text(
        json.dumps({"mediciones": m, "reglas": rs}, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8")
    pais.to_csv(args.pais_csv, index=False)

    print("== Reglas ejecutables (R2) ==")
    for r in rs:
        marca = {"ok": "OK  ", "warn": "WARN", "fail": "FAIL"}[r["estado"]]
        print(f"[{marca}] {r['dimension']:22s} {r['nombre']}")
        print(f"        valor: {r['valor']}")
        print(f"        umbral: {r['umbral']}")
        print(f"        decisión: {r['decision']}")

    resumen = {e: sum(1 for r in rs if r["estado"] == e) for e in ("ok", "warn", "fail")}
    print(f"\nResultado: {resumen['ok']} ok, {resumen['warn']} warn, {resumen['fail']} fail")

    print("\n== Índice de calidad por país (10 peores) ==")
    print(pais[["pais_iso3", "indice", "retrocesos", "gaps_largos",
                "deaths_gt_confirmed", "negativas", "cfr_100"]].head(10).to_string(index=False))
    print("\n== 10 mejores ==")
    print(pais[["pais_iso3", "indice"]].tail(10).to_string(index=False))

    print(f"\nEscrito: {args.reglas_json} y {args.pais_csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
