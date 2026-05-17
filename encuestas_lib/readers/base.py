"""Base class para todos los lectores de microdatos de encuestas.

Cada encuestadora (Atlas, GAD3, Invamer, CNC, …) tiene su propia subclase
que sabe leer su formato específico y mapearlo al schema canónico.

Para agregar una nueva encuestadora:
    1. Crear módulo en encuestas_lib/readers/<nombre>.py
    2. Heredar de BaseReader, implementar `read()`.
    3. Registrar la clase en encuestas_lib/readers/registry.py.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import pandas as pd

from encuestas_lib.harmonization import (
    DEMO_COLS,
    META_COLS,
    OPINION_COLS,
    VOTE_COLS,
)

if TYPE_CHECKING:
    from encuestas_lib.config import SurveyEntry
    from encuestas_lib.harmonization import CandidateHarmonizer


class BaseReader(ABC):
    """Lector abstracto.

    Subclases deben implementar `read()` retornando un DataFrame con al
    menos las columnas META_COLS + DEMO_COLS + VOTE_COLS + OPINION_COLS,
    más cualquier número de columnas `sv_*` para matchups de segunda vuelta.

    Attributes:
        survey: metadata de la encuesta (de surveys.yaml).
        harmonizer: para resolver nombres canónicos.
    """

    def __init__(
        self,
        survey: SurveyEntry,
        harmonizer: CandidateHarmonizer,
    ) -> None:
        self.survey = survey
        self.harmonizer = harmonizer

    # ────────────────────────────────────────────────────────────────────
    @abstractmethod
    def read(self) -> pd.DataFrame:
        """Leer microdatos y devolver DataFrame en schema canónico.

        Returns:
            DataFrame con al menos las columnas:
                encuestadora, fecha, factor,
                departamento, municipio, region, zona,
                genero, edad_grupo, estrato, educacion,
                primera_vuelta, primera_vuelta_espontanea,
                aprobacion_petro,
                sv_*  (cero o más matchups de SV).
        """

    # ────────────────────────────────────────────────────────────────────
    def _empty_canonical_df(self, index: pd.Index) -> pd.DataFrame:
        """Construir DataFrame vacío con todas las columnas canónicas en None."""
        cols = META_COLS + DEMO_COLS + VOTE_COLS + OPINION_COLS
        return pd.DataFrame({c: pd.Series([None] * len(index), index=index) for c in cols})

    def _validate_output(self, df: pd.DataFrame) -> pd.DataFrame:
        """Verificar que el DataFrame retornado cumple el schema mínimo.

        Args:
            df: DataFrame a validar.

        Returns:
            El mismo DataFrame si pasa, sino raise.

        Raises:
            ValueError: si faltan columnas requeridas o `factor` no es numérico.
        """
        required = set(META_COLS)  # encuestadora, fecha, factor son críticas
        missing = required - set(df.columns)
        if missing:
            raise ValueError(
                f"Reader {self.__class__.__name__} omitió columnas requeridas: "
                f"{missing} para encuesta {self.survey.id}"
            )
        if not pd.api.types.is_numeric_dtype(df["factor"]):
            raise ValueError(
                f"Reader {self.__class__.__name__}: columna 'factor' no es numérica "
                f"para encuesta {self.survey.id}. dtype={df['factor'].dtype}"
            )
        return df

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id={self.survey.id!r})"


# ════════════════════════════════════════════════════════════════════════════
#  Utilidades comunes a varios readers
# ════════════════════════════════════════════════════════════════════════════
def find_col(df: pd.DataFrame, *substrings: str) -> str | None:
    """Encontrar la primera columna que contiene cualquiera de las substrings.

    Case-insensitive. Útil porque las encuestadoras renombran columnas
    entre versiones del cuestionario.

    Args:
        df: DataFrame a inspeccionar.
        *substrings: substrings a buscar (en orden de prioridad).

    Returns:
        Nombre de columna o None.
    """
    cols = [str(c) for c in df.columns]
    for s in substrings:
        s_low = s.lower()
        matches = [c for c in cols if s_low in c.lower()]
        if matches:
            return matches[0]
    return None


def ensure_canonical_columns(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Garantizar que todas las columnas canónicas existan en el DataFrame.

    Las que no existan se agregan con None.

    Args:
        df: DataFrame a completar (modificado in-place + retornado).
        cols: lista de columnas requeridas.

    Returns:
        El mismo DataFrame con columnas completadas.
    """
    for c in cols:
        if c not in df.columns:
            df[c] = None
    return df
