---
name: k8s-minio
description: "K8s MinIO 运维子专题：节点定位、桶巡检、对象排查、跨集群同步"
targets: ["*"]
---

你现在进入 **K8s MinIO 子专题**。

## 1. 基础信息

常用桶：`prom` `loki` `gitlab-lfs-prod`

### 1.1 集群 MinIO 节点

| 集群 | minio=true 节点 | MinIO 监听地址 |
|------|-----------------|---------------|
| ks（昆山） | 10.15.200.11, 10.15.200.12 | 127.0.0.1:19000 |
| qd（青岛） | 10.1.4.11, 10.1.4.12 | 127.0.0.1:19000 |
| dz（达州） | 10.1.114.1, 10.1.114.2 | 11.1.114.201:9000（独立部署，不在节点本地） |
| zz（郑州） | 10.13.17.168, 10.13.17.169, 10.13.17.170 | 127.0.0.1:19000 |

> 注意：达州 MinIO 不在 K8s 节点上直接运行，通过 IB 网络 `11.1.114.201:9000` 访问。

### 1.2 mc 别名约定（所有 minio=true 节点已统一配置）

| 别名 | 用途 | 指向 |
|------|------|------|
| `origin` | 西安主集群（公网 IP） | `http://221.11.21.199:9000` |
| `xaminio` | 西安主集群（同 origin） | `http://221.11.21.199:9000` |
| `minio-local` | 本集群 MinIO | ks/qd/zz: `127.0.0.1:19000`，dz: `11.1.114.201:9000` |

所有别名账号：`admin / SugonMinio2024_pro`

## 2. 排障流程

1. 定位节点：`kubectl --context=<别名> get node -l minio=true -o wide`
2. 进入节点：`kubectl node-shell --context=<别名> <minio节点IP>`
3. 核验对象：`mc ls <alias>/` 与 `mc ls <alias>/<bucket>/`
4. 桶级统计（快速）：`mc stat <alias>/<bucket>` — 返回桶的 Total Size / Total Objects

西安快速通道：
- `ssh xa-login "~/mc ls oss_scnet/"`
- `ssh xa-login "~/mc ls oss_scnet/gitlab-lfs-prod/"`
- `ssh xa-login "~/mc cp <远程路径> oss_scnet/<桶>/<路径>"`

## 3. 跨集群同步

### 3.1 CronJob 自动同步（当前方案）

- 资源位置：各集群 `ske` 命名空间
- CronJob 名称：`minio-lfs-sync`
- YAML 源文件：`~/agent/gitlab/minio-sync-cronjob.yaml`
- 镜像：`image.ac.com:5000/k8s/library/busybox:1.31.1`
- 调度：每天凌晨 2 点（`0 2 * * *`）
- 最大运行时间：20 小时
- 并发策略：Forbid（上一次没跑完则跳过）
- 同步方向：`origin/gitlab-lfs-prod` → `minio-local/gitlab-lfs-prod`
- 同步策略：按 256 个十六进制前缀分段 mirror，`--overwrite --preserve`（覆盖式，不删除）
- 依赖：节点上的 `/usr/local/bin/mc` 二进制 + `/root/.mc` 配置（origin + minio-local 别名）

常用操作：
```bash
# 查看 CronJob 状态
kubectl --context <别名> -n ske get cronjob minio-lfs-sync

# 查看最近的 Job
kubectl --context <别名> -n ske get job -l job-name

# 手动触发一次
kubectl --context <别名> -n ske create job --from=cronjob/minio-lfs-sync minio-lfs-sync-manual-$(date +%s)

# 查看运行日志
kubectl --context <别名> -n ske logs -l job-name --tail=50

# 更新 CronJob（修改 YAML 后）
kubectl --context <别名> -n ske apply -f ~/agent/gitlab/minio-sync-cronjob.yaml
```

### 3.2 历史方案（已废弃）

`minio-sync.service`：systemd 服务，`mc mirror --watch` 持续同步。已在所有集群 stop + disable。
问题：`--watch` 依赖事件通知，跨集群不生效，初始同步后不再有增量。

## 4. 工具脚本

- `minio_bucket_policy.py` - MinIO 桶策略分析与报告工具

## 5. 高风险约束

`mc rm` / `mc rb` / `mc mv` 必须先确认。
