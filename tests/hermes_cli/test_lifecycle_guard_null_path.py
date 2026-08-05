"""Regression tests for the embedded-NUL path crash in lifecycle_guard (#76762).

`os.open(path, flags)` raises ``ValueError: embedded null character in path``
when a referenced-script path contains a NUL byte (a binary's decoded contents
tokenized as a path). The guard's ``except OSError`` did not catch it, so the
exception escaped, aborted the calling tool, and left the gateway's restart
drain waiting on a zombie session forever ("restarting" loop).

The fix widens the guard to ``except (OSError, ValueError)`` so a NUL path is
treated as "nothing to scan" (``(None, False)``), matching the intent already
documented at the binary-detection branch.
"""

from pathlib import Path

from cron.lifecycle_guard import (
    _contains_unsafe_gateway_action,
    _read_referenced_script,
)


class TestReadReferencedScriptNullPath:
    """``_read_referenced_script`` must not raise on a NUL-byte path (#76762)."""

    def test_null_byte_path_returns_nothing_to_scan(self):
        # os.open raises ValueError: embedded null character in path.
        result = _read_referenced_script(Path("/tmp/foo\x00bar.sh"))
        assert result == (None, False)

    def test_null_byte_path_with_extension_variants(self):
        for suffix in (".sh", ".py", ".bash", ""):
            path = Path(f"/etc/cron.d/payload\x00{suffix}")
            assert _read_referenced_script(path) == (None, False)


class TestContainsUnsafeNullPath:
    """Recursion entry must also swallow the NUL-path ValueError (#76762)."""

    def test_command_referencing_null_path_does_not_crash(self):
        # A command whose referenced-script token contains a NUL must not
        # raise; it should fall through to a benign result.
        cmd = "/bin/bash /home/hermes/.hermes/scripts/ops\x00helper.sh"
        # Raises nothing; returns a bool.
        result = _contains_unsafe_gateway_action(cmd, cwd="/tmp", depth=0, visited=set())
        assert isinstance(result, bool)
