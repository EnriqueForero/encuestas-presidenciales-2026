# ── 11.10 Exportar dashboard HTML interactivo ─────────────────────────
from encuestas_lib.viz.dashboard import SECCIONES_STEP11, export_dashboard

# En esta celda exportamos solo Step 11 — la celda 12.9 añade Step 12 al
# mismo archivo si está disponible.
out_path = export_dashboard(
    figuras=FIGURAS,
    out_path=FIG_DIR / "dashboard_interactivo.html",
    secciones_step11=SECCIONES_STEP11,
    secciones_step12=(),  # se completa en Step 12
)
size_mb = out_path.stat().st_size / 1e6

print("\n✅ Dashboard exportado correctamente")
print(f"   📄 Archivo : {out_path}")
print(f"   📦 Tamaño  : {size_mb:.2f} MB")
print(f"   📊 Gráficas: {len(FIGURAS)}")
print("\n💡 Para descargar: clic derecho en el archivo en el panel de Drive → Descargar")
