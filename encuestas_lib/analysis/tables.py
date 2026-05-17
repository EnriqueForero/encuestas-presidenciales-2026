"""Tablas analíticas básicas.

Reproducción de las tablas del repo original con código modular y vectorizado:
    - primera_vuelta_total
    - voto_por_region / edad / genero
    - aprobacion_vs_voto / voto_vs_aprobacion
    - sesgo_por_encuestadora (house effects)
    - indecisos_* (demografías)
"""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from encuestas_lib.analysis.weighting import (
    calcular_por_encuesta,
    combinar_entre_encuestas,
)


# ════════════════════════════════════════════════════════════════════════════
#  Filtros de candidatos
# ════════════════════════════════════════════════════════════════════════════
def filtrar_voto_vigente(
    df: pd.DataFrame,
    candidatos_vigentes: Iterable[str],
    opciones_indecisos: Iterable[str],
) -> pd.DataFrame:
    """Mantener filas con voto en candidatos vigentes o en opciones de indeciso.

    Esto descarta menciones de candidatos retirados/no oficializados, pero
    conserva NS/NR, blanco, ninguno (que serán analizados como indecisos).
    """
    if "primera_vuelta" not in df.columns:
        return df.copy()
    permitidos = set(candidatos_vigentes) | set(opciones_indecisos)
    return df[df["primera_vuelta"].isin(permitidos)].copy()


def es_indeciso(valor: object, candidatos_reales: Iterable[str]) -> bool:
    """True si el valor NO es un candidato real (incluye blanco, NS/NR, ninguno)."""
    if pd.isna(valor):
        return False
    return valor not in candidatos_reales


# ════════════════════════════════════════════════════════════════════════════
#  Tabla: primera vuelta total
# ════════════════════════════════════════════════════════════════════════════
def tabla_primera_vuelta_total(
    df: pd.DataFrame,
    pesos: dict[tuple[str, str], float],
) -> pd.DataFrame:
    """Intención de voto agregada en primera vuelta."""
    base = calcular_por_encuesta(df, group_cols=["primera_vuelta"], normalize_within=[])
    if base.empty:
        return pd.DataFrame(columns=["primera_vuelta", "valor"])
    out = combinar_entre_encuestas(base, pesos, group_cols=["primera_vuelta"], normalize_within=[])
    return out.sort_values("valor", ascending=False).reset_index(drop=True)


# ════════════════════════════════════════════════════════════════════════════
#  Tabla: voto por demográfica
# ════════════════════════════════════════════════════════════════════════════
def _tabla_voto_por_demografica(
    df: pd.DataFrame,
    pesos: dict[tuple[str, str], float],
    demo_col: str,
) -> pd.DataFrame:
    """Tabla voto × demográfica (cierre = 100% por categoría demográfica)."""
    if demo_col not in df.columns:
        return pd.DataFrame()

    base = calcular_por_encuesta(
        df,
        group_cols=[demo_col, "primera_vuelta"],
        normalize_within=[demo_col],
    )
    out = combinar_entre_encuestas(
        base, pesos, group_cols=[demo_col, "primera_vuelta"], normalize_within=[demo_col]
    )
    if out.empty:
        return out
    piv = out.pivot(index=demo_col, columns="primera_vuelta", values="valor").fillna(0).round(2)
    # reset_index para que la categoría quede como columna explícita en Excel
    return piv.reset_index()


def tabla_voto_por_region(df, pesos):
    """Voto × región."""
    return _tabla_voto_por_demografica(df, pesos, "region")


def tabla_voto_por_edad(df, pesos):
    """Voto × edad."""
    return _tabla_voto_por_demografica(df, pesos, "edad_grupo")


def tabla_voto_por_genero(df, pesos):
    """Voto × sexo."""
    return _tabla_voto_por_demografica(df, pesos, "sexo")


# ════════════════════════════════════════════════════════════════════════════
#  Tabla: género dentro de top-N candidatos
# ════════════════════════════════════════════════════════════════════════════
def tabla_genero_por_candidato_top4(
    df: pd.DataFrame,
    pesos: dict[tuple[str, str], float],
    top_n: int = 4,
) -> pd.DataFrame:
    """Distribución de género dentro del votante de cada candidato top-N."""
    if "sexo" not in df.columns:
        return pd.DataFrame()
    pv_total = tabla_primera_vuelta_total(df, pesos)
    if pv_total.empty:
        return pd.DataFrame()
    top = pv_total.head(top_n)["primera_vuelta"].tolist()
    sub = df[df["primera_vuelta"].isin(top)].copy()

    base = calcular_por_encuesta(
        sub,
        group_cols=["primera_vuelta", "sexo"],
        normalize_within=["primera_vuelta"],
    )
    out = combinar_entre_encuestas(
        base,
        pesos,
        group_cols=["primera_vuelta", "sexo"],
        normalize_within=["primera_vuelta"],
    )
    if out.empty:
        return pd.DataFrame()
    return (
        out.pivot(index="primera_vuelta", columns="sexo", values="valor")
        .fillna(0)
        .round(2)
        .reset_index()
    )


# ════════════════════════════════════════════════════════════════════════════
#  Tabla: aprobación de Petro × voto
# ════════════════════════════════════════════════════════════════════════════
def tabla_aprobacion_vs_voto(df, pesos):
    """Voto condicional a aprobación de Petro (filas = aprobación, suma = 100)."""
    base = calcular_por_encuesta(
        df,
        group_cols=["aprobacion_petro", "primera_vuelta"],
        normalize_within=["aprobacion_petro"],
    )
    out = combinar_entre_encuestas(
        base,
        pesos,
        group_cols=["aprobacion_petro", "primera_vuelta"],
        normalize_within=["aprobacion_petro"],
    )
    if out.empty:
        return out
    return (
        out.pivot(index="aprobacion_petro", columns="primera_vuelta", values="valor")
        .fillna(0)
        .round(2)
        .reset_index()
    )


def tabla_voto_vs_aprobacion(df, pesos):
    """Aprobación de Petro condicional al voto (filas = candidato, suma = 100)."""
    base = calcular_por_encuesta(
        df,
        group_cols=["primera_vuelta", "aprobacion_petro"],
        normalize_within=["primera_vuelta"],
    )
    out = combinar_entre_encuestas(
        base,
        pesos,
        group_cols=["primera_vuelta", "aprobacion_petro"],
        normalize_within=["primera_vuelta"],
    )
    if out.empty:
        return out
    return (
        out.pivot(index="primera_vuelta", columns="aprobacion_petro", values="valor")
        .fillna(0)
        .round(2)
        .reset_index()
    )


# ════════════════════════════════════════════════════════════════════════════
#  Tabla: sesgo por encuestadora (house effects)
# ════════════════════════════════════════════════════════════════════════════
def sesgo_por_encuestadora(
    df: pd.DataFrame,
    pesos: dict[tuple[str, str], float],
    variable: str,
) -> pd.DataFrame:
    """House effects: distribución propia vs promedio del resto.

    Mide en cuántos puntos porcentuales una encuestadora se desvía del
    promedio ponderado de las demás, por categoría de `variable`.

    Args:
        df: microdatos.
        pesos: dict de pesos.
        variable: nombre de la columna (e.g. 'sexo', 'edad_grupo').

    Returns:
        DataFrame con [encuestadora, variable, categoria,
        peso_encuestadora, peso_promedio_otras, sesgo_rel_pp].
    """
    base = calcular_por_encuesta(df, group_cols=[variable], normalize_within=[])
    if base.empty:
        return pd.DataFrame()

    encuestadoras = sorted(base["encuestadora"].dropna().unique())
    rows: list[dict] = []

    for enc in encuestadoras:
        own = base[base["encuestadora"] == enc]
        oth = base[base["encuestadora"] != enc]
        if own.empty or oth.empty:
            continue

        own_c = combinar_entre_encuestas(own, pesos, group_cols=[variable], normalize_within=[])
        oth_c = combinar_entre_encuestas(oth, pesos, group_cols=[variable], normalize_within=[])
        if own_c.empty or oth_c.empty:
            continue

        merged = own_c.merge(oth_c, on=variable, suffixes=("_enc", "_otras"))
        for _, r in merged.iterrows():
            rows.append(
                {
                    "encuestadora": enc,
                    "variable": variable,
                    "categoria": r[variable],
                    "peso_encuestadora": round(float(r["valor_enc"]), 2),
                    "peso_promedio_otras": round(float(r["valor_otras"]), 2),
                    "sesgo_rel_pp": round(float(r["valor_enc"] - r["valor_otras"]), 2),
                }
            )

    if not rows:
        return pd.DataFrame()
    return (
        pd.DataFrame(rows)
        .sort_values(["encuestadora", "sesgo_rel_pp"], ascending=[True, False])
        .reset_index(drop=True)
    )


# ════════════════════════════════════════════════════════════════════════════
#  Tablas: indecisos
# ════════════════════════════════════════════════════════════════════════════
def tabla_indecisos_demograficas(
    df: pd.DataFrame,
    pesos: dict[tuple[str, str], float],
    candidatos_reales: set[str],
    demo_cols: list[str] | None = None,
) -> dict[str, pd.DataFrame]:
    """Demografías de indecisos por variable.

    Args:
        df: microdatos completos (NO filtrados).
        pesos: dict de pesos.
        candidatos_reales: nombres canónicos de candidatos vigentes (sin blanco/NS/NR).
        demo_cols: variables a desglosar.

    Returns:
        dict variable → DataFrame.
    """
    if demo_cols is None:
        demo_cols = ["edad_grupo", "region", "sexo", "estrato"]
    if "primera_vuelta" not in df.columns:
        return {}

    indecisos = df[~df["primera_vuelta"].isin(candidatos_reales)].copy()
    if indecisos.empty:
        return {}

    out: dict[str, pd.DataFrame] = {}
    for col in demo_cols:
        if col not in indecisos.columns:
            continue
        base = calcular_por_encuesta(indecisos, group_cols=[col], normalize_within=[])
        if base.empty:
            continue
        agg = combinar_entre_encuestas(base, pesos, group_cols=[col], normalize_within=[])
        if agg.empty:
            continue
        out[col] = agg.round(2)
    return out


def tabla_indecisos_total(
    df: pd.DataFrame,
    pesos: dict[tuple[str, str], float],
    candidatos_reales: set[str],
) -> pd.DataFrame:
    """Porcentaje total de indecisos (combinado entre encuestas)."""
    if "primera_vuelta" not in df.columns:
        return pd.DataFrame()
    sub = df.dropna(subset=["primera_vuelta"]).copy()
    if sub.empty:
        return pd.DataFrame()
    sub["es_indeciso"] = (~sub["primera_vuelta"].isin(candidatos_reales)).astype(int)

    base = calcular_por_encuesta(
        sub,
        group_cols=["es_indeciso"],
        normalize_within=[],  # → %
    )
    if base.empty:
        return pd.DataFrame()
    out = combinar_entre_encuestas(base, pesos, group_cols=["es_indeciso"], normalize_within=[])
    if out.empty:
        return out
    pct_indecisos = float(out[out["es_indeciso"] == 1]["valor"].sum())
    return pd.DataFrame([{"pct_total": round(pct_indecisos, 2)}])
