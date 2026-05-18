# ── 12.1 Trasvase del centro: Fajardo · Claudia · Botero · Barreras ──
# UN solo Figure con los DOS escenarios apilados (esc. A y esc. B), leyenda
# compartida, benchmarks doc. forense anotados fuera del área. Mejora
# estética v0.2.4 sobre la doble llamada que producía leyenda flotante.
#
# Parámetros centralizados en ``encuestas_lib.viz.charts.step12``.
from encuestas_lib.viz.charts.step12 import (
    CANDS_CENTRO_DOC,
    chart_trasvase_centro_doble,
)

fig_trasvase = chart_trasvase_centro_doble(
    tablas,
    sv_col_keys=(
        "transfer_sv_cepeda_vs_espriella",
        "transfer_sv_cepeda_vs_valencia",
    ),
    subtitles=(
        "Escenario A: Cepeda vs Espriella",
        "Escenario B: Cepeda vs Valencia",
    ),
    candidato_a="Iván Cepeda",
    cands_centro=CANDS_CENTRO_DOC,
)
FIGURAS12["12_01_trasvase_centro"] = fig_trasvase
fig_trasvase.show()
