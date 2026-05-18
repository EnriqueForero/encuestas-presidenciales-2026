# ── 11.5 Barras 100% apiladas (edad, género, región) ─────────────────
from encuestas_lib.viz.charts.step11 import chart_stacked_bar

fig_edad = chart_stacked_bar(
    tablas, tabla_key="voto_por_edad", dim_col="edad_grupo",
    titulo="Intención de voto por edad",
    subtitle="Barras 100% apiladas · Grupos etarios",
    esconder_indecisos=False, height=380,
)
FIGURAS["05a_voto_edad"] = fig_edad
fig_edad.show()

fig_genero = chart_stacked_bar(
    tablas, tabla_key="voto_por_genero", dim_col="sexo",
    titulo="Intención de voto por género",
    subtitle="Barras 100% apiladas",
    esconder_indecisos=False, height=320,
)
FIGURAS["05b_voto_genero"] = fig_genero
fig_genero.show()

fig_region = chart_stacked_bar(
    tablas, tabla_key="voto_por_region", dim_col="region",
    titulo="Intención de voto por región",
    subtitle="Barras 100% apiladas · 9 regiones",
    esconder_indecisos=False, height=520,
)
FIGURAS["05c_voto_region"] = fig_region
fig_region.show()
