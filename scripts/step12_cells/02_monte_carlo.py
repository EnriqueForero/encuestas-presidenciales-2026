# ── 12.2 Simulación Monte Carlo de segunda vuelta ────────────────────
# Parámetros centralizados en ``encuestas_lib.viz.charts.step12.MC_PARAMS_DOC``.
# Para cambiar n_iter o seed: editar SOLO ese módulo.
from encuestas_lib.viz.charts.step12 import MC_PARAMS_DOC, chart_monte_carlo

print(
    f"⏳ Corriendo simulaciones Monte Carlo "
    f"({MC_PARAMS_DOC.n_iter:,} iter. × 2 escenarios, seed={MC_PARAMS_DOC.seed})…"
)

res_A, df_iters_A = simular_segunda_vuelta(
    PESOS_PV_DOC, MATRIZ_A,
    candidato_a="Iván Cepeda", candidato_b="Abelardo de la Espriella",
    n_iter=MC_PARAMS_DOC.n_iter, seed=MC_PARAMS_DOC.seed,
)
res_B, df_iters_B = simular_segunda_vuelta(
    PESOS_PV_DOC, MATRIZ_B,
    candidato_a="Iván Cepeda", candidato_b="Paloma Valencia",
    n_iter=MC_PARAMS_DOC.n_iter, seed=MC_PARAMS_DOC.seed,
)

print(f"\n📊 Escenario A — {res_A.candidato_a} vs {res_A.candidato_b}")
print(f"   Cepeda    : {res_A.media_a:.1f}%  "
      f"IC80: {res_A.ic80_a[0]:.1f}–{res_A.ic80_a[1]:.1f}%")
print(f"   Espriella : {res_A.media_b:.1f}%  "
      f"IC80: {res_A.ic80_b[0]:.1f}–{res_A.ic80_b[1]:.1f}%")
print(f"   P(Cepeda gana)    : {res_A.prob_a_gana*100:.1f}%")
print(f"   P(Espriella gana) : {res_A.prob_b_gana*100:.1f}%")
print(f"   P(Empate técnico <2pp): {res_A.prob_empate_tecnico*100:.1f}%")

print(f"\n📊 Escenario B — {res_B.candidato_a} vs {res_B.candidato_b}")
print(f"   Cepeda  : {res_B.media_a:.1f}%  "
      f"IC80: {res_B.ic80_a[0]:.1f}–{res_B.ic80_a[1]:.1f}%")
print(f"   Valencia: {res_B.media_b:.1f}%  "
      f"IC80: {res_B.ic80_b[0]:.1f}–{res_B.ic80_b[1]:.1f}%")
print(f"   P(Cepeda gana)   : {res_B.prob_a_gana*100:.1f}%")
print(f"   P(Valencia gana) : {res_B.prob_b_gana*100:.1f}%")

fig_mc = chart_monte_carlo(
    df_iters_A, df_iters_B, res_A, res_B,
    cand_b_name_a="Abelardo de la Espriella",
    cand_b_name_b="Paloma Valencia",
)
FIGURAS12["12_02_monte_carlo"] = fig_mc
fig_mc.show()
