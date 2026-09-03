"""从开源价格数据库 LiteLLM（各厂商官网公开定价，社区维护）拉取原始数据，
归一化为统一格式供前端对比使用。本项目不自行抓取厂商官网。

Usage: python scripts/update.py
Output: data/models.json
"""

import json
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


def fetch(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "llm-pricing-compare/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def norm(raw: dict) -> list[dict]:
    rows = []
    for name, m in raw.items():
        if not isinstance(m, dict):
            continue
        provider = m.get("litellm_provider", "")
        if provider not in VENDOR_NAMES:  # 只保留已映射的主流厂商/平台，长尾噪音丢弃
            continue
        in_cost = m.get("input_cost_per_token")
        out_cost = m.get("output_cost_per_token")
        rows.append({
            "model": name,
            "vendor": provider,
            "vendor_name": VENDOR_NAMES.get(provider, provider),
            # 统一为 美元/百万 token；None = 官方未公布
            "input": round(in_cost * 1e6, 3) if in_cost is not None else None,
            "output": round(out_cost * 1e6, 3) if out_cost is not None else None,
            "cache_read": (round(m["cache_read_input_token_cost"] * 1e6, 3)
                           if m.get("cache_read_input_token_cost") is not None else None),
            "context": m.get("max_input_tokens") or m.get("max_tokens"),
            "max_output": m.get("max_output_tokens"),
            "mode": m.get("mode"),  # chat / embedding / audio / image ...
            "official": provider not in AGGREGATORS,
            "vision": bool(m.get("supports_vision")),
            "reasoning": bool(m.get("supports_reasoning")),
            "tool_call": bool(m.get("supports_function_calling")),
        })
    rows.sort(key=lambda r: (r["vendor_name"], r["model"]))
    return rows


def norm_name(s: str) -> str:
    return s.lower().replace(":", "-").replace("_", "-").replace(".", "-").strip()


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
            "official": False,
            "via": "OpenRouter",   # 品牌归 vendor_name，价格是 OpenRouter 的
            "new": True,
            "vision": bool(m.get("architecture", {}).get("input_modalities")
                           and "image" in m["architecture"]["input_modalities"]),
            "reasoning": False,
            "tool_call": bool(m.get("supported_parameters")
                              and "tools" in m["supported_parameters"]),
        })
    return rows


def main() -> None:
    rows = norm(fetch(SRC))
    known = {norm_name(r["model"]) for r in rows}
    known |= {norm_name(n) for n in known}  # 归一化后自匹配
    new_rows = fetch_new(fetch(SRC_NEW), known)
    for r in new_rows:
        r.setdefault("new", False)
    for r in rows:
        r["new"] = False
    rows += new_rows
    rows.sort(key=lambda r: (r["vendor_name"], r["model"]))
    n_priced = sum(1 for r in rows if r["input"] is not None)
    OUT.write_text(json.dumps({
        "updated_at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
        "source": "https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json",
        "source_new": "https://openrouter.ai/api/v1/models",
        "count": len(rows),
        "models": rows,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"OK: {len(rows)} models ({n_priced} with prices, "
          f"{len(new_rows)} new from OpenRouter, "
          f"{sum(1 for r in rows if not r['official'])} on aggregators) -> {OUT}")


if __name__ == "__main__":
    main()
