# Star Child Cosmic Portal

## What
一个橙黑配色的 Star Child 品牌门户页面：仅展示 “Star Child” 一行字，所有动效集中在文字上（流光渐变、3D 翻转入场、悬停每字符 3D 倾斜与橙色光晕、鼠标跟随火星光斑、背景熔岩光晕跟随鼠标）。点击文字直接跳转 Star Child 官网。

## Required env
无必填环境变量。

## How to start
直接作为静态页面预览即可，无需构建步骤。

## Outputs
- `index.html`：单文件页面，包含全部样式、动效与点击跳转逻辑

## Troubleshooting
- 如果页面无法公网访问，先确认预览已运行，再重新执行 publish_preview。
- 如果项目发布失败，先检查 `project.yaml` 字段是否完整且 `name` 与目录名一致。
