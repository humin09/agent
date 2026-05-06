### deepseek-32b
- http://deepseek-32b.ksai.scnet.cn:58000:/v1/models ✅
- Anthropic 协议: ❌
- OpenAI Responses 协议: ❌(404)
- Responses 多轮对话: 未探测
- Responses 工具调用: 未探测
- 模型信息: /opt/model/DeepSeek-R1-Distill-Qwen-32B
- 模型最大上下文长度: 32768
- 副本数5/5
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
- http://deepseek-7b.ksai.scnet.cn:58000:/v1/models ✅
- Anthropic 协议: ❌
- OpenAI Responses 协议: ❌(404)
- Responses 多轮对话: 未探测
- Responses 工具调用: 未探测
- 模型信息: /opt/model/DeepSeek-R1-Distill-Qwen-7B
- 模型最大上下文长度: 32768
- 副本数5/5
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
- http://deepseek-r1-0528-8b.ksai.scnet.cn:58000:/v1/models ✅
- Anthropic 协议: ❌
- OpenAI Responses 协议: ❌(404)
- Responses 多轮对话: 未探测
- Responses 工具调用: 未探测
- 模型信息: /opt/model/DeepSeek-R1-0528-Qwen3-8B
- 模型最大上下文长度: 32768
- 副本数20/20
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
- http://deepseek-r1-70b.ksai.scnet.cn:58000:/v1/models ✅
- Anthropic 协议: ❌
- OpenAI Responses 协议: ❌(404)
- Responses 多轮对话: 未探测
- Responses 工具调用: 未探测
- 模型信息: /opt/model/DeepSeek-R1-Distill-Llama-70B
- 模型最大上下文长度: 32000
- 副本数3/3
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
- http://deepseek-v4-flash.ksai.scnet.cn:58000:/v1/models ✅
- Anthropic 协议: ✅
- OpenAI Responses 协议: ✅
- Responses 多轮对话: ❌(404)
- Responses 工具调用: ✅
- 模型信息: DeepSeek-V4-Flash
- 模型最大上下文长度: 1048576
- 副本数1/1
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

### deepseek-v4-pro
- http://deepseek-v4-pro.ksai.scnet.cn:58000:/v1/models ❌
- Anthropic 协议: ❌
- OpenAI Responses 协议: 未探测
- Responses 多轮对话: ❌
- Responses 工具调用: ❌
- 模型信息: ❌
- 模型最大上下文长度: N/A
- 副本数0/0

### qwen3-30b
- http://qwen3-30b.ksai.scnet.cn:58000:/v1/models ✅
- Anthropic 协议: ❌
- OpenAI Responses 协议: ❌(404)
- Responses 多轮对话: 未探测
- Responses 工具调用: 未探测
- 模型信息: /opt/model/Qwen3-30B-A3B
- 模型最大上下文长度: 131072
- 副本数4/4
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
- http://qwen3-embedding-8b.ksai.scnet.cn:58000:/v1/models ✅
- Anthropic 协议: ❌
- OpenAI Responses 协议: ❌(404)
- Responses 多轮对话: 未探测
- Responses 工具调用: 未探测
- 模型信息: /opt/model/Qwen3-Embedding-8B
- 模型最大上下文长度: 131072
- 副本数8/8
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
- http://qwen36-35b-a3b.ksai.scnet.cn:58000:/v1/models ✅
- Anthropic 协议: ✅
- OpenAI Responses 协议: ✅
- Responses 多轮对话: ❌(404)
- Responses 工具调用: ✅
- 模型信息: Qwen3.6-35B-A3B
- 模型最大上下文长度: 262144
- 副本数1/1
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
OpenAI Responses 工具调用示例:
```bash
curl -X POST 'http://qwen36-35b-a3b.ksai.scnet.cn:58000/v1/responses' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "Qwen3.6-35B-A3B",
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

### qwen36-35b-a3b-vllm18
- http://qwen36-35b-a3b-vllm18.ksai.scnet.cn:58000:/v1/models ❌
- Anthropic 协议: ❌
- OpenAI Responses 协议: 未探测
- Responses 多轮对话: ❌
- Responses 工具调用: ❌
- 模型信息: ❌
- 模型最大上下文长度: N/A
- 副本数0/0

### qwq-32b
- http://qwq-32b.ksai.scnet.cn:58000:/v1/models ✅
- Anthropic 协议: ❌
- OpenAI Responses 协议: ❌(404)
- Responses 多轮对话: 未探测
- Responses 工具调用: 未探测
- 模型信息: /opt/model/QwQ-32B
- 模型最大上下文长度: 32768
- 副本数11/11
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

### r1-h20
- http://r1-h20.ksai.scnet.cn:58000:/v1/models ❌
- Anthropic 协议: ❌
- OpenAI Responses 协议: 未探测
- Responses 多轮对话: ❌
- Responses 工具调用: ❌
- 模型信息: ❌
- 模型最大上下文长度: N/A
- 副本数1/0

### deepseek-r1-0528
- http://deepseek-r1-0528.zzai2.scnet.cn:58000:/v1/models ✅
- Anthropic 协议: ✅
- OpenAI Responses 协议: ✅
- Responses 多轮对话: ❌(404)
- Responses 工具调用: ✅
- 模型信息: deepseek-r1-0528
- 模型最大上下文长度: 131072
- 副本数8/8
请求示例:
```bash
curl -X POST 'http://deepseek-r1-0528.zzai2.scnet.cn:58000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "deepseek-r1-0528",
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.7,
    "stream": false
  }'
```
OpenAI Responses 示例:
```bash
curl -X POST 'http://deepseek-r1-0528.zzai2.scnet.cn:58000/v1/responses' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "deepseek-r1-0528",
    "input": "你好，请用一句话介绍你自己",
    "max_output_tokens": 128
  }'
```
OpenAI Responses 工具调用示例:
```bash
curl -X POST 'http://deepseek-r1-0528.zzai2.scnet.cn:58000/v1/responses' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "deepseek-r1-0528",
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

### deepseek-v32-int8
- http://deepseek-v32-int8.zzai2.scnet.cn:58000:/v1/models ✅
- Anthropic 协议: ❌
- OpenAI Responses 协议: ❌(404)
- Responses 多轮对话: 未探测
- Responses 工具调用: 未探测
- 模型信息: deepseek-v3.2-int8
- 模型最大上下文长度: 131072
- 副本数2/2
请求示例:
```bash
curl -X POST 'http://deepseek-v32-int8.zzai2.scnet.cn:58000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "deepseek-v3.2-int8",
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.7,
    "stream": false
  }'
```

### kimi-k26
- http://kimi-k26.zzai2.scnet.cn:58000:/v1/models ✅
- Anthropic 协议: ✅
- OpenAI Responses 协议: ✅
- Responses 多轮对话: ❌(404)
- Responses 工具调用: ✅
- 模型信息: Kimi-K2.6
- 模型最大上下文长度: 262144
- 副本数1/1
请求示例:
```bash
curl -X POST 'http://kimi-k26.zzai2.scnet.cn:58000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "Kimi-K2.6",
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.7,
    "stream": false
  }'
```
OpenAI Responses 示例:
```bash
curl -X POST 'http://kimi-k26.zzai2.scnet.cn:58000/v1/responses' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "Kimi-K2.6",
    "input": "你好，请用一句话介绍你自己",
    "max_output_tokens": 128
  }'
```
OpenAI Responses 工具调用示例:
```bash
curl -X POST 'http://kimi-k26.zzai2.scnet.cn:58000/v1/responses' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "Kimi-K2.6",
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

### kimi-k26-worker-1
- /v1/models ❌
- 副本数1/1

### minimax-m25-int8
- http://minimax-m25-int8.zzai2.scnet.cn:58000:/v1/models ✅
- Anthropic 协议: ✅
- OpenAI Responses 协议: ✅
- Responses 多轮对话: ❌(404)
- Responses 工具调用: ✅
- 模型信息: /models/MiniMax-M2.5-W8A8
- 模型最大上下文长度: 196608
- 副本数15/15
请求示例:
```bash
curl -X POST 'http://minimax-m25-int8.zzai2.scnet.cn:58000/v1/chat/completions' \
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
curl -X POST 'http://minimax-m25-int8.zzai2.scnet.cn:58000/v1/responses' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "/models/MiniMax-M2.5-W8A8",
    "input": "你好，请用一句话介绍你自己",
    "max_output_tokens": 128
  }'
```
OpenAI Responses 工具调用示例:
```bash
curl -X POST 'http://minimax-m25-int8.zzai2.scnet.cn:58000/v1/responses' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "/models/MiniMax-M2.5-W8A8",
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

### minimax-m25-int8-vip
- http://minimax-m25-int8-vip.zzai2.scnet.cn:58000:/v1/models ✅
- Anthropic 协议: ✅
- OpenAI Responses 协议: ✅
- Responses 多轮对话: ❌(404)
- Responses 工具调用: ✅
- 模型信息: /models/MiniMax-M2.5-W8A8
- 模型最大上下文长度: 196608
- 副本数50/50
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
OpenAI Responses 工具调用示例:
```bash
curl -X POST 'http://minimax-m25-int8-vip.zzai2.scnet.cn:58000/v1/responses' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "/models/MiniMax-M2.5-W8A8",
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

### minimax-m25-int8-yy
- http://minimax-m25-int8-yy.zzai2.scnet.cn:58000:/v1/models ✅
- Anthropic 协议: ✅
- OpenAI Responses 协议: ✅
- Responses 多轮对话: ❌(404)
- Responses 工具调用: ✅
- 模型信息: /models/MiniMax-M2.5-W8A8
- 模型最大上下文长度: 196608
- 副本数1/1
请求示例:
```bash
curl -X POST 'http://minimax-m25-int8-yy.zzai2.scnet.cn:58000/v1/chat/completions' \
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
curl -X POST 'http://minimax-m25-int8-yy.zzai2.scnet.cn:58000/v1/responses' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "/models/MiniMax-M2.5-W8A8",
    "input": "你好，请用一句话介绍你自己",
    "max_output_tokens": 128
  }'
```
OpenAI Responses 工具调用示例:
```bash
curl -X POST 'http://minimax-m25-int8-yy.zzai2.scnet.cn:58000/v1/responses' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "/models/MiniMax-M2.5-W8A8",
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

### minimax-m25-internal
- http://minimax-m25-internal.zzai2.scnet.cn:58000:/v1/models ❌
- Anthropic 协议: ❌
- OpenAI Responses 协议: 未探测
- Responses 多轮对话: ❌
- Responses 工具调用: ❌
- 模型信息: ❌
- 模型最大上下文长度: N/A
- 副本数0/0

### qwen3-235b-a22b
- http://qwen3-235b-a22b.zzai2.scnet.cn:58000:/v1/models ✅
- Anthropic 协议: ❌
- OpenAI Responses 协议: ❌(404)
- Responses 多轮对话: 未探测
- Responses 工具调用: 未探测
- 模型信息: /data/model/Qwen3-235B-A22B
- 模型最大上下文长度: 32768
- 副本数10/10
请求示例:
```bash
curl -X POST 'http://qwen3-235b-a22b.zzai2.scnet.cn:58000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "/data/model/Qwen3-235B-A22B",
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.7,
    "stream": false
  }'
```

### qwen3-235b-a22b-thinking-2507
- http://qwen3-235b-a22b-thinking-2507.zzai2.scnet.cn:58000:/v1/models ✅
- Anthropic 协议: ❌
- OpenAI Responses 协议: ❌(404)
- Responses 多轮对话: 未探测
- Responses 工具调用: 未探测
- 模型信息: /data/models/Qwen3-235B-A22B-Thinking-2507
- 模型最大上下文长度: 32768
- 副本数1/1
请求示例:
```bash
curl -X POST 'http://qwen3-235b-a22b-thinking-2507.zzai2.scnet.cn:58000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "/data/models/Qwen3-235B-A22B-Thinking-2507",
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.7,
    "stream": false
  }'
```

### qwen3-30b-a3b-instruct-2507
- http://qwen3-30b-a3b-instruct-2507.zzai2.scnet.cn:58000:/v1/models ✅
- Anthropic 协议: ❌
- OpenAI Responses 协议: ❌(404)
- Responses 多轮对话: 未探测
- Responses 工具调用: 未探测
- 模型信息: /data/models/Qwen3-30B-A3B-Instruct-2507
- 模型最大上下文长度: 262144
- 副本数3/3
请求示例:
```bash
curl -X POST 'http://qwen3-30b-a3b-instruct-2507.zzai2.scnet.cn:58000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "/data/models/Qwen3-30B-A3B-Instruct-2507",
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.7,
    "stream": false
  }'
```

### qwen3-coder-480b-a35b-instruct
- http://qwen3-coder-480b.zzai2.scnet.cn:58000:/v1/models ❌
- Anthropic 协议: ❌
- OpenAI Responses 协议: 未探测
- Responses 多轮对话: ❌
- Responses 工具调用: ❌
- 模型信息: ❌
- 模型最大上下文长度: N/A
- 副本数4/4

### qwen35-397b-a17b-int8
- http://qwen35-397b-a17b-int8.zzai2.scnet.cn:58000:/v1/models ✅
- Anthropic 协议: ✅
- OpenAI Responses 协议: ❌(400)
- Responses 多轮对话: 未探测
- Responses 工具调用: 未探测
- 模型信息: Qwen3.5-397B-A17B-int8
- 模型最大上下文长度: 262144
- 副本数1/1
请求示例:
```bash
curl -X POST 'http://qwen35-397b-a17b-int8.zzai2.scnet.cn:58000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "Qwen3.5-397B-A17B-int8",
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.7,
    "stream": false
  }'
```

### wan22-ti2v-5b-diffusers
- http://wan22-ti2v-5b-diffusers.zzai2.scnet.cn:58000:/v1/models ✅
- Anthropic 协议: ❌
- OpenAI Responses 协议: ❌(500)
- Responses 多轮对话: 未探测
- Responses 工具调用: 未探测
- 模型信息: /data/models/Wan2.2-TI2V-5B-Diffusers
- 模型最大上下文长度: None
- 副本数1/1
请求示例:
```bash
curl -X POST 'http://wan22-ti2v-5b-diffusers.zzai2.scnet.cn:58000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "/data/models/Wan2.2-TI2V-5B-Diffusers",
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.7,
    "stream": false
  }'
```

### z-image-turbo
- http://z-image-turbo.zzai2.scnet.cn:58000:/v1/models ✅
- Anthropic 协议: ❌
- OpenAI Responses 协议: ❌(500)
- Responses 多轮对话: 未探测
- Responses 工具调用: 未探测
- 模型信息: /data/models/Z-Image-Turbo
- 模型最大上下文长度: None
- 副本数1/1
请求示例:
```bash
curl -X POST 'http://z-image-turbo.zzai2.scnet.cn:58000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "/data/models/Z-Image-Turbo",
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.7,
    "stream": false
  }'
```

