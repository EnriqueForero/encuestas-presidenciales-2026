"""Tests de generación de columnas SV (matchups de segunda vuelta)."""

from __future__ import annotations

import pytest

from encuestas_lib.harmonization.candidates import build_harmonizer
from encuestas_lib.harmonization.matchups import (
    parse_atlas_label,
    sv_col_name,
)


@pytest.fixture
def harmonizer():
    candidates = [
        {"canonical": "Iván Cepeda", "key": "cepeda", "status": "vigente",
         "bloque": "izquierda", "aliases": ["cepeda", "ivan cepeda"]},
        {"canonical": "Abelardo de la Espriella", "key": "espriella",
         "status": "vigente", "bloque": "derecha",
         "aliases": ["espriella", "abelardo de la espriella", "de la espriella"]},
        {"canonical": "Sergio Fajardo", "key": "fajardo", "status": "vigente",
         "bloque": "centro", "aliases": ["fajardo", "sergio fajardo"]},
    ]
    return build_harmonizer(candidates, [])


class TestSVColName:
    def test_orden_alfabetico(self, harmonizer):
        """sv_a_vs_b siempre con a < b alfabéticamente."""
        a = sv_col_name("Iván Cepeda", "Abelardo de la Espriella", harmonizer)
        b = sv_col_name("Abelardo de la Espriella", "Iván Cepeda", harmonizer)
        assert a == b == "sv_cepeda_vs_espriella"

    def test_genera_nombre_correcto(self, harmonizer):
        assert sv_col_name("Iván Cepeda", "Sergio Fajardo", harmonizer) == "sv_cepeda_vs_fajardo"

    def test_candidato_desconocido_devuelve_none(self, harmonizer):
        assert sv_col_name("Inexistente", "Iván Cepeda", harmonizer) is None
        assert sv_col_name(None, "Iván Cepeda", harmonizer) is None


class TestParseAtlasLabel:
    def test_formato_vs_punto(self, harmonizer):
        assert (
            parse_atlas_label("Cepeda vs. Espriella", harmonizer)
            == "sv_cepeda_vs_espriella"
        )

    def test_formato_vs_sin_punto(self, harmonizer):
        assert (
            parse_atlas_label("Cepeda vs Espriella", harmonizer)
            == "sv_cepeda_vs_espriella"
        )

    def test_case_insensitive(self, harmonizer):
        assert (
            parse_atlas_label("CEPEDA VS ESPRIELLA", harmonizer)
            == "sv_cepeda_vs_espriella"
        )

    def test_label_invalido(self, harmonizer):
        # Sin "vs" → None
        assert parse_atlas_label("Cepeda y Espriella", harmonizer) is None
        # Solo un candidato → None
        assert parse_atlas_label("Cepeda", harmonizer) is None
