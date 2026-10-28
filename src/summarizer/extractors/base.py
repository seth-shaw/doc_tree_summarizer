"""Shared result type for document extractors."""

from dataclasses import dataclass, field


@dataclass
class Extracted:
    """Text and extraction metadata returned by an extractor."""

    text: str
    extractor: str
    warnings: list[str] = field(default_factory=list)
