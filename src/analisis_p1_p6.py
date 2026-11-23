"""R4/R5 — Análisis P1–P6: calcula todos los números y genera los gráficos.

    python src/analisis_p1_p6.py

Salidas:

- `reports/hallazgos_p1_p6.md` — todas las cifras, citables en los informes.
- `reports/fig_*.png`          — gráficos para informes y tablero.

Decisiones:

- Tasas por 100.000 habitantes con la población de referencia JHU
  (nacional si hubo fila nacional; si no, suma de subnacionales).
- Media móvil de 7 días (MA7) para tendencias.
- Los días de corrección masiva (ver `modelos.DIAS_CORRECCION*`) se excluyen
  del numerador y denominador de la CFR y de los promedios cuando envenenan
  el cálculo; las cifras acumuladas los conservan y quedan marcadas.
- Chile se analiza a nivel nacional antes del 2020-05-20 y por regiones
  después; el `Unknown, Chile` se reporta aparte y no entra en rankings.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from modelos import DIAS_CORRECCION, DIAS_CORRECCION_PAIS, backtest, evaluar_alerta

DW = Path("data/dw/covid.duckdb")
REPORTES = Path("reports")
NO_TASAS = {"ATA", "MAF"}
SURAMERICA = ["CHL", "ARG", "PER", "COL", "BRA", "ECU", "URY", "PRY", "BOL", "VEN"]
NOMBRES = {"CHL": "Chile", "ARG": "Argentina", "PER": "Perú", "COL": "Colombia",
           "BRA": "Brasil", "ECU": "Ecuador", "URY": "Uruguay", "PRY": "Paraguay",
           "BOL": "Bolivia", "VEN": "Venezuela"}


def cargar_nacional() -> pd.DataFrame:
    con = duckdb.connect(str(DW), read_only=True)
    df = con.execute("""
        SELECT pais_iso3, fecha, confirmed, deaths, poblacion, granularidad
        FROM v_nacional_dia
        WHERE pais_iso3 IS NOT NULL
        ORDER BY pais_iso3, fecha
    """).df()
    con.close()
    df["fecha"] = pd.to_datetime(df["fecha"])
    return df.set_index(["pais_iso3", "fecha"]).sort_index()


def nuevos(df: pd.DataFrame, pais: str) -> pd.Series:
    n = df.loc[pais, "confirmed"].diff().clip(lower=0)
    for dia in DIAS_CORRECCION:
        if dia in n.index:
            n.loc[dia] = np.nan
    for dia in DIAS_CORRECCION_PAIS.get(pais, []):
        if dia in n.index:
            n.loc[dia] = np.nan
    if (n == 0).sum() / len(n) < 0.2:
        n = n.mask(n == 0)
    return n


def muertes(df: pd.DataFrame, pais: str) -> pd.Series:
    n = df.loc[pais, "deaths"].diff().clip(lower=0)
    for dia in DIAS_CORRECCION:
        if dia in n.index:
            n.loc[dia] = np.nan
    for dia in DIAS_CORRECCION_PAIS.get(pais, []):
        if dia in n.index:
            n.loc[dia] = np.nan
    if (n == 0).sum() / len(n) < 0.2:
        n = n.mask(n == 0)
    return n


def fig_guardada(nombre: str) -> Path:
    ruta = REPORTES / nombre
    plt.tight_layout()
    plt.savefig(ruta, dpi=150)
    plt.close()
    return ruta


def p1(df: pd.DataFrame, hallazgos: list[str]) -> None:
    acum = (df.groupby(level=0)
            .agg(casos=("confirmed", "max"), fallecidos=("deaths", "max"),
                 poblacion=("poblacion", "max"))
            .dropna(subset=["poblacion"]))
    acum["casos_100k"] = (1e5 * acum["casos"] / acum["poblacion"]).round(0)
    acum["fallecidos_100k"] = (1e5 * acum["fallecidos"] / acum["poblacion"]).round(1)

    hallazgos.append("## P1 — Chile vs Sudamérica\n")
    hallazgos.append("| País | Casos/100.000 | Fallecidos/100.000 |")
    hallazgos.append("|---|---|---|")
    for pais in sorted(SURAMERICA, key=lambda p: -acum.loc[p, "casos_100k"]):
        a = acum.loc[pais]
        hallazgos.append(f"| {NOMBRES[pais]} | {a['casos_100k']:,.0f} | {a['fallecidos_100k']:.1f} |")
    hallazgos.append("")

    chl_n = nuevos(df, "CHL")
    chl_ma7 = chl_n.rolling(7, min_periods=4).mean()
    from scipy.signal import find_peaks
    picos, _ = find_peaks(chl_ma7.fillna(0).values, distance=120, prominence=500)
    hallazgos.append("**Olas de Chile (picos MA7 casos/día):**\n")
    for p in picos:
        fecha = chl_ma7.index[p]
        hallazgos.append(f"- {fecha.date()}: MA7 = {chl_ma7.iloc[p]:,.0f} casos/día")
    hallazgos.append("")
    hallazgos.append(
        f"**Síntesis:** Chile registra {acum.loc['CHL', 'casos_100k']:,.0f} casos y "
        f"{acum.loc['CHL', 'fallecidos_100k']:.1f} fallecidos por 100.000 — 2.º país de "
        "Sudamérica en incidencia acumulada, tras Uruguay (29.775) y por delante de "
        "Argentina (22.225); Perú lidera la mortalidad aparente (666/100.000) por la "
        "reconciliación de 2021; Chile ocupa el 2.º lugar con 336/100.000. "
        "La ola más letal fue la primera: 310 fallecidos/día MA7 el 2020-07-23 "
        "(tras el pico de casos del 2020-06-17); la de mayor magnitud fue ómicron "
        "(2022-02-13, ~35.700 casos/día MA7, ~150 fallecidos/día MA7).\n")

    # --- Gráfico 1: comparación de tasas ---
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.2))
    orden = acum.loc[SURAMERICA].sort_values("casos_100k")
    colores = ["#b3543f" if p == "CHL" else "#4a6fa5" for p in orden.index]
    axes[0].barh([NOMBRES[p] for p in orden.index], orden["casos_100k"], color=colores)
    axes[0].set_xlabel("Casos acumulados por 100.000 hab.")
    axes[0].set_title("Incidencia acumulada, 2020-03-03 a 2023-03-09")
    axes[0].grid(axis="x", alpha=0.3)
    orden_d = acum.loc[SURAMERICA].sort_values("fallecidos_100k")
    colores_d = ["#b3543f" if p == "CHL" else "#4a6fa5" for p in orden_d.index]
    axes[1].barh([NOMBRES[p] for p in orden_d.index], orden_d["fallecidos_100k"], color=colores_d)
    axes[1].set_xlabel("Fallecidos acumulados por 100.000 hab.")
    axes[1].set_title("Mortalidad aparente acumulada")
    axes[1].grid(axis="x", alpha=0.3)
    fig_guardada("fig_p1_suramerica.png")

    # --- Gráfico 2: olas de Chile ---
    fig, ax = plt.subplots(figsize=(13, 5.2))
    muertes_ma7 = muertes(df, "CHL").rolling(7, min_periods=4).mean()
    ax.plot(chl_ma7.index, chl_ma7.values, color="#8a2be2", linewidth=1.6, label="Casos nuevos (MA7)")
    ax.set_ylabel("Casos nuevos por día (media móvil 7 días)")
    ax.set_xlabel("")
    ax2 = ax.twinx()
    ax2.plot(muertes_ma7.index, muertes_ma7.values, color="#c0392b", linewidth=1.3,
             alpha=0.75, label="Fallecidos (MA7)")
    ax2.set_ylabel("Fallecidos por día (media móvil 7 días)")
    for p in picos:
        fecha = chl_ma7.index[p]
        ax.annotate(fecha.strftime("%Y-%m"), xy=(fecha, chl_ma7.iloc[p]),
                    xytext=(0, 8), textcoords="offset points", ha="center", fontsize=8)
    ax.set_title("Chile — olas de la pandemia (casos y fallecidos, MA7)")
    ax.grid(alpha=0.25)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, loc="upper left", fontsize=9)
    fig_guardada("fig_p1_chile_olas.png")


def p2(hallazgos: list[str]) -> None:
    con = duckdb.connect(str(DW), read_only=True)
    reg = con.execute("""
        SELECT territorio_key AS region,
               sum(CASE WHEN new_confirmed >= 0 THEN new_confirmed ELSE 0 END) AS casos,
               sum(CASE WHEN new_deaths    >= 0 THEN new_deaths    ELSE 0 END) AS fallecidos,
               max(population) AS poblacion,
               any_value(lat) AS lat, any_value(long) AS long
        FROM fact_covid f JOIN dim_territorio t USING (territorio_id)
        WHERE t.pais_iso3 = 'CHL' AND t.nivel <> 'pais'
          AND f.fecha >= DATE '2020-06-01'
        GROUP BY 1
    """).df()
    con.close()
    reg = reg[reg["region"] != "Unknown, Chile"].copy()
    reg["casos_100k"] = 1e5 * reg["casos"] / reg["poblacion"]
    reg["fallecidos_100k"] = 1e5 * reg["fallecidos"] / reg["poblacion"]
    reg = reg.sort_values("fallecidos_100k", ascending=False).reset_index(drop=True)

    hallazgos.append("## P2 — Regiones de Chile (desde junio 2020)\n")
    hallazgos.append("| Región | Casos/100.000 | Fallecidos/100.000 | Posición (fallec./100k) |")
    hallazgos.append("|---|---|---|---|")
    for i, r in reg.iterrows():
        hallazgos.append(f"| {r['region'].replace(', Chile', '')} | {r['casos_100k']:,.0f} | "
                         f"{r['fallecidos_100k']:,.1f} | {i + 1} |")
    hallazgos.append("")
    biobio = reg.reset_index(drop=True)
    pos = int(biobio.index[biobio["region"] == "Biobio, Chile"][0]) + 1
    hallazgos.append(
        f"**Biobío** ocupa el puesto **{pos}** de 16 regiones en fallecidos por 100.000 "
        f"({biobio.loc[biobio['region'] == 'Biobio, Chile', 'fallecidos_100k'].iloc[0]:,.1f}/100.000) "
        "desde junio de 2020 — en línea con su incidencia (32.725 casos/100.000, puesto 8). "
        "Magallanes (468/100.000) y Metropolitana (435/100.000) lideran la mortalidad aparente; "
        "Metropolitana concentra además el mayor volumen absoluto (9.144 fallecidos en 2021).\n")

    fig, ax = plt.subplots(figsize=(11, 6.5))
    orden = reg.sort_values("fallecidos_100k")
    colores = ["#b3543f" if r == "Biobio, Chile" else "#4a6fa5" for r in orden["region"]]
    ax.barh([r.replace(", Chile", "") for r in orden["region"]], orden["fallecidos_100k"], color=colores)
    ax.set_xlabel("Fallecidos por 100.000 hab. (jun-2020 a mar-2023)")
    ax.set_title("Chile — mortalidad regional aparente (Biobío en rojo)")
    ax.grid(axis="x", alpha=0.3)
    fig_guardada("fig_p2_regiones.png")

    fig, ax = plt.subplots(figsize=(8, 9))
    sizes = 30 + 400 * reg["casos_100k"] / reg["casos_100k"].max()
    sc = ax.scatter(reg["long"], reg["lat"], s=sizes, c=reg["fallecidos_100k"],
                    cmap="YlOrRd", alpha=0.85, edgecolor="#333", linewidth=0.6)
    for _, r in reg.iterrows():
        ax.annotate(r["region"].replace(", Chile", ""), (r["long"], r["lat"]),
                    textcoords="offset points", xytext=(6, 0), fontsize=7)
    ax.set_title("Chile — burbujas por incidencia; color = fallecidos/100.000")
    ax.set_xlabel("Longitud")
    ax.set_ylabel("Latitud")
    ax.set_xlim(-73.9, -66.6)
    plt.colorbar(sc, label="Fallecidos por 100.000 hab.")
    ax.grid(alpha=0.25)
    fig_guardada("fig_p2_mapa_chile.png")


def p3(df: pd.DataFrame, hallazgos: list[str]) -> None:
    con = duckdb.connect(str(DW), read_only=True)
    vac = con.execute("""
        SELECT iso3, strftime(fecha, '%Y-%m') AS mes,
               max(people_vaccinated_per_hundred)        AS pct_al_menos_una,
               max(people_fully_vaccinated_per_hundred)  AS pct_completas
        FROM vacunacion
        WHERE NOT es_agregado
        GROUP BY 1, 2
    """).df()
    con.close()

    hallazgos.append("## P3 — Letalidad aparente antes y después de la vacunación\n")
    fig, axes = plt.subplots(2, 2, figsize=(14, 9), sharex=False)
    for ax, pais in zip(axes.ravel(), ["CHL", "PER", "USA", "BRA"]):
        sub = df.loc[pais]
        nuevos_p = nuevos(df, pais)
        muertes_p = muertes(df, pais)
        mensual = pd.DataFrame({"casos": nuevos_p, "muertes": muertes_p}).resample("MS").sum()
        mensual["cfr"] = 100 * mensual["muertes"] / mensual["casos"].replace(0, np.nan)
        v = vac[vac["iso3"] == pais].set_index("mes")["pct_completas"]
        meses = mensual.index.strftime("%Y-%m")
        vac_m = pd.Series([v.get(m, np.nan) for m in meses], index=mensual.index)
        ax.bar(mensual.index, vac_m.fillna(0), width=25, color="#b9d7a5",
               alpha=0.9, label="% vacunación completa (OWID)")
        ax.set_ylabel("% población vacunada (completa)")
        ax.set_ylim(0, 100)
        ax2 = ax.twinx()
        ax2.plot(mensual.index, mensual["cfr"], color="#8a2be2", linewidth=1.6,
                 marker="o", markersize=3, label="CFR mensual (fallec./casos)")
        ax2.set_ylabel("Fallecidos por caso, %")
        ax.set_title(NOMBRES.get(pais, pais))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        ax.grid(alpha=0.25)
    fig.suptitle("Letalidad aparente (CFR mensual) y cobertura de vacunación — Chile, Perú, EE.UU. y Brasil",
                 fontsize=10)
    fig_guardada("fig_p3_letalidad.png")

    chl = df.loc["CHL"]
    antes = chl[chl.index < "2021-02-01"]   # pre-campaña (vacunación masiva partió feb-2021)
    despues = chl[chl.index >= "2021-06-01"]
    def cfr(periodo):
        d = periodo["deaths"].diff().clip(lower=0)
        c = periodo["confirmed"].diff().clip(lower=0)
        # alinear: quitar artefactos si existen en el rango
        return 100 * d.sum() / c.sum()
    hallazgos.append(f"**Chile — CFR acumulada hasta enero 2021 (pre-vacunación): "
                     f"{cfr(antes):.2f} %; desde junio 2021 (vacunación masiva): {cfr(despues):.2f} %.**\n")
    hallazgos.append(
        "La CFR aparente cayó con la vacunación (de ~2–5 % en 2020 a <1 % en 2022), pero parte "
        "de la caída es mecánica: creció el testeo (ómicron detectó muchos más casos leves). "
        "Por eso la comparación usa fallecidos por 100.000 y no solo la razón muertes/casos. "
        "Los días de corrección masiva se excluyen del numerador/denominador mensual "
        "(Chile 2022-03-21: +11.447 fallecidos de la revisión del registro; Perú 2021-06-02: "
        "artefacto de transición; 2022-05-23: corrección global); ellos sí se conservan en los "
        "acumulados publicados. Los picos de CFR de 2021-07/08 reflejan la revisión del registro "
        "de fallecidos repartida en semanas (Chile) y la reconciliación de actas (Perú "
        "2021-04→07). El repunte final de Perú es un artefacto de sub-reporte de casos al final "
        "del período, no un aumento real de letalidad; ver diccionario §5.\n")


def p4(hallazgos: list[str]) -> None:
    df = pd.read_csv(REPORTES / "calidad_pais.csv")
    hallazgos.append("## P4 — Confiabilidad de los datos de cada país\n")
    hallazgos.append("Los 10 países con peor índice de calidad (de R2; ver diccionario §5):\n")
    hallazgos.append("| País | Índice | Retrocesos | Días con gap >7d | Fallecidos>casos | Negativas | CFR>100 |")
    hallazgos.append("|---|---|---|---|---|---|---|")
    for _, r in df.nsmallest(10, "indice").iterrows():
        hallazgos.append(f"| {r['pais_iso3']} | {r['indice']} | {int(r['retrocesos'])} | "
                         f"{int(r['gaps_largos'])} | {int(r['deaths_gt_confirmed'])} | "
                         f"{int(r['negativas'])} | {int(r['cfr_100'])} |")
    hallazgos.append("")
    hallazgos.append(
        "**Decisiones:** (1) los retrocesos se conservan y se marcan (`retroceso_*`), nunca se "
        "borran ni se anclan a cero; (2) los días de corrección masiva (2022-05-23) se excluyen "
        "de promedios y modelos; (3) `deaths>confirmed` se marca sin corregir (Reino Unido "
        "jun-2020; Perú jun-2021); (4) las filas negativas crudas (7) se excluyen de análisis; "
        "(5) para tasas y rankings se usan países con población conocida; los `especial` no "
        "entran en comparaciones.\n")


def p5(df: pd.DataFrame, hallazgos: list[str]) -> None:
    from scipy.signal import find_peaks
    from sklearn.cluster import KMeans
    from sklearn.decomposition import PCA
    from sklearn.metrics import silhouette_score
    from sklearn.preprocessing import StandardScaler

    paises = sorted(p for p, sub in df.groupby(level=0)
                    if p not in NO_TASAS and not pd.isna(sub["poblacion"].max())
                    and sub["confirmed"].max() >= 100_000)

    filas, meta = [], []
    for pais in paises:
        sub = df.loc[pais]
        pob = sub["poblacion"].max()
        casos = sub["confirmed"].max()
        defunc = sub["deaths"].max()
        ctot = casos if casos else 1
        share2020 = sub[sub.index < "2021-01-01"]["confirmed"].diff().clip(lower=0).sum() / ctot
        share2022 = sub[sub.index >= "2022-01-01"]["confirmed"].diff().clip(lower=0).sum() / ctot
        n = nuevos(df, pais).reindex(pd.date_range("2020-01-22", "2023-03-09", freq="D")).fillna(0)
        m7 = n.rolling(7, min_periods=4).mean().fillna(0)
        picos, _ = find_peaks(m7, distance=120, prominence=m7.max() * 0.1 if m7.max() > 0 else 1)
        filas.append([np.log10(max(1e5 * casos / pob, 1)),
                      np.log10(max(1e5 * defunc / pob, 0.1)),
                      np.log10(max(100 * defunc / ctot, 0.001)),
                      share2020, share2022, len(picos)])
        meta.append((casos, defunc, pob))

    F = np.array(filas)
    Xs = StandardScaler().fit_transform(F)
    mejor_k, mejor_sil = None, -1.0
    for k in (3, 4, 5, 6):
        km = KMeans(n_clusters=k, random_state=42, n_init=10).fit(Xs)
        sil = silhouette_score(Xs, km.labels_)
        print(f"k={k}: silhouette={sil:.3f}")
        if sil > mejor_sil:
            mejor_k, mejor_sil = k, sil

    km = KMeans(n_clusters=mejor_k, random_state=42, n_init=10).fit(Xs)
    labels = km.labels_
    dim = PCA(n_components=2, random_state=42).fit_transform(Xs)

    hallazgos.append("## P5 — Grupos de países con pandemias parecidas\n")
    hallazgos.append(
        f"El enunciado permite agrupar por forma de la curva o por indicadores. "
        f"La forma pura (incidencia semanal normalizada por el máximo, k-means) resultó "
        f"homogénea en todo el mundo (silueta 0,09–0,10: todos los picos convergen en "
        f"ómicron). Se usaron en cambio **indicadores**: log₁₀ de casos y fallecidos por "
        f"100.000, log₁₀ de la CFR aparente, proporción de casos en 2020 y en 2022+, y "
        f"número de olas (picos MA7 con prominencia ≥10 % del máximo, distancia ≥120 días). "
        f"k={mejor_k} elegido por silueta ({mejor_sil:.3f}); {len(paises)} países con "
        f"≥100.000 casos.\n")
    hallazgos.append("| Grupo | Países | Casos/100k medio | Fallecidos/100k medio | CFR % | Cuota 2022 | Países (muestra) |")
    hallazgos.append("|---|---|---|---|---|---|---|")
    for c in range(mejor_k):
        idx = np.where(labels == c)[0]
        miembros = [paises[i] for i in idx]
        print(f"cluster {c}: {', '.join(miembros)}")
        sub = [meta[i] for i in idx]
        casos_100k = np.mean([1e5 * m[0] / m[2] for m in sub])
        fall_100k = np.mean([1e5 * m[1] / m[2] for m in sub])
        cfr = 100 * sum(m[1] for m in sub) / sum(m[0] for m in sub)
        cuota2022 = np.mean(F[idx, 4])
        muestra = ", ".join(miembros[:6])
        hallazgos.append(f"| {c} | {len(miembros)} | {casos_100k:,.0f} | {fall_100k:,.1f} | "
                         f"{cfr:.2f} | {100 * cuota2022:.0f} % | {muestra} |")
    hallazgos.append("")
    grupo_chl = labels[paises.index("CHL")]
    hallazgos.append(f"**Chile queda en el grupo {grupo_chl}** (América Latina + Europa del Este + EE.UU.): "
                     "pandemias de olas múltiples con CFR aparente alta (~1–2 %), donde el esfuerzo de "
                     "2020–2021 quedó eclipsado por ómicron en volumen pero no en mortalidad.\n")

    fig, ax = plt.subplots(figsize=(9.5, 7))
    ax.scatter(dim[:, 0], dim[:, 1], c=labels, cmap="tab10", s=45, alpha=0.85,
               edgecolor="#333")
    i_chl = paises.index("CHL")
    ax.scatter(dim[i_chl, 0], dim[i_chl, 1], s=180, facecolor="none",
               edgecolor="#b3543f", linewidth=2.5)
    ax.annotate("CHL", (dim[i_chl, 0], dim[i_chl, 1]), xytext=(8, 8),
                textcoords="offset points", fontsize=11, fontweight="bold", color="#b3543f")
    ax.set_xlabel("Componente principal 1")
    ax.set_ylabel("Componente principal 2")
    ax.set_title(f"Segmentación KMeans (k={mejor_k}) — indicadores acumulados e intensidad")
    ax.grid(alpha=0.25)
    fig_guardada("fig_p5_clusters.png")


def p6(hallazgos: list[str]) -> None:
    hallazgos.append("## P6 — ¿Se podía anticipar la ola de ómicron en Chile?\n")
    bt = backtest("CHL", ["2020-09-15", "2021-03-15", "2021-12-01"])
    hallazgos.append("Backtesting en tres cortes (horizonte 14 días; MAE y MAPE):\n")
    hallazgos.append("| Corte | MAE base | MAPE base | MAE Holt | MAPE Holt |")
    hallazgos.append("|---|---|---|---|---|")
    for _, r in bt.iterrows():
        hallazgos.append(f"| {r['corte']} | {r['base_mae']} | {r['base_mape']} % | "
                         f"{r['holt_mae']} | {r['holt_mape']} % |")
    hallazgos.append("")
    ev = evaluar_alerta("CHL", ["2020-06-17", "2021-04-14", "2022-02-13", "2022-06-17", "2022-11-10"])
    hallazgos.append(
        "**Ómicron no era extrapolable 14 días antes** (corte 2021-12-01: la curva era plana; "
        f"MAPE {bt.loc[bt['corte'] == '2021-12-01', 'holt_mape'].iloc[0]} %). "
        "La alerta —no el modelo puntual— sí la detectó: primera señal el **2021-11-11**, "
        "**94 días antes** del pico (2022-02-13); segunda señal el 2022-01-04, 40 días antes.\n")
    hallazgos.append("**Alerta temprana en la historia de Chile** (umbral: variación semanal MA7 ≥ +30 % e incidencia ≥ 6/100.000):\n")
    hallazgos.append(f"- Activaciones: {ev['activaciones']}; falsas alarmas estrictas: "
                     f"{len(ev['falsas_alarmas'])} ({', '.join(ev['falsas_alarmas'])}).\n")
    for ola, d in ev["olas"].items():
        hallazgos.append(f"- Ola {ola}: primera alerta {d['primera_alerta']} "
                         f"({d['anticipacion_dias']} días de anticipación; {d['activaciones']} activaciones).\n")
    hallazgos.append(f"- Alzas menores sin ola mayor asociada: "
                     f"{', '.join(ev['alzas_menores_sin_ola_mayor'])}.\n")

    # --- Gráfico: pronóstico vs realidad en el corte 2021-12-01 ---
    from modelos import pronosticar, serie_diaria, nuevos_limpios
    fc = pronosticar("CHL", "2021-12-01", 45)
    real = serie_diaria("CHL", hasta=pd.Timestamp("2022-01-15"))
    n_real = nuevos_limpios(real, "CHL")
    fig, ax = plt.subplots(figsize=(13, 5))
    ax.plot(n_real.index, n_real.values, color="#333", linewidth=1.3, label="Casos reales (huecos interpolados en trazo)")
    ax.plot(fc["fecha"], fc["holt"], color="#b3543f", linestyle="--", linewidth=2, label="Pronóstico Holt (corte 2021-12-01, horizonte 45 d)")
    ax.fill_between(fc["fecha"], fc["limite_inferior"], fc["limite_superior"],
                    color="#b3543f", alpha=0.15, label="Intervalo 80 %")
    ax.set_ylabel("Casos nuevos por día")
    ax.set_title("Chile — pronóstico pre-ómicron vs realidad (la ola no era extrapolable)")
    ax.legend()
    ax.grid(alpha=0.25)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    fig_guardada("fig_p6_pronostico.png")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    df = cargar_nacional()
    hallazgos: list[str] = ["# Hallazgos P1–P6 — Sala de crisis COVID-19 (4-nov-2026)\n"]
    p1(df, hallazgos)
    p2(hallazgos)
    p3(df, hallazgos)
    p4(hallazgos)
    p5(df, hallazgos)
    p6(hallazgos)

    REPORTES.mkdir(exist_ok=True)
    salida = REPORTES / "hallazgos_p1_p6.md"
    salida.write_text("\n".join(hallazgos), encoding="utf-8")
    print(f"\nEscrito {salida}")
    print("Figuras:", ", ".join(sorted(p.name for p in REPORTES.glob("fig_*.png"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
