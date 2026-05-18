# ── 11.1 Tendencia temporal top-5 ───────────────────────────────────
from encuestas_lib.viz.charts.step11 import chart_tendencia_temporal

fig = chart_tendencia_temporal(tablas, top=5)
FIGURAS["01_tendencia"] = fig
fig.show()
