import os
from dataclasses import dataclass
from typing import List

@dataclass(frozen=True)
class ResearchConfig:
    # Strict Bounty Constraint: Maximum total spend cap in SOL
    MAX_TOTAL_SPEND_SOL: float = 0.05
    LAMPORTS_PER_SOL: int = 1_000_000_000
    
    # Base fee per signature on Solana
    BASE_SIGNATURE_FEE_LAMPORTS: int = 5_000
    
    # Priority fee testing tiers (in micro-lamports per compute unit)
    PRIORITY_FEE_TIERS = {
        "ZERO": 0,
        "LOW": 1_000,          # 0.0002 lamports / CU
        "MEDIUM": 25_000,      # 0.005 lamports / CU
        "HIGH": 100_000,       # 0.02 lamports / CU
        "ULTRA": 500_000       # 0.1 lamports / CU
    }
    
    # Default compute unit limit per test transaction
    DEFAULT_COMPUTE_UNIT_LIMIT: int = 20_000
    
    # Primary & Failover RPC Endpoints
    RPC_ENDPOINTS: List[str] = (
        os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com"),
        "https://solana-rpc.publicnode.com",
        "https://api.mainnet-beta.solana.com"
    )
    
    # Slots per leader window in Solana consensus
    LEADER_WINDOW_SLOTS: int = 4
    
    # Nominal slot duration in milliseconds
    NOMINAL_SLOT_MS: int = 400
    
    # Post-Alpenglow reference cutoff (Oct 21, 2026)
    ALPENGLOW_CUTOFF_DATE: str = "2026-10-21T00:00:00Z"
    
    # Raw measurement data directory
    DATA_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    RAW_MEASUREMENTS_DIR: str = os.path.join(DATA_DIR, "raw_measurements")

config = ResearchConfig()
