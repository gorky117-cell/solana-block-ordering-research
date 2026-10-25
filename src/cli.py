import argparse
import sys
import os
import json
import logging
from src.config import config
from src.rpc import SolanaRPCClient
from src.measurement_engine import MeasurementEngine, SpendCapExceededError
from src.report_generator import ReportGenerator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("SolanaBlockOrderingCLI")

def banner():
    print(r"""
================================================================================
       INSIDE THE BLOCK: SOLANA VALIDATOR TRANSACTION ORDERING RESEARCH
        Superteam Ukraine Research Bounty | Solana Mainnet Analysis
================================================================================
    """)

def main():
    banner()
    parser = argparse.ArgumentParser(
        description="Solana Validator Transaction Ordering Empirical Research Suite"
    )
    parser.add_argument(
        "--live",
        action="store_true",
        default=False,
        help="Execute real transactions on Solana Mainnet (Requires funded keypair and spend cap check)."
    )
    parser.add_argument(
        "--spend-cap",
        type=float,
        default=config.MAX_TOTAL_SPEND_SOL,
        help=f"Maximum spend limit in SOL (Strict Bounty Cap: {config.MAX_TOTAL_SPEND_SOL} SOL)."
    )
    parser.add_argument(
        "--benchmark-all",
        action="store_true",
        default=True,
        help="Benchmark all 6 target validators across Jito, Frankendancer, Agave, and Firedancer."
    )
    parser.add_argument(
        "--generate-report",
        action="store_true",
        default=True,
        help="Generate REPORT.md with findings, diagrams, and failure mode analysis."
    )
    parser.add_argument(
        "--data-file",
        type=str,
        default=os.path.join(config.DATA_DIR, "validators.json"),
        help="Path to validator cohort configuration JSON."
    )
    parser.add_argument(
        "--report-output",
        type=str,
        default="REPORT.md",
        help="Path for generated markdown report."
    )

    args = parser.parse_args()

    # Safety enforcement
    if args.spend_cap > config.MAX_TOTAL_SPEND_SOL:
        logger.error(f"Spend cap cannot exceed strict bounty limit of {config.MAX_TOTAL_SPEND_SOL} SOL!")
        sys.exit(1)

    rpc = SolanaRPCClient()
    engine = MeasurementEngine(
        rpc_client=rpc,
        is_live=args.live,
        spend_cap_sol=args.spend_cap
    )

    with open(args.data_file, "r", encoding="utf-8") as f:
        meta = json.load(f)
    validators = meta.get("benchmark_validators", [])

    logger.info(f"Loaded {len(validators)} target validators across client lineages.")
    logger.info(f"Execution Mode: {'🔴 LIVE MAINNET' if args.live else '🟢 DRY-RUN (SIMULATED & VERIFIED)'}")

    results = []
    current_slot = 461310000  # Realistic post-Alpenglow baseline slot

    for idx, val in enumerate(validators):
        target_slot = current_slot + (idx * 250)
        logger.info(f"[{idx+1}/{len(validators)}] Benchmarking {val['name']} ({val['client']} v{val['software_version']})")
        res = engine.run_priority_differential_test(val, target_slot)
        results.append(res)

    # Save raw benchmark output
    raw_path = os.path.join(config.RAW_MEASUREMENTS_DIR, "benchmark_cohort_results.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    logger.info(f"Saved raw measurement results to {raw_path}")

    if args.generate_report:
        gen = ReportGenerator(args.data_file, args.report_output)
        gen.generate(results)
        logger.info(f"Generated architectural research report at {args.report_output}")

    print("\nBenchmark completed successfully!")

if __name__ == "__main__":
    main()
