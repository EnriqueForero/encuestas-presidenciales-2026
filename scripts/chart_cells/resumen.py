# 11.9 — Resumen ejecutivo
fig = plt.figure(figsize=(16, 6))
fig.suptitle("Resumen ejecutivo — Intención de voto primera vuelta", fontsize=14, fontweight="bold")

ax1 = fig.add_subplot(1, 2, 1)
pv = tablas["primera_vuelta_total"].copy()
pv_dec = pv[~pv["primera_vuelta"].isin(INDECISOS_CATS)].sort_values("valor", ascending=True)
colors_bar = [c(cand) for cand in pv_dec["primera_vuelta"]]
bars = ax1.barh(pv_dec["primera_vuelta"], pv_dec["valor"], color=colors_bar, edgecolor="white", height=0.6)
for bar, v in zip(bars, pv_dec["valor"]):
    ax1.text(v + 0.3, bar.get_y() + bar.get_height()/2, f"{v:.1f}%", va="center", fontsize=8.5)
ax1.set_xlim(0, float(pv_dec["valor"].max()) * 1.25)
ax1.set_title("Intención de voto (% total respondentes)")
ax1.set_xlabel("Porcentaje (%)")
ax1.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x,_: f"{x:.0f}%"))

ax2 = fig.add_subplot(1, 2, 2)
trend = tablas.get("trend_primera_vuelta", pd.DataFrame())
if not trend.empty:
    for cand in TOP5:
        sub = trend[trend["primera_vuelta"] == cand].sort_values("fecha")
        if sub.empty: continue
        col_v = "valor_suavizado" if "valor_suavizado" in sub.columns else "valor_punto"
        ax2.plot(sub["fecha"], sub[col_v], lw=2.5, color=c(cand), label=cand[:20])
        last = sub.iloc[-1]
        ax2.annotate(f'{last[col_v]:.1f}%', (last["fecha"], last[col_v]),
                     textcoords="offset points", xytext=(5,0), fontsize=8, color=c(cand), fontweight="bold")
    ax2.set_ylabel("Intención de voto (%)")
    ax2.set_title("Tendencia temporal — Top 5 candidatos")
    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v,_: f"{v:.0f}%"))
    ax2.legend(fontsize=8)
    fig.autofmt_xdate()

plt.tight_layout()
plt.savefig(FIG_DIR / "11_9_resumen_ejecutivo.png", bbox_inches="tight", dpi=150)
plt.show()
