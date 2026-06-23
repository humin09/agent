# MinIO 跨集群同步方案演进与问题分析

**生成时间**: 2026-06-23  
**背景**: xa(西安) → ly(洛阳) → {ks(昆山), qd(青岛), dz(达州)} 的 gitlab-lfs-prod 桶同步  
**数据规模**: ~109,737 对象，~92 TiB，gitlab-lfs 目录结构 `xx/yy/<64位hash>`（65536 个二级目录）

---

## 方案演进

### V1: mc-client StatefulSet (2026-05-13)

**架构**: `minio-client/` chart

```
StatefulSet (多 Pod 分片)
  ├─ Pod mc-client-0: prefix 0/65536, 1/65536, ...
  ├─ Pod mc-client-1: prefix 32768/65536, 32769/65536, ...
  └─ lfs_sync.py: mc ls --recursive → state file → mc cp --preserve
```

**关键组件**:
- `lfs_sync.py`: 全桶 `mc ls --recursive --json` 扫描，找出 diff，逐个 `mc cp`
- `runner.sh`: 监控 batch replicate 任务状态
- State file: 存储在 MinIO 的 `tmp/gitlab-lfs-prod/sync-state.json`

**问题**:
1. **全桶 scan 超时**: `mc ls --recursive` 要扫 10 万+ 对象，扫描时间 >2 小时超时
2. **State file 管理开销**: 需要定期 flush，进程挂掉时进度丢失
3. **Job 卡住**: 某些 Pod 长时间无进展，需要人工干预

---

### V2: MinIO 内置 batch replicate (2026-06-19)

**架构**: `minio-server/` chart 内置 CronJob

```yaml
CronJob (*/5 minutes)
  └─ mc batch start local /configs/replicate.yaml
      └─ batch replicate 跑在 MinIO server 进程内部
```

**优势**:
- 内置支持，无需额外组件
- 自动并发控制（`maxConcurrentRequests`）
- 重试机制（`retry.attempts`）

**致命问题**:
1. **Server 被打挂**: `maxConcurrentRequests=6` × 10GB 并发 → goroutine 打满 → GC 停顿
2. **Liveness probe 超时**: `timeout 10s` × `failureThreshold 5` → 连续 5 次 10s 超时 → kill
3. **重启风暴**: ly 重启 21 次，每次重启后又被新一轮 batch 打挂
4. **同步无法完成**: 每次只跑几分钟就 crash，永远追不上 xa

**数据**: 
- ly 下载速率 282 MB/s (0.97 TiB/h)
- 但 IncompleteBody 错误 2062 次/30min，791 个对象反复失败

---

### V3: mc mirror 外部 Job (2026-06-23)

**架构**: 一次性 Job

```yaml
Job/minio-mirror-initial
  └─ mc mirror --overwrite --max-workers=16 origin/bucket local/bucket
```

**尝试的变体**:
- **全 bucket mirror**: xa 在 list 10 万对象时断开连接 (Connection closed by foreign host)
- **按 256 顶层目录拆**: 每个目录下还有 256 个子目录，list 阶段卡 7 分钟无输出

**问题**:
1. **xa 大 list 断连**: 超过几万个对象的 list 操作，xa 主动关闭 HTTP 连接
2. **目录层级太深**: 单个 `xx/` 目录有 256 个 `yy/` 子目录，list 规模仍然太大
3. **速度慢**: 按目录拆的话，256 个 Job 预估 1-2 小时

---

## 共同死因

**xa 的 gitlab-lfs-prod list 操作不稳定**

```
mc list 对象数 → 连接稳定性
0-10K          → 稳定
10K-50K        → 偶发断连
50K-100K+      → 必定断连 (Connection closed)
```

三个方案都死于同一个点：
- V1: `mc ls --recursive --json` 全桶 scan 卡住
- V2: batch replicate 内部 scan 触发 server hang
- V3: `mc mirror` 全桶 list 被 xa 断连

---

## 当前状态 (2026-06-23)

| 集群 | Source | Objects | Target | Gap | Status |
|------|--------|---------|--------|-----|--------|
| xa   | -      | 109,737 | -      | -   | 源站 |
| ly   | xa     | 95,937  | 109,737| 13,800 | ⚠️ 同步失败 (server crash) |
| ks   | xa     | 87,580  | 109,737| 22,157 | ⚠️ batch 还在跑，但 IncompleteBody |
| qd   | xa     | 87,609  | 109,737| 22,128 | ⚠️ batch 还在跑，但 IncompleteBody |
| dz   | xa     | 87,536  | 109,737| 22,201 | ⚠️ batch 还在跑，但 IncompleteBody |

**MinIO 版本**: RELEASE.2025-04-22T22-12-26Z（所有集群已升级）

---

## 推荐方案 D

### 256 顶层目录 × 独立 Job

**思路**: 把 list 规模控制在 xa 可接受范围内（~430 对象/目录）

```
xa gitlab-lfs-prod/
├── 00/    (~430 个对象)  ← Job #0
├── 01/    (~430 个对象)  ← Job #1
├── ...
└── ff/    (~430 个对象)  ← Job #255
```

**实现**:

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: minio-mirror-{xx}  # 00, 01, ..., ff
spec:
  backoffLimit: 3
  template:
    spec:
      containers:
        - name: mc-mirror
          image: image.ac.com:5000/k8s/ske-model-tool:v2-mc
          command: ["/bin/sh", "-c"]
          args:
            - |
              mc mirror --overwrite --max-workers=4 \
                origin/gitlab-lfs-prod/{xx}/ \
                local/gitlab-lfs-prod/{xx}/
          envFrom:
            - configMapRef:
                name: minio-replicate  # MC_HOST_origin, MC_HOST_local
```

**优势**:
1. **独立进程**: crash 不影响 MinIO server（解决 V2 问题）
2. **List 规模小**: ~430 对象/目录，xa 不会断连（解决 V3 问题）
3. **幂等可重跑**: `mc cp --overwrite` 天然 skip 已存在对象（解决 V1 问题）
4. **失败隔离**: 一个 Job 失败不影响其他 255 个
5. **可观测**: 每个 Job 独立完成，容易监控进度

**预估时间**:
- 256 个 Job 串行：4-8 小时
- 并行度 8：30-60 分钟
- 增量同步（后续 batch replicate）：几分钟

---

## 下一步

1. 批量生成 256 个 Job YAML
2. 控制在 ly 集群运行
3. 监控完成度
4. 全部完成后，重新启用 batch replicate CronJob 做增量同步

---

## 配置文件位置

- **minio-client chart**: `/Users/humin/sugon/ske-chart/minio-client/`
- **minio-server chart**: `/Users/humin/sugon/ske-chart/minio-server/`
- **监控脚本**: `/Users/humin/agent/scripts/minio_scan.py`
- **优化脚本**: `/Users/humin/agent/scripts/sync_optimizer.py`
