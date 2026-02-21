"""
在 AoE2 DE 的 dat 文件（empires2_x2_p1.dat）中，将指定起始 ID 的一段单位整体后移，
原位置用空白单位/空白头填补。可从项目根运行：python tools/dat_shift_units.py
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_genie = _ROOT / "genieutils-py" / "src"
if _genie.exists() and str(_genie) not in sys.path:
    sys.path.insert(0, str(_genie))

from genieutils.datfile import DatFile
from genieutils.unitheaders import UnitHeaders


def _blank_unit_header() -> UnitHeaders:
    """创建一个空白单位头（exists=0，用于占位）。"""
    return UnitHeaders(exists=0, task_list=None)


def _ensure_length(lst: list, length: int, blank_fill):
    """将列表扩展到 length，不足部分用 blank_fill 填充。"""
    while len(lst) < length:
        lst.append(blank_fill)


def shift_units_in_dat(
    dat_path: str | Path,
    output_path: str | Path,
    start_id: int,
    offset: int,
    count: int | None = None,
) -> int:
    """
    将 dat 中从 start_id 开始的单位整体后移 offset 个位置，原区间用空白填补。

    Args:
        dat_path: 输入的 empires2_x2_p1.dat 路径
        output_path: 输出 dat 路径（建议不覆盖原文件）
        start_id: 要移动的单位的起始 ID（含）
        offset: 后移量（例如 400 表示新起始 = start_id + 400）
        count: 要移动的单位数量；None 表示从 start_id 到当前末尾全部移动

    Returns:
        实际移动的单位数量

    说明：
        - 每个文明 (civ) 的 units 列表与全局 unit_headers 会同步后移并填补。
        - 空白单位在 civ.units 中为 None，在 unit_headers 中为 exists=0 的 UnitHeaders。
    """
    dat_path = Path(dat_path)
    output_path = Path(output_path)
    data = DatFile.parse(dat_path)

    n_units_total = len(data.unit_headers)  # 以全局 unit_headers 长度为基准
    if start_id >= n_units_total:
        raise ValueError(f"start_id={start_id} 超出当前单位数量 {n_units_total}")

    if count is None:
        count = n_units_total - start_id
    else:
        count = min(count, n_units_total - start_id)

    new_start = start_id + offset
    fill_len = offset  # 2600..2999 共 400 个空白

    print(f"[移动前] 单位总数: {n_units_total}, 将移动 ID [{start_id}..{start_id + count - 1}] 共 {count} 个 -> 新位置 [{new_start}..{new_start + count - 1}], 中间 {fill_len} 格填空白")

    # 1) 扩展 unit_headers（全局），空白头用 exists=0
    need_len = new_start + count
    _ensure_length(data.unit_headers, need_len, _blank_unit_header())

    # 2) 对 unit_headers 做“块移动 + 填补”
    saved_headers = list(data.unit_headers[start_id : start_id + count])
    data.unit_headers[start_id : start_id + fill_len] = [_blank_unit_header() for _ in range(fill_len)]
    _ensure_length(data.unit_headers, new_start + count, _blank_unit_header())
    data.unit_headers[new_start : new_start + count] = saved_headers

    # 3) 对每个文明的 units 做同样操作（空白 = None）
    for civ in data.civs:
        ulen = len(civ.units)
        _ensure_length(civ.units, ulen, None)  # 确保至少当前长度
        need_len_civ = new_start + count
        while len(civ.units) < need_len_civ:
            civ.units.append(None)

        saved_units = list(civ.units[start_id : start_id + count])
        civ.units[start_id : start_id + fill_len] = [None] * fill_len
        civ.units[new_start : new_start + count] = saved_units

    data.save(output_path)
    return count


# ============ 使用示例 ============
if __name__ == "__main__":
    _dat = Path("resources") / "_common" / "dat"
    dat_path = _ROOT / "Source" / _dat / "empires2_x2_p1.dat"
    output_path = _ROOT / "Output" / _dat / "empires2_x2_p1_shifted.dat"

    START_ID = 2600
    OFFSET = 400   # 后移 400，即 2600 -> 3000
    COUNT = None   # None = 从 2600 到末尾全部移动；也可设为具体数量如 100

    n = shift_units_in_dat(dat_path, output_path, START_ID, OFFSET, COUNT)
    print(f"已将 {n} 个单位自 ID {START_ID} 后移 {OFFSET} 至 {START_ID + OFFSET}，中间已用空白填补。")
    print(f"已保存: {output_path}")
    