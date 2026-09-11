# personal-intro

## What
一个静态个人介绍页，基于 HTML5 UP「Read Only」模板定制（浅色侧栏式布局，含关于我 / 我能做什么 / 一些经历 / 联系我 四个板块），纯 HTML/CSS/JS，无任何后端依赖。

## Required env
无。全部静态文件，不需要任何环境变量。

## How to start
直接用浏览器打开 `index.html` 即可；或在本目录起一个静态服务器：
```
python3 -m http.server 9081
```

## Outputs
`index.html` — 页面入口；`assets/` — 样式与脚本；`images/` — 头像、横幅与配图。发布后可通过公开链接访问。

## Troubleshooting
- 页面样式错乱：确认 `assets/css/main.css` 与 `assets/webfonts/` 一起拷贝。
- 图标不显示：FontAwesome 依赖 `assets/webfonts/`，勿单独复制 CSS。
- 想换配色：改 `assets/css/main.css` 中 accent 颜色变量（当前为青绿色系）。
