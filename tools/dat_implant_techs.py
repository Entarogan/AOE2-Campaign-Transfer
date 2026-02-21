"""
将「源」数据模组中指定区间的科技（及对应效果）植入「目标」数据模组中的指定起始位置。
可从项目根运行：python tools/dat_implant_techs.py 或由 mod_sync_to_official 调用。
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


def _parse_if_path(dat: Union[str, Path, DatFile]) -> DatFile:
    """路径则解析一次，已是 DatFile 则直接返回（避免重复 parse）。"""
    if isinstance(dat, (str, Path)):
        return DatFile.parse(dat)
    return dat


def _ensure_length(lst: list, length: int, placeholder):
    """将列表扩展到 length，不足部分用 placeholder 的深拷贝填充。"""
    while len(lst) < length:
        lst.append(copy.deepcopy(placeholder))


def implant_techs_from_dat(
    source_dat_path: str | Path | DatFile,
    target_dat_path: str | Path | DatFile,
    output_path: str | Path | None,
    source_start: int,
    source_end: int | None = None,
    count: int | None = None,
    target_tech_start: int = 0,
    *,
    warn_overwrite: bool = True,
) -> int:
    """
    将源 dat 中指定区间的科技及其引用的效果植入目标 dat，并保存到 output_path。
    效果植入位置与科技的 ID 偏移一致；required_techs 仅在被迁移范围内时做偏移。

    Args:
        source_dat_path: 源模组 dat 路径或已解析的 DatFile
        target_dat_path: 目标 dat 路径或已解析的 DatFile（将被原地修改）
        output_path: 输出路径；为 None 时不写入磁盘（由调用方统一 save）
        source_start: 源科技段起始 ID（含）
        source_end: 源科技段结束 ID（含）；与 count 二选一
        count: 要植入的科技数量；与 source_end 二选一，若都给出则优先 count
        target_tech_start: 目标模组中植入科技的起始 ID
        warn_overwrite: 是否在覆盖时打印被覆盖的槽位与名称

    Returns:
        实际植入的科技数量
    """
    source_data = _parse_if_path(source_dat_path)
    target_data = _parse_if_path(target_dat_path)
    output_path = Path(output_path) if output_path is not None else None

    n_source_techs = len(source_data.techs)
    n_source_effects = len(source_data.effects)
    n_target_techs = len(target_data.techs)
    n_target_effects = len(target_data.effects)

    if source_start >= n_source_techs:
        raise ValueError(f"源模组科技总数 {n_source_techs}，source_start={source_start} 越界")

    if count is not None:
        implant_count = min(count, n_source_techs - source_start)
    elif source_end is not None:
        if source_end < source_start:
            raise ValueError(f"source_end={source_end} 不能小于 source_start={source_start}")
        if source_end >= n_source_techs:
            raise ValueError(
                f"source_end={source_end} 越界：源模组科技 ID 范围为 [0, {n_source_techs - 1}]"
            )
        implant_count = source_end - source_start + 1
    else:
        implant_count = n_source_techs - source_start

    if implant_count <= 0:
        raise ValueError("植入数量为 0，请检查 source_start / source_end / count")

    tech_offset = target_tech_start - source_start
    source_tech_end = source_start + implant_count - 1

    # 收集本段科技引用的 effect_id，并校验不越界
    effect_ids_to_implant: set[int] = set()
    for i in range(implant_count):
        tech = source_data.techs[source_start + i]
        eid = tech.effect_id
        if eid < 0 or eid >= n_source_effects:
            raise ValueError(
                f"源科技 ID {source_start + i} (name={getattr(tech, 'name', '')!r}) 的 effect_id={eid} 越界："
                f"源模组效果数量为 {n_source_effects}"
            )
        effect_ids_to_implant.add(eid)

    # 目标需达到的 effect / tech 长度
    max_effect_idx = max(eid + tech_offset for eid in effect_ids_to_implant)
    need_effect_len = max_effect_idx + 1
    need_tech_len = target_tech_start + implant_count

    # 用目标自身的 0 号 placeholder 扩展
    placeholder_effect = target_data.effects[0]
    placeholder_tech = target_data.techs[0]

    if need_effect_len > n_target_effects:
        print(f"[植入前] 目标效果数 {n_target_effects}，将扩展至 {need_effect_len}（补 {need_effect_len - n_target_effects} 个 placeholder）")
    if need_tech_len > n_target_techs:
        print(f"[植入前] 目标科技数 {n_target_techs}，将扩展至 {need_tech_len}（补 {need_tech_len - n_target_techs} 个 placeholder）")
    print(f"[植入前] 源科技 [{source_start}..{source_tech_end}] 共 {implant_count} 个 -> 目标科技 [{target_tech_start}..{target_tech_start + implant_count - 1}]，effect 偏移量 = {tech_offset}")

    _ensure_length(target_data.effects, need_effect_len, placeholder_effect)
    _ensure_length(target_data.techs, need_tech_len, placeholder_tech)

    # 收集将被覆盖的 effect / tech 槽位及名称（effect 去重）
    overwritten_effects: dict[int, str] = {}
    overwritten_techs: list[tuple[int, str]] = []
    for eid in effect_ids_to_implant:
        tgt_idx = eid + tech_offset
        overwritten_effects[tgt_idx] = getattr(target_data.effects[tgt_idx], "name", "")
    for i in range(implant_count):
        tgt_idx = target_tech_start + i
        overwritten_techs.append((tgt_idx, getattr(target_data.techs[tgt_idx], "name", "")))

    if overwritten_effects or overwritten_techs:
        if warn_overwrite:
            if overwritten_effects:
                print("[提醒] 以下目标效果槽位将被覆盖（原数据）：")
                for idx in sorted(overwritten_effects):
                    print(f"  effect[{idx}] 原 name={overwritten_effects[idx]!r}")
            if overwritten_techs:
                print("[提醒] 以下目标科技槽位将被覆盖（原数据）：")
                for idx, name in overwritten_techs:
                    print(f"  tech[{idx}] 原 name={name!r}")

    # 先植入效果（按新 ID）
    for eid in effect_ids_to_implant:
        tgt_idx = eid + tech_offset
        target_data.effects[tgt_idx] = copy.deepcopy(source_data.effects[eid])

    # 再植入科技，并重写 effect_id 与 required_techs（仅范围内者偏移）
    for i in range(implant_count):
        src_idx = source_start + i
        tgt_idx = target_tech_start + i
        tech = copy.deepcopy(source_data.techs[src_idx])
        tech.effect_id = tech.effect_id + tech_offset
        req = tech.required_techs
        # 仅当 r 在本次迁移的科技范围内时才做 ID 偏移（-1 等无效值保持不变）
        new_req = tuple(
            r + tech_offset if (source_start <= r <= source_tech_end) else r
            for r in req
        )
        tech.required_techs = new_req
        target_data.techs[tgt_idx] = tech

    if output_path is not None:
        target_data.save(output_path)
    return implant_count


# ============ 使用示例 ============
if __name__ == "__main__":
    _dat = Path("resources") / "_common" / "dat"
    source_dat = _ROOT / "Source" / _dat / "empires2_x2_p1.dat"
    target_dat = _ROOT / "Target" / _dat / "empires2_x2_p1.dat"
    output_dat = _ROOT / "Output" / _dat / "empires2_x2_p1_techs_implanted.dat"

    SOURCE_START = 0
    SOURCE_END = 50
    TARGET_TECH_START = 100

    n = implant_techs_from_dat(
        source_dat,
        target_dat,
        output_dat,
        source_start=SOURCE_START,
        source_end=SOURCE_END,
        target_tech_start=TARGET_TECH_START,
        warn_overwrite=True,
    )
    print(f"已植入 {n} 个科技及对应效果，保存至: {output_dat}")
