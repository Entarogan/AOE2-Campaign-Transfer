"""
独立 debug 脚本：解析「输出后的」dat 文件，收集所有出现指定单位 ID（默认 2606、3206）的字段，
并检查自洽性。

重要：新 dat 中 单位[2606] 是官方新单位，我们的模组单位已迁移到 3206。
自洽性 = 仅当「迁移后的单位」（32xx 区间）内仍引用 2606 时报错（原意应为 3206）；
其他单位引用 2606 可能是合法引用官方 2606，不判为不一致。

用法（在项目根目录执行）：
  python debug/debug_dat_unit_id_refs.py [output_dat路径] [ID1] [ID2] ...
  python -m debug.debug_dat_unit_id_refs [output_dat路径] [ID1] [ID2] ...
  不传参数时默认：Output/.../empires2_x2_p1.dat，检查 2606 和 3206。
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_clone_genie = _ROOT / "genieutils-py" / "src"
if _clone_genie.exists() and str(_clone_genie) not in sys.path:
    sys.path.insert(0, str(_clone_genie))

from genieutils.datfile import DatFile


# 与 dat_implant_units 中一致：所有「单位 ID」类属性及其在 Unit 内的路径
def _iter_unit_id_refs(unit):
    """Yield (path_str, value) for each unit-ID-like attribute in unit."""
    if unit is None:
        return
    for attr in ("copy_id", "base_id", "dead_unit_id", "blood_unit_id"):
        if hasattr(unit, attr):
            val = getattr(unit, attr, None)
            if isinstance(val, int):
                yield (attr, val)
    building = getattr(unit, "building", None)
    if building is not None:
        for attr in ("stack_unit_id", "head_unit", "transform_unit", "pile_unit"):
            if hasattr(building, attr):
                val = getattr(building, attr, None)
                if isinstance(val, int):
                    yield (f"building.{attr}", val)
        annexes = getattr(building, "annexes", None)
        if annexes is not None:
            for i, annex in enumerate(annexes):
                if annex is not None and hasattr(annex, "unit_id"):
                    val = getattr(annex, "unit_id", None)
                    if isinstance(val, int):
                        yield (f"building.annexes[{i}].unit_id", val)
    projectile = getattr(unit, "projectile", None)
    if projectile is not None and hasattr(projectile, "projectile_unit_id"):
        val = getattr(projectile, "projectile_unit_id", None)
        if isinstance(val, int):
            yield ("projectile.projectile_unit_id", val)
    dead_fish = getattr(unit, "dead_fish", None)
    if dead_fish is not None and hasattr(dead_fish, "tracking_unit"):
        val = getattr(dead_fish, "tracking_unit", None)
        if isinstance(val, int):
            yield ("dead_fish.tracking_unit", val)
    creatable = getattr(unit, "creatable", None)
    if creatable is not None:
        train_locations = getattr(creatable, "train_locations", None)
        if train_locations is not None:
            for i, tl in enumerate(train_locations):
                if tl is not None and hasattr(tl, "unit_id"):
                    val = getattr(tl, "unit_id", None)
                    if isinstance(val, int):
                        yield (f"creatable.train_locations[{i}].unit_id", val)


def collect_unit_id_refs(data: DatFile, watch_ids: set[int]) -> list[tuple[int, int, str, int]]:
    """
    遍历 dat 中所有文明的单位，收集「字段值在 watch_ids 中」的 (unit_index, civ_index, path, value)。
    """
    out = []
    for civ_idx, civ in enumerate(data.civs):
        units = civ.units or []
        for unit_idx in range(len(units)):
            u = units[unit_idx] if unit_idx < len(units) else None
            for path, val in _iter_unit_id_refs(u):
                if val in watch_ids:
                    out.append((unit_idx, civ_idx, path, val))
    return out


def check_consistency(
    refs: list[tuple[int, int, str, int]],
    watch_ids: set[int],
    *,
    migrated_old: set[int] | None = None,
    unit_offset: int = 600,
    implanted_unit_start: int = 3201,
) -> tuple[list[str], list[str]]:
    """
    根据迁移规则检查自洽性。
    仅当「迁移后单位」（unit_index >= implanted_unit_start）内仍引用 migrated_old 时报错：
    新 dat 中 2606 是官方单位，只有我们的 32xx 单位引用 2606 才表示漏迁移（应为 3206）。
    """
    errors = []
    warnings = []
    if migrated_old is None:
        migrated_old = set()

    for unit_idx, civ_idx, path, val in refs:
        if unit_idx < implanted_unit_start:
            continue  # 非迁移单位引用 2606 可能是引用官方 2606，不报错
        if val in migrated_old:
            new_id = val + unit_offset
            loc = f"单位[{unit_idx}] 文明{civ_idx} {path}={val}"
            errors.append(
                f"迁移后单位 {unit_idx} 仍引用旧 ID {val}（应为 {new_id}）：{loc}"
            )
    return errors, warnings


def main() -> None:
    default_dat = _ROOT / "Output" / "resources" / "_common" / "dat" / "empires2_x2_p1.dat"

    argv = sys.argv[1:]
    dat_path = Path(argv[0]) if argv else default_dat
    watch_ids = {2606, 3206}
    if len(argv) > 1:
        watch_ids = set(int(x) for x in argv[1:])

    if not dat_path.exists():
        print(f"文件不存在: {dat_path}")
        sys.exit(1)

    print(f"解析: {dat_path}")
    print(f"检查以下单位 ID 的引用: {sorted(watch_ids)}")
    print()

    data = DatFile.parse(dat_path)
    refs = collect_unit_id_refs(data, watch_ids)

    # 按 (value, unit_idx, civ_idx, path) 分组便于阅读
    by_val = {}
    for unit_idx, civ_idx, path, val in refs:
        by_val.setdefault(val, []).append((unit_idx, civ_idx, path))

    print("========== 所有出现 2606 / 3206 的项 ==========")
    for val in sorted(by_val.keys()):
        entries = by_val[val]
        print(f"\n--- 值 = {val}（共 {len(entries)} 处）---")
        for unit_idx, civ_idx, path in sorted(entries):
            print(f"  单位[{unit_idx}] 文明{civ_idx}  {path} = {val}")

    # 自洽性：新 dat 中 2606 是官方单位，我们的单位在 3206。仅「迁移后单位」(32xx) 引用 2606 才判为漏迁移
    UNIT_OFFSET = 600
    IMPLANTED_START = 2601 + UNIT_OFFSET  # 3201
    migrated_old = watch_ids & {2606}
    errors, _ = check_consistency(
        refs, watch_ids,
        migrated_old=migrated_old,
        unit_offset=UNIT_OFFSET,
        implanted_unit_start=IMPLANTED_START,
    )

    print("\n========== 自洽性检查 ==========")
    print("说明：新 dat 中 单位[2606] 为官方单位，我们的模组单位在 3206。仅检查 32xx 单位是否仍误引用 2606。")
    if not errors:
        print("通过：未发现迁移后单位（32xx）仍引用 2606。")
    else:
        print("以下不一致（迁移后单位仍引用 2606，应已为 3206）：")
        for e in errors:
            print(f"  [不一致] {e}")

    # 额外：明确列出「单位 3206」（我们的迁移单位）的所有单位 ID 类引用
    print("\n========== 单位 3206（模组迁移单位）的所有单位 ID 类引用 ==========")
    for civ_idx, civ in enumerate(data.civs):
        units = civ.units or []
        if 3206 < len(units) and civ.units[3206] is not None:
            u = civ.units[3206]
            items = list(_iter_unit_id_refs(u))
            if not items:
                print(f"  文明{civ_idx} 单位[3206]: 无单位 ID 类字段或均为 -1/0")
            else:
                for path, val in items:
                    flag = "  [应迁移]" if val == 2606 else ""
                    print(f"  文明{civ_idx} 单位[3206]  {path} = {val}{flag}")


if __name__ == "__main__":
    main()
