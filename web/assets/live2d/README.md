# Live2D 数字形象（可选升级）

Nyx 默认使用**内置 SVG 月亮精灵**（零依赖、离线可用、表情联动完整）。

如果你希望小夜升级为**真正的 Live2D 动态形象**，按以下步骤：

## 使用方法

1. 准备一个 Live2D 模型（`.model3.json` + 配套纹理/动作文件）
   - 可从 [Live2D 官网](https://www.live2d.com/en/download/sample-data/) 下载官方免费示例模型
   - 或使用社区模型（如免费模型站）

2. 把整个模型文件夹的内容放进本目录：

   ```
   web/assets/live2d/
     ├── 你的模型.model3.json
     ├── *.png（纹理）
     └── *.motion3.json（动作，可选）
   ```

3. 重新打开 Nyx（或刷新页面），自动检测到 `.model3.json` 后即用 Live2D 渲染

## 渲染依赖（二选一）

- **本地优先**：把 `pixi.min.js` 和 `pixi-live2d-display.min.js` 也放进本目录（离线可用）
- **在线兜底**：未放置本地库时，会尝试从 jsdelivr CDN 加载（需联网）

## 表情联动

对话情绪（happy/sad/curious/angry/surprised/shy）会自动尝试驱动 Live2D 的表情参数；
模型没有对应表情参数时自动静默，不影响使用。

## 回退

删除本目录里的 `.model3.json`（或清空目录），重启即恢复为内置 SVG 月亮精灵。
