"""Generación de nombres canónicos de columnas para matchups de segunda vuelta.

Una segunda vuelta entre dos candidatos canónicos se nombra como:
    sv_{key_a}_vs_{key_b}
donde key_a < key_b alfabéticamente. Esto evita que la misma matchup
aparezca con dos columnas distintas según el orden en que la encuestadora
la presentó.

Ejemplo:
    >>> sv_col_name("Iván Cepeda", "Abelardo de la Espriella", harmonizer)
    'sv_cepeda_vs_espriella'
"""

from __future__ import annotations

import json
import re

import pandas as pd

from encuestas_lib.harmonization.candidates import CandidateHarmonizer


def sv_col_name(
    cand_a: str | None,
    cand_b: str | None,
    harmonizer: CandidateHarmonizer,
) -> str | None:
    """Devolver el nombre de columna para una matchup de SV.

    Args:
        cand_a: nombre canónico del primer candidato.
        cand_b: nombre canónico del segundo candidato.
        harmonizer: para resolver canonical → key.

    Returns:
        sv_{key_a}_vs_{key_b} con keys ordenadas alfabéticamente, o None
        si alguno de los candidatos no está registrado.
    """
    if not cand_a or not cand_b:
        return None
    k1 = harmonizer.key_de(cand_a)
    k2 = harmonizer.key_de(cand_b)
    if not k1 or not k2:
        return None
    a, b = sorted([k1, k2])
    return f"sv_{a}_vs_{b}"


def parse_atlas_label(
    label: str,
    harmonizer: CandidateHarmonizer,
) -> str | None:
    """Convertir una etiqueta tipo Atlas (e.g. 'Espriella vs. Cepeda') a sv_col_name.

    Args:
        label: etiqueta cruda del JSON de Atlas.
        harmonizer: para armonizar nombres.

    Returns:
        Nombre de columna sv_xxx_vs_yyy o None si no parsea.
    """
    parts = re.split(r"\s+vs\.?\s+", str(label), flags=re.IGNORECASE)
    if len(parts) != 2:
        return None
    h1 = harmonizer.harmonize(parts[0].strip())
    h2 = harmonizer.harmonize(parts[1].strip())
    return sv_col_name(h1, h2, harmonizer)


def parse_atlas_json_cell(
    cell: object,
    harmonizer: CandidateHarmonizer,
) -> dict[str, str | None]:
    """Parsear una celda JSON de Atlas con múltiples matchups en SV.

    El campo `second_round_president_2026_co` viene como:
        [{"label": "Espriella vs. Cepeda", "value": "Iván Cepeda"}, ...]

    Args:
        cell: celda cruda (string JSON o NaN).
        harmonizer: para armonizar.

    Returns:
        Dict {sv_col_name: candidato_canónico}. Vacío si la celda es NaN o
        si el JSON está malformado.
    """
    if pd.isna(cell):
        return {}
    s = str(cell).strip()
    if not s:
        return {}
    try:
        items = json.loads(s)
    except (ValueError, TypeError):
        return {}
    if not isinstance(items, list):
        return {}

    result: dict[str, str | None] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        col = parse_atlas_label(item.get("label", ""), harmonizer)
        if col:
            result[col] = harmonizer.harmonize(item.get("value"))
    return result


# ════════════════════════════════════════════════════════════════════════════
#  Schema canónico de columnas de salida
# ════════════════════════════════════════════════════════════════════════════
META_COLS: list[str] = ["encuestadora", "fecha", "factor"]

DEMO_COLS: list[str] = [
    "departamento",
    "municipio",
    "region",
    "zona",
    "genero",
    "edad_grupo",
    "estrato",
    "educacion",
]

VOTE_COLS: list[str] = [
    "primera_vuelta",
    "primera_vuelta_espontanea",
]

OPINION_COLS: list[str] = ["aprobacion_petro"]


def all_meta_columns() -> list[str]:
    """Devolver todas las columnas que NO son matchups de SV."""
    return META_COLS + DEMO_COLS + VOTE_COLS + OPINION_COLS
