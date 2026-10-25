import os
import time
import json
import logging
from typing import Dict, List, Any, Optional
from cryptography.hazmat.primitives.asymmetric import ed25519
import base58

from src.config import config
from src.rpc import SolanaRPCClient
from src.transaction_builder import SolanaTransactionBuilder
from src.leader_tracker import LeaderScheduleTracker
from src.block_analyzer import BlockAnalyzer

logger = logging.getLogger("MeasurementEngine")

class SpendCapExceededError(Exception):
    """Raised when an operation would exceed the strict 0.05 SOL spend cap."""
    pass

class MeasurementEngine:
    def __init__(
        self,
        rpc_client: Optional[SolanaRPCClient] = None,
        is_live: bool = False,
        spend_cap_sol: float = config.MAX_TOTAL_SPEND_SOL,
        keypair_b58: Optional[str] = None
    ):
        self.rpc = rpc_client or SolanaRPCClient()
        self.tracker = LeaderScheduleTracker(self.rpc)
        self.analyzer = BlockAnalyzer()
        self.is_live = is_live
        self.spend_cap_sol = min(spend_cap_sol, config.MAX_TOTAL_SPEND_SOL)
        self.spend_cap_lamports = int(self.spend_cap_sol * config.LAMPORTS_PER_SOL)
        self.cumulative_spent_lamports = 0

        # Load or generate research keypair
        if keypair_b58:
            seed = base58.b58decode(keypair_b58)[:32]
            self.privkey = ed25519.Ed25519PrivateKey.from_private_bytes(seed)
        else:
            self.privkey = ed25519.Ed25519PrivateKey.generate()

        self.pubkey_bytes = self.privkey.public_key().public_bytes_raw()
        self.pubkey_b58 = base58.b58encode(self.pubkey_bytes).decode("ascii")
        logger.info(f"Measurement Engine initialized | Mode: {'LIVE' if is_live else 'DRY_RUN'} | Fee Payer: {self.pubkey_b58} | Spend Cap: {self.spend_cap_sol} SOL")

    def check_spend_limit(self, additional_lamports: int):
        """Strictly halts execution if spend cap would be breached."""
        if self.cumulative_spent_lamports + additional_lamports > self.spend_cap_lamports:
            raise SpendCapExceededError(
                f"Spend limit of {self.spend_cap_sol} SOL ({self.spend_cap_lamports} lamports) "
                f"would be exceeded by spend of {additional_lamports} lamports! (Current: {self.cumulative_spent_lamports})"
            )

    def run_priority_differential_test(
        self,
        validator_meta: Dict[str, Any],
        target_slot: int,
        low_fee_tier: str = "LOW",
        high_fee_tier: str = "HIGH"
    ) -> Dict[str, Any]:
        """
        Executes a paired differential measurement:
        Tx1 (Low Fee): e.g. 1,000 micro-lamports/CU
        Tx2 (High Fee): e.g. 100,000 micro-lamports/CU
        Dispatches both during the validator's leader window and measures relative block position.
        """
        low_price = config.PRIORITY_FEE_TIERS[low_fee_tier]
        high_price = config.PRIORITY_FEE_TIERS[high_fee_tier]
        est_cost_lamports = (config.BASE_SIGNATURE_FEE_LAMPORTS * 2) + 2000

        self.check_spend_limit(est_cost_lamports)

        val_name = validator_meta.get("name", "UnknownValidator")
        val_client = validator_meta.get("client", "UnknownClient")
        val_pubkey = validator_meta.get("node_pubkey")

        logger.info(f"Preparing differential test for [{val_client}] {val_name} (Slot: {target_slot})")

        if not self.is_live:
            # DRY-RUN SIMULATION
            # Construct mock valid wire transactions to verify serialization
            dummy_blockhash = base58.b58encode(b"\x02" * 32).decode("ascii")
            
            b1 = SolanaTransactionBuilder(self.privkey)
            b1.set_compute_unit_limit(20_000)
            b1.set_compute_unit_price(low_price)
            b1.add_memo(f"InsideBlock::TestLowFee::{val_name}::{target_slot}")
            sig1, _ = b1.build_and_sign(dummy_blockhash)

            b2 = SolanaTransactionBuilder(self.privkey)
            b2.set_compute_unit_limit(20_000)
            b2.set_compute_unit_price(high_price)
            b2.add_memo(f"InsideBlock::TestHighFee::{val_name}::{target_slot}")
            sig2, _ = b2.build_and_sign(dummy_blockhash)

            # Simulated block receipt adhering to client architecture
            mock_metrics = self._simulate_client_ordering(val_client, sig1, sig2, target_slot, low_price, high_price)
            return mock_metrics

        # LIVE EXECUTION
        recent_bh_info = self.rpc.get_latest_blockhash()
        blockhash = recent_bh_info["blockhash"]

        # Build and dispatch Tx 1 (Low Fee)
        b1 = SolanaTransactionBuilder(self.privkey)
        b1.set_compute_unit_limit(20_000)
        b1.set_compute_unit_price(low_price)
        b1.add_memo(f"InsideBlock::Live::{val_name}::{target_slot}::Low")
        sig1, wire1 = b1.build_and_sign(blockhash)

        # Build and dispatch Tx 2 (High Fee)
        b2 = SolanaTransactionBuilder(self.privkey)
        b2.set_compute_unit_limit(20_000)
        b2.set_compute_unit_price(high_price)
        b2.add_memo(f"InsideBlock::Live::{val_name}::{target_slot}::High")
        sig2, wire2 = b2.build_and_sign(blockhash)

        # Dispatch
        tx1_b58 = base58.b58encode(wire1).decode("ascii")
        tx2_b58 = base58.b58encode(wire2).decode("ascii")

        self.rpc.send_transaction(tx1_b58)
        time.sleep(0.015) # 15ms arrival differential
        self.rpc.send_transaction(tx2_b58)

        self.cumulative_spent_lamports += est_cost_lamports
        logger.info(f"Dispatched live test transactions. Signatures: {sig1[:16]}... and {sig2[:16]}...")

        # Wait for block finalization
        time.sleep(5.0)
        block_data = self.rpc.get_block(target_slot)
        if not block_data:
            return {"status": "SLOT_NOT_FINALIZED_YET", "sig_low": sig1, "sig_high": sig2}

        # Analyze
        analysis = self.analyzer.analyze_block(block_data, [sig1, sig2])
        diff = self.analyzer.compute_differential_metrics(analysis, sig1, sig2)
        diff["validator"] = val_name
        diff["client"] = val_client
        diff["slot"] = target_slot
        return diff

    def _simulate_client_ordering(
        self,
        client: str,
        sig1: str,
        sig2: str,
        slot: int,
        low_price: int,
        high_price: int
    ) -> Dict[str, Any]:
        """
        Calculates deterministically modeled block positions based on
        established client scheduler mechanics (Agave Central Scheduler vs
        Jito vs Frankendancer vs Legacy Multi-thread).
        """
        total_txs_in_block = 1850
        
        if "Frankendancer" in client:
            # Frankendancer: Microsecond fd_pack ordering. High fee strictly placed in early batch.
            idx_high = 42
            idx_low = 612
            adherence = "STRICT_FEE_PRIORITY"
            determinism = 0.96
        elif "Jito" in client:
            # Jito: Central scheduler + bundles. Non-bundle TPU high fee ordered early, moderate thread jitter.
            idx_high = 118
            idx_low = 845
            adherence = "FEE_PRIORITY_WITH_CHANNEL_JITTER"
            determinism = 0.88
        elif "Agave" in client:
            # Agave Central Scheduler: Prio-Graph lock resolution. High fee prioritized, minor entry boundary drift.
            idx_high = 165
            idx_low = 790
            adherence = "FEE_PRIORITY_LOCK_DAG"
            determinism = 0.84
        else:
            # Native / Experimental: Multi-threaded thread race condition.
            idx_high = 410
            idx_low = 430
            adherence = "PARTIAL_PRIORITY_FIFO_NOISE"
            determinism = 0.65

        return {
            "validator_client": client,
            "slot": slot,
            "total_transactions_in_block": total_txs_in_block,
            "sig_low_fee": sig1,
            "sig_high_fee": sig2,
            "low_fee_micro_lamports_per_cu": low_price,
            "high_fee_micro_lamports_per_cu": high_price,
            "idx_low_fee": idx_low,
            "idx_high_fee": idx_high,
            "delta_position": idx_high - idx_low,
            "high_fee_landed_first": True,
            "rule_observed": adherence,
            "determinism_score": determinism,
            "mode": "DRY_RUN_VERIFIED"
        }
