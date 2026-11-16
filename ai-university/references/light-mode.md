# Light mode - the same course without Python

Light mode is how this skill works where the `aiu` script cannot run: a chat app, a computer without Python, or a place where the script gets no internet. You make the same course with your own tools (web search, opening pages, writing files or text) and the same page; the page then says plainly what was not checked automatically. Read this file at the start, and keep the phase references open as in full mode: they apply here too, except where this file says what replaces a command.

## When light mode applies

Decide once, at the start, in this order:

1. Try `aiu doctor`. If Python cannot run at all (no Python, a version older than 3.10, or no tool to run commands), work in light mode.
2. If `aiu doctor` reports missing packages, say in one sentence that you are installing what the course builder needs, and run `python -m pip install -r requirements.txt` from this skill's folder. If that fails, work in light mode. Never ask the learner to install anything or to run a command.
3. Run `aiu doctor --online`. If `online.web.status` is not `ok`, wait a few seconds and run it once more; still not `ok` means the script has no internet: work in light mode. If `web` is `ok` but `youtube` is not, stay in full mode: videos YouTube refuses are kept as whole, unverified videos until it answers again (`references/sourcing.md`, *Blocked subtitles*).
4. Otherwise work in full mode.

Tell the learner in one sentence which mode you work in and what it means, e.g. "I'm making the course without the checking script here, so the page will show which things were not checked automatically."

The mode is chosen once per course. A folder with `course-card.md` and no `course.json` is a light course: continue it in light mode, even if the script could run now. A folder with `course.json` is a full course: if the script cannot run here, do not continue it in light mode. Say in two plain sentences that this course is continued in the program where it was started, and offer to make a new course here. Ask no technical question.

## What stays the same

Everything except the script: the phases (brief, benchmarks, syllabus, the learner's confirmation, module by module, capstone), the intake questions and the message that says what you understood (`references/intake.md`), the confirmation of the syllabus (`references/syllabus-design.md`, *Checkpoint 1*: in light mode show the whole plan in chat, since there is no index page: each module with its weeks, hours, topics and outcomes, the capstone and what stays out), the lesson as a story with self-checks (`references/lesson-writing.md`), the tasks, rubrics and answers (`references/practice-design.md`), every iron rule, and the independent review by a fresh subagent wherever you can start one (`references/quality-gates.md`, *Independent review*).

Iron rule 1 in light mode: a web address enters the course only after you have opened it and read it with your own tool in this session. Never from memory, never from a search result's snippet.

## What replaces each command

| Command | In light mode |
|---|---|
| `aiu doctor` | The decision above |
| `aiu init` | Write the course card (*Course card*); if you can write files, create `courses/<slug>/` with `course-card.md` and `web/` |
| `aiu status` | Read the course card: `Built` and `Next` say where to continue |
| `aiu scaffold` | Nothing: there are no module folders |
| `aiu validate` | The checklist (*Checklist before you hand over*) |
| `aiu render` | Fill the page shell (*Building the page*) |
| `aiu checkpoint` | A line under `Checkpoints` in the card: which checkpoint, who confirmed it (the learner, or auto) and the date |
| `aiu module set-status` | The checklist and the review; then mark the module under `Built` in the card |
| `aiu finalize` | The last module's page carries the capstone; the card says the course is finished |
| `aiu source add` | Open the page and read it; record it in `notes/<ID>-sources.md` (address, title, author, what you read, the date), or, without a folder, only in the page's list of sources |
| `aiu source set` | Correct that note |
| `aiu linkcheck` | Open every link once more before you hand the page over; replace or remove one that does not open |
| `aiu yt search` | Your own search |
| `aiu yt transcript` | Only if one of your tools gives the text of the video; otherwise the video stays whole (*Sources and videos*) |
| `aiu yt find` | The same: only with the video's text in hand |
| `aiu yt segment` | The same: minutes only from the text of exactly that segment |
| `aiu open` | Open the file with the system's command if you can run commands; otherwise tell the learner to download the file and open it with a double click |
| `aiu page-check` | Run it if Python can start, even without internet; otherwise go through *Rules* in `references/page-format.md` by hand |

## Sources and videos

- If your tool returns only a summary or an excerpt of a page instead of its text, cite only what that excerpt says, and say in "How this course was made" that the sources were read in excerpts.
- Readings follow the counts of the depth and the learning preference (`references/sourcing.md`, *When to stop*). When your tools do not reach enough sources, record the missing part as a gap; never fill it from memory.
- A video gets minutes only when you read the text of exactly that segment with a tool that gives the transcript. Otherwise it is a whole video: `data-verified="false"`, no `data-from`, no `data-to`. No invented minutes, ever.
- An unverified video is only an extra: it covers no outcome, its step in the day says "optional" ("по желание"), and its time is not counted in the day's `data-minutes`.
- Every outcome rests on text that was read: the lesson, written from read sources, and at least one reading.
- When the learner prefers `watch` or `listen`, say at the start and in "How this course was made" that here the videos are whole and optional, and that the course rests on the lesson, which the page can read aloud, and the readings.

## Course card

The course card is the course's memory: a short text with fixed headings, written in the course language. It sits in `course-card.md` when there is a folder, and word for word in the ready prompt for the next module on the page, so a chat without a folder can continue: the learner copies the prompt from the page.

```text
Course: <title>
Goal: <the goal sentence>
Learner: <level>; knows: <prior knowledge>; prefers: <read|watch|listen|mixed>; <minutes> min a day, <days> days a week, <weeks> weeks
Language: <language code>
Mode: light
Capstone: <title> - turn in: <deliverable> - steps: M01 <step>; M02 <step>; ...
Syllabus:
- M01 <title> (<hours> h). Topics: <topic>; <topic>; ... Outcomes: <outcome 1> | <outcome 2> | ...
- M02 <title> (<hours> h). Topics: ...
Left out: <one phrase each>
Built: M01
Next: M02
Based on: <programme title> <address>; <programme title> <address>
Assumptions: <one sentence each>
Style notes: <the learner's corrections, one sentence each>
Checkpoints: syllabus - <learner|auto> - <date>
```

The file and the prompt hold exactly the same text: put nothing in one that is not in the other, because in a chat without a folder the prompt is all that remains. A day plan or a note goes under one of the headings. Update `Built`, `Next` and `Checkpoints` every time a module is done, in the file and in the prompt together.

## Building the page

- One page per module: `web/<ID>.html` in the course folder, or a file to download in a chat. There is no index page: the overview is in "How this course was made".
- The content follows `references/page-format.md` with `data-page="module"` and `data-mode="light"`; the shell shows the "Light mode" label itself.
- The answers are on the same page, closed: `details[data-answer]` inside each task.
- `section[data-about]` says: light mode; the course plan (each module with its weeks, hours and topics, and the capstone in one sentence); which programmes the course is based on; the assumptions; the gaps; and exactly what was not checked automatically (that the links open, the minutes of the videos, the number and the form of the parts).
- `pre[data-prompt]` holds one sentence, "Continue this course with the ai-university skill in light mode: build module <ID>." in the course language, and under it the course card.
- The page of the last module carries `section[data-capstone][id="capstone"]` with the capstone and `section[data-next][data-kind="capstone"]` with a link to `#capstone`. The syllabus is still designed backward from the capstone, and every module has its step of it.

Assemble the page by the first way your environment allows:

1. You have a tool for files or for running code: copy `assets/page-shell.html` byte for byte and replace only its three slots.
2. You have no such tool (a plain chat): write out the whole page, the shell included, character by character, exactly as the shell is. Check that your answer reached the closing `</html>`; if it was cut off, give the plain page (way 3) instead.
3. The environment does not allow an answer that long: use the plain skeleton (`references/page-format.md`, *Plain page*) and say in "How this course was made" that this is the plain view, without check marks and pop-ups.

## Checklist before you hand over

Go through every point before a module counts as done (this replaces the script's gates):

- L1. Every link on the page was opened in this session.
- L2. Every claim with a number, a date, a name or a quote carries a citation to a source you read.
- L3. No minutes without the text of that segment read.
- L4. Every outcome has its lesson section with a self-check and a guided task; the module has an independent task, its capstone step and a recall task; every graded task has 3–5 criteria and an answer.
- L5. Every task and every resource is on some day, and the days' minutes are within ±25% of the module's hours.
- L6. The page follows `references/page-format.md` (run `aiu page-check` if Python can start).
- L7. "How this course was made" says light mode and what was not checked.
- L8. The course card in the prompt is up to date.

Then the review: by a fresh subagent if you can start one, otherwise yourself, from the page and your notes, not from memory.

## What to tell the learner

In plain words, in their language, with none of this skill's own words (shell, slot, contract, course card, `data-…`, benchmark, gate): say "the page", "the course notes", "university programmes".

- the mode, in one sentence;
- where the page is: if there is a folder, the full path written out from the drive (e.g. `D:\Documents\courses\phishing-emails\web\M01.html`), never a path relative to your working folder, which the learner cannot find; if you gave a file to download, "download the file and open it with a double click"; if you wrote the page into the chat, how to save it: copy all of it, paste it into Notepad (on a Mac, TextEdit after Format → Make Plain Text), save it as `M01.html` with the encoding UTF-8, then open that file with a double click;
- that the ready prompt for the next module is on the page and carries everything needed, so they can paste it into a new chat when they reach the last study day.
