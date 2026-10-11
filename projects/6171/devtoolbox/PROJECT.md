# DevToolbox — 开发者多合一工具箱

## What
纯前端、零依赖的开发者工具集合（12 合 1）：JSON 格式化/压缩/键排序、YAML ⇄ JSON 互转、时间戳转换、Base64/URL 编解码、UUID 生成、SHA-256/SHA-1 哈希、JWT 解析、命名转换、正则测试、逐行文本 Diff、二维码生成。深色科技风单页应用。

## Required env
无。本项目为纯前端应用，不需要任何环境变量或 API 密钥（见 .env.example）。

## How to start
直接用浏览器打开 `index.html` 即可，无需构建、无外部依赖。

## Outputs / Behavior
浏览器内渲染交互式工具面板；所有计算在本地完成，数据不出设备；无网络请求（二维码除外，走公共渲染 API）。

## Troubleshooting
- 页面空白：确认使用现代浏览器（Chrome/Edge/Firefox/Safari 近两年版本）。
- Base64 解码报错：输入需为合法 Base64，含中文请先编码再传输。
- 二维码不显示：该功能走公共 API，需网络可用。
