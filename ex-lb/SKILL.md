---
name: k8s-ex-lb
description: "K8s Ex-LB 子专题：外部负载均衡链路排障与配置维护"
targets: ["*"]
---

你现在进入 **K8s Ex-LB 子专题**。

## 1. 适用范围

- 外部 HTTP 访问异常排查
- ex-lb 节点与服务状态核查
- ex-lb 配置检查与变更

## 2. 链路与定位

默认访问链路：`外网域名:端口`->`snat到内网keepalived vip:端口`->`nginx (ex-lb)+keepalived -> ingress -> service/endpoints -> pod`

先按链路分段排查：
1. ex-lb 层
2. ingress 层
3. service/endpoints 层
4. pod 层

## 3. 节点与服务信息

- ex-lb 节点标签：`ex-lb=true`
- 配置目录：`/etc/ex-lb/conf`
- 服务管理：`systemctl status/reload ex-lb`
- 配置验证: `/etc/ex-lb/sbin/ex-lb -c /etc/ex-lb/conf/ex-lb.conf`

常用命令：

- 查询ex-lb的节点: `kubectl --context <别名> get node -l ex-lb=true -o wide`
- 登录ex-lb的节点: `kubectl node-shell --context <别名> <ex-lb节点IP>`
- 查看ex-lb服务状态: `systemctl status ex-lb`
- 查看ex-lb配置文件: `ls /etc/ex-lb/conf/`
- 查看keepalived配置文件: `cat /etc/keepalived/keepalived.conf`
```

## 4. 变更约束

以下操作属于变更，必须先给主人确认：
- 修改 ex-lb 配置文件
- `systemctl reload ex-lb`

执行前必须给出：
- 目标集群与目标节点
- 变更文件与变更点
- 影响范围与回滚方式

执行后必须同步文件到 /Users/humin/sugon/ske-chart/ex-lb

命名规则: `ex-lb-{ctx}.conf`，每个集群一份文件。

DNS forward 的 `listen` 绑定使用 `$NODE_IP` 占位符（不能用 0.0.0.0 因为 node-local-dns 已占用 `169.254.20.10:53`），上传时由脚本替换为节点实际 IP。

上传命令：
```bash
python ~/agent/scripts/ex-lb-conf-upload.py -c <ctx> -n <node_ip> /Users/humin/sugon/ske-chart/ex-lb/ex-lb-<ctx>.conf
```

示例：`python ~/agent/scripts/ex-lb-conf-upload.py -c dz -n 10.1.114.2 ex-lb-dz.conf`

## 5. 集群速查

| context | 城市 | 环境 | ex-lb vip | ex-lb地址 |
|---|---|---|---|---|
| `ks` | 昆山 | 生产 | 10.15.200.50 | `https://<app>.ksai.scnet.cn:58043` |
| `dz` | 达州 | 生产 | 192.168.114.201 | `https://<app>.dzai.scnet.cn:58043` |
| `qd` | 青岛 | 生产 | 10.28.4.204 | `https://<app>.qdai.scnet.cn:58043` |
| `wh` | 武汉 | 生产 | 10.100.2.24 | `https://<app>.whai.scnet.cn:58043` |
| `sz` | 深圳 | 生产 | 192.168.0.206 | `https://<app>.szai.scnet.cn:58043` |
| `zz` | 郑州 | 生产 | 172.20.13.202 | `https://<app>.zzai.scnet.cn:58043` |
| `ny` | 纽约 | 生产 | 10.4.17.5 | `https://<app>.zzai.scnet.ai:58043` |
| `wq` | 魏桥 | 生产 | 172.18.18.18 | `https://<app>.sd5ai.scnet.cn:58043` |
| `bj` | 北京 | 测试 | 10.0.31.15 | `https://<app>.sugon-bj.xyz:58043` |
| `sh` | 上海 | 测试 | 10.16.5.1 | `https://<app>.sugon-sh.xyz:58043` |
| `ly` | 洛阳 | 测试 | 172.20.13.202 | `https://<app>.zzai.scnet.ai:58043` |
| `xa` | 西安 | 测试 | - | `https://<app>.xaai.scnet.ai:58043` |
| `bs` | 璧山 | 测试 | 10.32.0.11 | `https://<app>.sugon-bs.xyz:58043` |

端口说明：
- `58043`: HTTPS ingress 入口，常见 app：`minio`、`vm`、`vl ingress` 等
- `58000`: HTTP MAAS ingress 地址
- `9000`: minio 地址

## 6. 上线流程

### 6.1 检查线上与本地差异

```bash
python ~/agent/scripts/upload.py -c <cluster> <node_ip>:/etc/ex-lb/conf/ex-lb.conf /tmp/online.conf
diff /tmp/online.conf ~/sugon/ske-chart/ex-lb/ex-lb-<cluster>.conf
```

期望仅 DNS forward 块的 `listen` 不同（线上是具体 IP，本地是 `$NODE_IP` 占位符）。

### 6.2 准备本地配置

**情况 A：仅 DNS 占位符差异**
- 复制本地 `ex-lb-<cluster>.conf` 为 `ex-lb-<cluster>.conf.new`
- 在 `.new` 上应用变更

**情况 B：有其他差异**
- 将线上配置拉取到本地 `ex-lb-<cluster>.conf`
- 将 DNS 块的 IP 替换为 `$NODE_IP` 占位符
- 再复制为 `.new` 并应用变更

### 6.3 上传配置

```bash
python ~/agent/scripts/ex-lb-conf-upload.py -c <cluster>
```

脚本自动处理所有 ex-lb 节点：替换 `$NODE_IP` → 备份 → 上传 → 验证 → reload。

### 6.4 验证

```bash
python ~/agent/scripts/ex-lb-conf-test.py -c <cluster>
```

期望全部 ✅：DNS 解析（vm.local、image.ac.com、aa.<domain>）和 HTTP 探测均正常。

### 6.5 异常时回滚

若验证失败，upload 脚本已在每个节点生成 `/etc/ex-lb/conf/ex-lb.conf.bak`。对每个 ex-lb 节点执行：

```bash
# 获取节点列表
kubectl get node -l ex-lb=true -o jsonpath='{range .items[*]}{.status.addresses[0].address}{"\n"}{end}'

# 对每个节点回滚
kubectl node-shell --context <ctx> <node_ip> -- bash -c 'cp /etc/ex-lb/conf/ex-lb.conf.bak /etc/ex-lb/conf/ex-lb.conf && systemctl reload ex-lb'
```

**⚠️ 安全约束：严禁修改 ex-lb 节点上除 `/etc/ex-lb/conf/ex-lb.conf` 之外的任何文件（包括其他配置文件、服务文件、系统文件等），除非获得用户明确确认。**

### 6.6 正式上线

验证通过后，本地文件即为当前线上状态，无需 reload（upload 已完成）。删除 `.new` 文件即可。

