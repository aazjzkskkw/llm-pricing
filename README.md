# llm-pricing

一个大模型价格查询页。起因是想找个价格表对比各家定价，现成的几个项目要么没区分价格来源，要么国产模型基本没有，索性自己写了一个。

在线版：<https://aazjzkskkw.github.io/llm-pricing/>

## 它能干嘛

四个页面：

- **价格总表** — 搜模型、按厂商筛、按最新发布或价格排序。同一模型官方价和各平台价摆在一起看，差价一目了然。每个价格都标了来源：**官方直营**、平台转售，还是**经 OpenRouter**
- **按厂商看** — 每家一张卡片，默认按最近发布排，卡片里的模型也是新的在上面，带官方价格页链接方便自己复核
- **模型评测** — 9 个榜单：ECI 综合能力指数、GPQA Diamond、SWE-Bench Verified、Terminal-Bench、FrontierMath、SimpleQA Verified、ARC-AGI-2、SimpleBench、Vectara 幻觉率。每个榜标了「最新上榜模型」的发布时间，默认隐藏两年前的老模型
- **活动与优惠** — 分成长期免费 / 赠送额度 / 其他优惠三档
- **公益站** — 社区公益及半公益中转站名单，按可用状态分档，另附官方免费额度对照和使用风险提示。名单同步自 [公益中转分享](https://ytzzjx.github.io/)，脚本会去掉里面的邀请参数

国产厂商都是中文名：通义千问、智谱、Kimi、豆包这些。

已官宣退役、明确的上一代产品线（gpt-3.5、claude-2、gemini-1.x 这类）、以及两年前发布的对话模型都不收录。向量和语音模型不按年龄筛，那类模型寿命长得多，`text-embedding-3` 至今还是主力。

## 数据哪来的

不自己抓官网也不自己跑评测，都是拿开源项目的公开数据：

**价格**
- [LiteLLM 价格库](https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json)（主力，各家官网公开定价）
- [OpenRouter](https://openrouter.ai/api/v1/models)（补最新模型，页面标"新"；它的 `created` 字段还顺便当了全站的模型发布日期来源）

**评测**
- [Epoch AI · AI Benchmarking Hub](https://epoch.ai/benchmarks)（主源，一个 zip 打包几十个 benchmark 的原始成绩，每天更新，CC-BY 4.0，模型发布日期也是现成的）
- [Vectara 幻觉榜](https://github.com/vectara/hallucination-leaderboard)（Epoch 没覆盖的维度）

**公益站名单**
- [公益中转分享](https://ytzzjx.github.io/)（社区维护，这块更新最勤的一份，没必要自己再攒）

三个脚本：`scripts/update.py` 管价格，`scripts/bench.py` 管榜单，`scripts/stations.py` 管公益站名单，都归一成 `data/*.json`。GitHub Actions 每天自动跑一次，所以这页不用手动维护。

价格以各家官网为准，每家的官方价格页链接在「按厂商看」的卡片里。评测那边跨榜单的分数不能直接比：题目、评分方式、跑分用的 agent 框架都不一样；同一模型有多档推理强度时只留了最高分。

上游那份价格库是社区维护的，偶尔会有人把「每千 token」的价格填进「每 token」字段，价格就离谱 1000 倍（比如 Cohere 的 embed-multilingual-light 标成 $100/1M，实际是 $0.1）。这种明显超出同类模型上限的会打个红色 `?`，鼠标放上去有说明，不直接删是怕误伤真·天价模型（o1-pro 确实是 $150/1M）。

## 本地跑

```
python scripts/update.py      # 拉最新价格
python scripts/bench.py       # 拉评测榜单（要先跑上面那条，它读发布日期）
python scripts/stations.py    # 拉公益站名单
python -m http.server 8000    # 打开 http://localhost:8000
```

三个脚本都只用标准库，没有依赖要装。

公益站那部分要说一句：那些站基本没有正经上游授权，请求会经过对方服务器，模型可能被换、内容可能被留存。页面上写了提示，自己拿主意。

## License

MIT
