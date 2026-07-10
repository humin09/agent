---
name: kubesphere
description: KubeSphere 4.1 多集群与 IAM 运维技能。默认开户流程：用户名=workspace=同名 namespace，global role 固定为 platform-regular，workspace role 为 <user>-admin，ns role 为 admin，不分 cluster-viewer。涉及开户流程或其排障时必须使用。
---

# KubeSphere
## 功能开发
1. 源码仓库: ~/sugon/kubesphere
2. 发布仓库: ~/sugon/ske-chart/kubesphere
3. 如果是新功能开发, 应该在上海测试环境验证完毕后

## 控制台前端页面修改与发布

适用范围：修改 KubeSphere console 页面、`server/views/index.html` 注入脚本、覆盖静态资源、修复前端路由或 dashboard 体验等。

### 目录规范

patch 放在 `~/sugon/kubesphere/console/patches/<feature>/`，至少包含：
- `Dockerfile`
- `README.md`
- 被覆盖文件，例如 `index.html`

### 修改要求

1. 优先小范围 patch，避免直接改 dist bundle。
2. 注入脚本兼容 SPA 路由：`popstate`、`history.pushState/replaceState`、必要时 `MutationObserver`。
3. 不依赖随机 class name，优先用稳定文本、DOM 层级、`id`、语义属性定位。
4. 外部注入链接优先用 `window.location.assign(<target>)` 跳转。
5. 用户可见功能同时处理中英文文本。
6. 授权集群、workspace、项目等数据优先读 KubeSphere CRD/API。

### 构建镜像

先确认线上当前镜像：

```bash
kubectl --context ks -n kubesphere-system get deploy ks-console -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
```

`Dockerfile` 基于当前稳定 base 镜像：

```dockerfile
FROM image.ac.com:5000/k8s/kubesphere/ks-console:v4.1.2-gateway-fix
COPY index.html /opt/kubesphere/console/server/views/index.html
```

在 `ks` 集群通过 `ske-model` 的 `ske-tool` 进行镜像构建和推送：

```bash
kubectl --context ks -n ske-model get pod -l app=ske-tool -o wide
kubectl --context ks -n ske-model exec <ske-tool-pod> -- mkdir -p /tmp/build/<feature>-<tag>
kubectl --context ks -n ske-model cp ~/sugon/kubesphere/console/patches/<feature>/. <ske-tool-pod>:/tmp/build/<feature>-<tag>
kubectl --context ks -n ske-model exec <ske-tool-pod> -- sh -c 'cd /tmp/build/<feature>-<tag> && docker build -t image.ac.com:5000/k8s/kubesphere/ks-console:<new-tag> . && docker push image.ac.com:5000/k8s/kubesphere/ks-console:<new-tag>'
```

### 发布上线

生产发布必须先按 AGENTS 变更模板给出完整命令、影响范围、回滚方案，并等待用户确认。

```bash
kubectl --context ks -n kubesphere-system set image deploy/ks-console ks-console=image.ac.com:5000/k8s/kubesphere/ks-console:<new-tag>
kubectl --context ks -n kubesphere-system rollout status deploy/ks-console --timeout=180s
```

影响范围必须写清楚：
- context: `ks`
- namespace: `kubesphere-system`
- resource: `deployment/ks-console`
- expected impact: KubeSphere console 滚动升级，用户可能遇到一次页面刷新
- rollback: 回退到发布前镜像

### 发布后验证

```bash
kubectl --context ks -n kubesphere-system get deploy ks-console -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
kubectl --context ks -n kubesphere-system get pod -l app=ks-console -o wide
kubectl --context ks -n kubesphere-system exec deploy/ks-console -- sh -c 'grep -n "<关键标记>" /opt/kubesphere/console/server/views/index.html'
```

页面交互改动需要浏览器登录验证：
- 目标页面能渲染
- 新增元素位置符合预期
- 点击跳转目标 URL 正确
- 非目标路由不显示或不影响原页面

### 回滚

发布前记录旧镜像，异常时回滚旧镜像：

```bash
kubectl --context ks -n kubesphere-system set image deploy/ks-console ks-console=<old-image>
kubectl --context ks -n kubesphere-system rollout status deploy/ks-console --timeout=180s
```

回滚也属于线上变更，执行前仍需确认。

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
