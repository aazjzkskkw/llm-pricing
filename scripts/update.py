"""从开源价格数据库 LiteLLM（各厂商官网公开定价，社区维护）拉取原始数据，
归一化为统一格式供前端对比使用。本项目不自行抓取厂商官网。

Usage: python scripts/update.py
Output: data/models.json
"""

import json
import re
import time
import urllib.request
from pathlib import Path

# 国内网络 GitHub raw 直连不稳，走 jsDelivr 镜像；有条件可换回官方地址
SRC = "https://cdn.jsdelivr.net/gh/BerriAI/litellm@main/model_prices_and_context_window.json"
# 第二数据源：OpenRouter 上新最快，用于补充 LiteLLM 还没收录的最新模型
SRC_NEW = "https://openrouter.ai/api/v1/models"
# 第三、第四数据源：只用来交叉核对官方直营价，对不上的在页面上标出来
SRC_PYDANTIC = ("https://cdn.jsdelivr.net/gh/ENTERPILOT/ai-model-price-list@main"
                "/sources/pydantic_genai_prices.json")
SRC_LLMPRICES = "https://www.llm-prices.com/current-v1.json"
# 其余公开渠道，都带自家报价，用来给同一个模型凑出多个可比渠道
SRC_VERCEL = "https://ai-gateway.vercel.sh/v1/models"
SRC_NOVITA = "https://api.novita.ai/v3/openai/models"
SRC_DEEPINFRA = "https://api.deepinfra.com/models/list"

OUT = Path(__file__).resolve().parent.parent / "data" / "models.json"

VENDOR_NAMES = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "gemini": "Google",
    "google": "Google",
    "vertex_ai-language-models": "Google",
    "vertex_ai-anthropic_models": "Anthropic",
    "vertex_ai-mistral_models": "Mistral",
    "deepseek": "DeepSeek",
    "dashscope": "阿里通义千问",
    "moonshot": "月之暗面 Kimi",
    "zhipu": "智谱 GLM",
    "minimax": "MiniMax",
    "zai": "智谱 Z.ai",
    "zhipu": "智谱 GLM",
    "volcengine": "字节豆包",
    "baidu": "百度文心",
    "xai": "xAI",
    "mistral": "Mistral",
    "cohere": "Cohere",
    "perplexity": "Perplexity",
    "meta_llama": "Meta",
    "ai21": "AI21",
    "voyage": "Voyage",
    "jina_ai": "Jina",
    "elevenlabs": "ElevenLabs",
    "cartesia": "Cartesia",
    # 聚合/托管平台
    "fireworks_ai": "Fireworks",
    "fireworks-ai": "Fireworks",
    "bedrock": "AWS Bedrock",
    "bedrock_converse": "AWS Bedrock",
    "sagemaker": "AWS",
    "azure": "Azure OpenAI",
    "azure_ai": "Azure AI",
    "github": "GitHub Models",
    "github_copilot": "GitHub Copilot",
    "nvidia_nim": "NVIDIA",
    "together_ai": "Together",
    "together-ai": "Together",
    "deepinfra": "DeepInfra",
    "vercel_ai_gateway": "Vercel",
    "openrouter": "OpenRouter",
    "databricks": "Databricks",
    "groq": "Groq",
    "anyscale": "Anyscale",
    "replicate": "Replicate",
    "baseten": "Baseten",
    "hyperbolic": "Hyperbolic",
    "nscale": "Nscale",
    "ovhcloud": "OVHcloud",
    "friendliai": "FriendliAI",
    "fal_ai": "fal.ai",
    "recraft": "Recraft",
    "black_forest_labs": "Black Forest Labs",
    "runwayml": "Runway",
    "assemblyai": "AssemblyAI",
    "deepgram": "Deepgram",
    "sarvam": "Sarvam",
    "gigachat": "GigaChat",
    "palm": "Google",
    "meta": "Meta",
    "amazon_nova": "Amazon",
    "azure_text": "Azure AI",
    "codestral": "Mistral",
    "cohere_chat": "Cohere",
    "qwen_ai_platform": "阿里通义千问(国际)",
    "qwencloud": "阿里云百炼",
    "novita": "Novita",
    "nebius": "Nebius",
    "lambda_ai": "Lambda",
    "sambanova": "SambaNova",
    "cerebras": "Cerebras",
    "featherless_ai": "Featherless",
    "ppio": "PPIO",
    "infinity": "Infinity",
    "ollama": "Ollama(本地)",
    "huggingface": "HuggingFace",
}

# 各渠道用来标厂商的 slug -> 展示名。写法各家不一样（openrouter 用 z-ai、
# vercel 用 zai、novita 用 zai-org），都收进来，认不出的丢掉免得长尾噪音。
VENDOR_SLUGS = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "google": "Google",
    "deepseek": "DeepSeek",
    "deepseek-ai": "DeepSeek",
    "moonshotai": "月之暗面 Kimi",
    "moonshot": "月之暗面 Kimi",
    "z-ai": "智谱 Z.ai",
    "zai": "智谱 Z.ai",
    "zai-org": "智谱 Z.ai",
    "qwen": "阿里通义千问(国际)",
    "alibaba": "阿里通义千问(国际)",
    "minimax": "MiniMax",
    "minimaxai": "MiniMax",
    "xai": "xAI",
    "spacexai": "xAI",
    "meta-llama": "Meta",
    "meta": "Meta",
    "mistralai": "Mistral",
    "mistral": "Mistral",
    "cohere": "Cohere",
    "perplexity": "Perplexity",
    "baidu": "百度文心",
    "bytedance": "字节豆包",
    "tencent": "腾讯混元",
    "stepfun-ai": "阶跃星辰",
    "stepfun": "阶跃星辰",
    "xiaomi": "小米 MiMo",
    "xiaomimimo": "小米 MiMo",
    "kwaipilot": "快手 KwaiCoder",
    "inclusionai": "蚂蚁 Ling",
    "microsoft": "Microsoft",
    "amazon-nova": "Amazon",
    "amazon": "Amazon",
    "nvidia": "NVIDIA",
    "arcee-ai": "Arcee",
    "inception": "Inception",
    "morph": "Morph",
    "ibm-granite": "IBM Granite",
    "nousresearch": "Nous Research",
    "openrouter": "OpenRouter",
    "thinkingmachines": "Thinking Machines",
    "poolside": "Poolside",
    "sakana": "Sakana",
}

# 平台上架的是原厂商模型的转售价，非厂商官网直营定价 —— 这是本项目对比的重点
AGGREGATORS = {
    "fireworks_ai", "fireworks-ai", "deepinfra", "together_ai", "together-ai",
    "vercel_ai_gateway", "openrouter", "databricks", "bedrock",
    "bedrock_converse", "sagemaker", "azure", "azure_ai", "github",
    "github_copilot", "nvidia_nim", "novita", "nebius", "lambda_ai",
    "sambanova", "cerebras", "featherless_ai", "ppio", "infinity", "groq",
    "huggingface",
}


# 官方价格页，用来核对（页面上每家会带个「官方价格页」链接，方便自己复核）
PRICING_PAGES = {
    "OpenAI": "https://platform.openai.com/docs/pricing",
    "Anthropic": "https://www.anthropic.com/pricing#api",
    "Google": "https://ai.google.dev/gemini-api/docs/pricing",
    "DeepSeek": "https://api-docs.deepseek.com/quick_start/pricing",
    "xAI": "https://docs.x.ai/docs/models",
    "Mistral": "https://mistral.ai/pricing#api-pricing",
    "Cohere": "https://cohere.com/pricing",
    "Perplexity": "https://docs.perplexity.ai/getting-started/pricing",
    "Meta": "https://llama.developer.meta.com/docs/pricing/",
    "MiniMax": "https://platform.minimaxi.com/document/price",
    "智谱 Z.ai": "https://docs.z.ai/guides/overview/pricing",
    "智谱 GLM": "https://open.bigmodel.cn/pricing",
    "月之暗面 Kimi": "https://platform.moonshot.cn/docs/pricing/chat",
    "阿里通义千问": "https://help.aliyun.com/zh/model-studio/models",
    "阿里云百炼": "https://help.aliyun.com/zh/model-studio/models",
    "阿里通义千问(国际)": "https://www.alibabacloud.com/help/en/model-studio/models",
    "字节豆包": "https://www.volcengine.com/docs/82379/1099320",
    "百度文心": "https://cloud.baidu.com/doc/qianfan-docs/s/Blfmc9dlf",
    "腾讯混元": "https://cloud.tencent.com/document/product/1729/97731",
    "阶跃星辰": "https://platform.stepfun.com/docs/pricing/details",
    "OpenRouter": "https://openrouter.ai/models",
    "Together": "https://www.together.ai/pricing",
    "Fireworks": "https://fireworks.ai/pricing",
    "Groq": "https://groq.com/pricing",
    "DeepInfra": "https://deepinfra.com/pricing",
    "AWS Bedrock": "https://aws.amazon.com/bedrock/pricing/",
    "Azure OpenAI": "https://azure.microsoft.com/en-us/pricing/details/cognitive-services/openai-service/",
    "Azure AI": "https://azure.microsoft.com/en-us/pricing/details/phi-3/",
    "Vercel": "https://vercel.com/docs/ai-gateway/pricing",
    "Cerebras": "https://www.cerebras.ai/pricing",
    "Novita": "https://novita.ai/pricing",
    "Databricks": "https://www.databricks.com/product/pricing/foundation-model-serving",
}


def fetch(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "llm-pricing-compare/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def norm(raw: dict, or_dates: dict[str, str]) -> list[dict]:
    rows = []
    dropped = 0
    for name, m in raw.items():
        if not isinstance(m, dict):
            continue
        provider = m.get("litellm_provider", "")
        if provider not in VENDOR_NAMES:  # 只保留已映射的主流厂商/平台，长尾噪音丢弃
            continue
        released = released_of(name, or_dates)
        if outdated(name, m, released):
            dropped += 1
            continue
        in_cost = m.get("input_cost_per_token")
        out_cost = m.get("output_cost_per_token")
        mode = m.get("mode")
        in_price = round(in_cost * 1e6, 3) if in_cost is not None else None
        out_price = round(out_cost * 1e6, 3) if out_cost is not None else None
        # 向量/重排模型没有输出 token，上游填 0，显示成「免费」会误导
        if mode in ("embedding", "rerank") and out_price == 0:
            out_price = None
        rows.append({
            "model": name,
            "vendor": provider,
            "vendor_name": VENDOR_NAMES.get(provider, provider),
            # 统一为 美元/百万 token；None = 官方未公布
            "input": in_price,
            "output": out_price,
            "cache_read": (round(m["cache_read_input_token_cost"] * 1e6, 3)
                           if m.get("cache_read_input_token_cost") is not None else None),
            "context": m.get("max_input_tokens") or m.get("max_tokens"),
            "max_output": m.get("max_output_tokens"),
            "mode": mode,  # chat / embedding / audio / image ...
            "released": released,
            "official": provider not in AGGREGATORS,
            "suspect": suspect(in_price, mode),
            "vision": bool(m.get("supports_vision")),
            "reasoning": bool(m.get("supports_reasoning")),
            "tool_call": bool(m.get("supports_function_calling")),
        })
    rows.sort(key=lambda r: (r["vendor_name"], r["model"]))
    print(f"   剔除过时/已退役模型 {dropped} 个")
    return rows


def norm_name(s: str) -> str:
    return s.lower().replace(":", "-").replace("_", "-").replace(".", "-").strip()


TODAY = time.strftime("%Y-%m-%d")
# 对话模型迭代快，两年前发布的基本没人用了（gpt-4、gpt-3.5-turbo 这些）；
# 向量/语音模型寿命长得多（text-embedding-3 至今还是主力），所以只对对话类做年龄筛。
AGE_CUTOFF = f"{int(TODAY[:4]) - 2}{TODAY[4:]}"
AGED_MODES = {"chat", "responses", "completion"}
DATE_RE = re.compile(r"(20\d{2})-?(\d{2})-?(\d{2})")
LEGACY_RE = re.compile(
    r"gpt-3\.5|gpt-35|text-(davinci|curie|babbage|ada)|davinci-|curie-|babbage-|ada-"
    r"|claude-(1|2|instant)|claude-v1|palm|chat-bison|text-bison|gemini-1\.|gemini-pro"
    r"|llama-?2|llama2|j2-|dall-e-2|command-(light|nightly)?$",
    re.I)


def released_of(name: str, or_dates: dict[str, str]) -> str | None:
    """模型发布日期：名字里带日期的直接取，否则查 OpenRouter 的 created。"""
    m = DATE_RE.search(name)
    if m:
        return "%s-%s-%s" % m.groups()
    k = norm_name(name)
    return or_dates.get(k) or or_dates.get(norm_name(name.split("/")[-1]))


def outdated(name: str, meta: dict, released: str | None) -> bool:
    dep = meta.get("deprecation_date")
    if isinstance(dep, str) and DATE_RE.match(dep) and dep < TODAY:
        return True                       # 官方已宣布退役且日子过了
    if LEGACY_RE.search(name):
        return True                       # 明确的上一代产品线
    return bool(released and released < AGE_CUTOFF
                and meta.get("mode") in AGED_MODES)


# 上游偶尔把「每千 token」的价格填进「每 token」字段，结果价格离谱 1000 倍
# （见 embed-multilingual-light-v3.0、azure_ai/jais-30b-chat）。这里按各类模型
# 真实价格上限粗筛一下标出来，不直接删，免得把真·天价模型（o1-pro $150/1M）误伤。
SANE_MAX = {"embedding": 10, "chat": 200, "responses": 200, "rerank": 10}


def suspect(price: float | None, mode: str | None) -> bool:
    return price is not None and price > SANE_MAX.get(mode or "", 500)


def _mtok(v) -> float | None:
    """genai-prices 的单价可能是数字，也可能是 {base, tiers} 的分档结构，取基础价。"""
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, dict) and isinstance(v.get("base"), (int, float)):
        return float(v["base"])
    return None


def _price_block(model: dict) -> dict:
    """prices 有时是一组带生效条件的变体，取最后一个（一般是当前生效的那档）。"""
    p = model.get("prices")
    if isinstance(p, list):
        for item in reversed(p):
            if isinstance(item, dict) and isinstance(item.get("prices"), dict):
                return item["prices"]
        return {}
    return p if isinstance(p, dict) else {}


def xref_prices() -> dict[str, list[tuple[str, float, float | None]]]:
    """另外两个价格库的官方直营价，用来跟 LiteLLM 对账。
    返回 归一化模型名 -> [(来源, 输入价, 输出价)]，单位都是 美元/百万 token。"""
    out: dict[str, list] = {}

    def add(name: str, src: str, inp, outp) -> None:
        if inp is None or not name:
            return
        out.setdefault(norm_name(name), []).append(
            (src, float(inp), float(outp) if outp is not None else None))

    try:
        for p in fetch(SRC_PYDANTIC):
            for m in p.get("models") or []:
                pr = _price_block(m)
                add(m.get("id", ""), "genai-prices",
                    _mtok(pr.get("input_mtok")), _mtok(pr.get("output_mtok")))
    except Exception as e:                       # 对账源挂了不该拖垮主流程
        print(f"   genai-prices 拉取失败，跳过对账：{e}")
    try:
        for m in fetch(SRC_LLMPRICES).get("prices") or []:
            add(m.get("id", ""), "llm-prices", m.get("input"), m.get("output"))
    except Exception as e:
        print(f"   llm-prices 拉取失败，跳过对账：{e}")
    return out


def price_check(row: dict, xref: dict) -> list[dict] | None:
    """跟别的源对一下输入价。差 20% 以内算正常（各家口径、分档不同），
    差得多就把别人的报价带上，页面里标出来让人自己判断。"""
    if not row["official"] or row["input"] in (None, 0):
        return None
    others = xref.get(norm_name(row["model"]))
    if not others:
        return None
    bad = [(s, i) for s, i, _ in others
           if i > 0 and abs(i - row["input"]) / max(i, row["input"]) > 0.2]
    if not bad:
        return None
    return [{"src": s, "input": round(i, 3)} for s, i in bad[:2]]


def or_release_dates(raw: dict) -> dict[str, str]:
    dates = {}
    for m in raw.get("data", []):
        ts, mid = m.get("created"), m.get("id", "")
        if not ts or not mid:
            continue
        d = time.strftime("%Y-%m-%d", time.gmtime(ts))
        for k in (norm_name(mid), norm_name(mid.partition("/")[2])):
            dates.setdefault(k, d)
    return dates


def _row(mid: str, vendor: str, channel: str, prov: str, inp: float | None,
         outp: float | None, ctx, released: str | None,
         vision=False, tools=False) -> dict | None:
    """渠道补充行的统一构造。inp/outp 单位已经是 美元/百万 token。"""
    if inp is None or LEGACY_RE.search(mid):
        return None
    if released and released < AGE_CUTOFF:
        return None
    return {
        "model": mid,
        "vendor": prov,
        "vendor_name": vendor,          # 模型品牌
        "input": round(inp, 3),
        "output": round(outp, 3) if outp is not None else None,
        "cache_read": None,
        "context": ctx if isinstance(ctx, int) and ctx > 0 else None,
        "max_output": None,
        "mode": "chat",
        "released": released,
        "official": False,
        "via": channel,                 # 真正在收钱的渠道
        "suspect": suspect(round(inp, 3), "chat"),
        "new": True,
        "vision": bool(vision),
        "reasoning": False,
        "tool_call": bool(tools),
    }


def _ts(v) -> str | None:
    if isinstance(v, (int, float)) and v > 0:
        return time.strftime("%Y-%m-%d", time.gmtime(v))
    if isinstance(v, str) and DATE_RE.match(v):
        return v[:10]
    return None


def ch_openrouter(raw: dict) -> list[dict]:
    out = []
    for m in raw.get("data", []):
        mid = m.get("id", "")
        vendor = VENDOR_SLUGS.get(mid.partition("/")[0])
        p = m.get("pricing") or {}
        if not vendor:
            continue
        try:
            inp, outp = float(p.get("prompt") or 0), float(p.get("completion") or 0)
        except ValueError:
            continue
        out.append(_row(mid, vendor, "OpenRouter", "openrouter", inp * 1e6, outp * 1e6,
                        m.get("context_length"), _ts(m.get("created")),
                        "image" in (m.get("architecture", {}).get("input_modalities") or []),
                        "tools" in (m.get("supported_parameters") or [])))
    return [r for r in out if r]


def ch_vercel(raw: dict) -> list[dict]:
    """Vercel AI Gateway：owned_by 就是上游厂商，覆盖国内厂商也全。"""
    out = []
    for m in raw.get("data", []):
        if m.get("type") != "language":
            continue
        vendor = VENDOR_SLUGS.get(m.get("owned_by", ""))
        p = m.get("pricing") or {}
        if not vendor or p.get("input") is None:
            continue
        try:
            inp, outp = float(p["input"]), float(p.get("output") or 0)
        except ValueError:
            continue
        out.append(_row(m.get("id", ""), vendor, "Vercel AI Gateway", "vercel_ai_gateway",
                        inp * 1e6, outp * 1e6, m.get("context_window"),
                        _ts(m.get("released")),
                        "image" in (m.get("modalities", {}).get("input") or []),
                        "tools" in (m.get("supported_parameters") or [])))
    return [r for r in out if r]


def ch_novita(raw: dict) -> list[dict]:
    """Novita：price_per_m 的单位是 1e-4 美元，decimal 字段直接就是美元。"""
    out = []
    for m in raw.get("data", []):
        mid = m.get("id", "")
        vendor = VENDOR_SLUGS.get(mid.partition("/")[0])
        if not vendor:
            continue
        pr = m.get("pricing") or {}

        def usd(side: str, fallback: str):
            blk = pr.get(side) or {}
            d = blk.get("price_per_m_decimal")
            if d not in (None, ""):
                try:
                    return float(d)
                except ValueError:
                    pass
            v = m.get(fallback)
            return v / 1e4 if isinstance(v, (int, float)) else None

        inp = usd("prompt", "input_token_price_per_m")
        out.append(_row(mid, vendor, "Novita", "novita", inp,
                        usd("completion", "output_token_price_per_m"),
                        None, _ts(m.get("created")), False, False))
    return [r for r in out if r]


def ch_deepinfra(raw: list) -> list[dict]:
    """DeepInfra：cents_per_*_token 是「美分 / token」，×1e4 得美元/百万。"""
    out = []
    for m in raw:
        if m.get("type") != "text-generation" or m.get("deprecated"):
            continue
        mid = m.get("model_name", "")
        vendor = VENDOR_SLUGS.get(mid.partition("/")[0])
        p = m.get("pricing") or {}
        if not vendor or p.get("cents_per_input_token") is None:
            continue
        out.append(_row(mid, vendor, "DeepInfra", "deepinfra",
                        p["cents_per_input_token"] * 1e4,
                        (p.get("cents_per_output_token") or 0) * 1e4,
                        m.get("max_tokens"), _ts(m.get("create_ts"))))
    return [r for r in out if r]


# 除主源之外的渠道。每个渠道只在 LiteLLM 没收录该渠道的同名模型时才补，
# 所以同一个模型会在表里出现多行 —— 那正是用来比价的。
CHANNELS = [
    ("OpenRouter", "openrouter", SRC_NEW, ch_openrouter),
    ("Vercel AI Gateway", "vercel_ai_gateway", SRC_VERCEL, ch_vercel),
    ("Novita", "novita", SRC_NOVITA, ch_novita),
    ("DeepInfra", "deepinfra", SRC_DEEPINFRA, ch_deepinfra),
]


def supplement(base: list[dict]) -> list[dict]:
    """按渠道补模型。同渠道内 LiteLLM 已有的跳过，避免一个渠道重复两行。"""
    seen: dict[str, set[str]] = {}
    for r in base:
        seen.setdefault(r["vendor"], set()).add(norm_name(r["model"].split("/")[-1]))
    added = []
    for name, prov, url, parse in CHANNELS:
        try:
            rows = parse(fetch(url))
        except Exception as e:
            print(f"   渠道 {name} 拉取失败，跳过：{e}")
            continue
        have = seen.setdefault(prov, set())
        n = 0
        for r in rows:
            key = norm_name(r["model"].split("/")[-1])
            if key in have:
                continue
            have.add(key)
            added.append(r)
            n += 1
        print(f"   渠道 {name}: 补充 {n} / 返回 {len(rows)}")
    return added


def main() -> None:
    openrouter = fetch(SRC_NEW)
    rows = norm(fetch(SRC), or_release_dates(openrouter))
    for r in rows:
        r["new"] = False
    new_rows = supplement(rows)
    rows += new_rows
    rows.sort(key=lambda r: (r["vendor_name"], r["model"]))

    xref = xref_prices()
    for r in rows:
        diff = price_check(r, xref)
        if diff:
            r["xref"] = diff
    n_priced = sum(1 for r in rows if r["input"] is not None)
    n_diff = sum(1 for r in rows if r.get("xref"))
    channels = sorted({r["via"] for r in rows if r.get("via")})
    OUT.write_text(json.dumps({
        "updated_at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
        "sources": [
            {"name": "LiteLLM", "role": "主源",
             "url": "https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json"},
            {"name": "OpenRouter", "role": "渠道",
             "url": "https://openrouter.ai/api/v1/models"},
            {"name": "Vercel AI Gateway", "role": "渠道",
             "url": "https://vercel.com/docs/ai-gateway"},
            {"name": "Novita", "role": "渠道", "url": "https://novita.ai/pricing"},
            {"name": "DeepInfra", "role": "渠道", "url": "https://deepinfra.com/pricing"},
            {"name": "genai-prices", "role": "价格对账",
             "url": "https://github.com/pydantic/genai-prices"},
            {"name": "llm-prices", "role": "价格对账",
             "url": "https://www.llm-prices.com/"},
        ],
        "channels": channels,
        "cutoff": AGE_CUTOFF,
        "pricing_pages": PRICING_PAGES,
        "count": len(rows),
        "models": rows,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"OK: {len(rows)} models ({n_priced} with prices, "
          f"{len(new_rows)} 来自渠道补充, "
          f"{sum(1 for r in rows if not r['official'])} on aggregators, "
          f"{sum(1 for r in rows if r['suspect'])} suspect, "
          f"{n_diff} 与其他源报价不一致) -> {OUT}")


if __name__ == "__main__":
    main()
