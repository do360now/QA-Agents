---
name: Analyst Agent
description: Reads a codebase, builds a structural snapshot, and derives requirements — feeds Risk Analyst
type: reference
---

# Analyst Agent

## Purpose
First agent in the pipeline. Takes a codebase root path, reads every relevant
source file, builds a structural snapshot, and derives a requirements list —
both explicit (from docs and comments) and implicit (inferred from code
patterns). Output feeds directly into the Risk Analyst.

This agent replaces the combination of a "Code Reader" and a "Requirements
Engineer". They were separated in early design but the interface between them
was tighter than either's internal complexity — a sign they belong together.

## When to Use
- At the start of every pipeline run (Phase.ANALYSIS)
- When re-running after the codebase has changed
- When the scope of analysis changes (new modules added)

## Inputs

From `PipelineState`:
```python
state.scope   # root path: e.g. "hi-tech/"
```

No artifact dependencies — this is the first agent.

## What It Reads

```
hi-tech/
├── *.py                  # all Python source files
├── requirements.txt      # dependency inventory
├── README.md             # explicit requirements source
├── docs/                 # any markdown docs
├── *.md                  # prompt files, spec files, review notes
└── tests/                # existing test files (coverage baseline)
```

Files explicitly excluded (noise, not signal):
- `__pycache__/`, `.git/`, `node_modules/`, `venv/`, `.env`
- Binary files, images, compiled artifacts

## Analysis Steps

### 1. Build Codebase Snapshot

Walk the scope directory and for each Python file extract:

```markdown
### hi-tech/news.py
**Classes:** NewsFetcher
**Functions:** get_latest_news, _search_topic, _parse_date
**Imports:** requests, feedparser, datetime, schedule
**External calls:** requests.get, feedparser.parse
**Config dependencies:** RSS_FEED_URL, REQUEST_TIMEOUT
**TODOs / FIXMEs:** [list any found in comments]
**Line count:** 187
```

Group by module. Flag files with no existing test coverage.

### 2. Derive Requirements

Extract requirements from three sources, in priority order:

**Explicit** — stated in docs, README, prompt files, or comments:
```
REQ-001 [Explicit] System must post tweets on a configurable schedule
REQ-002 [Explicit] News articles must be deduplicated across runs
REQ-003 [Explicit] Bot must handle RSS feed unavailability gracefully
```

**Inferred** — derived from code structure and patterns:
```
REQ-004 [Inferred] Date parsing must tolerate malformed RFC2822 strings
         Source: news.py::_parse_date uses try/except with no logging
REQ-005 [Inferred] HTTP requests must enforce timeouts
         Source: requests.get() called without timeout= parameter
REQ-006 [Inferred] File paths must be configurable, not hardcoded
         Source: used_articles.json path hardcoded in UsedArticlesTracker
```

**Gap** — things the code clearly does but no requirement documents:
```
REQ-007 [Gap] Image download behaviour on 404 is undefined
         Source: ImageFinder._download() has no error handling
```

### 3. Map Requirements to Modules

Cross-reference each requirement to the module(s) that implement or violate it.
This becomes the Risk Analyst's starting point.

## Output Artifacts

### `codebase_snapshot`

```python
state.set_artifact(ArtifactKey.CODEBASE_SNAPSHOT, {
    "root": "hi-tech/",
    "files": [
        {
            "path": "hi-tech/news.py",
            "classes": ["NewsFetcher"],
            "functions": ["get_latest_news", "_search_topic", "_parse_date"],
            "imports": ["requests", "feedparser", "datetime"],
            "external_calls": ["requests.get", "feedparser.parse"],
            "config_deps": ["RSS_FEED_URL"],
            "has_tests": True,
            "line_count": 187,
            "todos": ["TODO: add retry logic for 429 responses"],
        },
        # ... one entry per file
    ],
    "dependency_inventory": ["requests", "feedparser", "tweepy", "schedule"],
    "uncovered_modules": ["config.py", "image_finder.py"],
})
```

### `requirements`

```python
state.set_artifact(ArtifactKey.REQUIREMENTS, [
    {
        "id": "REQ-001",
        "type": "explicit",          # explicit | inferred | gap
        "text": "System must post tweets on a configurable schedule",
        "source": "README.md:L14",
        "modules": ["main.py"],
    },
    {
        "id": "REQ-004",
        "type": "inferred",
        "text": "Date parsing must tolerate malformed RFC2822 strings",
        "source": "news.py::_parse_date",
        "modules": ["news.py"],
    },
    # ...
])
```

## LLM Prompt Strategy

The Analyst uses two LLM calls per run to stay within context limits:

**Call 1 — Structural extraction** (can use a smaller/faster model)
```
System: You are a code analyst. Extract structure from Python source files.
        Respond only in JSON matching the codebase_snapshot schema.
        Do not summarise. Do not explain. Emit JSON only.

User:   [file contents, one at a time or batched if small]
```

**Call 2 — Requirements derivation** (benefits from a stronger model)
```
System: You are a requirements analyst. Given a codebase snapshot and any
        available documentation, derive a requirements list.
        Classify each requirement as explicit, inferred, or gap.
        Respond only in JSON matching the requirements schema.

User:   Snapshot: [codebase_snapshot JSON]
        Docs: [README.md, prompt files, inline comments extracted]
```

Structured JSON output is mandatory. If the model returns prose, call
`state.record_error()` and retry — the Orchestrator handles the loop.

## Error Handling

| Condition | Action |
|-----------|--------|
| File unreadable (permissions) | Log path to `state.record_error()`, skip file |
| Binary file encountered | Skip silently |
| LLM returns malformed JSON | `state.record_error()`, Orchestrator retries |
| Scope directory missing | Raise exception — Orchestrator marks run FAILED |
| No Python files found | Raise exception — nothing to analyse |

## Output Summary (logged by agent)

```markdown
## Analyst Output

**Scope:** hi-tech/
**Files analysed:** 8
**Uncovered modules:** config.py, image_finder.py
**Requirements derived:** 12
  - Explicit: 4
  - Inferred: 6
  - Gap: 2

**Passing to:** Risk Analyst
```

## Implementation Notes

- File walking should respect `.gitignore` if present
- Large files (>500 lines) should be summarised by class/function signature
  rather than full content, to avoid LLM context overflow
- The `codebase_snapshot` artifact is consumed by Risk Analyst but also
  useful for the Reporter when generating coverage summaries
- If re-running after a partial pipeline, the Analyst is only re-invoked if
  the Orchestrator rewinds to `Phase.ANALYSIS` — otherwise its artifacts
  from the previous run are reused

**Why:** Without an Analyst, the Risk Analyst has to assume requirements exist
and code is already understood. That assumption fails on every new project.
The Analyst gives the pipeline a genuine entry point — it starts from nothing
and produces something every subsequent agent can rely on.
