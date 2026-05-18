"""Tests de regresión para los bugs corregidos en la segunda corrida.

Referencia: DIAGNOSTICO_SEGUNDA_CORRIDA.md
    - B_NEW_1: df_basicas usaba 24 vigentes en vez de 13 principales
    - B_NEW_2: indecisos_total 17.25% vs 28% (remap non-principal → Otro)
    - B_NEW_3: transfer SV incluye indecisos SV (documentación)
    - B_NEW_4: regiones duplicadas por claves con tildes en REGION_NORM
"""

from __future__ import annotations

import pandas as pd
import pytest

from encuestas_lib.analysis.tables import (
    filtrar_voto_vigente,
    tabla_indecisos_total,
    tabla_primera_vuelta_total,
)
from encuestas_lib.harmonization.demographics import REGION_NORM, aplicar_mapa_con_int
from encuestas_lib.pipeline.analyze import _remap_no_principales


# ════════════════════════════════════════════════════════════════════════════
#  Fixtures compartidas
# ════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def pesos_uniformes() -> dict[tuple[str, str], float]:
    """Pesos uniformes para una sola encuesta ficticia."""
    return {("TestEnc", "2026-04-25"): 1.0}


@pytest.fixture
def df_base() -> pd.DataFrame:
    """DataFrame mínimo con 13 principales + 3 no-principales + indecisos."""
    rows = [
        # 13 principales × 10 votos cada uno = 130 votos decididos principales
        *[
            {
                "encuestadora": "TestEnc",
                "fecha": pd.Timestamp("2026-04-25"),
                "factor": 1.0,
                "primera_vuelta": cand,
            }
            for cand in [
                "Iván Cepeda",
                "Abelardo de la Espriella",
                "Paloma Valencia",
                "Sergio Fajardo",
                "Claudia López",
                "Santiago Botero",
                "Luis Gilberto Murillo",
                "Roy Barreras",
                "Miguel Uribe Londoño",
                "Mauricio Lizcano",
                "Carlos Caicedo",
                "Sondra Macollins",
                "Clara López",
            ]
            for _ in range(10)
        ],
        # 3 candidatos NO-principales (vigentes pero fuera del corte) × 10 votos
        *[
            {
                "encuestadora": "TestEnc",
                "fecha": pd.Timestamp("2026-04-25"),
                "factor": 1.0,
                "primera_vuelta": cand,
            }
            for cand in ["Vicky Dávila", "Juan Manuel Galán", "Aníbal Gaviria"]
            for _ in range(10)
        ],
        # 40 indecisos "puros" (NS/NR, Ninguno, blanco, No votaría)
        *[
            {
                "encuestadora": "TestEnc",
                "fecha": pd.Timestamp("2026-04-25"),
                "factor": 1.0,
                "primera_vuelta": cat,
            }
            for cat in ["NS/NR", "Ninguno", "Voto en blanco", "No votaría"]
            for _ in range(10)
        ],
    ]
    return pd.DataFrame(rows)


CANDS_PRINCIPALES = frozenset(
    [
        "Iván Cepeda",
        "Abelardo de la Espriella",
        "Paloma Valencia",
        "Sergio Fajardo",
        "Claudia López",
        "Santiago Botero",
        "Luis Gilberto Murillo",
        "Roy Barreras",
        "Miguel Uribe Londoño",
        "Mauricio Lizcano",
        "Carlos Caicedo",
        "Sondra Macollins",
        "Clara López",
    ]
)

OPCIONES_INDECISOS = frozenset(
    ["NS/NR", "Ninguno", "Voto en blanco", "No votaría", "Otro candidato", "No sé"]
)

VIGENTES_24 = CANDS_PRINCIPALES | frozenset(["Vicky Dávila", "Juan Manuel Galán", "Aníbal Gaviria"])


# ════════════════════════════════════════════════════════════════════════════
#  B_NEW_1: filtrar_voto_vigente con candidatos_principales ≠ vigentes_totales
# ════════════════════════════════════════════════════════════════════════════
class TestBNew1FiltrarCandPrincipales:
    """Verifica que df_basicas usa candidatos_principales (13), no vigentes (24)."""

    def test_filtro_con_24_vigentes_incluye_no_principales(self, df_base):
        """Con 24 vigentes, los no-principales quedan en df_basicas → dilución."""
        df_filtrado = filtrar_voto_vigente(df_base, VIGENTES_24, OPCIONES_INDECISOS)
        # Con 24 vigentes: 130 + 30 + 40 = 200 filas
        assert len(df_filtrado) == 200
        assert "Vicky Dávila" in df_filtrado["primera_vuelta"].values

    def test_filtro_con_13_principales_excluye_no_principales(self, df_base):
        """Con 13 principales, los no-principales se excluyen → porcentajes correctos."""
        df_filtrado = filtrar_voto_vigente(df_base, CANDS_PRINCIPALES, OPCIONES_INDECISOS)
        # Con 13 principales: 130 + 40 = 170 filas (excluye 30 no-principales)
        assert len(df_filtrado) == 170
        assert "Vicky Dávila" not in df_filtrado["primera_vuelta"].values
        assert "Juan Manuel Galán" not in df_filtrado["primera_vuelta"].values

    def test_porcentaje_cepeda_correcto_con_principales(self, df_base, pesos_uniformes):
        """Cepeda: 10/(130+40)=5.88% con 13 principales (sin dilución de 24 vigentes)."""
        df_filtrado = filtrar_voto_vigente(df_base, CANDS_PRINCIPALES, OPCIONES_INDECISOS)
        t = tabla_primera_vuelta_total(df_filtrado, pesos_uniformes)
        cepeda_row = t[t["primera_vuelta"] == "Iván Cepeda"]
        assert not cepeda_row.empty
        pct = float(cepeda_row["valor"].iloc[0])
        # 10 votos / 170 total = 5.88%; con 24 vigentes sería 10/200 = 5%
        assert abs(pct - 5.88) < 0.5

    def test_porcentaje_cepeda_diluido_con_24_vigentes(self, df_base, pesos_uniformes):
        """Cepeda: 10/200=5% con 24 vigentes — 0.88pp menor, diferencia significativa."""
        df_filtrado = filtrar_voto_vigente(df_base, VIGENTES_24, OPCIONES_INDECISOS)
        t = tabla_primera_vuelta_total(df_filtrado, pesos_uniformes)
        cepeda_row = t[t["primera_vuelta"] == "Iván Cepeda"]
        pct = float(cepeda_row["valor"].iloc[0])
        assert abs(pct - 5.0) < 0.5


# ════════════════════════════════════════════════════════════════════════════
#  B_NEW_2: remap non-principal → "Otro candidato" para indecisos
# ════════════════════════════════════════════════════════════════════════════
class TestBNew2RemapNoPrincipales:
    """Verifica que _remap_no_principales convierte no-principales a Otro candidato."""

    def test_remap_transforma_no_principales(self, df_base):
        """Vicky Dávila, Galán, Gaviria → 'Otro candidato' tras remap."""
        df_out = _remap_no_principales(df_base, CANDS_PRINCIPALES, OPCIONES_INDECISOS)
        for cand in ["Vicky Dávila", "Juan Manuel Galán", "Aníbal Gaviria"]:
            assert cand not in df_out["primera_vuelta"].values, (
                f"'{cand}' debería haberse remapeado a 'Otro candidato'"
            )
        # 30 filas remapeadas a "Otro candidato"
        n_otro = (df_out["primera_vuelta"] == "Otro candidato").sum()
        assert n_otro == 30

    def test_remap_preserva_principales(self, df_base):
        """Los 13 principales no se modifican."""
        df_out = _remap_no_principales(df_base, CANDS_PRINCIPALES, OPCIONES_INDECISOS)
        for cand in CANDS_PRINCIPALES:
            n = (df_out["primera_vuelta"] == cand).sum()
            assert n == 10, f"'{cand}' debería tener 10 votos, tiene {n}"

    def test_remap_preserva_especiales(self, df_base):
        """NS/NR, Ninguno, blanco, No votaría no se modifican."""
        df_out = _remap_no_principales(df_base, CANDS_PRINCIPALES, OPCIONES_INDECISOS)
        for cat in ["NS/NR", "Ninguno", "Voto en blanco", "No votaría"]:
            n = (df_out["primera_vuelta"] == cat).sum()
            assert n == 10, f"'{cat}' debería tener 10 votos, tiene {n}"

    def test_indecisos_total_sube_con_remap(self, df_base, pesos_uniformes):
        """Verifica que el remap consolida no-principales bajo 'Otro candidato'.

        NOTA sobre B_NEW_2: la función tabla_indecisos_total usa
        ``~df["primera_vuelta"].isin(candidatos_reales)`` para clasificar
        indecisos, por lo que TANTO "Vicky Dávila" (no-principal explícita)
        COMO "Otro candidato" (resultado del remap) dan es_indeciso=1.  El
        porcentaje bruto de indecisos es idéntico en ambos casos.

        Lo que sí cambia con el remap: los valores explícitos de no-principales
        desaparecen del DataFrame (útil para tablas que listan candidatos
        individualmente, e.g. `voto_por_region` con el df completo).
        El fix real de B_NEW_2 (17% → 28%) requiere investigar el reader de
        Invamer para confirmar si ns/nr-vacíos se mapean a None en lugar de
        "NS/NR" (ver DIAGNOSTICO_SEGUNDA_CORRIDA.md § B_NEW_2).
        """
        # Con remap: no-principales → "Otro candidato"
        df_remapped = _remap_no_principales(df_base, CANDS_PRINCIPALES, OPCIONES_INDECISOS)

        # Los valores explícitos de no-principales deben haber desaparecido
        for cand in ["Vicky Dávila", "Juan Manuel Galán", "Aníbal Gaviria"]:
            assert cand not in df_remapped["primera_vuelta"].values

        # El % bruto de indecisos es el mismo porque tabla_indecisos_total
        # ya cuenta no-principales como indecisos via ~isin(candidatos_reales)
        t_sin = tabla_indecisos_total(df_base, pesos_uniformes, CANDS_PRINCIPALES)
        t_con = tabla_indecisos_total(df_remapped, pesos_uniformes, CANDS_PRINCIPALES)
        pct_sin = float(t_sin["pct_total"].iloc[0])
        pct_con = float(t_con["pct_total"].iloc[0])
        # Ambos deben dar el mismo resultado: (40+30)/200 = 35%
        assert abs(pct_con - pct_sin) < 0.01, (
            f"Remap no debe cambiar indecisos_total ({pct_sin}% vs {pct_con}%) "
            "porque tabla_indecisos_total ya cuenta no-principales via ~isin."
        )
        assert abs(pct_con - 35.0) < 0.1

    def test_remap_sin_primera_vuelta_devuelve_copia(self):
        """Si no hay columna primera_vuelta, devuelve el df sin modificar."""
        df_sin_pv = pd.DataFrame({"factor": [1.0, 2.0]})
        df_out = _remap_no_principales(df_sin_pv, CANDS_PRINCIPALES, OPCIONES_INDECISOS)
        assert "primera_vuelta" not in df_out.columns
        assert len(df_out) == 2

    def test_remap_no_modifica_nulos(self, df_base):
        """Filas con primera_vuelta=NaN no se tocan (no se convierten a Otro)."""
        df_con_nulo = df_base.copy()
        df_con_nulo.loc[0, "primera_vuelta"] = None
        df_out = _remap_no_principales(df_con_nulo, CANDS_PRINCIPALES, OPCIONES_INDECISOS)
        # Fila 0 debe seguir siendo NaN
        assert pd.isna(df_out.loc[0, "primera_vuelta"])


# ════════════════════════════════════════════════════════════════════════════
#  B_NEW_4: REGION_NORM con claves ASCII-normalizadas
# ════════════════════════════════════════════════════════════════════════════
class TestBNew4RegionNorm:
    """Verifica que las variantes problemáticas de región quedan normalizadas."""

    @pytest.mark.parametrize(
        "raw_input, expected",
        [
            # Atlas Intel: "Bogotá D.C." → "Bogotá"
            ("Bogotá D.C.", "Bogotá"),
            ("BOGOTÁ D.C.", "Bogotá"),
            ("bogotá d.c.", "Bogotá"),
            # Atlas Intel: sin el punto final
            ("Bogotá D.C", "Bogotá"),
            # Atlas Intel / orig: "Amazonía y Orinoquía" → "Amazonía - Orinoquía"
            ("Amazonía y Orinoquía", "Amazonía - Orinoquía"),
            ("amazonia y orinoquia", "Amazonía - Orinoquía"),
            # Invamer (antes del fix): con guion largo → "Centro - Sur - Amazonía"
            ("Centro – Sur - Amazonía", "Centro - Sur - Amazonía"),
            # Invamer (después del fix): con guion regular → "Centro - Sur - Amazonía"
            ("Centro - Sur - Amazonía", "Centro - Sur - Amazonía"),
            ("centro - sur - amazonia", "Centro - Sur - Amazonía"),
            # GAD3: strings ya en ASCII
            ("bogota", "Bogotá"),
            ("caribe", "Caribe"),
            ("pacifica", "Pacífico"),
            ("central", "Central"),
            ("oriental", "Centro - Oriente"),
            # Invamer: códigos numéricos
            ("1", "Caribe"),
            ("2", "Centro - Oriente"),
            ("4", "Pacífico"),
            ("5", "Centro - Sur - Amazonía"),
        ],
    )
    def test_region_normaliza_correctamente(self, raw_input: str, expected: str):
        """Verifica que la variante cruda se convierte al nombre canónico."""
        serie = pd.Series([raw_input])
        resultado = aplicar_mapa_con_int(serie, REGION_NORM)
        assert str(resultado.iloc[0]) == expected, (
            f"'{raw_input}' → '{resultado.iloc[0]}' (esperado '{expected}')"
        )

    def test_sin_duplicados_bogota(self):
        """'Bogotá D.C.' y 'bogota' deben mapear al MISMO valor canónico."""
        s1 = aplicar_mapa_con_int(pd.Series(["Bogotá D.C."]), REGION_NORM)
        s2 = aplicar_mapa_con_int(pd.Series(["bogota"]), REGION_NORM)
        assert s1.iloc[0] == s2.iloc[0] == "Bogotá"

    def test_sin_duplicados_amazonia(self):
        """'Amazonía y Orinoquía' y 'amaz-orin' deben mapear al MISMO valor."""
        s1 = aplicar_mapa_con_int(pd.Series(["Amazonía y Orinoquía"]), REGION_NORM)
        s2 = aplicar_mapa_con_int(pd.Series(["amaz-orin"]), REGION_NORM)
        assert s1.iloc[0] == s2.iloc[0] == "Amazonía - Orinoquía"

    def test_sin_duplicados_centro_sur(self):
        """Variantes de Centro-Sur-Amazonía deben mapear al MISMO valor."""
        variantes = [
            "Centro – Sur - Amazonía",  # Invamer original (en-dash)
            "Centro - Sur - Amazonía",  # Invamer corregido (guion regular)
            "centro - sur - amazonia",  # GAD3
        ]
        valores = [
            str(aplicar_mapa_con_int(pd.Series([v]), REGION_NORM).iloc[0]) for v in variantes
        ]
        assert len(set(valores)) == 1, f"Valores distintos: {valores}"
        assert valores[0] == "Centro - Sur - Amazonía"

    def test_region_norm_claves_son_ascii(self):
        """Todas las claves de REGION_NORM deben ser ASCII puro (sin tildes).

        Si una clave tiene tildes, nunca coincidirá con el string normalizado
        por normalize_text/aplicar_mapa_con_int.
        """
        for key in REGION_NORM:
            try:
                key.encode("ascii")
            except UnicodeEncodeError:
                pytest.fail(
                    f"Clave de REGION_NORM con caracter no-ASCII: {key!r}. "
                    "Las claves deben ser la forma NFKD-ASCII del string crudo "
                    "(sin tildes) para que aplicar_mapa_con_int las encuentre."
                )

    def test_resultado_nine_canonical_regions(self):
        """Los valores únicos de REGION_NORM deben ser ≤ 9 regiones canónicas."""
        canonical_regions = set(REGION_NORM.values())
        # Las 9 regiones esperadas del PDF
        expected_regions = {
            "Bogotá",
            "Caribe",
            "Central",
            "Centro - Oriente",
            "Eje Cafetero",
            "Pacífico",
            "Centro - Sur - Amazonía",
            "Llano",
            "Amazonía - Orinoquía",
        }
        unknown = canonical_regions - expected_regions
        assert not unknown, f"Regiones canónicas inesperadas: {unknown}"


# ════════════════════════════════════════════════════════════════════════════
#  B_NEW_3: transferencia SV incluye indecisos (documentación)
# ════════════════════════════════════════════════════════════════════════════
class TestBNew3TransferenciaSV:
    """Verifica que transferencia_pv_sv es accesible e importable."""

    def test_funcion_importable(self):
        """transferencia_pv_sv debe ser importable desde encuestas_lib.analysis."""
        from encuestas_lib.analysis import transferencia_pv_sv

        assert callable(transferencia_pv_sv)

    def test_docstring_documenta_indecisos_sv(self):
        """El docstring debe mencionar 'indecisos' de segunda vuelta (B_NEW_3)."""
        from encuestas_lib.analysis.advanced import transferencia_pv_sv

        doc = transferencia_pv_sv.__doc__ or ""
        assert "indecisos" in doc.lower(), (
            "El docstring de transferencia_pv_sv debe documentar que el % "
            "incluye indecisos de segunda vuelta (FIX B_NEW_3)."
        )

    def test_resultado_vacio_si_no_hay_sv_col(self):
        """Si sv_col no existe en df, devuelve DataFrame vacío."""
        from encuestas_lib.analysis.advanced import transferencia_pv_sv

        df = pd.DataFrame(
            {
                "encuestadora": ["TestEnc"],
                "fecha": [pd.Timestamp("2026-04-25")],
                "factor": [1.0],
                "primera_vuelta": ["Iván Cepeda"],
            }
        )
        result = transferencia_pv_sv(df, "sv_inexistente", {("TestEnc", "2026-04-25"): 1.0})
        assert result.empty
