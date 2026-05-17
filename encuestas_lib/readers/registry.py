"""Registro de Readers.

Mapea el campo `reader` de surveys.yaml a la clase concreta.
Para agregar una encuestadora nueva: importar la clase aquí y registrarla.
"""

from __future__ import annotations

from encuestas_lib.readers.atlas import AtlasReader
from encuestas_lib.readers.base import BaseReader
from encuestas_lib.readers.cnc import CNCExcelReader, CNCSavReader
from encuestas_lib.readers.gad3 import GAD3ExcelV1Reader, GAD3ExcelV2Reader, GAD3SavReader
from encuestas_lib.readers.invamer import InvamerReader

# ════════════════════════════════════════════════════════════════════════════
#  REGISTRO
# ════════════════════════════════════════════════════════════════════════════
#  Para agregar una nueva encuestadora:
#  1. Crear encuestas_lib/readers/<encuestadora>.py heredando de BaseReader.
#  2. Importarla arriba.
#  3. Agregar línea aquí: READERS["<nombre>"] = <Clase>Reader
#  4. Usar "<nombre>" en surveys.yaml.
# ════════════════════════════════════════════════════════════════════════════

READERS: dict[str, type[BaseReader]] = {
    "atlas": AtlasReader,
    "gad3_excel_v1": GAD3ExcelV1Reader,
    "gad3_excel_v2": GAD3ExcelV2Reader,
    "gad3_sav": GAD3SavReader,
    "invamer": InvamerReader,
    "cnc_sav": CNCSavReader,
    "cnc_excel": CNCExcelReader,
}


def get_reader_class(name: str) -> type[BaseReader]:
    """Devolver la clase de Reader para un nombre registrado.

    Args:
        name: clave del registro.

    Returns:
        Clase de Reader.

    Raises:
        KeyError: si el nombre no está registrado, con mensaje claro de
        los registros disponibles.
    """
    if name not in READERS:
        disponibles = ", ".join(sorted(READERS.keys()))
        raise KeyError(
            f"Reader '{name}' no registrado. Disponibles: {disponibles}. "
            f"Para agregar uno nuevo, ver encuestas_lib/readers/registry.py."
        )
    return READERS[name]
