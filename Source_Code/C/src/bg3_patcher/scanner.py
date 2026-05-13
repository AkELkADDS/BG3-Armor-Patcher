from __future__ import annotations

__author__ = "AkELkA"

from pathlib import Path

from bg3_patcher import lsx
from bg3_patcher.models import EquipmentRace, PatchConfig, PatchValidationError, RootTemplateRecord, ScanResult


VANILLA_EQUIPMENT_RACES = Path("Shared") / "Mods" / "SharedDev" / "EquipmentSettings" / "EquipmentRaces.lsx"

VANILLA_EQUIPMENT_RACES_FILENAME = "EquipmentRaces.lsx"


def vanilla_scan_anchor(vanilla_path: Path) -> Path:
    """Directory used as an extra search base for RootTemplates (when path is a file, use its parent)."""
    if vanilla_path.is_file():
        return vanilla_path.parent
    return vanilla_path


def vanilla_equipment_races_search_roots(vanilla_path: Path) -> list[Path]:
    """Try these directories under/below vanilla_path for Shared/Mods/... layout."""
    return [
        vanilla_path,
        vanilla_path / "UnpackedData",
        vanilla_path / "Data",
    ]


def resolve_vanilla_equipment_races_path(vanilla_path: Path) -> Path | None:
    """Locate vanilla EquipmentRaces.lsx.

    Accepts:
    - Full path to ``EquipmentRaces.lsx``
    - The ``EquipmentSettings`` folder containing that file
    - ``UnpackedData`` / ``Data`` / etc. (see ``vanilla_equipment_races_search_roots``)
    """
    try:
        if not vanilla_path.exists():
            return None
    except OSError:
        return None

    if vanilla_path.is_file():
        if vanilla_path.name.casefold() == VANILLA_EQUIPMENT_RACES_FILENAME.casefold():
            return vanilla_path
        return None

    if vanilla_path.is_dir():
        direct = vanilla_path / VANILLA_EQUIPMENT_RACES_FILENAME
        if direct.is_file():
            return direct

    rel = VANILLA_EQUIPMENT_RACES
    for root in vanilla_equipment_races_search_roots(vanilla_path):
        candidate = root / rel
        if candidate.is_file():
            return candidate
    return None


def format_vanilla_equipment_races_search_hint(vanilla_path: Path) -> str:
    lines: list[str] = []
    if vanilla_path.is_file():
        lines.append(str(vanilla_path))
    elif vanilla_path.is_dir():
        lines.append(str(vanilla_path / VANILLA_EQUIPMENT_RACES_FILENAME))
    for root in vanilla_equipment_races_search_roots(vanilla_path):
        lines.append(str(root / VANILLA_EQUIPMENT_RACES))
    seen: set[str] = set()
    ordered: list[str] = []
    for line in lines:
        if line not in seen:
            seen.add(line)
            ordered.append(line)
    return "\n".join(ordered)


def resolve_vanilla_data_root(vanilla_path: Path) -> Path | None:
    """Directory that contains ``Shared/Mods/SharedDev/...`` (usually UnpackedData)."""
    races_file = resolve_vanilla_equipment_races_path(vanilla_path)
    if races_file is None:
        return None
    root = races_file.resolve()
    for _ in range(len(VANILLA_EQUIPMENT_RACES.parts)):
        root = root.parent
    return root


def all_vanilla_root_template_dirs(vanilla_path: Path) -> list[Path]:
    """RootTemplates paths under the resolved data root and under vanilla_path (deduped)."""
    bases: list[Path] = []
    data_root = resolve_vanilla_data_root(vanilla_path)
    if data_root is not None:
        bases.append(data_root)
    bases.append(vanilla_scan_anchor(vanilla_path))
    seen_resolved: set[Path] = set()
    out: list[Path] = []
    for base in bases:
        for relative in VANILLA_ROOT_TEMPLATE_DIRS:
            candidate = base / relative
            try:
                key = candidate.resolve()
            except OSError:
                key = candidate
            if key in seen_resolved:
                continue
            seen_resolved.add(key)
            out.append(candidate)
    return out


VANILLA_ROOT_TEMPLATE_DIRS = [
    Path("Gustav") / "Public" / "Gustav" / "RootTemplates",
    Path("Gustav") / "Public" / "GustavDev" / "RootTemplates",
    Path("Gustav") / "Public" / "Honour" / "RootTemplates",
    Path("GustavX") / "Public" / "GustavX" / "RootTemplates",
    Path("Patch8_HotFix3") / "Public" / "Shared" / "RootTemplates",
    Path("Patch8_HotFix1") / "Public" / "Shared" / "RootTemplates",
    Path("Shared") / "Public" / "Shared" / "RootTemplates",
    Path("Shared") / "Public" / "SharedDev" / "RootTemplates",
]


def validate_config(config: PatchConfig) -> None:
    errors: list[str] = []

    if not config.vanilla_path.exists():
        errors.append(f"Vanilla path does not exist: {config.vanilla_path}")
    elif not (config.vanilla_path.is_dir() or config.vanilla_path.is_file()):
        errors.append(f"Vanilla path must be a file or directory: {config.vanilla_path}")

    if config.vanilla_path.exists() and (
        config.vanilla_path.is_dir() or config.vanilla_path.is_file()
    ):
        resolved_races = resolve_vanilla_equipment_races_path(config.vanilla_path)
        if resolved_races is None:
            errors.append(
                "Vanilla EquipmentRaces.lsx not found. Use UnpackedData, "
                r"\Shared\Mods\SharedDev\EquipmentSettings, or the full path to EquipmentRaces.lsx. "
                "Tried:\n"
                + format_vanilla_equipment_races_search_hint(config.vanilla_path)
            )

    for mod_path in config.mod_paths:
        if not mod_path.exists():
            errors.append(f"Mod path does not exist: {mod_path}")
        elif not mod_path.is_dir():
            errors.append(f"Mod path is not a directory: {mod_path}")

    for root_dir in existing_root_template_dirs(config):
        errors.extend(unconverted_lsf_errors(root_dir))

    if errors:
        raise PatchValidationError(errors)


def scan(config: PatchConfig) -> ScanResult:
    validate_config(config)

    priority_order = normalized_priority_order(config)
    priority_lookup = {path.resolve(): index for index, path in enumerate(priority_order)}

    equipment_races_by_source: dict[Path, list[EquipmentRace]] = {}
    root_templates_by_source: dict[Path, list[RootTemplateRecord]] = {}
    warnings: list[str] = []

    vanilla_races_path = resolve_vanilla_equipment_races_path(config.vanilla_path)
    if vanilla_races_path is None:
        raise PatchValidationError(["Vanilla EquipmentRaces.lsx missing after validation."])
    equipment_races_by_source[config.vanilla_path] = _read_equipment_races(
        vanilla_races_path,
        "Vanilla",
        config.vanilla_path,
    )

    mod_contributed_ids: set[str] = set()
    for mod_path in config.mod_paths:
        label = source_label(mod_path)
        race_files = mod_equipment_race_files(mod_path)
        races: list[EquipmentRace] = []
        for race_file in race_files:
            races.extend(_read_equipment_races(race_file, label, mod_path))
        equipment_races_by_source[mod_path] = races

        root_dirs = mod_root_template_dirs(mod_path)
        root_templates_by_source[mod_path] = _read_root_templates(
            root_dirs,
            label,
            mod_path,
            priority_lookup.get(mod_path.resolve(), len(priority_lookup)),
            warnings,
            template_id_filter=None,
        )
        for record in root_templates_by_source[mod_path]:
            if root_template_record_is_merge_candidate(record):
                mod_contributed_ids.add(record.template_id)

    vanilla_root_dirs = [path for path in all_vanilla_root_template_dirs(config.vanilla_path) if path.exists()]
    if mod_contributed_ids:
        root_templates_by_source[config.vanilla_path] = _read_root_templates(
            vanilla_root_dirs,
            "Vanilla",
            config.vanilla_path,
            priority_lookup.get(config.vanilla_path.resolve(), 0),
            warnings,
            template_id_filter=frozenset(mod_contributed_ids),
        )
    else:
        root_templates_by_source[config.vanilla_path] = []

    return ScanResult(
        vanilla_equipment_races_path=vanilla_races_path,
        vanilla_root_template_dirs=vanilla_root_dirs,
        equipment_races_by_source=equipment_races_by_source,
        root_templates_by_source=root_templates_by_source,
        mod_contributed_template_ids=frozenset(mod_contributed_ids),
        warnings=warnings,
    )


def normalized_priority_order(config: PatchConfig) -> list[Path]:
    ordered: list[Path] = []
    for path in [config.vanilla_path, *config.priority_order, *config.mod_paths]:
        if not _contains_path(ordered, path):
            ordered.append(path)
    return ordered


def existing_root_template_dirs(config: PatchConfig) -> list[Path]:
    dirs = [path for path in all_vanilla_root_template_dirs(config.vanilla_path) if path.exists()]
    for mod_path in config.mod_paths:
        dirs.extend(mod_root_template_dirs(mod_path))
    return dirs


def mod_equipment_race_files(mod_path: Path) -> list[Path]:
    mods_dir = mod_path / "Mods"
    if not mods_dir.exists():
        return []
    return sorted(mods_dir.glob("*/EquipmentSettings/EquipmentRaces.lsx"))


def mod_root_template_dirs(mod_path: Path) -> list[Path]:
    public_dir = mod_path / "Public"
    if not public_dir.exists():
        return []
    return sorted(path for path in public_dir.glob("*/RootTemplates") if path.is_dir())


def unconverted_lsf_errors(root_template_dir: Path) -> list[str]:
    errors: list[str] = []
    for lsf_path in sorted(root_template_dir.rglob("*.lsf")):
        if converted_lsx_exists(lsf_path):
            continue
        errors.append(
            "Root template .lsf needs manual conversion to .lsx before patching: "
            f"{lsf_path}"
        )
    return errors


def converted_lsx_exists(lsf_path: Path) -> bool:
    candidates = [
        lsf_path.with_suffix(".lsx"),
        lsf_path.with_name(f"{lsf_path.name}.lsx"),
    ]
    return any(candidate.exists() for candidate in candidates)


def source_label(path: Path) -> str:
    return path.name or str(path)


def _read_equipment_races(path: Path, label: str, source_path: Path) -> list[EquipmentRace]:
    if not path.exists():
        return []
    root = lsx.load_root(path)
    return lsx.extract_equipment_races(root, label, source_path)


def root_template_record_is_merge_candidate(record: RootTemplateRecord) -> bool:
    """True when this mod item defines Equipment and at least one Visual Object with a MapKey (race binding)."""
    if not lsx.contains_equipment(record.node):
        return False
    return any(lsx.visual_object_map_key(obj) for obj in lsx.visual_object_nodes(record.node))


def _read_root_templates(
    root_dirs: list[Path],
    label: str,
    source_path: Path,
    priority_index: int,
    warnings: list[str],
    template_id_filter: frozenset[str] | None,
) -> list[RootTemplateRecord]:
    records: list[RootTemplateRecord] = []
    for root_dir in root_dirs:
        for lsx_path in sorted(root_dir.rglob("*.lsx")):
            try:
                root = lsx.load_root(lsx_path)
            except Exception as exc:  # noqa: BLE001 - report malformed user data without hiding the path.
                warnings.append(f"Could not read root template file {lsx_path}: {exc}")
                continue
            for game_object in lsx.find_item_game_objects(root):
                template_id = lsx.game_object_map_key(game_object)
                if not template_id:
                    warnings.append(f"Skipped item without MapKey in {lsx_path}")
                    continue
                if template_id_filter is not None and template_id not in template_id_filter:
                    continue
                records.append(
                    RootTemplateRecord(
                        template_id=template_id,
                        source_label=label,
                        source_path=source_path,
                        priority_index=priority_index,
                        node=game_object,
                    )
                )
    return records


def _contains_path(paths: list[Path], candidate: Path) -> bool:
    try:
        resolved = candidate.resolve()
    except OSError:
        resolved = candidate
    for path in paths:
        try:
            if path.resolve() == resolved:
                return True
        except OSError:
            if path == candidate:
                return True
    return False
