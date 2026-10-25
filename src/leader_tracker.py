import logging
from typing import Dict, List, Optional, Tuple, Any
from src.rpc import SolanaRPCClient
from src.config import config

logger = logging.getLogger("LeaderTracker")

class LeaderScheduleTracker:
    def __init__(self, rpc_client: SolanaRPCClient):
        self.rpc = rpc_client
        self.epoch_info: Dict[str, Any] = {}
        self.leader_schedule: Dict[str, List[int]] = {}
        self.epoch: int = 0
        self.first_slot: int = 0

    def refresh_epoch_data(self) -> None:
        """Fetches current epoch info and leader schedule."""
        self.epoch_info = self.rpc.get_epoch_info()
        self.epoch = self.epoch_info.get("epoch", 0)
        self.first_slot = self.epoch_info.get("absoluteSlot", 0) - self.epoch_info.get("slotIndex", 0)
        logger.info(f"Epoch {self.epoch} | First Slot: {self.first_slot} | Current Slot: {self.epoch_info.get('absoluteSlot')}")

        try:
            self.leader_schedule = self.rpc.get_leader_schedule()
            logger.info(f"Loaded leader schedule with {len(self.leader_schedule)} validator schedules")
        except Exception as e:
            logger.error(f"Failed to fetch full leader schedule: {e}")
            self.leader_schedule = {}

    def get_validator_leader_slots(self, node_pubkey: str) -> List[int]:
        """Returns all absolute slots assigned to node_pubkey in current epoch."""
        relative_offsets = self.leader_schedule.get(node_pubkey, [])
        return [self.first_slot + offset for offset in relative_offsets]

    def get_upcoming_windows(
        self,
        node_pubkey: str,
        current_slot: Optional[int] = None,
        max_lookahead_slots: int = 500
    ) -> List[Tuple[int, int]]:
        """
        Returns list of (start_slot, end_slot) 4-slot leader windows
        that occur between current_slot and current_slot + max_lookahead_slots.
        """
        if current_slot is None:
            current_slot = self.rpc.get_slot()

        slots = self.get_validator_leader_slots(node_pubkey)
        future_slots = [s for s in slots if s >= current_slot and s <= current_slot + max_lookahead_slots]
        
        # Group consecutive 4 slots into windows
        windows = []
        if not future_slots:
            return windows

        # Solana consensus schedules leaders in contiguous runs of 4 slots
        i = 0
        while i < len(future_slots):
            start = future_slots[i]
            # Find contiguous end
            j = i
            while j + 1 < len(future_slots) and future_slots[j + 1] == future_slots[j] + 1:
                j += 1
            windows.append((start, future_slots[j]))
            i = j + 1

        return windows

    def is_in_leader_window(self, node_pubkey: str, slot: int) -> bool:
        """Returns True if the specified slot is assigned to node_pubkey."""
        relative_offset = slot - self.first_slot
        if relative_offset < 0:
            return False
        validator_offsets = self.leader_schedule.get(node_pubkey, [])
        return relative_offset in validator_offsets
