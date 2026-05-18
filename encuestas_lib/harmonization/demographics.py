"""Normalización de variables demográficas (edad, región, sexo, aprobación)."""

from __future__ import annotations

import contextlib

import pandas as pd

from encuestas_lib.harmonization.candidates import normalize_text

# ════════════════════════════════════════════════════════════════════════════
#  Edad
# ════════════════════════════════════════════════════════════════════════════
EDAD_NORM: dict[str, str] = {
    # Atlas Intel
    "18 - 24": "18-24",
    "25 - 34": "25-34",
    "35 - 44": "35-44",
    "45 - 59": "45-59",
    "60 - 100": "60+",
    # CNC
    "18 a 24": "18-24",
    "25 a 34": "25-34",
    "35 a 44": "35-44",
    "45 a 54": "45-54",
    "55 o mas": "55+",
    "55 o más": "55+",
    # GAD3
    "18-24": "18-24",
    "25-34": "25-34",
    "35-44": "35-44",
    "45-54": "45-54",
    "55+": "55+",
    "35-54": "35-54",
    "18-34": "18-34",
    # Invamer (etiquetas)
    "entre 18 y 24": "18-24",
    "entre 25 y 34": "25-34",
    "entre 35 y 44": "35-44",
    "entre 45 y 54": "45-54",
    "55 ó más": "55+",
    # Invamer (códigos numéricos)
    "1": "18-24",
    "2": "25-34",
    "3": "35-44",
    "4": "45-54",
    "5": "55+",
}

EDAD_COLAPSO_3: dict[str, str] = {
    "18-24": "18-34",
    "25-34": "18-34",
    "18-34": "18-34",
    "35-44": "35-54",
    "45-54": "35-54",
    "35-54": "35-54",
    "45-59": "55+",
    "55+": "55+",
    "60+": "55+",
}


# ════════════════════════════════════════════════════════════════════════════
#  Región
# ════════════════════════════════════════════════════════════════════════════
# IMPORTANTE: las claves de este dict deben estar en forma ASCII-normalizada
# (sin tildes, lowercase, espacios simples) porque `aplicar_mapa_con_int`
# aplica `normalize_text` al input ANTES de hacer la búsqueda en el dict.
# Un clave con tildes (p. ej. "bogotá d.c.") nunca coincidirá con el string
# normalizado "bogota d.c." → regiones duplicadas en el output.
REGION_NORM: dict[str, str] = {
    # ── Invamer: códigos numéricos directos ────────────────────────────
    "1": "Caribe",
    "2": "Centro - Oriente",
    "3": "Eje Cafetero",
    "4": "Pacífico",
    "5": "Centro - Sur - Amazonía",
    "6": "Llano",
    # ── GAD3: strings en minúscula ASCII (ya normalizados) ─────────────
    "central": "Central",
    "caribe": "Caribe",
    "oriental": "Centro - Oriente",
    "pacifica": "Pacífico",
    "bogota": "Bogotá",
    "amaz-orin": "Amazonía - Orinoquía",
    # ── Invamer vía _REGION_INV_MAP (strings pre-mapeados, luego norm.) ─
    # "Centro - Sur - Amazonía" → normalize → "centro - sur - amazonia"
    "centro - sur - amazonia": "Centro - Sur - Amazonía",
    # "Centro – Sur - Amazonía" (guion largo) → normalize → "centro sur - amazonia"
    # (el guion largo U+2013 desaparece con encode ASCII ignore → doble espacio
    #  que normalize_text colapsa a uno).  FIX B_NEW_4: clave en forma ASCII.
    "centro sur - amazonia": "Centro - Sur - Amazonía",
    # ── Atlas Intel: strings con tildes, ya normalizados por normalize_text ─
    # "Pacífica" → normalize → "pacifica"  (ya cubierto por clave GAD3)
    # "Bogotá D.C." → normalize → "bogota d.c."  FIX B_NEW_4: clave ASCII
    "bogota d.c.": "Bogotá",
    "bogota d.c": "Bogotá",
    # "Amazonía y Orinoquía" → normalize → "amazonia y orinoquia"  FIX B_NEW_4
    "amazonia y orinoquia": "Amazonía - Orinoquía",
}


# ════════════════════════════════════════════════════════════════════════════
#  Aprobación de Petro
# ════════════════════════════════════════════════════════════════════════════
APROBACION_PETRO_NORM: dict[str, str] = {
    "aprueba": "Aprueba",
    "desaprueba": "Desaprueba",
    "excelente / bueno": "Aprueba",
    "excelente/bueno": "Aprueba",
    "malo / muy malo": "Desaprueba",
    "malo/muy malo": "Desaprueba",
    "positiva": "Aprueba",
    "negativa": "Desaprueba",
    "regular": "Regular",
    "ns/nr": "NS/NR",
    "nsnr": "NS/NR",
    "no sabe": "NS/NR",
    "no responde": "NS/NR",
    "p2": "NS/NR",  # caso de Invamer cuando aparece header como valor
}


# ════════════════════════════════════════════════════════════════════════════
#  Sexo / Género
# ════════════════════════════════════════════════════════════════════════════
SEXO_NORM: dict[str, str] = {
    "hombre": "Hombre",
    "masculino": "Hombre",
    "varon": "Hombre",
    "h": "Hombre",
    "m": "Hombre",
    "mujer": "Mujer",
    "femenino": "Mujer",
    "f": "Mujer",
    "otro": "Otro",
    "no sabe": "NS/NR",
    "no responde": "NS/NR",
    "ns/nr": "NS/NR",
    "nsnr": "NS/NR",
    "b_sexo": "",
}


# ════════════════════════════════════════════════════════════════════════════
#  Aplicar mapping a una serie
# ════════════════════════════════════════════════════════════════════════════
def aplicar_mapa(serie: pd.Series, mapa: dict[str, str]) -> pd.Series:
    """Aplicar un mapeo de normalización a una serie completa, vectorizado.

    Implementación vectorizada (no `.apply`): muchísimo más rápida en
    series grandes.

    Args:
        serie: serie de strings/objetos.
        mapa: dict cuya clave es el texto normalizado (lowercase ASCII).

    Returns:
        Serie del mismo índice con valores mapeados; los valores sin
        match se devuelven como están (strip aplicado).
    """
    # str(.) → strip → normalizado (NFKD ASCII lowercase)
    s = serie.astype("string[pyarrow]").fillna("")
    s_norm = (
        s.str.normalize("NFKD")
        .str.encode("ascii", "ignore")
        .str.decode("ascii")
        .str.strip()
        .str.lower()
        .str.replace(r"\s+", " ", regex=True)
    )
    mapped = s_norm.map(mapa)
    # Donde no hay match, devolver el original strip
    out = mapped.where(mapped.notna(), serie.astype("string[pyarrow]").str.strip())
    # Vacíos → NA
    out = out.where(out.astype("string[pyarrow]").str.len() > 0, pd.NA)
    return out


def aplicar_mapa_con_int(serie: pd.Series, mapa: dict[str, str]) -> pd.Series:
    """Variante que primero intenta convertir códigos numéricos "1.0" → "1".

    Util para columnas de región/edad de Invamer donde los códigos vienen
    como flotantes después de la lectura de Excel.
    """

    def _coerce(x: object) -> str:
        if pd.isna(x):
            return ""
        s = str(x).strip()
        with contextlib.suppress(ValueError, TypeError):
            s = str(int(float(s)))
        return normalize_text(s)

    s_norm = serie.map(_coerce)
    mapped = s_norm.map(mapa)
    out = mapped.where(mapped.notna(), serie.astype("string[pyarrow]").str.strip())
    out = out.where(out.astype("string[pyarrow]").str.len() > 0, pd.NA)
    return out
