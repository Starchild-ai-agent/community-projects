# SkillAudit — Agent 技能体检台

浏览器端的 `SKILL.md` 静态检查器。粘贴（或拖入）一个技能文件，立刻得到评分、结构缺口和风险清单——**所有分析在本地完成，内容不会离开浏览器**。

## 为什么做这个

2026 年的 Agent 生态里，技能（Skill）已经变成一种需要"发布、审核、被检索"的资产：GitHub Trending 上周被 `security-audit-skill`、`impeccable`、`billion-context` 这类"技能层"项目占据。但绝大多数人写 SKILL.md 时仍在凭感觉——description 写得模型永远不会调用，正文堆到 3 万 token 挤爆上下文，或者把 API key 直接写进示例里。

SkillAudit 把这些经验固化成 13 条可执行规则。

## 检查项

| 类别 | 规则 |
| --- | --- |
| Frontmatter | YAML 块存在、`name` slug 规范、`description` 长度与「何时使用」触发语密度 |
| 结构 | 正文有效长度、编号步骤/代码块、`references/` 渐进披露 |
| 成本 | token 估算（CJK 与拉丁字符分开折算）、5000 token 建议线、体积超限警告 |
| 安全 | 硬编码密钥（OpenAI / GitHub / AWS / Slack / 通用 `key=value`）、提示注入话术、危险命令（`curl \| sh`、`rm -rf`、`chmod 777`、`eval`、base64 管道执行） |
| 副作用 | 含写/发/交易语义却无确认或 dry-run 提示 |

评分 = 规则通过率（ok=1 / warn=0.5 / bad=0）− 高危项×5 − 中危项×2，映射 A/B/C/D 四档结论。

## 使用

打开页面 → 粘贴 SKILL.md（或点「载入示例」/「选择文件」/直接拖入）→ 点「开始体检」或按 `⌘/Ctrl + Enter`。

右上报告可「复制 Markdown 报告」或「下载报告」，方便直接贴进 PR 或 issue。

## 技术

- 单页静态站，`index.html` + `style.css` + `app.js`，零依赖、无构建步骤
- 自写的轻量 YAML frontmatter 解析（含 `|` / `>` 块标量折叠）
- 深色科技风：径向光晕 + 网格遮罩 + 青/靛渐变 + 等宽数据字体
- 密钥/注入正则全部在客户端执行，无任何网络请求

## 运行

```bash
python3 -m http.server 9137 --directory .
```

## License

MIT
