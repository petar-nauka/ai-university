# Quality gates - phase 4 checks and phase 5 finish

`aiu` refuses to move a module or the course forward while a rule fails. This file covers what each gate checks and how to fix an error, the review of a module, Checkpoint 2, building by module, parallel builds, finishing the course, the final report and resuming in a new session.

## Module gates

A module climbs `planned` → `sourced` → `drafted` → `verified`, and only through `aiu module set-status`, which runs the checks first:

| Status | What is checked | Command |
|---|---|---|
| `sourced` | M1–M6: sources, resources, coverage of each outcome | `aiu module set-status --course <dir> <ID> sourced` |
| `drafted` | M1–M14; a link never checked is only warning M12w | `aiu linkcheck --course <dir> --module <ID>`, then `aiu module set-status --course <dir> <ID> drafted` |
| `verified` | M1–M14, a link never checked is an error, and a review is required | `aiu linkcheck --course <dir> --module <ID>` again if you added a source, then `aiu module set-status --course <dir> <ID> verified --review independent` (or `self`, see *Independent review*) |

Before each `set-status`, run `aiu validate --course <dir> --stage module --module <ID> --gate sourced|drafted|verified` (the default gate is `drafted`). It shows errors and warnings without moving anything; `set-status` lists the gate's warnings when it succeeds and its errors when it refuses. After `verified`, the lead agent runs `aiu render --course <dir>` so the module page shows the work; a builder in a parallel build does not (see *Parallel module builds*).

A refusal exits with code 1. Each item in `errors` and `warnings` is `{"code", "where", "message"}`: `code` names the rule, `where` the place: `M02` a module, `M02-O1` an outcome, `M02-P3` a task, `M02:S4` a source, `M02-O1/S4` a resource (outcome/source), `M02:resource#3`, `M02:task#2` or `M02:source#1` a record without a usable id. Codes ending in `w` are warnings: they do not block, but fix them or be ready to say why they stay. Exit code 2 means the command could not run:

- `E_USAGE`: wrong arguments (e.g. `verified` without `--review`) or a file that cannot be read, such as a `module.json`; the message names it. `aiu source add` also refuses with `E_USAGE` (exit code 2) whenever it registers or changes nothing; the message says which case:
  - the transcript fetch failed ("transcript fetch failed (error …); nothing registered", or "… is unchanged" on a retry): run the same command again later, or choose another video. When YouTube blocks the subtitles (`blocked`) on a first registration, the command does not refuse: it registers the whole video, unread (`access: metadata_only`, `video.transcript_note: blocked`; `references/sourcing.md`, *Videos*);
  - YouTube gave no metadata or no duration (a live stream, a premiere): choose another video;
  - an `--extract-file` that was not used ("the extract file was not used and nothing changed", or "cannot be used with a video source"): a video takes no extract file, and text you already supplied for a record stays as it is; run the command without `--extract-file`;
  - an extract file that is missing, not UTF-8 or under 1500 characters: save at least 1500 characters of the page's own text as UTF-8 and run the command again.

  `aiu source set` refuses with `E_USAGE` a field it does not set, a value the field does not allow, or an id that is not in the target; the message lists the fields and values it accepts (`references/sourcing.md`, *Correcting a record*).
- `C1`: `course.json` cannot be read.
- `E_TRANSCRIPT`: from `aiu yt transcript`, `yt find` or `yt segment`: no transcript could be fetched, or the video's metadata could not be read; the message gives the reason (`no_subs`, `blocked`, `unavailable`, `error`). `aiu source add` reports these failures as `E_USAGE` (above), except `no_subs` and `blocked`, for which it registers the video as `metadata_only` (`references/sourcing.md`).
- `E_ENV`: from `aiu doctor`: a missing package, a Python older than 3.10, or no write access.
- `E_INTERNAL`: a bug, or a record shaped in a way no rule caught. Run `aiu validate --course <dir> --stage syllabus` (and `--stage module --module <ID>`), fix what they report and try again; with the environment variable `AIU_DEBUG=1` the command also prints the traceback, for a bug report.

| Code | What failed | What to fix |
|---|---|---|
| M1 | `module.json` missing or invalid, wrong `module_id`, unknown `status`, a list missing | Repair the JSON by hand; never delete the file, it holds the sources |
| M2 | an outcome has no `video` or `reading` resource and no gap (M2w: it rests only on a gap) | Add a resource or record the gap (`references/sourcing.md`) |
| M3 | a resource names an unknown source or outcome, or an unknown role | Fix the ids; roles are `video`, `reading`, `reference`, `tool` |
| M4 | a video resource is not a read segment of a transcribed video (M4w: outside the recommended 120–1500 s) | Bounds in seconds within the video, 60–2400 s long, a cue inside, `before_question` and `after_task`; without a transcript, use role `reference` |
| M5 | a reading has no read text (M5w: only an abstract) | Re-run the same `aiu source add` with `--extract-file`, or choose another source |
| M6 | a source record is incomplete | Set a missing `title`, `why_selected` or `reliability` with `aiu source set`; restore anything else from what `aiu source add` wrote, never fill it in by hand; a video with `duration_sec` 0 cannot be used |
| M7 | `lesson.md` missing or too short, or an outcome marker missing | Write it, strengthen the weakest section, add the exact marker |
| M7w | the lesson is over 1.2 × the top of its target (lite 1200, standard 2500, deep 4000 words) | Cut repetition and what no outcome or task needs; add nothing (`references/lesson-writing.md`, *Length*) |
| M8 | a citation to an unknown or unread source, a bad time or a time on a non-video; a malformed citation (`[S2, S3]`, `[S2 p. 4]`, a time range); a section that cites nothing | Fix the id or the time, cite a read source, or add a source; write each citation as `[S3]` or `[S2 @12:30]`, one source per bracket (`references/lesson-writing.md`) |
| M9 | an invalid task record (id, kind, a `title`, `minutes` above 0, outcomes), an outcome without a `guided` task, no `independent` task, a rubric missing or not 3–5 criteria with points of at least 1 (M9w: not exactly one `project` task) | Complete the records (`references/practice-design.md`) |
| M10 | a marker missing in `practice.md` or `answers.md`, or an answer marker in `practice.md` | Add the marker; move answers to `answers.md` |
| M11 | a glossary entry without `term` or `definition` | Complete it; keep at least 3 entries (M11w) |
| M12 | a used source's link is dead (M12w: never checked, or `unreachable` at the last check) | Register a replacement, point resources and citations to it, run `aiu linkcheck --course <dir> --module <ID>`; for `unreachable`, open the link with your own tool first |
| M13 | `study_plan` missing or malformed (days not numbered 1, 2, 3, …, `minutes` not above 0, `items` empty), or a task id or the `S` id of a `video` or `reading` resource on no day (M13w: the plan's minutes are outside ±25% of the module's hours, or one day runs over 1.5 study days) | Write or complete the plan (`references/practice-design.md`, *Day-by-day plan*); name each task by its id and each video or reading by its `S` id in the day's items; M13w also flags a day, other than the last, under half a study day |
| M15w | an outcome's lesson section has no self-check (`<details>`); never for an outcome that rests only on a gap | End the section with 1–2 questions in `<details>` that the section answers (`references/lesson-writing.md`, *Structure*) |
| M14w | fewer video segments or readings than `brief.depth` and `brief.learning_preference` expect (mixed: lite 1 and 1, standard 2 and 3, deep 4 and 5; the other preferences in `references/sourcing.md`, *When to stop*) | Add sources; when YouTube blocks transcripts, add the video now as a whole, optional extra (`references/sourcing.md`, *Blocked subtitles*; it does not count as a segment) and its segment later (*Parallel module builds*); if none exists, keep the `no_video` or `no_reading` gap and say why the warning stays |

Never get past a check by editing what it reads (iron rule 6): no hand-set `status`, `review`, `check` or `access`, and no extract file written except through `--extract-file`. Fix the cause.

A status can go down freely. When the content of a module changes after a gate, set the lower status (`aiu module set-status --course <dir> <ID> drafted`, which also clears `review`) and climb again. Setting the current status again changes nothing, except `verified` with `--review`: that re-runs the gate and records the new review.

## Independent review

Review every module before `verified`: the gates check form (an id exists, a time lies inside the video), the review checks substance (the cited text really says it).

**The review is independent whenever you can launch a subagent**, i.e. you have a tool that starts another agent. `--review self` is allowed only when you cannot. Why: an author reads into the text what they meant, so a self review misses exactly the claims cited to the wrong source.

Start a fresh subagent and give it only three paths: the module folder, the course folder and this skill's folder, so it can run `aiu`. Do not give it your reasoning or your notes: a reviewer who knows what you meant reads that into the text. Tell it to change no file and to run these ten checks:

1. **Citations.** For every bracket in `lesson.md` and in `answers.md`, if it has any, look up the id in this module's `module.json` `sources` and open the file its `extract_path` or `original_path` names (relative to the course folder); for `[Sn @MM:SS]`, read the segment around that time with `aiu yt segment`. Find the passage that supports the claim. Report a claim the cited source does not contain (and which source does, if any), a time outside every segment the module assigns from that video, and a number, date, name or quote without a citation.
2. **Segments.** For every `video` resource in `module.json`, read its segment with `aiu yt segment --course <course dir> <video_id> --start MM:SS --end MM:SS`, taking `video_id` from the source record and the bounds from the resource's `locator` (seconds converted to MM:SS). It must answer `before_question`, contain everything `after_task` asks for, and start and end at a sentence or topic boundary.
3. **Tasks.** Every task in `practice.md` can be solved with the lesson and the module's resources.
4. **Answers.** Every answer in `answers.md` is correct, agrees with its sources and earns the points its criteria in `module.json` promise. Every requirement the task statement in `practice.md` sets is met by the model answer and scored by at least one criterion; report each one that is not.
5. **Level.** The lesson and the tasks fit `level` and `prior_knowledge` in the brief in `course.json`.
6. **Omissions.** What the module's main sources recommend prominently and the lesson leaves out is recorded as a gap of kind `other` (`references/lesson-writing.md`).
7. **Extracts.** For every non-video source that a resource or a citation uses, open its `extract_path` or `original_path` and confirm that it holds the source's actual content, not a login wall, a cookie or consent page, a catalogue or a listing of links (`references/sourcing.md`, *Check every extract*).
8. **Benchmarks.** For every outcome of this module with `origin: benchmark`, open the "Outcome support" section of `research/benchmarks.md` and each cited benchmark's saved text (`research/extracts/B<n>.md` or the original). Every id in the outcome's `benchmark_refs` needs its own row, and the quoted line must really be in that text and name this topic or skill. Report an outcome with no row, a missing row for one of its ids, or a benchmark text that does not cover it (that id should be dropped, or the outcome made `ai_designed`).
9. **Day plan.** Each day of `study_plan` in `module.json` can be done in its `minutes` by a learner at the brief's `level`: add up the video segments, the reading and the task minutes it lists. The days follow the lesson's order, a task comes after the material it needs, and every item tells the learner exactly what to open (a lesson section, a source id with its segment or section, a task id).
10. **Story and self-checks.** The lesson opens with a case and one question, and its summary answers that question; from the second module on, the opening says what the learner can already do from the previous module; every self-check question (`<details>`) is answered by its own section, and the answer given there is correct.

Ask for the findings as a list, one per problem: check number, file and id or marker, what is wrong, the evidence (a quote, or a source id with a time), a suggested fix; and "no findings" for each check that passed. Fix every finding or note why it stands, then run `aiu module set-status --course <dir> <ID> verified --review independent`; it runs the gate first.

Only when you cannot launch a subagent, run the same ten checks yourself: from the files, not from your memory of what you wrote, every bracket and every segment. Write the same list, fix, and record `--review self`. If an independent review becomes possible later, run it, fix what it finds and run `aiu module set-status --course <dir> <ID> verified --review independent` again: it re-checks the module and records the new review.

## Checkpoint 2

When the first module is `verified`, `aiu status` returns `approve_pilot`. Run `aiu render --course <dir>`, then show the user, in chat and in their language:

- the module page, `modules/<slug>/README.md` in the course folder, and `lesson.md` beside it;
- a summary of the lesson in a few sentences;
- one task as the learner sees it, with its deliverable and criteria;
- the module's gaps.

In `interactive` mode, ask three things: is the style right (tone, length, examples), is the depth right, and are these the right kinds of tasks? Wait for the answer.

- Write each correction into `brief.style_notes` in `course.json`, one sentence each (e.g. "Give every section a worked example from everyday work."), so it binds every later module. Editing `style_notes` does not touch the approved syllabus; changing modules, outcomes or the capstone does, and `aiu status` then returns `approve_syllabus` until that checkpoint is recorded again.
- Apply the corrections to the pilot module too: lower its status, revise, pass the gates and the review again.
- Then run `aiu checkpoint --course <dir> --name pilot --by user`. It refuses while the first module is not `verified`.
- In `confirm` mode (the default) and in `auto` mode, do not ask and do not wait: run `aiu checkpoint --course <dir> --name pilot --by auto` and go on (in `incremental` mode, `aiu status` then returns `wait_for_learner`: see *Building by module*). The learner has already confirmed the syllabus, and the independent review of the module has done the checking a user would do; in the stop report, say in one line what it found and what you fixed.

## Building by module

By default (`brief.build_mode` is `incremental`) the course is built one module at a time: the first run builds the benchmarks, the syllabus and the first module, and every later module is built when the learner asks for it. Why: a module built weeks before it is studied uses older sources and is wasted if the learner stops; one built on request costs only what is studied and uses what is new that day.

- After Checkpoint 2, `aiu status` returns `wait_for_learner`, with the next module in `next.module_id`. Stop building, run `aiu render --course <dir>` (the last study day of the built module now starts with the ready prompt for the next one, and `README.md` names the next module and that day), then `aiu open --course <dir>`. Tell the learner, in their language and in plain words: which module is ready; the full path of the page from `data.path`; that the page is now open in the browser (if `data.opened` is false: open that file with a double click); to bookmark it, so they find it again; that every step opens in a small window, where a video starts on YouTube at the right minute and the window says when to stop; and on which study day to ask for the next module by copying the ready prompt from the page (the build takes a while, so they ask at the start of that day and study while it runs). Use none of the script's words (`wait_for_learner`, `verified`, status names, rule codes): they mean nothing to a learner.
- When the learner asks ("продължи курса", "continue the course"), run `aiu status`. For `wait_for_learner`, build `next.module_id` from sourcing, as for `build_module` with status `planned`. Search afresh: what is new that day matters as much as the benchmarks did.
- If the fresh research shows that the outcomes of this module, or of a later module not yet built, are out of date, change them in `course.json`, validate the syllabus and record its checkpoint again (`--by auto --note "<what changed and why>"`; in `interactive` mode show the change and record `--by user`; in `confirm` mode record `--by auto` and name the change and its reason in plain words in the stop report, because the learner confirmed the earlier version). Never change a `verified` module the learner may already have studied: record in its `gaps` what has changed since.
- Build one module per request; after its review and `verified`, render and stop at `wait_for_learner` again. When the module you built is the last one, go on to *Finalize* in the same run: the capstone needs nothing the learner has not asked for yet.
- `full` mode builds every module in one run (*Parallel module builds*). Set it only when the user asks for the whole course at once.

## Parallel module builds

In `full` mode, after Checkpoint 2, build the remaining modules one by one or, if you can launch subagents, in parallel. Each module has its own folder and `module.json`, so builders do not collide as long as they keep to these rules:

- One builder per module. Give it the course folder, the module id, this skill's folder and the four phase 4 references to read.
- YouTube refuses transcripts (HTTP 429, `blocked`) when several builders fetch at once from the same address. Run at most two builders at a time, and tell each to fetch transcripts one at a time with a pause of a few seconds. When `blocked` persists, a builder finishes the rest of its module, records the videos it chose (id and planned segment) in its search log, and the lead adds them later, one module at a time, once YouTube answers again.
- A builder writes only inside its module folder and in `research/` files carrying its module id: the extracts and originals that `aiu source add` names `<ID>-S<n>`, its own log `research/search-log-<ID>.md`, and scratch files such as extract files in `research/scratch/`, named `<ID>-…`. `research/transcripts/` is a shared cache keyed by video that only the script writes.
- A builder always passes `--module <ID>` to `aiu linkcheck` (without it, the command rewrites every module) and never runs `aiu render` or `aiu checkpoint`.
- Only the lead agent edits `course.json`. A builder that needs a syllabus change reports it instead.
- Each builder takes its module up to `verified`, with an independent review if it can launch a reviewer, otherwise with `--review self`. A builder often cannot launch subagents while the lead can: the lead then runs the independent review (*Independent review*) for every module recorded as `self` before *Finalize*.
- When all builders are done, the lead runs `aiu status --course <dir>` and `aiu render --course <dir>`, then goes on to *Finalize*.

## Finalize

When `aiu status` returns `finalize`, every module is `verified`.

1. Write `capstone.md` (`references/practice-design.md`, *Capstone*) and its days in `capstone.study_plan` in `course.json` (same shape as a module's plan, rule S11; without it `schedule.md` shows the capstone days as one placeholder row). Then re-read `brief.assumptions` in `course.json` and correct every one the build did not keep, such as a source language that yielded nothing usable: the learner reads them as facts about the course (`references/intake.md`, after *Defaults*). Editing them does not touch the approved syllabus.
2. Run `aiu linkcheck --course <dir>`: it checks every link of the course, benchmarks included, and records each result. A dead link on a source a module uses (a resource or a lesson citation) or on a benchmark an outcome cites is error M12 and exit code 1: replace it (for a module source, lower that module, replace, verify again; for a benchmark, see F5 below). A dead link nothing uses is only warning M12w: it blocks nothing and is listed in `gaps.md`. Leave unused dead or unreadable sources registered: the record is honest, and a dead link matters only when something uses or cites it. `blocked` (the site refuses scripts, or the script cannot verify its security certificate although browsers open it) passes the gates; `unreachable` (no answer) passes with warning M12w on a used source. Both are listed in `gaps.md`; open such a link with your own tool and treat it as dead if it is really gone.
3. Run `aiu validate --course <dir> --stage final` to see every remaining problem at once.
4. Run `aiu finalize --course <dir>`: it runs the final check, renders the pages and records `finalized_at` with a digest of the syllabus, each module's `module.json`, `lesson.md`, `practice.md` and `answers.md`, and `capstone.md`. `aiu status` says `done` only while that digest still matches: when any of them changes later (`aiu linkcheck` too writes into `module.json`), it returns `finalize` again, and you repeat steps 3 and 4.

The final stage checks all S rules, all M rules of every `verified` module, and:

| Code | Rule |
|---|---|
| F1 | no `syllabus` checkpoint, or the syllabus changed after it |
| F2 | a module is not `verified` (a warning with `--allow-partial`) |
| F3 | `capstone.md` missing or under 150 words |
| F4w | no `pilot` checkpoint |
| F5 | a benchmark that an outcome cites (`origin: benchmark`) is dead: register a live copy and cite it, or change those outcomes, then get the syllabus approved again |
| F6 | a module is `verified` without a `self` or `independent` review: review it (*Independent review*), then run `aiu module set-status --course <dir> <ID> verified --review independent` (`self` only when you cannot launch a subagent) |

Add `--allow-partial` (to both `aiu validate --stage final` and `aiu finalize`) only when the user wants to start studying the finished modules before the rest are built, and say which modules are not ready. A partial run renders the pages and records `partial_finalized_at`, never `finalized_at`: `aiu status` keeps returning `build_module` (or `wait_for_learner` in `incremental` mode) for the unfinished modules and then `finalize`. Once they are `verified`, run `aiu finalize --course <dir>` without the flag; only a full finalize makes `aiu status` say `done`.

## Final report

Tell the user, in their language:

- where the course is and how to start: run `aiu open --course <dir>` and give the full path from `data.path`; the page is now open in the browser (if `data.opened` is false: open `web/index.html` with a double click, no program or server needed), and they should bookmark it. Every module page links from there. `README.md` and the Markdown pages hold the same content for reading without a browser;
- the counts: modules, outcomes, video segments, readings and tasks (the course `README.md` lists them near its end);
- the gaps, as a short list from `gaps.md`;
- the review each module got (`aiu status` shows it): `independent`, or `self` with the reason no subagent could be launched, because a self review is weaker and the user should know why it was used;
- what was not verified: modules with only a self review, readings with `abstract_only` access, links that were `blocked` or `unreachable`, transcripts from automatic captions;
- that this version does not track progress: the course claims nothing about what the learner knows (iron rule 9), and progress tracking comes with the Teacher mode, which is not built yet.

## Resume

In a new session, never trust memory of where you were. Run `aiu status --course <dir>` (the course is in `courses/<slug>/` unless the user named another folder) and act on `data.next.action`:

| `next.action` | What to do |
|---|---|
| `research_benchmarks` | Find and register benchmarks (`references/syllabus-design.md`) |
| `design_syllabus` | Write the modules and outcomes into `course.json` (`references/syllabus-design.md`) |
| `approve_syllabus` | Validate, scaffold, render, get the syllabus approved; if `next.detail` names syllabus errors, fix them first; if it was approved before, show what changed (`references/syllabus-design.md`) |
| `build_module` | Build `next.module_id`, continuing from its status (below) |
| `approve_pilot` | *Checkpoint 2* |
| `wait_for_learner` | *Building by module*: stop and tell the learner when to come back; if the learner has just asked for the next module, build `next.module_id` as for `build_module` with status `planned` |
| `finalize` | *Finalize*, then *Final report*; if `next.detail` says the course changed since it was finalized, run the final check and `aiu finalize` again |
| `done` | A full finalize ran and nothing changed since; report on the course or do what the user asks |

For `build_module`, `next.module_status` says where to continue:

- `planned`: sourcing. Keep the sources already in `module.json` and skip the queries already in the search log.
- `sourced`: the lesson, the tasks, the answers and the glossary. Read whatever already exists and continue it instead of starting over.
- `drafted`: link check, review, `verified`.

`next.module_id` is the first module in course order that is not `verified`. If `aiu status` fails because a `module.json` cannot be read, repair that file; never delete it.
