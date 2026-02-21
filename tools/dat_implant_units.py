"""
将「源」数据模组中指定区间的单位植入「目标」数据模组中的指定起始位置。

使用 genieutils-py：https://github.com/SiegeEngineers/genieutils-py
可从项目根目录运行：python tools/dat_implant_units.py 或由 mod_sync_to_official 调用。
"""

import sys
import copy
from pathlib import Path
from typing import Union

_ROOT = Path(__file__).resolve().parent.parent
_genie = _ROOT / "genieutils-py" / "src"
if _genie.exists() and str(_genie) not in sys.path:
    sys.path.insert(0, str(_genie))

from genieutils.datfile import DatFile
from genieutils.unitheaders import UnitHeaders


def _parse_if_path(dat: Union[str, Path, DatFile]) -> DatFile:
    """路径则解析一次，已是 DatFile 则直接返回（避免重复 parse）。"""
    if isinstance(dat, (str, Path)):
        return DatFile.parse(dat)
    return dat


def _blank_unit_header() -> UnitHeaders:
    """创建一个空白单位头（exists=0，用于占位）。"""
    return UnitHeaders(exists=0, task_list=None)


def _ensure_length(lst: list, length: int, blank_fill):
    """将列表扩展到 length，不足部分用 blank_fill 填充。"""
    while len(lst) < length:
        lst.append(blank_fill)


def _is_blank_header(h: UnitHeaders) -> bool:
    return h is None or (getattr(h, "exists", 1) == 0)


def implant_units_from_dat(
    source_dat_path: str | Path | DatFile,
    target_dat_path: str | Path | DatFile,
    output_path: str | Path | None,
    source_start: int,
    source_end: int | None = None,
    count: int | None = None,
    target_start: int = 0,
    *,
    warn_overwrite: bool = True,
    copy_extra_civs_from_first: bool = True,
) -> int:
    """
    将源 dat 中 [source_start, source_end] 或 [source_start, source_start+count) 的单位
    复制到目标 dat 的 [target_start, target_start+植入数量)，并保存到 output_path。

    Args:
        source_dat_path: 源模组 dat 路径或已解析的 DatFile（避免重复 parse）
        target_dat_path: 目标 dat 路径或已解析的 DatFile（将被原地修改）
        output_path: 输出路径；为 None 时不写入磁盘（由调用方在流程结束时统一 save）
        source_start: 源单位段起始 ID（含）
        source_end: 源单位段结束 ID（含）；与 count 二选一
        count: 要植入的单位数量；与 source_end 二选一，若都给出则优先 count
        target_start: 目标模组中植入的起始 ID
        warn_overwrite: 是否在覆盖非空白单位时打印提醒
        copy_extra_civs_from_first: 当目标文明数多于源时，是否用源文明 0 的同槽位单位填充多出的文明（与 AGE 同步行为一致）

    Returns:
        实际植入的单位数量

    说明：
        - 只写入目标槽位 [target_start, target_start+implant_count)，绝不写入源区间；例如 2606→3206 时只写 3206，目标里已有的 2606 不会被覆盖。
        - 植入前会在拷贝上把 .id 与 copy_id/base_id 等全部改为目标 ID，再 plug 到目标槽位。
        - 若 target_start 大于目标当前单位数量，会先扩展目标（空白）至 target_start 再写入。
    """
    source_data = _parse_if_path(source_dat_path)
    target_data = _parse_if_path(target_dat_path)
    output_path = Path(output_path) if output_path is not None else None

    # 单位槽位数以「每个文明的 units」为准，与 AGE 显示一致；无文明时退化为 unit_headers
    n_source = len(source_data.civs[0].units) if source_data.civs else len(source_data.unit_headers)
    if source_start >= n_source:
        raise ValueError(f"源模组单位总数 {n_source}，source_start={source_start} 越界")

    if count is not None:
        implant_count = min(count, n_source - source_start)
    elif source_end is not None:
        if source_end < source_start:
            raise ValueError(f"source_end={source_end} 不能小于 source_start={source_start}")
        if source_end >= n_source:
            raise ValueError(
                f"source_end={source_end} 越界：源模组单位 ID 范围为 [0, {n_source - 1}]，请改用 source_end<{n_source} 或 count 指定数量"
            )
        implant_count = source_end - source_start + 1
    else:
        implant_count = n_source - source_start

    if implant_count <= 0:
        raise ValueError("植入数量为 0，请检查 source_start / source_end / count")

    n_target_before = len(target_data.civs[0].units) if target_data.civs else len(target_data.unit_headers)
    need_len = target_start + implant_count
    if need_len > n_target_before:
        print(f"[植入前] 目标当前单位数 {n_target_before}，将扩展至 {need_len}（补 {need_len - n_target_before} 个空白）再写入")
    print(f"[植入前] 源 ID [{source_start}..{source_start + implant_count - 1}] 共 {implant_count} 个 -> 目标 ID [{target_start}..{target_start + implant_count - 1}]")

    # 1) 扩展目标 unit_headers（与 civ.units 保持同长，写入时 dat 格式要求一致）
    _ensure_length(target_data.unit_headers, need_len, _blank_unit_header())

    # 2) 扩展每个文明的 units
    for civ in target_data.civs:
        while len(civ.units) < need_len:
            civ.units.append(None)

    # 3) 收集将被覆盖的非空白槽位并提醒（每个槽位只提醒一次）
    overwritten_indices: set[int] = set()
    for i in range(implant_count):
        idx = target_start + i
        if idx >= len(target_data.unit_headers):
            continue
        if not _is_blank_header(target_data.unit_headers[idx]):
            overwritten_indices.add(idx)
            continue
        for civ in target_data.civs:
            if idx < len(civ.units) and civ.units[idx] is not None:
                overwritten_indices.add(idx)
                break

    if overwritten_indices and warn_overwrite:
        print(f"[提醒] 以下目标槽位原有非空白单位，将被覆盖: {sorted(overwritten_indices)}")

    # 4) 先在本单位数据内把源 ID 全部改为目标 ID，再写入目标槽位（只写 target_start..，绝不覆盖目标已有 2606 等）
    #    顺序：拷贝 → 在拷贝上 .id=tgt_idx 且 copy_id/base_id 等 26xx→32xx → 再 plug 到 tgt_idx
    n_source_civs = len(source_data.civs)
    n_target_civs = len(target_data.civs)
    n_source_headers = len(source_data.unit_headers)
    id_mapping = {source_start + j: target_start + j for j in range(implant_count)}

    for i in range(implant_count):
        src_idx = source_start + i
        tgt_idx = target_start + i

        if src_idx < n_source_headers:
            target_data.unit_headers[tgt_idx] = copy.deepcopy(source_data.unit_headers[src_idx])
        else:
            target_data.unit_headers[tgt_idx] = _blank_unit_header()

        for c in range(n_target_civs):
            if c < n_source_civs and src_idx < len(source_data.civs[c].units):
                u = source_data.civs[c].units[src_idx]
            else:
                u = source_data.civs[0].units[src_idx] if (copy_extra_civs_from_first and n_source_civs > 0 and src_idx < len(source_data.civs[0].units)) else None
            if u is not None:
                clone = copy.deepcopy(u)
                if hasattr(clone, "id"):
                    clone.id = tgt_idx
                _remap_unit_id_refs_in_unit(clone, id_mapping)
                target_data.civs[c].units[tgt_idx] = clone
            else:
                target_data.civs[c].units[tgt_idx] = None

    if output_path is not None:
        target_data.save(output_path)
    return implant_count


def _remap_unit_id_refs_in_unit(unit, id_mapping: dict[int, int]) -> int:
    """
    对单个 Unit 内所有「单位 ID」类引用做重映射（copy_id, base_id, dead_unit_id, blood_unit_id,
    building 的 stack_unit_id/head_unit/transform_unit/pile_unit/annexes[].unit_id,
    projectile.projectile_unit_id, dead_fish.tracking_unit, creatable.train_locations[].unit_id）。
    返回该单位内重映射的总次数。
    """
    n = 0

    def do(v):
        if isinstance(v, int) and v in id_mapping:
            return id_mapping[v], 1
        return v, 0

    for attr in ("copy_id", "base_id", "dead_unit_id", "blood_unit_id"):
        if not hasattr(unit, attr):
            continue
        val = getattr(unit, attr)
        new_val, c = do(val)
        if c:
            setattr(unit, attr, new_val)
            n += c

    building = getattr(unit, "building", None)
    if building is not None:
        for attr in ("stack_unit_id", "head_unit", "transform_unit", "pile_unit"):
            if hasattr(building, attr):
                val = getattr(building, attr)
                new_val, c = do(val)
                if c:
                    setattr(building, attr, new_val)
                    n += c
        annexes = getattr(building, "annexes", None)
        if annexes is not None:
            for annex in annexes:
                if annex is not None and hasattr(annex, "unit_id"):
                    val = getattr(annex, "unit_id", None)
                    new_val, c = do(val)
                    if c:
                        annex.unit_id = new_val
                        n += c

    projectile = getattr(unit, "projectile", None)
    if projectile is not None and hasattr(projectile, "projectile_unit_id"):
        val = getattr(projectile, "projectile_unit_id", None)
        new_val, c = do(val)
        if c:
            projectile.projectile_unit_id = new_val
            n += c

    dead_fish = getattr(unit, "dead_fish", None)
    if dead_fish is not None and hasattr(dead_fish, "tracking_unit"):
        val = getattr(dead_fish, "tracking_unit", None)
        new_val, c = do(val)
        if c:
            dead_fish.tracking_unit = new_val
            n += c

    creatable = getattr(unit, "creatable", None)
    if creatable is not None:
        train_locations = getattr(creatable, "train_locations", None)
        if train_locations is not None:
            for tl in train_locations:
                if tl is not None and hasattr(tl, "unit_id"):
                    val = getattr(tl, "unit_id", None)
                    new_val, c = do(val)
                    if c:
                        tl.unit_id = new_val
                        n += c
    return n


def _remap_unit_copy_base_in_range(
    target_data: DatFile,
    *,
    target_start: int,
    implant_count: int,
    source_start: int,
) -> int:
    """
    对 target_data 中单位 ID 在 [target_start, target_start+implant_count) 内的单位，
    将其内所有单位 ID 引用（copy_id/base_id/dead_unit_id/...）若落在 [source_start, source_start+implant_count) 则改为目标 ID。
    返回重映射总次数。
    """
    id_mapping = {source_start + i: target_start + i for i in range(implant_count)}
    total = 0
    for civ in target_data.civs:
        units = civ.units
        for i in range(target_start, min(target_start + implant_count, len(units))):
            u = units[i] if i < len(units) else None
            if u is not None:
                total += _remap_unit_id_refs_in_unit(u, id_mapping)
    if total:
        print(f"[单位 ID 引用重映射] 植入区间内共 {total} 处（copy_id/base_id/dead_unit_id/...）")
    return total


def fix_implanted_unit_self_ids(
    target_data: DatFile,
    unit_indices: set[int] | range,
) -> int:
    """
    将指定槽位的单位的 Unit.id 设为槽位下标（自身 ID 与槽位一致）。
    植入后若未在拷贝时修正，会残留源 ID（如 3206 槽位里 id=2606），导致游戏崩溃。
    返回修正的单位数。
    """
    indices = set(unit_indices)
    n = 0
    for civ in target_data.civs:
        units = civ.units or []
        for i in indices:
            if i < len(units) and units[i] is not None and hasattr(units[i], "id"):
                if getattr(units[i], "id", None) != i:
                    units[i].id = i
                    n += 1
    if n:
        print(f"[单位 .id 修正] 共 {n} 个单位的自身 id 已与槽位对齐")
    return n


def remap_unit_copy_base_ids_global(
    target_data: DatFile,
    id_mapping: dict[int, int],
) -> int:
    """
    对 target_data 中「所有」单位做同一检查：单位内所有单位 ID 引用（copy_id, base_id, dead_unit_id, blood_unit_id,
    building/projectile/dead_fish/creatable 内相关字段）若在 id_mapping 的 key 中则改为 value。
    返回重映射总次数。
    """
    total = 0
    for civ in target_data.civs:
        for u in civ.units or []:
            if u is not None:
                total += _remap_unit_id_refs_in_unit(u, id_mapping)
    if total:
        print(f"[单位 ID 引用全局重映射] 共 {total} 处（含 46/557 等对 26xx 的引用）")
    return total


def finalize_unit_id_migration(
    target_data: DatFile,
    id_mapping: dict[int, int],
    implanted_indices: set[int] | range,
) -> tuple[int, int]:
    """
    植入完成后统一收尾：先对齐植入单位的自身 ID（Unit.id = 槽位），再全局重映射 copy_id/base_id 等。
    调用方在完成所有 implant_units_from_dat 后调用一次即可。
    返回 (修正的 .id 数, 重映射的引用数)。
    """
    n_id = fix_implanted_unit_self_ids(target_data, implanted_indices)
    n_refs = remap_unit_copy_base_ids_global(target_data, id_mapping)
    return n_id, n_refs


def check_unit_id_coherence(
    data: DatFile,
    implanted_indices: set[int] | range,
    migrated_old_ids: set[int],
) -> list[tuple[int, int, str, int, str]]:
    """
    检查植入后单位 ID 属性是否自洽：植入槽位的 unit.id 应与槽位一致；
    植入槽位内不应再出现对 migrated_old_ids（如 26xx）的引用。
    返回 [(unit_index, civ_index, field_path, bad_value, message), ...]。
    """
    indices = set(implanted_indices)
    issues = []
    for civ_idx, civ in enumerate(data.civs):
        units = civ.units or []
        for ui in indices:
            if ui >= len(units) or units[ui] is None:
                continue
            u = units[ui]
            if hasattr(u, "id"):
                vid = getattr(u, "id", None)
                if isinstance(vid, int) and vid != ui:
                    issues.append((ui, civ_idx, "id", vid, f"单位[{ui}] 文明{civ_idx} .id={vid}，应为 {ui}"))
            for path, val in _iter_unit_id_refs_for_check(u):
                if isinstance(val, int) and val in migrated_old_ids:
                    issues.append((ui, civ_idx, path, val, f"单位[{ui}] 文明{civ_idx} {path}={val}，已迁移区间不应再引用"))
    return issues


def _iter_unit_id_refs_for_check(unit) -> list[tuple[str, int]]:
    """与 _remap_unit_id_refs_in_unit 同构：列出所有单位 ID 类字段的 (path, value)。"""
    out = []
    if unit is None:
        return out
    for attr in ("copy_id", "base_id", "dead_unit_id", "blood_unit_id"):
        if hasattr(unit, attr):
            v = getattr(unit, attr, None)
            if isinstance(v, int):
                out.append((attr, v))
    building = getattr(unit, "building", None)
    if building is not None:
        for attr in ("stack_unit_id", "head_unit", "transform_unit", "pile_unit"):
            if hasattr(building, attr):
                v = getattr(building, attr, None)
                if isinstance(v, int):
                    out.append((f"building.{attr}", v))
        for i, annex in enumerate(getattr(building, "annexes", None) or []):
            if annex is not None and hasattr(annex, "unit_id"):
                v = getattr(annex, "unit_id", None)
                if isinstance(v, int):
                    out.append((f"building.annexes[{i}].unit_id", v))
    for sub, attr, key in [
        (getattr(unit, "projectile", None), "projectile_unit_id", "projectile.projectile_unit_id"),
        (getattr(unit, "dead_fish", None), "tracking_unit", "dead_fish.tracking_unit"),
    ]:
        if sub is not None and hasattr(sub, attr):
            v = getattr(sub, attr, None)
            if isinstance(v, int):
                out.append((key, v))
    creatable = getattr(unit, "creatable", None)
    if creatable is not None:
        for i, tl in enumerate(getattr(creatable, "train_locations", None) or []):
            if tl is not None and hasattr(tl, "unit_id"):
                v = getattr(tl, "unit_id", None)
                if isinstance(v, int):
                    out.append((f"creatable.train_locations[{i}].unit_id", v))
    return out


# ============ 使用示例（从项目根运行：python tools/dat_implant_units.py）============
if __name__ == "__main__":
    _dat = Path("resources") / "_common" / "dat"
    source_dat = _ROOT / "Source" / _dat / "empires2_x2_p1.dat"
    target_dat = _ROOT / "Target" / _dat / "empires2_x2_p1.dat"
    output_dat = _ROOT / "Output" / _dat / "empires2_x2_p1_implanted.dat"

    SOURCE_START = 2600
    SOURCE_END = 2650     # 含 2650，共 51 个单位；也可用 count=51 代替
    TARGET_START = 2800   # 植入到目标从 2800 开始

    n = implant_units_from_dat(
        source_dat,
        target_dat,
        output_dat,
        source_start=SOURCE_START,
        source_end=SOURCE_END,   # 或 count=51
        target_start=TARGET_START,
        warn_overwrite=True,
    )
    print(f"已从源模组植入 {n} 个单位 (ID {SOURCE_START}..{SOURCE_START + n - 1}) -> 目标 ID {TARGET_START}..{TARGET_START + n - 1}")
    print(f"已保存: {output_dat}")
