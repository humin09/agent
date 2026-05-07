---
name: maas
description: "Maas(model as a service) 模型服务部署"
targets: ["*"]
---

# Maas 模型 URL 生成与探测

本 Skill 用于ske-model在昆山和郑州的部署的维护
1. 如果有ske-model的服务变更(replica数量调整除外), 你会把昆山和郑州的deployment和ingress的yaml同步到~/sugon/ske-chart/ske-model/ks和~/sugon/ske-chart/ske-model/zz
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
- `/Users/humin/.config/opencode/skills/maas/available_models.md` - 模型探测报告

### maas_test.py
Maas vLLM 单 Pod 压测主脚本，当前公共压测逻辑也已整合到这个文件中。
- Pod 和指标命名空间固定为 `ske-model`
- 会先确认目标 Pod 就绪，再通过 `kubectl port-forward pod/<pod>` 将流量只打到单个 Pod
- 默认输出长度为 `256 tokens`
- 支持显式指定：
  1. `--context`: 集群别名，默认 `zz`
  2. `--pod`: 目标 Pod
  3. `--token-lengths`: 输入长度列表
  4. `--cache-rates`: 缓存命中率列表
  5. `--concurrency` / `--total-requests`: 每组压测并发和总请求数
  6. `--benchmark-mode`: `fixed` 或 `sustained`
  7. `--duration-seconds` / `--report-interval-seconds`: sustained 模式参数
  8. `--local-port`: 本地 port-forward 端口，不传则自动选取
  9. `--thanos-query`: 自定义 PromQL 查询
- 结果按 JSON 格式统一保存到 `/tmp/maas-benchmark-result.log`
- 从 Thanos 收集 DCU 相关指标，结果按 JSON 格式统一保存到 `/tmp/maas-benchmark-result.log`

**使用方法：**
```bash
uv run /Users/humin/agent/maas/maas_test.py --help
# 单 Pod 测试
uv run /Users/humin/agent/maas/maas_test.py \
  --context zz \
  --pod minimax-m25-int8-vip-548776f468-2dzw5 \
  --token-lengths 20000 80000 \
  --cache-rates 0.0 0.8
```

### maas_tune.py
Maas vLLM 启动参数调优脚本，负责修改 deployment 启动参数并对每个配置做矩阵压测。
- 当前默认调优参数为 `--max-num-batched-tokens`
- 会 patch deployment，等待 rollout 完成，再调用与 `maas_test.py` 相同的压测与 Thanos 采集逻辑
- 支持 `--restore-on-exit` 在测试结束后恢复原始参数

**使用方法：**
```bash
uv run /Users/humin/agent/maas/maas_tune.py --help
uv run /Users/humin/agent/maas/maas_tune.py \
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

## ModelScope 模型下载 Pod

用于在 K8s 集群中并发下载 HuggingFace/ModelScope 模型到本地存储。

### 使用场景
- 需要在集群节点中下载大型 LLM 模型（支持 24 并发下载）
- 模型存储到节点本地存储（`/work2/ai_data/models/`）
- 支持代理访问外网（自动配置集群特定的代理认证）

### 部署方法

**基础模板**：`~/agent/maas/modelscope-download-pod.yaml`

**快速部署**（郑州集群）：
```bash
kubectl --context zz apply -f ~/agent/maas/modelscope-download-pod.yaml
```

**查看下载进度**：
```bash
kubectl --context zz -n default logs modelscope-download -f
```

**查看 Pod 状态**：
```bash
kubectl --context zz -n default get pod modelscope-download -o wide
```

### 配置说明

| 参数 | 说明 |
|------|------|
| `--model` | ModelScope 模型 ID（e.g., `XiaomiMiMo/MiMo-V2.5`） |
| `--cache_dir` | 本地存储路径（Pod 内挂载为 `/models`） |
| `--max-workers` | 并发下载线程数（默认 24） |
| `groupId: "127"` | 资源组选择器（可按需修改） |
| `http_proxy` | 代理地址（自动配置集群特定认证） |

### 修改模型和并发数

编辑 YAML 中的以下字段：
```yaml
# 修改下载模型
modelscope download --model <YOUR_MODEL_ID> --cache_dir /models --max-workers <WORKERS>
```

### 支持的代理配置（按集群）

| 集群 | 代理地址 |
|------|----------|
| `zz` (郑州) | `http://jsyadmin:1cdf8f60@10.13.17.166:3128` |
| `ks` (昆山) | `http://haowj:6c72c7e5@10.15.100.43:3120` |
| `qd` (青岛) | `http://aca1kgxhox:74409cf0@10.1.4.13:3120` |
| `dz` (达州) | `http://jsyadmin:4e2974de@10.1.100.10:3120` |


