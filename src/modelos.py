"""R5 — Modelos, pronóstico y alerta temprana (usados también por el tablero).

Contrato para el desafío en vivo del Comité:

    pronosticar(territorio, fecha_corte, horizonte=14)
    alerta(territorio, fecha)

`territorio` es un `pais_iso3` (p. ej. `"CHL"`) o una `territorio_key` del
DW (p. ej. `"Metropolitana, Chile"`). Ambas funciones SOLO usan datos
anteriores o iguales a la fecha pedida — nunca posteriores.

Decisiones documentadas:

- La serie de nuevos casos usada en ajuste y predicción usa
  `max(new_confirmed, 0)` (los retrocesos por corrección no son "casos
  negativos") y EXCLUYE los días de corrección masiva listados en
  `DIAS_CORRECCION` (2022-05-23: 1,1 M de casos retirados a nivel global;
  Chile 2022-03-21 y Perú 2021-06-02: artefactos de transición con total
  nacional casi conservado; Colombia 2020-11-02 idem). Esos días siguen en
  las cifras acumuladas y en las tasas reportadas; solo se apartan del
  ajuste y de la evaluación para no envenenar el modelo.
- Modelo base: promedio de la media móvil de 7 días, proyectado plano.
- Segundo modelo: Holt (suavizamiento exponencial con tendencia amortiguada)
  vía statsmodels.
- MAPE con denominador `max(actual, 1)` para no dividir por cero.
- `alerta(territorio, fecha)`: variación semanal de la incidencia =
  MA7(new_confirmed) / MA7 de 7 días antes − 1. Activa si ≥ `UMBRAL` (0,30)
  y la incidencia MA7 ≥ `PISO` casos/100.000/día. Evaluada en la historia
  de Chile; la evaluación operativa (anticipación y falsas alarmas) está en
  `evaluar_alerta()` y se reporta en el informe.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing

DW = Path("data/dw/covid.duckdb")

DIAS_CORRECCION = pd.to_datetime(["2022-05-23"])
DIAS_CORRECCION_PAIS: dict[str, list[pd.Timestamp]] = {
    # Colombia 2020-11-02: corrección de un día (−302.844 casos; el total
    # nacional se conservó porque las regiones absorbieron el ajuste).
    # Perú 2021-06-02: misma clase (+115.600 en fila «Unknown, Peru»; total conservado).
    # Chile 2022-03-21: +11.447 fallecidos por revisión del registro (sí se
    # sumó al total nacional; se excluye del ajuste y de la CFR).
    # Chile 2020-06-17: +36.179 casos rezagados insertados en un día (el «ajuste del 17 de junio»).
    # Chile 2020-07-17: +1.057 fallecidos en un día (misma clase de inserción).
    "COL": [pd.Timestamp("2020-11-02")],
    "PER": [pd.Timestamp("2021-06-02")],
    "CHL": [pd.Timestamp("2020-06-17"), pd.Timestamp("2020-07-17"),
            pd.Timestamp("2022-03-21")],
}
UMBRAL = 0.30
PISO_100K = 6.0


class SerieNoDisponible(LookupError):
    pass


def _conexion(dw: Path) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(dw), read_only=True)


def _clave(territorio: str) -> tuple[str, str]:
    """Devuelve ('pais', iso3) o ('region', territorio_key)."""
    territorio = territorio.strip()
    if len(territorio) == 3 and territorio.upper() == territorio:
        return "pais", territorio
    return "region", territorio


def serie_diaria(territorio: str, dw: Path = DW, hasta: pd.Timestamp | None = None) -> pd.DataFrame:
    """Serie diaria (casos, fallecidos, población) SOLO hasta `hasta` (incluida)."""
    tipo, clave = _clave(territorio)
    filtro_fecha = "AND fecha <= ?" if hasta is not None else ""
    params = [clave] + ([hasta] if hasta is not None else [])
    with _conexion(dw) as con:
        if tipo == "pais":
            df = con.execute(f"""
                SELECT fecha, confirmed, deaths, poblacion, 'pais' AS granularidad
                FROM v_nacional_dia WHERE pais_iso3 = ? {filtro_fecha} ORDER BY fecha
            """, params).df()
        else:
            df = con.execute(f"""
                SELECT f.fecha, f.confirmed, f.deaths, t.population AS poblacion,
                       'region' AS granularidad
                FROM fact_covid f JOIN dim_territorio t USING (territorio_id)
                WHERE t.territorio_key = ? {filtro_fecha} ORDER BY f.fecha
            """, params).df()
            if df.empty:
                df = con.execute(f"""
                    SELECT f.fecha, f.confirmed, f.deaths, t.population AS poblacion,
                           'region' AS granularidad
                    FROM fact_covid f JOIN dim_territorio t USING (territorio_id)
                    WHERE replace(t.territorio_key, ' ', '') = replace(?, ' ', '')
                      {filtro_fecha} ORDER BY f.fecha
                """, params).df()
    if df.empty:
        raise SerieNoDisponible(f"No hay serie para {territorio!r}")
    df["fecha"] = pd.to_datetime(df["fecha"])
    df = df.set_index("fecha").asfreq("D")
    return df


def nuevos_limpios(df: pd.DataFrame, territorio: str) -> pd.Series:
    """new cases por día; artefactos de corrección excluidos; resto >= 0.

    Días con acumulado exactamente sin cambio se tratan como HUECO de reporte
    (0 casos en un país que reporta >0 a diario es un artefacto de no-
    actualización), no como cero real; solo si esos días son minoría (<20 %)
    de la serie, para no inventar datos en países que sí reportan cero.
    Los huecos quedan NaN y los consumidores interpolan para ajustar/evaluar.
    """
    n = df["confirmed"].diff()
    n = n.clip(lower=0)
    for dia in DIAS_CORRECCION:
        if dia in n.index:
            n.loc[dia] = np.nan
    for dia in DIAS_CORRECCION_PAIS.get(territorio.upper(), []):
        if dia in n.index:
            n.loc[dia] = np.nan
    if n.notna().mean() > 0:
        ceros = (n == 0).sum()
        if ceros / len(n) < 0.2:
            n = n.mask(n == 0)
    return n


def _metricas(actual: pd.Series, predicho: np.ndarray) -> dict[str, float]:
    a = np.asarray(actual, dtype=float)
    f = np.asarray(predicho, dtype=float)
    mae = float(np.mean(np.abs(a - f)))
    mape = float(np.mean(np.abs(a - f) / np.maximum(a, 1.0)) * 100)
    return {"mae": round(mae, 2), "mape": round(mape, 2)}


def pronosticar(territorio: str, fecha_corte, horizonte: int = 14) -> pd.DataFrame:
    """Pronostica `horizonte` días desde el día siguiente a `fecha_corte`.

    Devuelve un DataFrame con columnas `fecha`, `base_ma7`, `holt`,
    `limite_inferior`/`limite_superior` (intervalo 80 % del Holt).
    """
    fecha_corte = pd.Timestamp(fecha_corte)
    df = serie_diaria(territorio, hasta=fecha_corte)
    n = nuevos_limpios(df, territorio).astype("float64")
    n_fit = n.asfreq("D").interpolate(limit_direction="both")  # solo para ajuste; no altera la serie reportada

    base = float(n_fit.tail(7).mean())
    base_pred = np.full(horizonte, base)

    try:
        modelo = ExponentialSmoothing(n_fit, trend="add", damped_trend=True,
                                      seasonal=None, initialization_method="estimated").fit(optimized=True)
        holt_pred = np.asarray(modelo.forecast(horizonte), dtype=float)
        resid_std = float(np.std(modelo.resid))
    except Exception:
        holt_pred = base_pred.copy()
        resid_std = float(n_fit.tail(28).std() or 1.0)

    fechas = pd.date_range(fecha_corte + pd.Timedelta(days=1), periods=horizonte, freq="D")
    return pd.DataFrame({
        "fecha": fechas,
        "base_ma7": np.round(base_pred, 2),
        "holt": np.round(np.clip(holt_pred, 0, None), 2),
        "limite_inferior": np.round(np.clip(holt_pred - 1.282 * resid_std, 0, None), 2),
        "limite_superior": np.round(np.clip(holt_pred + 1.282 * resid_std, 0, None), 2),
    })


def alerta(territorio: str, fecha) -> dict:
    """Estado de la alerta temprana en `fecha` (solo datos hasta esa fecha)."""
    fecha = pd.Timestamp(fecha)
    df = serie_diaria(territorio, hasta=fecha)
    n = nuevos_limpios(df, territorio).asfreq("D")
    m7 = n.rolling(7, min_periods=4).mean()
    prev = m7.shift(7)
    var = (m7 / prev - 1) if prev is not None else pd.Series(dtype=float)
    poblacion = float(df["poblacion"].dropna().iloc[-1]) if df["poblacion"].notna().any() else np.nan
    incidencia_100k = 1e5 * m7 / poblacion if poblacion == poblacion else np.nan
    var_hoy = float(var.iloc[-1]) if pd.notna(var.iloc[-1]) else 0.0
    inc_hoy = float(incidencia_100k.iloc[-1]) if pd.notna(incidencia_100k.iloc[-1]) else 0.0
    activa = (var_hoy >= UMBRAL) and (inc_hoy >= PISO_100K)
    return {
        "territorio": territorio,
        "fecha": fecha.date().isoformat(),
        "activa": bool(activa),
        "variacion_semanal": round(var_hoy, 3),
        "incidencia_ma7_por_100k": round(inc_hoy, 2),
        "umbral_variacion": UMBRAL,
        "piso_incidencia_por_100k": PISO_100K,
    }


def backtest(territorio: str, cortes: list[str], horizonte: int = 14) -> pd.DataFrame:
    """Evalúa ambos modelos en fechas de corte (MAE y MAPE)."""
    filas = []
    for corte in cortes:
        fc = pronosticar(territorio, corte, horizonte)
        real = serie_diaria(territorio, hasta=pd.Timestamp(corte) + pd.Timedelta(days=horizonte))
        n_real = nuevos_limpios(real, territorio).astype("float64").reindex(fc["fecha"]).interpolate(limit_direction="both")
        filas.append({
            "corte": corte,
            **{f"base_{k}": v for k, v in _metricas(n_real, fc["base_ma7"]).items()},
            **{f"holt_{k}": v for k, v in _metricas(n_real, fc["holt"]).items()},
        })
    return pd.DataFrame(filas)


def evaluar_alerta(territorio: str, olas_fechas: list[str],
                   ventana_deteccion: int = 100,
                   ventana_falsa: int = 42,
                   alza_falsa: float = 0.40) -> dict:
    """Evalúa la alerta en la historia: detección, anticipación y falsas alarmas.

    Protocolo (documentado en el informe):

    - Ola: pico de MA7 (en Chile: 2020-06-17, 2021-04-14, 2022-02-13,
      2022-06-17, 2022-11-10 — 2022 fue una ola prolongada con subpicos).
    - Detección/anticipación: días entre la PRIMERA activación de alerta
      previa al pico (búsqueda hacia atrás hasta `ventana_deteccion` días)
      y el pico. Las activaciones en el día del pico cuentan 0 días.
    - Falsa alarma: activación sin ola en los `ventana_deteccion` días
      siguientes Y sin alza ≥ `alza_falsa` de MA7 en `ventana_falsa` días.
    - Activaciones con alza real pero sin ola mayor asociada (p. ej.
      2021-10-17, 2023-02-25) se reportan aparte como «alzas menores».
    """
    df = serie_diaria(territorio, hasta=pd.Timestamp("2023-03-09"))
    n = nuevos_limpios(df, territorio).asfreq("D")
    m7 = n.rolling(7, min_periods=4).mean()
    poblacion = float(df["poblacion"].dropna().iloc[-1])
    inc = 1e5 * m7 / poblacion
    var = m7 / m7.shift(7) - 1
    activa = (var >= UMBRAL) & (inc >= PISO_100K)
    disparos = list((activa.ne(activa.shift(fill_value=False)) & activa)[lambda s: s].index)

    olas = [pd.Timestamp(o) for o in olas_fechas]
    asign: dict[pd.Timestamp, pd.Timestamp | None] = {}
    for d in disparos:
        futuras = [o for o in olas if 0 <= (o - d).days <= ventana_deteccion]
        asign[d] = min(futuras, key=lambda o: (o - d).days) if futuras else None

    por_ola: dict[str, dict] = {}
    for ola in olas:
        ds = [d for d, o in asign.items() if o == ola]
        por_ola[ola.date().isoformat()] = {
            "primera_alerta": min(ds).date().isoformat() if ds else None,
            "anticipacion_dias": int((ola - min(ds)).days) if ds else None,
            "activaciones": len(ds),
        }

    def alza_42d(d: pd.Timestamp) -> float:
        futuro = m7.loc[d:d + pd.Timedelta(days=ventana_falsa)]
        if len(futuro) == 0 or m7.loc[d] <= 0:
            return 0.0
        return float(futuro.max() / m7.loc[d] - 1)

    alzas_menores = []
    falsas = []
    for d, o in asign.items():
        if o is None:
            (alzas_menores if alza_42d(d) >= alza_falsa else falsas).append(d)

    return {
        "territorio": territorio,
        "activaciones": len(disparos),
        "olas": por_ola,
        "falsas_alarmas": [d.date().isoformat() for d in falsas],
        "alzas_menores_sin_ola_mayor": [d.date().isoformat() for d in alzas_menores],
        "detalle": [
            {"fecha": d.date().isoformat(),
             "ma7": round(float(m7.loc[d]), 1),
             "alza_42d_pct": round(100 * alza_42d(d), 1),
             "ola": (o.date().isoformat() if o else None)}
            for d, o in asign.items()
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("comando", choices=["pronosticar", "alerta", "backtest"])
    parser.add_argument("territorio")
    parser.add_argument("--fecha-corte", default=None)
    parser.add_argument("--horizonte", type=int, default=14)
    parser.add_argument("--cortes", default="2020-09-15,2021-03-15,2021-12-01")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if args.comando == "pronosticar":
        if not args.fecha_corte:
            parser.error("pronosticar requiere --fecha-corte YYYY-MM-DD")
        try:
            print(pronosticar(args.territorio, args.fecha_corte, args.horizonte).to_string(index=False))
        except SerieNoDisponible as error:
            print(f"Error: {error}", file=sys.stderr)
            return 2
    elif args.comando == "alerta":
        if not args.fecha_corte:
            parser.error("alerta requiere --fecha-corte YYYY-MM-DD")
        try:
            for k, v in alerta(args.territorio, args.fecha_corte).items():
                print(f"{k}: {v}")
        except SerieNoDisponible as error:
            print(f"Error: {error}", file=sys.stderr)
            return 2
    elif args.comando == "backtest":
        cortes = [c.strip() for c in args.cortes.split(",") if c.strip()]
        print(backtest(args.territorio, cortes, args.horizonte).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
