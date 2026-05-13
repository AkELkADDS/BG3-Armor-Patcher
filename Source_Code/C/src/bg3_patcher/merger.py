from __future__ import annotations

__author__ = "AkELkA"

import json
from collections import defaultdict
from pathlib import Path
from xml.etree.ElementTree import Element

from bg3_patcher import lsx
from bg3_patcher.models import EquipmentRace, PatchConfig, PatchReport, RootTemplateRecord, ScanResult
from bg3_patcher.scanner import scan

ZERO_GUID = "00000000-0000-0000-0000-000000000000"


def run_patch(config: PatchConfig) -> PatchReport:
    scan_result = scan(config)
    report = PatchReport(warnings=list(scan_result.warnings))

    output_root = config.output_dir / config.patch_name
    _write_merged_equipment_races(config, scan_result, output_root, report)
    _write_root_templates(config, scan_result, output_root, report)
    _write_report(output_root, report)

    return report


def _write_merged_equipment_races(
    config: PatchConfig,
    scan_result: ScanResult,
    output_root: Path,
    report: PatchReport,
) -> None:
    root = lsx.load_root(scan_result.vanilla_equipment_races_path)
    children = lsx.equipment_races_children(root)

    existing_guids = {
        race.guid
        for race in lsx.extract_equipment_races(root, "Vanilla", config.vanilla_path)
    }
    selected_custom_guids = _selected_custom_race_guids(config, scan_result)
    custom_races = _races_by_guid(scan_result)

    for guid in sorted(selected_custom_guids):
        race = custom_races.get(guid)
        if race is None:
            report.warnings.append(f"Selected custom equipment race was not found: {guid}")
            continue
        if guid in existing_guids:
            report.warnings.append(f"Skipped duplicate equipment race GUID: {guid} ({race.name})")
            continue
        children.append(lsx.clone(race.node))
        existing_guids.add(guid)

    output_path = output_root / "Mods" / config.patch_name / "EquipmentSettings" / "EquipmentRaces.lsx"
    lsx.write_tree(root, output_path)
    report.written_files.append(output_path)


def _write_root_templates(
    config: PatchConfig,
    scan_result: ScanResult,
    output_root: Path,
    report: PatchReport,
) -> None:
    needed_ids = scan_result.mod_contributed_template_ids
    if not needed_ids:
        report.warnings.append(
            "No mod RootTemplates with Equipment and Visual Object (race MapKey) entries were found; "
            "skipping merged RootTemplates output."
        )
        return

    assignments_by_source = _assigned_race_guids_by_source(config, scan_result)
    custom_default_parents = _selected_custom_race_default_parents(config, scan_result)
    grouped_records = _group_root_templates(scan_result)
    output_dir = output_root / "Public" / config.patch_name / "RootTemplates"
    vanilla_race_guids = {race.guid for race in scan_result.equipment_races_by_source.get(config.vanilla_path, [])}
    # Race-keyed maps from the visual-base record must not inject *non-vanilla* custom races: that
    # snapshot is often vanilla/low-priority and may contain wrong keys. True custom-GUID races are
    # merged from mod records next, then filled by _append_missing_*. (GUIDs that also exist in
    # vanilla EquipmentRaces are still seeded here so duplicate/reused GUIDs keep baseline visuals.)
    omit_from_visual_base_seed = _selected_custom_race_guids(config, scan_result) - vanilla_race_guids

    for template_id in sorted(needed_ids):
        records = grouped_records.get(template_id, [])
        if not records:
            report.warnings.append(
                f"Template {template_id} was listed from a mod but no matching RootTemplate records were loaded."
            )
            continue
        base = _choose_structural_base_record(config, records)
        if base is None:
            report.skipped.append(f"Skipped {template_id}: no priority source contains Equipment data.")
            continue

        merged_game_object = lsx.clone(base.node)
        visual_base = _choose_visual_base_record(records)
        if visual_base is not None:
            _replace_race_maps_from_base(
                merged_game_object,
                visual_base.node,
                omit_race_guids=omit_from_visual_base_seed,
            )

        for record in sorted(records, key=lambda item: item.priority_index):
            assigned_guids = assignments_by_source.get(record.source_path, set())
            if not assigned_guids:
                continue
            _merge_assigned_race_maps(merged_game_object, record.node, assigned_guids)

        _append_missing_custom_race_maps_from_default_parents(
            merged_game_object,
            custom_default_parents,
            is_footwear_template=_is_footwear_template(records),
        )

        document = lsx.create_root_template_document(merged_game_object)
        output_path = output_dir / f"{template_id}.lsx"
        lsx.write_tree(document, output_path)
        report.written_files.append(output_path)


def _write_report(output_root: Path, report: PatchReport) -> None:
    report_json = output_root / "patch-report.json"
    report_txt = output_root / "patch-report.txt"
    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_json.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")

    lines = ["BG3 Armor Patcher Report", ""]
    for title, entries in [
        ("Written files", [str(path) for path in report.written_files]),
        ("Warnings", report.warnings),
        ("Skipped", report.skipped),
        ("Errors", report.errors),
    ]:
        lines.append(title)
        lines.extend(f"- {entry}" for entry in entries)
        if not entries:
            lines.append("- none")
        lines.append("")
    report_txt.write_text("\n".join(lines), encoding="utf-8")
    report.written_files.extend([report_json, report_txt])


def _selected_custom_race_guids(config: PatchConfig, scan_result: ScanResult) -> set[str]:
    custom_guids: set[str] = set()
    source_races = scan_result.equipment_races_by_source

    for assignment in config.race_assignments:
        if assignment.use_vanilla_races:
            continue
        available = {race.guid for race in source_races.get(assignment.source_path, [])}
        if assignment.include_all:
            custom_guids.update(available)
        else:
            custom_guids.update(guid for guid in assignment.race_guids if guid in available)
    return custom_guids


def _assigned_race_guids_by_source(config: PatchConfig, scan_result: ScanResult) -> dict[Path, set[str]]:
    by_source: dict[Path, set[str]] = defaultdict(set)
    source_races = scan_result.equipment_races_by_source
    vanilla_guids = {race.guid for race in source_races.get(config.vanilla_path, [])}

    for assignment in config.race_assignments:
        if assignment.use_vanilla_races:
            by_source[assignment.source_path].update(assignment.race_guids)
            continue

        if assignment.include_all:
            by_source[assignment.source_path].update(
                race.guid for race in source_races.get(assignment.source_path, []) if race.guid not in vanilla_guids
            )
            continue

        by_source[assignment.source_path].update(guid for guid in assignment.race_guids if guid not in vanilla_guids)

    return by_source


def _selected_custom_race_default_parents(config: PatchConfig, scan_result: ScanResult) -> dict[str, str]:
    selected_custom_guids = _selected_custom_race_guids(config, scan_result)
    vanilla_guids = {race.guid for race in scan_result.equipment_races_by_source.get(config.vanilla_path, [])}
    defaults: dict[str, str] = {}

    for source_path, races in scan_result.equipment_races_by_source.items():
        if source_path == config.vanilla_path:
            continue
        for race in races:
            if race.guid not in selected_custom_guids or race.guid in vanilla_guids:
                continue
            default_parent = lsx.equipment_race_default_parent(race.node)
            if default_parent:
                defaults[race.guid] = default_parent

    return defaults


def _merge_assigned_race_maps(
    merged_game_object: Element,
    source_game_object: Element,
    assigned_guids: set[str],
) -> None:
    for race_map in lsx.equipment_race_map_nodes(source_game_object):
        map_node_id = race_map.attrib.get("id")
        if not map_node_id:
            continue
        for object_node in lsx.race_map_object_nodes(source_game_object, map_node_id):
            object_guid = lsx.visual_object_map_key(object_node)
            if object_guid in assigned_guids:
                lsx.replace_or_append_race_map_object(merged_game_object, map_node_id, object_node)


def _replace_race_maps_from_base(
    merged_game_object: Element,
    base_game_object: Element,
    *,
    omit_race_guids: set[str] | frozenset[str] = frozenset(),
) -> None:
    skip = frozenset(omit_race_guids)
    for race_map in lsx.equipment_race_map_nodes(base_game_object):
        map_node_id = race_map.attrib.get("id")
        if not map_node_id:
            continue
        object_nodes = lsx.race_map_object_nodes(base_game_object, map_node_id)
        if skip:
            object_nodes = [
                node
                for node in object_nodes
                if (key := lsx.visual_object_map_key(node)) is None or key not in skip
            ]
        lsx.replace_race_map_objects(merged_game_object, map_node_id, object_nodes)


def _append_missing_custom_race_maps_from_default_parents(
    game_object: Element,
    custom_default_parents: dict[str, str],
    *,
    is_footwear_template: bool,
) -> None:
    race_map_ids = lsx.equipment_race_map_ids(game_object)
    for custom_guid, parent_guid in sorted(custom_default_parents.items()):
        for map_node_id in sorted(race_map_ids):
            if lsx.race_map_object_for_race(game_object, map_node_id, custom_guid) is not None:
                continue
            if map_node_id == "ParentRace":
                lsx.replace_or_append_race_map_object(
                    game_object,
                    map_node_id,
                    lsx.create_parent_race_object(custom_guid, ZERO_GUID),
                )
                continue
            if map_node_id == "Visuals" and is_footwear_template:
                lsx.replace_or_append_race_map_object(
                    game_object,
                    map_node_id,
                    lsx.create_blank_visual_object(custom_guid),
                )
                continue
            parent_object = lsx.race_map_object_for_race(game_object, map_node_id, parent_guid)
            if parent_object is None:
                continue
            inherited_object = lsx.clone_visual_object_for_race(parent_object, custom_guid)
            lsx.replace_or_append_race_map_object(game_object, map_node_id, inherited_object)


def _is_footwear_template(records: list[RootTemplateRecord]) -> bool:
    return any(lsx.is_footwear_game_object(record.node) for record in records)


def _races_by_guid(scan_result: ScanResult) -> dict[str, EquipmentRace]:
    races: dict[str, EquipmentRace] = {}
    for source_races in scan_result.equipment_races_by_source.values():
        for race in source_races:
            races.setdefault(race.guid, race)
    return races


def _group_root_templates(scan_result: ScanResult) -> dict[str, list[RootTemplateRecord]]:
    grouped: dict[str, list[RootTemplateRecord]] = defaultdict(list)
    for records in scan_result.root_templates_by_source.values():
        for record in records:
            grouped[record.template_id].append(record)
    return grouped


def _choose_structural_base_record(config: PatchConfig, records: list[RootTemplateRecord]) -> RootTemplateRecord | None:
    with_equipment = [record for record in records if lsx.contains_equipment(record.node)]
    if not with_equipment:
        return None

    vanilla_assignment_sources = {
        assignment.source_path
        for assignment in config.race_assignments
        if assignment.use_vanilla_races
    }
    vanilla_assignment_records = [
        record for record in with_equipment if record.source_path in vanilla_assignment_sources
    ]
    if vanilla_assignment_records:
        return max(vanilla_assignment_records, key=lambda record: record.priority_index)

    assigned_sources = {assignment.source_path for assignment in config.race_assignments}
    assigned_records = [record for record in with_equipment if record.source_path in assigned_sources]
    if assigned_records:
        return max(assigned_records, key=lambda record: record.priority_index)

    return min(with_equipment, key=lambda record: record.priority_index)


def _choose_visual_base_record(records: list[RootTemplateRecord]) -> RootTemplateRecord | None:
    with_visuals = [record for record in records if lsx.visual_object_nodes(record.node)]
    if not with_visuals:
        return None
    return min(with_visuals, key=lambda record: record.priority_index)
