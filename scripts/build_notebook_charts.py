"""Inyecta las celdas de visualización en el notebook."""
import json
from pathlib import Path

NB_PATH = Path("notebooks/00_run_full_pipeline.ipynb")

# ── helpers ──────────────────────────────────────────────────────────────────
def md(src): return {"cell_type":"markdown","metadata":{},"source":[src]}
def code(src): return {"cell_type":"code","execution_count":None,"metadata":{},"outputs":[],"source":[src]}

# ══════════════════════════════════════════════════════════════════════════════
SETUP = r"""
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from pathlib import Path

# ── Paleta de colores (aproxima colores del PDF La Silla Vacía) ──────────────
PALETA = {
    "Iván Cepeda":              "#7B1E3C",
    "Abelardo de la Espriella": "#D4890A",
    "Paloma Valencia":          "#1B4F9A",
    "Sergio Fajardo":           "#2E7D4F",
    "Claudia López":            "#1A7A7A",
    "Santiago Botero":          "#5B3E8A",
    "Roy Barreras":             "#A63D2F",
    "Carlos Caicedo":           "#7B3F00",
    "Miguel Uribe Londoño":     "#3A3A8A",
    "Mauricio Lizcano":         "#4D5E6F",
    "Luis Gilberto Murillo":    "#1D6B1D",
    "Sondra Macollins":         "#9B6B2A",
    "Clara López":              "#0A6B5A",
    "Otro candidato":           "#A0A0A0",
    "Voto en blanco":           "#C8C8C8",
    "Blanco":                   "#C8C8C8",
    "NS/NR":                    "#B8B8B8",
    "Ninguno":                  "#D0D0D0",
    "No votaría":               "#D8D8D8",
    "No sé":                    "#E0E0E0",
    "Indecisos":                "#B0B0B0",
}

def c(nombre): return PALETA.get(nombre, "#888888")

INDECISOS_CATS = {"NS/NR","Ninguno","Voto en blanco","No votaría","No sé","Otro candidato","Blanco"}

plt.rcParams.update({
    "figure.facecolor":    "white",
    "axes.facecolor":      "white",
    "axes.spines.top":     False,
    "axes.spines.right":   False,
    "axes.grid":           True,
    "grid.alpha":          0.25,
    "grid.linestyle":      "--",
    "font.family":         "DejaVu Sans",
    "axes.titlesize":      13,
    "axes.titleweight":    "bold",
    "axes.labelsize":      10,
    "xtick.labelsize":     9,
    "ytick.labelsize":     9,
    "legend.fontsize":     8,
    "legend.framealpha":   0.9,
    "figure.dpi":          130,
})

FIG_DIR = Path(WORKSPACE) / "data" / "outputs" / "graficas"
FIG_DIR.mkdir(parents=True, exist_ok=True)

TOP5 = tablas["primera_vuelta_total"].nlargest(5, "valor")["primera_vuelta"].tolist()
ALL_CANDS = [c for c in tablas["primera_vuelta_total"]["primera_vuelta"].tolist()
             if c not in INDECISOS_CATS]

print(f"✅ Setup gráficas listo  |  Guardando en: {FIG_DIR}")
print(f"   Top 5: {TOP5}")
""".strip()

# ── CHART 1: Movimiento PV→SV ─────────────────────────────────────────────────
CHART_TRANSFER = r"""
# ── Datos: transferencia PV→SV para los dos matchups principales ────────────
def _transfer_flow(tabla_key, sv_col, matchup_label, pv_cands_mostrar, ax):
    """Barras horizontales apiladas: para cada candidato de PV, cómo se distribuye su voto en SV."""
    if tabla_key not in tablas:
        ax.set_visible(False); return
    t = tablas[tabla_key]
    if sv_col not in t.columns:
        ax.set_visible(False); return

    # Ordenar opciones SV: primero candidatos, luego indecisos
    sv_opts = [o for o in t[sv_col].dropna().unique() if o not in INDECISOS_CATS]
    sv_opts += [o for o in t[sv_col].dropna().unique() if o in INDECISOS_CATS]

    rows = []
    for pv_cand in pv_cands_mostrar:
        sub = t[t["primera_vuelta"] == pv_cand]
        if sub.empty: continue
        total = sub["valor"].sum()
        if total == 0: continue
        row = {"pv": pv_cand}
        for opt in sv_opts:
            v = sub[sub[sv_col] == opt]["valor"].sum()
            row[opt] = v
        rows.append(row)
    if not rows:
        ax.set_visible(False); return

    df_plot = pd.DataFrame(rows).set_index("pv").fillna(0)
    labels_y = df_plot.index.tolist()
    lefts = np.zeros(len(labels_y))

    for opt in sv_opts:
        if opt not in df_plot.columns: continue
        vals = df_plot[opt].values
        color = c(opt)
        bars = ax.barh(labels_y, vals, left=lefts, color=color,
                       edgecolor="white", linewidth=0.5, height=0.55)
        # Etiqueta si segmento > 8pp
        for bar, v, lft in zip(bars, vals, lefts):
            if v >= 8:
                xpos = lft + v / 2
                ax.text(xpos, bar.get_y() + bar.get_height()/2,
                        f"{v:.0f}%", ha="center", va="center",
                        fontsize=8, color="white", fontweight="bold")
        lefts = lefts + vals

    ax.set_xlim(0, 102)
    ax.set_xlabel("Porcentaje (%)")
    ax.set_title(matchup_label, fontsize=11, fontweight="bold", pad=8)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x,_: f"{x:.0f}%"))

    # Leyenda solo con opciones presentes y > 1%
    handles = []
    for opt in sv_opts:
        if opt in df_plot.columns and df_plot[opt].max() > 1:
            handles.append(mpatches.Patch(color=c(opt), label=opt))
    ax.legend(handles=handles, loc="lower right", fontsize=7.5, ncol=2)

fig, axes = plt.subplots(1, 2, figsize=(15, 4.5))
fig.suptitle("Movimiento de votos entre primera y segunda vuelta\n"
             "Última ponderación", fontsize=13, fontweight="bold", y=1.02)

_transfer_flow(
    "transfer_sv_cepeda_vs_valencia",
    "sv_cepeda_vs_valencia",
    "Escenario: Cepeda vs Valencia",
    ["Iván Cepeda", "Abelardo de la Espriella", "Paloma Valencia",
     "Sergio Fajardo", "Claudia López"],
    axes[0],
)
_transfer_flow(
    "transfer_sv_cepeda_vs_espriella",
    "sv_cepeda_vs_espriella",
    "Escenario: Cepeda vs Espriella",
    ["Iván Cepeda", "Abelardo de la Espriella", "Paloma Valencia",
     "Sergio Fajardo", "Claudia López"],
    axes[1],
)

plt.tight_layout()
plt.savefig(FIG_DIR / "11_1_movimiento_pv_sv.png", bbox_inches="tight", dpi=150)
plt.show()
""".strip()

# ── CHART 2: Trasvase de la derecha (tiempo) ──────────────────────────────────
CHART_TRASVASE = r"""
from encuestas_lib.analysis import resolve_weights

def _trasvase_por_fecha(df_full, sv_col, pv_cand, sv_cand_target):
    """% de pv_cand que iría a sv_cand_target (excl. indecisos SV) por fecha."""
    indecisos_sv = {"NS/NR","Ninguno","Voto en blanco","No votaría","No sé"}
    rows = []
    for (enc, fecha), grp in df_full.groupby(["encuestadora","fecha"]):
        if sv_col not in grp.columns: continue
        sub = grp[grp["primera_vuelta"] == pv_cand]
        if sub.empty: continue
        decided = sub[~sub[sv_col].isin(indecisos_sv)]
        if decided.empty: continue
        total_f = decided["factor"].sum()
        target_f = decided[decided[sv_col] == sv_cand_target]["factor"].sum()
        if total_f > 0:
            rows.append({"fecha": pd.Timestamp(fecha), "pct": target_f/total_f*100,
                         "encuestadora": enc})
    return pd.DataFrame(rows).sort_values("fecha") if rows else pd.DataFrame()

fig, axes = plt.subplots(1, 2, figsize=(14, 4.5))
fig.suptitle("Trasvase en segunda vuelta (excl. indecisos SV)", fontsize=13, fontweight="bold")

# ── Panel A: Paloma recibe de Abelardo / Abelardo recibe de Paloma ───────────
ax = axes[0]
paloma_de_abe = _trasvase_por_fecha(df, "sv_cepeda_vs_valencia",
                                     "Abelardo de la Espriella", "Paloma Valencia")
abe_de_paloma = _trasvase_por_fecha(df, "sv_cepeda_vs_espriella",
                                     "Paloma Valencia", "Abelardo de la Espriella")

for serie, lbl, col, marker in [
    (paloma_de_abe, "Paloma recibe de Abelardo", c("Paloma Valencia"), "o"),
    (abe_de_paloma, "Abelardo recibe de Paloma", c("Abelardo de la Espriella"), "s"),
]:
    if not serie.empty:
        ax.plot(serie["fecha"], serie["pct"], marker=marker, linewidth=2,
                color=col, label=lbl, markersize=8)
        # Anotar último punto
        last = serie.iloc[-1]
        ax.annotate(f'{last["pct"]:.0f}%', (last["fecha"], last["pct"]),
                    textcoords="offset points", xytext=(8,0), fontsize=9,
                    color=col, fontweight="bold")

ax.set_ylabel("% de trasvase"); ax.set_ylim(0, 105)
ax.set_title("Trasvase entre candidatos de derecha")
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x,_: f"{x:.0f}%"))
ax.legend(loc="lower left")
fig.autofmt_xdate()

# ── Panel B: Trasvase desde otros sectores ───────────────────────────────────
ax2 = axes[1]
# Otros sectores = candidatos que NO son Cepeda, Abelardo, Paloma
otros_cands = [c_ for c_ in ALL_CANDS
               if c_ not in {"Iván Cepeda","Abelardo de la Espriella","Paloma Valencia"}]

def _trasvase_otros(df_full, sv_col, sv_cand_target, otros):
    indecisos_sv = {"NS/NR","Ninguno","Voto en blanco","No votaría","No sé"}
    rows = []
    for (enc, fecha), grp in df_full.groupby(["encuestadora","fecha"]):
        if sv_col not in grp.columns: continue
        sub = grp[grp["primera_vuelta"].isin(otros)]
        if sub.empty: continue
        decided = sub[~sub[sv_col].isin(indecisos_sv)]
        if decided.empty: continue
        total_f = decided["factor"].sum()
        target_f = decided[decided[sv_col] == sv_cand_target]["factor"].sum()
        if total_f > 0:
            rows.append({"fecha": pd.Timestamp(fecha), "pct": target_f/total_f*100})
    return pd.DataFrame(rows).sort_values("fecha") if rows else pd.DataFrame()

paloma_otros = _trasvase_otros(df, "sv_cepeda_vs_valencia",  "Paloma Valencia",  otros_cands)
abe_otros    = _trasvase_otros(df, "sv_cepeda_vs_espriella", "Abelardo de la Espriella", otros_cands)

for serie, lbl, col, marker in [
    (paloma_otros, "Paloma · otros sectores", c("Paloma Valencia"), "o"),
    (abe_otros,    "Abelardo · otros sectores", c("Abelardo de la Espriella"), "s"),
]:
    if not serie.empty:
        ax2.plot(serie["fecha"], serie["pct"], marker=marker, linewidth=2,
                 color=col, label=lbl, markersize=8)
        last = serie.iloc[-1]
        ax2.annotate(f'{last["pct"]:.0f}%', (last["fecha"], last["pct"]),
                     textcoords="offset points", xytext=(8,0), fontsize=9,
                     color=col, fontweight="bold")

ax2.set_ylabel("% de trasvase"); ax2.set_ylim(0, 105)
ax2.set_title("Trasvase desde otros sectores")
ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x,_: f"{x:.0f}%"))
ax2.legend(loc="lower left")
fig.autofmt_xdate()

plt.tight_layout()
plt.savefig(FIG_DIR / "11_2_trasvase_tiempo.png", bbox_inches="tight", dpi=150)
plt.show()
""".strip()

# ── CHART 3: Indecisos por edad / género / región ────────────────────────────
CHART_INDECISOS = r"""
fig, axes = plt.subplots(1, 3, figsize=(16, 4.5))
fig.suptitle("Perfil de los indecisos en primera vuelta", fontsize=13, fontweight="bold")

GRIS = "#6B7280"

# ── Panel A: Por edad ────────────────────────────────────────────────────────
ax = axes[0]
t = tablas.get("indecisos_edad_grupo", pd.DataFrame())
if not t.empty:
    col_edad = [c for c in t.columns if "edad" in c.lower()][0]
    col_val  = [c for c in t.columns if c != col_edad][0]
    t_s = t.sort_values(col_val, ascending=True)
    bars = ax.barh(t_s[col_edad], t_s[col_val], color=GRIS, edgecolor="white", height=0.5)
    for bar, v in zip(bars, t_s[col_val]):
        ax.text(v + 0.5, bar.get_y() + bar.get_height()/2,
                f"{v:.1f}%", va="center", fontsize=9)
    ax.set_xlim(0, max(t_s[col_val]) * 1.25)
    ax.set_xlabel("Distribución (%)"); ax.set_title("Por edad")
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x,_: f"{x:.0f}%"))

# ── Panel B: Por género ──────────────────────────────────────────────────────
ax = axes[1]
t = tablas.get("indecisos_sexo", pd.DataFrame())
if not t.empty:
    col_g = [c for c in t.columns if "sex" in c.lower() or "gen" in c.lower()][0]
    col_v = [c for c in t.columns if c != col_g][0]
    t_s = t.sort_values(col_v, ascending=True)
    bars = ax.barh(t_s[col_g], t_s[col_v], color=GRIS, edgecolor="white", height=0.5)
    for bar, v in zip(bars, t_s[col_v]):
        ax.text(v + 0.5, bar.get_y() + bar.get_height()/2,
                f"{v:.1f}%", va="center", fontsize=9)
    ax.set_xlim(0, max(t_s[col_v]) * 1.3)
    ax.set_xlabel("Distribución (%)"); ax.set_title("Por género")
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x,_: f"{x:.0f}%"))

# ── Panel C: Por región ──────────────────────────────────────────────────────
ax = axes[2]
t = tablas.get("indecisos_region", pd.DataFrame())
if not t.empty:
    col_r = [c for c in t.columns if "region" in c.lower()][0]
    col_v = [c for c in t.columns if c != col_r][0]
    t_s = t.sort_values(col_v, ascending=True)
    bars = ax.barh(t_s[col_r], t_s[col_v], color=GRIS, edgecolor="white", height=0.55)
    for bar, v in zip(bars, t_s[col_v]):
        ax.text(v + 0.2, bar.get_y() + bar.get_height()/2,
                f"{v:.1f}%", va="center", fontsize=8)
    ax.set_xlim(0, max(t_s[col_v]) * 1.3)
    ax.set_xlabel("Distribución (%)"); ax.set_title("Por región")
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x,_: f"{x:.0f}%"))

plt.tight_layout()
plt.savefig(FIG_DIR / "11_3_indecisos_perfil.png", bbox_inches="tight", dpi=150)
plt.show()
""".strip()

# ── CHART 4: Intención de voto por edad (100% apilado) ───────────────────────
CHART_EDAD = r"""
def _stacked_h(tabla_key, dim_col, cands_orden, titulo, fig_name,
               esconder_indecisos=False, figsize=(12, 4)):
    if tabla_key not in tablas:
        print(f"⚠ Tabla '{tabla_key}' no disponible"); return
    t = tablas[tabla_key].copy()
    cands_disp = [cd for cd in cands_orden if cd in t.columns]
    if not cands_disp: print("⚠ Sin candidatos disponibles"); return

    if esconder_indecisos:
        cands_use = [cd for cd in cands_disp if cd not in INDECISOS_CATS]
        totales = t[cands_use].sum(axis=1)
        df_pct = t[cands_use].div(totales, axis=0) * 100
    else:
        cands_use = cands_disp
        df_pct = t[cands_use].copy()

    dims = t[dim_col].tolist()
    fig, ax = plt.subplots(figsize=figsize)
    lefts = np.zeros(len(dims))

    for cand in cands_use:
        vals = df_pct[cand].values
        bars = ax.barh(dims, vals, left=lefts,
                       color=c(cand), edgecolor="white", linewidth=0.4, height=0.55)
        for bar, v, lft in zip(bars, vals, lefts):
            if v >= 7:
                ax.text(lft + v/2, bar.get_y() + bar.get_height()/2,
                        f"{v:.0f}%", ha="center", va="center",
                        fontsize=8, color="white", fontweight="bold")
        lefts = lefts + vals

    ax.set_xlim(0, 102)
    ax.set_title(titulo, fontsize=13, fontweight="bold")
    ax.set_xlabel("Porcentaje (%)")
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x,_: f"{x:.0f}%"))

    handles = [mpatches.Patch(color=c(cd), label=cd) for cd in cands_use if df_pct[cd].max() > 1]
    ax.legend(handles=handles, bbox_to_anchor=(1.01,1), loc="upper left",
              fontsize=7.5, framealpha=0.9)
    plt.tight_layout()
    plt.savefig(FIG_DIR / fig_name, bbox_inches="tight", dpi=150)
    plt.show()

# Orden canónico de candidatos (top por intención de voto + indecisos al final)
orden_pv = ALL_CANDS + list(INDECISOS_CATS)

_stacked_h(
    "voto_por_edad", "edad_grupo", orden_pv,
    "Intención de voto por edad\n(barras 100% apiladas, con indecisos)",
    "11_4a_voto_edad_con_indecisos.png", esconder_indecisos=False, figsize=(13,4)
)
_stacked_h(
    "voto_por_edad", "edad_grupo", orden_pv,
    "Intención de voto por edad\n(esconder indecisos — normalizado sobre decididos)",
    "11_4b_voto_edad_sin_indecisos.png", esconder_indecisos=True, figsize=(13,4)
)
""".strip()

# ── CHART 5: Sesgo demográfico por encuestadora ───────────────────────────────
CHART_SESGO = r"""
def _sesgo_chart(tabla_key, dim_col, titulo, fig_name, figsize=(11,4)):
    if tabla_key not in tablas:
        print(f"⚠ Tabla '{tabla_key}' no disponible"); return
    t = tablas[tabla_key].copy()
    # tabla de sesgo: columnas = encuestadoras, filas = categorías demográficas
    if dim_col not in t.columns:
        # intentar primera columna no numérica
        dim_col = t.select_dtypes("object").columns[0]
    encuestadoras = [c_ for c_ in t.columns if c_ != dim_col]
    cats = t[dim_col].tolist()

    x = np.arange(len(cats))
    width = 0.8 / max(len(encuestadoras), 1)
    colores_enc = ["#1B4F9A","#D4890A","#7B1E3C","#2E7D4F","#5B3E8A"]

    fig, ax = plt.subplots(figsize=figsize)
    for i, enc in enumerate(encuestadoras):
        vals = t[enc].values.astype(float)
        ax.bar(x + i*width - (len(encuestadoras)-1)*width/2,
               vals, width*0.85,
               color=colores_enc[i % len(colores_enc)], label=enc, alpha=0.85)

    ax.axhline(0, color="black", linewidth=1)
    ax.set_xticks(x); ax.set_xticklabels(cats, rotation=15, ha="right")
    ax.set_ylabel("Diferencia en pp vs promedio del resto")
    ax.set_title(titulo, fontsize=13, fontweight="bold")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v,_: f"{v:+.0f}pp"))
    ax.legend(loc="upper right", fontsize=8)
    plt.tight_layout()
    plt.savefig(FIG_DIR / fig_name, bbox_inches="tight", dpi=150)
    plt.show()

_sesgo_chart("sesgo_edad",   "edad_grupo",
             "Sesgo demográfico por encuestadora — Edad\n(+ = sobreestima ese grupo)",
             "11_5a_sesgo_edad.png")
_sesgo_chart("sesgo_genero", "genero",
             "Sesgo demográfico por encuestadora — Género\n(+ = sobreestima ese grupo)",
             "11_5b_sesgo_genero.png")
""".strip()

# ── CHART 6: Petrismo — Votantes de Cepeda que aprueban a Petro ──────────────
CHART_PETRO = r"""
t = tablas.get("voto_vs_aprobacion")
if t is not None and "primera_vuelta" in t.columns:
    cep = t[t["primera_vuelta"] == "Iván Cepeda"].copy()
    cats_apro = [c_ for c_ in ["Aprueba","Regular","Desaprueba","NS/NR"] if c_ in cep.columns]
    if not cep.empty and cats_apro:
        vals = [float(cep[c_].iloc[0]) for c_ in cats_apro]
        colores_apro = {"Aprueba":"#1B4F9A","Regular":"#A0C4E8",
                        "Desaprueba":"#D4890A","NS/NR":"#C8C8C8"}
        fig, ax = plt.subplots(figsize=(10, 2.5))
        left = 0
        for cat, v in zip(cats_apro, vals):
            bar = ax.barh(["Votantes\nde Cepeda"], [v], left=left,
                          color=colores_apro.get(cat,"#999"), edgecolor="white",
                          linewidth=0.5, height=0.45, label=cat)
            if v >= 5:
                ax.text(left + v/2, 0, f"{cat}\n{v:.0f}%",
                        ha="center", va="center", color="white",
                        fontsize=9, fontweight="bold")
            left += v
        ax.set_xlim(0, 102)
        ax.set_title("¿Cuántos votantes de Cepeda aprueban a Petro?\n"
                     "Distribución de aprobación del gobierno entre votantes de Cepeda en PV",
                     fontsize=12, fontweight="bold")
        ax.set_xlabel("Porcentaje (%)")
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x,_: f"{x:.0f}%"))
        ax.set_yticks([])
        handles = [mpatches.Patch(color=colores_apro.get(cat,"#999"), label=cat)
                   for cat in cats_apro]
        ax.legend(handles=handles, loc="lower right", fontsize=9)
        plt.tight_layout()
        plt.savefig(FIG_DIR / "11_6_cepeda_aprueba_petro.png", bbox_inches="tight", dpi=150)
        plt.show()
else:
    print("⚠ Tabla 'voto_vs_aprobacion' no disponible o sin columna 'primera_vuelta'")
""".strip()

# ── CHART 7: Intención de voto por género ─────────────────────────────────────
CHART_GENERO = r"""
_stacked_h(
    "voto_por_genero", "sexo", orden_pv,
    "Intención de voto por género\n(con indecisos)",
    "11_7a_voto_genero_con_indecisos.png", esconder_indecisos=False, figsize=(13,3.5)
)
_stacked_h(
    "voto_por_genero", "sexo", orden_pv,
    "Intención de voto por género\n(esconder indecisos)",
    "11_7b_voto_genero_sin_indecisos.png", esconder_indecisos=True, figsize=(13,3.5)
)

# Composición por género de cada candidato (hombre/mujer entre sus votantes)
t_gc = tablas.get("genero_por_candidato_top4")
if t_gc is not None:
    # tabla: columnas = candidatos, filas = Hombre/Mujer
    cand_cols = [c_ for c_ in t_gc.columns
                 if c_ not in {"sexo","genero"} and c_ not in INDECISOS_CATS]
    dim_col_gc = "sexo" if "sexo" in t_gc.columns else t_gc.columns[0]
    if cand_cols:
        x = np.arange(len(cand_cols))
        h_row = t_gc[t_gc[dim_col_gc]=="Hombre"].iloc[0] if (t_gc[dim_col_gc]=="Hombre").any() else None
        m_row = t_gc[t_gc[dim_col_gc]=="Mujer"].iloc[0]  if (t_gc[dim_col_gc]=="Mujer").any()  else None

        fig, ax = plt.subplots(figsize=(10, 4))
        width = 0.38
        if h_row is not None:
            ax.bar(x - width/2, [float(h_row[c_]) for c_ in cand_cols],
                   width, label="Hombre", color="#4A90D9", edgecolor="white")
        if m_row is not None:
            ax.bar(x + width/2, [float(m_row[c_]) for c_ in cand_cols],
                   width, label="Mujer",  color="#E87A8C", edgecolor="white")
        ax.set_xticks(x)
        ax.set_xticklabels([c_[:20] for c_ in cand_cols], rotation=20, ha="right")
        ax.set_ylabel("% de los votantes del candidato"); ax.set_ylim(0, 100)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v,_: f"{v:.0f}%"))
        ax.set_title("Composición por género de cada candidato\n"
                     "De cada 100 votantes del candidato, % que son H/M",
                     fontsize=12, fontweight="bold")
        ax.legend()
        plt.tight_layout()
        plt.savefig(FIG_DIR / "11_7c_composicion_genero_candidato.png", bbox_inches="tight", dpi=150)
        plt.show()
""".strip()

# ── CHART 8: Intención de voto por región ────────────────────────────────────
CHART_REGION = r"""
_stacked_h(
    "voto_por_region", "region", orden_pv,
    "Intención de voto por región\n(con indecisos)",
    "11_8a_voto_region_con_indecisos.png", esconder_indecisos=False, figsize=(13,6)
)
_stacked_h(
    "voto_por_region", "region", orden_pv,
    "Intención de voto por región\n(esconder indecisos — normalizado sobre decididos)",
    "11_8b_voto_region_sin_indecisos.png", esconder_indecisos=True, figsize=(13,6)
)
""".strip()

# ── CHART 9: Resumen ejecutivo en un solo panel ───────────────────────────────
CHART_RESUMEN = r"""
fig = plt.figure(figsize=(16, 6))
fig.suptitle("Resumen ejecutivo — Intención de voto primera vuelta\n"
             f"Ponderación: {config.weighting.active_strategy}",
             fontsize=14, fontweight="bold")

# Panel A: PV total (candidatos decididos)
ax1 = fig.add_subplot(1, 2, 1)
pv = tablas["primera_vuelta_total"].copy()
pv_dec = pv[~pv["primera_vuelta"].isin(INDECISOS_CATS)].copy()
pv_dec = pv_dec.sort_values("valor", ascending=True)
colors_bar = [c(cand) for cand in pv_dec["primera_vuelta"]]
bars = ax1.barh(pv_dec["primera_vuelta"], pv_dec["valor"],
                color=colors_bar, edgecolor="white", height=0.6)
for bar, v in zip(bars, pv_dec["valor"]):
    ax1.text(v + 0.3, bar.get_y() + bar.get_height()/2,
             f"{v:.1f}%", va="center", fontsize=8.5)
ax1.set_xlim(0, pv_dec["valor"].max() * 1.25)
ax1.set_title("Intención de voto (% total respondentes)")
ax1.set_xlabel("Porcentaje (%)")
ax1.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x,_: f"{x:.0f}%"))

# Panel B: Tendencia top 5 candidatos
ax2 = fig.add_subplot(1, 2, 2)
trend = tablas.get("trend_primera_vuelta", pd.DataFrame())
if not trend.empty:
    for cand in TOP5:
        sub = trend[trend["primera_vuelta"] == cand].sort_values("fecha")
        if sub.empty: continue
        col_val = "valor_suavizado" if "valor_suavizado" in sub.columns else "valor_punto"
        ax2.plot(sub["fecha"], sub[col_val], linewidth=2.5,
                 color=c(cand), label=cand[:22])
        last = sub.iloc[-1]
        ax2.annotate(f'{last[col_val]:.1f}%',
                     (last["fecha"], last[col_val]),
                     textcoords="offset points", xytext=(5,0),
                     fontsize=8, color=c(cand), fontweight="bold")
    ax2.set_title("Tendencia temporal — Top 5 candidatos")
    ax2.set_ylabel("Intención de voto (%)")
    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v,_: f"{v:.0f}%"))
    ax2.legend(fontsize=8)
    fig.autofmt_xdate()

plt.tight_layout()
plt.savefig(FIG_DIR / "11_9_resumen_ejecutivo.png", bbox_inches="tight", dpi=150)
plt.show()
""".strip()

# ── CHART 10: Guardar índice de gráficas ─────────────────────────────────────
CHART_INDEX = r"""
figuras = sorted(FIG_DIR.glob("*.png"))
print(f"\n📊 {len(figuras)} gráficas guardadas en {FIG_DIR}:")
for f in figuras:
    size_kb = f.stat().st_size / 1024
    print(f"   {f.name:<50} {size_kb:>6.1f} KB")
print("\n✅ Todas las gráficas del PDF La Silla Vacía replicadas.")
""".strip()

# ══════════════════════════════════════════════════════════════════════════════
#  Ensamblar las nuevas celdas
# ══════════════════════════════════════════════════════════════════════════════
new_cells = [
    md("---\n## ✅ Step 11 — Visualizaciones (replicando PDF La Silla Vacía)\n\nCada gráfica se guarda automáticamente en `data/outputs/graficas/` en tu Drive.\n\n| # | Gráfica |\n|---|---|\n| 11.1 | Movimiento de votos PV → SV (las dos matchups) |\n| 11.2 | Trasvase de la derecha en SV (serie temporal) |\n| 11.3 | Perfil de indecisos (edad · género · región) |\n| 11.4 | Intención de voto por edad (100% apilado) |\n| 11.5 | Sesgo demográfico por encuestadora |\n| 11.6 | Votantes de Cepeda que aprueban a Petro |\n| 11.7 | Intención de voto por género + composición de cada candidato |\n| 11.8 | Intención de voto por región |\n| 11.9 | Resumen ejecutivo (PV + tendencia) |"),
    md("### 11.0 — Setup: paleta de colores y helpers"),
    code(SETUP),
    md("### 11.1 — Movimiento de votos PV → SV\n\nMuestra para cada candidato de primera vuelta cómo se distribuye su intención de voto en las matchups de segunda vuelta."),
    code(CHART_TRANSFER),
    md("### 11.2 — Trasvase de la derecha (serie temporal)\n\n% de votantes de Abelardo que irían a Paloma (y viceversa) en cada encuesta, excluyendo indecisos de segunda vuelta."),
    code(CHART_TRASVASE),
    md("### 11.3 — Perfil de los indecisos\n\nDistribución de los indecisos por edad, género y región."),
    code(CHART_INDECISOS),
    md("### 11.4 — Intención de voto por edad\n\nBarras 100% apiladas por grupo etario, con y sin indecisos."),
    code(CHART_EDAD),
    md("### 11.5 — Sesgo demográfico por encuestadora\n\nDiferencia en pp entre el peso que da cada encuestadora a cada grupo demográfico vs el promedio de las demás."),
    code(CHART_SESGO),
    md("### 11.6 — Petrismo: votantes de Cepeda que aprueban a Petro"),
    code(CHART_PETRO),
    md("### 11.7 — Intención de voto por género"),
    code(CHART_GENERO),
    md("### 11.8 — Intención de voto por región"),
    code(CHART_REGION),
    md("### 11.9 — Resumen ejecutivo"),
    code(CHART_RESUMEN),
    code(CHART_INDEX),
]

# ══════════════════════════════════════════════════════════════════════════════
#  Insertar ANTES del último cell (Pipeline terminado)
# ══════════════════════════════════════════════════════════════════════════════
with open(NB_PATH) as f:
    nb = json.load(f)

nb["cells"] = nb["cells"][:-1] + new_cells + [nb["cells"][-1]]

with open(NB_PATH, "w") as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print(f"✅ Notebook actualizado: {NB_PATH}")
print(f"   Total celdas: {len(nb['cells'])} (antes: 37, añadidas: {len(new_cells)})")
