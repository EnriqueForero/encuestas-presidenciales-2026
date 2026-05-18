figuras = sorted(FIG_DIR.glob("*.png"))
print(f"\n📊 {len(figuras)} gráficas guardadas en {FIG_DIR}:")
for f in figuras:
    print(f"   {f.name:<52} {f.stat().st_size/1024:>6.1f} KB")
print("\n✅ Todas las gráficas del PDF La Silla Vacía replicadas.")
