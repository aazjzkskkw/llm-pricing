# llm-pricing

一个大模型价格查询页。起因是想找个价格表对比各家定价，现成的几个项目要么没区分价格来源，要么国产模型基本没有，索性自己写了一个。

在线版：<https://aazjzkskkw.github.io/llm-pricing/>

## 它能干嘛

- 搜模型、按厂商筛、点列头按价格排序。同一模型官方价和各平台价摆在一起看，差价一目了然
- 每个价格都标了来源：**官方直营**还是 Together / Fireworks / DeepInfra 这些平台的转售价（差价经常不小）
- 国产厂商都是中文名：通义千问、智谱、Kimi、豆包这些
- 有个[活动页](promos.html)，收了各家的免费额度入口，想补充的话直接改 promos.html 里的 PROMOS 数组

## 数据哪来的

不自己抓官网，两个上游：

- [LiteLLM 价格库](https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json)（主力，3000+ 模型，各家官网公开定价）
- [OpenRouter](https://openrouter.ai/api/v1/models)（补充 LiteLLM 还没来得及收的最新模型，页面上标"新"）

`scripts/update.py` 把两边归一成一个 `data/models.json`，GitHub Actions 每天自动跑一次，所以这个页面不用手动维护。价格偶尔有滞后，以各家官网为准。

## 本地跑

```
python scripts/update.py      # 拉最新价格
python -m http.server 8000    # 打开 http://localhost:8000
```

就这两个命令，纯标准库，没有依赖要装。

## License

MIT
