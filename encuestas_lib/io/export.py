"""Exportadores de resultados analíticos.

Toma un dict {nombre_tabla: DataFrame} y lo serializa a Excel multi-hoja
o JSON con metadatos de auditoría (timestamp, n_filas, hash).

Exporters:
    - ExcelExporter: una hoja por tabla, columnas auto-ancho.
    - JSONExporter:  estructura {meta: {...}, tables: {nombre: [...]}}
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


# ════════════════════════════════════════════════════════════════════════════
#  Excel
# ════════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class ExcelExporter:
    """Exporta múltiples tablas a un único Excel.

    Excel limita los nombres de hoja a 31 caracteres y prohíbe ciertos
    caracteres. Esta clase trunca y sanea automáticamente.
    """

    autofit: bool = True
    max_sheet_name: int = 31

    def write(self, tablas: dict[str, pd.DataFrame], path: Path | str) -> Path:
        """Escribir todas las tablas en `path`.

        Returns:
            Path absoluto del archivo escrito.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            for nombre, df in tablas.items():
                sheet = self._sanitize_sheet_name(nombre)
                df.to_excel(writer, sheet_name=sheet, index=False)
                if self.autofit:
                    self._autofit(writer.sheets[sheet], df)
        return path.resolve()

    def _sanitize_sheet_name(self, raw: str) -> str:
        invalidos = "[]:*?/\\"
        clean = "".join("_" if c in invalidos else c for c in raw)
        return clean[: self.max_sheet_name]

    @staticmethod
    def _autofit(ws: Any, df: pd.DataFrame) -> None:
        """Ajustar ancho de columnas a contenido (aprox.)."""
        for idx, col in enumerate(df.columns, start=1):
            largo_max = max(
                [len(str(col))] + [len(str(v)) for v in df[col].head(200).astype(str).tolist()]
            )
            letter = ws.cell(row=1, column=idx).column_letter
            ws.column_dimensions[letter].width = min(60, largo_max + 2)


# ════════════════════════════════════════════════════════════════════════════
#  JSON
# ════════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class JSONExporter:
    """Exporta tablas a JSON con metadatos.

    Estructura:
        {
            "meta": {
                "generated_at": "2026-05-17T12:34:56+00:00",
                "n_tables": 12,
                "hash": "ab12cd..."
            },
            "tables": {
                "primera_vuelta_total": [{...}, {...}, ...],
                ...
            }
        }
    """

    indent: int = 2
    ensure_ascii: bool = False

    def write(self, tablas: dict[str, pd.DataFrame], path: Path | str) -> Path:
        """Serializa las tablas a JSON y las guarda en la ruta indicada."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        payload: dict[str, Any] = {
            "meta": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "n_tables": len(tablas),
            },
            "tables": {nombre: _df_to_records(df) for nombre, df in tablas.items()},
        }
        # Hash determinístico para detectar cambios entre runs
        body = json.dumps(payload["tables"], sort_keys=True, default=str)
        payload["meta"]["hash"] = hashlib.sha256(body.encode("utf-8")).hexdigest()[:12]

        with path.open("w", encoding="utf-8") as f:
            json.dump(
                payload,
                f,
                indent=self.indent,
                ensure_ascii=self.ensure_ascii,
                default=str,
            )
        return path.resolve()


def _df_to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """DataFrame → lista de dicts JSON-safe (Timestamp → str, NaN → None)."""
    if df.empty:
        return []
    d = df.copy()
    for col in d.select_dtypes(include=["datetime64[ns]", "datetime64[ns, UTC]"]):
        d[col] = d[col].astype(str)
    return d.where(d.notna(), None).to_dict(orient="records")


__all__ = ["ExcelExporter", "JSONExporter"]
