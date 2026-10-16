# L17 lecture slides — Evaluating and Monitoring ML Systems in Production

Source: deck `L17_evaluating_and_monitoring_ml_systems` (62 slides), "Lecture 17: Evaluating and Monitoring ML Systems in Production", AC215/E115, Pavlos Protopapas (SEAS/Harvard). These are the instructor's lecture slides (PDF), provided by the student for study; the PDFs are not in this repository; slide numbers are PDF page numbers. The page numbers printed in the slide footers fall behind the PDF numbering from slide 10 on (slide 10 is printed "9", slides 38–43 are printed 34–39, slides 55–59 are printed 41–45, and slides 16 and 17 both say "16"), so always cite the PDF number. Everything below is a summary in our own words. Quotes are limited to short titles, labels, names and formulas. L17 has no tutorial repository (`course/lectures.yaml`: `tutorials: []`, and the course tutorials page lists only the Ed lesson for this lecture). Where this digest compares the lecture's naming with "the tutorials", it means the repositories of neighbouring lectures, as recorded in our study guides (L07, L13, L15, L22, L23).

## 中文速览

- **这一讲讲什么：** L17 没有 tutorial，也没有 video，只有一份 62 页的 slides（"Lecture 17: Evaluating and Monitoring ML Systems in Production"）。开场的 hook 是 Zillow：model 安静地错了好几个月，一周蒸发了约 $8B market value（slide 3）。核心对比：training time 的 test set 是冻住的，serving time 的 data 一直在变；slide 10 把这个 gap 叫 "Training-Serving Skew"（slide 39 又用它的窄义：training 和 serving 两条 pipeline 算 feature 的方法不一样）。
- **Idea 1 · 三层 monitoring：** Data Quality（inputs 坏了没有：nulls、schema change）、Model Performance（判断有没有退化：accuracy、precision、calibration）、System Health（infrastructure 撑不撑得住：latency、errors、resources）（15）。slide 17 的连线把 item 1 和 item 3 画反了：latency spike 属于 System Health，precision 掉 8% 属于 Model Performance。
- **Idea 2 · data drift 用 KS test：** 每个 feature 拿最近的 rolling window 跟 reference distribution（training set，或上线后稳定的 "golden" 30 天）比；D 是两条 empirical CDF 之间最大的竖直距离，超过 D_critical 就是 drift signal（18–19）。在 production 里它是 Airflow 或 cron 跑的 scheduled batch job，结果推到 metrics store 和 dashboard（20）。50 多个 feature 天天测，一定会有 false positive，所以要做 multiple-testing correction，或者连续 2–3 个 window 都超了才 alert；alert 是叫人来 investigate，不是 auto rollback（21）。
- **Idea 3 · concept drift 和 retraining：** inputs 看起来正常，但 feature → outcome 的关系变了。key method 是 prediction-to-outcome tracking：ground truth 回来以后画 predicted vs actual，看 gap 是不是越拉越大（22）。label 来得慢，就用 streaming detectors（ADWIN、DDM/EDDM、Page-Hinkley，都在 River 里），或者 NannyML 的 CBPE（用 model 的 confidence 估 accuracy）（23–25）。retrain 要按事先定好的 policy，challenger 先赢过 champion 才能上线（26）。
- **Idea 4 · 四种 rollout：** shadow（新 model 照样打分，但没人用它的结果）、canary（一小部分真实 traffic 给新 model）、blue-green（两套完整环境，一个开关切过去，也能一下切回来）、A/B（故意 50/50 分流，比 business metric）（27–29）。slide 28 的 fraud team 要求新 model 还不能 block 任何人，四种里只有 shadow 让旧 model 继续决定每一笔交易。
- **Idea 5 · drift 之外的 failure：** Zillow 是 concept drift，本来有三个 signal 可以早点响：自家房子的 days-on-market、predicted vs actual resale gap、inventory 里压了多少钱；但总得有人（或者 alert、agent）真的在看（31–36）。另外还有 feedback loop（Tay、recommender → monitor output diversity）、pipeline bug（Uber → feature store + feature parity check，slide 说约 40% 的问题出在这里）、hardware（sensor decalibration、脏镜头、clock desync、thermal throttling，KS test 都看不见）（11–13, 38–44）。
- **Idea 6 · GenAI：** 没有唯一正确答案，最要紧的 failure 是 unsafe 或 harmful output；jailbreak 是专门绕过 safety training 的 prompt（46）。defense in depth 有三层：system prompt（单独用最弱）、refusal training（RLHF/DPO）、外部 classifiers（47）。五个 incident 各缺一个 control：Bard 没有 fact-check gate，Samsung 没有 outbound classifier，Mata v. Avianca 没有核对 citations，Air Canada 没有 grounding，Replit 的 code freeze 只写在 prompt 里（48–52）。KS test 换成 classifiers，prediction-to-outcome 换成 LLM-as-judge，而 judge 自己也会错（53）。
- **和 tutorials 的关系：** 没有任何 tutorial 跑 drift test、prediction-to-outcome tracking 或 production alerting；唯一的 alert 是 Tutorial 0 的 billing budget alert，L21 CI 的 Slack 消息又只在成功时才发。用得上的地方：L15 把 preprocessing 放进 serving signature 防 skew，`traffic_split` 可以做 canary（E5）；L22/L23 的 rolling update 不属于四种 rollout 之一；L13 notebooks 里有一个真实的 preprocessing mismatch（E13）；L07 有 approval gates 和 golden-case evaluation。每个 idea 在哪个 guide 的哪一节用到，见文末的 [Where this shows up in the tutorials](#where-this-shows-up-in-the-tutorials)。

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
- Slide 8 recaps the previous lecture (in our map, L16 "System Tradeoffs"): public and private subnets, NAT and Internet gateways, one immutable image for dev and prod, and a decision framework. There is no L16 study guide; the L16 slide digest is [L16-system-tradeoffs.md](L16-system-tradeoffs.md).
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

## Where this shows up in the tutorials

L17 has no tutorial and no video of its own, and no tutorial in the course builds production monitoring. Its ideas still turn up all over the course. Sometimes a tutorial builds the check (an approval gate, a serving signature, a traffic split). More often the tutorial's own code contains the failure that one of the lecture's signals would have caught. The first table takes each key idea above and lists the study-guide sections where it appears. Each row starts with a status in bold: **Applied** (a tutorial builds it, or its code shows the exact failure the idea warns about), **Pieces only** (some ingredients exist, but nothing joins them into the check) or **Not applied**. "[L15] §3.2" means section 3.2 of that lecture's study guide, and "Lecture slides" means the guide's *Lecture slides* section. The video folder for each guide is listed at the end.

### Key ideas → tutorials

| # | Key idea (slides) | Where the tutorials apply it |
|---|---|---|
| 1 | Production failures are quiet, and the signals are usually there (3, 36, 59) | **Applied, as failures.** [L15] §6 item 10 and E7: with `sync=False` a crashed training job leaves the pipeline step green, and Model Deploy can deploy the previous run's model. [L08] §4 Step 6: generation errors are caught and printed per batch, so `--generate` "succeeds" with data missing. [L20] §6 item 13: the vector-DB loader exits 0 even when ChromaDB was not ready, leaving an empty collection. In each case the evidence was in a log that nobody was asked to read. |
| 2 | The test set is frozen; production data is not (10) | **Applied, the training-time half only.** Every model in the course is judged once, on held-out data: [L13] §3.1 (five classifiers on 116 test images, where one image is 0.86%) and [L08] §3.8 (loss and perplexity on 100 test examples). Nothing measures the serving side. [L23] §3.7: the app serves a fixed CNN downloaded from a GitHub release. The one live data source already shifts under the code: [L15] §4 B2, the collector scrapes Bing with a regex and indexes 0 images when Bing changes its HTML. |
| 3 | A system that learns from live input needs a gate (11–13) | **Applied.** [L07] §3.5: memory is a separate store that only the host writes, and the model has no memory-write tool, so nothing a user says is "learned" without passing code. [L07] §3.3: retrieved text enters the conversation labelled as data, not instructions. [L06] §3.8: a model's proposal changes nothing until a later human turn approves it. |
| 4 | Monitor three layers: Data Quality, Model Performance, System Health (15–17) | **Applied, mostly before deployment.** Data quality: [L15] §4 B3, the data processor removes duplicates with difPy and deletes files that are not decodable JPEGs before training. Model performance: [L13] §3.1–3.2, accuracy and `val_accuracy` per run, tracked in W&B (offline only). System health: [L14] §3.2 (cold starts are latency), [L22] §3.6 (an HPA scales on CPU measured against the Pod's requests; the repo configures none), [L22] §6 item 13 (no readiness probe, so 502/503 for the first minute after a deploy), [L23] §3.8 (the load balancer health-checks the API on `/api-service/`). |
| 5 | Detect data drift by comparing distributions (KS test) (18) | **Not applied.** No tutorial compares a live feature distribution with a training-time one. |
| 6 | The KS statistic D and its critical value (19) | **Not applied.** |
| 7 | Running KS in production is a scheduled batch job (20) | **Pieces only.** A reference sample: [L11] §3.6, a git tag such as `dataset_v20` names an exact dataset that `dvc get --rev` can rebuild, which is what a "golden" reference needs. A job runner: [L15] §3.7 (a CLI container submits a Vertex pipeline) and [L23] §4 Part E (a commit message submits it), both on demand and never on a schedule. No result goes to a metrics store or a dashboard. |
| 8 | Make drift alerts trustworthy (18, 21) | **Pieces only, from testing.** A check that stays silent: [L09] §3.3, "skipped" is not "passed" (system tests skip when the server is down, and the run stays green). A check that over-fires: [L07] Exercise 8, an injection detector that quarantines a harmless quoted document on purpose, to show that heuristics over-block and that the real protection sits downstream. No tutorial routes an alert to an on-call person. |
| 9 | Concept drift: track predictions against outcomes (22) | **Pieces only.** Predictions are logged: [L18] §3.6, every chat is saved as JSON under `/persistent/chat-history/`. Outcomes are what labelling produces: [L11] §3.1, each annotation is a ground-truth record. No tutorial joins the two over time. |
| 10 | Streaming detectors when labels are late (23) | **Not applied.** |
| 11 | Estimate performance without labels (CBPE) (24–25) | **Not applied.** The raw material is there: [L15] §3.3, the endpoint returns the full softmax vector, and the client keeps only the argmax. CBPE works from those confidences. |
| 12 | Retrain by a policy agreed in advance; champion/challenger (26) | **Applied for prompts; missing for models.** [L07] §4 A12 and §3.8: the "live A/B" runs the current prompt and a copy with one change over the same golden cases, and `--compare` lists per-case improvements and regressions and flags confounding changes. That is a challenger tested against a champion. For models the gap is explicit. [L23] Lecture slides, idea 5, and §3.7: retraining starts when someone types `/run-ml-pipeline`, no metric is checked before the deploy, and the app never calls the new endpoint. [L13] §3.1 shows why a challenger needs a margin: on 116 test images a two-image gap is noise. |
| 13 | Four rollout strategies (27–29) | **Applied (canary only).** [L15] §3.2: one endpoint can route a percentage of requests to each deployed model. [L15] E5: deploy a second model to the same endpoint with `traffic_split={"0": 20, "<old id>": 80}`. The tutorial itself sends 100% to one model on a fresh endpoint ([L15] Lecture slides). [L22] §3.2 and [L23] §3.4: new image tags roll the Deployments with Kubernetes' default rolling update, which replaces Pods one at a time and is none of the four. No tutorial does shadow, blue-green or an A/B test on users. |
| 14 | Zillow passed every offline test and still failed (31–34) | **Applied, as a lesson about green checks.** [L09] §3.6: the guest lecture's babykev reaches "All green, and the mask is wrong", with 92 passing tests and 94% coverage while the model's attention mask is still wrong. [L07] §3.8: passing fixture runs test the machinery, not the model. |
| 15 | Three signals could have fired earlier; someone has to watch (35–36) | **Applied, mostly as gaps.** A business-level monitor: [L01] §7, Tutorial 0's billing budget alert, the only alert the course has you set up; [L15] §2 shows why it matters (an endpoint bills 24/7 with zero traffic). Someone watching: [L21] §3.8 and §6 G8, the CI's Slack step posts only on success, so a failed run is never announced. [L22] Lecture slides, idea 1: on one VM a person has to notice a crashed container. [L22] §3.2: a ReplicaSet notices a deleted Pod and replaces it by itself. |
| 16 | Recommenders can poison their own training data (38) | **Pieces only.** No tutorial retrains on its own outputs. The nearest case is one step of the loop: [L08] §3.2, a teacher LLM writes the training data, so its hallucinations become the student's training targets. |
| 17 | Training–serving skew as a pipeline bug; feature parity (39) | **Applied.** The fix: [L15] §3.1, the preprocessing lives inside the SavedModel's serving signature, so every client sends raw JPEG bytes and one definition serves them all; [L15] Lecture slides, idea 4, calls the alternative "client-side brittleness". The bug: [L13] §9 E13, the notebooks train on `image/255` and predict with `preprocess_input`. Its infrastructure cousin: [L15] §9 erratum 10, the pipeline trains with TF 2.17 and serves with a TF 2.12 container. |
| 18 | Hardware faults look statistically normal (40–44) | **Not applied.** No tutorial touches sensors or edge devices. The nearest device telemetry is [L13] §3.1: W&B records CPU and GPU utilisation for training runs. |
| 19 | GenAI has no single right answer; jailbreaks (46) | **Applied.** [L07] §3.8: evaluation grades properties over the trace rather than exact text, and repeats each case because the same input gives different outputs. Prompt injection, the jailbreak's cousin: [L07] §3.3 (retrieved text labelled as data) and Exercise 8 (`detect_injection`). |
| 20 | Defense in depth: system prompt, refusal training, classifiers (47) | **Applied.** The system prompt and its weakness: [L05] §9 E1 and Ex 4, the RAG system instruction is defined but never sent, so nothing redirects an off-topic question; [L06] §3.8, a prompt says "no monetary amounts" and code still checks with a regex. Refusal training, switched off: [L08] §4 Step 6 generates its data with Gemini's safety filters set to `OFF`. Independent checks: [L07] Exercise 8 (an injection detector) and [L06] §4 Part A (the quiz output must pass a JSON-schema check, cell 62). |
| 21 | Each GenAI incident maps to a missing control (48–52) | **Applied.** Review gate (Bard): [L06] §3.8 (a human "yes" before a plan is final), [L07] §3.4 (manager approval bound to a fingerprint of the exact cart) and §3.5 (human review of an email). Outbound control (Samsung): [L07] §3.6, recipients are checked against an allowlist in code. Citation check (Mata v. Avianca): [L06] §3.8, newsletter sources are registered only from search citation metadata. Grounding (Air Canada): [L05] §3.1 and §3.6, answers built from retrieved chunks. Permission boundary (Replit): [L07] §3.1, no Act 1 tool can place an order, whatever the prompt says, and §3.6, a skill gives guidance, never permission. |
| 22 | The principle carries over; LLM-as-judge (53) | **Applied, without a judge model.** [L07] §3.8: golden cases, repeats, immutable labels and property checks over traces; the final prose goes to a five-point human review. [L08] §3.8: loss and perplexity measure style fit, not correctness. No tutorial uses one LLM to grade another. |
| 23 | Match the signal to the failure type (55–57, 59) | **Pieces only.** No tutorial practises the matching, but the course's own failures make a good drill: see the practice table below. |
| 24 | Every cloud does the same five jobs (58) | **Applied, except streaming.** See the slide 58 table below. |

14 of the 24 ideas are applied in at least one tutorial, although ideas 1, 2, 12 and 15 mostly as failures or gaps that the tutorial shows. Five have pieces only (7, 8, 9, 16, 23). Five are not applied at all: the statistical detectors (5, 6, 10, 11) and hardware faults (18).

### The slide 58 table, row by row

| Layer (slide 58) | GCP product on the slide | What the course uses |
|---|---|---|
| General logging | Cloud Logging | Used without being set up: Vertex custom jobs ([L13] §3.4), Cloud Run ([L14] §5) and Vertex endpoints ([L15] §6) send stdout and server logs there. On the cluster: `kubectl logs` ([L22] §4 Part C). Agent runs: events and spans in SQLite ([L07] §3.8). |
| Metrics & dashboards | Cloud Monitoring | Training only: W&B charts and system metrics ([L13] §3.1–3.2), and L07's evaluation scorecard for agent runs ([L07] §3.8). No serving metrics anywhere. |
| Feature/prediction store | BigQuery, Firestore | Neither. The nearest thing is chat history as JSON files on a persistent volume ([L18] §3.6; [L22] §3.5 puts it on a PVC). |
| Streaming ingestion | Dataflow, Pub/Sub | None. |
| Drift monitoring (managed) | Vertex AI Model Monitoring | None. L15 deploys to the same kind of Vertex endpoint that this product watches, but creates no monitoring job ([L15] Lecture slides). |
| Alerting | Cloud Monitoring Alerts | A billing budget alert ([L01] §7), and a CI Slack message that fires only on success ([L21] §3.8, §6 G8). |

### Practice: the course's own failures, matched to a signal

Slides 55–57 drill matching a failure to the signal that would catch it. The tutorials supply their own cases. The first two columns come from the guides. The signals are our suggestions, in the lecture's vocabulary; cover the last column and try it first.

| Failure in a tutorial | What broke | A signal that would catch it *(ours)* |
|---|---|---|
| [L13] §9 E13: training scales by `/255`, prediction uses `preprocess_input` | Engineering bug: training–serving skew | A feature parity check (push the same images through both paths and compare the tensors), or move the preprocessing into the model as [L15] §3.1 does |
| [L15] §6 item 10, E7: a crashed training job leaves the step green, and the previous model gets deployed | Engineering bug in the pipeline | Fail the step when the job fails (`sync=True`, as E7 says), and check that the model on the endpoint comes from the latest run |
| [L15] §9 erratum 10: trained with TF 2.17, served by a TF 2.12 container | Infrastructure: version skew | A version parity check at deploy, plus a smoke prediction on known images after it |
| [L22] §6 item 13: 502/503 for the first minute after a deploy | System health | A readiness probe, and an error-rate monitor at the load balancer |
| [L21] §6 G8: failed CI runs never reach Slack | The alert path itself | Test the alert with a deliberately failing run |
| [L05] §9 E1: the RAG system instruction is never sent | A missing GenAI defense layer | A golden off-topic question whose expected answer is a redirect ([L05] Ex 4) |
| [L08] §4 Step 6: failed generation batches are printed and skipped | Data quality | Count and schema-check the generated rows before upload |
| [L23] §3.7: each pipeline run deploys an endpoint nothing calls, while the app keeps a fixed CNN | No champion/challenger; the model is never replaced | Monitor which model version serves production traffic, and how old it is |

### Questions to answer after the lecture

1. Why is a good score on a held-out test set not evidence that a deployed model is fine? Which two senses of "Training-Serving Skew" do slides 10 and 39 use? (10, 39)
2. What control was missing in Tay's case, and why is it a feedback-loop failure rather than data drift? What went wrong at the accidental relaunch? (11–13) Compare how L07 keeps the model from writing its own memory (guide §3.5).
3. Name the three layers of production monitoring, the question each one asks, and two metrics for each. (15)
4. Sort slide 16's three symptoms into the layers. Are slide 17's answer lines right? (15–17)
5. What does the KS statistic D measure? Sketch two empirical CDFs and mark D. How does D_critical change as the samples grow? (18–19)
6. What can serve as the reference distribution? How often should the test run for a fast-moving feature and for a slow one, and where do its results go? (18, 20)
7. You test 50 features a day at α = 0.05, and nothing has changed. About how many alerts do you get, and which two remedies does slide 21 give? What should a drift alert trigger, and what should it never trigger by itself? (21)
8. How does concept drift differ from data drift, and why can a KS test on the inputs miss it? What does prediction-to-outcome tracking plot? (22)
9. The labels arrive months late. Which two kinds of tool help before they arrive, and what does each one look at? (23–25)
10. Write a retraining policy in one sentence. What must a challenger show before it replaces the champion? (26) How does L07's `--compare` do this for prompts (guide §3.8)?
11. For each rollout strategy, whose output is acted on, and what do you learn from it? Which one fits the fraud team on slide 28? Which strategy does L15's Exercise E5 build, and why is the rolling update of L22 and L23 none of the four? (27–29)
12. Tell the Zillow story as before, during and after. Which three signals could have fired earlier, and what type is each? (31–36)
13. Why does a recommender need output-diversity monitoring, not just accuracy? (38)
14. What is a feature parity check, and why does a shared feature store make skew less likely? Find the skew in L13's notebooks (guide §9 E13), and say how L15 §3.1 avoids it. (39)
15. Why can't a KS test catch a dirty camera lens or a throttled inference chip? What check would, and does it run before or after the model? (40–44)
16. Why is a system prompt, on its own, the weakest of the three GenAI defense layers? Give one tutorial where a rule written in a prompt was not enforced. (47; L05 §9 E1, L06 §3.8)
17. For each incident on slides 48–52, name the missing control and where it sits in the system. (48–52)
18. What replaces KS tests and prediction-to-outcome tracking for generative systems, and what new risk does an LLM judge bring? (53)
19. Fill in slide 55's signal column before you look at slide 56. Then cover the last column of the practice table above and do the same. (55–56)
20. Name the five jobs of every monitoring stack, and the GCP product for each on slide 58. Which of them did you use in the course? (58)

### Study guides and video folders

The guides are in this repository's `guides/`. The video folders are in the Explainer_Videos repository under `videos/`, and each one already holds the episode's `digest.md` and `SLIDES.md`. The course map in `README.md` shows which videos are out; when this was written, only L01's was. The table lists the lectures cited above.

| Lecture | Study guide | Video folder |
|---|---|---|
| L01 | [L01] `L01-vms-venvs.md` | `ac215-l01-vms-venvs` |
| L05 | [L05] `L05-rag.md` | `ac215-l05-rag` |
| L06 | [L06] `L06-agents-1.md` | `ac215-l06-agents-1` |
| L07 | [L07] `L07-agents-2-harness.md` | `ac215-l07-agent-harness` |
| L08 | [L08] `L08-llm-finetuning.md` | `ac215-l08-llm-finetuning` |
| L09 | [L09] `L09-ci-testing-precommit.md` | `ac215-l09-ci-testing` |
| L11 | [L11] `L11-data-labeling-versioning.md` | `ac215-l11-data-labeling-versioning` |
| L13 | [L13] `L13-training-workflows.md` | `ac215-l13-training-workflows` |
| L14 | [L14] `L14-serverless-deployment.md` | `ac215-l14-serverless-deployment` |
| L15 | [L15] `L15-vertex-ml-workflows.md` | `ac215-l15-vertex-ml-workflows` |
| L18 | [L18] `L18-apis-frontend.md` | `ac215-l18-apis-frontend` |
| L20 | [L20] `L20-deployment-pulumi.md` | `ac215-l20-deployment-pulumi` |
| L21 | [L21] `L21-cicd-github-actions.md` | `ac215-l21-cicd-github-actions` |
| L22 | [L22] `L22-kubernetes-cloud.md` | `ac215-l22-kubernetes-cloud` |
| L23 | [L23] `L23-final-cicd-deployment.md` | `ac215-l23-final-cicd` |

[L01]: ../guides/L01-vms-venvs.md
[L05]: ../guides/L05-rag.md
[L06]: ../guides/L06-agents-1.md
[L07]: ../guides/L07-agents-2-harness.md
[L08]: ../guides/L08-llm-finetuning.md
[L09]: ../guides/L09-ci-testing-precommit.md
[L11]: ../guides/L11-data-labeling-versioning.md
[L13]: ../guides/L13-training-workflows.md
[L14]: ../guides/L14-serverless-deployment.md
[L15]: ../guides/L15-vertex-ml-workflows.md
[L18]: ../guides/L18-apis-frontend.md
[L20]: ../guides/L20-deployment-pulumi.md
[L21]: ../guides/L21-cicd-github-actions.md
[L22]: ../guides/L22-kubernetes-cloud.md
[L23]: ../guides/L23-final-cicd-deployment.md
