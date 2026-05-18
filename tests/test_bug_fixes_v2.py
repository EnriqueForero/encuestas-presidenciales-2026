"""Tests para B_NEW_5 (techo_potencial_sv) y B_NEW_6 (EDAD_COLAPSO_3).

Referencia: DIAGNOSTICO_SEGUNDA_CORRIDA.md (tercera corrida).
"""

from __future__ import annotations

import pandas as pd
import pytest

from encuestas_lib.analysis.advanced import techo_potencial_sv
from encuestas_lib.harmonization.demographics import EDAD_COLAPSO_3, aplicar_mapa_con_int


# ════════════════════════════════════════════════════════════════════════════
#  Fixtures
# ════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def pesos() -> dict[tuple[str, str], float]:
    return {("TestEnc", "2026-04-25"): 1.0}


@pytest.fixture
def df_sv() -> pd.DataFrame:
    """DataFrame mínimo con PV + una columna SV binaria para techo."""
    # 100 respondentes: 40 Cepeda PV, 30 Espriella PV, 30 indecisos PV
    # En SV Cepeda vs Espriella: 60 → Cepeda, 25 → Espriella, 15 → Ninguno
    rows = (
        [
            {
                "encuestadora": "TestEnc",
                "fecha": pd.Timestamp("2026-04-25"),
                "factor": 1.0,
                "primera_vuelta": "Iván Cepeda",
                "sv_cepeda_vs_espriella": "Iván Cepeda",
            }
        ]
        * 40
        + [
            {
                "encuestadora": "TestEnc",
                "fecha": pd.Timestamp("2026-04-25"),
                "factor": 1.0,
                "primera_vuelta": "Abelardo de la Espriella",
                "sv_cepeda_vs_espriella": "Abelardo de la Espriella",
            }
        ]
        * 20
        + [
            {
                "encuestadora": "TestEnc",
                "fecha": pd.Timestamp("2026-04-25"),
                "factor": 1.0,
                "primera_vuelta": "Abelardo de la Espriella",
                "sv_cepeda_vs_espriella": "Iván Cepeda",
            }
        ]
        * 10
        + [
            {
                "encuestadora": "TestEnc",
                "fecha": pd.Timestamp("2026-04-25"),
                "factor": 1.0,
                "primera_vuelta": "Ninguno",
                "sv_cepeda_vs_espriella": "Ninguno",
            }
        ]
        * 30
    )
    return pd.DataFrame(rows)


VIGENTES_TEST = {"Iván Cepeda", "Abelardo de la Espriella"}


# ════════════════════════════════════════════════════════════════════════════
#  B_NEW_5: techo_potencial_sv — normalize_within correcto
# ════════════════════════════════════════════════════════════════════════════
class TestBNew5TechoPotencial:
    """Verifica que techo_potencial_sv usa normalize_within=[] en PV y SV."""

    def test_voto_pv_pct_es_porcentaje_real(self, df_sv, pesos):
        """voto_pv_pct debe ser el % real de Cepeda entre vigentes decididos.

        Con el bug (normalize_within=["primera_vuelta"]):
            Cada candidato queda con valor=100 → voto_pv_pct = 100/200 = 50% × escala.
            En producción daba 4.35% porque había 24 vigentes (100/2400 aprox).

        Con el fix (normalize_within=[]):
            Cepeda = 40% de los 100 respondentes.
            Entre vigentes decididos (40+30=70): voto_pv_renorm = 40/70*100 = 57.14%.
        """
        t = techo_potencial_sv(
            df_sv,
            candidato_canonical="Iván Cepeda",
            candidato_key="cepeda",
            candidatos_vigentes=VIGENTES_TEST,
            pesos=pesos,
            rivales_keys=["espriella"],
        )
        assert not t.empty, "El resultado no debe estar vacío"
        voto_pv = float(t["voto_pv_pct"].iloc[0])
        # Cepeda = 40/100 = 40%; entre vigentes (70/100): 40/70*100 = 57.14%
        assert voto_pv > 15, (
            f"voto_pv_pct={voto_pv:.2f}% demasiado bajo — B_NEW_5 probablemente activo. "
            "Con normalize_within=['primera_vuelta'] el resultado es ~4-5%."
        )
        assert abs(voto_pv - 57.14) < 2.0, (
            f"voto_pv_pct esperado ~57.14% (Cepeda entre decididos), actual={voto_pv:.2f}%"
        )

    def test_voto_sv_pct_no_es_100_pct(self, df_sv, pesos):
        """voto_sv_pct debe ser < 100%.

        Con el bug (normalize_within=[sv_col]):
            Cada valor del SV queda normalizado a 100% dentro de sí mismo → 100%.
        Con el fix (normalize_within=[]):
            Cepeda en SV = (40+10)/100 = 50% del total de respondentes.
        """
        t = techo_potencial_sv(
            df_sv,
            candidato_canonical="Iván Cepeda",
            candidato_key="cepeda",
            candidatos_vigentes=VIGENTES_TEST,
            pesos=pesos,
            rivales_keys=["espriella"],
        )
        assert not t.empty
        voto_sv = float(t["voto_sv_pct"].iloc[0])
        assert voto_sv < 90, (
            f"voto_sv_pct={voto_sv:.2f}% demasiado alto — B_NEW_5 probablemente activo. "
            "Con normalize_within=[sv_col] el resultado es 100%."
        )
        # Cepeda en SV: 40 (propios) + 10 (de Espriella) = 50/100 = 50%
        assert abs(voto_sv - 50.0) < 2.0, (
            f"voto_sv_pct esperado ~50% (Cepeda en SV total), actual={voto_sv:.2f}%"
        )

    def test_techo_pp_coherente(self, df_sv, pesos):
        """techo_pp = voto_sv - voto_pv debe ser negativo o positivo coherente."""
        t = techo_potencial_sv(
            df_sv,
            candidato_canonical="Iván Cepeda",
            candidato_key="cepeda",
            candidatos_vigentes=VIGENTES_TEST,
            pesos=pesos,
            rivales_keys=["espriella"],
        )
        assert not t.empty
        techo = float(t["techo_pp"].iloc[0])
        voto_pv = float(t["voto_pv_pct"].iloc[0])
        voto_sv = float(t["voto_sv_pct"].iloc[0])
        assert abs(techo - (voto_sv - voto_pv)) < 0.1, (
            f"techo_pp={techo:.2f} debe ser voto_sv ({voto_sv:.2f}) - voto_pv ({voto_pv:.2f})"
        )

    def test_rival_inexistente_devuelve_vacio(self, df_sv, pesos):
        """Si no hay columna SV para ese rival, el resultado es vacío."""
        t = techo_potencial_sv(
            df_sv,
            candidato_canonical="Iván Cepeda",
            candidato_key="cepeda",
            candidatos_vigentes=VIGENTES_TEST,
            pesos=pesos,
            rivales_keys=["valencia"],  # no hay sv_cepeda_vs_valencia en df_sv
        )
        assert t.empty


# ════════════════════════════════════════════════════════════════════════════
#  B_NEW_6: EDAD_COLAPSO_3 colapsa los 9 grupos a 3
# ════════════════════════════════════════════════════════════════════════════
class TestBNew6EdadColapso:
    """Verifica que EDAD_COLAPSO_3 colapsa todos los grupos etarios a 3."""

    @pytest.mark.parametrize(
        "grupo_crudo, grupo_esperado",
        [
            # Atlas Intel: granulares jóvenes
            ("18-24", "18-34"),
            ("25-34", "18-34"),
            # GAD3 / Invamer: agregado
            ("18-34", "18-34"),
            # Edad media
            ("35-44", "35-54"),
            ("45-54", "35-54"),
            ("35-54", "35-54"),
            # Atlas 45-59 (no estándar)
            ("45-59", "55+"),
            # Mayores
            ("55+", "55+"),
            ("60+", "55+"),
        ],
    )
    def test_colapso_correcto(self, grupo_crudo: str, grupo_esperado: str):
        """Cada grupo crudo debe colapsarse al grupo canónico correcto."""
        assert EDAD_COLAPSO_3.get(grupo_crudo) == grupo_esperado, (
            f"'{grupo_crudo}' debe colapsar a '{grupo_esperado}', "
            f"obtenido '{EDAD_COLAPSO_3.get(grupo_crudo)}'"
        )

    def test_resultado_solo_3_grupos(self):
        """Aplicar EDAD_COLAPSO_3 a todos los grupos crudos debe dar solo 3 destinos."""
        grupos_destino = set(EDAD_COLAPSO_3.values())
        assert grupos_destino == {"18-34", "35-54", "55+"}, (
            f"Los grupos canónicos deben ser exactamente {{18-34, 35-54, 55+}}, "
            f"obtenido: {grupos_destino}"
        )

    def test_colapso_via_aplicar_mapa_con_int(self):
        """Verifica el flujo completo: EDAD_NORM → EDAD_COLAPSO_3 via aplicar_mapa_con_int."""
        from encuestas_lib.harmonization.demographics import EDAD_NORM

        grupos_crudos = pd.Series(
            ["18 - 24", "25 - 34", "entre 35 y 44", "45-54", "55+", "60 - 100", "55 ó más"]
        )
        # Paso 1: EDAD_NORM
        normalizados = aplicar_mapa_con_int(grupos_crudos, EDAD_NORM)
        # Paso 2: EDAD_COLAPSO_3
        colapsados = normalizados.map(EDAD_COLAPSO_3).where(
            normalizados.map(EDAD_COLAPSO_3).notna(), normalizados
        )
        grupos_finales = set(colapsados.dropna().unique())
        assert grupos_finales == {"18-34", "35-54", "55+"}, (
            f"Después de EDAD_NORM + EDAD_COLAPSO_3 solo deben quedar 3 grupos, "
            f"obtenido: {grupos_finales}"
        )

    def test_grupos_no_mapeados_se_preservan(self):
        """Un grupo sin mapping en EDAD_COLAPSO_3 debe preservarse sin cambio."""
        # "desconocido" no está en EDAD_COLAPSO_3
        resultado = EDAD_COLAPSO_3.get("desconocido")
        assert resultado is None, "get() debe devolver None para claves desconocidas"
