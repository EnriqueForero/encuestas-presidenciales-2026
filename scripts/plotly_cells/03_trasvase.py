# ── 11.3 Trasvase de la derecha (serie temporal) ─────────────────────
from encuestas_lib.viz.charts.step11 import chart_trasvase_derecha

fig_tr = chart_trasvase_derecha(df, tablas)
FIGURAS["03_trasvase"] = fig_tr
fig_tr.show()
