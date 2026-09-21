# CronGuru 中文版

## What
cron 表达式人话解释器与执行时间计算器。输入 5 段 cron 表达式，逐字段用中文解释含义，计算未来 10 次执行时间（本地时区），内置 10 个常用模板速查。支持 `*`、`*/n`、范围、逗号列表、月份/星期英文名（feb、sun 等）、7=周日。

## Required env
None. 纯前端，零依赖，所有计算在浏览器本地完成。

## How to start
Open `index.html` in any modern browser, or serve this directory as static files.

## Outputs
- 逐字段中文解释（含每个字段的原始片段与解析结果）
- 未来 10 次执行时间列表（本地时区，带星期）
- 常用模板表（点击「使用」一键填入）

## Troubleshooting
- 报「日 与 星期 不能同时为具体值」：标准 cron 语义限制，把其中一个改成 `*`。
- 报「暂不支持 6 段」：本工具只支持 5 段格式（分 时 日 月 周），不含秒。
