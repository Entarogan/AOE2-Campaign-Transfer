"""
批量替换「地图上」某单位类型为另一种单位类型。

与 batch_replace_trigger_unit_id.py 不同：本工具只改地图上已放置的单位（Unit），
不改触发器中的单位类型 ID。

数据结构说明：
- 地图单位存在 unit_manager.units 中，类型为 List[List[Unit]]。
- 共 9 个列表，按玩家索引 0~8（0=GAIA）。
- 每个玩家列表内是 Unit 对象列表，顺序即场景中的存储顺序。
- 本工具只原地修改每个 Unit 的 unit_const（单位类型 ID），不增删元素、不改变
  单位在列表中的位置，也不改 reference_id、坐标、玩家、驻扎关系等；仅替换类型
  （以及游戏会按新类型应用的属性）。
"""

from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario


def _count_map_units_by_const(unit_manager, unit_const: int) -> int:
    """统计地图上 unit_const 等于给定值的单位数量（不修改）。"""
    n = 0
    for player_units in unit_manager.units:
        for unit in player_units:
            if unit.unit_const == unit_const:
                n += 1
    return n


def replace_map_unit_id(
    scenario_path: str,
    output_path: str,
    old_unit_id: int,
    new_unit_id: int,
    *,
    print_before: bool = True,
) -> int:
    """
    将地图上所有单位类型为 old_unit_id 的单位改为 new_unit_id。
    不改变单位在列表中的位置，只修改 unit_const（及游戏按新类型应用的属性）。

    Args:
        scenario_path: 场景文件路径
        output_path: 输出文件路径（建议不覆盖原文件）
        old_unit_id: 要被替换的单位类型 ID（如 UnitInfo.PALADIN.ID）
        new_unit_id: 新的单位类型 ID（如 UnitInfo.SCOUT_CAVALRY.ID）

    Returns:
        被替换的单位数量
    """
    scenario = AoE2DEScenario.from_file(scenario_path)
    unit_manager = scenario.unit_manager

    n_before = _count_map_units_by_const(unit_manager, old_unit_id)
    if print_before:
        print(f"[替换前] 地图上单位类型 ID {old_unit_id} 共 {n_before} 个")
        if n_before == 0:
            print("  -> 未发现匹配，请核对 old_unit_id 是否为目标单位类型。")

    replaced = 0
    # units: List[List[Unit]]，按玩家分组的列表，顺序不变、只改 unit_const
    for player_units in unit_manager.units:
        for unit in player_units:
            if unit.unit_const == old_unit_id:
                unit.unit_const = new_unit_id
                replaced += 1

    scenario.write_to_file(output_path)
    return replaced


def apply_map_unit_id_in_scenario(scenario: "AoE2DEScenario", old_unit_id: int, new_unit_id: int) -> int:
    """
    在已加载的场景对象上替换地图单位类型 ID，不读不写文件。
    返回被替换的单位数量。
    """
    replaced = 0
    for player_units in scenario.unit_manager.units:
        for unit in player_units:
            if unit.unit_const == old_unit_id:
                unit.unit_const = new_unit_id
                replaced += 1
    return replaced


# ============ 使用示例（从项目根运行：python tools/batch_replace_map_unit_id.py）============
if __name__ == "__main__":
    from pathlib import Path
    from AoE2ScenarioParser.datasets.units import UnitInfo

    _ROOT = Path(__file__).resolve().parent.parent
    _sen = Path("senarios")
    scenario_path = _ROOT / "Source" / _sen / "my_scenario.aoe2scenario"
    output_path = _ROOT / "Output" / _sen / "my_scenario.aoe2scenario"

    OLD_UNIT_ID = UnitInfo.PALADIN.ID           # 例如：地图上的 圣骑士 (74)
    NEW_UNIT_ID = UnitInfo.SCOUT_CAVALRY.ID    # 改为 侦查骑兵

    count = replace_map_unit_id(
        scenario_path,
        output_path,
        OLD_UNIT_ID,
        NEW_UNIT_ID,
    )
    print(f"已替换 {count} 个地图单位，保存至: {output_path}")
