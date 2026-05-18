"""Helpers internos de visualización (no exportados como API pública).

Funciones puras para extracción y formato de datos a partir del dict
``tablas`` que produce :class:`encuestas_lib.pipeline.analyze.AnalysisPipeline`.
"""

from __future__ import annotations

import pandas as pd


def top_n_candidatos(
    tablas: dict[str, pd.DataFrame],
    n: int = 5,
    tabla_key: str = "primera_vuelta_total",
    valor_col: str = "valor",
    nombre_col: str = "primera_vuelta",
) -> list[str]:
    """Devolver los ``n`` candidatos con mayor valor en ``tabla_key``.

    Args:
        tablas: dict de DataFrames producido por ``AnalysisPipeline.run``.
        n: cuántos candidatos retornar.
        tabla_key: nombre de la tabla en ``tablas`` con el ranking total.
        valor_col: nombre de la columna de valor en la tabla.
        nombre_col: nombre de la columna de nombre del candidato.

    Returns:
        Lista de nombres canónicos de candidatos, ordenada de mayor a menor.

    Raises:
        KeyError: si ``tabla_key`` no está en ``tablas``.
    """
    if tabla_key not in tablas:
        raise KeyError(f"Tabla requerida no encontrada: {tabla_key!r}")
    return tablas[tabla_key].nlargest(n, valor_col)[nombre_col].tolist()


def candidatos_y_indecisos(
    tablas: dict[str, pd.DataFrame],
    indecisos_cats: frozenset[str],
    tabla_key: str = "primera_vuelta_total",
    nombre_col: str = "primera_vuelta",
) -> tuple[list[str], list[str]]:
    """Separar la lista de candidatos en *vigentes* e *indecisos*.

    Args:
        tablas: dict de DataFrames del pipeline.
        indecisos_cats: conjunto canónico de categorías especiales.
        tabla_key: nombre de la tabla con el ranking total.
        nombre_col: nombre de la columna del candidato.

    Returns:
        Tupla ``(candidatos, indecisos)`` — ambas listas en el orden en que
        aparecen en la tabla original.
    """
    if tabla_key not in tablas:
        return [], []
    todos = tablas[tabla_key][nombre_col].tolist()
    cands = [c for c in todos if c not in indecisos_cats]
    indec = [c for c in todos if c in indecisos_cats]
    return cands, indec


__all__ = ["candidatos_y_indecisos", "top_n_candidatos"]
