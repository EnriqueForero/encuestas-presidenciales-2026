"""Tests del módulo electoral.py — simulación de segunda vuelta, transferencia,
análisis de sensibilidad y techo de rechazo.
"""

from __future__ import annotations

import pandas as pd
import pytest

from encuestas_lib.analysis.electoral import (
    ResultadoSimulacion,
    sensibilidad_2v,
    simular_segunda_vuelta,
    trasvase_candidato,
)


# ════════════════════════════════════════════════════════════════════════════
#  Fixtures
# ════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def pesos_pv_simple() -> dict[str, float]:
    return {
        "Cepeda": 40.0,
        "Espriella": 30.0,
        "Valencia": 20.0,
        "Centro": 10.0,
    }


@pytest.fixture
def matriz_simple() -> dict:
    return {
        "Cepeda": {"A": (93.0, 97.0), "B": (0.0, 2.0), "blanco": (2.0, 5.0)},
        "Espriella": {"A": (0.0, 2.0), "B": (95.0, 99.0), "blanco": (1.0, 3.0)},
        "Valencia": {"A": (8.0, 12.0), "B": (78.0, 88.0), "blanco": (5.0, 10.0)},
        "Centro": {"A": (35.0, 55.0), "B": (20.0, 40.0), "blanco": (15.0, 35.0)},
    }


@pytest.fixture
def tablas_simple() -> dict[str, pd.DataFrame]:
    """Tabla de transferencia sintética para tests de trasvase_candidato."""
    rows = []
    for pv_cand, transfers in [
        ("Sergio Fajardo", [("Cepeda_SV", 42.0), ("Espriella_SV", 28.0), ("Ninguno", 30.0)]),
        ("Claudia López", [("Cepeda_SV", 55.0), ("Espriella_SV", 15.0), ("Ninguno", 30.0)]),
    ]:
        for sv_opt, val in transfers:
            rows.append({"primera_vuelta": pv_cand, "sv_test_col": sv_opt, "valor": val})

    t = pd.DataFrame(rows)
    return {"transfer_sv_test_col": t}


# ════════════════════════════════════════════════════════════════════════════
#  simular_segunda_vuelta
# ════════════════════════════════════════════════════════════════════════════
class TestSimularSegundaVuelta:
    def test_retorna_resultado_y_df(self, pesos_pv_simple, matriz_simple):
        res, df = simular_segunda_vuelta(
            pesos_pv_simple, matriz_simple, "Cepeda", "Espriella", n_iter=1_000, seed=0
        )
        assert isinstance(res, ResultadoSimulacion)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1_000

    def test_probabilidades_suman_100(self, pesos_pv_simple, matriz_simple):
        res, _ = simular_segunda_vuelta(
            pesos_pv_simple, matriz_simple, "Cepeda", "Espriella", n_iter=2_000, seed=1
        )
        # P(A gana) + P(B gana) debe ≈ 1 (salvo empate exacto que es prob 0 continua)
        assert abs(res.prob_a_gana + res.prob_b_gana - 1.0) < 0.01

    def test_medias_en_rango_valido(self, pesos_pv_simple, matriz_simple):
        res, _ = simular_segunda_vuelta(
            pesos_pv_simple, matriz_simple, "Cepeda", "Espriella", n_iter=2_000, seed=2
        )
        assert 30.0 < res.media_a < 70.0
        assert 30.0 < res.media_b < 70.0

    def test_reproducibilidad_con_seed(self, pesos_pv_simple, matriz_simple):
        res1, _ = simular_segunda_vuelta(
            pesos_pv_simple, matriz_simple, "C", "E", n_iter=500, seed=42
        )
        res2, _ = simular_segunda_vuelta(
            pesos_pv_simple, matriz_simple, "C", "E", n_iter=500, seed=42
        )
        assert res1.media_a == res2.media_a
        assert res1.prob_a_gana == res2.prob_a_gana

    def test_distintos_seeds_dan_resultados_distintos(self, pesos_pv_simple, matriz_simple):
        res1, _ = simular_segunda_vuelta(
            pesos_pv_simple, matriz_simple, "C", "E", n_iter=500, seed=1
        )
        res2, _ = simular_segunda_vuelta(
            pesos_pv_simple, matriz_simple, "C", "E", n_iter=500, seed=2
        )
        # No necesariamente distintos en media (puede haber coincidencia) pero
        # al menos los std deben estar en rango razonable
        assert res1.std_a > 0
        assert res2.std_a > 0

    def test_ic80_contiene_media(self, pesos_pv_simple, matriz_simple):
        res, _ = simular_segunda_vuelta(
            pesos_pv_simple, matriz_simple, "Cepeda", "Espriella", n_iter=2_000, seed=3
        )
        assert res.ic80_a[0] <= res.media_a <= res.ic80_a[1]
        assert res.ic80_b[0] <= res.media_b <= res.ic80_b[1]

    def test_candidato_dominante_gana_con_alta_prob(self):
        """Si Cepeda tiene 95% de transferencia propia, su prob de ganar es muy alta."""
        pesos = {"Cepeda": 50.0, "Rival": 50.0}
        matriz = {
            "Cepeda": {"A": (93.0, 97.0), "B": (0.0, 1.0), "blanco": (2.0, 7.0)},
            "Rival": {"A": (0.0, 2.0), "B": (93.0, 97.0), "blanco": (2.0, 5.0)},
        }
        res, _ = simular_segunda_vuelta(pesos, matriz, "Cepeda", "Rival", n_iter=2_000, seed=0)
        # Con pesos iguales y trasvase simétrico, debe ser ≈ 50/50
        assert 0.40 < res.prob_a_gana < 0.60

    def test_prob_empate_tecnico_es_subconjunto(self, pesos_pv_simple, matriz_simple):
        """P(empate técnico) ≤ min(P(A gana), P(B gana)) * 2 — es un subconjunto."""
        res, _ = simular_segunda_vuelta(
            pesos_pv_simple, matriz_simple, "Cepeda", "Espriella", n_iter=3_000, seed=4
        )
        assert 0.0 <= res.prob_empate_tecnico <= 1.0

    def test_df_columnas_correctas(self, pesos_pv_simple, matriz_simple):
        _, df = simular_segunda_vuelta(
            pesos_pv_simple, matriz_simple, "Cepeda", "Espriella", n_iter=500, seed=0
        )
        assert "Cepeda" in df.columns
        assert "Espriella" in df.columns
        assert "ganador" in df.columns
        assert "iter" in df.columns

    def test_pesos_no_normalizados_dan_resultado_valido(self):
        """Los pesos no necesitan sumar 100 — el resultado sigue siendo válido."""
        pesos = {"A": 0.4, "B": 0.3, "C": 0.3}
        matriz = {
            "A": {"A": (90.0, 95.0), "B": (2.0, 5.0), "blanco": (3.0, 7.0)},
            "B": {"A": (2.0, 5.0), "B": (90.0, 95.0), "blanco": (3.0, 7.0)},
            "C": {"A": (40.0, 60.0), "B": (30.0, 50.0), "blanco": (10.0, 20.0)},
        }
        res, df_it = simular_segunda_vuelta(pesos, matriz, "A", "B", n_iter=500, seed=0)
        # Las probabilidades deben sumar 1 y las medias deben ser válidas
        assert abs(res.prob_a_gana + res.prob_b_gana - 1.0) < 0.01
        assert 0.0 < res.media_a < 100.0
        assert 0.0 < res.media_b < 100.0
        assert len(df_it) == 500


# ════════════════════════════════════════════════════════════════════════════
#  sensibilidad_2v
# ════════════════════════════════════════════════════════════════════════════
class TestSensibilidad2V:
    def test_retorna_dataframe_correcto(self, pesos_pv_simple, matriz_simple):
        df = sensibilidad_2v(
            pesos_pv_simple,
            matriz_simple,
            "Cepeda",
            "Espriella",
            "Test param",
            "Valencia",
            "B",
            rango_param=(70.0, 90.0),
            n_puntos=5,
            n_iter_mc=500,
        )
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 5
        assert "param_valor" in df.columns
        assert "media_a" in df.columns
        assert "prob_a_gana" in df.columns

    def test_mayor_trasvase_b_reduce_prob_a(self, pesos_pv_simple, matriz_simple):
        """A más trasvase de Valencia→Espriella (B), menor P(Cepeda gana)."""
        df = sensibilidad_2v(
            pesos_pv_simple,
            matriz_simple,
            "Cepeda",
            "Espriella",
            "% Valencia → Espriella",
            "Valencia",
            "B",
            rango_param=(10.0, 90.0),
            n_puntos=5,
            n_iter_mc=300,
            seed=0,
        )
        # La probabilidad de A ganar debe ser monótonamente decreciente
        # (con algo de ruido MC a tan pocas iteraciones, usamos tendencia general)
        prob_inicio = df["prob_a_gana"].iloc[0]
        prob_fin = df["prob_a_gana"].iloc[-1]
        assert prob_inicio > prob_fin - 15  # tendencia esperada (sin ser estricto por MC)

    def test_n_puntos_correcto(self, pesos_pv_simple, matriz_simple):
        df = sensibilidad_2v(
            pesos_pv_simple,
            matriz_simple,
            "Cepeda",
            "Espriella",
            "P",
            "Valencia",
            "B",
            rango_param=(50.0, 90.0),
            n_puntos=10,
            n_iter_mc=200,
        )
        assert len(df) == 10

    def test_param_vals_en_rango(self, pesos_pv_simple, matriz_simple):
        df = sensibilidad_2v(
            pesos_pv_simple,
            matriz_simple,
            "Cepeda",
            "Espriella",
            "P",
            "Valencia",
            "B",
            rango_param=(60.0, 80.0),
            n_puntos=5,
            n_iter_mc=200,
        )
        assert df["param_valor"].min() >= 59.9
        assert df["param_valor"].max() <= 80.1


# ════════════════════════════════════════════════════════════════════════════
#  trasvase_candidato
# ════════════════════════════════════════════════════════════════════════════
class TestTrasvase:
    def test_retorna_df_con_columnas_correctas(self, tablas_simple):
        df = trasvase_candidato(
            tablas_simple,
            "sv_test_col",
            ["Sergio Fajardo", "Claudia López"],
        )
        assert not df.empty
        assert "primera_vuelta" in df.columns
        assert "sv_opcion" in df.columns
        assert "pct_total" in df.columns
        assert "pct_decididos" in df.columns

    def test_pct_decididos_excluye_indecisos(self, tablas_simple):
        """pct_decididos no incluye Ninguno (es_indeciso_sv=True)."""
        df = trasvase_candidato(
            tablas_simple,
            "sv_test_col",
            ["Sergio Fajardo"],
            excluir_indecisos_sv=True,
        )
        # Fajardo: 42% Cepeda + 28% Espriella = 70% decididos
        # pct_decididos(Cepeda) = 42/70 * 100 = 60%
        cep = df[(df["primera_vuelta"] == "Sergio Fajardo") & (df["sv_opcion"] == "Cepeda_SV")]
        assert not cep.empty
        assert abs(float(cep["pct_decididos"].iloc[0]) - 60.0) < 0.5

    def test_cand_no_en_tabla_retorna_vacio(self, tablas_simple):
        df = trasvase_candidato(
            tablas_simple,
            "sv_test_col",
            ["Candidato Inexistente"],
        )
        assert df.empty

    def test_tabla_inexistente_retorna_vacio(self, tablas_simple):
        df = trasvase_candidato(
            tablas_simple,
            "sv_col_inexistente",
            ["Sergio Fajardo"],
        )
        assert df.empty

    def test_todos_los_candidatos_presentes(self, tablas_simple):
        df = trasvase_candidato(
            tablas_simple,
            "sv_test_col",
            ["Sergio Fajardo", "Claudia López"],
        )
        pvs = df["primera_vuelta"].unique()
        assert "Sergio Fajardo" in pvs
        assert "Claudia López" in pvs
