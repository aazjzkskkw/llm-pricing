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

# 挑的是名气大、还在更新的那些。字段说明：
#   f 文件名 / name 展示名 / cat 分类 / short 总览表的列名 / desc 说明
#   col 分数列（不填就按 SCORE_COLS 猜）/ pct 分数是 0~1 需要乘 100
#   unit 分数列的单位后缀 / ov 是否进总览矩阵
EPOCH_BOARDS = [
    {"f": "epoch_capabilities_index.csv", "name": "ECI 综合能力指数", "cat": "综合",
     "short": "ECI", "col": "ECI Score", "pct": False, "unit": "分", "ov": True,
     "desc": "Epoch AI 依据数十个基准的成绩拟合出的综合能力指数，无固定上限，"
             "用于跨代际比较模型的整体能力水平。"},
    {"f": "metr_time_horizons_external.csv", "name": "METR 任务时长", "cat": "综合",
     "short": "METR", "col": "Time horizon", "pct": False, "unit": "分钟", "ov": True,
     "desc": "时间视野指标：模型以 50% 成功率完成的任务，人类专家所需分钟数。"
             "数值越大表示可独立完成的任务链越长。"},
    {"f": "gdpval_external.csv", "name": "GDPval 真实职业任务", "cat": "综合",
     "short": "GDPval", "col": "Win Rate (%)", "pct": True, "unit": "%", "ov": False,
     "desc": "覆盖 44 个行业的真实工作交付物，由业内专家盲评模型产出与人类产出，分数为模型胜出比例。"},

    {"f": "swe_bench_verified.csv", "name": "SWE-Bench Verified", "cat": "编程与 Agent",
     "short": "SWE-B", "pct": True, "unit": "%", "ov": True,
     "desc": "500 个经人工核验的真实 GitHub issue，模型提交的补丁需通过项目自带测试。"},
    {"f": "deepswe_external.csv", "name": "DeepSWE · Agent 修 bug", "cat": "编程与 Agent",
     "short": "DeepSWE", "col": "Pass@1", "pct": True, "unit": "%", "ov": True,
     "desc": "基于 mini-swe-agent 框架执行真实软件工程任务，每题运行四次。Pass@1 为单次通过率，"
             "Pass@4 为四次中至少一次通过。含每题平均成本，可评估性价比。"},
    {"f": "terminalbench_external.csv", "name": "Terminal-Bench · 终端 Agent",
     "cat": "编程与 Agent", "short": "T-Bench", "col": "Accuracy mean", "pct": True,
     "unit": "%", "ov": True,
     "desc": "在真实终端环境中完成配置、执行与调试任务，考察 Agent 能力而非单轮问答。"
             "同一模型搭配不同 Agent 框架，成绩差异较大。"},
    {"f": "aider_polyglot_external.csv", "name": "Aider Polyglot · 代码编辑",
     "cat": "编程与 Agent", "short": "Aider", "col": "Percent correct", "pct": False,
     "unit": "%", "ov": True,
     "desc": "225 道 Exercism 多语言编程题，考察修改代码并通过测试的能力。上游更新频率较低。"},
    {"f": "webdev_arena_external.csv", "name": "WebDev Arena · 前端对战",
     "cat": "编程与 Agent", "short": "WebDev", "col": "Arena Score", "pct": False,
     "unit": "Elo", "ov": True,
     "desc": "两个模型分别生成网页应用，由真人投票比较优劣，按 Elo 排名。"},
    {"f": "cybench_external.csv", "name": "Cybench · 安全 CTF", "cat": "编程与 Agent",
     "short": "Cybench", "col": "Unguided % Solved", "pct": True, "unit": "%", "ov": False,
     "desc": "无提示条件下独立解出 CTF 题目的比例，考察渗透与漏洞利用的实操能力。"},

    {"f": "frontiermath_tiers_1_3_v2.csv", "name": "FrontierMath · 前沿数学",
     "cat": "数学与推理", "short": "FMath", "pct": True, "unit": "%", "ov": True,
     "desc": "Epoch AI 自建的未公开数学题库，难度覆盖竞赛级至科研级，用于规避训练集污染。"},
    {"f": "otis_mock_aime_2024_2025.csv", "name": "AIME 模拟卷", "cat": "数学与推理",
     "short": "AIME", "pct": True, "unit": "%", "ov": True,
     "desc": "OTIS 编制的 AIME 模拟题，难度对应美国高中数学邀请赛，为常用数学基准之一。"},
    {"f": "arc_agi_2_external.csv", "name": "ARC-AGI-2 · 抽象推理",
     "cat": "数学与推理", "short": "ARC-2", "col": "Score", "pct": True, "unit": "%",
     "ov": True,
     "desc": "依据少量图形变换示例归纳规则，考察抽象归纳推理，不依赖知识储备。"},
    {"f": "arc_agi_external.csv", "name": "ARC-AGI-1", "cat": "数学与推理",
     "short": "ARC-1", "col": "Score", "pct": True, "unit": "%", "ov": False,
     "desc": "ARC-AGI 第一版，多数前沿模型已接近饱和，可用于观察趋势。"},
    {"f": "simplebench_external.csv", "name": "SimpleBench · 常识陷阱",
     "cat": "数学与推理", "short": "Simple", "col": "Score (AVG@5)", "pct": False,
     "unit": "%", "ov": False,
     "desc": "人类直觉简单但模型易错的常识与时空推理题，人类平均分高于多数模型。"},

    {"f": "gpqa_diamond.csv", "name": "GPQA Diamond · 科学推理", "cat": "知识与事实",
     "short": "GPQA", "pct": True, "unit": "%", "ov": True,
     "desc": "研究生级物理、化学、生物多选题，题目经过防检索设计。随机作答基准 25%。"},
    {"f": "hle_external.csv", "name": "HLE · 人类最后考试", "cat": "知识与事实",
     "short": "HLE", "col": "Accuracy", "pct": True, "unit": "%", "ov": True,
     "desc": "Humanity's Last Exam：覆盖上百个学科的专家级难题，为当前难度最高的知识类基准之一。"},
    {"f": "simpleqa_verified.csv", "name": "SimpleQA Verified · 事实准确率",
     "cat": "知识与事实", "short": "SimpleQA", "pct": True, "unit": "%", "ov": True,
     "desc": "短事实问答，考察知识准确性及不确定时是否编造答案。"},
    {"f": "scicode_external.csv", "name": "SciCode · 科研代码", "cat": "知识与事实",
     "short": "SciCode", "col": "Score", "pct": True, "unit": "%", "ov": False,
     "desc": "将科研论文中的方法实现为可运行代码，考察科学理解与编程能力的结合。"},
]

# 分数列没指定时按这个顺序猜（Epoch 各 benchmark 列名不统一）
SCORE_COLS = ["Best score (across scorers)", "mean_score", "Score", "Accuracy",
              "Accuracy mean", "Pass@1", "Pass@1 score", "Main score",
              "Score (AVG@5)", "Mean score", "Binary accuracy", "ECI Score",
              "Arena Score", "Percent correct", "Unguided % Solved", "Win Rate (%)",
              "Time horizon", "average_score"]

# 同一模型会按推理强度分成多条记录，两种写法都有：" (max)" 和 "_high"。
# 注意别用 \b 卡前缀，正则里 _ 也算单词字符，"_high" 前面没有词边界。
EFFORT_SUFFIX = r"[\s_]\(?(?:max|xhigh|high|medium|low|unknown|minimal)\)?$"


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "llm-pricing/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def rows_of(z: zipfile.ZipFile, name: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(z.read(name).decode("utf-8"))))


def _num(v) -> float | None:
    try:
        return round(float(v), 3)
    except (TypeError, ValueError):
        return None


def _pct(v, pct) -> float | None:
    n = _num(v)
    return None if n is None else round(n * 100 if pct else n, 1)


def epoch_board(z: zipfile.ZipFile, fname: str, score_col: str,
                pct: bool) -> list[dict]:
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
        if pct:                   # 原始值是 0~1 的比例，转成百分数
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
            "agent": (r.get("Agent") or r.get("Harness") or "").strip() or None,
            # 这两列只有部分榜单有，有就带上（DeepSWE 的四次通过率和每题成本）
            "pass4": _pct(r.get("Pass@4"), pct),
            "cost": _num(r.get("Mean cost (USD)")),
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


OV_IDS = {c["f"].removesuffix(".csv") for c in EPOCH_BOARDS if c.get("ov")}
OV_MIN = 3          # 至少在这么多张榜上出现才进总览，免得一行全是空格


def overview(boards: list[dict]) -> dict:
    """把主要榜单横过来拼一张矩阵：一行一个模型，一列一张榜。
    这是「谁强」最直观的看法，也省得逐张榜点。"""
    picked = [b for b in boards if b["id"] in OV_IDS]
    rows: dict[str, dict] = {}
    for b in picked:
        for r in b["rows"]:
            # 各榜写法不一（ECI 用 "Claude Fable 5"，别的用 "claude-fable-5"），
            # 归一后再拼，否则同一个模型会裂成好几行
            k = re.sub(r"[^a-z0-9]+", "-", r["model"].lower()).strip("-")
            row = rows.setdefault(k, {"model": r["model"], "org": r.get("org", ""),
                                      "released": r.get("released"), "n": 0})
            if " " in r["model"] and " " not in row["model"]:
                row["model"] = r["model"]      # 带空格的是展示名，更好看
            if row.get(b["short"]) is None:
                row[b["short"]] = r["score"]
                row["n"] += 1
            if not row.get("org"):
                row["org"] = r.get("org", "")
            if not row.get("released"):
                row["released"] = r.get("released")
    keep = [r for r in rows.values() if r["n"] >= OV_MIN]
    for r in keep:
        r["old"] = bool(r.get("released") and r["released"] < AGE_CUTOFF)
    # 按 ECI 排，没 ECI 的按上榜数量兜底
    keep.sort(key=lambda r: (-(r.get("ECI") or -1), -r["n"]))
    return {
        "id": "overview", "name": "总览 · 跨榜单对比", "cat": "综合",
        "short": "总览",
        "desc": "各榜单横向汇总，一行一个模型，默认按 ECI 综合分排序。"
                "空格表示该模型未上榜；点击列名可按单项成绩排序。",
        "source": "Epoch AI", "url": "https://epoch.ai/benchmarks",
        # 第一列是 ECI，前端默认按第一列排，这样打开就是按综合能力从强到弱
        "cols": ([{"k": b["short"], "t": f"{b['short']} {b['unit_short']}".strip(),
                   "num": True, "pct": b["unit"] == "%"} for b in picked]
                 + [{"k": "n", "t": "上榜数", "num": True},
                    {"k": "org", "t": "厂商"}]),
        "rows": keep,
    }


def main() -> None:
    z = zipfile.ZipFile(io.BytesIO(get(EPOCH_ZIP)))
    meta = {m["source_file"]: m for m in rows_of(z, "benchmark_metadata.csv")}

    boards = []
    for cfg in EPOCH_BOARDS:
        if cfg["f"] not in z.namelist():
            print(f"   跳过 {cfg['f']}：上游这次没给这个文件")
            continue
        rows = epoch_board(z, cfg["f"], cfg.get("col", ""), cfg.get("pct", True))
        if not rows:
            continue
        cols = [{"k": "score", "t": f"分数 {cfg['unit']}".strip(), "num": True,
                 "pct": cfg["unit"] == "%"},
                {"k": "org", "t": "厂商"}]
        if any(r.get("pass4") is not None for r in rows):
            cols.insert(1, {"k": "pass4", "t": "Pass@4 %", "num": True, "pct": True})
        if any(r["agent"] for r in rows):
            cols.append({"k": "agent", "t": "Agent 框架"})
        if any(r.get("cost") is not None for r in rows):
            cols.append({"k": "cost", "t": "每题成本 $", "num": True})
        boards.append({
            "id": cfg["f"].removesuffix(".csv"), "name": cfg["name"],
            "desc": cfg["desc"], "cat": cfg["cat"], "short": cfg["short"],
            "unit": cfg["unit"],
            "unit_short": "" if cfg["unit"] == "%" else cfg["unit"],
            "source": "Epoch AI", "url": "https://epoch.ai/benchmarks",
            "cols": cols, "rows": rows,
        })

    boards.append({
        "id": "hallucination", "name": "Vectara · 幻觉率",
        "desc": "对同一批文档生成摘要，由事实一致性模型判定是否存在编造内容。幻觉率越低越好。",
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

    boards.insert(0, overview(boards))

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
