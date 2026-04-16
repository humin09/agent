# ske-model 可用模型列表
生成时间: 2026-04-14 18:06:56

## 昆山 集群

### api-32b-deepseek
- Host: `api-32b-deepseek.ksai.scnet.cn`
- 部署状态: ❌ 不可用
- 错误: HTTP 404

### deepseek-r1
- 副本数: 1/1
- 访问地址: `http://r1-h20.ksai.scnet.cn:58000`
- 模型信息:
  - `/opt/model/DeepSeek-R1`
    - 最大上下文长度: 65536

#### 验证过的 curl 命令:
```bash
curl -X POST 'http://r1-h20.ksai.scnet.cn:58000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "/opt/model/DeepSeek-R1",
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.7,
    "stream": false
  }'
```

