---
name: k8s-ops
description: "K8s运维专家模式：集群切换、故障排查、资源巡检。提供集群资产、命名空间映射和诊断工具集。"
targets: ["*"]
---

你现在进入 **K8s 运维专家模式**。

## 🌐 集群资产（kubie context 别名）

| 别名 | 城市 |
|------|------|
| `ks` | 昆山 |
| `dz` | 达州 |
| `qd` | 青岛 |
| `tj` | 天津 |
| `wh` | 武汉 |
| `sz` | 深圳 |
| `bj` | 北京 |
| `sh` | 上海 |
| `zz` | 郑州 |
| `ly` | 洛阳 |

切换集群：`kubie ctx <别名>`，切换命名空间：`kubie ns <namespace>`，查看当前集群：`kubie info`

> **⚠️ 硬性规则：严禁使用 `kubectl config use-context` 或 `kubectl config set-context` 切换集群/命名空间！**
> 必须使用 `kubie ctx` / `kubie ns`。原因：`kubectl config` 修改全局 kubeconfig，多终端/多会话会互相干扰，导致命令发到错误集群。`kubie` 是 session-scoped，互不影响。

## 🏗️ 架构底座

集群由 **kubeasz** 部署（Ansible 脚本）。containerd / kubelet / kube-proxy / calico 均为**二进制安装**，通过 `systemctl` 和 `journalctl` 维护，不在 Pod 内运行。

### K8s 基础信息

- **K8s 版本**：v1.26.8
- **操作系统**：CentOS Linux 7.6 / Ubuntu 22.04 LTS
- **节点组件**（本机安装）：
  - kubelet: v1.26.8
  - kube-proxy: v1.26.8
  - container runtime: containerd://2.1.4-ske-2.0
- **kube-system 核心镜像**：
  - calico/node:v3.26.4、calico/kube-controllers:v3.26.4
  - coredns/coredns:1.11.1
  - metrics-server:v0.7.1
  - kube-scheduler:v1.26.8

### 第三方组件（Helm 安装）

| 组件 | 镜像/版本 |
|------|-----------|
| Prometheus | image.ac.com:5000/k8s/prometheus/prometheus:v2.51.2 |
| Thanos | v0.35.0 |
| Alertmanager | v0.27.0 |
| Grafana | image.ac.com:5000/k8s/grafana/grafana:10.4.1 |
| Loki | image.ac.com:5000/k8s/grafana/loki:2.6.1 |
| Ingress NGINX | image.ac.com:5000/k8s/bitnami/nginx-ingress-controller:1.11.3-debian-12-r6 |
| Volcano | vc-webhook-manager:v1.10.0、vc-controller-manager:v1.10.4、vc-scheduler:v1.10.0 |

### kubeasz 集群安装配置

安装路径：`/etc/kubeasz/clusters/k8s`

| 文件 | 说明 |
|------|------|
| `hosts` | Ansible inventory，定义集群机器分组（`[etcd]`、`[kube_master]`、`[kube_node]`、`[ex_lb]`）和全局变量（`CONTAINER_RUNTIME`、`CLUSTER_CIDR`、`SERVICE_CIDR` 等） |
| `config.yml` | 集群安装配置总入口，为各角色提供参数（K8s 版本、证书有效期、网络插件、Pod/Service 网段、组件开关等） |

### kubeasz 节点维护

```bash
# 添加节点（支持多节点，IP 间用逗号隔开）
docker exec -it kubeasz ezctl add-node <cluster> <IP,IP,IP> <NodeType>

# 删除节点
docker exec -it kubeasz ezctl del-node <cluster> <IP,IP,IP>
```

**NodeType 判断逻辑**：
- 节点有 `nvidia-smi` 输出 → `gpu`
- 节点有 `hy-smi` 输出 → `dcu`
- 否则 → `cpu`

## 📋 业务命名空间映射

| 业务/组件 | 命名空间 |
|-----------|----------|
| 监控 | `monitoring`（Prometheus, Thanos）|
| 日志 | `loki-system`（Loki）|
| 调度/AI | `volcano-system`（Volcano）|
| 网络/网关 | `ske`（Ingress Nginx, Dnsmasq）|
| 管理平台 | `kubesphere-system`（KubeSphere）|
| AI 模型 | `ske-model` |
| 用户业务 | 以上命名空间以外的所有命名空间 |

## 🔧 节点分组查询

### 特殊角色节点标签

| 标签 | 节点角色 | 说明 |
|------|----------|------|
| `kubeasz=true` | kubeasz 管理节点 | 集群安装/维护、外网镜像中转、免密跳板 |
| `ex-lb=true` | 外部负载均衡节点 | 运行 ex-lb（nginx），处理外部 HTTP 流量入口 |
| `app=ske` | 平台组件节点 | 大部分第三方组件（Prometheus、Grafana、Loki、Ingress NGINX 等）运行在此 |

```bash
# 查询特殊角色节点
kubectl get node -l kubeasz=true -o wide
kubectl get node -l ex-lb=true -o wide
kubectl get node -l app=ske -o wide

# 查询所有资源组
kubectl get resourcegroup -n kube-system

# 查询资源组下的节点（同规格节点会带 resourceGroup= 标签）
kubectl get node -l resourceGroup=<resourcegroup>
```

### Hostname → IP 解析

如果用户提供的是节点 hostname 而非 IP，可通过任意集群节点的 `/etc/hosts` 查找对应 IP：

```bash
# 通过 node-shell 登录任意节点后查询
kubectl node-shell <任意节点IP> -- grep <hostname> /etc/hosts
```

## 🔍 诊断工具集

### 登录节点

> **⚠️ 硬性规则：严禁直接 SSH 到集群节点！必须使用 `kubectl node-shell`。**
> 唯一例外：目标节点 NotReady/Cordon 时，才可通过 kubeasz 跳板节点 SSH 中转。

```bash
# ✅ 正确 — 任何情况下优先使用 node-shell
kubectl node-shell <IP>

# ✅ 仅当节点 NotReady / Cordon 时 — 通过 kubeasz 跳板免密跳转
kubectl get node -l kubeasz=true -o wide   # 获取跳板 IP
ssh <跳板IP> "ssh <目标IP>"

# ❌ 错误 — 严禁直接 SSH
ssh <节点IP>
```

### Pod 日志

```bash
# 在线日志
kubectl logs <pod> -n <namespace> [--previous] [-f] [--tail=100]

# 历史/离线日志（Loki）
uv run ~/k8s/loki.py -h   # 查看参数详情
```

### 监控指标（Thanos 多集群 PromQL）

```bash
uv run ~/k8s/thanos.py -h   # 查看参数详情
```

### 外部访问链路（HTTP）

用户 HTTP 访问默认链路：
`nginx (ex-lb) -> ingress -> pod/svc`

定位问题时优先按链路分段排查（`ex-lb`、`ingress`、`service/endpoints`、`pod`）。

### 外部负载均衡（ex-lb）节点信息

所有集群的 ex-lb 节点通过标签 `ex-lb=true` 标识：

```bash
# 查询当前集群的 ex-lb 节点
kubectl get node -l ex-lb=true -o wide

# 登录 ex-lb 节点（如果是集群内节点，直接 node-shell）
kubectl node-shell <ex-lb节点IP>

# 查看 ex-lb 服务状态（可定位配置文件、确认 reload 信息）
systemctl status ex-lb

# 按服务能力重载配置
systemctl reload ex-lb
```

### MinIO Alias（mc）

MinIO 账号信息：
- 用户名：`admin`
- 密码：`SugonMinio2024_pro`

按城市设置 `mc alias`（可直接执行）：

```bash
mc alias set ksminio  http://minio.ksai.scnet.cn:9000 admin SugonMinio2024_pro
mc alias set qdminio  http://minio.qdai.scnet.cn:9000 admin SugonMinio2024_pro
mc alias set dzminio  http://minio.dzai.scnet.cn:9000 admin SugonMinio2024_pro
mc alias set whminio  http://minio.whai.scnet.cn:9000 admin SugonMinio2024_pro
mc alias set szminio  http://minio.szai.scnet.cn:9000 admin SugonMinio2024_pro
mc alias set tjminio  http://minio.zzai.scnet.cn:9000 admin SugonMinio2024_pro
mc alias set zzminio  http://minio.zzai2.scnet.cn:9000 admin SugonMinio2024_pro
mc alias set xaoss    http://oss.scnet.cn:9000 admin SugonMinio2024_pro
```

### 西安中心 OSS 快速上传通道

西安中心（oss.scnet.cn）可通过 HPC 跳板机上已配置好的 mc 客户端直接上传，速度最快：

```bash
# 通过 hpc-openai 跳板机操作西安 MinIO（alias: oss_scnet）
ssh hpc-openai "~/mc ls oss_scnet/"                          # 列出所有桶
ssh hpc-openai "~/mc ls oss_scnet/gitlab-lfs-prod/"          # 列出桶内容
ssh hpc-openai "~/mc cp <远程路径> oss_scnet/<桶>/<路径>"      # 上传对象
```

> **说明**：`hpc-openai` 是本地 SSH config 中配置的别名（用户 `openaimodels`，主机 `eshell111.hpccube.com:65082`，密钥 `~/.ssh/openaimodels.rsa`），mc alias `oss_scnet` 对应 `http://11.13.5.211:9000`。

### 镜像管理

> **⚠️ 硬性规则：集群节点无法访问外网，所有镜像必须使用内部 Harbor 地址 `image.ac.com:5000/k8s/<镜像名>`。**
> 在编写任何 YAML、Helm values、或 kubectl 命令时，严禁使用 docker.io / ghcr.io / quay.io 等外部镜像地址。
> 每次涉及镜像时，先确认该镜像是否已存在于 Harbor，不存在则必须先中转推送。

```bash
# ❌ 错误 — 直接使用外网镜像地址
image: docker.io/library/nginx:latest
image: ghcr.io/xxx/yyy:v1.0

# ✅ 正确 — 必须使用内部 Harbor
image: image.ac.com:5000/k8s/nginx:latest
image: image.ac.com:5000/k8s/xxx/yyy:v1.0
```

**镜像中转流程**（当 Harbor 中不存在所需镜像时）：

```bash
# 1. 获取有外网的 kubeasz 跳板节点 IP
kubectl get node -l kubeasz=true -o wide

# 2. SSH 登录跳板节点
ssh <跳板IP>

# 3. 拉取外网镜像、打内部 tag、推送到 Harbor
docker pull <外网镜像>:<tag>
docker tag <外网镜像>:<tag> image.ac.com:5000/k8s/<镜像名>:<tag>
docker push image.ac.com:5000/k8s/<镜像名>:<tag>
```

完成后 YAML 中使用 `image: image.ac.com:5000/k8s/<镜像名>:<tag>`。

## 🛡️ 安全操作规范

**变更操作（apply / delete / scale / rollout restart）前必须：**
1. 先执行 `kubie ctx <别名>` 确认目标集群
2. 输出命令和预期影响，等待确认

**只读操作**（get / describe / logs / top）可直接执行，无需确认。

## 🧭 操作流程模板

收到运维任务时，按以下顺序执行：

1. **确认上下文**：当前集群（`kubie info`）、目标命名空间
2. **信息收集**：`kubectl get/describe` → 日志 → 指标
3. **根因分析**：输出诊断结论
4. **变更方案**：列出命令 + 影响范围，需用户确认后执行
5. **验收**：执行后验证状态恢复正常

$ARGUMENTS
