# Practice design - phase 4, step 3: tasks, answers and the capstone

Tasks are where the outcomes are tested: every "I can …" promise of the syllabus needs a task that shows it. This step writes `practice.md` (statements and hints), `answers.md` (solutions), the task records in `module.json` (what is handed in and how it is scored) and, in phase 5, `capstone.md`.

## The ladder

Each module climbs four kinds of task, from supported to independent:

| `kind` | What it is | How many per module |
|---|---|---|
| `guided` | An exercise with 2–3 graded hints hidden in `<details>` | every outcome in at least one; one task may cover several outcomes |
| `independent` | A new situation without hints: transfer of what was learned | `lite` 1, `standard` 1–2, `deep` 2–3 |
| `project` | The module's step of the capstone | exactly 1 |
| `recall` | Short questions to recall key ideas and terms | one task holding 3 / 5 / 8 questions (`lite` / `standard` / `deep`) |

From the second module on, the `recall` task includes at least two questions from earlier modules, each marked with its module in brackets ("(M01)"). Why: recall spread over weeks keeps knowledge far better than recalling only today's lesson. The page gives every task a "Check my answer" button that copies the task and its criteria into a prompt for any AI assistant, so write every criterion so that it can be understood without the lesson.

The gate (rule M9) refuses a module in which an outcome has no `guided` task (a `create` outcome too, even when the project step is its real evidence: give it a short guided warm-up on a small invented case, or let a guided task that serves another outcome cover it) or there is no `independent` task, and warns (M9w) unless there is exactly one `project` task. The `project` task is the capstone step already named in the module's `summary` and in `capstone.description` at Checkpoint 1: build that step, not a new one, so the steps add up to the capstone.

**Fit the module's hours.** Before `aiu module set-status --course <dir> <ID> drafted`, add up what the module asks of the learner and compare it with its `hours` × 60 minutes:

- the lesson: its words ÷ 200 (about 200 words a minute);
- each video segment: its length in minutes (`end_sec` − `start_sec`, ÷ 60), once, even when two outcomes use the same segment with the same bounds;
- each task: its `minutes`; a source section a task sends the learner to read counts in that task's minutes, at the reading speed below;
- each standalone reading, one that no task owns (a resource with role `reading` that no task sends the learner to): its words ÷ 200 when it is in the lesson's language; a source in another language (usually English for a non-English course) takes a beginner or intermediate learner about 130 words a minute, so divide by 130. Why: a learner reading a foreign language for meaning is far slower than in their own, and a plan that ignores it overruns its first day.

The sum should come within about ±25% of the module's minutes: 45–75 for 1 hour, 90–150 for 2 hours. Over it, cut what no outcome needs: let one guided task cover several outcomes (list them all in `outcome_ids`; rule M9 accepts it), shorten a segment to what its `after_task` needs, trim the lesson toward its minimum. Under it, add practice, not lesson text. No gate checks this sum, so it is your job. Why: the schedule tells the learner a module takes its hours, and one that takes far longer breaks the plan in its first week. Illustrative, a 1-hour `lite` module with 2 outcomes: lesson 700 words (3.5 min) + segments of 3 and 4 min + one guided task covering both outcomes (15) + independent (12) + project (10) + recall (5) = 52.5 min, inside 45–75.

Record every task in `module.json` `practice`:

- `id`: `M01-P1`, `M01-P2`, … with the module's own prefix, each used once. Number the guided tasks first, then independent, project and recall.
- `kind`, `title` and `minutes`: every task needs a non-empty `title` and `minutes` above 0 (rule M9), and the module page shows both. Estimate minutes honestly, for a learner at the brief's `level`; they count toward *Fit the module's hours*.
- `outcome_ids`: the outcomes the task shows, as many as it really tests; required for `guided` and `independent`, and worth filling for the others.
- `deliverable` and `criteria` for `guided`, `independent` and `project` (see *Rubrics*). A `recall` task has `"deliverable": ""` and `"criteria": []`.

## Task anatomy

In `practice.md` (start from `assets/practice-template.md`), each task has:

- the marker `<!-- practice: M01-P1 -->` on its own line (rule M10);
- a heading with id, title, kind and time: `## M01-P1 - <Title> (guided, 20 min)`;
- `**Outcomes:**` with the outcome ids;
- `**Task.**` with the statement: the situation, the material to work from, and what to produce. The learner must be able to start without asking anything.
- for a `guided` task, 2–3 hints, each in its own `<details><summary>Hint 1</summary> … </details>` block, graded: a direction, then a partial move, then nearly the solution. Hidden hints let the learner take only as much help as needed. An `independent` task has no hints.
- for the `recall` task, the questions, numbered.

Keep the template's line that sends the learner to the module page for what to hand in and how tasks are scored. Translate the labels into the course language; keep the markers exactly as they are.

A task's scenario must contain every fact its criteria ask for: if a criterion scores "names the device and system", the scenario names them, or the criterion accepts "says it must be asked". Invented data looks invented: `.example` domains, documentation IP ranges (192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24), phone numbers written as `0888 XXX XXX`, never a number that could belong to a real person. Amounts use the currency the learner's country uses today: check it rather than assume it (Bulgaria, for example, moved from the lev to the euro on 1 January 2026), because a stale currency makes the whole scenario look out of date.

In `module.json`, the record of a task (illustrative):

```json
{
  "id": "M01-P1", "kind": "guided", "outcome_ids": ["M01-O1"], "title": "Five emails", "minutes": 20,
  "deliverable": "A short written answer",
  "criteria": [
    {"text": "Names the decisive sign", "points": 2},
    {"text": "Justifies the choice", "points": 2},
    {"text": "States it clearly", "points": 1}
  ]
}
```

and of a `recall` task:

```json
{"id": "M01-P6", "kind": "recall", "outcome_ids": ["M01-O1", "M01-O2", "M01-O3"], "title": "Recall", "minutes": 10, "deliverable": "", "criteria": []}
```

## Rubrics

Every `guided`, `independent` and `project` task has 3–5 criteria, each `{"text": "…", "points": n}` with `points` of at least 1 (rule M9). A `recall` task has none.

- Each criterion names an observable quality of the answer, something a reader can find in it or not: "Names the evidence each source relies on", not "Understands the sources".
- Derive the criteria from the outcome statement, so that meeting them shows the outcome.
- Every requirement the task statement sets (each thing to produce, each condition such as "include at least one item the lesson does not list") is scored by at least one criterion and met by the model answer in `answers.md`. Check them pairwise before you finish the task. Why: a requirement no criterion scores tells the learner it does not matter, and a model answer that skips it fails its own task.
- Give the most points to what decides the outcome and fewer to form.
- Write criteria and `deliverable` **only** in `module.json`. `aiu render` shows them on the module page next to the task. Repeated in `practice.md`, the two copies would drift apart and the learner would not know which one counts.

## Answers file

`answers.md` (start from `assets/answers-template.md`) opens with a line telling the learner to read it only after trying the tasks. For every task, `recall` and `project` included, it has the marker `<!-- answer: M01-P1 -->` (rule M10), followed by:

- **Model answer**: a full solution at the level of the brief that meets every requirement of the task statement;
- **By criterion**: what earns the points of each criterion;
- **Common mistakes**: the usual wrong turns and why they are wrong;
- for an open task (an argued position, a design, a project step): **what a strong answer contains**, because no single answer is right.

A fact in a model answer carries a citation, as in the lesson. None of this appears in `practice.md` (iron rule 8); an `<!-- answer:` marker in `practice.md` fails rule M10. The reviewer checks that the answers are correct.

## Domain adaptation

`brief.domain_type` decides what the tasks and the capstone look like. The example tasks are illustrative:

| `domain_type` | Kinds of tasks | Capstone | Example task |
|---|---|---|---|
| `technical` | work with a tool, set something up, find a bug, run a small experiment | a working product or an audit with evidence | Given a small dataset with three planted errors, find each with the tool from the lesson and show the step that exposes it. |
| `analytical` | analyse a real decision or case, compare sources with different positions, write an argued position, make a forecast with a date to check it | an analytical report or a case dossier | Two published reports reach opposite verdicts on one policy: list the evidence each relies on and argue which is stronger. |
| `applied` | produce a real material, build a checklist, rework something against criteria | a portfolio of produced materials | Rework the supplied announcement against the lesson's five criteria and mark which criterion each change serves. |
| `mixed` | both kinds; in every module at least one task of analysis, source comparison or argued writing | one product that shows both parts of the goal, e.g. a worked plan with an argued analysis | Build the small cost model the lesson describes, then write a half-page recommendation from its result. |

- **`mixed`: analysis in every module.** At least one `guided`, `independent` or `project` task per module asks the learner to explain a cause or an effect with evidence, compare sources that differ, or argue a position with reasons. A task that only computes a number, fills in a table or copies figures from a source does not count, even when its outcome says `analyze`. Why: the goal names causes and effects (`references/intake.md`, *Classify the topic*), and arithmetic alone never shows them.
- An `independent` task puts the skill into a **new** context: another case, dataset, audience or period than the guided exercise, not the same exercise without hints. Transfer is what shows the outcome was learned.
- If `brief.practice_context` names the learner's real environment or work, build the tasks on it, within *Safety* below: a task on the learner's own material is the one that gets finished.
- The scripts know nothing about the topic and will not notice a task that misfits the domain; keeping this rule is your job.

## Day-by-day plan

The learner asked for a course they can simply follow: "today I do this". After the tasks are written and *Fit the module's hours* is done, split the module into study days in `module.json` `study_plan`. One study day is `hours_per_week` × 60 ÷ `days_per_week` minutes (60 with the defaults of 5 hours and 5 days); a 5-hour module is then five days. `aiu render` numbers the days across the course, places them in weeks (and on dates when `start_date` is set) and prints them in the module page and in `schedule.md`.

```json
"study_plan": [
  {"day": 1, "minutes": 60, "items": ["Урок: раздел „Какво е фишинг“", "Видео S1, 02:10–08:45: кои признаци вече не стигат", "Задача M01-P1"]},
  {"day": 2, "minutes": 55, "items": ["Урок: раздел „Проверка на подателя“", "Четиво S3, раздел 2", "Задача M01-P2"]}
]
```

- `day` runs 1, 2, 3, … within the module; `minutes` is your honest estimate for that day; `items` say, in the course language and in order, exactly what to open: a lesson section by its heading, a video by its `S` id and segment, a reading by its `S` id and section, a task by its id.
- Every task id and the `S` id of every `video` and `reading` resource must appear on some day (rule M13), so nothing in the module is left off the route. Give a long task its own day; split nothing a learner has to do in one sitting.
- Keep each day near the study day's length and the whole plan within ±25% of the module's hours (warning M13w). Put the recall task on the last day, and the material before the task that needs it.
- Order each day by `brief.learning_preference`: `read` puts the lesson section and the reading first; `watch` puts the video first; `listen` puts the video first, or the lesson section the page can read aloud; `mixed` uses whatever order suits the material. For `listen`, say in the video item that it can be just listened to (e.g. "Видео S1, 02:10–08:45 (може само да се слуша)"). The tasks are the same for every preference.
- A whole video kept as an optional extra (role `reference`, *Blocked subtitles* in `references/sourcing.md`) may appear on a day as "Видео S3 (цялото, по желание)"; its time does not count in the day's `minutes`.

## Safety

Iron rule 10, applied to tasks:

- **Security and other dual-use topics.** Frame the work as defence: recognise, detect, prevent, recover. Hands-on work happens only on systems the learner owns or on intentionally vulnerable training labs built for practice. Give no operational steps against third-party systems, people or organisations, even when a source contains them; teach the defensive lesson instead. Exercises that involve deceiving people use invented scenarios, never real colleagues or strangers.
- **Medicine, law and finance.** Keep the purpose educational: tasks work on published guidelines, laws, judgments, filings or studies, read from primary sources. Never ask the learner to diagnose themselves, settle their own legal matter or choose their own investments, and say in such a task that it is not personal advice.
- When `practice_context` would need something unsafe, such as testing a system the learner does not own, move the task to a training lab or a published case and say why in the task statement.

## Capstone

`capstone.md` in the course folder describes the final project. Write it in phase 5 (`references/quality-gates.md`, *Finalize*), in the course language, from the `capstone` record in `course.json`. It contains:

- **Description**: what the learner builds and how it shows the goal of the brief;
- **Final product**: what is handed in, matching `capstone.deliverable`;
- **Steps**: one per module, each naming that module's `project` task (e.g. "Step 2 - M02-P5") as in `capstone.description` and the module `summary`, then what is left to do in `capstone.hours` to join the steps into one product;
- **Criteria**: 3–5, each with points, for the finished product.

It needs at least 150 words (rule F3). Leave `capstone.title`, `deliverable` and `hours` in `course.json` as they are: they belong to the approved syllabus, and changing them sends `aiu status` back to `approve_syllabus`.
