---
name: k8s-resourcegroup
description: "K8s ResourceGroup 子专题：资源组识别、节点映射与容量定位"
targets: ["*"]
---

你现在进入 **K8s ResourceGroup 子专题**。

ResourceGroup 是 `resource.sugon.com/v1` 的 CRD，用于描述一组同规格节点。常见字段含义：
- `NAME`: 资源组名称；节点标签 `resourceGroup=<NAME>` 可反查归属。
- `GROUPID`: 资源组 ID；节点标签 `groupId=<GROUPID>` 可反查归属。
- `NAMESPACES`: 空数组表示共享资源组；非空表示仅这些 namespace 可使用。
- `NODENAMES`: 资源组包含的节点名列表（增删节点时重点字段）。
- `CARD-TYPE`: `cpu|dcu|gpu`。
  - `dcu`: 节点可获取 `hy-smi` 输出。
  - `gpu`: 节点可获取 `nvidia-smi` 输出。
  - 两者都无输出通常视为 `cpu`。

## 1) 只读发现流程（固定 kube-system）

说明：ResourceGroup 属于系统运维资源，不面向业务用户；命名空间固定为 `kube-system`。

1. 先确认 CRD 与作用域：
```bash
kubectl --context=<别名> get crd resourcegroups.resource.sugon.com -o jsonpath='{.spec.scope}{"\n"}'
```

2. 在固定命名空间查询资源组实例：
```bash
kubectl --context=<别名> -n kube-system get resourcegroup -o wide
```

3. 查询指定资源组明细：
```bash
kubectl --context=<别名> -n kube-system get resourcegroup <NAME> -o yaml
```

4. 通过节点标签核对映射关系：
```bash
kubectl --context=<别名> get node -L resourceGroup,groupId
kubectl --context=<别名> get node -l resourceGroup=<NAME>
kubectl --context=<别名> get node -l groupId=<GROUPID>
```

## 2) 无实例时的处理（常见）

当 `kubectl --context=<别名> -n kube-system get resourcegroup` 返回空：
- 记录结论：该集群当前未创建 ResourceGroup 实例。
- 同步核对节点是否已打 `resourceGroup/groupId` 标签。
- 若标签也为空，判定“未启用 ResourceGroup 管理模式”或“尚未初始化资源组数据”。

## 3) 变更类命令（需确认）

以下命令属于变更操作，执行前必须给主人确认（`<namespace>` 固定为 `kube-system`）：
```bash
kubectl --context=<别名> -n kube-system edit resourcegroup <NAME>
kubectl --context=<别名> -n kube-system apply -f <resourcegroup.yaml>
kubectl --context=<别名> -n kube-system patch resourcegroup <NAME> --type merge -p '<json>'
```

执行前必须给出：
- 目标集群/资源组名
- 具体变更字段（如 `nodeNames`、`namespaces`）
- 影响范围与回滚方案
