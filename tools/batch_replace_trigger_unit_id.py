"""
批量替换 AoE2 场景中指定触发器(trigger)内的「单位类型 ID」（数据库编号），
不修改任何「单位实例 ID」（地图上具体单位的引用）。

使用 AoE2ScenarioParser：https://github.com/KSneijders/AoE2ScenarioParser

满足两点：
1. 只替换单位类型 ID，绝不修改单位实例 ID（见下方常量说明）。
2. 触发器内所有出现单位类型 ID 的位置都会检查并替换（包括效果中的两个槽位，
   如「生成驻扎物体」里的驻扎单位 + 被驻扎单位 对应 object_list_unit_id 与 object_list_unit_id_2）。
"""

from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
from AoE2ScenarioParser.helper.helper import value_is_valid

# 按显示顺序选触发器时可使用：
# from AoE2ScenarioParser.objects.support.trigger_select import TS  # trigger_select=TS.display(0)

# ---------- 单位类型 ID（会替换）：数据库中的单位编号，如 圣骑士=74 ----------
# 效果中所有这类属性都会遍历，确保「驻扎单位 / 被驻扎单位」等双槽位都被覆盖
EFFECT_UNIT_TYPE_ATTRS = ("object_list_unit_id", "object_list_unit_id_2")
# 条件中表示「按单位类型筛选」时的属性（若该条件类型使用 object_list 存单位类型）
CONDITION_UNIT_TYPE_ATTRS = ("object_list",)

# ---------- 单位实例 ID（绝不修改）：地图上具体是哪一个单位 ----------
# 以下属性存的是实例 ID，本脚本不会读取或写入它们
# 效果: location_object_reference, selected_object_ids, legacy_location_object_reference
# 条件: unit_object


def _count_unit_type_in_effects(effects, unit_id: int) -> int:
    """仅计数：效果中等于 unit_id 的单位类型 ID 出现次数（不修改）。"""
    count = 0
    for effect in effects:
        for attr in EFFECT_UNIT_TYPE_ATTRS:
            if not hasattr(effect, attr):
                continue
            val = getattr(effect, attr, None)
            if value_is_valid(val) and val == unit_id:
                count += 1
    return count


def _count_unit_type_in_conditions(conditions, unit_id: int) -> int:
    """仅计数：条件中等于 unit_id 的单位类型相关属性出现次数（不修改）。"""
    count = 0
    for condition in conditions:
        for attr in CONDITION_UNIT_TYPE_ATTRS:
            if not hasattr(condition, attr):
                continue
            val = getattr(condition, attr, None)
            if value_is_valid(val) and val == unit_id:
                count += 1
    return count


def _replace_unit_type_in_effects(effects, old_unit_id: int, new_unit_id: int) -> int:
    """只替换效果中的单位类型 ID（EFFECT_UNIT_TYPE_ATTRS），不碰实例 ID。返回替换次数。"""
    count = 0
    for effect in effects:
        for attr in EFFECT_UNIT_TYPE_ATTRS:
            if not hasattr(effect, attr):
                continue
            val = getattr(effect, attr, None)
            if value_is_valid(val) and val == old_unit_id:
                setattr(effect, attr, new_unit_id)
                count += 1
    return count


def _replace_unit_type_in_conditions(conditions, old_unit_id: int, new_unit_id: int) -> int:
    """只替换条件中的单位类型相关属性（CONDITION_UNIT_TYPE_ATTRS），不碰 unit_object 等实例 ID。"""
    count = 0
    for condition in conditions:
        for attr in CONDITION_UNIT_TYPE_ATTRS:
            if not hasattr(condition, attr):
                continue
            val = getattr(condition, attr, None)
            if value_is_valid(val) and val == old_unit_id:
                setattr(condition, attr, new_unit_id)
                count += 1
    return count


def replace_unit_id_in_trigger(
    scenario_path: str,
    output_path: str,
    trigger_select,
    old_unit_id: int,
    new_unit_id: int,
    *,
    replace_in_conditions: bool = True,
):
    """
    在指定触发器中，将所有等于 old_unit_id 的「单位类型 ID」替换为 new_unit_id。
    不修改任何单位实例 ID（如 location_object_reference、selected_object_ids、unit_object）。

    Args:
        scenario_path: 场景文件路径，如 "C:/.../scenario.aoe2scenario"
        output_path: 输出文件路径（建议不要覆盖原文件）
        trigger_select: 触发器选择，如 0（按 index）或 TS.display(0)
        old_unit_id: 要被替换的单位类型 ID（数据库编号）
        new_unit_id: 新的单位类型 ID
        replace_in_conditions: 是否同时在条件中替换单位类型（object_list 等）
    """
    scenario = AoE2DEScenario.from_file(scenario_path)
    trigger_manager = scenario.trigger_manager
    trigger = trigger_manager.get_trigger(trigger_select)

    # 替换前先计数，便于用户确认是否选对了单位 ID
    n_effect = _count_unit_type_in_effects(trigger.effects, old_unit_id)
    n_condition = _count_unit_type_in_conditions(trigger.conditions, old_unit_id) if replace_in_conditions else 0
    print(f"[替换前] 单位类型 ID {old_unit_id} 在 effect 中出现 {n_effect} 次, 在 condition 中出现 {n_condition} 次")
    if n_effect == 0 and n_condition == 0:
        print("  -> 未发现匹配，请核对 old_unit_id 是否为目标单位类型。")

    count_effect = _replace_unit_type_in_effects(trigger.effects, old_unit_id, new_unit_id)
    count_condition = 0
    if replace_in_conditions:
        count_condition = _replace_unit_type_in_conditions(
            trigger.conditions, old_unit_id, new_unit_id
        )

    scenario.write_to_file(output_path)
    return count_effect, count_condition


def replace_unit_id_in_all_triggers(
    scenario_path: str,
    output_path: str,
    old_unit_id: int,
    new_unit_id: int,
    *,
    replace_in_conditions: bool = True,
    print_before: bool = True,
):
    """
    在场景的「所有」触发器中批量替换单位类型 ID。
    同样只替换类型 ID，不修改任何单位实例 ID；效果中所有单位类型槽位都会检查。
    """
    scenario = AoE2DEScenario.from_file(scenario_path)
    trigger_manager = scenario.trigger_manager

    if print_before:
        total_effect_pre = sum(
            _count_unit_type_in_effects(t.effects, old_unit_id) for t in trigger_manager.triggers
        )
        total_condition_pre = 0
        if replace_in_conditions:
            total_condition_pre = sum(
                _count_unit_type_in_conditions(t.conditions, old_unit_id) for t in trigger_manager.triggers
            )
        print(f"[替换前] 单位类型 ID {old_unit_id} 在 effect 中共出现 {total_effect_pre} 次, 在 condition 中共出现 {total_condition_pre} 次")
        if total_effect_pre == 0 and total_condition_pre == 0:
            print("  -> 未发现匹配，请核对 old_unit_id 是否为目标单位类型。")

    total_effect, total_condition = 0, 0
    for trigger in trigger_manager.triggers:
        total_effect += _replace_unit_type_in_effects(
            trigger.effects, old_unit_id, new_unit_id
        )
        if replace_in_conditions:
            total_condition += _replace_unit_type_in_conditions(
                trigger.conditions, old_unit_id, new_unit_id
            )

    scenario.write_to_file(output_path)
    return total_effect, total_condition


def apply_unit_id_in_scenario(
    scenario: "AoE2DEScenario",
    old_unit_id: int,
    new_unit_id: int,
    *,
    replace_in_conditions: bool = True,
) -> tuple[int, int]:
    """
    在已加载的场景对象上替换所有触发器中的单位类型 ID，不读不写文件。
    返回 (effect 替换次数, condition 替换次数)。
    """
    trigger_manager = scenario.trigger_manager
    total_effect, total_condition = 0, 0
    for trigger in trigger_manager.triggers:
        total_effect += _replace_unit_type_in_effects(
            trigger.effects, old_unit_id, new_unit_id
        )
        if replace_in_conditions:
            total_condition += _replace_unit_type_in_conditions(
                trigger.conditions, old_unit_id, new_unit_id
            )
    return total_effect, total_condition


# ============ 使用示例（从项目根运行：python tools/batch_replace_trigger_unit_id.py）============
if __name__ == "__main__":
    from pathlib import Path
    from AoE2ScenarioParser.datasets.units import UnitInfo

    _ROOT = Path(__file__).resolve().parent.parent
    _sen = Path("senarios")
    scenario_path = _ROOT / "Source" / _sen / "my_scenario.aoe2scenario"   # 源场景
    output_path = _ROOT / "Output" / _sen / "my_scenario.aoe2scenario"     # 输出到 Output/senarios

    # --------- 方式一：只替换「某一个」触发器 ---------
    # 触发器选择：整数 = 按创建顺序(trigger index)，如 0 表示第一个
    # 用 TS.display(0) 则按编辑器显示顺序选
    trigger_index = 0

    OLD_UNIT_ID = UnitInfo.PALADIN.ID          # 例如：原为 圣骑士
    NEW_UNIT_ID = UnitInfo.ELITE_PALADIN.ID    # 改为 精锐圣骑士

    eff, cond = replace_unit_id_in_trigger(
        scenario_path,
        output_path,
        trigger_index,
        OLD_UNIT_ID,
        NEW_UNIT_ID,
        replace_in_conditions=True,  # 条件中的单位类型也一并替换
    )
    print(f"[单触发器] 效果中替换: {eff} 处, 条件中替换: {cond} 处")

    # --------- 方式二：替换「所有」触发器中的该单位 ID ---------
    # total_eff, total_cond = replace_unit_id_in_all_triggers(
    #     scenario_path,
    #     output_path,
    #     OLD_UNIT_ID,
    #     NEW_UNIT_ID,
    #     replace_in_conditions=True,
    # )
    # print(f"[全场景] 效果中替换: {total_eff} 处, 条件中替换: {total_cond} 处")

    print(f"已保存: {output_path}")
