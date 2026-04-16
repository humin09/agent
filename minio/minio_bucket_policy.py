#!/usr/bin/env python3
import subprocess
import json
from datetime import datetime


def run_cmd(cmd):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return -1, "", str(e)


def get_buckets(alias):
    code, out, err = run_cmd(["mc", "ls", f"{alias}/"])
    if code != 0:
        return []
    buckets = []
    for line in out.strip().split("\n"):
        if line:
            parts = line.split()
            if len(parts) >= 5:
                bucket_name = parts[-1].rstrip("/")
                buckets.append(bucket_name)
    return buckets


def get_anonymous_policy(alias, bucket):
    code, out, err = run_cmd(["mc", "anonymous", "get", f"{alias}/{bucket}"])
    if code == 0:
        return out.strip()
    return "private"


def get_ilm_rules(alias, bucket):
    code, out, err = run_cmd(["mc", "ilm", "rule", "list", f"{alias}/{bucket}"])
    if code != 0:
        return "无"
    if not out.strip():
        return "无"

    lines = out.strip().split("\n")
    result = []

    noncurrent_expiration_found = False

    for line in lines:
        if "NoncurrentVersionExpiration" in line:
            noncurrent_expiration_found = True
            continue
        if "DAYS TO EXPIRE" in line:
            continue
        if "│" in line and "Enabled" in line:
            parts = [p.strip() for p in line.split("│") if p.strip()]
            if len(parts) >= 5:
                days = parts[4]
                if days.isdigit():
                    days_int = int(days)
                    if days_int > 0:
                        if noncurrent_expiration_found:
                            result.append(f"旧版本{days_int}天过期")
                        else:
                            result.append(f"{days_int}天过期")
                    elif days_int == 0:
                        if "EXPIRE DELETEMARKER" in line:
                            result.append("清理删除标记")

    if result:
        return ", ".join(result)
    return "已配置"


def get_version_status(alias, bucket):
    code, out, err = run_cmd(["mc", "version", "info", f"{alias}/{bucket}"])
    if code == 0:
        if "un-versioned" in out:
            return "未启用"
        elif "suspended" in out:
            return "已暂停"
        elif "Enabled" in out:
            return "已启用"
        return out.strip()
    return "未启用"


def extract_buckets_from_policy(alias, policy_name):
    buckets = []
    code, out, err = run_cmd(["mc", "admin", "policy", "info", alias, policy_name])
    if code == 0:
        try:
            policy_data = json.loads(out)
            if "Policy" in policy_data and "Statement" in policy_data["Policy"]:
                for stmt in policy_data["Policy"]["Statement"]:
                    if "Resource" in stmt:
                        for resource in stmt["Resource"]:
                            if resource.startswith("arn:aws:s3:::"):
                                bucket_part = resource[len("arn:aws:s3:::") :]
                                if "/" in bucket_part:
                                    bucket_name = bucket_part.split("/")[0]
                                else:
                                    bucket_name = bucket_part

                                if bucket_name and bucket_name != "*":
                                    if bucket_name not in buckets:
                                        buckets.append(bucket_name)
        except Exception:
            pass
    return buckets


def get_bucket_permissions(alias):
    bucket_permissions = {}

    code, out, err = run_cmd(["mc", "admin", "user", "list", alias])
    if code == 0:
        for line in out.strip().split("\n"):
            if line:
                parts = line.split()
                if len(parts) >= 2:
                    username = parts[1]
                    policy_name = parts[2] if len(parts) >= 3 else ""

                    if policy_name:
                        buckets = extract_buckets_from_policy(alias, policy_name)
                        for bucket in buckets:
                            if bucket not in bucket_permissions:
                                bucket_permissions[bucket] = []
                            if username not in bucket_permissions[bucket]:
                                bucket_permissions[bucket].append(username)

                    code2, out2, err2 = run_cmd(
                        ["mc", "admin", "user", "info", alias, username]
                    )
                    if code2 == 0 and "MemberOf" in out2:
                        import re

                        groups_match = re.search(r"MemberOf:\s*\[(.*?)\]", out2)
                        if groups_match:
                            groups_str = groups_match.group(1)
                            groups = [g.strip() for g in groups_str.split(",")]
                            for group_name in groups:
                                code3, out3, err3 = run_cmd(
                                    ["mc", "admin", "group", "info", alias, group_name]
                                )
                                if code3 == 0 and "Policy:" in out3:
                                    import re

                                    policy_match = re.search(r"Policy:\s*(\S+)", out3)
                                    if policy_match:
                                        group_policy = policy_match.group(1)
                                        buckets = extract_buckets_from_policy(
                                            alias, group_policy
                                        )
                                        for bucket in buckets:
                                            if bucket not in bucket_permissions:
                                                bucket_permissions[bucket] = []
                                            if (
                                                username
                                                not in bucket_permissions[bucket]
                                            ):
                                                bucket_permissions[bucket].append(
                                                    username
                                                )

    return bucket_permissions


def main():
    clusters = [
        ("ks", "昆山"),
        ("dzminio", "达州"),
        ("zzminio", "郑州"),
        ("qdminio", "青岛"),
        ("xaminio", "西安"),
    ]

    report = []
    report.append("# MinIO 集群桶策略报告")
    report.append("")
    report.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")

    for alias, name in clusters:
        report.append(f"## {name} ({alias})")
        report.append("")

        bucket_permissions = get_bucket_permissions(alias)

        report.append("| 桶名 | 访问策略 | 授权用户 | 淘汰策略 | 版本控制 | 同步策略 |")
        report.append("|------|----------|----------|----------|----------|----------|")

        buckets = get_buckets(alias)
        if not buckets:
            report.append("| (无法获取桶列表) | - | - | - | - | - |")
            report.append("")
            continue

        for bucket in buckets:
            anon_policy = get_anonymous_policy(alias, bucket)

            policy_display = "私有"
            if "public" in anon_policy.lower():
                policy_display = "**公开(读写)**"
            elif "download" in anon_policy.lower():
                policy_display = "公开(只读)"
            elif "upload" in anon_policy.lower():
                policy_display = "公开(只写)"

            authorized_users = bucket_permissions.get(bucket, [])
            if not authorized_users:
                authorized_users = ["admin(全局管理员)"]

            users_display = ", ".join(authorized_users)

            ilm_rules = get_ilm_rules(alias, bucket)
            version_status = get_version_status(alias, bucket)

            report.append(
                f"| {bucket} | {policy_display} | {users_display} | {ilm_rules} | {version_status} | - |"
            )

        report.append("")

    report.append("## 备注")
    report.append("")
    report.append("- **授权用户**: 通过 IAM Policy 或用户组授予该桶读写权限的用户")
    report.append(
        "- **admin(全局管理员)**: 拥有所有桶读写权限的管理员用户（如 readwrite 策略）"
    )
    report.append(
        "- **同步策略**: MinIO 桶间同步通常通过 `mc mirror`、`minio mirror` 或 Thanos/K8s 配置实现，mc 命令无法直接查询。建议检查各集群的 Prometheus/Thanos 配置或相关定时任务。"
    )
    report.append("")

    print("\n".join(report))

    with open("/Users/humin/opencode/minio_policy_report.md", "w") as f:
        f.write("\n".join(report))
    print(f"\n报告已保存到: /Users/humin/opencode/minio_policy_report.md")


if __name__ == "__main__":
    main()
