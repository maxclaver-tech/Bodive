def create(topic):
    return f"""# {topic.title()} Experiment Workbook

Use this workbook to evaluate one {topic.lower()} workflow over seven days.

## 1. Choose an outcome
Write the job in one sentence. Specify the deadline and what evidence will count
as completion. Record any constraint you cannot change this week.

## 2. Measure the baseline
Run the workflow once as you normally would. Record hands-on minutes, waiting
minutes and the number of corrections. Note the most expensive handoff.

## 3. Change one step
Write a hypothesis in this form: 'Changing ___ should reduce ___ from ___ to ___.'
Keep the remaining steps constant. Decide in advance when you will roll back.

| Date | Trial | Hands-on minutes | Waiting minutes | Corrections | Evidence |
| --- | --- | --- | --- | --- | --- |
| | Baseline | | | | |
| | Change | | | | |
| | Repeat | | | | |

## 4. Decide
Calculate the change in hands-on time and corrections. Keep the change if it
meets your target without increasing corrections. Repeat the trial if results
disagree. Record the decision, its owner, and the date you will revisit it.
"""


def prompt_for(dossier):
    topic = dossier["evidence"]["topic"]
    return (
        f"Write an original English Markdown workbook to help someone practice {topic}. "
        "Include a concrete example, exercises, reusable worksheets and acceptance criteria. "
        "Do not copy existing products or quote third-party content. Do not make market claims, "
        "invent statistics, insert links, or request external actions. Return the workbook only."
    )
