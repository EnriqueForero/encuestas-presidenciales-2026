# ── 12.6 Voto Cepeda por región vs aprobación Petro ─────────────────
from encuestas_lib.viz.charts.step12 import chart_geografia_petrismo

fig_reg = chart_geografia_petrismo(tablas)
FIGURAS12["12_06_geografia_petrismo"] = fig_reg
fig_reg.show()
