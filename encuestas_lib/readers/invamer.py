"""Lector de microdatos Invamer (Colombia Opina).

Formato Invamer:
    - Excel con códigos numéricos para candidatos (mapa oficial).
    - `Factor de ponderación`: peso de expansión.
    - P2 (aprobación), P24 (edad), P22 (educación).
    - P245 (PV inducida), P247 (PV espontánea).
    - P231-P233, P256-P268: matchups binarios SV.
    - P271/P272: escenarios multi-candidato (3-4 cands), no binarios → skip.
"""

from __future__ import annotations

import pandas as pd

from encuestas_lib.readers.base import BaseReader, find_col

# Mapa oficial de Invamer: código numérico → nombre canónico
INVAMER_CAND_MAP: dict[int, str] = {
    2: "Germán Vargas Lleras",
    3: "Sergio Fajardo",
    7: "Felipe Córdoba",
    11: "Claudia López",
    25: "Juan Manuel Galán",
    27: "Roy Barreras",
    29: "Paola Holguín",
    30: "Paloma Valencia",
    38: "Enrique Peñalosa",
    44: "Juan Carlos Pinzón",
    45: "Mauricio Cárdenas",
    50: "Iván Cepeda",
    52: "María Fernanda Cabal",
    55: "Camilo Romero",
    60: "Juan Fernando Cristo",
    65: "Luis Gilberto Murillo",
    87: "David Luna",
    88: "Juan Daniel Oviedo",
    90: "Vicky Dávila",
    95: "Carlos Caicedo",
    97: "Abelardo de la Espriella",
    98: "Mauricio Lizcano",
    100: "Aníbal Gaviria",
    101: "Juan Guillermo Zuluaga",
    102: "Maurice Armitage",
    103: "Mauricio Gómez Amín",
    104: "Miguel Uribe Londoño",
    105: "Juan Carlos Cárdenas",
    106: "Daniel Palacios",
    107: "Héctor Olimpo",
    108: "Efraín Cepeda",
    109: "Luis Carlos Reyes",
    110: "Santiago Botero",
    112: "Clara López",
    113: "Sondra Macollins",
    150: "Gustavo Petro",
    255: "Gustavo Matamoros",
    990: "Ninguno",
    995: "Voto en blanco",
    999: "NS/NR",
    9996: "Otro",
}

INVAMER_SV_MAP: dict[str, tuple[str, str]] = {
    "P231": ("Abelardo de la Espriella", "Sergio Fajardo"),
    "P232": ("Iván Cepeda", "Sergio Fajardo"),
    "P233": ("Iván Cepeda", "Abelardo de la Espriella"),
    "P256": ("Iván Cepeda", "Paloma Valencia"),
    "P258": ("Iván Cepeda", "Claudia López"),
    "P267": ("Sergio Fajardo", "Abelardo de la Espriella"),
    "P268": ("Paloma Valencia", "Sergio Fajardo"),
}

_REGION_INV_MAP: dict[int | str, str] = {
    1: "Caribe",
    2: "Centro - Oriente",
    3: "Eje Cafetero",
    4: "Pacífico",
    # FIX B_NEW_4: era "Centro – Sur - Amazonía" con guion largo (U+2013).
    # normalize_text elimina el guion largo → "centro sur - amazonia" (sin guion
    # antes de "sur"), que no coincidía con ninguna clave de REGION_NORM y
    # producía duplicados en voto_por_region (12 filas en vez de 9).
    # Se normaliza aquí a guion regular para que coincida con la clave
    # "centro - sur - amazonia" → "Centro - Sur - Amazonía" en REGION_NORM.
    5: "Centro - Sur - Amazonía",
    6: "Llano",
    "1": "Caribe",
    "2": "Centro - Oriente",
    "3": "Eje Cafetero",
    "4": "Pacífico",
    "5": "Centro - Sur - Amazonía",
    "6": "Llano",
}

_EDAD_INV_MAP: dict[int | str, str] = {
    1: "Entre 18 y 24",
    2: "Entre 25 y 34",
    3: "Entre 35 y 44",
    4: "Entre 45 y 54",
    5: "55 ó más",
    "1": "Entre 18 y 24",
    "2": "Entre 25 y 34",
    "3": "Entre 35 y 44",
    "4": "Entre 45 y 54",
    "5": "55 ó más",
}


class InvamerReader(BaseReader):
    """Reader para encuestas Invamer (Colombia Opina)."""

    def read(self) -> pd.DataFrame:
        """Lee el archivo xlsx de Invamer y retorna el DataFrame canónico."""
        path = self.survey.path

        df = pd.read_excel(path)
        h = self.harmonizer

        # Limpiar filas-header repetidas
        fac_col = find_col(df, "Factor de ponderaci")
        if fac_col is None:
            raise ValueError(
                f"Invamer {self.survey.id}: no se encontró columna 'Factor de ponderación'"
            )
        df = df[df[fac_col].astype(str) != fac_col].copy()
        df[fac_col] = pd.to_numeric(df[fac_col], errors="coerce")

        def decode(val: object) -> str | None:
            if pd.isna(val) or str(val).strip() in ("", "nan"):
                return None
            try:
                code = int(float(str(val)))
                name = INVAMER_CAND_MAP.get(code)
                if name:
                    return h.harmonize(name)
            except (ValueError, TypeError):
                pass
            return h.harmonize(val)

        r = self._empty_canonical_df(df.index)
        nota = self.survey.nota or self.survey.id
        r["encuestadora"] = f"Invamer ({nota})"
        r["fecha"] = pd.Timestamp(self.survey.fecha)
        r["factor"] = df[fac_col].astype(float)
        r["departamento"] = None
        r["municipio"] = df["Municipio"].astype("string") if "Municipio" in df.columns else None

        if "REGIÓN" in df.columns:
            r["region"] = df["REGIÓN"].map(_REGION_INV_MAP)
        if "ZONA" in df.columns:
            r["zona"] = df["ZONA"].astype("string").replace({"B_ZONA": None})
        if "SEXO" in df.columns:
            r["genero"] = (
                df["SEXO"]
                .map({"1": "Hombre", "2": "Mujer", 1: "Hombre", 2: "Mujer"})
                .fillna(df["SEXO"].astype("string"))
            )

        edad_col = find_col(df, "P24_GRUPOEDAD")
        if edad_col:
            r["edad_grupo"] = df[edad_col].map(_EDAD_INV_MAP)
        if "ESTRATO SOCIAL" in df.columns:
            r["estrato"] = df["ESTRATO SOCIAL"].astype("string").replace({"B_ESTRATO": None})

        p22 = find_col(df, "P22.")
        if p22:
            r["educacion"] = df[p22].astype("string")

        # Aprobación
        p2 = find_col(df, "P2.", "aprueba")
        if p2:
            r["aprobacion_petro"] = (
                df[p2]
                .map(
                    {
                        "1": "Aprueba",
                        "2": "Desaprueba",
                        "999": "NS/NR",
                        1: "Aprueba",
                        2: "Desaprueba",
                        999: "NS/NR",
                    }
                )
                .fillna(df[p2].astype("string").replace({"nan": None}))
            )

        # Primera vuelta
        p245 = find_col(df, "P245")
        p247 = find_col(df, "P247")
        if p245:
            r["primera_vuelta"] = df[p245].map(decode)
        if p247:
            r["primera_vuelta_espontanea"] = df[p247].map(decode)

        # Segunda vuelta
        from encuestas_lib.harmonization import sv_col_name

        for pat, (c1, c2) in INVAMER_SV_MAP.items():
            real_col = find_col(df, pat)
            sv = sv_col_name(c1, c2, h)
            if real_col and sv:
                r[sv] = df[real_col].map(decode)

        return self._validate_output(r)
