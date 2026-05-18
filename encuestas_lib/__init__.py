"""encuestas_lib — Análisis de microdatos de encuestas presidenciales Colombia 2026.

Pipeline modular para ingestión, armonización y análisis de microdatos de
encuestas publicados por el CNE.

Componentes principales:
    - config        : configuración centralizada (@dataclass)
    - harmonization : reglas de normalización (candidatos, demografía, matchups)
    - readers       : un Reader por encuestadora (BaseReader + subclases)
    - pipeline      : orquestación (ingest, analyze) + checkpoints
    - analysis      : tablas y análisis avanzados
    - io            : exportación a Excel / JSON

Uso:
    >>> from encuestas_lib.config import Config
    >>> from encuestas_lib.pipeline.ingest import IngestPipeline
    >>> config = Config.from_yaml("configs/")
    >>> df = IngestPipeline(config).run()
"""

__version__ = "0.1.3"
__author__ = "Pablo Manrique"
