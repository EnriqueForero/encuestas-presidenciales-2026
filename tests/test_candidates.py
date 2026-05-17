"""Tests de armonización de candidatos."""

from __future__ import annotations

import pytest

from encuestas_lib.harmonization.candidates import (
    build_harmonizer,
    normalize_text,
)


# ════════════════════════════════════════════════════════════════════════════
#  normalize_text
# ════════════════════════════════════════════════════════════════════════════
class TestNormalizeText:
    def test_basico_lowercase(self):
        assert normalize_text("Iván Cepeda") == "ivan cepeda"

    def test_espacios_y_caps(self):
        assert normalize_text("  IVÁN   CEPEDA  ") == "ivan cepeda"

    def test_none_y_vacios(self):
        assert normalize_text(None) == ""
        assert normalize_text("") == ""
        assert normalize_text("nan") == ""
        assert normalize_text("None") == ""

    def test_tildes_y_enie(self):
        assert normalize_text("Peñalosa") == "penalosa"
        assert normalize_text("Cárdenas") == "cardenas"


# ════════════════════════════════════════════════════════════════════════════
#  CandidateHarmonizer
# ════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def harmonizer():
    candidates_raw = [
        {
            "canonical": "Iván Cepeda",
            "key": "cepeda",
            "status": "vigente",
            "bloque": "izquierda",
            "aliases": ["ivan cepeda", "cepeda"],
        },
        {
            "canonical": "Abelardo de la Espriella",
            "key": "espriella",
            "status": "vigente",
            "bloque": "derecha",
            "aliases": ["abelardo de la espriella", "espriella", "de la espriella"],
        },
        {
            "canonical": "Sergio Fajardo",
            "key": "fajardo",
            "status": "vigente",
            "bloque": "centro",
            "aliases": ["fajardo", "sergio fajardo"],
        },
    ]
    special = [
        {"canonical": "NS/NR", "key": "ns_nr", "aliases": ["ns/nr", "no sabe", "ns nr"]},
        {"canonical": "Blanco", "key": "blanco", "aliases": ["blanco", "voto en blanco"]},
    ]
    return build_harmonizer(candidates_raw, special)


class TestCandidateHarmonizer:
    def test_match_canonical_directo(self, harmonizer):
        assert harmonizer.harmonize("Iván Cepeda") == "Iván Cepeda"

    def test_match_alias_con_tilde(self, harmonizer):
        assert harmonizer.harmonize("IVAN CEPEDA") == "Iván Cepeda"

    def test_match_alias_parcial(self, harmonizer):
        # "Espriella" sin el "Abelardo de la" debe matchear
        assert harmonizer.harmonize("Espriella") == "Abelardo de la Espriella"

    def test_ns_nr_detectado(self, harmonizer):
        assert harmonizer.harmonize("NS/NR") == "NS/NR"
        assert harmonizer.harmonize("no sabe") == "NS/NR"

    def test_sin_match_devuelve_original(self, harmonizer):
        result = harmonizer.harmonize("Candidato Inexistente")
        # Si no matchea, devuelve el original strip
        assert result == "Candidato Inexistente"

    def test_none_y_nan(self, harmonizer):
        assert harmonizer.harmonize(None) is None
        assert harmonizer.harmonize(float("nan")) is None

    def test_vigentes(self, harmonizer):
        vig = harmonizer.vigentes()
        assert "Iván Cepeda" in vig
        assert "Abelardo de la Espriella" in vig
        # Especiales no son vigentes
        assert "NS/NR" not in vig
        assert "Blanco" not in vig

    def test_key_de(self, harmonizer):
        assert harmonizer.key_de("Iván Cepeda") == "cepeda"
        assert harmonizer.key_de("Sergio Fajardo") == "fajardo"
        assert harmonizer.key_de("Inexistente") is None

    def test_por_bloque(self, harmonizer):
        izq = harmonizer.por_bloque("izquierda")
        assert izq == {"Iván Cepeda"}
        der = harmonizer.por_bloque("derecha")
        assert der == {"Abelardo de la Espriella"}
