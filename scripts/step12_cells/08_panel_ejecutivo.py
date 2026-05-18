# ── 12.8 Panel ejecutivo: escenarios finales ─────────────────────────
# Escenarios y probabilidades del documento forense centralizados en
# ``encuestas_lib.viz.charts.step12.ESCENARIOS_DOC``.
# Para tunearlos: editar SOLO ese módulo.
from encuestas_lib.viz.charts.step12 import (
    chart_panel_ejecutivo,
    construir_escenarios_consolidados,
)

ESCENARIOS = construir_escenarios_consolidados(res_A, res_B)

fig_ej = chart_panel_ejecutivo(ESCENARIOS)
FIGURAS12["12_08_panel_ejecutivo"] = fig_ej
fig_ej.show()

print("\n📋 Resumen de probabilidades consolidadas:")
print(ESCENARIOS.to_string(index=False))
