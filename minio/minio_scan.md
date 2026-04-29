# MinIO Metadata Scan

## Run Info

- Mode: `dry-run`
- Source: `http://10.13.17.168:19000`
- Target: `http://10.13.17.169:19000`
- Buckets scanned: `5`
- Buckets with diffs: `1`
- Buckets with planned actions: `1`
- Buckets with warnings: `0`
- Apply requested: `False`

## Safety

- Buckets are never deleted.
- Objects are never deleted.
- `gitlab-lfs-prod` lifecycle is only removed, never added.
- `gitlab-lfs-prod` versioning is suspended if enabled; true `unversioned` cannot be restored after enablement.

## Bucket Summary

| Bucket | Source Exists | Target Exists | Source Policy | Target Policy | Source Versioning | Target Versioning | Source ILM Rules | Target ILM Rules | Diffs | Actions | Warnings |
| --- | --- | --- | --- | --- | --- | --- | ---: | ---: | --- | --- | --- |
| gitlab-lfs-prod | yes | yes | private | private | unversioned | unversioned | 0 | 0 | - | - | - |
| k8s | yes | yes | private | private | unversioned | unversioned | 0 | 0 | - | - | - |
| loki | yes | yes | private | private | unversioned | unversioned | 1 | 1 | - | - | - |
| prom | yes | yes | private | private | unversioned | unversioned | 1 | 1 | - | - | - |
| tmp | yes | yes | public | private | unversioned | unversioned | 1 | 0 | policy:public->private<br>ilm:rules=1->0 | policy would-apply-json<br>ilm would-apply | - |

## Raw JSON

```json
{
  "bucket_count": 5,
  "guarantees": {
    "delete_bucket": false,
    "delete_object": false,
    "gitlab_lfs_prod_no_ilm": true
  },
  "mode": "dry-run",
  "results": [
    {
      "actions": [],
      "bucket": "gitlab-lfs-prod",
      "diffs": [],
      "source_error": null,
      "source_exists": true,
      "source_ilm_rules": 0,
      "source_policy": "private",
      "source_versioning": "unversioned",
      "target_error": null,
      "target_exists": true,
      "target_ilm_rules": 0,
      "target_policy": "private",
      "target_versioning": "unversioned",
      "warnings": []
    },
    {
      "actions": [],
      "bucket": "k8s",
      "diffs": [],
      "source_error": null,
      "source_exists": true,
      "source_ilm_rules": 0,
      "source_policy": "private",
      "source_versioning": "unversioned",
      "target_error": null,
      "target_exists": true,
      "target_ilm_rules": 0,
      "target_policy": "private",
      "target_versioning": "unversioned",
      "warnings": []
    },
    {
      "actions": [],
      "bucket": "loki",
      "diffs": [],
      "source_error": null,
      "source_exists": true,
      "source_ilm_rules": 1,
      "source_policy": "private",
      "source_versioning": "unversioned",
      "target_error": null,
      "target_exists": true,
      "target_ilm_rules": 1,
      "target_policy": "private",
      "target_versioning": "unversioned",
      "warnings": []
    },
    {
      "actions": [],
      "bucket": "prom",
      "diffs": [],
      "source_error": null,
      "source_exists": true,
      "source_ilm_rules": 1,
      "source_policy": "private",
      "source_versioning": "unversioned",
      "target_error": null,
      "target_exists": true,
      "target_ilm_rules": 1,
      "target_policy": "private",
      "target_versioning": "unversioned",
      "warnings": []
    },
    {
      "actions": [
        "policy would-apply-json",
        "ilm would-apply"
      ],
      "bucket": "tmp",
      "diffs": [
        "policy:public->private",
        "ilm:rules=1->0"
      ],
      "source_error": null,
      "source_exists": true,
      "source_ilm_rules": 1,
      "source_policy": "public",
      "source_versioning": "unversioned",
      "target_error": null,
      "target_exists": true,
      "target_ilm_rules": 0,
      "target_policy": "private",
      "target_versioning": "unversioned",
      "warnings": []
    }
  ],
  "source_endpoint": "http://10.13.17.168:19000",
  "target_endpoint": "http://10.13.17.169:19000"
}
```
