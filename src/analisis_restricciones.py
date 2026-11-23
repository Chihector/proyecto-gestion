"""Extra — Respuesta de política (Oxford OxCGRT) y evolución de la pandemia.

Segunda fuente externa del proyecto (además de la vacunación de OWID).
Integra el panel país-día de OxCGRT —tabla `restricciones` del DW— con las
series de casos de JHU para describir cómo se alinearon las restricciones y
las olas en Chile y en los tres países de P7 (Perú, EE.UU. y Brasil).

Decisiones y límites (misma disciplina que P7):

- Cruce por ISO3 (`CountryCode`); Kosovo se homologa RKS→XKS al cargar el DW.
- OxCGRT cubre 2020-01-01 a 2022-12-31: cierra antes que JHU (2023-03-09);
  las comparaciones usan el tramo común y lo declaran.
- ADVERTENCIA (obligatoria): asociación descriptiva, NO causal. Las
  restricciones suelen responder a los casos (endogeneidad); el índice mide
  política «de jure», no su cumplimiento; su metodología cambió con el
  tiempo (p. ej. la diferenciación por estado de vacunación y el índice M).

    python src/analisis_restricciones.py

Salidas:  reports/hallazgos_restricciones.md · reports/fig_restricciones.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

DW = Path("data/dw/covid.duckdb")
REPORTES = Path("reports")
PAISES = ["CHL", "PER", "USA", "BRA"]
NOMBRES = {"CHL": "Chile", "PER": "Perú", "USA": "EE.UU.", "BRA": "Brasil"}
COLORES = {"CHL": "#b3543f", "PER": "#4a6fa5", "USA": "#6d28d9", "BRA": "#2e8b57"}
OLAS_CHL = ["2020-06-17", "2021-04-14", "2022-02-13", "2022-06-17", "2022-11-10"]
JHU_FIN = pd.Timestamp("2023-03-09")


def _conexion() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(DW), read_only=True)


def cobertura(con: duckdb.DuckDBPyConnection) -> dict:
    filas, paises, fmin, fmax = con.execute(
        "SELECT count(*), count(DISTINCT iso3), min(fecha), max(fecha) "
        "FROM restricciones").fetchone()
    jhu_total = con.execute(
        "SELECT count(DISTINCT pais_iso3) FROM dim_territorio "
        "WHERE pais_iso3 IS NOT NULL").fetchone()[0]
    sin_cruce = [r[0] for r in con.execute("""
        SELECT DISTINCT r.iso3 FROM restricciones r
        LEFT JOIN (SELECT DISTINCT pais_iso3 FROM dim_territorio
                   WHERE pais_iso3 IS NOT NULL) t ON t.pais_iso3 = r.iso3
        WHERE t.pais_iso3 IS NULL ORDER BY 1""").fetchall()]
    jhu_sin = [r[0] for r in con.execute("""
        SELECT DISTINCT t.pais_iso3 FROM dim_territorio t
        WHERE t.pais_iso3 IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM restricciones r WHERE r.iso3 = t.pais_iso3)
        ORDER BY 1""").fetchall()]
    return {
        "filas": filas, "paises": paises, "fmin": pd.Timestamp(fmin),
        "fmax": pd.Timestamp(fmax), "jhu_total": jhu_total,
        "cruz": paises - len(sin_cruce), "sin_cruce": sin_cruce,
        "jhu_sin": jhu_sin,
    }


def serie_pais(con: duckdb.DuckDBPyConnection, pais: str) -> pd.DataFrame:
    """Casos MA7 (JHU) y stringency (OxCGRT) por día, en el tramo común."""
    df = con.execute("""
        WITH f AS (SELECT fecha, stringency_index FROM restricciones WHERE iso3 = ?)
        SELECT f.fecha, f.stringency_index, n.new_confirmed
        FROM f JOIN v_nacional_dia n ON n.fecha = f.fecha AND n.pais_iso3 = ?
        ORDER BY f.fecha
    """, [pais, pais]).df()
    df["fecha"] = pd.to_datetime(df["fecha"])
    df = df.set_index("fecha")
    df["casos_ma7"] = df["new_confirmed"].clip(lower=0).rolling(7, min_periods=4).mean()
    return df


def resumen(s: pd.Series) -> dict:
    idx_max = s.idxmax()
    s7 = s.rolling(7).mean()
    cand = s7[(s7.index >= "2021-01-01") & (s7 <= 30)]
    return {
        "max": float(s.max()), "max_fecha": idx_max.date().isoformat(),
        "media_2020": float(s[s.index.year == 2020].mean()),
        "media_2021": float(s[s.index.year == 2021].mean()),
        "media_2022": float(s[s.index.year == 2022].mean()),
        "dias_ge70": int((s >= 70).sum()),
        "relajacion": cand.index[0].date().isoformat() if len(cand) else "—",
    }


def fig_restricciones(series: dict[str, pd.DataFrame], chl_res: dict) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.4))

    ax = axes[0]
    chl = series["CHL"]
    ax.plot(chl.index, chl["casos_ma7"], color="#4a6fa5", lw=1.8, label="Casos MA7 (JHU)")
    ax.set_ylabel("casos nuevos, MA7", color="#4a6fa5")
    ax.tick_params(axis="y", labelcolor="#4a6fa5")
    ax2 = ax.twinx()
    ax2.plot(chl.index, chl["stringency_index"], color="#b3543f", lw=1.6,
             label="Stringency (OxCGRT)")
    ax2.set_ylabel("índice de stringency (0–100)", color="#b3543f")
    ax2.tick_params(axis="y", labelcolor="#b3543f")
    ax2.set_ylim(0, 100)
    for ola in OLAS_CHL:
        ax.axvline(pd.Timestamp(ola), color="#888", ls="--", lw=0.8, alpha=0.7)
    ax.set_title("Chile — olas de casos (JHU) vs restricciones (OxCGRT)")
    ax.grid(alpha=0.25)
    lineas = ax.get_lines()[:1] + ax2.get_lines()[:1]
    ax.legend(lineas, [l.get_label() for l in lineas], loc="upper left", fontsize=8)

    axb = axes[1]
    for pais in PAISES:
        axb.plot(series[pais].index, series[pais]["stringency_index"],
                 color=COLORES[pais], lw=1.6, label=NOMBRES[pais])
    axb.set_ylabel("índice de stringency (0–100)")
    axb.set_ylim(0, 100)
    axb.axhline(30, color="#888", ls=":", lw=0.8)
    axb.set_title("Índice de stringency — Chile, Perú, EE.UU. y Brasil")
    axb.grid(alpha=0.25)
    axb.legend(loc="upper left", fontsize=8, ncol=2)

    fig.suptitle("Respuesta de política (OxCGRT, «de jure») y evolución de la pandemia", fontsize=11)
    fig.tight_layout()
    fig.savefig(REPORTES / "fig_restricciones.png", dpi=150)
    plt.close(fig)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    con = _conexion()
    try:
        cob = cobertura(con)
    except duckdb.CatalogException:
        print("Falta la tabla `restricciones`: ejecuta primero src/construir_dw.py",
              file=sys.stderr)
        return 2

    series = {p: serie_pais(con, p) for p in PAISES}
    resumenes = {p: resumen(series[p]["stringency_index"]) for p in PAISES}
    chl = series["CHL"]
    chl_res = resumenes["CHL"]

    olas = []
    for o in OLAS_CHL:
        t = pd.Timestamp(o)
        if t in chl.index:
            olas.append({
                "fecha": o,
                "casos_ma7": float(chl.loc[t, "casos_ma7"]),
                "stringency": float(chl.loc[t, "stringency_index"]),
            })

    t0 = pd.Timestamp("2020-06-17")
    t28 = t0 + pd.Timedelta(days=28)
    caida_28d = 100 * (chl.loc[t28, "casos_ma7"] / chl.loc[t0, "casos_ma7"] - 1)
    t_omicron = pd.Timestamp("2022-02-13")
    vax_omicron = con.execute(
        "SELECT people_fully_vaccinated_per_hundred FROM vacunacion "
        "WHERE iso3 = 'CHL' AND fecha <= ? ORDER BY fecha DESC LIMIT 1",
        [t_omicron]).fetchone()[0]
    con.close()

    dias_jhu_oxcgrt = (JHU_FIN - cob["fmax"]).days
    pct_cruce = 100 * cob["cruz"] / cob["jhu_total"]
    mas_alto = max(PAISES, key=lambda p: resumenes[p]["max"])
    mas_bajo = min(PAISES, key=lambda p: resumenes[p]["max"])
    orden_relax = sorted((p for p in PAISES if resumenes[p]["relajacion"] != "—"),
                         key=lambda p: resumenes[p]["relajacion"])

    fig_restricciones(series, chl_res)

    h: list[str] = ["# Extra — Restricciones (OxCGRT) y olas de casos (4-nov-2026)\n"]
    h.append(
        "Segunda fuente externa integrada al DW (además de vacunación OWID): el panel "
        "país-día de Oxford (tabla `restricciones`). Mide la respuesta de política «de jure» "
        "(stringency index, 0–100) — no el cumplimiento real — y **no** sostiene causalidad: "
        "las restricciones suelen responder a los casos (endogeneidad).\n")

    h.append("## Cobertura del cruce por ISO3\n")
    h.append(f"- {cob['filas']:,} filas país-día; {cob['paises']} países; "
             f"{cob['fmin'].date()} a {cob['fmax'].date()} "
             f"(cierra {dias_jhu_oxcgrt} días antes que JHU).")
    h.append(f"- **{cob['cruz']}/{cob['jhu_total']} países del DW cruzan ({pct_cruce:.1f} %)** "
             f"(Kosovo homologado RKS→XKS). Sin cruce OxCGRT→DW: "
             f"{', '.join(cob['sin_cruce']) or '—'}.")
    muestra = ", ".join(cob["jhu_sin"][:12])
    h.append(f"- Del lado JHU quedan {len(cob['jhu_sin'])} países sin panel de OxCGRT "
             f"(microestados, territorios y algunos países sin datos de política): {muestra}, …\n")

    h.append("## Chile — restricciones y las cinco olas\n")
    h.append("| Ola (pico MA7 JHU) | Casos MA7 | Stringency ese día |")
    h.append("|---|---|---|")
    for o in olas:
        h.append(f"| {o['fecha']} | {o['casos_ma7']:,.0f} | {o['stringency']:.0f} |")
    h.append("")
    h.append(f"- Índice máximo de Chile: **{chl_res['max']:.1f} el {chl_res['max_fecha']}**; "
             f"{chl_res['dias_ge70']} días ≥ 70 (de {len(chl):,} con dato).")
    h.append(f"- La relajación sostenida (media móvil 7 días ≤ 30) empieza el "
             f"**{chl_res['relajacion']}**.")
    h.append(f"- Primera ola: el índice venía en {chl.loc[t0, 'stringency_index']:.0f} el día del "
             f"pico de casos y en {chl.loc[t28, 'stringency_index']:.0f} cuatro semanas después; "
             f"en ese mes los casos MA7 cayeron **{caida_28d:,.0f} %**.")
    h.append(f"- Ómicron: el pico del {t_omicron.date()} llegó con un índice de "
             f"{chl.loc[t_omicron, 'stringency_index']:.0f} y ~{vax_omicron:.0f} % de población "
             f"con vacunación completa (OWID): la ola más grande del país ocurrió con menos de la "
             f"mitad del rigor de 2020.\n")

    h.append("## Comparación: Chile, Perú, EE.UU. y Brasil\n")
    h.append("| País | Máx. (fecha) | Media 2020 | Media 2021 | Media 2022 | Días ≥ 70 | Relajación ≤ 30 |")
    h.append("|---|---|---|---|---|---|---|")
    for p in PAISES:
        r = resumenes[p]
        h.append(f"| {NOMBRES[p]} | {r['max']:.1f} ({r['max_fecha']}) | {r['media_2020']:.1f} | "
                 f"{r['media_2021']:.1f} | {r['media_2022']:.1f} | {r['dias_ge70']} | {r['relajacion']} |")
    h.append("")
    h.append(f"El máximo más alto es **{NOMBRES[mas_alto]}** "
             f"({resumenes[mas_alto]['max']:.1f}) y el más bajo {NOMBRES[mas_bajo]} "
             f"({resumenes[mas_bajo]['max']:.1f}). La relajación sostenida ≤ 30 llega primero en "
             f"{NOMBRES[orden_relax[0]]} ({resumenes[orden_relax[0]]['relajacion']}) y último en "
             f"{NOMBRES[orden_relax[-1]]} ({resumenes[orden_relax[-1]]['relajacion']}). "
             "En los cuatro países las restricciones fueron la herramienta central de 2020 y se "
             "aflojaron de forma sostenida durante 2021–2022, mientras las olas de ómicron eran "
             "las mayores de la serie: política relajada y olas récord conviven — la vacunación "
             "y la vigilancia pasan a ser las herramientas críticas (ver P7 y R2).\n")

    h.append("## Lectura y límites\n")
    h.append("- Asociación descriptiva, **no causal**: el índice sube porque hay casos y baja "
             "porque la situación lo permite; ambas series se mueven juntas por diseño.")
    h.append("- «De jure»: codifica lo anunciado, no su cumplimiento; la comparación entre "
             "países puede reflejar estilos de reporte.")
    h.append("- Cobertura 2020-01-01 a 2022-12-31 y metodología variable en el tiempo "
             "(diferenciación por vacunación): exigen leer las cifras como contexto, no como "
             "experimento.\n")

    salida = REPORTES / "hallazgos_restricciones.md"
    salida.write_text("\n".join(h), encoding="utf-8")

    for p in PAISES:
        r = resumenes[p]
        print(f"{NOMBRES[p]:6} max {r['max']:5.1f} ({r['max_fecha']})  ",
              f"medias {r['media_2020']:4.1f}/{r['media_2021']:4.1f}/{r['media_2022']:4.1f}  ",
              f"relajacion {r['relajacion']}")
    print(f"\nCruce: {cob['cruz']}/{cob['jhu_total']} ({pct_cruce:.1f} %) · "
          f"escrito {salida} y reports/fig_restricciones.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
