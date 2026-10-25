import struct
from typing import List, Tuple, Dict, Any, Optional
import base58
from cryptography.hazmat.primitives.asymmetric import ed25519

COMPUTE_BUDGET_PROGRAM_ID = "ComputeBudget111111111111111111111111111111"
SYSTEM_PROGRAM_ID = "11111111111111111111111111111111"
MEMO_PROGRAM_ID = "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr"

def encode_compact_u16(val: int) -> bytes:
    """Solana Compact-u16 variable length integer encoding."""
    out = bytearray()
    rem = val
    while True:
        elem = rem & 0x7F
        rem >>= 7
        if rem == 0:
            out.append(elem)
            break
        else:
            elem |= 0x80
            out.append(elem)
    return bytes(out)

class CompiledInstruction:
    def __init__(self, program_id_index: int, accounts: List[int], data: bytes):
        self.program_id_index = program_id_index
        self.accounts = accounts
        self.data = data

    def serialize(self) -> bytes:
        out = bytearray()
        out.append(self.program_id_index)
        out.extend(encode_compact_u16(len(self.accounts)))
        out.extend(bytes(self.accounts))
        out.extend(encode_compact_u16(len(self.data)))
        out.extend(self.data)
        return bytes(out)

class SolanaTransactionBuilder:
    def __init__(self, fee_payer_privkey: ed25519.Ed25519PrivateKey):
        self.fee_payer_privkey = fee_payer_privkey
        self.fee_payer_pubkey = fee_payer_privkey.public_key().public_bytes_raw()
        self.fee_payer_pubkey_b58 = base58.b58encode(self.fee_payer_pubkey).decode("ascii")
        self.instructions: List[Tuple[str, List[Tuple[str, bool, bool]], bytes]] = []

    def set_compute_unit_limit(self, units: int = 20_000) -> "SolanaTransactionBuilder":
        """ComputeBudget::SetComputeUnitLimit(units) [discriminant 0x02]"""
        data = struct.pack("<BI", 2, units)
        self.instructions.append((COMPUTE_BUDGET_PROGRAM_ID, [], data))
        return self

    def set_compute_unit_price(self, micro_lamports: int) -> "SolanaTransactionBuilder":
        """ComputeBudget::SetComputeUnitPrice(micro_lamports) [discriminant 0x03]"""
        data = struct.pack("<BQ", 3, micro_lamports)
        self.instructions.append((COMPUTE_BUDGET_PROGRAM_ID, [], data))
        return self

    def add_transfer(self, recipient_pubkey_b58: str, lamports: int) -> "SolanaTransactionBuilder":
        """SystemProgram::Transfer(from, to, lamports) [discriminant 0x02, 0x00, 0x00, 0x00]"""
        data = struct.pack("<II", 2, 0) + struct.pack("<Q", lamports)
        accounts = [
            (self.fee_payer_pubkey_b58, True, True),     # payer: writable, signer
            (recipient_pubkey_b58, True, False)          # recipient: writable, non-signer
        ]
        self.instructions.append((SYSTEM_PROGRAM_ID, accounts, data))
        return self

    def add_memo(self, memo_text: str) -> "SolanaTransactionBuilder":
        """Memo Program string annotation"""
        data = memo_text.encode("utf-8")
        accounts = [
            (self.fee_payer_pubkey_b58, False, True)    # signer
        ]
        self.instructions.append((MEMO_PROGRAM_ID, accounts, data))
        return self

    def build_and_sign(self, recent_blockhash_b58: str) -> Tuple[str, bytes]:
        """
        Compiles the message, signs with the fee payer private key,
        and returns (signature_b58, wire_bytes).
        """
        # Collect and order unique account keys
        # 1. fee payer (signer, writable)
        # 2. other signers, writable
        # 3. other signers, readonly
        # 4. non-signers, writable
        # 5. non-signers, readonly (including program IDs)
        
        signers_writable = [self.fee_payer_pubkey_b58]
        signers_readonly = []
        non_signers_writable = []
        non_signers_readonly = []

        def add_acc(acc_b58: str, is_writable: bool, is_signer: bool):
            if is_signer:
                if is_writable:
                    if acc_b58 not in signers_writable:
                        signers_writable.append(acc_b58)
                else:
                    if acc_b58 not in signers_readonly and acc_b58 not in signers_writable:
                        signers_readonly.append(acc_b58)
            else:
                if is_writable:
                    if acc_b58 not in non_signers_writable:
                        non_signers_writable.append(acc_b58)
                else:
                    if acc_b58 not in non_signers_readonly and acc_b58 not in non_signers_writable:
                        non_signers_readonly.append(acc_b58)

        # Collect program IDs and accounts
        for prog_id, accs, _ in self.instructions:
            add_acc(prog_id, is_writable=False, is_signer=False)
            for acc_b58, is_writable, is_signer in accs:
                add_acc(acc_b58, is_writable, is_signer)

        all_accounts = signers_writable + signers_readonly + non_signers_writable + non_signers_readonly
        account_index_map = {acc: i for i, acc in enumerate(all_accounts)}

        # Build Header
        num_required_signatures = len(signers_writable) + len(signers_readonly)
        num_readonly_signed_accounts = len(signers_readonly)
        num_readonly_unsigned_accounts = len(non_signers_readonly)
        header = bytes([
            num_required_signatures,
            num_readonly_signed_accounts,
            num_readonly_unsigned_accounts
        ])

        # Compile instructions
        compiled_ixs: List[CompiledInstruction] = []
        for prog_id, accs, data in self.instructions:
            prog_idx = account_index_map[prog_id]
            acc_indices = [account_index_map[a[0]] for a in accs]
            compiled_ixs.append(CompiledInstruction(prog_idx, acc_indices, data))

        # Assemble Message
        message = bytearray()
        message.extend(header)
        message.extend(encode_compact_u16(len(all_accounts)))
        for acc in all_accounts:
            message.extend(base58.b58decode(acc))
        message.extend(base58.b58decode(recent_blockhash_b58))
        message.extend(encode_compact_u16(len(compiled_ixs)))
        for c_ix in compiled_ixs:
            message.extend(c_ix.serialize())

        message_bytes = bytes(message)

        # Sign
        signature = self.fee_payer_privkey.sign(message_bytes)
        signature_b58 = base58.b58encode(signature).decode("ascii")

        # Assemble Wire Transaction
        wire = bytearray()
        wire.extend(encode_compact_u16(1)) # 1 signature
        wire.extend(signature)
        wire.extend(message_bytes)

        return signature_b58, bytes(wire)
