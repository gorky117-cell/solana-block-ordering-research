import unittest
import base58
from cryptography.hazmat.primitives.asymmetric import ed25519
from src.transaction_builder import (
    SolanaTransactionBuilder,
    encode_compact_u16,
    COMPUTE_BUDGET_PROGRAM_ID,
    MEMO_PROGRAM_ID
)

class TestTransactionBuilder(unittest.TestCase):
    def setUp(self):
        self.priv = ed25519.Ed25519PrivateKey.generate()
        self.pub_b58 = base58.b58encode(self.priv.public_key().public_bytes_raw()).decode("ascii")
        self.dummy_blockhash = base58.b58encode(b"\x01" * 32).decode("ascii")

    def test_compact_u16(self):
        self.assertEqual(encode_compact_u16(0), b"\x00")
        self.assertEqual(encode_compact_u16(1), b"\x01")
        self.assertEqual(encode_compact_u16(127), b"\x7f")
        self.assertEqual(encode_compact_u16(128), b"\x80\x01")
        self.assertEqual(encode_compact_u16(300), b"\xac\x02")

    def test_build_and_sign(self):
        builder = SolanaTransactionBuilder(self.priv)
        builder.set_compute_unit_limit(15_000)
        builder.set_compute_unit_price(25_000)
        builder.add_memo("InsideTheBlock::Experiment#1")

        sig_b58, wire_bytes = builder.build_and_sign(self.dummy_blockhash)
        
        # Verify wire format starts with 1 signature
        self.assertEqual(wire_bytes[0], 1)
        # Signature is 64 bytes
        sig = wire_bytes[1:65]
        self.assertEqual(base58.b58encode(sig).decode("ascii"), sig_b58)
        
        # Verify Ed25519 signature against message bytes
        msg_bytes = wire_bytes[65:]
        self.priv.public_key().verify(sig, msg_bytes)

    def test_signature_length(self):
        builder = SolanaTransactionBuilder(self.priv)
        builder.set_compute_unit_price(1_000)
        sig_b58, _ = builder.build_and_sign(self.dummy_blockhash)
        self.assertTrue(len(sig_b58) >= 86) # Standard base58 64-byte signature is 87-88 chars

if __name__ == "__main__":
    unittest.main()
