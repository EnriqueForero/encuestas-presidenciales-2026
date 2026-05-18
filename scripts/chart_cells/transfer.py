# 11.1 — Movimiento PV→SV
def _transfer_flow(tabla_key, sv_col, matchup_label, pv_cands, ax):
    if tabla_key not in tablas:
        ax.set_visible(False); return
    t = tablas[tabla_key]
    if sv_col not in t.columns:
        ax.set_visible(False); return
    sv_opts  = [o for o in t[sv_col].dropna().unique() if o not in INDECISOS_CATS]
    sv_opts += [o for o in t[sv_col].dropna().unique() if o in INDECISOS_CATS]
    rows = []
    for pv_cand in pv_cands:
        sub = t[t["primera_vuelta"] == pv_cand]
        if sub.empty: continue
        row = {"pv": pv_cand}
        for opt in sv_opts:
            row[opt] = float(sub[sub[sv_col] == opt]["valor"].sum())
        rows.append(row)
    if not rows: ax.set_visible(False); return
    df_p = pd.DataFrame(rows).set_index("pv").fillna(0)
    lefts = np.zeros(len(df_p))
    for opt in sv_opts:
        if opt not in df_p.columns: continue
        vals = df_p[opt].values
        bars = ax.barh(df_p.index.tolist(), vals, left=lefts,
                       color=c(opt), edgecolor="white", linewidth=0.5, height=0.55)
        for bar, v, lft in zip(bars, vals, lefts):
            if v >= 8:
                ax.text(lft + v/2, bar.get_y() + bar.get_height()/2,
                        f"{v:.0f}%", ha="center", va="center",
                        fontsize=8, color="white", fontweight="bold")
        lefts += vals
    ax.set_xlim(0, 102)
    ax.set_title(matchup_label, fontsize=11, fontweight="bold", pad=8)
    ax.set_xlabel("Porcentaje (%)")
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.0f}%"))
    handles = [mpatches.Patch(color=c(o), label=o)
               for o in sv_opts if o in df_p.columns and df_p[o].max() > 1]
    ax.legend(handles=handles, loc="lower right", fontsize=7.5, ncol=2)

fig, axes = plt.subplots(1, 2, figsize=(15, 5))
fig.suptitle("Movimiento de votos PV → SV", fontsize=13, fontweight="bold", y=1.01)
PV_TOP = ["Iván Cepeda","Abelardo de la Espriella","Paloma Valencia",
          "Sergio Fajardo","Claudia López"]
_transfer_flow("transfer_sv_cepeda_vs_valencia",  "sv_cepeda_vs_valencia",
               "Escenario: Cepeda vs Valencia",  PV_TOP, axes[0])
_transfer_flow("transfer_sv_cepeda_vs_espriella", "sv_cepeda_vs_espriella",
               "Escenario: Cepeda vs Espriella", PV_TOP, axes[1])
plt.tight_layout()
plt.savefig(FIG_DIR / "11_1_movimiento_pv_sv.png", bbox_inches="tight", dpi=150)
plt.show()
