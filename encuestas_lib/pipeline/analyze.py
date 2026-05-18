"""Pipeline de análisis: genera todas las tablas y las exporta.

Toma el DataFrame ingestado (output de `IngestPipeline`) y produce el
conjunto completo de tablas — básicas (`tables.py`) y avanzadas
(`advanced.py`) — exportándolas a Excel multi-hoja y JSON con metadatos.

Uso:
    >>> from encuestas_lib.config import Config
    >>> from encuestas_lib.pipeline.ingest import IngestPipeline
    >>> from encuestas_lib.pipeline.analyze import AnalysisPipeline
    >>>
    >>> config = Config.from_yaml("configs/")
    >>> df = IngestPipeline(config).run()
    >>> tablas = AnalysisPipeline(config).run(df)
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from rich.console import Console
from rich.table import Table

from encuestas_lib.analysis import (
    coalicion_aprobacion,
    filtrar_voto_vigente,
    indecisos_perfil,
    margen_error_efectivo,
    resolve_weights,
    resumen_validacion,
    sesgo_por_encuestadora,
    sv_columns,
    tabla_aprobacion_vs_voto,
    tabla_genero_por_candidato_top4,
    tabla_indecisos_demograficas,
    tabla_indecisos_total,
    tabla_primera_vuelta_total,
    tabla_voto_por_edad,
    tabla_voto_por_genero,
    tabla_voto_por_region,
    tabla_voto_vs_aprobacion,
    techo_potencial_sv,
    transferencia_pv_sv,
    trend_primera_vuelta,
    verificar_cierres_100,
    volatilidad_encuestadora,
)
from encuestas_lib.config import Config
from encuestas_lib.harmonization import build_harmonizer
from encuestas_lib.io import ExcelExporter, JSONExporter

console = Console()


# ════════════════════════════════════════════════════════════════════════════
#  Helpers de módulo
# ════════════════════════════════════════════════════════════════════════════
def _remap_no_principales(
    df: pd.DataFrame,
    cands_principales: Collection[str],
    opciones_indecisos: Collection[str],
) -> pd.DataFrame:
    """Remap first-round votes outside *cands_principales* to "Otro candidato".

    Replica el comportamiento del repo original (``encuestas_concatenadas.xlsx``),
    donde candidatos fuera del corte de 13 principales eran clasificados como
    "Otro candidato" en la columna ``primera_vuelta``.  Necesario para que
    ``indecisos_total`` alcance ~28% (vs ~17% sin el remap).

    Solo se remapean filas con ``primera_vuelta`` no-nulo que no están ni en
    ``cands_principales`` ni en ``opciones_indecisos`` (blanco, NS/NR, etc.).
    Las columnas de segunda vuelta **no** se tocan.

    Args:
        df: microdatos completos (sin filtrar).
        cands_principales: conjunto de 13 (o N) candidatos "en carrera".
        opciones_indecisos: categorías especiales (NS/NR, Ninguno, blanco…).

    Returns:
        Copia de ``df`` con ``primera_vuelta`` remapeada.
    """
    if "primera_vuelta" not in df.columns:
        return df.copy()

    allowed: set[str] = set(cands_principales) | set(opciones_indecisos)
    out = df.copy()
    mask_notnull = out["primera_vuelta"].notna()
    mask_nonallowed = ~out["primera_vuelta"].isin(allowed)
    n_remapped = int((mask_notnull & mask_nonallowed).sum())
    if n_remapped:
        out.loc[mask_notnull & mask_nonallowed, "primera_vuelta"] = "Otro candidato"
        console.print(
            f"[yellow]ℹ[/] Remap indecisos: {n_remapped:,} votos no-principales "
            f"→ 'Otro candidato' (necesario para paridad con repo original)."
        )
    return out


@dataclass
class AnalysisPipeline:
    """Genera todas las tablas y las exporta.

    Attributes:
        config: configuración global cargada de YAMLs.
    """

    config: Config

    # ────────────────────────────────────────────────────────────────────
    def run(
        self,
        df: pd.DataFrame,
        excel_name: str = "analisis_consolidado.xlsx",
        json_name: str = "analisis_consolidado.json",
        validar: bool = True,
        solo_vigentes: bool = True,
    ) -> dict[str, pd.DataFrame]:
        """Generar tablas, validar cierres y exportar.

        Args:
            df: DataFrame ingestado por `IngestPipeline`.
            excel_name: nombre del archivo Excel de salida.
            json_name: nombre del archivo JSON de salida.
            validar: si True, ejecuta `verificar_cierres_100` y loggea.
            solo_vigentes: si True (default), las tablas básicas se calculan
                sobre el subconjunto de votos a candidatos con
                `status: vigente` en candidates.yaml (más voto blanco/NS/NR).
                Si False, incluye todos los nombres que aparezcan en los
                microdatos — útil para revisión histórica.

        Returns:
            Dict {nombre_tabla: DataFrame} con todo lo generado.
        """
        # 1. Resolver pesos según estrategia activa
        pesos = resolve_weights(self.config.weighting, self.config.surveys)

        # 2. Construir harmonizer (necesario para vigentes y matchups)
        harmonizer = build_harmonizer(
            self.config.candidates_raw,
            self.config.special_categories_raw,
        )
        vigentes = harmonizer.vigentes()

        # 2b. Candidatos "en carrera" y categorías especiales.
        # Definir ANTES del filtro de df_basicas: ambos bloques los usan.
        #
        # FIX B_NEW_1: usar `candidatos_principales` (13 candidatos del corte)
        # en lugar de `vigentes` (24 vigentes totales).  Con 24 vigentes en
        # df_basicas, candidatos históricos (~8-10 pp del denominador) diluían
        # los porcentajes de los 13 principales (ej. Cepeda: 27% → 37%).
        #
        # GUARDIA EXPLÍCITA: frozenset() es falsy en Python, por lo que
        # `frozenset() or vigentes` silenciosamente cae en vigentes aunque el
        # YAML exista.  Verificamos antes y fallamos de forma audible.
        _cands_raw: frozenset[str] = self.config.candidatos_principales
        if not _cands_raw:
            console.print(
                "[bold red]⚠ ADVERTENCIA B_NEW_1:[/] `candidatos_principales` está vacío "
                "en candidates.yaml.  Asegúrese de que el YAML activo contiene la sección "
                "`candidatos_principales` con los 13 candidatos del corte.  "
                "Usando `vigentes` (24 candidatos) como fallback — los porcentajes de "
                "primera vuelta quedarán DILUIDOS."
            )
        cands_principales: frozenset[str] = _cands_raw if _cands_raw else vigentes
        opciones_indecisos: set[str] = {
            str(c.get("canonical"))
            for c in self.config.special_categories_raw
            if c.get("canonical")
        }

        # 2c. df_basicas: filas con voto a candidatos principales o especiales.
        if solo_vigentes:
            df_basicas = filtrar_voto_vigente(df, cands_principales, opciones_indecisos)
            console.print(
                f"[yellow]ℹ[/] Filtro candidatos_principales activo: "
                f"{len(df_basicas):,} de {len(df):,} filas conservadas "
                f"({len(df_basicas) / len(df) * 100:.1f}%). "
                f"Principales: {len(cands_principales)} · Especiales: {len(opciones_indecisos)}."
            )
        else:
            df_basicas = df
            console.print(
                "[yellow]⚠[/] solo_vigentes=False → tablas básicas incluyen "
                "TODOS los candidatos del histórico (incl. retirados)."
            )

        # 2d. df_indecisos: remap candidatos no-principales → "Otro candidato".
        #
        # FIX B_NEW_2: replica el comportamiento de encuestas_concatenadas.xlsx
        # (repo original), donde candidatos fuera del corte de 13 principales
        # (Galán, Dávila, Gaviria, Pinzón…) eran clasificados como
        # "Otro candidato".  Sin este remap, indecisos_total ≈ 17% en lugar
        # del ~28% que reporta el PDF de La Silla Vacía.
        df_indecisos = _remap_no_principales(df, cands_principales, opciones_indecisos)

        tablas: dict[str, pd.DataFrame] = {}

        # 3. Tablas básicas (replican el repo original)
        console.print("[bold]Generando tablas básicas…")
        tablas["primera_vuelta_total"] = tabla_primera_vuelta_total(df_basicas, pesos)
        tablas["voto_por_region"] = tabla_voto_por_region(df_basicas, pesos)
        tablas["voto_por_edad"] = tabla_voto_por_edad(df_basicas, pesos)
        tablas["voto_por_genero"] = tabla_voto_por_genero(df_basicas, pesos)
        tablas["genero_por_candidato_top4"] = tabla_genero_por_candidato_top4(df_basicas, pesos)
        tablas["aprobacion_vs_voto"] = tabla_aprobacion_vs_voto(df_basicas, pesos)
        tablas["voto_vs_aprobacion"] = tabla_voto_vs_aprobacion(df_basicas, pesos)
        # Los sesgos demográficos NO dependen de quién esté vigente
        tablas["sesgo_genero"] = sesgo_por_encuestadora(df, pesos, "genero")
        tablas["sesgo_edad"] = sesgo_por_encuestadora(df, pesos, "edad_grupo")
        tablas["sesgo_region"] = sesgo_por_encuestadora(df, pesos, "region")
        # Indecisos: sobre df_indecisos (con remap), NO sobre df ni df_basicas.
        # `cands_principales` (13 candidatos del corte) define quién es "real".
        tablas["indecisos_total"] = tabla_indecisos_total(df_indecisos, pesos, cands_principales)
        for dim_name, dim_df in tabla_indecisos_demograficas(
            df_indecisos, pesos, cands_principales
        ).items():
            tablas[f"indecisos_{dim_name}"] = dim_df

        # 4. Tablas avanzadas (NUEVAS)
        console.print("[bold]Generando tablas avanzadas…")
        tablas["trend_primera_vuelta"] = trend_primera_vuelta(df, vigentes)
        tablas["coalicion_aprobacion"] = coalicion_aprobacion(df, pesos)
        tablas["volatilidad_encuestadora"] = volatilidad_encuestadora(df, vigentes)
        tablas["indecisos_perfil"] = indecisos_perfil(df, vigentes)

        # MoE para top-3 candidatos del agregado de PV
        top3 = tablas["primera_vuelta_total"].nlargest(3, "valor")["primera_vuelta"].tolist()
        for cand in top3:
            cand_key = harmonizer.key_de(cand) or cand.lower().split()[-1]
            tablas[f"moe_{cand_key}"] = margen_error_efectivo(df, cand)

        # Transferencia PV→SV para cada matchup disponible
        for sv_col in sv_columns(df):
            t = transferencia_pv_sv(df, sv_col, pesos)
            if not t.empty:
                tablas[f"transfer_{sv_col}"] = t

        # Techos de potencial: para el candidato #1 vs todos los rivales
        if top3:
            top1 = top3[0]
            top1_key = harmonizer.key_de(top1)
            if top1_key:
                rivales = [
                    harmonizer.key_de(c) for c in vigentes if c != top1 and harmonizer.key_de(c)
                ]
                rivales = [r for r in rivales if r]
                t_techo = techo_potencial_sv(
                    df,
                    candidato_canonical=top1,
                    candidato_key=top1_key,
                    candidatos_vigentes=vigentes,
                    pesos=pesos,
                    rivales_keys=rivales,
                )
                if not t_techo.empty:
                    tablas[f"techo_potencial_{top1_key}"] = t_techo

        # 5. Validación forense
        if validar:
            diag = verificar_cierres_100(tablas)
            tablas["_validacion_cierres"] = diag
            self._print_validacion(diag)

        # 6. Export
        out_dir: Path = self.config.paths.outputs_dir
        excel_path = ExcelExporter().write(tablas, out_dir / excel_name)
        json_path = JSONExporter().write(tablas, out_dir / json_name)
        console.print(f"[green]✓[/] Excel: [bold]{excel_path}[/]")
        console.print(f"[green]✓[/] JSON:  [bold]{json_path}[/]")

        return tablas

    # ────────────────────────────────────────────────────────────────────
    def _print_validacion(self, diag: pd.DataFrame) -> None:
        """Imprimir resumen de validación con rich."""
        resumen = resumen_validacion(diag)
        t = Table(title="Validación de cierres a 100%", show_header=True)
        t.add_column("Métrica", style="cyan")
        t.add_column("Valor", style="bold")
        t.add_row("Filas validadas", str(resumen["n_filas"]))
        t.add_row("OK", f"[green]{resumen['n_ok']}[/]")
        t.add_row(
            "Fallidas",
            f"[red]{resumen['n_fallidas']}[/]" if resumen["n_fallidas"] else "0",
        )
        t.add_row("Desviación máxima (pp)", f"{resumen['desviacion_max']:.3f}")
        console.print(t)

        if resumen["n_fallidas"] > 0:
            fallidas = diag[~diag["ok"]].head(10)
            console.print("[yellow]Detalle de las primeras fallas:[/]")
            console.print(fallidas.to_string(index=False))


# ════════════════════════════════════════════════════════════════════════════
#  CLI
# ════════════════════════════════════════════════════════════════════════════
def cli() -> None:
    """Entry point para `encuestas-analyze --config configs/`."""
    import argparse

    from encuestas_lib.pipeline.ingest import IngestPipeline

    parser = argparse.ArgumentParser(description="Generar tablas analíticas.")
    parser.add_argument("--config", type=str, default="configs/", help="Directorio configs/")
    parser.add_argument("--forzar", action="store_true", help="Reingesta ignorando checkpoint")
    parser.add_argument("--no-validar", action="store_true", help="Saltar verificación de cierres")
    args = parser.parse_args()

    config = Config.from_yaml(args.config)
    df = IngestPipeline(config).run(forzar=args.forzar)
    AnalysisPipeline(config).run(df, validar=not args.no_validar)


if __name__ == "__main__":
    cli()


__all__ = ["AnalysisPipeline", "_remap_no_principales"]
