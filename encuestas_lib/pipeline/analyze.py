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

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from rich.console import Console
from rich.table import Table

from encuestas_lib.analysis import (
    coalicion_aprobacion,
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

        # 2b. Filtrar a vigentes para tablas básicas si corresponde
        if solo_vigentes:
            # Opciones especiales (blanco, NS/NR, ninguno) salen de
            # special_categories del YAML — se preservan junto a vigentes.
            opciones_indecisos = {
                str(c.get("canonical"))
                for c in self.config.special_categories_raw
                if c.get("canonical")
            }
            from encuestas_lib.analysis import filtrar_voto_vigente

            df_basicas = filtrar_voto_vigente(df, vigentes, opciones_indecisos)
            console.print(
                f"[yellow]ℹ[/] Filtro vigentes activo: "
                f"{len(df_basicas):,} de {len(df):,} filas conservadas "
                f"({len(df_basicas) / len(df) * 100:.1f}%). "
                f"Vigentes: {len(vigentes)} · Especiales: {len(opciones_indecisos)}."
            )
        else:
            df_basicas = df
            console.print(
                "[yellow]⚠[/] solo_vigentes=False → tablas básicas incluyen "
                "TODOS los candidatos del histórico (incl. retirados)."
            )

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
        # Indecisos: el universo es el original (sin filtrar), pero la
        # función ya usa `vigentes` para decidir quién cuenta como indeciso.
        tablas["indecisos_total"] = tabla_indecisos_total(df, pesos, vigentes)
        for dim_name, dim_df in tabla_indecisos_demograficas(df, pesos, vigentes).items():
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


__all__ = ["AnalysisPipeline"]
