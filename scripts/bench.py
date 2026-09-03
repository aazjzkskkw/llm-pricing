"""拉取几个开源评测榜单，统一成 data/bench.json 供 bench.html 渲染。

来源都是各项目仓库里公开的结果数据，不自己跑评测：
  - Aider polyglot / refactor 榜（代码编辑能力）
  - Vectara 幻觉率榜（摘要事实一致性）

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
AIDER_REFACTOR = f"{CDN}/Aider-AI/aider@main/aider/website/_data/refactor_leaderboard.yml"
VECTARA = f"{CDN}/vectara/hallucination-leaderboard@main/README.md"

OUT = Path(__file__).resolve().parent.parent / "data" / "bench.json"


def get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "llm-pricing/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8")


def aider_board(url: str, score_key: str) -> list[dict]:
    rows = []
    for e in yaml.safe_load(get(url)) or []:
        score = e.get(score_key)
        if not e.get("model") or score is None:
            continue
        cost = e.get("total_cost")
        rows.append({
            "model": e["model"],
            "score": round(float(score), 1),
            "wellformed": (round(float(e["percent_cases_well_formed"]), 1)
                           if e.get("percent_cases_well_formed") is not None else None),
            "format": e.get("edit_format"),
            "cost": round(float(cost), 2) if cost else None,
            "date": str(e.get("date") or ""),
        })
    rows.sort(key=lambda r: -r["score"])
    return rows


def vectara_board() -> list[dict]:
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
        rows.append({"model": c[0], "hall": hall, "fact": fact,
                     "answer": ans, "words": words})
    rows.sort(key=lambda r: r["hall"])
    return rows


def main() -> None:
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
            "rows": aider_board(AIDER_POLYGLOT, "pass_rate_2"),
        },
        {
            "id": "refactor",
            "name": "Aider Refactor · 大文件重构",
            "desc": "89 个大型 Python 文件重构任务，专门考模型会不会偷懒省略代码（写 “... 此处省略”）。",
            "source": "Aider",
            "url": "https://aider.chat/docs/leaderboards/refactor.html",
            "cols": [
                {"k": "score", "t": "正确率 %", "num": True},
                {"k": "wellformed", "t": "格式正确 %", "num": True},
                {"k": "format", "t": "编辑格式"},
                {"k": "date", "t": "测试日期"},
            ],
            "rows": aider_board(AIDER_REFACTOR, "pass_rate_1"),
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
            "rows": vectara_board(),
        },
    ]
    OUT.write_text(json.dumps({
        "updated_at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
        "boards": boards,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("OK: " + ", ".join(f"{b['id']}={len(b['rows'])}" for b in boards) + f" -> {OUT}")


if __name__ == "__main__":
    main()
