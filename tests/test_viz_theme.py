"""Tests del módulo ``encuestas_lib.viz.theme``.

Cubre los puntos críticos:
    - ``register_template`` es idempotente y registra el template ``lsv``.
    - ``c()`` devuelve el color canónico o el fallback gris.
    - ``hex_to_rgba`` valida sus inputs (regresión del bug raíz).
    - ``LAYOUT_BASE`` NO contiene ``xaxis``/``yaxis`` — la causa raíz del
      TypeError ``got multiple values for keyword argument 'yaxis'``.
"""

from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio
import pytest

from encuestas_lib.viz import theme


# ════════════════════════════════════════════════════════════════════════════
#  Color helpers
# ════════════════════════════════════════════════════════════════════════════
class TestPaleta:
    """Paleta y helper ``c()``."""

    def test_candidato_principal_tiene_color_unico(self):
        """Cepeda y Espriella tienen colores distintos definidos."""
        assert theme.c("Iván Cepeda") != theme.c("Abelardo de la Espriella")
        assert theme.c("Iván Cepeda").startswith("#")

    def test_candidato_desconocido_devuelve_gris(self):
        assert theme.c("Candidato Inexistente") == theme.DEFAULT_COLOR

    def test_indecisos_cats_no_vacio(self):
        assert "NS/NR" in theme.INDECISOS_CATS
        assert "Otro candidato" in theme.INDECISOS_CATS


class TestHexToRgba:
    """Conversor hex → rgba."""

    def test_hex_valido_con_prefijo(self):
        assert theme.hex_to_rgba("#7B1E3C", 0.5) == "rgba(123,30,60,0.5)"

    def test_hex_valido_sin_prefijo(self):
        assert theme.hex_to_rgba("7B1E3C", 0.25) == "rgba(123,30,60,0.25)"

    def test_alpha_fuera_de_rango_lanza_valueerror(self):
        with pytest.raises(ValueError, match="alpha"):
            theme.hex_to_rgba("#000000", 1.5)
        with pytest.raises(ValueError, match="alpha"):
            theme.hex_to_rgba("#000000", -0.1)

    def test_hex_longitud_invalida_lanza_valueerror(self):
        with pytest.raises(ValueError, match="6 dígitos"):
            theme.hex_to_rgba("#ABC", 0.5)

    def test_hex_no_hex_lanza_valueerror(self):
        with pytest.raises(ValueError, match="no-hex"):
            theme.hex_to_rgba("#ZZZZZZ", 0.5)


# ════════════════════════════════════════════════════════════════════════════
#  Template Plotly
# ════════════════════════════════════════════════════════════════════════════
class TestRegisterTemplate:
    """Registro del template ``lsv`` en plotly.io."""

    def test_register_template_es_idempotente(self):
        theme.register_template()
        theme.register_template()  # no debe fallar al re-registrar
        assert theme.TEMPLATE_NAME in pio.templates

    def test_default_template_incluye_lsv(self):
        theme.register_template(set_as_default=True)
        assert theme.TEMPLATE_NAME in (pio.templates.default or "")

    def test_template_aporta_paper_bgcolor(self):
        theme.register_template()
        tmpl = pio.templates[theme.TEMPLATE_NAME]
        assert tmpl.layout.paper_bgcolor == "#ffffff"


# ════════════════════════════════════════════════════════════════════════════
#  Regresión del bug raíz
# ════════════════════════════════════════════════════════════════════════════
class TestLayoutBaseNoColisionaConEjes:
    """``LAYOUT_BASE`` no debe contener ``xaxis``/``yaxis``.

    Es la causa raíz del TypeError reportado al usuario.  Si alguien vuelve a
    añadir esos kwargs a ``LAYOUT_BASE``, este test los atrapa antes de CI.
    """

    def test_layout_base_no_contiene_xaxis(self):
        assert "xaxis" not in theme.LAYOUT_BASE

    def test_layout_base_no_contiene_yaxis(self):
        assert "yaxis" not in theme.LAYOUT_BASE

    def test_update_layout_con_layout_base_y_yaxis_no_falla(self):
        theme.register_template()
        fig = go.Figure()
        # Justo el patrón que producía TypeError en el código original
        fig.update_layout(
            **theme.LAYOUT_BASE,
            yaxis=dict(ticksuffix="%"),
            xaxis=dict(title="Fecha"),
        )
        assert fig.layout.yaxis.ticksuffix == "%"
        assert fig.layout.xaxis.title.text == "Fecha"
