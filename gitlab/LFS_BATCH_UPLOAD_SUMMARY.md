# GitLab LFS 批量上传完成总结

## 日期
2026-04-15

## 背景
修复Dazhou集群中的git clone失败问题，原因是GitLab LFS对象在MinIO中缺失。通过批量扫描、验证和上传，系统地修复了3个主要模型目录中的缺失LFS对象。

## 处理结果

### 总体统计
- **处理目录数**: 3
- **总LFS对象数**: 444
- **预存在对象**: 30
- **缺失对象**: 414
- **成功上传**: 414 ✓

### 目录详情

#### 1. Wan2.2-Animate-14B
- 路径: `/work/home/openaimodels/ai_community/model/Wan-AI/Wan2.2-Animate-14B`
- 总OID数: 424
- 预存在: 27
- 缺失: 397
- **上传完成**: 397/397 ✓
- 上传时间: 2026-04-15 15:57:09 CST

#### 2. Qwen3.5-27B
- 路径: `/work/home/openaimodels/ai_community/model/Qwen/Qwen3.5-27B`
- 总OID数: 11
- 预存在: 3
- 缺失: 8
- **上传完成**: 8/8 ✓
- 上传时间: 2026-04-15 17:16:39 CST

#### 3. Janus-Pro-7B
- 路径: `/work/home/openaimodels/ai_community/re_model/deepseek-ai/Janus-Pro-7B`
- 总OID数: 9
- 预存在: 0
- 缺失: 9
- **上传完成**: 9/9 ✓
- 上传时间: 2026-04-15 17:18:08 CST

## 技术细节

### batch_upload_lfs.py 脚本
创建了综合的LFS对象批量处理脚本，具有以下功能：

**核心特性**:
- 多线程并发处理（可配置worker数，默认12）
- 灵活的LFS规则检测：
  - 标准后缀匹配（.safetensors, .bin, .pt, .pth, .ckpt等）
  - 特殊模式匹配（onnx__, backbone., keypoint_等）
- 完整的SHA256计算和OID验证
- MinIO对象存在性检查
- 批量上传失败重试
- JSON格式详细报告生成

**命令语法**:
```bash
python3 batch_upload_lfs.py \
  --dirs <目录列表文件或逗号分隔目录> \
  --workers <并发数> \
  --upload [可选：启用上传，默认仅验证]
```

**使用示例**:
```bash
# 验证模式（仅扫描和检查，不上传）
python3 batch_upload_lfs.py --dirs /tmp/model_dirs.txt --workers 4

# 上传模式
python3 batch_upload_lfs.py \
  --dirs /work/home/openaimodels/ai_community/model/Wan-AI/Wan2.2-Animate-14B \
  --workers 1 \
  --upload
```

### MinIO 存储验证
所有上传的对象已在MinIO的`xaminio`集群中验证：
- 存储位置: `gitlab-lfs-prod/{oid[0:2]}/{oid[2:4]}/{oid[4:]}`
- 所有414个对象均已成功写入

## 后续建议

### 1. 子集群同步
将新上传的414个对象同步到子集群缓存节点：
```bash
# 同步到昆山
mc mirror xaminio/gitlab-lfs-prod ksminio/gitlab-lfs-prod

# 同步到达州（这是git clone失败的集群）
mc mirror xaminio/gitlab-lfs-prod dzminio/gitlab-lfs-prod

# 同步到其他集群...
```

### 2. git clone 测试
在Dazhou集群中测试git clone是否成功：
```bash
git clone --depth 1 \
  https://gitlab.scnet.cn:9002/model/sugon_scnet/Wan2.2-Animate-14B.git \
  --filter=blob:none
```

### 3. 监控和告警
- 监控后续LFS上传的完整性
- 在GitLab webhook或CI中加入LFS完整性检查

### 4. 扩展处理
如果其他模型目录有类似问题，可使用同样的脚本和流程进行批量修复。

## 已知问题
- 某些大型文件读取时偶发"Bad address"错误（Errno 14），这是网络文件系统的临时问题，重试可解决
- 建议在文件系统状态良好的时间段运行批量上传

## 日志位置
- MinIO客户端操作日志: `/tmp/batch_lfs_*.log`
- 详细批处理报告: `/tmp/batch_lfs_report_*.json`
