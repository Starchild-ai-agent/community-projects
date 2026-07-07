# 生辰八字算命服务 (bazi-fortune)

## What

基于中国传统八字命理的算命 Web 服务。用户输入出生年月日时，服务计算并返回：

- **四柱八字**：年柱、月柱、日柱、时柱（天干+地支）
- **日主五行**：日干及其五行属性
- **五行强度**：金木水火土计数与日主强弱判断（中和/偏强/偏弱）
- **命理解读**：基于八字格局的文字分析

服务通过 x402 协议按次付费，每次调用收费 $0.01 USDC（Base 主网）。

## Required env

无必需环境变量。服务纯本地计算，不依赖外部 API。

## How to start

```bash
pip install flask
python app.py
```

服务默认监听 `0.0.0.0:5000`。

如需启用 x402 付费网关，使用 x402 skill 的 `monetize.py`：

```bash
python3 skills/x402/scripts/monetize.py \
  --name bazi-api \
  --upstream-port 5000 \
  --mode pay_per_use \
  --price 0.01 \
  --route 'POST /api/*=$0.01' \
  --network eip155:8453
```

## Outputs

### Web 界面

- `GET /` — 八字算命表单页
- `POST /calculate` — 表单提交，渲染结果页

### JSON API

- `POST /api/bazi` — 接收 JSON `{year, month, day, hour}`，返回八字分析结果

响应示例：

```json
{
  "year_pillar": "庚午",
  "month_pillar": "癸未",
  "day_pillar": "辛亥",
  "hour_pillar": "甲午",
  "day_master": "辛",
  "day_master_element": "金",
  "elements": {"金": 2, "木": 1, "水": 2, "火": 2, "土": 1},
  "strength": "中和",
  "analysis": "你的日主为辛（金），五行较为均衡，属于中和格局。",
  "year": 1990, "month": 6, "day": 15, "hour": 12
}
```

## Troubleshooting

| 问题 | 原因 | 解决 |
|------|------|------|
| 表单提交 404 | 静态文件相对路径错误 | 确保 `templates/` 目录与 `app.py` 同级 |
| 402 未触发付费 | 网关未启动或配置错误 | 检查 `.x402/bazi-api/x402.config.json` 的 `facilitator` 是否为 `https://starchild-x402-facilitator.fly.dev` |
| 算命结果异常 | 输入日期非法 | 确认 year∈[1900,2100], month∈[1,12], day∈[1,31], hour∈[0,23] |
