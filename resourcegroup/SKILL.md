---
name: k8s-resourcegroup
description: "K8s ResourceGroup 子专题：资源组识别、节点映射、容量定位与节点迁移（通过 patch CR 的 spec.nodeNames 操作）"
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

## 3) CR 关键字段速查

| 字段路径 | 说明 |
|---|---|
| `spec.nodeNames` | 节点名列表，增删节点的核心字段 |
| `spec.labels` | 写入节点 label 的模板（含 `groupId`、`resourceGroup`、`serviceType`） |
| `spec.namespaces` | 空数组=共享资源组；非空=仅这些 namespace 可用 |
| `spec.hard` | 每卡 CPU/内存配额上限 |
| `status.nodeInfo.cardType` | 卡类型：`dcu` / `gpu`，无则为 `cpu` |
| `status.nodes` | 各节点容量、已用、状态、入组时间 |
| `status.freeCards` / `totalCards` | 资源组空闲/总量卡数 |

## 4) 节点迁移（重要）

**原则：通过 patch `ResourceGroup` CR 的 `spec.nodeNames` 来变更节点归属，禁止直接修改节点 label/annotation。**

`resource-operator` 会持续监听 CR 变更，并自动将 `spec.labels` 同步到节点的 label 和 `volcano.sh/resource-group` annotation 上。直接打 label 会被 operator 回滚。

### 迁移步骤

假设要将节点从资源组 A 迁到资源组 B：

**4.1** 先查当前两个资源组的 `spec.nodeNames`：
```bash
kubectl --context=<别名> -n kube-system get resourcegroup <RG_B> -o jsonpath='{.spec.nodeNames}'
kubectl --context=<别名> -n kube-system get resourcegroup <RG_A> -o jsonpath='{.spec.nodeNames}'
```

**4.2** patch 目标资源组 B，追加节点名：
```bash
kubectl --context=<别名> -n kube-system patch resourcegroup <RG_B> \
  --type=merge -p '{"spec":{"nodeNames":["...原列表...","<新节点IP>"]}}'
```

**4.3** patch 原资源组 A，移除节点名：
```bash
kubectl --context=<别名> -n kube-system patch resourcegroup <RG_A> \
  --type=merge -p '{"spec":{"nodeNames":["...移除目标节点后的列表..."]}}'
```

**4.4** 等待 5~10 秒，验证节点 label 已同步：
```bash
sleep 5 && kubectl --context=<别名> get node <IP> -o jsonpath='groupId={.metadata.labels.groupId} resourceGroup={.metadata.labels.resourceGroup} volcano={.metadata.annotations.volcano\.sh/resource-group}'
```

### 确认模板

按 AGENTS.md §4 格式输出：
```
准备执行变更命令：kubectl --context <ctx> -n kube-system patch resourcegroup <RG_B> ...
影响范围：
- context: <ctx>
- resource: resourcegroup/<RG_B>, resourcegroup/<RG_A>
- expected impact: <节点列表> 迁入 <RG_B>，<节点> 从 <RG_A> 迁出
- rollback: 还原两个 CR 的 spec.nodeNames 到原始值
```

## 5) 变更类命令（需确认）

以下命令属于变更操作，执行前必须按确认模板输出并等待主人确认（`<namespace>` 固定为 `kube-system`）：
```bash
kubectl --context=<别名> -n kube-system edit resourcegroup <NAME>
kubectl --context=<别名> -n kube-system apply -f <resourcegroup.yaml>
kubectl --context=<别名> -n kube-system patch resourcegroup <NAME> --type merge -p '<json>'
```
