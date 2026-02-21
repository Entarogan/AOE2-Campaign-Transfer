# -*- coding: utf-8 -*-
import json, argparse, sys, os
from typing import Any, Dict, List, Tuple

def get_nested(d: Dict[str, Any], path: List[str]):
    cur = d
    for p in path:
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        else:
            return None
    return cur

def set_nested(d: Dict[str, Any], path: List[str], value):
    cur = d
    for p in path[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]
    cur[path[-1]] = value

def index_by_unique(items: List[Dict[str, Any]], subpath: List[str]) -> Dict[str, int]:
    idx = {}
    for i, item in enumerate(items):
        key = get_nested(item, subpath)
        if key is not None:
            idx[str(key)] = i
    return idx

def merge_array(base_items: List[Dict[str, Any]],
                mod_items: List[Dict[str, Any]],
                unique_path: List[str],
                override: bool,
                prefix: str = "") -> Tuple[List[Dict[str, Any]], Dict[str, List[str]]]:
    report = {"injected": [], "overridden": [], "skipped_dupes": [], "missing_key": []}
    base_index = index_by_unique(base_items, unique_path)
    out = list(base_items)
    for mod_item in mod_items:
        key = get_nested(mod_item, unique_path)
        if key is None:
            report["missing_key"].append(json.dumps(mod_item, ensure_ascii=False)[:160] + " ...")
            continue
        key = str(key)
        # Optionally namespace the unique field in the object itself
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

def merge_materials(base: Dict[str, Any], mod: Dict[str, Any], override: bool, prefix: str):
    if "Materials" not in base or not isinstance(base["Materials"], list):
        raise SystemExit("[ERROR] Base JSON missing 'Materials' array")
    if "Materials" not in mod or not isinstance(mod["Materials"], list):
        raise SystemExit("[ERROR] Mod JSON missing 'Materials' array")
    merged, rep = merge_array(base["Materials"], mod["Materials"], ["MaterialDef","Name"], override, prefix)
    base["Materials"] = merged
    return rep

def merge_atlas_textures(base: Dict[str, Any], mod: Dict[str, Any],
                         atlas_name: str, override: bool, prefix: str):
    # find atlas in base
    if "AtlasTextures" not in base or not isinstance(base["AtlasTextures"], list):
        raise SystemExit("[ERROR] Base JSON missing 'AtlasTextures' array")
    # locate target atlas by AtlasDef.Name
    target_base = None
    for entry in base["AtlasTextures"]:
        if get_nested(entry, ["AtlasDef","Name"]) == atlas_name:
            target_base = entry
            break
    if target_base is None:
        raise SystemExit(f"[ERROR] Base JSON has no AtlasTextures entry with AtlasDef.Name='{atlas_name}'")
    if "AtlasDef" not in target_base or "Textures" not in target_base["AtlasDef"]:
        raise SystemExit("[ERROR] Base atlas entry missing AtlasDef.Textures")

    # For mod side: allow either a full AtlasTextures structure OR just a flat list under key 'Textures'
    mod_textures = []
    if "AtlasTextures" in mod and isinstance(mod["AtlasTextures"], list):
        for entry in mod["AtlasTextures"]:
            if get_nested(entry, ["AtlasDef","Name"]) == atlas_name:
                arr = get_nested(entry, ["AtlasDef","Textures"])
                if isinstance(arr, list):
                    mod_textures.extend(arr)
    if not mod_textures and "Textures" in mod and isinstance(mod["Textures"], list):
        mod_textures = mod["Textures"]
    if not mod_textures:
        raise SystemExit("[ERROR] Mod JSON must contain textures for the target atlas (under AtlasTextures[].AtlasDef.Textures or top-level 'Textures').")

    base_textures = target_base["AtlasDef"]["Textures"]
    merged, rep = merge_array(base_textures, mod_textures, ["RefName"], override, prefix)
    target_base["AtlasDef"]["Textures"] = merged
    return rep

def main(argv=None):
    ap = argparse.ArgumentParser(description="AoE2DE widgetui injector for materials.json (and atlas textures).")
    ap.add_argument("base_json", help="vanilla/new patch materials.json (same file also contains AtlasTextures)")
    ap.add_argument("mod_json", help="your small inject JSON (see README)")
    ap.add_argument("-o","--out", default=None)
    ap.add_argument("--pretty", action="store_true")
    ap.add_argument("--override", action="store_true")
    ap.add_argument("--prefix", default="", help="namespace to add to unique keys")
    ap.add_argument("--atlas-name", default="ingameunits", help="target atlas under AtlasTextures[].AtlasDef.Name")
    ap.add_argument("--no-materials", action="store_true", help="skip Materials[] merging")
    ap.add_argument("--no-atlas", action="store_true", help="skip AtlasTextures.Textures[] merging")
    args = ap.parse_args(argv)

    with open(args.base_json, "r", encoding="utf-8") as f:
        base = json.load(f)
    with open(args.mod_json, "r", encoding="utf-8") as f:
        mod = json.load(f)

    report = {}
    if not args.no_materials:
        report["materials"] = merge_materials(base, mod, args.override, args.prefix)
    if not args.no_atlas:
        report["atlas_textures"] = merge_atlas_textures(base, mod, args.atlas_name, args.override, args.prefix)

    out_path = args.out or (os.path.splitext(args.base_json)[0] + "-merged.json")
    with open(out_path, "w", encoding="utf-8") as f:
        if args.pretty:
            json.dump(base, f, ensure_ascii=False, indent=2)
            f.write("\n")
        else:
            json.dump(base, f, ensure_ascii=False, separators=(",",":"))
    print(json.dumps({"output": out_path, "report": report}, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
