"""
在整个 dat 文件的原始字节中全局搜索指定数值（默认 2606），按 int16 与 int32 小端解析，
报告每次出现的文件偏移与次数，便于定位「漏迁移」或导致崩溃的残留引用。

用法（在项目根目录执行）：
  python debug/debug_dat_grep_value.py [dat路径] [数值]
  python -m debug.debug_dat_grep_value [dat路径] [数值]
  默认：Output/resources/_common/dat/empires2_x2_p1.dat  2606
"""

import struct
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def find_all_substrings(data: bytes, pattern: bytes) -> list[int]:
    """返回 pattern 在 data 中所有出现的起始偏移。"""
    out = []
    start = 0
    while True:
        i = data.find(pattern, start)
        if i == -1:
            break
        out.append(i)
        start = i + 1
    return out


def main() -> None:
    default_dat = _ROOT / "Output" / "resources" / "_common" / "dat" / "empires2_x2_p1.dat"

    argv = sys.argv[1:]
    dat_path = Path(argv[0]) if argv else default_dat
    value = int(argv[1]) if len(argv) > 1 else 2606

    if not dat_path.exists():
        print(f"文件不存在: {dat_path}")
        sys.exit(1)

    raw = dat_path.read_bytes()
    size = len(raw)
    print(f"文件: {dat_path}")
    print(f"大小: {size} 字节")
    print(f"搜索数值: {value}（int16 与 int32 小端）")
    print()

    # 2606 作为 int16 小端: 0x0A26 -> \x26\x0a
    pattern_16 = struct.pack("<h", value)
    # 作为 int32 小端
    pattern_32 = struct.pack("<i", value)

    offsets_16 = find_all_substrings(raw, pattern_16)
    offsets_32 = find_all_substrings(raw, pattern_32)

    # 某些偏移可能同时被 16 位和 32 位匹配（重叠），合并去重并标注可能类型
    all_offsets = sorted(set(offsets_16) | set(offsets_32))
    # 标注：若该偏移也是 32 位的前两字节，则可能实际是 32 位的一部分，这里统一按「出现位置」列出
    print(f"========== 数值 {value} 出现次数 ==========")
    print(f"  as int16 (2 字节): {len(offsets_16)} 处")
    print(f"  as int32 (4 字节): {len(offsets_32)} 处")
    print(f"  去重后不同偏移数: {len(all_offsets)} 处")
    print()

    print("========== 所有出现位置（文件偏移，十六进制）==========")
    for i, off in enumerate(all_offsets):
        is_16 = off in offsets_16
        is_32 = off in offsets_32
        tag = []
        if is_16:
            tag.append("int16")
        if is_32:
            tag.append("int32")
        # 若偏移-2 也在 int32 里，说明这里可能是某个 int32 的高 16 位，仅作参考
        print(f"  {i+1:4d}. 偏移 0x{off:08X} ({off:10d})  可能: {', '.join(tag)}")
    print()

    # 简要分段提示（dat 大致结构：头部、unit_headers、civs*units 等，无法精确到字段，仅作区间参考）
    if all_offsets:
        print("========== 前 20 处与后 10 处上下文（前后各 4 字节，十六进制）==========")
        for idx, off in enumerate(all_offsets[:20]):
            lo = max(0, off - 4)
            hi = min(size, off + 6)
            snippet = raw[lo:hi].hex(" ")
            print(f"  偏移 0x{off:08X}: ... {snippet} ...")
        if len(all_offsets) > 20:
            print("  ...")
            for idx, off in enumerate(all_offsets[-10:], start=len(all_offsets) - 10):
                lo = max(0, off - 4)
                hi = min(size, off + 6)
                snippet = raw[lo:hi].hex(" ")
                print(f"  偏移 0x{off:08X}: ... {snippet} ...")


if __name__ == "__main__":
    main()
