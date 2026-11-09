# SkillAudit — Agent 技能体检台

浏览器端 `SKILL.md` 静态检查器：粘贴一个技能文件，立刻得到评分、结构缺口与风险清单。全部在本地计算，内容不出浏览器。

## What

Agent 技能（Skill）已经是需要发布、审核、被检索的资产，但手写 SKILL.md 时几乎无法自查：description 写得模型永远不会调用、正文堆到 3 万 token 挤爆上下文、示例里硬编码 API key、正文里藏着远程脚本直通 shell 的写法。

SkillAudit 把这些问题固化成 12 条可执行规则，并给出 A/B/C/D 四档结论：

- **Frontmatter**：YAML 块存在、`name` slug 规范、`description` 长度与「何时使用」触发语密度
- **结构**：正文有效长度、编号步骤/代码块、`references/` 渐进披露
- **成本**：token 估算（CJK 与拉丁字符分开折算）、5000 token 建议线、超限警告
- **安全**：硬编码密钥（OpenAI / GitHub / AWS / Slack / 通用 key=value）、提示注入话术、危险命令（远程脚本管道执行、`rm -rf`、`chmod 777`、`eval`、base64 解码后执行）
- **副作用**：含写/发/交易语义却无确认或 dry-run 提示

评分 = 规则通过率（ok=1 / warn=0.5 / bad=0）− 高危×5 − 中危×2。

## Required env

无。纯静态站，零外部依赖、零网络请求。

## How to start

```bash
python3 -m http.server 9137 --directory .
```

或直接把 `index.html` 用浏览器打开（`file://` 同样可用）。

使用：粘贴 SKILL.md（或点「载入示例」/「选择文件」/拖入文件）→ 点「开始体检」或按 `⌘/Ctrl + Enter`。

## Outputs / Behavior

- 左侧：源码编辑器、技能画像（token / 行数 / 步骤数 / 外部资源引用）、token 预算条与可检索性条
- 右侧：评分环 + 结论档位、12 项规则检查明细（✓ / ! / ✕）、按严重度排序的风险清单
- 「复制 Markdown 报告」/「下载报告」导出 `.md`，可直接贴进 PR 或 issue

## Troubleshooting

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| 点击体检后无变化 | 编辑器为空 | 先粘贴内容或点「载入示例」 |
| 报告说「未检测到 frontmatter」 | 文件没以 `---` 开头 | 在首行加 `---`，补 `name` / `description` 后再 `---` |
| token 数远低于预期 | 估算按 CJK≈1 token/字、拉丁≈3.85 字符/token 折算 | 正常近似值，与具体分词器有 ±10% 偏差 |
| 拖入文件无反应 | 浏览器限制 `file://` 下的 FileReader | 用 `python3 -m http.server` 起本地服务再访问 |
