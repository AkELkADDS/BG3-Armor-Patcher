from __future__ import annotations

__author__ = "AkELkA"

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from xml.etree.ElementTree import Element


@dataclass(frozen=True)
class EquipmentRace:
    name: str
    guid: str
    source_label: str
    source_path: Path
    node: Element = field(compare=False, repr=False)


@dataclass(frozen=True)
class ModSource:
    label: str
    root_path: Path


@dataclass(frozen=True)
class RootTemplateRecord:
    template_id: str
    source_label: str
    source_path: Path
    priority_index: int
    node: Element = field(compare=False, repr=False)


@dataclass(frozen=True)
class RaceAssignment:
    source_label: str
    source_path: Path
    race_guids: tuple[str, ...] = ()
    include_all: bool = False
    use_vanilla_races: bool = False


@dataclass
class PatchConfig:
    vanilla_path: Path
    output_dir: Path
    patch_name: str = "GeneratedPatch"
    mod_paths: list[Path] = field(default_factory=list)
    priority_order: list[Path] = field(default_factory=list)
    race_assignments: list[RaceAssignment] = field(default_factory=list)


@dataclass
class ScanResult:
    vanilla_equipment_races_path: Path
    vanilla_root_template_dirs: list[Path]
    equipment_races_by_source: dict[Path, list[EquipmentRace]]
    root_templates_by_source: dict[Path, list[RootTemplateRecord]]
    """Template MapKeys merged to disk: from mods only, Equipment + ≥1 Visual Object with MapKey."""
    mod_contributed_template_ids: frozenset[str] = field(default_factory=frozenset)
    warnings: list[str] = field(default_factory=list)


@dataclass
class PatchReport:
    written_files: list[Path] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "written_files": [str(path) for path in self.written_files],
            "warnings": self.warnings,
            "errors": self.errors,
            "skipped": self.skipped,
        }


class PatchValidationError(Exception):
    """Raised when input files cannot be patched safely."""

    def __init__(self, messages: list[str]) -> None:
        self.messages = messages
        super().__init__("\n".join(messages))
