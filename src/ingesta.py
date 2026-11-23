"""Ingesta de los reportes diarios de Johns Hopkins CSSE.

Unifica los cinco esquemas publicados entre 2020-01-22 y 2023-03-09:

- `etapa_1` (2020-01-22 a 2020-02-29): `Province/State, Country/Region, Last Update, Confirmed, Deaths, Recovered`.
- `etapa_2` (2020-03-01 a 2020-03-21): añade `Latitude, Longitude`.
- `etapa_3` (2020-03-22 a 2020-05-28): `FIPS, Admin2, Province_State, Country_Region, Last_Update, Lat, Long_, ..., Active, Combined_Key`.
- `etapa_4` (2020-05-29 a 2020-11-08): añade `Incidence_Rate, Case-Fatality_Ratio`.
- `etapa_5` (2020-11-09 a 2023-03-09): renombra las dos últimas a `Incident_Rate, Case_Fatality_Ratio`.

Reglas de la capa limpia:

- Los nombres quedan en `snake_case`; `report_date` viene del nombre del
  archivo (`MM-DD-YYYY.csv`) y `last_update` se conserva como el momento en
  que JHU actualizó la fila, nunca como fecha de observación.
- `etapa_esquema` indica el esquema detectado por el conjunto de columnas
  crudas (antes de renombrar). Si un archivo no encaja en ninguna etapa
  conocida, se marca `etapa_desconocida` y se reporta; nunca se fuerza el
  encaje.
- `clave_raw` replica la convención `province_state, country_region` de JHU
  (o `country_region` si no hay provincia): es la llave de linaje (con
  `report_date` identifica el archivo y la fila de origen) y del cruce con
  la tabla de identidad territorial.
- Las columnas que aún no existían en una etapa quedan nulas en la
  consolidación; no se inventan valores ni se imputan.
- `FIPS` se guarda como texto de 5 dígitos (con ceros a la izquierda);
  `confirmed`, `deaths`, `recovered` y `active` quedan como enteros nulos.

Uso:

    python src/ingesta.py                 # consolida todo y escribe Parquet + validación + medición
    python src/ingesta.py --desde 2020-03-01 --hasta 2020-04-30
    python src/ingesta.py --sin-escribir   # solo valida, no escribe Parquet
    python src/ingesta.py --sin-medicion   # omite el benchmark CSV vs Parquet
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date
from pathlib import Path

import pandas as pd

from territorios import construir_clave_cruda

RAW_DIR = Path("data/raw/daily_reports")
PARQUET_DESTINO = Path("data/clean/daily_reports.parquet")

RENOMBRAR = {
    "Province/State": "province_state", "Province_State": "province_state",
    "Country/Region": "country_region", "Country_Region": "country_region",
    "Last Update": "last_update", "Last_Update": "last_update",
    "Latitude": "lat", "Lat": "lat", "Longitude": "long", "Long_": "long",
    "Incidence_Rate": "incident_rate", "Incident_Rate": "incident_rate",
    "Case-Fatality_Ratio": "case_fatality_ratio",
    "Case_Fatality_Ratio": "case_fatality_ratio",
}

# Firmas crudas (tras snake_case y sin intercapas de renombrado) por etapa.
ETAPAS: dict[str, frozenset[str]] = {
    "etapa_1": frozenset(
        "province_state,country_region,last_update,confirmed,deaths,recovered".split(",")),
    "etapa_2": frozenset(
        "province_state,country_region,last_update,confirmed,deaths,recovered,latitude,longitude".split(",")),
    "etapa_3": frozenset(
        "fips,admin2,province_state,country_region,last_update,lat,long,"
        "confirmed,deaths,recovered,active,combined_key".split(",")),
    "etapa_4": frozenset(
        "fips,admin2,province_state,country_region,last_update,lat,long,"
        "confirmed,deaths,recovered,active,combined_key,incidence_rate,case_fatality_ratio".split(",")),
    "etapa_5": frozenset(
        "fips,admin2,province_state,country_region,last_update,lat,long,"
        "confirmed,deaths,recovered,active,combined_key,incident_rate,case_fatality_ratio".split(",")),
}
FIRMA_A_ETAPA = {firma: etapa for etapa, firma in ETAPAS.items()}

COLUMNAS_ENTERAS = ("confirmed", "deaths", "recovered", "active")
COLUMNAS_TEXTO = ("admin2", "province_state", "country_region", "combined_key")
COLUMNAS_NUMERICAS = ("lat", "long", "incident_rate", "case_fatality_ratio")


def normalizar_columnas(columnas) -> list[str]:
    """snake_case: minúsculas, sin tildes de formato, sin caracteres ajenos a [a-z0-9]."""
    indice = pd.Index(list(columnas))
    return list(
        indice.str.strip().str.lower()
        .str.replace(r"[^a-z0-9]+", "_", regex=True)
        .str.strip("_")
    )


def etapa_de(columnas_crudas) -> str:
    """Detecta la etapa por el conjunto de columnas crudas normalizadas."""
    return FIRMA_A_ETAPA.get(frozenset(normalizar_columnas(columnas_crudas)),
                             "etapa_desconocida")


def nombre_a_fecha(nombre: str) -> date:
    """Convierte `MM-DD-YYYY.csv` a fecha; falla explícitamente si no encaja."""
    try:
        return pd.to_datetime(Path(nombre).stem, format="%m-%d-%Y", errors="raise").date()
    except ValueError as error:
        raise ValueError(f"Nombre de archivo no reconocido: {nombre}") from error


def cargar_reporte(ruta: Path) -> pd.DataFrame:
    """Carga un reporte diario ya estandarizado a la capa limpia."""
    crudo = pd.read_csv(ruta)
    etapa = etapa_de(crudo.columns)

    df = crudo.rename(columns=RENOMBRAR)
    df.columns = normalizar_columnas(df.columns)

    if "last_update" in df:
        df["last_update"] = pd.to_datetime(
            df["last_update"], format="mixed", errors="coerce", utc=True)

    if "fips" in df:
        fips = pd.to_numeric(df["fips"], errors="coerce").astype("Int64")
        df["fips"] = fips.astype("string").str.zfill(5)

    for columna in COLUMNAS_TEXTO:
        if columna in df:
            df[columna] = df[columna].astype("string")

    for columna in COLUMNAS_ENTERAS:
        if columna in df:
            numerico = pd.to_numeric(df[columna], errors="coerce")
            if numerico.notna().all():
                df[columna] = numerico.astype("Int64")
            elif (numerico.dropna() % 1 == 0).all():
                df[columna] = numerico.astype("Int64")
            else:
                df[columna] = numerico  # valores no enteros: se conservan y se reportan

    for columna in COLUMNAS_NUMERICAS:
        if columna in df:
            df[columna] = pd.to_numeric(df[columna], errors="coerce")

    df["report_date"] = pd.Timestamp(nombre_a_fecha(ruta.name))
    df["etapa_esquema"] = etapa
    return df


def listar_reportes(directorio: Path, desde: date | None, hasta: date | None) -> list[Path]:
    archivos = []
    for ruta in sorted(directorio.glob("*.csv")):
        try:
            fecha = nombre_a_fecha(ruta.name)
        except ValueError:
            continue  # se reporta aparte en validar()
        if desde and fecha < desde:
            continue
        if hasta and fecha > hasta:
            continue
        archivos.append(ruta)
    return archivos


def cargar_reportes(archivos: list[Path]) -> pd.DataFrame:
    frames = [cargar_reporte(ruta) for ruta in archivos]
    if not frames:
        raise ValueError("No hay reportes en el rango indicado.")
    df = pd.concat(frames, ignore_index=True, sort=False)
    df["clave_raw"] = construir_clave_cruda(df)
    return df


def validar(df: pd.DataFrame, archivos: list[Path]) -> None:
    print("== Validación de la consolidación ==")
    print(f"Archivos procesados: {len(archivos)}")
    print(f"Filas consolidadas: {len(df):,}; columnas: {len(df.columns)}")
    print(f"report_date: {df['report_date'].min().date()} a {df['report_date'].max().date()}"
          f" ({df['report_date'].nunique()} fechas)")
    print("\nFilas por etapa de esquema:")
    print(df.groupby("etapa_esquema").size().rename("filas").to_string())
    desconocidas = df.loc[df["etapa_esquema"].eq("etapa_desconocida"), "report_date"].unique()
    if len(desconocidas):
        print(f"ATENCIÓN: {len(desconocidas)} fecha(s) con esquema desconocido: "
              + ", ".join(str(pd.Timestamp(d).date()) for d in sorted(desconocidas)))
    else:
        print("Ningún archivo quedó con etapa_desconocida.")

    print("\nNulos en columnas clave (% del total):")
    clave = ["confirmed", "deaths", "recovered", "active", "incident_rate",
             "case_fatality_ratio", "fips", "lat", "long"]
    for columna in clave:
        if columna in df:
            nulos = int(df[columna].isna().sum())
            print(f"  {columna:20s} {nulos:>9,}  ({100 * nulos / len(df):5.1f} %)")

    por_fecha = df.groupby("report_date").size()
    print(f"\nFilas por reporte: mín {por_fecha.min():,}; "
          f"mediana {int(por_fecha.median()):,}; máx {por_fecha.max():,}")


def medir(df: pd.DataFrame, archivos: list[Path], parquet: Path, repeticiones: int = 2) -> None:
    bytes_csv = sum(a.stat().st_size for a in archivos)
    bytes_parquet = parquet.stat().st_size
    print("\n== Tamaño en disco ==")
    print(f"CSV (suma de {len(archivos)} archivos): {bytes_csv / 1e6:,.1f} MB")
    print(f"Parquet:                               {bytes_parquet / 1e6:,.1f} MB"
          f"  ({100 * bytes_parquet / bytes_csv:.1f} % del CSV)")

    print("\n== Tiempo de lectura (mejor de "
          f"{repeticiones} repeticiones) ==")
    mejor_csv = min(_tiempo(lambda: cargar_reportes(archivos)) for _ in range(repeticiones))
    mejor_parquet = min(_tiempo(lambda: pd.read_parquet(parquet)) for _ in range(repeticiones))
    print(f"Leer y consolidar CSV: {mejor_csv:6.2f} s")
    print(f"Leer Parquet:          {mejor_parquet:6.2f} s"
          f"  ({mejor_csv / mejor_parquet:.1f}x más rápido)")


def _tiempo(funcion) -> float:
    inicio = time.perf_counter()
    funcion()
    return time.perf_counter() - inicio


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--desde", type=date.fromisoformat, default=None,
                        help="Fecha inicial ISO (incluida) según el nombre del archivo.")
    parser.add_argument("--hasta", type=date.fromisoformat, default=None,
                        help="Fecha final ISO (incluida) según el nombre del archivo.")
    parser.add_argument("--directorio", type=Path, default=RAW_DIR,
                        help="Carpeta con los CSV crudos.")
    parser.add_argument("--destino", type=Path, default=PARQUET_DESTINO,
                        help="Ruta del Parquet de salida.")
    parser.add_argument("--sin-escribir", action="store_true",
                        help="Solo valida; no escribe el Parquet.")
    parser.add_argument("--sin-medicion", action="store_true",
                        help="Omite el benchmark CSV vs Parquet.")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    if not args.directorio.exists():
        print(f"No existe la carpeta de crudos: {args.directorio}", file=sys.stderr)
        return 1

    archivos = listar_reportes(args.directorio, args.desde, args.hasta)
    inesperados = sorted(set(args.directorio.glob("*.csv")) - set(archivos))
    if inesperados and (args.desde or args.hasta) is None:
        print("ATENCIÓN: archivos con nombre no reconocido:", file=sys.stderr)
        for ruta in inesperados:
            print(f"  - {ruta.name}", file=sys.stderr)
    if not archivos:
        print("No hay reportes en el rango indicado.", file=sys.stderr)
        return 1

    df = cargar_reportes(archivos)
    validar(df, archivos)

    if args.sin_escribir:
        return 0

    args.destino.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(args.destino, index=False)
    print(f"\nParquet escrito en {args.destino}")

    if not args.sin_medicion:
        medir(df, archivos, args.destino)
    return 0


if __name__ == "__main__":
    sys.exit(main())
