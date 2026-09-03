"""拉取几个开源评测榜单，统一成 data/bench.json 供 bench.html 渲染。

来源都是各项目仓库里公开的结果数据，不自己跑评测：
  - Aider polyglot 榜（代码编辑能力）
  - Vectara 幻觉率榜（摘要事实一致性）

跑之前先跑 update.py：这里要读 data/models.json 里的发布日期来判断哪些上榜模型已经过时。

Usage: python scripts/bench.py
"""

import json
import re
import time
import urllib.request
from pathlib import Path

import yaml

CDN = "https://cdn.jsdelivr.net/gh"
AIDER_POLYGLOT = f"{CDN}/Aider-AI/aider@main/aider/website/_data/polyglot_leaderboard.yml"
VECTARA = f"{CDN}/vectara/hallucination-leaderboard@main/README.md"

DATA = Path(__file__).resolve().parent.parent / "data"
OUT = DATA / "bench.json"

TODAY = time.strftime("%Y-%m-%d")
AGE_CUTOFF = f"{int(TODAY[:4]) - 2}{TODAY[4:]}"


def get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "llm-pricing/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8")


def released_map() -> dict[str, str]:
    """从价格数据里借模型发布日期，用来标注榜单上的模型有多老。"""
    out = {}
    try:
        models = json.loads((DATA / "models.json").read_text(encoding="utf-8"))["models"]
    except FileNotFoundError:
        return out
    for m in models:
        if not m.get("released"):
            continue
        key = re.sub(r"[^a-z0-9.]", "", m["model"].split("/")[-1].lower())
        out.setdefault(key, m["released"])
    return out


def match_release(model: str, rel: dict[str, str]) -> str | None:
    """榜单里的模型名写法很随意（'gpt-5 (high)'、'zai-org/GLM-4.5'），粗暴归一后匹配。"""
    m = re.search(r"(20\d{2})-?(\d{2})-?(\d{2})", model)
    if m:
        return "%s-%s-%s" % m.groups()
    key = re.sub(r"\(.*?\)|[^a-z0-9./]", "", model.lower()).split("/")[-1]
    if key in rel:
        return rel[key]
    # 榜单名常带后缀（-high、-preview、-turbo），逐段砍掉再试
    while "-" in key:
        key = key.rsplit("-", 1)[0]
        if key in rel:
            return rel[key]
    return None


def aider_board(url: str, score_key: str, rel: dict[str, str]) -> list[dict]:
    rows = []
    for e in yaml.safe_load(get(url)) or []:
        score = e.get(score_key)
        if not e.get("model") or score is None:
            continue
        cost = e.get("total_cost")
        released = match_release(e["model"], rel) or str(e.get("date") or "") or None
        rows.append({
            "model": e["model"],
            "score": round(float(score), 1),
            "wellformed": (round(float(e["percent_cases_well_formed"]), 1)
                           if e.get("percent_cases_well_formed") is not None else None),
            "format": e.get("edit_format"),
            "cost": round(float(cost), 2) if cost else None,
            "date": str(e.get("date") or ""),
            "released": released,
            "old": bool(released and released < AGE_CUTOFF),
        })
    rows.sort(key=lambda r: -r["score"])
    return rows


def vectara_board(rel: dict[str, str]) -> list[dict]:
    rows = []
    for line in get(VECTARA).splitlines():
        if not line.startswith("|") or line.startswith("|-") or line.startswith("|Model"):
            continue
        c = [x.strip() for x in line.strip("|").split("|")]
        if len(c) < 5:
            continue
        nums = [re.sub(r"[^\d.]", "", x) for x in c[1:5]]
        try:
            hall, fact, ans, words = (float(x) for x in nums)
        except ValueError:
            continue
        released = match_release(c[0], rel)
        rows.append({"model": c[0], "hall": hall, "fact": fact,
                     "answer": ans, "words": words, "released": released,
                     "old": bool(released and released < AGE_CUTOFF)})
    rows.sort(key=lambda r: r["hall"])
    return rows


def main() -> None:
    rel = released_map()
    boards = [
        {
            "id": "polyglot",
            "name": "Aider Polyglot · 代码编辑",
            "desc": "225 道 Exercism 多语言编程题，考模型改代码并让测试通过的能力。分数为两轮尝试后的正确率。",
            "source": "Aider",
            "url": "https://aider.chat/docs/leaderboards/",
            "cols": [
                {"k": "score", "t": "正确率 %", "num": True},
                {"k": "wellformed", "t": "格式正确 %", "num": True},
                {"k": "format", "t": "编辑格式"},
                {"k": "cost", "t": "跑完成本 $", "num": True},
                {"k": "date", "t": "测试日期"},
            ],
            "rows": aider_board(AIDER_POLYGLOT, "pass_rate_2", rel),
        },
        {
            "id": "hallucination",
            "name": "Vectara · 幻觉率",
            "desc": "让模型给同一批文档写摘要，再用事实一致性模型判断有没有编造内容。幻觉率越低越好。",
            "source": "Vectara",
            "url": "https://github.com/vectara/hallucination-leaderboard",
            "cols": [
                {"k": "hall", "t": "幻觉率 %", "num": True, "asc": True},
                {"k": "fact", "t": "事实一致 %", "num": True},
                {"k": "answer", "t": "作答率 %", "num": True},
                {"k": "words", "t": "摘要平均字数", "num": True},
            ],
            "rows": vectara_board(rel),
        },
    ]
    for b in boards:
        dates = [r["released"] for r in b["rows"] if r.get("released")]
        b["latest"] = max(dates) if dates else None   # 榜单里最新的模型有多新
        b["old_count"] = sum(1 for r in b["rows"] if r.get("old"))
    OUT.write_text(json.dumps({
        "updated_at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
        "cutoff": AGE_CUTOFF,
        "boards": boards,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("OK: " + ", ".join(
        f"{b['id']}={len(b['rows'])}(过时 {b['old_count']}, 最新 {b['latest']})"
        for b in boards) + f" -> {OUT}")


if __name__ == "__main__":
    main()
