import json
import logging
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger("BlockAnalyzer")

class BlockAnalyzer:
    def __init__(self):
        pass

    def analyze_block(
        self,
        block_data: Dict[str, Any],
        target_signatures: List[str]
    ) -> Dict[str, Any]:
        """
        Analyzes transaction ordering within a single confirmed Solana block.
        """
        transactions = block_data.get("transactions", [])
        slot = block_data.get("parentSlot", 0) + 1  # or actual slot from query context
        block_time = block_data.get("blockTime")
        block_height = block_data.get("blockHeight")
        total_txs = len(transactions)

        sig_positions = {}
        for idx, tx_entry in enumerate(transactions):
            tx_obj = tx_entry.get("transaction", {})
            signatures = tx_obj.get("signatures", [])
            for sig in signatures:
                if sig in target_signatures:
                    meta = tx_entry.get("meta", {})
                    cu_consumed = meta.get("computeUnitsConsumed", 0)
                    fee_paid = meta.get("fee", 5000)
                    status_err = meta.get("err")

                    sig_positions[sig] = {
                        "index_in_block": idx,
                        "relative_position_pct": round((idx / max(1, total_txs)) * 100, 2),
                        "compute_units_consumed": cu_consumed,
                        "fee_lamports": fee_paid,
                        "status": "SUCCESS" if status_err is None else f"ERROR: {status_err}"
                    }

        return {
            "total_transactions_in_block": total_txs,
            "block_time": block_time,
            "block_height": block_height,
            "matched_targets": sig_positions
        }

    def compute_differential_metrics(
        self,
        analysis_result: Dict[str, Any],
        tx_low_sig: str,
        tx_high_sig: str
    ) -> Dict[str, Any]:
        """
        Computes ordering metrics between low-fee and high-fee transaction pairs.
        """
        targets = analysis_result.get("matched_targets", {})
        low_data = targets.get(tx_low_sig)
        high_data = targets.get(tx_high_sig)

        if not low_data or not high_data:
            return {
                "pair_landed_same_block": False,
                "missing_sig": tx_low_sig if not low_data else tx_high_sig
            }

        idx_low = low_data["index_in_block"]
        idx_high = high_data["index_in_block"]
        delta_position = idx_high - idx_low

        # If idx_high < idx_low, high-fee landed EARLIER in the block
        high_fee_landed_first = (idx_high < idx_low)

        return {
            "pair_landed_same_block": True,
            "idx_low_fee": idx_low,
            "idx_high_fee": idx_high,
            "delta_position": delta_position,
            "high_fee_landed_first": high_fee_landed_first,
            "rule_adherence": "FEE_PRIORITY" if high_fee_landed_first else "FIFO_OR_THREAD_JITTER",
            "low_pct": low_data["relative_position_pct"],
            "high_pct": high_data["relative_position_pct"]
        }
