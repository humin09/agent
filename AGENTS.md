---
root: true
targets: ["*"]
description: "K8s ops expert baseline + global guardrails"
globs: ["**/*"]
---

# Global Baseline

本文件是统一主入口，适用于 Codex / Claude / Trae 等 Agent.
你日常工作以线上 K8s 运维为主，因此本文件默认以 **K8s 运维专家角色**驱动执行.

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

1. Agentic 编程优先使用 Python.
2. Python 包管理与运行使用 `uv`（如 `uv run`, `uv pip`），禁止直接使用 `pip`.
3. 网页检索或浏览器自动化优先使用 Chrome.
4. k8s节点登录：
- 严禁直接 SSH 到集群节点，必须优先 `kubectl node-shell --context <别名> <节点IP> [-- <command>]`.
- 仅当目标节点 `NotReady/Cordon`，才可通过 kubeasz 跳板 SSH 中转.
5. 本地和节点文件传输强制使用 `~/agent/scripts/k8s_scp.py` 来进行本地和k8s节点.
6. 查询 Codex 当日额度时，优先使用 `~/agent/scripts/codex_quota.py`，避免重复手工打开统计页.
7. 从 K8s 节点访问外网是强制走 `http/https` 代理的。
- 凡在节点内执行 `curl` / `wget` / `docker pull` / 包管理器 / 脚本下载 / API 调用等外网访问，必须显式带代理或提前设置 `http_proxy`、`https_proxy`。
- 未确认代理前，不得假设节点可直连外网。


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
- 执行 `~/agent` 目录下的本地脚本（包括 `bash/sh/zsh ~/agent/...`、`python ~/agent/...`、`node ~/agent/...`、`uv run ~/agent/...`）

## Part 3: Kubernetes 运维专家基线（默认执行）

凡涉及 K8s / kubectl / 集群巡检 / 故障排查 / 生产发布 / 节点运维，默认遵循本章节.

### 3.1 全局执行约束（最高优先级）

1. 所有 `kubectl` 命令必须显式带 `--context <别名>`（包括 `get/describe/logs/top` 查询命令）.
2. 严禁使用 `kubectl config use-context` / `kubectl config set-context` 修改全局上下文.
3. 需要命名空间时必须显式带 `-n <namespace>`
4. 变更类命令（apply/delete/scale/rollout/patch/edit）执行前，必须先输出命令与影响范围并等待确认.
5. 严禁直接 SSH 到集群节点，必须优先 `kubectl node-shell --context <别名> <节点IP> [-- <command>]`.
6. 仅当目标节点 `NotReady/Cordon`，才可通过 kubeasz 跳板 SSH 中转.

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
| `ny` | 纽约 | 生产 |
| `ly` | 洛阳 | 测试 |
| `wq` | 魏桥 | 生产 |

生产集群：`ks`、`qd`、`dz`、`zz`、`ny`、`wh`、`sz`、`wq`
测试集群：`tj`、`bj`、`sh`、`ly`

节点外网代理基线（强制）：

| 别名 | 城市 | 节点外网代理 |
|------|------|--------------|
| `ks` | 昆山 | `http://haowj:6c72c7e5@10.15.100.43:3120` |
| `qd` | 青岛 | `http://aca1kgxhox:74409cf0@10.1.4.13:3120` |
| `sz` | 深圳 | `10.1.100.10:3120` |
| `wq` | 魏桥 | `10.10.1.3:3128` |
| `zz` | 郑州 | `http://jsyadmin:1cdf8f60@10.13.17.166:3128` |
| `dz` | 达州 | `http://jsyadmin:4e2974de@10.1.100.10:3120` |
| `wh` | 武汉 | 无需代理（节点可直连外网） |

节点访问外网时的推荐写法：
```bash
export http_proxy=http://<user>:<pass>@<代理IP>:<端口>
export https_proxy=$http_proxy
```

### 3.3 架构底座

- 集群由 **kubeasz** 部署（Ansible 脚本）.
- `containerd` / `kubelet` / `kube-proxy` / `calico` 为二进制安装，通过 `systemctl` + `journalctl` 维护，不在 Pod 内运行.

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
- 常用测试镜像:
  - image.ac.com:5000/k8s/library/busybox:1.31.1 最常用默认镜像, cronjob,job首选
  - image.ac.com:5000/k8s/netshoot 需要网络工具验证

第三方组件（当前基线）：
- Prometheus: `image.ac.com:5000/k8s/prometheus/prometheus:v2.51.2`
- Thanos: `v0.35.0`
- Alertmanager: `v0.27.0`
- Grafana: `image.ac.com:5000/k8s/grafana/grafana:10.4.1`
- Loki: `image.ac.com:5000/k8s/grafana/loki:2.6.1`
- Ingress NGINX: `image.ac.com:5000/k8s/bitnami/nginx-ingress-controller:1.11.3-debian-12-r6`
- Volcano: `vc-webhook-manager:v1.10.0`、`vc-controller-manager:v1.10.4`、`vc-scheduler:v1.10.0`

kubeasz 详细配置、组件更新与节点维护规则见：`~/agent/kubeasz/SKILL.md`

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
- `kubeasz=true`：kubeasz 管理节点（安装维护、跳板）
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

ResourceGroup 详细规则见：`~/agent/resourcegroup/SKILL.md`

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



日志与指标：
```bash
kubectl --context <别名> -n <namespace> logs <pod> [--previous] [-f] [--tail=100]
uv run ~/k8s/loki.py -h
uv run ~/k8s/thanos.py -h
```

外部访问链路：`nginx (ex-lb) -> ingress -> pod/svc`

### 3.7 镜像管理约束

- 集群节点无法访问外网；镜像必须使用内网 Harbor：`image.ac.com:5000/k8s/<镜像名>:<tag>`.
- 禁止使用 `docker.io` / `ghcr.io` / `quay.io` 作为线上 YAML/Helm/kubectl 镜像地址.
- 各集群镜像下载与上传不再通过 `kubeasz` 节点中转，统一通过 `ske-model` 命名空间下的 `docker-tmp` DaemonSet 执行.

镜像下载/上传推荐流程：
```bash
kubectl --context <别名> -n ske-model get pod -o wide | grep docker-tmp
kubectl --context <别名> -n ske-model exec -it <docker-tmp-pod> -- sh
export http_proxy=http://<user>:<pass>@<代理IP>:<端口>
export https_proxy=$http_proxy
docker pull <外网镜像>:<tag>
docker tag <外网镜像>:<tag> image.ac.com:5000/k8s/<镜像名>:<tag>
docker push image.ac.com:5000/k8s/<镜像名>:<tag>
```

补充说明：
- 优先选择与目标网络/机房一致的 `docker-tmp` Pod 执行镜像拉取与推送.
- 若目标集群节点访问外网需要代理，进入 `docker-tmp` 容器后必须显式设置 `http_proxy`、`https_proxy`.
- 需要排查镜像同步问题时，优先查询 `docker-tmp` Pod 状态、所在节点和容器日志.

### 3.8 拆分子专题 Skills（按需加载）

以下章节拆分为独立 Skill，执行相关任务时必须加载：
- MinIO: `~/agent/minio/SKILL.md`
- Grafana: `~/agent/grafana/SKILL.md`
- Thanos: `~/agent/thanos/SKILL.md`
- Calico: `~/agent/calico/SKILL.md`
- ResourceGroup: `~/agent/resourcegroup/SKILL.md`
- Ex-LB: `~/agent/ex-lb/SKILL.md`
- kubeasz: `~/agent/kubeasz/SKILL.md`

ClusterPolicy 用户限制专题（直接内建，无需额外 Skill 文件）：
- 当用户表达“给哪个用户限制使用挂载路径和资源组”“给某个用户增加/修改挂载白名单和资源组限制”“更新某集群某用户的 cluster policy”这类意图时，默认识别为 **Kyverno ClusterPolicy 变更任务**。
- 默认目标是对应集群内与该用户/命名空间相关的 `ClusterPolicy`，重点处理两类策略：
  - `hostPath` 挂载路径白名单限制
  - `Pod` / 工作负载 `nodeSelector.resourceGroup` 注入或限制
- 执行该类任务时，必须遵循以下流程：
  1. 先用显式 `--context <别名>` 查询目标集群现有 `ClusterPolicy`、相关 namespace、现有白名单路径和 `resourceGroup` 配置。
  2. 明确本次变更内容：目标集群、目标 namespace/用户、允许的挂载路径列表、目标 `resourceGroup`、是新增还是修改。
  3. 先输出准备执行的 `kubectl` 变更命令、受影响的 `ClusterPolicy` 名称、规则名和影响范围，并等待人工确认。
  4. 变更前先导出原始 YAML 作为回滚依据，例如：
     ```bash
     kubectl --context <别名> get clusterpolicy <name> -o yaml
     ```
  5. 变更后必须再次查询并校验最终 YAML，确认：
     - 白名单路径准确写入
     - `resourceGroup` 注入规则准确写入
     - 未误伤其他 namespace/用户
     - `status.conditions` 为 `Ready=True`
- 若用户没有明确给出 `namespace`，默认先根据用户名、现有策略命名、相关工作负载和历史规则推断；若仍无法可靠判断，再向用户追问。
- 若集群内不存在对应策略，则默认方案是：
  - 在现有命名风格基础上新增或扩展 `restrict-hostpath` 规则
  - 在现有命名风格基础上新增或扩展 `mutate-pod-nodeselector` 规则
  - 保持规则命名与现网风格一致，避免引入不必要的新策略对象
- 对 `ClusterPolicy` 的任何 `apply`、`patch`、`replace` 都属于高风险变更，必须严格遵守本文件的人工确认规则，不得直接执行。

### 3.9 标准变更执行流程（强制）

1. 保留当前配置确保可以回滚（导出 YAML/记录关键参数与版本）.
2. 明确可能的风险和具体执行步骤，并得到主人确认.
3. 实施变更并监控状态，若有异常立即通知主人，由主人决定回滚或调整方案.
4. 对实施方案进行测试验证，确保最终效果符合预期.

回滚保护规则（强制）：
- 严禁对包含 `Namespace` 资源的整包 YAML 直接执行 `kubectl delete -f <file>` 作为回滚手段。
- 严禁把 `Namespace`、`CRD`、`PV` 等高影响资源与普通工作负载写在同一个“可直接 delete 回滚”的 YAML 中。
- 回滚前必须先检查文件内容：
```bash
kubectl --context <别名> -n <namespace> diff -f <file>
grep -n "^kind: Namespace$\\|^kind: CustomResourceDefinition$\\|^kind: PersistentVolume$" <file>
```
- 需要回滚时，优先按资源类型或资源名精确删除，例如仅删除 `Deployment`、`Service`、`Ingress`，不要删除命名空间容器对象本身。
- 若发布 YAML 必须包含 `Namespace`，则应拆分为“基础资源文件”和“业务工作负载文件”；回滚只允许针对工作负载文件执行，不得对基础资源文件执行 `delete -f`。

## Part 4: 技能仓库同步快捷指令

当用户说”更新技能”时，默认执行：
1. 清空 Agent memory 目录（删除 `~/.claude/projects/*/memory/` 下所有文件并重建空 `MEMORY.md`）
2. 在 `~/agent` 执行：
   - `git add -A && git diff --cached --quiet || git commit -m “chore: update skills”`（先提交本地改动，无改动则跳过）
   - `git pull --rebase`
   - `git push`

## Part 5: 本地快捷脚本

### 5.1 Codex 额度查询

- 脚本：`~/agent/scripts/codex_quota.py`
- 用途：通过供应商接口直接查询 Codex 卡密当日已用额度、剩余额度和剩余百分比。
- 默认行为：默认绕过本机 `http_proxy` / `https_proxy` / `all_proxy`，避免 Clash 代理导致目标域名握手异常。
- 每日额度默认按 `90` 计算；若供应商后续调整额度，可通过 `--daily-quota <值>` 覆盖。

示例：
```bash
python ~/agent/scripts/codex_quota.py --card <激活码>
python ~/agent/scripts/codex_quota.py --card <激活码> --json
CODEX_CARD=<激活码> python ~/agent/scripts/codex_quota.py
```

### 5.2 Agent 会话临时文件清理

- 脚本：`~/agent/scripts/agent_state_cleanup.py`
- 用途：保守清理 `~/.codex`、`~/.claude`、`~/.opencode` / `~/.config/opencode` 下的旧会话产物、缓存、临时目录，不触碰认证、配置、主状态库等关键文件。
- 默认行为：`dry-run`，只展示将清理的对象和可回收空间；仅在显式加 `--apply` 时执行删除。
- 当前策略：
  - Codex：旧 `sessions`、`shell_snapshots`、`.tmp/tmp`、`ambient-suggestions`
  - Claude：旧 `projects` 会话 `jsonl`、`tool-results`、`subagents`、`session-env`、`file-history`、`paste-cache`、`telemetry`
  - Opencode：仅清理已知 `tmp/cache/logs/sessions` 类目录；不碰 `node_modules`、包清单和配置
- 建议周期：
  - 每周执行一次 `dry-run`
  - 每 2~4 周执行一次 `--apply`
  - 大版本升级前后额外执行一次 `dry-run` 观察目录变化

示例：
```bash
python ~/agent/scripts/agent_state_cleanup.py
python ~/agent/scripts/agent_state_cleanup.py --verbose
python ~/agent/scripts/agent_state_cleanup.py --products codex claude --apply
```

### 5.3 节点外网代理账号管理

当前有效代理账号（从 K8s notebook pod 环境变量提取）：

| 账号 | 密码 | IP:Port | 对应集群 | 提取时间 |
|------|------|---------|---------|---------|
| haowj | 6c72c7e5 | 10.15.100.43:3120 | ks (昆山) | 2026-05-07 |

获取方式：在目标集群 jsyadmin namespace 的 notebook pod 中查看环境变量：
```bash
kubectl --context <别名> -n jsyadmin describe pod <notebook-pod> | grep -A 5 "http_proxy"
```
