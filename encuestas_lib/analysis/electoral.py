"""Módulo de análisis electoral avanzado para segunda vuelta.

Funciones de modelación cuantitativa para el análisis de transferencia de voto,
simulación de segunda vuelta (Monte Carlo), análisis de factores de swing y
techo de rechazo.

Uso:
    >>> from encuestas_lib.analysis.electoral import (
    ...     trasvase_candidato,
    ...     simular_segunda_vuelta,
    ...     sensibilidad_2v,
    ...     calcular_techo_rechazo,
    ... )

Diseño:
    * Todas las funciones son puras (sin efectos secundarios).
    * Devuelven DataFrames estructurados, compatibles con Plotly/Excel.
    * Parámetros de incertidumbre expresados como tuplas (min, max).
    * Escalable: agregar nuevos candidatos sin cambiar la interfaz.
"""

from __future__ import annotations

import warnings
from collections.abc import Collection, Mapping
from typing import NamedTuple

import numpy as np
import pandas as pd

# ══════════════════════════════════════════════════════════════════════════════
#  Types
# ══════════════════════════════════════════════════════════════════════════════

#: Rango de transferencia (min_pct, max_pct) expresado en porcentaje (0–100).
TransferRango = tuple[float, float]

#: Matriz de transferencia: {candidato_pv: {destino_sv: (min%, max%)}}.
MatrizTransferencia = Mapping[str, Mapping[str, TransferRango]]

INDECISOS_SV: frozenset[str] = frozenset(
    {"NS/NR", "Ninguno", "Voto en blanco", "No votaría", "No sé"}
)


# ══════════════════════════════════════════════════════════════════════════════
#  1. Transferencia de voto para candidatos específicos
# ══════════════════════════════════════════════════════════════════════════════
def trasvase_candidato(
    tablas: Mapping[str, pd.DataFrame],
    sv_col: str,
    candidatos_pv: Collection[str],
    excluir_indecisos_sv: bool = True,
) -> pd.DataFrame:
    """Calcular el % de transferencia de voto para candidatos PV específicos.

    Para cada candidato en *candidatos_pv*, calcula qué fracción de sus
    votantes se trasladaría a cada opción de SV en el matchup *sv_col*.

    Args:
        tablas: diccionario de tablas analíticas producido por ``AnalysisPipeline``.
        sv_col: nombre de la hoja de transferencia (ej. "transfer_sv_cepeda_vs_espriella").
        candidatos_pv: lista de nombres canónicos de candidatos PV a analizar.
        excluir_indecisos_sv: si True, normaliza sobre los respondentes que SÍ
            eligieron una opción en SV (excluye NS/NR, Ninguno, etc.). El % resultante
            es directamente comparable con las cifras del PDF de La Silla Vacía.
            Si False, usa el denominador total (incluye indecisos SV).

    Returns:
        DataFrame con columnas: primera_vuelta · sv_opcion · pct_total ·
        pct_decididos · n_sv_options.

    Example:
        >>> t = trasvase_candidato(tablas, "transfer_sv_cepeda_vs_espriella",
        ...                        ["Sergio Fajardo", "Claudia López"])
        >>> t[t["primera_vuelta"] == "Sergio Fajardo"]
    """
    tabla_key = sv_col if sv_col.startswith("transfer_") else f"transfer_{sv_col}"
    if tabla_key not in tablas:
        warnings.warn(f"Tabla '{tabla_key}' no encontrada en tablas.", stacklevel=2)
        return pd.DataFrame()

    t = tablas[tabla_key]
    # Detectar la columna de opciones SV (segunda columna no-PV)
    pv_key = "primera_vuelta"
    if pv_key not in t.columns:
        warnings.warn(f"Columna '{pv_key}' no encontrada en '{tabla_key}'.", stacklevel=2)
        return pd.DataFrame()

    # Inferir nombre de columna SV
    sv_opt_col = next((c for c in t.columns if c not in {pv_key, "valor"}), None)
    if sv_opt_col is None:
        warnings.warn("No se encontró columna de opciones SV.", stacklevel=2)
        return pd.DataFrame()

    rows: list[dict] = []
    for pv_cand in candidatos_pv:
        sub = t[t[pv_key] == pv_cand].copy()
        if sub.empty:
            continue

        total_pct = float(sub["valor"].sum())
        if total_pct == 0:
            continue

        # Decisivos (excl. indecisos SV)
        decided_mask = ~sub[sv_opt_col].isin(INDECISOS_SV)
        total_decided = float(sub.loc[decided_mask, "valor"].sum())

        for _, row in sub.iterrows():
            opt = row[sv_opt_col]
            pct_tot = float(row["valor"])
            pct_dec = (pct_tot / total_decided * 100) if total_decided > 0 else float("nan")
            rows.append(
                {
                    "primera_vuelta": pv_cand,
                    "sv_opcion": opt,
                    "pct_total": round(pct_tot, 2),
                    "pct_decididos": round(pct_dec, 2),
                    "es_indeciso_sv": opt in INDECISOS_SV,
                }
            )

    if not rows:
        return pd.DataFrame()

    df_out = pd.DataFrame(rows)
    df_out = df_out.sort_values(["primera_vuelta", "pct_total"], ascending=[True, False])
    return df_out.reset_index(drop=True)


# ══════════════════════════════════════════════════════════════════════════════
#  2. Simulación de segunda vuelta (Monte Carlo)
# ══════════════════════════════════════════════════════════════════════════════
class ResultadoSimulacion(NamedTuple):
    """Resultados de la simulación Monte Carlo."""

    candidato_a: str
    candidato_b: str
    media_a: float
    media_b: float
    std_a: float
    std_b: float
    prob_a_gana: float
    prob_b_gana: float
    prob_empate_tecnico: float  # |A - B| < 2pp
    ic80_a: tuple[float, float]
    ic80_b: tuple[float, float]
    n_iter: int


def simular_segunda_vuelta(
    pesos_pv: Mapping[str, float],
    matriz: MatrizTransferencia,
    candidato_a: str,
    candidato_b: str,
    n_iter: int = 20_000,
    seed: int = 42,
    umbral_empate_pp: float = 2.0,
) -> tuple[ResultadoSimulacion, pd.DataFrame]:
    """Simulación Monte Carlo de una segunda vuelta.

    En cada iteración muestrea las tasas de transferencia de cada candidato PV
    uniformemente dentro de los rangos de incertidumbre especificados en *matriz*,
    y calcula el resultado de la segunda vuelta con esos parámetros.

    Args:
        pesos_pv: peso de cada candidato PV (% de voto en primera vuelta).
            No necesita sumar 100 — se usa relativamente.
        matriz: diccionario {candidato_pv: {destino_sv: (min_pct, max_pct)}}.
            Destinos típicos: candidato_a, candidato_b, "blanco".
        candidato_a: nombre del candidato A en la SV.
        candidato_b: nombre del candidato B en la SV.
        n_iter: número de iteraciones Monte Carlo (default 20 000).
        seed: semilla para reproducibilidad.
        umbral_empate_pp: diferencia máxima para declarar empate técnico (default 2pp).

    Returns:
        Tupla (ResultadoSimulacion, DataFrame con distribución iteración×resultado).

    Example:
        >>> pesos = {"Iván Cepeda": 38, "Abelardo de la Espriella": 25,
        ...          "Paloma Valencia": 19, "Fajardo+López": 5, "blanco": 9}
        >>> matriz = {
        ...     "Iván Cepeda":              {"A": (93, 97), "B": (0, 2), "blanco": (2, 5)},
        ...     "Abelardo de la Espriella": {"A": (0, 2),  "B": (95, 99), "blanco": (1, 3)},
        ...     "Paloma Valencia":          {"A": (5, 12), "B": (75, 88), "blanco": (5, 15)},
        ...     "Fajardo+López":            {"A": (30, 55), "B": (15, 40), "blanco": (15, 40)},
        ...     "blanco":                   {"A": (8, 14), "B": (22, 32), "blanco": (55, 68)},
        ... }
        >>> result, df_iters = simular_segunda_vuelta(pesos, matriz, "Iván Cepeda", "Abelardo")
    """
    rng = np.random.default_rng(seed)
    pv_cands = list(pesos_pv.keys())
    total_pv = sum(pesos_pv.values())

    votos_a = np.zeros(n_iter)
    votos_b = np.zeros(n_iter)

    for pv_cand in pv_cands:
        peso = pesos_pv[pv_cand] / total_pv
        if pv_cand not in matriz:
            continue
        transfers = matriz[pv_cand]

        # Muestrar rangos de transferencia
        lo_a, hi_a = transfers.get("A", (0.0, 0.0))
        lo_b, hi_b = transfers.get("B", (0.0, 0.0))
        lo_bl, hi_bl = transfers.get("blanco", (0.0, 0.0))

        t_a = rng.uniform(lo_a, hi_a, n_iter) / 100.0
        t_b = rng.uniform(lo_b, hi_b, n_iter) / 100.0
        t_bl = rng.uniform(lo_bl, hi_bl, n_iter) / 100.0

        # Normalizar para que los tres sumen 1
        total_t = t_a + t_b + t_bl
        total_t = np.where(total_t == 0, 1.0, total_t)
        t_a /= total_t
        t_b /= total_t

        votos_a += peso * t_a
        votos_b += peso * t_b

    # Renormalizar entre A y B (excl. blanco)
    total_valid = votos_a + votos_b
    total_valid = np.where(total_valid == 0, 1.0, total_valid)
    pct_a = votos_a / total_valid * 100
    pct_b = votos_b / total_valid * 100

    prob_a = float((pct_a > pct_b).mean())
    prob_b = float((pct_b > pct_a).mean())
    prob_empate = float((np.abs(pct_a - pct_b) < umbral_empate_pp).mean())

    result = ResultadoSimulacion(
        candidato_a=candidato_a,
        candidato_b=candidato_b,
        media_a=float(pct_a.mean()),
        media_b=float(pct_b.mean()),
        std_a=float(pct_a.std()),
        std_b=float(pct_b.std()),
        prob_a_gana=prob_a,
        prob_b_gana=prob_b,
        prob_empate_tecnico=prob_empate,
        ic80_a=(float(np.percentile(pct_a, 10)), float(np.percentile(pct_a, 90))),
        ic80_b=(float(np.percentile(pct_b, 10)), float(np.percentile(pct_b, 90))),
        n_iter=n_iter,
    )

    df_iters = pd.DataFrame(
        {
            "iter": np.arange(n_iter),
            candidato_a: pct_a.round(2),
            candidato_b: pct_b.round(2),
            "ganador": np.where(pct_a > pct_b, candidato_a, candidato_b),
        }
    )

    return result, df_iters


# ══════════════════════════════════════════════════════════════════════════════
#  3. Análisis de sensibilidad de segunda vuelta
# ══════════════════════════════════════════════════════════════════════════════
def sensibilidad_2v(
    pesos_pv_base: Mapping[str, float],
    matriz_base: MatrizTransferencia,
    candidato_a: str,
    candidato_b: str,
    param_name: str,
    param_pv_cand: str,
    param_destino: str,
    rango_param: tuple[float, float] = (0.0, 100.0),
    n_puntos: int = 50,
    n_iter_mc: int = 5_000,
    seed: int = 42,
) -> pd.DataFrame:
    """Análisis de sensibilidad: cómo cambia la 2V al variar un parámetro.

    Fija todos los rangos de transferencia en su valor medio excepto el
    parámetro especificado, que varía de forma determinista en el rango dado.

    Args:
        pesos_pv_base: pesos base de primera vuelta por candidato.
        matriz_base: matriz de transferencia con rangos (min, max).
        candidato_a: candidato A en la segunda vuelta.
        candidato_b: candidato B en la segunda vuelta.
        param_name: etiqueta descriptiva del parámetro variado.
        param_pv_cand: candidato PV cuya transferencia se varía.
        param_destino: destino SV cuya tasa se varía (usualmente "A" o "B").
        rango_param: (min_pct, max_pct) del parámetro a variar.
        n_puntos: número de puntos en el rango.
        n_iter_mc: iteraciones MC por punto.
        seed: semilla.

    Returns:
        DataFrame con columnas: param_valor · media_a · media_b ·
        prob_a_gana · prob_b_gana · ic80_a_lo · ic80_a_hi.

    Example:
        >>> df_sens = sensibilidad_2v(
        ...     pesos_pv, matriz, "Cepeda", "Espriella",
        ...     "% Valencia → Espriella", "Paloma Valencia", "B",
        ...     rango_param=(65, 95),
        ... )
    """
    param_vals = np.linspace(rango_param[0], rango_param[1], n_puntos)
    rows = []

    # Precomputar medias de la matriz base para todos los parámetros no variados
    matriz_fija: dict[str, dict[str, tuple[float, float]]] = {}
    for pv_c, transfers in matriz_base.items():
        matriz_fija[pv_c] = {}
        for dest, (lo, hi) in transfers.items():
            mid = (lo + hi) / 2.0
            matriz_fija[pv_c][dest] = (mid, mid)  # determinista en el medio

    for val in param_vals:
        # Ajustar solo el parámetro de interés — el complementario se redistribuye
        m_local = {pv: dict(t) for pv, t in matriz_fija.items()}
        if param_pv_cand in m_local:
            m_local[param_pv_cand][param_destino] = (val, val)
            # Mantener el otro destino fijo y ajustar blanco
            d = m_local[param_pv_cand]
            suma_otros = sum(v[0] for k, v in d.items() if k != "blanco")
            blanco_rest = max(0.0, 100.0 - suma_otros)
            m_local[param_pv_cand]["blanco"] = (blanco_rest, blanco_rest)

        res, _ = simular_segunda_vuelta(
            pesos_pv_base,
            m_local,
            candidato_a,
            candidato_b,
            n_iter=n_iter_mc,
            seed=seed,
        )
        rows.append(
            {
                "param_valor": round(val, 1),
                "param_name": param_name,
                "media_a": round(res.media_a, 2),
                "media_b": round(res.media_b, 2),
                "prob_a_gana": round(res.prob_a_gana * 100, 1),
                "prob_b_gana": round(res.prob_b_gana * 100, 1),
                "prob_empate_tecnico": round(res.prob_empate_tecnico * 100, 1),
                "ic80_a_lo": round(res.ic80_a[0], 2),
                "ic80_a_hi": round(res.ic80_a[1], 2),
                "ic80_b_lo": round(res.ic80_b[0], 2),
                "ic80_b_hi": round(res.ic80_b[1], 2),
            }
        )

    return pd.DataFrame(rows)


# ══════════════════════════════════════════════════════════════════════════════
#  4. Techo de rechazo (favorabilidad neta)
# ══════════════════════════════════════════════════════════════════════════════
def calcular_techo_rechazo(
    df: pd.DataFrame,
    candidatos: Collection[str],
    pesos: Mapping[tuple[str, str], float],
    col_rechazo: str = "rechazaria",
) -> pd.DataFrame:
    """Calcular el techo de rechazo para cada candidato.

    Usa la columna ``rechazaria`` (si existe) o infiere el rechazo como el
    porcentaje de encuestados que NO votaría por ese candidato en ningún escenario
    (cruce de baja favorabilidad + alta polarización).

    Args:
        df: microdatos completos.
        candidatos: lista de candidatos a analizar.
        pesos: pesos de ponderación por (encuestadora, fecha).
        col_rechazo: nombre de la columna de rechazo en los microdatos.

    Returns:
        DataFrame con columnas: candidato · pct_rechazo · n_encuestas_con_dato.
    """
    from encuestas_lib.analysis.weighting import calcular_por_encuesta, combinar_entre_encuestas

    if col_rechazo not in df.columns:
        # Inferencia: % del electorado con primera_vuelta distinto del candidato
        # y que en SV también lo rechaza — proxy simple
        rows = []
        for cand in candidatos:
            col_sv = next(
                (c for c in df.columns if "sv_" in c and cand.split()[0].lower() in c.lower()),
                None,
            )
            if col_sv is None:
                rows.append({"candidato": cand, "pct_rechazo": float("nan"), "metodo": "sin_dato"})
                continue
            # Proxy: quienes en SV dicen NO votarle (suma de votos a otros)
            mask_rechazo = (df["primera_vuelta"] != cand) & (~df[col_sv].isin({cand}))
            sub = df.copy()
            sub["rechazo"] = mask_rechazo.astype(int)
            base = calcular_por_encuesta(sub, group_cols=["rechazo"], normalize_within=[])
            agg = combinar_entre_encuestas(
                base, dict(pesos), group_cols=["rechazo"], normalize_within=[]
            )
            pct_r = (
                float(agg.loc[agg["rechazo"] == 1, "valor"].sum())
                if not agg.empty
                else float("nan")
            )
            rows.append({"candidato": cand, "pct_rechazo": round(pct_r, 2), "metodo": "proxy_sv"})
        return pd.DataFrame(rows)

    # Caso directo: columna rechazaria existe
    from encuestas_lib.analysis.weighting import calcular_por_encuesta, combinar_entre_encuestas

    rows = []
    for cand in candidatos:
        sub = df.dropna(subset=[col_rechazo]).copy()
        sub["rechazo_cand"] = sub[col_rechazo].apply(
            lambda x: 1 if cand in str(x) else 0  # noqa: B023
        )
        base = calcular_por_encuesta(sub, group_cols=["rechazo_cand"], normalize_within=[])
        agg = combinar_entre_encuestas(
            base, dict(pesos), group_cols=["rechazo_cand"], normalize_within=[]
        )
        pct_r = (
            float(agg.loc[agg["rechazo_cand"] == 1, "valor"].sum())
            if not agg.empty
            else float("nan")
        )
        rows.append({"candidato": cand, "pct_rechazo": round(pct_r, 2), "metodo": "directo"})
    return pd.DataFrame(rows)


# ══════════════════════════════════════════════════════════════════════════════
#  5. Resumen comparativo de escenarios de segunda vuelta
# ══════════════════════════════════════════════════════════════════════════════
def resumen_escenarios_2v(
    tablas: Mapping[str, pd.DataFrame],
    candidatos_principales: Collection[str],
    pesos_pv: Mapping[str, float],
    matrices: Mapping[str, tuple[str, str, MatrizTransferencia]],
    n_iter: int = 10_000,
    seed: int = 42,
) -> pd.DataFrame:
    """Calcular y comparar múltiples escenarios de segunda vuelta.

    Args:
        tablas: tablas analíticas del pipeline.
        candidatos_principales: lista de candidatos con datos en tablas.
        pesos_pv: pesos de primera vuelta por candidato.
        matrices: dict {nombre_escenario: (candidato_a, candidato_b, matriz)}.
        n_iter: iteraciones Monte Carlo.
        seed: semilla.

    Returns:
        DataFrame consolidado con resultados de cada escenario.
    """
    rows = []
    for escenario, (cand_a, cand_b, matriz) in matrices.items():
        res, _ = simular_segunda_vuelta(pesos_pv, matriz, cand_a, cand_b, n_iter=n_iter, seed=seed)
        rows.append(
            {
                "escenario": escenario,
                "candidato_a": cand_a,
                "candidato_b": cand_b,
                "media_a": round(res.media_a, 1),
                "media_b": round(res.media_b, 1),
                "prob_a_gana_pct": round(res.prob_a_gana * 100, 1),
                "prob_b_gana_pct": round(res.prob_b_gana * 100, 1),
                "prob_empate_tecnico_pct": round(res.prob_empate_tecnico * 100, 1),
                "ic80_a": f"{res.ic80_a[0]:.1f}–{res.ic80_a[1]:.1f}",
                "ic80_b": f"{res.ic80_b[0]:.1f}–{res.ic80_b[1]:.1f}",
            }
        )
    return pd.DataFrame(rows)


# ══════════════════════════════════════════════════════════════════════════════
#  Públicos
# ══════════════════════════════════════════════════════════════════════════════
__all__ = [
    "INDECISOS_SV",
    "MatrizTransferencia",
    "ResultadoSimulacion",
    "TransferRango",
    "calcular_techo_rechazo",
    "resumen_escenarios_2v",
    "sensibilidad_2v",
    "simular_segunda_vuelta",
    "trasvase_candidato",
]
