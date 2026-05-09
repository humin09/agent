---
name: maas
description: "Maas(model as a service) 模型服务部署"
targets: ["*"]
---

# Maas

用于 `ske-model` / `maas` 相关运维，主要覆盖：

1. 模型推理服务检查：核对 `Deployment` 副本、`Service/Ingress` 映射、探测 URL 可用性。
2. 模型列表探测：运行 `probe_models.py` 生成 `available_models.md`。
3. 单 Pod 压测：运行 `maas_test.py`。
4. `ske-model` 服务变更后，同步 `ks/zz` 的 YAML 到 chart 目录。

## 触发规则

- 用户说“检查服务”“排查 maas / ske-model 服务异常”时：
  - 检查目标 `Deployment` 是否达到预期副本数。
  - 命名契约host=service=deployment
  - 从本地探测服务可用性，必要时继续查看 Pod 日志。
- 用户说“更新可用模型列表”时，运行 `probe_models.py`。
- 用户说“压测某个模型性能”“看某个模型性能”时，运行 `maas_test.py`。
- 如果是 `ske-model` 服务变更（`replica` 数调整除外），同步 `ks` 和 `zz` 的 `Deployment/Ingress` YAML：
  - 模型推理服务同步到 `~/sugon/ske-chart/ske-model/ks` 和 `~/sugon/ske-chart/ske-model/zz`
  - 辅助服务（如 `rsync`、下载器、同步工具）同步到 `~/sugon/ske-chart/maas/`

## 快速规则

- 命名空间固定为 `ske-model`。
- 模型推理服务的公网入口固定看 `maas-ingress`。
- 命名契约host=service=deployment
- 只将 `post_status=200` 视为当前可访问。
- 模型信息探测路径固定为 `/v1/models`。
- 路径对应请求类型：
  - `/v1/chat/completions` 使用 chat 请求体
  - `/v1/embeddings` 使用 embedding 请求体
  - `/v1/images/generations` 使用 image 请求体
- 公网 URL 规则：
  - `zz`: `http://<host>.zzai2.scnet.cn:58000<path>`
  - `ks`: `http://<host>.ksai.scnet.cn:58000<path>`
- 做压测、性能对比或异常分析时，指标口径优先参考 Grafana `maas` 面板。

## 脚本入口

### `probe_models.py`

- 用途：探测 `ks/zz` 集群 `ske-model` 命名空间下的可用模型并生成报告。
- 用户说“更新可用模型列表”时使用。
- 输出：`available_models.md`

```bash
uv run /Users/humin/agent/maas/probe_models.py
```

### `maas_test.py`

- 用途：vLLM 单 Pod 压测。
- 特点：先确认 Pod 就绪，再通过 `kubectl port-forward` 只打单个 Pod。
- 详细参数直接查看 `--help`。

```bash
uv run /Users/humin/agent/maas/maas_test.py --help
```

- 常用结果文件：`/tmp/maas-benchmark-result.log`

