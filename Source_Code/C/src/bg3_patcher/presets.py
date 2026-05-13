from __future__ import annotations

__author__ = "AkELkA"

import json
from pathlib import Path
from typing import Any

from bg3_patcher.models import PatchConfig, RaceAssignment


def load_preset(path: Path) -> PatchConfig:
    data = json.loads(path.read_text(encoding="utf-8"))
    return config_from_dict(data)


def save_preset(config: PatchConfig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config_to_dict(config), indent=2), encoding="utf-8")


def config_to_dict(config: PatchConfig) -> dict[str, Any]:
    return {
        "vanilla_path": str(config.vanilla_path),
        "output_dir": str(config.output_dir),
        "patch_name": config.patch_name,
        "mod_paths": [str(path) for path in config.mod_paths],
        "priority_order": [str(path) for path in config.priority_order],
        "race_assignments": [
            {
                "source_label": assignment.source_label,
                "source_path": str(assignment.source_path),
                "race_guids": list(assignment.race_guids),
                "include_all": assignment.include_all,
                "use_vanilla_races": assignment.use_vanilla_races,
            }
            for assignment in config.race_assignments
        ],
    }


def config_from_dict(data: dict[str, Any]) -> PatchConfig:
    return PatchConfig(
        vanilla_path=Path(data["vanilla_path"]),
        output_dir=Path(data.get("output_dir", "GeneratedPatch")),
        patch_name=data.get("patch_name", "GeneratedPatch"),
        mod_paths=[Path(path) for path in data.get("mod_paths", [])],
        priority_order=[Path(path) for path in data.get("priority_order", [])],
        race_assignments=[
            RaceAssignment(
                source_label=assignment.get("source_label", Path(assignment["source_path"]).name),
                source_path=Path(assignment["source_path"]),
                race_guids=tuple(assignment.get("race_guids", [])),
                include_all=assignment.get("include_all", False),
                use_vanilla_races=assignment.get("use_vanilla_races", False),
            )
            for assignment in data.get("race_assignments", [])
        ],
    )
