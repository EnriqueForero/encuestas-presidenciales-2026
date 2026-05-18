# Changelog

Formato: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versionado: [SemVer](https://semver.org/).

## [0.2.3] — 2026-05-17 (publicación-ready)

### Lint y formato listos para CI/CD

Pase completo de `ruff check` + `ruff format` sobre el paquete. El publicador
automatizado (notebook `Publicacion_GitHub_PyPI_Encuestas.ipynb`) ahora
acepta el repo sin warnings.

### Fixed (errores ruff)
- **`encuestas_lib/viz/_helpers.py`** — RUF022: `__all__` sorteado alfabéticamente.
- **`encuestas_lib/viz/charts/step11.py`** — UP035: `Iterable` migrado de
  `typing` a `collections.abc`.
- **`encuestas_lib/viz/charts/step12.py`** — UP035 + RUF022: `Mapping`,
  `Sequence` migrados a `collections.abc`; `__all__` sorteado.
- **`encuestas_lib/viz/dashboard.py`** — F401 (unused `OrderedDict`) + UP035
  (`Iterable`, `Mapping` → `collections.abc`).
- **`encuestas_lib/viz/theme.py`** — RUF100: removida directiva `# noqa: D401`
  obsoleta.
- **`tests/test_viz_step12_params.py`** — F401: import `pandas` no usado.
- **Formato** — 4 archivos reformateados a 100 cols, comillas dobles
  (`quote-style = "double"`).

### Changed
- **`pyproject.toml`** — añadido `[tool.ruff].extend-exclude` con
  `scripts/plotly_cells`, `scripts/step12_cells`, `scripts/chart_cells`,
  `notebooks`. Esos directorios contienen *cells* de Jupyter que dependen
  del namespace global del notebook (`tablas`, `df`, `FIGURAS`, …); lintar
  esos archivos como módulos independientes produce falsos positivos F821.

### Validation
- ✅ `ruff check encuestas_lib` → All checks passed!
- ✅ `ruff format --check encuestas_lib` → 32 files already formatted
- ✅ `ruff check .` (todo el repo, con exclusiones) → All checks passed!
- ✅ `pytest` → 186 passed, 1 warning
- ✅ `encuestas_lib.__version__` → `"0.2.3"`

### Cómo publicar
```python
publicar_profesional(solo_github=True)   # ya no se bloquea por linting
```

---

## [0.2.2] — 2026-05-17 (v7.1)

### Bugfix: paridad de schema entre charts y pipeline real

El refactor v0.2.0/v0.2.1 introdujo dos charts con un **bug semántico
heredado del v6 original**: asumían formato wide cuando el pipeline produce
formato long (o pivot ortogonal). El bug no se manifestaba en v6 porque las
celdas anteriores fallaban con el TypeError `yaxis` antes de llegar; al
fixearse ese TypeError, el bug latente quedó al descubierto.

### Fixed
- **`chart_sesgo_demografico`** — antes:
  `ValueError: could not convert string to float: 'edad_grupo'`.
  La tabla real `sesgo_edad` viene en formato long
  `[encuestadora, variable, categoria, peso_encuestadora,
  peso_promedio_otras, sesgo_rel_pp]`. Ahora se detecta automáticamente y se
  pivota a wide dentro de la función con `pivot_table(aggfunc='mean')`
  (robusto a duplicados). Mantiene compatibilidad con el formato wide para
  tests/uso manual.
- **`chart_composicion_genero`** — antes devolvía figura vacía en silencio
  (más insidioso que un error). El pipeline produce
  `[primera_vuelta, Hombre, Mujer]` (pivot con `index=primera_vuelta`,
  `columns=sexo`), pero el chart buscaba filas con
  `dim_col == 'Hombre'`/`'Mujer'` (esperaba el pivot transpuesto). Ahora
  detecta cuál schema viene y dibuja correctamente en ambos.
- **Conversión numérica defensiva** — reemplazo de `.values.astype(float)`
  por `pd.to_numeric(..., errors='coerce').to_numpy(dtype=float)` para
  tolerar `NaN`/`None` en celdas individuales sin propagar `ValueError`.

### Added
- **`tests/test_viz_charts.py`** — 8 tests nuevos de regresión:
  - `TestSesgoDemograficoSchemaReal` (4 tests): formato long del pipeline,
    formato wide legacy, tabla vacía, duplicados por error.
  - `TestComposicionGeneroSchemaReal` (4 tests): schema real, schema
    transpuesto, tabla vacía, solo un género presente.
- **Fixture `sesgo_edad_formato_long`** que reproduce exactamente el output
  de `tabla_sesgo_por_encuestadora` para que cualquier cambio futuro en la
  función rompa el test antes que el notebook.

### Validation
- **186 tests pasan** (178 de v0.2.1 + 8 nuevos).
- Smoke test del notebook: las 81 celdas compilan limpiamente.
- Cero warnings de deprecation.

### Lecciones aprendidas (anti-patrones detectados)
1. **No confiar en fixtures mockeadas para refactors**. La fixture
   `tablas_minimas` tenía formato wide; el pipeline produce long. El test
   smoke pasaba pero el notebook fallaba.
2. **Auditar el schema real antes de migrar lógica**. Cuando el otro Claude
   convirtió las celdas a funciones, no inspeccionó qué producía realmente
   `sesgo_por_encuestadora` y `tabla_genero_por_candidato_top4`.
3. **Fallar ruidosamente, no en silencio.** `chart_composicion_genero`
   devolvía figura vacía cuando no encontraba filas — debería haber lanzado
   o al menos retornado un placeholder visible. Ahora lo hace.

---

## [0.2.1] — 2026-05-17 (v7)

### Cambio arquitectónico complementario: centralización total de parámetros

Iteración sobre v0.2.0. El bug raíz ya estaba resuelto, pero **5 celdas delgadas
seguían teniendo datos del documento forense hardcoded inline** — violando el
principio de "una sola fuente de verdad" y la regla del usuario sobre
parámetros centralizados.

### Added
- **`encuestas_lib.viz.charts.step12`** — nuevas constantes y dataclasses
  centralizadas:
  - `MonteCarloParams` (dataclass frozen con validación: `n_iter`, `seed`).
  - `SwingFactor` (dataclass frozen con validación: rango, n_puntos,
    n_iter_mc, destino).
  - `MC_PARAMS_DOC` — parámetros canónicos MC (20 000 iter, seed=42).
  - `SWING_FACTORS_DOC` — 3 swing factors críticos del documento forense.
  - `TECHO_RECHAZO_DOC` — rangos de techo de rechazo por candidato.
  - `CANDS_CENTRO_DOC` — tupla canónica de candidatos del centro.
  - `POLYMARKET_SNAPSHOT_DOC` — snapshot Polymarket 16-17 may (18 claves).
  - `ESCENARIOS_DOC` — 7 escenarios del panel ejecutivo.
- **Constructores de DataFrames runtime** que combinan params doc + MC:
  - `construir_comparativo_polymarket(res_a, res_b)` — 4 filas.
  - `construir_escenarios_consolidados(res_a, res_b)` — 7 filas con
    `prob_doc` (canónico) + `prob_modelo` (resultado MC de la sesión).
- **`tests/test_viz_step12_params.py`** — **24 tests** que cubren:
  - Validación de las dataclasses (rangos inválidos lanzan `ValueError`).
  - Coherencia de las constantes `*_DOC` (PESOS suman 100; matrices A/B
    comparten estructura; rangos válidos; tipos correctos).
  - Constructores devuelven DataFrames con shape y columnas esperadas.
  - Snapshots personalizados respetan overrides.

### Changed
- **Cells delgadas Step 12** — eliminados TODOS los datos hardcoded inline:
  - `01_transfer_centro.py` — usa `CANDS_CENTRO_DOC`.
  - `02_monte_carlo.py` — usa `MC_PARAMS_DOC.n_iter` y `MC_PARAMS_DOC.seed`.
  - `03_sensibilidad.py` — itera `SWING_FACTORS_DOC` con validación
    `len == 3` antes del unpack.
  - `04_polymarket.py` — usa `construir_comparativo_polymarket(res_A, res_B)`.
  - `05_techo_rechazo.py` — usa `TECHO_RECHAZO_DOC`.
  - `08_panel_ejecutivo.py` — usa `construir_escenarios_consolidados(res_A, res_B)`.
- **`step11.py`** — `select_dtypes("object")` → `select_dtypes(include=["object", "string"])`
  (silencia `Pandas4Warning` de migración futura).
- **`__all__`** de `step12.py` actualizado con los nuevos símbolos.

### Removed
- Bloques de constantes inline `COMPARATIVO`, `TECHO_DOC`, `ESCENARIOS`,
  `CANDS_CENTRO`, parámetros sueltos `n_iter=20_000`, `seed=42`, rangos
  `(60.0, 95.0)`, `n_puntos=36`, `n_iter_mc=4_000` que vivían dispersos en
  las celdas.
- `scripts/build_notebook_charts.py` — regeneraba el notebook desde strings
  embebidos (fuente de regresión: cualquier fix manual al notebook se perdía
  al re-ejecutar este script). Reemplazado por `refresh_notebook_charts.py`
  que solo *actualiza* las celdas leyendo desde `scripts/*_cells/*.py`.

### Validation
- **178 tests pasan** (154 de v0.2.0 + 24 nuevos).  1 warning intencional
  (test de tabla inexistente).  0 warnings de deprecation.
- Todas las 81 celdas del notebook compilan limpiamente.
- Reducción de LoC: ~1 400 → 279 líneas en cells Step 11/12 (-80 %).

### Migration guide
Si tu cell tenía:
```python
COMPARATIVO = pd.DataFrame([{...}, {...}, ...])  # ❌ hardcoded
```
Ahora:
```python
from encuestas_lib.viz.charts.step12 import construir_comparativo_polymarket
COMPARATIVO = construir_comparativo_polymarket(res_A, res_B)  # ✅ centralizado
```

Para tunear valores: edita `encuestas_lib/viz/charts/step12.py` en la sección
"Parámetros adicionales del documento forense" (líneas ~71-185).

---

## [0.2.0] — 2026-05-17

### Cambio arquitectónico mayor: paquete `encuestas_lib.viz`

Toda la lógica de visualización que vivía como código embebido en celdas
del notebook fue extraída a un paquete Python instalable, modular y testable.

### Added
- **`encuestas_lib.viz.theme`** — Single source of truth de la paleta (24
  candidatos + indecisos), helper `c()`, conversor `hex_to_rgba()` con
  validación, template Plotly `lsv` registrado vía `register_template()`.
- **`encuestas_lib.viz.charts.step11`** — 9 funciones puras
  (`chart_tendencia_temporal`, `chart_sankey_pv_sv`, `chart_trasvase_derecha`,
  `chart_perfil_indecisos`, `chart_stacked_bar`, `chart_sesgo_demografico`,
  `chart_petrismo_cepeda`, `chart_composicion_genero`,
  `chart_primera_vuelta_total`). Cada una recibe `tablas: dict[str, DataFrame]`
  y retorna `plotly.graph_objects.Figure`.
- **`encuestas_lib.viz.charts.step12`** — 8 funciones puras para análisis
  predictivo (`chart_trasvase_centro`, `chart_monte_carlo`,
  `chart_sensibilidad`, `chart_polymarket`, `chart_techo_rechazo`,
  `chart_geografia_petrismo`, `chart_voto_joven`, `chart_panel_ejecutivo`).
  Constantes `PESOS_PV_DOC`, `MATRIZ_A`, `MATRIZ_B` con tipado explícito.
- **`encuestas_lib.viz.dashboard`** — `SeccionMeta` (dataclass frozen) y
  `export_dashboard()` que escribe un HTML interactivo autocontenido.
- **35 tests nuevos** (`test_viz_theme.py`, `test_viz_charts.py`,
  `test_viz_dashboard.py`):
  - `TestLayoutBaseNoColisionaConEjes` — test de regresión del bug raíz.
  - Smoke tests de las 9 funciones de Step 11 con fixtures mínimas.
  - Tests de placeholder cuando faltan tablas.
  - Tests de `export_dashboard` (genera HTML válido, omite secciones sin
    figura, lanza `ValueError` si recibe dict vacío, UTF-8 correcto, banner
    condicional Step 12).
- `scripts/refresh_notebook_charts.py` — Regenera el notebook reemplazando
  las celdas de Step 11/12 con los scripts delgados de `scripts/plotly_cells/`
  y `scripts/step12_cells/`.  Idempotente.

### Changed
- **`plotly>=5.18`** movido de `[project.optional-dependencies] viz` a
  `dependencies` core: el módulo `encuestas_lib.viz` lo requiere
  directamente.
- `requirements.txt` actualizado para incluir `plotly>=5.18`.
- Scripts `scripts/plotly_cells/*.py` y `scripts/step12_cells/*.py`
  reescritos como glue cells delgadas (3-30 líneas cada una).  Reducción
  total: ~1400 líneas → ~395 líneas.
- Notebook `notebooks/00_run_full_pipeline.ipynb` regenerado vía
  `refresh_notebook_charts.py`.

### Fixed
- **Bug raíz: `TypeError: update_layout() got multiple values for keyword
  argument 'yaxis'`** (y variantes con `xaxis`, `margin`, `legend`).  Causa:
  `LAYOUT_BASE` declaraba esas claves; cada `fig.update_layout(**LAYOUT_BASE,
  yaxis=..., margin=..., ...)` colisionaba.
- **Solución arquitectónica**: `LAYOUT_BASE` ahora es `{}` (dict vacío).
  Todos los defaults visuales (font, paper_bgcolor, plot_bgcolor, hoverlabel,
  margin, legend, xaxis, yaxis, colorway) los aporta el Plotly template
  `lsv` registrado vía `register_template()`.  Esto elimina la *clase entera*
  de bugs, no solo la instancia reportada — cualquier override es seguro
  porque no hay `**` con keys preexistentes.

### Removed
- 1 400+ líneas de código duplicado entre celdas (paleta repetida en
  3 lugares, helpers redefinidos en cada celda, CSS hardcodeado).
- Funciones internas anidadas dentro de celdas (ahora vivien en módulos
  importables).

### Migration guide
Código que importaba:
```python
LAYOUT_BASE = dict(xaxis=..., yaxis=..., margin=...)
fig.update_layout(**LAYOUT_BASE, yaxis=dict(...))  # ❌ TypeError
```
Ahora:
```python
from encuestas_lib.viz import register_template, LAYOUT_BASE
register_template()                                   # una vez por sesión
fig.update_layout(**LAYOUT_BASE, yaxis=dict(...))   # ✅ funciona (LAYOUT_BASE={})
# o más limpio:
fig.update_layout(title=..., yaxis=..., xaxis=...)
```

---

## [0.1.0] — 2026-04 (baseline)

- Pipeline modular de ingestión y armonización de microdatos
  (Atlas Intel, GAD3, Invamer, CNC).
- Análisis: intención de voto, demografía, indecisos, house effects,
  transferencia PV→SV, simulación Monte Carlo, sensibilidad.
- Visualizaciones Plotly como celdas embebidas en el notebook
  (con el bug reportado).
