---
name: maas
description: "Maas(model as a service) 模型服务部署"
targets: ["*"]
---

# Maas 模型 URL 生成与探测

本 Skill 用于ske-model在昆山和郑州的部署的维护
1. 如果有ske-model的服务变更(replica数量调整除外), 你会把昆山和郑州的deployment和ingress的yaml同步到~/Users/humin/sugon/ske-chart/ske-model/ks和~/Users/humin/sugon/ske-chart/ske-model/zz
2. 如果有ske-model的服务变更,你会重新生成服务的可探测url, url生成规则见下面章节.
3. 如果用户说检查服务, 你会查看各个deployment是否都达到预期的副本数, 以及基于可探测url校验服务是否可用.
4. 如果用户说更新可用模型列表, 你会运行 probe_models.py 脚本来生成 available_models.md 报告.

## 工具脚本

### probe_models.py
用于自动探测 ske-model 命名空间下的可用模型并生成 markdown 报告。

**使用方法：**
```bash
uv run /Users/humin/.config/opencode/skills/maas/probe_models.py
```

**功能：**
- 自动发现昆山(ks)和郑州(zz)集群的 ske-model 命名空间下的 deployment
- 通过 ingress -> service -> deployment 的匹配关系找到正确的访问 host
- 从本地通过 ingress 访问 `/v1/models` 端点获取模型信息
- 生成包含验证过的 curl 命令的 markdown 报告

**输出文件：**
- `/Users/humin/.config/opencode/skills/maas/probe_models.md` - 模型探测报告

### bench_ttft.py
vLLM 完整压测脚本，支持：
- 不同输入长度
- 缓存命中率
- TTFT（首字延迟）和 E2E（端到端延迟）测量

### maas_test.py
Maas vLLM 自动化测试脚本，入口脚本，用于：
- 测试 3 个 `max-num-batched-tokens` × 4 个输入长度 × 3 个缓存命中率 = 36 个组合
- 会 patch 指定 deployment 的 `--max-num-batched-tokens`，等待 rollout 完成后自动进行压测
- deployment 和指标命名空间固定为 `ske-model`，不再暴露 namespace 参数
- 支持显式指定：
  1. `--context`: 集群别名，默认 `zz`
  2. `--deployment-name`: 目标 deployment
  3. `--pods` / `--pod-regex`: 显式传入测试 pod，优先用于 Thanos 指标过滤
  4. `--batched-tokens`: `max-num-batched-tokens` 值列表
  5. `--token-lengths`: 输入长度列表
  6. `--cache-rates`: 缓存命中率列表
  7. `--concurrency` / `--total-requests`: 每组压测并发和总请求数
  8. `--metrics-service`: Thanos 中 vLLM 指标的 service 标签，默认等于 deployment 名
  9. `--thanos-selector` / `--thanos-query`: 自定义 PromQL selector 或整条查询
  10. `--restore-on-exit`: 压测结束后恢复 deployment 原始参数
- 从 Thanos 收集指标，默认复用 maas Grafana 面板的 PromQL 口径：
  - `vllm:num_requests_waiting`
  - `vllm:num_requests_running`
  - `vllm:e2e_request_latency_seconds_bucket`
  - `vllm:time_to_first_token_seconds_bucket`
  - `vllm:prompt_tokens_total`
  - `vllm:generation_tokens_total`
  - `vllm:gpu_prefix_cache_hits_total / queries_total`
  - `vllm:prefix_cache_hits_total / queries_total`
  - `vllm:kv_cache_usage_perc`
- 结果按 JSON 格式统一保存到 `/tmp/maas-benchmark-result.log`

**使用方法：**
```bash
uv run /Users/humin/agent/maas/maas_test.py --help
# 默认测试
uv run /Users/humin/agent/maas/maas_test.py
# 郑州集群实际使用建议
uv run /Users/humin/agent/maas/maas_test.py \
  --context zz \
  --deployment-name minimax-m25-int8-yy \
  --pods <pod1> <pod2> \
  --metrics-service minimax-m25-int8-yy \
  --batched-tokens 4096 6144 8192 \
  --token-lengths 20000 40000 80000 120000 \
  --cache-rates 0.0 0.4 0.8 \
  --restore-on-exit
```




## url生成规则
1. 仅将 `post_status=200` 的条目视为“当前可访问”。
2. 公网 ingress URL 按集群固定拼接：
   - 郑州集群 `zz`：`http://<host>.zzai2.scnet.cn:58000<path>`
   - 昆山集群 `ks`：`http://<host>.ksai.scnet.cn:58000<path>`
3. 获取模型信息的路径为: `/v1/models`。
4. `path=/v1/chat/completions` 时使用 chat 请求体（`messages`）。
5. `path=/v1/embeddings` 时使用 embedding 请求体（`input`）。
6. `path=/v1/images/generations` 时使用 image 请求体（`prompt`）。
7. 使用的 ingress 固定为 `maas-ingress`。
8. ingress(host)通过 service selector 匹配到 deployment，并非简单的 host=deployment=svc。

## 获取模型信息的方法
从本地通过 ingress 访问：
```bash
curl -s http://<host>.zzai2.scnet.cn:58000/v1/models
curl -s http://<host>.ksai.scnet.cn:58000/v1/models
```

其中：
- `zz` 集群使用 `http://<host>.zzai2.scnet.cn:58000`
- `ks` 集群使用 `http://<host>.ksai.scnet.cn:58000`
- `<host>` 来源于 `maas-ingress` 中与目标 service/deployment 对应的 host


## 使用场景
1. 检查服务的可用性, 从本地通过 ingress 访问：
### Chat
```bash
curl -X POST 'http://<host>.<cluster-domain>:58000/v1/chat/completions' \
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
curl -X POST 'http://<host>.<cluster-domain>:58000/v1/embeddings' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "<model>",
    "input": "你好"
  }'
```

### Images
```bash
curl -X POST 'http://<host>.<cluster-domain>:58000/v1/images/generations' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "<model>",
    "prompt": "一只在月球上奔跑的橘猫"
  }'
```
2. 检查deployment的replica
3. 检查服务异常的时候, 找到对应的pod分析日志.
4. 常用性能指标以 Grafana 的 `maas` 面板为准；做压测、性能对比或异常分析时，优先参考该面板中的指标口径。

其中 `cluster-domain` 固定取值：
- 郑州 `zz`：`zzai2.scnet.cn`
- 昆山 `ks`：`ksai.scnet.cn`
 
