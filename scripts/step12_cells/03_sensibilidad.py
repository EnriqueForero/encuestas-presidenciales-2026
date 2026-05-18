# ── 12.3 Análisis de sensibilidad — swing factors ─────────────────────
# Los 3 swing factors (nombre, rango, n_puntos, n_iter_mc) están centralizados
# en ``encuestas_lib.viz.charts.step12.SWING_FACTORS_DOC``.
# Para tunearlos: editar SOLO ese módulo.
from encuestas_lib.viz.charts.step12 import SWING_FACTORS_DOC, chart_sensibilidad

print(f"⏳ Computando análisis de sensibilidad ({len(SWING_FACTORS_DOC)} swing factors)…")

# chart_sensibilidad espera exactamente 3 DataFrames (subplot_titles hardcoded).
# Si quieres más/menos factores, edita también la función en step12.py.
if len(SWING_FACTORS_DOC) != 3:
    raise ValueError(
        f"SWING_FACTORS_DOC tiene {len(SWING_FACTORS_DOC)} elementos; "
        "chart_sensibilidad requiere exactamente 3.  Edita step12.py."
    )

dfs_sens = []
for sf in SWING_FACTORS_DOC:
    df_s = sensibilidad_2v(
        PESOS_PV_DOC, MATRIZ_A,
        candidato_a="Iván Cepeda", candidato_b="Abelardo de la Espriella",
        param_name=sf.nombre,
        param_pv_cand=sf.pv_cand, param_destino=sf.destino,
        rango_param=(sf.rango_min, sf.rango_max),
        n_puntos=sf.n_puntos, n_iter_mc=sf.n_iter_mc,
    )
    dfs_sens.append(df_s)

fig_sens = chart_sensibilidad(*dfs_sens)
FIGURAS12["12_03_sensibilidad"] = fig_sens
fig_sens.show()
