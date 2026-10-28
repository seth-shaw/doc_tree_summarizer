from dataclasses import dataclass, field


@dataclass
class Extracted:
    text: str
    extractor: str
    warnings: list[str] = field(default_factory=list)
