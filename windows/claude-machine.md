# This machine (Windows)

- Before running shell commands, read `C:\Users\DELL\Documents\CLI-guides\cli-guide-agents.md` (shell quirks, installed CLI tools, which are interactive and must not be run). Format hook details: section 7 there.
- Pre-built envs live in `C:\Users\DELL\envs\`. Use them instead of installing packages:
  - Documents, PDF, Office files, HTML→PDF: `uv run --project C:\Users\DELL\envs\docs python <script>`
  - Data science / EDA / plotting: `uv run --project C:\Users\DELL\envs\ds python <script>`
  - What each env contains: `C:\Users\DELL\envs\README.md`. Read `C:\Users\DELL\envs\CONTEXT.md` before changing the env setup.
- CLI tools on PATH: quarto, pandoc, typst, latexmk (TinyTeX), dot (Graphviz), ffmpeg.
- Zotero library is auto-exported to `C:\Users\DELL\Documents\References\library.bib` (styles in `References\csl\`, Vancouver by default). See `References\README.md`.
- `new-project` defaults to `D:\Personal Projects\<name>\` (`--engine typst|latex` for reports). Older projects in `C:\Users\DELL\Documents\Projects\` stay where they are.
