# Final citation audit — TAS 2026 submission

Every entry checked against a canonical source (publisher/proceedings > official
project/dataset page > arXiv). No entry rests on a search snippet. Audited
2026-09-05.

| key | manuscript form | canonical source | authors | title | year | venue | id / revision | supports | status |
|---|---|---|---|---|---|---|---|---|---|
| `yao2025taubench` | Yao et al. (2025) | proceedings.iclr.cc paper page | Yao, Shinn, Razavi, Narasimhan | τ-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains | 2025 | **ICLR** | proceedings.iclr.cc 2025 hash 1b126cc3… | secondary corpus benchmark | **FIXED** (was arXiv 2406.12045, 2024) |
| `nebius2024trajectories` | (Nebius 2024) | HF API `createdAt` | Nebius | SWE-agent-trajectories | **2024** | HF dataset | rev `68195a14…`, CC-BY-4.0 | primary corpus | **FIXED** (was 2025) |
| `agentsuite2026taubench` | (AgentSuite 2026) | HF dataset card + API | AgentSuite | tau-bench-trajectories | 2026 | HF dataset | rev `382e57d1…` | secondary corpus | **FIXED** (note now describes the dataset, not our analysis) |
| `moghadasi2026disclose` | Naser Moghadasi and Ghaderi (2026) | arXiv abs page | **Mahdi Naser Moghadasi**, Faezeh Ghaderi | What Twelve LLM Agent Benchmark Papers Disclose About Themselves | 2026 | arXiv | 2605.21404 | limited disclosure in agent benchmark papers | **FIXED** (family name braced) |
| `jimenez2024swebench` | (Jimenez et al. 2024) | ICLR 2024 | Jimenez et al. | SWE-bench: Can Language Models Resolve Real-World GitHub Issues? | 2024 | **ICLR** | arXiv 2310.06770 | benchmark lineage | PASS (already refereed) |
| `yang2024sweagent` | (Yang et al. 2024) | NeurIPS 2024 | Yang et al. | SWE-agent: Agent-Computer Interfaces… | 2024 | **NeurIPS** | arXiv 2405.15793 | scaffold lineage | PASS (already refereed) |
| `zhao2026failure` | Zhao et al. (2026) | arXiv | Zhao, Li, Li, Zhao, Barr, Sarro, Ye | Failure as a Process | 2026 | arXiv | 2607.09510 | failure over complete trajectories | PASS |
| `ruan2026doomed` | Ruan et al. (2026) | arXiv | Ruan, Huang, Zhou, Wei, Wang, Sun | Doomed from the Start | 2026 | arXiv | 2607.06503 | early abort = censoring mechanism | PASS |
| `li2026early` | Li et al. (2026) | arXiv | Li, Yan, Wu, Liang, Yuan, Liu, Yang | Early Diagnosis of Wasted Computation… | 2026 | arXiv | 2606.01365 | failure-aware observability; runs w/o usable answer | PASS (wording weakened, see below) |
| `gonuguntla2026replay` | Gonuguntla (2026) | arXiv | **Ashritha Gonuguntla (single author)** | The Replay Gap | 2026 | arXiv | 2608.08239 | static replay scores a counterfactual world | **FIXED** ("show" → "shows") |
| `wang2026interface` | Wang (2026) | arXiv | **Wenbo Wang (single author)** | Interface-Induced Trajectory Censoring | 2026 | arXiv | 2609.03966 | "censoring" = interface output suppression | PASS ("uses", singular) |
| `raghu2026proper` | Raghu, Pandey, and Pandey (2026) | arXiv | Raghu, Pandey, Pandey | Proper Scoring Rules for Agentic Uncertainty Quantification | 2026 | arXiv | 2605.24756 | administrative censoring, no IPCW | PASS |
| `zhu2026guardrails` | Zhu and Chang (2026) | arXiv | Zhu, Chang | When Guardrails Look Effective | 2026 | arXiv | 2609.01519 | construct-validity contract | PASS |
| `chen2026judge` | Chen et al. (2026) | arXiv | Chen, Chen, Lin, Vong | A Judge Should Know What Changed | 2026 | arXiv | 2608.24419 | judge-side construct validity | PASS |
| `weidinger2025evalscience` | Weidinger et al. (2025) | arXiv | Weidinger et al. (10 authors) | Toward an Evaluation Science for Generative AI Systems | 2025 | arXiv | 2503.05336 | evaluation-science norms | PASS |
| `kapoor2024agentsthatmatter` | Kapoor et al. (2024) | arXiv | Kapoor, Stroebl, Siegel, Nadgir, Narayanan | AI Agents That Matter | 2024 | arXiv | 2407.01502 | agent benchmarking methodology | PASS |
| `horvitz1952generalization` | Horvitz and Thompson (1952) | JASA | Horvitz, Thompson | A Generalization of Sampling Without Replacement… | 1952 | JASA 47(260):663–685 | HT estimator | PASS |
| `robins1994estimation` | Robins, Rotnitzky, and Zhao (1994) | JASA | Robins, Rotnitzky, Zhao | Estimation of Regression Coefficients When Some Regressors Are Not Always Observed | 1994 | JASA 89(427):846–866 | IPCW; consistency under estimated weights | PASS |
| `manski1990nonparametric` | Manski (1990) | AER | Manski | Nonparametric Bounds on Treatment Effects | 1990 | AER 80(2):319–323 | worst-case identification bounds | PASS |

**Totals:** 19 entries, 19 cited, 0 uncited, 0 duplicates, 0 undefined
citations in the compiled PDF.

## Claim/citation mismatches fixed

1. **`gonuguntla2026replay`** — single author. "Gonuguntla (2026) show" → **"shows"**.
2. **`li2026early`** — our previous phrasing ("encounter, but do not model, a
   missing-outcome population") attributed our framing to them. Replaced with:
   *"study failure-aware observability, including runs producing no usable
   answer, but do not formulate infrastructure termination as a missing-outcome
   identification problem."*
3. **`wang2026interface`** — single author; verb already singular ("uses").
4. **`agentsuite2026taubench`** — the manuscript previously implied 29 × 165.
   Corrected to *"from 30 per-model files (29 distinct model identifiers, since
   one identifier appears in two files), with 165 tasks per file"*. The
   bibliography note now describes the dataset only.

## Deviations from the instructed corrections, with evidence

- **Naser Moghadasi is NOT hyphenated.** The instruction specified
  "Naser-Moghadasi". The canonical arXiv metadata for 2605.21404 lists
  **"Mahdi Naser Moghadasi"** (spaces, no hyphen). Canonical metadata governs,
  so we keep the unhyphenated form and instead brace the compound family name —
  `author = {{Naser Moghadasi}, Mahdi and Ghaderi, Faezeh}` — so BibTeX cannot
  split it. Renders "Naser Moghadasi and Ghaderi (2026)", verified in the PDF.
- **Nebius release date.** The instruction said December 20, 2024. The HF API
  reports `createdAt` 2024-12-08 and `lastModified` 2024-12-23. Either way the
  year is **2024**, which is what we now cite; we do not assert an exact day.

## Rendering defects found and fixed

- **τ rendered as "au"** in the bibliography. Root cause was *not* BibTeX's tie
  accent: an earlier automated edit had written a literal **tab character** into
  `references.bib` in place of `\t`. Repaired; the file now contains zero tab
  characters and the entry renders "τ-bench" correctly in the compiled PDF.
