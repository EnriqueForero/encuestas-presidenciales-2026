# ── 12.9 Exportar todas las figuras (Step 11 + Step 12) al dashboard ─
from encuestas_lib.viz.dashboard import (
    SECCIONES_STEP11, SECCIONES_STEP12, export_dashboard,
)

# Combinar Step 11 + Step 12 (idempotente, sobrescribe el archivo HTML)
try:
    todas_figuras = {**FIGURAS, **FIGURAS12}
    secciones_11 = SECCIONES_STEP11
except NameError:
    # Step 11 no se corrió en esta sesión: solo Step 12
    todas_figuras = dict(FIGURAS12)
    secciones_11 = ()

out_path = export_dashboard(
    figuras=todas_figuras,
    out_path=FIG_DIR / "dashboard_interactivo.html",
    secciones_step11=secciones_11,
    secciones_step12=SECCIONES_STEP12,
)
size_mb = out_path.stat().st_size / 1e6

print(f"✅ Dashboard actualizado: {out_path.name} ({size_mb:.2f} MB)")
try:
    print(f"   Step 11: {len(FIGURAS)} gráficas  |  Step 12: {len(FIGURAS12)} gráficas")
except NameError:
    print(f"   Step 12: {len(FIGURAS12)} gráficas (Step 11 no disponible)")
