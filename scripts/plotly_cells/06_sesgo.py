# ── 11.6 Sesgo demográfico por encuestadora ────────────────────────────
from encuestas_lib.viz.charts.step11 import chart_sesgo_demografico

fig_se1 = chart_sesgo_demografico(
    tablas, tabla_key="sesgo_edad",
    titulo="Sesgo demográfico por encuestadora — Edad",
    subtitle="+pp = sobreestima ese grupo etario · −pp = subestima",
)
FIGURAS["06a_sesgo_edad"] = fig_se1
fig_se1.show()

fig_se2 = chart_sesgo_demografico(
    tablas, tabla_key="sesgo_genero",
    titulo="Sesgo demográfico por encuestadora — Género",
    subtitle="+pp = sobreestima ese género · −pp = subestima",
)
FIGURAS["06b_sesgo_genero"] = fig_se2
fig_se2.show()
