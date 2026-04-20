#!/usr/bin/env python3
"""
Tune a deployment by changing startup args and benchmarking each configuration.

Uses ingress URL by default (not port-forward) for reliable high-concurrency testing.
"""

import argparse
import asyncio
from dataclasses import asdict
from datetime import datetime

from maas_benchmark_lib import (
    DEFAULT_BATCHED_TOKENS,
    DEFAULT_NAMESPACE,
    DeploymentConfig,
    add_common_args,
    build_ingress_base_url,
    get_container_args,
    get_deployment_json,
    get_pod_regex,
    patch_container_args,
    print_benchmark_summary,
    run_benchmark_matrix,
    save_results,
    upsert_cli_arg,
    validate_common_args,
    wait_for_rollout_ready,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Patch deployment startup args and benchmark each configuration.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  # Test 3 batched-tokens configs, sustained mode, restore after
  uv run %(prog)s --context zz --deployment-name minimax-m25-int8-yy \\
      --batched-tokens 4096 6144 8192 \\
      --benchmark-mode sustained --duration-seconds 600 \\
      --token-lengths 20000 --cache-rates 0.0 \\
      --restore-on-exit

  # Quick fixed-mode tuning
  uv run %(prog)s --context zz --deployment-name minimax-m25-int8-yy \\
      --batched-tokens 4096 8192 \\
      --token-lengths 20000 40000 --cache-rates 0.0 0.4 \\
      --restore-on-exit
""",
    )
    add_common_args(parser)
    parser.add_argument(
        "--container-index",
        type=int,
        default=0,
        help="container index inside deployment pod spec",
    )
    parser.add_argument(
        "--batched-tokens",
        type=int,
        nargs="+",
        default=DEFAULT_BATCHED_TOKENS,
        help="max-num-batched-tokens values to test",
    )
    parser.add_argument(
        "--rollout-timeout-seconds",
        type=int,
        default=1800,
        help="deployment rollout timeout",
    )
    parser.add_argument(
        "--restore-on-exit",
        action="store_true",
        help="restore original deployment args after the full test matrix",
    )
    args = validate_common_args(parser, parser.parse_args())
    if not args.batched_tokens:
        parser.error("--batched-tokens requires at least one value")
    return args


async def orchestrate(args: argparse.Namespace):
    metrics_service = args.metrics_service or args.deployment_name
    base_url = args.base_url or build_ingress_base_url(args.context, args.deployment_name)

    print_benchmark_summary(
        args,
        "vLLM startup-arg tuning benchmark",
        extra_lines=[
            f"Base URL: {base_url}",
            f"Batched tokens: {args.batched_tokens}",
        ],
    )

    deployment = get_deployment_json(args.context, args.deployment_name)
    original_args = get_container_args(deployment, args.container_index)
    all_results = {
        "test_start_time": datetime.now().isoformat(),
        "target": {
            "context": args.context,
            "namespace": DEFAULT_NAMESPACE,
            "deployment_name": args.deployment_name,
            "thanos_context": args.thanos_context or args.context,
            "container_index": args.container_index,
            "metrics_namespace": DEFAULT_NAMESPACE,
            "metrics_service": metrics_service,
            "mode": "startup-tuning",
        },
        "parameters": {
            "batched_tokens": args.batched_tokens,
            "base_url": base_url,
        },
        "baseline": {
            "original_container_args": original_args,
        },
        "results": [],
        "restore_on_exit": args.restore_on_exit,
        "restored": False,
        "test_end_time": None,
    }

    for batched_tokens in args.batched_tokens:
        config = DeploymentConfig(max_num_batched_tokens=batched_tokens)
        updated_args = upsert_cli_arg(
            original_args,
            "--max-num-batched-tokens",
            str(config.max_num_batched_tokens),
        )
        config_result = {
            "config": asdict(config),
            "deployment_patch_args": updated_args,
            "cases": [],
            "error": None,
        }

        try:
            patch_container_args(
                args.context,
                args.deployment_name,
                args.container_index,
                updated_args,
            )
            wait_for_rollout_ready(
                args.context,
                args.deployment_name,
                rollout_timeout_seconds=args.rollout_timeout_seconds,
                warmup_seconds=args.warmup_seconds,
            )
            refreshed_deployment = get_deployment_json(args.context, args.deployment_name)
            pod_regex = get_pod_regex(
                args.context,
                refreshed_deployment,
                args.deployment_name,
                explicit_pods=args.pods,
                explicit_pod_regex=args.pod_regex,
            )
            case_results = await run_benchmark_matrix(
                args=args,
                base_url=base_url,
                metrics_service=metrics_service,
                pod_regex=pod_regex,
                result_prefix={
                    "target": all_results["target"],
                    "baseline": {
                        "original_container_args": original_args,
                        "current_config_args": updated_args,
                    },
                },
                save_intermediate=False,
            )
            config_result["cases"] = case_results["results"]
        except Exception as exc:
            config_result["error"] = str(exc)[:500]

        all_results["results"].append(config_result)
        save_results(args.result_log, all_results)

    if args.restore_on_exit:
        patch_container_args(
            args.context,
            args.deployment_name,
            args.container_index,
            original_args,
        )
        wait_for_rollout_ready(
            args.context,
            args.deployment_name,
            rollout_timeout_seconds=args.rollout_timeout_seconds,
            warmup_seconds=args.warmup_seconds,
        )
        all_results["restored"] = True

    all_results["test_end_time"] = datetime.now().isoformat()
    save_results(args.result_log, all_results)
    return all_results


def main() -> int:
    args = parse_args()
    try:
        asyncio.run(orchestrate(args))
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        return 130
    except Exception as exc:
        print(f"\nERROR: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
