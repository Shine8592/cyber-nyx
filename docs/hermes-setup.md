# Hermes 内核接入指南

> 前提：Cyber Nyx 运行用户（如 `yaner`）需要能执行 Hermes CLI。
> 常见问题：Hermes 的 venv 解释器位于 `/root/.local/share/uv/python/...`，
> 普通用户无 `/root` 访问权限，直接运行 `hermes` 会报
> `bad interpreter: Permission denied`。

## 方案 A：把 Hermes venv 迁移到用户可读位置（推荐）

需要 **root** 执行一次（以下以 `yaner` 为例）：

```bash
# 1. 复制 venv 到用户目录
cp -a /usr/local/lib/hermes-agent/venv /home/yaner/hermes-venv

# 2. 修正解释器路径（venv 里的 shebang 指向 /root/...，需重写）
cd /home/yaner/hermes-venv
sed -i 's|/usr/local/lib/hermes-agent/venv/bin/python|/home/yaner/hermes-venv/bin/python|g' \
  bin/hermes bin/pip bin/activate 2>/dev/null

# 3. 把软链 python → /root/... 改为本机系统 python（或复制解释器）
ls -l bin/python   # 若指向 /root/...，替换为：
ln -sfn $(command -v python3) bin/python

# 4. 授权
chown -R yaner:yaner /home/yaner/hermes-venv
chmod -R u+rwx /home/yaner/hermes-venv

# 5. 验证（yaner 身份执行）
su yaner -c '/home/yaner/hermes-venv/bin/hermes --version'
```

> 注意：若步骤 3 替换了 python 解释器，venv 内的依赖（fastapi 等）仍按
> 原路径链接，可能失效；更稳的做法是保留原 venv 不动，改用**方案 C**
> （root 起 gateway）或**方案 B**（sudo）。

## 方案 B：给运行用户配 sudo NOPASSWD

需要 **root** 编辑 `/etc/sudoers.d/hermes`：

```bash
# root 执行：visudo -f /etc/sudoers.d/hermes
yaner ALL=(ALL) NOPASSWD: /usr/local/lib/hermes-agent/venv/bin/hermes
```

然后 Cyber Nyx 设置界面的"可执行路径"填：

```
sudo /usr/local/lib/hermes-agent/venv/bin/hermes
```

（adapter 通过 `subprocess` 调用，`sudo` 以列表形式传参即可）

## 方案 C：root 起 Hermes gateway，adapter 走 HTTP

系统已存在 `hermes gateway run`（root 身份）时，把 gateway 暴露端口：

```bash
# root 执行：启动 gateway 并监听某端口（如 8898）
hermes gateway run --port 8898 --host 0.0.0.0
```

后续在 `bridges/hermes_adapter.py` 增加 HTTP 传输模式（`NYX_HERMES_HTTP`），
设置界面填 `http://127.0.0.1:8898` 即可。此方案需要一次小改代码。

## 接入步骤（权限解决后）

1. 打开 Cyber Nyx 页面 → ⚙️ 设置
2. "可执行路径"填入方案 A/B 得到的命令路径
3. 点"保存并应用"——状态区显示"✅ Hermes 内核在线"即接入成功
4. 也可在 `config.json` 中直接配置：
   ```json
   { "hermes": { "bin": "/home/yaner/hermes-venv/bin/hermes" } }
   ```

## 验证

```bash
# 命令行验证内核可用
/home/yaner/hermes-venv/bin/hermes -z "说一句话"
# API 验证
curl http://127.0.0.1:8899/api/settings   # hermes.online 应为 true
```
