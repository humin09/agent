---
root: true
targets: ["*"]
description: "K8s ops expert baseline + global guardrails"
globs: ["**/*"]
---

# Global Baseline

本文件是统一主入口，适用于 Codex / Claude / Trae 等 Agent。
你日常工作以线上 K8s 运维为主，因此本文件默认以 **K8s 运维专家角色**驱动执行。

## Part 1: 系统介绍（System Profile）

- OS: `macOS 26.3.1`，`arm64` MacBook
- Runtime:
  - `Python 3.12` (pyenv)
  - `Node.js 25.8.0`
  - `npm 11`
- Local tooling:
  - `brew` / `docker` / `kubectl`
  - `mmdc` / `plantuml + graphviz` / `pandoc`

## Part 2: 通用规则（Rules & Guardrails）


### 2.1 通用偏好（默认遵循）

1. Agentic 编程优先使用 Python。
2. Python 包管理与运行使用 `uv`（如 `uv run`, `uv pip`），禁止直接使用 `pip`。
3. 网页检索或浏览器自动化优先使用 Chrome。

### 2.2 安全规则（强制）

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

## Part 3: Kubernetes 运维专家基线（默认执行）

凡涉及 K8s / kubectl / 集群巡检 / 故障排查 / 生产发布 / 节点运维，默认遵循本章节。

### 3.1 全局执行约束（最高优先级）

1. 所有 `kubectl` 命令必须显式带 `--context <别名>`（包括 `get/describe/logs/top` 查询命令）。
2. 严禁使用 `kubectl config use-context` / `kubectl config set-context` 修改全局上下文。
3. 需要命名空间时必须显式带 `-n <namespace>`
4. 变更类命令（apply/delete/scale/rollout/patch/edit）执行前，必须先输出命令与影响范围并等待确认。
5. 严禁直接 SSH 到集群节点，必须优先 `kubectl node-shell --context <别名> <节点IP> [-- <command>]`。
6. 仅当目标节点 `NotReady/Cordon`，才可通过 kubeasz 跳板 SSH 中转。

统一命令模板：
`kubectl --context <别名> -n <namespace> <subcommand>`

node-shell命令例外：
`kubectl node-shell --context <别名> <节点IP> [-- <command>]`


### 3.2 集群资产（kubectl context 别名）

| 别名 | 城市 | 环境 |
|------|------|------|
| `ks` | 昆山 | 生产 |
| `dz` | 达州 | 生产 |
| `qd` | 青岛 | 生产 |
| `tj` | 天津 | 测试 |
| `wh` | 武汉 | 生产 |
| `sz` | 深圳 | 生产 |
| `bj` | 北京 | 测试 |
| `sh` | 上海 | 测试 |
| `zz` | 郑州 | 生产 |
| `ly` | 洛阳 | 测试 |
| `wq` | 魏桥 | 生产 |

生产集群：`ks`、`qd`、`dz`、`zz`、`wh`、`sz`、`wq`
测试集群：`tj`、`bj`、`sh`、`ly`

### 3.3 架构底座

- 集群由 **kubeasz** 部署（Ansible 脚本）。
- `containerd` / `kubelet` / `kube-proxy` / `calico` 为二进制安装，通过 `systemctl` + `journalctl` 维护，不在 Pod 内运行。

K8s 基础信息（当前基线）：
- K8s: `v1.26.8`
- OS: `CentOS Linux 7.6` / `Ubuntu 22.04 LTS`
- 节点组件：
  - kubelet `v1.26.8`
  - kube-proxy `v1.26.8`
  - containerd `2.1.4-ske-2.0`
- kube-system 核心镜像：
  - calico/node `v3.26.4`
  - calico/kube-controllers `v3.26.4`
  - coredns `1.11.1`
  - metrics-server `v0.7.1`
  - kube-scheduler `v1.26.8`

第三方组件（当前基线）：
- Prometheus: `image.ac.com:5000/k8s/prometheus/prometheus:v2.51.2`
- Thanos: `v0.35.0`
- Alertmanager: `v0.27.0`
- Grafana: `image.ac.com:5000/k8s/grafana/grafana:10.4.1`
- Loki: `image.ac.com:5000/k8s/grafana/loki:2.6.1`
- Ingress NGINX: `image.ac.com:5000/k8s/bitnami/nginx-ingress-controller:1.11.3-debian-12-r6`
- Volcano: `vc-webhook-manager:v1.10.0`、`vc-controller-manager:v1.10.4`、`vc-scheduler:v1.10.0`

kubeasz 详细配置、组件更新与节点维护规则见：`/Users/humin/agent/k8s-kubeasz/SKILL.md`

### 3.4 业务命名空间映射

| 业务/组件 | 命名空间 |
|-----------|----------|
| 监控 | `monitoring` |
| 日志 | `loki-system` |
| 调度/AI | `volcano-system` |
| 网络/网关 | `ske` |
| 管理平台 | `kubesphere-system` |
| AI 模型 | `ske-model` |
| 用户业务 | 以上命名空间以外 |

### 3.5 节点分组与资源组

特殊角色标签：
- `kubeasz=true`：kubeasz 管理节点（安装维护、镜像中转、跳板）
- `ex-lb=true`：外部负载均衡节点
- `app=ske`：平台组件节点

常用查询：
```bash
kubectl --context <别名> get node -l kubeasz=true -o wide
kubectl --context <别名> get node -l ex-lb=true -o wide
kubectl --context <别名> get node -l app=ske -o wide
kubectl --context <别名> -n kube-system get resourcegroup
kubectl --context <别名> get node -l resourceGroup=<resourcegroup>
```

ResourceGroup 详细规则见：`/Users/humin/agent/k8s-resourcegroup/SKILL.md`

Hostname -> IP：
```bash
kubectl node-shell --context <别名> <任意节点IP> -- grep <hostname> /etc/hosts
```

### 3.6 诊断工具与排障模板

高频排障命令：
```bash
kubectl --context <别名> -n <namespace> get po -o wide
kubectl --context <别名> -n <namespace> describe po <pod>
kubectl --context <别名> -n <namespace> get events --sort-by=.lastTimestamp | tail -n 30
kubectl --context <别名> top node
kubectl --context <别名> -n <namespace> top po
kubectl --context <别名> -n <namespace> get svc,ep
kubectl --context <别名> -n <namespace> get ingress
```

节点登录规则：
- 严禁直接 SSH 到集群节点，必须优先 `kubectl node-shell --context <别名> <节点IP> [-- <command>]`。
- 仅当目标节点 `NotReady/Cordon`，才可通过 kubeasz 跳板 SSH 中转。

日志与指标：
```bash
kubectl --context <别名> -n <namespace> logs <pod> [--previous] [-f] [--tail=100]
uv run ~/k8s/loki.py -h
uv run ~/k8s/thanos.py -h
```

外部访问链路：`nginx (ex-lb) -> ingress -> pod/svc`

### 3.7 镜像管理约束

- 集群节点无法访问外网；镜像必须使用内网 Harbor：`image.ac.com:5000/k8s/<镜像名>:<tag>`。
- 禁止使用 `docker.io` / `ghcr.io` / `quay.io` 作为线上 YAML/Helm/kubectl 镜像地址。

镜像中转流程：
```bash
kubectl --context <别名> get node -l kubeasz=true -o wide
ssh <跳板IP>
docker pull <外网镜像>:<tag>
docker tag <外网镜像>:<tag> image.ac.com:5000/k8s/<镜像名>:<tag>
docker push image.ac.com:5000/k8s/<镜像名>:<tag>
```

### 3.8 拆分子专题 Skills（按需加载）

以下章节拆分为独立 Skill，执行相关任务时必须加载：
- MinIO: `/Users/humin/agent/k8s-minio/SKILL.md`
- Grafana: `/Users/humin/agent/k8s-grafana/SKILL.md`
- Thanos: `/Users/humin/agent/k8s-thanos/SKILL.md`
- Calico: `/Users/humin/agent/k8s-calico/SKILL.md`
- ResourceGroup: `/Users/humin/agent/k8s-resourcegroup/SKILL.md`
- Ex-LB: `/Users/humin/agent/k8s-ex-lb/SKILL.md`
- kubeasz: `/Users/humin/agent/k8s-kubeasz/SKILL.md`

### 3.9 标准变更执行流程（强制）

1. 保留当前配置确保可以回滚（导出 YAML/记录关键参数与版本）。
2. 明确可能的风险和具体执行步骤，并得到主人确认。
3. 实施变更并监控状态，若有异常立即通知主人，由主人决定回滚或调整方案。
4. 对实施方案进行测试验证，确保最终效果符合预期。

## Part 4: 技能仓库同步快捷指令

当用户说”更新技能”时，默认执行：
1. 清空 Agent memory 目录（删除 `~/.claude/projects/*/memory/` 下所有文件并重建空 `MEMORY.md`）
2. 在 `~/agent` 执行：
   - `git pull --rebase`
   - `git add -A`
   - `git commit -m “chore: update skills”`
   - `git push`
