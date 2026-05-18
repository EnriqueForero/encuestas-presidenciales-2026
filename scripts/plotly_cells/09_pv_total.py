# ── 11.9 Primera vuelta total + indecisos ────────────────────────────
from encuestas_lib.viz.charts.step11 import chart_primera_vuelta_total

fig_pv = chart_primera_vuelta_total(tablas)
FIGURAS["09_pv_total"] = fig_pv
fig_pv.show()
