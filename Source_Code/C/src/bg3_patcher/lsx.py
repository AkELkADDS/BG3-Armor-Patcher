from __future__ import annotations

__author__ = "AkELkA"

from copy import deepcopy
from pathlib import Path
from typing import Iterable
from xml.dom import minidom
from xml.etree import ElementTree as ET
from xml.etree.ElementTree import Element, ElementTree

from bg3_patcher.models import EquipmentRace


def local_tag(element: Element) -> str:
    """LSX may use XML namespaces; ElementTree uses Clark notation ``{uri}node``."""
    tag = element.tag
    if not isinstance(tag, str):
        return ""
    if tag.startswith("{") and "}" in tag:
        return tag.split("}", 1)[1]
    return tag


ROOT_TEMPLATE_SKELETON = """<?xml version="1.0" encoding="utf-8"?>
<save>
    <version major="4" minor="8" revision="0" build="200" lslib_meta="v1,bswap_guids,lsf_keys_adjacency" />
    <region id="Templates">
        <node id="Templates">
            <children>
            </children>
        </node>
    </region>
</save>
"""


def load_tree(path: Path) -> ElementTree:
    return ET.parse(path)


def load_root(path: Path) -> Element:
    return load_tree(path).getroot()


def _strip_blank_lines_from_pretty_xml(data: bytes) -> bytes:
    """minidom.toprettyxml adds empty lines between tags; LSX tools look cleaner without them."""
    text = data.decode("utf-8")
    lines = [line for line in text.splitlines() if line.strip()]
    return ("\n".join(lines) + "\n").encode("utf-8")


def write_tree(root: Element, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rough = ET.tostring(root, encoding="utf-8")
    parsed = minidom.parseString(rough)
    pretty = parsed.toprettyxml(indent="    ", encoding="utf-8")
    path.write_bytes(_strip_blank_lines_from_pretty_xml(pretty))


def clone(element: Element) -> Element:
    return deepcopy(element)


def is_node(element: Element, node_id: str | None = None) -> bool:
    if local_tag(element) != "node":
        return False
    return node_id is None or element.attrib.get("id") == node_id


def iter_nodes(root: Element, node_id: str | None = None) -> Iterable[Element]:
    for element in root.iter():
        if local_tag(element) != "node":
            continue
        if node_id is None or element.attrib.get("id") == node_id:
            yield element


def iter_direct_attributes(node: Element) -> Iterable[Element]:
    for child in list(node):
        if local_tag(child) == "attribute":
            yield child


def iter_equipment_race_attributes(node: Element) -> Iterable[Element]:
    """All ``attribute`` elements under this EquipmentRace node (any depth under LSX ``children`` chains)."""
    for el in node.iter():
        if el is node:
            continue
        if local_tag(el) == "attribute":
            yield el


def get_attribute_value(node: Element, attribute_id: str, type_value: str | None = None) -> str | None:
    for attribute in iter_direct_attributes(node):
        if attribute.attrib.get("id") != attribute_id:
            continue
        if type_value is not None and attribute.attrib.get("type") != type_value:
            continue
        return attribute.attrib.get("value")
    return None


def has_attribute(node: Element, attribute_id: str, value: str, type_value: str | None = None) -> bool:
    for attribute in iter_direct_attributes(node):
        if attribute.attrib.get("id") != attribute_id:
            continue
        if attribute.attrib.get("value") != value:
            continue
        if type_value is not None and attribute.attrib.get("type") != type_value:
            continue
        return True
    return False


def get_children_container(node: Element) -> Element | None:
    for child in list(node):
        if local_tag(child) == "children":
            return child
    return None


def ensure_children_container(node: Element) -> Element:
    existing = get_children_container(node)
    if existing is not None:
        return existing
    return ET.SubElement(node, "children")


def child_nodes(node: Element, node_id: str | None = None) -> list[Element]:
    found: list[Element] = []
    for child in list(node):
        if is_node(child, node_id):
            found.append(child)
        elif local_tag(child) == "children":
            for grandchild in list(child):
                if is_node(grandchild, node_id):
                    found.append(grandchild)
    return found


def first_child_node(node: Element, node_id: str) -> Element | None:
    nodes = child_nodes(node, node_id)
    return nodes[0] if nodes else None


def is_item_game_object(node: Element) -> bool:
    return is_node(node, "GameObjects") and has_attribute(node, "Type", "item", "FixedString")


def find_item_game_objects(root: Element) -> list[Element]:
    return [node for node in iter_nodes(root, "GameObjects") if is_item_game_object(node)]


def game_object_map_key(game_object: Element) -> str | None:
    return get_attribute_value(game_object, "MapKey", "FixedString") or get_attribute_value(game_object, "MapKey")


def game_object_name(game_object: Element) -> str | None:
    return get_attribute_value(game_object, "Name", "LSString") or get_attribute_value(game_object, "Name")


def is_footwear_game_object(game_object: Element) -> bool:
    name = game_object_name(game_object)
    if not name:
        return False
    lowered = name.lower()
    return any(token in lowered for token in ("shoe", "shoes", "boot", "boots"))


def equipment_node(game_object: Element) -> Element | None:
    return first_child_node(game_object, "Equipment")


def visuals_node(game_object: Element) -> Element | None:
    equipment = equipment_node(game_object)
    if equipment is None:
        return None
    return first_child_node(equipment, "Visuals")


def visual_object_nodes(game_object: Element) -> list[Element]:
    return race_map_object_nodes(game_object, "Visuals")


def visual_object_map_key(object_node: Element) -> str | None:
    return get_attribute_value(object_node, "MapKey", "guid") or get_attribute_value(object_node, "MapKey")


def contains_equipment(game_object: Element) -> bool:
    return equipment_node(game_object) is not None


def ensure_equipment_visuals(game_object: Element) -> Element:
    return ensure_equipment_race_map(game_object, "Visuals")


def replace_or_append_visual_object(game_object: Element, object_node: Element) -> None:
    replace_or_append_race_map_object(game_object, "Visuals", object_node)


def equipment_race_map_nodes(game_object: Element) -> list[Element]:
    equipment = equipment_node(game_object)
    if equipment is None:
        return []

    maps: list[Element] = []
    for node in child_nodes(equipment):
        if any(visual_object_map_key(object_node) for object_node in child_nodes(node, "Object")):
            maps.append(node)
    return maps


def equipment_race_map_ids(game_object: Element) -> set[str]:
    return {
        node_id
        for node in equipment_race_map_nodes(game_object)
        if (node_id := node.attrib.get("id"))
    }


def race_map_object_nodes(game_object: Element, map_node_id: str) -> list[Element]:
    equipment = equipment_node(game_object)
    if equipment is None:
        return []
    race_map = first_child_node(equipment, map_node_id)
    if race_map is None:
        return []
    return child_nodes(race_map, "Object")


def ensure_equipment_race_map(game_object: Element, map_node_id: str) -> Element:
    equipment = equipment_node(game_object)
    if equipment is None:
        equipment = ET.Element("node", {"id": "Equipment"})
        ensure_children_container(game_object).append(equipment)
    race_map = first_child_node(equipment, map_node_id)
    if race_map is None:
        race_map = ET.Element("node", {"id": map_node_id})
        ensure_children_container(equipment).append(race_map)
    return race_map


def replace_or_append_race_map_object(game_object: Element, map_node_id: str, object_node: Element) -> None:
    incoming_guid = visual_object_map_key(object_node)
    if not incoming_guid:
        return

    race_map = ensure_equipment_race_map(game_object, map_node_id)
    container = get_children_container(race_map)
    search_parent = container if container is not None else race_map

    for index, existing in enumerate(list(search_parent)):
        if not is_node(existing, "Object"):
            continue
        if visual_object_map_key(existing) == incoming_guid:
            search_parent.remove(existing)
            search_parent.insert(index, clone(object_node))
            return

    ensure_children_container(race_map).append(clone(object_node))


def replace_visual_objects(game_object: Element, object_nodes: list[Element]) -> None:
    replace_race_map_objects(game_object, "Visuals", object_nodes)


def replace_race_map_objects(game_object: Element, map_node_id: str, object_nodes: list[Element]) -> None:
    race_map = ensure_equipment_race_map(game_object, map_node_id)
    container = get_children_container(race_map)
    search_parent = container if container is not None else race_map

    for existing in list(search_parent):
        if is_node(existing, "Object"):
            search_parent.remove(existing)

    target = ensure_children_container(race_map)
    for object_node in object_nodes:
        target.append(clone(object_node))


def visual_object_for_race(game_object: Element, race_guid: str) -> Element | None:
    return race_map_object_for_race(game_object, "Visuals", race_guid)


def race_map_object_for_race(game_object: Element, map_node_id: str, race_guid: str) -> Element | None:
    for object_node in race_map_object_nodes(game_object, map_node_id):
        if visual_object_map_key(object_node) == race_guid:
            return object_node
    return None


def clone_visual_object_for_race(object_node: Element, race_guid: str) -> Element:
    cloned = clone(object_node)
    for attribute in iter_direct_attributes(cloned):
        if attribute.attrib.get("id") == "MapKey":
            attribute.attrib["type"] = "guid"
            attribute.attrib["value"] = race_guid
            return cloned

    map_key = ET.Element("attribute", {"id": "MapKey", "type": "guid", "value": race_guid})
    cloned.insert(0, map_key)
    return cloned


def create_parent_race_object(race_guid: str, parent_guid: str) -> Element:
    node = ET.Element("node", {"id": "Object"})
    node.append(ET.Element("attribute", {"id": "MapKey", "type": "guid", "value": race_guid}))
    node.append(ET.Element("attribute", {"id": "MapValue", "type": "guid", "value": parent_guid}))
    return node


def create_blank_visual_object(race_guid: str) -> Element:
    node = ET.Element("node", {"id": "Object"})
    node.append(ET.Element("attribute", {"id": "MapKey", "type": "guid", "value": race_guid}))
    children = ET.SubElement(node, "children")
    map_value = ET.SubElement(children, "node", {"id": "MapValue"})
    map_value.append(ET.Element("attribute", {"id": "Object", "type": "FixedString", "value": ""}))
    return node


def find_equipment_race_nodes(root: Element) -> list[Element]:
    return list(iter_nodes(root, "EquipmentRace"))


def equipment_race_name(node: Element) -> str | None:
    """Display name from ``<attribute id="Name" value="..." />`` (any ``type``, e.g. ``22``)."""
    for attribute in iter_equipment_race_attributes(node):
        if attribute.attrib.get("id") != "Name":
            continue
        raw = attribute.attrib.get("value")
        if raw is not None and str(raw).strip():
            return str(raw).strip()
    return None


def equipment_race_guid(node: Element) -> str | None:
    attrs = list(iter_equipment_race_attributes(node))

    def pick(attr_id: str, type_opt: str | None = None) -> str | None:
        for attribute in attrs:
            if attribute.attrib.get("id") != attr_id:
                continue
            if type_opt is not None and attribute.attrib.get("type") != type_opt:
                continue
            raw = attribute.attrib.get("value")
            return str(raw).strip() if raw is not None and str(raw).strip() else None
        return None

    return (
        pick("MapKey", "guid")
        or pick("MapKey", "FixedString")
        or pick("MapKey")
        or pick("UUID", "guid")
        or pick("UUID", "FixedString")
        or pick("UUID")
        # bg3-modders-multitool / some exports use Guid + numeric type (e.g. 31), not MapKey
        or pick("Guid", "31")
        or pick("Guid", "guid")
        or pick("Guid")
    )


def equipment_race_default_parent(node: Element) -> str | None:
    attrs = list(iter_equipment_race_attributes(node))
    for type_opt in ("31", "guid", "FixedString", None):
        for attribute in attrs:
            if attribute.attrib.get("id") != "DefaultParent":
                continue
            if type_opt is not None and attribute.attrib.get("type") != type_opt:
                continue
            raw = attribute.attrib.get("value")
            if raw is not None and str(raw).strip():
                return str(raw).strip()
    return None


def extract_equipment_races(root: Element, source_label: str, source_path: Path) -> list[EquipmentRace]:
    races: list[EquipmentRace] = []
    for node in find_equipment_race_nodes(root):
        name = equipment_race_name(node)
        guid = equipment_race_guid(node)
        if not name or not guid:
            continue
        races.append(
            EquipmentRace(
                name=name,
                guid=guid,
                source_label=source_label,
                source_path=source_path,
                node=node,
            )
        )
    return races


def equipment_races_children(root: Element) -> Element:
    region_nodes = list(iter_nodes(root, "EquipmentRaces"))
    if region_nodes:
        return ensure_children_container(region_nodes[0])

    race_nodes = find_equipment_race_nodes(root)
    if not race_nodes:
        raise ValueError("No EquipmentRace nodes found.")

    parent = _find_parent(root, race_nodes[0])
    if parent is None:
        raise ValueError("Could not locate EquipmentRace parent.")
    if local_tag(parent) == "children":
        return parent
    return ensure_children_container(parent)


def root_templates_children(root: Element) -> Element:
    template_nodes = list(iter_nodes(root, "Templates"))
    if not template_nodes:
        raise ValueError("No Templates node found.")
    return ensure_children_container(template_nodes[0])


def create_root_template_document(game_object: Element) -> Element:
    root = ET.fromstring(ROOT_TEMPLATE_SKELETON)
    root_templates_children(root).append(clone(game_object))
    return root


def _find_parent(root: Element, target: Element) -> Element | None:
    for parent in root.iter():
        for child in list(parent):
            if child is target:
                return parent
    return None
