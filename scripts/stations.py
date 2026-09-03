"""公益站/中转站名单。数据取自社区维护的目录站 ytzzjx.github.io，
它是这块更新最勤的一份，没必要自己再攒一遍。

这里只做三件事：把条目结构化、去掉链接里的邀请码、按可用状态归类。
输出 data/stations.json 给 free.html 用。

Usage: python scripts/stations.py
"""

import json
import re
import time
import urllib.request
from pathlib import Path

SRC = "https://ytzzjx.github.io/app.js"
CREDIT = "https://ytzzjx.github.io/"

OUT = Path(__file__).resolve().parent.parent / "data" / "stations.json"

FIELDS = ("publishedAt", "kind", "name", "summary", "registration",
          "signupBonus", "dailyCheckin", "models", "caveat", "url")

# 上游把状态写在 kind 和 caveat 的自然语言里，这里归成四档方便排序和标色
STATUS_RULES = [
    ("stopped", r"暂停注册|停止注册|已关站|跑路"),
    ("avoid", r"不建议|谨慎|被清空|清理.*账号"),
    ("watch", r"不可用|调不通|观察|待核实|新站|待确认"),
]


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "llm-pricing/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "ignore")


def field(block: str, key: str) -> str:
    m = re.search(key + r':\s*\n?\s*"((?:[^"\\]|\\.)*)"', block)
    return re.sub(r"\\(.)", r"\1", m.group(1)).strip() if m else ""


def clean_url(url: str) -> str:
    """去掉别人的推广参数，只留站点入口。"""
    url = re.sub(r"[?&](aff|ref|invite_code|invitation_code)=[^&]*", "", url, flags=re.I)
    return url.rstrip("?&")


# 分类口径（用户定义）：
#   公益站 = 不能充钱，只有注册赠送和签到额度
#   中转站 = 能充钱的第三方反代，多数基于 new-api / sub2api，卖得比官方便宜
# 上游那份目录本身就是「公益中转分享」，绝大多数是公益/羊毛站，所以
# 默认按公益算，只有出现明确的付费证据才归到中转 —— 反过来默认会把
# AnyRouter 这种只能签到、不能充值的误判成中转。
CHARITY_TAG = re.compile(r"公益")
PAID_TAG = re.compile(r"付费|老牌中转|多上游聚合|一分钱")
NEG_PAY = re.compile(r"(?:未见|没有|不能|不支持|暂无|无)\s*(?:充值|付费)")
PAY_WORD = re.compile(r"充值\s*1\s*:\s*1|可充值|充值入口|按量计费|自费|购买额度|下单")


def kind_of(name: str, kind: str, body: str) -> str:
    tag = f"{name} {kind}"
    if CHARITY_TAG.search(tag):
        return "charity"
    if PAID_TAG.search(tag):
        return "paid"
    if NEG_PAY.search(body):
        return "charity"
    return "paid" if PAY_WORD.search(body) else "charity"


def status_of(text: str) -> str:
    for name, pat in STATUS_RULES:
        if re.search(pat, text):
            return name
    return "open"


def parse(js: str) -> list[dict]:
    rows = []
    for b in re.findall(r"\{\s*publishedAt:.*?\n\s*\},", js, flags=re.S):
        r = {k: field(b, k) for k in FIELDS}
        if not (r["name"] and r["url"]):
            continue
        rows.append({
            "name": r["name"],
            "url": clean_url(r["url"]),
            "kind": r["kind"],
            "summary": r["summary"],
            "signup": r["signupBonus"],
            "checkin": r["dailyCheckin"],
            "models": r["models"],
            "entry": r["registration"],
            "caveat": r["caveat"],
            "updated": r["publishedAt"][:10],
            "status": status_of(f"{r['kind']} {r['caveat']}"),
            "type": kind_of(r["name"], r["kind"],
                            f"{r['summary']} {r['caveat']} {r['registration']}"),
        })
    order = {"open": 0, "watch": 1, "avoid": 2, "stopped": 3}
    rows.sort(key=lambda x: (order[x["status"]], x["updated"]), reverse=False)
    rows.sort(key=lambda x: (order[x["status"]], -int(x["updated"].replace("-", ""))))
    return rows


def main() -> None:
    rows = parse(fetch(SRC))
    if not rows:
        # 上游改了写法就直接失败，别把已有数据清空
        raise SystemExit("没解析到任何条目，上游格式可能变了，保留旧数据")
    OUT.write_text(json.dumps({
        "updated_at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
        "credit": CREDIT,
        "count": len(rows),
        "stations": rows,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    n, t = {}, {}
    for r in rows:
        n[r["status"]] = n.get(r["status"], 0) + 1
        t[r["type"]] = t.get(r["type"], 0) + 1
    print(f"OK: {len(rows)} 个站点 状态{n} 类型{t} -> {OUT}")


if __name__ == "__main__":
    main()
