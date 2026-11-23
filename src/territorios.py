"""Construye la tabla de identidad territorial (`data/clean/territorios.parquet`).

Problema que resuelve: los reportes diarios de JHU identifican cada territorio
por un `Combined_Key` (etapas 3–5) o por `Province_State` + `Country_Region`
(etapas 1–2, donde aún no existía esa columna). Los nombres cambiaron en el
tiempo (p. ej. `Taiwan*`, `Korea, South`, `Mainland China`) y hay erratas.

Estrategia (documentada, sin inventar correspondencias):

1. Clave cruda: `combined_key` si existe; si no, se construye como
   `province_state, country_region` (o solo `country_region` si no hay
   provincia), con la misma convención que usó JHU después.
2. Normalización para empatar: sin tildes, minúsculas, solo [a-z0-9].
   Esto ya resuelve `Doña Ana` → `Dona Ana` y `Viet Nam` → `Vietnam`.
3. Alias explícitos (`ALIAS`): erratas de JHU, fusiones/renombrados censales
   de EE.UU. y movimientos de territorios bajo un país administador en la
   tabla UID. Cada alias está comentado. Nunca se fuerza el emparejamiento
   entre territorios distintos.
4. Lo que no calza queda `sin_match` y se lista en el informe; para agregados
   por país se le infiere `iso3` desde el componente país de la clave
   (con el inverso `PAIS_A_ISO3`), sin inventar población ni coordenadas.
5. `territorio_id` en el DW es la clave UID empatada (o un id sintético para
   `sin_match`), de modo que series como `Taiwan` (etapas 1–2) y `Taiwan*`
   (etapas 3–5) quedan unidas en una sola serie temporal.

Salidas:

- `data/clean/territorios.parquet`: una fila por clave cruda observada.
- Informe por pantalla: cobertura de match, iso3 inferidos y lista de
  claves sin correspondencia (para documentar en el diccionario de datos).
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

RAW_PARQUET = Path("data/clean/daily_reports.parquet")
UID_CSV = Path("data/raw/UID_ISO_FIPS_LookUp_Table.csv")
DESTINO = Path("data/clean/territorios.parquet")

# Alias: clave normalizada cruda -> clave normalizada UID. Comentado uno a uno.
ALIAS = {
    # --- Erratas tipográficas de JHU ---
    "australiancapneitalterritoryaustralia": "australiancapitalterritoryaustralia",
    "falklandislandsislasmalvinasunitedkingdom": "falklandislandsmalvinasunitedkingdom",
    # Unión territorial de la India (Dadra and Nagar Haveli fusionada con
    # Daman and Diu en 2020); JHU reporta la fila con el nombre antiguo.
    "dadarnagarhaveliindia": "dadraandnagarhavelianddamananddiuindia",
    # JHU escribió "Capneital" y "Malvinas"/"Malvinas"; Falkland corregido arriba.
    # --- Reorganizaciones censales de EE.UU. (mismo territorio) ---
    "yakutatalaskaus": "yakutatplushoonahangoonalaskaus",      # censo 2020 (ADC)
    "lakeandpeninsulaalaskaus": "bristolbaypluslakeandpeninsulaalaskaus",  # fusión ADC
    "southwestutahus": "southwestutahutahus",                      # nombre censal
    # --- Territorios que la tabla UID lista bajo su país administador ---
    "guam": "guamus",
    "hongkong": "hongkongchina", "hongkongsar": "hongkongchina",
    "hongkonghongkongsar": "hongkongchina",
    "macao": "macauchina", "macau": "macauchina", "macaosar": "macauchina",
    "macaumacaosar": "macauchina",
    "taiwantaipeiandenvirons": "taiwan",
    "fenchguianafrance": "frenchguianafrance",  # errata: "Fench Guiana"
    "aruba": "arubanetherlands", "curacao": "curacaonetherlands",
    "guernsey": "guernseyunitedkingdom", "jersey": "jerseyunitedkingdom",
    "caymanislands": "caymanislandsunitedkingdom",
    "frenchguiana": "frenchguianafrance",
    "puertorico": "puertoricous",
    "mayotte": "mayottefrance",
    "greenland": "greenlanddenmark", "faroeislands": "faroeislandsdenmark",
    "guadeloupe": "guadeloupefrance", "martinique": "martiniquefrance",
    "reunion": "reunionfrance", "gibraltar": "gibraltarunitedkingdom",
    "saintbarthelemy": "saintbarthelemyfrance",
    # --- Barcos/eventos especiales (la tabla UID los tiene sin iso3) ---
    "diamondprincesscruiseship": "diamondprincess",
    # --- Nombres alternativos de países (misma entidad) ---
    "czechrepublic": "czechia",
    "easttimor": "timorleste",
    "iranislamicrepublicof": "iran",
    "ivorycoast": "cotedivoire",
    "republicofkorea": "koreasouth", "southkorea": "koreasouth",
    "thebahamas": "bahamas", "bahamasthe": "bahamas",
    "thegambia": "gambia", "gambiathe": "gambia",
    "capeverde": "caboverde",
    "vatican": "holysee", "vaticancity": "holysee",
    "russianfederation": "russia",
    "republicofireland": "ireland",
    "republicofmoldova": "moldova",
    "republicofthecongo": "congobrazzaville",
    "taipeiandenvirons": "taiwan",
}

# Fallback nombre de país (componente tras la última coma, o clave completa si
# no hay coma) -> iso3, para claves sin correspondencia en la UID.
# Mapa explícito: no se usan modas de la UID (los territorios administrados
# distorsionarían el resultado, p. ej. Francia).
PAIS_A_ISO3 = {
    "us": "USA", "usa": "USA", "canada": "CAN", "australia": "AUS",
    "india": "IND", "germany": "DEU", "france": "FRA",
    "unitedkingdom": "GBR", "israel": "ISR", "italy": "ITA",
    "spain": "ESP", "netherlands": "NLD", "denmark": "DNK",
    "china": "CHN", "japan": "JPN", "brazil": "BRA",
    # Administrados (la fila pertenece administrativamente a ese país,
    # pero el territorio tiene iso3 propio; ver ALIAS para empatarlos en la UID)
    "hongkong": "HKG", "hongkongsar": "HKG", "macao": "MAC", "macaosar": "MAC",
    "aruba": "ABW", "curacao": "CUW",
    "guernsey": "GGY", "jersey": "JEY", "caymanislands": "CYM",
    "frenchguiana": "GUF", "guadeloupe": "GLP", "martinique": "MTQ",
    "reunion": "REU", "mayotte": "MYT",
    "greenland": "GRL", "faroeislands": "FRO", "gibraltar": "GIB",
    "puertorico": "PRI", "guam": "GUM",
    "northireland": "GBR", "channelislands": None,
    "vatican": "VAT", "vaticancity": "VAT", "holysee": "VAT",
    "palestine": "PSE", "westbankandgaza": "PSE", "occupiedpalestinianterritory": "PSE",
    "stmartin": "MAF", "saintmartin": "MAF",
    "saintbarthelemy": "BLM",
    "taipeiandenvirons": "TWN", "taiwan": "TWN",
    "mainlandchina": "CHN",
    "repatriatedtravellers": "CAN",  # canadienses repatriados (fila especial JHU)
    "falklandislandsislasmalvinas": "FLK",
    "capeverde": "CPV", "caboverde": "CPV",
}

ESPECIALES = (
    "cruiseship", "diamondprincess", "mszaandam", "olympics",
    "repatriatedtravellers", "wuhanevacuee",
)


def norm_clave(valor: object) -> str:
    """Normaliza para empatar: sin tildes, minúsculas, solo [a-z0-9]."""
    if pd.isna(valor):
        return ""
    texto = unicodedata.normalize("NFKD", str(valor)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", texto.lower())


def construir_clave_cruda(df: pd.DataFrame) -> pd.Series:
    """Replica la convención `province_state, country_region` para etapas 1–2."""
    clave = df["combined_key"].copy()
    sin_ck = clave.isna()
    prov = df["province_state"]
    pais = df["country_region"].replace({"Mainland China": "China"})
    con_prov = sin_ck & prov.notna() & (prov.str.strip().str.lower() != pais.str.strip().str.lower())
    clave[con_prov] = prov[con_prov].str.strip() + ", " + pais[con_prov].str.strip()
    clave[sin_ck & ~con_prov] = pais[sin_ck & ~con_prov].str.strip()
    return clave.str.strip()


def clave_pais_componente(clave: str) -> str:
    """Extrae el componente país (tras la última coma) con reglas 'The'."""
    if clave.startswith("The "):
        return clave[4:].strip()
    if clave.endswith(", The"):
        return clave[:-5].strip()
    partes = clave.split(",")
    return partes[-1].strip() if len(partes) > 1 else clave.strip()


def clasificar_nivel(clave: str, admin2: object) -> str:
    normalizada = norm_clave(clave)
    if any(token in normalizada for token in ESPECIALES):
        return "especial"
    partes = [p for p in clave.split(",")]
    if len(partes) == 1:
        return "pais"
    if norm_clave(partes[-1]) == "us" and pd.notna(admin2) and str(admin2).strip():
        return "condado"
    return "region_estado"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parquet", type=Path, default=RAW_PARQUET)
    parser.add_argument("--uid", type=Path, default=UID_CSV)
    parser.add_argument("--destino", type=Path, default=DESTINO)
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    df = pd.read_parquet(args.parquet, columns=[
        "report_date", "combined_key", "province_state", "admin2",
        "country_region", "etapa_esquema",
    ])
    df["clave_raw"] = construir_clave_cruda(df)
    claves = df["clave_raw"].dropna().unique()
    print(f"Claves crudas únicas observadas: {len(claves):,}")

    ref = pd.DataFrame({"clave_raw": claves})
    ref["clave_norm"] = ref["clave_raw"].map(norm_clave)
    ref["clave_uid"] = ref["clave_norm"].map(lambda k: ALIAS.get(k, k))
    ref["alias_aplicado"] = ref["clave_norm"] != ref["clave_uid"]

    uid = pd.read_csv(args.uid, dtype={"FIPS": "string"},
                      usecols=["UID", "iso2", "iso3", "Province_State",
                               "Country_Region", "Combined_Key", "Population",
                               "Lat", "Long_"])
    uid["clave_norm"] = uid["Combined_Key"].map(norm_clave)
    uid_map = uid.drop_duplicates(subset="clave_norm").set_index("clave_norm")

    ref = ref.merge(
        uid_map[["UID", "iso2", "iso3", "Combined_Key", "Population", "Lat", "Long_"]],
        left_on="clave_uid", right_index=True, how="left",
    )
    ref["match_uid"] = ref["Combined_Key"].notna()
    ref["tipo_match"] = "sin_match"
    ref.loc[ref["match_uid"] & ~ref["alias_aplicado"]
            & (ref["clave_raw"].str.strip() == ref["Combined_Key"].str.strip()), "tipo_match"] = "exacto"
    ref.loc[ref["match_uid"] & (ref["tipo_match"] == "sin_match") & ~ref["alias_aplicado"], "tipo_match"] = "normalizado"
    ref.loc[ref["match_uid"] & ref["alias_aplicado"], "tipo_match"] = "alias"

    # Inferencia de iso3 para claves sin UID: componente país de la clave.
    def inferir_iso3(clave: str):
        return PAIS_A_ISO3.get(norm_clave(clave_pais_componente(clave)))

    sin_match = ~ref["match_uid"]
    ref.loc[sin_match, "iso3"] = [inferir_iso3(c) for c in ref.loc[sin_match, "clave_raw"]]
    ref.loc[sin_match, "iso3"] = ref.loc[sin_match, "iso3"].where(ref.loc[sin_match, "iso3"].notna(), None)

    # Nivel y país lógico (parent country) para agregados.
    admin2_por_clave = df.groupby("clave_raw")["admin2"].first()
    ref["admin2_muestra"] = ref["clave_raw"].map(admin2_por_clave)
    ref["nivel"] = [clasificar_nivel(c, a) for c, a in zip(ref["clave_raw"], ref["admin2_muestra"])]
    ref["pais_iso3"] = ref["iso3"]  # para nivel='pais' queda el propio iso3
    # Para subnacionales, el país lógico es el iso3 del componente país, no el propio.
    if (ref["nivel"] != "pais").any():
        comp = [norm_clave(clave_pais_componente(c)) for c in ref.loc[ref["nivel"] != "pais", "clave_raw"]]
        pais_iso3_inferido = [PAIS_A_ISO3.get(c) for c in comp]
        # Si el iso3 inferido del componente es nulo, conservar el iso3 propio (país pequeño listado como provincia).
        propia = ref.loc[ref["nivel"] != "pais", "iso3"].tolist()
        ref.loc[ref["nivel"] != "pais", "pais_iso3"] = [
            i if i else p for i, p in zip(pais_iso3_inferido, propia)
        ]

    ref = ref.rename(columns={"Combined_Key": "clave_uid_resuelta",
                              "Lat": "lat", "Long_": "long",
                              "UID": "uid", "Population": "population"})
    salida = ref[["clave_raw", "clave_uid_resuelta", "match_uid", "tipo_match",
                  "nivel", "iso3", "iso2", "pais_iso3", "uid",
                  "population", "lat", "long"]]
    args.destino.parent.mkdir(parents=True, exist_ok=True)
    salida.to_parquet(args.destino, index=False)

    # ---- Informe ----
    print(f"\nEscrito {args.destino} ({len(salida):,} territorios)")
    print("\nTipos de match (territorios):")
    print(salida["tipo_match"].value_counts().to_string())
    filas_raw = df.merge(salida[["clave_raw", "match_uid", "iso3"]],
                         on="clave_raw", how="left")
    print("\nCobertura en filas:")
    print(f"  match UID:      {filas_raw['match_uid'].mean() * 100:6.2f} %")
    print(f"  con iso3 final: {filas_raw['iso3'].notna().mean() * 100:6.2f} %")
    print("\nClaves sin match en UID (territorios, con nº de filas):")
    conteo = filas_raw.loc[~filas_raw["match_uid"]].groupby("clave_raw").size().sort_values(ascending=False)
    for clave, n in conteo.items():
        iso3 = salida.set_index("clave_raw").loc[clave, "iso3"]
        print(f"  {clave!r:55s} filas={n:>6}  iso3={iso3}")
    print("\nDistribución por nivel:")
    print(salida["nivel"].value_counts().to_string())
    sin_iso3 = salida["iso3"].isna().sum()
    print(f"\nTerritorios sin iso3 (especiales): {sin_iso3}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
