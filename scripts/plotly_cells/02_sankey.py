# ── 11.2 Sankey PV → SV (dos matchups) ─────────────────────────────
from encuestas_lib.viz.charts.step11 import chart_sankey_pv_sv

fig_sv1 = chart_sankey_pv_sv(
    tablas,
    tabla_key="transfer_sv_cepeda_vs_valencia",
    sv_col="sv_cepeda_vs_valencia",
    titulo="Movimiento de votos PV → SV · Escenario Cepeda vs Valencia",
    subtitle=(
        "Cada flujo = (% en PV) × (% transferencia a SV). "
        "Hover para ver valores exactos."
    ),
)
FIGURAS["02a_sankey_cepeda_valencia"] = fig_sv1
fig_sv1.show()

fig_sv2 = chart_sankey_pv_sv(
    tablas,
    tabla_key="transfer_sv_cepeda_vs_espriella",
    sv_col="sv_cepeda_vs_espriella",
    titulo="Movimiento de votos PV → SV · Escenario Cepeda vs Espriella",
    subtitle=(
        "Cada flujo = (% en PV) × (% transferencia a SV). "
        "Hover para ver valores exactos."
    ),
)
FIGURAS["02b_sankey_cepeda_espriella"] = fig_sv2
fig_sv2.show()
