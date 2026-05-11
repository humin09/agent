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

## 2. 速查区

### 2.1 本机环境

- OS: `macOS 26.3.1`，`arm64`
- Python: `3.12` (`pyenv`)
- Node.js: `25.8.0`
- npm: `11`
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

### 2.3 节点外网代理

| 别名 | 城市 | 节点外网代理 |
|------|------|--------------|
| `ks` | 昆山 | `http://haowj:6c72c7e5@10.15.100.43:3120` |
| `qd` | 青岛 | `http://aca1kgxhox:74409cf0@10.1.4.13:3120` |
| `sz` | 深圳 | `10.1.100.10:3120` |
| `wq` | 魏桥 | `10.10.1.3:3128` |
| `zz` | 郑州 | `http://jsyadmin:1cdf8f60@10.13.17.166:3128` |
| `dz` | 达州 | `http://jsyadmin:4e2974de@10.1.100.10:3120` |
| `wh` | 武汉 | 无需代理（节点可直连外网） |

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

### 2.6 节点角色与资源组

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

### 2.7 镜像管理速查

- 线上镜像必须使用内网 Harbor：
  `image.ac.com:5000/k8s/<镜像名>:<tag>`
- 禁止使用 `docker.io` / `ghcr.io` / `quay.io` 作为线上镜像地址。
- 镜像下载与上传统一通过 `ske-model` 命名空间下的 `docker-tmp` DaemonSet 执行。
- 推荐以 `zz` 集群作为镜像构建和源站推送枢纽。
- 源站 Harbor：
  `image.sourcefind.cn:5000/k8s/<镜像名>:<tag>`

## 3. 标准操作模板区

### 3.1 kubectl 查询模板

```bash
kubectl --context <ctx> get <resource>
kubectl --context <ctx> -n <ns> get <resource>
kubectl --context <ctx> -n <ns> describe <resource> <name>
kubectl --context <ctx> -n <ns> get pod -o wide
kubectl --context <ctx> -n <ns> get svc
kubectl --context <ctx> -n <ns> get events --sort-by=.lastTimestamp | tail -n 30
```

### 3.2 巡检模板

```bash
kubectl --context <ctx> get node -o wide
kubectl --context <ctx> get pod -A -o wide
kubectl --context <ctx> get pod -A | grep -E 'CrashLoopBackOff|Error|ImagePullBackOff|Evicted'
kubectl --context <ctx> get svc -A
kubectl --context <ctx> get ingress -A
kubectl --context <ctx> top node
kubectl --context <ctx> top pod -A
```

### 3.3 日志排查模板

```bash
kubectl --context <ctx> -n <ns> logs <pod>
kubectl --context <ctx> -n <ns> logs <pod> --tail=200
kubectl --context <ctx> -n <ns> logs <pod> -f
kubectl --context <ctx> -n <ns> logs <pod> -c <container> --tail=200
kubectl --context <ctx> -n <ns> logs <pod> --previous
kubectl --context <ctx> -n <ns> describe pod <pod>
```

### 3.4 工作负载定位模板

```bash
kubectl --context <ctx> -n <ns> get deploy
kubectl --context <ctx> -n <ns> get sts
kubectl --context <ctx> -n <ns> get pod -o wide
kubectl --context <ctx> -n <ns> get pod -l <label_key>=<label_value> -o wide
kubectl --context <ctx> -n <ns> get svc <svc> -o yaml
kubectl --context <ctx> -n <ns> get endpoints <svc>
kubectl --context <ctx> -n <ns> describe svc <svc>
```

### 3.5 node-shell 模板

```bash
kubectl node-shell --context <ctx> <node_ip>
kubectl node-shell --context <ctx> <node_ip> -- hostname
kubectl node-shell --context <ctx> <node_ip> -- ip addr
kubectl node-shell --context <ctx> <node_ip> -- crictl ps -a
kubectl node-shell --context <ctx> <node_ip> -- systemctl status kubelet
kubectl node-shell --context <ctx> <node_ip> -- journalctl -u kubelet -n 200 --no-pager
kubectl node-shell --context <ctx> <node_ip> -- journalctl -u containerd -n 200 --no-pager
```

### 3.6 节点代理模板

```bash
kubectl node-shell --context <ctx> <node_ip> -- sh -c '
export http_proxy=http://<user>:<pass>@<proxy_ip>:<port>
export https_proxy=$http_proxy
curl -I https://example.com
'
```

### 3.7 文件上传模板

```bash
~/agent/scripts/upload.py -c <ctx> <local_file> <node_ip>:<remote_path>
~/agent/scripts/upload.py --minio-only -c <ctx> <local_file>
```

### 3.8 镜像构建模板

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

### 3.9 镜像同步模板

```bash
kubectl --context <target_ctx> -n ske-model exec <docker-tmp-pod> -- sh -c '
docker pull image.sourcefind.cn:5000/k8s/<image>:<tag> &&
docker tag image.sourcefind.cn:5000/k8s/<image>:<tag> image.ac.com:5000/k8s/<image>:<tag> &&
docker push image.ac.com:5000/k8s/<image>:<tag>
'
```

批量同步骨架：

```bash
for ctx in ks qd dz ny wh sz wq; do
  kubectl --context "$ctx" -n ske-model exec <docker-tmp-pod> -- sh -c '
  docker pull image.sourcefind.cn:5000/k8s/<image>:<tag> &&
  docker tag image.sourcefind.cn:5000/k8s/<image>:<tag> image.ac.com:5000/k8s/<image>:<tag> &&
  docker push image.ac.com:5000/k8s/<image>:<tag>
  '
done
```

### 3.10 变更前确认模板

执行以下命令前，先向人工明确输出：

- 完整命令
- 目标 context
- 目标 namespace
- 目标资源
- 影响范围
- 回滚思路

标准话术骨架：

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

### 3.11 额度查询模板

用户说“查额度”“看 Codex 额度”“今天还剩多少额度”时，默认执行：

```bash
python ~/agent/scripts/codex_quota.py
```

### 3.12 更新技能模板

用户说“更新技能”“同步 skills”“刷新 agent 技能”时，默认执行：

```bash
python ~/agent/scripts/skill_update.py
```

### 3.13 上传文件模板

用户说“上传文件到某集群某节点某路径”时，先从用户语句中解析：

- 集群：`<ctx>`
- 源文件：`<local_file>`
- 目标节点：`<node_ip>`
- 目标路径：`<remote_path>`

默认执行：

```bash
python ~/agent/scripts/upload.py -c <ctx> <local_file> <node_ip>:<remote_path>
```

仅上传到 MinIO `tmp` 桶时，执行：

```bash
python ~/agent/scripts/upload.py --minio-only -c <ctx> <local_file>
```

解析示例：

- “把 `/tmp/a.tar.gz` 上传到 `qd` 的 `10.1.4.11:/tmp/`”
- 解析为：
  - `ctx=qd`
  - `local_file=/tmp/a.tar.gz`
  - `node_ip=10.1.4.11`
  - `remote_path=/tmp/`

### 3.14 跨节点拷贝文件模板

用户说“从某集群某节点拷文件到另一节点”时，先解析：

- 集群：`<ctx>`
- 源节点：`<src_node_ip>`
- 源路径：`<src_path>`
- 目标节点：`<dst_node_ip>`
- 目标路径：`<dst_path>`

默认使用 `ske-model-tool` 作为中转执行 `rsync`。

标准思路：

1. 在 `ske-model` 命名空间启动或选择一个 `ske-model-tool` Pod。
2. 将源节点目录通过 `rsync` 拉到中转 Pod 临时目录。
3. 再从中转 Pod 推到目标节点。

示例骨架：

```bash
kubectl --context <ctx> -n ske-model get pod -o wide | grep ske-model-tool
kubectl --context <ctx> -n ske-model exec <ske-model-tool-pod> -- sh -c '
mkdir -p /tmp/rsync-work &&
rsync -av --progress root@<src_node_ip>:<src_path> /tmp/rsync-work/ &&
rsync -av --progress /tmp/rsync-work/ root@<dst_node_ip>:<dst_path>
'
```

补充规则：

- 若用户给的是单文件，`src_path` 与 `dst_path` 直接按文件路径处理。
- 若用户给的是目录，默认保留目录结构，优先使用 `rsync -av --progress`。
- 若目标集群或目标路径不明确，先补全参数后再执行。

### 3.15 下载模型模板

用户说“下载模型到某集群”时，先解析：

- 集群：`<ctx>`
- 模型名或模型路径：`<model_name>`
- 目标目录：`<target_dir>`
- 额外参数：如 revision、source、量化版本、是否走代理

默认使用 `ske-model-tool` 内的 `modelscope` 执行下载。

示例骨架：

```bash
kubectl --context <ctx> -n ske-model get pod -o wide | grep ske-model-tool
kubectl --context <ctx> -n ske-model exec <ske-model-tool-pod> -- sh -c '
cd <target_dir> &&
python -m modelscope.cli.download <model_name>
'
```

若节点或 Pod 内访问外网，需要先显式设置代理：

```bash
kubectl --context <ctx> -n ske-model exec <ske-model-tool-pod> -- sh -c '
export http_proxy=<proxy>
export https_proxy=$http_proxy
cd <target_dir> &&
python -m modelscope.cli.download <model_name>
'
```

### 3.16 压测模型模板

用户说“压测某个模型”“跑一下某服务性能”“测 token 长度 / cache rate / 并发”时，先解析：

- 集群：`<ctx>`
- 服务名：`<service>`
- token lengths：`<token_lengths>`
- cache rates：`<cache_rates>`
- 并发：`<concurrency>`
- 输出 token 数：`<output_tokens>`
- 其他参数：如 benchmark mode、model、timeout

默认先进入目标集群 `ske-model` 命名空间内的 `ske-model-tool` Pod，再在 Pod 内执行 `maas-test.py`。

帮助命令：

```bash
kubectl --context <ctx> -n ske-model get pod -o wide | grep ske-model-tool
kubectl --context <ctx> -n ske-model exec <ske-model-tool-pod> -- python /usr/local/bin/maas-test.py --help
```

常用骨架：

```bash
kubectl --context <ctx> -n ske-model exec <ske-model-tool-pod> -- \
  python /usr/local/bin/maas-test.py \
  --service <service> \
  --token-lengths <token_length_1> <token_length_2> \
  --cache-rates <cache_rate_1> <cache_rate_2>
```

带并发与输出 token 的示例：

```bash
kubectl --context <ctx> -n ske-model exec <ske-model-tool-pod> -- \
  python /usr/local/bin/maas-test.py \
  --service <service> \
  --token-lengths 20000 80000 \
  --cache-rates 0.0 0.8 \
  --concurrency 24 \
  --output-tokens 256
```

默认结果文件：

```text
/tmp/maas-benchmark-result.log
```

### 3.17 MinIO 桶扫描模板

用户说“扫描 MinIO 桶”“出 MinIO 桶策略报告”“看桶权限/生命周期/版本控制”时，默认使用本地扫描脚本：

```bash
python ~/agent/minio/minio_scan.py
```

输出说明：

- 脚本会扫描多个 MinIO alias 的桶信息
- 生成桶访问策略、授权用户、生命周期、版本控制等报告
- 默认输出文件：

```text
/Users/humin/opencode/minio_policy_report.md
```

### 3.18 MinIO 同步进度模板

用户说“看 MinIO 同步进度”“看 LFS 同步跑到哪了”“检查 MinIO 同步状态”时，默认按 CronJob / Job / 日志 三步检查：

```bash
kubectl --context <ctx> -n ske get cronjob minio-lfs-sync
kubectl --context <ctx> -n ske get job -l job-name
kubectl --context <ctx> -n ske logs -l job-name --tail=50
```

需要手动触发一次时：

```bash
kubectl --context <ctx> -n ske create job --from=cronjob/minio-lfs-sync minio-lfs-sync-manual-$(date +%s)
```

需要看桶级对象变化时，可补充：

```bash
kubectl --context <ctx> -n ske exec deploy/mc-client -- mc stat local/<bucket>
kubectl --context <ctx> -n ske exec deploy/mc-client -- mc ls local/<bucket>/
```

### 3.19 扫描模型模板

用户说“扫描模型”“更新可用模型列表”“探测 ks/zz 当前可用模型”时，默认执行：

```bash
python ~/agent/maas/probe_models.py
```

若按 `maas` 技能标准流程执行，也可使用：

```bash
uv run /Users/humin/agent/maas/probe_models.py
```

输出：

```text
available_models.md
```
