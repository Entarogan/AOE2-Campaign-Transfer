"""
批量替换场景触发器中引用的「科技 ID」，按映射表替换（如植入后 904→1504）。

使用 AoE2ScenarioParser。会替换 effect 中的 technology / force_research_technology / local_technology，
以及 condition 中的 technology / local_technology。
"""

from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
from AoE2ScenarioParser.helper.helper import value_is_valid
from AoE2ScenarioParser.exceptions.asp_exceptions import UnsupportedAttributeError

EFFECT_TECH_ATTRS = ("technology", "force_research_technology", "local_technology")
CONDITION_TECH_ATTRS = ("technology", "local_technology")


def _get_tech_val_and_set(obj, attr: str, mapping: dict[int, int]) -> int | None:
    """若 obj 的 attr 在 mapping 中则替换并返回旧 ID，否则返回 None。1.54 等旧格式无 local_technology 会抛 UnsupportedAttributeError，返回 None。"""
    try:
        val = getattr(obj, attr, None)
    except UnsupportedAttributeError:
        return None
    if not value_is_valid(val) or val not in mapping:
        return None
    setattr(obj, attr, mapping[val])
    return val


def _apply_tech_mapping_in_effects(effects, mapping: dict[int, int]) -> tuple[int, dict[int, int]]:
    """返回 (总替换次数, {旧科技 ID: 该 ID 被替换次数})"""
    total = 0
    by_old_id: dict[int, int] = {}
    for effect in effects:
        for attr in EFFECT_TECH_ATTRS:
            old_id = _get_tech_val_and_set(effect, attr, mapping)
            if old_id is not None:
                total += 1
                by_old_id[old_id] = by_old_id.get(old_id, 0) + 1
    return total, by_old_id


def _apply_tech_mapping_in_conditions(conditions, mapping: dict[int, int]) -> tuple[int, dict[int, int]]:
    """返回 (总替换次数, {旧科技 ID: 该 ID 被替换次数})"""
    total = 0
    by_old_id: dict[int, int] = {}
    for condition in conditions:
        for attr in CONDITION_TECH_ATTRS:
            old_id = _get_tech_val_and_set(condition, attr, mapping)
            if old_id is not None:
                total += 1
                by_old_id[old_id] = by_old_id.get(old_id, 0) + 1
    return total, by_old_id


def replace_trigger_tech_ids(
    scenario_path: str,
    output_path: str,
    tech_id_mapping: dict[int, int],
    *,
    print_summary: bool = True,
) -> tuple[int, int, dict[int, tuple[int, int]]]:
    """
    在场景的「所有」触发器中，按 tech_id_mapping 将科技 ID 替换为新 ID。

    Args:
        scenario_path: 场景文件路径
        output_path: 输出文件路径
        tech_id_mapping: 旧科技 ID -> 新科技 ID，如 {904: 1504, 905: 1505}
        print_summary: 是否打印「哪些 ID 被替换」及各处替换次数

    Returns:
        (effect 总替换次数, condition 总替换次数, {旧 ID: (effect 次数, condition 次数)})
    """
    scenario = AoE2DEScenario.from_file(scenario_path)
    trigger_manager = scenario.trigger_manager

    total_effect, total_condition = 0, 0
    effect_by_id: dict[int, int] = {}
    condition_by_id: dict[int, int] = {}
    for trigger in trigger_manager.triggers:
        te, be = _apply_tech_mapping_in_effects(trigger.effects, tech_id_mapping)
        tc, bc = _apply_tech_mapping_in_conditions(trigger.conditions, tech_id_mapping)
        total_effect += te
        total_condition += tc
        for k, v in be.items():
            effect_by_id[k] = effect_by_id.get(k, 0) + v
        for k, v in bc.items():
            condition_by_id[k] = condition_by_id.get(k, 0) + v

    # 仅对有发生替换的 ID 建明细，便于调用方和打印
    detail: dict[int, tuple[int, int]] = {}
    all_old_ids = set(effect_by_id.keys()) | set(condition_by_id.keys())
    for old_id in sorted(all_old_ids):
        detail[old_id] = (effect_by_id.get(old_id, 0), condition_by_id.get(old_id, 0))

    if print_summary:
        print("[场景科技替换] 执行次数: effect 共 %d 处, condition 共 %d 处" % (total_effect, total_condition))
        if detail:
            print("  以下科技 ID 被替换:")
            for old_id in sorted(detail.keys()):
                e, c = detail[old_id]
                new_id = tech_id_mapping[old_id]
                print("    %s -> %s  (effect %d 处, condition %d 处)" % (old_id, new_id, e, c))
        else:
            print("  (场景中未出现映射表中的科技 ID，无替换)")

    scenario.write_to_file(output_path)
    return total_effect, total_condition, detail


def apply_tech_mapping_in_scenario(
    scenario: "AoE2DEScenario",
    tech_id_mapping: dict[int, int],
) -> tuple[int, int, dict[int, tuple[int, int]]]:
    """
    在已加载的场景对象上按 tech_id_mapping 替换触发器中的科技 ID，不读不写文件。
    返回 (effect 总替换次数, condition 总替换次数, {旧 ID: (effect 次数, condition 次数)})。
    """
    trigger_manager = scenario.trigger_manager
    total_effect, total_condition = 0, 0
    effect_by_id: dict[int, int] = {}
    condition_by_id: dict[int, int] = {}
    for trigger in trigger_manager.triggers:
        te, be = _apply_tech_mapping_in_effects(trigger.effects, tech_id_mapping)
        tc, bc = _apply_tech_mapping_in_conditions(trigger.conditions, tech_id_mapping)
        total_effect += te
        total_condition += tc
        for k, v in be.items():
            effect_by_id[k] = effect_by_id.get(k, 0) + v
        for k, v in bc.items():
            condition_by_id[k] = condition_by_id.get(k, 0) + v
    detail = {}
    for old_id in sorted(set(effect_by_id.keys()) | set(condition_by_id.keys())):
        detail[old_id] = (effect_by_id.get(old_id, 0), condition_by_id.get(old_id, 0))
    return total_effect, total_condition, detail
