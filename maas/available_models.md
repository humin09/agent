deepseek-32b
- http://deepseek-32b.ksai.scnet.cn:58000:/v1/models ✅
- Anthropic 协议: ❌
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

deepseek-7b
- http://deepseek-7b.ksai.scnet.cn:58000:/v1/models ✅
- Anthropic 协议: ❌
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

deepseek-r1-0528-8b
- http://deepseek-r1-0528-8b.ksai.scnet.cn:58000:/v1/models ✅
- Anthropic 协议: ❌
- 模型信息: /opt/model/DeepSeek-R1-0528-Qwen3-8B
- 模型最大上下文长度: 32768
- 副本数30/30
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

deepseek-r1-70b
- http://deepseek-r1-70b.ksai.scnet.cn:58000:/v1/models ✅
- Anthropic 协议: ❌
- 模型信息: /opt/model/DeepSeek-R1-Distill-Llama-70B
- 模型最大上下文长度: 32000
- 副本数3/2
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

deepseek-v4-pro
- http://deepseek-v4-pro.ksai.scnet.cn:58000:/v1/models ✅
- Anthropic 协议: ❌
- 模型信息: deepseek-v4-pro
- 模型最大上下文长度: 1000000
- 副本数1/1
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

qwen3-30b
- http://qwen3-30b.ksai.scnet.cn:58000:/v1/models ✅
- Anthropic 协议: ❌
- 模型信息: /opt/model/Qwen3-30B-A3B
- 模型最大上下文长度: 131072
- 副本数5/3
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

qwen3-embedding-8b
- http://qwen3-embedding-8b.ksai.scnet.cn:58000:/v1/models ✅
- Anthropic 协议: ❌
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

qwq-32b
- http://qwq-32b.ksai.scnet.cn:58000:/v1/models ✅
- Anthropic 协议: ❌
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

r1-h20
- http://r1-h20.ksai.scnet.cn:58000:/v1/models ❌
- Anthropic 协议: ❌
- 模型信息: ❌
- 模型最大上下文长度: N/A
- 副本数1/0

deepseek-r1-0528
- http://deepseek-r1-0528.zzai2.scnet.cn:58000:/v1/models ✅
- Anthropic 协议: ❌
- 模型信息: /data/models/DeepSeek-R1-0528-BF16
- 模型最大上下文长度: 131072
- 副本数8/8
请求示例:
```bash
curl -X POST 'http://deepseek-r1-0528.zzai2.scnet.cn:58000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "/data/models/DeepSeek-R1-0528-BF16",
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.7,
    "stream": false
  }'
```

deepseek-v32-int8
- http://deepseek-v32-int8.zzai2.scnet.cn:58000:/v1/models ❌
- Anthropic 协议: ❌
- 模型信息: ❌
- 模型最大上下文长度: N/A
- 副本数2/2

minimax-m25-int8
- http://minimax-m25-int8.zzai2.scnet.cn:58000:/v1/models ✅
- Anthropic 协议: ✅
- 模型信息: /models/MiniMax-M2.5-W8A8
- 模型最大上下文长度: 196608
- 副本数30/30
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

minimax-m25-int8-vip
- http://minimax-m25-int8-vip.zzai2.scnet.cn:58000:/v1/models ✅
- Anthropic 协议: ✅
- 模型信息: /models/MiniMax-M2.5-W8A8
- 模型最大上下文长度: 196608
- 副本数100/99
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

minimax-m25-int8-yy
- http://minimax-m25-int8-yy.zzai2.scnet.cn:58000:/v1/models ✅
- Anthropic 协议: ✅
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

minimax-m25-internal
- http://minimax-m25-internal.zzai2.scnet.cn:58000:/v1/models ✅
- Anthropic 协议: ✅
- 模型信息: /models/MiniMax-M2.5-W8A8
- 模型最大上下文长度: 196608
- 副本数4/2
请求示例:
```bash
curl -X POST 'http://minimax-m25-internal.zzai2.scnet.cn:58000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "/models/MiniMax-M2.5-W8A8",
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.7,
    "stream": false
  }'
```

minimax-m27-bf16-test
- http://minimax-m27-bf16-test.zzai2.scnet.cn:58000:/v1/models ✅
- Anthropic 协议: ✅
- 模型信息: /models/MiniMax-M2.7-bf16
- 模型最大上下文长度: 153600
- 副本数1/1
请求示例:
```bash
curl -X POST 'http://minimax-m27-bf16-test.zzai2.scnet.cn:58000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "/models/MiniMax-M2.7-bf16",
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.7,
    "stream": false
  }'
```

qwen3-235b-a22b
- http://qwen3-235b-a22b.zzai2.scnet.cn:58000:/v1/models ✅
- Anthropic 协议: ❌
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

qwen3-235b-a22b-thinking-2507
- http://qwen3-235b-a22b-thinking-2507.zzai2.scnet.cn:58000:/v1/models ✅
- Anthropic 协议: ❌
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

qwen3-30b-a3b-instruct-2507
- http://qwen3-30b-a3b-instruct-2507.zzai2.scnet.cn:58000:/v1/models ✅
- Anthropic 协议: ❌
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

qwen3-coder-480b-a35b-instruct
- http://qwen3-coder-480b.zzai2.scnet.cn:58000:/v1/models ❌
- Anthropic 协议: ❌
- 模型信息: ❌
- 模型最大上下文长度: N/A
- 副本数4/4

qwen36
- http://qwen36.zzai2.scnet.cn:58000:/v1/models ✅
- Anthropic 协议: ✅
- 模型信息: /public/ai_data/models/Qwen3.6-35B-A3B
- 模型最大上下文长度: 262144
- 副本数1/1
请求示例:
```bash
curl -X POST 'http://qwen36.zzai2.scnet.cn:58000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "/public/ai_data/models/Qwen3.6-35B-A3B",
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.7,
    "stream": false
  }'
```

qwen36-vllm18
- http://qwen36-vllm18.zzai2.scnet.cn:58000:/v1/models ✅
- Anthropic 协议: ✅
- 模型信息: /public/ai_data/models/Qwen3.6-35B-A3B
- 模型最大上下文长度: 262144
- 副本数1/1
请求示例:
```bash
curl -X POST 'http://qwen36-vllm18.zzai2.scnet.cn:58000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "/public/ai_data/models/Qwen3.6-35B-A3B",
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.7,
    "stream": false
  }'
```

wan22-ti2v-5b-diffusers
- http://wan22-ti2v-5b-diffusers.zzai2.scnet.cn:58000:/v1/models ✅
- Anthropic 协议: ❌
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

z-image-turbo
- http://z-image-turbo.zzai2.scnet.cn:58000:/v1/models ✅
- Anthropic 协议: ❌
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

