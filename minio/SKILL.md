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

### 1.3 元数据一致性约束

- 当前多集群 MinIO 不是官方分布式单集群，而是多个独立 MinIO 实例对外挂在同一套或相近底层存储。
- 这类架构下，对任一实例执行桶元数据变更后，其他实例不会自动同步相同变更。
- 桶元数据包括但不限于：
  - ILM / 生命周期规则
  - IAM 相关桶级访问控制与匿名策略
  - Versioning 状态
  - 桶通知、加密、Object Lock 等桶级配置
- 因此，凡是新建或修改上述桶元数据，必须把同一集群内每个独立 MinIO 实例都做一次归一化，不能只改 ex-lb 后面的某一个入口。
- 归一化目标是“同集群所有后端实例的桶元数据语义一致”；若 rule ID、策略 JSON 字段顺序不同但语义一致，也要优先收敛到同一份来源配置。

## 2. 排障流程

1. 定位节点：`kubectl --context=<别名> get node -l minio=true -o wide`
2. 进入节点：`kubectl node-shell --context=<别名> <minio节点IP>`
3. 核验对象：`mc ls <alias>/` 与 `mc ls <alias>/<bucket>/`
4. 桶级统计（快速）：`mc stat <alias>/<bucket>` — 返回桶的 Total Size / Total Objects

涉及桶元数据变更时，额外执行：
1. 明确同集群所有 MinIO 后端实例列表，不要只看 ex-lb 域名
2. 选定一份 authoritative 配置作为源头
3. 将 ILM / IAM / versioning 等配置逐实例导入或对齐
4. 变更后逐实例执行 `mc stat --json <alias>/<bucket>` 复核 `Policy`、`Versioning`、`ilm`
5. 如存在 `gitlab-lfs-prod`，默认单独确认后再执行任何 lifecycle 或 versioning 变更

西安快速通道：
- `ssh xa-login "~/mc ls oss_scnet/"`
- `ssh xa-login "~/mc ls oss_scnet/gitlab-lfs-prod/"`
- `ssh xa-login "~/mc cp <远程路径> oss_scnet/<桶>/<路径>"`

## 3. 跨集群同步

### 3.1 临时文件 / 目录同步（推荐默认方案）

适用场景：
- 跨集群临时传输单个文件
- 跨集群临时传输整个目录（如模型目录、归档目录、离线包）
- 目标是“先把对象安全搬过去”，而不是长期保存在业务桶

默认规则：
- 跨集群传文件或目录时，优先使用各集群 MinIO 的 `tmp` 桶做中转
- 推荐路径格式：`tmp/<名称>` 或 `tmp/<目录名>/`
- 源集群先上传到本集群 `tmp` 桶，再由目标集群通过 `mc cp` / `mc mirror` 从源 alias 拉取到目标集群 `tmp` 桶
- 目录优先直接同步目录，不要默认先压缩；仅在用户明确要求压缩包时再打包

标准流程：
1. 在源集群 `minio=true` 节点确认源文件/目录存在
2. 使用 `mc mb --ignore-existing <源alias>/tmp` 确保源 `tmp` 桶存在
3. 文件使用 `mc cp`，目录使用 `mc mirror --overwrite --preserve` 上传到源 `tmp` 桶
4. 在目标集群 `minio=true` 节点确认已配置源集群 alias
5. 使用 `mc mb --ignore-existing <目标alias>/tmp` 确保目标 `tmp` 桶存在
6. 文件使用 `mc cp`，目录使用 `mc mirror --overwrite --preserve` 同步到目标 `tmp` 桶
7. 用 `mc ls` / `mc du` / `mc stat` 校验对象数量、大小和关键文件

示例：
```bash
# 源集群：上传目录到本集群 tmp 桶
mc mb --ignore-existing local/tmp
mc mirror --overwrite --preserve /public/ai_data/models/Qwen3.6-35B-A3B local/tmp/Qwen3.6-35B-A3B

# 目标集群：从源集群 tmp 桶同步目录到本集群 tmp 桶
mc mb --ignore-existing local/tmp
mc mirror --overwrite --preserve zz/tmp/Qwen3.6-35B-A3B local/tmp/Qwen3.6-35B-A3B

# 文件场景
mc cp /tmp/example.tar.gz local/tmp/
mc cp zz/tmp/example.tar.gz local/tmp/
```

注意事项：
- 跨集群同步前，先验证目标节点是否能访问源 alias：`mc ls <源alias>/tmp/`
- 若 `mc alias set` 因域名连通性或网关问题失败，可按已知可用地址或直接写入 `/root/.mc/config.json` 补齐 alias
- 若节点缺少 `mc`，先处理 `mc` 二进制或补齐 `/root/.mc/config.json` 后再执行
- `tmp` 桶默认视为临时中转区；长期数据不要默认放在 `tmp`

### 3.2 CronJob 自动同步（当前方案）

- 资源位置：各集群 `ske` 命名空间
- CronJob 名称：`minio-lfs-sync`
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


## 4. 工具脚本

- `minio_bucket_policy.py` - MinIO 桶策略分析与报告工具

## 5. 高风险约束

`mc rm` / `mc rb` / `mc mv` 必须先确认。

新增约束：
- 新建或修改 ILM / IAM / versioning / 桶策略后，必须在同集群每个独立 MinIO 实例上完成归一化与复核，不能假设会自动同步。
- 只改一个后端实例就结束，视为不完整操作。
- `gitlab-lfs-prod` 的 lifecycle 或 versioning 变更必须单独确认。
