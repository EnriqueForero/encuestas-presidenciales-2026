"""Lector de microdatos CNC (Centro Nacional de Consultoría).

Dos variantes:
    - cnc_sav: encuesta 25 (Feb 2026), SPSS .sav.
    - cnc_excel: encuesta 34 (Mar 2026), .xlsx con codificación TEXTOS.
"""

from __future__ import annotations

from typing import ClassVar

import pandas as pd

from encuestas_lib.readers.base import BaseReader


class _CNCBase(BaseReader):
    """Base con utilidades comunes de CNC."""

    SV_MAP_25: ClassVar[dict[str, tuple[str, str]]] = {
        "P5": ("Iván Cepeda", "Sergio Fajardo"),
        "P6": ("Iván Cepeda", "Abelardo de la Espriella"),
        "P7": ("Iván Cepeda", "Claudia López"),
        "P8": ("Iván Cepeda", "Paloma Valencia"),
        "P9": ("Iván Cepeda", "Juan Manuel Galán"),
        "P10": ("Iván Cepeda", "Aníbal Gaviria"),
        "P11": ("Iván Cepeda", "Vicky Dávila"),
        "P12": ("Iván Cepeda", "Mauricio Cárdenas"),
    }

    SV_MAP_34: ClassVar[dict[str, tuple[str, str]]] = {
        "P7": ("Iván Cepeda", "Abelardo de la Espriella"),
        "P8": ("Iván Cepeda", "Paloma Valencia"),
        "P9": ("Iván Cepeda", "Sergio Fajardo"),
        "P10": ("Iván Cepeda", "Claudia López"),
        "P11": ("Iván Cepeda", "Roy Barreras"),
        "P12": ("Iván Cepeda", "Miguel Uribe Londoño"),
        "P13": ("Iván Cepeda", "Mauricio Lizcano"),
        "P14": ("Iván Cepeda", "Luis Gilberto Murillo"),
    }


# ════════════════════════════════════════════════════════════════════════════
class CNCSavReader(_CNCBase):
    """Reader CNC variante .sav (encuesta 25, Feb 2026)."""

    def read(self) -> pd.DataFrame:
        """Lee el archivo .sav de CNC y retorna el DataFrame canónico."""
        import pyreadstat

        path = self.survey.path
        if not path.exists():
            raise FileNotFoundError(f"CNC: archivo no encontrado: {path}")
        df, _ = pyreadstat.read_sav(str(path), apply_value_formats=True)

        r = self._empty_canonical_df(df.index)
        h = self.harmonizer

        r["encuestadora"] = "CNC"
        r["fecha"] = pd.Timestamp(self.survey.fecha)
        r["factor"] = pd.to_numeric(df["FACTOR"], errors="coerce")
        r["departamento"] = df.get("DPTO")
        r["municipio"] = df.get("MUNICIPIO")
        r["region"] = df.get("REGION")
        r["zona"] = df.get("ZONA")
        r["genero"] = df["GENERO"].map(h.harmonize) if "GENERO" in df.columns else None
        r["edad_grupo"] = df.get("REDAD")
        r["estrato"] = df.get("ESTRATO")
        r["educacion"] = df.get("P20")
        r["aprobacion_petro"] = df["P14"].map(h.harmonize) if "P14" in df.columns else None

        if "P2" in df.columns:
            r["primera_vuelta"] = df["P2"].map(h.harmonize)
        r["primera_vuelta_espontanea"] = None

        from encuestas_lib.harmonization import sv_col_name

        for col, (c1, c2) in self.SV_MAP_25.items():
            sv = sv_col_name(c1, c2, h)
            if col in df.columns and sv:
                r[sv] = df[col].map(h.harmonize)

        return self._validate_output(r)


class CNCExcelReader(_CNCBase):
    """Reader CNC variante .xlsx con TEXTOS (encuesta 34, Mar 2026)."""

    def read(self) -> pd.DataFrame:
        """Lee el archivo .xlsx de CNC y retorna el DataFrame canónico."""
        path = self.survey.path
        if not path.exists():
            raise FileNotFoundError(f"CNC: archivo no encontrado: {path}")
        df = pd.read_excel(path)

        r = self._empty_canonical_df(df.index)
        h = self.harmonizer

        r["encuestadora"] = "CNC"
        r["fecha"] = pd.Timestamp(self.survey.fecha)
        r["factor"] = pd.to_numeric(df["FACTOR"], errors="coerce")
        r["departamento"] = df.get("DPTO")
        r["municipio"] = df.get("MUNICIPIO")
        r["region"] = df.get("REGION")
        r["zona"] = df.get("ZONA")
        r["genero"] = df["GENERO"].map(h.harmonize) if "GENERO" in df.columns else None
        r["edad_grupo"] = df.get("REDAD")
        r["estrato"] = df.get("ESTRATO")
        r["educacion"] = df.get("P19")
        r["aprobacion_petro"] = df["P15"].map(h.harmonize) if "P15" in df.columns else None

        if "P1" in df.columns:
            r["primera_vuelta"] = df["P1"].map(h.harmonize)
        r["primera_vuelta_espontanea"] = None

        from encuestas_lib.harmonization import sv_col_name

        for col, (c1, c2) in self.SV_MAP_34.items():
            sv = sv_col_name(c1, c2, h)
            if col in df.columns and sv:
                r[sv] = df[col].map(h.harmonize)

        return self._validate_output(r)
