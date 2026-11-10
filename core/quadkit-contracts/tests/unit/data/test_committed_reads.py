"""Committed-read contracts describe adapters, not trusted implementation identity."""

from quadkit.contracts.data.sql.committed_reads import (
    CommittedReadGuardProtocol,
    CommittedReadState,
)


def test_states_and_structural_protocol_are_not_attestation() -> None:
    class Adapter:
        supports_committed_read_guard_v1 = False

        def committed_read_state(self) -> CommittedReadState:
            return CommittedReadState.UNSUPPORTED_PROVIDER

    assert isinstance(Adapter(), CommittedReadGuardProtocol)
    assert Adapter().supports_committed_read_guard_v1 is False
    assert not isinstance(object(), CommittedReadGuardProtocol)
    assert CommittedReadState.SAFE.value == "safe"
    assert len(CommittedReadState) == 5
