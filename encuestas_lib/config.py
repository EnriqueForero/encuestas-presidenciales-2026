"""Configuración centralizada del pipeline.

Toda la configuración se lee desde archivos YAML en `configs/`. No hay
constantes mágicas dentro del código de negocio.

Ejemplo:
    >>> config = Config.from_yaml("configs/")
    >>> print(config.paths.raw_dir)
    PosixPath('data/raw')
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Literal

import yaml

ReaderName = Literal[
    "atlas",
    "gad3_excel_v1",
    "gad3_excel_v2",
    "gad3_sav",
    "invamer",
    "cnc_sav",
    "cnc_excel",
]


@dataclass(frozen=True)
class Paths:
    """Rutas del proyecto.

    Attributes:
        root: directorio raíz del repositorio.
        raw_dir: microdatos crudos (descargas del CNE).
        processed_dir: parquet checkpoints intermedios.
        outputs_dir: Excel y JSON finales.
        configs_dir: archivos YAML de configuración.
    """

    root: Path
    raw_dir: Path
    processed_dir: Path
    outputs_dir: Path
    configs_dir: Path

    def __post_init__(self) -> None:
        for d in (self.raw_dir, self.processed_dir, self.outputs_dir):
            d.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class SurveyEntry:
    """Una encuesta registrada en surveys.yaml."""

    id: str
    encuestadora: str
    fecha: date
    reader: str
    path: Path
    n_muestra: int | None = None
    nota: str | None = None

    @property
    def fecha_str(self) -> str:
        """Fecha como YYYY-MM-DD."""
        return self.fecha.isoformat()


@dataclass(frozen=True)
class WeightingConfig:
    """Configuración de la estrategia de ponderación entre encuestas.

    Attributes:
        active_strategy: nombre de la estrategia a usar.
        params: parámetros específicos (e.g. half_life_days).
        manual_weights: dict (encuestadora, fecha_str) → peso, si strategy=manual.
    """

    active_strategy: str
    params: dict[str, Any] = field(default_factory=dict)
    manual_weights: dict[tuple[str, str], float] = field(default_factory=dict)


@dataclass(frozen=True)
class Config:
    """Configuración global del pipeline.

    Construir con `Config.from_yaml(configs_dir)`. No instanciar directamente
    salvo en tests.
    """

    paths: Paths
    surveys: list[SurveyEntry]
    weighting: WeightingConfig
    candidates_raw: list[dict[str, Any]]  # se procesa en harmonization/candidates.py
    special_categories_raw: list[dict[str, Any]]

    # ────────────────────────────────────────────────────────────────────
    @classmethod
    def from_yaml(
        cls,
        configs_dir: str | Path,
        root: str | Path | None = None,
    ) -> Config:
        """Cargar configuración desde el directorio configs/.

        Args:
            configs_dir: directorio que contiene surveys.yaml, candidates.yaml,
                weights.yaml.
            root: directorio raíz del proyecto. Si es None, se infiere como
                parent de configs_dir.

        Returns:
            Config validada.

        Raises:
            FileNotFoundError: si falta algún YAML requerido.
            ValueError: si el contenido no cumple el schema esperado.
        """
        configs_dir = Path(configs_dir).resolve()
        if root is None:
            root = configs_dir.parent
        root = Path(root).resolve()

        surveys_yaml = configs_dir / "surveys.yaml"
        cands_yaml = configs_dir / "candidates.yaml"
        weights_yaml = configs_dir / "weights.yaml"

        for p in (surveys_yaml, cands_yaml, weights_yaml):
            if not p.exists():
                raise FileNotFoundError(f"YAML requerido no encontrado: {p}")

        # ── Paths ──
        paths = Paths(
            root=root,
            raw_dir=root / "data" / "raw",
            processed_dir=root / "data" / "processed",
            outputs_dir=root / "data" / "outputs",
            configs_dir=configs_dir,
        )

        # ── Surveys ──
        with surveys_yaml.open(encoding="utf-8") as f:
            surveys_doc = yaml.safe_load(f)
        if "surveys" not in surveys_doc:
            raise ValueError("surveys.yaml debe contener una clave 'surveys'.")

        surveys = [
            SurveyEntry(
                id=s["id"],
                encuestadora=s["encuestadora"],
                fecha=_parse_fecha(s["fecha"]),
                reader=s["reader"],
                path=paths.raw_dir / s["path"],
                n_muestra=s.get("n_muestra"),
                nota=s.get("nota"),
            )
            for s in surveys_doc["surveys"]
        ]

        # ── Candidates ──
        with cands_yaml.open(encoding="utf-8") as f:
            cands_doc = yaml.safe_load(f)
        candidates_raw = cands_doc.get("candidates", [])
        special_categories_raw = cands_doc.get("special_categories", [])

        # ── Weights ──
        with weights_yaml.open(encoding="utf-8") as f:
            weights_doc = yaml.safe_load(f)
        active = weights_doc.get("active_strategy", "inverse_recency_size")
        strat_block = weights_doc.get("strategies", {}).get(active, {})

        manual_weights: dict[tuple[str, str], float] = {}
        if active == "manual":
            for w in strat_block.get("weights", []):
                manual_weights[(w["encuestadora"], w["fecha"])] = float(w["peso"])

        weighting = WeightingConfig(
            active_strategy=active,
            params=strat_block.get("params", {}),
            manual_weights=manual_weights,
        )

        return cls(
            paths=paths,
            surveys=surveys,
            weighting=weighting,
            candidates_raw=candidates_raw,
            special_categories_raw=special_categories_raw,
        )


# ════════════════════════════════════════════════════════════════════════════
#  Helpers
# ════════════════════════════════════════════════════════════════════════════
def _parse_fecha(val: Any) -> date:
    """Aceptar tanto date (YAML lo deserializa nativo) como string YYYY-MM-DD."""
    if isinstance(val, date):
        return val
    if isinstance(val, str):
        return date.fromisoformat(val)
    raise ValueError(f"Fecha inválida: {val!r}")
