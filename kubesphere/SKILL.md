---
name: kubesphere
description: KubeSphere 4.1 多集群与 IAM 运维技能。默认开户流程：用户名=workspace=同名 namespace，global role 固定为 platform-regular，workspace role 为 <user>-admin，ns role 为 admin，不分 cluster-viewer。涉及开户流程或其排障时必须使用。
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
   - global role = `platform-regular`（**不给 cluster-viewer**）
   - workspace role = `<username>-admin`（自动创建同名 WorkspaceTemplate）
   - namespace role = `admin`
   - 只给指定 clusters
   - namespace 必须**已存在**，脚本只 patch 标签，不创建 ns
3. 默认密码：`<Username>@123`（用户名首字母大写 + @123），邮箱：`<username>@example.com`
4. 所有 KubeSphere cluster 查询，统一从 host cluster `ks` 上看 `clusters.cluster.kubesphere.io`。

## 集群映射

区分两套名字：
- `kubectl --context <alias>` 是你本地 kubeconfig 的上下文别名
- `clusters.cluster.kubesphere.io/<name>` 是 KubeSphere 内部 cluster 标识

当前已确认映射（2026-06-23 全量重命名完成）：

| 城市 | 本地 kubectl context | KubeSphere cluster name | 别名 | API Endpoint |
|------|----------------------|-------------------------|------|--------------|
| 昆山 | `ks` | `cluster-host-kunshan` | 昆山生产集群 | `https://k8s.ksai.scnet.cn:56443` |
| 达州 | `dz` | `dz` | 达州生产集群 | `https://k8s.dzai.scnet.cn:56443` |
| 青岛 | `qd` | `qd` | 青岛生产集群 | `https://k8s.qdai.scnet.cn:56443` |
| 魏桥 | `wq` | `wq` | 魏桥生产集群 | `https://k8s.sd5ai.scnet.cn:56443` |
| 武汉 | `wh` | `wh` | 武汉生产集群 | `https://k8s.whai.scnet.cn:56443` |
| 郑州 | `zz` | `zz` | 郑州生产集群 | `https://k8s.zzai.scnet.cn:56443` |
| 深圳 | `sz` | `sz` | 深圳生产集群 | `https://k8s.szai.scnet.cn:56443` |
| 纽约 | - | `ny` | 纽约生产集群 | (hw endpoint) |
| 西安 | - | `xa` | 西安生产集群 | `https://xak8sapi.scnet.cn:56443` |
| 乌镇 | - | `wz` | 乌镇生产集群 | (endpoint) |
| 腾讯 | - | `cluster-tx` | 腾讯集群 | (SSH 模式) |

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
2. `GlobalRoleBinding`（`platform-regular`）
3. `WorkspaceTemplate`（同名，自动创建）
4. `WorkspaceRoleBinding`（`<username>-admin`）
5. `Namespace` patch（仅补 workspace + managed 标签，ns 必须预存在）
6. namespace 下的 `RoleBinding.iam.kubesphere.io`（`admin`）

默认角色：
- `platform-regular`: 平台普通用户，业务用户默认入口
- namespace `admin`: 项目/命名空间全权限
- **不分 cluster-viewer**，集群只读由 GlobalRole 内隐含权限覆盖

默认契约：
- 用户名 = workspace = 各子集群 namespace
- namespace 必须打上：
  - `kubesphere.io/workspace=<username>`
  - `kubesphere.io/managed=true`

## 标准做法

创建或批量生成用户授权清单时，优先使用：
- `~/agent/scripts/kubesphere_user_bootstrap.py`

默认行为：
| 参数 | 默认 |
|---|---|
| `--email` | `<username>@example.com` |
| `--password` | `<Username>@123`（首字母大写） |
| `--no-namespace-labels` | 关闭（默认生成 ns patch） |
| `--no-git` | 关闭（默认自动备份到 `~/sugon/ske-chart/kubesphere/user/<username>.yaml` 并 `git add` + `git commit`） |

推荐模式：
- 先生成 YAML，人工 review，确认后再 apply
- 用 `--skip-existing --context ks` 跳过已存在资源
- 用 `--member-context zz=zz` 映射 KubeSphere cluster name 到本地 kubectl context
- NS 不存在时脚本会自动报错，提示先手动创建

示例：

```bash
python ~/agent/scripts/kubesphere_user_bootstrap.py \
  --context ks \
  --skip-existing \
  --member-context zz=zz \
  --username demo-user \
  --cluster cluster-host-kunshan \
  --cluster zz \
  --output demo-user.yaml
```

输出清单：
- `User` / `GlobalRoleBinding` / `WorkspaceTemplate` / `WorkspaceRoleBinding` / `Namespace patch` / `RoleBinding`

说明：
- 脚本只 render YAML，apply 需要人工确认（遵循 AGENTS.md 变更确认规则）
- 自动备份到 `~/sugon/ske-chart/kubesphere/user/<username>.yaml` 并 git commit（审计溯源）
- 执行 `kubectl apply` 之前，遵循根 `AGENTS.md` 的人工确认规则

## 排障要点

1. 用户存在但控制台看不到集群：
   - 看 `User.metadata.annotations["iam.kubesphere.io/granted-clusters"]`
   - 看 `WorkspaceTemplate.spec.placement.clusters`
   - 看对应 workspace 是否存在（ks 集群 `get workspace.tenant.kubesphere.io`）
2. 用户有 workspace 但进不了项目：
   - 看 namespace 下是否存在 `rolebindings.iam.kubesphere.io/<user>-admin`
   - 看该 namespace 是否打了 `kubesphere.io/workspace=<workspace>`
   - 看该 namespace 是否打了 `kubesphere.io/managed=true`
   - 看 namespace 的 `ownerReferences` 是否有 `Workspace/<user>`
3. 不同集群项目不一致：
   - 先对比 `WorkspaceTemplate.spec.placement.clusters`
   - 再对比 member cluster 上实际 namespace 标签和 `RoleBinding.iam.kubesphere.io`
