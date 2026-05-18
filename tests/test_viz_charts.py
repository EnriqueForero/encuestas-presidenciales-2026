"""Smoke tests de las funciones de ``encuestas_lib.viz.charts``.

Cada función debe (a) devolver un ``plotly.graph_objects.Figure``, (b) no
lanzar excepciones con tablas mínimas válidas, (c) devolver una figura
placeholder limpia cuando los datos están ausentes.

Estos tests son rápidos (<1 s en total) y deben correr en CI sin datos
reales del CNE.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import pytest

from encuestas_lib.viz import register_template
from encuestas_lib.viz.charts import step11


# ════════════════════════════════════════════════════════════════════════════
#  Fixtures
# ════════════════════════════════════════════════════════════════════════════
@pytest.fixture(autouse=True)
def _registrar_template():
    """Asegura que el template ``lsv`` está activo en cada test."""
    register_template()


@pytest.fixture
def tablas_minimas() -> dict[str, pd.DataFrame]:
    """Conjunto mínimo de tablas que satisface las firmas de Step 11."""
    pv_total = pd.DataFrame(
        {
            "primera_vuelta": [
                "Iván Cepeda",
                "Abelardo de la Espriella",
                "Paloma Valencia",
                "Sergio Fajardo",
                "Claudia López",
                "NS/NR",
                "Voto en blanco",
            ],
            "valor": [37.5, 18.2, 12.0, 7.5, 4.0, 12.0, 8.8],
        }
    )
    trend = pd.DataFrame(
        {
            "primera_vuelta": ["Iván Cepeda"] * 3 + ["Paloma Valencia"] * 3,
            "fecha": pd.to_datetime(
                ["2026-02-01", "2026-03-01", "2026-04-01"] * 2,
            ),
            "valor_punto": [35.0, 36.5, 37.5, 10.5, 11.0, 12.0],
            "valor_suavizado": [35.2, 36.6, 37.4, 10.6, 11.1, 11.9],
        }
    )
    voto_region = pd.DataFrame(
        {
            "region": ["Bogotá", "Caribe", "Pacífico"],
            "Iván Cepeda": [35.0, 42.0, 48.0],
            "Paloma Valencia": [18.0, 9.0, 6.0],
            "NS/NR": [12.0, 11.0, 14.0],
        }
    )
    voto_edad = pd.DataFrame(
        {
            "edad_grupo": ["18-34", "35-54", "55+"],
            "Iván Cepeda": [45.0, 36.0, 28.0],
            "Paloma Valencia": [10.0, 13.0, 16.0],
            "NS/NR": [11.0, 12.0, 13.0],
        }
    )
    indecisos_edad = pd.DataFrame(
        {
            "edad_grupo": ["18-34", "35-54", "55+"],
            "pct": [38.0, 32.0, 30.0],
        }
    )
    indecisos_sexo = pd.DataFrame(
        {
            "sexo": ["Hombre", "Mujer"],
            "pct": [46.0, 54.0],
        }
    )
    indecisos_region = pd.DataFrame(
        {
            "region": ["Bogotá", "Caribe", "Pacífico"],
            "pct": [25.0, 35.0, 40.0],
        }
    )
    sesgo_edad = pd.DataFrame(
        {
            "edad_grupo": ["18-34", "35-54", "55+"],
            "GAD3": [1.2, -0.5, -0.7],
            "Invamer": [-0.3, 0.8, -0.5],
        }
    )
    return {
        "primera_vuelta_total": pv_total,
        "trend_primera_vuelta": trend,
        "voto_por_region": voto_region,
        "voto_por_edad": voto_edad,
        "voto_por_genero": pd.DataFrame(
            {
                "sexo": ["Hombre", "Mujer"],
                "Iván Cepeda": [38.0, 36.0],
                "Paloma Valencia": [11.0, 13.0],
                "NS/NR": [12.0, 12.0],
            }
        ),
        "indecisos_edad_grupo": indecisos_edad,
        "indecisos_sexo": indecisos_sexo,
        "indecisos_region": indecisos_region,
        "sesgo_edad": sesgo_edad,
        "sesgo_genero": sesgo_edad.rename(columns={"edad_grupo": "sexo"}),
        "voto_vs_aprobacion": pd.DataFrame(
            {
                "primera_vuelta": ["Iván Cepeda"],
                "Aprueba": [62.0],
                "Regular": [22.0],
                "Desaprueba": [12.0],
                "NS/NR": [4.0],
            }
        ),
        "genero_por_candidato_top4": pd.DataFrame(
            {
                "sexo": ["Hombre", "Mujer"],
                "Iván Cepeda": [50.0, 50.0],
                "Paloma Valencia": [55.0, 45.0],
            }
        ),
        "transfer_sv_cepeda_vs_valencia": pd.DataFrame(
            {
                "primera_vuelta": [
                    "Iván Cepeda",
                    "Iván Cepeda",
                    "Paloma Valencia",
                    "Paloma Valencia",
                ],
                "sv_cepeda_vs_valencia": [
                    "Iván Cepeda",
                    "Paloma Valencia",
                    "Paloma Valencia",
                    "Iván Cepeda",
                ],
                "valor": [95.0, 5.0, 90.0, 10.0],
            }
        ),
    }


@pytest.fixture
def df_microdatos_minimo() -> pd.DataFrame:
    """DataFrame de microdatos mínimo para chart_trasvase_derecha."""
    return pd.DataFrame(
        {
            "encuestadora": ["TestEnc"] * 4,
            "fecha": pd.to_datetime(["2026-04-01"] * 4),
            "factor": [1.0, 1.0, 1.0, 1.0],
            "primera_vuelta": [
                "Abelardo de la Espriella",
                "Abelardo de la Espriella",
                "Paloma Valencia",
                "Sergio Fajardo",
            ],
            "sv_cepeda_vs_valencia": [
                "Paloma Valencia",
                "Paloma Valencia",
                "Iván Cepeda",
                "Iván Cepeda",
            ],
            "sv_cepeda_vs_espriella": [
                "Abelardo de la Espriella",
                "Iván Cepeda",
                "Abelardo de la Espriella",
                "Abelardo de la Espriella",
            ],
        }
    )


# ════════════════════════════════════════════════════════════════════════════
#  Smoke tests — cada chart retorna Figure válida sin lanzar
# ════════════════════════════════════════════════════════════════════════════
class TestSmokeStep11:
    """Cada función chart_* devuelve una go.Figure válida."""

    def test_tendencia_temporal_devuelve_figure(self, tablas_minimas):
        fig = step11.chart_tendencia_temporal(tablas_minimas)
        assert isinstance(fig, go.Figure)

    def test_sankey_devuelve_figure(self, tablas_minimas):
        fig = step11.chart_sankey_pv_sv(
            tablas_minimas,
            tabla_key="transfer_sv_cepeda_vs_valencia",
            sv_col="sv_cepeda_vs_valencia",
            titulo="Test Sankey",
        )
        assert isinstance(fig, go.Figure)

    def test_trasvase_derecha_devuelve_figure(self, df_microdatos_minimo, tablas_minimas):
        fig = step11.chart_trasvase_derecha(df_microdatos_minimo, tablas_minimas)
        assert isinstance(fig, go.Figure)

    def test_perfil_indecisos_devuelve_figure(self, tablas_minimas):
        fig = step11.chart_perfil_indecisos(tablas_minimas)
        assert isinstance(fig, go.Figure)

    def test_stacked_bar_devuelve_figure(self, tablas_minimas):
        fig = step11.chart_stacked_bar(
            tablas_minimas,
            tabla_key="voto_por_region",
            dim_col="region",
            titulo="Test region",
        )
        assert isinstance(fig, go.Figure)

    def test_sesgo_demografico_devuelve_figure(self, tablas_minimas):
        fig = step11.chart_sesgo_demografico(
            tablas_minimas,
            tabla_key="sesgo_edad",
            titulo="Test sesgo",
        )
        assert isinstance(fig, go.Figure)

    def test_petrismo_devuelve_figure(self, tablas_minimas):
        fig = step11.chart_petrismo_cepeda(tablas_minimas)
        assert isinstance(fig, go.Figure)

    def test_composicion_genero_devuelve_figure(self, tablas_minimas):
        fig = step11.chart_composicion_genero(tablas_minimas)
        assert isinstance(fig, go.Figure)

    def test_primera_vuelta_total_devuelve_figure(self, tablas_minimas):
        fig = step11.chart_primera_vuelta_total(tablas_minimas)
        assert isinstance(fig, go.Figure)


# ════════════════════════════════════════════════════════════════════════════
#  Comportamiento en ausencia de datos — figura placeholder
# ════════════════════════════════════════════════════════════════════════════
class TestRobustezAusenciaDatos:
    """Las funciones devuelven figura placeholder cuando faltan tablas."""

    def test_tendencia_sin_tabla_devuelve_figure(self, tablas_minimas):
        sin_trend = dict(tablas_minimas)
        sin_trend["trend_primera_vuelta"] = pd.DataFrame()
        fig = step11.chart_tendencia_temporal(sin_trend)
        assert isinstance(fig, go.Figure)

    def test_sankey_sin_tabla_devuelve_figure_placeholder(self, tablas_minimas):
        fig = step11.chart_sankey_pv_sv(
            tablas_minimas,
            tabla_key="tabla_inexistente",
            sv_col="sv_x",
            titulo="Test",
        )
        assert isinstance(fig, go.Figure)

    def test_stacked_bar_sin_tabla_devuelve_figure(self, tablas_minimas):
        fig = step11.chart_stacked_bar(
            tablas_minimas,
            tabla_key="no_existe",
            dim_col="x",
            titulo="Test",
        )
        assert isinstance(fig, go.Figure)


# ════════════════════════════════════════════════════════════════════════════
#  Regresión: chart_sesgo_demografico debe aceptar el schema real del pipeline
# ════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def sesgo_edad_formato_long() -> pd.DataFrame:
    """Schema EXACTO que produce ``analysis.tables.sesgo_por_encuestadora``.

    Es formato long: una fila por (encuestadora, categoria); el wide se
    construye dentro del chart.  Si esta fixture cambia, también debe
    cambiar el código del chart.
    """
    return pd.DataFrame(
        [
            {
                "encuestadora": "GAD3",
                "variable": "edad_grupo",
                "categoria": "18-34",
                "peso_encuestadora": 25.5,
                "peso_promedio_otras": 28.0,
                "sesgo_rel_pp": -2.5,
            },
            {
                "encuestadora": "GAD3",
                "variable": "edad_grupo",
                "categoria": "35-54",
                "peso_encuestadora": 35.0,
                "peso_promedio_otras": 33.5,
                "sesgo_rel_pp": 1.5,
            },
            {
                "encuestadora": "GAD3",
                "variable": "edad_grupo",
                "categoria": "55+",
                "peso_encuestadora": 39.5,
                "peso_promedio_otras": 38.5,
                "sesgo_rel_pp": 1.0,
            },
            {
                "encuestadora": "Invamer",
                "variable": "edad_grupo",
                "categoria": "18-34",
                "peso_encuestadora": 30.0,
                "peso_promedio_otras": 27.0,
                "sesgo_rel_pp": 3.0,
            },
            {
                "encuestadora": "Invamer",
                "variable": "edad_grupo",
                "categoria": "35-54",
                "peso_encuestadora": 32.0,
                "peso_promedio_otras": 34.5,
                "sesgo_rel_pp": -2.5,
            },
            {
                "encuestadora": "Invamer",
                "variable": "edad_grupo",
                "categoria": "55+",
                "peso_encuestadora": 38.0,
                "peso_promedio_otras": 38.5,
                "sesgo_rel_pp": -0.5,
            },
        ]
    )


class TestSesgoDemograficoSchemaReal:
    """Regresión del bug ``could not convert string to float: 'edad_grupo'``.

    El refactor original asumía formato wide; el pipeline real produce long.
    """

    def test_acepta_schema_long_del_pipeline(self, sesgo_edad_formato_long):
        fig = step11.chart_sesgo_demografico(
            {"sesgo_edad": sesgo_edad_formato_long},
            tabla_key="sesgo_edad",
            titulo="Sesgo edad",
            subtitle="+pp = sobreestima",
        )
        assert isinstance(fig, go.Figure)
        # Una traza por encuestadora (sin contar la hline horizontal)
        n_bar_traces = sum(1 for tr in fig.data if tr.type == "bar")
        assert n_bar_traces == 2  # GAD3 + Invamer

    def test_acepta_schema_wide_para_tests(self):
        """Mantiene compatibility con el formato wide preparado a mano."""
        wide = pd.DataFrame(
            {
                "edad_grupo": ["18-34", "35-54", "55+"],
                "GAD3": [1.2, -0.5, -0.7],
                "Invamer": [-0.3, 0.8, -0.5],
            }
        )
        fig = step11.chart_sesgo_demografico(
            {"sesgo_edad": wide},
            tabla_key="sesgo_edad",
            titulo="Test wide",
        )
        assert isinstance(fig, go.Figure)
        n_bar_traces = sum(1 for tr in fig.data if tr.type == "bar")
        assert n_bar_traces == 2

    def test_tabla_vacia_devuelve_placeholder(self):
        fig = step11.chart_sesgo_demografico(
            {"sesgo_edad": pd.DataFrame()},
            tabla_key="sesgo_edad",
            titulo="Test",
        )
        assert isinstance(fig, go.Figure)

    def test_long_con_categoria_repetida_se_promedia(self):
        """Si por error vienen filas duplicadas, ``pivot_table`` con
        ``aggfunc=mean`` evita el ``ValueError`` de pivot tradicional."""
        df_dup = pd.DataFrame(
            [
                {"encuestadora": "GAD3", "categoria": "18-34", "sesgo_rel_pp": -2.5},
                {"encuestadora": "GAD3", "categoria": "18-34", "sesgo_rel_pp": -1.5},
                {"encuestadora": "GAD3", "categoria": "35-54", "sesgo_rel_pp": 1.0},
            ]
        )
        fig = step11.chart_sesgo_demografico(
            {"sesgo_edad": df_dup},
            tabla_key="sesgo_edad",
            titulo="dup",
        )
        assert isinstance(fig, go.Figure)


# ════════════════════════════════════════════════════════════════════════════
#  Regresión: chart_composicion_genero debe aceptar el pivot real del pipeline
# ════════════════════════════════════════════════════════════════════════════
class TestComposicionGeneroSchemaReal:
    """El pipeline produce ``[primera_vuelta, Hombre, Mujer]``; el chart
    original asumía el pivot transpuesto."""

    def test_acepta_schema_real_filas_candidato(self):
        """Schema producido por ``tabla_genero_por_candidato_top4``."""
        t_gc = pd.DataFrame(
            {
                "primera_vuelta": ["Iván Cepeda", "Espriella", "Valencia", "Fajardo"],
                "Hombre": [52.0, 65.0, 38.0, 48.0],
                "Mujer": [48.0, 35.0, 62.0, 52.0],
            }
        )
        fig = step11.chart_composicion_genero({"genero_por_candidato_top4": t_gc})
        assert isinstance(fig, go.Figure)
        # 2 trazas: Hombre + Mujer
        names = {tr.name for tr in fig.data}
        assert names == {"Hombre", "Mujer"}
        # X = candidatos (no géneros)
        for tr in fig.data:
            assert "Iván Cepeda" in tr.x or "Cepeda" in tr.x

    def test_acepta_schema_transpuesto_compatibility(self):
        """Schema legacy ``[sexo, candA, candB, ...]`` también funciona."""
        t_gc = pd.DataFrame(
            {
                "sexo": ["Hombre", "Mujer"],
                "Cepeda": [52.0, 48.0],
                "Espriella": [65.0, 35.0],
            }
        )
        fig = step11.chart_composicion_genero({"genero_por_candidato_top4": t_gc})
        assert isinstance(fig, go.Figure)
        names = {tr.name for tr in fig.data}
        assert names == {"Hombre", "Mujer"}

    def test_tabla_vacia_devuelve_placeholder(self):
        fig = step11.chart_composicion_genero(
            {"genero_por_candidato_top4": pd.DataFrame()},
        )
        assert isinstance(fig, go.Figure)

    def test_solo_hombres_no_lanza_error(self):
        """Tabla con solo género Hombre (caso de borde)."""
        t_gc = pd.DataFrame(
            {
                "primera_vuelta": ["A", "B"],
                "Hombre": [50.0, 60.0],
            }
        )
        fig = step11.chart_composicion_genero({"genero_por_candidato_top4": t_gc})
        assert isinstance(fig, go.Figure)
        names = {tr.name for tr in fig.data}
        assert names == {"Hombre"}


# ════════════════════════════════════════════════════════════════════════════
#  Regresión v0.2.5: chart_stacked_bar — toggle FUNCIONAL + consolidación
# ════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def tablas_stacked_minoritarios() -> dict:
    """Tabla con 15+ candidatos donde varios son < 3% (minoritarios)."""
    voto = pd.DataFrame(
        {
            "edad_grupo": ["18-34", "35-54", "55+"],
            "Iván Cepeda": [33.0, 27.0, 22.0],
            "Abelardo de la Espriella": [13.0, 21.0, 24.0],
            "Paloma Valencia": [10.0, 12.0, 16.0],
            "Sergio Fajardo": [4.0, 5.0, 6.0],
            "Santiago Botero": [1.2, 1.5, 1.8],  # minoritario
            "Carlos Caicedo": [0.5, 0.6, 0.8],  # minoritario
            "Mauricio Lizcano": [0.3, 0.4, 0.5],  # minoritario
            "NS/NR": [10.0, 11.0, 9.0],
            "No votaría": [7.0, 7.0, 8.0],
            "Voto en blanco": [4.0, 5.0, 4.0],
            "Ninguno": [6.0, 3.0, 2.0],
            "No sé": [4.0, 1.5, 3.0],
        }
    )
    pvt = pd.DataFrame(
        {
            "primera_vuelta": list(voto.columns[1:]),
            "valor": [voto[c].mean() for c in voto.columns[1:]],
        }
    )
    return {"voto_por_edad": voto, "primera_vuelta_total": pvt}


class TestStackedBarToggleFuncional:
    """v0.2.5: los botones Con/Sin indecisos DEBEN alternar datos, no solo título."""

    def test_metodos_de_botones_son_update_no_relayout(self, tablas_stacked_minoritarios):
        fig = step11.chart_stacked_bar(
            tablas_stacked_minoritarios,
            tabla_key="voto_por_edad",
            dim_col="edad_grupo",
            titulo="Test",
        )
        um = fig.layout.updatemenus
        assert len(um) == 1, "Debería haber 1 menú de toggle"
        for btn in um[0].buttons:
            assert btn.method == "update", (
                f"Botón {btn.label!r} usa method={btn.method!r}, debe ser 'update' "
                "(antes era 'relayout', que solo cambiaba el título → bug funcional)."
            )

    def test_botones_alternan_visibilidad_de_trazas(self, tablas_stacked_minoritarios):
        """Cada botón debe cambiar `visible` con un patrón de Trues/Falses."""
        fig = step11.chart_stacked_bar(
            tablas_stacked_minoritarios,
            tabla_key="voto_por_edad",
            dim_col="edad_grupo",
            titulo="Test",
        )
        btn_con, btn_sin = fig.layout.updatemenus[0].buttons
        vis_con = btn_con.args[0]["visible"]
        vis_sin = btn_sin.args[0]["visible"]
        # Listas de booleans, mismo tamaño
        assert len(vis_con) == len(vis_sin) == len(fig.data)
        # Una visible donde la otra está oculta y viceversa (perfectamente complementarios)
        for v1, v2 in zip(vis_con, vis_sin, strict=True):
            assert v1 != v2, "Los dos botones no son complementarios"

    def test_consolida_candidatos_minoritarios(self, tablas_stacked_minoritarios):
        from encuestas_lib.viz.charts.step11 import _OTROS_MINOR_LABEL

        fig = step11.chart_stacked_bar(
            tablas_stacked_minoritarios,
            tabla_key="voto_por_edad",
            dim_col="edad_grupo",
            titulo="Test",
        )
        nombres = {t.name for t in fig.data}
        assert _OTROS_MINOR_LABEL in nombres
        # Los candidatos con max < 3% NO deben aparecer sueltos
        for cand in ("Santiago Botero", "Carlos Caicedo", "Mauricio Lizcano"):
            assert cand not in nombres, f"{cand!r} aparece suelto (debería consolidarse)"

    def test_consolidacion_desactivada_con_min_pct_visible_0(self, tablas_stacked_minoritarios):
        """min_pct_visible=0 desactiva la consolidación (modo original)."""
        from encuestas_lib.viz.charts.step11 import _OTROS_MINOR_LABEL

        fig = step11.chart_stacked_bar(
            tablas_stacked_minoritarios,
            tabla_key="voto_por_edad",
            dim_col="edad_grupo",
            titulo="Test",
            min_pct_visible=0,
        )
        nombres = {t.name for t in fig.data}
        assert _OTROS_MINOR_LABEL not in nombres
        # Todos los minoritarios aparecen sueltos
        for cand in ("Santiago Botero", "Carlos Caicedo", "Mauricio Lizcano"):
            assert cand in nombres

    def test_leyenda_con_margen_inferior_amplio(self, tablas_stacked_minoritarios):
        """La leyenda debe quedar FUERA del plot area (margin.b >= 150)."""
        fig = step11.chart_stacked_bar(
            tablas_stacked_minoritarios,
            tabla_key="voto_por_edad",
            dim_col="edad_grupo",
            titulo="Test",
        )
        assert fig.layout.margin.b >= 150, (
            f"margin.b={fig.layout.margin.b} insuficiente para acomodar leyenda; "
            "esto causa que la leyenda se meta encima de las barras."
        )
        # Leyenda con y negativo (debajo del plot)
        assert fig.layout.legend.y < 0, (
            f"legend.y={fig.layout.legend.y}, debe ser negativo para quedar abajo del plot"
        )
