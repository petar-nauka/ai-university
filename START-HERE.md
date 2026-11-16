# START HERE - AI University (for the AI assistant)

You have been given AI University: instructions for building a free, source-grounded self-study course on any topic, one module at a time, as web pages the learner opens in a browser. The person who gave you this wants to learn something; their message names the topic. If it does not, ask what they want to learn.

Talk to the learner in the language they write in. Never ask the learner to install, copy or run anything, and never show them file names, commands or rule codes from this folder: say what the instructions tell you to say, in plain words.

## Choose your way in, once

1. **You can run commands in a terminal and read this folder** (a coding agent such as Claude Code, Codex, Gemini CLI or Cursor, or any assistant with a shell on the learner's computer). Read `ai-university/SKILL.md` and follow it. It decides by itself whether you work in full mode, with its checker `ai-university/scripts/aiu.py`, or in light mode. Run the checker from this folder as `python ai-university/scripts/aiu.py <command>`; where `python` is missing or older than 3.10, try `python3` or `py -3`. Install its packages with `python -m pip install -r ai-university/requirements.txt`; if the system refuses (for example "externally-managed-environment"), create a virtual environment here with `python -m venv .venv` and use its Python (`.venv/bin/python`, or `.venv\Scripts\python.exe` on Windows) for the install and for the checker. Work in light mode only when Python cannot run at all. Put the course folders in `courses/` here.
2. **You are a chat app**, even one that can run code in a sandbox. Read `chat/ai-university.md` and follow it: it is the same skill as one file, in light mode. Build every page from `chat/page-shell.html`, unchanged except for its three slots.

If you can open only some of the files, `chat/ai-university.md` and `chat/page-shell.html` are all you need.

## Begin

Start with the intake questions: `ai-university/references/intake.md` in way 1, or the part headed `# FILE: references/intake.md` in `chat/ai-university.md` in way 2. Build the plan, show it to the learner, and build the first module as the instructions say.
