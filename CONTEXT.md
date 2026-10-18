# CONTEXT.md

Single-context glossary for BrotatoStratGuide (wayfinder map #33, ticket: 目录与格式契约).

## Glossary

- **slug**: character English id (e.g. `cyborg`, `engineer`). Matches `data/roster.json` `id`.
- **variant-id**: single source of truth for a variant directory name (e.g. `ultimate`, `danger-5`, `ultimate-nightmare`). Slugified from covers; merged multi-difficulty coverage uses one id with `-` join.
- **covers**: display difficulty array (e.g. `["Ultimate"]`, `["Ultimate","Nightmare"]`). Lives inside `manifest.json` / `meta.json` only; never creates extra directories.
- **inputs/**: per-variant read-only inputs under `G:/brotato-work/<slug>/<variant>/inputs/`. Fixed four files: `source.vtt`, `meta.json`, `registry-slice.json`, `manifest.json`. `top3.json` stays repo-side as selection evidence, not an input.
- **steps/**: per-variant process data under `G:/brotato-work/<slug>/<variant>/steps/<step>/`. Pilot locks three steps: `01-sentences/`, `02-verbs/`, `03-grouping/`. No placeholder dirs for future B-chain steps.
- **outputs/**: per-variant final product under `G:/brotato-work/<slug>/<variant>/outputs/`. Pilot: `groups.json` (+ verb lists promoted from steps).
- **sentence record**: `{id, text}` minimal; VTT parse drops timestamps/seq/WEBVTT/NOTE/STYLE, strips HTML, cap 500 chars, quotes cap 10 (along #17).
- **verb record**: `{verb, object_norm, sentence_id, quote}` + discretion fields (`surface_verb, mapped_to, inferred`); closed 10 verbs (take/buy/pick up/lock/get/roll for/ban/recycle/sell/skip) are lower bound, never extended.
- **verified**: exact `name_en` match (case-insensitive) + closed verb + verbatim quote; machine-green anchor.
- **candidates**: agent discretion (alias norm / verb paraphrase / no-verb intent), each with `surface + normalized_to/mapped_to + quote + reason`; `inferred:true` for no-verb intent; audit-HTML yellow, never machine-green.
- **surface**: verbatim word in subtitle; **object_norm**: normalized to registry `name_en`; **mapped_to**: paraphrase target in closed 10.
- **groups.json**: final grouping JSON (必拿分档核心/顺手/妥协 + 提过未拿说原因 + ban说依据). `03-grouping/` draft adds `reason + count` only; pilot includes all `count>0`; 誠实评价 must cite verified/candidates signal.
- **base**: audit-HTML dynamic root. HTML resolves `inputs/` + `steps/*/` + `outputs/` by relative path under `?base=<slug>/<variant>` + directory picker; no hardcoded absolute drive letter.
