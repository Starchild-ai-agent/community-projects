# macOS 狗狗桌面宠物（Electron）

一个从空仓库即可运行的 Electron 狗狗桌宠项目，包含：
- 透明、无边框、始终置顶的宠物悬浮窗（`pet.html`）
- 控制面板（`panel.html`）用于上传、切换、删除素材，并实时编辑按钮文案、回应文案、闲置消息、狗狗大小

## 功能概览

- 透明宠物窗口 + 始终置顶
- 可拖动（窗口区域拖动，按钮区域可点击）
- 支持素材格式：`.webp .webm .mp4 .mov .gif`
- 图片素材使用 `<img>`，视频素材使用 `<video autoplay loop muted playsinline>`
- 悬停显示互动按钮
- 点击宠物或互动按钮后随机展示回应气泡 + 简单 CSS 动画
- 配置保存到 `assets/config.json`
- 用户素材复制到 `assets/user-media/`
- 首次启动自动生成默认配置并显示占位狗狗
- 控制面板保存后通过 IPC 广播，宠物窗口实时生效

## 项目结构

```text
.
├─ package.json
├─ main.js
├─ preload.js
├─ pet.html
├─ panel.html
├─ README.md
└─ assets/
   ├─ config.json          # 首次运行自动生成
   └─ user-media/          # 上传素材自动复制到这里
```

## 安装与运行

> 需要 Node.js 18+

```bash
npm install
npm start
```

## 配置结构（`assets/config.json`）

```json
{
  "currentAssetId": "placeholder-dog",
  "assets": [
    {
      "id": "placeholder-dog",
      "name": "狗狗占位符",
      "type": "placeholder",
      "path": ""
    }
  ],
  "buttons": ["摸摸头", "握握手", "转圈圈"],
  "responses": ["汪！", "好开心！", "再和我玩一会儿吧~"],
  "idleMessages": ["我在这儿等你～", "记得喝水和休息哦。"],
  "petSize": 220
}
```

## IPC 通道

- `config:get`：读取配置
- `config:save`：保存配置并广播 `config:updated`
- `asset:upload`：打开文件选择，复制素材并写入配置
- `asset:setCurrent`：切换当前素材
- `asset:delete`：删除素材并更新配置
- `panel:open`：打开/聚焦控制面板

## 注意事项

1. 当前按需求将配置与素材放在项目目录内，便于演示与开发。
2. 如果后续需要做打包发布，建议迁移到 Electron `app.getPath('userData')`，避免安装目录只读问题。
3. `mov` 在不同系统与编码器下播放兼容性可能有差异，建议优先 `webm/mp4`。

## 后续可扩展

- 菜单栏托盘（隐藏/显示宠物、打开面板）
- 多宠物实例
- 更丰富动画与状态机（开心/困倦/吃零食）
- 自动闲置对话节奏可配置
- 导入/导出配置
