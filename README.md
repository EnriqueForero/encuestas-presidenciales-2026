# Análisis de Microdatos de Encuestas — Presidenciales Colombia 2026

Pipeline reproducible para armonizar, ponderar y analizar microdatos de encuestas
presidenciales de Colombia 2026, a partir de bases publicadas por el CNE.

> Refactor profesional del repositorio
> [Analisis-microdatos-encuestas](https://github.com/PabloManriqueo/Analisis-microdatos-encuestas).
> Migración de scripts monolíticos a paquete modular con registro YAML de
> encuestas, lectores polimórficos y tests.

---

## Por qué este refactor

La versión inicial (`harmonize_encuestas.py` + `analisis_desde_cero.py`) era
funcional pero **no escalable**:

| Problema antes | Solución ahora |
| --- | --- |
| Rutas hardcoded a una máquina Windows | `Config` parametrizable, `pathlib.Path` |
| Una función `read_*` por encuesta | `BaseReader` + registro YAML |
| `PESOS` hardcoded sin justificación | `configs/weights.yaml` con método declarado |
| Mapeo de candidatos duplicado en dos archivos | `harmonization/candidates.py` como única fuente |
| Cero tests | Suite `pytest` con casos canónicos |
| README de una línea | Este documento |
| `.apply(harmonize)` sin caché | `@lru_cache` + normalización vectorizable |

---

## Estructura

```
encuestas/
├── configs/
│   ├── surveys.yaml           # registro de encuestas (un YAML, no código)
│   ├── candidates.yaml        # candidatos canónicos y retiros
│   └── weights.yaml           # estrategia de ponderación explícita
├── encuestas_lib/
│   ├── config.py              # @dataclass Config
│   ├── harmonization/         # reglas de normalización
│   │   ├── candidates.py      # única fuente de verdad para nombres
│   │   ├── demographics.py    # edad, región, sexo, aprobación
│   │   └── matchups.py        # nombres de columnas de segunda vuelta
│   ├── readers/
│   │   ├── base.py            # BaseReader (ABC)
│   │   ├── atlas.py
│   │   ├── gad3.py
│   │   ├── invamer.py
│   │   ├── cnc.py
│   │   └── registry.py        # ReaderRegistry: nombre → clase
│   ├── pipeline/
│   │   ├── ingest.py          # IngestPipeline.run()
│   │   ├── analyze.py         # AnalysisPipeline.run()
│   │   └── checkpoints.py     # cargar_o_procesar (cache-aside)
│   ├── analysis/
│   │   ├── tables.py          # voto_por_region, voto_por_edad, ...
│   │   ├── weighting.py       # combinar_entre_encuestas
│   │   ├── validation.py      # verificar_cierres_100
│   │   └── advanced.py        # análisis profundos (ver §5)
│   └── io/
│       └── export.py          # ExcelExporter, JSONExporter
├── notebooks/
│   └── 00_run_full_pipeline.ipynb
├── tests/
│   ├── test_candidates.py
│   ├── test_matchups.py
│   └── test_weighting.py
└── data/
    ├── raw/                   # microdatos del CNE (gitignored)
    ├── processed/             # parquet checkpoints
    └── outputs/               # excel + json finales
```

---

## Instalación

```bash
git clone https://github.com/EnriqueForero/encuestas-presidenciales-2026
cd encuestas-presidenciales-2026
python -m venv .venv
source .venv/bin/activate          # Linux/macOS
# .venv\Scripts\activate            # Windows
pip install -e .[dev]
```

Requisitos: Python 3.10+.

---

## Uso rápido

### Desde notebook

```bash
jupyter lab notebooks/00_run_full_pipeline.ipynb
```

El notebook tiene **dos celdas**:

1. **EXTRAS**: imports, configuración de logging.
2. **EJECUTAR**: 8 líneas que corren todo.

```python
from encuestas_lib.config import Config
from encuestas_lib.pipeline.ingest import IngestPipeline
from encuestas_lib.pipeline.analyze import AnalysisPipeline

config = Config.from_yaml("configs/")
df_harmonized = IngestPipeline(config).run(forzar=False)
results       = AnalysisPipeline(config).run(df_harmonized)
```

### Desde CLI

```bash
python -m encuestas_lib.pipeline.ingest --config configs/
python -m encuestas_lib.pipeline.analyze --config configs/
```

---

## Agregar una nueva encuesta

### Caso 1: formato ya soportado (Atlas, GAD3, Invamer, CNC)

Agrega una fila al `configs/surveys.yaml`:

```yaml
- id: atlas_2026_05_15
  encuestadora: Atlas Intel
  fecha: 2026-05-15
  reader: atlas
  path: "40. CNE-E-DG-2026-XXXXX - ATLAS INTEL/Base de Dados Atlas Semana 051526.xlsx"
  n_muestra: 2500
```

Luego en el notebook: `IngestPipeline(config).run(forzar=True)`. Listo.

### Caso 2: encuestadora nueva (Guarumo, Datexco, …)

1. Crea `encuestas_lib/readers/guarumo.py` heredando de `BaseReader`.
2. Implementa `read()` → debe devolver `pd.DataFrame` con el schema canónico.
3. Registra en `encuestas_lib/readers/registry.py`:

   ```python
   from encuestas_lib.readers.guarumo import GuarumoReader
   READERS["guarumo"] = GuarumoReader
   ```

4. Agrega la encuesta al YAML como Caso 1, con `reader: guarumo`.

**Tiempo estimado**: 30-60 minutos. Antes: re-escribir el script monolítico.

---

## Sobre los pesos (importante)

**El mayor riesgo metodológico** del repo original era usar pesos por encuesta
sin justificación documentada. Ahora `configs/weights.yaml` declara la
estrategia explícitamente:

```yaml
strategy: inverse_recency_size
description: |
  Peso final = n_muestra × decay(días_desde_corte).
  decay(d) = 0.5 ** (d / half_life_days).
  half_life_days = 21 (3 semanas).
params:
  half_life_days: 21
  reference_date: 2026-05-15
```

Esto NO es la única estrategia válida. Pero ahora la decisión es:
**explícita, versionada en git, y discutible**. Cambiar la estrategia es cambiar
un YAML, no buscar números mágicos en un `.py`.

Ver `encuestas_lib/analysis/weighting.py` para implementación.

---

## Análisis disponibles

### Básicos (paridad con el repo original)

| Tabla | Descripción |
| --- | --- |
| `primera_vuelta_total` | Intención de voto agregada con ponderación |
| `voto_por_region` | Voto por región (cierre = 100% por región) |
| `voto_por_edad` | Voto por grupo etario |
| `voto_por_genero` | Voto por sexo |
| `genero_por_candidato_top4` | Distribución de género dentro de los 4 más votados |
| `aprobacion_vs_voto` | Voto condicional a aprobación de Petro |
| `voto_vs_aprobacion` | Aprobación de Petro condicional al voto |
| `indecisos_*` | Demografía de indecisos (edad, región, sexo, estrato) |
| `sesgo_*` | House effects por encuestadora vs promedio del resto |
| `verificacion_100` | Auditoría: todos los cierres en 100% ± 0.25 |

### Avanzados (nuevos)

| Análisis | Descripción |
| --- | --- |
| `trend_primera_vuelta` | Serie temporal con loess y banda 95% por candidato |
| `transferencia_pv_sv` | Matriz: votante PV de X → cómo vota en SV vs Y |
| `techo_potencial_sv` | Para cada candidato: voto PV + intención SV vs cada rival |
| `coalicion_aprobacion` | Voto SV ponderado por aprobación a Petro |
| `volatilidad_encuestadora` | Desviación estándar por encuestadora ajustada por tiempo |
| `indecisos_perfil` | Logit: probabilidad de ser indeciso vs decidido |
| `margen_error_efectivo` | IC95% por encuesta usando diseño muestral implícito |

---

## Tests

```bash
pytest tests/ -v
```

Cobertura mínima en CI: 80% en `harmonization/` y `analysis/`.

---

## Licencia

MIT. Los microdatos originales son públicos del CNE.

## Referencias

- [Consejo Nacional Electoral — encuestas](https://www.cne.gov.co/)
- [PEP 8](https://peps.python.org/pep-0008/), [PEP 257](https://peps.python.org/pep-0257/), [PEP 484](https://peps.python.org/pep-0484/)
- Pandas: [User Guide — Enhancing performance](https://pandas.pydata.org/docs/user_guide/enhancingperf.html)
