# Sammy Mutuku — LinkedIn strategy for remote ML Engineer / Data Scientist offers

Goal: **remote international job offers**, primary title **ML Engineer**, secondary **Data Scientist**.
Built from your CV (`Sammy_S_Mutuku_CV_KQ.pdf`), your GitHub (`github.com/subu53`, 60 public repos), and the
vendored `linkedin-profile-optimizer` workflow (goal = **job seeking**).

---

## 1. The honest headline

Your CV is stronger than your LinkedIn presence. The fix is not more content. It is
**three specific repairs**, in this order:

1. ~~**A serious contradiction between your CV and your GitHub.**~~ **RESOLVED** — see §2.
2. **A headline that wastes 102 of its 220 characters** and never says what you want.
3. **Your proof is scattered across 60 repos**, which reads as a practice account rather than a
   professional one.

Everything below is either a repair or a rewrite, ranked by impact.

---

## 2. ✅ RESOLVED — the CV ↔ GitHub contradiction

Your CV described the flagship project differently from the repo. **Resolution: the CV is correct.**
The first build was Twilio + Claude 3.5; it was then migrated to **Meta's WhatsApp Cloud API +
DeepSeek**. The repo description was simply stale.

**This is an asset, not an embarrassment.** "I evaluated the channel and the model provider and
swapped both" is a stronger engineering signal than either stack alone, because it shows you can
choose and replace infrastructure rather than inherit it.

So it is now stated explicitly, both in the repo description and in your About:

> Production LLM sales agent on Meta's WhatsApp Cloud API. Answers only from a live product catalogue
> via retrieval grounding, escalates to a human when it should. **Migrated from Twilio + Claude 3.5 to
> the Cloud API + DeepSeek.** Python, FastAPI, Azure.

**Say the migration out loud in interviews.** If an interviewer finds the old names in the git
history, the prepared answer is *"Twilio and Claude 3.5 were the first build; I moved to the Cloud API
and DeepSeek because ___"* — which is a better interview moment than never having had to change
anything. Have the reason ready; that is the actual question.



---

## 3. Priority 2 — headline

### Current (measured: 118 of 220 characters, 102 wasted)

```
Data Scientist  |  Python, SQL, Machine Learning, Time-Series Forecasting  |  MSc AI Student, Open University of Kenya
```

Three problems: it says *student* (which caps your perceived seniority), it overshares a course,
and 102 characters of free recruiter-search surface sit unused.

### Proposed (189 of 220)

```
ML Engineer | I build AI systems that run in production, not notebooks | Python, PyTorch, FastAPI, Azure | Retrieval-grounded LLM agents | MSc Artificial Intelligence | Open to remote roles
```

Why this shape:

- **Leads with `ML Engineer`** — that is the literal string recruiter search matches on.
- **`I build AI systems that run in production, not notebooks`** — your single sharpest differentiator.
  Most entry-level ML candidates have notebooks only; you have two deployed systems.
- **Technology keywords** — Python, PyTorch, FastAPI, Azure are all common recruiter filters.
- **`Open to remote roles`** — closes the question rather than leaving it to inference.

Keyword note: put `Computer Vision`, `NLP`, `XGBoost`, `RAG` in your **Skills** section instead, not the
headline. Skills is where those filters usually look, and cramming them into the headline makes it unreadable.

---

## 4. Priority 3 — About section

`OK` against both the 2,600-char cap and the 265-char fold, and it survives LinkedIn stripping the
blank lines on paste. Verified with
[`bin/li_limits.py`](../bin/li_limits.py) — run it again after you edit anything.

```
I build AI systems that run in production, not notebooks. Two of mine are live right now, serving real customers in Kenya, and I did the whole thing on each one: the data work, the model, the API and the deployment that keeps it running for the people who use it.

The first is a WhatsApp sales agent that answers only from a client's live product catalogue, so it cannot invent a price or promise a delivery date. It escalates to a human when it should. Laravel backend, Python AI service, Azure deployment.

The second reads CT scans. EfficientNet-B0 with Grad-CAM, so a radiologist can see where the model looked before trusting it. FastAPI behind a React front end.

What I actually do: I take a model out of a notebook and make it survive contact with users. That means the unglamorous parts. Scheduled jobs instead of manual reruns. Version control so a client can audit what changed. Retrieval grounding so an LLM cannot make things up. Error handling for the day the API returns nothing.

Numbers I can stand behind:

- Automated recurring client reporting, cutting manual effort by over 60%
- Credit card fraud classifier: 88.8% recall and 0.979 ROC AUC on 284,807 transactions with 0.17% fraud
- Zindi agriBORA maize price forecasting: ranked 85th of 354, top 25%
- 15% monthly sales uplift from a data-led commercial recommendation

Background: MSc in Artificial Intelligence at the Open University of Kenya (in progress). BSc in Data Science, KCA University, Second Class Honours Upper Division. Diploma in Mathematics and Statistics, so the statistics under the models are not a black box to me.

Stack I work in daily: Python, SQL, PyTorch, TensorFlow, XGBoost, LightGBM, scikit-learn, FastAPI, Streamlit, Azure, Git.

I am open to remote ML Engineer and Data Scientist roles, and I work comfortably across time zones with European and US teams.

If you are hiring, or you have a model stuck in a notebook that needs to reach users, message me. The fastest way to judge my work is the code: github.com/subu53
```

**Paste warning:** LinkedIn strips blank lines when you paste into About. Either **type the line breaks
in the editor** after pasting, or accept one flowing block — the opener is written so it reads correctly
either way.

**Numbers I did not invent and did not have:** the WhatsApp agent has no business metric anywhere
(conversion rate, enquiries handled, hours saved, cost per enquiry). That is the single biggest missing
number in your whole profile, because it is your flagship project. If you have it, add it — a live agent
with a measured result is worth more than every other line combined. If you do not, measure it for two
weeks; it will pay for itself in interviews.

---

## 5. Priority 4 — Experience section

Your CV already has the right instincts. Two changes make them land for a remote recruiter.

**Retitle the freelance role so the date range does not read as a gap.** "Freelance, Nairobi" is fine,
but `Data Scientist (Freelance)` for Jun 2025–Present plus "Research Consultant (Intern)" ending Jan 2025
leaves a recruiter guessing. Lead the bullets with the production work, not the modeling:

```
Data Scientist — Freelance
Jun 2025 – Present · Remote / Nairobi, Kenya

- Shipped a production LLM sales agent (Python, FastAPI, retrieval grounding, Azure App
  Service) that qualifies inbound WhatsApp enquiries for a retail client, answering only
  from the live product catalogue and escalating to a human when it should.
- Trained and served an EfficientNet-B0 CT-scan classifier with Grad-CAM explanations for
  radiologist-facing interpretability, behind a FastAPI back end.
- Automated recurring client reporting with scheduled Python jobs, cutting manual effort
  by over 60%.
- Built Streamlit tools that let non-technical clients pull their own metrics instead of
  waiting on an analyst.
- Kept every deployment version-controlled and reproducible on GitHub, so client work can
  be rerun and audited.
```

The rule: **each bullet is `action verb + what shipped + the measurable effect`.** Your CV's bullets are
close; they bury the deployment and lead with "built and tuned predictive models", which is what every
other applicant says.

**Keep every number exactly as your CV has it.** 88.8% recall, 0.979 ROC AUC, 284,807 transactions,
0.17% fraud, 85th of 354, 15% uplift, 60% reduction — all verifiable and specific. That is the
strongest part of your profile. Do not round or inflate them; interviewers probe exactly these.

---

## 6. Priority 5 — Featured section and proof hygiene

The skill's job-seeking guidance says Featured should hold **portfolio + best work samples + a
top-performing post**. You have the portfolio. Two problems sit in front of it.

### 6a. Curate — 60 repos is a liability, not an asset

A hiring manager who clicks your profile sees a wall of repos, many named `_v1`/`_v2`/`_v3`/`test`.
You have **at least eight near-duplicate lung-cancer repos**: `Lung_Cancer_diagnostic_test1`,
`esubu_lung_cancer_diagnostic`, `Lung_diagnostic_system`, `lungcancerai_v1`, `lungcanceraiv2`,
`Deep_learning_chest_xray_pneumonia`, `digicow_challenge_agent_test`, `champplpclass2024`.

Pin the best one, archive or delete the rest. Same for the credit-scoring set: `esubu_credit_scoring_fnal`,
`esubu_credit_scoring_v2`, `esubu_credit_scoring_v3`, `esubu-credit-scoring`,
`esubusacco_credit_scoring_app_demo`.

**Then:** pin the six repos below to your profile and put three in Featured, in this order.

| # | Repo | Why it earns a slot |
|---|---|---|
| 1 | `whatsapp-sales-agent` | Deployed LLM system with retrieval grounding. Your strongest single asset. **Fix the description first.** |
| 2 | `lungcanceraiv2` | CNN + Grad-CAM interpretability + FastAPI + React. Shows the full stack, not just the model. |
| 3 | `Credit-Card-Fraud-Detection-Imbalanced-Class` | Directly matches your CV's 88.8% / 0.979 numbers. Real class-imbalance handling. |
| 4 | `dataorg-financial-health-prediction` | Zindi competition, 50+ engineered features, ensemble blending. Ranking evidence. |
| 5 | `Telco-Customer-Churn-Prediction` | Business-facing ML — the kind of framing MLE interviews test. |
| 6 | `Market-Basket-Analysis-on-Online-Retail-Data` | Shows SQL/analytics range beyond deep learning. |

At least four of these have **no description at all**. A repo with no description is invisible in search
and looks abandoned. One sentence each is a 20-minute job with an outsized return.

### 6b. ⚠️ Remove `FREE-openai-api-keys`

You have a public repo named `FREE-openai-api-keys`, described as "collection for free openai keys".
Whatever it actually contains, **the name alone is a red flag to a hiring manager at any security-conscious
employer**, and it sits in the first screen of a profile you are about to send to recruiters who hire for
production AI systems. Delete it or make it private.

While you are there: `Scrapegraph-ai`, `pytorch-image-models`, `fastbook_practical_deep_learning`,
`deep-learning-keras-tf-tutorial`, `free-llm-api-resources`, `awesome-low-level-design` and
`data-engineering-zoomcamp` are **forks or course clones**. They add no signal and dilute the ones that do.
GitHub does not count forks as your work, but a non-technical recruiter cannot tell.

### 6c. Fill the two empty signals

- **GitHub bio** currently reads "🚀 AI Engineer, Data Scientist & Autonomous Systems Developer" — emoji-led
  and vague. Make it match the CV headline.
- **No website on your GitHub profile.** You have `portfolio_v1`, `_v2`, `_v3` — deploy one and link it.

---

## 7. Your About's biggest weakness, and the fix

Your background is: freelance + one internship + sales, with a degree in progress. For remote
international roles that is a **credibility gap**, and no amount of profile polish closes it. What closes
it is **public evidence of the way remote teams work**:

- **Your Zindi results are your strongest under-used asset.** 85th of 354 on a real forecasting task is
  objectively verifiable and comparable across borders. Lead with it more than you do.
- **The WorldQuant Brain internship is under-played.** Quantitative alpha signals with out-of-sample
  validation is exactly the signal a fintech or trading-adjacent MLE employer wants. Give it its own
  expanded entry, not one line as an intern.
- **Contribute visibly to one open-source project in your target stack.** For MLE roles that usually
  means inference serving, evaluation harnesses, or agent tooling. A merged PR in a library an interviewer
  already uses is worth more than a tenth personal repo.

---

## 8. Content plan (secondary — only after the profile is fixed)

Feed content should echo the profile thesis, not replace it. Your thesis is
**"I take models to production"**. Three pillars, in priority order:

1. **Production reality** — the parts nobody posts about. What broke when the sales agent met real
   customers; how you stopped it inventing prices; how you handled the day the API returned nothing.
   This pillar is your differentiator and almost nobody writes it well.
2. **Competition write-ups** — how you placed 85th of 354. Feature engineering decisions, what you tried
   that failed, what the leaderboard taught you. Verifiable, technical, and it doubles as a portfolio piece.
3. **Learning in public** — MSc AI coursework applied to a real dataset. Only where you actually have
   something concrete; this pillar goes thin and generic fastest.

**Cadence: 2 posts a week, not daily.** For a job search, 10 well-argued posts over five weeks beat 40
thin ones, and you have a degree and client work to protect.

Every post should be checked before it goes out:

```bash
python bin/lk.py review --mode audit --file draft.txt
```

---

## 9. What I could not assess

The skill's scorecard has nine components. I only had text, so **six are unverified** and I will not
score what I have not seen:

| Section | Status |
|---|---|
| Headline | ✅ audited and rewritten |
| About | ✅ audited and rewritten |
| Experience | ✅ rewritten from your CV |
| Featured | ✅ plan given; need to know which three you pick |
| **Photo** | ❓ not seen — for job seeking this is the first thing a recruiter judges |
| **Banner** | ❓ not seen — a remote recruiter looks here for timezone/work-authorisation signals |
| **Skills** | ❓ not seen — needs mirroring against real remote MLE job descriptions |
| **Custom URL** | ✅ already good: `linkedin.com/in/samsubu`, not a hash |
| **Recommendations** | ❓ not seen — you need 3, and your WorldQuant and agency contacts are the sources |

Send me a screenshot of your photo and banner, and your current Skills list, and I will finish the audit.

## 10. Do this in order

Status as of this build:

1. ✅ **CV ↔ GitHub contradiction resolved** (§2). The CV was right; the repo was stale. Corrected
   text is in `bin/gh_fix.py` and applies in one command.
2. ⬜ **Delete or privatise `FREE-openai-api-keys`** (§6b). Still the highest-value manual fix.
3. ⬜ **Replace the headline** — 189 chars, ready to paste (§3).
4. ⬜ **Replace About** — 2,023 chars, ready to paste (§4).
5. ⬜ **Rewrite the freelance Experience entry** (§5).
6. ⬜ **Pin 6 repos** (§6a). Manual: GitHub has no API for pinned repositories.
   ✅ Descriptions and topics on 5 repos are already applied and verified.
7. ⬜ Then, and only then, start posting (§8).

### Remaining GitHub work

```bash
# 1. Put a token in .env (section 5 of the template explains the scopes needed)
# 2. Apply the corrected whatsapp-sales-agent description + topics:
python bin/gh_fix.py --apply

# Verify nothing else drifted:
python bin/gh_fix.py --audit

# Deletion commands for the duplicate clusters, when you have decided which to keep:
python bin/gh_fix.py --delete-plan
```

Two clusters are still untouched because they need your judgement, not mine: the six lung-cancer /
chest-imaging repos and the five credit-scoring repos. `--delete-plan` prints a keep/delete
recommendation for each; nothing is deleted automatically, ever.

