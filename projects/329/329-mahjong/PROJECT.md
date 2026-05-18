# 中国麻将 Chinese Mahjong

## What

一个纯前端的中国麻将单机小游戏，提供 1 名玩家对战 3 名 AI。

## Required env

无。该项目不依赖任何环境变量。

## How to start

在项目目录下启动静态文件服务：

```bash
python -m http.server 9080
```

然后在浏览器访问：

```text
http://localhost:9080/src/
```

## Outputs

- `src/index.html`：游戏入口页面
- `src/css/style.css`：样式文件
- `src/js/*.js`：游戏逻辑与 AI 逻辑

## Troubleshooting

- 如果页面资源加载失败，请确认是从 HTTP 服务访问（不是直接双击打开 `index.html`）。
- 如果 9080 端口被占用，请先释放端口后重试。
