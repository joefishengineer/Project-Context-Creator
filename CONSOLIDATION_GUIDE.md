# File Consolidation Guide

## Overview

After conversion, the flat `_markdown` folder may contain hundreds of files — too many
to upload directly to AI platforms with file limits (Copilot: 50, ICA: varies).

The consolidator (`consolidate_by_initiative.py`) merges them into a small set of
topic-grouped mega-documents. **The grouping logic is defined by a `groups.json` config
file that you create once with AI assistance and reuse on every subsequent run.**

---

## How It Works

```
_markdown/ (hundreds of .md files)
        ↓
  groups.json  ←  AI-authored once, maintained as project evolves
        ↓
consolidate_by_initiative.py
        ↓
_markdown/_CONSOLIDATED/
  ├── PROJECT_01_TOPIC_ONE.md
  ├── PROJECT_02_TOPIC_TWO.md
  ├── ...
  ├── MISC_UNCATEGORIZED.md   (files that didn't match any group)
  ├── _MASTER_INDEX.md
  └── _FILE_MAPPING.md
```

Each output file embeds a **collection map** — a table listing all files in the set —
so any AI reading even a single retrieved chunk knows the full collection structure.

---

## Step-by-Step Workflow

### Step 1 — Convert your project folder

Run the GUI in Project Folder mode. After conversion, your `_markdown` folder contains
a flat set of `.md` files and an `_INDEX.md` that lists all of them.

### Step 2 — Get AI to create your groups.json (first time only)

Share `_INDEX.md` with your AI assistant (Bob, Claude, ChatGPT, etc.) and say:

> *"Analyse these filenames and create a groups.json for the consolidator.
> Group the files by topic area. Use short codes like PROJECT_01, PROJECT_02, etc."*

The AI will return a complete `groups.json`. Example structure:

```json
{
  "project_name": "Example Project",
  "description": "Example project documentation",
  "groups": [
    {
      "code": "PROJ_01",
      "name": "Process Design",
      "filename": "PROJ_01_PROCESS_DESIGN.md",
      "prefixes": [
        "Example Project_Process Design_",
        "Example Project_BPO Transition_"
      ]
    },
    {
      "code": "PROJ_02",
      "name": "Governance and Tollgates",
      "filename": "PROJ_02_GOVERNANCE.md",
      "prefixes": [
        "Example Project_Governance_",
        "Example Project_Tollgate_"
      ]
    }
  ]
}
```

### Step 3 — Drop the file into your output folder

Save `groups.json` into your `_markdown` folder (the same folder the converted `.md`
files are in). The GUI auto-detects it on the next run — no Browse needed.

### Step 4 — Run conversion again (or just the consolidator)

**Via GUI (recommended):**
- Check **Auto-consolidate after conversion** in the Consolidation panel
- The tool finds `groups.json` automatically and runs after conversion completes

**Via command line:**
```powershell
python consolidate_by_initiative.py "C:\path\to\_markdown" --config "C:\path\to\_markdown\groups.json"
```

### Step 5 — Upload the `_CONSOLIDATED` folder to your AI platform

Upload the files from `_CONSOLIDATED/` — typically 5–25 files depending on project size.

---

## Maintaining the Config Over Time

The groups config is a stable artefact. It only needs updating when:
- New topic areas appear in the source folder
- Existing folder structure is significantly reorganised
- You want to split or merge groups

**To update:** Share the new `_INDEX.md` with AI and say:
> *"Here is the updated file list. Please revise the groups.json — the existing groups
> are [paste current config or describe changes]. Add/adjust groups as needed."*

AI diffs the new file list against the existing config and returns a revised JSON.

---

## GUI Controls (Consolidation Panel)

| Control | Behaviour |
|---------|-----------|
| ☐ Auto-consolidate after conversion | When checked, runs consolidator automatically after every conversion pass |
| Groups config (.json) | Path to your groups.json — leave blank to auto-detect from output folder |
| Browse button | Manually select a groups.json from any location |

**Config resolution order (auto-consolidate):**
1. Path in the Browse field — used directly
2. Any `.json` found in the output folder — auto-detected and field populated
3. No `.json` found anywhere — consolidation is skipped (no error)

> **Note:** The Groups config field always starts blank on launch. It is never
> pre-populated from a previous session because config paths are project-specific.

---

## Output File Structure

Each consolidated file follows this structure:

```markdown
# PROJ_01: Process Design

**Consolidated from 87 source files**
**Generated**: 2026-07-10 09:00:00
**Project**: Example Project

## About This Collection

This file is part of the Example Project knowledge base...

| Code | File | Topics Covered |
|------|------|----------------|
| PROJ_01 | PROJ_01_PROCESS_DESIGN.md | Process Design **(this file)** |
| PROJ_02 | PROJ_02_GOVERNANCE.md | Governance and Tollgates |
...

---

## Table of Contents
1. [Document Name 1](#...)
2. [Document Name 2](#...)

---

## 1. Document Name 1
**Source File**: `Example Project_Process Design_Document1.md`
[original document content]

---
```

The **About This Collection** block is embedded in every file so that any AI reading
a single retrieved chunk immediately knows the full collection structure and can direct
users to the right file for topics not in the current chunk.

---

## No groups.json

If no `groups.json` is provided, the consolidator skips consolidation and says so.
Create a `groups.json` (Step 2 above) to enable it.

---

## Troubleshooting

**Files landing in MISC_UNCATEGORIZED.md**
The file's name prefix doesn't match any group's `prefixes` list. Share the
uncategorized filenames with AI and ask it to add appropriate prefix rules to
the relevant groups.

**Groups config not detected automatically**
Verify the `.json` file is saved directly in the `_markdown` output folder
(not in a subfolder). The auto-detect only scans the top level.

**Consolidation produces empty groups**
The `prefixes` values must exactly match the start of each filename. Check
`_FILE_MAPPING.md` to see which files were matched, and compare against your
actual filenames in `_INDEX.md`.

**Output file too large for AI platform**
Split the group into two by creating two entries in `groups.json` with more
specific prefix lists. Share the current config with AI and say
"split [group name] into two smaller groups".
