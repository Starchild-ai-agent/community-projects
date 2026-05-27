## What

一个 macOS 狗狗桌宠 Electron 项目：
- 透明无边框始终置顶宠物窗口（可拖动、可交互）
- 控制面板（上传/切换/删除狗狗素材，实时编辑文案与大小）
- 支持 GIF/WEBP 图片素材与 WEBM/MP4/MOV 视频素材
- 本地配置持久化到 `assets/config.json`

## Required env

无必需环境变量。

## How to start

```bash
npm install
npm start
```

> 说明：在无 GUI 的 Linux 容器内，Electron 无法拉起图形窗口；请在本机 macOS/Windows/Linux 桌面环境运行。

## Outputs

- `main.js`: Electron 主进程（双窗口、IPC、托盘、自启动）
- `preload.js`: 安全桥接 API
- `pet.html`: 桌宠窗口与交互
- `panel.html`: 控制面板
- `assets/config.json`: 运行时自动生成
- `assets/user-media/`: 用户上传素材存储目录

## Troubleshooting

1. 启动时报缺少 GTK / 图形库：
   - 属于无桌面环境容器限制，请在本机桌面系统运行。
2. 上传素材后不显示：
   - 确认素材扩展名为 `.webp .webm .mp4 .mov .gif`。
3. 视频不能自动播放：
   - 已设置 `muted + autoplay + loop + playsinline`，如仍异常请转码为 `webm` 或标准 H.264 mp4。
