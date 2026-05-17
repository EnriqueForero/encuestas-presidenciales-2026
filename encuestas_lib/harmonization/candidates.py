"""Armonización de nombres de candidatos.

Única fuente de verdad para nombres canónicos. Las reglas se cargan desde
configs/candidates.yaml.

Las funciones públicas son:
    - build_harmonizer(config) → CandidateHarmonizer
    - normalize_text(s)        → string sin tildes, lowercase
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any


# ════════════════════════════════════════════════════════════════════════════
#  Normalización de texto
# ════════════════════════════════════════════════════════════════════════════
@lru_cache(maxsize=50_000)
def normalize_text(text: str | None) -> str:
    """Normalizar texto a ASCII lowercase sin tildes ni espacios extra.

    Aplicado a strings inmutables. Cacheado por `@lru_cache` ya que la misma
    cadena ("ivan cepeda") aparece millones de veces en microdatos.

    Args:
        text: cadena cruda. None y NaN se aceptan y devuelven "".

    Returns:
        cadena normalizada. Cadena vacía si la entrada es nula/vacía.

    Examples:
        >>> normalize_text("Iván Cepeda")
        'ivan cepeda'
        >>> normalize_text("  Á.B.C.  ")
        'a.b.c.'
        >>> normalize_text(None)
        ''
    """
    if text is None:
        return ""
    s = str(text).strip().lower()
    if s in ("nan", "none", ""):
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    return " ".join(s.split())


# ════════════════════════════════════════════════════════════════════════════
#  Candidatos
# ════════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class CandidateRule:
    """Regla compilada para matchear un candidato en datos crudos."""

    canonical: str
    key: str
    status: str
    bloque: str
    pattern: re.Pattern[str]


@dataclass
class CandidateHarmonizer:
    """Armonizador de nombres de candidatos.

    Construir con `build_harmonizer(config)`. La instancia es inmutable
    después de construida.

    Attributes:
        rules: reglas en orden de prioridad (específico → genérico).
        by_canonical: índice canonical → CandidateRule.
        by_key: índice key → CandidateRule.
    """

    rules: list[CandidateRule] = field(default_factory=list)
    by_canonical: dict[str, CandidateRule] = field(default_factory=dict)
    by_key: dict[str, CandidateRule] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.by_canonical = {r.canonical: r for r in self.rules}
        self.by_key = {r.key: r for r in self.rules}

    # ────────────────────────────────────────────────────────────────────
    def harmonize(self, value: object) -> str | None:
        """Devolver el nombre canónico de un valor crudo, o el valor original.

        Args:
            value: celda cruda (str, NaN, número).

        Returns:
            Nombre canónico (si matcheó alguna regla), o el valor original
            stripeado (si no matcheó), o None si está vacío.
        """
        return _harmonize_cached(self._rules_tuple, value)

    @property
    def _rules_tuple(self) -> tuple[tuple[str, str], ...]:
        """Tupla hashable de reglas para usar como cache key."""
        return tuple((r.pattern.pattern, r.canonical) for r in self.rules)

    # ────────────────────────────────────────────────────────────────────
    def vigentes(self) -> set[str]:
        """Candidatos canónicos con status='vigente'."""
        return {r.canonical for r in self.rules if r.status == "vigente"}

    def por_bloque(self, bloque: str) -> set[str]:
        """Candidatos canónicos en un bloque dado."""
        return {r.canonical for r in self.rules if r.bloque == bloque}

    def key_de(self, canonical: str) -> str | None:
        """Devolver la `key` corta de un canonical, o None si no existe."""
        r = self.by_canonical.get(canonical)
        return r.key if r else None


# ════════════════════════════════════════════════════════════════════════════
#  Cache global para harmonize (compartido entre instancias)
# ════════════════════════════════════════════════════════════════════════════
@lru_cache(maxsize=50_000)
def _harmonize_cached(
    rules_tuple: tuple[tuple[str, str], ...],
    value: object,
) -> str | None:
    """Versión cacheada de harmonize.

    Crítico para performance: en datasets de 100K+ filas la misma cadena
    aparece miles de veces.
    """
    if value is None:
        return None
    # Detectar NaN sin importar pandas
    try:
        if value != value:  # type: ignore[comparison-overlap]
            return None
    except (TypeError, ValueError):
        pass

    s = normalize_text(str(value))
    if not s:
        return None

    for pattern_str, canonical in rules_tuple:
        if re.search(pattern_str, s):
            return canonical

    # Sin match → devolver original strip
    raw = str(value).strip()
    return raw if raw else None


# ════════════════════════════════════════════════════════════════════════════
#  Factory
# ════════════════════════════════════════════════════════════════════════════
def build_harmonizer(
    candidates_raw: list[dict[str, Any]],
    special_categories_raw: list[dict[str, Any]] | None = None,
    extra_demographic_rules: list[tuple[str, str]] | None = None,
) -> CandidateHarmonizer:
    """Construir un CandidateHarmonizer a partir del YAML.

    Args:
        candidates_raw: lista de dicts leídos de candidates.yaml → candidates.
        special_categories_raw: lista de categorías especiales (blanco, NS/NR, …).
        extra_demographic_rules: reglas adicionales (e.g., género) que se
            apilan al final.

    Returns:
        CandidateHarmonizer construido.

    Raises:
        ValueError: si un alias no compila como regex.
    """
    rules: list[CandidateRule] = []

    def _append_from_dict(d: dict[str, Any]) -> None:
        for alias in d.get("aliases", []):
            try:
                pat = re.compile(alias)
            except re.error as e:
                raise ValueError(
                    f"Alias inválido para {d.get('canonical', '?')}: {alias!r} ({e})"
                ) from e
            rules.append(
                CandidateRule(
                    canonical=d["canonical"],
                    key=d["key"],
                    status=d.get("status", "vigente"),
                    bloque=d.get("bloque", "otro"),
                    pattern=pat,
                )
            )

    # Orden importa: específico antes que genérico.
    # El YAML ya viene ordenado por construcción.
    for d in candidates_raw:
        _append_from_dict(d)

    if special_categories_raw:
        for d in special_categories_raw:
            d2 = dict(d)
            d2.setdefault("status", "categoria_especial")
            d2.setdefault("bloque", "no_aplica")
            _append_from_dict(d2)

    if extra_demographic_rules:
        # Patrones tipo género: (regex, canonical)
        for regex_str, canonical in extra_demographic_rules:
            try:
                pat = re.compile(regex_str)
            except re.error as e:
                raise ValueError(f"Regla demográfica inválida: {regex_str!r} ({e})") from e
            rules.append(
                CandidateRule(
                    canonical=canonical,
                    key=normalize_text(canonical).replace(" ", "_"),
                    status="demografico",
                    bloque="no_aplica",
                    pattern=pat,
                )
            )

    return CandidateHarmonizer(rules=rules)


# ════════════════════════════════════════════════════════════════════════════
#  Reglas demográficas comunes (género)
# ════════════════════════════════════════════════════════════════════════════
GENERO_RULES: list[tuple[str, str]] = [
    (r"hombre|masculino|varon|^m$", "Hombre"),
    (r"mujer|femenino|^f$", "Mujer"),
]
