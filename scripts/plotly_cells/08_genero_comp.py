# ── 11.8 Composición por género de cada candidato ─────────────────────
from encuestas_lib.viz.charts.step11 import chart_composicion_genero

fig_gc = chart_composicion_genero(tablas)
FIGURAS["08_genero_composicion"] = fig_gc
fig_gc.show()
