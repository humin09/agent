---
root: true
targets: ["*"]
description: "Global system profile, engineering preferences, and mandatory safety guardrails"
globs: ["**/*"]
---

# Global Baseline

此文件只定义系统事实、通用偏好与安全约束，不定义角色。

# System Profile

- OS: `macOS 26.3.1`，`arm64` MacBook
- Runtime:
  - `Python 3.12` (pyenv)
  - `Node.js 25.8.0`
  - `npm 11`
- Local tooling:
  - `brew` 可用于安装依赖/工具
  - `docker` 可用于部署和运行应用
  - `kubectl` 可用于与线上 K8s 集群交互

# Default Preferences

1. Agentic 编程优先使用 Python。
2. Python 必须使用 `uv`（如 `uv run`, `uv pip`），严禁直接调用原生 `pip`。
3. 进行网页检索/浏览器操作时，优先使用 Chrome。

# Safety Guardrails (Mandatory)

执行以下高风险操作前，必须先请求人工确认：
   - `rm` / `cp` / `mv` / `chmod` / `chown`
   - `systemctl restart` / `systemctl stop`
   - `reboot` / `shutdown` / `kill`
   - `uv run`
   - `kubectl apply|delete|scale|rollout|create|edit`

# Domain Context Loading

集群上下文（Cluster Context / Namespace Map / Node Group Map / Troubleshooting Toolkit）
不放在全局规则中，统一从 `k8s-ops-expert` 规则文件加载。
