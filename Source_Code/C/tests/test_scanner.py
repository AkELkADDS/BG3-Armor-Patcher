from __future__ import annotations

__author__ = "AkELkA"

from pathlib import Path

import pytest

from bg3_patcher.models import PatchConfig, PatchValidationError
from bg3_patcher.scanner import resolve_vanilla_equipment_races_path, validate_config


def test_validation_fails_when_lsf_needs_manual_conversion(tmp_path):
    vanilla = _vanilla_base(tmp_path)
    root_templates = vanilla / "Shared" / "Public" / "Shared" / "RootTemplates"
    root_templates.mkdir(parents=True)
    (root_templates / "armor.lsf").write_text("binary-ish", encoding="utf-8")

    config = PatchConfig(vanilla_path=vanilla, output_dir=tmp_path / "out")

    with pytest.raises(PatchValidationError) as exc_info:
        validate_config(config)

    assert "manual conversion" in str(exc_info.value)
    assert "armor.lsf" in str(exc_info.value)


def test_resolve_equipment_settings_folder_or_file(tmp_path):
    vanilla = tmp_path / "UnpackedData"
    eq_dir = vanilla / "Shared" / "Mods" / "SharedDev" / "EquipmentSettings"
    eq_dir.mkdir(parents=True)
    eq_file = eq_dir / "EquipmentRaces.lsx"
    eq_file.write_text("<save />", encoding="utf-8")

    assert resolve_vanilla_equipment_races_path(eq_dir) == eq_file
    assert resolve_vanilla_equipment_races_path(eq_file) == eq_file


def test_validation_accepts_equipment_races_file_path(tmp_path):
    vanilla = _vanilla_base(tmp_path)
    races_file = vanilla / "Shared" / "Mods" / "SharedDev" / "EquipmentSettings" / "EquipmentRaces.lsx"
    root_templates = vanilla / "Shared" / "Public" / "Shared" / "RootTemplates"
    root_templates.mkdir(parents=True)
    (root_templates / "armor.lsx").write_text("<save />", encoding="utf-8")

    validate_config(PatchConfig(vanilla_path=races_file, output_dir=tmp_path / "out"))


def test_resolve_vanilla_equipment_races_parent_or_unpacked_root(tmp_path):
    export = tmp_path / "BG3Export"
    unpacked = export / "UnpackedData"
    races_dir = unpacked / "Shared" / "Mods" / "SharedDev" / "EquipmentSettings"
    races_dir.mkdir(parents=True)
    file_path = races_dir / "EquipmentRaces.lsx"
    file_path.write_text("<save />", encoding="utf-8")

    assert resolve_vanilla_equipment_races_path(unpacked) == file_path
    assert resolve_vanilla_equipment_races_path(export) == file_path


def test_validation_accepts_lsf_when_matching_lsx_exists(tmp_path):
    vanilla = _vanilla_base(tmp_path)
    root_templates = vanilla / "Shared" / "Public" / "Shared" / "RootTemplates"
    root_templates.mkdir(parents=True)
    (root_templates / "armor.lsf").write_text("binary-ish", encoding="utf-8")
    (root_templates / "armor.lsx").write_text("<save />", encoding="utf-8")

    validate_config(PatchConfig(vanilla_path=vanilla, output_dir=tmp_path / "out"))


def _vanilla_base(tmp_path: Path) -> Path:
    vanilla = tmp_path / "UnpackedData"
    races = vanilla / "Shared" / "Mods" / "SharedDev" / "EquipmentSettings"
    races.mkdir(parents=True)
    (races / "EquipmentRaces.lsx").write_text("<save />", encoding="utf-8")
    return vanilla
