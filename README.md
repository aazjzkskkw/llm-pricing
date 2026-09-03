# llm-pricing

一个大模型价格查询页。起因是想找个价格表对比各家定价，现成的几个项目要么没区分价格来源，要么国产模型基本没有，索性自己写了一个。

在线版：<https://aazjzkskkw.github.io/llm-pricing/>

## 它能干嘛

四个页面：

- **价格总表** — 搜模型、按厂商筛、点列头按价格排序。同一模型官方价和各平台价摆在一起看，差价一目了然。每个价格都标了来源：**官方直营**、平台转售，还是**经 OpenRouter**
- **按厂商看** — 每家一张卡片，列出主力对话模型和价格区间，点进去跳总表看全部
- **模型评测** — 三个开源榜单：Aider Polyglot（代码编辑）、Aider Refactor（会不会偷懒省略代码）、Vectara 幻觉率
- **活动与优惠** — 各家的免费额度入口，想补充就改 promos.html 里的 PROMOS 数组

国产厂商都是中文名：通义千问、智谱、Kimi、豆包这些。

## 数据哪来的

不自己抓官网也不自己跑评测，都是拿开源项目的公开数据：

**价格**
- [LiteLLM 价格库](https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json)（主力，3000+ 模型，各家官网公开定价）
- [OpenRouter](https://openrouter.ai/api/v1/models)（补充 LiteLLM 还没来得及收的最新模型，页面上标"新"）

**评测**
- [Aider](https://aider.chat/docs/leaderboards/) 的 polyglot 和 refactor 榜
- [Vectara 幻觉榜](https://github.com/vectara/hallucination-leaderboard)

`scripts/update.py` 管价格，`scripts/bench.py` 管榜单，都归一成 `data/*.json`。GitHub Actions 每天自动跑一次，所以这页不用手动维护。价格偶尔有滞后，以各家官网为准；不同榜单的题目和评分方式差别很大，跨榜单的分数不能直接比。

## 本地跑

```
python scripts/update.py      # 拉最新价格
python scripts/bench.py       # 拉评测榜单
python -m http.server 8000    # 打开 http://localhost:8000
```

价格脚本纯标准库，榜单脚本要个 pyyaml（`pip install pyyaml`）。

## License

MIT
