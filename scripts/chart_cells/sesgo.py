# 11.5 — Sesgo demográfico por encuestadora
def _sesgo_chart(tabla_key, titulo, fig_name, figsize=(11,4)):
    if tabla_key not in tablas: print(f"Tabla '{tabla_key}' no disponible"); return
    t = tablas[tabla_key].copy()
    dim_col = t.select_dtypes("object").columns[0]
    encuestadoras = [col for col in t.columns if col != dim_col]
    cats = t[dim_col].tolist()
    x = np.arange(len(cats)); width = 0.8 / max(len(encuestadoras), 1)
    colores_e = ["#1B4F9A","#D4890A","#7B1E3C","#2E7D4F","#5B3E8A"]
    fig, ax = plt.subplots(figsize=figsize)
    for i, enc in enumerate(encuestadoras):
        vals = t[enc].values.astype(float)
        ax.bar(x + i*width - (len(encuestadoras)-1)*width/2,
               vals, width*0.85, color=colores_e[i % len(colores_e)],
               label=enc, alpha=0.85)
    ax.axhline(0, color="black", lw=1)
    ax.set_xticks(x); ax.set_xticklabels(cats, rotation=15, ha="right")
    ax.set_ylabel("Diferencia en pp vs promedio del resto")
    ax.set_title(titulo, fontsize=13, fontweight="bold")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v,_: f"{v:+.0f}pp"))
    ax.legend(loc="upper right", fontsize=8)
    plt.tight_layout()
    plt.savefig(FIG_DIR / fig_name, bbox_inches="tight", dpi=150)
    plt.show()

_sesgo_chart("sesgo_edad",  "Sesgo por encuestadora — Edad\n(+pp = sobreestima ese grupo)",   "11_5a_sesgo_edad.png")
_sesgo_chart("sesgo_genero","Sesgo por encuestadora — Género\n(+pp = sobreestima ese grupo)", "11_5b_sesgo_genero.png")
