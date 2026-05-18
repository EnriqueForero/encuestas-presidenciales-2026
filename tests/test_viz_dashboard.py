"""Tests del exportador HTML de ``encuestas_lib.viz.dashboard``."""

from __future__ import annotations

import plotly.graph_objects as go
import pytest

from encuestas_lib.viz.dashboard import (
    SECCIONES_STEP11,
    SECCIONES_STEP12,
    SeccionMeta,
    export_dashboard,
)


@pytest.fixture
def figuras_minimas() -> dict[str, go.Figure]:
    """Tres figuras válidas listas para incrustar en el HTML."""
    fig_a = go.Figure(data=[go.Bar(x=["A", "B"], y=[1, 2])])
    fig_b = go.Figure(data=[go.Scatter(x=[0, 1], y=[1, 2])])
    fig_c = go.Figure(data=[go.Bar(x=["X"], y=[3])])
    return {
        "09_pv_total": fig_a,
        "01_tendencia": fig_b,
        "12_02_monte_carlo": fig_c,
    }


class TestSeccionMeta:
    def test_icon_y_label_separados_correctamente(self):
        sec = SeccionMeta("k", "📊 Voto total", "desc")
        assert sec.icon == "📊"
        assert sec.label == "Voto total"

    def test_secciones_step11_no_duplican_keys(self):
        keys = [s.key for s in SECCIONES_STEP11]
        assert len(keys) == len(set(keys))

    def test_secciones_step12_no_duplican_keys(self):
        keys = [s.key for s in SECCIONES_STEP12]
        assert len(keys) == len(set(keys))


class TestExportDashboard:
    def test_genera_archivo_html(self, figuras_minimas, tmp_path):
        out = export_dashboard(
            figuras=figuras_minimas,
            out_path=tmp_path / "dashboard.html",
        )
        assert out.exists()
        assert out.suffix == ".html"
        contenido = out.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in contenido
        assert "Dashboard · Colombia 2026" in contenido

    def test_html_incluye_secciones_de_figuras_presentes(
        self,
        figuras_minimas,
        tmp_path,
    ):
        out = export_dashboard(
            figuras=figuras_minimas,
            out_path=tmp_path / "dashboard.html",
        )
        contenido = out.read_text(encoding="utf-8")
        assert 'id="09_pv_total"' in contenido
        assert 'id="01_tendencia"' in contenido

    def test_html_omite_secciones_sin_figura(self, figuras_minimas, tmp_path):
        """Si una sección de SECCIONES_STEP11 no tiene figura, no aparece."""
        out = export_dashboard(
            figuras=figuras_minimas,
            out_path=tmp_path / "dashboard.html",
        )
        contenido = out.read_text(encoding="utf-8")
        # "07_petro" está en SECCIONES_STEP11 pero no en figuras_minimas
        assert 'id="07_petro"' not in contenido

    def test_dict_figuras_vacio_lanza_valueerror(self, tmp_path):
        with pytest.raises(ValueError, match="vacío"):
            export_dashboard(figuras={}, out_path=tmp_path / "x.html")

    def test_html_es_utf8_valido(self, figuras_minimas, tmp_path):
        out = export_dashboard(
            figuras=figuras_minimas,
            out_path=tmp_path / "dashboard.html",
        )
        # No debe lanzar al decodificar
        out.read_text(encoding="utf-8")

    def test_step12_banner_solo_si_hay_secciones_step12(
        self,
        figuras_minimas,
        tmp_path,
    ):
        # Caso 1: con Step 12 — div con class step12-banner debe aparecer
        out = export_dashboard(
            figuras=figuras_minimas,
            out_path=tmp_path / "con_step12.html",
        )
        assert 'class="step12-banner"' in out.read_text(encoding="utf-8")

        # Caso 2: sin Step 12 — sin el div banner (aunque el CSS sigue presente)
        out = export_dashboard(
            figuras={k: v for k, v in figuras_minimas.items() if not k.startswith("12_")},
            out_path=tmp_path / "sin_step12.html",
            secciones_step12=(),
        )
        assert 'class="step12-banner"' not in out.read_text(encoding="utf-8")
