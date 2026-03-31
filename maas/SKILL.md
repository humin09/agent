---
name: maas
description: "Maas 模型 可用性探测（基于探测结果拼接可访问推理地址）"
targets: ["*"]
---

# Maas 模型 URL 生成与探测

本 Skill 用于基于校验ske-model在昆山和郑州的部署和服务可用的检查 `生成可访问的模型推理 URL（`host:58000`）。



## 规则
1. 仅将 `post_status=200` 的条目视为“当前可访问”。
2. URL 统一拼接为：`http://<host>:58000<path>`。
3. 获取模型信息的路径为: `http://<host>:58000/model`。
3. `path=/v1/chat/completions` 时使用 chat 请求体（`messages`）。
4. `path=/v1/embeddings` 时使用 embedding 请求体（`input`）。
5. `path=/v1/images/generations` 时使用 image 请求体（`prompt`）。
6. ingress(host)和deployment, svc的命名映射规则基本都是host=deployment=svc


## 使用场景
1. 检查服务的可用性, 需要生成curl请求, 本地可拿到200的响应.
### Chat
```bash
curl -X POST 'http://<host>:58000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "<model>",
    "messages": [
      {"role": "user", "content": "你好"}
    ],
    "temperature": 0.7,
    "stream": false
  }'
```

### Embeddings
```bash
curl -X POST 'http://<host>:58000/v1/embeddings' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "<model>",
    "input": "你好"
  }'
```

### Images
```bash
curl -X POST 'http://<host>:58000/v1/images/generations' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "<model>",
    "prompt": "一只在月球上奔跑的橘猫"
  }'
```
2. 检查deployment的replica
3. 检查服务异常的时候, 找到对应的pod分析日志.


