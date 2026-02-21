"""
用 genieutils 解析 dat 后，递归遍历所有字段，找出值等于指定数值（默认 2606）的字段路径。
便于精确定位「漏迁移」或导致崩溃的残留引用。

用法（在项目根目录执行）：
  python debug/debug_dat_genie_grep_value.py [dat路径] [数值]
  python -m debug.debug_dat_genie_grep_value [dat路径] [数值]
  默认：Output/resources/_common/dat/empires2_x2_p1.dat  2606
"""

import dataclasses
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_clone_genie = _ROOT / "genieutils-py" / "src"
if _clone_genie.exists() and str(_clone_genie) not in sys.path:
    sys.path.insert(0, str(_clone_genie))

from genieutils.datfile import DatFile


def _is_int_or_float(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _walk_and_find_value(obj, target_value: int, path: str, visited: set[int]) -> list[tuple[str, int | float]]:
    """
    递归遍历 dataclass/list/tuple，收集所有值等于 target_value 的 (路径, 值)。
    visited 用 id() 避免循环引用导致死递归。
    """
    out = []
    if obj is None:
        return out
    oid = id(obj)
    if oid in visited:
        return out
    visited.add(oid)

    try:
        if _is_int_or_float(obj):
            if int(obj) == target_value:
                out.append((path, obj))
            return out
        if isinstance(obj, (list, tuple)):
            for i, item in enumerate(obj):
                out.extend(_walk_and_find_value(item, target_value, f"{path}[{i}]", visited))
            return out
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            for f in dataclasses.fields(obj):
                try:
                    val = getattr(obj, f.name)
                except (AttributeError, TypeError, ValueError) as e:
                    continue
                sub_path = f"{path}.{f.name}" if path else f.name
                out.extend(_walk_and_find_value(val, target_value, sub_path, visited))
            return out
        # 其他类型（str, bytes, enum 等）不递归
        return out
    finally:
        visited.discard(oid)


def collect_value_paths(dat_path: Path, target_value: int) -> list[tuple[str, int | float]]:
    """解析 dat 并返回所有值等于 target_value 的 (路径, 值)。"""
    data = DatFile.parse(dat_path)
    visited = set()
    return _walk_and_find_value(data, target_value, "DatFile", visited)


def main() -> None:
    default_dat = _ROOT / "Output" / "resources" / "_common" / "dat" / "empires2_x2_p1.dat"

    argv = sys.argv[1:]
    dat_path = Path(argv[0]) if argv else default_dat
    value = int(argv[1]) if len(argv) > 1 else 2606

    if not dat_path.exists():
        print(f"文件不存在: {dat_path}")
        sys.exit(1)

    print(f"解析: {dat_path}")
    print(f"搜索数值: {value}（genieutils 递归遍历所有字段）")
    print()

    results = collect_value_paths(dat_path, value)

    print(f"========== 所有出现 {value} 的字段（共 {len(results)} 处）==========")
    for path, val in sorted(results, key=lambda x: (x[0], x[1])):
        print(f"  {path} = {val}")

    if not results:
        print("  （无）")


if __name__ == "__main__":
    main()
