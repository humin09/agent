---
name: k8s-ex-lb
description: "K8s Ex-LB 子专题：外部负载均衡链路排障与配置维护"
targets: ["*"]
---

你现在进入 **K8s Ex-LB 子专题**。

## 1) 适用范围

- 外部 HTTP 访问异常排查
- ex-lb 节点与服务状态核查
- ex-lb 配置检查与变更

## 2) 链路与定位

默认访问链路：`nginx (ex-lb) -> ingress -> service/endpoints -> pod`

先按链路分段排查：
1. ex-lb 层
2. ingress 层
3. service/endpoints 层
4. pod 层

## 3) 节点与服务信息

- ex-lb 节点标签：`ex-lb=true`
- 配置目录：`/etc/ex-lb/conf`
- 服务管理：`systemctl status/reload ex-lb`

常用命令：

- 查询ex-lb的节点: `kubectl --context <别名> get node -l ex-lb=true -o wide`
- 登录ex-lb的节点: `kubectl node-shell --context <别名> <ex-lb节点IP>`
- 查看ex-lb服务状态: `systemctl status ex-lb`
- 查看ex-lb配置文件: `ls /etc/ex-lb/conf/`
```

## 4) 变更约束

以下操作属于变更，必须先给主人确认：
- 修改 ex-lb 配置文件
- `systemctl reload ex-lb`

执行前必须给出：
- 目标集群与目标节点
- 变更文件与变更点
- 影响范围与回滚方式

执行后必须同步文件到/Users/humin/sugon/ske-chart/ex-lb
命名方式为:
1.如果各个集群配置是一样的只用保留一份conf文件
2.如果各个集群配置是不一样的那么用集群的别名作为名字最后部分, 比如 
 - 昆山: ex-lb-ks.conf
 - 青岛: ex-lb-qd.conf
 - 深圳: ex-lb-sz.conf
 - 郑州: ex-lb-zz.conf
 - 武汉: ex-lb-wh.conf
 - 达州: ex-lb-dz.conf
 - 魏桥: ex-lb-wq.conf