"""Tests del sistema de fingerprint para detección automática de obsolescencia.

Verifica que el checkpoint se invalida automáticamente cuando cambian los
archivos de configuración o de código relevantes para la ingesta, sin
necesidad de borrar el parquet manualmente.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from encuestas_lib.pipeline.checkpoints import (
    INGEST_PIPELINE_VERSION,
    _fingerprint_path,
    _save_fingerprint,
    cargar_o_procesar,
    checkpoint_is_stale,
    compute_fingerprint,
)


# ════════════════════════════════════════════════════════════════════════════
#  Fixtures
# ════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def tmp_dir(tmp_path: Path) -> Path:
    """Directorio temporal aislado por test."""
    return tmp_path


@pytest.fixture
def surveys_yaml(tmp_dir: Path) -> Path:
    p = tmp_dir / "surveys.yaml"
    p.write_text("surveys:\n  - id: s1\n    encuestadora: Atlas\n", encoding="utf-8")
    return p


@pytest.fixture
def candidates_yaml(tmp_dir: Path) -> Path:
    p = tmp_dir / "candidates.yaml"
    p.write_text("candidates:\n  - canonical: Iván Cepeda\n", encoding="utf-8")
    return p


@pytest.fixture
def parquet_path(tmp_dir: Path) -> Path:
    return tmp_dir / "processed" / "encuestas.parquet"


@pytest.fixture
def df_simple() -> pd.DataFrame:
    return pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})


# ════════════════════════════════════════════════════════════════════════════
#  compute_fingerprint
# ════════════════════════════════════════════════════════════════════════════
class TestComputeFingerprint:
    def test_contiene_version(self, surveys_yaml, candidates_yaml):
        fp = compute_fingerprint(surveys_yaml, candidates_yaml)
        assert fp["version"] == INGEST_PIPELINE_VERSION

    def test_contiene_hash_yamls(self, surveys_yaml, candidates_yaml):
        fp = compute_fingerprint(surveys_yaml, candidates_yaml)
        assert "surveys_yaml" in fp
        assert "candidates_yaml" in fp
        assert len(fp["surveys_yaml"]) == 16  # SHA-256 truncado a 16 chars

    def test_archivo_faltante_da_hash_missing(self, tmp_dir, candidates_yaml):
        no_existe = tmp_dir / "no_existe.yaml"
        fp = compute_fingerprint(no_existe, candidates_yaml)
        assert fp["surveys_yaml"] == "missing"

    def test_cambio_en_surveys_yaml_cambia_fingerprint(self, surveys_yaml, candidates_yaml):
        fp1 = compute_fingerprint(surveys_yaml, candidates_yaml)
        surveys_yaml.write_text("surveys:\n  - id: s1\n  - id: s2\n", encoding="utf-8")
        fp2 = compute_fingerprint(surveys_yaml, candidates_yaml)
        assert fp1["surveys_yaml"] != fp2["surveys_yaml"]

    def test_cambio_en_candidates_yaml_cambia_fingerprint(self, surveys_yaml, candidates_yaml):
        fp1 = compute_fingerprint(surveys_yaml, candidates_yaml)
        candidates_yaml.write_text(
            "candidates:\n  - canonical: Iván Cepeda\n  - canonical: Paloma Valencia\n",
            encoding="utf-8",
        )
        fp2 = compute_fingerprint(surveys_yaml, candidates_yaml)
        assert fp1["candidates_yaml"] != fp2["candidates_yaml"]

    def test_mismos_archivos_mismo_fingerprint(self, surveys_yaml, candidates_yaml):
        fp1 = compute_fingerprint(surveys_yaml, candidates_yaml)
        fp2 = compute_fingerprint(surveys_yaml, candidates_yaml)
        assert fp1 == fp2


# ════════════════════════════════════════════════════════════════════════════
#  checkpoint_is_stale
# ════════════════════════════════════════════════════════════════════════════
class TestCheckpointIsStale:
    def test_parquet_no_existe_es_obsoleto(self, parquet_path, surveys_yaml, candidates_yaml):
        stale, razon = checkpoint_is_stale(parquet_path, surveys_yaml, candidates_yaml)
        assert stale
        assert "no existe" in razon

    def test_sin_fingerprint_es_obsoleto(
        self, parquet_path, surveys_yaml, candidates_yaml, df_simple
    ):
        parquet_path.parent.mkdir(parents=True, exist_ok=True)
        df_simple.to_parquet(parquet_path)
        # Sin fingerprint guardado
        stale, razon = checkpoint_is_stale(parquet_path, surveys_yaml, candidates_yaml)
        assert stale
        assert "fingerprint" in razon.lower()

    def test_fingerprint_valido_no_es_obsoleto(
        self, parquet_path, surveys_yaml, candidates_yaml, df_simple
    ):
        parquet_path.parent.mkdir(parents=True, exist_ok=True)
        df_simple.to_parquet(parquet_path)
        fp = compute_fingerprint(surveys_yaml, candidates_yaml)
        _save_fingerprint(parquet_path, fp)

        stale, razon = checkpoint_is_stale(parquet_path, surveys_yaml, candidates_yaml)
        assert not stale
        assert razon == ""

    def test_cambio_surveys_detectado(self, parquet_path, surveys_yaml, candidates_yaml, df_simple):
        parquet_path.parent.mkdir(parents=True, exist_ok=True)
        df_simple.to_parquet(parquet_path)
        fp = compute_fingerprint(surveys_yaml, candidates_yaml)
        _save_fingerprint(parquet_path, fp)

        # Simular nueva encuesta agregada a surveys.yaml
        surveys_yaml.write_text("surveys:\n  - id: s1\n  - id: s_nueva\n", encoding="utf-8")
        stale, razon = checkpoint_is_stale(parquet_path, surveys_yaml, candidates_yaml)
        assert stale
        assert "surveys.yaml" in razon

    def test_cambio_candidates_detectado(
        self, parquet_path, surveys_yaml, candidates_yaml, df_simple
    ):
        parquet_path.parent.mkdir(parents=True, exist_ok=True)
        df_simple.to_parquet(parquet_path)
        fp = compute_fingerprint(surveys_yaml, candidates_yaml)
        _save_fingerprint(parquet_path, fp)

        # Simular nuevo candidato principal
        candidates_yaml.write_text(
            "candidates:\n  - canonical: Iván Cepeda\n  - canonical: Paloma Valencia\n",
            encoding="utf-8",
        )
        stale, razon = checkpoint_is_stale(parquet_path, surveys_yaml, candidates_yaml)
        assert stale
        assert "candidates.yaml" in razon

    def test_fingerprint_json_corrupto_es_obsoleto(
        self, parquet_path, surveys_yaml, candidates_yaml, df_simple
    ):
        parquet_path.parent.mkdir(parents=True, exist_ok=True)
        df_simple.to_parquet(parquet_path)
        _fingerprint_path(parquet_path).write_text("not valid json!!!")

        stale, _ = checkpoint_is_stale(parquet_path, surveys_yaml, candidates_yaml)
        assert stale


# ════════════════════════════════════════════════════════════════════════════
#  cargar_o_procesar con fingerprint
# ════════════════════════════════════════════════════════════════════════════
class TestCargarOProcesar:
    """Integración: verifica el flujo completo de cache con fingerprint."""

    def test_primera_llamada_ejecuta_funcion(self, parquet_path, surveys_yaml, candidates_yaml):
        call_count = [0]

        def proceso() -> pd.DataFrame:
            call_count[0] += 1
            return pd.DataFrame({"x": [1, 2, 3]})

        df = cargar_o_procesar(
            parquet_path,
            proceso,
            surveys_yaml=surveys_yaml,
            candidates_yaml=candidates_yaml,
        )
        assert call_count[0] == 1
        assert len(df) == 3
        assert parquet_path.exists()
        assert _fingerprint_path(parquet_path).exists()

    def test_segunda_llamada_usa_cache(self, parquet_path, surveys_yaml, candidates_yaml):
        call_count = [0]

        def proceso() -> pd.DataFrame:
            call_count[0] += 1
            return pd.DataFrame({"x": [1, 2, 3]})

        cargar_o_procesar(
            parquet_path, proceso, surveys_yaml=surveys_yaml, candidates_yaml=candidates_yaml
        )
        cargar_o_procesar(
            parquet_path, proceso, surveys_yaml=surveys_yaml, candidates_yaml=candidates_yaml
        )
        assert call_count[0] == 1  # segunda vez usa cache

    def test_cambio_en_yaml_invalida_cache(self, parquet_path, surveys_yaml, candidates_yaml):
        call_count = [0]

        def proceso() -> pd.DataFrame:
            call_count[0] += 1
            return pd.DataFrame({"x": [1, 2, 3]})

        cargar_o_procesar(
            parquet_path, proceso, surveys_yaml=surveys_yaml, candidates_yaml=candidates_yaml
        )
        # Simular nueva encuesta → cache debe invalidarse
        surveys_yaml.write_text("surveys:\n  - id: s1\n  - id: s2\n", encoding="utf-8")
        cargar_o_procesar(
            parquet_path, proceso, surveys_yaml=surveys_yaml, candidates_yaml=candidates_yaml
        )
        assert call_count[0] == 2  # se reprocesó

    def test_forzar_siempre_reprocesa(self, parquet_path, surveys_yaml, candidates_yaml):
        call_count = [0]

        def proceso() -> pd.DataFrame:
            call_count[0] += 1
            return pd.DataFrame({"x": [1]})

        cargar_o_procesar(
            parquet_path, proceso, surveys_yaml=surveys_yaml, candidates_yaml=candidates_yaml
        )
        cargar_o_procesar(
            parquet_path,
            proceso,
            forzar=True,
            surveys_yaml=surveys_yaml,
            candidates_yaml=candidates_yaml,
        )
        assert call_count[0] == 2

    def test_sin_yamls_funciona_sin_fingerprint(self, parquet_path):
        """Sin surveys_yaml/candidates_yaml, comportamiento legacy (sin fingerprint)."""
        call_count = [0]

        def proceso() -> pd.DataFrame:
            call_count[0] += 1
            return pd.DataFrame({"x": [1]})

        cargar_o_procesar(parquet_path, proceso)
        cargar_o_procesar(parquet_path, proceso)
        assert call_count[0] == 1  # segunda vez usa cache (legacy: solo comprueba si existe)
