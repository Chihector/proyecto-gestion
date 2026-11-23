"""R7 — Tablero «Sala de crisis COVID-19» (Streamlit + DuckDB).

    .venv/Scripts/python.exe -m streamlit run dashboard/app.py

Secciones:

- Selectores: territorio (país del mundo o región de Chile), fecha de corte
  (<= 2023-03-09) y supresion de conteos pequeños.
- Pestañas: «Chile y regiones», «Mundo», «Desafío en vivo» (ejecuta
  pronosticar(territorio, fecha_corte, 14) y el estado de la alerta a esa
  fecha — exactamente lo que el Comité pide en la sesión en vivo), y
  «Calidad y advertencias».
- Advertencias visibles: fecha de corte, correcciones marcadas, discontinuidad
  de JHU de recuperados, y supresion de conteos 1–4 (regla R6).
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from modelos import alerta, pronosticar  # noqa: E402

DW = ROOT / "data" / "dw" / "covid.duckdb"
FECHA_MAX = pd.Timestamp("2023-03-09")
UMBRAL_ALERTA = 0.30

st.set_page_config(page_title="Sala de crisis COVID-19", page_icon="🦠", layout="wide")


@st.cache_resource
def conectar():
    return duckdb.connect(str(DW), read_only=True)


NOMBRES_PAIS = {
    "ARG": "Argentina", "AUS": "Australia", "AUT": "Austria", "BEL": "Bélgica",
    "BGR": "Bulgaria", "BOL": "Bolivia", "BRA": "Brasil", "CAN": "Canadá",
    "CHL": "Chile", "CHN": "China", "COL": "Colombia", "CUB": "Cuba",
    "CZE": "Chequia", "DEU": "Alemania", "DNK": "Dinamarca", "ECU": "Ecuador",
    "ESP": "España", "FRA": "Francia", "GBR": "Reino Unido", "GRC": "Grecia",
    "HUN": "Hungría", "IND": "India", "IRL": "Irlanda", "ITA": "Italia",
    "JPN": "Japón", "KOR": "Corea del Sur", "MEX": "México", "NLD": "Países Bajos",
    "NOR": "Noruega", "NZL": "Nueva Zelanda", "PER": "Perú", "POL": "Polonia",
    "PRT": "Portugal", "ROU": "Rumanía", "RUS": "Rusia", "SVK": "Eslovaquia",
    "SWE": "Suecia", "TUR": "Turquía", "UKR": "Ucrania", "URY": "Uruguay",
    "USA": "EE.UU.", "VEN": "Venezuela", "ZAF": "Sudáfrica",
}


@st.cache_data(ttl=600)
def paises() -> list[tuple[str, str]]:
    con = conectar()
    filas = con.execute(
        "SELECT DISTINCT pais_iso3 FROM dim_territorio WHERE pais_iso3 IS NOT NULL ORDER BY 1"
    ).fetchall()
    return [(p[0], NOMBRES_PAIS.get(p[0], p[0])) for p in filas]


@st.cache_data(ttl=600)
def regiones_chile() -> list[str]:
    con = conectar()
    filas = con.execute("""
        SELECT territorio_key FROM dim_territorio
        WHERE pais_iso3 = 'CHL' AND nivel <> 'pais'
        ORDER BY 1
    """).fetchall()
    return [f[0] for f in filas]


@st.cache_data(ttl=600)
def serie_nacional(pais: str, hasta) -> pd.DataFrame:
    con = conectar()
    df = con.execute("""
        SELECT fecha, confirmed, deaths, new_confirmed, new_deaths,
               poblacion, granularidad
        FROM v_nacional_dia
        WHERE pais_iso3 = ? AND fecha <= ?
        ORDER BY fecha
    """, [pais, hasta]).df()
    df["fecha"] = pd.to_datetime(df["fecha"])
    return df.set_index("fecha")


@st.cache_data(ttl=600)
def serie_region(territorio_key: str, hasta) -> pd.DataFrame:
    con = conectar()
    df = con.execute("""
        SELECT f.fecha, f.confirmed, f.deaths, f.new_confirmed, f.new_deaths,
               t.population AS poblacion
        FROM fact_covid f JOIN dim_territorio t USING (territorio_id)
        WHERE t.territorio_key = ? AND f.fecha <= ?
        ORDER BY f.fecha
    """, [territorio_key, hasta]).df()
    df["fecha"] = pd.to_datetime(df["fecha"])
    return df.set_index("fecha")


@st.cache_data(ttl=600)
def mapa_mundial(fecha) -> pd.DataFrame:
    con = conectar()
    # nivel='pais' si existe (sin doble conteo); si no, se suman subnacionales.
    return con.execute("""
        WITH nacional AS (
            SELECT pais_iso3,
                   max(confirmed) AS confirmed,
                   max(deaths)    AS deaths,
                   max(poblacion) AS poblacion,
                   sum(CASE WHEN new_confirmed >= 0 THEN new_confirmed ELSE 0 END) AS casos_periodo
            FROM v_nacional_dia
            WHERE fecha <= ? AND pais_iso3 IS NOT NULL
            GROUP BY 1
        ),
        geo AS (
            SELECT pais_iso3,
                   coalesce(max(CASE WHEN nivel = 'pais' THEN lat END), avg(lat)) AS lat,
                   coalesce(max(CASE WHEN nivel = 'pais' THEN long END), avg(long)) AS long
            FROM dim_territorio
            WHERE pais_iso3 IS NOT NULL
            GROUP BY 1
        )
        SELECT n.*, g.lat, g.long
        FROM nacional n JOIN geo g USING (pais_iso3)
    """, [fecha]).df()


@st.cache_data(ttl=600)
def mapa_chile(fecha) -> pd.DataFrame:
    con = conectar()
    return con.execute("""
        SELECT t.territorio_key AS region, t.lat, t.long, t.population,
               max(f.confirmed) AS confirmed, max(f.deaths) AS deaths,
               sum(CASE WHEN f.new_confirmed >= 0 THEN f.new_confirmed ELSE 0 END) AS casos_periodo
        FROM fact_covid f JOIN dim_territorio t USING (territorio_id)
        WHERE f.fecha <= ? AND t.pais_iso3 = 'CHL' AND t.nivel <> 'pais'
        GROUP BY 1, 2, 3, 4
    """, [fecha]).df()


def supresion_txt(valor):
    """R6: los conteos 1–4 se muestran como «<5»; el resto, con separador de miles."""
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return str(valor)
    if 1 <= v <= 4:
        return "<5"
    return f"{v:,.0f}"


def curva_ma7(nuevos: pd.Series) -> pd.Series:
    return nuevos.clip(lower=0).rolling(7, min_periods=1).mean()


def kpi(columna, etiqueta, valor, ayuda=None):
    columna.metric(etiqueta, valor, help=ayuda)


def aplicacion():
    st.title("Sala de crisis COVID-19")
    st.caption(
        f"Datos JHU CSSE hasta **{FECHA_MAX.date()}** · Elaborado el 4-nov-2026 · "
        "Las cifras acumuladas retroceden por correcciones de JHU: se marcan, no se ocultan."
    )

    # ---------- Sidebar ----------
    st.sidebar.header("Selección")
    fecha_corte = st.sidebar.date_input(
        "Fecha de corte", value=FECHA_MAX.date(),
        min_value=pd.Timestamp("2020-01-22").date(), max_value=FECHA_MAX.date(),
        help="Todo lo mostrado usa solo datos hasta esta fecha.",
    )
    fecha_corte = pd.Timestamp(fecha_corte)
    nivel = st.sidebar.radio("Nivel", ["País (mundo)", "Región de Chile"], horizontal=True)
    if nivel == "País (mundo)":
        opciones = {f"{p} — {nombre}": p for p, nombre in paises()}
        territorio = opciones[st.sidebar.selectbox("Territorio", list(opciones), index=list(opciones).index("CHL — Chile"))]
    else:
        territorio = st.sidebar.selectbox("Región de Chile", regiones_chile())
    suprimir = st.sidebar.checkbox("Supresión de conteos 1–4 (R6)", value=True)
    st.sidebar.caption(
        "Regla de divulgación: los conteos entre 1 y 4 se muestran como «<5». "
        "No se muestran microdatos: todo es agregado."
    )

    tab_chile, tab_mundo, tab_desafio, tab_calidad = st.tabs(
        ["Chile y regiones", "Mundo", "Desafío en vivo", "Calidad y advertencias"])

    serie = (serie_nacional(territorio, fecha_corte) if nivel == "País (mundo)"
             else serie_region(territorio, fecha_corte))
    titulo = territorio if nivel == "País (mundo)" else territorio

    # ---------- Tab Chile y regiones ----------
    with tab_chile:
        st.subheader(f"{titulo} — situación al {fecha_corte.date()}")
        if serie.empty:
            st.warning("Sin datos para este territorio en el rango.")
        else:
            ult = serie.iloc[-1]
            pob = ult["poblacion"] if ult["poblacion"] and not pd.isna(ult["poblacion"]) else None
            c1, c2, c3, c4, c5 = st.columns(5)
            kpi(c1, "Casos acumulados", f"{ult['confirmed']:,.0f}")
            kpi(c2, "Fallecidos", f"{ult['deaths']:,.0f}")
            if pob:
                kpi(c3, "Casos por 100.000 hab.", f"{1e5 * ult['confirmed'] / pob:,.0f}")
                kpi(c4, "Fallecidos por 100.000 hab.", f"{1e5 * ult['deaths'] / pob:,.1f}")
            else:
                c3.metric("Casos por 100.000 hab.", "s/d (sin población)")
                c4.metric("Fallecidos por 100.000 hab.", "s/d (sin población)")
            kpi(c5, "Letalidad aparente", f"{100 * ult['deaths'] / max(ult['confirmed'], 1):.2f} %",
                ayuda="Fallecidos/casos confirmados. Depende del testeo: úsese con cautela.")

            n = serie["new_confirmed"].clip(lower=0).rolling(7, min_periods=1).mean()
            d = serie["new_deaths"].clip(lower=0).rolling(7, min_periods=1).mean()
            fig = go.Figure()
            fig.add_scatter(x=n.index, y=n, name="Casos MA7", line=dict(color="#6d28d9", width=2.4))
            fig.add_scatter(x=d.index, y=d, name="Fallecidos MA7 (eje der.)",
                            line=dict(color="#b3543f", width=1.8, dash="dot"), yaxis="y2")
            fig.update_layout(
                title="Casos y fallecidos por día (MA7)",
                yaxis=dict(title="Casos nuevos"),
                yaxis2=dict(title="Fallecidos nuevos", overlaying="y", side="right", showgrid=False),
                hovermode="x unified", height=460, margin=dict(l=10, r=10, t=60),
                legend=dict(orientation="h", y=-0.15))
            st.plotly_chart(fig, width="stretch")

            filas = serie.tail(10).copy()
            for col in ("confirmed", "deaths"):
                filas[col] = filas[col].map(lambda v: f"{v:,.0f}")
            if suprimir:
                filas["new_confirmed"] = filas["new_confirmed"].map(supresion_txt)
                filas["new_deaths"] = filas["new_deaths"].map(supresion_txt)
            else:
                filas["new_confirmed"] = filas["new_confirmed"].map(lambda v: f"{v:,.0f}")
                filas["new_deaths"] = filas["new_deaths"].map(lambda v: f"{v:,.0f}")
            st.dataframe(filas[["confirmed", "deaths", "new_confirmed", "new_deaths"]],
                         width="stretch")
            st.caption("Los conteos «<5» están suprimidos (R6). Fallecidos MA7 usa la escala derecha.")

    # ---------- Tab Mundo ----------
    with tab_mundo:
        st.subheader(f"Panorama mundial al {fecha_corte.date()}")
        mapa = mapa_mundial(fecha_corte)
        mapa = mapa.dropna(subset=["lat", "long"])
        mapa["casos_100k"] = 1e5 * mapa["casos_periodo"] / mapa["poblacion"].replace(0, np.nan)
        fig = go.Figure(go.Scattergeo(
            lon=mapa["long"], lat=mapa["lat"],
            text=[f"{p}: {c:,.0f} casos/100k" for p, c in zip(mapa["pais_iso3"], mapa["casos_100k"])],
            mode="markers",
            marker=dict(size=np.sqrt(mapa["casos_periodo"].clip(lower=1)) / 220 + 4,
                        color=mapa["casos_100k"], colorscale="YlOrRd",
                        colorbar=dict(title="Casos/100k"), line=dict(width=0.5, color="#333")),
        ))
        fig.update_geos(scope="world", projection_type="natural earth")
        fig.update_layout(height=520, margin=dict(l=0, r=0, t=30), title="Burbujas: incidencia del período seleccionado")
        st.plotly_chart(fig, width="stretch")

        rank = mapa.sort_values("casos_periodo", ascending=False).head(15).copy()
        if suprimir:
            rank["casos_periodo"] = rank["casos_periodo"].map(supresion_txt)
        else:
            rank["casos_periodo"] = rank["casos_periodo"].map(lambda v: f"{v:,.0f}")
        rank["poblacion"] = rank["poblacion"].map(lambda v: f"{v:,.0f}" if pd.notna(v) else "s/d")
        st.dataframe(rank[["pais_iso3", "casos_periodo", "poblacion"]], width="stretch")

    # ---------- Tab Desafío en vivo ----------
    with tab_desafio:
        st.subheader("Desafío en vivo — ejecutar pronosticar(territorio, fecha_corte, 14)")
        st.caption(
            "Replica el formato del Comité: elige un territorio y una fecha de corte; "
            "el modelo usa SOLO datos hasta el corte y se compara con lo que ocurrió."
        )
        if nivel == "País (mundo)":
            territorio_desafio = territorio
        else:
            territorio_desafio = territorio
        st.write(f"Territorio: **{territorio_desafio}** · Fecha de corte: **{fecha_corte.date()}** · Horizonte: 14 días")

        estado = alerta(territorio_desafio, fecha_corte)
        st.metric("Alerta temprana a la fecha",
                  "ACTIVA" if estado["activa"] else "INACTIVA",
                  help=f"Variación semanal MA7 = {estado['variacion_semanal']:+.1%} "
                       f"(umbral +{UMBRAL_ALERTA:.0%}); incidencia MA7 = "
                       f"{estado['incidencia_ma7_por_100k']:.1f}/100.000 (piso 6).")
        fc = pronosticar(territorio_desafio, fecha_corte, 14)
        hist = serie_nacional(territorio_desafio, fecha_corte) if nivel == "País (mundo)" else serie_region(territorio_desafio, fecha_corte)
        hist = hist.tail(120)
        fig = go.Figure()
        fig.add_scatter(x=hist.index, y=hist["new_confirmed"].clip(lower=0).rolling(7, min_periods=1).mean(),
                        name="Realidad MA7 (últimos 120 días)", line=dict(color="#333"))
        fig.add_scatter(x=fc["fecha"], y=fc["holt"], name="Pronóstico Holt", line=dict(color="#b3543f", dash="dash", width=2.4))
        fig.add_scatter(x=fc["fecha"], y=fc["base_ma7"], name="Base (media móvil 7d)", line=dict(color="#4a6fa5", dash="dot"))
        fig.add_scatter(x=pd.concat([fc["fecha"], fc["fecha"][::-1]]),
                        y=pd.concat([fc["limite_superior"], fc["limite_inferior"][::-1]]),
                        fill="toself", fillcolor="rgba(179,84,63,0.15)",
                        line=dict(color="rgba(0,0,0,0)"), name="Intervalo 80 %")
        fig.update_layout(height=420, hovermode="x unified", margin=dict(l=10, r=10, t=30))
        st.plotly_chart(fig, width="stretch")

        despues = serie_nacional(territorio_desafio, FECHA_MAX) if nivel == "País (mundo)" else serie_region(territorio_desafio, FECHA_MAX)
        despues = despues.loc[despues.index > fecha_corte].head(14)
        if len(despues):
            mae = float((despues["new_confirmed"].clip(lower=0) - fc["holt"].iloc[:len(despues)].values).abs().mean())
            st.info(f"Comparando con lo ocurrido en los {len(despues)} días posteriores: MAE Holt = {mae:,.0f} casos/día.")
        else:
            st.info("La fecha de corte es la última disponible: no hay «después» con qué comparar (correcta ausencia de datos posteriores).")

    # ---------- Tab Calidad y advertencias ----------
    with tab_calidad:
        st.subheader("Advertencias de calidad y límites de interpretación")
        st.markdown(
            """
- **Fecha de corte de los datos:** 2023-03-09 (JHU archivó el repositorio). No hay información posterior.
- **Correcciones masivas marcadas, no ocultas:** el 2022-05-23 JHU retiró 1.097.163 casos a nivel global
  (Chile −9.827). Chile añadió +36.179 casos el 2020-06-17 y +1.057 fallecidos el 2020-07-17 («actas»).
  El DW las conserva con bandera `retroceso_*`; los promedios y modelos las excluyen.
- **JHU dejó de publicar `recovered`/`active`** desde 2021-03 (~100 % nulos desde 2021-10). No se usan.
- **Fallecidos > casos** en 10.777 filas: Reino Unido jun-2020 (fallecidos sin casos vinculados) y la
  reconciliación de Perú (jun-2021). Se marcan; no se corrigen (imputar es inventar).
- **Letalidad aparente** depende del testeo: a más detección de casos leves, menor CFR. Las comparaciones
  entre países exigen cautela; se prefiere fallecidos por 100.000.
- **Granularidad:** EE.UU. y otros países reportan a nivel de condado; Chile desde el 2020-05-20, por sus
  16 regiones (+ `Unknown`). Nivel país ≠ nivel región: no se mezclan.
- **Entidades no-país** (Diamond Princess, MS Zaandam, Juegos Olímpicos, Antártida) se excluyen de
  comparaciones entre países.
- **Supresión (R6):** conteos entre 1 y 4 se muestran «<5»; los 317 condados de EE.UU. con <5.000
  habitantes no aportan a tablas de detalle. Todo lo mostrado es agregado, no microdato.
- **Índice de calidad por país:** ver `reports/calidad_pais.csv` y `docs/diccionario_datos.md`.
  Los países con peor índice concentran retrocesos/rezagos (EE.UU. 34,0; COL 64,1; PER 65,8).
- **Fuentes:** JHU CSSE (reportes, series y tabla UID) + OWID (vacunación, cruce ISO3; 196/212 países
  cruzan; sin datos: Eritrea, Antártida, microestados y territorios). JHU = datos agregados sin personas
  identificables.
            """
        )
        st.warning("Este tablero describe asociaciones; no establece causalidad. Las recomendaciones del informe derivan de los análisis, con sus límites explícitos.")


if __name__ == "__main__":
    aplicacion()
