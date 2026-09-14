# 5093-intro — 个人介绍页

## What

一个中文个人介绍单页站点，基于 StyleShout 的 Luther 模板定制：

- 首页大图与一句话定位
- 关于我（简介 + 头像）
- 能力清单（技能条）
- 经历与教育时间线
- 作品集（6 个卡片，点击弹出详情）
- 联系方式（邮箱 + 社交链接）

所有占位文案已中文化，模板自带的虚构名人推荐语已移除。中文字体回退链为
`PingFang SC` / `Hiragino Sans GB` / `Microsoft YaHei` / `Noto Sans SC`。

## Required env

无。纯静态站点，不需要任何环境变量或 API Key。

## How to start

本地静态服务：

```bash
cd output/projects/5093-intro
python3 -m http.server 9082
```

然后访问 `http://localhost:9082/`。

公开访问地址：https://5093-intro.community.iamstarchild.com/

## Outputs

- 静态站点文件：`index.html`、`css/`、`js/`、`images/`
- 预览服务端口：9082
- 公开链接与画廊条目（slug `5093-intro`）

## Troubleshooting

- **首屏空白**：模板带 preloader 动画，需等待约 8 秒才渲染完成；截图或自动化测试要相应延时。
- **中文字体显示异常**：检查系统是否命中回退链中的任一字体，Linux 环境建议安装 `Noto Sans SC`。
- **作品弹窗打不开**：确认 `js/` 下的脚本已随 `index.html` 一同部署，且路径未被改写。
- **公开链接 404**：链接依赖预览服务在 9082 端口运行，服务停止后链接不可访问。
