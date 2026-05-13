from __future__ import annotations

__author__ = "AkELkA"

from pathlib import Path

from bg3_patcher import lsx
from bg3_patcher.merger import run_patch
from bg3_patcher.models import PatchConfig, RaceAssignment


def test_patch_merges_equipment_races_and_priority_visuals(tmp_path):
    vanilla = tmp_path / "UnpackedData"
    mod_a = tmp_path / "Clawstep"
    mod_b = tmp_path / "BreastPatch"
    output = tmp_path / "Generated"

    _write_equipment_races(vanilla / "Shared" / "Mods" / "SharedDev" / "EquipmentSettings" / "EquipmentRaces.lsx", [
        ("Dragonborn Female", "vanilla-race"),
    ])
    _write_root_template(
        vanilla / "Shared" / "Public" / "Shared" / "RootTemplates" / "armor.lsx",
        "armor-template",
        {"vanilla-race": "vanilla"},
    )

    _write_equipment_races(mod_a / "Mods" / "Clawstep" / "EquipmentSettings" / "EquipmentRaces.lsx", [
        ("Satyr", "custom-race"),
    ])
    _write_root_template(
        mod_a / "Public" / "Clawstep" / "RootTemplates" / "armor.lsx",
        "armor-template",
        {"vanilla-race": "clawstep", "custom-race": "clawstep-custom"},
    )
    _write_root_template(
        mod_b / "Public" / "BreastPatch" / "RootTemplates" / "armor.lsx",
        "armor-template",
        {"vanilla-race": "breast-patch"},
    )

    config = PatchConfig(
        vanilla_path=vanilla,
        output_dir=output,
        patch_name="Patch",
        mod_paths=[mod_a, mod_b],
        priority_order=[vanilla, mod_a, mod_b],
        race_assignments=[
            RaceAssignment("Clawstep", mod_a, include_all=True),
            RaceAssignment("BreastPatch", mod_b, race_guids=("vanilla-race",), use_vanilla_races=True),
        ],
    )

    report = run_patch(config)

    equipment_races = lsx.extract_equipment_races(
        lsx.load_root(output / "Patch" / "Mods" / "Patch" / "EquipmentSettings" / "EquipmentRaces.lsx"),
        "Patch",
        output,
    )
    race_guids = {race.guid for race in equipment_races}
    assert race_guids == {"vanilla-race", "custom-race"}

    root = lsx.load_root(output / "Patch" / "Public" / "Patch" / "RootTemplates" / "armor-template.lsx")
    game_object = lsx.find_item_game_objects(root)[0]
    markers = {
        lsx.visual_object_map_key(object_node): lsx.get_attribute_value(object_node, "Marker")
        for object_node in lsx.visual_object_nodes(game_object)
    }
    assert markers["vanilla-race"] == "breast-patch"
    assert markers["custom-race"] == "clawstep-custom"
    assert not report.errors


def test_root_template_base_does_not_leak_unselected_high_priority_visuals(tmp_path):
    vanilla = tmp_path / "UnpackedData"
    mod_a = tmp_path / "LowerPriority"
    mod_b = tmp_path / "HigherPriority"
    output = tmp_path / "Generated"

    _write_equipment_races(vanilla / "Shared" / "Mods" / "SharedDev" / "EquipmentSettings" / "EquipmentRaces.lsx", [
        ("Race A", "race-a"),
        ("Race B", "race-b"),
    ])
    _write_root_template(
        vanilla / "Shared" / "Public" / "Shared" / "RootTemplates" / "armor.lsx",
        "armor-template",
        {"race-a": "vanilla-a", "race-b": "vanilla-b"},
        game_object_marker="vanilla-structure",
    )

    _write_equipment_races(mod_a / "Mods" / "LowerPriority" / "EquipmentSettings" / "EquipmentRaces.lsx", [])
    _write_root_template(
        mod_a / "Public" / "LowerPriority" / "RootTemplates" / "armor.lsx",
        "armor-template",
        {"race-a": "mod-a", "race-b": "mod-a-unselected"},
    )
    _write_equipment_races(mod_b / "Mods" / "HigherPriority" / "EquipmentSettings" / "EquipmentRaces.lsx", [])
    _write_root_template(
        mod_b / "Public" / "HigherPriority" / "RootTemplates" / "armor.lsx",
        "armor-template",
        {"race-a": "mod-b", "race-b": "mod-b-unselected"},
        game_object_marker="mod-b-structure",
    )

    run_patch(
        PatchConfig(
            vanilla_path=vanilla,
            output_dir=output,
            patch_name="Patch",
            mod_paths=[mod_a, mod_b],
            priority_order=[vanilla, mod_a, mod_b],
            race_assignments=[
                RaceAssignment("LowerPriority", mod_a, race_guids=("race-a",), use_vanilla_races=True),
                RaceAssignment("HigherPriority", mod_b, race_guids=("race-a",), use_vanilla_races=True),
            ],
        )
    )

    root = lsx.load_root(output / "Patch" / "Public" / "Patch" / "RootTemplates" / "armor-template.lsx")
    game_object = lsx.find_item_game_objects(root)[0]
    markers = {
        lsx.visual_object_map_key(object_node): lsx.get_attribute_value(object_node, "Marker")
        for object_node in lsx.visual_object_nodes(game_object)
    }

    assert markers["race-a"] == "mod-b"
    assert markers["race-b"] == "vanilla-b"
    assert lsx.get_attribute_value(game_object, "RootMarker") == "mod-b-structure"


def test_selected_equipment_race_and_visual_nodes_keep_full_payload(tmp_path):
    vanilla = tmp_path / "UnpackedData"
    mod = tmp_path / "PayloadMod"
    output = tmp_path / "Generated"

    _write_equipment_races(vanilla / "Shared" / "Mods" / "SharedDev" / "EquipmentSettings" / "EquipmentRaces.lsx", [
        ("Vanilla Race", "vanilla-race"),
    ])
    _write_root_template(
        vanilla / "Shared" / "Public" / "Shared" / "RootTemplates" / "armor.lsx",
        "armor-template",
        {"vanilla-race": "vanilla"},
    )
    _write_equipment_race_with_payload(
        mod / "Mods" / "PayloadMod" / "EquipmentSettings" / "EquipmentRaces.lsx",
        "Payload Race",
        "payload-race",
    )
    _write_root_template_with_visual_payload(
        mod / "Public" / "PayloadMod" / "RootTemplates" / "armor.lsx",
        "armor-template",
        "payload-race",
    )

    run_patch(
        PatchConfig(
            vanilla_path=vanilla,
            output_dir=output,
            patch_name="Patch",
            mod_paths=[mod],
            priority_order=[vanilla, mod],
            race_assignments=[RaceAssignment("PayloadMod", mod, race_guids=("payload-race",))],
        )
    )

    race_root = lsx.load_root(output / "Patch" / "Mods" / "Patch" / "EquipmentSettings" / "EquipmentRaces.lsx")
    payload_race = next(
        race.node
        for race in lsx.extract_equipment_races(race_root, "Patch", output)
        if race.guid == "payload-race"
    )
    assert any(
        element.attrib.get("id") == "BodySetVisual" and element.attrib.get("value") == "payload-body"
        for element in payload_race.iter()
    )
    assert any(
        element.attrib.get("id") == "NestedRaceData" and element.attrib.get("value") == "payload-nested"
        for element in payload_race.iter()
    )

    template_root = lsx.load_root(output / "Patch" / "Public" / "Patch" / "RootTemplates" / "armor-template.lsx")
    game_object = lsx.find_item_game_objects(template_root)[0]
    payload_visual = next(
        object_node
        for object_node in lsx.visual_object_nodes(game_object)
        if lsx.visual_object_map_key(object_node) == "payload-race"
    )
    assert any(
        element.attrib.get("id") == "VisualResource" and element.attrib.get("value") == "payload-visual"
        for element in payload_visual.iter()
    )
    assert any(
        element.attrib.get("id") == "NestedVisualData" and element.attrib.get("value") == "payload-nested-visual"
        for element in payload_visual.iter()
    )


def test_only_mod_touched_root_templates_are_written(tmp_path):
    """Vanilla may contain thousands of templates; we emit only IDs that mods actually define with Equipment+Objects."""
    vanilla = tmp_path / "UnpackedData"
    mod_a = tmp_path / "Clawstep"
    output = tmp_path / "Generated"

    _write_equipment_races(vanilla / "Shared" / "Mods" / "SharedDev" / "EquipmentSettings" / "EquipmentRaces.lsx", [
        ("Dragonborn Female", "vanilla-race"),
    ])
    rt_v = vanilla / "Shared" / "Public" / "Shared" / "RootTemplates"
    _write_root_template(rt_v / "armor.lsx", "armor-template", {"vanilla-race": "vanilla"})
    _write_root_template(rt_v / "boots.lsx", "boots-only-vanilla", {"vanilla-race": "boots"})

    _write_equipment_races(mod_a / "Mods" / "Clawstep" / "EquipmentSettings" / "EquipmentRaces.lsx", [
        ("Satyr", "custom-race"),
    ])
    _write_root_template(mod_a / "Public" / "Clawstep" / "RootTemplates" / "armor.lsx", "armor-template", {"vanilla-race": "mod"})

    run_patch(
        PatchConfig(
            vanilla_path=vanilla,
            output_dir=output,
            patch_name="Patch",
            mod_paths=[mod_a],
            priority_order=[vanilla, mod_a],
            race_assignments=[RaceAssignment("Clawstep", mod_a, include_all=True)],
        )
    )

    rt_dir = output / "Patch" / "Public" / "Patch" / "RootTemplates"
    written = {p.name for p in rt_dir.glob("*.lsx")}
    assert written == {"armor-template.lsx"}


def test_duplicate_custom_equipment_race_is_warned_and_not_appended(tmp_path):
    vanilla = tmp_path / "UnpackedData"
    mod = tmp_path / "DuplicateRaceMod"

    _write_equipment_races(vanilla / "Shared" / "Mods" / "SharedDev" / "EquipmentSettings" / "EquipmentRaces.lsx", [
        ("Dragonborn Female", "same-race"),
    ])
    _write_root_template(
        vanilla / "Shared" / "Public" / "Shared" / "RootTemplates" / "armor.lsx",
        "armor-template",
        {"same-race": "vanilla"},
    )
    _write_equipment_races(mod / "Mods" / "DuplicateRaceMod" / "EquipmentSettings" / "EquipmentRaces.lsx", [
        ("Dragonborn Female Copy", "same-race"),
    ])
    _write_root_template(
        mod / "Public" / "DuplicateRaceMod" / "RootTemplates" / "armor.lsx",
        "armor-template",
        {"same-race": "mod"},
    )

    report = run_patch(
        PatchConfig(
            vanilla_path=vanilla,
            output_dir=tmp_path / "out",
            patch_name="Patch",
            mod_paths=[mod],
            priority_order=[vanilla, mod],
            race_assignments=[RaceAssignment("DuplicateRaceMod", mod, include_all=True)],
        )
    )

    assert any("duplicate" in warning.lower() for warning in report.warnings)
    root = lsx.load_root(tmp_path / "out" / "Patch" / "Public" / "Patch" / "RootTemplates" / "armor-template.lsx")
    game_object = lsx.find_item_game_objects(root)[0]
    markers = {
        lsx.visual_object_map_key(object_node): lsx.get_attribute_value(object_node, "Marker")
        for object_node in lsx.visual_object_nodes(game_object)
    }
    assert markers["same-race"] == "vanilla"


def test_custom_eqr_mod_does_not_override_selected_vanilla_eqr_mod(tmp_path):
    vanilla = tmp_path / "UnpackedData"
    vanilla_mod = tmp_path / "VanillaRaceArmor"
    custom_mod = tmp_path / "CustomRaceArmor"
    output = tmp_path / "Generated"

    _write_equipment_races(vanilla / "Shared" / "Mods" / "SharedDev" / "EquipmentSettings" / "EquipmentRaces.lsx", [
        ("Vanilla Race", "vanilla-race"),
    ])
    _write_root_template(
        vanilla / "Shared" / "Public" / "Shared" / "RootTemplates" / "armor.lsx",
        "armor-template",
        {"vanilla-race": "vanilla"},
    )

    _write_root_template(
        vanilla_mod / "Public" / "VanillaRaceArmor" / "RootTemplates" / "armor.lsx",
        "armor-template",
        {"vanilla-race": "vanilla-mod"},
        game_object_marker="vanilla-eqr-mod-structure",
    )
    _write_equipment_races(custom_mod / "Mods" / "CustomRaceArmor" / "EquipmentSettings" / "EquipmentRaces.lsx", [
        ("Copied Vanilla Race", "vanilla-race"),
        ("Custom Race", "custom-race"),
    ])
    _write_root_template(
        custom_mod / "Public" / "CustomRaceArmor" / "RootTemplates" / "armor.lsx",
        "armor-template",
        {"vanilla-race": "custom-mod-should-not-win", "custom-race": "custom-mod"},
        game_object_marker="custom-eqr-mod-structure",
    )

    run_patch(
        PatchConfig(
            vanilla_path=vanilla,
            output_dir=output,
            patch_name="Patch",
            mod_paths=[vanilla_mod, custom_mod],
            priority_order=[vanilla, vanilla_mod, custom_mod],
            race_assignments=[
                RaceAssignment("VanillaRaceArmor", vanilla_mod, race_guids=("vanilla-race",), use_vanilla_races=True),
                RaceAssignment("CustomRaceArmor", custom_mod, include_all=True),
            ],
        )
    )

    root = lsx.load_root(output / "Patch" / "Public" / "Patch" / "RootTemplates" / "armor-template.lsx")
    game_object = lsx.find_item_game_objects(root)[0]
    markers = {
        lsx.visual_object_map_key(object_node): lsx.get_attribute_value(object_node, "Marker")
        for object_node in lsx.visual_object_nodes(game_object)
    }

    assert markers["vanilla-race"] == "vanilla-mod"
    assert markers["custom-race"] == "custom-mod"
    assert lsx.get_attribute_value(game_object, "RootMarker") == "vanilla-eqr-mod-structure"


def test_missing_custom_visual_is_inherited_from_default_parent(tmp_path):
    vanilla = tmp_path / "UnpackedData"
    custom_mod = tmp_path / "CustomRace"
    output = tmp_path / "Generated"

    _write_equipment_races(vanilla / "Shared" / "Mods" / "SharedDev" / "EquipmentSettings" / "EquipmentRaces.lsx", [
        ("Human Female", "human-female"),
    ])
    _write_root_template(
        vanilla / "Shared" / "Public" / "Shared" / "RootTemplates" / "boots.lsx",
        "boots-template",
        {"human-female": "human-boots"},
        game_object_name="EPI_Camp_Shoes_Example",
        parent_races_by_race={"human-female": "parent-human"},
    )
    _write_equipment_race_with_default_parent(
        custom_mod / "Mods" / "CustomRace" / "EquipmentSettings" / "EquipmentRaces.lsx",
        "Satyr Female",
        "satyr-female",
        "human-female",
    )
    _write_root_template(
        custom_mod / "Public" / "CustomRace" / "RootTemplates" / "boots.lsx",
        "boots-template",
        {"human-female": "custom-mod-human-only"},
    )

    run_patch(
        PatchConfig(
            vanilla_path=vanilla,
            output_dir=output,
            patch_name="Patch",
            mod_paths=[custom_mod],
            priority_order=[vanilla, custom_mod],
            race_assignments=[RaceAssignment("CustomRace", custom_mod, race_guids=("satyr-female",))],
        )
    )

    root = lsx.load_root(output / "Patch" / "Public" / "Patch" / "RootTemplates" / "boots-template.lsx")
    game_object = lsx.find_item_game_objects(root)[0]
    markers = {
        lsx.visual_object_map_key(object_node): lsx.get_attribute_value(object_node, "Marker")
        for object_node in lsx.visual_object_nodes(game_object)
    }

    assert markers["human-female"] == "human-boots"
    assert markers["satyr-female"] is None
    satyr_visual = lsx.visual_object_for_race(game_object, "satyr-female")
    assert satyr_visual is not None
    map_value = next(node for node in satyr_visual.iter() if node.attrib.get("id") == "MapValue")
    assert lsx.get_attribute_value(map_value, "Object") == ""
    parent_race = lsx.race_map_object_for_race(game_object, "ParentRace", "satyr-female")
    assert parent_race is not None
    assert lsx.get_attribute_value(parent_race, "MapValue") == "00000000-0000-0000-0000-000000000000"


def test_footwear_selected_custom_races_not_seeded_from_visual_base(tmp_path):
    """Wrong custom-race keys in the visual-base file must not be copied; merge/append define them."""
    vanilla = tmp_path / "UnpackedData"
    custom_mod = tmp_path / "CustomRace"
    output = tmp_path / "Generated"

    _write_equipment_races(vanilla / "Shared" / "Mods" / "SharedDev" / "EquipmentSettings" / "EquipmentRaces.lsx", [
        ("Human Female", "human-female"),
    ])
    _write_root_template(
        vanilla / "Shared" / "Public" / "Shared" / "RootTemplates" / "boots.lsx",
        "boots-template",
        {"human-female": "human-boots", "satyr-female": "wrong-leaked-boots"},
        game_object_name="EPI_Camp_Shoes_Example",
    )
    _write_equipment_race_with_default_parent(
        custom_mod / "Mods" / "CustomRace" / "EquipmentSettings" / "EquipmentRaces.lsx",
        "Satyr Female",
        "satyr-female",
        "human-female",
    )
    _write_root_template(
        custom_mod / "Public" / "CustomRace" / "RootTemplates" / "boots.lsx",
        "boots-template",
        {"human-female": "custom-mod-human-only"},
        game_object_name="EPI_Camp_Shoes_Example",
    )

    run_patch(
        PatchConfig(
            vanilla_path=vanilla,
            output_dir=output,
            patch_name="Patch",
            mod_paths=[custom_mod],
            priority_order=[vanilla, custom_mod],
            race_assignments=[RaceAssignment("CustomRace", custom_mod, race_guids=("satyr-female",))],
        )
    )

    root = lsx.load_root(output / "Patch" / "Public" / "Patch" / "RootTemplates" / "boots-template.lsx")
    game_object = lsx.find_item_game_objects(root)[0]
    markers = {
        lsx.visual_object_map_key(object_node): lsx.get_attribute_value(object_node, "Marker")
        for object_node in lsx.visual_object_nodes(game_object)
    }

    assert markers["human-female"] == "human-boots"
    assert markers["satyr-female"] is None
    satyr_visual = lsx.visual_object_for_race(game_object, "satyr-female")
    map_value = next(node for node in satyr_visual.iter() if node.attrib.get("id") == "MapValue")
    assert lsx.get_attribute_value(map_value, "Object") == ""


def test_selected_custom_race_maps_are_copied_beyond_visuals(tmp_path):
    vanilla = tmp_path / "UnpackedData"
    custom_mod = tmp_path / "CustomRace"
    output = tmp_path / "Generated"

    _write_equipment_races(vanilla / "Shared" / "Mods" / "SharedDev" / "EquipmentSettings" / "EquipmentRaces.lsx", [
        ("Human Female", "human-female"),
    ])
    _write_root_template(
        vanilla / "Shared" / "Public" / "Shared" / "RootTemplates" / "armor.lsx",
        "armor-template",
        {"human-female": "human-visual"},
        parent_races_by_race={"human-female": "parent-human"},
    )
    _write_equipment_race_with_default_parent(
        custom_mod / "Mods" / "CustomRace" / "EquipmentSettings" / "EquipmentRaces.lsx",
        "Satyr Female",
        "satyr-female",
        "human-female",
    )
    _write_root_template(
        custom_mod / "Public" / "CustomRace" / "RootTemplates" / "armor.lsx",
        "armor-template",
        {"satyr-female": "satyr-visual"},
        parent_races_by_race={"satyr-female": "parent-satyr"},
    )

    run_patch(
        PatchConfig(
            vanilla_path=vanilla,
            output_dir=output,
            patch_name="Patch",
            mod_paths=[custom_mod],
            priority_order=[vanilla, custom_mod],
            race_assignments=[RaceAssignment("CustomRace", custom_mod, race_guids=("satyr-female",))],
        )
    )

    root = lsx.load_root(output / "Patch" / "Public" / "Patch" / "RootTemplates" / "armor-template.lsx")
    game_object = lsx.find_item_game_objects(root)[0]
    satyr_parent = lsx.race_map_object_for_race(game_object, "ParentRace", "satyr-female")

    assert satyr_parent is not None
    assert lsx.get_attribute_value(satyr_parent, "MapValue") == "parent-satyr"


def _write_equipment_races(path: Path, races: list[tuple[str, str]]) -> None:
    nodes = "\n".join(
        f"""<node id="EquipmentRace">
            <attribute id="Name" value="{name}" type="22" />
            <attribute id="MapKey" type="guid" value="{guid}" />
        </node>"""
        for name, guid in races
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""<?xml version="1.0" encoding="utf-8"?>
<save>
    <region id="EquipmentRaces">
        <node id="EquipmentRaces">
            <children>{nodes}</children>
        </node>
    </region>
</save>""",
        encoding="utf-8",
    )


def _write_equipment_race_with_payload(path: Path, name: str, guid: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""<?xml version="1.0" encoding="utf-8"?>
<save>
    <region id="EquipmentRaces">
        <node id="EquipmentRaces">
            <children>
                <node id="EquipmentRace">
                    <attribute id="Name" value="{name}" type="22" />
                    <attribute id="MapKey" type="guid" value="{guid}" />
                    <attribute id="BodySetVisual" type="FixedString" value="payload-body" />
                    <children>
                        <node id="Payload">
                            <attribute id="NestedRaceData" type="FixedString" value="payload-nested" />
                        </node>
                    </children>
                </node>
            </children>
        </node>
    </region>
</save>""",
        encoding="utf-8",
    )


def _write_equipment_race_with_default_parent(path: Path, name: str, guid: str, default_parent: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""<?xml version="1.0" encoding="utf-8"?>
<save>
    <region id="EquipmentRaces">
        <node id="EquipmentRaces">
            <children>
                <node id="EquipmentRace">
                    <attribute id="Name" value="{name}" type="22" />
                    <attribute id="Guid" value="{guid}" type="31" />
                    <attribute id="DefaultParent" value="{default_parent}" type="31" />
                </node>
            </children>
        </node>
    </region>
</save>""",
        encoding="utf-8",
    )


def _write_root_template(
    path: Path,
    template_id: str,
    markers_by_race: dict[str, str],
    game_object_marker: str | None = None,
    game_object_name: str | None = None,
    parent_races_by_race: dict[str, str] | None = None,
) -> None:
    objects = "\n".join(
        f"""<node id="Object">
            <attribute id="MapKey" type="guid" value="{race_guid}" />
            <attribute id="Marker" type="FixedString" value="{marker}" />
        </node>"""
        for race_guid, marker in markers_by_race.items()
    )
    extra_attribute = (
        f'\n                    <attribute id="RootMarker" type="FixedString" value="{game_object_marker}" />'
        if game_object_marker
        else ""
    )
    name_attribute = (
        f'\n                    <attribute id="Name" type="LSString" value="{game_object_name}" />'
        if game_object_name
        else ""
    )
    parent_race_objects = "\n".join(
        f"""<node id="Object">
            <attribute id="MapKey" type="guid" value="{race_guid}" />
            <attribute id="MapValue" type="guid" value="{parent_guid}" />
        </node>"""
        for race_guid, parent_guid in (parent_races_by_race or {}).items()
    )
    parent_race_node = (
        f"""
                                <node id="ParentRace">
                                    <children>{parent_race_objects}</children>
                                </node>"""
        if parent_races_by_race
        else ""
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""<?xml version="1.0" encoding="utf-8"?>
<save>
    <region id="Templates">
        <node id="Templates">
            <children>
                <node id="GameObjects">
                    <attribute id="Type" type="FixedString" value="item" />
                    <attribute id="MapKey" type="FixedString" value="{template_id}" />{name_attribute}{extra_attribute}
                    <children>
                        <node id="Equipment">
                            <children>
                                <node id="Visuals">
                                    <children>{objects}</children>
                                </node>{parent_race_node}
                            </children>
                        </node>
                    </children>
                </node>
            </children>
        </node>
    </region>
</save>""",
        encoding="utf-8",
    )


def _write_root_template_with_visual_payload(path: Path, template_id: str, race_guid: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""<?xml version="1.0" encoding="utf-8"?>
<save>
    <region id="Templates">
        <node id="Templates">
            <children>
                <node id="GameObjects">
                    <attribute id="Type" type="FixedString" value="item" />
                    <attribute id="MapKey" type="FixedString" value="{template_id}" />
                    <children>
                        <node id="Equipment">
                            <children>
                                <node id="Visuals">
                                    <children>
                                        <node id="Object">
                                            <attribute id="MapKey" type="guid" value="{race_guid}" />
                                            <attribute id="VisualResource" type="FixedString" value="payload-visual" />
                                            <children>
                                                <node id="Payload">
                                                    <attribute id="NestedVisualData" type="FixedString" value="payload-nested-visual" />
                                                </node>
                                            </children>
                                        </node>
                                    </children>
                                </node>
                            </children>
                        </node>
                    </children>
                </node>
            </children>
        </node>
    </region>
</save>""",
        encoding="utf-8",
    )
