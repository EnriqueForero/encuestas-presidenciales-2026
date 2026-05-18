# ── 12.5 Techo de rechazo por candidato ──────────────────────────────
# Rangos del documento forense centralizados en
# ``encuestas_lib.viz.charts.step12.TECHO_RECHAZO_DOC``.
# Para tunearlos: editar SOLO ese módulo.
from encuestas_lib.analysis.weighting import resolve_weights
from encuestas_lib.viz.charts.step12 import TECHO_RECHAZO_DOC, chart_techo_rechazo

t_rec = calcular_techo_rechazo(
    df, list(TECHO_RECHAZO_DOC.keys()),
    resolve_weights(config.weighting, config.surveys),
)
print("Techo de rechazo estimado desde microdatos:")
print(t_rec.to_string(index=False))

fig_tr = chart_techo_rechazo(t_rec, TECHO_RECHAZO_DOC)
FIGURAS12["12_05_techo_rechazo"] = fig_tr
fig_tr.show()
