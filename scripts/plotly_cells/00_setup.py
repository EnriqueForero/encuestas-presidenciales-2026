# ══════════════════════════════════════════════════════════════════════
#  Step 11 · Setup — Plotly interactivo
# ══════════════════════════════════════════════════════════════════════
#
# Esta celda registra el template visual ``lsv`` y prepara los handles
# globales que las demás celdas de Step 11 esperan en el notebook.
# La lógica vive en ``encuestas_lib.viz`` para que sea testable.
# ──────────────────────────────────────────────────────────────────────
from collections import OrderedDict
from pathlib import Path

import plotly.graph_objects as go

from encuestas_lib.viz import (
    INDECISOS_CATS, LAYOUT_BASE, PALETA, c, hex_to_rgba, register_template,
)

# Activar template y dejarlo como default (resuelve el TypeError 'yaxis duplicado')
register_template()

# ── Helpers de candidatos (derivados del dict ``tablas`` que produce el pipeline) ──
TOP5 = (
    tablas["primera_vuelta_total"]
    .nlargest(5, "valor")["primera_vuelta"]
    .tolist()
)
ALL_CANDS = [
    cd for cd in tablas["primera_vuelta_total"]["primera_vuelta"].tolist()
    if cd not in INDECISOS_CATS
]
ORDEN_PV = ALL_CANDS + [
    cd for cd in tablas["primera_vuelta_total"]["primera_vuelta"].tolist()
    if cd in INDECISOS_CATS
]

# ── Directorio de salida de gráficas ──
FIG_DIR = Path(WORKSPACE) / "data" / "outputs" / "graficas"
FIG_DIR.mkdir(parents=True, exist_ok=True)

# Dict ordenado de figuras (alimenta el dashboard HTML al final)
FIGURAS: "OrderedDict[str, go.Figure]" = OrderedDict()

print("✅ Setup Plotly listo")
print(f"   Top 5 candidatos : {TOP5}")
print(f"   Guardando en     : {FIG_DIR}")
