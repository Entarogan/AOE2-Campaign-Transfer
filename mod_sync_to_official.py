"""
业务：将旧模组 dat 的新增/变更内容注入到官方新 dat，并可选地更新场景中的单位/科技 ID。

若项目内已 clone genieutils-py，会优先使用其 src（支持 VER 8.8 等），避免 site-packages 中旧版报 Version 错误。

步骤：
1. 单位：2601（含）到末尾 +UNIT_OFFSET 注入；46、557 覆盖同 ID。
2. 科技：490 及其 effect 覆盖；904-912 及对应 effect +TECH_OFFSET 注入（如 600 则 1504-1512）。
3. 图像：17601（含）到末尾，默认同 ID 覆盖，可选迁移。
4. 语音：850（含）到末尾，默认同 ID 覆盖。
5. 可选：对指定场景应用单位 ID、科技 ID 映射。

单位/科技中名称含 Graphics、Graphic、Sound 的属性：默认图像与语音不迁移 ID（同位置覆盖），故无需改这些引用；若将来开启 GRAPHICS_MIGRATE/SOUNDS_MIGRATE，需在植入后对单位/效果中上述属性按新 ID 做二次映射（可在此脚本或植入工具中实现）。

TODO（本次暂不实现，后续如需再补）：
- dead unit（死亡单位）
- blood unit（血迹单位）
- trailing unit（尾迹单位）
- stack unit（堆叠单位）
- annex unit（附属单位）
- 各类 projectile（抛射物）等
上述若在模组中有新增或修改，也需纳入迁移/植入流程。
"""
import sys
from pathlib import Path as _Path

_clone_genie = _Path(__file__).resolve().parent / "genieutils-py" / "src"
if _clone_genie.exists():
    sys.path.insert(0, str(_clone_genie))

import shutil
from pathlib import Path

from genieutils.datfile import DatFile

from tools.dat_implant_units import implant_units_from_dat, finalize_unit_id_migration, check_unit_id_coherence
from tools.dat_implant_techs import implant_techs_from_dat
from tools.dat_implant_graphics import implant_graphics_from_dat
from tools.dat_implant_sounds import implant_sounds_from_dat
from tools.dat_remap_graphic_sound_in_units import apply_remap_to_dat
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
from tools.batch_replace_trigger_unit_id import apply_unit_id_in_scenario
from tools.batch_replace_map_unit_id import apply_map_unit_id_in_scenario
from tools.batch_replace_trigger_tech_id import apply_tech_mapping_in_scenario
from tools.aoe2_json_injector_all_atlases import run_materials_inject
from tools.aoe2_icons_extender import run_icons_extend

# ---------- 可调参数 ----------
UNIT_OFFSET = 600   # 单位 2601 起植入到 2601+UNIT_OFFSET
TECH_OFFSET = 600   # 科技 904-912 植入到 904+TECH_OFFSET（可与 UNIT_OFFSET 不同）
GRAPHICS_MIGRATE = False  # True 时图像迁移到新 ID（需设 GRAPHICS_TARGET_START）
GRAPHICS_TARGET_START = None  # 图像迁移时的目标起始 ID
SOUNDS_MIGRATE = False
SOUNDS_TARGET_START = None

# widgetui：materials 用 injection_skk 注入，icons 按范围扩展（用户可改下列最大值）
ICONS_EXTEND_TECHS_MAX = 520      # Techs 表扩展到该下标（含）
ICONS_EXTEND_UNITS_MAX = 999      # Units 表扩展到该下标（含）
ICONS_EXTEND_BUILDINGS_MAX = 400  # Buildings 表扩展到该下标（含）
ICONS_EXTEND_UNITS_SUFFIX = "50730"


def run_dat_sync(
    old_mod_dat: str | Path,
    official_dat: str | Path,
    output_dat: str | Path,
    *,
    warn_overwrite: bool = True,
) -> None:
    """
    将旧模组内容注入到官方 dat，结果写入 output_dat。
    会依次：复制官方到 output → 单位 → 科技 → 图像 → 语音。
    只解析源 dat 与目标 dat 各一次，全程在内存中修改，最后统一写入。
    """
    old_mod_dat = Path(old_mod_dat)
    official_dat = Path(official_dat)
    output_dat = Path(output_dat)
    output_dat.parent.mkdir(parents=True, exist_ok=True)

    # 只解析一次，后续全部复用
    source_data = DatFile.parse(old_mod_dat)
    shutil.copy(official_dat, output_dat)
    work_data = DatFile.parse(output_dat)

    # 单位槽位数以每个文明的 units 为准（与 AGE 显示一致），无文明时退化为 unit_headers
    n_units = len(source_data.civs[0].units) if source_data.civs else len(source_data.unit_headers)
    n_gfx = len(source_data.graphics)
    n_sounds = len(source_data.sounds)

    print("[debug] gfx: ", n_gfx)
    print("[debug] sounds: ", n_sounds)

    # 单位：2601 到末尾 -> 2601+UNIT_OFFSET
    if n_units > 2601:
        implant_units_from_dat(
            source_data, work_data, None,
            source_start=2601,
            source_end=n_units - 1,
            target_start=2601 + UNIT_OFFSET,
            warn_overwrite=warn_overwrite,
        )
    implant_units_from_dat(source_data, work_data, None, 46, count=1, target_start=46, warn_overwrite=warn_overwrite)
    implant_units_from_dat(source_data, work_data, None, 557, count=1, target_start=557, warn_overwrite=warn_overwrite)

    # 单位 ID 迁移收尾：植入单位的 .id 与槽位对齐，copy_id/base_id 等 26xx→32xx 全局重映射（一次完成）
    _implanted_indices = {46, 557}
    if n_units > 2601:
        _implanted_indices.update(range(2601 + UNIT_OFFSET, n_units + UNIT_OFFSET))
        _unit_id_map = {i: i + UNIT_OFFSET for i in range(2601, n_units)}
    else:
        _unit_id_map = {}
    finalize_unit_id_migration(work_data, _unit_id_map, _implanted_indices)

    # 自洽性检查：植入槽位内 .id 与槽位一致、且无对已迁移旧 ID 的残留引用
    _migrated_old = set(range(2601, n_units)) if n_units > 2601 else set()
    _issues = check_unit_id_coherence(work_data, _implanted_indices, _migrated_old)
    if _issues:
        print("[单位 ID 自洽性检查] 发现不一致：")
        for _ui, _civ, _path, _val, _msg in _issues[:20]:
            print(f"  {_msg}")
        if len(_issues) > 20:
            print(f"  ... 共 {len(_issues)} 处")
    else:
        print("[单位 ID 自洽性检查] 通过")

    # 科技
    implant_techs_from_dat(source_data, work_data, None, 490, source_end=490, target_tech_start=490, warn_overwrite=warn_overwrite)
    implant_techs_from_dat(source_data, work_data, None, 904, source_end=912, target_tech_start=904 + TECH_OFFSET, warn_overwrite=warn_overwrite)

    # 图像：不迁移 = 原位植入（17601 起同 ID 覆盖）；迁移 = 植入到 GRAPHICS_TARGET_START 起
    if n_gfx > 17601:
        n_implanted_gfx = implant_graphics_from_dat(
            source_data, work_data, None,
            source_start=17601,
            source_end=n_gfx - 1,
            target_start=GRAPHICS_TARGET_START if GRAPHICS_MIGRATE else None,
            warn_overwrite=warn_overwrite,
        )
        _gfx_desc = f"迁移到 {GRAPHICS_TARGET_START}" if (GRAPHICS_MIGRATE and GRAPHICS_TARGET_START is not None) else f"原位 17601..{n_gfx - 1}"
        print(f"[图像] 已植入 {n_implanted_gfx} 个（{_gfx_desc}）")
    else:
        print(f"[图像] 跳过：源图像数 {n_gfx}，无 17601 及以后区间可植入")

    # 语音：不迁移 = 原位植入（850 起同 ID 覆盖）
    if n_sounds > 850:
        n_implanted_snd = implant_sounds_from_dat(
            source_data, work_data, None,
            source_start=850,
            source_end=n_sounds - 1,
            target_start=SOUNDS_TARGET_START if SOUNDS_MIGRATE else None,
            warn_overwrite=warn_overwrite,
        )
        _snd_desc = f"迁移到 {SOUNDS_TARGET_START}" if (SOUNDS_MIGRATE and SOUNDS_TARGET_START is not None) else f"原位 850..{n_sounds - 1}"
        print(f"[语音] 已植入 {n_implanted_snd} 个（{_snd_desc}）")
    else:
        print(f"[语音] 跳过：源语音数 {n_sounds}，无 850 及以后区间可植入")

    # 图像/语音迁移开启时：单位内 graphic/sound 属性按迁移范围加偏移（原地修改 work_data）
    if (GRAPHICS_MIGRATE and GRAPHICS_TARGET_START is not None and n_gfx > 17601) or (SOUNDS_MIGRATE and SOUNDS_TARGET_START is not None and n_sounds > 850):
        implanted_unit_indices = {46, 557}
        if n_units > 2601:
            implanted_unit_indices.update(range(2601 + UNIT_OFFSET, n_units + UNIT_OFFSET))
        cg, cs = apply_remap_to_dat(
            work_data,
            implanted_unit_indices,
            graphic_source_start=17601 if GRAPHICS_MIGRATE else None,
            graphic_source_end=(n_gfx - 1) if GRAPHICS_MIGRATE else None,
            graphic_target_start=GRAPHICS_TARGET_START if GRAPHICS_MIGRATE else None,
            sound_source_start=850 if SOUNDS_MIGRATE else None,
            sound_source_end=(n_sounds - 1) if SOUNDS_MIGRATE else None,
            sound_target_start=SOUNDS_TARGET_START if SOUNDS_MIGRATE else None,
            verbose=True,
        )
        print(f"[图像/语音属性迁移] 单位内 graphic 引用更新 {cg} 处, sound 引用更新 {cs} 处")

    work_data.save(output_dat)
    print(f"[完成] 模组 dat 已写入: {output_dat}")


def run_widgetui_sync(
    target_dir: Path,
    output_dir: Path,
    injection_skk_path: Path,
    *,
    techs_max: int | None = ICONS_EXTEND_TECHS_MAX,
    units_max: int | None = ICONS_EXTEND_UNITS_MAX,
    buildings_max: int | None = ICONS_EXTEND_BUILDINGS_MAX,
    units_suffix: str = ICONS_EXTEND_UNITS_SUFFIX,
    widgetui_subdir: str = "widgetui",
) -> None:
    """
    将 Target/widgetui 的 materials.json、icons.json 与 injection_skk 合并/扩展后写入 Output/widgetui。
    materials：官方 materials + injection_skk.json 注入；
    icons：官方 icons 按 techs_max/units_max/buildings_max 扩展。
    """
    w = Path(widgetui_subdir)
    base_materials = target_dir / w / "materials.json"
    base_icons = target_dir / w / "icons.json"
    out_materials = output_dir / w / "materials.json"
    out_icons = output_dir / w / "icons.json"

    if not base_materials.exists():
        print(f"[widgetui] 跳过 materials：未找到 {base_materials}")
    elif not injection_skk_path.exists():
        print(f"[widgetui] 跳过 materials：未找到 injection_skk {injection_skk_path}")
    else:
        rep = run_materials_inject(base_materials, injection_skk_path, out_materials)
        n_mat = len(rep["materials"].get("injected", [])) + len(rep["materials"].get("overridden", []))
        n_atl = sum(len(r.get("injected", [])) + len(r.get("overridden", [])) for k, r in rep["atlases"].items() if isinstance(r, dict))
        print(f"[widgetui] materials 已注入：Materials +{n_mat}，Atlases 共 +{n_atl} 条纹理 -> {out_materials}")

    if not base_icons.exists():
        print(f"[widgetui] 跳过 icons：未找到 {base_icons}")
    else:
        report = run_icons_extend(
            base_icons, out_icons,
            techs_max=techs_max, units_max=units_max, buildings_max=buildings_max,
            units_suffix=units_suffix,
        )
        t, u, b = report.get("Techs", {}), report.get("Units", {}), report.get("Buildings", {})
        print(f"[widgetui] icons 已扩展：Techs +{t.get('added', 0)}，Units +{u.get('added', 0)}，Buildings +{b.get('added', 0)} -> {out_icons}")


def build_unit_id_mapping(old_mod_dat: str | Path | DatFile) -> dict[int, int]:
    """返回本次业务下 单位旧 ID -> 新 ID 的映射（用于场景替换）。可传路径或已解析的 DatFile 避免重复 parse。"""
    data = DatFile.parse(old_mod_dat) if isinstance(old_mod_dat, (str, Path)) else old_mod_dat
    n_units = len(data.civs[0].units) if data.civs else len(data.unit_headers)
    mapping = {}
    for i in range(2601, n_units):
        mapping[i] = i + UNIT_OFFSET
    mapping[46] = 46
    mapping[557] = 557
    return mapping


def build_tech_id_mapping() -> dict[int, int]:
    """返回本次业务下 科技旧 ID -> 新 ID 的映射（使用 TECH_OFFSET）。"""
    return {904: 904 + TECH_OFFSET, 905: 905 + TECH_OFFSET, 906: 906 + TECH_OFFSET,
            907: 907 + TECH_OFFSET, 908: 908 + TECH_OFFSET, 909: 909 + TECH_OFFSET,
            910: 910 + TECH_OFFSET, 911: 911 + TECH_OFFSET, 912: 912 + TECH_OFFSET}
    # 490 不变，不放入 mapping 即可


def apply_scenario_unit_mapping(
    scenario_path: str | Path,
    output_path: str | Path,
    unit_mapping: dict[int, int],
    *,
    print_summary: bool = True,
) -> list[tuple[int, int, int, int, int]]:
    """
    对场景中触发器与地图单位按 unit_mapping 做批量替换（旧单位类型 ID -> 新 ID）。
    解析一次、在内存中处理完、再写一次到 output_path。

    Returns:
        发生替换的条目列表，每项为 (old_id, new_id, 触发器_effect次数, 触发器_condition次数, 地图单位数)
    """
    scenario_path = Path(scenario_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    scenario = AoE2DEScenario.from_file(str(scenario_path))
    report: list[tuple[int, int, int, int, int]] = []
    for old_id, new_id in unit_mapping.items():
        if old_id == new_id:
            continue
        eff, cond = apply_unit_id_in_scenario(
            scenario, old_id, new_id, replace_in_conditions=True
        )
        map_count = apply_map_unit_id_in_scenario(scenario, old_id, new_id)
        if eff > 0 or cond > 0 or map_count > 0:
            report.append((old_id, new_id, eff, cond, map_count))
    scenario.write_to_file(str(output_path))
    if print_summary:
        print("[场景单位替换] 执行次数汇总:")
        if report:
            for old_id, new_id, eff, cond, map_count in report:
                print("  %s -> %s  触发器 effect %d 处, condition %d 处, 地图 %d 个" % (old_id, new_id, eff, cond, map_count))
        else:
            print("  (场景中未出现映射表中的单位类型 ID，无替换)")
    return report


def apply_scenario_tech_mapping(
    scenario_path: str | Path,
    output_path: str | Path,
    tech_mapping: dict[int, int],
    *,
    print_summary: bool = True,
) -> tuple[int, int]:
    """对场景中触发器科技 ID 按 tech_mapping 替换。解析一次、在内存中处理、再写一次。"""
    scenario_path = Path(scenario_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    scenario = AoE2DEScenario.from_file(str(scenario_path))
    total_effect, total_condition, detail = apply_tech_mapping_in_scenario(scenario, tech_mapping)
    scenario.write_to_file(str(output_path))
    if print_summary:
        print("[场景科技替换] 执行次数: effect 共 %d 处, condition 共 %d 处" % (total_effect, total_condition))
        if detail:
            print("  以下科技 ID 被替换:")
            for old_id in sorted(detail.keys()):
                e, c = detail[old_id]
                new_id = tech_mapping[old_id]
                print("    %s -> %s  (effect %d 处, condition %d 处)" % (old_id, new_id, e, c))
        else:
            print("  (场景中未出现映射表中的科技 ID，无替换)")
    return total_effect, total_condition


def apply_scenario_mappings(
    scenario_path: str | Path,
    output_path: str | Path,
    unit_mapping: dict[int, int],
    tech_mapping: dict[int, int],
    *,
    print_summary: bool = True,
) -> tuple[list[tuple[int, int, int, int, int]], tuple[int, int]]:
    """
    对场景做单位 ID + 科技 ID 的批量替换：只解析一次、在内存中处理完、再写一次到 output_path。

    Returns:
        (单位替换 report, (科技 effect 总次数, 科技 condition 总次数))
    """
    scenario_path = Path(scenario_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    scenario = AoE2DEScenario.from_file(str(scenario_path))
    report: list[tuple[int, int, int, int, int]] = []
    for old_id, new_id in unit_mapping.items():
        if old_id == new_id:
            continue
        eff, cond = apply_unit_id_in_scenario(
            scenario, old_id, new_id, replace_in_conditions=True
        )
        map_count = apply_map_unit_id_in_scenario(scenario, old_id, new_id)
        if eff > 0 or cond > 0 or map_count > 0:
            report.append((old_id, new_id, eff, cond, map_count))
    total_effect, total_condition, tech_detail = apply_tech_mapping_in_scenario(scenario, tech_mapping)
    scenario.write_to_file(str(output_path))
    if print_summary:
        print("[场景单位替换] 执行次数汇总:")
        if report:
            for old_id, new_id, eff, cond, map_count in report:
                print("  %s -> %s  触发器 effect %d 处, condition %d 处, 地图 %d 个" % (old_id, new_id, eff, cond, map_count))
        else:
            print("  (场景中未出现映射表中的单位类型 ID，无替换)")
        print("[场景科技替换] 执行次数: effect 共 %d 处, condition 共 %d 处" % (total_effect, total_condition))
        if tech_detail:
            print("  以下科技 ID 被替换:")
            for old_id in sorted(tech_detail.keys()):
                e, c = tech_detail[old_id]
                new_id = tech_mapping[old_id]
                print("    %s -> %s  (effect %d 处, condition %d 处)" % (old_id, new_id, e, c))
        else:
            print("  (场景中未出现映射表中的科技 ID，无替换)")
    return report, (total_effect, total_condition)


# ---------- 默认目录（与项目子目录一致：Source/Target/Output 下各有 resources/_common/dat、senarios、widgetui） ----------
_BASE_DIR = Path(__file__).resolve().parent
SOURCE_DIR = _BASE_DIR / "Source"
TARGET_DIR = _BASE_DIR / "Target"
OUTPUT_DIR = _BASE_DIR / "Output"
DAT_SUBDIR = Path("resources") / "_common" / "dat"   # .dat 在此子目录下（注意是 _common 带下划线）
SCENARIOS_SUBDIR = Path("senarios")             # 场景文件在此子目录下（拼写为 senarios）
WIDGETUI_SUBDIR = "widgetui"                    # materials.json / icons.json 所在子目录
INJECTION_SKK_PATH = _BASE_DIR / "injection_skk.json"  # 图标/材质注入用 JSON（materials 源）

# ---------- 运行方式 ----------
# 1. 目录结构：Source/、Target/、Output/ 下均有 resources/_common/dat/，其中放 empires2_x2_p1.dat。
# 2. 旧模组 dat：Source/...；官方新 dat：Target/...。在项目根目录执行：python mod_sync_to_official.py
# 3. 工具脚本在 tools/，debug 脚本在 debug/。从根目录执行：python tools/xxx.py、python debug/xxx.py 或 python -m debug.xxx

# ---------- 使用示例 ----------
if __name__ == "__main__":
    OLD_MOD_DAT = SOURCE_DIR / DAT_SUBDIR / "empires2_x2_p1.dat"
    OFFICIAL_DAT = TARGET_DIR / DAT_SUBDIR / "empires2_x2_p1.dat"
    OUTPUT_DAT = OUTPUT_DIR / DAT_SUBDIR / "empires2_x2_p1.dat"

    run_dat_sync(OLD_MOD_DAT, OFFICIAL_DAT, OUTPUT_DAT, warn_overwrite=True)

    # widgetui：Target 的 materials + injection_skk -> Output；Target 的 icons 按范围扩展 -> Output
    run_widgetui_sync(
        TARGET_DIR, OUTPUT_DIR, INJECTION_SKK_PATH,
        widgetui_subdir=WIDGETUI_SUBDIR,
        techs_max=ICONS_EXTEND_TECHS_MAX,
        units_max=ICONS_EXTEND_UNITS_MAX,
        buildings_max=ICONS_EXTEND_BUILDINGS_MAX,
        units_suffix=ICONS_EXTEND_UNITS_SUFFIX,
    )

    # 可选：更新场景中的单位 ID 与科技 ID（场景在 Source/senarios/，输出到 Output/senarios/，只解析一次、处理完再输出）
    _scenario_name = "TogawaSakiko1_Haruhikage.aoe2scenario"
    unit_map = build_unit_id_mapping(OLD_MOD_DAT)
    tech_map = build_tech_id_mapping()
    apply_scenario_mappings(
        SOURCE_DIR / SCENARIOS_SUBDIR / _scenario_name,
        OUTPUT_DIR / SCENARIOS_SUBDIR / _scenario_name,
        unit_map,
        tech_map,
    )
