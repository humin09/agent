# ske-model 可用模型列表
生成时间: 2026-04-22 17:27:23

## 昆山 集群

### deepseek-r1
- 副本数: 1/0
- 访问地址: `http://r1-h20.ksai.scnet.cn:58000`
- 模型信息: ❌ 无法访问 (HTTP Connection failed)

### deepseek-r1-distill-llama-70b
- 副本数: 3/3
- 访问地址: `http://deepseek-70b.ksai.scnet.cn:58000`
- 模型信息:
  - `/opt/model/DeepSeek-R1-Distill-Llama-70B`
    - 最大上下文长度: 32000
- Anthropic 协议: ❌ 不支持或探测失败 (HTTP Connection failed)

#### 验证过的 curl 命令:
**获取模型列表:**
```bash
curl -s http://deepseek-70b.ksai.scnet.cn:58000/v1/models
```

**Chat Completions 测试:**
```bash
curl -X POST 'http://deepseek-70b.ksai.scnet.cn:58000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "/opt/model/DeepSeek-R1-Distill-Llama-70B",
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.7,
    "stream": false
  }'
```

### deepseek-r1-distill-qwen-32b
- 副本数: 5/5
- 访问地址: `http://z100-32b.ksai.scnet.cn:58000`
- 模型信息:
  - `/opt/model/DeepSeek-R1-Distill-Qwen-32B`
    - 最大上下文长度: 32768
- Anthropic 协议: ❌ 不支持或探测失败 (HTTP Connection failed)

#### 验证过的 curl 命令:
**获取模型列表:**
```bash
curl -s http://z100-32b.ksai.scnet.cn:58000/v1/models
```

**Chat Completions 测试:**
```bash
curl -X POST 'http://z100-32b.ksai.scnet.cn:58000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "/opt/model/DeepSeek-R1-Distill-Qwen-32B",
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.7,
    "stream": false
  }'
```

### deepseek-r1-distill-qwen-7b
- 副本数: 5/5
- 访问地址: `http://deepseek-7b.ksai.scnet.cn:58000`
- 模型信息:
  - `/opt/model/DeepSeek-R1-Distill-Qwen-7B`
    - 最大上下文长度: 32768
- Anthropic 协议: ❌ 不支持或探测失败 (HTTP Connection failed)

#### 验证过的 curl 命令:
**获取模型列表:**
```bash
curl -s http://deepseek-7b.ksai.scnet.cn:58000/v1/models
```

**Chat Completions 测试:**
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

### deepseek-r1-distill-qwen3-8b
- 副本数: 30/30
- 访问地址: `http://deepseek-r1-0528-8b.ksai.scnet.cn:58000`
- 模型信息:
  - `/opt/model/DeepSeek-R1-0528-Qwen3-8B`
    - 最大上下文长度: 32768
- Anthropic 协议: ❌ 不支持或探测失败 (HTTP Connection failed)

#### 验证过的 curl 命令:
**获取模型列表:**
```bash
curl -s http://deepseek-r1-0528-8b.ksai.scnet.cn:58000/v1/models
```

**Chat Completions 测试:**
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

### qwen3-30b-a3b
- 副本数: 5/4
- 访问地址: `http://qwen3-30b-k100.ksai.scnet.cn:58000`
- 模型信息:
  - `/opt/model/Qwen3-30B-A3B`
    - 最大上下文长度: 131072
- Anthropic 协议: ❌ 不支持或探测失败 (HTTP Connection failed)

#### 验证过的 curl 命令:
**获取模型列表:**
```bash
curl -s http://qwen3-30b-k100.ksai.scnet.cn:58000/v1/models
```

**Chat Completions 测试:**
```bash
curl -X POST 'http://qwen3-30b-k100.ksai.scnet.cn:58000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "/opt/model/Qwen3-30B-A3B",
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.7,
    "stream": false
  }'
```

### qwen3-embedding-8b
- 副本数: 8/8
- 访问地址: `http://qwen3-embedding-8b.ksai.scnet.cn:58000`
- 模型信息:
  - `/opt/model/Qwen3-Embedding-8B`
    - 最大上下文长度: 131072
- Anthropic 协议: ❌ 不支持或探测失败 (HTTP Connection failed)

#### 验证过的 curl 命令:
**获取模型列表:**
```bash
curl -s http://qwen3-embedding-8b.ksai.scnet.cn:58000/v1/models
```

**Chat Completions 测试:**
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

### qwq-32b
- 副本数: 11/11
- 访问地址: `http://qwq-32b.ksai.scnet.cn:58000`
- 模型信息:
  - `/opt/model/QwQ-32B`
    - 最大上下文长度: 32768
- Anthropic 协议: ❌ 不支持或探测失败 (HTTP Connection failed)

#### 验证过的 curl 命令:
**获取模型列表:**
```bash
curl -s http://qwq-32b.ksai.scnet.cn:58000/v1/models
```

**Chat Completions 测试:**
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

## 郑州 集群

### deepseek-r1-0528-1
- 副本数: 7/7
- 模型信息: ❌ 无对应 ingress

### deepseek-r1-0528-head-1
- 副本数: 1/1
- 模型信息: ❌ 无对应 ingress

### deepseek-v32-int8-1
- 副本数: 0/0
- 模型信息: ❌ 无对应 ingress

### deepseek-v32-int8-head-1
- 副本数: 0/0
- 模型信息: ❌ 无对应 ingress

### minimax-m25-int8
- 副本数: 40/40
- 访问地址: `http://minimax-m25-int8.zzai2.scnet.cn:58000`
- 模型信息:
  - `/models/MiniMax-M2.5-W8A8`
    - 最大上下文长度: 196608
- Anthropic 协议: ✅ 支持 (/v1/messages)

#### 验证过的 curl 命令:
**获取模型列表:**
```bash
curl -s http://minimax-m25-int8.zzai2.scnet.cn:58000/v1/models
```

**Chat Completions 测试:**
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

**Anthropic Messages 测试:**
```bash
curl -X POST 'http://minimax-m25-int8.zzai2.scnet.cn:58000/v1/messages' \
  -H 'Content-Type: application/json' \
  -H 'anthropic-version: 2023-06-01' \
  -d '{
    "model": "/models/MiniMax-M2.5-W8A8",
    "max_tokens": 16,
    "messages": [{"role": "user", "content": "你好"}],
    "stream": false
  }'
```

### minimax-m25-int8-test
- 副本数: 1/1
- 访问地址: `http://minimax-m25-int8-test.zzai2.scnet.cn:58000`
- 模型信息:
  - `/models/MiniMax-M2.5-W8A8`
    - 最大上下文长度: 196608
- Anthropic 协议: ✅ 支持 (/v1/messages)

#### 验证过的 curl 命令:
**获取模型列表:**
```bash
curl -s http://minimax-m25-int8-test.zzai2.scnet.cn:58000/v1/models
```

**Chat Completions 测试:**
```bash
curl -X POST 'http://minimax-m25-int8-test.zzai2.scnet.cn:58000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "/models/MiniMax-M2.5-W8A8",
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.7,
    "stream": false
  }'
```

**Anthropic Messages 测试:**
```bash
curl -X POST 'http://minimax-m25-int8-test.zzai2.scnet.cn:58000/v1/messages' \
  -H 'Content-Type: application/json' \
  -H 'anthropic-version: 2023-06-01' \
  -d '{
    "model": "/models/MiniMax-M2.5-W8A8",
    "max_tokens": 16,
    "messages": [{"role": "user", "content": "你好"}],
    "stream": false
  }'
```

### minimax-m25-int8-vip
- 副本数: 100/100
- 访问地址: `http://minimax-m25-int8-vip.zzai2.scnet.cn:58000`
- 模型信息:
  - `/models/MiniMax-M2.5-W8A8`
    - 最大上下文长度: 196608
- Anthropic 协议: ✅ 支持 (/v1/messages)

#### 验证过的 curl 命令:
**获取模型列表:**
```bash
curl -s http://minimax-m25-int8-vip.zzai2.scnet.cn:58000/v1/models
```

**Chat Completions 测试:**
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

**Anthropic Messages 测试:**
```bash
curl -X POST 'http://minimax-m25-int8-vip.zzai2.scnet.cn:58000/v1/messages' \
  -H 'Content-Type: application/json' \
  -H 'anthropic-version: 2023-06-01' \
  -d '{
    "model": "/models/MiniMax-M2.5-W8A8",
    "max_tokens": 16,
    "messages": [{"role": "user", "content": "你好"}],
    "stream": false
  }'
```

### minimax-m25-int8-vllm18
- 副本数: 1/0
- 访问地址: `http://minimax-m25-int8-vllm18.zzai2.scnet.cn:58000`
- 模型信息: ❌ 无法访问 (HTTP Connection failed)

### minimax-m25-int8-vllm8
- 副本数: 1/0
- 模型信息: ❌ 无对应 ingress

### minimax-m25-int8-yy
- 副本数: 1/1
- 访问地址: `http://minimax-m25-int8-yy.zzai2.scnet.cn:58000`
- 模型信息:
  - `/models/MiniMax-M2.5-W8A8`
    - 最大上下文长度: 196608
- Anthropic 协议: ✅ 支持 (/v1/messages)

#### 验证过的 curl 命令:
**获取模型列表:**
```bash
curl -s http://minimax-m25-int8-yy.zzai2.scnet.cn:58000/v1/models
```

**Chat Completions 测试:**
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

**Anthropic Messages 测试:**
```bash
curl -X POST 'http://minimax-m25-int8-yy.zzai2.scnet.cn:58000/v1/messages' \
  -H 'Content-Type: application/json' \
  -H 'anthropic-version: 2023-06-01' \
  -d '{
    "model": "/models/MiniMax-M2.5-W8A8",
    "max_tokens": 16,
    "messages": [{"role": "user", "content": "你好"}],
    "stream": false
  }'
```

### minimax-m25-internal
- 副本数: 4/4
- 访问地址: `http://minimax-m25-internal.zzai2.scnet.cn:58000`
- 模型信息:
  - `/models/MiniMax-M2.5-W8A8`
    - 最大上下文长度: 196608
- Anthropic 协议: ✅ 支持 (/v1/messages)

#### 验证过的 curl 命令:
**获取模型列表:**
```bash
curl -s http://minimax-m25-internal.zzai2.scnet.cn:58000/v1/models
```

**Chat Completions 测试:**
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

**Anthropic Messages 测试:**
```bash
curl -X POST 'http://minimax-m25-internal.zzai2.scnet.cn:58000/v1/messages' \
  -H 'Content-Type: application/json' \
  -H 'anthropic-version: 2023-06-01' \
  -d '{
    "model": "/models/MiniMax-M2.5-W8A8",
    "max_tokens": 16,
    "messages": [{"role": "user", "content": "你好"}],
    "stream": false
  }'
```

### minimax-m25-test1
- 副本数: 1/1
- 访问地址: `http://minimax-m25-test1.zzai2.scnet.cn:58000`
- 模型信息:
  - `/models/MiniMax-M2.5-W8A8`
    - 最大上下文长度: 196608
- Anthropic 协议: ✅ 支持 (/v1/messages)

#### 验证过的 curl 命令:
**获取模型列表:**
```bash
curl -s http://minimax-m25-test1.zzai2.scnet.cn:58000/v1/models
```

**Chat Completions 测试:**
```bash
curl -X POST 'http://minimax-m25-test1.zzai2.scnet.cn:58000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "/models/MiniMax-M2.5-W8A8",
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.7,
    "stream": false
  }'
```

**Anthropic Messages 测试:**
```bash
curl -X POST 'http://minimax-m25-test1.zzai2.scnet.cn:58000/v1/messages' \
  -H 'Content-Type: application/json' \
  -H 'anthropic-version: 2023-06-01' \
  -d '{
    "model": "/models/MiniMax-M2.5-W8A8",
    "max_tokens": 16,
    "messages": [{"role": "user", "content": "你好"}],
    "stream": false
  }'
```

### minimax-m25-test2
- 副本数: 1/1
- 访问地址: `http://minimax-m25-test2.zzai2.scnet.cn:58000`
- 模型信息:
  - `/models/MiniMax-M2.5-W8A8`
    - 最大上下文长度: 196608
- Anthropic 协议: ✅ 支持 (/v1/messages)

#### 验证过的 curl 命令:
**获取模型列表:**
```bash
curl -s http://minimax-m25-test2.zzai2.scnet.cn:58000/v1/models
```

**Chat Completions 测试:**
```bash
curl -X POST 'http://minimax-m25-test2.zzai2.scnet.cn:58000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "/models/MiniMax-M2.5-W8A8",
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.7,
    "stream": false
  }'
```

**Anthropic Messages 测试:**
```bash
curl -X POST 'http://minimax-m25-test2.zzai2.scnet.cn:58000/v1/messages' \
  -H 'Content-Type: application/json' \
  -H 'anthropic-version: 2023-06-01' \
  -d '{
    "model": "/models/MiniMax-M2.5-W8A8",
    "max_tokens": 16,
    "messages": [{"role": "user", "content": "你好"}],
    "stream": false
  }'
```

### minimax-m27-bf16-test
- 副本数: 1/1
- 访问地址: `http://minimax-m27-bf16-test.zzai2.scnet.cn:58000`
- 模型信息:
  - `/models/MiniMax-M2.7-bf16`
    - 最大上下文长度: 153600
- Anthropic 协议: ✅ 支持 (/v1/messages)

#### 验证过的 curl 命令:
**获取模型列表:**
```bash
curl -s http://minimax-m27-bf16-test.zzai2.scnet.cn:58000/v1/models
```

**Chat Completions 测试:**
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

**Anthropic Messages 测试:**
```bash
curl -X POST 'http://minimax-m27-bf16-test.zzai2.scnet.cn:58000/v1/messages' \
  -H 'Content-Type: application/json' \
  -H 'anthropic-version: 2023-06-01' \
  -d '{
    "model": "/models/MiniMax-M2.7-bf16",
    "max_tokens": 16,
    "messages": [{"role": "user", "content": "你好"}],
    "stream": false
  }'
```

### minimax-m27-bf16-vllm18
- 副本数: 1/0
- 访问地址: `http://minimax-m27-bf16-vllm18.zzai2.scnet.cn:58000`
- 模型信息: ❌ 无法访问 (HTTP Connection failed)

### qwen3-235b-a22b
- 副本数: 10/10
- 访问地址: `http://qwen3-235b-a22b.zzai2.scnet.cn:58000`
- 模型信息:
  - `/data/model/Qwen3-235B-A22B`
    - 最大上下文长度: 32768
- Anthropic 协议: ❌ 不支持或探测失败 (HTTP Connection failed)

#### 验证过的 curl 命令:
**获取模型列表:**
```bash
curl -s http://qwen3-235b-a22b.zzai2.scnet.cn:58000/v1/models
```

**Chat Completions 测试:**
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

### qwen3-235b-a22b-test
- 副本数: 1/1
- 访问地址: `http://qwen3-235b-a22b-test.zzai2.scnet.cn:58000`
- 模型信息:
  - `/data/model/Qwen3-235B-A22B`
    - 最大上下文长度: 32768
- Anthropic 协议: ✅ 支持 (/v1/messages)

#### 验证过的 curl 命令:
**获取模型列表:**
```bash
curl -s http://qwen3-235b-a22b-test.zzai2.scnet.cn:58000/v1/models
```

**Chat Completions 测试:**
```bash
curl -X POST 'http://qwen3-235b-a22b-test.zzai2.scnet.cn:58000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "/data/model/Qwen3-235B-A22B",
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.7,
    "stream": false
  }'
```

**Anthropic Messages 测试:**
```bash
curl -X POST 'http://qwen3-235b-a22b-test.zzai2.scnet.cn:58000/v1/messages' \
  -H 'Content-Type: application/json' \
  -H 'anthropic-version: 2023-06-01' \
  -d '{
    "model": "/data/model/Qwen3-235B-A22B",
    "max_tokens": 16,
    "messages": [{"role": "user", "content": "你好"}],
    "stream": false
  }'
```

### qwen3-235b-a22b-thinking-2507
- 副本数: 1/1
- 访问地址: `http://qwen3-235b-a22b-thinking-2507.zzai2.scnet.cn:58000`
- 模型信息:
  - `/data/models/Qwen3-235B-A22B-Thinking-2507`
    - 最大上下文长度: 32768
- Anthropic 协议: ❌ 不支持或探测失败 (HTTP Connection failed)

#### 验证过的 curl 命令:
**获取模型列表:**
```bash
curl -s http://qwen3-235b-a22b-thinking-2507.zzai2.scnet.cn:58000/v1/models
```

**Chat Completions 测试:**
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
- 副本数: 3/3
- 访问地址: `http://qwen3-30b-a3b-instruct-2507.zzai2.scnet.cn:58000`
- 模型信息:
  - `/data/models/Qwen3-30B-A3B-Instruct-2507`
    - 最大上下文长度: 262144
- Anthropic 协议: ❌ 不支持或探测失败 (HTTP Connection failed)

#### 验证过的 curl 命令:
**获取模型列表:**
```bash
curl -s http://qwen3-30b-a3b-instruct-2507.zzai2.scnet.cn:58000/v1/models
```

**Chat Completions 测试:**
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

### qwen3-coder-480b-a35b-instruct-head-1
- 副本数: 1/1
- 模型信息: ❌ 无对应 ingress

### qwen36
- 副本数: 1/1
- 访问地址: `http://qwen36.zzai2.scnet.cn:58000`
- 模型信息:
  - `/public/ai_data/models/Qwen3.6-35B-A3B`
    - 最大上下文长度: 262144
- Anthropic 协议: ❌ 不支持或探测失败 (HTTP Connection failed)

#### 验证过的 curl 命令:
**获取模型列表:**
```bash
curl -s http://qwen36.zzai2.scnet.cn:58000/v1/models
```

**Chat Completions 测试:**
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

### qwen36-vllm18
- 副本数: 1/1
- 访问地址: `http://qwen36-vllm18.zzai2.scnet.cn:58000`
- 模型信息:
  - `/public/ai_data/models/Qwen3.6-35B-A3B`
    - 最大上下文长度: 262144
- Anthropic 协议: ✅ 支持 (/v1/messages)

#### 验证过的 curl 命令:
**获取模型列表:**
```bash
curl -s http://qwen36-vllm18.zzai2.scnet.cn:58000/v1/models
```

**Chat Completions 测试:**
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

**Anthropic Messages 测试:**
```bash
curl -X POST 'http://qwen36-vllm18.zzai2.scnet.cn:58000/v1/messages' \
  -H 'Content-Type: application/json' \
  -H 'anthropic-version: 2023-06-01' \
  -d '{
    "model": "/public/ai_data/models/Qwen3.6-35B-A3B",
    "max_tokens": 16,
    "messages": [{"role": "user", "content": "你好"}],
    "stream": false
  }'
```

### wan22-ti2v-5b-diffusers
- 副本数: 1/0
- 访问地址: `http://wan22-ti2v-5b-diffusers.zzai2.scnet.cn:58000`
- 模型信息: ❌ 无法访问 (HTTP Connection failed)

### z-image-turbo
- 副本数: 1/0
- 访问地址: `http://z-image-turbo.zzai2.scnet.cn:58000`
- 模型信息: ❌ 无法访问 (HTTP Connection failed)

