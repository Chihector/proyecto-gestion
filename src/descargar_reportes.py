"""Descarga reproducible de los datos de Johns Hopkins CSSE.

Descarga, sin clonar el historial de Git:

- Los reportes diarios (`MM-DD-YYYY.csv`) entre `--desde` y `--hasta`
  (por defecto, 2020-01-22 a 2023-03-09: los 1.143 reportes publicados).
- Las series temporales (`time_series_*.csv`) en `--series-destino`.
- La tabla de territorios `UID_ISO_FIPS_LookUp_Table.csv` en `--lookup-destino`.
- La serie de vacunación de **Our World in Data** en `--owid-destino`
  (integración externa del proyecto, cruce por `iso_code` = ISO3).
- El panel de respuesta de política de **Oxford OxCGRT** en `--oxcgrt-destino`
  (segunda fuente externa, país-día 2020-01-01 a 2022-12-31; cruce por
  `CountryCode` = ISO3).

Los archivos ya descargados se reutilizan y no se vuelven a bajar. Los
problemas se reportan explícitamente al final (con la URL y el motivo) y el
proceso termina con código de salida 1 si hubo fallos.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

BASE_URL = (
    "https://raw.githubusercontent.com/CSSEGISandData/COVID-19/"
    "master/csse_covid_19_data/csse_covid_19_daily_reports"
)
SERIES_URL = (
    "https://raw.githubusercontent.com/CSSEGISandData/COVID-19/"
    "master/csse_covid_19_data/csse_covid_19_time_series"
)
LOOKUP_URL = (
    "https://raw.githubusercontent.com/CSSEGISandData/COVID-19/"
    "master/csse_covid_19_data/UID_ISO_FIPS_LookUp_Table.csv"
)
OWID_VACUNAS_URL = (
    "https://raw.githubusercontent.com/owid/covid-19-data/"
    "master/public/data/vaccinations/vaccinations.csv"
)
OXCGRT_URL = (
    "https://raw.githubusercontent.com/OxCGRT/covid-policy-dataset/"
    "main/data/OxCGRT_compact_national_v1.csv"
)
PRIMER_REPORTE = date(2020, 1, 22)
ULTIMO_REPORTE = date(2023, 3, 9)
SERIES_ARCHIVOS = (
    "time_series_covid19_confirmed_global.csv",
    "time_series_covid19_deaths_global.csv",
    "time_series_covid19_recovered_global.csv",
    "time_series_covid19_confirmed_US.csv",
    "time_series_covid19_deaths_US.csv",
)


class DescargaError(RuntimeError):
    """Agrupa todos los archivos que no pudieron descargarse."""

    def __init__(self, fallos: list[tuple[str, str]]) -> None:
        self.fallos = fallos
        detalle = "\n".join(f"  - {url}: {motivo}" for url, motivo in fallos)
        super().__init__(f"{len(fallos)} archivo(s) sin descargar:\n{detalle}")


def _descargar_archivo(url: str, destino: Path, reintentos: int = 2) -> str | None:
    """Descarga `url` en `destino`; devuelve None o el motivo del fallo."""
    if destino.exists() and destino.stat().st_size > 0:
        return None  # ya descargado y no vacío: se reutiliza

    ultimo_error = "error desconocido"
    for _ in range(max(1, reintentos)):
        try:
            with urlopen(url, timeout=60) as respuesta:
                contenido = respuesta.read()
            if not contenido.strip():
                ultimo_error = "el archivo descargado está vacío"
                continue
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(contenido)
            return None
        except (HTTPError, URLError, TimeoutError, OSError) as error:
            ultimo_error = str(error)
    return ultimo_error


def descargar_reportes(fecha_inicio: date, fecha_fin: date, destino: Path) -> int:
    """Descarga los CSV en el rango inclusivo y devuelve cuántos se obtuvieron.

    Reutiliza los archivos ya presentes y, al terminar, lanza `DescargaError`
    con la lista completa de fallos si alguno no pudo descargarse.
    """
    if fecha_inicio > fecha_fin:
        raise ValueError("La fecha inicial debe ser anterior o igual a la fecha final.")

    destino.mkdir(parents=True, exist_ok=True)
    descargados = 0
    fallos: list[tuple[str, str]] = []
    fecha = fecha_inicio
    while fecha <= fecha_fin:
        nombre = f"{fecha:%m-%d-%Y}.csv"
        url = f"{BASE_URL}/{nombre}"
        archivo = destino / nombre
        existia = archivo.exists() and archivo.stat().st_size > 0
        motivo = _descargar_archivo(url, archivo)
        if motivo is not None:
            fallos.append((url, motivo))
        elif not existia:
            descargados += 1
        fecha += timedelta(days=1)

    if fallos:
        raise DescargaError(fallos)
    return descargados


def descargar_series(destino: Path) -> int:
    """Descarga las series temporales; devuelve cuántas son nuevas."""
    destino.mkdir(parents=True, exist_ok=True)
    descargadas = 0
    fallos: list[tuple[str, str]] = []
    for nombre in SERIES_ARCHIVOS:
        url = f"{SERIES_URL}/{nombre}"
        archivo = destino / nombre
        existia = archivo.exists() and archivo.stat().st_size > 0
        motivo = _descargar_archivo(url, archivo)
        if motivo is not None:
            fallos.append((url, motivo))
        elif not existia:
            descargadas += 1

    if fallos:
        raise DescargaError(fallos)
    return descargadas


def descargar_lookup(destino: Path) -> bool:
    """Descarga la tabla UID/ISO/FIPS; True si el archivo es nuevo."""
    existia = destino.exists() and destino.stat().st_size > 0
    motivo = _descargar_archivo(LOOKUP_URL, destino)
    if motivo is not None:
        raise DescargaError([(LOOKUP_URL, motivo)])
    return not existia


def descargar_owid(destino: Path) -> bool:
    """Descarga la serie de vacunación de Our World in Data; True si es nueva."""
    existia = destino.exists() and destino.stat().st_size > 0
    motivo = _descargar_archivo(OWID_VACUNAS_URL, destino)
    if motivo is not None:
        raise DescargaError([(OWID_VACUNAS_URL, motivo)])
    return not existia


def descargar_oxcgrt(destino: Path) -> bool:
    """Descarga el panel de respuesta de política de OxCGRT; True si es nuevo."""
    existia = destino.exists() and destino.stat().st_size > 0
    motivo = _descargar_archivo(OXCGRT_URL, destino)
    if motivo is not None:
        raise DescargaError([(OXCGRT_URL, motivo)])
    return not existia


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--desde", default=PRIMER_REPORTE.isoformat(),
                        help="Fecha inicial ISO de reportes (incluida).")
    parser.add_argument("--hasta", default=ULTIMO_REPORTE.isoformat(),
                        help="Fecha final ISO de reportes (incluida).")
    parser.add_argument("--destino", type=Path, default=Path("data/raw/daily_reports"),
                        help="Directorio de reportes diarios.")
    parser.add_argument("--series-destino", type=Path, default=Path("data/raw/time_series"),
                        help="Directorio de series temporales.")
    parser.add_argument("--lookup-destino", type=Path,
                        default=Path("data/raw/UID_ISO_FIPS_LookUp_Table.csv"),
                        help="Ruta de la tabla UID/ISO/FIPS.")
    parser.add_argument("--omitir-series", action="store_true",
                        help="No descargar las series temporales.")
    parser.add_argument("--omitir-lookup", action="store_true",
                        help="No descargar la tabla UID/ISO/FIPS.")
    parser.add_argument("--owid-destino", type=Path, default=Path("data/raw/owid_vaccinations.csv"),
                        help="Ruta del CSV de vacunación de OWID.")
    parser.add_argument("--omitir-owid", action="store_true",
                        help="No descargar la serie de vacunación de OWID.")
    parser.add_argument("--oxcgrt-destino", type=Path,
                        default=Path("data/raw/oxcgrt_restricciones.csv"),
                        help="Ruta del CSV de políticas de OxCGRT.")
    parser.add_argument("--omitir-oxcgrt", action="store_true",
                        help="No descargar el panel de políticas de OxCGRT.")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    try:
        fecha_inicio = date.fromisoformat(args.desde)
        fecha_fin = date.fromisoformat(args.hasta)
    except ValueError as error:
        parser.error(f"Fechas inválidas: {error}")

    fallos: list[str] = []

    try:
        nuevos = descargar_reportes(fecha_inicio, fecha_fin, args.destino)
        total = len(list(args.destino.glob("*.csv")))
        print(f"Reportes diarios: {nuevos} nuevos; {total} CSV en {args.destino}")
    except DescargaError as error:
        fallos.append(str(error))

    if not args.omitir_series:
        try:
            nuevas = descargar_series(args.series_destino)
            print(f"Series temporales: {nuevas} nuevas; carpeta: {args.series_destino}")
        except DescargaError as error:
            fallos.append(str(error))

    if not args.omitir_lookup:
        try:
            nuevo = descargar_lookup(args.lookup_destino)
            estado = "descargada" if nuevo else "ya existía"
            print(f"Tabla UID/ISO/FIPS: {estado} ({args.lookup_destino})")
        except DescargaError as error:
            fallos.append(str(error))

    if not args.omitir_owid:
        try:
            nuevo = descargar_owid(args.owid_destino)
            estado = "descargada" if nuevo else "ya existía"
            print(f"Vacunación OWID:    {estado} ({args.owid_destino})")
        except DescargaError as error:
            fallos.append(str(error))

    if not args.omitir_oxcgrt:
        try:
            nuevo = descargar_oxcgrt(args.oxcgrt_destino)
            estado = "descargado" if nuevo else "ya existía"
            print(f"Políticas OxCGRT:   {estado} ({args.oxcgrt_destino})")
        except DescargaError as error:
            fallos.append(str(error))

    if fallos:
        print("\nERRORES DE DESCARGA:\n" + "\n".join(fallos), file=sys.stderr)
        return 1
    print("Descarga finalizada sin errores.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
