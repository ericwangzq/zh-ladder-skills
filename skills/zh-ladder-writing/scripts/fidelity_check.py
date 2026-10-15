#!/usr/bin/env python3
"""对比原文和改写稿，提示可能丢失或走样的信息。

用法：python3 fidelity_check.py 原文文件 新稿文件 [--summary]

检查四类东西：
1. 原文里的数字（连同单位）在新稿里还在不在；数字还在但单位变了（如「12 个百分点」变成「12%」）。
2. 原文里带「预计」「约」「尚未」等限定的数字，在新稿里是否丢了限定，变成了确定的说法。
3. 确定程度词、条件和例外词、否定词、归属和状态词：原文有、新稿没有的；新稿新冒出来的。
4. 原文没有、新稿里出现的数字（可能是编造或算错）。

这只是提醒，不是判决。摘要本来就会省略一些数字，加 --summary 时只把数字缺失当作参考。
零依赖，Python 3.9 及以上（未在更低版本验证）。
"""
import re
import sys
from collections import Counter

FULLWIDTH = str.maketrans("０１２３４５６７８９．％", "0123456789.%")

UNITS = [
    "个百分点", "百分点", "%", "‰", "万元", "亿元", "元", "万", "亿", "千",
    "人次", "人", "家", "条", "个", "项", "份", "次", "件", "台", "张", "页", "字",
    "天", "日", "周", "个月", "月", "年", "小时", "分钟", "秒", "毫秒", "ms", "s",
    "GB", "MB", "TB", "KB", "QPS", "TPS", "倍", "岁", "公里", "米", "层", "级", "档", "号",
]
UNIT_RE = "|".join(sorted((re.escape(u) for u in UNITS), key=len, reverse=True))
NUM_RE = re.compile(r"(?<![A-Za-z_])(\d+(?:\.\d+)?)\s*(" + UNIT_RE + r")?")

HEDGES = ["预计", "预估", "估算", "估计", "初步", "大约", "约", "左右", "可能", "或许",
          "也许", "尚未", "未经", "未验证", "未确认", "待定", "暂定", "推测", "理论上", "预期", "目标"]
CONDITIONS = ["如果", "若", "假如", "除非", "只有", "仅当", "仅限", "仅", "前提", "否则",
              "例外", "除外", "不包括", "不含", "以内", "以上", "以下", "至少", "至多",
              "不超过", "不少于", "不低于", "不高于", "之一", "同时满足", "任一"]
NEGATIONS = ["不得", "不能", "不应", "不可", "无需", "不必", "没有", "不是", "禁止", "不予", "不再", "未"]
ATTRIBUTION = ["据称", "称", "认为", "表示", "建议", "拟", "计划", "提议", "倾向", "同意",
               "反对", "决定", "未决", "已完成", "已验证", "部分完成", "失败", "阻塞"]

HEDGE_WINDOW_BEFORE = 10
HEDGE_WINDOW_AFTER = 6


# 「约」在这些词里不是约数：条约、预约、约定、约束、契约、节约、约谈
FAKE_YUE = re.compile(r"(?:条|预|契|节|制|特|签|违|履|邀|如)约|约(?:定|束|谈|见|稿|请|款)")
# 不当作数量比较的数字：时刻 13:50、多级编号 4.1.2、日期 2026-10-12、
# 行首的条款编号「4.1 」、条款引用「第 12.2 条」
SKIP_RE = re.compile(
    r"\d{1,2}:\d{2}|\d+(?:\.\d+){2,}|\d{4}-\d{1,2}-\d{1,2}"
    r"|(?m:^[\s>*#-]*\d+(?:\.\d+)+(?=\s))|第\s*\d+(?:\.\d+)*\s*[条款章节项]"
)


def load(path):
    with open(path, encoding="utf-8") as f:
        text = f.read().translate(FULLWIDTH)
    # 去掉数字里的千位分隔符：3,412 → 3412
    return re.sub(r"(?<=\d),(?=\d{3}\b)", "", text)


def mask_fake_yue(text):
    return FAKE_YUE.sub(lambda m: m.group(0).replace("约", "\u25a1"), text)


def char_count(path):
    """汉字、字母、数字、标点都算；空白和 Markdown 符号不算。"""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    text = re.sub(r"[\s#*|`>_~\-]", "", text)
    return len(text)


def numbers(text):
    """返回 [(数字, 单位, 起点, 终点)]。"""
    out = []
    skip = [(m.start(), m.end()) for m in SKIP_RE.finditer(text)]
    for m in NUM_RE.finditer(text):
        if any(a <= m.start() < b for a, b in skip):
            continue
        num = m.group(1)
        if "." in num:
            num = num.rstrip("0").rstrip(".")
        out.append((num, m.group(2) or "", m.start(), m.end()))
    return out


def hedged(text, start, end):
    window = mask_fake_yue(text[max(0, start - HEDGE_WINDOW_BEFORE - 2): end + HEDGE_WINDOW_AFTER + 2])
    return [h for h in HEDGES if h in window]


def count_terms(text, terms):
    c = Counter()
    text = mask_fake_yue(text)
    for t in terms:
        c[t] = text.count(t)
    return c


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    summary = "--summary" in argv
    if len(args) != 2:
        print(__doc__)
        return 2
    src, new = load(args[0]), load(args[1])
    src_nums, new_nums = numbers(src), numbers(new)
    new_by_num = {}
    for num, unit, s, e in new_nums:
        new_by_num.setdefault(num, []).append((unit, s, e))

    missing, unit_changed, lost_hedge = [], [], []
    seen = set()
    for num, unit, s, e in src_nums:
        key = (num, unit)
        if key in seen:
            continue
        seen.add(key)
        hits = new_by_num.get(num)
        ctx = src[max(0, s - 8): e + 4].replace("\n", " ")
        if not hits:
            missing.append(f"{num}{unit}  ←「{ctx}」")
            continue
        # 只在新稿给了「另一个」单位时提示；表格里省掉量词（312 条 → 312）不算
        if unit and all(u and u != unit for u, _, _ in hits):
            units = "、".join(sorted({u for u, _, _ in hits}))
            unit_changed.append(f"{num}{unit} → 新稿里写作 {num}{units}  ←「{ctx}」")
        src_h = hedged(src, s, e)
        if src_h and not any(hedged(new, hs, he) for _, hs, he in hits):
            lost_hedge.append(f"{num}{unit}：原文带「{'、'.join(src_h)}」，新稿附近没有限定词  ←「{ctx}」")

    src_set = {n for n, _, _, _ in src_nums}
    invented = sorted({f"{n}{u}" for n, u, _, _ in new_nums if n not in src_set})

    print("== 保真对比 ==")
    n_new, n_src = char_count(args[1]), char_count(args[0])
    ratio = f"，是原文（{n_src} 字）的 {n_new / n_src:.0%}" if n_src else ""
    print(f"新稿字数：{n_new}{ratio}（汉字、字母、数字、标点都算；空白和 Markdown 符号不算）")
    label = "（摘要模式：数字缺失仅供参考）" if summary else ""
    print(f"\n[数字缺失] {len(missing)} 处{label}")
    if summary:
        print("  （摘要会有意省略数字，这里不逐条列出；重点看下面的单位、确定程度、条件和否定）")
    else:
        for x in missing:
            print("  -", x)
    print(f"\n[单位可能变了] {len(unit_changed)} 处")
    for x in unit_changed:
        print("  -", x)
    print(f"\n[可能被说成确定] {len(lost_hedge)} 处")
    for x in lost_hedge:
        print("  -", x)
    print(f"\n[原文没有的数字] {len(invented)} 个（可能是换算、合计，也可能是编造或算错）")
    if invented:
        print("  -", "、".join(invented))

    for name, terms in (("确定程度词", HEDGES), ("条件和例外词", CONDITIONS),
                        ("否定词", NEGATIONS), ("归属和状态词", ATTRIBUTION)):
        a, b = count_terms(src, terms), count_terms(new, terms)
        gone = [t for t in terms if a[t] and not b[t]]
        added = [t for t in terms if b[t] and not a[t]]
        print(f"\n[{name}] 原文有、新稿没有：{'、'.join(gone) or '无'}；新稿新出现：{'、'.join(added) or '无'}")

    print("\n逐条判断：有意省略的跳过；丢了的补回；新出现的确认原文有依据。")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
