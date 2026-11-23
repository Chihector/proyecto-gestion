"""P7 — ¿Cómo se relaciona la cobertura de vacunación con la mortalidad
reportada en las ocho semanas siguientes? (Chile y tres países a elección).

Países: Chile, Perú, EE.UU. y Brasil. Fuentes: JHU (fallecidos) y OWID
(`people_fully_vaccinated_per_hundred`, cruce por ISO3; Chile 90,3 % al
cierre, Perú 84,3 %, EE.UU. 69,5 %, Brasil 81,8 %).

Método (documentado, asociación ecológica — NO causalidad):

1. Serie semanal de fallecidos por 100.000 hab. (JHU, nuevos ≥ 0, días de
   corrección masiva excluidos: 2022-05-23 global; Chile 2020-06-17 y
   2020-07-17 son de casos/inserciones, 2022-03-21 propio de fallecidos).
2. Cobertura semanal de vacunación completa (OWID), interpolada linealmente
   y rellenada hacia atrás hasta el inicio de la serie JHU (0 % antes de
   que existieran las vacunas).
3. Correlación Spearman entre cobertura en la semana t y fallecimientos en
   la semana t+lag, para lag = 0…8 semanas.
4. Comparación simple antes/después de alcanzar el 50 % de vacunación
   completa (momento «mass rollout» de cada país).

Advertencias (obligatorias en el informe): asociación ecológica, no
causal; confusión por fase de la ola (ómicron llegó con cobertura alta y
repuntó la mortalidad); el testeo y la definición de muerte por COVID
cambiaron en el tiempo; la cobertura OWID depende del reporte nacional;
Perú tuvo reportes muy irregulares al final del período.

    python src/p7_vacunacion.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr, linregress

sys.path.insert(0, str(Path(__file__).parent))
from modelos import DIAS_CORRECCION, DIAS_CORRECCION_PAIS

DW = Path("data/dw/covid.duckdb")
OWID = Path("data/raw/owid_vaccinations.csv")
PAISES = ["CHL", "PER", "USA", "BRA"]
NOMBRES = {"CHL": "Chile", "PER": "Perú", "USA": "EE.UU.", "BRA": "Brasil"}
ARTEFACTOS_PAIS = DIAS_CORRECCION_PAIS


def fallecidos_semana(pais: str) -> pd.Series:
    con = duckdb.connect(str(DW), read_only=True)
    df = con.execute(
        "SELECT fecha, deaths, poblacion FROM v_nacional_dia "
        "WHERE pais_iso3 = ? ORDER BY fecha", [pais]).df()
    con.close()
    df["fecha"] = pd.to_datetime(df["fecha"])
    n = df.set_index("fecha")["deaths"].diff().clip(lower=0)
    for dia in DIAS_CORRECCION:
        if dia in n.index:
            n.loc[dia] = np.nan
    for dia in ARTEFACTOS_PAIS.get(pais, []):
        if dia in n.index:
            n.loc[dia] = np.nan
    if (n == 0).sum() / len(n) < 0.2:
        n = n.mask(n == 0)
    pob = float(df["poblacion"].dropna().iloc[-1])
    return (1e5 * n / pob).resample("W").sum()


def vacunacion_semana(pais: str) -> pd.Series:
    v = pd.read_csv(OWID, usecols=["iso_code", "date",
                                   "people_fully_vaccinated_per_hundred"])
    v = v[v["iso_code"] == pais].copy()
    v["date"] = pd.to_datetime(v["date"])
    v = v.set_index("date")["people_fully_vaccinated_per_hundred"].sort_index()
    v = v.resample("W").last().ffill().interpolate()
    return v


def analizar_pais(pais: str) -> dict:
    muertes = fallecidos_semana(pais)
    vac = vacunacion_semana(pais)
    indice = muertes.index.intersection(vac.index)
    # robustez: usar primero semanas donde hay dato de vacunación o rellenar 0 al inicio
    vac = vac.reindex(muertes.index).bfill().fillna(0.0)
    out = {"pais": pais}
    rhos = []
    for lag in range(0, 9):
        x = vac
        y = muertes.shift(-lag)
        mask = x.notna() & y.notna()
        rho, p = spearmanr(x[mask], y[mask])
        rhos.append((lag, round(rho, 3), round(p, 4)))
    out["spearman_por_lag"] = rhos
    below = muertes[vac < 50]
    above = muertes[vac >= 50]
    out["fallecidos_100k_sem_antes_50pct"] = round(float(below.mean()), 2) if len(below) else None
    out["fallecidos_100k_sem_despues_50pct"] = round(float(above.mean()), 2) if len(above) else None
    out["semanas_antes_50pct"] = int((vac < 50).sum())
    out["semanas_despues_50pct"] = int((vac >= 50).sum())
    # Estrato "era de alta vacunación" (semanas con >= 50 % cubierto):
    # controla groseramente la tendencia compartida.
    mask_alta = vac >= 50
    rhos_alta = []
    for lag in range(0, 9):
        x = vac[mask_alta]
        y = muertes.shift(-lag)[mask_alta]
        mask = x.notna() & y.notna()
        if mask.sum() > 20:
            rho, _ = spearmanr(x[mask], y[mask])
            rhos_alta.append((lag, round(rho, 3)))
    out["spearman_era_alta_vacunacion"] = rhos_alta
    return out


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    resultados = []
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    for ax, pais in zip(axes.ravel(), PAISES):
        r = analizar_pais(pais)
        resultados.append(r)
        muertes = fallecidos_semana(pais)
        vac = vacunacion_semana(pais).reindex(muertes.index).bfill().fillna(0.0)
        y = muertes.shift(-4)  # lag de 4 semanas
        mask = vac.notna() & y.notna()
        ax.scatter(vac[mask], y[mask], s=18, alpha=0.6, color="#4a6fa5", edgecolor="#233", linewidth=0.4)
        if mask.sum() > 10:
            z = np.polyfit(vac[mask], y[mask], 1)
            xs = np.linspace(0, 100, 100)
            ax.plot(xs, np.polyval(z, xs), color="#b3543f", linestyle="--", linewidth=2)
        ax.set_xlabel("Población con vacunación completa, % (OWID)")
        ax.set_ylabel("Fallecidos por 100.000 hab., 4 semanas después")
        ax.set_title(NOMBRES[pais])
        ax.grid(alpha=0.25)
    fig.suptitle("Cobertura de vacunación vs mortalidad reportada 4 semanas después", fontsize=11)
    plt.tight_layout()
    plt.savefig("reports/fig_p7_vacunacion.png", dpi=150)
    plt.close()

    for r in resultados:
        print("=" * 60, NOMBRES[r["pais"]])
        print(f"Fall./100k/sem antes de 50 % vacunados:  {r['fallecidos_100k_sem_antes_50pct']}")
        print(f"Fall./100k/sem después de 50 % vacunados: {r['fallecidos_100k_sem_despues_50pct']}")
        print(f"Semanas antes/después del 50 %: {r['semanas_antes_50pct']} / {r['semanas_despues_50pct']}")
        print("Spearman cobertura(t) ~ fallecidos(t+lag):")
        for lag, rho, p in r["spearman_por_lag"]:
            print(f"   lag {lag} sem: rho = {rho:+.3f}  (p = {p})")
        print("Spearman dentro de la era con >= 50 % vacunado:")
        for lag, rho in r["spearman_era_alta_vacunacion"]:
            print(f"   lag {lag} sem: rho = {rho:+.3f}")
    print("\nEscrito reports/fig_p7_vacunacion.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
