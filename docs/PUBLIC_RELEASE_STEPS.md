# Exact steps only you can finish

I finished the local Phase 1 packaging in
`C:\Users\chhab\Downloads\Github\chhabrashilin\research\resched`
(branch `tas-censoring-final`). Below is what still needs your browser, signature,
or accounts. Check every official page for current deadlines, fees, and quotas.

---

## A. Phase 0 — TAS 2026 camera-ready (today)

Upload files already built:

- PDF: `C:\Users\chhab\Downloads\TAS2026_Chhabra_camera_ready.pdf`
- Sources: `C:\Users\chhab\Downloads\TAS2026_Chhabra_sources.zip`
- Notes: `tas_camera_ready\CAMERA_READY_NOTES.txt` in the repo

Do this on the **AAAI CRC site** (not EasyChair), for paper **7658**:

1. Open the CRC camera-ready upload page from the editors' email.
2. Upload the PDF.
3. Upload the sources zip.
4. Download the copyright form. Sign **page 1 only** (signature + date). Upload it.
5. Enter metadata: title, author (Shilin Chhabra), affiliation, email, abstract
   (from `tas_camera_ready/main.tex`). Submit for editorial review.
6. Register for the symposium and book travel. An author must attend in person.
   Early rate was said to end **October 2**; **verify** the current rate page.
7. Save the editors' email addresses. Bring any formatting requests back to Cursor.

**Done when:** CRC shows PDF + sources + copyright + metadata submitted, and you
have a registration confirmation.

---

## B. GitHub public repo

**Already done from this session.** Live at:

https://github.com/chhabrashilin/invalid-is-not-failure

Local branch `tas-censoring-final` tracks `origin/main`. Only create the repo again if that URL 404s.

---

## C. Zenodo DOI

1. Sign in at https://zenodo.org (check current free login options: ORCID / GitHub / etc.).
2. Enable GitHub integration; turn on the switch for `invalid-is-not-failure`.
3. On GitHub → Releases → Draft a new release → tag `v0.1.0` → title
   `Invalid Is Not Failure v0.1.0` → Publish.
4. Wait for Zenodo to mint a DOI. Copy `https://doi.org/10.5281/...`.
5. Paste the DOI into `README.md` (Links table) and into the Reproduction
   paragraph of `extended_paper/main.tex`, then commit and push.

**Done when:** the DOI resolves to this release.

---

## D. Hugging Face dataset

1. Create a free account at https://huggingface.co and accept current terms.
2. In PowerShell:

```powershell
cd C:\Users\chhab\Downloads\Github\chhabrashilin\research\resched
pip install huggingface_hub
huggingface-cli login
python hf_dataset/pack_derived.py
python hf_dataset/upload.py --repo shilinc1/infra-censoring-derived
```

**Already done.** Live at:
https://huggingface.co/datasets/shilinc1/infra-censoring-derived

(HF account is `shilinc1`; GitHub account is `chhabrashilin`. That mismatch is fine.)

---

## E. Hugging Face Space (free Static; Gradio is gated)

Current HF policy: Gradio/Docker Spaces need a paid plan, except up to 2
ZeroGPU Gradio Spaces on some free personal accounts. Prefer **Static**.

1. Open https://huggingface.co/new-space as `shilinc1`.
2. Set:
   - Space name: `identified-intervals`
   - SDK: **Static** (not Gradio)
   - Visibility: Public
3. Upload both files from
   `spaces/identified_intervals_static/`:
   - `index.html`
   - `README.md`
4. Open the Space URL and confirm the example table appears.
5. Send the Space URL back so the README/paper links can be updated.

**Done when:** `https://huggingface.co/spaces/shilinc1/identified-intervals` loads
and Compute shows intervals.

---

## F. After B–E

1. Rebuild `extended_paper` PDF once the four links are real (no "pending" text).
2. Do **not** start Phase 2 until Phase 0 is submitted and Phase 1 links work.
3. Reply in chat with: CRC status, GitHub URL, Zenodo DOI, HF dataset URL, Space URL.

---

## What I cannot guarantee

Acceptance, scores, free-tier uptime, or that any venue will accept an extended
archival workshop paper. Always read the venue rules yourself.
