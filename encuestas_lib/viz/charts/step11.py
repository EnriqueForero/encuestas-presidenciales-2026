"""Gráficas Step 11 — Visualizaciones interactivas Plotly.

Cada función toma como input el dict ``tablas`` producido por
:class:`encuestas_lib.pipeline.analyze.AnalysisPipeline` y devuelve un
``plotly.graph_objects.Figure``.  Son funciones puras, sin estado global,
testables individualmente.

Ninguna función llama a ``fig.show()``: la presentación queda a cargo del
notebook o del exportador HTML.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Final

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from encuestas_lib.viz._helpers import candidatos_y_indecisos, top_n_candidatos
from encuestas_lib.viz.theme import (
    INDECISOS_CATS,
    LAYOUT_BASE,
    c,
    hex_to_rgba,
)


# ════════════════════════════════════════════════════════════════════════════
#  11.1 — Tendencia temporal top-5
# ════════════════════════════════════════════════════════════════════════════
def chart_tendencia_temporal(
    tablas: dict[str, pd.DataFrame],
    top: int = 5,
    height: int = 480,
) -> go.Figure:
    """Serie temporal de intención de voto para los ``top`` candidatos.

    Args:
        tablas: dict de DataFrames del pipeline.
        top: número de candidatos en el ranking.
        height: alto del lienzo en píxeles.

    Returns:
        ``go.Figure`` con líneas + marcadores y banda de incertidumbre.
    """
    fig = go.Figure()
    trend = tablas.get("trend_primera_vuelta", pd.DataFrame())
    if trend.empty:
        return _figura_vacia("No hay datos de tendencia temporal disponibles.")

    top_cands = top_n_candidatos(tablas, n=top)
    col_v = "valor_suavizado" if "valor_suavizado" in trend.columns else "valor_punto"

    for cand in top_cands:
        sub = trend[trend["primera_vuelta"] == cand].sort_values("fecha")
        if sub.empty:
            continue
        # Banda de IC si hay valor puntual además del suavizado
        if "valor_punto" in sub.columns and col_v == "valor_suavizado":
            fig.add_trace(
                go.Scatter(
                    x=list(sub["fecha"]) + list(sub["fecha"])[::-1],
                    y=list(sub["valor_punto"] + 1.5) + list(sub["valor_punto"] - 1.5)[::-1],
                    fill="toself",
                    fillcolor=hex_to_rgba(c(cand), 0.10),
                    line=dict(width=0),
                    showlegend=False,
                    hoverinfo="skip",
                    name=f"{cand} IC",
                )
            )
        fig.add_trace(
            go.Scatter(
                x=sub["fecha"],
                y=sub[col_v],
                mode="lines+markers",
                name=cand,
                line=dict(color=c(cand), width=2.8),
                marker=dict(size=6, color=c(cand)),
                hovertemplate=(
                    f"<b>{cand}</b><br>%{{x|%d %b %Y}}<br><b>%{{y:.1f}}%</b><extra></extra>"
                ),
            )
        )

    fig.update_layout(
        **LAYOUT_BASE,
        title=dict(
            text=(
                "<b>Tendencia temporal — Intención de voto primera vuelta</b><br>"
                f"<sup>Promedio ponderado por encuesta · Top {top} candidatos</sup>"
            ),
            x=0.01,
            font_size=16,
        ),
        height=height,
    )
    # Ejes específicos vía update_xaxes/update_yaxes — NO via update_layout kwargs
    fig.update_yaxes(ticksuffix="%", showgrid=True, gridcolor="#e8eaf0", zeroline=False)
    fig.update_xaxes(title="Fecha de campo", showgrid=True, gridcolor="#e8eaf0")
    return fig


# ════════════════════════════════════════════════════════════════════════════
#  11.2 — Sankey PV → SV
# ════════════════════════════════════════════════════════════════════════════
def chart_sankey_pv_sv(
    tablas: dict[str, pd.DataFrame],
    tabla_key: str,
    sv_col: str,
    titulo: str,
    subtitle: str = "",
    n_pv: int = 8,
    flow_min: float = 0.15,
    height: int = 520,
) -> go.Figure:
    """Diagrama Sankey de transferencia primera vuelta → segunda vuelta.

    Args:
        tablas: dict de DataFrames del pipeline.
        tabla_key: nombre de la tabla de transferencia (e.g.
            ``transfer_sv_cepeda_vs_valencia``).
        sv_col: nombre de la columna que codifica la opción de segunda vuelta.
        titulo: título principal.
        subtitle: subtítulo (sup en HTML).
        n_pv: máximo de candidatos PV a mostrar (los más votados).
        flow_min: umbral mínimo (en puntos porcentuales) para dibujar un flujo.
        height: alto del lienzo.

    Returns:
        ``go.Figure`` con el diagrama Sankey.
    """
    if tabla_key not in tablas:
        return _figura_vacia(f"Tabla {tabla_key!r} no disponible.")
    t_transfer = tablas[tabla_key]
    if sv_col not in t_transfer.columns:
        return _figura_vacia(f"Columna {sv_col!r} no está en {tabla_key!r}.")

    pv_totals = tablas["primera_vuelta_total"]
    pv_cands = (
        pv_totals[~pv_totals["primera_vuelta"].isin(INDECISOS_CATS)]
        .query("valor > 1")
        .sort_values("valor", ascending=False)["primera_vuelta"]
        .tolist()
    )[:n_pv]

    sv_all = t_transfer[sv_col].dropna().unique().tolist()
    sv_cands_lst = [o for o in sv_all if o not in INDECISOS_CATS]
    sv_indec = [o for o in sv_all if o in INDECISOS_CATS]
    sv_opts = sv_cands_lst + sv_indec

    node_labels = pv_cands + [f"→ {o}" for o in sv_opts]
    node_colors = [c(cd) for cd in pv_cands] + [c(o) for o in sv_opts]
    node_x = [0.01] * len(pv_cands) + [0.99] * len(sv_opts)
    # Posiciones Y igualmente espaciadas en cada columna
    import numpy as np

    node_y_pv = np.linspace(0.05, 0.95, len(pv_cands)).tolist() if pv_cands else []
    node_y_sv = np.linspace(0.05, 0.95, len(sv_opts)).tolist() if sv_opts else []

    sources, targets, values, link_cols = [], [], [], []
    for i, pv_cand in enumerate(pv_cands):
        pv_share = float(pv_totals.loc[pv_totals["primera_vuelta"] == pv_cand, "valor"].sum())
        sub = t_transfer[t_transfer["primera_vuelta"] == pv_cand]
        for j, sv_opt in enumerate(sv_opts):
            transfer_pct = float(sub.loc[sub[sv_col] == sv_opt, "valor"].sum())
            flow = pv_share * transfer_pct / 100
            if flow < flow_min:
                continue
            sources.append(i)
            targets.append(len(pv_cands) + j)
            values.append(round(flow, 2))
            link_cols.append(hex_to_rgba(c(pv_cand), 0.45))

    fig = go.Figure(
        go.Sankey(
            arrangement="snap",
            node=dict(
                label=node_labels,
                color=node_colors,
                x=node_x,
                y=node_y_pv + node_y_sv,
                pad=18,
                thickness=22,
                line=dict(color="white", width=0.5),
                hovertemplate="<b>%{label}</b><br>Flujo total: %{value:.1f}pp<extra></extra>",
            ),
            link=dict(
                source=sources,
                target=targets,
                value=values,
                color=link_cols,
                hovertemplate=(
                    "<b>%{source.label}</b> → <b>%{target.label}</b><br>"
                    "Flujo: <b>%{value:.1f}pp</b><extra></extra>"
                ),
            ),
        )
    )
    fig.update_layout(
        **LAYOUT_BASE,
        title=dict(
            text=f"<b>{titulo}</b><br><sup>{subtitle}</sup>",
            x=0.01,
            font_size=15,
        ),
        height=height,
        margin=dict(l=20, r=20, t=80, b=20),
    )
    return fig


# ════════════════════════════════════════════════════════════════════════════
#  11.3 — Trasvase derecha (serie temporal)
# ════════════════════════════════════════════════════════════════════════════
_INDECISOS_SV: frozenset[str] = frozenset(
    {"NS/NR", "Ninguno", "Voto en blanco", "No votaría", "No sé"}
)


def _trasvase_por_fecha(
    df_full: pd.DataFrame,
    sv_col: str,
    pv_cand: str,
    sv_target: str,
) -> pd.DataFrame:
    """Calcular la tasa de trasvase por fecha para un candidato origen único."""
    rows: list[dict] = []
    for (enc, fecha), grp in df_full.groupby(["encuestadora", "fecha"]):
        if sv_col not in grp.columns:
            continue
        sub = grp[grp["primera_vuelta"] == pv_cand]
        if sub.empty:
            continue
        dec = sub[~sub[sv_col].isin(_INDECISOS_SV)]
        if dec.empty:
            continue
        tf = dec["factor"].sum()
        sf = dec[dec[sv_col] == sv_target]["factor"].sum()
        if tf > 0:
            rows.append({"fecha": pd.Timestamp(fecha), "pct": sf / tf * 100, "encuestadora": enc})
    return pd.DataFrame(rows).sort_values("fecha") if rows else pd.DataFrame()


def _trasvase_otros(
    df_full: pd.DataFrame,
    sv_col: str,
    sv_target: str,
    otros: Iterable[str],
) -> pd.DataFrame:
    """Calcular la tasa de trasvase desde un conjunto de candidatos *otros*."""
    rows: list[dict] = []
    for (_enc, fecha), grp in df_full.groupby(["encuestadora", "fecha"]):
        if sv_col not in grp.columns:
            continue
        sub = grp[grp["primera_vuelta"].isin(otros)]
        if sub.empty:
            continue
        dec = sub[~sub[sv_col].isin(_INDECISOS_SV)]
        if dec.empty:
            continue
        tf = dec["factor"].sum()
        sf = dec[dec[sv_col] == sv_target]["factor"].sum()
        if tf > 0:
            rows.append({"fecha": pd.Timestamp(fecha), "pct": sf / tf * 100})
    return pd.DataFrame(rows).sort_values("fecha") if rows else pd.DataFrame()


def chart_trasvase_derecha(
    df: pd.DataFrame,
    tablas: dict[str, pd.DataFrame],
    height: int = 440,
) -> go.Figure:
    """Trasvase de la derecha entre Espriella, Valencia y otros sectores.

    Args:
        df: microdatos completos (output del ingest pipeline).
        tablas: dict de DataFrames del pipeline.
        height: alto del lienzo.

    Returns:
        ``go.Figure`` con dos paneles (entre-derecha vs otros sectores).
    """
    cands_no_derecha = [
        c
        for c in top_n_candidatos(tablas, n=999, valor_col="valor")
        if c not in {"Iván Cepeda", "Abelardo de la Espriella", "Paloma Valencia"}
        and c not in INDECISOS_CATS
    ]

    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=(
            "Trasvase entre candidatos de derecha<br><sup>(excl. indecisos SV)</sup>",
            "Trasvase desde otros sectores<br><sup>(excl. indecisos SV)</sup>",
        ),
        shared_yaxes=False,
    )

    series_panel_a = [
        (
            _trasvase_por_fecha(
                df, "sv_cepeda_vs_valencia", "Abelardo de la Espriella", "Paloma Valencia"
            ),
            "Paloma recibe de Abelardo",
            c("Paloma Valencia"),
            "circle",
        ),
        (
            _trasvase_por_fecha(
                df, "sv_cepeda_vs_espriella", "Paloma Valencia", "Abelardo de la Espriella"
            ),
            "Abelardo recibe de Paloma",
            c("Abelardo de la Espriella"),
            "square",
        ),
    ]
    for serie, lbl, color, sym in series_panel_a:
        if not serie.empty:
            fig.add_trace(
                go.Scatter(
                    x=serie["fecha"],
                    y=serie["pct"],
                    name=lbl,
                    line=dict(color=color, width=2.5),
                    marker=dict(symbol=sym, size=9, color=color),
                    mode="lines+markers",
                    hovertemplate=(
                        f"<b>{lbl}</b><br>%{{x|%d %b}}: <b>%{{y:.1f}}%</b><extra></extra>"
                    ),
                ),
                row=1,
                col=1,
            )

    series_panel_b = [
        (
            _trasvase_otros(df, "sv_cepeda_vs_valencia", "Paloma Valencia", cands_no_derecha),
            "Paloma · otros sectores",
            c("Paloma Valencia"),
            "circle",
        ),
        (
            _trasvase_otros(
                df, "sv_cepeda_vs_espriella", "Abelardo de la Espriella", cands_no_derecha
            ),
            "Abelardo · otros sectores",
            c("Abelardo de la Espriella"),
            "square",
        ),
    ]
    for serie, lbl, color, sym in series_panel_b:
        if not serie.empty:
            fig.add_trace(
                go.Scatter(
                    x=serie["fecha"],
                    y=serie["pct"],
                    name=lbl,
                    line=dict(color=color, width=2.5, dash="dot"),
                    marker=dict(symbol=sym, size=9, color=color),
                    mode="lines+markers",
                    hovertemplate=(
                        f"<b>{lbl}</b><br>%{{x|%d %b}}: <b>%{{y:.1f}}%</b><extra></extra>"
                    ),
                ),
                row=1,
                col=2,
            )

    fig.update_layout(
        **LAYOUT_BASE,
        title=dict(
            text=(
                "<b>Trasvase en segunda vuelta</b><br>"
                "<sup>Porcentaje que fluye a cada candidato, "
                "excluyendo indecisos de SV</sup>"
            ),
            x=0.01,
            font_size=16,
        ),
        height=height,
        legend=dict(orientation="h", y=-0.18),
    )
    fig.update_yaxes(ticksuffix="%", range=[0, 105])
    return fig


# ════════════════════════════════════════════════════════════════════════════
#  11.4 — Perfil de indecisos
# ════════════════════════════════════════════════════════════════════════════
def chart_perfil_indecisos(
    tablas: dict[str, pd.DataFrame],
    height: int = 420,
    color_gris: str = "#6B7280",
) -> go.Figure:
    """Tres paneles con la composición demográfica de los indecisos."""
    fig = make_subplots(
        rows=1,
        cols=3,
        subplot_titles=("Por edad", "Por género", "Por región"),
        horizontal_spacing=0.08,
    )

    paneles = [
        ("indecisos_edad_grupo", "Por edad"),
        ("indecisos_sexo", "Por género"),
        ("indecisos_region", "Por región"),
    ]
    for col_idx, (tabla_key, _titulo) in enumerate(paneles, start=1):
        t = tablas.get(tabla_key, pd.DataFrame())
        if t.empty:
            continue
        dim = t.columns[0]
        val = t.columns[-1]
        ts = t.sort_values(val)
        fig.add_trace(
            go.Bar(
                x=ts[val],
                y=ts[dim],
                orientation="h",
                marker=dict(color=color_gris, line=dict(color="white", width=1)),
                text=[f"{v:.1f}%" for v in ts[val]],
                textposition="outside",
                hovertemplate=f"<b>%{{y}}</b><br>{val}: <b>%{{x:.1f}}%</b><extra></extra>",
                showlegend=False,
            ),
            row=1,
            col=col_idx,
        )
        fig.update_xaxes(ticksuffix="%", row=1, col=col_idx)

    fig.update_layout(
        **LAYOUT_BASE,
        title=dict(
            text=(
                "<b>Perfil de los indecisos en primera vuelta</b><br>"
                "<sup>Distribución de quienes no escogieron un candidato "
                "(NS/NR · Ninguno · Blanco · No votaría)</sup>"
            ),
            x=0.01,
            font_size=16,
        ),
        height=height,
        legend=dict(orientation="h", y=-0.15),
    )
    return fig


# ════════════════════════════════════════════════════════════════════════════
#  11.5 — Stacked bars por dimensión (helper + tres figuras)
# ════════════════════════════════════════════════════════════════════════════
_OTROS_MINOR_LABEL: Final[str] = "Otros candidatos"
_OTROS_MINOR_COLOR: Final[str] = "#7D8590"


def _consolidar_minoritarios(
    df_p: pd.DataFrame,
    cands_plot: list[str],
    *,
    min_pct_visible: float,
    cands_indecisos: frozenset[str],
) -> tuple[pd.DataFrame, list[str]]:
    """Consolidar candidatos minoritarios en una sola serie ``Otros candidatos``.

    Un candidato es minoritario si su % máximo a través de todas las categorías
    está por debajo de ``min_pct_visible``.  Los indecisos NUNCA se consolidan
    (mantienen su identidad NS/NR, No votaría, etc.).

    Args:
        df_p: DataFrame ya normalizado (porcentajes).  Filas = categorías,
            columnas = candidatos.
        cands_plot: lista ordenada de candidatos.
        min_pct_visible: umbral en %.  Default 3.0.
        cands_indecisos: set de nombres canónicos de indecisos para NO
            consolidarlos.

    Returns:
        Tupla ``(df_consolidado, cands_finales)`` con la nueva columna
        ``"Otros candidatos"`` agregada si hay minoritarios.
    """
    if min_pct_visible <= 0:
        return df_p, cands_plot

    minoritarios = [
        cd for cd in cands_plot if cd not in cands_indecisos and df_p[cd].max() < min_pct_visible
    ]
    if not minoritarios:
        return df_p, cands_plot

    out = df_p.drop(columns=minoritarios).copy()
    out[_OTROS_MINOR_LABEL] = df_p[minoritarios].sum(axis=1).round(2)
    # Reordenar: vigentes mayores → "Otros candidatos" → indecisos
    finales_mayores = [
        cd for cd in cands_plot if cd not in minoritarios and cd not in cands_indecisos
    ]
    finales_indecisos = [cd for cd in cands_plot if cd in cands_indecisos]
    cands_finales = [*finales_mayores, _OTROS_MINOR_LABEL, *finales_indecisos]
    return out, cands_finales


def chart_stacked_bar(
    tablas: dict[str, pd.DataFrame],
    tabla_key: str,
    dim_col: str,
    titulo: str,
    subtitle: str = "",
    esconder_indecisos: bool = False,
    height: int = 420,
    toggle_buttons: bool = True,
    min_pct_visible: float = 3.0,
) -> go.Figure:
    """Barras 100% apiladas: distribución de voto por una dimensión.

    Mejoras v0.2.5:
        - Los botones ``Con/Sin indecisos`` ahora **realmente alternan los
          datos**, no solo el título (antes era teatro: ``method="relayout"``
          sobre ``title.text`` ignorando las trazas).  Implementación: se
          dibujan AMBOS sets de trazas (con + sin indecisos) y los botones
          alternan ``visible=True/False`` via ``method="update"``.
        - Los candidatos con voto máximo < ``min_pct_visible`` (default 3 %)
          se consolidan en una sola serie gris ``"Otros candidatos"``.
          Reduce el cluster verde/púrpura/marrón ilegible.  Tooltip mantiene
          el detalle.
        - Leyenda fuera del plot area, con margen inferior recalibrado.

    Args:
        tablas: dict del pipeline.
        tabla_key: nombre de la tabla (e.g. ``voto_por_region``).
        dim_col: columna que aporta las categorías (e.g. ``region``).
        titulo: título principal.
        subtitle: subtítulo.
        esconder_indecisos: si True, el estado INICIAL es "sin indecisos".
            Los botones permiten alternar dinámicamente sin recargar.
        height: alto del lienzo (recomendado: 380 para edad/género,
            560 para región).
        toggle_buttons: si True, agrega botones funcionales de toggle.
        min_pct_visible: % máximo bajo el cual un candidato se considera
            minoritario y se consolida en "Otros candidatos".  Pasa 0 para
            desactivar la consolidación.

    Returns:
        ``go.Figure`` con la barra apilada o ``Figure`` vacía si faltan datos.
    """
    if tabla_key not in tablas:
        return _figura_vacia(f"Tabla {tabla_key!r} no disponible.")
    t = tablas[tabla_key].copy()
    cands_v, cands_i = candidatos_y_indecisos(tablas, INDECISOS_CATS)
    orden_completo = cands_v + cands_i
    cands_use = [cd for cd in orden_completo if cd in t.columns]
    if not cands_use:
        return _figura_vacia("No hay columnas de candidato en la tabla.")

    dims = t[dim_col].tolist()

    # ── 1. Calcular AMBOS sets de datos (con y sin indecisos) ──────────
    # Con indecisos: usa todos los candidatos tal cual
    df_con = t[cands_use].copy()
    # Sin indecisos: renormaliza descontando indecisos
    cands_sin = [cd for cd in cands_use if cd not in INDECISOS_CATS]
    if cands_sin:
        totales = t[cands_sin].sum(axis=1)
        df_sin = t[cands_sin].div(totales, axis=0).mul(100)
    else:
        df_sin = pd.DataFrame()

    # Consolidar minoritarios en cada set (solo no-indecisos)
    df_con_c, cands_con_final = _consolidar_minoritarios(
        df_con,
        cands_use,
        min_pct_visible=min_pct_visible,
        cands_indecisos=INDECISOS_CATS,
    )
    if cands_sin:
        df_sin_c, cands_sin_final = _consolidar_minoritarios(
            df_sin,
            cands_sin,
            min_pct_visible=min_pct_visible,
            cands_indecisos=INDECISOS_CATS,
        )
    else:
        df_sin_c, cands_sin_final = pd.DataFrame(), []

    # ── 2. Pintar ambos sets como trazas (uno visible, otro oculto) ─────
    visible_inicial_con = not esconder_indecisos
    fig = go.Figure()

    def _color_serie(cand: str) -> str:
        if cand == _OTROS_MINOR_LABEL:
            return _OTROS_MINOR_COLOR
        return c(cand)

    def _texto_contrastado(color_bg: str) -> str:
        """Devolver color de texto adecuado al fondo (blanco/negro)."""
        # Cálculo simple de luminosidad (no tan estricto como WCAG pero
        # suficiente para colores planos)
        hexv = color_bg.lstrip("#")
        if len(hexv) != 6:
            return "white"
        r, g, b = int(hexv[0:2], 16), int(hexv[2:4], 16), int(hexv[4:6], 16)
        lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        return "white" if lum < 0.55 else "#2A2A2A"

    # Trazas "con indecisos"
    n_con = 0
    for cand in cands_con_final:
        col = _color_serie(cand)
        vals = df_con_c[cand].to_numpy(dtype=float).round(1)
        texts = [f"{v:.0f}%" if v >= 5 else "" for v in vals]
        fig.add_trace(
            go.Bar(
                name=cand,
                y=dims,
                x=vals,
                orientation="h",
                marker=dict(color=col, line=dict(color="white", width=0.8)),
                text=texts,
                textposition="inside",
                insidetextanchor="middle",
                textfont=dict(color=_texto_contrastado(col), size=12),
                hovertemplate=f"<b>{cand}</b><br>%{{y}}: <b>%{{x:.1f}}%</b><extra></extra>",
                visible=visible_inicial_con,
                legendgroup="con",
            )
        )
        n_con += 1

    # Trazas "sin indecisos"
    n_sin = 0
    for cand in cands_sin_final:
        col = _color_serie(cand)
        vals = df_sin_c[cand].to_numpy(dtype=float).round(1)
        texts = [f"{v:.0f}%" if v >= 5 else "" for v in vals]
        fig.add_trace(
            go.Bar(
                name=cand,
                y=dims,
                x=vals,
                orientation="h",
                marker=dict(color=col, line=dict(color="white", width=0.8)),
                text=texts,
                textposition="inside",
                insidetextanchor="middle",
                textfont=dict(color=_texto_contrastado(col), size=12),
                hovertemplate=f"<b>{cand}</b><br>%{{y}}: <b>%{{x:.1f}}%</b><extra></extra>",
                visible=not visible_inicial_con,
                legendgroup="sin",
            )
        )
        n_sin += 1

    # ── 3. Botones que REALMENTE alternan visibilidad de los dos sets ──
    updatemenus = []
    if toggle_buttons and n_con > 0 and n_sin > 0:
        vis_con = [True] * n_con + [False] * n_sin
        vis_sin = [False] * n_con + [True] * n_sin
        updatemenus = [
            dict(
                type="buttons",
                direction="right",
                x=0.0,
                y=1.18,
                xanchor="left",
                yanchor="bottom",
                showactive=True,
                pad=dict(r=4, t=2, b=2),
                buttons=[
                    dict(
                        label="Con indecisos",
                        method="update",
                        args=[
                            {"visible": vis_con},
                            {
                                "title.text": (
                                    f"<b>{titulo}</b><br>"
                                    f"<sup style='color:#666'>{subtitle} · "
                                    "Con indecisos</sup>"
                                ),
                            },
                        ],
                    ),
                    dict(
                        label="Sin indecisos",
                        method="update",
                        args=[
                            {"visible": vis_sin},
                            {
                                "title.text": (
                                    f"<b>{titulo}</b><br>"
                                    f"<sup style='color:#666'>{subtitle} · "
                                    "Sin indecisos (normalizado sobre decididos)</sup>"
                                ),
                            },
                        ],
                    ),
                ],
            )
        ]

    estado_inicial = "Con indecisos" if visible_inicial_con else "Sin indecisos"
    fig.update_layout(
        **LAYOUT_BASE,
        barmode="stack",
        title=dict(
            text=(
                f"<b>{titulo}</b><br><sup style='color:#666'>{subtitle} · {estado_inicial}</sup>"
            ),
            x=0.01,
            y=0.97,
            font_size=15,
        ),
        height=height,
        margin=dict(l=110, r=30, t=110, b=170),
        updatemenus=updatemenus,
        legend=dict(
            orientation="h",
            y=-0.22,
            x=0.5,
            xanchor="center",
            traceorder="normal",
            bgcolor="rgba(255,255,255,0.95)",
            bordercolor="#E5E7EB",
            borderwidth=1,
            font=dict(size=11),
        ),
    )
    fig.update_xaxes(range=[0, 101], ticksuffix="%", showgrid=True, gridcolor="#e8eaf0")
    fig.update_yaxes(autorange="reversed")
    return fig


# ════════════════════════════════════════════════════════════════════════════
#  11.6 — Sesgo demográfico por encuestadora
# ════════════════════════════════════════════════════════════════════════════
def chart_sesgo_demografico(
    tablas: dict[str, pd.DataFrame],
    tabla_key: str,
    titulo: str,
    subtitle: str = "",
    height: int = 400,
) -> go.Figure:
    """Barras agrupadas con el sesgo (en pp) de cada encuestadora vs el resto.

    Acepta dos formatos de tabla:

    *Long* — el que produce :func:`encuestas_lib.analysis.tables.sesgo_por_encuestadora`
    con columnas ``[encuestadora, variable, categoria, peso_encuestadora,
    peso_promedio_otras, sesgo_rel_pp]``.  Se pivota a wide internamente.

    *Wide* — un DataFrame con una columna categórica (la dimensión, e.g.
    ``edad_grupo``) y una columna numérica por encuestadora.  Útil para tests
    y para datos preparados manualmente.

    Args:
        tablas: dict del pipeline.
        tabla_key: nombre de la tabla (e.g. ``sesgo_edad``).
        titulo: título principal.
        subtitle: subtítulo.
        height: alto del lienzo.

    Returns:
        ``go.Figure`` con barras agrupadas o una figura placeholder si los
        datos no permiten graficar.
    """
    if tabla_key not in tablas:
        return _figura_vacia(f"Tabla {tabla_key!r} no disponible.")
    t = tablas[tabla_key].copy()
    if t.empty:
        return _figura_vacia(f"Tabla {tabla_key!r} está vacía.")

    # Detectar formato long del pipeline real y pivotar a wide
    cols_long = {"encuestadora", "categoria", "sesgo_rel_pp"}
    if cols_long.issubset(t.columns):
        t = (
            t.pivot_table(
                index="categoria",
                columns="encuestadora",
                values="sesgo_rel_pp",
                aggfunc="mean",
            )
            .reset_index()
            .rename_axis(columns=None)
        )
        dim_col = "categoria"
        encuestadoras = [col for col in t.columns if col != dim_col]
    else:
        # Formato wide: primera columna categórica = dimensión; resto = encuestadoras
        obj_cols = t.select_dtypes(include=["object", "string"]).columns
        if not len(obj_cols):
            return _figura_vacia("No hay columna categórica en la tabla.")
        dim_col = obj_cols[0]
        encuestadoras = [col for col in t.columns if col != dim_col]

    if not encuestadoras:
        return _figura_vacia(f"Tabla {tabla_key!r} no tiene columnas de encuestadora.")

    cats = t[dim_col].tolist()
    colores = ["#1B4F9A", "#D4890A", "#7B1E3C", "#2E7D4F", "#5B3E8A"]

    fig = go.Figure()
    for i, enc in enumerate(encuestadoras):
        # to_numeric con coerción evita TypeError si alguna celda viene NaN/None
        vals = pd.to_numeric(t[enc], errors="coerce").to_numpy(dtype=float)
        fig.add_trace(
            go.Bar(
                name=str(enc),
                x=cats,
                y=vals,
                marker=dict(
                    color=colores[i % len(colores)],
                    opacity=0.85,
                    line=dict(color="white", width=0.8),
                ),
                hovertemplate=f"<b>{enc}</b><br>%{{x}}: <b>%{{y:+.1f}}pp</b><extra></extra>",
            )
        )
    fig.add_hline(y=0, line_color="#1a1a2e", line_width=1.5)

    fig.update_layout(
        **LAYOUT_BASE,
        barmode="group",
        title=dict(
            text=f"<b>{titulo}</b><br><sup>{subtitle}</sup>",
            x=0.01,
            font_size=15,
        ),
        height=height,
        legend=dict(orientation="h", y=1.15, x=0),
    )
    fig.update_yaxes(
        ticksuffix="pp",
        title="Diferencia en pp vs promedio del resto",
        showgrid=True,
        gridcolor="#e8eaf0",
        zeroline=False,
    )
    fig.update_xaxes(title="")
    return fig


# ════════════════════════════════════════════════════════════════════════════
#  11.7 — Petrismo entre votantes del candidato líder
# ════════════════════════════════════════════════════════════════════════════
def chart_petrismo_cepeda(
    tablas: dict[str, pd.DataFrame],
    candidato: str = "Iván Cepeda",
    height: int = 260,
) -> go.Figure:
    """Distribución de la aprobación a Petro entre los votantes de ``candidato``."""
    fig = go.Figure()
    t_vva = tablas.get("voto_vs_aprobacion")
    if t_vva is None or "primera_vuelta" not in t_vva.columns:
        return _figura_vacia("Tabla voto_vs_aprobacion no disponible.")

    cep = t_vva[t_vva["primera_vuelta"] == candidato]
    cats_apro = [ca for ca in ["Aprueba", "Regular", "Desaprueba", "NS/NR"] if ca in cep.columns]
    col_map = {
        "Aprueba": "#1B4F9A",
        "Regular": "#7EB3D8",
        "Desaprueba": "#D4890A",
        "NS/NR": "#C8C8C8",
    }
    if cep.empty or not cats_apro:
        return _figura_vacia(f"Sin datos para {candidato!r}.")

    for cat in cats_apro:
        val = float(cep[cat].iloc[0])
        fig.add_trace(
            go.Bar(
                name=cat,
                x=[val],
                y=[f"Votantes de {candidato.split()[-1]}"],
                orientation="h",
                marker=dict(color=col_map.get(cat, "#888"), line=dict(color="white", width=0.8)),
                text=[f"<b>{cat}</b><br>{val:.0f}%"] if val >= 5 else [""],
                textposition="inside",
                insidetextanchor="middle",
                hovertemplate=f"<b>{cat}</b>: <b>%{{x:.1f}}%</b><extra></extra>",
            )
        )

    fig.update_layout(
        **LAYOUT_BASE,
        barmode="stack",
        title=dict(
            text=(
                f"<b>¿Cuántos votantes de {candidato.split()[-1]} aprueban a Petro?</b><br>"
                "<sup>Distribución de la aprobación del gobierno Petro entre "
                f"quienes votarían por {candidato.split()[-1]} en primera vuelta</sup>"
            ),
            x=0.01,
            font_size=15,
        ),
        height=height,
        legend=dict(orientation="h", y=-0.25, x=0),
        showlegend=True,
    )
    fig.update_xaxes(range=[0, 101], ticksuffix="%", showgrid=True, gridcolor="#e8eaf0")
    fig.update_yaxes(showgrid=False)
    return fig


# ════════════════════════════════════════════════════════════════════════════
#  11.8 — Composición por género de cada candidato
# ════════════════════════════════════════════════════════════════════════════
def chart_composicion_genero(
    tablas: dict[str, pd.DataFrame],
    height: int = 400,
) -> go.Figure:
    """Distribución H/M para cada candidato del top-4.

    Acepta dos schemas de ``genero_por_candidato_top4``:

    *Real (pipeline)* — ``[primera_vuelta, Hombre, Mujer]``: producto de
    ``out.pivot(index='primera_vuelta', columns='sexo', values='valor')``.
    Cada fila es un candidato; columnas ``Hombre``/``Mujer`` son numéricas.

    *Transpuesto (tests legacy)* — ``[sexo, candA, candB, ...]``: una fila
    por género, columnas por candidato.

    Se detecta automáticamente cuál de los dos viene mirando si las columnas
    incluyen ``"Hombre"`` y/o ``"Mujer"``.
    """
    fig = go.Figure()
    t_gc = tablas.get("genero_por_candidato_top4")
    if t_gc is None or t_gc.empty:
        return _figura_vacia("Tabla genero_por_candidato_top4 no disponible.")

    cols = set(t_gc.columns)
    schema_real = (
        {"Hombre", "Mujer"}.issubset(cols) or {"Hombre"}.issubset(cols) or {"Mujer"}.issubset(cols)
    )

    if schema_real:
        # Schema real: filas=candidato, columnas=Hombre/Mujer
        obj_cols = t_gc.select_dtypes(include=["object", "string"]).columns
        if not len(obj_cols):
            return _figura_vacia("Tabla sin columna de candidato.")
        cand_col = obj_cols[0]  # 'primera_vuelta' u otra
        candidatos = t_gc[cand_col].tolist()
        if "Hombre" in cols:
            fig.add_trace(
                go.Bar(
                    name="Hombre",
                    x=candidatos,
                    y=pd.to_numeric(t_gc["Hombre"], errors="coerce").to_numpy(dtype=float),
                    marker=dict(color="#4A90D9", line=dict(color="white", width=0.8)),
                    hovertemplate="<b>Hombre</b><br>%{x}: <b>%{y:.1f}%</b><extra></extra>",
                )
            )
        if "Mujer" in cols:
            fig.add_trace(
                go.Bar(
                    name="Mujer",
                    x=candidatos,
                    y=pd.to_numeric(t_gc["Mujer"], errors="coerce").to_numpy(dtype=float),
                    marker=dict(color="#E87A8C", line=dict(color="white", width=0.8)),
                    hovertemplate="<b>Mujer</b><br>%{x}: <b>%{y:.1f}%</b><extra></extra>",
                )
            )
    else:
        # Schema transpuesto: filas=género, columnas=candidatos
        obj_cols = t_gc.select_dtypes(include=["object", "string"]).columns
        if not len(obj_cols):
            return _figura_vacia("Tabla sin columna categórica.")
        dim_col = obj_cols[0]
        cand_cols = [col for col in t_gc.columns if col != dim_col and col not in INDECISOS_CATS]
        h_row = t_gc[t_gc[dim_col] == "Hombre"]
        m_row = t_gc[t_gc[dim_col] == "Mujer"]
        if not h_row.empty and cand_cols:
            fig.add_trace(
                go.Bar(
                    name="Hombre",
                    x=cand_cols,
                    y=[float(h_row.iloc[0][col]) for col in cand_cols],
                    marker=dict(color="#4A90D9", line=dict(color="white", width=0.8)),
                    hovertemplate="<b>Hombre</b><br>%{x}: <b>%{y:.1f}%</b><extra></extra>",
                )
            )
        if not m_row.empty and cand_cols:
            fig.add_trace(
                go.Bar(
                    name="Mujer",
                    x=cand_cols,
                    y=[float(m_row.iloc[0][col]) for col in cand_cols],
                    marker=dict(color="#E87A8C", line=dict(color="white", width=0.8)),
                    hovertemplate="<b>Mujer</b><br>%{x}: <b>%{y:.1f}%</b><extra></extra>",
                )
            )

    fig.update_layout(
        **LAYOUT_BASE,
        barmode="group",
        title=dict(
            text=(
                "<b>Composición por género de cada candidato</b><br>"
                "<sup>De cada 100 votantes del candidato, "
                "porcentaje que son Hombre / Mujer</sup>"
            ),
            x=0.01,
            font_size=15,
        ),
        height=height,
        legend=dict(orientation="h", y=1.12),
    )
    fig.update_yaxes(ticksuffix="%", range=[0, 100], showgrid=True, gridcolor="#e8eaf0")
    fig.update_xaxes(tickangle=-20)
    return fig


# ════════════════════════════════════════════════════════════════════════════
#  11.9 — Primera vuelta total + indecisos
# ════════════════════════════════════════════════════════════════════════════
def chart_primera_vuelta_total(
    tablas: dict[str, pd.DataFrame],
    height: int = 480,
) -> go.Figure:
    """Dos paneles: candidatos vs indecisos del agregado de primera vuelta."""
    pv = tablas["primera_vuelta_total"].copy()
    pv_dec = pv[~pv["primera_vuelta"].isin(INDECISOS_CATS)].sort_values("valor")
    pv_ind = pv[pv["primera_vuelta"].isin(INDECISOS_CATS)].sort_values("valor")

    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=(
            "Candidatos (% total respondentes)",
            "Indecisos desglosados",
        ),
        horizontal_spacing=0.10,
    )

    fig.add_trace(
        go.Bar(
            y=pv_dec["primera_vuelta"],
            x=pv_dec["valor"],
            orientation="h",
            marker=dict(
                color=[c(cd) for cd in pv_dec["primera_vuelta"]],
                line=dict(color="white", width=0.8),
            ),
            text=[f"<b>{v:.1f}%</b>" for v in pv_dec["valor"]],
            textposition="outside",
            hovertemplate="<b>%{y}</b>: <b>%{x:.1f}%</b><extra></extra>",
            showlegend=False,
        ),
        row=1,
        col=1,
    )

    gris2 = "#9CA3AF"
    fig.add_trace(
        go.Bar(
            y=pv_ind["primera_vuelta"],
            x=pv_ind["valor"],
            orientation="h",
            marker=dict(color=gris2, line=dict(color="white", width=0.8)),
            text=[f"{v:.1f}%" for v in pv_ind["valor"]],
            textposition="outside",
            hovertemplate="<b>%{y}</b>: <b>%{x:.1f}%</b><extra></extra>",
            showlegend=False,
        ),
        row=1,
        col=2,
    )

    fig.update_layout(
        **LAYOUT_BASE,
        title=dict(
            text=(
                "<b>Intención de voto — Primera vuelta</b><br>"
                "<sup>Promedio ponderado de todas las encuestas</sup>"
            ),
            x=0.01,
            font_size=16,
        ),
        height=height,
    )
    fig.update_xaxes(ticksuffix="%")
    return fig


# ════════════════════════════════════════════════════════════════════════════
#  Helpers privados
# ════════════════════════════════════════════════════════════════════════════
def _figura_vacia(mensaje: str) -> go.Figure:
    """Devolver una figura vacía con un mensaje informativo en el centro."""
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
    "chart_composicion_genero",
    "chart_perfil_indecisos",
    "chart_petrismo_cepeda",
    "chart_primera_vuelta_total",
    "chart_sankey_pv_sv",
    "chart_sesgo_demografico",
    "chart_stacked_bar",
    "chart_tendencia_temporal",
    "chart_trasvase_derecha",
]
