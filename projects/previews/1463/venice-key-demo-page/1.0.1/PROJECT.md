# Venice Key Demo Page

可 fork 的 Venice API 演示项目（前端 + 后端代理）。

## What

提供 3 个可直接体验的能力：
- 查询账户余额（`/api/balance`）
- 列出模型（`/api/models`）
- 快速对话（`/api/chat`）

前端只把用户 key 存在浏览器 localStorage。后端统一代理请求，避免把密钥写进页面源码。

## Required env

- `VENICE_API_KEY`（可选，作为服务端 fallback key）

## How to start

```bash
pip install flask
python src/server.py
```

## Outputs

- 前端：`src/index.html`
- 后端：`src/server.py`

## Troubleshooting

- 报错“缺少 Venice API Key”：在页面填入 key，或配置 `VENICE_API_KEY`
- 模型请求失败：检查模型 ID 是否在 Venice `/models` 列表中
