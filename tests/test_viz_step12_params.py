"""Tests de los parámetros centralizados y constructores de ``step12``.

Cubre:
    - Validación de :class:`MonteCarloParams` (rangos válidos).
    - Validación de :class:`SwingFactor` (rangos y destino).
    - Coherencia de constantes ``*_DOC`` (presencia, tipos, no-vacías).
    - Construcción de DataFrames runtime (``construir_comparativo_polymarket``,
      ``construir_escenarios_consolidados``) con resultados MC mockeados.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from encuestas_lib.viz.charts.step12 import (
    CANDS_CENTRO_DOC,
    ESCENARIOS_DOC,
    MATRIZ_A,
    MATRIZ_B,
    MC_PARAMS_DOC,
    PESOS_PV_DOC,
    POLYMARKET_SNAPSHOT_DOC,
    SWING_FACTORS_DOC,
    TECHO_RECHAZO_DOC,
    MonteCarloParams,
    MonteCarloResult,
    SwingFactor,
    construir_comparativo_polymarket,
    construir_escenarios_consolidados,
)


# ════════════════════════════════════════════════════════════════════════════
#  Validación de MonteCarloParams
# ════════════════════════════════════════════════════════════════════════════
class TestMonteCarloParams:
    """Dataclass que parametriza la simulación MC."""

    def test_defaults_son_doc_forense(self):
        assert MC_PARAMS_DOC.n_iter == 20_000
        assert MC_PARAMS_DOC.seed == 42

    def test_n_iter_minimo_lanza_valueerror(self):
        with pytest.raises(ValueError, match="n_iter"):
            MonteCarloParams(n_iter=500)

    def test_seed_negativa_lanza_valueerror(self):
        with pytest.raises(ValueError, match="seed"):
            MonteCarloParams(seed=-1)

    def test_es_frozen(self):
        with pytest.raises(FrozenInstanceError):
            MC_PARAMS_DOC.n_iter = 50_000  # type: ignore[misc]


# ════════════════════════════════════════════════════════════════════════════
#  Validación de SwingFactor
# ════════════════════════════════════════════════════════════════════════════
class TestSwingFactor:
    """Dataclass que parametriza un swing factor."""

    def test_3_swing_factors_canonicos(self):
        assert len(SWING_FACTORS_DOC) == 3
        nombres = [sf.nombre for sf in SWING_FACTORS_DOC]
        assert any("Valencia" in n for n in nombres)
        assert any("Fajardo" in n for n in nombres)
        assert any("Blanco" in n for n in nombres)

    def test_destino_invalido_lanza_valueerror(self):
        with pytest.raises(ValueError, match="destino"):
            SwingFactor(
                nombre="x",
                pv_cand="y",
                destino="invalid",
                rango_min=0,
                rango_max=100,
            )

    def test_rango_invertido_lanza_valueerror(self):
        with pytest.raises(ValueError, match="Rango"):
            SwingFactor(
                nombre="x",
                pv_cand="y",
                destino="A",
                rango_min=80,
                rango_max=20,
            )

    def test_rango_fuera_de_0_100_lanza_valueerror(self):
        with pytest.raises(ValueError, match="Rango"):
            SwingFactor(
                nombre="x",
                pv_cand="y",
                destino="A",
                rango_min=-1,
                rango_max=50,
            )

    def test_todos_los_swing_factors_tienen_destinos_validos(self):
        for sf in SWING_FACTORS_DOC:
            assert sf.destino in {"A", "B", "blanco"}
            assert 0 <= sf.rango_min < sf.rango_max <= 100
            assert sf.n_puntos > 0
            assert sf.n_iter_mc >= 1_000


# ════════════════════════════════════════════════════════════════════════════
#  Coherencia de constantes — ``*_DOC``
# ════════════════════════════════════════════════════════════════════════════
class TestConstantesDocForense:
    """Las constantes están presentes, no vacías y con tipos correctos."""

    def test_pesos_pv_doc_suman_100(self):
        assert abs(sum(PESOS_PV_DOC.values()) - 100.0) < 0.01

    def test_pesos_pv_doc_tiene_cepeda(self):
        assert "Iván Cepeda" in PESOS_PV_DOC

    def test_matriz_a_y_b_misma_estructura(self):
        assert set(MATRIZ_A.keys()) == set(MATRIZ_B.keys())
        for pv_cand, transferencias in MATRIZ_A.items():
            assert set(transferencias.keys()) == {"A", "B", "blanco"}, pv_cand

    def test_techo_rechazo_doc_rangos_validos(self):
        for cand, (lo, hi) in TECHO_RECHAZO_DOC.items():
            assert 0 <= lo <= hi <= 100, cand

    def test_cands_centro_doc_es_tupla_no_vacia(self):
        assert isinstance(CANDS_CENTRO_DOC, tuple)
        assert len(CANDS_CENTRO_DOC) >= 2

    def test_escenarios_doc_tiene_7_escenarios(self):
        assert len(ESCENARIOS_DOC) == 7
        tipos = {e["tipo"] for e in ESCENARIOS_DOC}
        assert tipos == {"1V", "2V", "Incertidumbre"}

    def test_polymarket_snapshot_claves_esperadas(self):
        # Cada bloque (Mercado, Encuestas, Modelo, Consolidado) requiere
        # ciertas claves para construir el DataFrame comparativo
        for prefix in ("polymarket", "encuestas", "modelo", "consolidado"):
            keys = [k for k in POLYMARKET_SNAPSHOT_DOC if k.startswith(prefix)]
            assert len(keys) > 0, f"Faltan claves con prefix={prefix!r}"


# ════════════════════════════════════════════════════════════════════════════
#  Constructores de DataFrames runtime
# ════════════════════════════════════════════════════════════════════════════
def _mock_resultado_mc(
    prob_a_gana: float = 0.55,
    prob_b_gana: float = 0.40,
    prob_empate: float = 0.05,
) -> MonteCarloResult:
    """Mock ligero de un resultado MC para tests."""
    return MonteCarloResult(
        media_a=51.0,
        media_b=49.0,
        prob_a_gana=prob_a_gana,
        prob_b_gana=prob_b_gana,
        prob_empate_tecnico=prob_empate,
        candidato_a="Iván Cepeda",
        candidato_b="Abelardo de la Espriella",
    )


class TestConstruirComparativoPolymarket:
    """``construir_comparativo_polymarket`` retorna el DataFrame esperado."""

    def test_devuelve_4_filas(self):
        res_a = _mock_resultado_mc()
        res_b = _mock_resultado_mc(prob_a_gana=0.45, prob_b_gana=0.50)
        df = construir_comparativo_polymarket(res_a, res_b)
        assert len(df) == 4
        assert list(df["tipo"]) == ["Mercado", "Encuestas", "Modelo", "Consolidado"]

    def test_columnas_esperadas(self):
        res_a = _mock_resultado_mc()
        res_b = _mock_resultado_mc()
        df = construir_comparativo_polymarket(res_a, res_b)
        for col in [
            "fuente",
            "tipo",
            "cepeda_gana_pv1",
            "espriella_2do",
            "cepeda_presidencia",
            "espriella_presidencia",
            "valencia_presidencia",
        ]:
            assert col in df.columns

    def test_fila_modelo_usa_resultados_mc(self):
        res_a = _mock_resultado_mc(prob_a_gana=0.70, prob_b_gana=0.20)
        res_b = _mock_resultado_mc(prob_b_gana=0.30)
        df = construir_comparativo_polymarket(res_a, res_b)
        modelo = df[df["tipo"] == "Modelo"].iloc[0]
        assert modelo["cepeda_presidencia"] == pytest.approx(70.0)
        assert modelo["espriella_presidencia"] == pytest.approx(20.0)

    def test_snapshot_personalizado_se_respeta(self):
        res_a = _mock_resultado_mc()
        res_b = _mock_resultado_mc()
        snap_custom = dict(POLYMARKET_SNAPSHOT_DOC)
        snap_custom["polymarket_cepeda_presidencia"] = 99.0
        df = construir_comparativo_polymarket(res_a, res_b, snapshot=snap_custom)
        mercado = df[df["tipo"] == "Mercado"].iloc[0]
        assert mercado["cepeda_presidencia"] == 99.0


class TestConstruirEscenariosConsolidados:
    """``construir_escenarios_consolidados`` combina doc + MC."""

    def test_devuelve_7_filas(self):
        res_a = _mock_resultado_mc()
        res_b = _mock_resultado_mc()
        df = construir_escenarios_consolidados(res_a, res_b)
        assert len(df) == 7

    def test_columnas_esperadas(self):
        res_a = _mock_resultado_mc()
        res_b = _mock_resultado_mc()
        df = construir_escenarios_consolidados(res_a, res_b)
        assert set(df.columns) == {"escenario", "prob_doc", "prob_modelo", "tipo"}

    def test_escenario_2v_usa_prob_a_gana_de_res_a(self):
        res_a = _mock_resultado_mc(prob_a_gana=0.85)
        res_b = _mock_resultado_mc()
        df = construir_escenarios_consolidados(res_a, res_b)
        cepeda_gana_a = df[df["escenario"] == "2V: Cepeda gana (esc. A)"].iloc[0]
        assert cepeda_gana_a["prob_modelo"] == pytest.approx(85.0)

    def test_columna_tipo_solo_tiene_categorias_validas(self):
        res_a = _mock_resultado_mc()
        res_b = _mock_resultado_mc()
        df = construir_escenarios_consolidados(res_a, res_b)
        assert set(df["tipo"]).issubset({"1V", "2V", "Incertidumbre"})
