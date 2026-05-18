# ── 12.7 Abstención diferencial y voto joven ─────────────────────────
from encuestas_lib.viz.charts.step12 import chart_voto_joven

fig_abs = chart_voto_joven(tablas)
FIGURAS12["12_07_voto_joven"] = fig_abs
fig_abs.show()
