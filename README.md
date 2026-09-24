# Personal Skills · ban11111

从真实项目的返工、修复和验收中沉淀可复用的 agent skills。主要内容使用中文，标识、文件结构和调用方式保持跨工具兼容。

## 已有 skills

| Skill | 用途 | 调用 |
| --- | --- | --- |
| [2D 人物骨骼动画](skills/2d-character-animation/SKILL.md) | 人体结构、左右约定、关节拼接、步态、遮挡、连续演出、表情、满场性能与资源缓存 | `$2d-character-animation` |

该 skill 源自《到点下班》的七角色、多队列与电梯动画迭代。[案例复盘](skills/2d-character-animation/references/case-study.md)保留症状、原因、修复与防回归检查；不包含游戏源码、人物素材、玩家数据或第三方 runtime。

## 安装与使用

```bash
git clone https://github.com/ban11111/personal-skills.git
cd personal-skills
python3 scripts/install_skill.py 2d-character-animation
```

默认将指定 skill 的目录链接到 `${CODEX_HOME:-~/.codex}/skills/`，不会覆盖同名目录。可通过 `--target /path/to/agent/skills` 安装到其他支持 `SKILL.md` 的工具。符号链接指向本地克隆，克隆目录需要保留；更新代码前检查变更，然后 `git pull --ff-only`。Windows 或不支持符号链接的环境可使用 `--copy`，后续手动同步副本。

新会话可自动发现，也可以明确调用：

> 使用 $2d-character-animation 检查这个角色走路像倒退、肘关节反折和换动作闪一下的问题。先保留人物比例，给出定位证据，再修改并验证。

> 使用 $2d-character-animation 为七个人物制作走路和各自的生气动作，先完成一个持物角色的审核样片，再批量推广。

仓库同时带有可选的 Codex 插件清单 `.codex-plugin/plugin.json`，直接复用同一份 `skills/`，不维护第二套内容。本仓库没有配置个人 marketplace，也没有安装第三方 skills 或 runtime。

## 结构与扩展

```text
personal-skills/
├── skills/<skill-id>/          # 每个 skill 自包含、可单独安装
│   ├── SKILL.md                # 短入口与按需阅读路由
│   ├── agents/openai.yaml      # Codex 发现信息
│   ├── references/             # 细节、案例、验收方法
│   ├── scripts/                # 确定性检查工具（有需要才创建）
│   └── assets/                 # 交付模板（有需要才创建）
├── catalog.json                # 分类和检索，不按领域嵌套目录
├── scripts/                    # 仓库验证与安装
├── tests/                      # 工具的行为回归
├── .github/workflows/          # CI
└── .codex-plugin/plugin.json   # 可选打包入口
```

增加新领域只需增加 `skills/<skill-id>/` 和目录项；不用新建空分类目录、修改既有 skill，或预装一组依赖。写法和验证规则见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 本地检查

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
python scripts/validate_repo.py
python -m unittest discover -s tests -v
```

动画检查器只需要 Python 标准库。合成测试样例验证检查器，不代表真实人物已通过视觉或手机验收。

## 来源与许可

原创说明、模板与脚本采用 [MIT](LICENSE)。[工具分工与来源](skills/2d-character-animation/references/tool-routing.md)说明与已有 skills 的关系及使用边界；本仓库没有复制它们的实现，也不重新许可第三方美术、字体、模型或动画引擎。
