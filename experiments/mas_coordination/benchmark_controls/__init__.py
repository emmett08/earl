"""Frozen intermediate execution modes, excluded from the installed EAL package."""
from pathlib import Path

from .snapshot.lab_mcp import LabMCPTransport as _SnapshotTransport


ROOT = Path(__file__).resolve().parents[3]


def make_control(arm, runtime, database, *, binary=None):
    """Select an explicitly named historical mode for benchmarks/equivalence tests."""
    if arm not in {"persistent_mcp", "persistent_mcp_codec"}:
        raise ValueError("Not a frozen intermediate transport arm")
    if binary is None:
        binary = (Path(runtime) / "rust-protocol/target/release/mas-protocol-codec"
                  if arm == "persistent_mcp"
                  else ROOT / "src/eal/coordination/rust_codec/target/release/mas-protocol-codec")
    return _SnapshotTransport(runtime, database, binary=binary,
                              codec_mode="oneshot" if arm == "persistent_mcp" else "persistent",
                              admission_mode="roundtrip")
