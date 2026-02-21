# -*- coding: utf-8 -*-
"""
AoE2DE icons.json 扩展：将 Techs/Buildings/Units 三张表按范围扩展到指定最大下标。
  - Techs: key "XXX" -> "TechIconsTXXX"
  - Buildings: key "XXX" -> "None"
  - Units: key "XXX" -> "UnitIconsXXX<SUFFIX>" (默认 SUFFIX=50730)

可配置路径，供 mod_sync_to_official 主流程调用；也可独立运行（argparse）。
"""
import json
import argparse
import os
import sys
from pathlib import Path
from typing import Dict, Any, Union

def ensure_section(d: Dict[str, Any], name: str) -> Dict[str, str]:
    if name not in d or not isinstance(d[name], dict):
        d[name] = {}
    return d[name]

def zkey(i: int, pad: int) -> str:
    return str(i).zfill(pad)

def current_max_index(section: Dict[str, str], pad: int) -> int:
    max_i = -1
    for k in section.keys():
        try:
            i = int(k)
            if i > max_i: max_i = i
        except ValueError:
            # ignore non-numeric keys
            pass
    return max_i

def fill_range(section: Dict[str, str], start_i: int, end_i: int, pad: int, value_func, overwrite: bool, stats: Dict[str,int]):
    for i in range(start_i, end_i+1):
        k = zkey(i, pad)
        v_new = value_func(k)
        if k in section and not overwrite:
            stats["kept_existing"] += 1
            continue
        if k in section and overwrite:
            if section[k] != v_new:
                stats["overwritten"] += 1
            else:
                stats["no_change"] += 1
        else:
            stats["added"] += 1
        section[k] = v_new


def run_icons_extend(
    icons_path: Union[str, Path],
    output_path: Union[str, Path],
    *,
    techs_max: int | None = None,
    units_max: int | None = None,
    buildings_max: int | None = None,
    pad: int = 3,
    units_suffix: str = "50730",
    overwrite_existing: bool = False,
) -> Dict[str, Any]:
    """
    读取 icons.json，按指定范围扩展 Techs/Buildings/Units 表，写入 output_path。
    返回 report（Techs/Buildings/Units 各段的 added/overwritten/kept_existing/no_change）。
    """
    icons_path = Path(icons_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(icons_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    techs = ensure_section(data, "Techs")
    buildings = ensure_section(data, "Buildings")
    units = ensure_section(data, "Units")
    report: Dict[str, Any] = {"Techs": {}, "Buildings": {}, "Units": {}}

    if techs_max is not None:
        stats = {"added": 0, "overwritten": 0, "kept_existing": 0, "no_change": 0}
        fill_range(techs, 0, techs_max, pad, lambda k: f"TechIconsT{k}", overwrite_existing, stats)
        report["Techs"] = stats

    if buildings_max is not None:
        stats = {"added": 0, "overwritten": 0, "kept_existing": 0, "no_change": 0}
        fill_range(buildings, 0, buildings_max, pad, lambda k: "None", overwrite_existing, stats)
        report["Buildings"] = stats

    if units_max is not None:
        stats = {"added": 0, "overwritten": 0, "kept_existing": 0, "no_change": 0}
        fill_range(units, 0, units_max, pad, lambda k: f"UnitIcons{k}{units_suffix}", overwrite_existing, stats)
        report["Units"] = stats

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description="Extend AoE2DE widgetui/icons.json mappings (Techs/Buildings/Units) to specified maxima.")
    ap.add_argument("icons_json", help="Path to icons.json (base, e.g. Target/widgetui/icons.json).")
    ap.add_argument("-o", "--out", default=None, help="Output path (default: <icons_json>-ext.json)")
    ap.add_argument("--pad", type=int, default=3, help="Zero-padding width for numeric keys (default: 3).")
    ap.add_argument("--overwrite-existing", action="store_true", help="Overwrite existing keys with generated values.")
    ap.add_argument("--units-max", type=int, default=None, help="Extend 'Units' table up to this index (inclusive).")
    ap.add_argument("--techs-max", type=int, default=None, help="Extend 'Techs' table up to this index (inclusive).")
    ap.add_argument("--buildings-max", type=int, default=None, help="Extend 'Buildings' table up to this index (inclusive).")
    ap.add_argument("--units-suffix", default="50730", help="Suffix appended to Units values (default: '50730').")
    args = ap.parse_args(argv)

    out = args.out or (str(Path(args.icons_json).with_suffix("")) + "-ext.json")
    report = run_icons_extend(
        args.icons_json, out,
        techs_max=args.techs_max, units_max=args.units_max, buildings_max=args.buildings_max,
        pad=args.pad, units_suffix=args.units_suffix, overwrite_existing=args.overwrite_existing,
    )
    print(json.dumps({"output": out, "report": report}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
