---
name: minio
description: "MinIO 运维技能：桶授权、同步进度、对象检查与跨集群数据维护。"
---

# MinIO 运维技能

## 使用场景

- 查询 MinIO 同步进度、桶容量、对象数、错误率。
- 检查对象是否存在、定位对象路径、排查对象访问失败。
- 为用户或服务账号配置桶级访问授权。
- 维护跨集群 MinIO 数据同步。

## 安全规则

- `mc rm|rb|mv` 属于高风险变更，执行前必须按 AGENTS 变更确认模板等待用户确认。
- 修改用户、policy、桶权限属于线上变更，执行前必须明确目标集群、MinIO alias、桶名、用户或服务账号、影响范围和回滚方式。
- 禁止对未知桶或未知用户批量授权；不确定时先查询现状。
- 授权完成后，如权限由 Helm/YAML 或脚本维护，必须同步回写本地配置仓库。

## 桶授权

### 默认授权权限

当给用户进行桶授权时，默认授予以下 S3 Action：

- `s3:ListBucket`
- `s3:GetBucketLocation`
- `s3:GetObject`
- `s3:PutObject`
- `s3:DeleteObject`
- `s3:ListBucketMultipartUploads`
- `s3:AbortMultipartUpload`
- `s3:ListMultipartUploadParts`

### 默认桶配置

- 创建桶默认不开启 versioning。
- 创建桶默认不开启定期清理。
- 桶授权权限固定使用默认授权权限列表，不按 versioning 场景扩展。

### 默认授权范围

- `s3:ListBucket`、`s3:GetBucketLocation`、`s3:ListBucketMultipartUploads` 作用于桶资源：`arn:aws:s3:::<bucket>`
- 对象读写和分片上传相关权限作用于对象资源：`arn:aws:s3:::<bucket>/*`
- 如用户只要求只读授权，不要默认加入 `s3:PutObject`、`s3:DeleteObject`、`s3:ListBucketMultipartUploads`、`s3:AbortMultipartUpload`、`s3:ListMultipartUploadParts`，必须先确认需求。
- 默认授权包含对象删除权限 `s3:DeleteObject`，执行实际删除对象操作仍需按高风险规则确认。

### Policy 模板

为 `<bucket>` 授予默认读写上传权限的 policy 内容：

- 桶级权限：`{"Effect":"Allow","Action":["s3:ListBucket","s3:GetBucketLocation","s3:ListBucketMultipartUploads"],"Resource":["arn:aws:s3:::<bucket>"]}`
- 对象与分片上传权限：`{"Effect":"Allow","Action":["s3:GetObject","s3:PutObject","s3:DeleteObject","s3:AbortMultipartUpload","s3:ListMultipartUploadParts"],"Resource":["arn:aws:s3:::<bucket>/*"]}`

### 操作流程

- 查询目标用户现有信息：`mc admin user info <alias> <user>`
- 查询现有 policy：`mc admin policy info <alias> <policy-name>`
- 创建或更新 policy 前，先向用户展示完整 policy JSON、目标 alias、桶名、用户、影响范围和回滚方式。
- 绑定 policy：`mc admin policy attach <alias> <policy-name> --user <user>`
- 验证授权：`mc ls <alias>/<bucket>`、`mc cp <test-file> <alias>/<bucket>/<test-key>`、`mc rm <alias>/<bucket>/<test-key>` 前必须按高风险规则确认删除测试对象。

## 同步进度

### 常用命令

- 扫描多集群 MinIO 同步进度：`python ~/agent/scripts/minio_scan.py -c ks zz qd dz`

## 参考入口

- GitLab LFS 与 MinIO 专项排障：`~/agent/gitlab/SKILL.md`
- 集群统一规则：`~/agent/AGENTS.md`
