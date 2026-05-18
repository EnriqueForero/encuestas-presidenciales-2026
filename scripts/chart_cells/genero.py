# 11.7 — Intención de voto por género
_stacked_h("voto_por_genero","sexo",orden_pv,
           "Intención de voto por género (con indecisos)","11_7a_genero_con_ind.png",False,(13,3.5))
_stacked_h("voto_por_genero","sexo",orden_pv,
           "Intención de voto por género (esconder indecisos)","11_7b_genero_sin_ind.png",True,(13,3.5))

# Composición H/M de cada candidato
t_gc = tablas.get("genero_por_candidato_top4")
if t_gc is not None:
    dim_col_gc = t_gc.select_dtypes("object").columns[0]
    cand_cols = [col for col in t_gc.columns if col != dim_col_gc and col not in INDECISOS_CATS]
    if cand_cols:
        x = np.arange(len(cand_cols)); width = 0.38
        h_row = t_gc[t_gc[dim_col_gc]=="Hombre"]
        m_row = t_gc[t_gc[dim_col_gc]=="Mujer"]
        fig, ax = plt.subplots(figsize=(10, 4))
        if not h_row.empty:
            ax.bar(x - width/2, [float(h_row.iloc[0][col]) for col in cand_cols],
                   width, label="Hombre", color="#4A90D9", edgecolor="white")
        if not m_row.empty:
            ax.bar(x + width/2, [float(m_row.iloc[0][col]) for col in cand_cols],
                   width, label="Mujer",  color="#E87A8C", edgecolor="white")
        ax.set_xticks(x); ax.set_xticklabels([col[:22] for col in cand_cols], rotation=20, ha="right")
        ax.set_ylabel("% de los votantes"); ax.set_ylim(0, 100)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v,_: f"{v:.0f}%"))
        ax.set_title("Composición por género de cada candidato\n"
                     "De cada 100 votantes, % que son Hombre/Mujer", fontsize=12, fontweight="bold")
        ax.legend()
        plt.tight_layout()
        plt.savefig(FIG_DIR / "11_7c_composicion_genero.png", bbox_inches="tight", dpi=150)
        plt.show()
