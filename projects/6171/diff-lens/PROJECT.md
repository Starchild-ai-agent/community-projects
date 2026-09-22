# Diff Lens

## What

Diff Lens 是一个纯前端、零上传的文本/JSON 差异对比工具。粘贴任意两段文本，用 LCS（最长公共子序列）算法生成行级对齐的 diff，支持 unified patch 与 side-by-side 双视图。

核心能力：

1. **行级 LCS diff** — 动态规划求最长公共子序列，删除/新增/保留三类行精确对齐
2. **双视图切换** — Unified patch（`@@ -1,N +1,M @@` 标准格式）与 Side-by-side 并排视图
3. **JSON pretty 模式** — 自动解析并格式化 JSON 后再 diff，避免格式化噪声淹没真实改动
4. **相似度统计** — 实时统计新增/删除/未变行数与整体相似度百分比
5. **导出** — 一键复制 unified patch 到剪贴板，或下载为 `diff.patch`
6. **大文本保护** — 输入规模超过 400 万单元格时自动降级为集合差集算法，避免浏览器卡死

## Required env

无。完全离线运行，所有数据只存在于浏览器内存中，不发送任何网络请求。

## How to start

1. 用浏览器直接打开 `src/index.html`
2. 按流程操作：
   - 点「Load sample」在左右两侧载入示例代码
   - 点「Run diff」生成差异结果（加载示例后已自动运行一次）
   - 切换 `<select>` 在 Unified 与 Side by side 视图间切换
   - 点「JSON pretty mode」进入 JSON 格式化对比模式（按钮高亮表示开启）
   - 点「Swap sides」交换左右两侧内容
   - 点「Copy patch」/「Download」导出 unified patch
   - 快捷键 `⌘/Ctrl + Enter` 重新运行 diff

## Outputs

- `src/index.html` — 单页应用，包含全部 HTML/CSS/JS，无外部依赖
- `project.yaml` — 项目元数据
- `.env.example` — 环境变量模板（当前为空）
- `.gitignore` — Git 忽略规则

## Troubleshooting

| 问题 | 解决 |
|------|------|
| 页面样式异常 | 确认浏览器支持 CSS Grid 与 CSS 变量（Chrome 60+ / Firefox 63+ / Safari 11+） |
| JSON pretty 模式报错 | 检查两侧输入是否为合法 JSON；解析失败会提示具体错误信息，切换回纯文本模式即可 |
| 大文本 diff 很慢 | 输入超过约 200 万字符时算法自动降级为集合差集，结果会丢失行对齐但保持可用 |
| 剪贴板复制失败 | 浏览器需授予剪贴板权限，或改用「Download」导出 |
| 移动端布局错乱 | 屏幕宽度 ≤900px 时自动切换为堆叠布局 |
