"""Exportador del dashboard HTML interactivo.

Encapsula la generación del archivo ``dashboard_interactivo.html`` con todos
los gráficos de Step 11 y Step 12.  Antes vivía como string concatenado en
``scripts/plotly_cells/10_export_html.py`` y ``scripts/step12_cells/09_export12.py``;
ahora es una función testable que recibe figuras + metadatos.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

import plotly.graph_objects as go
import plotly.io as pio


# ════════════════════════════════════════════════════════════════════════════
#  Metadatos por defecto
# ════════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class SeccionMeta:
    """Metadatos de una sección del dashboard."""

    key: str
    icon_label: str
    descripcion: str

    @property
    def icon(self) -> str:
        """Primer token del icon_label, asumido como emoji."""
        return self.icon_label.split(" ", 1)[0]

    @property
    def label(self) -> str:
        """Resto del icon_label, sin el emoji inicial."""
        partes = self.icon_label.split(" ", 1)
        return partes[1] if len(partes) > 1 else partes[0]


SECCIONES_STEP11: tuple[SeccionMeta, ...] = (
    SeccionMeta("09_pv_total", "📊 Primera vuelta", "Intención de voto total"),
    SeccionMeta("01_tendencia", "📈 Tendencia", "Serie temporal top 5 candidatos"),
    SeccionMeta("02a_sankey_cepeda_valencia", "🔀 SV: Cepeda–Valencia", "Flujos PV→SV — Sankey"),
    SeccionMeta("02b_sankey_cepeda_espriella", "🔀 SV: Cepeda–Espriella", "Flujos PV→SV — Sankey"),
    SeccionMeta("03_trasvase", "↔ Trasvase", "Serie temporal de trasvase de derecha"),
    SeccionMeta("04_indecisos", "❓ Indecisos", "Perfil demográfico del voto indeciso"),
    SeccionMeta("05a_voto_edad", "👥 Edad", "Intención de voto por grupo etario"),
    SeccionMeta("05b_voto_genero", "⚥ Género (voto)", "Intención de voto por género"),
    SeccionMeta("05c_voto_region", "🗺 Región", "Intención de voto por región"),
    SeccionMeta("06a_sesgo_edad", "🔍 Sesgo edad", "Sesgos demográficos encuestadoras"),
    SeccionMeta("06b_sesgo_genero", "🔍 Sesgo género", "Sesgos demográficos encuestadoras"),
    SeccionMeta("07_petro", "🇨🇴 Petrismo", "Aprobación Petro × votantes Cepeda"),
    SeccionMeta(
        "08_genero_composicion", "⚖ Composición H/M", "Composición por género de cada candidato"
    ),
)

SECCIONES_STEP12: tuple[SeccionMeta, ...] = (
    SeccionMeta(
        "12_01_trasvase_centro",
        "🎯 Trasvase del centro",
        "Fajardo, Claudia, Botero, Barreras: ¿a quién apoyan en 2V? (esc. A y B)",
    ),
    SeccionMeta(
        "12_02_monte_carlo", "🎲 Monte Carlo", "Distribución de resultados — 20 000 simulaciones"
    ),
    SeccionMeta(
        "12_03_sensibilidad", "🔧 Swing factors", "Sensibilidad de la 2V a los 3 factores críticos"
    ),
    SeccionMeta("12_04_polymarket", "📈 Mercado vs modelo", "Polymarket vs encuestas vs modelo MC"),
    SeccionMeta("12_05_techo_rechazo", "🚧 Techo rechazo", "Techo de rechazo por candidato"),
    SeccionMeta("12_06_geografia_petrismo", "🗺 Geografía", "Petrismo e indecisos por región"),
    SeccionMeta(
        "12_07_voto_joven", "👥 Voto joven", "Ruptura generacional y abstención diferencial"
    ),
    SeccionMeta(
        "12_08_panel_ejecutivo",
        "📊 Panel ejecutivo",
        "Probabilidades consolidadas: doc. forense vs modelo",
    ),
)


# ════════════════════════════════════════════════════════════════════════════
#  CSS extraído como constante (DRY)
# ════════════════════════════════════════════════════════════════════════════
_DASHBOARD_CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --sidebar-w : 220px;
  --accent    : #7B1E3C;
  --bg-page   : #f0f2f5;
  --bg-card   : #ffffff;
  --text-h    : #1a1a2e;
  --text-body : #374151;
  --border    : #e5e7eb;
  --shadow    : 0 2px 8px rgba(0,0,0,.10);
  --font      : 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
  --radius    : 10px;
}

html { scroll-behavior: smooth; }
body {
  font-family: var(--font);
  background: var(--bg-page);
  color: var(--text-body);
  display: flex;
  min-height: 100vh;
}

.sidebar {
  position: fixed;
  top: 0; left: 0;
  width: var(--sidebar-w);
  height: 100vh;
  background: #1a1a2e;
  color: #e5e7eb;
  overflow-y: auto;
  z-index: 100;
  display: flex;
  flex-direction: column;
}
.sidebar-brand {
  padding: 20px 16px 14px;
  border-bottom: 1px solid rgba(255,255,255,.1);
}
.sidebar-brand h1 {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: #f9fafb;
}
.sidebar-brand p {
  font-size: 11px;
  color: #9ca3af;
  margin-top: 4px;
}
.section-divider {
  padding: 8px 16px;
  font-size: 10px;
  letter-spacing: 1px;
  color: #6b7280;
  text-transform: uppercase;
  margin-top: 8px;
}
.nav-link {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 16px;
  color: #d1d5db;
  text-decoration: none;
  font-size: 12.5px;
  transition: background .15s, color .15s;
  border-left: 3px solid transparent;
}
.nav-link:hover {
  background: rgba(255,255,255,.07);
  color: #f9fafb;
  border-left-color: var(--accent);
}
.nav-icon { font-size: 15px; flex-shrink: 0; }
.sidebar-footer {
  margin-top: auto;
  padding: 12px 16px;
  font-size: 10.5px;
  color: #6b7280;
  border-top: 1px solid rgba(255,255,255,.08);
}

.main {
  margin-left: var(--sidebar-w);
  flex: 1;
  padding: 0 24px 40px;
  max-width: 1280px;
}

.top-header {
  background: var(--bg-card);
  margin: 0 -24px 28px;
  padding: 28px 32px;
  border-bottom: 3px solid var(--accent);
  box-shadow: var(--shadow);
}
.top-header h1 {
  font-size: 22px;
  font-weight: 800;
  color: var(--text-h);
  line-height: 1.3;
}
.top-header .meta {
  font-size: 13px;
  color: #6b7280;
  margin-top: 8px;
}
.badge {
  display: inline-block;
  background: var(--accent);
  color: white;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 9px;
  border-radius: 12px;
  margin-right: 6px;
  vertical-align: middle;
}

.chart-section {
  background: var(--bg-card);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  margin-bottom: 28px;
  overflow: hidden;
  scroll-margin-top: 20px;
}
.chart-header {
  padding: 18px 24px 12px;
  border-bottom: 1px solid var(--border);
}
.chart-header h2 {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-h);
}
.chart-desc {
  font-size: 12.5px;
  color: #6b7280;
  margin-top: 4px;
}
.chart-body {
  padding: 6px 4px;
}

.step12-banner {
  background:#1a1a2e;
  border-radius:10px;
  padding:18px 24px;
  margin-bottom:28px;
}
.step12-banner h2 {
  color:white;
  font-size:16px;
  margin:0;
}
.step12-banner p {
  color:#9ca3af;
  font-size:12.5px;
  margin-top:6px;
}

.scroll-top {
  position: fixed;
  bottom: 24px;
  right: 24px;
  background: var(--accent);
  color: white;
  border: none;
  border-radius: 50%;
  width: 42px; height: 42px;
  font-size: 18px;
  cursor: pointer;
  box-shadow: var(--shadow);
  transition: opacity .2s;
  opacity: .85;
}
.scroll-top:hover { opacity: 1; }

@media (max-width: 768px) {
  .sidebar { width: 60px; }
  .nav-label { display: none; }
  .sidebar-brand h1, .sidebar-brand p { display: none; }
  .main { margin-left: 60px; padding: 0 12px 40px; }
}
""".strip()


# ════════════════════════════════════════════════════════════════════════════
#  Generación HTML
# ════════════════════════════════════════════════════════════════════════════
def _fig_to_div(
    fig: go.Figure,
    div_id: str,
    plotly_config: Mapping[str, object] | None = None,
) -> str:
    """Renderizar una figura como ``<div>`` Plotly sin incluir plotly.js."""
    cfg: dict[str, object] = {
        "displayModeBar": True,
        "responsive": True,
        "modeBarButtonsToRemove": ["autoScale2d", "lasso2d", "select2d"],
        "toImageButtonOptions": {
            "format": "png",
            "width": 1400,
            "height": 700,
            "scale": 2,
        },
    }
    if plotly_config:
        cfg.update(plotly_config)
    return pio.to_html(
        fig,
        include_plotlyjs=False,
        full_html=False,
        div_id=div_id,
        config=cfg,
    )


def _build_nav(secciones: Iterable[SeccionMeta]) -> str:
    """Construir links del nav sidebar."""
    items = []
    for sec in secciones:
        items.append(
            f'<a href="#{sec.key}" class="nav-link">'
            f'<span class="nav-icon">{sec.icon}</span>'
            f'<span class="nav-label">{sec.label}</span>'
            f"</a>"
        )
    return "\n".join(items)


def _build_sections(
    secciones: Iterable[SeccionMeta],
    figuras: Mapping[str, go.Figure],
) -> str:
    """Construir el HTML de las secciones de gráficos."""
    chunks = []
    for sec in secciones:
        fig = figuras.get(sec.key)
        if fig is None:
            continue
        chunks.append(
            f'\n    <section id="{sec.key}" class="chart-section">'
            f'\n      <div class="chart-header">'
            f"\n        <h2>{sec.icon_label}</h2>"
            f'\n        <p class="chart-desc">{sec.descripcion}</p>'
            f"\n      </div>"
            f'\n      <div class="chart-body">{_fig_to_div(fig, sec.key)}</div>'
            f"\n    </section>"
        )
    return "".join(chunks)


def export_dashboard(
    figuras: Mapping[str, go.Figure],
    out_path: Path,
    secciones_step11: Iterable[SeccionMeta] = SECCIONES_STEP11,
    secciones_step12: Iterable[SeccionMeta] = SECCIONES_STEP12,
    titulo: str = "Cruces microdatos encuestas 2026 — Dashboard interactivo",
    h1: str = "Cruces con los microdatos de las encuestas",
    plotly_cdn_url: str = "https://cdn.plot.ly/plotly-2.27.0.min.js",
) -> Path:
    """Exportar todas las figuras como un dashboard HTML autocontenido.

    Args:
        figuras: dict ``key → go.Figure`` con todas las gráficas.
        out_path: ruta del archivo HTML de salida.  Se sobrescribe si existe.
        secciones_step11: orden y metadata de las secciones de Step 11.
        secciones_step12: orden y metadata de las secciones de Step 12.
        titulo: ``<title>`` del HTML.
        h1: encabezado principal del dashboard.
        plotly_cdn_url: URL del bundle de plotly.js a cargar en ``<head>``.

    Returns:
        ``Path`` absoluto del archivo escrito.

    Raises:
        ValueError: si ``figuras`` está vacío.
    """
    if not figuras:
        raise ValueError("export_dashboard recibió un dict de figuras vacío.")

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    secciones_step11 = list(secciones_step11)
    secciones_step12 = list(secciones_step12)

    s11_nav = _build_nav(secciones_step11)
    s12_nav = _build_nav(secciones_step12)
    s11_sections = _build_sections(secciones_step11, figuras)
    s12_sections = _build_sections(secciones_step12, figuras)

    s12_banner = (
        '<div class="step12-banner">'
        "<h2>⚡ Step 12 — Análisis predictivo avanzado</h2>"
        "<p>Monte Carlo · Swing factors · Techo de rechazo · "
        "Comparativo Polymarket</p></div>"
    )

    html = (
        f"<!DOCTYPE html>\n"
        f'<html lang="es"><head>\n'
        f'<meta charset="UTF-8">\n'
        f'<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        f"<title>{titulo}</title>\n"
        f'<script src="{plotly_cdn_url}" charset="utf-8"></script>\n'
        f"<style>{_DASHBOARD_CSS}</style>\n"
        f"</head><body>\n"
        f'<nav class="sidebar">\n'
        f'  <div class="sidebar-brand">'
        f"<h1>Dashboard · Colombia 2026</h1>"
        f"<p>Microdatos encuestas CNE</p></div>\n"
        f"  {s11_nav}\n"
    )

    if s12_sections:
        html += f'  <div class="section-divider">─── Análisis predictivo ───</div>\n  {s12_nav}\n'

    html += (
        f'  <div class="sidebar-footer">'
        f"Generado con encuestas_lib<br>"
        f"Datos: GAD3 · Atlas · Invamer · CNC"
        f"</div>\n"
        f"</nav>\n"
        f'<div class="main">\n'
        f'  <div class="top-header">\n'
        f"    <h1>{h1}</h1>\n"
        f'    <div class="meta">'
        f'<span class="badge">Interactivo</span>'
        f"Basado en {len(figuras)} gráficas · Hace zoom, hover y descarga "
        f"PNG de cada gráfica. Datos: microdatos públicos del Consejo Nacional "
        f"Electoral — GAD3, AtlasIntel, Invamer, CNC.</div>\n"
        f"  </div>\n"
        f"  {s11_sections}\n"
    )

    if s12_sections:
        html += f"\n  {s12_banner}\n  {s12_sections}\n"

    html += (
        "</div>\n"
        '<button class="scroll-top" '
        "onclick=\"window.scrollTo({top:0,behavior:'smooth'})\" "
        'title="Volver arriba">↑</button>\n'
        "</body></html>"
    )

    out_path.write_text(html, encoding="utf-8")
    return out_path.resolve()


__all__ = [
    "SECCIONES_STEP11",
    "SECCIONES_STEP12",
    "SeccionMeta",
    "export_dashboard",
]
