# 11.2 — Trasvase de la derecha (serie temporal)
def _trasvase_por_fecha(df_full, sv_col, pv_cand, sv_target):
    inds = {"NS/NR","Ninguno","Voto en blanco","No votaría","No sé"}
    rows = []
    for (enc, fecha), grp in df_full.groupby(["encuestadora","fecha"]):
        if sv_col not in grp.columns: continue
        sub = grp[grp["primera_vuelta"] == pv_cand]
        if sub.empty: continue
        dec = sub[~sub[sv_col].isin(inds)]
        if dec.empty: continue
        tf = dec["factor"].sum()
        sf = dec[dec[sv_col] == sv_target]["factor"].sum()
        if tf > 0:
            rows.append({"fecha": pd.Timestamp(fecha), "pct": sf/tf*100})
    return pd.DataFrame(rows).sort_values("fecha") if rows else pd.DataFrame()

def _trasvase_otros(df_full, sv_col, sv_target, otros):
    inds = {"NS/NR","Ninguno","Voto en blanco","No votaría","No sé"}
    rows = []
    for (enc, fecha), grp in df_full.groupby(["encuestadora","fecha"]):
        if sv_col not in grp.columns: continue
        sub = grp[grp["primera_vuelta"].isin(otros)]
        if sub.empty: continue
        dec = sub[~sub[sv_col].isin(inds)]
        if dec.empty: continue
        tf = dec["factor"].sum()
        sf = dec[dec[sv_col] == sv_target]["factor"].sum()
        if tf > 0:
            rows.append({"fecha": pd.Timestamp(fecha), "pct": sf/tf*100})
    return pd.DataFrame(rows).sort_values("fecha") if rows else pd.DataFrame()

otros_cands = [cd for cd in ALL_CANDS
               if cd not in {"Iván Cepeda","Abelardo de la Espriella","Paloma Valencia"}]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 4.5))
fig.suptitle("Trasvase en segunda vuelta (excl. indecisos SV)", fontsize=13, fontweight="bold")

for serie, lbl, col, mk in [
    (_trasvase_por_fecha(df, "sv_cepeda_vs_valencia",  "Abelardo de la Espriella", "Paloma Valencia"),
     "Paloma recibe de Abelardo", c("Paloma Valencia"), "o"),
    (_trasvase_por_fecha(df, "sv_cepeda_vs_espriella", "Paloma Valencia", "Abelardo de la Espriella"),
     "Abelardo recibe de Paloma", c("Abelardo de la Espriella"), "s"),
]:
    if not serie.empty:
        ax1.plot(serie["fecha"], serie["pct"], marker=mk, lw=2, color=col, label=lbl, ms=8)
        last = serie.iloc[-1]
        ax1.annotate(f'{last["pct"]:.0f}%', (last["fecha"], last["pct"]),
                     textcoords="offset points", xytext=(7,0), fontsize=9, color=col, fontweight="bold")

ax1.set_ylim(0, 105); ax1.set_ylabel("% de trasvase")
ax1.set_title("Trasvase entre candidatos de derecha")
ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v,_: f"{v:.0f}%"))
ax1.legend(loc="lower left")

for serie, lbl, col, mk in [
    (_trasvase_otros(df, "sv_cepeda_vs_valencia",  "Paloma Valencia",          otros_cands), "Paloma · otros", c("Paloma Valencia"), "o"),
    (_trasvase_otros(df, "sv_cepeda_vs_espriella", "Abelardo de la Espriella", otros_cands), "Abelardo · otros", c("Abelardo de la Espriella"), "s"),
]:
    if not serie.empty:
        ax2.plot(serie["fecha"], serie["pct"], marker=mk, lw=2, color=col, label=lbl, ms=8)
        last = serie.iloc[-1]
        ax2.annotate(f'{last["pct"]:.0f}%', (last["fecha"], last["pct"]),
                     textcoords="offset points", xytext=(7,0), fontsize=9, color=col, fontweight="bold")

ax2.set_ylim(0, 105); ax2.set_ylabel("% de trasvase")
ax2.set_title("Trasvase desde otros sectores")
ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v,_: f"{v:.0f}%"))
ax2.legend(loc="lower left")

fig.autofmt_xdate()
plt.tight_layout()
plt.savefig(FIG_DIR / "11_2_trasvase_tiempo.png", bbox_inches="tight", dpi=150)
plt.show()
