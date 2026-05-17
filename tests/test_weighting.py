"""Tests de estrategias de ponderación entre encuestas."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from encuestas_lib.analysis.weighting import (
    resolve_weights,
    weights_inverse_recency_size,
    weights_recency_decay,
    weights_sample_size,
    weights_uniform,
)
from encuestas_lib.config import SurveyEntry, WeightingConfig


@pytest.fixture
def surveys():
    return [
        SurveyEntry(
            id="a",
            encuestadora="Atlas",
            fecha=date(2026, 4, 25),
            reader="atlas",
            path=Path("a.csv"),
            n_muestra=2000,
        ),
        SurveyEntry(
            id="b",
            encuestadora="Invamer",
            fecha=date(2026, 4, 11),
            reader="invamer",
            path=Path("b.csv"),
            n_muestra=1200,
        ),
        SurveyEntry(
            id="c",
            encuestadora="CNC",
            fecha=date(2026, 1, 15),
            reader="cnc_sav",
            path=Path("c.csv"),
            n_muestra=800,
        ),
    ]


class TestWeightsUniform:
    def test_todas_pesan_uno(self, surveys):
        w = weights_uniform(surveys)
        assert len(w) == 3
        assert all(v == 1.0 for v in w.values())


class TestWeightsSampleSize:
    def test_proporcional_a_n(self, surveys):
        w = weights_sample_size(surveys)
        assert w[("Atlas", "2026-04-25")] == 2000.0
        assert w[("Invamer", "2026-04-11")] == 1200.0
        assert w[("CNC", "2026-01-15")] == 800.0


class TestWeightsRecencyDecay:
    def test_mas_reciente_pesa_uno(self, surveys):
        w = weights_recency_decay(surveys, half_life_days=21)
        # La encuesta más reciente (Atlas 2026-04-25) tiene peso = 1.0
        assert w[("Atlas", "2026-04-25")] == pytest.approx(1.0, abs=1e-9)

    def test_decae_con_distancia_temporal(self, surveys):
        w = weights_recency_decay(surveys, half_life_days=21)
        # Invamer es 14 días antes que Atlas → peso ≈ 0.5^(14/21) ≈ 0.630
        # CNC es 100 días antes → peso mucho menor
        assert w[("Atlas", "2026-04-25")] > w[("Invamer", "2026-04-11")]
        assert w[("Invamer", "2026-04-11")] > w[("CNC", "2026-01-15")]

    def test_half_life_correcto(self, surveys):
        # Con half_life=14 días, una encuesta de 14 días atrás debería tener peso 0.5
        w = weights_recency_decay(surveys, half_life_days=14)
        # Invamer: 14 días antes que Atlas
        assert w[("Invamer", "2026-04-11")] == pytest.approx(0.5, abs=0.01)


class TestWeightsInverseRecencySize:
    def test_combina_n_y_decay(self, surveys):
        w = weights_inverse_recency_size(surveys, half_life_days=21)
        # Atlas: 2000 * 1.0 = 2000
        assert w[("Atlas", "2026-04-25")] == pytest.approx(2000.0, abs=1.0)
        # Invamer: 1200 * decay(14d, hl=21) ≈ 1200 * 0.630 ≈ 756
        assert 700 < w[("Invamer", "2026-04-11")] < 820


class TestResolveWeights:
    def test_estrategia_uniform(self, surveys):
        config = WeightingConfig(active_strategy="uniform", params={}, manual_weights={})
        w = resolve_weights(config, surveys)
        assert all(v == 1.0 for v in w.values())

    def test_estrategia_sample_size(self, surveys):
        config = WeightingConfig(active_strategy="sample_size", params={}, manual_weights={})
        w = resolve_weights(config, surveys)
        assert w[("Atlas", "2026-04-25")] == 2000.0

    def test_estrategia_inverse_recency_size_con_params(self, surveys):
        config = WeightingConfig(
            active_strategy="inverse_recency_size",
            params={"half_life_days": 21},
            manual_weights={},
        )
        w = resolve_weights(config, surveys)
        assert len(w) == 3
        assert w[("Atlas", "2026-04-25")] > w[("CNC", "2026-01-15")]

    def test_estrategia_desconocida_lanza(self, surveys):
        config = WeightingConfig(active_strategy="inexistente", params={}, manual_weights={})
        with pytest.raises(ValueError, match="desconocida"):
            resolve_weights(config, surveys)

    def test_estrategia_manual(self, surveys):
        config = WeightingConfig(
            active_strategy="manual",
            params={},
            manual_weights={
                ("Atlas", "2026-04-25"): 5.0,
                ("Invamer", "2026-04-11"): 3.0,
                ("CNC", "2026-01-15"): 1.0,
            },
        )
        w = resolve_weights(config, surveys)
        assert w[("Atlas", "2026-04-25")] == 5.0
        assert w[("Invamer", "2026-04-11")] == 3.0
