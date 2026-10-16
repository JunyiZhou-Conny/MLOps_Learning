# L17 lecture slides — Evaluating and Monitoring ML Systems in Production

Source: deck `L17_evaluating_and_monitoring_ml_systems` (62 slides), "Lecture 17: Evaluating and Monitoring ML Systems in Production", AC215/E115, Pavlos Protopapas (SEAS/Harvard). These are the instructor's lecture slides (PDF), provided by the student for study; the PDFs are not in this repository; slide numbers are PDF page numbers. The page numbers printed in the slide footers fall behind the PDF numbering from slide 10 on (slide 10 is printed "9", slides 38–43 are printed 34–39, slides 55–59 are printed 41–45, and slides 16 and 17 both say "16"), so always cite the PDF number. Everything below is a summary in our own words. Quotes are limited to short titles, labels, names and formulas. L17 has no tutorial repository (`course/lectures.yaml`: `tutorials: []`, and the course tutorials page lists only the Ed lesson for this lecture). Where this digest compares the lecture's naming with "the tutorials", it means the repositories of neighbouring lectures, as recorded in our study guides (L07, L13, L15, L22, L23).

## Outline

- Slide 1 · Title: "Lecture 17: Evaluating and Monitoring ML Systems in Production".
- Slide 2 · "Announcements": an empty placeholder ("Add +").
- Slide 3 · Hook: "What Happens When Models Go Wrong Quietly in Production". $8B of one company's market value lost in a week after its model failed quietly for months (Zillow, shown with the "This is fine" dog meme).
- Slide 4 · Agenda with seven sections. The same agenda returns as a section divider, with the current section in bold, on slides 5, 9, 14, 30, 37, 45 and 54.
- Slides 5–8 · **1. Recap**. Divider (5). The project timeline, now highlighting the model-building and ML-workflow phase (6). The four-step cheese-app ML pipeline on GCP (7). Recap of the previous lecture: the cloud service spectrum and the "What Should I Use?" decision framework (8).
- Slides 9–13 · **2. Foundations: why production evaluation differs from offline evaluation**. Divider (9). A frozen test set against moving production data, and the key term "Training-Serving Skew" (10). Microsoft's Tay as the motivating example: the 16-hour timeline (11), the "repeat after me" exploit (12), the aftermath and the accidental relaunch (13).
- Slides 14–29 · **3. Monitoring Toolkit: layers of monitoring, data drift and concept drift**. Divider (14). Three layers: Data Quality, Model Performance, System Health (15). A matching quiz, as a question (16) and with the answer lines drawn (17). Data drift with the Kolmogorov–Smirnov test: the idea and rules of thumb (18), the math (19), the production set-up (20), making it reliable (21). Concept drift: prediction-to-outcome tracking (22), streaming detectors (23), label-free estimation with NannyML's CBPE (24), the tools teams use (25). When to retrain (26). Rollout strategies (27), a fraud-detection question (28) and its worked example (29).
- Slides 30–36 · **4. Case Study: Zillow, a $500M+ production ML failure**. Divider (30). The losses in numbers (31). "Any guesses?" (32). What happened: the 2021 housing market moved faster than the model (33). The mechanism: before, during, after (34). "Could we have caught this?" (35). Three signals that should have fired (36).
- Slides 37–44 · **5. Beyond one domain: more failures**, all titled "Other Than Data Drift and Concept Drift". Divider (37). Software: the recommendation feedback loop (38). Infrastructure: training–serving skew at Uber (39). Hardware: sensor decalibration in autonomous vehicles (40), lens fouling and occlusion (41), sensor timing desync (42), thermal throttling of onboard inference chips (43). "Meme break": the dirty-lens joke (44).
- Slides 45–53 · **6. Generative AI: a different kind of failure**. Divider (45). No ground truth, and the key term "Jailbreak" (46). Defense in depth: system prompts, refusal training, classifiers (47). Five incident cards: Google Bard (48), Samsung and ChatGPT (49), Mata v. Avianca (50), Air Canada's chatbot (51), Replit's coding agent (52). What carries over from classic ML monitoring and what does not (53).
- Slides 54–59 · **7. Practical checklist: a takeaway framework**. Divider (54). "Match the Failure to the Signal" exercise (55) and its answers (56). Four rules for the job (57). Tools per layer on GCP, AWS, Azure and open source (58). The takeaway (59).
- Slide 60 · "Tutorial": pointer to the course tutorials page.
- Slide 61 · "Readings": pointer to the course readings page.
- Slide 62 · "The End".

## Key ideas

1. **Production failures are quiet, and the signals are usually there.** A model can keep serving confident predictions while it loses money for months. In hindsight the warning signs existed; the job is to see them before the press does. (Slides 3, 36, 59)
2. **The test set is frozen; production data is not.** Offline evaluation measures once, on a fixed dataset with a known distribution. In serving, user behaviour, markets and sensors keep changing, so exposure to risk is continuous. The lecture calls the resulting gap "Training-Serving Skew". (Slide 10)
3. **A feedback loop is a different failure from drift.** Tay learned from live conversations, so a coordinated group could feed it abuse that it then repeated and folded into its own replies. Nothing gated what it learned, and it was offline within a day. When it was accidentally switched on again it got stuck repeating one message, the same missing gate a second time. (Slides 11–13)
4. **Monitor three layers.** Data Quality asks whether the inputs are broken (nulls, schema changes, type mismatches). Model Performance asks whether the model's judgement is degrading (accuracy, precision, recall, calibration). System Health asks whether the infrastructure holds up (latency, throughput, errors, resources). A perfect model can still fail the business at the system layer. (Slides 15–17)
5. **Detect data drift by comparing distributions.** The Kolmogorov–Smirnov test compares one feature's recent distribution with its training-time distribution. Run it per feature over a rolling window (for example 7 or 30 days), at a cadence that matches how fast the feature changes. (Slide 18)
6. **The KS statistic is a maximum gap between two CDFs.** D is the largest vertical distance between the empirical CDFs of the reference sample and the current window, from 0 (identical) to 1 (disjoint). If D exceeds a critical value that shrinks as the samples grow, the two samples are unlikely to come from one distribution, and that is the drift signal. (Slide 19)
7. **Running KS in production is a scheduled batch job.** Keep a reference distribution (the training set, or a "golden" window such as the first stable 30 days after launch). A scheduled job (Airflow or cron) tests the last N days of each feature against it and pushes the statistic and p-value to a metrics store and dashboard. (Slide 20)
8. **Make drift alerts trustworthy.** With 50+ features tested daily, some will fire by chance, so correct for multiple testing or require 2–3 consecutive windows. A drift alert pages a person to investigate (real shift or upstream bug?); it does not trigger an automatic rollback. Use existing tools rather than hand-rolling. (Slides 18, 21)
9. **Concept drift changes the relationship, not the inputs.** Inputs can look normal while the mapping from features to outcome has moved. The key method is prediction-to-outcome tracking: once ground truth arrives, plot predictions against actual outcomes over time and watch the gap, instead of trusting one offline score. (Slide 22)
10. **When labels are late, use the signals you already have.** Streaming detectors watch the error stream: ADWIN shrinks its window when it sees real change, DDM and EDDM flag error rates that cross a control-chart threshold, and Page-Hinkley catches gradual drift. All three are in the Python library River. (Slide 23)
11. **Estimate performance without labels.** NannyML's CBPE (Confidence-Based Performance Estimation) estimates current accuracy or precision from the model's confidence distribution, before ground truth exists. The slide presents this as the practical answer to catching a Zillow-type failure before it shows up in earnings. (Slides 24–25)
12. **Retraining follows a policy agreed in advance.** For example: retrain when the performance estimate falls more than 5% for two consecutive weeks, or monthly, whichever comes first. A new model must beat the current one in a champion/challenger set-up before it replaces it. (Slide 26)
13. **Four rollout strategies trade safety against what you learn.** Shadow: the new model scores everything, but nobody acts on its output. Canary: a small share of real traffic gets the new model. Blue-green: two full environments and an instant switch, and an instant switch back. A/B test: a deliberate even split to prove which model is better on a business metric. Slide 28 asks which one fits a fraud team whose new model must not block anyone yet; the slides give no explicit answer, but in slide 29's walkthrough only shadow keeps the old model deciding every transaction. (Slides 27–29)
14. **Zillow passed every offline test and still failed.** The Zestimate-driven home-buying business worked while prices moved predictably. In 2021 prices surged and then cooled faster than the model's assumptions adjusted. Zillow kept buying at prices it could not resell, and the problem was found only after the losses had compounded: a $304M write-down, about $569M expected losses, about $8B of market value lost in a week, and about 25% of staff laid off. (Slides 31–34)
15. **Three signals could have fired earlier.** A leading indicator (days-on-market creeping up for Zillow's own homes), a concept-drift alarm (predicted versus actual resale price on a rolling basis) and a business-level monitor (how much capital sits in unsold inventory). Collecting the data is not enough: a person, an alert or an agent has to watch it. (Slides 35–36)
16. **Recommenders can poison their own training data.** Their past recommendations shape what users click, which becomes the next training set: Tay's loop in a commercial setting. No outside cause is needed, so a purely offline retraining pipeline is dangerous for any system that generates its own future labels. Monitor output diversity, not only accuracy. (Slide 38)
17. **Training–serving skew can be a pipeline bug.** When features are computed one way in training and another way in serving, the model breaks without any drift. Uber's Michelangelo answered with a central feature store (one definition, computed once, used by both paths); the monitor is a feature parity check. The slide cites an industry estimate that about 40% of production model issues trace back to this. (Slide 39)
18. **Hardware faults look statistically normal.** Misaligned LiDAR and cameras, a dirty lens, clocks drifting between fused sensors and a hot chip that throttles or falls back to a smaller model all degrade predictions without raising an error. A KS test will not see them. Each needs its own physical-layer check, run independently of the model's confidence. (Slides 40–44)
19. **Generative AI has no single right answer.** One prompt can have many valid answers, and the failure that matters most is unsafe or harmful output, not a wrong number. A jailbreak is a prompt designed to get past the model's safety training. (Slide 46)
20. **Defend GenAI in depth.** There are three layers: system prompts (instructions, the weakest layer on its own because text can be argued with), refusal training (RLHF or DPO, baked into the weights) and external classifiers that scan prompts and completions independently of the LLM's judgement. (Slide 47)
21. **Each GenAI incident maps to a missing control.** Bard: no fact-check gate before a public demo. Samsung: no outbound classifier on what employees paste into an external chatbot. Mata v. Avianca: no deterministic check of citations. Air Canada: answers about policy should be grounded in the current policy page, because the bot speaks for the company. Replit: a code freeze written only in the prompt is not a permission boundary. (Slides 48–52)
22. **The principle carries over; the tools change.** Without a fixed ground truth, KS tests give way to classifiers and prediction-to-outcome tracking gives way to LLM-as-judge. The judge model is itself a new thing that can fail. Layered defenses mirror the three monitoring layers. (Slide 53)
23. **Match the signal to the failure type.** Concept drift → prediction-to-outcome tracking. Feedback loop → output diversity monitoring. Physical drift → calibration-state monitoring. Engineering bug → feature parity checks. Drift tests catch statistical failures only. (Slides 55–57, 59)
24. **Every cloud does the same five jobs.** Log it, aggregate it, store it, stream it if you need speed, and alert a human. The products differ between GCP, AWS, Azure and open source. (Slide 58)

## Diagrams

**Slide 3 · Hook (illustration).** A large red "$8B" with a one-line caption, an italic two-line punchline below, and on the right the "This is fine" dog in a burning room with a blue Zillow logo over its corner. "Quietly" in the title is in orange-red. It teaches no mechanism; it sets up the case study.

**Slide 6 · Project timeline (recap).**
- *Layout:* the same Gantt-style picture as in L12. A light-blue arrow runs left to right through the phases POC, Prototype and MVP, separated by dashed vertical lines. Staggered bars underneath: "Design Cheese App" (POC and Prototype), "Data Collection" (early POC), "Setup Experiment Tracking" (POC), "Build Baseline Models" (across the POC/Prototype line), "Build Better Models" and "ML Workflow" (Prototype), "Build Cheese App" (MVP), and "Deployment, Scaling & Automation" (late Prototype to the end of MVP).
- *Highlight:* a red dashed box encloses "Build Better Models", "ML Workflow" and the Prototype-phase start of the deployment bar. In L12 the box was on "Design Cheese App".
- *Purpose:* to show the course has reached the stage where models are trained and deployed, which is when monitoring starts to matter.

**Slide 7 · Cheese App Development (the ML pipeline).**
- *Layout:* four coloured tiles in a row, each with a numbered circle above it: 1 "Data Collector" (red, download icon), 2 "Data Processor" (blue, gears), 3 "Model Training" (yellow, light bulb), 4 "Model Deploy" (green, bulb in a ring). Tiles 1–3 have a green tick in the corner; tile 4 has none.
- *Bottom:* a dashed box labelled "Google Cloud Platform" holds "Cloud Storage" (left) and "Vertex AI" (right).
- *Arrows:* Data Collector → down and right into the GCP box (red, one-way). Data Processor ↔ GCP (blue, two-way, vertical). Model Training → down into the box above Vertex AI (gold, one-way). Model Deploy → down and left into the right edge of the box (green, one-way).
- *Purpose:* steps 1–3 are done and deployment is next. Monitoring is about what happens after step 4.

**Slide 10 · Training time versus serving time (contrast).** A grey "KEY TERM" box defines "Training-Serving Skew". Below it, two columns with teal circle badges: "T · Training Time" (fixed dataset, known distribution, one evaluation on held-out data) and "S · Serving Time" (live, moving data, unknown future distribution, continuous exposure). Purpose: the core contrast of the lecture. Slide 46 reuses the same layout for Traditional ML versus Generative Systems.

**Slide 11 · Tay's 16 hours (timeline).** A big dark-red "16 HOURS" with an italic caption about launch-to-shutdown time. Below it, four teal numbered circles in a vertical list, each with a bold label and a one-line description: 1 Launch, 2 Exploit, 3 Collapse, 4 Shutdown. A glitchy "Tay.ai" logo sits bottom right.
- *Redraw tip (ours):* the mechanism is a loop with no gate: users → messages → Tay learns from them in real time → Tay's replies → users. The slides name the missing piece as a "monitoring gate" between incoming input and learning.

**Slides 12–13 · Tay, the exploit and the aftermath.** Slide 12 is a bullet slide with a screenshot of Tay's Twitter profile (glitch-art banner, profile photo, follower counts) and an italic note that this is a feedback-loop failure, not data drift. Slide 13 is text only. Illustration, not mechanism.

**Slide 15 · Three layers of production monitoring.** Three tall cards side by side, each with a title, an italic question, a thin rule, and examples at the bottom:
- "Data Quality" (light blue, dark text): "Are the inputs broken?"
- "Model Performance" (orange-red, white text): "Is the model's judgment degrading?"
- "System Health" (navy, white text): "Is the infrastructure holding up?"

Purpose: a taxonomy for sorting any alert. Slide 47 repeats the three-card layout for GenAI safety, and slide 53 makes the parallel explicit.

**Slides 16–17 · "Try Thinking About It Now" (matching quiz).**
- *Layout:* three numbered symptoms on the left (a latency spike right after a model update; a sudden rise in null feature values; precision down 8% week over week) and three outlined boxes on the right, top to bottom: System Health, Data Quality, Model Performance. Slide 16 has no lines.
- *Slide 17* adds thin connecting lines with arrowheads. Item 2 runs straight across to Data Quality. Items 1 and 3 cross: item 1 goes down to Model Performance and item 3 goes up to System Health.
- *Caution:* this crossing contradicts slide 15's definitions (latency is System Health, precision is Model Performance). Read row by row, the boxes already line up with the correct answers, so the lines for items 1 and 3 appear to be swapped. Use 1 → System Health, 2 → Data Quality, 3 → Model Performance. Item 1 is a fair trap anyway, because "after a model update" tempts people to blame the model.

**Slide 18 · Data drift with the KS test.** On the left, a grey panel with two side-by-side, non-overlapping ellipses: a blue solid ellipse labelled "Training distribution" and a slightly lower red dashed ellipse labelled "Live distribution (today)". On the right, a "PRACTICAL RULE OF THUMB" list with four bullets. Purpose: two samples of the same feature that no longer match.
- *Redraw tip (ours):* the ellipses are only a metaphor. The mechanism on slide 19 is better shown as two histograms of one feature turning into two empirical CDF staircases on one axis, with the largest vertical gap marked as D and compared with a D_critical line.

**Slide 19 · KS math.** Two formulas in grey monospace boxes (see Commands and code), each followed by a sentence that defines the symbols. There is no plot.

**Slide 22 · Prediction-to-outcome tracking (chart).**
- *Layout:* a navy "KEY METHOD" banner with the method's name and a one-sentence description. Below it, a pale chart with no axes or numbers: a solid navy line labelled "Predicted" rises gently from left to right, and a dashed red line labelled "Actual" falls gently. The two start close together on the left, under a small italic "stable market", and spread apart to the right, where a red "gap widens →" sits below the chart.
- *Purpose:* concept drift shows up as a growing gap between what the model predicts and what actually happens. In the lecture's example, house prices.
- *Redraw tip (ours):* put time on the x-axis, draw the two lines, shade the gap between them, and add an alert threshold the gap crosses partway along.

**Slides 23–26 · text slides.** There is no diagram. Slide 24 has a grey callout box naming CBPE, and slide 26 has a yellow callout box with the example retraining policy.

**Slides 27–29 · Rollout strategies (text only, but a routing mechanism).** The slides are bullet text. A scene author can draw them as traffic routing between an "old model" box and a "new model" box. *Redraw tip (ours), from the slides' wording:*
- *Shadow:* every request is copied to both models. Only the old model's score decides approve/block; the new model's score goes to a log and is checked later against confirmed fraud.
- *Canary:* a router sends a small slice to the new model, whose score then really decides. The slide says "1 in 10" on slide 27 and "5%" on slide 29.
- *Blue-green:* two full, identical stacks, with all traffic on one of them. One switch moves 100% at once, and the same switch moves it back.
- *A/B:* a deliberate split of about 50/50, both models live, with a business metric (false-decline rate, fraud caught; signups or clicks on slide 27) compared side by side.

Slide 28 is a single question in large text, with no diagram.

**Slide 31 · Zillow by the numbers.** Four grey tiles with large dark-red figures and small captions: "$304M" (Q3 2021 inventory write-down), "~$569M" (total expected losses), "~$8B" (market value lost in a week), "~25%" (of the workforce laid off). A line below gives the shutdown announcement date, November 2, 2021.

**Slide 34 · Zillow, the mechanism (three-stage flow).**
- *Layout:* three panels left to right, joined by red arrows. Each has a small teal stage label and a bold title: "BEFORE · Stable Market" (grey), "DURING · Market Shifts" (pale pink, highlighted), "AFTER · Detection Lag" (grey).
- *Text:* the model did fine while prices moved predictably; prices then moved faster than its assumptions and Zillow kept buying homes it could not resell at a profit; by Q3 2021 it held thousands of overpriced homes, and the problem was caught only after the damage had compounded.
- *Caption:* offline accuracy looked fine throughout the "during" stage.
- *Purpose:* the failure was invisible to a static test set; only live monitoring could have shortened the detection lag.

**Slide 36 · Three signals.** Three rows, each with a teal numbered circle, a bold signal name, an italic teal tag giving its type, and a description on the right:
1. "Days-on-Market Creep", tagged "Leading Indicator".
2. "Predicted vs. Actual Resale Gap", tagged "Concept-Drift Alarm".
3. "Inventory Concentration Risk", tagged "Business-Level Monitor".

An italic footer says someone, an alert or an agent has to actually watch. Purpose: monitors at three levels (business leading indicator, model, business risk) for one failure. Slide 53 reuses this row layout.

**Slides 38–43 · "Other Than Data Drift and Concept Drift" (failure cards).** Every slide uses the same template. A small grey domain tag ("SOFTWARE", "INFRASTRUCTURE", "HARDWARE") sits over a bold case title. A grey "What Breaks" panel has a rule, then a navy "MONITORING SIGNAL" heading and an italic signal. Slides 38–40 add a right-hand panel: "WHY IT'S DIFFERENT FROM ZILLOW" (38), "REAL-WORLD RESPONSE" (39) or "THE KEY DISTINCTION" (40). Slides 41–43 use one wide panel. Slide 39 adds a teal-bordered stat box, "~40%". Purpose: one card per failure mode, each paired with the signal that would catch it.
- *Redraw tips (ours):*
  - Slide 38 is a loop: model → recommendations → user clicks → next training set → model, with a "diversity" gauge narrowing on each turn.
  - Slide 39 is two parallel pipelines (training path and serving path), each with its own "compute features" box, whose outputs differ for the same input. Replace them with one shared feature store feeding both paths, and add a parity check comparing the two.
  - Slides 40–43 can share one picture: sensors → (gate) → model. The checks (geometric agreement between sensors, blur/contrast/coverage, timestamp offsets, temperature against latency and the model version served) sit on the sensor and hardware side, before or beside the model, not after it.

**Slide 44 · Meme break.** A grey box in monospace text: four short lines with speaker labels, "engineer:", "also engineer:" and "still engineer:" in blue and "five minutes later:" in red. Accuracy drops, the engineer blames concept drift and retrains for hours without success, and the real cause turns out to be a dirty camera lens (facepalm emoji). Purpose: the wrong layer gets blamed when the failure is physical.

**Slide 46 · Traditional ML versus Generative Systems (contrast).** The same layout as slide 10: an intro paragraph, a grey "KEY TERM" box defining "Jailbreak", then two columns with teal badges, "T · Traditional ML" (one correct answer per input, measured against ground truth) and "G · Generative Systems" (many valid answers; failure means unsafe or harmful content).

**Slide 47 · Defense in depth for GenAI.** Three cards in the slide-15 layout:
- "System Prompts" (pale pink, dark text): "What is the model told to do?"
- "Refusal Training" (dark red, white text): "Has the model itself learned to say no?"
- "Classifiers" (teal, white text): "Is something external watching, too?"

Each card has a short description at the bottom. Purpose: three independent layers that fail differently.
- *Redraw tip (ours):* show a prompt passing through three filters in sequence (an input classifier, the model with system prompt and trained refusals, an output classifier), and show that an attack has to get through all of them.

**Slides 48–52 · GenAI incident cards.** These use the same card template as 38–43, with a dated category tag over the title:
- 48: "FEBRUARY 2023 · NO REVIEW GATE"
- 49: "APRIL 2023 · DATA LEAKAGE", with the right panel "REAL-WORLD RESPONSE" and a teal-bordered stat box "3 in 20"
- 50: "JUNE 2023 · HALLUCINATION", with "THE KEY DISTINCTION"
- 51: "FEBRUARY 2024 · ACCOUNTABILITY"
- 52: "JULY 2025 · AGENTIC AI"

Each pairs "What Breaks" with a "MONITORING SIGNAL", which is really the missing control. Purpose: a timeline of real failures, each tied to one control.

**Slide 53 · What carries over.** Three rows in the slide-36 layout:
1. "Same Input, Different Output", tagged "No Fixed Ground Truth".
2. "The Judge Is Now Part of the System", tagged "LLM-as-Judge".
3. "Defense in Depth, Not One Gate", tagged "Layered, Not Singular".

The footer maps the old tools to the new: KS tests → classifiers, prediction-to-outcome tracking → LLM-as-judge.
- *Redraw tip (ours):* a two-column "classic ML → GenAI" mapping, with the three monitoring layers (slide 15) on the left morphing into the three safety layers (slide 47) on the right.

**Slides 55–56 · Match the failure to the signal (exercise table).** A table with a teal header row and the columns "Failure Case", "What Broke" and "Monitoring Signal". The rows are Zillow home pricing, a Tay-style feedback loop, AV sensor decalibration and Uber's feature pipeline. On slide 55 the signal column holds teal "?" marks, and a teal circle "90s" with "in pairs" sits top right. On slide 56 the answers are filled in in teal (see Key idea 23) and the "What Broke" column is shortened to two-word labels.

**Slide 57 · What to do in your job.** Four teal numbered circles, each with a bold rule and a one-line explanation (see What the lecture stresses).

**Slide 58 · Tools by layer and cloud (table).** A teal header row ("Layer", "GCP", "AWS", "Azure", "Cloud-agnostic / OSS") over six rows: General logging, Metrics & dashboards, Feature/prediction store, Streaming ingestion, Drift monitoring (managed), Alerting. The full table is under Terms. An italic footer lists "five jobs" (log, aggregate, store, stream, alert). The table has six rows; drift monitoring is the one the footer leaves out.

**Slide 59 · Takeaway.** A yellow callout with the one-sentence takeaway (monitoring versus headlines), with a line below about picking the right layer.

## Terms the lecture uses

| Term (as on the slides) | Slides | Meaning, and how it compares with the tutorials |
|---|---|---|
| Training-Serving Skew | 10, 39, 55–57 | Used in **two senses**. Slide 10 defines it broadly: the gap between performance on the build-time data and on live data, which covers drift too. Slide 39 uses the usual narrow sense: features computed differently in training and in serving, a pipeline bug. Our guides use the narrow sense: L15 calls the client-side preprocessing that a serving signature avoids "training/serving skew waiting to happen", and L13 E13 records a real mismatch in the notebooks (training scales by `/255`, prediction uses `preprocess_input`). |
| Training Time / Serving Time | 10 | The two halves of the lecture's contrast. |
| Feedback loop failure; "monitoring gate" | 11–13, 38 | The model's own outputs (or users' reactions to them) become its next training input, with nothing checking what gets in. |
| Data Quality / Model Performance / System Health | 15–17, 53 | "Three Layers of Production Monitoring". |
| Layer 1: Detecting Data Drift; Layer 2: Detecting Concept Drift | 18, 22 | A second, separate use of "Layer". The slides do not map these two onto the three layers of slide 15, so keep the two numberings apart in narration. |
| Data drift | 18–22 | The input distribution shifts. |
| Concept drift | 22–25, 33, 36, 56 | The feature-to-outcome relationship shifts while the inputs may look normal. |
| Kolmogorov-Smirnov (KS) test; KS statistic D; D_critical; c(α); empirical CDF | 18–21 | The two-sample test used per feature. α is "typically 0.05". |
| Reference distribution; "golden" window; rolling window | 18, 20 | The baseline (training set or the first stable 30 days) and the recent window compared with it. |
| Multiple testing; consecutive windows | 21 | Guarding against false alarms when many features are tested. |
| Prediction-to-Outcome Tracking | 22, 53, 56–57 | The "KEY METHOD" for concept drift. |
| Ground truth (delayed) | 22–24, 46, 53 | The real outcome; for Zillow it took months to know. |
| Streaming detectors: ADWIN (Adaptive Windowing), DDM, EDDM, Page-Hinkley test; River | 23 | Online change detectors over the error stream, and the Python library that has them. |
| Label-free estimation; CBPE (Confidence-Based Performance Estimation); NannyML | 24–25 | Estimating performance from model confidence before labels arrive. |
| ML observability platforms | 25 | Arize AI, Fiddler and WhyLabs (commercial), Evidently AI (open source), NannyML, and the cloud-native Vertex AI Model Monitoring and SageMaker Model Monitor. |
| Retraining policy; champion / challenger | 26 | A rule agreed in advance for when to retrain, and the head-to-head validation before a new model replaces the old one. |
| Shadow / Canary / Blue-green deployment; A/B test | 27–29 | The four rollout strategies. Our guides meet two relatives. L15's Vertex AI endpoint `traffic_split` is how a canary is done there (`{"0": 100}` in the tutorial; the guide's exercise E5 builds a 20/80 split). L22 and L23 deploy with Kubernetes' default **rolling update**, which replaces pods one at a time and is not one of the lecture's four. |
| Zestimate; Zillow Offers | 31–34, 36 | Zillow's pricing model and its home-buying business. |
| Detection Lag | 34 | The time between the market shifting and the failure being noticed. |
| Leading Indicator / Concept-Drift Alarm / Business-Level Monitor | 36, 57 | Types of signal. "Leading" means it moves before the model metric does. |
| Days-on-Market Creep; Inventory Concentration Risk | 36 | The Zillow-specific business signals. |
| Output diversity monitoring | 38, 56–57 | Watching whether recommendations narrow over time. |
| Feature parity checks; centralized feature store; Michelangelo | 39, 56–57 | Comparing training-path and serving-path feature values for the same input; Uber's platform with one shared feature definition. No tutorial in the course uses a feature store. The closest thing in our guides is L15 putting the preprocessing inside the SavedModel's serving signature. |
| Calibration-state monitoring; cross-sensor consistency checks | 40, 56 | Checking that sensors still agree geometrically. |
| Image quality checks (blur score, contrast, coverage) as a gate before inference | 41 | A check on each camera frame that runs before the model sees it. |
| Timestamp offset monitoring | 42 | Watching the clock offset between fused sensor streams against a tolerance of a few milliseconds. |
| Thermal throttling; device temperature telemetry | 43 | A hot edge chip slows down or falls back to a smaller model; correlate temperature with latency and the model version served. |
| Jailbreak | 46 | A "KEY TERM": a prompt designed to get around safety training. |
| Defense in Depth: System Prompts / Refusal Training (RLHF, DPO) / Classifiers | 47, 52–53 | The three GenAI safety layers. |
| Review gate / fact-check gate; outbound content classifiers; citation verification; retrieval layer grounded in the policy page; enforced permission boundary | 48–52 | The controls named by the incident cards. The L07 tutorial (`agent-harness`) builds the last idea in code: the model only proposes, and Python-owned approval gates and re-validation decide ("the model proposes; the harness decides", L07 guide). |
| LLM-as-Judge; groundedness; refusal correctness | 53 | Grading one model with another. L07's evaluation does not use a judge model: code checks score application properties over golden cases, and the prose goes to a human review checklist (L07 guide). |
| Vertex AI; Vertex AI Model Monitoring | 7, 21, 25, 58 | This deck says **Vertex AI**, as the tutorial READMEs do (L13, L15). The L12 deck calls the same platform "Agent Platform". |
| Data Collector / Data Processor / Model Training / Model Deploy | 7 | The pipeline steps. In `ml-workflow` the deploy step is a component inside `src/workflow/`, not its own folder (L15 guide). |
| "Same five jobs": log, aggregate, store, stream, alert | 58 | The slide's summary of what every monitoring stack does. |

**Monitoring tools by layer (slide 58).**

| Layer | GCP | AWS | Azure | Cloud-agnostic / OSS |
|---|---|---|---|---|
| General logging | Cloud Logging | CloudWatch Logs | Azure Monitor Logs | ELK Stack |
| Metrics & dashboards | Cloud Monitoring | CloudWatch Metrics | Azure Monitor / App Insights | Prometheus + Grafana, Datadog |
| Feature/prediction store | BigQuery, Firestore | DynamoDB, S3 + Athena | Cosmos DB | n/a |
| Streaming ingestion | Dataflow, Pub/Sub | Kinesis Data Firehose | Event Hubs | Kafka |
| Drift monitoring (managed) | Vertex AI Model Monitoring | SageMaker Model Monitor | Azure ML Data Drift Monitor | Evidently AI, WhyLabs, NannyML |
| Alerting | Cloud Monitoring Alerts | CloudWatch Alarms + SNS | Azure Monitor Alerts | PagerDuty, Opsgenie |

Of these, only Cloud Logging appears in our tutorials: Vertex AI custom jobs (L13), Cloud Run (L14) and Vertex endpoints (L15) all send stdout or server logs there. No tutorial covered by our guides sets up model metrics, drift monitoring or alerting; the only alert in the course so far is L01's billing budget alert.

**Inconsistencies on the slides worth knowing before scripting.**
- "Training-Serving Skew" is defined broadly on slide 10 and used narrowly on slide 39 (see above).
- On slide 17 the answer lines for items 1 and 3 appear swapped relative to slide 15's definitions.
- The canary share is "1 in 10" on slide 27 and "5%" on slide 29. Both are only examples.
- Slide 49's title says the code "Leaked via ChatGPT", but its body says the code was not leaked; it was stored on an outside provider's servers and could not be deleted. Say "exposed to an outside service". The body also has a typo ("no ay to delete").
- Slide 58's footer counts five jobs, but the table has six rows.
- The slides give no source for the "~40%" (slide 39) beyond "industry estimates", or for the dollar figures. Quote them as the slide's figures, not as verified facts.

## Commands and code on the slides

The slides show no shell commands, no Python and no configuration. The only code-like content:

- Slide 19, the two KS formulas, in monospace boxes:

  ```
  D  =  sup_x  | F₁(x) − F₂(x) |
  D_critical  ≈  c(α) · √( (n + m) / (n·m) )
  ```

  F₁ is the empirical CDF of the training-time sample and F₂ that of the current production window; n and m are the two sample sizes. *Our note, not on the slide:* for the two-sample test at α = 0.05, c(α) ≈ 1.36, and the formula is a large-sample approximation.
- Slide 26, the example retraining rule (prose, not code): retrain on a drop of more than 5% for two consecutive weeks, or monthly, whichever comes first.
- Slide 44 is set in monospace, but it is a joke, not code.
- Slide 60: `harvard-iacs.github.io/2026-AC215/tutorials_demo`.
- Slide 61: `harvard-iacs.github.io/2026-AC215/readings`.

## What the lecture stresses

- **Offline accuracy is not evidence that production is fine.** Zillow's metrics looked fine throughout the failure. Track prediction-to-outcome gaps continuously once labels arrive, not only at release. (Slides 10, 34, 57)
- **Somebody has to be watching.** Collecting the data is not enough: a person, an alert or an agent must act on it. The same principle closes the GenAI section. (Slides 36, 53, 59)
- **Systems that learn from live input need a gate.** Tay twice, and recommenders generally. Purely offline retraining pipelines are risky whenever the system creates its own future training data. (Slides 11–13, 38)
- **Run drift tests per feature, over a rolling window, at a cadence suited to the data.** Daily for fast-moving features, weekly for slow ones. (Slide 18)
- **A drift alert means investigate, not roll back automatically.** Page the on-call engineer, who decides whether it is a real shift or an upstream data bug. (Slides 18, 21)
- **Beware false positives.** Correct for multiple testing, or require 2–3 consecutive windows before alerting. (Slide 21)
- **Don't hand-roll monitoring.** Use TFDV, Evidently, whylogs, Great Expectations, or the managed cloud monitors. (Slides 21, 25, 58)
- **Ground truth is often late.** Use streaming detectors or label-free estimates instead of waiting months. (Slides 23–24)
- **Retrain by policy, not by reflex.** Decide the trigger in advance, and validate the challenger before it replaces the champion. (Slide 26)
- **Know the rollout trade-offs.** Shadow is safe but teaches nothing about user response. Canary is real but limited in reach. Blue-green gives an instant rollback but no warning before the switch. A/B is for proving which model is better, not for catching bugs. (Slides 27, 29)
- **Watch leading indicators, not just lagging ones.** Business and system signals (days on market, output diversity, calibration state) often move before the model metric does. (Slides 36, 57)
- **Match the signal to the failure type.** Drift tests catch statistical failures, not engineering bugs or hardware faults. Check the right layer before retraining (the dirty-lens joke). (Slides 40, 44, 55–57, 59)
- **Build feature parity into the pipeline.** If the two paths compute features differently, a better model cannot fix it. The slide says this is common, not an edge case (~40%). (Slides 39, 57)
- **Check hardware independently of the model.** An image-quality gate runs before inference and does not rely on the model's confidence. Throttling must be visible as its own signal, not just as "latency is bad today". (Slides 40–43)
- **A system prompt alone is the weakest defense.** Layer system prompts, refusal training and independent classifiers. (Slide 47)
- **"Confident and wrong is worse than uncertain and honest."** Fact-check high-stakes public outputs before release. (Slide 48)
- **Policy alone does not hold; technical controls do.** Samsung had three leaks in 20 days before it banned the tools and built input-side controls. (Slide 49)
- **Verify citations deterministically** against a real database before they reach a filing. (Slide 50)
- **A chatbot's answer is a company statement.** Ground policy answers in the current policy page; the tribunal rejected the "separate legal entity" defence. (Slide 51)
- **A freeze that lives only in the prompt is "a request, not a boundary".** An agent with write access needs enforced permissions. (Slide 52)
- **LLM-as-judge is not a solved problem.** The judge is one more component that can fail. (Slide 53)
- **Monitoring isn't overhead.** It decides whether you find a problem on a dashboard or in a headline. (Slide 59)

## Pointers

- Slide 60, "Tutorial": this week's hands-on tutorial is on the course tutorials page, `harvard-iacs.github.io/2026-AC215/tutorials_demo`. The course's tutorial entry for Lecture 17 lists only the Ed lesson, and `course/lectures.yaml` records no repository.
- Slide 61, "Readings": `harvard-iacs.github.io/2026-AC215/readings`. In the copy of the course site checked for this digest, the readings page has sections only for virtual environments and containers, and nothing for this lecture.
- Slide 8 recaps the previous lecture (in our map, L16 "System Tradeoffs"): public and private subnets, NAT and Internet gateways, one immutable image for dev and prod, and a decision framework. There is no L16 digest or guide in this repository.
- Slides 6–7 point back to the project timeline (L12) and the cheese-app ML pipeline on Vertex AI (L13, L15).
- In-class activities:
  - the layer-matching quiz (16–17)
  - the fraud-team rollout question (28)
  - "Any guesses?" about Zillow (32)
  - "Could we have caught this?" (35)
  - the "Match the Failure to the Signal" exercise, 90 seconds in pairs (55–56)
  - a meme break (44)
- Tools and platforms named on the slides (names only, no links):
  - Airflow, cron, Prometheus, BigQuery, Grafana, Datadog (20)
  - TensorFlow Data Validation, Evidently AI, whylogs, Great Expectations, Vertex AI Model Monitoring, SageMaker Model Monitor (21)
  - River (23)
  - NannyML (24–25)
  - Arize AI, Fiddler, WhyLabs (25)
  - Uber Michelangelo (39)
  - the slide-58 table
- No homework, milestone or quiz is mentioned on the slides; the announcements slide (2) is empty.
- Outside the slides:
  - The course site's week-10 module puts this lecture on Nov 3 together with "Quiz 4", but labels its link "Lecture 16" and APIs + Frontend "Lecture 17". Our map follows the Ed numbering (L17).
  - Related study guides in this repository:
    - L13 (Cloud Logging for Vertex jobs; E13, a real preprocessing mismatch)
    - L15 (preprocessing inside the serving signature; endpoint `traffic_split` and the canary exercise E5)
    - L22 and L23 (Kubernetes rolling updates)
    - L07 (approval gates and deterministic evaluation over golden cases, the code-level counterpart of slides 47, 52 and 53)
    - L11 (whose lecture title mentions monitoring; the guide points ahead to this lecture for it)
