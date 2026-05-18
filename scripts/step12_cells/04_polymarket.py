# ── 12.4 Polymarket vs encuestas vs modelo de transferencia ─────────
# Datos del documento forense (cifras del 16-17 may) centralizados en
# ``encuestas_lib.viz.charts.step12.POLYMARKET_SNAPSHOT_DOC``.
# Para actualizar snapshots: editar SOLO ese módulo.
from encuestas_lib.viz.charts.step12 import (
    chart_polymarket,
    construir_comparativo_polymarket,
)

COMPARATIVO = construir_comparativo_polymarket(res_A, res_B)

fig_pm = chart_polymarket(COMPARATIVO)
FIGURAS12["12_04_polymarket"] = fig_pm
fig_pm.show()
