"""Checkpoints cache-aside con detección automática de obsolescencia.

Patrón de uso:
    >>> df = cargar_o_procesar(checkpoint_path, mi_funcion, arg1, arg2)
    # Primera vez: ejecuta mi_funcion, guarda parquet + fingerprint.
    # Siguientes: compara fingerprint; si coincide, lee del parquet (rápido).
    # Si el fingerprint cambió (nuevo survey, nueva demografía, etc.): reprocesa.
    # forzar=True siempre reprocesa, aunque el fingerprint coincida.

¿Qué invalida el cache automáticamente?
    - Cambio en surveys.yaml  (nueva encuesta, cambio de path o reader)
    - Cambio en candidates.yaml  (nuevo candidato, cambio de candidatos_principales)
    - Cambio en demographics.py  (nueva regla REGION_NORM, EDAD_COLAPSO_3, etc.)
    - Cambio en cualquier reader .py  (invamer, atlas, cnc, gad3)
    - Cambio en ingest.py  (_normalize_demographics, _procesar, etc.)
    - Cambio en INGEST_PIPELINE_VERSION  (bump manual para forzar re-ingestión)

¿Qué NO invalida el cache?
    - Cambios solo en analyze.py, advanced.py, tables.py  (post-ingesta)
    - Cambios solo en weights.yaml  (los pesos se aplican en el análisis, no en ingesta)
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

import pandas as pd
from rich.console import Console

console = Console()

T = TypeVar("T")

# Incrementar este número cuando se haga un cambio en la lógica de ingesta
# que NO esté reflejado en surveys.yaml, candidates.yaml ni en los archivos
# de código monitoreados (e.g. cambio conceptual en el esquema de columnas).
INGEST_PIPELINE_VERSION = "1.0.0"

# Archivos de código cuyo hash se incluye en el fingerprint.
# Rutas relativas a la raíz del paquete encuestas_lib/.
_CODE_FILES_TO_HASH: tuple[str, ...] = (
    "harmonization/demographics.py",
    "pipeline/ingest.py",
    "readers/invamer.py",
    "readers/atlas.py",
    "readers/cnc.py",
    "readers/gad3.py",
)


# ════════════════════════════════════════════════════════════════════════════
#  Fingerprint
# ════════════════════════════════════════════════════════════════════════════
def _hash_file(path: Path) -> str:
    """SHA-256 de un archivo (primeros 64K bytes — suficiente para detectar cambios)."""
    if not path.exists():
        return "missing"
    h = hashlib.sha256()
    with path.open("rb") as f:
        h.update(f.read(65_536))
    return h.hexdigest()[:16]


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def compute_fingerprint(
    surveys_yaml: Path,
    candidates_yaml: Path,
    encuestas_lib_root: Path | None = None,
) -> dict[str, str]:
    """Calcular el fingerprint de ingesta.

    Args:
        surveys_yaml: path a surveys.yaml.
        candidates_yaml: path a candidates.yaml.
        encuestas_lib_root: directorio raíz del paquete (default: auto-detectado).

    Returns:
        Dict {clave: hash_corto} — serializable a JSON.
    """
    if encuestas_lib_root is None:
        # encuestas_lib/ está dos niveles arriba de este archivo
        # (encuestas_lib/pipeline/checkpoints.py → encuestas_lib/)
        encuestas_lib_root = Path(__file__).parent.parent

    fp: dict[str, str] = {
        "version": INGEST_PIPELINE_VERSION,
        "surveys_yaml": _hash_file(surveys_yaml),
        "candidates_yaml": _hash_file(candidates_yaml),
    }
    for rel in _CODE_FILES_TO_HASH:
        key = rel.replace("/", "__").replace(".py", "")
        fp[key] = _hash_file(encuestas_lib_root / rel)

    return fp


def _fingerprint_path(checkpoint_path: Path) -> Path:
    """Path del archivo JSON de fingerprint junto al parquet."""
    return checkpoint_path.with_suffix(".fingerprint.json")


def _load_stored_fingerprint(checkpoint_path: Path) -> dict[str, str] | None:
    fp_path = _fingerprint_path(checkpoint_path)
    if not fp_path.exists():
        return None
    try:
        return json.loads(fp_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_fingerprint(checkpoint_path: Path, fp: dict[str, str]) -> None:
    fp_path = _fingerprint_path(checkpoint_path)
    fp_path.write_text(json.dumps(fp, indent=2, ensure_ascii=False), encoding="utf-8")


def checkpoint_is_stale(
    checkpoint_path: Path,
    surveys_yaml: Path,
    candidates_yaml: Path,
    encuestas_lib_root: Path | None = None,
) -> tuple[bool, str]:
    """Comprobar si el checkpoint está desactualizado.

    Args:
        checkpoint_path: path al parquet.
        surveys_yaml: path a surveys.yaml.
        candidates_yaml: path a candidates.yaml.
        encuestas_lib_root: directorio raíz del paquete.

    Returns:
        (es_obsoleto, razón) — razón es "" si está fresco.
    """
    if not checkpoint_path.exists():
        return True, "parquet no existe"

    stored = _load_stored_fingerprint(checkpoint_path)
    if stored is None:
        return True, "fingerprint no encontrado (parquet creado con versión anterior)"

    current = compute_fingerprint(surveys_yaml, candidates_yaml, encuestas_lib_root)

    diffs = [k for k in current if current[k] != stored.get(k)]
    if diffs:
        keys_legibles = {
            "version": "INGEST_PIPELINE_VERSION",
            "surveys_yaml": "surveys.yaml",
            "candidates_yaml": "candidates.yaml",
            "harmonization__demographics": "demographics.py",
            "pipeline__ingest": "ingest.py",
            "readers__invamer": "invamer.py",
            "readers__atlas": "atlas.py",
            "readers__cnc": "cnc.py",
            "readers__gad3": "gad3.py",
        }
        nombres = [keys_legibles.get(k, k) for k in diffs]
        return True, f"cambios detectados en: {', '.join(nombres)}"

    return False, ""


# ════════════════════════════════════════════════════════════════════════════
#  API pública
# ════════════════════════════════════════════════════════════════════════════
def cargar_o_procesar(
    ruta_checkpoint: Path,
    funcion_proceso: Callable[..., pd.DataFrame],
    *args,
    forzar: bool = False,
    surveys_yaml: Path | None = None,
    candidates_yaml: Path | None = None,
    **kwargs,
) -> pd.DataFrame:
    """Cargar checkpoint si está fresco; reprocesar si está obsoleto o forzado.

    Compara el fingerprint actual (surveys.yaml + candidates.yaml + código clave)
    contra el fingerprint guardado junto al parquet.  Si difieren, re-ingesta
    automáticamente sin necesidad de borrar el parquet a mano.

    Args:
        ruta_checkpoint: path al parquet de salida.
        funcion_proceso: callable que retorna un DataFrame.
        *args, **kwargs: pasados a funcion_proceso.
        forzar: si True, reprocesa aunque el fingerprint coincida.
        surveys_yaml: path a surveys.yaml  (necesario para fingerprint).
        candidates_yaml: path a candidates.yaml  (necesario para fingerprint).

    Returns:
        DataFrame, ya sea leído del checkpoint o recién procesado.
    """
    ruta_checkpoint = Path(ruta_checkpoint)
    ruta_checkpoint.parent.mkdir(parents=True, exist_ok=True)

    # ── Decidir si re-ingestar ────────────────────────────────────────────
    necesita_procesar = forzar
    razon_reproceso = "forzado por --forzar" if forzar else ""

    if not necesita_procesar and surveys_yaml and candidates_yaml:
        stale, razon = checkpoint_is_stale(
            ruta_checkpoint,
            Path(surveys_yaml),
            Path(candidates_yaml),
        )
        if stale:
            necesita_procesar = True
            razon_reproceso = razon

    elif not necesita_procesar and not ruta_checkpoint.exists():
        necesita_procesar = True
        razon_reproceso = "parquet no existe"

    # ── Cache hit ─────────────────────────────────────────────────────────
    if not necesita_procesar and ruta_checkpoint.exists():
        df = pd.read_parquet(ruta_checkpoint)
        console.print(
            f"[cyan]♻[/cyan]  Cache hit: {ruta_checkpoint.name} "
            f"([magenta]{len(df):,}[/magenta] filas) — fingerprint ✓"
        )
        return df

    # ── Reprocesar ────────────────────────────────────────────────────────
    if razon_reproceso:
        console.print(
            f"[yellow]⚙[/yellow]  Re-ingesta automática "
            f"([yellow]{razon_reproceso}[/yellow]) → {ruta_checkpoint.name}…"
        )
    else:
        console.print(f"[yellow]⚙[/yellow]  Procesando → {ruta_checkpoint.name}…")

    df = funcion_proceso(*args, **kwargs)
    df.to_parquet(ruta_checkpoint, index=False, compression="snappy")
    size_mb = ruta_checkpoint.stat().st_size / 1024 / 1024
    console.print(
        f"[green]💾[/green] Guardado: {ruta_checkpoint.name} "
        f"([magenta]{len(df):,}[/magenta] filas · [cyan]{size_mb:.1f} MB[/cyan])"
    )

    # Guardar fingerprint junto al parquet
    if surveys_yaml and candidates_yaml:
        fp = compute_fingerprint(Path(surveys_yaml), Path(candidates_yaml))
        _save_fingerprint(ruta_checkpoint, fp)
        console.print(
            f"[dim]   Fingerprint guardado → {_fingerprint_path(ruta_checkpoint).name}[/dim]"
        )

    return df
