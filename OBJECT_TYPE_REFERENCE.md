# object_type / object_type2 对应触发器一览

供手动甄别：是否要在「批量替换单位类型 ID」时一并处理这两个字段。

---

## 重要说明：这两个字段的语义

在 AoE2ScenarioParser 的 `datasets/trigger_lists/object_type.py` 中，**object_type** 定义为：

| 值 | 枚举名   | 含义   |
|----|----------|--------|
| 1  | OTHER    | 其它   |
| 2  | BUILDING | 建筑   |
| 3  | CIVILIAN | 平民   |
| 4  | MILITARY | 军事   |

即 **object_type 是「对象大类」筛选（单位/建筑/平民/军事），不是单位在数据库里的具体类型 ID**（如 74=圣骑士）。  
若在替换「单位类型 ID」时把 object_type 也按单位 ID 替换，会把原本的“军事/建筑”等筛选项改成某个单位 ID，语义会错。  
**object_type2** 在 1.55 后加入，语义与 object_type 相同，用于带“第二组”筛选的效果/条件。

以下列出所有使用到这两个属性的触发器，便于你按需甄别。

---

## 使用 object_type 的效果 (Effects)

| EffectId | 英文名                 | 说明           |
|----------|------------------------|----------------|
| 12       | TASK_OBJECT            | 指派对象       |
| 14       | KILL_OBJECT            | 杀死对象       |
| 15       | REMOVE_OBJECT          | 移除对象       |
| 17       | UNLOAD                 | 卸载           |
| 18       | CHANGE_OWNERSHIP       | 改变所有权     |
| 19       | PATROL                 | 巡逻           |
| 22       | FREEZE_OBJECT          | 冻结对象       |
| 24       | DAMAGE_OBJECT          | 损坏对象       |
| 27       | CHANGE_OBJECT_HP       | 改变对象生命值 |
| 28       | CHANGE_OBJECT_ATTACK   | 改变对象攻击   |
| 29       | STOP_OBJECT            | 停止对象       |
| 30       | ATTACK_MOVE            | 攻击移动       |
| 31       | CHANGE_OBJECT_ARMOR   | 改变对象护甲   |
| 32       | CHANGE_OBJECT_RANGE   | 改变对象射程   |
| 33       | CHANGE_OBJECT_SPEED   | 改变对象速度   |
| 34       | HEAL_OBJECT            | 治疗对象       |
| 35       | TELEPORT_OBJECT        | 传送对象       |
| 36       | CHANGE_OBJECT_STANCE  | 改变对象姿态   |
| 42       | CHANGE_OBJECT_ICON     | 改变对象图标   |
| 43       | REPLACE_OBJECT         | 替换对象       |
| 77       | CREATE_OBJECT_ATTACK  | 创建对象攻击（1.51+） |
| 78       | CREATE_OBJECT_ARMOR   | 创建对象护甲（1.51+） |
| 108      | BUILD_OBJECT           | 建造对象（1.57+）     |

上述效果中，**object_type** 与 **object_group** 一起用于限定「对哪一类对象」生效（如：仅军事单位、仅建筑等），不是具体单位类型 ID。

---

## 使用 object_type 的条件 (Conditions)

| ConditionId | 英文名              | 说明           |
|-------------|---------------------|----------------|
| 3           | OWN_OBJECTS         | 拥有对象       |
| 4           | OWN_FEWER_OBJECTS   | 拥有更少对象   |
| 5           | OBJECTS_IN_AREA     | 区域内对象     |
| 14          | OBJECT_HAS_TARGET   | 对象拥有目标   |
| 76          | OBJECT_ATTACKED     | 对象被攻击（1.54+） |

同样，这里的 **object_type** 表示对象大类（其它/建筑/平民/军事），与 object_list、object_group 配合做筛选。

---

## 使用 object_type2 的触发器

- **效果**：目前文档中明确使用 **object_type2**（及 object_group2）的只有：
  - **MODIFY_ATTRIBUTE_FOR_CLASS (104)**，1.55+：按**对象类别**修改属性（object_group2 + object_type2 表示第二组类别筛选）。

- **条件**：Condition 数据模型在 1.55 起支持 **object_type2** / **object_group2**，但 `conditions.py` 里没有单独列出具体哪条条件使用；若游戏新版本有“第二组对象类型”的筛选条件，会用到这两个字段。

---

## 结论与建议

- **object_type / object_type2** 表示的是 **ObjectType 枚举（OTHER/BUILDING/CIVILIAN/MILITARY）**，不是单位类型 ID。
- 做「批量替换单位类型 ID」时，**一般不应**把 object_type / object_type2 当作单位类型 ID 替换，否则会破坏“按大类筛选”的语义。
- 若你的场景里有特殊用法（例如某些 MOD 或自定义把 object_type 存成单位 ID），再根据上面表格手动甄别并决定是否在脚本里对个别效果/条件做额外处理即可。
