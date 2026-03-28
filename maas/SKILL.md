---
name: maas
description: "Maas 模型 URL 生成与探测（基于探测结果拼接可访问推理地址）"
targets: ["*"]
---

# Maas 模型 URL 生成与探测

本 Skill 用于基于 `/tmp/model_probe_rows.json` 生成可访问的模型推理 URL（`host:58000`）。

## 输入来源
- 探测结果文件：`/tmp/model_probe_rows.json`
- 关键字段：`host`、`model`、`path`、`post_status`

## 规则
1. 仅将 `post_status=200` 的条目视为“当前可访问”。
2. URL 统一拼接为：`http://<host>:58000<path>`。
3. `path=/v1/chat/completions` 时使用 chat 请求体（`messages`）。
4. `path=/v1/embeddings` 时使用 embedding 请求体（`input`）。
5. `path=/v1/images/generations` 时使用 image 请求体（`prompt`）。

## 关于 minimax-m25 的模型名
- 用户给出的地址 `http://minimax-m25.zzai2.scnet.cn:58000/model` 当前返回 ingress 默认 404 页面，不能直接拿模型名。
- 同组可达域名的 `/v1/models` 实测结果：
  - `minimax-m25-internal.zzai2.scnet.cn` -> `MiniMax-M2.5`
  - `minimax-m25-w8a8.zzai2.scnet.cn` -> `/models/MiniMax-M2.5-W8A8`
  - `minimax-m25-tencent.zzai2.scnet.cn` -> `/models/MiniMax-M2.5-W8A8`
  - `minimax-m25-zd.zzai2.scnet.cn` -> `/models/MiniMax-M2.5-bf16`

## 可访问 URL（快照，更新于 2026-03-29）

### KS
- `http://api-32b-deepseek.ksai.scnet.cn:58000/v1/chat/completions` model=`/opt/model/DeepSeek-R1-Distill-Qwen-32B`
- `http://deepseek-32b.ksai.scnet.cn:58000/v1/chat/completions` model=`/opt/model/DeepSeek-R1-Distill-Qwen-32B`
- `http://deepseek-70b.ksai.scnet.cn:58000/v1/chat/completions` model=`/opt/model/DeepSeek-R1-Distill-Llama-70B`
- `http://deepseek-r1-0528-8b.ksai.scnet.cn:58000/v1/chat/completions` model=`/opt/model/DeepSeek-R1-0528-Qwen3-8B`
- `http://qwen3-30b-k100.ksai.scnet.cn:58000/v1/chat/completions` model=`/opt/model/Qwen3-30B-A3B`
- `http://qwen3-30b.ksai.scnet.cn:58000/v1/chat/completions` model=`/opt/model/Qwen3-30B-A3B`
- `http://qwen3-embedding-8b.ksai.scnet.cn:58000/v1/embeddings` model=`/opt/model/Qwen3-Embedding-8B`
- `http://qwq-32b.ksai.scnet.cn:58000/v1/chat/completions` model=`/opt/model/QwQ-32B`
- `http://r1-h20.ksai.scnet.cn:58000/v1/chat/completions` model=`/opt/model/DeepSeek-R1`
- `http://z100-32b.ksai.scnet.cn:58000/v1/chat/completions` model=`/opt/model/DeepSeek-R1-Distill-Qwen-32B`

### ZZ
- `http://minimax-m2.zzai2.scnet.cn:58000/v1/chat/completions` model=`MiniMax-M2`
- `http://minimax-m25-internal.zzai2.scnet.cn:58000/v1/chat/completions` model=`MiniMax-M2.5`
- `http://minimax-m25-tencent.zzai2.scnet.cn:58000/v1/chat/completions` model=`/models/MiniMax-M2.5-W8A8`
- `http://minimax-m25-w8a8.zzai2.scnet.cn:58000/v1/chat/completions` model=`/models/MiniMax-M2.5-W8A8`
- `http://minimax-m25-zd.zzai2.scnet.cn:58000/v1/chat/completions` model=`/models/MiniMax-M2.5-bf16`
- `http://qwen3-235b-a22b-thinking-2507.zzai2.scnet.cn:58000/v1/chat/completions` model=`/data/models/Qwen3-235B-A22B-Thinking-2507`
- `http://qwen3-235b-a22b.zzai2.scnet.cn:58000/v1/chat/completions` model=`/data/model/Qwen3-235B-A22B`
- `http://qwen3-30b-a3b-instruct-2507.zzai2.scnet.cn:58000/v1/chat/completions` model=`/data/models/Qwen3-30B-A3B-Instruct-2507`

## 标准请求模板

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
