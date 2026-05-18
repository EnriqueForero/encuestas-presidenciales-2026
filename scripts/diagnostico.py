"""Diagnóstico pre-producción del pipeline de encuestas.

Ejecutar ANTES de correr el pipeline completo para detectar:
    - candidatos_principales vacío o mal configurado  (B_NEW_1)
    - checkpoint parquet desactualizado               (B_NEW_4 / B_NEW_6)
    - archivos de encuesta faltantes
    - regiones duplicadas en el parquet existente
    - grupos de edad no colapsados en el parquet

Uso:
    python scripts/diagnostico.py --config configs/
    python scripts/diagnostico.py --config configs/ --excel data/outputs/analisis_consolidado.xlsx

El script imprime un reporte y termina con código 0 (todo OK)
o código 1 (hay checks fallidos que bloquean producción).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# ── Targets del PDF La Silla Vacía (2026-05-13) ──────────────────────────────
PDF_TARGETS: dict[str, float] = {
    "Iván Cepeda": 37.0,
    "Abelardo de la Espriella": 27.0,
    "Paloma Valencia": 19.0,
}
PDF_INDECISOS: float = 28.0
PDF_CEPEDA_APRUEBA_PETRO: float = 84.0
PDF_TRANSFERENCIA_ABELARDO_PALOMA: float = 79.0  # en matchup Cepeda vs Valencia

TOLERANCIA_PP: float = 2.0  # ±pp aceptable para paridad
REGIONES_ESPERADAS: int = 9
GRUPOS_EDAD_ESPERADOS: int = 3  # 18-34 / 35-54 / 55+
GRUPOS_EDAD_CANONICOS: set[str] = {"18-34", "35-54", "55+"}

# ─────────────────────────────────────────────────────────────────────────────


def _ok(msg: str) -> None:
    print(f"  ✅  {msg}")


def _warn(msg: str) -> None:
    print(f"  ⚠   {msg}")


def _fail(msg: str) -> None:
    print(f"  ❌  {msg}")


def _section(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


# ─────────────────────────────────────────────────────────────────────────────
#  CHECK 1: Configuración
# ─────────────────────────────────────────────────────────────────────────────
def check_config(configs_dir: Path) -> tuple[bool, object]:
    """Valida que el Config carga bien y candidatos_principales está completo."""
    _section("CHECK 1 · Configuración (candidates.yaml / surveys.yaml / weights.yaml)")
    ok = True
    config = None

    try:
        from encuestas_lib.config import Config

        config = Config.from_yaml(configs_dir)
        _ok(f"Config cargado desde {configs_dir}")
    except Exception as exc:
        _fail(f"Error al cargar Config: {exc}")
        return False, None

    # candidatos_principales
    cp = config.candidatos_principales
    if not cp:
        _fail(
            "candidatos_principales está VACÍO en candidates.yaml.  "
            "Esto es la causa de B_NEW_1: filtrar_voto_vigente usará los 24 vigentes "
            "en lugar de los 13 principales → porcentajes diluidos (~27% vs ~37% Cepeda).\n"
            "       ACCIÓN: agregar la sección `candidatos_principales:` en configs/candidates.yaml"
        )
        ok = False
    else:
        _ok(f"candidatos_principales cargados: {len(cp)} candidatos")
        expected_13 = {
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
        }
        missing = expected_13 - cp
        extra = cp - expected_13
        if missing:
            _warn(f"Candidatos faltantes en principales: {missing}")
        if extra:
            _warn(f"Candidatos extra no esperados en principales: {extra}")
        if not missing and not extra:
            _ok("Los 13 candidatos principales coinciden con el corte del PDF")

    # surveys
    _ok(f"Surveys registrados: {len(config.surveys)}")
    missing_files = [s for s in config.surveys if not s.path.exists()]
    if missing_files:
        for s in missing_files:
            _fail(f"Archivo no encontrado: {s.path}  ({s.id})")
        ok = False
    else:
        _ok("Todos los archivos de encuesta encontrados en disco")

    # weights
    _ok(f"Estrategia de ponderación activa: {config.weighting.active_strategy}")
    if config.weighting.active_strategy == "manual":
        n_weights = len(config.weighting.manual_weights)
        _ok(f"Pesos manuales configurados: {n_weights} entradas")
        surveys_sin_peso = [
            s
            for s in config.surveys
            if config.weighting.manual_weights.get((s.encuestadora, s.fecha_str), 0) == 0
        ]
        if surveys_sin_peso:
            _warn(
                f"{len(surveys_sin_peso)} encuesta(s) sin peso manual (se excluirán): "
                + ", ".join(s.id for s in surveys_sin_peso)
            )

    return ok, config


# ─────────────────────────────────────────────────────────────────────────────
#  CHECK 2: Checkpoint parquet
# ─────────────────────────────────────────────────────────────────────────────
def check_checkpoint(config: object) -> tuple[bool, object]:
    """Verifica que el checkpoint parquet existe y no tiene problemas conocidos."""
    import pandas as pd

    _section("CHECK 2 · Checkpoint parquet (encuestas_concatenadas.parquet)")
    ok = True
    df = None

    parquet_path = config.paths.processed_dir / "encuestas_concatenadas.parquet"

    if not parquet_path.exists():
        _warn(
            "Checkpoint NO existe.  El pipeline correrá la ingesta desde cero "
            "(puede tomar varios minutos)."
        )
        return True, None  # no es un error — se creará al correr

    try:
        df = pd.read_parquet(parquet_path)
    except Exception as exc:
        _fail(f"Error al leer parquet: {exc}")
        return False, None

    n_rows = len(df)
    _ok(f"Checkpoint cargado: {n_rows:,} filas · {len(df.columns)} columnas")

    # ── Regiones duplicadas (B_NEW_4) ─────────────────────────────────
    if "region" in df.columns:
        regiones = df["region"].dropna().unique().tolist()
        n_reg = len(regiones)
        duplicados_region = {
            ("Bogotá", "Bogotá D.C."),
            ("Amazonía - Orinoquía", "Amazonía y Orinoquía"),
            ("Centro - Sur - Amazonía", "Centro – Sur - Amazonía"),
        }
        dup_activos = [(a, b) for (a, b) in duplicados_region if a in regiones and b in regiones]
        if n_reg > REGIONES_ESPERADAS:
            _fail(
                f"B_NEW_4 ACTIVO en checkpoint: {n_reg} regiones en vez de {REGIONES_ESPERADAS}.\n"
                f"       Pares duplicados: {dup_activos}\n"
                "       ACCIÓN: borrar el parquet y re-correr con --forzar para "
                "que demographics.py actualizado normalice las regiones."
            )
            ok = False
        else:
            _ok(f"Regiones en checkpoint: {n_reg} (esperado ≤{REGIONES_ESPERADAS}) ✓")
    else:
        _warn("Columna 'region' no encontrada en checkpoint")

    # ── Grupos de edad no colapsados (B_NEW_6) ─────────────────────────
    if "edad_grupo" in df.columns:
        grupos_edad = set(df["edad_grupo"].dropna().unique())
        no_canonicos = grupos_edad - GRUPOS_EDAD_CANONICOS
        if no_canonicos:
            _fail(
                f"B_NEW_6 ACTIVO en checkpoint: grupos de edad no colapsados: {no_canonicos}.\n"
                "       ACCIÓN: borrar el parquet y re-correr con --forzar para "
                "que EDAD_COLAPSO_3 se aplique en la ingesta."
            )
            ok = False
        else:
            _ok(f"Grupos de edad en checkpoint: {sorted(grupos_edad)} ✓")

    # ── Encuestadoras en parquet vs config ─────────────────────────────
    if "encuestadora" in df.columns and "fecha" in df.columns:
        parquet_enc = set(
            df.groupby(["encuestadora", df["fecha"].astype(str).str[:10]]).size().index
        )
        config_enc = {(s.encuestadora, s.fecha_str) for s in config.surveys}
        solo_en_parquet = parquet_enc - config_enc
        solo_en_config = config_enc - parquet_enc
        if solo_en_config:
            _warn(
                f"Encuestas en config pero NO en parquet (necesitan ingesta): "
                f"{solo_en_config}\n"
                "       ACCIÓN: correr con --forzar para re-ingestar."
            )
        if solo_en_parquet:
            _warn(f"Encuestas en parquet pero NO en config (datos huérfanos): {solo_en_parquet}")
        if not solo_en_config and not solo_en_parquet:
            _ok("Parquet y config tienen las mismas encuestas ✓")

    return ok, df


# ─────────────────────────────────────────────────────────────────────────────
#  CHECK 3: Output Excel (si se pasa --excel)
# ─────────────────────────────────────────────────────────────────────────────
def check_excel(excel_path: Path) -> bool:
    """Valida el Excel de output contra los targets del PDF."""
    import pandas as pd

    _section(f"CHECK 3 · Output Excel ({excel_path.name})")
    ok = True

    if not excel_path.exists():
        _warn(f"Excel no encontrado: {excel_path}  (omitiendo check 3)")
        return True

    xl = pd.ExcelFile(excel_path)
    sheets = xl.sheet_names

    # ── Primera vuelta ─────────────────────────────────────────────────
    if "primera_vuelta_total" in sheets:
        pv = pd.read_excel(xl, "primera_vuelta_total")
        print("\n  [primera_vuelta_total]")
        for cand, target in PDF_TARGETS.items():
            row = pv[pv["primera_vuelta"] == cand]
            if row.empty:
                _fail(f"{cand}: no encontrado en la tabla")
                ok = False
                continue
            val = float(row["valor"].iloc[0])
            gap = val - target
            status = "✅" if abs(gap) <= TOLERANCIA_PP else "❌"
            print(f"  {status}  {cand:<35} actual={val:5.2f}%  PDF={target:.1f}%  gap={gap:+.2f}pp")
            if abs(gap) > TOLERANCIA_PP:
                ok = False
                if abs(gap) > 8:
                    print(
                        "       ↳ Gap > 8pp sugiere B_NEW_1 activo: "
                        "candidatos_principales vacío o parquet sin re-ingestar."
                    )
    else:
        _warn("Hoja 'primera_vuelta_total' no encontrada")

    # ── Indecisos ──────────────────────────────────────────────────────
    if "indecisos_total" in sheets:
        ind = pd.read_excel(xl, "indecisos_total")
        val_ind = float(ind["pct_total"].iloc[0])
        gap_ind = val_ind - PDF_INDECISOS
        status = "✅" if abs(gap_ind) <= TOLERANCIA_PP else "❌"
        print("\n  [indecisos_total]")
        print(
            f"  {status}  indecisos       actual={val_ind:5.2f}%  "
            f"PDF={PDF_INDECISOS:.1f}%  gap={gap_ind:+.2f}pp"
        )
        if abs(gap_ind) > TOLERANCIA_PP:
            ok = False
            print(
                "       ↳ Gap en indecisos requiere investigación del reader Invamer "
                "(ver DIAGNOSTICO_SEGUNDA_CORRIDA.md § B_NEW_2)."
            )

    # ── Aprobación Petro × voto ────────────────────────────────────────
    if "voto_vs_aprobacion" in sheets:
        vva = pd.read_excel(xl, "voto_vs_aprobacion")
        print("\n  [voto_vs_aprobacion — Cepeda % aprueba Petro]")
        if "primera_vuelta" in vva.columns and "Aprueba" in vva.columns:
            row = vva[vva["primera_vuelta"] == "Iván Cepeda"]
            if not row.empty:
                val_ap = float(row["Aprueba"].iloc[0])
                gap_ap = val_ap - PDF_CEPEDA_APRUEBA_PETRO
                status = "✅" if abs(gap_ap) <= TOLERANCIA_PP else "❌"
                print(
                    f"  {status}  Cepeda % aprueba Petro  actual={val_ap:5.2f}%  "
                    f"PDF={PDF_CEPEDA_APRUEBA_PETRO:.1f}%  gap={gap_ap:+.2f}pp"
                )
                if abs(gap_ap) > TOLERANCIA_PP:
                    ok = False

    # ── Regiones ───────────────────────────────────────────────────────
    if "voto_por_region" in sheets:
        reg = pd.read_excel(xl, "voto_por_region")
        n_reg = len(reg)
        print("\n  [voto_por_region]")
        status = "✅" if n_reg <= REGIONES_ESPERADAS else "❌"
        print(f"  {status}  Regiones en output: {n_reg}  (esperado: {REGIONES_ESPERADAS})")
        if n_reg > REGIONES_ESPERADAS:
            ok = False
            reg_col = reg.columns[0]
            reg_names = reg[reg_col].tolist()
            print(f"       ↳ Regiones encontradas: {reg_names}")
            print(
                "       ↳ Causa: B_NEW_4 activo (parquet no re-ingesta "
                "o demographics.py no actualizado)."
            )

    # ── Edad ───────────────────────────────────────────────────────────
    if "voto_por_edad" in sheets:
        edad = pd.read_excel(xl, "voto_por_edad")
        n_edad = len(edad)
        print("\n  [voto_por_edad]")
        status = "✅" if n_edad <= GRUPOS_EDAD_ESPERADOS else "❌"
        print(
            f"  {status}  Grupos de edad en output: {n_edad}  (esperado: {GRUPOS_EDAD_ESPERADOS})"
        )
        if n_edad > GRUPOS_EDAD_ESPERADOS:
            ok = False
            edad_col = edad.columns[0]
            grupos = edad[edad_col].tolist()
            print(f"       ↳ Grupos encontrados: {grupos}")
            print("       ↳ Causa: B_NEW_6 activo (EDAD_COLAPSO_3 no aplicado o parquet viejo).")

    # ── Transferencia SV ───────────────────────────────────────────────
    sv_sheet = "transfer_sv_cepeda_vs_valencia"
    if sv_sheet in sheets:
        t = pd.read_excel(xl, sv_sheet)
        print("\n  [transfer_sv_cepeda_vs_valencia — Abelardo → Paloma]")
        row = t[t["primera_vuelta"] == "Abelardo de la Espriella"]
        if not row.empty:
            sv_col_name = "sv_cepeda_vs_valencia"
            paloma_row = (
                row[row[sv_col_name] == "Paloma Valencia"]
                if sv_col_name in row.columns
                else pd.DataFrame()
            )
            if not paloma_row.empty:
                val_tr = float(paloma_row["valor"].iloc[0])
                print(
                    f"  ⚠   Abelardo→Paloma (incl. indecisos SV): {val_tr:.2f}%\n"
                    f"       PDF reporta {PDF_TRANSFERENCIA_ABELARDO_PALOMA:.0f}% "
                    "(excluyendo indecisos SV — diferencia metodológica esperada, ver B_NEW_3)"
                )

    # ── Techo potencial ────────────────────────────────────────────────
    if "techo_potencial_cepeda" in sheets:
        techo = pd.read_excel(xl, "techo_potencial_cepeda")
        print("\n  [techo_potencial_cepeda]")
        if not techo.empty:
            voto_pv = float(techo["voto_pv_pct"].iloc[0])
            status = "✅" if voto_pv > 15 else "❌"
            print(f"  {status}  voto_pv_pct (Cepeda): {voto_pv:.2f}%  (esperado > 15%)")
            if voto_pv <= 15:
                ok = False
                print(
                    "       ↳ B_NEW_5 activo: normalize_within incorrecto en "
                    "techo_potencial_sv.  Aplicar fix en advanced.py."
                )

    # ── Validación de cierres ──────────────────────────────────────────
    if "_validacion_cierres" in sheets:
        val = pd.read_excel(xl, "_validacion_cierres")
        if "ok" in val.columns:
            n_ok = int(val["ok"].sum())
            n_fail = int((~val["ok"]).sum())
            print("\n  [_validacion_cierres]")
            status = "✅" if n_fail == 0 else "❌"
            print(f"  {status}  Cierres a 100%: {n_ok} OK · {n_fail} fallidas")
            if n_fail > 0:
                ok = False
                print(val[~val["ok"]].head(5).to_string(index=False))

    return ok


# ─────────────────────────────────────────────────────────────────────────────
#  CHECK 4: Acción recomendada
# ─────────────────────────────────────────────────────────────────────────────
def recomendar_accion(config: object, df_parquet: object) -> None:
    """Imprime el plan de acción más corto para llegar a resultados correctos."""
    import pandas as pd

    _section("CHECK 4 · Plan de acción recomendado")

    acciones: list[str] = []

    # ¿candidatos_principales vacío?
    if config and not config.candidatos_principales:
        acciones.append(
            "1. Agregar la sección `candidatos_principales:` en configs/candidates.yaml "
            "(13 candidatos del corte — ver README)."
        )

    # ¿Parquet desactualizado?
    needs_reingest = False
    if df_parquet is not None:
        regiones = (
            df_parquet.get("region", pd.Series()).dropna().unique()
            if hasattr(df_parquet, "get")
            else []
        )
        grupos_edad = (
            set(df_parquet.get("edad_grupo", pd.Series()).dropna().unique())
            if hasattr(df_parquet, "get")
            else set()
        )
        if len(regiones) > REGIONES_ESPERADAS or (grupos_edad - GRUPOS_EDAD_CANONICOS):
            needs_reingest = True

    if needs_reingest:
        acciones.append(
            "2. Borrar el checkpoint y re-ingestar:\n"
            "      rm data/processed/encuestas_concatenadas.parquet\n"
            "      encuestas-ingest --config configs/ --forzar\n"
            "   (o desde Python: IngestPipeline(config).run(forzar=True))"
        )
    else:
        acciones.append(
            "2. Re-correr el pipeline de análisis:\n"
            "      encuestas-analyze --config configs/\n"
            "   (o desde Python: AnalysisPipeline(config).run(df))"
        )

    if not acciones:
        print("  🎉 No se requieren acciones correctivas.  El pipeline está listo para producción.")
    else:
        for a in acciones:
            print(f"  → {a}\n")

    print()
    print("  Orden correcto de ejecución:")
    print("    1. encuestas-ingest --config configs/ [--forzar]")
    print("    2. encuestas-analyze --config configs/")
    print()
    print("  Para diagnóstico post-análisis:")
    print(
        "    python scripts/diagnostico.py --config configs/ --excel data/outputs/analisis_consolidado.xlsx"
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Punto de entrada
# ─────────────────────────────────────────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Diagnóstico pre-producción del pipeline de encuestas."
    )
    parser.add_argument(
        "--config",
        type=str,
        default="configs/",
        help="Directorio de configuración (default: configs/)",
    )
    parser.add_argument(
        "--excel",
        type=str,
        default=None,
        help="Ruta al Excel de output para validar paridad vs PDF (opcional)",
    )
    args = parser.parse_args()

    configs_dir = Path(args.config).resolve()
    print(f"\n{'═' * 60}")
    print("  DIAGNÓSTICO DE PIPELINE — ENCUESTAS PRESIDENCIALES 2026")
    print(f"{'═' * 60}")
    print(f"  Config: {configs_dir}")

    all_ok = True

    # Check 1: Config
    ok1, config = check_config(configs_dir)
    all_ok = all_ok and ok1

    # Check 2: Checkpoint
    ok2, df_parquet = check_checkpoint(config) if config else (True, None)
    all_ok = all_ok and ok2

    # Check 3: Excel output (opcional)
    if args.excel:
        excel_path = Path(args.excel).resolve()
        ok3 = check_excel(excel_path)
        all_ok = all_ok and ok3

    # Check 4: Plan de acción
    recomendar_accion(config, df_parquet)

    # Resumen final
    _section("RESUMEN FINAL")
    if all_ok:
        print("  🎉 Todos los checks pasaron.  El pipeline está listo para producción.")
        return 0
    else:
        print("  🚨 Hay checks fallidos.  Revisar las acciones recomendadas arriba.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
