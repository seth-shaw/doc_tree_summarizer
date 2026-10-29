"""Shared data structures for document extractors."""

from dataclasses import dataclass, field


@dataclass
class Extracted:
    """Represent extracted text, its source, and any extraction warnings."""
    text: str
    extractor: str
    warnings: list[str] = field(default_factory=list)
