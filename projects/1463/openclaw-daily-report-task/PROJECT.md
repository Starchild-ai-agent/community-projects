# OpenClaw 日报分析 Task

自动抓取 OpenClaw 仓库最近 24 小时 commits/releases，生成中文日报并推送。

## What

这是一个 `task` 类型项目，核心逻辑在 `src/run.py`：
- 调用本地 Agent 接口执行数据抓取和分析
- 强约束 JSON 输出（`summary` + `content`）
- 多级解析容错，失败时回退原文推送
- 通过 `/push` 发送标题 + 正文

## Required env

无必须环境变量。

## How to start

1. 先 fork 安装这个项目。
2. 安装后会自动注册为 **paused** 的任务。
3. 进入任务列表启用，或手动设置你想要的 cron（默认建议 `59 16 * * *`，UTC）。

## Outputs

每次执行向用户推送一条 OpenClaw 日报：
- 标题：`summary`
- 正文：`content`（Markdown）

## Troubleshooting

- 若出现 GitHub 请求异常：稍后重试（可能是速率限制或网络抖动）
- 若分析返回非 JSON：脚本会自动回退原文并继续推送
- 若无推送：检查任务是否已激活，以及 push 通道是否可用
