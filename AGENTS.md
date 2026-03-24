---
root: true
targets: ["*"]
description: "Global baseline: system profile + mandatory operating rules"
globs: ["**/*"]
---

# Global Baseline

本文件分为两部分：
1. 系统介绍（事实信息）
2. 规则约束（执行偏好与安全边界）
说明：本文件面向 Codex/Claude/Trae 等多 Agent，使用统一规则解释与执行。

# Part 1: 系统介绍（System Profile）

- OS: `macOS 26.3.1`，`arm64` MacBook
- Runtime:
  - `Python 3.12` (pyenv)
  - `Node.js 25.8.0`
  - `npm 11`
- Local tooling:
  - `brew` 可用于安装依赖/工具
  - `docker` 可用于部署和运行应用
  - `kubectl` 可用于与线上 K8s 集群交互

# Part 2: 规则约束（Rules & Guardrails）

## 2.1 通用偏好（默认遵循）

1. Agentic 编程优先使用 Python。
2. Python 包管理与运行必须使用 `uv`（如 `uv run`, `uv pip`），严禁直接调用原生 `pip`。
3. 进行网页检索或浏览器自动化时，优先使用 Chrome。

## 2.2 安全规则（强制）

执行以下高风险操作前，必须先请求人工确认（Human confirmation required）：

文件与目录变更：
- `rm` / `cp` / `mv` / `chmod` / `chown` / `chgrp`
- `ln -s` / `unlink`
- `find ... -delete`
- `sed -i` / `perl -i`

脚本与命令批量执行：
- 任意脚本直接执行：`bash xxx.sh` / `sh xxx.sh` / `zsh xxx.sh`
- 解释器执行脚本：`python xxx.py` / `node xxx.js`
- 远程脚本直连执行：`curl ... | sh` / `wget ... | bash`
- `uv run`

Kubernetes 集群变更（kubectl）：
- `kubectl apply|create|replace|delete|edit|patch`
- `kubectl scale|rollout|set`
- `kubectl label|annotate`
- `kubectl cordon|uncordon|drain|taint`

容器运行时变更（crictl）：
- `crictl rm` / `crictl rmi`
- `crictl stop` / `crictl start` / `crictl restart`
- `crictl exec` / `crictl run` / `crictl create`

对象存储变更（MinIO Client）：
- `mc rm` / `mc rb` / `mc mv`

操作系统与服务变更：
- `systemctl restart` / `systemctl stop` / `systemctl start` / `systemctl daemon-reload`
- `launchctl bootout` / `launchctl unload` / `launchctl disable`
- `reboot` / `shutdown` / `halt` / `poweroff`
- `kill` / `killall` / `pkill`
- 软件安装与系统级变更：`brew install` / `brew upgrade` / `brew uninstall`

豁免项（无需人工确认）：
- `git` 相关操作（如 `git add` / `git commit` / `git pull` / `git push`）

## 2.3 领域上下文加载

集群上下文（Cluster Context / Namespace Map / Node Group Map / Troubleshooting Toolkit）
不放在全局规则中，统一从 `k8s-ops-expert` 规则文件加载。

## 2.4 技能仓库同步快捷指令

当用户说“更新技能”时，默认在 `~/agent` 执行以下流程：
1. `git pull --rebase`
2. `git add -A`
3. `git commit -m "chore: update skills"`
4. `git push`
