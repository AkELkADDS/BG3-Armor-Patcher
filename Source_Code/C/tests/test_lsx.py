from __future__ import annotations

__author__ = "AkELkA"

from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from bg3_patcher import lsx


def test_extracts_equipment_races_with_xml_namespaces(tmp_path):
    """Game LSX often uses a default xmlns; tags become ``{uri}node`` which breaks bare ``.iter('node')``."""
    ns = "http://example.com/ls"
    root = ET.fromstring(
        f"""<save xmlns="{ns}">
            <region id="EquipmentRaces">
                <node id="EquipmentRaces">
                    <children>
                        <node id="EquipmentRace">
                            <attribute id="Name" value="Human Male" type="22" />
                            <attribute id="MapKey" type="guid" value="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee" />
                        </node>
                    </children>
                </node>
            </region>
        </save>"""
    )

    races = lsx.extract_equipment_races(root, "test", tmp_path)
    assert [(race.name, race.guid) for race in races] == [
        ("Human Male", "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"),
    ]


def test_parse_repo_root_equipment_races_sample_if_present():
    """Regression: multitool-export vanilla layout next to tests (optional file)."""
    sample = Path(__file__).resolve().parents[1] / "EquipmentRaces.lsx"
    if not sample.is_file():
        pytest.skip("EquipmentRaces.lsx not at repo root")
    races = lsx.extract_equipment_races(lsx.load_root(sample), "vanilla", sample.parent)
    names = {r.name for r in races}
    assert "Half-Elf Male" in names
    assert "Human Female" in names
    assert len(races) >= 20


def test_extract_equipment_races_multitool_guid_attr(tmp_path):
    """Multitool-style vanilla file: ``Guid`` + type 31, wrapper ``node id=root``."""
    root = ET.fromstring(
        """<save>
            <region id="EquipmentRaces">
                <node id="root">
                    <children>
                        <node id="EquipmentRace">
                            <attribute id="Name" value="Half-Elf Male" type="22" />
                            <attribute id="Guid" value="a0737289-ca84-4fde-bd52-25bae4fe8dea" type="31" />
                        </node>
                    </children>
                </node>
            </region>
        </save>"""
    )
    races = lsx.extract_equipment_races(root, "test", tmp_path)
    assert races[0].name == "Half-Elf Male"
    assert races[0].guid == "a0737289-ca84-4fde-bd52-25bae4fe8dea"


def test_equipment_race_attributes_deeply_nested_children(tmp_path):
    root = ET.fromstring(
        """<save>
            <region id="EquipmentRaces">
                <node id="EquipmentRaces">
                    <children>
                        <node id="EquipmentRace">
                            <children>
                                <children>
                                    <attribute id="Name" value="Deep Nested" type="22" />
                                    <attribute id="MapKey" type="guid" value="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb" />
                                </children>
                            </children>
                        </node>
                    </children>
                </node>
            </region>
        </save>"""
    )

    races = lsx.extract_equipment_races(root, "test", tmp_path)
    assert [(race.name, race.guid) for race in races] == [
        ("Deep Nested", "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
    ]


def test_equipment_race_attributes_under_children_wrapper(tmp_path):
    root = ET.fromstring(
        """<save>
            <region id="EquipmentRaces">
                <node id="EquipmentRaces">
                    <children>
                        <node id="EquipmentRace">
                            <children>
                                <attribute id="Name" value="Half-Elf Female" type="22" />
                                <attribute id="MapKey" type="guid" value="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee" />
                            </children>
                        </node>
                    </children>
                </node>
            </region>
        </save>"""
    )

    races = lsx.extract_equipment_races(root, "test", tmp_path)
    assert [(race.name, race.guid) for race in races] == [
        ("Half-Elf Female", "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"),
    ]


def test_extracts_item_game_objects_and_equipment_races(tmp_path):
    root = ET.fromstring(
        """<save>
            <region id="Templates">
                <node id="Templates">
                    <children>
                        <node id="GameObjects">
                            <attribute id="Type" type="FixedString" value="item" />
                            <attribute id="MapKey" type="FixedString" value="armor-1" />
                        </node>
                        <node id="GameObjects">
                            <attribute id="Type" type="FixedString" value="character" />
                            <attribute id="MapKey" type="FixedString" value="ignored" />
                        </node>
                    </children>
                </node>
            </region>
            <region id="EquipmentRaces">
                <node id="EquipmentRaces">
                    <children>
                        <node id="EquipmentRace">
                            <attribute id="Name" value="Dragonborn Male" type="22" />
                            <attribute id="MapKey" type="guid" value="race-1" />
                        </node>
                    </children>
                </node>
            </region>
        </save>"""
    )

    game_objects = lsx.find_item_game_objects(root)
    races = lsx.extract_equipment_races(root, "test", tmp_path)

    assert [lsx.game_object_map_key(node) for node in game_objects] == ["armor-1"]
    assert [(race.name, race.guid) for race in races] == [("Dragonborn Male", "race-1")]


def test_write_tree_does_not_insert_double_blank_lines(tmp_path: Path) -> None:
    root = ET.fromstring(
        '<save><region id="R"><node id="N"><attribute id="a" value="b" /></node></region></save>'
    )
    path = tmp_path / "out.lsx"
    lsx.write_tree(root, path)
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    prev_blank = False
    for line in lines:
        blank = not line.strip()
        assert not (blank and prev_blank), "consecutive whitespace-only lines from pretty printer"
        prev_blank = blank


def test_replaces_visual_object_by_equipment_race_guid():
    game_object = ET.fromstring(
        """<node id="GameObjects">
            <attribute id="Type" type="FixedString" value="item" />
            <attribute id="MapKey" type="FixedString" value="armor-1" />
            <children>
                <node id="Equipment">
                    <children>
                        <node id="Visuals">
                            <children>
                                <node id="Object">
                                    <attribute id="MapKey" type="guid" value="race-1" />
                                    <attribute id="Marker" type="FixedString" value="old" />
                                </node>
                            </children>
                        </node>
                    </children>
                </node>
            </children>
        </node>"""
    )
    incoming = ET.fromstring(
        """<node id="Object">
            <attribute id="MapKey" type="guid" value="race-1" />
            <attribute id="Marker" type="FixedString" value="new" />
        </node>"""
    )

    lsx.replace_or_append_visual_object(game_object, incoming)

    objects = lsx.visual_object_nodes(game_object)
    assert len(objects) == 1
    assert lsx.get_attribute_value(objects[0], "Marker") == "new"
