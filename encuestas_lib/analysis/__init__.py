"""Tablas y análisis sobre microdatos ingestados.

Re-exporta la API pública para uso desde notebooks:

    from encuestas_lib.analysis import (
        tabla_primera_vuelta_total,
        trend_primera_vuelta,
        margen_error_efectivo,
        ...
    )
"""

from encuestas_lib.analysis.advanced import (
    coalicion_aprobacion,
    indecisos_perfil,
    margen_error_efectivo,
    sv_columns,
    techo_potencial_sv,
    transferencia_pv_sv,
    trend_primera_vuelta,
    volatilidad_encuestadora,
)
from encuestas_lib.analysis.tables import (
    es_indeciso,
    filtrar_voto_vigente,
    sesgo_por_encuestadora,
    tabla_aprobacion_vs_voto,
    tabla_genero_por_candidato_top4,
    tabla_indecisos_demograficas,
    tabla_indecisos_total,
    tabla_primera_vuelta_total,
    tabla_voto_por_edad,
    tabla_voto_por_genero,
    tabla_voto_por_region,
    tabla_voto_vs_aprobacion,
)
from encuestas_lib.analysis.validation import (
    resumen_validacion,
    verificar_cierres_100,
)
from encuestas_lib.analysis.weighting import (
    calcular_por_encuesta,
    combinar_entre_encuestas,
    resolve_weights,
)

__all__ = [
    # weighting
    "calcular_por_encuesta",
    # advanced
    "coalicion_aprobacion",
    "combinar_entre_encuestas",
    # tables
    "es_indeciso",
    "filtrar_voto_vigente",
    "indecisos_perfil",
    "margen_error_efectivo",
    "resolve_weights",
    # validation
    "resumen_validacion",
    "sesgo_por_encuestadora",
    "sv_columns",
    "tabla_aprobacion_vs_voto",
    "tabla_genero_por_candidato_top4",
    "tabla_indecisos_demograficas",
    "tabla_indecisos_total",
    "tabla_primera_vuelta_total",
    "tabla_voto_por_edad",
    "tabla_voto_por_genero",
    "tabla_voto_por_region",
    "tabla_voto_vs_aprobacion",
    "techo_potencial_sv",
    "transferencia_pv_sv",
    "trend_primera_vuelta",
    "verificar_cierres_100",
    "volatilidad_encuestadora",
]
