"""Actualiza notebooks/00_run_full_pipeline.ipynb reemplazando las celdas
Step 11 (38-58) y Step 12 (61-79) con las versiones delgadas de
``scripts/plotly_cells/`` y ``scripts/step12_cells/``.

Idempotente: leer un script, sobreescribir el ``source`` de la celda destino,
limpiar ``outputs`` y ``execution_count``.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NB_PATH = ROOT / "notebooks" / "00_run_full_pipeline.ipynb"
P_DIR = ROOT / "scripts" / "plotly_cells"
S12_DIR = ROOT / "scripts" / "step12_cells"

# Mapeo: cell_index → script file
MAPPING: dict[int, Path] = {
    38: P_DIR / "00_setup.py",
    40: P_DIR / "01_tendencia.py",
    42: P_DIR / "02_sankey.py",
    44: P_DIR / "03_trasvase.py",
    46: P_DIR / "04_indecisos.py",
    48: P_DIR / "05_stacked.py",
    50: P_DIR / "06_sesgo.py",
    52: P_DIR / "07_petro.py",
    54: P_DIR / "08_genero_comp.py",
    56: P_DIR / "09_pv_total.py",
    58: P_DIR / "10_export_html.py",
    61: S12_DIR / "00_setup12.py",
    63: S12_DIR / "01_transfer_centro.py",
    65: S12_DIR / "02_monte_carlo.py",
    67: S12_DIR / "03_sensibilidad.py",
    69: S12_DIR / "04_polymarket.py",
    71: S12_DIR / "05_techo_rechazo.py",
    73: S12_DIR / "06_voto_region_petrismo.py",
    75: S12_DIR / "07_abstension_edad.py",
    77: S12_DIR / "08_panel_ejecutivo.py",
    79: S12_DIR / "09_export12.py",
}


def _src_a_lineas_jupyter(path: Path) -> list[str]:
    """Leer un .py y devolverlo como lista de líneas con \\n final."""
    txt = path.read_text(encoding="utf-8")
    lineas = txt.splitlines(keepends=True)
    # Asegurar \n al final de la última línea (convenio Jupyter)
    if lineas and not lineas[-1].endswith("\n"):
        lineas[-1] = lineas[-1] + "\n"
    return lineas


def main() -> None:
    nb = json.loads(NB_PATH.read_text(encoding="utf-8"))
    n_cells = len(nb["cells"])

    actualizadas: list[int] = []
    for idx, script in MAPPING.items():
        if idx >= n_cells:
            print(f"⚠ Celda {idx} fuera de rango ({n_cells} celdas).  Saltada.")
            continue
        cell = nb["cells"][idx]
        if cell["cell_type"] != "code":
            print(f"⚠ Celda {idx} no es code (es {cell['cell_type']!r}).  Saltada.")
            continue
        if not script.exists():
            print(f"⚠ Script {script.name!r} no existe.  Saltada.")
            continue
        cell["source"] = _src_a_lineas_jupyter(script)
        cell["outputs"] = []
        cell["execution_count"] = None
        actualizadas.append(idx)

    NB_PATH.write_text(
        json.dumps(nb, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"✅ Notebook actualizado: {len(actualizadas)} celdas")
    print(f"   Índices: {actualizadas}")
    print(f"   Archivo: {NB_PATH}")


if __name__ == "__main__":
    main()
