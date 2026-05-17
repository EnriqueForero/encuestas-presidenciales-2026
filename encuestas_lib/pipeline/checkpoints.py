"""Checkpoints cache-aside.

Patrón:
    >>> df = cargar_o_procesar(checkpoint_path, mi_funcion, arg1, arg2)
    # primera vez: ejecuta mi_funcion, guarda parquet.
    # siguientes: lee del parquet (rápido).
    # forzar=True para recomputar.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

import pandas as pd
from rich.console import Console

console = Console()

T = TypeVar("T")


def cargar_o_procesar(
    ruta_checkpoint: Path,
    funcion_proceso: Callable[..., pd.DataFrame],
    *args,
    forzar: bool = False,
    **kwargs,
) -> pd.DataFrame:
    """Cargar checkpoint si existe; ejecutar y guardar si no.

    Args:
        ruta_checkpoint: path al parquet.
        funcion_proceso: callable que retorna un DataFrame.
        *args, **kwargs: pasados a funcion_proceso.
        forzar: si True, ignora el checkpoint y reprocesa.

    Returns:
        DataFrame, ya sea leído del checkpoint o recién procesado.
    """
    ruta_checkpoint = Path(ruta_checkpoint)
    ruta_checkpoint.parent.mkdir(parents=True, exist_ok=True)

    if not forzar and ruta_checkpoint.exists():
        df = pd.read_parquet(ruta_checkpoint)
        console.print(
            f"[cyan]♻[/cyan]  Cache hit: {ruta_checkpoint.name} "
            f"([magenta]{len(df):,}[/magenta] filas)"
        )
        return df

    console.print(f"[yellow]⚙[/yellow]  Procesando → {ruta_checkpoint.name}…")
    df = funcion_proceso(*args, **kwargs)
    df.to_parquet(ruta_checkpoint, index=False, compression="snappy")
    size_mb = ruta_checkpoint.stat().st_size / 1024 / 1024
    console.print(
        f"[green]💾[/green] Guardado: {ruta_checkpoint.name} "
        f"([magenta]{len(df):,}[/magenta] filas · [cyan]{size_mb:.1f} MB[/cyan])"
    )
    return df
