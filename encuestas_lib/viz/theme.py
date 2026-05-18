"""Tema visual unificado para Plotly — Encuestas Presidenciales Colombia 2026.

Contexto: Google Colab Free (~12 GB RAM, sesión de 12 h).
Punto de verdad único para paleta, indecisos, template Plotly y layout base.

Resuelve el bug recurrente ``TypeError: update_layout() got multiple values for
keyword argument 'yaxis'`` que aparecía al combinar ``**LAYOUT_BASE`` con un
``yaxis=`` o ``xaxis=`` explícito en cada gráfica.  La solución profesional es
registrar un *Plotly template* (``lsv``) que aporta los defaults visuales sin
ocupar los kwargs ``xaxis``/``yaxis`` del layout — de ese modo las gráficas
quedan libres de redefinir esos ejes sin colisión.

Dependencias: plotly>=5.18.

Author: encuestas_lib
Date: 2026-05-17
Version: 0.2.0
"""

from __future__ import annotations

from typing import Final

import plotly.graph_objects as go
import plotly.io as pio

# ════════════════════════════════════════════════════════════════════════════
#  Paleta canónica (aproxima los colores del PDF de La Silla Vacía)
# ════════════════════════════════════════════════════════════════════════════
PALETA: Final[dict[str, str]] = {
    # Candidatos vigentes
    "Iván Cepeda": "#7B1E3C",
    "Abelardo de la Espriella": "#D4890A",
    "Paloma Valencia": "#1B4F9A",
    "Sergio Fajardo": "#2E7D4F",
    "Claudia López": "#1A7A7A",
    "Santiago Botero": "#5B3E8A",
    "Roy Barreras": "#A63D2F",
    "Carlos Caicedo": "#7B3F00",
    "Miguel Uribe Londoño": "#3A3A8A",
    "Mauricio Lizcano": "#4D5E6F",
    "Luis Gilberto Murillo": "#1D6B1D",
    "Sondra Macollins": "#9B6B2A",
    "Clara López": "#0A6B5A",
    # Categorías especiales / indecisos
    "Otro candidato": "#A0A0A0",
    "Voto en blanco": "#C8C8C8",
    "Blanco": "#C8C8C8",
    "NS/NR": "#B8B8B8",
    "Ninguno": "#D0D0D0",
    "No votaría": "#D8D8D8",
    "No sé": "#E0E0E0",
    "Indecisos": "#B0B0B0",
    # Aprobación
    "Aprueba": "#1B4F9A",
    "Regular": "#7EB3D8",
    "Desaprueba": "#D4890A",
}

INDECISOS_CATS: Final[frozenset[str]] = frozenset(
    {
        "NS/NR",
        "Ninguno",
        "Voto en blanco",
        "No votaría",
        "No sé",
        "Otro candidato",
        "Blanco",
    }
)

# Color por defecto si una categoría no está en la paleta
DEFAULT_COLOR: Final[str] = "#888888"

# Nombre del template Plotly registrado por este módulo
TEMPLATE_NAME: Final[str] = "lsv"


# ════════════════════════════════════════════════════════════════════════════
#  Helpers de color
# ════════════════════════════════════════════════════════════════════════════
def c(nombre: str) -> str:
    """Devolver el hex color asignado a ``nombre`` o el gris por defecto."""
    return PALETA.get(nombre, DEFAULT_COLOR)


def hex_to_rgba(hex_color: str, alpha: float = 0.25) -> str:
    """Convertir un hex ``#RRGGBB`` a una cadena ``rgba(r,g,b,a)``.

    Args:
        hex_color: hex code con o sin ``#`` prefix (e.g. ``#7B1E3C``).
        alpha: opacidad entre 0 y 1.

    Returns:
        Cadena ``rgba(r,g,b,a)`` lista para usar en marcadores Plotly.

    Raises:
        ValueError: si ``alpha`` está fuera de ``[0, 1]`` o si ``hex_color``
            no tiene 6 dígitos hex después de eliminar el prefijo ``#``.

    Example:
        >>> hex_to_rgba("#7B1E3C", 0.5)
        'rgba(123,30,60,0.5)'
    """
    if not 0.0 <= alpha <= 1.0:
        raise ValueError(f"alpha debe estar entre 0 y 1, recibido {alpha}.")
    h = hex_color.lstrip("#")
    if len(h) != 6:
        raise ValueError(f"hex_color debe tener 6 dígitos, recibido {hex_color!r}.")
    try:
        r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    except ValueError as exc:
        raise ValueError(f"hex_color contiene dígitos no-hex: {hex_color!r}") from exc
    return f"rgba({r},{g},{b},{alpha})"


# ════════════════════════════════════════════════════════════════════════════
#  Template Plotly registrado — fuente única de verdad de estilo
# ════════════════════════════════════════════════════════════════════════════
# Notas de diseño:
#   1. El template aporta defaults visuales (font, bg, hover, gridlines) PERO
#      NO declara ``xaxis``/``yaxis`` específicos como keys del layout, sino
#      como ``xaxis_*``/``yaxis_*`` patron-aplicado por Plotly.  Esto evita el
#      conflicto cuando una gráfica hace ``fig.update_layout(xaxis=dict(...))``.
#   2. Cada gráfica puede sobreescribir cualquier propiedad sin error.
_LSV_TEMPLATE = go.layout.Template(
    layout=go.Layout(
        font=dict(
            family="'Source Sans Pro', 'Helvetica Neue', Arial, sans-serif",
            size=13,
            color="#1a1a2e",
        ),
        paper_bgcolor="#ffffff",
        plot_bgcolor="#f8f9fb",
        hoverlabel=dict(bgcolor="white", font_size=13, font_family="Arial"),
        margin=dict(l=10, r=10, t=60, b=10),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            bgcolor="rgba(255,255,255,0.9)",
            bordercolor="#e0e0e0",
            borderwidth=1,
        ),
        xaxis=dict(showgrid=True, gridcolor="#e8eaf0", zeroline=False),
        yaxis=dict(showgrid=False, zeroline=False),
        colorway=list(PALETA.values()),
    ),
)


def register_template(set_as_default: bool = True) -> None:
    """Registrar el template ``lsv`` en ``plotly.io.templates``.

    Llamar una sola vez al inicio del notebook.  Idempotente.

    Args:
        set_as_default: si True (default), configura ``pio.templates.default``
            con el template combinado ``"plotly+lsv"``, de modo que cualquier
            ``go.Figure()`` recibe el estilo sin código adicional.
    """
    pio.templates[TEMPLATE_NAME] = _LSV_TEMPLATE
    if set_as_default:
        pio.templates.default = f"plotly+{TEMPLATE_NAME}"


# ════════════════════════════════════════════════════════════════════════════
#  Layout overrides reutilizables — dict VACÍO por diseño
# ════════════════════════════════════════════════════════════════════════════
#: Dict vacío para ``fig.update_layout(**LAYOUT_BASE, ...)``.
#:
#: Convertido a ``{}`` en v0.2.0 (eliminación del bug raíz).  Originalmente
#: contenía ``font``, ``margin``, ``legend``, ``xaxis``, ``yaxis`` — pero
#: CUALQUIER clave aquí podía colisionar con un override en la gráfica y
#: producir ``TypeError: got multiple values for keyword argument 'X'``.
#:
#: Solución arquitectónica: el template ``lsv`` registrado vía
#: :func:`register_template` aporta TODOS los defaults visuales (font,
#: paper_bgcolor, plot_bgcolor, hoverlabel, margin, legend, xaxis, yaxis,
#: colorway).  Las gráficas hacen sus overrides libremente con
#: ``fig.update_layout(margin=..., legend=..., title=..., ...)`` sin ningún
#: riesgo de colisión.
#:
#: Se mantiene la variable como nombre simbólico para compatibilidad y para
#: que cualquier código existente que haga ``**LAYOUT_BASE`` siga compilando
#: sin efecto secundario.
LAYOUT_BASE: Final[dict] = {}


__all__ = [
    "DEFAULT_COLOR",
    "INDECISOS_CATS",
    "LAYOUT_BASE",
    "PALETA",
    "TEMPLATE_NAME",
    "c",
    "hex_to_rgba",
    "register_template",
]
