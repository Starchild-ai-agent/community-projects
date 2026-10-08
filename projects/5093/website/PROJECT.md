# 个人介绍页（Hola 模板 · 中文定制版）

基于 [StyleShout Hola](https://www.styleshout.com/free-templates/hola/) 模板定制的单页中文个人介绍站。

## What

单页静态个人介绍站：首页 Hero、关于、技能条、经历时间线、作品集（6 卡 + PhotoSwipe 灯箱）、统计、联系表单、页脚。全部文案为中文占位内容（占位人物 Alex Chen），时间线处有 `<!-- 占位内容，待替换为真实经历 -->` 标记；`css/main.css` 末尾已追加 PingFang SC / Microsoft YaHei 中文字体回退。

## Required env

无。本项目为纯静态站点，不依赖任何环境变量、密钥或后端服务。

## How to start

```bash
# 本地预览（默认端口 8080）
python3 -m http.server 8080
# 浏览器打开 http://localhost:8080/
```

无构建步骤。替换占位内容：直接编辑 `index.html` 中的文案与链接即可。

## Outputs / Behavior

- 输出：可直接托管的静态站点（`index.html` 为唯一入口）
- 交互：平滑滚动导航、技能条动画、作品集灯箱、滚动计数动画（模板自带 JS）
- 联系表单为静态展示（无后端处理逻辑）

## Troubleshooting

- 页面空白：确认通过 HTTP 服务访问而非 `file://` 直接打开（部分浏览器策略会拦截字体/JS）
- 字体显示异常：`css/main.css` 末尾的中文字体回退依赖系统字体（PingFang SC / Microsoft YaHei / Noto Sans SC）
- 表单点击无响应：属预期行为，后端未实现；可接入任意表单服务后填写 `form` 的 `action`

## 结构

```
index.html      单入口页面
css/            样式（main.css 末尾含中文字体回退）
js/             jQuery 与模板脚本
images/         模板图片资源
fonts/          Montserrat / Libre Baskerville 字体
```

## 许可

- 模板：StyleShout 免费模板许可
- 定制内容：MIT
