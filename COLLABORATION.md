# 🤝 Cyber Nyx 三人协作规范（必读）

> 主创：聆听花瓣雨 · 合创：疯ˣ · 可怕食肉动物
> 目标：**本地改好 → 测试通过 → 再推送**，绝不直接改 GitHub

## 核心铁律

1. **永远本地开发**：改代码 → 本地测试 → 推送
2. **绝不直接在 GitHub 网页改代码**（网页改无法测试、无法检查冲突）
3. **开工先拉**：`git fetch origin && git status`
4. **推送前先合并**：`git pull --rebase origin main`
5. **有冲突先解决**，确认别人代码不被覆盖

## 标准流程

```bash
# ① 开工：拉取最新
git fetch origin
git status                # 确认工作区干净

# ② 本地修改（改你自己的分支）
#    …写代码、改文件…

# ③ 本地测试（必须！）
python -m pytest tests/ -q      # 跑测试
python app.py                    # 冒烟测试

# ④ 提交前合并队友代码（防冲突关键）
git add -A
git stash                       # 若有未提交改动先暂存
git pull --rebase origin main   # 把远端最新代码合进来
git stash pop                   # 恢复你的改动
# → 若有冲突：逐个文件解决，保留双方内容

# ⑤ 提交并推送
git add -A
git commit -m "feat: 你的改动说明"
git push origin main            # 推送 = 发布
```

## 分支约定

| 情况 | 操作 |
|------|------|
| 小改动/修复 | 直接在 main 上改（按流程） |
| 大功能（新模块） | 开 `feat/xxx` 分支 → 完成后 PR 合并 |
| 实验性探索 | `experiment/xxx` 分支，不污染 main |

## 提交信息规范

```
feat:    新功能        fix:     修复
test:    测试          docs:    文档
refactor: 重构         style:   格式
```

示例：`feat: add SSE streaming output` / `fix: memory bridge reconnect`

## 冲突解决原则

- **别人的代码 = 资产**：合并时保留双方内容，不要覆盖
- 冲突文件逐个看：`git diff` 对比，双方内容都保留
- 拿不准就问：在群里喊一声，别闷头覆盖

## 推送前检查清单

- [ ] 本地测试全绿（pytest）
- [ ] 已 pull --rebase，无冲突
- [ ] 提交信息规范
- [ ] 没覆盖队友的改动
