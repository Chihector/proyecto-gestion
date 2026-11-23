"""R3 — Consultas OLAP de demostración sobre el DW (DuckDB).

Ejemplo de las operaciones del curso: roll-up, drill-down, slice y dice,
además de dos KPI comparativos. NO son los análisis finales (esos viven en
los notebooks y el tablero); son la prueba de que el DW soporta el trabajo
analítico.

    python src/consultas_olap.py

Salida por pantalla y, además, en `reports/olap_consultas.txt`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

DW = Path("data/dw/covid.duckdb")
SALIDA = Path("reports/olap_consultas.txt")

CONSULTAS = [
    ("ROLL-UP — mundo por año (casos y fallecidos nuevos)",
     """
     SELECT year(f.fecha) AS anio,
            sum(f.new_confirmed) FILTER (WHERE f.new_confirmed >= 0) AS nuevos_casos,
            sum(f.new_deaths)    FILTER (WHERE f.new_deaths >= 0)    AS nuevos_fallecidos
     FROM fact_covid f
     GROUP BY 1 ORDER BY 1
     """),

    ("ROLL-UP — Chile por año (nacional)",
     """
     SELECT year(fecha) AS anio,
            sum(new_confirmed) FILTER (WHERE new_confirmed >= 0) AS nuevos_casos,
            sum(new_deaths)    FILTER (WHERE new_deaths >= 0)    AS nuevos_fallecidos
     FROM v_nacional_dia
     WHERE pais_iso3 = 'CHL'
     GROUP BY 1 ORDER BY 1
     """),

    ("DRILL-DOWN — Chile 2021 por región (incidencia por 100.000 y fallecidos por 100.000)",
     """
     SELECT t.territorio_key AS region,
            sum(f.new_confirmed) FILTER (WHERE f.new_confirmed >= 0)              AS nuevos_casos,
            sum(f.new_deaths)    FILTER (WHERE f.new_deaths >= 0)                 AS nuevos_fallecidos,
            round(1e5 * sum(f.new_confirmed) FILTER (WHERE f.new_confirmed >= 0)
                  / any_value(t.population), 1)                                    AS casos_por_100k,
            round(1e5 * sum(f.new_deaths)    FILTER (WHERE f.new_deaths >= 0)
                  / any_value(t.population), 1)                                    AS fallecidos_por_100k
     FROM fact_covid f JOIN dim_territorio t USING (territorio_id)
     WHERE t.pais_iso3 = 'CHL' AND t.nivel <> 'pais' AND year(f.fecha) = 2021
     GROUP BY 1 ORDER BY casos_por_100k DESC
     """),

    ("SLICE — solo dimensión fecha 2021-03 (un corte temporal)",
     """
     SELECT pais_iso3,
            sum(CASE WHEN new_confirmed >= 0 THEN new_confirmed ELSE 0 END) AS nuevos_casos,
            sum(CASE WHEN new_deaths    >= 0 THEN new_deaths    ELSE 0 END) AS nuevos_fallecidos
     FROM v_nacional_dia
     WHERE fecha BETWEEN DATE '2021-03-01' AND DATE '2021-03-31'
     GROUP BY 1 ORDER BY nuevos_casos DESC LIMIT 15
     """),

    ("DICE — Chile, 2020-2021 × región (matriz)",
     """
     SELECT t.territorio_key AS region,
            sum(CASE WHEN year(f.fecha) = 2020 AND f.new_confirmed >= 0 THEN f.new_confirmed ELSE 0 END) AS casos_2020,
            sum(CASE WHEN year(f.fecha) = 2021 AND f.new_confirmed >= 0 THEN f.new_confirmed ELSE 0 END) AS casos_2021
     FROM fact_covid f JOIN dim_territorio t USING (territorio_id)
     WHERE t.pais_iso3 = 'CHL' AND t.nivel <> 'pais'
     GROUP BY 1 ORDER BY casos_2021 DESC
     """),

    ("KPI — 10 países con más fallecimientos por 100.000 (población JHU; excluye especiales)",
     """
     SELECT pais_iso3,
            max(deaths)                                               AS fallecidos,
            max(poblacion)                                            AS poblacion,
            round(1e5 * max(deaths) / max(poblacion), 1)              AS fallecidos_por_100k
     FROM v_nacional_dia
     WHERE poblacion IS NOT NULL AND poblacion > 100000
     GROUP BY 1 ORDER BY fallecidos_por_100k DESC LIMIT 10
     """),

    ("KPI — Chile vs Sudamérica: casos por 100.000 por año",
     """
     SELECT pais_iso3, year(fecha) AS anio,
            round(1e5 * sum(CASE WHEN new_confirmed >= 0 THEN new_confirmed ELSE 0 END)
                  / max(poblacion), 1) AS casos_por_100k
     FROM v_nacional_dia
     WHERE pais_iso3 IN ('CHL','ARG','PER','COL','BRA','ECU','URY','PRY','BOL')
       AND poblacion IS NOT NULL AND poblacion > 0
     GROUP BY 1, 2 ORDER BY 2, 3 DESC
     """),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dw", type=Path, default=DW)
    parser.add_argument("--salida", type=Path, default=SALIDA)
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    con = duckdb.connect(str(args.dw), read_only=True)
    lineas: list[str] = []
    for titulo, consulta in CONSULTAS:
        lineas.append("=" * 78)
        lineas.append(titulo)
        lineas.append("=" * 78)
        df = con.execute(consulta).df()
        lineas.append(df.to_string(index=False))
        lineas.append("")
    con.close()

    texto = "\n".join(lineas)
    print(texto)
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(texto, encoding="utf-8")
    print(f"Guardado en {args.salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
