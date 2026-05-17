"""Pipelines de ingestión y análisis."""

from encuestas_lib.pipeline.analyze import AnalysisPipeline
from encuestas_lib.pipeline.checkpoints import cargar_o_procesar
from encuestas_lib.pipeline.ingest import IngestPipeline

__all__ = ["AnalysisPipeline", "IngestPipeline", "cargar_o_procesar"]
