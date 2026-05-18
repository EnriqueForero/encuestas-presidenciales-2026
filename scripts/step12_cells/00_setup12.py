# ══════════════════════════════════════════════════════════════════════
#  Step 12 · Setup — Análisis predictivo avanzado
# ══════════════════════════════════════════════════════════════════════
from encuestas_lib.analysis.electoral import (
    calcular_techo_rechazo, resumen_escenarios_2v, sensibilidad_2v,
    simular_segunda_vuelta, trasvase_candidato,
)
from encuestas_lib.viz.charts.step12 import MATRIZ_A, MATRIZ_B, PESOS_PV_DOC

# El template ``lsv`` ya fue registrado en el Setup de Step 11.
# Si esta celda corre primero, lo registramos de forma idempotente:
from encuestas_lib.viz import register_template
register_template()

FIGURAS12 = {}
print("✅ Step 12 setup listo — módulo electoral importado")
print(f"   Pesos PV base: {PESOS_PV_DOC}")
