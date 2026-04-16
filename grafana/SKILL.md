---
name: k8s-grafana
description: "K8s Grafana 运维子专题：Dashboard 定位、面板修改、回滚"
targets: ["*"]
---

你现在进入 **K8s Grafana 子专题**。

## 访问信息

- 地址：`https://grafana.ksai.scnet.cn:58043`
- 账户：`admin` / `prom-sugon`
- 集群：昆山（ks），命名空间：`ske`
- ai 文件夹 folderUid：`aek4z00z7upkwa`

## API 常用操作

```bash
# 搜索 dashboard
curl -sk -u admin:prom-sugon 'https://grafana.ksai.scnet.cn:58043/api/search?type=dash-db'

# 获取 dashboard JSON
curl -sk -u admin:prom-sugon 'https://grafana.ksai.scnet.cn:58043/api/dashboards/uid/<UID>'

# 推送 dashboard（注意带 folderUid）
curl -sk -u admin:prom-sugon -X POST 'https://grafana.ksai.scnet.cn:58043/api/dashboards/db' \
  -H 'Content-Type: application/json' -d @payload.json
```

**推送注意**：payload 必须包含 `"folderUid": "aek4z00z7upkwa"`，否则 dashboard 会跑到 General 文件夹。

## ai 文件夹 Dashboard 索引

| uid | title |
|-----|-------|
| maas | maas |
| adslfq8amercwa | Notebook |
| effqyxiahu29sa | openclaw |
| aeh6piwqe1gjkb | Pod 资源计量 |
| bea4kzmry7qiod | 模型训练 |
| adslfq8amercw4 | 模型部署 |
| bensv5jok3hmoe | 节点列表 |
| xfpJB9FGz | 节点详情 |
| becc3itr2rbb4d | 运营101 |

## 执行规则
1. 改动前必须备份 Dashboard JSON（同目录生成 `*.bak.<timestamp>.json`）。
2. 优先按 `dashboard uid` 定位，再用 folder/title 辅助。
3. 涉及指标语义变更时，联动 Thanos 校验。
4. 不在 Skill 中保存明文口令。



## 标准流程
定位（uid + folder=ai） -> 判断 CM/API-only -> 备份 -> 修改 -> 更新索引 -> 回归验证

协作：指标核验加载 `/Users/humin/agent/k8s-thanos/SKILL.md`。


