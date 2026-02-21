# -*- coding: utf-8 -*-
"""
AoE2DE materials.json 注入：将 mod（如 injection_skk.json）的 Materials + 全部 AtlasTextures 合并进 base（官方）。
可配置路径，供 mod_sync_to_official 主流程调用；也可独立运行（argparse）。
"""
import json
import argparse
import sys
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

def get_nested(d, path):
    cur = d
    for pth in path:
        if isinstance(cur, dict) and pth in cur:
            cur = cur[pth]
        else:
            return None
    return cur

def set_nested(d, path, value):
    cur = d
    for pth in path[:-1]:
        if pth not in cur or not isinstance(cur[pth], dict):
            cur[pth] = {}
        cur = cur[pth]
    cur[path[-1]] = value

def index_by_unique(items, subpath):
    idx = {}
    for i, item in enumerate(items):
        key = get_nested(item, subpath)
        if key is not None:
            idx[str(key)] = i
    return idx

def merge_array(base_items, mod_items, unique_path, override, prefix=""):
    report = {"injected": [], "overridden": [], "skipped_dupes": [], "missing_key": []}
    base_index = index_by_unique(base_items, unique_path)
    out = list(base_items)
    for mod_item in mod_items:
        key = get_nested(mod_item, unique_path)
        if key is None:
            report["missing_key"].append(json.dumps(mod_item, ensure_ascii=False)[:160] + " ...")
            continue
        key = str(key)
        if prefix and not key.startswith(prefix):
            set_nested(mod_item, unique_path, prefix + key)
            key = prefix + key
        if key in base_index:
            if override:
                out[base_index[key]] = mod_item
                report["overridden"].append(key)
            else:
                report["skipped_dupes"].append(key)
        else:
            out.append(mod_item)
            report["injected"].append(key)
    return out, report

def merge_materials(base, mod, override, prefix):
    if "Materials" not in base or not isinstance(base["Materials"], list):
        raise SystemExit("[ERROR] Base JSON missing 'Materials' array")
    if "Materials" not in mod or not isinstance(mod["Materials"], list):
        return {"injected": [], "overridden": [], "skipped_dupes": [], "missing_key": []}
    merged, rep = merge_array(base["Materials"], mod["Materials"], ["MaterialDef","Name"], override, prefix)
    base["Materials"] = merged
    return rep

def merge_all_atlases(base, mod, override, prefix, fallback_atlas_name=None):
    if "AtlasTextures" not in base or not isinstance(base["AtlasTextures"], list):
        raise SystemExit("[ERROR] Base JSON missing 'AtlasTextures' array")
    reports = {}
    if "AtlasTextures" in mod and isinstance(mod["AtlasTextures"], list) and len(mod["AtlasTextures"]) > 0:
        for entry in mod["AtlasTextures"]:
            atlas_name = get_nested(entry, ["AtlasDef","Name"])
            textures = get_nested(entry, ["AtlasDef","Textures"])
            if not atlas_name or not isinstance(textures, list):
                continue
            base_entry = None
            for e in base["AtlasTextures"]:
                if get_nested(e, ["AtlasDef","Name"]) == atlas_name:
                    base_entry = e
                    break
            if base_entry is None:
                reports[atlas_name or "UNKNOWN"] = {"error": "atlas_not_found_in_base"}
                continue
            base_textures = get_nested(base_entry, ["AtlasDef","Textures"])
            if not isinstance(base_textures, list):
                reports[atlas_name] = {"error": "base_atlas_missing_textures"}
                continue
            merged, rep = merge_array(base_textures, textures, ["RefName"], override, prefix)
            base_entry["AtlasDef"]["Textures"] = merged
            reports[atlas_name] = rep
        return reports
    if "Textures" in mod and isinstance(mod["Textures"], list) and fallback_atlas_name:
        base_entry = None
        for e in base["AtlasTextures"]:
            if get_nested(e, ["AtlasDef","Name"]) == fallback_atlas_name:
                base_entry = e
                break
        if base_entry is None:
            reports[fallback_atlas_name] = {"error": "atlas_not_found_in_base"}
            return reports
        base_textures = get_nested(base_entry, ["AtlasDef","Textures"])
        merged, rep = merge_array(base_textures, mod["Textures"], ["RefName"], override, prefix)
        base_entry["AtlasDef"]["Textures"] = merged
        reports[fallback_atlas_name] = rep
        return reports
    return {"_info": "no atlas textures provided in mod JSON"}


def run_materials_inject(
    base_path: Union[str, Path],
    mod_path: Union[str, Path],
    output_path: Union[str, Path],
    *,
    override: bool = False,
    prefix: str = "",
    fallback_atlas_name: str | None = None,
    pretty: bool = True,
) -> Dict[str, Any]:
    """
    将 mod（如 injection_skk.json）合并进 base materials.json，写入 output_path。
    返回 report（materials + atlases）。
    """
    base_path = Path(base_path)
    mod_path = Path(mod_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(base_path, "r", encoding="utf-8") as f:
        base = json.load(f)
    with open(mod_path, "r", encoding="utf-8") as f:
        mod = json.load(f)

    report = {
        "materials": merge_materials(base, mod, override, prefix),
        "atlases": merge_all_atlases(base, mod, override, prefix, fallback_atlas_name),
    }

    with open(output_path, "w", encoding="utf-8") as f:
        if pretty:
            json.dump(base, f, ensure_ascii=False, indent=2)
            f.write("\n")
        else:
            json.dump(base, f, ensure_ascii=False, separators=(",", ":"))
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description="AoE2DE materials.json injector: materials + ALL atlases present in the mod JSON.")
    ap.add_argument("base_json", help="官方 materials.json 路径（如 Target/widgetui/materials.json）")
    ap.add_argument("mod_json", help="要植入的 JSON 路径（如 injection_skk.json）")
    ap.add_argument("-o", "--out", default=None, help="输出路径（默认 base 同目录 -merged.json）")
    ap.add_argument("--pretty", action="store_true", default=True, help="输出格式化 JSON（默认 True）")
    ap.add_argument("--no-pretty", action="store_false", dest="pretty")
    ap.add_argument("--override", action="store_true")
    ap.add_argument("--prefix", default="", help="namespace to add to unique keys (MaterialDef.Name / RefName)")
    ap.add_argument("--atlas-name", default=None, help="(fallback) use when mod provides only top-level 'Textures'")
    args = ap.parse_args(argv)

    out_path = args.out or (str(Path(args.base_json).with_suffix("")) + "-merged.json")
    report = run_materials_inject(
        args.base_json, args.mod_json, out_path,
        override=args.override, prefix=args.prefix,
        fallback_atlas_name=args.atlas_name, pretty=args.pretty,
    )
    print(json.dumps({"output": out_path, "report": report}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
