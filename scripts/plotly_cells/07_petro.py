# ── 11.7 Petrismo: votantes de Cepeda que aprueban a Petro ───────────
from encuestas_lib.viz.charts.step11 import chart_petrismo_cepeda

fig_petro = chart_petrismo_cepeda(tablas, candidato="Iván Cepeda")
FIGURAS["07_petro"] = fig_petro
fig_petro.show()
