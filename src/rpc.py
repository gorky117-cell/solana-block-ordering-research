import time
import json
import logging
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional
from src.config import config

logger = logging.getLogger("SolanaRPC")

class SolanaRPCClient:
    def __init__(self, endpoints: Optional[List[str]] = None, timeout: int = 15):
        self.endpoints = endpoints or list(config.RPC_ENDPOINTS)
        self.current_ep_idx = 0
        self.timeout = timeout
        self._request_id = 1

    def _next_endpoint(self):
        self.current_ep_idx = (self.current_ep_idx + 1) % len(self.endpoints)
        logger.warning(f"Failing over to RPC endpoint: {self.endpoints[self.current_ep_idx]}")

    def call(self, method: str, params: Optional[List[Any]] = None, retries: int = 3) -> Any:
        params = params if params is not None else []
        payload = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params
        }
        self._request_id += 1
        data_bytes = json.dumps(payload).encode("utf-8")

        for attempt in range(retries):
            endpoint = self.endpoints[self.current_ep_idx]
            req = urllib.request.Request(
                endpoint,
                data=data_bytes,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "SolanaBlockOrderingResearcher/1.0"
                }
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    if "error" in resp_data:
                        err = resp_data["error"]
                        logger.error(f"RPC Error [{method}]: {err}")
                        raise RuntimeError(f"RPC Error: {err}")
                    return resp_data.get("result")
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
                logger.warning(f"RPC call failed on {endpoint} (attempt {attempt+1}/{retries}): {e}")
                self._next_endpoint()
                time.sleep(0.5 * (attempt + 1))
            except Exception as e:
                logger.error(f"Unexpected RPC exception: {e}")
                time.sleep(0.5)

        raise ConnectionError(f"All RPC endpoints failed for method: {method}")

    def get_slot(self, commitment: str = "finalized") -> int:
        return self.call("getSlot", [{"commitment": commitment}])

    def get_epoch_info(self, commitment: str = "finalized") -> Dict[str, Any]:
        return self.call("getEpochInfo", [{"commitment": commitment}])

    def get_latest_blockhash(self, commitment: str = "finalized") -> Dict[str, Any]:
        return self.call("getLatestBlockhash", [{"commitment": commitment}])

    def get_leader_schedule(self, slot: Optional[int] = None) -> Dict[str, List[int]]:
        params = []
        if slot is not None:
            params.append(slot)
        return self.call("getLeaderSchedule", params)

    def get_block(self, slot: int, commitment: str = "finalized") -> Optional[Dict[str, Any]]:
        params = [
            slot,
            {
                "encoding": "json",
                "transactionDetails": "full",
                "rewards": False,
                "commitment": commitment,
                "maxSupportedTransactionVersion": 0
            }
        ]
        try:
            return self.call("getBlock", params)
        except Exception as e:
            logger.warning(f"Could not fetch block for slot {slot}: {e}")
            return None

    def get_balance(self, pubkey: str, commitment: str = "finalized") -> int:
        res = self.call("getBalance", [pubkey, {"commitment": commitment}])
        return res.get("value", 0) if isinstance(res, dict) else 0

    def send_transaction(self, base64_or_base58_tx: str, encoding: str = "base58") -> str:
        params = [
            base64_or_base58_tx,
            {
                "encoding": encoding,
                "skipPreflight": True,
                "preflightCommitment": "processed"
            }
        ]
        return self.call("sendTransaction", params)

    def get_signature_statuses(self, signatures: List[str]) -> List[Optional[Dict[str, Any]]]:
        res = self.call("getSignatureStatuses", [signatures, {"searchTransactionHistory": True}])
        return res.get("value", []) if isinstance(res, dict) else []
