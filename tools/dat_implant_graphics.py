"""
将「源」数据模组中指定区间的图像 (graphics) 植入「目标」数据模组。

使用 genieutils-py。默认不迁移 ID（直接覆盖目标同位置）；可选迁移（+offset）。
"""

import copy
from pathlib import Path
from typing import Union

from genieutils.datfile import DatFile


def _parse_if_path(dat: Union[str, Path, DatFile]) -> DatFile:
    if isinstance(dat, (str, Path)):
        return DatFile.parse(dat)
    return dat


def _ensure_length(lst: list, length: int, fill_with=None):
    while len(lst) < length:
        lst.append(fill_with)


def implant_graphics_from_dat(
    source_dat_path: str | Path | DatFile,
    target_dat_path: str | Path | DatFile,
    output_path: str | Path | None,
    source_start: int = 17601,
    source_end: int | None = None,
    *,
    target_start: int | None = None,
    warn_overwrite: bool = True,
) -> int:
    """
    将源 dat 中 [source_start, source_end] 的图像植入目标 dat。
    不迁移（target_start 为 None）= 在原位植入（同 ID 覆盖）；迁移 = 植入到 target_start 起。

    Args:
        source_dat_path: 源 dat 路径或已解析的 DatFile
        target_dat_path: 目标 dat 路径或已解析的 DatFile（将被原地修改）
        output_path: 输出路径；为 None 时不写入磁盘
        source_start: 源图像起始 ID（含），默认 17601
        source_end: 源图像结束 ID（含）；None 表示到源末尾
        target_start: 目标起始 ID；None 表示不迁移（覆盖同位置）
        warn_overwrite: 是否打印被覆盖的槽位

    Returns:
        植入的图像数量
    """
    source_data = _parse_if_path(source_dat_path)
    target_data = _parse_if_path(target_dat_path)
    output_path = Path(output_path) if output_path is not None else None


    n_source = len(source_data.graphics)
    if source_start >= n_source:
        raise ValueError(f"源模组图像总数 {n_source}，source_start={source_start} 越界")

    if source_end is None:
        source_end = n_source - 1
    else:
        if source_end < source_start:
            raise ValueError(f"source_end={source_end} 不能小于 source_start={source_start}")
        if source_end >= n_source:
            raise ValueError(f"source_end={source_end} 越界，源图像 ID 范围 [0, {n_source - 1}]")

    implant_count = source_end - source_start + 1
    migrate = target_start is not None
    if migrate:
        t_start = target_start
        need_len = t_start + implant_count
        _ensure_length(target_data.graphics, need_len, None)
        overwritten = [
            (t_start + i, getattr(target_data.graphics[t_start + i], "name", ""))
            for i in range(implant_count)
            if target_data.graphics[t_start + i] is not None
        ]
    else:
        t_start = source_start
        need_len = source_end + 1
        _ensure_length(target_data.graphics, need_len, None)
        overwritten = [
            (source_start + i, getattr(target_data.graphics[source_start + i], "name", ""))
            for i in range(implant_count)
            if target_data.graphics[source_start + i] is not None
        ]

    if overwritten and warn_overwrite:
        print("[提醒] 以下目标图像槽位将被覆盖（原数据）：")
        for idx, name in overwritten[:20]:
            print(f"  graphic[{idx}] 原 name={name!r}")
        if len(overwritten) > 20:
            print(f"  ... 共 {len(overwritten)} 个")

    for i in range(implant_count):
        src_idx = source_start + i
        tgt_idx = t_start + i
        g = source_data.graphics[src_idx]
        target_data.graphics[tgt_idx] = copy.deepcopy(g) if g is not None else None

    if output_path is not None:
        target_data.save(output_path)
    return implant_count
