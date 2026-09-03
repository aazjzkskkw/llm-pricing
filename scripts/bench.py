"""把开源评测榜单归一成 data/bench.json 供 bench.html 渲染。不自己跑评测。

主源是 Epoch AI 的 AI Benchmarking Hub（epoch.ai/benchmarks），一个 zip 里几十个
benchmark 的原始成绩，CC-BY 授权，每天更新，模型发布日期也是现成的。
另外保留 Vectara 幻觉榜，那是 Epoch 没覆盖的维度。

跑之前先跑 update.py：Vectara 那张榜要读 data/models.json 里的发布日期判断模型新旧。

Usage: python scripts/bench.py
"""

import csv
import io
import json
import re
import time
import urllib.request
import zipfile
from pathlib import Path

EPOCH_ZIP = "https://epoch.ai/data/benchmark_data.zip"
VECTARA = ("https://cdn.jsdelivr.net/gh/vectara/hallucination-leaderboard"
           "@main/README.md")

DATA = Path(__file__).resolve().parent.parent / "data"
OUT = DATA / "bench.json"

TODAY = time.strftime("%Y-%m-%d")
AGE_CUTOFF = f"{int(TODAY[:4]) - 2}{TODAY[4:]}"

# 从 Epoch 那几十个 benchmark 里挑的：覆盖面不重复、数据还在更新、结果看得懂。
# (文件名, 展示名, 说明) —— 分数列和量纲从 benchmark_metadata.csv 里读，不写死。
EPOCH_BOARDS = [
    ("epoch_capabilities_index.csv", "ECI 综合能力指数",
     "Epoch AI 把几十个 benchmark 的成绩拟合成一个综合分，用来跨代际比模型总体能力，"
     "分数没有上限、越高越强。想一眼看谁最强就看这个。"),
    ("gpqa_diamond.csv", "GPQA Diamond · 科学推理",
     "博士级物理、化学、生物选择题，网上搜不到答案的那种。随机猜是 25%。"),
    ("swe_bench_verified.csv", "SWE-Bench Verified · 真实修 bug",
     "500 个从 GitHub 真实 issue 里人工筛出来的 Python bug，改完要跑过项目自己的测试。"),
    ("terminalbench_external.csv", "Terminal-Bench · 终端 Agent",
     "把模型丢进真终端里干活：装环境、跑脚本、调试。考的是 agent 能力不是单轮问答，"
     "所以同一个模型换不同 agent 框架分数会差很多。"),
    ("frontiermath_tiers_1_3_v2.csv", "FrontierMath · 前沿数学",
     "Epoch 自己攒的未公开数学题，难度从奥赛到研究生科研级，专门防训练集污染。"),
    ("simpleqa_verified.csv", "SimpleQA Verified · 事实准确率",
     "短事实问答，考的是模型知不知道、以及不知道时会不会硬编。"),
    ("arc_agi_2_external.csv", "ARC-AGI-2 · 抽象推理",
     "看几个图形变换例子推规律，人类容易机器难，纯考归纳推理不考知识量。"),
    ("simplebench_external.csv", "SimpleBench · 常识陷阱",
     "人类觉得简单、模型容易翻车的常识和时空推理题，普通人平均分远高于多数模型。"),
]

# 分数列的候选名，按优先级找（Epoch 各 benchmark 的列名不统一）
SCORE_COLS = ["Best score (across scorers)", "mean_score", "Score", "Accuracy",
              "Accuracy mean", "Pass@1", "Pass@1 score", "Main score",
              "Score (AVG@5)", "Mean score", "Binary accuracy", "ECI Score"]

# 同一模型会按推理强度分成多条记录，两种写法都有：" (max)" 和 "_high"。
# 注意别用 \b 卡前缀，正则里 _ 也算单词字符，"_high" 前面没有词边界。
EFFORT_SUFFIX = r"[\s_]\(?(?:max|xhigh|high|medium|low|unknown|minimal)\)?$"


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "llm-pricing/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def rows_of(z: zipfile.ZipFile, name: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(z.read(name).decode("utf-8"))))


def epoch_board(z: zipfile.ZipFile, fname: str, score_col: str,
                scale: float | None) -> list[dict]:
    """一个 benchmark 的 csv → 榜单行。同一模型有多档推理强度时只留最高分。"""
    best: dict[str, dict] = {}
    for r in rows_of(z, fname):
        raw = next((r[c] for c in ([score_col] + SCORE_COLS)
                    if r.get(c) not in (None, "")), None)
        if raw is None:
            continue
        try:
            score = float(raw)
        except ValueError:
            continue
        if scale == 1.0:          # 0~1 的比例，转成百分数；ECI 那种无量纲分数不动
            score *= 100
        name = (r.get("Display name") or r.get("Name") or r.get("Model name")
                or r.get("Model version") or "").strip()
        if not name:
            continue
        # 推理档位后缀（"Claude Fable 5 (max)"、"gemini-3.7-flash_high"）去掉，
        # 同一模型合并只留最高分
        name = re.sub(EFFORT_SUFFIX, "", name, flags=re.I).strip()
        released = (r.get("Release date") or "").strip() or None
        cur = best.get(name)
        if cur and cur["score"] >= round(score, 1):
            continue
        best[name] = {
            "model": name,
            "score": round(score, 1),
            "org": (r.get("Organization") or r.get("Model Org") or "").strip(),
            "agent": (r.get("Agent") or "").strip() or None,
            "released": released,
            "old": bool(released and released < AGE_CUTOFF),
        }
    return sorted(best.values(), key=lambda x: -x["score"])


def released_map() -> dict[str, str]:
    """Vectara 那张榜没有发布日期，从价格数据里借。"""
    out = {}
    try:
        models = json.loads((DATA / "models.json").read_text(encoding="utf-8"))["models"]
    except FileNotFoundError:
        return out
    for m in models:
        if m.get("released"):
            out.setdefault(re.sub(r"[^a-z0-9.]", "", m["model"].split("/")[-1].lower()),
                           m["released"])
    return out


def match_release(model: str, rel: dict[str, str]) -> str | None:
    m = re.search(r"(20\d{2})-?(\d{2})-?(\d{2})", model)
    if m:
        return "%s-%s-%s" % m.groups()
    key = re.sub(r"\(.*?\)|[^a-z0-9./]", "", model.lower()).split("/")[-1]
    while key:
        if key in rel:
            return rel[key]
        if "-" not in key:
            return None
        key = key.rsplit("-", 1)[0]
    return None


def vectara_board(rel: dict[str, str]) -> list[dict]:
    rows = []
    for line in get(VECTARA).decode("utf-8").splitlines():
        if not line.startswith("|") or line.startswith(("|-", "|Model")):
            continue
        c = [x.strip() for x in line.strip("|").split("|")]
        if len(c) < 5:
            continue
        try:
            hall, fact, ans, words = (float(re.sub(r"[^\d.]", "", x)) for x in c[1:5])
        except ValueError:
            continue
        released = match_release(c[0], rel)
        rows.append({"model": c[0], "hall": hall, "fact": fact, "answer": ans,
                     "words": words, "released": released,
                     "old": bool(released and released < AGE_CUTOFF)})
    return sorted(rows, key=lambda r: r["hall"])


SCORE_TITLE = {"ECI 综合能力指数": "ECI 分"}


def main() -> None:
    z = zipfile.ZipFile(io.BytesIO(get(EPOCH_ZIP)))
    meta = {m["source_file"]: m for m in rows_of(z, "benchmark_metadata.csv")}

    boards = []
    for fname, name, desc in EPOCH_BOARDS:
        if fname not in z.namelist():
            print(f"   跳过 {fname}：上游这次没给这个文件")
            continue
        m = meta.get(fname, {})
        # 有 metadata 且 scale=1 的是 0~1 比例分；ECI 不在 metadata 里，分数原样用
        try:
            scale = float(m["scale"]) if m.get("scale") else None
        except ValueError:
            scale = None
        rows = epoch_board(z, fname, m.get("score_column", ""), scale)
        if not rows:
            continue
        cols = [{"k": "score", "t": SCORE_TITLE.get(name, "分数 %"), "num": True},
                {"k": "org", "t": "厂商"}]
        if any(r["agent"] for r in rows):
            cols.append({"k": "agent", "t": "Agent 框架"})
        boards.append({
            "id": fname.removesuffix(".csv"), "name": name, "desc": desc,
            "source": "Epoch AI", "url": "https://epoch.ai/benchmarks",
            "cols": cols, "rows": rows,
        })

    boards.append({
        "id": "hallucination", "name": "Vectara · 幻觉率",
        "desc": "让模型给同一批文档写摘要，再用事实一致性模型判断有没有编造内容。幻觉率越低越好。",
        "source": "Vectara",
        "url": "https://github.com/vectara/hallucination-leaderboard",
        "cols": [
            {"k": "hall", "t": "幻觉率 %", "num": True, "asc": True},
            {"k": "fact", "t": "事实一致 %", "num": True},
            {"k": "answer", "t": "作答率 %", "num": True},
            {"k": "words", "t": "摘要平均字数", "num": True},
        ],
        "rows": vectara_board(released_map()),
    })

    for b in boards:
        dates = [r["released"] for r in b["rows"] if r.get("released")]
        b["latest"] = max(dates) if dates else None   # 榜单里最新的模型有多新
        b["old_count"] = sum(1 for r in b["rows"] if r.get("old"))
    OUT.write_text(json.dumps({
        "updated_at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
        "cutoff": AGE_CUTOFF,
        "credit": ("Epoch AI, 'AI Benchmarking Hub', epoch.ai/benchmarks, "
                   "CC-BY 4.0"),
        "boards": boards,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("OK: " + " | ".join(
        f"{b['name'][:14]} {len(b['rows'])}行 最新{b['latest']}" for b in boards)
        + f"\n-> {OUT}")


if __name__ == "__main__":
    main()
