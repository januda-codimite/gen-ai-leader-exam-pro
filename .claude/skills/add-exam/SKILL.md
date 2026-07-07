---
name: add-exam
description: Add a new certification exam (e.g. a new ExamTopics-sourced practice exam) to this exam simulator app. Use when the user asks to add/import/scrape a new exam, add a new exam bank, or wire up a new certification into index.html.
---

# Add a new exam to the simulator

This repo is a single-page exam simulator (`index.html`) backed by per-exam question
arrays and a markdown archive in `db/`. Adding a new exam touches three things:
`scrape_examtopics.py` (source), `db/<id>_exam_questions.md` (archive), and
`index.html` (the actual app data). The quiz UI itself (exam picker, timer, scoring,
review screen) is fully generic and reads from a single `EXAMS` registry — **never
edit UI/markup/JS logic to add an exam**, only add data.

## 0. Check if the exam is already configured

```bash
grep -n "EXAM_CONFIGS = {" -A 60 scrape_examtopics.py
```

If the exam isn't listed, add an entry to `EXAM_CONFIGS` in `scrape_examtopics.py`:

```python
'newexam': ExamConfig(
    name='NEWEXAM',
    full_name='Full Official Exam Name',
    discussion_path='/discussions/<vendor>/',   # e.g. /discussions/google/, /discussions/amazon/
    filter_pattern='<string that appears in matching discussion titles>',
    default_pages=100,   # rough guess; auto-detected at runtime anyway
    output_file='<newexam>_exam_questions.md'
),
```

Also add the new choice to `--exam` in `main()`'s argparse `choices` list (it's
derived from `EXAM_CONFIGS.keys()` already, so this is automatic — just confirm).

## 1. Scrape ExamTopics into a markdown archive

```bash
source .venv/bin/activate   # requests, bs4, lxml already installed here
python scrape_examtopics.py --exam <id> --pages <N>   # omit --pages to auto-detect
```

This writes `db/<id>_exam_questions.md` and prints line/size stats. It resumes from
`scrape_progress_<name>.json` if interrupted — pass `--clean` to start over. Delete
the progress file once done; don't leave it committed.

The scraper pulls the **community-voted answer and top comment** as `desc`, which is
often terse, hedgy, or references "the other options" without explaining why. Treat
the generated `.md` as raw material, not final copy — step 3 rewrites it.

## 2. Convert the markdown into a JS question array

There is no automated md→JS converter (this was done by hand/by-agent last time) —
read `db/<id>_exam_questions.md` and transform each `## Topic X Question Y` block into
one object, matching the exact schema already used by `GAIL_QUESTIONS` /
`PCA_QUESTIONS` in `index.html`:

```js
{
  topic: 1,                 // number; matches the md's "Topic N"
  num: "1",                 // string or number, either works — just be consistent per exam
  q: "Question text…",      // \n allowed for multi-paragraph questions
  opts: ["Option A text", "Option B text", "Option C text", "Option D text"],
  ans: [1],                 // 0-based indices of correct option(s); letter A=0, B=1, C=2…
                             // multi-answer questions ("Choose two/three") get multiple indices
  desc: "Why the correct answer is right, and briefly why each distractor is wrong.",
  images: ["https://…"]      // OPTIONAL — only when the md has an "**Images:**" block
},
```

Notes learned from doing this for GAIL and PCA:
- `ans` may be a bare int (`ans:1`) or an array (`ans:[1]`) — the app normalizes both
  via `normAns()` — but prefer the array form for new exams, it's unambiguous for
  multi-answer questions.
- Escape embedded `"` and use `\n` for line breaks inside the JS string literals;
  scraped question text sometimes contains quotes, code snippets, or stray HTML
  entities — clean those up while converting.
- Preserve topic numbering from the md so `topicNames` (step 3) can map topic → name.

Append the new array as its own top-level `const`, e.g.:

```js
const NEWEXAM_QUESTIONS = [ /* … */ ];
```

placed alongside the existing `GAIL_QUESTIONS` / `PCA_QUESTIONS` arrays, immediately
before `const EXAMS = {`.

## 3. Rewrite explanations to match house style

This is the step that produced the "updated pca explanations" follow-up commit last
time — don't skip it. For every question, rewrite `desc` (using your own knowledge,
not just the scraped comment) into 3-6 sentences that:
1. state *why* the correct option is correct,
2. explain *why each wrong option is wrong* (not just "this is incorrect"),
3. read as a standalone explanation with no reference to "the community" or vote counts.

Look at existing `GAIL_QUESTIONS`/`PCA_QUESTIONS` entries in `index.html` for the exact
tone/length to match.

## 4. Register the exam in `index.html`

Add an entry to the `EXAMS` object (search for `const EXAMS = {`):

```js
newexam: {
  id: 'newexam',
  title: 'Full Official Exam Name',
  shortTitle: 'NEWEXAM',
  subtitle: 'NEWEXAM Exam Simulator — ExamTopics Practice',
  paceMinPerQ: <official_exam_minutes> / <official_exam_question_count>,
  passPct: <official_passing_percentage>,   // 70 for both existing exams; check the real exam
  defaultCount: null,   // or a number to cap the default question-count picker (PCA uses 50)
  topicNames: {},        // optional map: {1:"Topic name", 2:"Topic name", …} — {} just shows "Topic N"
  questions: NEWEXAM_QUESTIONS
},
```

That's the entire integration — `buildExamCards()`, `selectExam()`, scoring, timer,
and the review screen all iterate `Object.values(EXAMS)` / read `currentExam.questions`
generically. No other file needs to change.

## 5. Verify

- Open `index.html` in a browser (or via the `run` skill) and confirm the new exam
  card appears on the picker screen with the right question/topic counts, and that a
  full run-through (start → answer → submit → review) works.
- Sanity-check a handful of `ans` indices against the md's `**Correct Answer:**`
  letters — an off-by-one here silently grades questions wrong.
- Don't leave scratch files behind: remove `scrape_progress_<name>.json` and any
  `*.bak` files before finishing; they have no reason to be committed (see git
  history — a stray `db/gail_exam_questions.md.bak` had to be cleaned up after the
  fact).
