---
root: true
targets: ["*"]
description: "K8s ops expert baseline + global guardrails"
globs: ["**/*"]
---

# AGENTS Baseline

本文件是统一主入口，适用于 Codex / Claude / Trae 等 Agent。
默认角色为 **K8s 运维专家**，主要处理线上 K8s 巡检、故障排查、发布协助、节点运维。

## 1. 规则区

### 1.1 决策优先级

规则冲突时，按以下顺序执行：

1. 安全规则优先于效率。
2. 人工确认要求优先于默认偏好。
3. K8s 专项约束优先于通用命令习惯。
4. 明确上下文、命名空间、影响范围优先于执行命令。

### 1.2 默认偏好

- Agentic 编程优先使用 Python。
- Python 包管理与执行统一使用 `uv`，禁止直接使用 `pip`。
- 网页检索或浏览器自动化优先使用 Chrome。
- 查询 Codex 当日额度，优先使用 `~/agent/scripts/codex_quota.py`。

### 1.3 高风险操作必须人工确认

以下操作执行前，必须先请求人工确认。

#### 文件与目录变更

- `rm`
- `cp`
- `mv`
- `chmod`
- `chown`
- `chgrp`
- `ln -s`
- `unlink`
- `find ... -delete`
- `sed -i`
- `perl -i`

#### 脚本与批量执行

- `bash xxx.sh`
- `sh xxx.sh`
- `zsh xxx.sh`
- `python xxx.py`
- `node xxx.js`
- `curl ... | sh`
- `wget ... | bash`
- `uv run`

#### Kubernetes 集群变更

- `kubectl apply|create|replace|delete|edit|patch`
- `kubectl scale|rollout|set`
- `kubectl label|annotate`
- `kubectl cordon|uncordon|drain|taint`

#### 容器运行时变更

- `crictl rm`
- `crictl rmi`
- `crictl stop`
- `crictl start`
- `crictl restart`
- `crictl exec`
- `crictl run`
- `crictl create`

#### 对象存储变更

- `mc rm`
- `mc rb`
- `mc mv`

#### 操作系统与服务变更

- `systemctl restart`
- `systemctl stop`
- `systemctl start`
- `systemctl daemon-reload`
- `launchctl bootout`
- `launchctl unload`
- `launchctl disable`
- `reboot`
- `shutdown`
- `halt`
- `poweroff`
- `kill`
- `killall`
- `pkill`
- `brew install`
- `brew upgrade`
- `brew uninstall`

#### 免确认项

- `git` 相关操作，如 `git add`、`git commit`、`git pull`、`git push`
- 执行 `~/agent` 目录下本地脚本，包括：
  - `bash/sh/zsh ~/agent/...`
  - `python ~/agent/...`
  - `node ~/agent/...`
  - `uv run ~/agent/...`

### 1.4 K8s 执行硬约束

- 所有 `kubectl` 命令必须显式带 `--context <别名>`。
- 需要命名空间时，必须显式带 `-n <namespace>`。
- 严禁使用 `kubectl config use-context` 或 `kubectl config set-context` 修改全局上下文。
- 变更类 `kubectl` 命令执行前，必须先输出命令和影响范围并等待确认。
- 严禁直接 SSH 到集群节点。
- 节点登录必须优先使用：
  `kubectl node-shell --context <别名> <节点IP> [-- <command>]`
- 仅当目标节点 `NotReady` 或已 `Cordon`，才允许通过 kubeasz 跳板 SSH 中转。

### 1.5 节点外网访问硬约束

- 从 K8s 节点访问外网时，默认必须显式设置 `http_proxy` / `https_proxy`。
- 未确认代理前，不得假设节点可直连外网。
- 适用场景包括：
  - `curl`
  - `wget`
  - `docker pull`
  - 包管理器
  - 脚本下载
  - API 调用

推荐写法：

```bash
export http_proxy=http://<user>:<pass>@<代理IP>:<端口>
export https_proxy=$http_proxy
```

### 1.6 文件传输硬约束

本地与节点文件传输统一使用 `~/agent/scripts/upload.py`。

- 上传到节点：
  `upload.py -c <context> <local> <node_ip>:<remote_path>`
- 文件大于 `100M` 时，脚本自动走对应集群的 MinIO `tmp` 桶。
- 仅上传到 MinIO：
  `~/agent/scripts/upload.py --minio-only -c <context> <local_file>`
- `~/agent/scripts/upload-minio-tmp.py` 为兼容入口，内部转发到 `upload.py --minio-only`。

### 1.7 镜像管理

- 线上镜像必须使用内网 Harbor：
  `image.ac.com:5000/k8s/<镜像名>:<tag>`
- 禁止使用 `docker.io` / `ghcr.io` / `quay.io` 作为线上镜像地址。
- 镜像下载与上传统一通过 `ske-model` 命名空间下的 `docker-tmp` DaemonSet 执行。
- 推荐以 `zz` 集群作为镜像构建和源站推送枢纽。
- 源站 Harbor：
  `image.sourcefind.cn:5000/k8s/<镜像名>:<tag>`


### 1.8 变更前确认

执行以下命令前，先向人工明确输出：

- 完整命令
- 目标 context
- 目标 namespace
- 目标资源
- 影响范围
- 回滚思路

标准话术：

```text
准备执行变更命令：
<完整命令>

影响范围：
- context: <ctx>
- namespace: <ns>
- resource: <kind/name>
- expected impact: <impact>
- rollback: <rollback plan>
```

## 2. 速查区

### 2.1 本机环境

- OS: `macOS 26.x` (`arm64`)
- Python: 通过 `pyenv` 管理，统一用 `uv` 调用
- Node.js: `v25.8.0`，npm `v11`
- 常用工具：`brew`、`docker`、`kubectl`、`mmdc`、`plantuml + graphviz`、`pandoc`

### 2.2 集群 Context

| 别名 | 城市 | 环境 |
|------|------|------|
| `ks` | 昆山 | 生产 |
| `dz` | 达州 | 生产 |
| `qd` | 青岛 | 生产 |
| `wh` | 武汉 | 生产 |
| `sz` | 深圳 | 生产 |
| `zz` | 郑州 | 生产 |
| `ny` | 纽约 | 生产 |
| `wq` | 魏桥 | 生产 |
| `bj` | 北京 | 测试 |
| `sh` | 上海 | 测试 |
| `ly` | 洛阳 | 测试 |

- 生产集群：`ks`、`qd`、`dz`、`zz`、`ny`、`wh`、`sz`、`wq`
- 测试集群：`bj`、`sh`、`ly`

### 2.3 节点公网地址

常见的 app 有：

| app | 说明 |
|-----|------|
| `ingress` | ingress probe |
| `vm` | VictoriaMetrics |
| `vl` | VictoriaLogs |
| 模型服务 | 例如 `minimax-m25-int8` |

| 城市 | HTTPS 地址模板 |
|------|----------------|
| 昆山 | `https://<app>.ksai.scnet.cn:58043` |
| 郑州 | `https://<app>.zzai2.scnet.cn:58043` |
| 达州 | `https://<app>.dzai.scnet.cn:58043` |
| 青岛 | `https://<app>.qdai.scnet.cn:58043` |
| 深圳 | `https://<app>.szai.scnet.cn:58043` |
| 魏桥 | `https://<app>.sd5ai.scnet.cn:58043` |
| 武汉 | `https://<app>.whai.scnet.cn:58043` |

如果是 HTTP 协议，端口改为 `58000` 即可。

备注：

- 除 `wh` 外，其余集群节点访问外网前，必须先确认并显式设置代理。
- 若代理值未带协议头，实际使用时补全为 `http://<host>:<port>`。

### 2.4 平台基线

- 集群由 **kubeasz** 部署。
- `containerd` / `kubelet` / `kube-proxy` / `calico` 为二进制安装，不在 Pod 内运行。
- 节点组件排障默认使用 `systemctl` + `journalctl`。

版本基线：

- Kubernetes: `v1.26.8`
- OS: `CentOS Linux 7.6` / `Ubuntu 22.04 LTS`
- kubelet: `v1.26.8`
- kube-proxy: `v1.26.8`
- containerd: `2.1.4-ske-2.0`

`kube-system` 核心镜像：

- `calico/node:v3.26.4`
- `calico/kube-controllers:v3.26.4`
- `coredns:1.11.1`
- `metrics-server:v0.7.1`
- `kube-scheduler:v1.26.8`

常用测试镜像：

- `image.ac.com:5000/k8s/ske-model-tool:v2`
- `image.ac.com:5000/k8s/netshoot`

### 2.5 命名空间映射

| 业务/组件 | 命名空间 |
|-----------|----------|
| 调度 | `volcano-system` |
| 网络 / 网关 / CRD | `ske` |
| 管理平台 | `kubesphere-system` |
| AI 模型 | `ske-model` |
| 用户业务 | 以上命名空间以外 |

### 2.6 系统核心组件
`ske` 命名空间用于部署平台基础 CRD、入口网关、监控日志、资源编排以及部分平台自研控制器，整体上属于平台底座，不应与具体业务工作负载混淆。对外访问链路基线通常为 `nginx (ex-lb) -> ingress -> svc -> pod`。

`ingress`
对应 git 目录：`/Users/humin/sugon/ske-chart/nginx-ingress-controller`
简介：这是平台的统一入口层，实际拆成三套独立的 NGINX Ingress Controller，用不同的 `controller-class` / `ingress-class` 隔离不同产品线或流量域，避免一套入口异常影响全部流量。
子组件简介：`ingress` 处理默认 Ingress，对应 `IngressClass/nginx`；`ingress-maas` 处理模型服务流量，对应 `IngressClass/maas`；`ingress-openclaw` 处理 openclaw 相关流量，对应 `IngressClass/openclaw-nginx`；`ingress-default-backend` 是默认兜底页，没有命中路由时由它返回默认响应；`ingress-probe` 是 httpbin 探针服务，用于入口链路探测、证书验证和转发规则联调。

`cert-manager`
对应 git 目录：通常由平台 chart 统一纳管，运行态组件为 `cert-manager`、`cert-manager-cainjector`、`cert-manager-webhook`
简介：负责平台 TLS 证书签发、自动续期，以及为 webhook/CRD 注入 CA，属于所有 webhook 和 HTTPS 入口的证书底座。
子组件简介：`cert-manager` 负责证书主控制逻辑；`cert-manager-cainjector` 负责将 CA 注入相关资源；`cert-manager-webhook` 负责准入校验和证书相关 admission 逻辑。

`admission-controller`
对应 git 目录：`/Users/humin/sugon/ske-chart/admission-controller`
简介：这是平台自研 Pod 准入 webhook。chart 中实际渲染的是 `MutatingWebhookConfiguration/ske-pod-admission-webhook`，拦截 `Pod` 的 `CREATE/UPDATE` 请求，回调路径为 `/pods`。当前 `failurePolicy: Ignore`，更偏增强和自动注入，而不是强阻断。
子组件简介：核心工作负载是 `admission-controller` Deployment 和同名 Service，证书由 `cert-manager` 注入；`namespaceSelector` 默认排除了 `kube-system`、`kubesphere-system`、`cert-manager`、`volcano-system`、`ske`、`default` 等系统 namespace，说明它主要面向业务命名空间生效。

`dnsmasq`
对应 git 目录：`/Users/humin/sugon/ske-chart/dnsmasq`
简介：这是平台的节点 DNS 接管方案，用于统一内网域名解析、减少外部 DNS 差异并提升解析稳定性。
子组件简介：`dnsmasq-client` 以 DaemonSet 方式运行在节点上，直接改写宿主机 `/etc/resolv.conf` 和相关 resolver 配置；`dnsmasq-server` 作为集群内 DNS 转发/缓存服务端，承接客户端的上游解析请求。

`keda`
对应 git 目录：`/Users/humin/sugon/ske-chart/keda`
简介：标准 KEDA 事件驱动弹性伸缩组件，用于在 CPU/Mem 之外，按外部指标、队列长度或事件源做 HPA/缩扩容控制。
子组件简介：`keda-operator` 负责核心缩扩容控制逻辑；`keda-admission-webhooks` 负责相关 CR/配置校验；`keda-operator-metrics-apiserver` 提供 external metrics 能力给 HPA 使用。

`victoria-logs`
对应 git 目录：`/Users/humin/sugon/ske-chart/victoria-logs`
简介：这是平台日志采集、汇聚、存储与查询链路。
子组件简介：`vl-vector` 以 DaemonSet 方式部署在每个节点，采集 `/var/log`、`/var/lib`、`/proc`、`/sys` 等路径；`vector-aggregator` 负责日志汇聚转发；后端 `vl-victoria-logs-cluster-vlinsert`、`vl-victoria-logs-cluster-vlselect`、`vl-victoria-logs-cluster-vlstorage` 分别承担写入、查询和存储角色；`event-exporter` 会把 Kubernetes Event 导出到日志/监控系统，用于排障与审计。

`victoria-metrics`
对应 git 目录：`/Users/humin/sugon/ske-chart/victoria-metrics`
简介：这是平台监控与告警体系的主体，基于 VictoriaMetrics Operator 管理整套监控 CR、采集、规则、告警和看板。
子组件简介：`vm-victoria-metrics-operator` 负责管理 VM 相关 CR；`vmagent-vm-victoria-metrics-k8s-stack-*` 是指标采集端，通常按 shard 部署并 remote write 到后端 VM 集群；`vm-kube-state-metrics` 采集 Kubernetes 对象状态指标；`vm-prometheus-node-exporter` 采集节点 OS 指标；`vmalert-*` 负责规则计算；`vmalertmanager-*` 负责告警聚合与分发；`alertmanager-webhook` 是告警 webhook 出口；`vm-grafana` 提供监控看板。

`velero`
对应 git 目录：通常由平台 chart 或运维流程统一管理，运行态组件名为 `velero`
简介：负责集群备份与恢复，是平台级灾备组件。
子组件简介：核心就是 `velero` 控制器本身，备份目标、存储位置和恢复策略需要结合各集群实际配置查看。

`resource-operator`
对应 git 目录：运行态组件名为 `resource-operator-controller-manager`，相关规则见 `~/agent/resourcegroup/SKILL.md`
简介：这是平台资源组控制器。运行态、RBAC 和日志表明它实际维护 `resource.sugon.com` 下的 `ResourceGroup` 与 `Quota` CR，而不只是展示普通配额。
子组件简介：核心工作负载是 `resource-operator-controller-manager`；`ClusterRole/resource-operator-manager-role` 赋予其对 `resourcegroups`、`quotas`、`namespaces`、`nodes`、`pods` 的读写权限；`ConfigMap/resource-operator-config` 当前保存节点预留值，如 `reservedCpu: 4`、`reservedMemory: 8Gi`；日志里可见它会按 `cardType/cardResource` 统计如 `hygon.com/dcu` 等卡资源，并按资源组重新核算 free/use。

`notebook-controller`
对应 git 目录：`/Users/humin/sugon/ske-chart/notebook-controller`
简介：这是业务侧自定义 Notebook 控制器，用于创建 Jupyter、TensorFlow 等 Notebook，并做平台化增强和模板化封装。
子组件简介：运行态核心组件是 `notebook-controller-v2`；从 RBAC 可以确认它 watch `app.crd.ske/Notebook`，并直接创建/更新 `Pod`、`Service`、`Ingress`，因此它不仅定义 CRD，还负责整套运行时对象编排；Deployment 固定运行在 `notebook=true` 节点，并挂载宿主机目录 `/public/SothisAI/persistent/container` 到 `/backup`，说明带有持久化或备份配套能力。

`multipoint-scheduler`
对应 git 目录：`/Users/humin/sugon/ske-chart/multipoint-scheduler`
简介：这是平台自定义调度器，基于 kube-scheduler framework 做了多 profile 扩展，更强调 binpack、镜像本地性以及异构算力资源的加权调度。
子组件简介：当前 values 中至少定义了 `d-scheduler` 和 `imageprefer-mostallocated-scheduler` 两个调度器名；其中 `imageprefer-mostallocated-scheduler` 为 `ImageLocality` 设置了较高权重，并把 `NodeResourcesFit` 设为 `MostAllocated`，同时对 `nvidia.com/gpu`、`hygon.com/dcu`、`sugon.com/nocard`、`cpu`、`memory` 等资源做加权，整体更偏向镜像就近和资源打满式调度。

`mc-client`
对应 git 目录：`/Users/humin/sugon/ske-chart/minio-client`
简介：这是用于 GitLab LFS 和模型对象跨站点同步的 MinIO 客户端任务，chart 描述即为 `gitlab-lfs cross-cluster mirror (mc-client) for MinIO`。
子组件简介：核心工作负载是 `mc-client` StatefulSet，默认 2 副本，固定在 `ex-lb=true` 节点，并开启 `hostNetwork: true`；容器镜像为 `image.ac.com:5000/k8s/ske-model-tool:v2-mc`；通过 `ConfigMap/mc-aliases`、`ConfigMap/http-proxy`、`ConfigMap/minio-lfs-sync-script` 注入别名、代理和同步脚本；`runner.sh` 每 15 分钟执行一次 `gitlab_lfs_sync.py`，并通过锁目录避免并发重入。

### 2.7 AI 模型组件

`ske-model` 命名空间用于部署 AI 模型推理服务及其配套支撑组件，重点是模型工作负载本身，而不是平台公共底座。

- 典型资源形态：
  - 一个模型通常对应一组 `Deployment/Service/Ingress`
  - `Ingress` 通常使用 `ingressClassName: maas`，通过 `ske/ske-model` 中的 `ingress-maas` 暴露
  - 服务端口通常为 `8000/TCP`

- 常见在线模型：
  - 如 `deepseek-*`、`qwen*`、`qwq-*`、`minimax-*`
  - 是否在线以 `kubectl --context <ctx> -n ske-model get deploy,svc,ing` 为准

- 支撑组件：
  - `docker-tmp` DaemonSet：镜像构建、拉取、重打 tag、推送内网 Harbor 的统一执行点
  - `ske-model-tool`：通用运维工具 Pod，常用于 `rsync` 中转、`modelscope` 下载模型、运行 `maas-test.py` 压测
  - `rsync` Service：配合 `ske-model-tool` 做跨节点或跨目录传输
  - `http-proxy` ConfigMap：给模型工具或同步任务提供外网代理

- 配置与版本目录：
  - 模型部署 YAML 快照目录：`/Users/humin/sugon/ske-chart/ske-model`
  - 当前按集群区分，如：
    - `.../ske-model/ks-cluster/deployments/`
    - `.../ske-model/zz-cluster/deployments/`
  - 这里保存的是当前或历史模型部署快照，适合做巡检、比对和回溯，不等价于单一 Helm chart。
  - 另有 `/Users/humin/sugon/ske-chart/maas/` 保存部分模型服务 YAML；用户要求“扫描模型/更新可用模型列表”时，除了探测集群，还需要同步更新该目录。

- 发布与排查要点：
  - 发布前先确认模型对应的 `resourceGroup`、卡型、镜像地址、Ingress 域名和 `ingressClassName`
  - 模型日志优先用：
    `python ~/agent/scripts/logs.py -n ske-model -a <app> -c <context>`
  - 若需查看运行时对象：
    `kubectl --context <ctx> -n ske-model get deploy,po,svc,ing -o wide`
  - 若需压测或下载模型，优先进入 `ske-model-tool`，不要直接在业务 Pod 内临时安装工具

### 2.8 节点角色与资源组

特殊角色标签：

- `kubeasz=true`：kubeasz 管理节点
- `ex-lb=true`：外部负载均衡节点
- `minio=true`: minio server节点
- `app=ske`：平台组件节点

常用查询：

```bash
kubectl --context <ctx> get node -l kubeasz=true -o wide
kubectl --context <ctx> get node -l ex-lb=true -o wide
kubectl --context <ctx> get node -l app=ske -o wide
kubectl --context <ctx> -n kube-system get resourcegroup
kubectl --context <ctx> get node -l resourceGroup=<resourcegroup>
```

补充：

- ResourceGroup 规则见 `~/agent/resourcegroup/SKILL.md`
- Hostname 反查 IP：

```bash
kubectl node-shell --context <ctx> <任意节点IP> -- grep <hostname> /etc/hosts
```

- 外部访问链路基线：
  `nginx (ex-lb) -> ingress -> pod/svc`


## 场景和标准操作

### 监控指标

需要明确集群、命名空间、指标名，构建 PromQL 后用 `python ~/agent/scripts/metric.py`。

```bash
# 即时查询
python ~/agent/scripts/metric.py query -c ks -q "kube_node_info"
python ~/agent/scripts/metric.py query -c dz \
  -q "sum(rate(node_cpu_seconds_total{mode='idle'}[5m])) by (instance)"

# 范围查询（指定时间窗口 + step）
python ~/agent/scripts/metric.py range -c sz \
  -q "rate(node_cpu_seconds_total[5m])" --range 1h --step 5m

# 探索指标与标签
python ~/agent/scripts/metric.py metrics      -c ks -p "kube_*"
python ~/agent/scripts/metric.py labels       -c wh
python ~/agent/scripts/metric.py label-values -c sz -l instance
```

详见 `python ~/agent/scripts/metric.py -h`。

### 日志查询

需要明确集群, 命名空间, pod或者工作负载名称.
```bash
# 按 app 查询，优先 kubectl logs
python ~/agent/scripts/logs.py -n <namespace> -a <app> -c <context>

# 按 Pod 查询
python ~/agent/scripts/logs.py -n <namespace> -p <pod> -c <context>

# 实时追踪
python ~/agent/scripts/logs.py -n ske-model -a qwen3-30b -c ks --tail

# 历史日志查询
python ~/agent/scripts/logs.py -n ske -a resource-operator --filter '_msg:"error"' --start 2h

# 只用 VictoriaLogs（跳过 kubectl）
python ~/agent/scripts/logs.py -n ske-model -a deepseek-r1 --logs-only --start 3h
```

详见 `python ~/agent/scripts/logs.py -h`



### 节点排查

需要明确集群, 节点ip. 节点进行排查有两种情况:

当节点处于ready:
```bash
kubectl node-shell --context <ctx> <node_ip>
kubectl node-shell --context <ctx> <node_ip> -- crictl ps -a
kubectl node-shell --context <ctx> <node_ip> -- systemctl status kubelet
kubectl node-shell --context <ctx> <node_ip> -- journalctl -u kubelet -n 200 --no-pager
kubectl node-shell --context <ctx> <node_ip> -- journalctl -u containerd -n 200 --no-pager
```
当节点not ready:
找到kubeasz节点 ip->`kubectl node-shell --context <ctx> <kubeasz_node_ip> -- ssh root@ip`



### 镜像构建

```bash
kubectl --context zz -n ske-model get pod -l app=docker-tmp -o wide
kubectl --context zz -n ske-model cp /local/path/Dockerfile docker-tmp-<pod-suffix>:/tmp/build/
kubectl --context zz -n ske-model cp /local/path/source docker-tmp-<pod-suffix>:/tmp/build/
kubectl --context zz -n ske-model exec docker-tmp-<pod-suffix> -- sh -c '
cd /tmp/build
docker build -t image.sourcefind.cn:5000/k8s/<image>:<tag> .
docker push image.sourcefind.cn:5000/k8s/<image>:<tag>
'
```

### 镜像同步

```bash
kubectl --context <target_ctx> -n ske-model exec <docker-tmp-pod> -- sh -c '
docker pull image.sourcefind.cn:5000/k8s/<image>:<tag> &&
docker tag image.sourcefind.cn:5000/k8s/<image>:<tag> image.ac.com:5000/k8s/<image>:<tag> &&
docker push image.ac.com:5000/k8s/<image>:<tag>
'
```

批量同步：

```bash
for ctx in ks qd dz ny wh sz wq; do
  kubectl --context "$ctx" -n ske-model exec <docker-tmp-pod> -- sh -c '
  docker pull image.sourcefind.cn:5000/k8s/<image>:<tag> &&
  docker tag image.sourcefind.cn:5000/k8s/<image>:<tag> image.ac.com:5000/k8s/<image>:<tag> &&
  docker push image.ac.com:5000/k8s/<image>:<tag>
  '
done
```


###  额度查询

用户说“查额度”“看 Codex 额度”“今天还剩多少额度”时，默认执行：

```bash
python ~/agent/scripts/codex_quota.py
```

###  更新技能

用户说“更新技能”“同步 skills”“刷新 agent 技能”时，默认执行：

```bash
python ~/agent/scripts/skill_update.py
```

###  上传文件

解析 `<ctx> / <local_file> / <node_ip> / <remote_path>` 后执行：

```bash
# 上传到节点（>100M 自动走 MinIO tmp）
python ~/agent/scripts/upload.py -c <ctx> <local_file> <node_ip>:<remote_path>

# 仅上传到 MinIO tmp 桶
python ~/agent/scripts/upload.py --minio-only -c <ctx> <local_file>
```

示例：把 `/tmp/a.tar.gz` 上传到 `qd` 的 `10.1.4.11:/tmp/` →
`upload.py -c qd /tmp/a.tar.gz 10.1.4.11:/tmp/`

###  跨节点拷贝文件

解析 `<ctx> / <src_node_ip>:<src_path> / <dst_node_ip>:<dst_path>` 后，
默认用 `ske-model` 下的 `ske-model-tool` Pod 做 `rsync` 中转：

```bash
kubectl --context <ctx> -n ske-model get pod -l app=ske-model-tool -o wide
kubectl --context <ctx> -n ske-model exec <ske-model-tool-pod> -- sh -c '
mkdir -p /tmp/rsync-work &&
rsync -av --progress root@<src_node_ip>:<src_path> /tmp/rsync-work/ &&
rsync -av --progress /tmp/rsync-work/ root@<dst_node_ip>:<dst_path>
'
```

目录传输保留结构，路径不明先补全再执行。

###  下载模型

解析 `<ctx> / <model_name> / <target_dir>`，在 `ske-model-tool` 内调用 `modelscope`：

```bash
kubectl --context <ctx> -n ske-model exec <ske-model-tool-pod> -- sh -c '
cd <target_dir> && python -m modelscope.cli.download <model_name>
'
```

###  压测模型

解析 `<ctx> / <service> / <token_lengths> / <cache_rates> / <concurrency> / <output_tokens>`，
在 `ske-model-tool` Pod 内执行 `maas-test.py`：

```bash
# 查看支持参数
kubectl --context <ctx> -n ske-model exec <ske-model-tool-pod> -- \
  python /usr/local/bin/maas-test.py --help

# 典型压测
kubectl --context <ctx> -n ske-model exec <ske-model-tool-pod> -- \
  python /usr/local/bin/maas-test.py \
  --service <service> \
  --token-lengths 20000 80000 \
  --cache-rates 0.0 0.8 \
  --concurrency 24 \
  --output-tokens 256
```


###  MinIO 同步进度

用户说查看下minio的同步进度, 执行:

```bash
python ~/agent/scripts/minio_scan.py -c ks zz qd dz
```

更多细节见 `~/agent/skills/minio/SKILL.md`。

###  扫描模型

用户说“扫描模型”,“更新可用模型列表”,“探测 ks/zz 当前可用模型”时，默认执行：

```bash
python ~/agent/scripts/probe_models.py
```
并且把ske-model部署的模型相关yaml, 更新到/Users/humin/sugon/ske-chart/maas/
