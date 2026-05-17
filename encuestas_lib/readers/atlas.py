"""Lector de microdatos Atlas Intel.

Formato Atlas Intel:
    - Excel o CSV.
    - Columna `weight` para factor de expansión.
    - `presidential_election_2026` para primera vuelta (texto libre).
    - `vote_president_2026_spontaneous` para espontánea.
    - `second_round_president_2026_co`: JSON con lista de matchups SV.
    - Variables demográficas: state, municipality, region, gender, age,
      educational_level.
    - Aprobación: `approve_disapprove_president`.
"""

from __future__ import annotations

import pandas as pd

from encuestas_lib.harmonization import parse_atlas_json_cell
from encuestas_lib.readers.base import BaseReader


class AtlasReader(BaseReader):
    """Reader para encuestas Atlas Intel."""

    def read(self) -> pd.DataFrame:
        """Leer una encuesta Atlas Intel.

        Returns:
            DataFrame en schema canónico.

        Raises:
            FileNotFoundError: si el path declarado no existe.
        """
        path = self.survey.path
        if not path.exists():
            raise FileNotFoundError(f"Atlas: archivo no encontrado: {path}")

        # Atlas viene en xlsx o csv según la semana
        if str(path).endswith(".csv"):
            df = pd.read_csv(path, dtype_backend="pyarrow")
        else:
            df = pd.read_excel(path)

        r = self._empty_canonical_df(df.index)
        r["encuestadora"] = "Atlas Intel"
        r["fecha"] = pd.Timestamp(self.survey.fecha)
        r["factor"] = pd.to_numeric(df.get("weight"), errors="coerce")
        r["departamento"] = df.get("state")
        r["municipio"] = df.get("municipality")
        r["region"] = df.get("region")
        r["zona"] = None
        r["genero"] = df.get("gender")
        r["edad_grupo"] = df.get("age")
        r["educacion"] = df.get("educational_level")
        r["estrato"] = None
        r["aprobacion_petro"] = df.get("approve_disapprove_president")

        # Primera vuelta (texto libre → harmonize)
        h = self.harmonizer
        if "presidential_election_2026" in df.columns:
            r["primera_vuelta"] = df["presidential_election_2026"].map(h.harmonize)

        spont = "vote_president_2026_spontaneous"
        if spont in df.columns:
            r["primera_vuelta_espontanea"] = df[spont].map(h.harmonize)

        # Segunda vuelta: parsear JSON multi-matchup
        sv_col = "second_round_president_2026_co"
        if sv_col in df.columns:
            json_series = df[sv_col].map(lambda c: parse_atlas_json_cell(c, h))
            # Construir columnas sv_* a partir de los dicts
            all_sv_cols: set[str] = set()
            for d in json_series:
                all_sv_cols.update(d.keys())
            for c in sorted(all_sv_cols):
                r[c] = json_series.map(lambda d, k=c: d.get(k))

        # Nota: s2/s3/s4 son escenarios multi-candidato (3-4), no binarios → skip
        return self._validate_output(r)
