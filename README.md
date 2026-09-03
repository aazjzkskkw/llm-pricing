# llm-pricing

一个大模型价格查询页。起因是想找个价格表对比各家定价，现成的几个项目要么没区分价格来源，要么国产模型基本没有，索性自己写了一个。

在线版：<https://aazjzkskkw.github.io/llm-pricing/>

## 它能干嘛

四个页面：

- **价格总表** — 默认只看近一年发布的对话模型（约 2600 行），旗舰排在最前面；一到两年的降级成「扩展」，切「全部」才出来，两年前的和官宣退役的根本不收。同一个模型在各渠道的报价紧挨着排，组内按价格升序、最便宜那行打「最低价」标；也可以切成「每个模型只留最便宜渠道」一眼看结论。每行标了渠道：官方直营 / 平台名 / 经 OpenRouter、Vercel AI Gateway、Novita、DeepInfra

  旗舰不是我按名字猜的，是拿评测页那份 [Epoch ECI 综合能力分](https://epoch.ai/benchmarks) 联表取每家前三（584 行匹配到分数）；没上榜的厂商退回「同厂当前最贵的型号」当代理，鼠标放在「旗舰」标上会写明是哪种依据。

  各渠道给同一个模型起的名字五花八门 —— 智谱 GLM-5.3 在官方叫 `zai/glm-5.3`、OpenRouter 叫 `z-ai/glm-5.3`、Novita 叫 `zai-org/glm-5.3`、Bedrock 叫 `us.zai.glm-5-3`、Fireworks 写成 `glm-5p3`。`model_key()` 把命名空间、地域段、`4p6` 这类写法都归一掉，表格才排得到一起；搜索也会拿这个键匹配一次，所以搜 `glm-5.3` 能带出 Fireworks 那行
- **按厂商看** — 每家一张卡片，默认按最近发布排，卡片里的模型也是新的在上面，带官方价格页链接方便自己复核
- **模型评测** — 10 个榜单：ECI 综合能力指数、GPQA Diamond、SWE-Bench Verified、Terminal-Bench、FrontierMath、SimpleQA Verified、ARC-AGI-2、DeepSWE、SimpleBench、Vectara 幻觉率。每个榜标了「最新上榜模型」的发布时间，默认隐藏两年前的老模型。DeepSWE 那张带每题平均成本，能直接看性价比
- **订阅与渠道** — Cursor、Copilot、Claude、Kiro、Trae、Zed、Augment、v0、Cline 的订阅档位（逐个核对过官网标价），加上 15 个聚合平台的模型数和价格区间（这部分从价格总表实时算，不手工维护）
- **活动与优惠** — 分成长期免费 / 赠送额度 / 其他优惠三档
- **公益站** — 社区公益及半公益中转站名单，按可用状态分档，另附官方免费额度对照和使用风险提示。名单同步自 [公益中转分享](https://ytzzjx.github.io/)，脚本会去掉里面的邀请参数

国产厂商都是中文名：通义千问、智谱、Kimi、豆包这些。

已官宣退役、明确的上一代产品线（gpt-3.5、claude-2、gemini-1.x 这类）、以及两年前发布的对话模型都不收录。向量和语音模型不按年龄筛，那类模型寿命长得多，`text-embedding-3` 至今还是主力。

## 数据哪来的

不自己抓官网也不自己跑评测，都是拿开源项目的公开数据：

**价格**
- [LiteLLM 价格库](https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json)（主力，各家官网公开定价）
- 四个渠道的公开接口补最新模型（页面标"新"，厂商列会写「经 XX」）：[OpenRouter](https://openrouter.ai/api/v1/models)、[Vercel AI Gateway](https://ai-gateway.vercel.sh/v1/models)、[Novita](https://api.novita.ai/v3/openai/models)、[DeepInfra](https://api.deepinfra.com/models/list)。这四家的接口不用鉴权就能拿到型号和自家报价，所以同一个模型往往能凑出好几行，按输入价排一下就知道哪个渠道便宜。OpenRouter 的 `created` 字段还顺便当了全站的模型发布日期来源
- [pydantic/genai-prices](https://github.com/pydantic/genai-prices) 和 [llm-prices.com](https://www.llm-prices.com/)（只用来对账：同一个模型三家报价差超 20% 就在页面上标「对账不一致」，把别人的报价一并列出来）

**评测**
- [Epoch AI · AI Benchmarking Hub](https://epoch.ai/benchmarks)（主源，一个 zip 打包几十个 benchmark 的原始成绩，每天更新，CC-BY 4.0，模型发布日期也是现成的）
- [Vectara 幻觉榜](https://github.com/vectara/hallucination-leaderboard)（Epoch 没覆盖的维度）

**公益站名单**
- [公益中转分享](https://ytzzjx.github.io/)（社区维护，这块更新最勤的一份，没必要自己再攒）

三个脚本：`scripts/update.py` 管价格，`scripts/bench.py` 管榜单，`scripts/stations.py` 管公益站名单，都归一成 `data/*.json`。GitHub Actions 每天自动跑一次，所以这页不用手动维护。

价格以各家官网为准，每家的官方价格页链接在「按厂商看」的卡片里。评测那边跨榜单的分数不能直接比：题目、评分方式、跑分用的 agent 框架都不一样；同一模型有多档推理强度时只留了最高分。

价格对账那块说清楚：三个源差得多的时候，能查到官网的我就去查，结论写进 `data/price_notes.json`，页面显示「已核对官网」并把官网原文档位写在提示里；查不到的显示「待核对」，附上其他库的报价和厂商官方价格页链接。

试过三源投票，不靠谱，直接放弃了：DeepSeek v4-flash 上 genai-prices 和 llm-prices 一致报 $0.14，两票压 LiteLLM 的 $0.44，但打开 DeepSeek 官网，cache miss 高峰 $0.44、低谷 $0.22、cache hit $0.014/$0.007 —— 四个档位里没有 $0.14，是那两个库一起过期了。v4-pro 也一样。所以只认官网，不认票数。

注意 `price_notes.json` 里的 `vendor` 字段不能省：阿里云百炼也卖 DeepSeek 的模型，标价 $0.2/$2.4 是它自己的转售价，拿 DeepSeek 官网价去判它「错」就闹笑话了（这个坑我踩过一次，加 vendor 匹配才修掉）。

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
