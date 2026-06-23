# 模型服务信息

## 模型总览

| 模型 | 集群 | Chat | Responses | Anthropic | 副本数 |
|------|------|------|-----------|-----------|--------|
| deepseek-32b | 昆山 | ✅ | ❌ | ❌ | 5/5 |
| deepseek-7b | 昆山 | ✅ | ❌ | ❌ | 5/5 |
| deepseek-r1-0528-8b | 昆山 | ✅ | ❌ | ❌ | 20/20 |
| deepseek-r1-70b | 昆山 | ✅ | ❌ | ❌ | 3/3 |
| deepseek-v4-pro | 昆山 | ✅ | ✅ | ✅ | 1/1 |
| qwen3-30b | 昆山 | ✅ | ❌ | ❌ | 4/4 |
| qwen3-embedding-8b | 昆山 | ✅ | ❌ | ❌ | 8/8 |
| qwen36-35b-a3b | 昆山 | ✅ | ✅ | ✅ | 1/1 |
| qwq-32b | 昆山 | ✅ | ❌ | ❌ | 11/11 |
| minimax-m25-int8 | 纽约 | ✅ | ✅ | ✅ | 1/1 |
| qwen3-235b-a22b | 纽约 | ✅ | ✅ | ✅ | 1/1 |
| minimax-m25-int8 | 郑州 | ✅ | ✅ | ✅ | 20/8 |
| qwen3-235b-a22b | 郑州 | ✅ | ✅ | ✅ | 10/10 |
| qwen3-235b-a22b-thinking-2507 | 郑州 | ✅ | ❌ | ❌ | 1/1 |
| qwen3-30b-a3b-instruct-2507 | 郑州 | ✅ | ❌ | ❌ | 3/1 |

## 昆山

### deepseek-32b
**模型信息**

- 模型名称: deepseek-32b
- base_url: http://deepseek-32b.ksai.scnet.cn:58000
- model_id: /opt/model/DeepSeek-R1-Distill-Qwen-32B
- 模型最大上下文长度: 32768
- 副本数: 5/5

**协议支持总览**

| 协议 | 支持 | 状态码 | basic | stream | usage | tool_calls | JSON output | structured output | error format |
|---|---|---|---|---|---|---|---|---|---|
| OpenAI Chat Completions | ✅ | 200 | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ | ✅ |
| OpenAI Responses | ❌ | 404 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Anthropic Messages | ❌ | 404 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

请求示例:
```bash
curl -X POST 'http://deepseek-32b.ksai.scnet.cn:58000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "/opt/model/DeepSeek-R1-Distill-Qwen-32B",
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.7,
    "stream": false
  }'
```

### deepseek-7b
**模型信息**

- 模型名称: deepseek-7b
- base_url: http://deepseek-7b.ksai.scnet.cn:58000
- model_id: /opt/model/DeepSeek-R1-Distill-Qwen-7B
- 模型最大上下文长度: 32768
- 副本数: 5/5

**协议支持总览**

| 协议 | 支持 | 状态码 | basic | stream | usage | tool_calls | JSON output | structured output | error format |
|---|---|---|---|---|---|---|---|---|---|
| OpenAI Chat Completions | ✅ | 200 | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ | ✅ |
| OpenAI Responses | ❌ | 404 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Anthropic Messages | ❌ | 404 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

请求示例:
```bash
curl -X POST 'http://deepseek-7b.ksai.scnet.cn:58000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "/opt/model/DeepSeek-R1-Distill-Qwen-7B",
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.7,
    "stream": false
  }'
```

### deepseek-r1-0528-8b
**模型信息**

- 模型名称: deepseek-r1-0528-8b
- base_url: http://deepseek-r1-0528-8b.ksai.scnet.cn:58000
- model_id: /opt/model/DeepSeek-R1-0528-Qwen3-8B
- 模型最大上下文长度: 32768
- 副本数: 20/20

**协议支持总览**

| 协议 | 支持 | 状态码 | basic | stream | usage | tool_calls | JSON output | structured output | error format |
|---|---|---|---|---|---|---|---|---|---|
| OpenAI Chat Completions | ✅ | 200 | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ |
| OpenAI Responses | ❌ | 404 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Anthropic Messages | ❌ | 404 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

请求示例:
```bash
curl -X POST 'http://deepseek-r1-0528-8b.ksai.scnet.cn:58000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "/opt/model/DeepSeek-R1-0528-Qwen3-8B",
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.7,
    "stream": false
  }'
```

### deepseek-r1-70b
**模型信息**

- 模型名称: deepseek-r1-70b
- base_url: http://deepseek-r1-70b.ksai.scnet.cn:58000
- model_id: /opt/model/DeepSeek-R1-Distill-Llama-70B
- 模型最大上下文长度: 32000
- 副本数: 3/3

**协议支持总览**

| 协议 | 支持 | 状态码 | basic | stream | usage | tool_calls | JSON output | structured output | error format |
|---|---|---|---|---|---|---|---|---|---|
| OpenAI Chat Completions | ✅ | 200 | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ |
| OpenAI Responses | ❌ | 404 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Anthropic Messages | ❌ | 404 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

请求示例:
```bash
curl -X POST 'http://deepseek-r1-70b.ksai.scnet.cn:58000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "/opt/model/DeepSeek-R1-Distill-Llama-70B",
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.7,
    "stream": false
  }'
```

### deepseek-v4-pro
**模型信息**

- 模型名称: deepseek-v4-pro
- base_url: http://deepseek-v4-pro.ksai.scnet.cn:58000
- model_id: deepseek-v4-pro
- 模型最大上下文长度: 1000000
- 副本数: 1/1

**协议支持总览**

| 协议 | 支持 | 状态码 | basic | stream | usage | tool_calls | JSON output | structured output | error format |
|---|---|---|---|---|---|---|---|---|---|
| OpenAI Chat Completions | ✅ | 200 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| OpenAI Responses | ✅ | 200 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Anthropic Messages | ✅ | 200 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

请求示例:
```bash
curl -X POST 'http://deepseek-v4-pro.ksai.scnet.cn:58000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "deepseek-v4-pro",
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.7,
    "stream": false
  }'
```
OpenAI Responses 示例:
```bash
curl -X POST 'http://deepseek-v4-pro.ksai.scnet.cn:58000/v1/responses' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "deepseek-v4-pro",
    "input": "你好，请用一句话介绍你自己",
    "max_output_tokens": 128
  }'
```

### qwen3-30b
**模型信息**

- 模型名称: qwen3-30b
- base_url: http://qwen3-30b.ksai.scnet.cn:58000
- model_id: /opt/model/Qwen3-30B-A3B
- 模型最大上下文长度: 131072
- 副本数: 4/4

**协议支持总览**

| 协议 | 支持 | 状态码 | basic | stream | usage | tool_calls | JSON output | structured output | error format |
|---|---|---|---|---|---|---|---|---|---|
| OpenAI Chat Completions | ✅ | 200 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| OpenAI Responses | ❌ | 404 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Anthropic Messages | ❌ | 404 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

请求示例:
```bash
curl -X POST 'http://qwen3-30b.ksai.scnet.cn:58000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "/opt/model/Qwen3-30B-A3B",
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.7,
    "stream": false
  }'
```

### qwen3-embedding-8b
**模型信息**

- 模型名称: qwen3-embedding-8b
- base_url: http://qwen3-embedding-8b.ksai.scnet.cn:58000
- model_id: /opt/model/Qwen3-Embedding-8B
- 模型最大上下文长度: 131072
- 副本数: 8/8

**协议支持总览**

| 协议 | 支持 | 状态码 | basic | stream | usage | tool_calls | JSON output | structured output | error format |
|---|---|---|---|---|---|---|---|---|---|
| OpenAI Chat Completions | ✅ | 200 | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ | ✅ |
| OpenAI Responses | ❌ | 404 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Anthropic Messages | ❌ | 404 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

请求示例:
```bash
curl -X POST 'http://qwen3-embedding-8b.ksai.scnet.cn:58000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "/opt/model/Qwen3-Embedding-8B",
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.7,
    "stream": false
  }'
```

### qwen36-35b-a3b
**模型信息**

- 模型名称: qwen36-35b-a3b
- base_url: http://qwen36-35b-a3b.ksai.scnet.cn:58000
- model_id: Qwen3.6-35B-A3B
- 模型最大上下文长度: 262144
- 副本数: 1/1

**协议支持总览**

| 协议 | 支持 | 状态码 | basic | stream | usage | tool_calls | JSON output | structured output | error format |
|---|---|---|---|---|---|---|---|---|---|
| OpenAI Chat Completions | ✅ | 200 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| OpenAI Responses | ✅ | 200 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Anthropic Messages | ✅ | 200 | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ |

请求示例:
```bash
curl -X POST 'http://qwen36-35b-a3b.ksai.scnet.cn:58000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "Qwen3.6-35B-A3B",
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.7,
    "stream": false
  }'
```
OpenAI Responses 示例:
```bash
curl -X POST 'http://qwen36-35b-a3b.ksai.scnet.cn:58000/v1/responses' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "Qwen3.6-35B-A3B",
    "input": "你好，请用一句话介绍你自己",
    "max_output_tokens": 128
  }'
```

### qwq-32b
**模型信息**

- 模型名称: qwq-32b
- base_url: http://qwq-32b.ksai.scnet.cn:58000
- model_id: /opt/model/QwQ-32B
- 模型最大上下文长度: 32768
- 副本数: 11/11

**协议支持总览**

| 协议 | 支持 | 状态码 | basic | stream | usage | tool_calls | JSON output | structured output | error format |
|---|---|---|---|---|---|---|---|---|---|
| OpenAI Chat Completions | ✅ | 200 | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ | ✅ |
| OpenAI Responses | ❌ | 404 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Anthropic Messages | ❌ | 404 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

请求示例:
```bash
curl -X POST 'http://qwq-32b.ksai.scnet.cn:58000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "/opt/model/QwQ-32B",
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.7,
    "stream": false
  }'
```

## 纽约

### minimax-m25-int8
**模型信息**

- 模型名称: minimax-m25-int8
- base_url: http://minimax-m25-int8.zzai.scnet.ai:58000
- model_id: MiniMax-M2.5-W8A8
- 模型最大上下文长度: 196608
- 副本数: 1/1

**协议支持总览**

| 协议 | 支持 | 状态码 | basic | stream | usage | tool_calls | JSON output | structured output | error format |
|---|---|---|---|---|---|---|---|---|---|
| OpenAI Chat Completions | ✅ | 200 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| OpenAI Responses | ✅ | 200 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Anthropic Messages | ✅ | 200 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

请求示例:
```bash
curl -X POST 'http://minimax-m25-int8.zzai.scnet.ai:58000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "MiniMax-M2.5-W8A8",
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.7,
    "stream": false
  }'
```
OpenAI Responses 示例:
```bash
curl -X POST 'http://minimax-m25-int8.zzai.scnet.ai:58000/v1/responses' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "MiniMax-M2.5-W8A8",
    "input": "你好，请用一句话介绍你自己",
    "max_output_tokens": 128
  }'
```

### qwen3-235b-a22b
**模型信息**

- 模型名称: qwen3-235b-a22b
- base_url: http://qwen3-235b-a22b.zzai.scnet.ai:58000
- model_id: Qwen3-235B-A22B
- 模型最大上下文长度: 32768
- 副本数: 1/1

**协议支持总览**

| 协议 | 支持 | 状态码 | basic | stream | usage | tool_calls | JSON output | structured output | error format |
|---|---|---|---|---|---|---|---|---|---|
| OpenAI Chat Completions | ✅ | 200 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| OpenAI Responses | ✅ | 200 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Anthropic Messages | ✅ | 200 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

请求示例:
```bash
curl -X POST 'http://qwen3-235b-a22b.zzai.scnet.ai:58000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "Qwen3-235B-A22B",
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.7,
    "stream": false
  }'
```
OpenAI Responses 示例:
```bash
curl -X POST 'http://qwen3-235b-a22b.zzai.scnet.ai:58000/v1/responses' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "Qwen3-235B-A22B",
    "input": "你好，请用一句话介绍你自己",
    "max_output_tokens": 128
  }'
```

## 郑州

### minimax-m25-int8
**模型信息**

- 模型名称: minimax-m25-int8
- base_url: http://minimax-m25-int8.zzai.scnet.cn:58000
- model_id: /models/MiniMax-M2.5-W8A8
- 模型最大上下文长度: 196608
- 副本数: 20/8

**协议支持总览**

| 协议 | 支持 | 状态码 | basic | stream | usage | tool_calls | JSON output | structured output | error format |
|---|---|---|---|---|---|---|---|---|---|
| OpenAI Chat Completions | ✅ | 200 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| OpenAI Responses | ✅ | 200 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Anthropic Messages | ✅ | 200 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

请求示例:
```bash
curl -X POST 'http://minimax-m25-int8.zzai.scnet.cn:58000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "/models/MiniMax-M2.5-W8A8",
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.7,
    "stream": false
  }'
```
OpenAI Responses 示例:
```bash
curl -X POST 'http://minimax-m25-int8.zzai.scnet.cn:58000/v1/responses' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "/models/MiniMax-M2.5-W8A8",
    "input": "你好，请用一句话介绍你自己",
    "max_output_tokens": 128
  }'
```

### qwen3-235b-a22b
**模型信息**

- 模型名称: qwen3-235b-a22b
- base_url: http://qwen3-235b-a22b.zzai.scnet.cn:58000
- model_id: /models/Qwen3-235B-A22B
- 模型最大上下文长度: 32768
- 副本数: 10/10

**协议支持总览**

| 协议 | 支持 | 状态码 | basic | stream | usage | tool_calls | JSON output | structured output | error format |
|---|---|---|---|---|---|---|---|---|---|
| OpenAI Chat Completions | ✅ | 200 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| OpenAI Responses | ✅ | 200 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Anthropic Messages | ✅ | 200 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

请求示例:
```bash
curl -X POST 'http://qwen3-235b-a22b.zzai.scnet.cn:58000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "/models/Qwen3-235B-A22B",
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.7,
    "stream": false
  }'
```
OpenAI Responses 示例:
```bash
curl -X POST 'http://qwen3-235b-a22b.zzai.scnet.cn:58000/v1/responses' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "/models/Qwen3-235B-A22B",
    "input": "你好，请用一句话介绍你自己",
    "max_output_tokens": 128
  }'
```

### qwen3-235b-a22b-thinking-2507
**模型信息**

- 模型名称: qwen3-235b-a22b-thinking-2507
- base_url: http://qwen3-235b-a22b-thinking-2507.zzai.scnet.cn:58000
- model_id: /data/models/Qwen3-235B-A22B-Thinking-2507
- 模型最大上下文长度: 32768
- 副本数: 1/1

**协议支持总览**

| 协议 | 支持 | 状态码 | basic | stream | usage | tool_calls | JSON output | structured output | error format |
|---|---|---|---|---|---|---|---|---|---|
| OpenAI Chat Completions | ✅ | 200 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| OpenAI Responses | ❌ | 404 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Anthropic Messages | ❌ | 404 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

请求示例:
```bash
curl -X POST 'http://qwen3-235b-a22b-thinking-2507.zzai.scnet.cn:58000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "/data/models/Qwen3-235B-A22B-Thinking-2507",
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.7,
    "stream": false
  }'
```

### qwen3-30b-a3b-instruct-2507
**模型信息**

- 模型名称: qwen3-30b-a3b-instruct-2507
- base_url: http://qwen3-30b-a3b-instruct-2507.zzai.scnet.cn:58000
- model_id: /data/models/Qwen3-30B-A3B-Instruct-2507
- 模型最大上下文长度: 262144
- 副本数: 3/1

**协议支持总览**

| 协议 | 支持 | 状态码 | basic | stream | usage | tool_calls | JSON output | structured output | error format |
|---|---|---|---|---|---|---|---|---|---|
| OpenAI Chat Completions | ✅ | 200 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| OpenAI Responses | ❌ | 404 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Anthropic Messages | ❌ | 404 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

请求示例:
```bash
curl -X POST 'http://qwen3-30b-a3b-instruct-2507.zzai.scnet.cn:58000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "/data/models/Qwen3-30B-A3B-Instruct-2507",
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.7,
    "stream": false
  }'
```

