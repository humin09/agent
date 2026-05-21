## 模型总览

| 模型 | /v1/chat/completions | Anthropic | Responses | 工具调用 | 副本数 |
|------|----------------------|-----------|-----------|---------|--------|
| deepseek-32b | ✅ | ❌ | ❌(404) | 未探测 | 5/5 |
| deepseek-7b | ✅ | ❌ | ❌(404) | 未探测 | 5/5 |
| deepseek-r1-0528-8b | ❌ | ❌ | ❌ | ❌ | 20/20 |
| deepseek-r1-70b | ✅ | ❌ | ❌(404) | 未探测 | 3/3 |
| deepseek-v4-flash | ✅ | ✅ | ✅ | ✅ | 1/1 |
| deepseek-v4-pro | ❌ | ❌ | ❌ | ❌ | 1/1 |
| minimax-m25-int8-vip | ✅ | ✅ | ✅ | ❌ | 25/25 |
| qwen3-30b | ❌ | ❌ | ❌ | ❌ | 4/4 |
| qwen3-embedding-8b | ✅ | ❌ | ❌(404) | 未探测 | 8/8 |
| qwen35-122b-a10 | ✅ | ✅ | ❌(400) | 未探测 | 1/1 |
| qwen36-27b | ❌ | ❌ | ❌ | ❌ | 2/2 |
| qwen36-35b-a3b | ❌ | ❌ | ❌ | ❌ | 1/1 |
| qwq-32b | ❌ | ❌ | ❌ | ❌ | 11/11 |

## 昆山

### deepseek-32b
- /v1/chat/completions ✅
- Anthropic 协议: ❌
- OpenAI Responses 协议: ❌(404)
- Responses 工具调用: 未探测
- 模型信息: /opt/model/DeepSeek-R1-Distill-Qwen-32B
- 模型最大上下文长度: 32768
- 副本数: 5/5

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
- /v1/chat/completions ✅
- Anthropic 协议: ❌
- OpenAI Responses 协议: ❌(404)
- Responses 工具调用: 未探测
- 模型信息: /opt/model/DeepSeek-R1-Distill-Qwen-7B
- 模型最大上下文长度: 32768
- 副本数: 5/5

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

### deepseek-r1-70b
- /v1/chat/completions ✅
- Anthropic 协议: ❌
- OpenAI Responses 协议: ❌(404)
- Responses 工具调用: 未探测
- 模型信息: /opt/model/DeepSeek-R1-Distill-Llama-70B
- 模型最大上下文长度: 32000
- 副本数: 3/3

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

### deepseek-v4-flash
- /v1/chat/completions ✅
- Anthropic 协议: ✅
- OpenAI Responses 协议: ✅
- Responses 工具调用: ✅
- 模型信息: DeepSeek-V4-Flash
- 模型最大上下文长度: 1000000
- 副本数: 1/1

请求示例:
```bash
curl -X POST 'http://deepseek-v4-flash.ksai.scnet.cn:58000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "DeepSeek-V4-Flash",
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.7,
    "stream": false
  }'
```
OpenAI Responses 示例:
```bash
curl -X POST 'http://deepseek-v4-flash.ksai.scnet.cn:58000/v1/responses' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "DeepSeek-V4-Flash",
    "input": "你好，请用一句话介绍你自己",
    "max_output_tokens": 128
  }'
```
OpenAI Responses 多轮示例:
```bash
curl -X POST 'http://deepseek-v4-flash.ksai.scnet.cn:58000/v1/responses' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "DeepSeek-V4-Flash",
    "previous_response_id": "<上一轮返回的 id>",
    "input": "继续展开上一轮回答",
    "max_output_tokens": 128
  }'
```
OpenAI Responses 工具调用示例:
```bash
curl -X POST 'http://deepseek-v4-flash.ksai.scnet.cn:58000/v1/responses' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "DeepSeek-V4-Flash",
    "input": "北京天气如何？如果需要就调用工具。",
    "tool_choice": "auto",
    "tools": [
      {
        "type": "function",
        "name": "get_weather",
        "description": "Get weather by city",
        "parameters": {
          "type": "object",
          "properties": {
            "city": {"type": "string"}
          },
          "required": ["city"]
        }
      }
    ],
    "max_output_tokens": 128
  }'
```

### qwen3-embedding-8b
- /v1/chat/completions ✅
- Anthropic 协议: ❌
- OpenAI Responses 协议: ❌(404)
- Responses 工具调用: 未探测
- 模型信息: /opt/model/Qwen3-Embedding-8B
- 模型最大上下文长度: 131072
- 副本数: 8/8

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

## 郑州

### minimax-m25-int8-vip
- /v1/chat/completions ✅
- Anthropic 协议: ✅
- OpenAI Responses 协议: ✅
- Responses 工具调用: ❌
- 模型信息: /models/MiniMax-M2.5-W8A8
- 模型最大上下文长度: 196608
- 副本数: 25/25

请求示例:
```bash
curl -X POST 'http://minimax-m25-int8-vip.zzai2.scnet.cn:58000/v1/chat/completions' \
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
curl -X POST 'http://minimax-m25-int8-vip.zzai2.scnet.cn:58000/v1/responses' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "/models/MiniMax-M2.5-W8A8",
    "input": "你好，请用一句话介绍你自己",
    "max_output_tokens": 128
  }'
```
OpenAI Responses 多轮示例:
```bash
curl -X POST 'http://minimax-m25-int8-vip.zzai2.scnet.cn:58000/v1/responses' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "/models/MiniMax-M2.5-W8A8",
    "previous_response_id": "<上一轮返回的 id>",
    "input": "继续展开上一轮回答",
    "max_output_tokens": 128
  }'
```

### qwen35-122b-a10
- /v1/chat/completions ✅
- Anthropic 协议: ✅
- OpenAI Responses 协议: ❌(400)
- Responses 工具调用: 未探测
- 模型信息: Qwen3.5-122B-A10B
- 模型最大上下文长度: 65536
- 副本数: 1/1

请求示例:
```bash
curl -X POST 'http://qwen35-122b-a10.zzai2.scnet.cn:58000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "Qwen3.5-122B-A10B",
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.7,
    "stream": false
  }'
```

