"""encuestas_lib.viz — Visualización Plotly del pipeline de encuestas 2026.

Submódulos:
    - theme       : paleta, helpers de color, template Plotly registrado.
    - charts      : funciones puras que devuelven ``plotly.graph_objects.Figure``.
    - dashboard   : exportador HTML autocontenido.

Entrada típica:
    >>> from encuestas_lib.viz import register_template
    >>> from encuestas_lib.viz.charts.step11 import chart_tendencia_temporal
    >>> register_template()
    >>> fig = chart_tendencia_temporal(tablas)
    >>> fig.show()
"""

from encuestas_lib.viz.theme import (
    INDECISOS_CATS,
    LAYOUT_BASE,
    PALETA,
    c,
    hex_to_rgba,
    register_template,
)

__all__ = [
    "INDECISOS_CATS",
    "LAYOUT_BASE",
    "PALETA",
    "c",
    "hex_to_rgba",
    "register_template",
]
