# Coding guide: GenAI policies in course syllabi (v1)

Adapted from Ali et al. (SIGCSE 2025), "Analysis of Generative AI Policies in
Computing Course Syllabi." Their scheme was built for a single 2023–24 snapshot;
this version adds a `none` category and per-assessment scope so it works across
terms before and after ChatGPT's release (Nov 2022).

Unit of coding: one syllabus = one course offering (course × term × instructor).
Code only what the syllabus states. When unsure, pick the more conservative
label and write a note.

## 1. ai_policy (required, pick one)

| Code | Rule | Maps to our original 3 tiers |
|---|---|---|
| `none` | No rule about students using AI tools. A generic "work must be your own" with no mention of AI also counts as none. | (new) |
| `prohibited` | AI use is banned for all graded work. | fully restricted |
| `permission_required` | Allowed only if the instructor explicitly approves, case by case. | (new) |
| `partial` | Allowed for some activities, banned for others (e.g. OK for debugging, not for writing solutions). | limited use |
| `permitted` | Allowed for most or all work, possibly with citation. | fair use (with citations) |

Decision order: is there any AI rule? → is anything allowed? → is everything
allowed? → is it conditioned on permission?

## 2. scope (per assessment type)

For each of homework, projects, take_home_exams, proctored_exams, writing,
studying_learning: `allowed`, `prohibited`, `conditional` (allowed with
conditions such as citation or a use restriction), or `not_specified`.
A blanket rule applies to every type the course has.

## 3. Binary codes

- `citation_required`: must cite or disclose AI use (any format).
- `detection_mentioned`: mentions detection software or that the instructor checks for AI use.
- `ai_is_course_content`: AI/ML is a subject of the course. Code separately from
  the policy; an ML course can still have ai_policy = none.

## 4. stance

`encourages` / `discourages` / `neutral`. Code encourages or discourages only
when the syllabus goes beyond the rule itself (e.g. "try it!", "don't even think
about it", warnings about consequences for learning). Otherwise neutral.

## 5. implications (multi-select)

Reasons the syllabus gives: `veracity` (outputs may be wrong), `privacy`,
`hindering_learning`, `skill_development`.

## 6. tools_named

Free text list: ChatGPT, Copilot, Claude, Gemini, etc.

## 7. assessment weights

Each graded component with its percent and a category: homework, project, lab,
quiz, proctored_exam, take_home_exam, participation, other. Code an exam as
take-home only if the syllabus says so. These feed the AI-exposure measure in
the grade analysis, since AI can only affect grades through unproctored work.

## Process

1. Two coders independently code the same pilot set (~50 syllabi) in
   `labels/human_labels.csv`.
2. `python src/validate.py agreement` → kappa per field and a disagreements file.
3. Meet, resolve every disagreement, update this guide where the rule was
   unclear, record the final answer in `labels/gold.csv`.
4. Run the LLM on the same docs, then `python src/validate.py llm`.
5. Read `labels/llm_errors.csv`; revise the prompt or this guide, bump the
   version numbers, repeat until agreement is acceptable. Then scale.
