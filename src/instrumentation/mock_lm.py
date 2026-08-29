"""Deterministic mock language model for infrastructure validation.

WHY THIS EXISTS
---------------
docs/research_log.md contains no `PHASE_0_API_BUDGET_USD` line, so paid API
calls are forbidden (Phase 0 cost rule). A paid model is not needed to prove
logging, schema validity, environment lifecycle, checkpointing, restoration or
evaluator integration -- which is all Phase 0 claims to test.

The mock emits a fixed, seeded sequence of bash commands. It is NOT an agent
and produces NO scientific result. Any run using it is flagged in
`SessionMeta.model_id` with the `mock:` prefix so it can never be mistaken for
a real trajectory in later analysis.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field


MOCK_MODEL_PREFIX = "mock:"


@dataclass
class MockResponse:
    """One mocked model response."""

    command: str
    raw_text: str
    is_submit: bool = False


@dataclass
class ScriptedMockLM:
    """Replays a fixed command list. Fully deterministic.

    Args:
        commands: bash commands to emit, in order.
        model_name: recorded in the trajectory; always prefixed with ``mock:``.
    """

    commands: list[str]
    model_name: str = "scripted-v1"
    _i: int = field(default=0, init=False)

    @property
    def model_id(self) -> str:
        return f"{MOCK_MODEL_PREFIX}{self.model_name}"

    def reset(self) -> None:
        self._i = 0

    def next_response(self, _messages: list[dict] | None = None) -> MockResponse:
        if self._i >= len(self.commands):
            return MockResponse(command="", raw_text="TASK_COMPLETE", is_submit=True)
        cmd = self.commands[self._i]
        self._i += 1
        return MockResponse(
            command=cmd,
            raw_text=f"I will run the following command.\n```bash\n{cmd}\n```",
            is_submit=False,
        )


@dataclass
class StochasticMockLM:
    """Seeded mock that chooses among candidate commands.

    Used for the same-condition fork test (Phase 0 Step 10): two continuations
    from one checkpoint under identical nominal conditions. With distinct seeds
    it exercises the divergence-measurement path; with identical seeds it must
    produce byte-identical trajectories, which is a determinism test.
    """

    candidates: list[list[str]]
    seed: int
    model_name: str = "stochastic-v1"
    _rng: random.Random = field(init=False)
    _i: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)

    @property
    def model_id(self) -> str:
        return f"{MOCK_MODEL_PREFIX}{self.model_name}"

    def reset(self) -> None:
        self._rng = random.Random(self.seed)
        self._i = 0

    def next_response(self, _messages: list[dict] | None = None) -> MockResponse:
        if self._i >= len(self.candidates):
            return MockResponse(command="", raw_text="TASK_COMPLETE", is_submit=True)
        options = self.candidates[self._i]
        self._i += 1
        cmd = self._rng.choice(options)
        return MockResponse(
            command=cmd,
            raw_text=f"```bash\n{cmd}\n```",
            is_submit=False,
        )
