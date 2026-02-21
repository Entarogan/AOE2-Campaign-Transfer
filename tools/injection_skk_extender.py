# -*- coding: utf-8 -*-
"""
injection_skk.json 按 pattern 自动扩展（独立脚本，非每次主流程执行）。

按类型与起止下标扩展 Materials 与 AtlasTextures；支持不同 atlas、不同 filename 规则；
纹理坐标默认从指定 ref 下标复制（如 800）。

示例：
  # 扩展 Tech 500-509 -> 500-520，Unit 800-842 -> 800-999
  python injection_skk_extender.py injection_skk.json -o injection_skk.json ^
    --tech 500-520 --tech-atlas ingametechs --tech-filename "textures/ingame/techs/{idx}_tech.dds" ^
    --unit 800-999 --unit-atlas ingameunits --unit-filename "textures/ingame/units/{idx}_50730.dds" --unit-suffix 50730 ^
    --ref-index 800
"""
import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


def _ensure_key(d: dict, path: List[str], default_factory):
    cur = d
    for p in path[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]
    key = path[-1]
    if key not in cur or not isinstance(cur[key], list):
        cur[key] = default_factory()
    return cur[key]


def _find_texture_by_ref(textures: List[Dict], ref_name: str) -> Dict | None:
    for t in textures:
        if t.get("RefName") == ref_name:
            return t
    return None


def _find_atlas(data: Dict, atlas_name: str) -> Dict | None:
    for entry in data.get("AtlasTextures") or []:
        if (entry.get("AtlasDef") or {}).get("Name") == atlas_name:
            return entry
    return None


def _material_def(name: str, atlas_ref: str) -> Dict:
    return {
        "MaterialDef": {
            "Name": name,
            "Type": "Atlas",
            "Blend": "AlphaPlayerColor",
            "TextureRef": name,
            "AtlasRef": atlas_ref,
        }
    }


def _texture_entry(ref_name: str, file_name: str, image_tlx: str, image_tly: str, image_brx: str, image_bry: str) -> Dict:
    return {
        "RefName": ref_name,
        "FileName": file_name,
        "imageTLX": image_tlx,
        "imageTLY": image_tly,
        "imageBRX": image_brx,
        "imageBRY": image_bry,
    }


def extend_skk(
    data: Dict[str, Any],
    *,
    tech_start: int | None = None,
    tech_end: int | None = None,
    tech_atlas: str = "ingametechs",
    tech_filename: str = "textures/ingame/techs/{idx}_tech.dds",
    tech_ref_index: int | None = None,
    unit_start: int | None = None,
    unit_end: int | None = None,
    unit_atlas: str = "ingameunits",
    unit_filename: str = "textures/ingame/units/{idx}_50730.dds",
    unit_suffix: str = "50730",
    unit_ref_index: int | None = 800,
    building_start: int | None = None,
    building_end: int | None = None,
    building_atlas: str = "ingamebuildings",
    building_filename: str = "textures/ingame/buildings/{idx}_building.dds",
    building_ref_index: int | None = None,
    pad: int = 3,
) -> Dict[str, Any]:
    """
    原地扩展 data 的 Materials 与 AtlasTextures。
    *_ref_index：从该下标的已有纹理复制 imageTLX/TLY/BRX/BRY；None 则用该 atlas 下第一条。
    返回统计 report。
    """
    report: Dict[str, Any] = {"Materials": {"Tech": 0, "Unit": 0, "Building": 0}, "Textures": {}, "skipped_existing": {"Materials": 0, "Textures": 0}}
    materials = data.setdefault("Materials", [])
    if "AtlasTextures" not in data or not isinstance(data["AtlasTextures"], list):
        data["AtlasTextures"] = []

    # 已有条目：仅追加缺失的，使默认范围下执行不改变文件
    existing_material_names: set[str] = set()
    for m in materials:
        name = (m.get("MaterialDef") or {}).get("Name")
        if name:
            existing_material_names.add(name)
    existing_ref_by_atlas: Dict[str, set[str]] = {}
    for entry in data.get("AtlasTextures") or []:
        atlas_name = (entry.get("AtlasDef") or {}).get("Name")
        if not atlas_name:
            continue
        existing_ref_by_atlas.setdefault(atlas_name, set())
        for t in (entry.get("AtlasDef") or {}).get("Textures") or []:
            ref = t.get("RefName")
            if ref:
                existing_ref_by_atlas[atlas_name].add(ref)

    def get_ref_coords(atlas_name: str, ref_name: str) -> tuple[str, str, str, str]:
        entry = _find_atlas(data, atlas_name)
        if not entry:
            return "0.000078", "0.961614", "0.039922", "0.999925"
        textures = (entry.get("AtlasDef") or {}).get("Textures") or []
        t = _find_texture_by_ref(textures, ref_name)
        if not t:
            t = textures[0] if textures else None
        if not t:
            return "0.000078", "0.961614", "0.039922", "0.999925"
        return (
            str(t.get("imageTLX", "0.000078")),
            str(t.get("imageTLY", "0.961614")),
            str(t.get("imageBRX", "0.039922")),
            str(t.get("imageBRY", "0.999925")),
        )

    def ensure_atlas(atlas_name: str) -> Dict:
        entry = _find_atlas(data, atlas_name)
        if entry is None:
            entry = {"AtlasDef": {"Name": atlas_name, "Textures": []}}
            data["AtlasTextures"].append(entry)
        if "Textures" not in (entry.get("AtlasDef") or {}):
            (entry.setdefault("AtlasDef", {}))["Textures"] = []
        return entry["AtlasDef"]["Textures"]

    def zkey(i: int) -> str:
        return str(i).zfill(pad)

    # ----- Tech -----
    if tech_start is not None and tech_end is not None and tech_end >= tech_start:
        ref_name = f"TechIconsT{zkey(tech_ref_index if tech_ref_index is not None else tech_start)}"
        tlx, tly, brx, bry = get_ref_coords(tech_atlas, ref_name)
        textures = ensure_atlas(tech_atlas)
        ref_set = existing_ref_by_atlas.setdefault(tech_atlas, set())
        for i in range(tech_start, tech_end + 1):
            k = zkey(i)
            name = f"TechIconsT{k}"
            if name not in existing_material_names:
                materials.append(_material_def(name, tech_atlas))
                existing_material_names.add(name)
                report["Materials"]["Tech"] += 1
            else:
                report["skipped_existing"]["Materials"] += 1
            if name not in ref_set:
                textures.append(_texture_entry(name, tech_filename.format(idx=i), tlx, tly, brx, bry))
                ref_set.add(name)
                report["Textures"][tech_atlas] = report["Textures"].get(tech_atlas, 0) + 1
            else:
                report["skipped_existing"]["Textures"] += 1

    # ----- Unit -----
    if unit_start is not None and unit_end is not None and unit_end >= unit_start:
        ref_name = f"UnitIcons{zkey(unit_ref_index if unit_ref_index is not None else unit_start)}{unit_suffix}"
        tlx, tly, brx, bry = get_ref_coords(unit_atlas, ref_name)
        textures = ensure_atlas(unit_atlas)
        ref_set = existing_ref_by_atlas.setdefault(unit_atlas, set())
        for i in range(unit_start, unit_end + 1):
            k = zkey(i)
            name = f"UnitIcons{k}{unit_suffix}"
            if name not in existing_material_names:
                materials.append(_material_def(name, unit_atlas))
                existing_material_names.add(name)
                report["Materials"]["Unit"] += 1
            else:
                report["skipped_existing"]["Materials"] += 1
            if name not in ref_set:
                textures.append(_texture_entry(name, unit_filename.format(idx=i), tlx, tly, brx, bry))
                ref_set.add(name)
                report["Textures"][unit_atlas] = report["Textures"].get(unit_atlas, 0) + 1
            else:
                report["skipped_existing"]["Textures"] += 1

    # ----- Building -----
    if building_start is not None and building_end is not None and building_end >= building_start:
        ref_name = f"BuildingIcons{zkey(building_ref_index if building_ref_index is not None else building_start)}"
        tlx, tly, brx, bry = get_ref_coords(building_atlas, ref_name)
        textures = ensure_atlas(building_atlas)
        ref_set = existing_ref_by_atlas.setdefault(building_atlas, set())
        for i in range(building_start, building_end + 1):
            k = zkey(i)
            name = f"BuildingIcons{k}"
            if name not in existing_material_names:
                materials.append(_material_def(name, building_atlas))
                existing_material_names.add(name)
                report["Materials"]["Building"] += 1
            else:
                report["skipped_existing"]["Materials"] += 1
            if name not in ref_set:
                textures.append(_texture_entry(name, building_filename.format(idx=i), tlx, tly, brx, bry))
                ref_set.add(name)
                report["Textures"][building_atlas] = report["Textures"].get(building_atlas, 0) + 1
            else:
                report["skipped_existing"]["Textures"] += 1

    return report


def _parse_range(s: str) -> tuple[int, int]:
    a, _, b = s.partition("-")
    return int(a.strip()), int(b.strip()) if b else int(a.strip())


def main(argv=None):
    ap = argparse.ArgumentParser(description="按 pattern 扩展 injection_skk.json（Materials + AtlasTextures）。")
    ap.add_argument("input_json", help="injection_skk.json 路径")
    ap.add_argument("-o", "--out", default=None, help="输出路径（默认覆盖输入）")
    ap.add_argument("--pad", type=int, default=3, help="数字键零填充宽度（默认 3）")

    g_tech = ap.add_argument_group("Tech")
    g_tech.add_argument("--tech", metavar="START-END", default="500-509", help="默认与现有 JSON 一致，执行后无变化；例: 500-520")
    g_tech.add_argument("--tech-atlas", default="ingametechs")
    g_tech.add_argument("--tech-filename", default="textures/ingame/techs/{idx}_tech.dds", help="{idx} 为下标")
    g_tech.add_argument("--tech-ref-index", type=int, default=None, help="复制坐标的参考下标（默认用 start）")

    g_unit = ap.add_argument_group("Unit")
    g_unit.add_argument("--unit", metavar="START-END", default="800-853", help="单位图标范围；例: 800-999")
    g_unit.add_argument("--unit-atlas", default="ingameunits")
    g_unit.add_argument("--unit-filename", default="textures/ingame/units/{idx}_50730.dds", help="{idx} 为下标")
    g_unit.add_argument("--unit-suffix", default="50730")
    g_unit.add_argument("--unit-ref-index", type=int, default=800, help="复制坐标的参考下标（默认 800）")

    g_building = ap.add_argument_group("Building")
    g_building.add_argument("--building", metavar="START-END")
    g_building.add_argument("--building-atlas", default="ingamebuildings")
    g_building.add_argument("--building-filename", default="textures/ingame/buildings/{idx}_building.dds")
    g_building.add_argument("--building-ref-index", type=int, default=None)

    args = ap.parse_args(argv)

    input_path = Path(args.input_json)
    output_path = Path(args.out) if args.out else input_path

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    tech_start = tech_end = unit_start = unit_end = building_start = building_end = None
    if args.tech is not None:
        tech_start, tech_end = _parse_range(args.tech)
    if args.unit is not None:
        unit_start, unit_end = _parse_range(args.unit)
    if args.building is not None:
        building_start, building_end = _parse_range(args.building)

    report = extend_skk(
        data,
        tech_start=tech_start, tech_end=tech_end,
        tech_atlas=args.tech_atlas, tech_filename=args.tech_filename, tech_ref_index=args.tech_ref_index,
        unit_start=unit_start, unit_end=unit_end,
        unit_atlas=args.unit_atlas, unit_filename=args.unit_filename, unit_suffix=args.unit_suffix, unit_ref_index=args.unit_ref_index,
        building_start=building_start, building_end=building_end,
        building_atlas=args.building_atlas, building_filename=args.building_filename, building_ref_index=args.building_ref_index,
        pad=args.pad,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(json.dumps({"output": str(output_path), "report": report}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
