# 11.6 — Votantes de Cepeda que aprueban a Petro
t = tablas.get("voto_vs_aprobacion")
if t is not None and "primera_vuelta" in t.columns:
    cep = t[t["primera_vuelta"] == "Iván Cepeda"]
    cats_apro = [ca for ca in ["Aprueba","Regular","Desaprueba","NS/NR"] if ca in cep.columns]
    if not cep.empty and cats_apro:
        vals = [float(cep[ca].iloc[0]) for ca in cats_apro]
        col_map = {"Aprueba":"#1B4F9A","Regular":"#A0C4E8","Desaprueba":"#D4890A","NS/NR":"#C8C8C8"}
        fig, ax = plt.subplots(figsize=(10, 2.5))
        left = 0
        for cat, v in zip(cats_apro, vals):
            ax.barh(["Votantes\nde Cepeda"], [v], left=left,
                    color=col_map.get(cat,"#999"), edgecolor="white", linewidth=0.5, height=0.45, label=cat)
            if v >= 5:
                ax.text(left + v/2, 0, f"{cat}\n{v:.0f}%", ha="center", va="center",
                        color="white", fontsize=9, fontweight="bold")
            left += v
        ax.set_xlim(0, 102)
        ax.set_title("¿Cuántos votantes de Cepeda aprueban a Petro?", fontsize=12, fontweight="bold")
        ax.set_xlabel("Porcentaje (%)")
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x,_: f"{x:.0f}%"))
        ax.set_yticks([])
        handles = [mpatches.Patch(color=col_map.get(ca,"#999"), label=ca) for ca in cats_apro]
        ax.legend(handles=handles, loc="lower right", fontsize=9)
        plt.tight_layout()
        plt.savefig(FIG_DIR / "11_6_cepeda_aprueba_petro.png", bbox_inches="tight", dpi=150)
        plt.show()
