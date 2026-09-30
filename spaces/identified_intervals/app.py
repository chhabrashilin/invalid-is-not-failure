"""
Identified intervals and sharp rank intervals for leaderboard submissions.

Implements Proposition (sharp rank intervals) from:
  Invalid Is Not Failure (TAS 2026 / extended preprint).

Input CSV columns (header required):
  name,N,resolved,E,U
where
  N        = number of tasks
  resolved = number resolved (successes)
  E        = evaluation-censored / infrastructure-invalid runs (strict missing)
  U        = unattributable runs (added under the broad reading)

Strict interval:  [resolved/N, (resolved+E)/N]
Broad interval:   [resolved/N, (resolved+E+U)/N]
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass

import numpy as np

EXAMPLE = """name,N,resolved,E,U
agent_a,500,350,10,5
agent_b,500,340,0,20
agent_c,500,330,15,0
agent_d,500,300,0,0
"""


@dataclass
class Row:
    name: str
    n: int
    resolved: int
    e: int
    u: int

    @property
    def lo(self) -> float:
        return self.resolved / self.n

    @property
    def hi_strict(self) -> float:
        return (self.resolved + self.e) / self.n

    @property
    def hi_broad(self) -> float:
        return (self.resolved + self.e + self.u) / self.n


def parse_csv(text: str) -> list[Row]:
    text = (text or "").strip()
    if not text:
        raise ValueError("Paste a CSV with header name,N,resolved,E,U")
    reader = csv.DictReader(io.StringIO(text))
    required = {"name", "N", "resolved", "E", "U"}
    if reader.fieldnames is None or required - {h.strip() for h in reader.fieldnames}:
        raise ValueError("CSV must have columns: name,N,resolved,E,U")
    rows: list[Row] = []
    for i, raw in enumerate(reader, start=2):
        try:
            row = Row(
                name=str(raw["name"]).strip(),
                n=int(raw["N"]),
                resolved=int(raw["resolved"]),
                e=int(raw["E"]),
                u=int(raw["U"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Bad row {i}: {exc}") from exc
        if row.n <= 0:
            raise ValueError(f"Row {i}: N must be positive")
        if min(row.resolved, row.e, row.u) < 0:
            raise ValueError(f"Row {i}: counts must be non-negative")
        if row.resolved + row.e + row.u > row.n:
            raise ValueError(f"Row {i}: resolved+E+U cannot exceed N")
        rows.append(row)
    if not rows:
        raise ValueError("CSV has a header but no data rows")
    return rows


def rank_intervals(lo: np.ndarray, hi: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Best and worst ranks (1-based) from identified intervals; Prop. sharp ranks."""
    n = len(lo)
    best = 1 + (lo[None, :] > hi[:, None]).sum(axis=1)
    # worst: how many others can beat me (their hi > my lo), excluding self
    worst = 1 + ((hi[None, :] > lo[:, None]) & ~np.eye(n, dtype=bool)).sum(axis=1)
    return best.astype(int), worst.astype(int)


def identified_orderings(lo: np.ndarray, hi: np.ndarray) -> list[tuple[int, int]]:
    """Pairs (i,j) with i identified above j: lo[i] > hi[j]."""
    out = []
    n = len(lo)
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            if lo[i] > hi[j]:
                out.append((i, j))
    return out


def analyse(text: str) -> tuple[str, str, str]:
    try:
        rows = parse_csv(text)
    except ValueError as exc:
        return str(exc), "", ""

    order = sorted(range(len(rows)), key=lambda i: -rows[i].lo)
    rows = [rows[i] for i in order]

    lo = np.array([r.lo for r in rows], dtype=float)
    hi_s = np.array([r.hi_strict for r in rows], dtype=float)
    hi_b = np.array([r.hi_broad for r in rows], dtype=float)
    best_s, worst_s = rank_intervals(lo, hi_s)
    best_b, worst_b = rank_intervals(lo, hi_b)

    table_lines = [
        "name | score (lo) | hi_strict | hi_broad | rank_strict | rank_broad",
        "---|---|---|---|---|---",
    ]
    for i, r in enumerate(rows):
        table_lines.append(
            f"{r.name} | {100*r.lo:.2f}% | {100*r.hi_strict:.2f}% | "
            f"{100*r.hi_broad:.2f}% | [{best_s[i]}, {worst_s[i]}] | "
            f"[{best_b[i]}, {worst_b[i]}]"
        )
    table = "\n".join(table_lines)

    def pair_block(label: str, hi: np.ndarray) -> str:
        pairs = identified_orderings(lo, hi)
        lines = [f"### {label}: {len(pairs)} identified orderings (lo_A > hi_B)"]
        if not pairs:
            lines.append("(none)")
        else:
            for i, j in pairs:
                lines.append(
                    f"- {rows[i].name} above {rows[j].name} "
                    f"({100*lo[i]:.2f}% > {100*hi[j]:.2f}%)"
                )
        return "\n".join(lines)

    pairs_md = pair_block("Strict reading", hi_s) + "\n\n" + pair_block(
        "Broad reading", hi_b
    )

    notes = (
        "Strict: only E is missing. Broad: E and U are missing. "
        "Leaderboard score is the lower endpoint. "
        "Rank intervals are sharp under the paper's identification argument. "
        "This tool does not add sampling (bootstrap) uncertainty; that is Phase 2A."
    )
    return table, pairs_md, notes


def build_ui():
    import gradio as gr

    with gr.Blocks(title="Identified intervals") as demo:
        gr.Markdown(
            "# Identified intervals and sharp rank intervals\n"
            "Paste leaderboard counts. Columns: `name,N,resolved,E,U`.\n"
            "From *Invalid Is Not Failure* (TAS 2026)."
        )
        inp = gr.Textbox(lines=12, label="CSV", value=EXAMPLE)
        btn = gr.Button("Compute", variant="primary")
        out_table = gr.Markdown(label="Intervals")
        out_pairs = gr.Markdown(label="Identified orderings")
        out_notes = gr.Markdown()
        btn.click(analyse, inputs=inp, outputs=[out_table, out_pairs, out_notes])
        demo.load(analyse, inputs=inp, outputs=[out_table, out_pairs, out_notes])
    return demo


if __name__ == "__main__":
    build_ui().launch()
