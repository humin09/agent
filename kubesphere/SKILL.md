---
name: kubesphere
description: KubeSphere 4.1 多集群与 IAM 运维技能。默认流程是开户并附带 cluster 只读视图权限：用户名=workspace=各子集群 namespace，global role 固定为 platform-regular，cluster role 固定为 cluster-viewer，仅绑定指定 clusters，并在同名 namespace 下授 admin。涉及这条默认开户流程或其排障时必须使用。
---

# KubeSphere

适用范围：
- KubeSphere 默认开户流程
- 用户、workspace、同名 namespace 授权排查
- host/member cluster 名称映射查询

当前基线：
- Host cluster: `cluster-host-kunshan`
- KubeSphere: `v4.1.2`
- 默认流程遵循最小授权原则

## 关键原则

1. 用户、workspace、项目授权统一看 KubeSphere CRD，不走数据库直改。
2. 默认流程固定为：
   - `username = workspace = namespace`
   - global role = `platform-regular`
   - cluster role = `cluster-viewer`
   - workspace role = `<username>-admin`
   - namespace role = `admin`
   - 只给指定 clusters
3. 默认给 `cluster-viewer`，不默认给 `cluster-admin`。
4. 所有 KubeSphere cluster 查询，统一从 host cluster `ks` 上看 `clusters.cluster.kubesphere.io`。

## 集群映射

区分两套名字：
- `kubectl --context <alias>` 是你本地 kubeconfig 的上下文别名
- `clusters.cluster.kubesphere.io/<name>` 是 KubeSphere 内部 cluster 标识

当前已确认映射：

| 城市 | 本地 kubectl context | KubeSphere cluster name | 别名 | API Endpoint |
|------|----------------------|-------------------------|------|--------------|
| 昆山 | `ks` | `cluster-host-kunshan` | 昆山生产集群 | `https://k8s.ksai.scnet.cn:56443` |
| 达州 | `dz` | `cluster-member-dazhou` | 达州生产集群 | `https://k8s.dzai.scnet.cn:56443` |
| 青岛 | `qd` | `cluster-member-qingdao` | 青岛生产集群 | `https://qdk8sapi.scnet.cn:56443` |
| 魏桥 | `wq` | `cluster-member-weiqiao` | 魏桥生产集群 | `https://k8s.sd5ai.scnet.cn:56443` |
| 武汉 | `wh` | `cluster-member-wuhan` | 武汉生产集群 | `https://k8s.whai.scnet.cn:56443` |
| 郑州 | `zz` | `cluster-member-zhengzhou` | 郑州生产集群 | `https://k8s.zzai2.scnet.cn:56443` |
| 深圳 | `sz` | `k8s-sz` | 深圳生产集群 | `https://k8s.szai.scnet.cn:56443` |

## 常用查询

列出 KubeSphere 管理的 cluster：

```bash
kubectl --context ks get clusters.cluster.kubesphere.io -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.metadata.annotations.kubesphere\.io/alias-name}{"\t"}{.spec.connection.kubernetesAPIEndpoint}{"\n"}{end}'
```

查看某个用户的授权链路：

```bash
kubectl --context ks get user.iam.kubesphere.io <user> -o yaml
kubectl --context ks get globalrolebindings.iam.kubesphere.io,workspacerolebindings.iam.kubesphere.io,rolebindings.iam.kubesphere.io -A | rg "\b<user>\b"
kubectl --context ks get workspacetemplates.tenant.kubesphere.io,workspaces.tenant.kubesphere.io -A | rg "\b<user>\b"
```

查看某个 workspace 放到了哪些集群：

```bash
kubectl --context ks get workspacetemplate.tenant.kubesphere.io <workspace> -o yaml
```

查看某个 namespace 的 KubeSphere 项目授权：

```bash
kubectl --context ks -n <namespace> get rolebindings.iam.kubesphere.io -o yaml
kubectl --context ks -n <namespace> get role,rolebinding
```

## 账号授权模型

默认对象链路：

1. `User`
2. `GlobalRoleBinding`
3. `ClusterRoleBinding`
4. `WorkspaceTemplate`
5. `WorkspaceRoleBinding`
6. `Namespace`
7. namespace 下的 `RoleBinding.iam.kubesphere.io`

默认角色：
- `platform-regular`: 平台普通用户，适合业务用户默认入口
- `cluster-viewer`: 集群只读视图权限
- namespace `admin`: 项目/命名空间全权限

默认契约：
- 用户名 = workspace = 各子集群 namespace
- namespace 必须打上：
  - `kubesphere.io/workspace=<username>`
  - `kubesphere.io/managed=true`
- 默认加 `ClusterRoleBinding/cluster-viewer`

## 标准做法

创建或批量生成用户授权清单时，优先使用：
- `~/agent/kubesphere/scripts/kubesphere_user_bootstrap.py`

推荐模式：
- 先生成 YAML，不直接改集群
- 如果要防重复，使用 `--skip-existing --context ks`

示例：

```bash
python ~/agent/kubesphere/scripts/kubesphere_user_bootstrap.py \
  --context ks \
  --skip-existing \
  --username demo-user \
  --email demo-user@example.com \
  --password 'P@88w0rd!' \
  --cluster cluster-host-kunshan \
  --cluster cluster-member-zhengzhou \
  --output demo-user.yaml
```

说明：
- 该脚本默认只输出资源清单，不直接 apply
- 执行 `python` 或 `kubectl apply` 之前，遵循根 `AGENTS.md` 的人工确认规则

## 排障要点

1. 用户存在但控制台看不到集群：
   - 看 `User.metadata.annotations["iam.kubesphere.io/granted-clusters"]`
   - 看 `ClusterRoleBinding/<user>-cluster-viewer` 是否存在
   - 看 `WorkspaceTemplate.spec.placement.clusters`
2. 用户有 workspace 但进不了项目：
   - 看 namespace 下是否存在 `rolebindings.iam.kubesphere.io/<user>-admin`
   - 看该 namespace 是否打了 `kubesphere.io/workspace=<workspace>`
   - 看该 namespace 是否打了 `kubesphere.io/managed=true`
3. 不同集群项目不一致：
   - 先对比 `WorkspaceTemplate.spec.placement.clusters`
   - 再对比 member cluster 上实际 namespace 标签和 `RoleBinding.iam.kubesphere.io`
