"""Lector de microdatos GAD3 (tres variantes de cuestionario).

GAD3 publicó al menos tres variantes:
    - gad3_excel_v1: 505-221 RCN Enero (formato xlsx, Q02/Q10/Q11A-G).
    - gad3_sav: SPSS .sav (Q02/Q08/Q09A-D).
    - gad3_excel_v2: 31. xlsx (Q06/Q08 con prefijo separador "Q08 - ").

Cada variante tiene su propia subclase para evitar `if reader_version == 'X'`
adentro de un solo método.
"""

from __future__ import annotations

from typing import ClassVar

import pandas as pd

from encuestas_lib.readers.base import BaseReader, find_col


class _GAD3Base(BaseReader):
    """Base con utilidades comunes para variantes de GAD3."""

    def _read_dataframe(self) -> pd.DataFrame:
        """Leer el archivo (xlsx o sav) según extensión."""
        path = self.survey.path
        if not path.exists():
            raise FileNotFoundError(f"GAD3: archivo no encontrado: {path}")

        if str(path).endswith(".sav"):
            import pyreadstat

            df, _ = pyreadstat.read_sav(str(path), apply_value_formats=True)
            return df
        return pd.read_excel(path)

    def _apply_sv_map(
        self,
        r: pd.DataFrame,
        df: pd.DataFrame,
        sv_map: dict[str, tuple[str, str]],
        col_finder=None,
    ) -> None:
        """Aplicar mapeo de columnas Q* → matchups SV.

        Args:
            r: DataFrame de salida (modificado in-place).
            df: DataFrame crudo.
            sv_map: { "Q11A": ("cand1_canonical", "cand2_canonical"), ... }.
            col_finder: función para resolver el nombre real de la columna,
                por defecto `find_col(df, prefix)`. Si la encuesta usa
                separador (e.g. "Q08 -"), pasar lambda alternativo.
        """
        from encuestas_lib.harmonization import sv_col_name

        col_finder = col_finder or (lambda d, p: find_col(d, p))
        h = self.harmonizer
        for prefix, (c1, c2) in sv_map.items():
            real_col = col_finder(df, prefix)
            sv_name = sv_col_name(c1, c2, h)
            if real_col and sv_name and real_col in df.columns:
                r[sv_name] = df[real_col].map(h.harmonize)


# ════════════════════════════════════════════════════════════════════════════
#  Variante v1: encuesta 05 (Enero 2026)
# ════════════════════════════════════════════════════════════════════════════
class GAD3ExcelV1Reader(_GAD3Base):
    """Reader GAD3 — variante v1 (Q02, Q10, Q11A-G)."""

    SV_MAP: ClassVar[dict[str, tuple[str, str]]] = {
        "Q11A": ("Abelardo de la Espriella", "Iván Cepeda"),
        "Q11B": ("Iván Cepeda", "Sergio Fajardo"),
        "Q11C": ("Paloma Valencia", "Iván Cepeda"),
        "Q11D": ("Iván Cepeda", "Juan Carlos Pinzón"),
        "Q11E": ("Abelardo de la Espriella", "Sergio Fajardo"),
        "Q11F": ("Juan Carlos Pinzón", "Sergio Fajardo"),
        "Q11G": ("Paloma Valencia", "Sergio Fajardo"),
    }

    def read(self) -> pd.DataFrame:
        """Lee el archivo xlsx v1 de GAD3 y retorna el DataFrame canónico."""
        df = self._read_dataframe()
        r = self._empty_canonical_df(df.index)
        h = self.harmonizer

        r["encuestadora"] = "GAD3"
        fecha_col = find_col(df, "Fecha")
        r["fecha"] = (
            pd.to_datetime(df[fecha_col], errors="coerce").dt.normalize().min()
            if fecha_col
            else pd.Timestamp(self.survey.fecha)
        )
        r["factor"] = pd.to_numeric(df.get("Ponderación total"), errors="coerce")
        r["departamento"] = df.get("Departamento")
        r["municipio"] = df.get("Municipio")
        r["region"] = None
        r["zona"] = None

        q02 = find_col(df, "Q02")
        r["genero"] = df[q02].map(h.harmonize) if q02 else None
        r["edad_grupo"] = df.get("Grupo de edad")
        q14 = find_col(df, "Q14")
        q16 = find_col(df, "Q16")
        r["educacion"] = df[q14].astype("string") if q14 else None
        r["estrato"] = df[q16].astype("string") if q16 else None
        r["aprobacion_petro"] = None

        q10 = find_col(df, "Q10")
        if q10:
            r["primera_vuelta"] = df[q10].map(h.harmonize)
            r["primera_vuelta_espontanea"] = df[q10].map(h.harmonize)

        self._apply_sv_map(r, df, self.SV_MAP)
        return self._validate_output(r)


# ════════════════════════════════════════════════════════════════════════════
#  Variante .sav: encuesta 23 (Febrero 2026)
# ════════════════════════════════════════════════════════════════════════════
class GAD3SavReader(_GAD3Base):
    """Reader GAD3 — variante .sav (Q02, Q08, Q09A-D)."""

    SV_MAP: ClassVar[dict[str, tuple[str, str]]] = {
        "Q09": ("Abelardo de la Espriella", "Iván Cepeda"),
        "Q09A": ("Iván Cepeda", "Sergio Fajardo"),
        "Q09B": ("Paloma Valencia", "Iván Cepeda"),
        "Q09C": ("Abelardo de la Espriella", "Sergio Fajardo"),
        "Q09D": ("Paloma Valencia", "Abelardo de la Espriella"),
    }

    def read(self) -> pd.DataFrame:
        """Lee el archivo .sav de GAD3 y retorna el DataFrame canónico."""
        df = self._read_dataframe()
        r = self._empty_canonical_df(df.index)
        h = self.harmonizer

        r["encuestadora"] = "GAD3"
        r["fecha"] = (
            pd.to_datetime(df.get("fecha"), errors="coerce").dt.normalize().min()
            if "fecha" in df.columns
            else pd.Timestamp(self.survey.fecha)
        )
        r["factor"] = pd.to_numeric(df.get("Ponderación"), errors="coerce")
        r["departamento"] = df.get("Departamento")
        r["municipio"] = df.get("municipio")
        r["region"] = df.get("Macroregion")
        r["zona"] = df.get("zona")
        r["genero"] = df["Q02"].map(h.harmonize) if "Q02" in df.columns else None
        r["edad_grupo"] = df.get("Gedad")
        r["educacion"] = df["Q11"].astype("string") if "Q11" in df.columns else None
        r["estrato"] = df["Q13"].astype("string") if "Q13" in df.columns else None
        r["aprobacion_petro"] = None

        if "Q08" in df.columns:
            r["primera_vuelta"] = df["Q08"].map(h.harmonize)
            r["primera_vuelta_espontanea"] = df["Q08"].map(h.harmonize)

        # SV: match exacto del nombre de columna
        self._apply_sv_map(
            r,
            df,
            self.SV_MAP,
            col_finder=lambda d, p: p if p in d.columns else None,
        )
        return self._validate_output(r)


# ════════════════════════════════════════════════════════════════════════════
#  Variante v2: encuesta 31 (Marzo 2026)
# ════════════════════════════════════════════════════════════════════════════
class GAD3ExcelV2Reader(_GAD3Base):
    """Reader GAD3 — variante v2 (Q06, Q08 con prefijo separador)."""

    SV_MAP: ClassVar[dict[str, tuple[str, str]]] = {
        "Q08 -": ("Abelardo de la Espriella", "Iván Cepeda"),
        "Q08A -": ("Iván Cepeda", "Sergio Fajardo"),
        "Q08B -": ("Paloma Valencia", "Iván Cepeda"),
        "Q08C -": ("Abelardo de la Espriella", "Sergio Fajardo"),
        "Q08D -": ("Paloma Valencia", "Abelardo de la Espriella"),
    }

    def read(self) -> pd.DataFrame:
        """Lee el archivo xlsx v2 de GAD3 y retorna el DataFrame canónico."""
        df = self._read_dataframe()
        r = self._empty_canonical_df(df.index)
        h = self.harmonizer

        r["encuestadora"] = "GAD3"
        fecha_col = find_col(df, "fecha")
        r["fecha"] = (
            pd.to_datetime(df[fecha_col], errors="coerce").dt.normalize().min()
            if fecha_col
            else pd.Timestamp(self.survey.fecha)
        )
        r["factor"] = pd.to_numeric(df.get("Ponderación"), errors="coerce")
        r["departamento"] = None
        muni = find_col(df, "municipio")
        r["municipio"] = df[muni] if muni else None
        r["region"] = None
        zona = find_col(df, "zona")
        r["zona"] = df[zona] if zona else None

        q02 = find_col(df, "Q02")
        r["genero"] = df[q02].map(h.harmonize) if q02 else None
        gedad = find_col(df, "Gedad")
        r["edad_grupo"] = df[gedad] if gedad else None
        q10 = find_col(df, "Q10")
        r["educacion"] = df[q10].astype("string") if q10 else None
        q12 = find_col(df, "Q12")
        r["estrato"] = df[q12].astype("string") if q12 else None
        r["aprobacion_petro"] = None

        q06 = find_col(df, "Q06")
        if q06:
            r["primera_vuelta"] = df[q06].map(h.harmonize)
            r["primera_vuelta_espontanea"] = df[q06].map(h.harmonize)

        def _starts_with_prefix(d: pd.DataFrame, prefix: str) -> str | None:
            return next((c for c in d.columns if str(c).startswith(prefix)), None)

        self._apply_sv_map(r, df, self.SV_MAP, col_finder=_starts_with_prefix)
        return self._validate_output(r)
