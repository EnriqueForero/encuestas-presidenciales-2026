# 11.3 — Perfil indecisos (edad / género / región)
fig, axes = plt.subplots(1, 3, figsize=(16, 4.5))
fig.suptitle("Perfil de los indecisos en primera vuelta", fontsize=13, fontweight="bold")
GRIS = "#6B7280"

for ax, tabla_key, titulo in [
    (axes[0], "indecisos_edad_grupo", "Por edad"),
    (axes[1], "indecisos_sexo",       "Por género"),
    (axes[2], "indecisos_region",     "Por región"),
]:
    t = tablas.get(tabla_key, pd.DataFrame())
    if t.empty: ax.set_visible(False); continue
    dim = t.columns[0]; val = t.columns[-1]
    ts = t.sort_values(val, ascending=True)
    bars = ax.barh(ts[dim], ts[val], color=GRIS, edgecolor="white", height=0.55)
    for bar, v in zip(bars, ts[val]):
        ax.text(v + 0.4, bar.get_y() + bar.get_height()/2,
                f"{v:.1f}%", va="center", fontsize=8.5)
    ax.set_xlim(0, float(ts[val].max()) * 1.3)
    ax.set_xlabel("Distribución (%)"); ax.set_title(titulo)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x,_: f"{x:.0f}%"))

plt.tight_layout()
plt.savefig(FIG_DIR / "11_3_indecisos_perfil.png", bbox_inches="tight", dpi=150)
plt.show()
