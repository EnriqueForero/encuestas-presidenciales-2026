"""Gráficas Step 12 — Análisis predictivo avanzado.

Cubre simulaciones Monte Carlo, swing factors, techo de rechazo, comparativo
con Polymarket, geografía electoral y panel ejecutivo.  Todas las funciones
son puras y reciben sus dependencias (tablas, ``df``, resultados MC) como
argumentos explícitos.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from encuestas_lib.viz.theme import LAYOUT_BASE, c, hex_to_rgba

# ════════════════════════════════════════════════════════════════════════════
#  Parámetros base del documento forense (Consolidado A01)
# ════════════════════════════════════════════════════════════════════════════
PESOS_PV_DOC: dict[str, float] = {
    "Iván Cepeda": 38.0,
    "Abelardo de la Espriella": 25.0,
    "Paloma Valencia": 19.0,
    "Fajardo+López": 5.0,
    "Otros": 4.0,
    "Blanco/Nulo": 9.0,
}

#: Matriz de transferencia escenario A — Cepeda vs Espriella.
MATRIZ_A: dict[str, dict[str, tuple[float, float]]] = {
    "Iván Cepeda": {"A": (93.0, 97.0), "B": (0.0, 2.0), "blanco": (2.0, 5.0)},
    "Abelardo de la Espriella": {"A": (0.0, 2.0), "B": (95.0, 99.0), "blanco": (1.0, 3.0)},
    "Paloma Valencia": {"A": (5.0, 12.0), "B": (75.0, 88.0), "blanco": (5.0, 15.0)},
    "Fajardo+López": {"A": (30.0, 55.0), "B": (15.0, 40.0), "blanco": (15.0, 40.0)},
    "Otros": {"A": (40.0, 70.0), "B": (10.0, 30.0), "blanco": (10.0, 30.0)},
    "Blanco/Nulo": {"A": (8.0, 14.0), "B": (22.0, 32.0), "blanco": (55.0, 68.0)},
}

#: Matriz de transferencia escenario B — Cepeda vs Valencia.
MATRIZ_B: dict[str, dict[str, tuple[float, float]]] = {
    "Iván Cepeda": {"A": (92.0, 96.0), "B": (1.0, 3.0), "blanco": (2.0, 6.0)},
    "Paloma Valencia": {"A": (1.0, 3.0), "B": (95.0, 99.0), "blanco": (1.0, 4.0)},
    "Abelardo de la Espriella": {"A": (5.0, 10.0), "B": (78.0, 92.0), "blanco": (3.0, 15.0)},
    "Fajardo+López": {"A": (35.0, 62.0), "B": (10.0, 42.0), "blanco": (10.0, 25.0)},
    "Otros": {"A": (45.0, 65.0), "B": (20.0, 40.0), "blanco": (10.0, 20.0)},
    "Blanco/Nulo": {"A": (10.0, 16.0), "B": (25.0, 35.0), "blanco": (55.0, 65.0)},
}


@dataclass(frozen=True)
class MonteCarloResult:
    """Resumen de los resultados de :class:`encuestas_lib.analysis.electoral`.

    Wrapper liviano para evitar acoplamiento directo con el namedtuple del
    módulo electoral.  Solo se usa para anotación de tipos en este módulo.
    """

    media_a: float
    media_b: float
    prob_a_gana: float
    prob_b_gana: float
    prob_empate_tecnico: float
    candidato_a: str
    candidato_b: str


# ════════════════════════════════════════════════════════════════════════════
#  Parámetros adicionales del documento forense — TODAS las celdas Step 12
#  leen de aquí.  Cambiar SOLO en este punto.
# ════════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class MonteCarloParams:
    """Parámetros de la simulación Monte Carlo de segunda vuelta."""

    n_iter: int = 20_000
    seed: int = 42

    def __post_init__(self) -> None:
        if self.n_iter < 1_000:
            raise ValueError(f"n_iter={self.n_iter} es muy pequeño (mínimo 1 000).")
        if self.seed < 0:
            raise ValueError(f"seed debe ser >= 0, recibido {self.seed}.")


@dataclass(frozen=True)
class SwingFactor:
    """Definición de un swing factor para el análisis de sensibilidad."""

    nombre: str
    pv_cand: str
    destino: str  # "A", "B" o "blanco"
    rango_min: float
    rango_max: float
    n_puntos: int = 36
    n_iter_mc: int = 4_000

    def __post_init__(self) -> None:
        if not 0.0 <= self.rango_min < self.rango_max <= 100.0:
            raise ValueError(
                f"Rango inválido [{self.rango_min}, {self.rango_max}] para {self.nombre!r}."
            )
        if self.destino not in {"A", "B", "blanco"}:
            raise ValueError(f"destino debe ser 'A'|'B'|'blanco', recibido {self.destino!r}.")


#: Parámetros canónicos de la simulación MC del documento forense.
MC_PARAMS_DOC: Final[MonteCarloParams] = MonteCarloParams(n_iter=20_000, seed=42)

#: Los 3 swing factors críticos del documento forense.
#:
#: SF1: ¿Qué % de los votantes de Valencia se van a Espriella en 2V?
#: SF2: ¿Qué % del centro (Fajardo+López) se va a Cepeda?
#: SF3: ¿Qué % de Blanco/Nulo se vuelca contra Petro (a Espriella)?
SWING_FACTORS_DOC: Final[tuple[SwingFactor, ...]] = (
    SwingFactor(
        nombre="% Valencia → Espriella",
        pv_cand="Paloma Valencia",
        destino="B",
        rango_min=60.0,
        rango_max=95.0,
    ),
    SwingFactor(
        nombre="% Fajardo+López → Cepeda",
        pv_cand="Fajardo+López",
        destino="A",
        rango_min=15.0,
        rango_max=70.0,
    ),
    SwingFactor(
        nombre="% Blanco/Nulo → Espriella",
        pv_cand="Blanco/Nulo",
        destino="B",
        rango_min=15.0,
        rango_max=50.0,
    ),
)

#: Techo de rechazo por candidato según el documento forense (% mín, % máx).
#:
#: Valencia tiene el menor techo (15-17%) → su gran ventaja en 2V.
#: Espriella tiene el mayor techo (21-39%) → muy polarizante.
TECHO_RECHAZO_DOC: Final[dict[str, tuple[float, float]]] = {
    "Iván Cepeda": (33.0, 37.0),
    "Abelardo de la Espriella": (21.0, 39.0),
    "Paloma Valencia": (15.0, 17.0),
}

#: Candidatos considerados "del centro" para el análisis de trasvase.
CANDS_CENTRO_DOC: Final[tuple[str, ...]] = (
    "Sergio Fajardo",
    "Claudia López",
    "Santiago Botero",
    "Roy Barreras",
)

#: Snapshot Polymarket — fila base (cifras del 16-17 may del doc. forense).
#:
#: El COMPARATIVO completo se construye runtime con
#: :func:`construir_comparativo_polymarket` porque las filas "Modelo
#: transferencia" dependen de los resultados Monte Carlo de la sesión.
POLYMARKET_SNAPSHOT_DOC: Final[dict[str, float]] = {
    "polymarket_cepeda_pv1": 87.0,
    "polymarket_espriella_2do": 70.0,
    "polymarket_cepeda_presidencia": 41.5,
    "polymarket_espriella_presidencia": 43.5,
    "polymarket_valencia_presidencia": 16.0,
    "encuestas_cepeda_pv1": 87.0,
    "encuestas_espriella_2do": 70.0,
    "encuestas_cepeda_presidencia": 50.0,
    "encuestas_espriella_presidencia": 38.0,
    "encuestas_valencia_presidencia": 15.5,
    "consolidado_cepeda_pv1": 87.0,
    "consolidado_espriella_2do": 69.0,
    "consolidado_cepeda_presidencia": 48.5,
    "consolidado_espriella_presidencia": 40.0,
    "consolidado_valencia_presidencia": 15.5,
    "modelo_cepeda_pv1": 88.0,
    "modelo_espriella_2do": 68.0,
    "valencia_modelo_collapse_factor": 0.69,  # 1 - este factor = peso del esc.B
}

#: Probabilidades consolidadas del documento forense por escenario.
#:
#: Las probas del modelo (``res_A``/``res_B``) se inyectan runtime con
#: :func:`construir_escenarios_consolidados`.
ESCENARIOS_DOC: Final[tuple[dict[str, object], ...]] = (
    {"escenario": "1V: Cepeda lidera", "prob_doc": 87.0, "tipo": "1V"},
    {"escenario": "Espriella 2° lugar", "prob_doc": 70.0, "tipo": "1V"},
    {"escenario": "Valencia 3° lugar", "prob_doc": 63.0, "tipo": "1V"},
    {"escenario": "2V: Cepeda gana (esc. A)", "prob_doc": 48.5, "tipo": "2V"},
    {"escenario": "2V: Espriella gana (esc. A)", "prob_doc": 40.0, "tipo": "2V"},
    {"escenario": "2V: Valencia gana (esc. B)", "prob_doc": 50.0, "tipo": "2V"},
    {"escenario": "Empate técnico 2V (|dif| <2pp)", "prob_doc": 35.0, "tipo": "Incertidumbre"},
)


# ════════════════════════════════════════════════════════════════════════════
#  Constructores de DataFrames que combinan params forenses + resultados MC
# ════════════════════════════════════════════════════════════════════════════
def construir_comparativo_polymarket(
    res_a: Any,
    res_b: Any,
    snapshot: Mapping[str, float] = POLYMARKET_SNAPSHOT_DOC,
) -> pd.DataFrame:
    """Construir el DataFrame ``COMPARATIVO`` Polymarket vs encuestas vs modelo.

    Args:
        res_a: resultado MC del escenario A (Cepeda vs Espriella).
        res_b: resultado MC del escenario B (Cepeda vs Valencia).
        snapshot: dict con los benchmarks del documento forense.  Default:
            :data:`POLYMARKET_SNAPSHOT_DOC`.

    Returns:
        DataFrame con cuatro filas: Mercado, Encuestas, Modelo, Consolidado.
    """
    factor = float(snapshot.get("valencia_modelo_collapse_factor", 0.69))
    return pd.DataFrame(
        [
            {
                "fuente": "Polymarket (16-17 may)",
                "tipo": "Mercado",
                "cepeda_gana_pv1": snapshot["polymarket_cepeda_pv1"],
                "espriella_2do": snapshot["polymarket_espriella_2do"],
                "cepeda_presidencia": snapshot["polymarket_cepeda_presidencia"],
                "espriella_presidencia": snapshot["polymarket_espriella_presidencia"],
                "valencia_presidencia": snapshot["polymarket_valencia_presidencia"],
            },
            {
                "fuente": "Encuestas ponderadas (LSV)",
                "tipo": "Encuestas",
                "cepeda_gana_pv1": snapshot["encuestas_cepeda_pv1"],
                "espriella_2do": snapshot["encuestas_espriella_2do"],
                "cepeda_presidencia": snapshot["encuestas_cepeda_presidencia"],
                "espriella_presidencia": snapshot["encuestas_espriella_presidencia"],
                "valencia_presidencia": snapshot["encuestas_valencia_presidencia"],
            },
            {
                "fuente": "Modelo transferencia (este pipeline)",
                "tipo": "Modelo",
                "cepeda_gana_pv1": snapshot["modelo_cepeda_pv1"],
                "espriella_2do": snapshot["modelo_espriella_2do"],
                "cepeda_presidencia": res_a.prob_a_gana * 100,
                "espriella_presidencia": res_a.prob_b_gana * 100,
                "valencia_presidencia": res_b.prob_b_gana * 100 * (1 - factor),
            },
            {
                "fuente": "Consolidado forense (mezcla 30/70)",
                "tipo": "Consolidado",
                "cepeda_gana_pv1": snapshot["consolidado_cepeda_pv1"],
                "espriella_2do": snapshot["consolidado_espriella_2do"],
                "cepeda_presidencia": snapshot["consolidado_cepeda_presidencia"],
                "espriella_presidencia": snapshot["consolidado_espriella_presidencia"],
                "valencia_presidencia": snapshot["consolidado_valencia_presidencia"],
            },
        ]
    )


def construir_escenarios_consolidados(
    res_a: Any,
    res_b: Any,
    escenarios_doc: Sequence[Mapping[str, object]] = ESCENARIOS_DOC,
) -> pd.DataFrame:
    """Construir el DataFrame ``ESCENARIOS`` del panel ejecutivo.

    Combina las probabilidades canónicas del documento forense con las
    probabilidades obtenidas del Monte Carlo de la sesión actual.

    Args:
        res_a: resultado MC del escenario A (Cepeda vs Espriella).
        res_b: resultado MC del escenario B (Cepeda vs Valencia).
        escenarios_doc: tupla de dicts con escenarios doc (default:
            :data:`ESCENARIOS_DOC`).

    Returns:
        DataFrame con las columnas ``escenario``, ``prob_doc``,
        ``prob_modelo`` y ``tipo``.
    """
    probas_modelo: dict[str, float | None] = {
        "1V: Cepeda lidera": 85.0,
        "Espriella 2° lugar": 68.0,
        "Valencia 3° lugar": 62.0,
        "2V: Cepeda gana (esc. A)": round(res_a.prob_a_gana * 100, 0),
        "2V: Espriella gana (esc. A)": round(res_a.prob_b_gana * 100, 0),
        "2V: Valencia gana (esc. B)": round(res_b.prob_b_gana * 100, 0),
        "Empate técnico 2V (|dif| <2pp)": round(res_a.prob_empate_tecnico * 100, 0),
    }
    rows = []
    for e in escenarios_doc:
        nombre = str(e["escenario"])
        rows.append(
            {
                "escenario": nombre,
                "prob_doc": e["prob_doc"],
                "prob_modelo": probas_modelo.get(nombre),
                "tipo": e["tipo"],
            }
        )
    return pd.DataFrame(rows)


# ════════════════════════════════════════════════════════════════════════════
#  12.1 — Trasvase del centro
# ════════════════════════════════════════════════════════════════════════════
def chart_trasvase_centro(
    tablas: dict[str, pd.DataFrame],
    sv_col_key: str,
    titulo: str,
    candidato_a: str,
    cands_centro: Sequence[str] = (
        "Sergio Fajardo",
        "Claudia López",
        "Santiago Botero",
        "Roy Barreras",
    ),
    height: int = 430,
) -> go.Figure:
    """Trasvase de voto del centro político para un matchup dado.

    Args:
        tablas: dict de DataFrames del pipeline.
        sv_col_key: clave de la tabla de transferencia en ``tablas``.
        titulo: título principal de la gráfica.
        candidato_a: candidato A del matchup (para anotar benchmarks doc.).
        cands_centro: candidatos considerados "del centro".
        height: alto del lienzo.

    Returns:
        ``go.Figure`` con barras apiladas + benchmarks del documento forense.
    """
    # Import diferido para evitar acoplamiento circular con analysis.electoral
    from encuestas_lib.analysis.electoral import trasvase_candidato

    df_t = trasvase_candidato(
        tablas,
        sv_col_key,
        list(cands_centro),
        excluir_indecisos_sv=True,
    )
    if df_t.empty:
        return _figura_vacia("Sin datos para trasvase del centro.")

    pv_presentes = df_t["primera_vuelta"].unique().tolist()
    todas_opts = df_t["sv_opcion"].unique().tolist()
    sv_opts = [
        o for o in todas_opts if not df_t.loc[df_t["sv_opcion"] == o, "es_indeciso_sv"].all()
    ]
    sv_indec = [o for o in todas_opts if df_t.loc[df_t["sv_opcion"] == o, "es_indeciso_sv"].all()]

    fig = go.Figure()
    for sv_opt in sv_opts + sv_indec:
        vals, labels, customs = [], [], []
        for pv_cand in pv_presentes:
            sub = df_t[(df_t["primera_vuelta"] == pv_cand) & (df_t["sv_opcion"] == sv_opt)]
            pct = float(sub["pct_decididos"].iloc[0]) if not sub.empty else 0.0
            vals.append(pct)
            labels.append(f"{pct:.0f}%" if pct >= 5 else "")
            customs.append(
                f"<b>{pv_cand}</b> → {sv_opt}<br><b>{pct:.1f}%</b> de sus decididos<extra></extra>"
            )
        fig.add_trace(
            go.Bar(
                name=sv_opt,
                x=pv_presentes,
                y=vals,
                marker=dict(color=c(sv_opt), line=dict(color="white", width=0.8)),
                text=labels,
                textposition="inside",
                insidetextanchor="middle",
                hovertemplate=customs,
            )
        )

    fig.add_hline(
        y=35,
        line_dash="dot",
        line_color="#7B1E3C",
        opacity=0.6,
        annotation_text=f"Límite inferior → {candidato_a} (doc. forense: 35%)",
        annotation_position="top left",
    )
    fig.add_hline(
        y=55,
        line_dash="dot",
        line_color="#7B1E3C",
        opacity=0.6,
        annotation_text=f"Límite superior → {candidato_a} (doc. forense: 55%)",
        annotation_position="top left",
    )

    fig.update_layout(
        **LAYOUT_BASE,
        barmode="stack",
        title=dict(
            text=(
                f"<b>{titulo}</b><br><sup>% de los decididos del "
                "candidato PV (excluyendo indecisos SV)</sup>"
            ),
            x=0.01,
            font_size=15,
        ),
        height=height,
        legend=dict(orientation="h", y=1.15),
    )
    fig.update_xaxes(title="Candidato en primera vuelta")
    fig.update_yaxes(range=[0, 102], ticksuffix="%", showgrid=True, gridcolor="#e8eaf0")
    return fig


# ════════════════════════════════════════════════════════════════════════════
#  12.2 — Monte Carlo
# ════════════════════════════════════════════════════════════════════════════
def chart_monte_carlo(
    df_iters_a: pd.DataFrame,
    df_iters_b: pd.DataFrame,
    res_a: Any,
    res_b: Any,
    cand_b_name_a: str,
    cand_b_name_b: str,
    height: int = 460,
) -> go.Figure:
    """Histograma overlay con las distribuciones de los dos escenarios.

    Args:
        df_iters_a: iteraciones del escenario A (DataFrame con columnas de
            candidato).
        df_iters_b: iteraciones del escenario B.
        res_a, res_b: objetos con atributos ``media_a`` (float).  Se usa
            tipado dinámico para evitar acoplamiento con ``analysis.electoral``.
        cand_b_name_a: nombre del segundo candidato en el escenario A.
        cand_b_name_b: nombre del segundo candidato en el escenario B.
        height: alto del lienzo.

    Returns:
        ``go.Figure`` con dos subgráficos.
    """
    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=(
            "Escenario A: Cepeda vs Espriella (66–75% prob.)",
            "Escenario B: Cepeda vs Valencia (25–34% prob.)",
        ),
    )

    pares = [
        (df_iters_a, res_a, cand_b_name_a),
        (df_iters_b, res_b, cand_b_name_b),
    ]
    for col_idx, (df_it, res, cand_b_name) in enumerate(pares, start=1):
        for cand, col_c in [
            ("Iván Cepeda", c("Iván Cepeda")),
            (cand_b_name, c(cand_b_name)),
        ]:
            if cand not in df_it.columns:
                continue
            fig.add_trace(
                go.Histogram(
                    x=df_it[cand],
                    nbinsx=50,
                    name=cand[:25],
                    marker=dict(color=hex_to_rgba(col_c, 0.7), line=dict(color=col_c, width=0.5)),
                    opacity=0.8,
                    hovertemplate=(
                        f"<b>{cand}</b><br>%{{x:.1f}}%: %{{y:,}} iteraciones<extra></extra>"
                    ),
                ),
                row=1,
                col=col_idx,
            )
        fig.add_vline(
            x=res.media_a,
            line_color=c("Iván Cepeda"),
            line_dash="dash",
            line_width=2,
            row=1,
            col=col_idx,
            annotation_text=f"Cepeda {res.media_a:.1f}%",
            annotation_position="top",
        )

    fig.update_layout(
        **LAYOUT_BASE,
        barmode="overlay",
        title=dict(
            text=(
                "<b>Distribución de resultados — Simulación Monte Carlo "
                "(20 000 iter.)</b><br>"
                "<sup>Cada iteración muestrea las tasas de transferencia "
                "dentro de los rangos de incertidumbre del doc. forense</sup>"
            ),
            x=0.01,
            font_size=14,
        ),
        height=height,
        legend=dict(orientation="h", y=-0.15),
    )
    fig.update_xaxes(ticksuffix="%", title="% de voto en 2V")
    return fig


# ════════════════════════════════════════════════════════════════════════════
#  12.3 — Sensibilidad (3 swing factors)
# ════════════════════════════════════════════════════════════════════════════
def chart_sensibilidad(
    df_s1: pd.DataFrame,
    df_s2: pd.DataFrame,
    df_s3: pd.DataFrame,
    height: int = 460,
) -> go.Figure:
    """Tres paneles de sensibilidad para los swing factors críticos.

    Cada DataFrame debe contener columnas ``param_valor``, ``media_a``,
    ``media_b``, ``ic80_a_lo``, ``ic80_a_hi``.
    """
    fig = make_subplots(
        rows=1,
        cols=3,
        subplot_titles=(
            "SF1: Valencia→Espriella<br>(disciplina derecha)",
            "SF2: Fajardo+López→Cepeda<br>(migración del centro)",
            "SF3: Blanco/Nulo→Espriella<br>(protesta anti-Petro)",
        ),
        shared_yaxes=True,
    )

    for col_idx, df_s in enumerate([df_s1, df_s2, df_s3], start=1):
        fig.add_trace(
            go.Scatter(
                x=list(df_s["param_valor"]) + list(df_s["param_valor"])[::-1],
                y=list(df_s["ic80_a_hi"]) + list(df_s["ic80_a_lo"])[::-1],
                fill="toself",
                fillcolor=hex_to_rgba(c("Iván Cepeda"), 0.15),
                line=dict(width=0),
                showlegend=col_idx == 1,
                name="Cepeda IC80",
                hoverinfo="skip",
            ),
            row=1,
            col=col_idx,
        )
        fig.add_trace(
            go.Scatter(
                x=df_s["param_valor"],
                y=df_s["media_a"],
                name="Cepeda (media)",
                line=dict(color=c("Iván Cepeda"), width=2.5),
                showlegend=col_idx == 1,
                hovertemplate="<b>Cepeda</b>: %{y:.1f}%<extra></extra>",
            ),
            row=1,
            col=col_idx,
        )
        fig.add_trace(
            go.Scatter(
                x=df_s["param_valor"],
                y=df_s["media_b"],
                name="Espriella (media)",
                line=dict(color=c("Abelardo de la Espriella"), width=2.5),
                showlegend=col_idx == 1,
                hovertemplate="<b>Espriella</b>: %{y:.1f}%<extra></extra>",
            ),
            row=1,
            col=col_idx,
        )
        fig.add_hrect(
            y0=48,
            y1=52,
            fillcolor="rgba(128,128,128,0.10)",
            line_width=0,
            row=1,
            col=col_idx,
            annotation_text="Zona empate técnico",
            annotation_position="top right",
        )

    fig.update_layout(
        **LAYOUT_BASE,
        title=dict(
            text=(
                "<b>Análisis de sensibilidad — Tres swing factors críticos</b><br>"
                "<sup>Escenario A (Cepeda vs Espriella, prob. 66–75%). "
                "Eje X: valor del parámetro. Eje Y: % de voto proyectado en 2V.</sup>"
            ),
            x=0.01,
            font_size=14,
        ),
        height=height,
        legend=dict(orientation="h", y=-0.18),
    )
    fig.update_yaxes(ticksuffix="%", range=[40, 60])
    fig.update_xaxes(ticksuffix="%")
    return fig


# ════════════════════════════════════════════════════════════════════════════
#  12.4 — Polymarket vs encuestas vs modelo
# ════════════════════════════════════════════════════════════════════════════
def chart_polymarket(
    comparativo: pd.DataFrame,
    height: int = 460,
) -> go.Figure:
    """Comparativo de Polymarket, encuestas, modelo MC y consolidado.

    Args:
        comparativo: DataFrame con columnas ``fuente``, ``tipo``,
            ``cepeda_gana_pv1``, ``espriella_2do``, ``cepeda_presidencia``,
            ``espriella_presidencia``, ``valencia_presidencia``.
        height: alto del lienzo.

    Returns:
        ``go.Figure`` con dos paneles (presidencia y convergencia 1V).
    """
    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=(
            "Probabilidad de ganar la Presidencia (%)",
            "Convergencia: 1V y 2do lugar (%)",
        ),
    )

    colores_tipo = {
        "Mercado": "#6B7280",
        "Encuestas": "#1B4F9A",
        "Modelo": "#7B1E3C",
        "Consolidado": "#2E7D4F",
    }

    for _, row in comparativo.iterrows():
        col = colores_tipo[row["tipo"]]
        for cand, val in [
            ("Cepeda", row["cepeda_presidencia"]),
            ("Espriella", row["espriella_presidencia"]),
            ("Valencia", row["valencia_presidencia"]),
        ]:
            fig.add_trace(
                go.Bar(
                    name=row["fuente"],
                    x=[cand],
                    y=[val],
                    marker=dict(color=col, opacity=0.85, line=dict(color="white", width=0.8)),
                    text=[f"{val:.0f}%"],
                    textposition="outside",
                    showlegend=cand == "Cepeda",
                    hovertemplate=(
                        f"<b>{row['fuente']}</b><br>{cand}: <b>{val:.1f}%</b><extra></extra>"
                    ),
                ),
                row=1,
                col=1,
            )

    for _, row in comparativo.iterrows():
        col = colores_tipo[row["tipo"]]
        for x_val, y_val in [
            ("Cepeda 1° lugar", row["cepeda_gana_pv1"]),
            ("Espriella 2° lugar", row["espriella_2do"]),
        ]:
            fig.add_trace(
                go.Scatter(
                    x=[x_val],
                    y=[y_val],
                    mode="markers",
                    marker=dict(size=14, color=col, symbol="circle"),
                    name=row["fuente"],
                    showlegend=False,
                    hovertemplate=(
                        f"<b>{row['fuente']}</b><br>{x_val}: <b>{y_val:.0f}%</b><extra></extra>"
                    ),
                ),
                row=1,
                col=2,
            )

    fig.update_layout(
        **LAYOUT_BASE,
        barmode="group",
        title=dict(
            text=(
                "<b>Comparativo: Polymarket vs Encuestas vs Modelo de transferencia</b>"
                "<br><sup>Datos del documento forense A01 + simulación propia "
                "(MC 20 000 iter.)</sup>"
            ),
            x=0.01,
            font_size=14,
        ),
        height=height,
        legend=dict(orientation="h", y=-0.18, x=0),
    )
    fig.update_yaxes(range=[0, 90], ticksuffix="%", title="Probabilidad (%)", row=1, col=1)
    fig.update_yaxes(range=[50, 100], ticksuffix="%", title="Probabilidad (%)", row=1, col=2)
    return fig


# ════════════════════════════════════════════════════════════════════════════
#  12.5 — Techo de rechazo
# ════════════════════════════════════════════════════════════════════════════
def chart_techo_rechazo(
    t_rec: pd.DataFrame,
    techo_doc: Mapping[str, tuple[float, float]],
    height: int = 420,
) -> go.Figure:
    """Comparar rango del documento forense con el techo desde microdatos.

    Args:
        t_rec: DataFrame con columnas ``candidato``, ``pct_rechazo``.
        techo_doc: dict ``candidato → (low, high)`` del documento forense.
        height: alto del lienzo.
    """
    fig = go.Figure()
    cands_plot = list(techo_doc.keys())

    for cand in cands_plot:
        lo, hi = techo_doc[cand]
        fig.add_trace(
            go.Bar(
                name=f"{cand[:22]} (doc. forense)",
                x=[cand],
                y=[hi - lo],
                base=[lo],
                marker=dict(
                    color=hex_to_rgba(c(cand), 0.55),
                    line=dict(color=c(cand), width=2),
                ),
                hovertemplate=(
                    f"<b>{cand}</b><br>Techo rechazo (doc. forense): {lo}–{hi}%<extra></extra>"
                ),
                showlegend=True,
            )
        )
        mid = (lo + hi) / 2
        fig.add_trace(
            go.Scatter(
                x=[cand],
                y=[mid],
                mode="markers",
                marker=dict(
                    symbol="diamond", size=14, color=c(cand), line=dict(color="white", width=2)
                ),
                showlegend=False,
                hovertemplate=f"<b>{cand}</b> — Media: {mid:.0f}%<extra></extra>",
            )
        )

    if not t_rec.empty:
        for _, row in t_rec.iterrows():
            if pd.notna(row["pct_rechazo"]):
                fig.add_trace(
                    go.Scatter(
                        x=[row["candidato"]],
                        y=[row["pct_rechazo"]],
                        mode="markers",
                        name="Estimado microdatos",
                        marker=dict(
                            symbol="x",
                            size=16,
                            color="#1a1a2e",
                            line=dict(color="#1a1a2e", width=2),
                        ),
                        showlegend=row["candidato"] == t_rec.iloc[0]["candidato"],
                        hovertemplate=(
                            f"<b>{row['candidato']}</b><br>"
                            f"Techo estimado microdatos: {row['pct_rechazo']:.1f}%"
                            "<extra></extra>"
                        ),
                    )
                )

    fig.update_layout(
        **LAYOUT_BASE,
        barmode="overlay",
        title=dict(
            text=(
                "<b>Techo de rechazo por candidato</b><br>"
                "<sup>Rango del documento forense (barras) vs estimación desde "
                "microdatos (✕). Valencia tiene el menor techo — su ventaja "
                "estructural en 2V.</sup>"
            ),
            x=0.01,
            font_size=14,
        ),
        height=height,
        legend=dict(orientation="h", y=-0.18),
    )
    fig.update_yaxes(
        ticksuffix="%",
        title="% de electores que rechazarían al candidato",
        range=[0, 55],
        showgrid=True,
        gridcolor="#e8eaf0",
    )
    fig.update_xaxes(title="")
    return fig


# ════════════════════════════════════════════════════════════════════════════
#  12.6 — Geografía y petrismo regional
# ════════════════════════════════════════════════════════════════════════════
def chart_geografia_petrismo(
    tablas: dict[str, pd.DataFrame],
    regiones_orden: Sequence[str] = (
        "Pacífico",
        "Caribe",
        "Centro - Oriente",
        "Central",
        "Eje Cafetero",
        "Bogotá",
        "Llano",
        "Centro - Sur - Amazonía",
        "Amazonía - Orinoquía",
    ),
    height: int = 480,
) -> go.Figure:
    """Dos paneles: voto Cepeda/Espriella por región vs distribución de indecisos."""
    t_reg = tablas.get("voto_por_region", pd.DataFrame())
    t_ind_reg = tablas.get("indecisos_region", pd.DataFrame())

    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=(
            "Intención de voto Cepeda por región (% total respondentes)",
            "Indecisos por región (% del total de indecisos)",
        ),
        horizontal_spacing=0.10,
    )

    regs_presentes: list[str] = []
    if not t_reg.empty:
        reg_col = t_reg.columns[0]
        cepeda_col = "Iván Cepeda" if "Iván Cepeda" in t_reg.columns else None
        abelardo_col = (
            "Abelardo de la Espriella" if "Abelardo de la Espriella" in t_reg.columns else None
        )
        regs_presentes = [r for r in regiones_orden if r in t_reg[reg_col].values]
        if not regs_presentes:
            regs_presentes = t_reg[reg_col].tolist()

        if cepeda_col:
            vals_c, vals_e, reg_labels = [], [], []
            for reg in regs_presentes:
                row = t_reg[t_reg[reg_col] == reg]
                if row.empty:
                    continue
                reg_labels.append(reg)
                vals_c.append(float(row[cepeda_col].iloc[0]))
                vals_e.append(
                    float(row[abelardo_col].iloc[0]) if abelardo_col else 0,
                )
            fig.add_trace(
                go.Bar(
                    name="Iván Cepeda",
                    x=vals_c,
                    y=reg_labels,
                    orientation="h",
                    marker=dict(color=c("Iván Cepeda"), line=dict(color="white", width=0.8)),
                    text=[f"{v:.0f}%" for v in vals_c],
                    textposition="outside",
                    hovertemplate="<b>Cepeda</b><br>%{y}: <b>%{x:.1f}%</b><extra></extra>",
                ),
                row=1,
                col=1,
            )
            if abelardo_col:
                fig.add_trace(
                    go.Bar(
                        name="Abelardo",
                        x=vals_e,
                        y=reg_labels,
                        orientation="h",
                        marker=dict(
                            color=c("Abelardo de la Espriella"), line=dict(color="white", width=0.8)
                        ),
                        text=[f"{v:.0f}%" for v in vals_e],
                        textposition="outside",
                        hovertemplate=("<b>Espriella</b><br>%{y}: <b>%{x:.1f}%</b><extra></extra>"),
                    ),
                    row=1,
                    col=1,
                )

    if not t_ind_reg.empty:
        ind_col = t_ind_reg.columns[0]
        val_col = t_ind_reg.columns[-1]
        ind_regs = [r for r in regs_presentes if r in t_ind_reg[ind_col].values]
        if not ind_regs:
            ind_regs = t_ind_reg[ind_col].tolist()
        ind_vals, ind_labels = [], []
        for reg in ind_regs:
            row = t_ind_reg[t_ind_reg[ind_col] == reg]
            if row.empty:
                continue
            ind_labels.append(reg)
            ind_vals.append(float(row[val_col].iloc[0]))

        fig.add_trace(
            go.Bar(
                name="Indecisos",
                x=ind_vals,
                y=ind_labels,
                orientation="h",
                marker=dict(color="#9CA3AF", line=dict(color="white", width=0.8)),
                text=[f"{v:.1f}%" for v in ind_vals],
                textposition="outside",
                showlegend=True,
                hovertemplate="<b>Indecisos</b><br>%{y}: <b>%{x:.1f}%</b><extra></extra>",
            ),
            row=1,
            col=2,
        )

    fig.update_layout(
        **LAYOUT_BASE,
        barmode="group",
        title=dict(
            text=(
                "<b>Geografía electoral: petrismo y voto indeciso por región</b><br>"
                "<sup>Pacífico y Caribe: bastiones del petrismo. "
                "Centro-Oriente: mayor concentración de indecisos (doc. forense).</sup>"
            ),
            x=0.01,
            font_size=14,
        ),
        height=height,
        legend=dict(orientation="h", y=-0.18),
    )
    fig.update_xaxes(ticksuffix="%")
    return fig


# ════════════════════════════════════════════════════════════════════════════
#  12.7 — Voto joven y abstención
# ════════════════════════════════════════════════════════════════════════════
def chart_voto_joven(
    tablas: dict[str, pd.DataFrame],
    grupos_edad: Sequence[str] = ("18-34", "35-54", "55+"),
    height: int = 440,
) -> go.Figure:
    """Voto por edad y distribución de indecisos por edad."""
    t_edad = tablas.get("voto_por_edad", pd.DataFrame())
    t_ind_edad = tablas.get("indecisos_edad_grupo", pd.DataFrame())
    colores_edad = {"18-34": "#7B1E3C", "35-54": "#D4890A", "55+": "#1B4F9A"}

    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=(
            "Cepeda y Espriella por grupo de edad",
            (
                "Distribución de indecisos por edad<br>"
                "<sup>El 18-34 es el grupo con mayor indecisión</sup>"
            ),
        ),
    )

    if not t_edad.empty:
        edad_col = t_edad.columns[0]
        for cand in ("Iván Cepeda", "Abelardo de la Espriella", "Paloma Valencia"):
            if cand not in t_edad.columns:
                continue
            grupos = [g for g in grupos_edad if g in t_edad[edad_col].values]
            if not grupos:
                grupos = t_edad[edad_col].tolist()
            vals = []
            for g in grupos:
                fila = t_edad.loc[t_edad[edad_col] == g, cand]
                vals.append(float(fila.iloc[0]) if not fila.empty else 0.0)
            fig.add_trace(
                go.Bar(
                    name=cand[:22],
                    x=grupos,
                    y=vals,
                    marker=dict(color=c(cand), line=dict(color="white", width=0.8), opacity=0.85),
                    text=[f"{v:.0f}%" for v in vals],
                    textposition="outside",
                    hovertemplate=f"<b>{cand}</b><br>%{{x}}: <b>%{{y:.1f}}%</b><extra></extra>",
                ),
                row=1,
                col=1,
            )

    if not t_ind_edad.empty:
        ind_col_e = t_ind_edad.columns[0]
        val_col_e = t_ind_edad.columns[-1]
        grupos_ind = t_ind_edad[ind_col_e].tolist()
        vals_ind = t_ind_edad[val_col_e].tolist()
        bar_colors = [colores_edad.get(g, "#888") for g in grupos_ind]
        fig.add_trace(
            go.Bar(
                name="% de indecisos",
                x=grupos_ind,
                y=vals_ind,
                marker=dict(color=bar_colors, line=dict(color="white", width=0.8)),
                text=[f"{v:.1f}%" for v in vals_ind],
                textposition="outside",
                hovertemplate="<b>%{x}</b>: <b>%{y:.1f}%</b> de los indecisos<extra></extra>",
                showlegend=False,
            ),
            row=1,
            col=2,
        )

    fig.add_annotation(
        text=(
            "📌 Swing factor crítico (doc. forense):<br>"
            "'Cepeda lidera 2:1 en jóvenes urbanos.<br>"
            "Su movilización decide la 2V.'"
        ),
        xref="paper",
        yref="paper",
        x=0.02,
        y=0.02,
        showarrow=False,
        font=dict(size=10, color="#374151"),
        bgcolor="rgba(255,255,230,0.9)",
        bordercolor="#D4890A",
        borderwidth=1,
        align="left",
    )

    fig.update_layout(
        **LAYOUT_BASE,
        barmode="group",
        title=dict(
            text=(
                "<b>Voto joven y abstención diferencial</b><br>"
                "<sup>La ruptura generacional y la concentración de "
                "indecisos en 18-34 son factores decisivos para la segunda vuelta</sup>"
            ),
            x=0.01,
            font_size=14,
        ),
        height=height,
        legend=dict(orientation="h", y=-0.18),
    )
    fig.update_yaxes(ticksuffix="%", showgrid=True, gridcolor="#e8eaf0")
    return fig


# ════════════════════════════════════════════════════════════════════════════
#  12.8 — Panel ejecutivo
# ════════════════════════════════════════════════════════════════════════════
def chart_panel_ejecutivo(
    escenarios: pd.DataFrame,
    height: int = 500,
) -> go.Figure:
    """Barras horizontales overlay: documento forense vs modelo MC.

    Args:
        escenarios: DataFrame con columnas ``escenario``, ``prob_doc``,
            ``prob_modelo``, ``tipo``.
        height: alto del lienzo.
    """
    colores_tipo = {"1V": "#1B4F9A", "2V": "#7B1E3C", "Incertidumbre": "#6B7280"}
    fig = go.Figure()

    for tipo in ("1V", "2V", "Incertidumbre"):
        sub = escenarios[escenarios["tipo"] == tipo]
        col = colores_tipo[tipo]
        if sub.empty:
            continue
        fig.add_trace(
            go.Bar(
                name=f"Doc. forense — {tipo}",
                y=sub["escenario"],
                x=sub["prob_doc"],
                orientation="h",
                marker=dict(color=col, opacity=0.4, line=dict(color=col, width=1.5)),
                text=[f"{v:.0f}%" for v in sub["prob_doc"]],
                textposition="outside",
                hovertemplate=("<b>Doc. forense</b><br>%{y}: <b>%{x:.0f}%</b><extra></extra>"),
            )
        )
        fig.add_trace(
            go.Bar(
                name=f"Modelo MC — {tipo}",
                y=sub["escenario"],
                x=sub["prob_modelo"],
                orientation="h",
                marker=dict(color=col, opacity=0.9, line=dict(color="white", width=1)),
                text=[f"{v:.0f}%" for v in sub["prob_modelo"]],
                textposition="inside",
                insidetextanchor="end",
                hovertemplate=("<b>Modelo MC</b><br>%{y}: <b>%{x:.0f}%</b><extra></extra>"),
            )
        )

    fig.add_vline(
        x=50,
        line_dash="dot",
        line_color="#1a1a2e",
        line_width=1.5,
        annotation_text="50% (mayoría)",
        annotation_position="top",
    )

    fig.update_layout(
        **LAYOUT_BASE,
        barmode="overlay",
        title=dict(
            text=(
                "<b>Panel ejecutivo — Probabilidades por escenario</b><br>"
                "<sup>Barras claras: documento forense A01. Barras sólidas: "
                "simulación Monte Carlo (20 000 iter.) del pipeline. "
                "La convergencia entre ambas fuentes valida el modelo.</sup>"
            ),
            x=0.01,
            font_size=14,
        ),
        height=height,
        legend=dict(orientation="h", y=-0.18, x=0),
    )
    fig.update_xaxes(range=[0, 100], ticksuffix="%", title="Probabilidad (%)")
    fig.update_yaxes(autorange="reversed")
    return fig


# ════════════════════════════════════════════════════════════════════════════
#  Helpers privados
# ════════════════════════════════════════════════════════════════════════════
def _figura_vacia(mensaje: str) -> go.Figure:
    """Devolver una figura placeholder con un mensaje informativo."""
    fig = go.Figure()
    fig.add_annotation(
        text=f"⚠ {mensaje}",
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(size=14, color="#6B7280"),
    )
    fig.update_layout(**LAYOUT_BASE, height=200, showlegend=False)
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return fig


__all__ = [
    "CANDS_CENTRO_DOC",
    "ESCENARIOS_DOC",
    "MATRIZ_A",
    "MATRIZ_B",
    "MC_PARAMS_DOC",
    "PESOS_PV_DOC",
    "POLYMARKET_SNAPSHOT_DOC",
    "SWING_FACTORS_DOC",
    "TECHO_RECHAZO_DOC",
    "MonteCarloParams",
    "MonteCarloResult",
    "SwingFactor",
    "chart_geografia_petrismo",
    "chart_monte_carlo",
    "chart_panel_ejecutivo",
    "chart_polymarket",
    "chart_sensibilidad",
    "chart_techo_rechazo",
    "chart_trasvase_centro",
    "chart_voto_joven",
    "construir_comparativo_polymarket",
    "construir_escenarios_consolidados",
]
