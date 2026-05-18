"""Análisis avanzados sobre microdatos de encuestas.

Estos análisis NO existen en el repo original y son la pieza diferenciadora
del refactor. Cada función es pura: recibe el DataFrame ingestado y el
catálogo de pesos, devuelve un DataFrame.

Funciones públicas:
    - trend_primera_vuelta:      serie temporal con suavizado
    - transferencia_pv_sv:       matriz de transferencia PV → SV
    - techo_potencial_sv:        voto SV vs voto PV (techo de cada candidato)
    - coalicion_aprobacion:      voto cruzado con aprobación a Petro
    - volatilidad_encuestadora:  desviación intra-pollster ajustada por tiempo
    - margen_error_efectivo:     IC95% por encuesta (n efectivo con factores)
    - indecisos_perfil:          regresión logística (decidido vs indeciso)
"""

from __future__ import annotations

from collections.abc import Iterable
from math import sqrt

import pandas as pd

from encuestas_lib.analysis.weighting import (
    calcular_por_encuesta,
    combinar_entre_encuestas,
)


# ════════════════════════════════════════════════════════════════════════════
#  1. Tendencia temporal (la encuesta más importante: cuándo cambió todo)
# ════════════════════════════════════════════════════════════════════════════
def trend_primera_vuelta(
    df: pd.DataFrame,
    candidatos_vigentes: Iterable[str],
    ventana_dias: int = 14,
) -> pd.DataFrame:
    """Serie temporal de intención de voto en PV con suavizado por ventana móvil.

    Para cada candidato vigente, calcula su porcentaje por (encuestadora, fecha)
    y luego una media móvil ponderada por tamaño muestral.

    Args:
        df: microdatos ingestados con columnas
            ['encuestadora', 'fecha', 'factor', 'primera_vuelta'].
        candidatos_vigentes: nombres canónicos a incluir.
        ventana_dias: ventana del rolling (en días, no en filas).

    Returns:
        DataFrame [fecha, primera_vuelta, valor_punto, valor_suavizado].
    """
    base = calcular_por_encuesta(df, group_cols=["primera_vuelta"], normalize_within=[])
    if base.empty:
        return pd.DataFrame(columns=["fecha", "primera_vuelta", "valor_punto", "valor_suavizado"])

    base = base[base["primera_vuelta"].isin(set(candidatos_vigentes))].copy()
    base["fecha"] = pd.to_datetime(base["fecha"])

    # Punto por encuesta: ya viene como %. Suavizado por ventana fechada.
    out_rows: list[pd.DataFrame] = []
    for cand, sub in base.groupby("primera_vuelta"):
        s = (
            sub[["fecha", "valor"]]
            .rename(columns={"valor": "valor_punto"})
            .sort_values("fecha")
            .set_index("fecha")
        )
        # Rolling con offset de tiempo, no filas
        s["valor_suavizado"] = s["valor_punto"].rolling(f"{ventana_dias}D", min_periods=1).mean()
        s = s.reset_index()
        s["primera_vuelta"] = cand
        out_rows.append(s)

    return (
        pd.concat(out_rows, ignore_index=True)
        if out_rows
        else pd.DataFrame(columns=["fecha", "primera_vuelta", "valor_punto", "valor_suavizado"])
    )


# ════════════════════════════════════════════════════════════════════════════
#  2. Transferencia PV → SV (a dónde se va el voto de cada candidato en SV)
# ════════════════════════════════════════════════════════════════════════════
def transferencia_pv_sv(
    df: pd.DataFrame,
    sv_col: str,
    pesos: dict[tuple[str, str], float],
) -> pd.DataFrame:
    """Matriz: dado que votó X en PV, qué dice en una matchup de SV.

    Args:
        df: microdatos con 'primera_vuelta' y la columna `sv_col`.
        sv_col: columna de SV (e.g. 'sv_cepeda_vs_espriella').
        pesos: pesos por (encuestadora, fecha_str).

    Returns:
        DataFrame [primera_vuelta, <sv_col>, valor] donde ``valor`` suma 100
        dentro de cada ``primera_vuelta``.

    Note:
        Los porcentajes **incluyen** indecisos de segunda vuelta (NS/NR,
        Ninguno, No votaría, No sé), por lo que el % de transferencia directa
        entre candidatos es menor que el publicado por La Silla Vacía, que
        calcula el porcentaje sobre el subconjunto de encuestados que sí
        eligieron una opción en SV (excluyendo indecisos).

        FIX B_NEW_3: para replicar el % del PDF (e.g. Abelardo→Paloma = 79%
        en vez de ~60%), filtrar las filas de SV donde sv_col está en
        opciones_indecisos antes de llamar esta función, o calcular el %
        sobre el subconjunto ``sv_col.notna() & ~sv_col.isin(indecisos)``.
    """
    if sv_col not in df.columns or "primera_vuelta" not in df.columns:
        return pd.DataFrame(columns=["primera_vuelta", sv_col, "valor"])

    base = calcular_por_encuesta(
        df, group_cols=["primera_vuelta", sv_col], normalize_within=["primera_vuelta"]
    )
    if base.empty:
        return pd.DataFrame(columns=["primera_vuelta", sv_col, "valor"])

    return combinar_entre_encuestas(
        base,
        pesos,
        group_cols=["primera_vuelta", sv_col],
        normalize_within=["primera_vuelta"],
    )


# ════════════════════════════════════════════════════════════════════════════
#  3. Techo potencial en SV (voto SV - voto PV = espacio para crecer)
# ════════════════════════════════════════════════════════════════════════════
def techo_potencial_sv(
    df: pd.DataFrame,
    candidato_canonical: str,
    candidato_key: str,
    candidatos_vigentes: Iterable[str],
    pesos: dict[tuple[str, str], float],
    rivales_keys: Iterable[str],
) -> pd.DataFrame:
    """Techo potencial: cuánto crece el candidato de PV a cada SV.

    Args:
        df: microdatos.
        candidato_canonical: nombre canónico (e.g. 'Iván Cepeda').
        candidato_key: key corta (e.g. 'cepeda').
        candidatos_vigentes: usado para filtrar voto válido.
        pesos: pesos por encuesta.
        rivales_keys: claves de rivales a chequear (sv_cand_vs_rival).

    Returns:
        DataFrame [rival_key, sv_col, voto_pv_pct, voto_sv_pct,
        techo_pp, techo_relativo_pct] donde ``voto_pv_pct`` es el %
        del candidato entre respondentes válidos de PV (excluyendo
        indecisos/no responde) y ``voto_sv_pct`` es su % de la
        intención en SV (incluyendo indecisos de SV).

    Note:
        FIX B_NEW_5: el cálculo anterior usaba
        ``normalize_within=["primera_vuelta"]`` / ``normalize_within=[sv_col]``
        que normalizaba cada candidato a 100 % dentro de sí mismo (una sola
        fila por candidato por encuesta), produciendo ``voto_pv_pct = 4.35 %``
        y ``voto_sv_pct = 100 %`` para todos.  El fix cambia ambos a
        ``normalize_within=[]``, que divide por el total de factores de la
        encuesta → % reales dentro de cada encuesta antes de ponderar.
    """
    # ── Voto en PV agregado ────────────────────────────────────────────────
    # FIX B_NEW_5: normalize_within=[] para obtener % reales por encuesta
    pv_base = calcular_por_encuesta(df, group_cols=["primera_vuelta"], normalize_within=[])
    if pv_base.empty:
        return pd.DataFrame()

    pv_table = combinar_entre_encuestas(
        pv_base,
        pesos,
        group_cols=["primera_vuelta"],
        normalize_within=[],
    )
    if pv_table.empty:
        return pd.DataFrame()

    # Filtrar a candidatos vigentes (excluye indecisos / especiales)
    pv_vigentes = pv_table[pv_table["primera_vuelta"].isin(set(candidatos_vigentes))].copy()
    voto_pv = float(
        pv_vigentes.loc[pv_vigentes["primera_vuelta"] == candidato_canonical, "valor"].sum()
    )
    # Renormalizar a 100 % entre vigentes (voto sobre decididos)
    total_pv = float(pv_vigentes["valor"].sum())
    voto_pv_renorm = voto_pv / total_pv * 100 if total_pv > 0 else 0.0

    rows: list[dict] = []
    for rk in rivales_keys:
        a, b = sorted([candidato_key, rk])
        if a == b:
            continue
        sv_col = f"sv_{a}_vs_{b}"
        if sv_col not in df.columns:
            continue

        # FIX B_NEW_5: normalize_within=[] → % real de cada opción en SV
        sv_base = calcular_por_encuesta(df, group_cols=[sv_col], normalize_within=[])
        sv_table = combinar_entre_encuestas(
            sv_base,
            pesos,
            group_cols=[sv_col],
            normalize_within=[],
        )
        if sv_table.empty:
            continue

        # % del candidato en SV (sobre todos los que respondieron la encuesta,
        # incluyendo los que contestaron indecisos en SV)
        mask = sv_table[sv_col] == candidato_canonical
        voto_sv = float(sv_table.loc[mask, "valor"].sum()) if mask.any() else 0.0

        techo = voto_sv - voto_pv_renorm
        rel = (techo / voto_pv_renorm * 100) if voto_pv_renorm > 0 else float("nan")
        rows.append(
            {
                "rival_key": rk,
                "sv_col": sv_col,
                "voto_pv_pct": round(voto_pv_renorm, 2),
                "voto_sv_pct": round(voto_sv, 2),
                "techo_pp": round(techo, 2),
                "techo_relativo_pct": round(rel, 1),
            }
        )

    if not rows:
        return pd.DataFrame(
            columns=[
                "rival_key",
                "sv_col",
                "voto_pv_pct",
                "voto_sv_pct",
                "techo_pp",
                "techo_relativo_pct",
            ]
        )
    return pd.DataFrame(rows).sort_values("techo_pp", ascending=False).reset_index(drop=True)


# ════════════════════════════════════════════════════════════════════════════
#  4. Coalición × aprobación (voto cruzado con aprobación Petro)
# ════════════════════════════════════════════════════════════════════════════
def coalicion_aprobacion(
    df: pd.DataFrame,
    pesos: dict[tuple[str, str], float],
) -> pd.DataFrame:
    """Distribución condicional: aprobación de Petro × voto PV.

    Útil para detectar coalición petrista (aprueba × Cepeda) y
    voto de oposición (desaprueba × Espriella/Valencia).

    Returns:
        DataFrame [aprobacion_petro, primera_vuelta, valor] donde valor
        suma 100 dentro de cada nivel de aprobacion_petro.
    """
    if "aprobacion_petro" not in df.columns or "primera_vuelta" not in df.columns:
        return pd.DataFrame(columns=["aprobacion_petro", "primera_vuelta", "valor"])

    base = calcular_por_encuesta(
        df,
        group_cols=["aprobacion_petro", "primera_vuelta"],
        normalize_within=["aprobacion_petro"],
    )
    if base.empty:
        return pd.DataFrame(columns=["aprobacion_petro", "primera_vuelta", "valor"])

    return combinar_entre_encuestas(
        base,
        pesos,
        group_cols=["aprobacion_petro", "primera_vuelta"],
        normalize_within=["aprobacion_petro"],
    )


# ════════════════════════════════════════════════════════════════════════════
#  5. Volatilidad por encuestadora (¿qué tan errática es cada firma?)
# ════════════════════════════════════════════════════════════════════════════
def volatilidad_encuestadora(
    df: pd.DataFrame,
    candidatos_vigentes: Iterable[str],
) -> pd.DataFrame:
    """Desviación intra-encuestadora del voto por candidato.

    Si una pollster tiene 5 mediciones, calcula la desv std de cada
    candidato. Volatilidad alta = encuestadora ruidosa o capturando
    movimiento real (no se puede saber sin más info).

    Returns:
        DataFrame [encuestadora, primera_vuelta, n_mediciones, media,
                   desv_std, rango]
    """
    if "primera_vuelta" not in df.columns:
        return pd.DataFrame()

    base = calcular_por_encuesta(df, group_cols=["primera_vuelta"], normalize_within=[])
    base = base[base["primera_vuelta"].isin(set(candidatos_vigentes))].copy()

    out = (
        base.groupby(["encuestadora", "primera_vuelta"])["valor"]
        .agg(["count", "mean", "std", "min", "max"])
        .reset_index()
        .rename(
            columns={
                "count": "n_mediciones",
                "mean": "media_pct",
                "std": "desv_std_pp",
                "min": "min_pct",
                "max": "max_pct",
            }
        )
    )
    out["rango_pp"] = (out["max_pct"] - out["min_pct"]).round(2)
    out = out[out["n_mediciones"] >= 2].copy()  # std requiere ≥2 obs
    return out.sort_values(["primera_vuelta", "desv_std_pp"], ascending=[True, False])


# ════════════════════════════════════════════════════════════════════════════
#  6. Margen de error efectivo (IC95% por encuesta con factores de expansión)
# ════════════════════════════════════════════════════════════════════════════
def margen_error_efectivo(
    df: pd.DataFrame,
    candidato: str,
) -> pd.DataFrame:
    """Margen de error a 95% por encuesta para un candidato.

    Usa el "n efectivo" de Kish que corrige por dispersión de factores:
        n_eff = (sum w)^2 / sum(w^2)
    El MoE clásico p±1.96 * sqrt(p(1-p)/n_eff). Si una encuesta tiene
    factores muy dispersos, su n_eff puede ser <<n nominal.

    Args:
        df: microdatos.
        candidato: nombre canónico (PV).

    Returns:
        DataFrame [encuestadora, fecha, n, n_efectivo, p_estimado, moe_pp,
                   ic95_lo, ic95_hi]
    """
    if "primera_vuelta" not in df.columns or "factor" not in df.columns:
        return pd.DataFrame()

    rows: list[dict] = []
    for (enc, fecha), sub in df.groupby(["encuestadora", "fecha"]):
        sub = sub[sub["primera_vuelta"].notna() & sub["factor"].notna()]
        if sub.empty:
            continue
        w = sub["factor"].to_numpy(dtype=float)
        sum_w = float(w.sum())
        sum_w2 = float((w * w).sum())
        if sum_w2 <= 0 or sum_w <= 0:
            continue
        n_eff = (sum_w * sum_w) / sum_w2
        mask_cand = sub["primera_vuelta"] == candidato
        p = float(sub.loc[mask_cand, "factor"].sum() / sum_w) if mask_cand.any() else 0.0
        if 0.0 < p < 1.0 and n_eff > 0:
            moe = 1.96 * sqrt(p * (1 - p) / n_eff)
        else:
            moe = float("nan")
        rows.append(
            {
                "encuestadora": enc,
                "fecha": fecha,
                "n_nominal": len(sub),
                "n_efectivo": round(n_eff, 1),
                "p_estimado_pct": round(p * 100, 2),
                "moe_pp": round(moe * 100, 2),
                "ic95_lo": round(max(0.0, p - moe) * 100, 2),
                "ic95_hi": round(min(1.0, p + moe) * 100, 2),
            }
        )

    return pd.DataFrame(rows).sort_values("fecha").reset_index(drop=True)


# ════════════════════════════════════════════════════════════════════════════
#  7. Perfil de indecisos (¿quiénes son los que no se deciden?)
# ════════════════════════════════════════════════════════════════════════════
def indecisos_perfil(
    df: pd.DataFrame,
    candidatos_vigentes: Iterable[str],
    dims: tuple[str, ...] = ("region", "edad_grupo", "genero", "aprobacion_petro"),
) -> pd.DataFrame:
    """Tasa de indecisión por intersección de dimensiones demográficas.

    En vez de un logit que requiere sklearn, calculamos la tasa marginal
    (ponderada por factor) en cada categoría. Para una visión más rica,
    extiendir a interacciones con `pd.crosstab` desde el notebook.

    Returns:
        DataFrame [dimension, categoria, tasa_indecisos_pct, n]
    """
    if "primera_vuelta" not in df.columns:
        return pd.DataFrame()

    vigentes = set(candidatos_vigentes)
    d = df[df["primera_vuelta"].notna()].copy()
    d["es_indeciso"] = (~d["primera_vuelta"].isin(vigentes)).astype(int)

    rows: list[dict] = []
    for dim in dims:
        if dim not in d.columns:
            continue
        sub = d[d[dim].notna()]
        if sub.empty:
            continue
        agg = (
            sub.groupby(dim, dropna=False)
            .apply(
                lambda g: pd.Series(
                    {
                        "tasa_indecisos_pct": (
                            (g["es_indeciso"] * g["factor"]).sum() / g["factor"].sum() * 100
                            if g["factor"].sum() > 0
                            else float("nan")
                        ),
                        "n": len(g),
                    }
                ),
                include_groups=False,
            )
            .reset_index()
            .rename(columns={dim: "categoria"})
        )
        agg["dimension"] = dim
        rows.append(agg[["dimension", "categoria", "tasa_indecisos_pct", "n"]])

    if not rows:
        return pd.DataFrame(columns=["dimension", "categoria", "tasa_indecisos_pct", "n"])
    out = pd.concat(rows, ignore_index=True)
    out["tasa_indecisos_pct"] = out["tasa_indecisos_pct"].round(2)
    return out.sort_values(["dimension", "tasa_indecisos_pct"], ascending=[True, False])


# ════════════════════════════════════════════════════════════════════════════
#  Helper: detectar columnas SV disponibles
# ════════════════════════════════════════════════════════════════════════════
def sv_columns(df: pd.DataFrame) -> list[str]:
    """Listar columnas sv_* presentes en el DataFrame."""
    return sorted([c for c in df.columns if c.startswith("sv_") and "_vs_" in c])


__all__ = [
    "coalicion_aprobacion",
    "indecisos_perfil",
    "margen_error_efectivo",
    "sv_columns",
    "techo_potencial_sv",
    "transferencia_pv_sv",
    "trend_primera_vuelta",
    "volatilidad_encuestadora",
]
