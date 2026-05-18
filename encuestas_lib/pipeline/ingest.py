"""Pipeline de ingestión y armonización de microdatos.

Itera sobre `surveys.yaml`, lee cada encuesta con su Reader, normaliza
columnas demográficas comunes, y concatena en un único DataFrame canónico.

Resultado: un parquet en `data/processed/encuestas_concatenadas.parquet`.

Uso:
    >>> from encuestas_lib.config import Config
    >>> from encuestas_lib.pipeline.ingest import IngestPipeline
    >>> config = Config.from_yaml("configs/")
    >>> df = IngestPipeline(config).run(forzar=False)
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, replace
from pathlib import Path

import pandas as pd
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from encuestas_lib.config import Config, SurveyEntry
from encuestas_lib.harmonization import (
    APROBACION_PETRO_NORM,
    EDAD_COLAPSO_3,
    EDAD_NORM,
    GENERO_RULES,
    REGION_NORM,
    SEXO_NORM,
    aplicar_mapa,
    aplicar_mapa_con_int,
    build_harmonizer,
)
from encuestas_lib.pipeline.checkpoints import cargar_o_procesar
from encuestas_lib.readers import ensure_canonical_columns, get_reader_class

console = Console()


# ════════════════════════════════════════════════════════════════════════════
#  Resolución tolerante de paths (Unicode NFC ↔ NFD, espacios, case)
# ════════════════════════════════════════════════════════════════════════════
def _canonical_name(name: str) -> str:
    """Forma canónica para comparación tolerante de nombres de archivo.

    Aplica tres normalizaciones que comúnmente difieren entre el YAML
    y los nombres reales en Drive:

    1. Unicode → NFC (compone tildes descompuestas que vienen de Mac).
    2. Espacios múltiples → uno solo (typos del publicador, e.g. CNE).
    3. Case-fold (Unicode-aware lower) para fallback case-insensitive.
    """
    s = unicodedata.normalize("NFC", name)
    s = " ".join(s.split())  # colapsa runs de whitespace
    return s.casefold()


def _locate(p: Path) -> Path:
    """Resolver un path tolerando NFC↔NFD, espacios duplicados y case.

    Drive sincronizado desde Mac escribe nombres con tildes en NFD;
    publicadores como el CNE a veces tienen typos con dobles espacios;
    en algunos sistemas el casing varía. Esta función intenta resolver
    cualquiera de esas variaciones sin requerir editar el YAML.

    Estrategia en cascada (más estricta → más tolerante):
        1. Match exacto NFC sobre el nombre.
        2. Forma canónica completa (Unicode + espacios + case).

    Aplica recursivamente al padre si éste tampoco existe (cualquier
    componente de la ruta puede tener el mismo problema).

    Args:
        p: Path a resolver.

    Returns:
        Path resuelto si encuentra match, o el original si no.
    """
    if p.exists():
        return p
    parent = p.parent
    # Resolver padre primero si no existe (recursión sobre la cadena)
    if not parent.exists():
        parent_fixed = _locate(parent)
        if parent_fixed != parent and parent_fixed.exists():
            return _locate(parent_fixed / p.name)
        return p

    target_nfc = unicodedata.normalize("NFC", p.name)
    target_canon = _canonical_name(p.name)

    # Intento 1: NFC exacto (caso Mac → Linux clásico)
    for child in parent.iterdir():
        if unicodedata.normalize("NFC", child.name) == target_nfc:
            return child
    # Intento 2: forma canónica (espacios + case)
    for child in parent.iterdir():
        if _canonical_name(child.name) == target_canon:
            return child
    return p


@dataclass
class IngestPipeline:
    """Pipeline de ingestión.

    Attributes:
        config: configuración global.
    """

    config: Config

    # ────────────────────────────────────────────────────────────────────
    def preflight(self) -> pd.DataFrame:
        """Verificar qué surveys están listos para procesar.

        No procesa nada, solo audita la disponibilidad de cada archivo
        declarado en `surveys.yaml`. Aplica resolución tolerante a Unicode
        (NFC ↔ NFD) por si los archivos vienen sincronizados desde Mac.

        Returns:
            DataFrame [id, encuestadora, fecha, reader, path_relativo,
            existe, tamano_mb, unicode_fix].
        """
        rows: list[dict] = []
        n_unicode_fixed = 0
        for s in self.config.surveys:
            resolved = _locate(s.path)
            existe = resolved.exists()
            unicode_fix = existe and (resolved != s.path)
            if unicode_fix:
                n_unicode_fixed += 1
            tamano = resolved.stat().st_size / 1e6 if existe else 0.0
            rows.append(
                {
                    "id": s.id,
                    "encuestadora": s.encuestadora,
                    "fecha": str(s.fecha),
                    "reader": s.reader,
                    "path_relativo": str(s.path.relative_to(self.config.paths.raw_dir))
                    if s.path.is_relative_to(self.config.paths.raw_dir)
                    else str(s.path),
                    "existe": existe,
                    "tamano_mb": round(tamano, 2),
                    "unicode_fix": unicode_fix,
                }
            )
        out = pd.DataFrame(rows)
        # Reporte rich
        n_total = len(out)
        n_ok = int(out["existe"].sum())
        console.print(
            f"\n[bold]Preflight:[/bold] {n_ok}/{n_total} archivos disponibles "
            f"en [cyan]{self.config.paths.raw_dir}[/cyan]"
        )
        if n_unicode_fixed > 0:
            console.print(
                f"[yellow]ℹ[/] {n_unicode_fixed} archivo(s) resueltos vía normalización "
                f"Unicode (NFC↔NFD). Drive desde Mac suele causar esto."
            )
        if n_ok < n_total:
            faltantes = out.loc[~out["existe"], ["id", "path_relativo"]]
            console.print("[yellow]Archivos faltantes:[/yellow]")
            for _, r in faltantes.iterrows():
                console.print(f"  [red]✗[/] {r['id']}: {r['path_relativo']}")
        return out

    # ────────────────────────────────────────────────────────────────────
    def run(self, forzar: bool = False, skip_missing: bool = False) -> pd.DataFrame:
        """Ejecutar la ingestión completa.

        Args:
            forzar: si True, ignora checkpoint y reprocesa todo.
            skip_missing: si True, omite surveys cuyo archivo no existe
                en lugar de fallar. Útil para probar con subconjunto.

        Returns:
            DataFrame concatenado y normalizado.
        """
        # Resolver paths con tolerancia Unicode ANTES de filtrar/procesar
        resolved_surveys = [replace(s, path=_locate(s.path)) for s in self.config.surveys]

        if skip_missing:
            disponibles = [s for s in resolved_surveys if s.path.exists()]
            faltantes = len(resolved_surveys) - len(disponibles)
            if faltantes:
                console.print(
                    f"[yellow]⚠[/] Omitiendo {faltantes} surveys sin archivo. "
                    f"Procesando {len(disponibles)}/{len(resolved_surveys)}."
                )
            if not disponibles:
                raise FileNotFoundError(
                    f"Ningún archivo de encuesta encontrado en {self.config.paths.raw_dir}. "
                    f"Sube al menos un archivo según la tabla del Step 4 del notebook, "
                    f"o ejecuta el preflight para ver qué se espera."
                )
            self.config = replace(self.config, surveys=disponibles)
        else:
            self.config = replace(self.config, surveys=resolved_surveys)

        out_path = self.config.paths.processed_dir / "encuestas_concatenadas.parquet"
        return cargar_o_procesar(
            out_path,
            self._procesar,
            forzar=forzar,
            surveys_yaml=self.config.paths.configs_dir / "surveys.yaml",
            candidates_yaml=self.config.paths.configs_dir / "candidates.yaml",
        )

    # ────────────────────────────────────────────────────────────────────
    def _procesar(self) -> pd.DataFrame:
        """Lógica de ingestión (sin caché)."""
        # 1. Construir harmonizer una sola vez (reutilizable por todos los readers)
        harmonizer = build_harmonizer(
            self.config.candidates_raw,
            self.config.special_categories_raw,
            extra_demographic_rules=GENERO_RULES,
        )

        # 2. Leer cada encuesta
        pieces: list[pd.DataFrame] = []
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(
                f"Leyendo {len(self.config.surveys)} encuestas…",
                total=len(self.config.surveys),
            )
            for survey in self.config.surveys:
                df_i = self._read_one(survey, harmonizer)
                pieces.append(df_i)
                progress.update(
                    task,
                    advance=1,
                    description=f"✓ {survey.id} ({len(df_i):,} filas)",
                )

        # 3. Asegurar schema canónico en cada pieza
        all_sv_cols: set[str] = set()
        for p in pieces:
            all_sv_cols.update(c for c in p.columns if c.startswith("sv_"))

        from encuestas_lib.harmonization import all_meta_columns

        final_cols = all_meta_columns() + sorted(all_sv_cols)
        for p in pieces:
            ensure_canonical_columns(p, final_cols)

        # 4. Concatenar
        combined = pd.concat([p[final_cols] for p in pieces], ignore_index=True)

        # 5. Normalizar demográficas vectorizado
        combined = self._normalize_demographics(combined)

        console.print(
            f"\n[bold green]✓ Ingestión completa[/bold green]: "
            f"{len(combined):,} filas, {len(combined.columns)} columnas"
        )
        self._report_coverage(combined)
        return combined

    # ────────────────────────────────────────────────────────────────────
    @staticmethod
    def _read_one(survey: SurveyEntry, harmonizer) -> pd.DataFrame:
        """Leer una encuesta con su Reader."""
        reader_cls = get_reader_class(survey.reader)
        reader = reader_cls(survey, harmonizer)
        return reader.read()

    # ────────────────────────────────────────────────────────────────────
    @staticmethod
    def _normalize_demographics(df: pd.DataFrame) -> pd.DataFrame:
        """Aplicar normalización vectorizada a columnas demográficas.

        Pasos para edad (en orden):
            1. ``EDAD_NORM``: unifica las etiquetas crudas de cada encuestadora
               (e.g. "entre 18 y 24" → "18-24", "55 ó más" → "55+").
            2. ``EDAD_COLAPSO_3``: colapsa los grupos granulares a los 3 grupos
               canónicos del PDF de La Silla Vacía: 18-34 / 35-54 / 55+.
               FIX B_NEW_6: este paso estaba definido pero nunca se aplicaba,
               produciendo 9 grupos etarios en vez de 3.
        """
        if "edad_grupo" in df.columns:
            # Paso 1: normalizar etiquetas crudas por encuestadora
            df["edad_grupo"] = aplicar_mapa_con_int(df["edad_grupo"], EDAD_NORM)
            # Paso 2 — FIX B_NEW_6: colapsar a 3 grupos canónicos (18-34 / 35-54 / 55+)
            collapsed = df["edad_grupo"].map(EDAD_COLAPSO_3)
            df["edad_grupo"] = collapsed.where(collapsed.notna(), df["edad_grupo"])
        if "region" in df.columns:
            df["region"] = aplicar_mapa_con_int(df["region"], REGION_NORM)
        if "genero" in df.columns:
            # sexo = copia normalizada de género
            df["sexo"] = aplicar_mapa(df["genero"], SEXO_NORM)
        if "aprobacion_petro" in df.columns:
            df["aprobacion_petro"] = aplicar_mapa(df["aprobacion_petro"], APROBACION_PETRO_NORM)

        # Normalizar 'encuestadora' (colapsar Invamer subtítulos)
        if "encuestadora" in df.columns:
            df["encuestadora"] = (
                df["encuestadora"]
                .astype("string")
                .str.replace(r"\s*\(Colombia Opina \d+\)", "", regex=True)
            )

        # ── Coerción de dtypes para parquet/Arrow ──────────────────────
        # Columnas categóricas de texto que pueden venir con tipos mixtos
        # entre readers (CNC devuelve `estrato` como int, GAD3/Atlas como
        # str; Arrow requiere consistencia por columna). Casteamos todo a
        # string nullable, que también limpia FutureWarnings de pd.concat
        # con columnas all-NA.
        categoricas_texto = [
            "departamento",
            "municipio",
            "region",
            "zona",
            "genero",
            "sexo",
            "edad_grupo",
            "educacion",
            "estrato",
            "aprobacion_petro",
            "primera_vuelta",
            "primera_vuelta_espontanea",
        ]
        for col in categoricas_texto:
            if col in df.columns:
                # str() preserva el valor; pd.NA reemplaza NaN/None.
                df[col] = df[col].astype("string")

        # Columnas SV (segunda vuelta) también pueden venir mixtas
        for col in [c for c in df.columns if c.startswith("sv_")]:
            df[col] = df[col].astype("string")

        return df

    # ────────────────────────────────────────────────────────────────────
    def _report_coverage(self, df: pd.DataFrame) -> None:
        """Imprimir resumen de cobertura por encuestadora y por matchup SV."""
        console.print("\n[bold]Filas por encuesta:[/bold]")
        coverage = df.groupby(["encuestadora", "fecha"]).size().reset_index(name="n")
        for _, row in coverage.iterrows():
            console.print(
                f"  {row['encuestadora']:<15} {str(row['fecha'])[:10]} → "
                f"[magenta]{row['n']:,}[/magenta]"
            )

        sv_cols = [c for c in df.columns if c.startswith("sv_")]
        console.print(f"\n[bold]Matchups SV detectados:[/bold] {len(sv_cols)}")
        for c in sv_cols:
            n_valid = df[c].notna().sum()
            encs = df.loc[df[c].notna(), "encuestadora"].nunique()
            console.print(
                f"  {c:<35} → [magenta]{n_valid:,}[/magenta] obs · "
                f"[cyan]{encs}[/cyan] encuestadora(s)"
            )


# ════════════════════════════════════════════════════════════════════════════
#  CLI
# ════════════════════════════════════════════════════════════════════════════
def cli() -> None:
    """Entry point para `encuestas-ingest --config configs/`."""
    import argparse

    parser = argparse.ArgumentParser(description="Ingestar y armonizar microdatos.")
    parser.add_argument("--config", type=str, default="configs/", help="Directorio configs/")
    parser.add_argument("--forzar", action="store_true", help="Reprocesar ignorando checkpoint")
    args = parser.parse_args()

    config = Config.from_yaml(args.config)
    IngestPipeline(config).run(forzar=args.forzar)


if __name__ == "__main__":
    cli()
