---
name: k8s-minio
description: "K8s MinIO 运维子专题：节点定位、桶巡检、对象排查"
targets: ["*"]
---

你现在进入 **K8s MinIO 子专题**。

常用桶：`prom` `loki` `gitlab-lfs-prod`

排障流程：
1. 定位节点：`kubectl --context=<别名> get node -l minio=true -o wide`
2. 进入节点：`kubectl node-shell --context=<别名> <minio节点IP>`
3. 核验对象：`mc ls <alias>/` 与 `mc ls <alias>/<bucket>/`

西安快速通道：
- `ssh xa-login "~/mc ls oss_scnet/"`
- `ssh xa-login "~/mc ls oss_scnet/gitlab-lfs-prod/"`
- `ssh xa-login "~/mc cp <远程路径> oss_scnet/<桶>/<路径>"`

工具脚本：
- `minio_bucket_policy.py` - MinIO 桶策略分析与报告工具

高风险约束：`mc rm` / `mc rb` / `mc mv` 必须先确认。
