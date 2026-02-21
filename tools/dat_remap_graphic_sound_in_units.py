"""
在已植入单位的 dat 中，对被迁移单位内「名称含 Graphic/Graphics/Sound 且值为整数」的属性，
若其值落在被迁移的图像/语音范围内，则按迁移偏移一并更新。

供 mod_sync_to_official 在开启 GRAPHICS_MIGRATE 或 SOUNDS_MIGRATE 时调用。

说明：通过属性名包含 "graphic" 或 "sound" 自动识别（排除 sound_name 等明显字符串）。
genie/dat 中常见相关属性包括但不限于：单位/对象上的 standing_graphic, dying_graphic,
attack_graphic, selection_sound, move_sound, damage_sound 等（具体以 genieutils Unit 为准）。
"""

from pathlib import Path

from genieutils.datfile import DatFile


def _is_graphic_or_sound_attr(name: str) -> bool:
    """属性名是否与图像/语音 ID 相关（且排除明显是字符串的如 sound_name）。"""
    n = name.lower()
    if "sound_name" in n or "graphic_name" in n or "file_name" in n:
        return False
    return "graphic" in n or "sound" in n


def _remap_int_in_range(value: int, src_lo: int, src_hi: int, offset: int) -> int | None:
    """若 value 在 [src_lo, src_hi] 内则返回 value + offset，否则返回 None 表示不改。"""
    if not isinstance(value, int):
        return None
    if src_lo <= value <= src_hi:
        return value + offset
    return None


def remap_graphic_sound_in_implanted_units(
    data: DatFile,
    implanted_unit_indices: set[int],
    *,
    graphic_source_start: int | None = None,
    graphic_source_end: int | None = None,
    graphic_offset: int = 0,
    sound_source_start: int | None = None,
    sound_source_end: int | None = None,
    sound_offset: int = 0,
    verbose: bool = True,
) -> tuple[int, int]:
    """
    对 data 中「仅在被植入单位索引」内的单位，检查其名称含 Graphic/Sound 的整数属性；
    若值在图像迁移范围内则 +graphic_offset，在语音迁移范围内则 +sound_offset。

    Args:
        data: 已包含植入单位的 DatFile（会被原地修改）
        implanted_unit_indices: 被植入单位的 ID 集合，如 {46, 557, 3201, 3202, ...}
        graphic_source_start/end: 被迁移的图像 ID 范围（含）
        graphic_offset: 图像 ID 偏移（目标起始 - 源起始）
        sound_source_start/end: 被迁移的语音 ID 范围（含）
        sound_offset: 语音 ID 偏移
        verbose: 是否打印每个被修改的属性

    Returns:
        (被修改的 graphic 引用次数, 被修改的 sound 引用次数)
    """
    count_graphic = 0
    count_sound = 0
    do_graphic = graphic_source_start is not None and graphic_source_end is not None and graphic_offset != 0
    do_sound = sound_source_start is not None and sound_source_end is not None and sound_offset != 0

    if not do_graphic and not do_sound:
        return 0, 0

    for civ in data.civs:
        for unit_index, unit in enumerate(civ.units):
            if unit is None or unit_index not in implanted_unit_indices:
                continue
            for attr_name in dir(unit):
                if attr_name.startswith("_"):
                    continue
                if not _is_graphic_or_sound_attr(attr_name):
                    continue
                try:
                    val = getattr(unit, attr_name)
                except Exception:
                    continue
                if not isinstance(val, int):
                    continue
                new_val = None
                if do_graphic and graphic_source_start <= val <= graphic_source_end:
                    new_val = val + graphic_offset
                    count_graphic += 1
                elif do_sound and sound_source_start <= val <= sound_source_end:
                    new_val = val + sound_offset
                    count_sound += 1
                if new_val is not None:
                    try:
                        setattr(unit, attr_name, new_val)
                        if verbose:
                            print(f"  unit[{unit_index}] {attr_name}: {val} -> {new_val}")
                    except Exception:
                        pass

    return count_graphic, count_sound


def apply_remap_to_dat(
    data: DatFile,
    implanted_unit_indices: set[int],
    *,
    graphic_source_start: int | None = None,
    graphic_source_end: int | None = None,
    graphic_target_start: int | None = None,
    sound_source_start: int | None = None,
    sound_source_end: int | None = None,
    sound_target_start: int | None = None,
    verbose: bool = True,
) -> tuple[int, int]:
    """
    对已加载的 DatFile 做植入单位内 graphic/sound 属性迁移（原地修改，不写入磁盘）。
    若某侧未提供 target_start 或 source 范围则不做该侧迁移。
    """
    graphic_offset = (
        (graphic_target_start - graphic_source_start)
        if (graphic_target_start is not None and graphic_source_start is not None)
        else 0
    )
    sound_offset = (
        (sound_target_start - sound_source_start)
        if (sound_target_start is not None and sound_source_start is not None)
        else 0
    )
    return remap_graphic_sound_in_implanted_units(
        data,
        implanted_unit_indices,
        graphic_source_start=graphic_source_start,
        graphic_source_end=graphic_source_end,
        graphic_offset=graphic_offset,
        sound_source_start=sound_source_start,
        sound_source_end=sound_source_end,
        sound_offset=sound_offset,
        verbose=verbose,
    )


def apply_remap_to_saved_dat(
    output_dat: Path | str,
    implanted_unit_indices: set[int],
    *,
    graphic_source_start: int | None = None,
    graphic_source_end: int | None = None,
    graphic_target_start: int | None = None,
    sound_source_start: int | None = None,
    sound_source_end: int | None = None,
    sound_target_start: int | None = None,
    verbose: bool = True,
) -> tuple[int, int]:
    """
    读取已保存的 dat，对植入单位做 graphic/sound 属性迁移后写回。
    若某侧未提供 target_start 或 source 范围则不做该侧迁移。
    """
    output_dat = Path(output_dat)
    data = DatFile.parse(output_dat)
    cg, cs = apply_remap_to_dat(
        data,
        implanted_unit_indices,
        graphic_source_start=graphic_source_start,
        graphic_source_end=graphic_source_end,
        graphic_target_start=graphic_target_start,
        sound_source_start=sound_source_start,
        sound_source_end=sound_source_end,
        sound_target_start=sound_target_start,
        verbose=verbose,
    )
    data.save(output_dat)
    return cg, cs
