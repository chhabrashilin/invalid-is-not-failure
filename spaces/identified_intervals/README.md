---
title: Identified Intervals
emoji: 📊
colorFrom: gray
colorTo: blue
sdk: gradio
sdk_version: 4.44.0
app_file: app.py
pinned: false
license: mit
short_description: Identified success intervals and sharp rank intervals for agent leaderboards
---

# Identified intervals

Companion Space for *Invalid Is Not Failure* (TAS 2026).

Paste CSV columns `name,N,resolved,E,U` to get:

- identified intervals under strict and broad readings
- sharp rank intervals
- which pairwise orderings are identified by the published evidence

This Space does **not** implement bootstrap rank confidence sets (planned follow-up).
Check current Hugging Face Space free-tier limits before relying on uptime.
