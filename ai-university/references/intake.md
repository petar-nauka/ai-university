# Intake - phase 1: the brief

The brief is the contract for the whole course: the number of benchmarks, the lesson length, the kind of tasks and the weekly schedule are all read from it. Get it in one short exchange, record every guess you make, and create the course folder with `aiu init`.

## Questions

Ask these five in one message, in the user's language, numbered so the user can answer in a few words. One message, because a course is not worth an interview; plain words, because most learners are not technical people.

1. What do you want to be able to do at the end? (1–2 sentences)
2. What do you already know about the topic?
3. How do you prefer to learn: by reading, by watching videos, by listening, or a mix?
4. How many minutes a day, and on how many days a week? (and by when, if there is a deadline)
5. Is there a real piece of your work or your own setting the tasks could be built on? (optional)

- Leave out every question the user has already answered, in the request or earlier in the conversation. Asking again tells them you were not listening.
- Say in the same message that unanswered questions get the defaults below, and that they can reply "go" ("давай") to skip the questions altogether (see *Auto mode*).
- Do not ask for the language: the course is written in the language of the conversation. Do not ask about constraints: record in `constraints` only what the user mentions on their own (no paid resources, a tool they cannot use).
- Ask once. When some answers are missing, use the defaults and record each one as an assumption rather than sending a second round: the user sees every assumption in the message below and on the syllabus page, and can correct it there. The only follow-up this phase allows is the *Scope check*.

Answers map to the brief:

- 1 → `goal`.
- 2 → `prior_knowledge` (in the user's words) and `level`.
- 3 → `learning_preference`: reading → `read`, videos → `watch`, listening → `listen`; a mix, or no answer → `mixed`.
- 4 → `session_minutes` = the minutes a day; `days_per_week` = the days; `hours_per_week` = minutes × days ÷ 60, rounded to 0.01 (20 minutes on 5 days is 1.67; 30 minutes on 4 days is 2); `weeks` = 8, or the number of weeks until the deadline. Never round `hours_per_week` to half an hour: the checks compute the length of a study day from `hours_per_week` and `days_per_week`, and it must come out as the minutes the learner gave.
- 5 → `practice_context`.
- The conversation's language → `language` and `source_languages` (*Defaults*). A start date, if the user names one, goes into `start_date` and puts calendar dates into `schedule.md`.

**Say what you understood.** Right after the answers (or the "go"), before any research, send one message in plain words: the goal as you understood it; every assumption you made, each with its reason (the time, the level, the way of learning, the scope, the language); and what happens next: you look for university programmes on the topic, design a syllabus and show it as a page in the browser (in light mode, in the chat), ask whether it is what they want to learn (unless they said "go"), then build module 1 and tell them where its page is. Say how long this first run takes: about an hour with the script; in light mode, a few answers in a row. Why: the learner sees what was decided for them before any work is spent on it, and can correct it in one reply.

## Defaults

| Field | Default | Comes from |
|---|---|---|
| `topic` | none (required) | the topic in the user's own words |
| `goal` | none (required) | question 1; if unanswered, or in auto mode, you write it as in *Auto mode* |
| `level` | `beginner` when nothing is known | question 2, see *Classify the topic* |
| `prior_knowledge` | `""` | question 2, in the user's words |
| `hours_per_week` | `5` | question 4: minutes × days ÷ 60, to 0.01 |
| `weeks` | `8` | question 4: 8, or the weeks until the deadline |
| `days_per_week` | `5` | question 4; a whole number 1–7, the study days of a week in `schedule.md` |
| `session_minutes` | `60` | question 4: the minutes a day; with no answer, one study day (`hours_per_week` × 60 ÷ `days_per_week`) |
| `learning_preference` | `mixed` | question 3: `read`, `watch`, `listen` or `mixed`; it changes how many videos and readings a module has (`references/sourcing.md`, *When to stop*), never the tasks |
| `language` | the language of the conversation, as a code (`bg`, `en`, …) | never asked |
| `source_languages` | `["en", <lesson language>]`; just `["en"]` for English lessons | the language |
| `depth` | `standard` | see *Classify the topic* |
| `approval_mode` | `confirm` | `auto` after "go" or with nobody to answer; `interactive` only when the user asks to review the syllabus and the first module (*Auto mode*) |
| `build_mode` | `incremental` | `full` only when the user asks for the whole course at once (*Auto mode*) |
| `domain_type` | no default: classify | see *Classify the topic* |
| `topic_velocity` | no default: classify | see *Classify the topic* |
| `practice_context` | `""` | question 5 |
| `constraints` | `[]` | only what the user mentions on their own, one item each |
| `assumptions` | `[]` | every guess you made, one full sentence each |
| `style_notes` | `[]` | stays empty until Checkpoint 2 |
| `start_date` | `null` | a date the user names, `YYYY-MM-DD` |

The rendered pages get Bulgarian or English labels; for any other language code the labels fall back to English, while the lessons are still written in that language.

`assumptions` are written for the learner: the course `README.md` prints them as they are. Write each in the course language, with no rule or warning codes (`S9w`), field names, untranslated values (say what `applied` means, not the word) or file names: they mean nothing to a learner. State only what is true of the finished course: an assumption that sources are read in a language holds only if that language was searched. Before `aiu finalize`, re-read the list and correct every assumption the build did not keep, e.g. "No usable sources in the lesson language were found, so all sources are in English."

## Auto mode

Two separate things, do not mix them up: who approves what, and whether you ask the questions at all.

**Who approves what** (`approval_mode`):

- `confirm` (the default): the learner confirms that the syllabus fits their goal before any module is built (`references/syllabus-design.md`, *Checkpoint 1*); the first module does not wait for them. Why: only the learner can say whether this is what they want to learn, but a beginner cannot judge whether a syllabus is correct, so the independent reviews check correctness before the learner sees it.
- `auto`: nobody is asked. Set it when the user says "go" (see below) or when the environment does not let you ask; say in the assumptions that the syllabus was not shown for confirmation because they asked you to go ahead.
- `interactive`: the learner reviews both the syllabus and the first module before you go on. Set it only when the user asks for that in their own words, and say in the assumptions that they asked to review.

**Skipping the questions.** When the user says "go", "just go", "no questions", "давай", "без въпроси" or anything similar, in the request or in reply to your questions, or when the environment does not let you ask (you run as a subagent, in a scheduled job, or with nobody to reply), ask nothing more and set `approval_mode` to `auto`. "Go" never means "let me approve later": do not stop at a checkpoint the user did not ask to review.

**One module at a time.** `build_mode` is `incremental` unless the user asks for the whole course at once ("build the whole course", „направи целия курс наведнъж“). "Go" skips questions; it does not mean "build everything", and you still stop at `wait_for_learner`. Why: a module built weeks before it is studied uses older sources and is wasted if the learner stops; one built when the learner reaches it costs only what is studied and uses what is new that day. See `references/quality-gates.md`, *Building by module*.

When you skip the questions:

- Keep every answer the user did give; take the defaults for the rest.
- Write the goal yourself: one "I can …" sentence in the course language that is concrete, observable and reachable within the budget from the inferred level. Backward design starts from this sentence, so a vague goal gives a vague course.
- Record **every** assumption in `brief.assumptions` as a full sentence a learner can read and dispute, with its reason: "Lessons are in English because the conversation is in English.", not "lang=en". The learner sees these sentences in the message after the questions, in the course `README.md` and in "How this course was made" on the page: that is where they learn what you decided for them.
- With `approval_mode` `auto`, record both checkpoints with `--by auto` and do not wait for a reply: `aiu checkpoint --course <dir> --name syllabus --by auto`, later `--name pilot --by auto`. You still send the message from *Say what you understood*.
- Auto mode skips questions, not checks. Every gate and iron rule still applies.

## Classify the topic

Decide these four fields yourself and add each choice to `brief.assumptions` with its reason, e.g. "Domain type is analytical because the goal is an argued assessment, not a working tool." A wrong guess is then corrected at Checkpoint 1 instead of being discovered in module 3.

**`level`**, from the answer to question 2: `beginner` (no experience, or only casual exposure), `intermediate` (knows the basics and does simple tasks unaided), `advanced` (works with the topic regularly and wants depth or a specialism). Between two levels choose the lower: a first module that is too easy costs an hour, one that is too hard loses the learner.

**`domain_type`**, by what the goal asks the learner to do, not by the subject's name. Read every verb of the goal and match it to the table. Why: the type decides the kind of tasks and the capstone (`references/practice-design.md`), so a wrong type gives the whole course the wrong practice.

| `domain_type` | The goal asks the learner to | Typical subjects | The goal is shown by |
|---|---|---|---|
| `technical` | build, configure or test a working tool or system | programming, security, data | a working product or an audit with evidence |
| `analytical` | understand the causes and effects of decisions or phenomena and judge the evidence about them | economics, policy, history, geopolitics, law | an analytical report or a case dossier |
| `applied` | do a concrete personal or professional task | communication, management, craft | a portfolio of produced materials |
| `mixed` | both: understand causes and effects, and do a concrete task | any subject whose goal has both parts | both kinds of product |

- When the goal has both parts, choose `mixed`, never the type of the doing part alone. Then every module needs at least one task of analysis, source comparison or argued writing (`references/practice-design.md`, *Domain adaptation*). Why: a goal that names causes and effects is not shown by calculations and filled-in forms.
- "Statistics" is `technical` when the goal is to build an analysis and `analytical` when it is to judge published studies.

Worked example, an economics topic. Topic "How inflation affects the family budget"; goal "I can explain why prices rise, calculate how inflation changes my household's costs and draw up a budget that allows for it." "Explain why prices rise" asks for causes and effects (`analytical`); "draw up a budget" is a concrete personal task (`applied`). Both are in the goal, so `domain_type` is `mixed`, and each module pairs a calculation task with an analytical one, e.g. "Two sources explain this year's price rise differently: name the cause and the evidence each gives, and argue which fits the official figures better." With the goal "I can explain why inflation rose in my country in the last two years" the type is `analytical`; with "I can keep a monthly household budget in a spreadsheet" it is `applied`.

**`topic_velocity`**, how fast knowledge in the topic goes out of date; phase 4 uses it to decide how recent sources must be. `fast`: AI, software versions, law and regulation, markets, medical guidelines. `stable`: foundations, history, classical methods. `medium`: everything else. When a topic mixes both, classify by the part the goal depends on.

**`depth`**: `standard` unless the user asks for a lighter overview (`lite`) or a more thorough course (`deep`). It sets the budgets of every later phase:

| | `lite` | `standard` | `deep` |
|---|---|---|---|
| Benchmarks (min–max) | 2–3 | 3–5 | 5–8 |
| Benchmark queries (cap) | 6 | 12 | 20 |
| Video segments per module | 1–2 | 2–4 | 4–6 |
| Readings per module | 1–2 | 3–5 | 5–8 |
| Queries per module: video / web (cap) | 4 / 4 | 8 / 8 | 12 / 12 |
| Lesson: minimum words (checked) | 600 | 1200 | 2000 |
| Lesson: target words | 600–1200 | 1200–2500 | 2000–4000 |
| Independent tasks per module | 1 | 1–2 | 2–3 |
| Recall questions per module | 3 | 5 | 8 |

## Scope check

Total hours = `weeks` × `hours_per_week` (40 with the defaults). About 15% of that goes to the capstone and about 10% to a reserve, and a module takes 3–8 hours (1–3 when the total is under about 10 hours: `references/syllabus-design.md`, *Time budget*), so the budget buys a handful of modules, not a degree. The goal does not fit when it needs more separate sub-fields than you can give a module each, or when the topic joins two disciplines, such as "geopolitics and economics" in 40 hours.

If it does not fit, propose 2–3 concrete narrowings, each with one sentence on what is left out, and ask which one the user wants. For example:

- "Web development", 40 h: (a) front-end basics with HTML, CSS and a little JavaScript, leaving out servers and databases; (b) one small data-backed web app in a single framework, leaving out visual design.
- "Geopolitics and economics", 40 h: (a) economic sanctions: how they work and whether they reach their aims, leaving out military alliances; (b) energy security in one region, leaving out trade theory and the rest of the world.

In auto mode choose the narrowest option that still covers the goal: a narrow course that gets finished beats a broad one that gets skimmed. In both modes write the chosen scope into `brief.assumptions` (what is in, what is out), make the `goal` match it, and keep the left-out parts for "what stays out of the course" at Checkpoint 1.

## Write the brief

1. Write the brief as one JSON object with every field from *Defaults*; `learning_preference` is one of `read`, `watch`, `listen`, `mixed`. `aiu init` checks only `topic` and `goal`; a field you leave out is filled from a fixed fallback that knows nothing about this conversation (its `language`, for instance, is always `bg`). The other fields are checked later by rule S1 of `aiu validate --stage syllabus`, so get the allowed values right now: `language` is a code such as `bg`, `en` or `bg-BG`, never a name like "Bulgarian", and `start_date` is `null` or `YYYY-MM-DD`.
2. Save it as UTF-8 to `<root>/.scratch/brief.json`, where `<root>` is the folder you will pass to `init` as `--root` (usually `courses`, so `courses/.scratch/brief.json`). This is the one file written outside the course folder, and it is not a breach of iron rule 12: the rule protects a course folder, and before `init` none exists, so the brief has nowhere else to go. `init` creates the folder from it; from then on the brief lives in `course.json`, the scratch file is not read again, and everything you write goes inside the course folder, with scratch files for `aiu` (such as an `--extract-file`) in its `research/scratch/`.
3. Run `aiu init --root courses --title "<topic as the user said it>" --brief <file>`. The title is what the learner sees, so keep the user's words. The folder name (slug) is derived from it, with Cyrillic transliterated; for any other non-Latin script, or to shorten it, add `--slug` with lowercase ASCII words joined by hyphens. Use another `--root` only when the user names another location.

A complete brief for a technical topic, where the user answered questions 1–3 and said on their own that they can use free tools only:

```json
{
  "topic": "SQL for data analysis",
  "goal": "I can answer everyday business questions from a company database with SQL queries I write and check myself.",
  "level": "beginner",
  "prior_knowledge": "Uses spreadsheets every day; has never written a query.",
  "hours_per_week": 5,
  "weeks": 8,
  "days_per_week": 5,
  "session_minutes": 60,
  "learning_preference": "read",
  "language": "en",
  "source_languages": ["en"],
  "depth": "standard",
  "approval_mode": "confirm",
  "build_mode": "incremental",
  "domain_type": "technical",
  "topic_velocity": "stable",
  "practice_context": "",
  "constraints": ["Free tools only."],
  "assumptions": [
    "No time was given, so the default of 60 minutes a day on 5 days a week for 8 weeks applies.",
    "Lessons are in English because the conversation is in English.",
    "Level is beginner because the learner has never written a query.",
    "Domain type is technical because the goal is shown by working queries with checked results.",
    "Topic velocity is stable because core SQL changes slowly; product-specific features are out of scope.",
    "Depth is standard because the user asked for neither a quick overview nor an in-depth course."
  ],
  "style_notes": [],
  "start_date": null
}
```

For an analytical topic only the content changes, e.g. a course on current sanctions policy has `"domain_type": "analytical"` and `"topic_velocity": "fast"`.

`init` prints one JSON object; `data` holds `course_dir`, `course_id`, `title` and `created`. Use `data.course_dir` (written with forward slashes, which every shell accepts) as `--course` in every later command, in quotes if it contains a space. `init` also creates the `research/` and `modules/` folders and an empty `research/benchmarks.json`.

Repeating `init` changes nothing: when `course.json` already exists in that folder it returns `"created": false` and ignores the brief file. That makes it safe after an interruption, but it is not the way to change a brief; edit `brief` in `course.json` instead. If `created` is false for a course you did not mean to resume, another course already has that slug: pick a different `--slug`. An `E_USAGE` error (exit code 2) names the problem, usually an empty `topic` or `goal`.

Next, `aiu status --course <dir>` returns `research_benchmarks`: continue with `references/syllabus-design.md`.
