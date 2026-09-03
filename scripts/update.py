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

# OpenRouter 的厂商 slug -> 展示名；只收录主流厂商，避免长尾噪音
OR_VENDORS = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "google": "Google",
    "deepseek": "DeepSeek",
    "moonshotai": "月之暗面 Kimi",
    "z-ai": "智谱 Z.ai",
    "qwen": "阿里通义千问(国际)",
    "minimax": "MiniMax",
    "xai": "xAI",
    "meta-llama": "Meta",
    "mistralai": "Mistral",
    "cohere": "Cohere",
    "perplexity": "Perplexity",
    "baidu": "百度文心",
    "bytedance": "字节豆包",
    "tencent": "腾讯混元",
    "stepfun-ai": "阶跃星辰",
    "microsoft": "Microsoft",
    "amazon-nova": "Amazon",
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


def or_release_dates(raw: dict) -> dict[str, str]:
    """OpenRouter 的 created 时间戳是现成的发布日期，拿来给 LiteLLM 那边的模型标年龄。"""
    dates = {}
    for m in raw.get("data", []):
        ts, mid = m.get("created"), m.get("id", "")
        if not ts or not mid:
            continue
        d = time.strftime("%Y-%m-%d", time.gmtime(ts))
        for k in (norm_name(mid), norm_name(mid.partition("/")[2])):
            dates.setdefault(k, d)
    return dates


def fetch_new(raw: dict, known: set[str]) -> list[dict]:
    """OpenRouter 补充最新模型：只取主流厂商、且 LiteLLM 还未收录的。"""
    rows = []
    for m in raw.get("data", []):
        mid = m.get("id", "")
        slug, _, suffix = mid.partition("/")
        vendor = OR_VENDORS.get(slug)
        if not vendor or not suffix:
            continue
        # LiteLLM 已有同款（含 :free 变体除外）就跳过，避免重复
        if norm_name(suffix) in known:
            continue
        if LEGACY_RE.search(mid):
            continue
        released = (time.strftime("%Y-%m-%d", time.gmtime(m["created"]))
                    if m.get("created") else None)
        if released and released < AGE_CUTOFF:
            continue
        p = m.get("pricing") or {}
        try:
            in_cost = float(p.get("prompt") or 0)
            out_cost = float(p.get("completion") or 0)
        except ValueError:
            continue
        ctx = m.get("context_length")
        rows.append({
            "model": mid,
            "vendor": "openrouter",
            "vendor_name": vendor,
            "input": round(in_cost * 1e6, 3),
            "output": round(out_cost * 1e6, 3),
            "cache_read": None,
            "context": ctx if isinstance(ctx, int) else None,
            "max_output": None,
            "mode": "chat",
            "released": released,
            "official": False,
            "via": "OpenRouter",   # 品牌归 vendor_name，价格是 OpenRouter 的
            "suspect": suspect(round(in_cost * 1e6, 3), "chat"),
            "new": True,
            "vision": bool(m.get("architecture", {}).get("input_modalities")
                           and "image" in m["architecture"]["input_modalities"]),
            "reasoning": False,
            "tool_call": bool(m.get("supported_parameters")
                              and "tools" in m["supported_parameters"]),
        })
    return rows


def main() -> None:
    openrouter = fetch(SRC_NEW)
    rows = norm(fetch(SRC), or_release_dates(openrouter))
    known = {norm_name(r["model"]) for r in rows}
    new_rows = fetch_new(openrouter, known)
    for r in rows:
        r["new"] = False
    rows += new_rows
    rows.sort(key=lambda r: (r["vendor_name"], r["model"]))
    n_priced = sum(1 for r in rows if r["input"] is not None)
    OUT.write_text(json.dumps({
        "updated_at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
        "source": "https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json",
        "source_new": "https://openrouter.ai/api/v1/models",
        "cutoff": AGE_CUTOFF,
        "pricing_pages": PRICING_PAGES,
        "count": len(rows),
        "models": rows,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"OK: {len(rows)} models ({n_priced} with prices, "
          f"{len(new_rows)} new from OpenRouter, "
          f"{sum(1 for r in rows if not r['official'])} on aggregators, "
          f"{sum(1 for r in rows if r['suspect'])} suspect) -> {OUT}")


if __name__ == "__main__":
    main()
