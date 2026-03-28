---
name: gitlab
description: "GitLab & MinIO 运维技能手册：LFS 对象管理、跨集群数据同步、故障排查。"
targets: ["*"]
---

# GitLab & MinIO 运维技能手册

## 1. 基础架构

### 1.1 GitLab 主集群

| 项目 | 值 |
|------|-----|
| 部署节点 | vlogin31 / vlogin32 / vlogin33 |
| 内网地址 | https://11.13.5.210:9002 |
| 外网地址 | https://gitlab.scnet.cn:9002 |
| 存储目录 | /aihub/gitlab |
| 账号 | root / SugonHpc2024_pro |
| LFS 启用 | 是（大文件通过 MinIO 存储） |

### 1.2 MinIO 主集群（西安）

| 项目 | 值 |
|------|-----|
| 部署节点 | vlogin34 / vlogin35 / vlogin36 |
| 内网地址 | http://11.13.5.210:9000 |
| 外网地址 | http://oss.scnet.cn:9000（公网 IP: 221.11.21.199:9000） |
| 存储目录 | /aihub/minio |
| 账号 | admin / SugonMinio2024_pro |
| GitLab LFS 桶 | gitlab-lfs-prod |

### 1.3 子集群 MinIO

| mc 别名 | 区域 | 说明 |
|---------|------|------|
| xaminio | 西安（主集群） | 数据源头 |
| ksminio | 昆山 | 子集群 |
| qdminio | 青岛 | 子集群 |
| dzminio | 达州 | 子集群 |
| zzminio | 郑州 | 子集群 |

> 子集群节点查找：`kubectl get nodes -l minio=true` 配合对应区域 context，然后用 node shell 登录。

## 2. 数据流架构

```
用户 git clone/pull
  → gitlab.scnet.cn:9002 拉取 git 元数据
  → LFS 指针解析后走 oss.scnet.cn:9000 拉取大文件
    → 子集群内 oss.scnet.cn 被 DNS 劫持到本地 MinIO（缓存层）
    → 缓存未命中 → 回源 http://221.11.21.199:9000（主集群公网）
```

## 3. GitLab LFS 对象存储规则

### 3.1 LFS 跟踪的文件后缀

- **模型权重**: `.safetensors` `.bin` `.pt` `.pth` `.ckpt` `.h5` `.onnx` `.pb` `.tflite` `.mlmodel` `.model` `.ot` `.ftz` `.gguf`
- **序列化数据**: `.pkl` `.joblib` `.msgpack` `.npy` `.npz` `.arrow` `.parquet`
- **压缩包**: `.7z` `.bz2` `.gz` `.rar` `.tar` `.tar.*` `.tgz` `.xz` `.zip` `.zst`

### 3.2 LFS 对象在 MinIO 中的存储路径

计算规则：
1. 对文件内容计算 `sha256`，得到 OID（十六进制字符串）
2. 存储路径：`gitlab-lfs-prod/{oid[0:2]}/{oid[2:4]}/{oid[4:]}`

示例：
```
OID = a1b2c3d4e5f6...
路径 = gitlab-lfs-prod/a1/b2/c3d4e5f6...
```

## 4. 常见运维场景

### 4.1 查看 GitLab 服务状态

```bash
# SSH 登录 GitLab 节点
ssh vlogin31

# 查看 GitLab 组件状态
gitlab-ctl status

# 查看日志
gitlab-ctl tail
gitlab-ctl tail gitlab-rails
```

### 4.2 查看 MinIO 服务状态

```bash
# SSH 登录 MinIO 节点
ssh vlogin34

# 查看 MinIO 进程
systemctl status minio
```

### 4.3 本地 mc 客户端操作

```bash
# 列出主集群 LFS 桶内容
mc ls xaminio/gitlab-lfs-prod/

# 查看桶信息
mc stat xaminio/gitlab-lfs-prod

# 查看某个 LFS 对象（已知 OID）
mc cat xaminio/gitlab-lfs-prod/a1/b2/c3d4e5f6...
```

### 4.4 从主集群同步 LFS 数据到子集群

当子集群缓存缺失、需要手动预热或批量同步时：

```bash
# 同步整个 LFS 桶到昆山
mc mirror xaminio/gitlab-lfs-prod ksminio/gitlab-lfs-prod

# 同步到青岛
mc mirror xaminio/gitlab-lfs-prod qdminio/gitlab-lfs-prod

# 同步到达州
mc mirror xaminio/gitlab-lfs-prod dzminio/gitlab-lfs-prod

# 同步到郑州
mc mirror xaminio/gitlab-lfs-prod zzminio/gitlab-lfs-prod

# 只同步特定前缀（如某个 OID 前缀）
mc mirror xaminio/gitlab-lfs-prod/a1/ ksminio/gitlab-lfs-prod/a1/
```

**在子集群节点上通过公网回源同步**（当本地 mc 无法直连时）：

```bash
# 先登录到子集群 MinIO 节点
# 例如昆山：通过 kubie 切到昆山 context，找到 minio 节点后 node shell

# 在子集群节点上配置主集群为远程源
mc alias set origin http://221.11.21.199:9000 admin SugonMinio2024_pro

# 同步
mc mirror origin/gitlab-lfs-prod local/gitlab-lfs-prod
```

### 4.5 查找某个 LFS 文件的 MinIO 存储位置

```bash
# 方法1：从 git 仓库中获取 LFS 指针的 OID
git lfs ls-files --long
# 输出格式: <oid> - <filename>

# 方法2：直接计算文件的 sha256
sha256sum <file>

# 然后按规则拼接路径
# OID=a1b2c3d4... → gitlab-lfs-prod/a1/b2/c3d4...

# 验证对象是否存在
mc stat xaminio/gitlab-lfs-prod/a1/b2/c3d4...
```

### 4.6 检查子集群 LFS 缓存命中情况

```bash
# 对比主集群和子集群的对象数量
mc ls --summarize xaminio/gitlab-lfs-prod/ | tail -1
mc ls --summarize ksminio/gitlab-lfs-prod/ | tail -1

# 查找主集群有但子集群缺失的对象
mc diff xaminio/gitlab-lfs-prod ksminio/gitlab-lfs-prod
```

### 4.7 GitLab API 常用操作

```bash
GITLAB_URL="https://gitlab.scnet.cn:9002"
TOKEN="<personal-access-token>"

# 列出项目
curl -k --header "PRIVATE-TOKEN: $TOKEN" "$GITLAB_URL/api/v4/projects?per_page=20"

# 查看某项目 LFS 对象
curl -k --header "PRIVATE-TOKEN: $TOKEN" \
  "$GITLAB_URL/api/v4/projects/<project_id>/repository/files/.gitattributes/raw?ref=main"
```

### 4.8 排查 LFS 拉取失败

1. **确认 git 端正常**：`git lfs env` 查看 LFS endpoint 是否指向正确地址
2. **确认 MinIO 端对象存在**：用 `mc stat` 检查对象是否在桶中
3. **确认网络连通性**：
   - 子集群 → 本地 MinIO：`curl -I http://<local-minio>:9000`
   - 子集群 → 主集群公网回源：`curl -I http://221.11.21.199:9000`
4. **查看 GitLab LFS 日志**：`gitlab-ctl tail gitlab-rails/production.log | grep lfs`

## 5. LFS 对象排查与补充工具

### 5.1 背景

GitLab 部分仓库的 LFS 指针映射的 object 在 MinIO (`gitlab-lfs-prod`) 中丢失，导致 `git clone` / `git lfs pull` 失败。拆分为两个独立脚本：

| 脚本 | 位置 | 执行环境 | 功能 |
|------|------|----------|------|
| `check_lfs.py` | `~/agent/gitlab/check_lfs.py` | 本地 | 排查仓库 LFS object 缺失 |
| `upload_lfs.py` | xa-login:`/tmp/upload_lfs.py` | xa-login | 上传本地文件补充 LFS object |

### 5.2 check_lfs.py — 排查仓库 LFS object 缺失

浅克隆指定仓库（`GIT_LFS_SKIP_SMUDGE=1`），遍历工作区中符合 LFS 后缀的文件，解析 LFS 指针获取 OID，用 `mc stat` 检查 object 是否存在。

```bash
# 直接传仓库 URL
python3 ~/agent/gitlab/check_lfs.py \
  https://gitlab.scnet.cn:9002/model/sugon_scnet/DeepSeek-V3.2.git \
  https://gitlab.scnet.cn:9002/model/sugon_scnet/Wan2.2-Animate-14B.git

# 从文件读取仓库列表（每行一个 URL，# 开头为注释）
python3 ~/agent/gitlab/check_lfs.py -f repos.txt
```

参数：
- 位置参数：GitLab 仓库 URL（可多个）
- `-f / --file`：从文件读取仓库 URL 列表

环境变量：`GITLAB_USER` / `GITLAB_PASS`（默认 root / SugonHpc2024_pro），`MC`（mc 路径，默认 `mc`）。

输出：每个仓库的 LFS 指针总数、已有数、缺失数，以及缺失明细（OID + 文件名 + 大小）。有缺失时 exit 1。

### 5.3 upload_lfs.py — 上传本地 LFS 文件到 MinIO

在 xa-login 上执行。扫描本地目录中符合 LFS 后缀的文件，计算 `sha256` 得到 OID，按 `gitlab-lfs-prod/{oid[0:2]}/{oid[2:4]}/{oid[4:]}` 路径上传。已存在的自动跳过。

```bash
# 直接传目录
python3 /tmp/upload_lfs.py \
  /work/home/openaimodels/ai_community/model/Qwen/Qwen3.5-27B \
  /work/home/openaimodels/ai_community/re_model/deepseek-ai/Janus-Pro-7B

# 从文件读取目录列表，并发 16
python3 /tmp/upload_lfs.py -f /tmp/dirs.txt -j 16

# dry-run 仅检查不上传
python3 /tmp/upload_lfs.py --dry-run /path/to/model

# 后台执行（防止 SSH 断连）
nohup python3 /tmp/upload_lfs.py -f /tmp/dirs.txt -j 12 &
```

参数：
- 位置参数：本地目录路径（可多个）
- `-f / --file`：从文件读取目录列表
- `-j / --jobs`：并发数（默认 12）
- `--dry-run`：仅扫描和检查，不实际上传

日志输出到 `/tmp/upload_lfs_YYYYMMDD_HHMMSS.log`。

部署方式：`scp ~/agent/gitlab/upload_lfs.py xa-login:/tmp/upload_lfs.py`

### 5.4 典型工作流

```
1. 本地执行 check_lfs.py 排查哪些仓库有缺失
2. 在 xa-login 下载对应模型文件到本地目录
3. 在 xa-login 执行 upload_lfs.py 将本地文件补充上传到 MinIO
4. 本地再次 check_lfs.py 验证缺失已修复
```

## 6. 安全注意事项

- 所有 `mc rm` / `mc rb` / `mc mv` 操作需要**人工确认**后再执行
- 同步操作（`mc mirror`）在大数据量时注意带宽影响，建议在低峰期执行
- 跨集群同步走公网（221.11.21.199:9000）时注意流量成本
- GitLab / MinIO 的账号密码属于敏感信息，仅在必要时使用
