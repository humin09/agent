# 模型可用性探测报告
生成时间: 2026-04-02 11:38:54

## 昆山 (ks) 集群
### api-32b-deepseek
- Host: `api-32b-deepseek.ksai.scnet.cn`
- 部署状态: ❌ 不可用
#### 探测命令:
**Chat Completions**:
```bash
curl -X POST 'http://api-32b-deepseek.ksai.scnet.cn:58000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "api-32b-deepseek",
    "messages": [
      {"role": "user", "content": "你好"}
    ],
    "temperature": 0.7,
    "stream": false
  }'
```



## 郑州 (zz) 集群
### minimax-m25-int8
- Host: `minimax-m25-int8.zzai2.scnet.cn`
- 部署状态: ✅ 可用
#### 探测命令:
**Chat Completions**:
```bash
curl -X POST 'http://minimax-m25-int8.zzai2.scnet.cn:58000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "minimax-m25-int8",
    "messages": [
      {"role": "user", "content": "你好"}
    ],
    "temperature": 0.7,
    "stream": false
  }'
```


