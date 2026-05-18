# ── 11.4 Perfil de indecisos ─────────────────────────────────────────
from encuestas_lib.viz.charts.step11 import chart_perfil_indecisos

fig_ind = chart_perfil_indecisos(tablas)
FIGURAS["04_indecisos"] = fig_ind
fig_ind.show()
