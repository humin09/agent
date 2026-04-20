#!/usr/bin/env python3
"""
Benchmark a single existing vLLM deployment configuration.

Uses ingress URL by default (proven reliable at 24+ concurrency).
Port-forward is not used — it drops connections at high concurrency.
"""

import argparse
import asyncio

from maas_benchmark_lib import (
    DEFAULT_NAMESPACE,
    add_common_args,
    build_ingress_base_url,
    get_deployment_json,
    get_pod_regex,
    print_benchmark_summary,
    run_benchmark_matrix,
    validate_common_args,
    wait_for_rollout_ready,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark one existing vLLM deployment configuration.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  # Quick fixed-mode test (24 concurrency, 48 requests, 256 output tokens)
  uv run %(prog)s --context zz --deployment-name minimax-m25-int8-yy \\
      --token-lengths 20000 --cache-rates 0.0

  # Sustained 10-minute pressure test
  uv run %(prog)s --context zz --deployment-name minimax-m25-int8-yy \\
      --benchmark-mode sustained --duration-seconds 600 \\
      --token-lengths 20000 --cache-rates 0.0 --concurrency 24

  # Full matrix: 4 input lengths x 3 cache rates = 12 cases
  uv run %(prog)s --context zz --deployment-name minimax-m25-int8-yy \\
      --token-lengths 20000 40000 80000 120000 --cache-rates 0.0 0.4 0.8
""",
    )
    add_common_args(parser)
    parser.add_argument(
        "--rollout-timeout-seconds",
        type=int,
        default=300,
        help="timeout for confirming deployment readiness before benchmarking",
    )
    return validate_common_args(parser, parser.parse_args())


async def orchestrate(args: argparse.Namespace):
    metrics_service = args.metrics_service or args.deployment_name

    deployment = get_deployment_json(args.context, args.deployment_name)
    pod_regex = get_pod_regex(
        args.context,
        deployment,
        args.deployment_name,
        explicit_pods=args.pods,
        explicit_pod_regex=args.pod_regex,
    )

    wait_for_rollout_ready(
        args.context,
        args.deployment_name,
        rollout_timeout_seconds=args.rollout_timeout_seconds,
        warmup_seconds=args.warmup_seconds,
    )

    base_url = args.base_url or build_ingress_base_url(args.context, args.deployment_name)

    print_benchmark_summary(
        args,
        "vLLM single-configuration benchmark",
        extra_lines=[f"Base URL: {base_url}"],
    )

    return await run_benchmark_matrix(
        args=args,
        base_url=base_url,
        metrics_service=metrics_service,
        pod_regex=pod_regex,
        result_prefix={
            "target": {
                "context": args.context,
                "namespace": DEFAULT_NAMESPACE,
                "deployment_name": args.deployment_name,
                "thanos_context": args.thanos_context or args.context,
                "metrics_namespace": DEFAULT_NAMESPACE,
                "metrics_service": metrics_service,
                "mode": "single-config",
            },
            "baseline": {},
        },
    )


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
