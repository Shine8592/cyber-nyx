# 内嵌记忆引擎 — universal-agent-memory

本项目在 `vendor/universal-agent-memory/scripts/` 内嵌了自研记忆系统 **universal-agent-memory** 的最新源码，使 cyber-nyx 跨平台开箱即用（无需单独安装记忆系统）。

## 版本与来源

- **版本**：v3.0.2（2026-08-07）
- **上游仓库**：[Shine8592/universal-agent-memory](https://github.com/Shine8592/universal-agent-memory)
- **本地工作副本**：`E:\工作类\研发\universal-agent-memory`
- **同步规则**：上游仓库升级时，将 `scripts/*.py` 复制到本目录。

## 升级方法

1. 本地更新 `universal-agent-memory` 仓库（`git pull origin main`）
2. 复制最新引擎：
   ```bash
   cp ~/universal-agent-memory/scripts/*.py vendor/universal-agent-memory/scripts/
   ```
3. 更新上方「版本」说明
4. 跑测试：`python -m pytest tests/ -q`
5. 提交并在 README 标注新版本

## 运行机制

`bridges/memory_bridge.py` 通过 **MCP JSON-RPC over stdio** 与本目录的 `mcp_server.py` 通信，自动优先探测本内嵌引擎。

- 嵌入模型首次运行时下载到 `~/.config/opencode/memory/models/`（约 250MB）
- 记忆数据默认存于 `~/.config/opencode/memory/`，可用环境变量 `MEMORY_STORE` 覆盖