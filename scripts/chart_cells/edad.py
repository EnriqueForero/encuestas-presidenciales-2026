# 11.4 — Intención de voto por edad (100% apilado)
def _stacked_h(tabla_key, dim_col, cands_orden, titulo, fig_name,
               esconder_indecisos=False, figsize=(13, 4)):
    if tabla_key not in tablas:
        print(f"Tabla '{tabla_key}' no disponible"); return
    t = tablas[tabla_key].copy()
    cands_disp = [cd for cd in cands_orden if cd in t.columns]
    if not cands_disp: return
    if esconder_indecisos:
        cands_use = [cd for cd in cands_disp if cd not in INDECISOS_CATS]
        totales = t[cands_use].sum(axis=1)
        df_p = t[cands_use].div(totales, axis=0).mul(100)
    else:
        cands_use = cands_disp
        df_p = t[cands_use].copy()
    dims = t[dim_col].tolist()
    fig, ax = plt.subplots(figsize=figsize)
    lefts = np.zeros(len(dims))
    for cand in cands_use:
        vals = df_p[cand].values
        bars = ax.barh(dims, vals, left=lefts,
                       color=c(cand), edgecolor="white", linewidth=0.4, height=0.55)
        for bar, v, lft in zip(bars, vals, lefts):
            if v >= 7:
                ax.text(lft + v/2, bar.get_y() + bar.get_height()/2,
                        f"{v:.0f}%", ha="center", va="center",
                        fontsize=8, color="white", fontweight="bold")
        lefts += vals
    ax.set_xlim(0, 102); ax.set_xlabel("Porcentaje (%)")
    ax.set_title(titulo, fontsize=13, fontweight="bold")
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x,_: f"{x:.0f}%"))
    handles = [mpatches.Patch(color=c(cd), label=cd)
               for cd in cands_use if df_p[cd].max() > 1]
    ax.legend(handles=handles, bbox_to_anchor=(1.01,1), loc="upper left", fontsize=7.5)
    plt.tight_layout()
    plt.savefig(FIG_DIR / fig_name, bbox_inches="tight", dpi=150)
    plt.show()

orden_pv = ALL_CANDS + list(INDECISOS_CATS)
_stacked_h("voto_por_edad","edad_grupo",orden_pv,
           "Intención de voto por edad (con indecisos)","11_4a_voto_edad_con_ind.png",False,(13,4))
_stacked_h("voto_por_edad","edad_grupo",orden_pv,
           "Intención de voto por edad (esconder indecisos)","11_4b_voto_edad_sin_ind.png",True,(13,4))
