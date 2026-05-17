"""Validación forense de tablas analíticas.

Verifica que las tablas que deben sumar 100% efectivamente lo hagan,
con tolerancia configurable. Soporta dos formatos:

    - long:  columnas [..., valor]   → suma de `valor` (o por grupo) debe ser 100
    - pivot: columnas categóricas    → suma de cada fila debe ser 100

Función pública:
    - verificar_cierres_100(tablas, tolerancia=0.5) → DataFrame con diagnóstico
"""

from __future__ import annotations

from typing import Literal

import pandas as pd

# ════════════════════════════════════════════════════════════════════════════
#  Spec: qué validar y cómo
# ════════════════════════════════════════════════════════════════════════════
ClosureSpec = tuple[str, Literal["long_total", "long_group", "pivot_row"], tuple[str, ...]]

CLOSURE_SPECS: tuple[ClosureSpec, ...] = (
    ("primera_vuelta_total", "long_total", ()),
    ("voto_por_region", "pivot_row", ()),
    ("voto_por_edad", "pivot_row", ()),
    ("voto_por_genero", "pivot_row", ()),
    ("genero_por_candidato_top4", "pivot_row", ()),
    ("aprobacion_vs_voto", "pivot_row", ()),
    ("voto_vs_aprobacion", "pivot_row", ()),
    ("coalicion_aprobacion", "long_group", ("aprobacion_petro",)),
)


# ════════════════════════════════════════════════════════════════════════════
#  Verificación
# ════════════════════════════════════════════════════════════════════════════
def verificar_cierres_100(
    tablas: dict[str, pd.DataFrame],
    tolerancia: float = 0.5,
    specs: tuple[ClosureSpec, ...] = CLOSURE_SPECS,
) -> pd.DataFrame:
    """Verificar cierres a 100 según el formato de cada tabla.

    Args:
        tablas: dict nombre → DataFrame.
        tolerancia: desviación máxima permitida en puntos porcentuales.
        specs: especificación (nombre, formato, group_cols).

    Returns:
        DataFrame [tabla, grupo, suma_observada, desviacion, ok].
    """
    rows: list[dict] = []
    for nombre, formato, group_cols in specs:
        df = tablas.get(nombre)
        if df is None or df.empty:
            rows.append(
                {
                    "tabla": nombre,
                    "grupo": "<vacia>",
                    "suma_observada": 0.0,
                    "desviacion": float("nan"),
                    "ok": False,
                }
            )
            continue
        if formato == "long_total":
            rows.extend(_check_long_total(nombre, df, tolerancia))
        elif formato == "long_group":
            rows.extend(_check_long_group(nombre, df, group_cols, tolerancia))
        elif formato == "pivot_row":
            rows.extend(_check_pivot_row(nombre, df, tolerancia))
    return pd.DataFrame(rows)


def _check_long_total(nombre: str, df: pd.DataFrame, tol: float) -> list[dict]:
    if "valor" not in df.columns:
        return [
            {
                "tabla": nombre,
                "grupo": "<sin columna valor>",
                "suma_observada": float("nan"),
                "desviacion": float("nan"),
                "ok": False,
            }
        ]
    total = float(df["valor"].sum())
    desv = abs(total - 100.0)
    return [
        {
            "tabla": nombre,
            "grupo": "<total>",
            "suma_observada": round(total, 3),
            "desviacion": round(desv, 3),
            "ok": desv <= tol,
        }
    ]


def _check_long_group(
    nombre: str, df: pd.DataFrame, group_cols: tuple[str, ...], tol: float
) -> list[dict]:
    if "valor" not in df.columns or not all(c in df.columns for c in group_cols):
        return [
            {
                "tabla": nombre,
                "grupo": f"<faltan cols: valor o {group_cols}>",
                "suma_observada": float("nan"),
                "desviacion": float("nan"),
                "ok": False,
            }
        ]
    rows: list[dict] = []
    for vals, sub in df.groupby(list(group_cols), dropna=False):
        total = float(sub["valor"].sum())
        desv = abs(total - 100.0)
        label = vals if not isinstance(vals, tuple) else " | ".join(str(v) for v in vals)
        rows.append(
            {
                "tabla": nombre,
                "grupo": str(label),
                "suma_observada": round(total, 3),
                "desviacion": round(desv, 3),
                "ok": desv <= tol,
            }
        )
    return rows


def _check_pivot_row(nombre: str, df: pd.DataFrame, tol: float) -> list[dict]:
    """Suma de cada fila (sobre columnas numéricas) debe ser 100."""
    num = df.select_dtypes(include="number")
    if num.empty:
        return [
            {
                "tabla": nombre,
                "grupo": "<sin columnas numéricas>",
                "suma_observada": float("nan"),
                "desviacion": float("nan"),
                "ok": False,
            }
        ]
    rows: list[dict] = []
    for idx, valor in num.sum(axis=1).items():
        total = float(valor)
        desv = abs(total - 100.0)
        rows.append(
            {
                "tabla": nombre,
                "grupo": f"fila_{idx}",
                "suma_observada": round(total, 3),
                "desviacion": round(desv, 3),
                "ok": desv <= tol,
            }
        )
    return rows


def resumen_validacion(diag: pd.DataFrame) -> dict[str, int | float]:
    """Resumen ejecutivo del DataFrame de diagnóstico."""
    if diag.empty:
        return {"n_filas": 0, "n_ok": 0, "n_fallidas": 0, "desviacion_max": 0.0}
    return {
        "n_filas": len(diag),
        "n_ok": int(diag["ok"].sum()),
        "n_fallidas": int((~diag["ok"]).sum()),
        "desviacion_max": float(diag["desviacion"].max(skipna=True) or 0.0),
    }


__all__ = ["CLOSURE_SPECS", "resumen_validacion", "verificar_cierres_100"]
