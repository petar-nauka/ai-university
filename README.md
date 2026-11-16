# AI University

Turn any topic into a free, source-grounded self-study course, built by your own AI assistant.

You name what you want to learn. The AI asks a few questions, shows you a syllabus to approve or change, and then builds the course one module at a time as web pages that open with a double click: a day-by-day plan, lecture videos opened at the right minute, readings, a lesson, practice tasks with rubrics, separate model answers and a final project.

Works with Claude, ChatGPT, Gemini, Copilot and coding agents such as Claude Code, Codex, Gemini CLI and Cursor.

*На български: [README.bg.md](README.bg.md)*

## What makes it different

- **No invented sources.** A link enters the course only after it was really opened and read.
- **No invented timestamps.** A video segment is cited only after its transcript text was read.
- **Facts carry citations.** Numbers, dates, names and quotes in a lesson point to the text they came from.
- **Gaps stay visible.** What could not be found or verified is listed, not papered over.
- **Answers are kept apart.** Solutions never sit next to the task.
- **Free to study.** Everything required in the course is free online.

## How to start

### In a coding agent (full mode)

Clone or download this repository, open the folder in your agent and write:

> Read START-HERE.md and follow it. I want to learn: [topic].

`AGENTS.md`, `CLAUDE.md` and `GEMINI.md` point the agent to `START-HERE.md` on their own. Full mode needs Python 3.10 or newer and internet access; the agent installs the packages from `ai-university/requirements.txt` itself. A checker script (`ai-university/scripts/aiu.py`) verifies every source, every video timestamp and every module.

### As a Claude skill

- **Claude Code:** copy the `ai-university/` folder to `~/.claude/skills/`.
- **Claude.ai / Claude desktop app:** turn on *Code execution and file creation* in Settings → Capabilities, then upload `ai-university_claude-ai.zip` from [Releases](../../releases) in Customize → Skills. In a new chat write: "I want to learn: [topic]."

### In a chat app (light mode)

Attach the two files from the `chat/` folder, `ai-university.md` and `page-shell.html`, and write:

> Follow ai-university.md. I want to learn: [topic].

For a reusable setup, put both files in a project or custom assistant (see `chat/HOW-TO.md`). In light mode there is no checker script, so the page says "Light mode" at the top and lists what was not checked automatically.

## Repository layout

```
START-HERE.md           entry point for any AI assistant
AGENTS.md, CLAUDE.md,   one-line pointers to START-HERE.md for coding agents
GEMINI.md
ai-university/          the skill
  SKILL.md                instructions the AI follows
  references/             phase-by-phase guides: intake, syllabus, sourcing, lessons,
                          practice, quality gates, page format, light mode
  scripts/aiu.py          checker: sources, transcripts, link checks, validation, rendering
  scripts/aiu_core/       the rules behind each command
  assets/                 page shell and markdown templates
  agents/openai.yaml      metadata for other agent hosts
chat/                   the same skill as one file for chat apps, plus the page shell
```

## Not in this version

Teaching sessions, grading, progress tracking and spaced review; input from a university programme URL, a PDF or a folder of materials; slides or PDF output. Each task has a button that copies its statement and criteria, so you can check your answer with an AI.

## Privacy

The AI searches the web while it builds the course. Do not put personal details you want to keep private (income, debts, health) into your answers.

## Feedback

This is a trial version (2026-11-16). Tell us in [Issues](../../issues) what confused you and where the AI had to ask something the instructions do not cover.

## License

MIT, see [LICENSE](LICENSE). Made by Petar Teodosiev, [БГ Наука](https://nauka.bg).
