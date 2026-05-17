"""Estrategias de ponderación entre encuestas.

Cada estrategia es una función pura: recibe el catálogo de encuestas y
devuelve un dict (encuestadora, fecha_str) → peso.

La decisión metodológica está documentada en configs/weights.yaml.
"""

from __future__ import annotations

from datetime import date
from math import exp, log

import pandas as pd

from encuestas_lib.config import SurveyEntry, WeightingConfig


# ════════════════════════════════════════════════════════════════════════════
#  Estrategias
# ════════════════════════════════════════════════════════════════════════════
def weights_uniform(surveys: list[SurveyEntry]) -> dict[tuple[str, str], float]:
    """Todas las encuestas pesan 1."""
    return {(s.encuestadora, s.fecha_str): 1.0 for s in surveys}


def weights_sample_size(surveys: list[SurveyEntry]) -> dict[tuple[str, str], float]:
    """Peso = n_muestra; 1 si no está declarado."""
    return {(s.encuestadora, s.fecha_str): float(s.n_muestra or 1) for s in surveys}


def weights_recency_decay(
    surveys: list[SurveyEntry],
    half_life_days: int = 21,
) -> dict[tuple[str, str], float]:
    """Decaimiento exponencial con vida media `half_life_days`."""
    if not surveys:
        return {}
    t_ref: date = max(s.fecha for s in surveys)
    tau = half_life_days / log(2)
    out: dict[tuple[str, str], float] = {}
    for s in surveys:
        delta = (t_ref - s.fecha).days
        out[(s.encuestadora, s.fecha_str)] = float(exp(-delta / tau))
    return out


def weights_inverse_recency_size(
    surveys: list[SurveyEntry],
    half_life_days: int = 21,
) -> dict[tuple[str, str], float]:
    """Combina tamaño muestral con decaimiento temporal.

    peso = n_muestra × 0.5 ** (días_desde_corte / half_life_days)
    """
    decay = weights_recency_decay(surveys, half_life_days)
    out: dict[tuple[str, str], float] = {}
    for s in surveys:
        n = float(s.n_muestra or 1)
        out[(s.encuestadora, s.fecha_str)] = n * decay[(s.encuestadora, s.fecha_str)]
    return out


def weights_manual(
    surveys: list[SurveyEntry],
    manual: dict[tuple[str, str], float],
) -> dict[tuple[str, str], float]:
    """Pesos explícitos por (encuestadora, fecha).

    Las encuestas no presentes en `manual` reciben peso 0 y son excluidas.
    """
    out: dict[tuple[str, str], float] = {}
    for s in surveys:
        out[(s.encuestadora, s.fecha_str)] = manual.get((s.encuestadora, s.fecha_str), 0.0)
    return out


# ════════════════════════════════════════════════════════════════════════════
#  Dispatcher
# ════════════════════════════════════════════════════════════════════════════
def resolve_weights(
    config: WeightingConfig,
    surveys: list[SurveyEntry],
) -> dict[tuple[str, str], float]:
    """Resolver pesos según la estrategia activa.

    Args:
        config: configuración de pesos.
        surveys: lista de encuestas registradas.

    Returns:
        Dict (encuestadora, fecha_str) → peso.

    Raises:
        ValueError: si la estrategia no está implementada.
    """
    strategy = config.active_strategy
    params = config.params

    if strategy == "uniform":
        return weights_uniform(surveys)
    if strategy == "sample_size":
        return weights_sample_size(surveys)
    if strategy == "recency_decay":
        return weights_recency_decay(surveys, **params)
    if strategy == "inverse_recency_size":
        return weights_inverse_recency_size(surveys, **params)
    if strategy == "manual":
        return weights_manual(surveys, config.manual_weights)
    raise ValueError(f"Estrategia de ponderación desconocida: {strategy}")


# ════════════════════════════════════════════════════════════════════════════
#  Combinar resultados entre encuestas
# ════════════════════════════════════════════════════════════════════════════
def combinar_entre_encuestas(
    tabla_encuesta: pd.DataFrame,
    pesos: dict[tuple[str, str], float],
    group_cols: list[str],
    normalize_within: list[str] | None = None,
    value_col: str = "valor",
) -> pd.DataFrame:
    """Combinar resultados por (encuestadora, fecha) en una tabla agregada.

    Aplica los pesos de la estrategia activa y agrega por `group_cols`.

    Args:
        tabla_encuesta: DataFrame con columnas
            [encuestadora, fecha, *group_cols, value_col].
        pesos: dict (encuestadora, fecha_str) → peso.
        group_cols: columnas de agrupación finales.
        normalize_within: si no es None, renormaliza a 100 dentro de estas
            columnas (subconjunto de group_cols).
        value_col: nombre de la columna de valor.

    Returns:
        DataFrame agregado con columnas [*group_cols, value_col].
    """
    if tabla_encuesta.empty:
        return pd.DataFrame(columns=[*group_cols, value_col])

    d = tabla_encuesta.copy()
    d["fecha_str"] = d["fecha"].astype(str).str[:10]

    # Mapear pesos
    d["peso_encuesta"] = d.apply(
        lambda r: pesos.get((r["encuestadora"], r["fecha_str"]), 0.0),
        axis=1,
    )
    d = d[d["peso_encuesta"] > 0].copy()
    if d.empty:
        return pd.DataFrame(columns=[*group_cols, value_col])

    d["_num"] = d[value_col] * d["peso_encuesta"]
    out = (
        d.groupby(group_cols, dropna=False)
        .agg(num=("_num", "sum"), den=("peso_encuesta", "sum"))
        .reset_index()
    )
    out = out[out["den"] > 0].copy()
    out[value_col] = out["num"] / out["den"]
    out = out.drop(columns=["num", "den"])

    if normalize_within is not None:
        out = _renormalize_to_100(out, value_col, normalize_within)

    out[value_col] = out[value_col].round(2)
    return out


def _renormalize_to_100(
    df: pd.DataFrame,
    value_col: str,
    group_cols: list[str],
) -> pd.DataFrame:
    """Renormalizar para que la suma de value_col sea 100 dentro de group_cols."""
    out = df.copy()
    if not group_cols:
        total = out[value_col].sum()
        if total > 0:
            out[value_col] = out[value_col] / total * 100
        return out
    total = out.groupby(group_cols)[value_col].transform("sum")
    mask = total > 0
    out.loc[mask, value_col] = out.loc[mask, value_col] / total[mask] * 100
    return out


# ════════════════════════════════════════════════════════════════════════════
#  Calcular métricas por encuesta (antes de combinar)
# ════════════════════════════════════════════════════════════════════════════
def calcular_por_encuesta(
    df: pd.DataFrame,
    group_cols: str | list[str],
    normalize_within: list[str] | None,
    value_col: str = "factor",
) -> pd.DataFrame:
    """Agregar métrica por encuesta (encuestadora + fecha) y combinación.

    Args:
        df: DataFrame de microdatos (incluye 'encuestadora', 'fecha', 'factor').
        group_cols: columna(s) de salida (categorías).
        normalize_within: subconjunto de group_cols dentro del cual renormalizar
            a 100. [] = renormaliza dentro de toda la encuesta. None = devuelve
            sumas absolutas.
        value_col: columna de pesos (usualmente 'factor').

    Returns:
        DataFrame con [encuestadora, fecha, *group_cols, valor].
    """
    cols = [group_cols] if isinstance(group_cols, str) else list(group_cols)
    base_cols = ["encuestadora", "fecha", value_col, *cols]
    sub = df[base_cols].copy()
    sub = sub[sub[value_col].notna()]
    for c in cols:
        sub = sub[sub[c].notna()]
    if sub.empty:
        return pd.DataFrame()

    agg = (
        sub.groupby(["encuestadora", "fecha", *cols], dropna=False)[value_col]
        .sum()
        .reset_index(name="valor")
    )

    if normalize_within is None:
        return agg

    denom_keys = ["encuestadora", "fecha", *list(normalize_within)]
    denom = agg.groupby(denom_keys, dropna=False)["valor"].transform("sum")
    mask = denom > 0
    agg = agg.loc[mask].copy()
    agg["valor"] = agg.loc[mask, "valor"] / denom[mask] * 100
    agg = _renormalize_to_100(agg, "valor", denom_keys)
    return agg
