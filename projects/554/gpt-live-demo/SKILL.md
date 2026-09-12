---
name: gpt-live-demo
version: 0.1.0
description: >
  GPT-Live 语音接线员 Demo — WebRTC 语音通话前端 + Express 中继服务器 + Starchild brain 桥接。
  用户通过浏览器直接与 GPT-Live 语音模型对话，对话内容由 Starchild agent 作为后端大脑处理。
  适用于：语音 Demo 演示、GPT-Live 中继服务开发、实时语音 + AI 代理集成原型。
tags: [voice, gpt-live, webrtc, demo, relay-server]
author: Starchild
---

# GPT-Live 语音接线员 Demo

## 概述

本 skill 封装了一个完整的 GPT-Live WebRTC 语音 Demo：

- **Web 前端**（`scripts/index.html`）：纯浏览器 WebRTC 客户端，含通话控制、事件日志、按秒计费显示
- **中继服务器**（`scripts/server.mjs`）：Node.js/Express，负责向 OpenAI 申请 WebRTC session 并将委派任务转发给 Starchild agent
- **部署说明**（`references/deploy.md`）：本地开发与生产部署步骤

## 架构

```
浏览器 (index.html)
  │  WebRTC audio
  │  DataChannel (oai-events)
  ▼
OpenAI GPT-Live (gpt-live-1)
  │  client delegation 事件
  ▼
server.mjs (/api/agent)
  │  HTTP SSE stream
  ▼
Starchild agent (localhost:8000/chat/stream)
  │  结果回传
  ▼
GPT-Live → 语音播报
```

## 快速开始

### 1. 安装依赖

```bash
cd <skill-dir>/scripts
npm install
```

### 2. 设置环境变量

```bash
export OPENAI_API_KEY=sk-...   # 需要有 gpt-live-1 访问权限
export PORT=3000               # 可选，默认 3000
```

### 3. 启动服务

```bash
node server.mjs
```

然后打开 `http://localhost:3000` 即可开始语音通话。

> **前提**：Starchild agent 的 `/chat/stream` 端点须在 `localhost:8000` 运行；
> 若你在 Starchild 平台内使用本 skill，该端点已自动可用。

## 文件说明

| 文件 | 说明 |
|------|------|
| `scripts/server.mjs` | Express 中继服务器（WebRTC session 代理 + brain 桥接） |
| `scripts/index.html` | 浏览器前端（WebRTC + UI + 计费器） |
| `scripts/package.json` | Node.js 依赖（express, openai） |
| `references/deploy.md` | 本地开发与生产部署完整指南 |
| `references/api-notes.md` | GPT-Live delegation API 要点与已知坑 |

## 使用本 skill 的场景

当用户要求：
- 启动 / 演示 GPT-Live 语音 Demo
- 修改语音接线员的系统提示（`LIVE_PROMPT`）
- 调整 delegation 策略（何时委派给 Starchild brain）
- 部署到生产（Fly.io / Docker / Nginx 反代）

→ 读 `references/deploy.md` 获取完整步骤。

## 注意事项

- `OPENAI_API_KEY` 必须有 `gpt-live-1` 模型的访问权限（需申请 Beta 访问）
- 服务默认仅监听本地，生产部署前须在 `/api/session` 加鉴权
- 中继服务器保存对话历史在内存中（`histories` Map），重启即清空；生产环境建议持久化
- 计费估算基于 $0.05/分钟（gpt-live-1 语音），后端 brain 调用费用另计
