# ── 12.1 Transferencia de voto: Fajardo y Claudia López ─────────────
# Parámetros centralizados en ``encuestas_lib.viz.charts.step12``.
# Para tunearlos: editar SOLO ese módulo.
from encuestas_lib.viz.charts.step12 import CANDS_CENTRO_DOC, chart_trasvase_centro

fig_tc1 = chart_trasvase_centro(
    tablas,
    sv_col_key="transfer_sv_cepeda_vs_espriella",
    titulo=(
        "Trasvase de votos del centro — Escenario Cepeda vs Espriella<br>"
        "¿A quién van los votantes de Fajardo, Claudia, Botero y Barreras?"
    ),
    candidato_a="Iván Cepeda",
    cands_centro=CANDS_CENTRO_DOC,
)
FIGURAS12["12_01a_trasvase_centro_escA"] = fig_tc1
fig_tc1.show()

fig_tc2 = chart_trasvase_centro(
    tablas,
    sv_col_key="transfer_sv_cepeda_vs_valencia",
    titulo=(
        "Trasvase de votos del centro — Escenario Cepeda vs Valencia<br>"
        "¿A quién van los votantes de Fajardo, Claudia, Botero y Barreras?"
    ),
    candidato_a="Iván Cepeda",
    cands_centro=CANDS_CENTRO_DOC,
)
FIGURAS12["12_01b_trasvase_centro_escB"] = fig_tc2
fig_tc2.show()
