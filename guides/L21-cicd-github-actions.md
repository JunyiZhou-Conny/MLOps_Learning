# L21 · Automating Software Development: CI/CD with GitHub Actions II — study guide

[Ed lesson](https://edstem.org/us/courses/97373/lessons/166046/) · Tutorial: [`dlops-io/cheese-app-ci-cd`](https://github.com/dlops-io/cheese-app-ci-cd) `main` @ [`b8458ff`](https://github.com/dlops-io/cheese-app-ci-cd/tree/b8458ff0cc1898700b32a873b4665f43f50df71e) (Part 5 · GitHub Actions Remote CI; the same repo and commit as L09) · Colab: none for this lecture · Video: [AC215 · L21 follow-along](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l21-cicd-github-actions) · Made from the verified digest and real terminal captures, 2026-11-06

## 中文速览

- **做什么：** 还是 L09 那个很小的 FastAPI service（`/`、`/health`、`/euclidean_distance/` 三个 endpoint，一个 `power()`，26 个 pytest test：11 unit、10 integration、5 system），这次让 GitHub 替你跑。`.github/workflows/ci.yml` 定义了 6 个 job：`build` 只 build 一次 Docker image（tag 是 commit SHA），`docker save` 成一个约 176 MB 的 tar，作为 artifact `docker-image` 传给 4 个并行 job（Black/Flake8、unit + coverage、integration、system），最后 `test-summary` 汇总；设了 repository secret `SLACK_WEBHOOK_URL` 才会发 Slack。只有 push 到 `main`/`develop`、或者开 PR 进这两个 branch 才触发。全程不碰 GCP。
- **先把 repo 放到你自己能 push 的地方：** README 的 `git add .` / `git commit -m "Add CI pipeline"` 在 fresh clone 里只会得到 `nothing to commit, working tree clean`（`ci.yml` 早就 commit 好了）；`origin` 还是 `dlops-io` 的 repo，`git push` 会被 GitHub 拒绝。fork（然后在 Actions tab 里 enable workflows）或者建一个空 repo，`git remote set-url origin …`，再 `git push`，这一次 push 就是触发 run 的 event。
- **Idea 1 · 每个 job 都是一台全新的 machine，job 之间什么都不共享：** 录制时每个 check job 一开始 `docker images` 都是空的；所以 image 要 `docker save` → `upload-artifact` → 每个 job 再 `download-artifact` + `docker load`。少了 `docker load`，`docker run` 会去 Docker Hub 拉，得到 `pull access denied for cheese-app-api`，exit 125。lint 和 test 检查的是 bake 进 image 的 `/app/api`、`/app/tests`。
- **Idea 2 · `needs` 画出一个 DAG：** `build` fan-out 到 4 个 job；`test-summary` 只 `needs` 三个 test job，加上 `if: always()`。`lint-and-format` 不在 `needs` 里，所以第一次 run 是红的（Black 报 `would reformat /app/api/utils.py`），但同一个 run 里 summary 照样打印 `✅ All tests passed!`。
- **Idea 3 · CI 只认 exit code：** Black 是 blocking，Flake8 是 advisory（`continue-on-error: true`）；Black fail 之后 Flake8 这个 step 直接 skipped，看不到它的 output。coverage step 在 Linux runner 上其实 fail 了（`PermissionError`，exit 3，`coverage/` 是 root 建的，container 是 uid 1000），被 `continue-on-error` 盖住，job 还是绿的，artifact 里 0 个文件。
- **Idea 4 · local hooks 和 remote CI 是两张不同的网：** hook 只在跑过 `pre-commit install` 的那个 clone 里生效；`git commit --no-verify -m "quick fix"` 直接跳过（slides 29–31），CI 的 Black 再把它抓出来。但 CI 只重跑 Black 和 Flake8（只看 `api/`），7 个 hygiene hooks（包括 `detect-private-key`）在 CI 里根本不跑。
- **Idea 5 · push-triggered run 只报告、不拒绝：** run 变红的时候 commit 已经在 `main` 上了。真正能拦住的是 Part 6 的 branch protection（required status checks 要选 job 的 `name:`，比如 "Unit Tests"，不是 job ID `unit-tests`）。
- **最费时间的坑：** ① 第一次 run 一定是红的，README 里全绿的截图来自更早的 code state；`pre-commit run --all-files` 改好 `utils.py`，commit、push，六个 job 全绿。② Part 6 的 `echo "def broken(): assert False"` 不会被 pytest collect（还是 `11 passed`），要写 `def test_broken`（`1 failed, 11 passed`）。③ tests fail 时 Slack 永远不会发 "❌ CI Pipeline Failed"：`slack-check` step 没有 `if: always()`，被 skip 了。④ README 说的 "Docker Buildx caching" 并没有用上：build 跑在 `default` builder 上，每次从头 build。
- **做完要删：** 本地 `docker stop api-server && docker rm api-server`、`docker system prune`；private repo 上把 workflow Disable（Actions → "CI Pipeline" → "⋯" → Disable workflow），在 run 页面删掉旧的 artifact（`docker-image` 一天后自己过期）。没有任何 GCP 资源要删。
- **Lecture slides：** Lecture 21 slides（35 页）和这份 guide 各节怎么对应、做 tutorial 需要的 10 个 lecture ideas，以及 slides 和今天 repo 不一样的 9 处，都在下面的 [Lecture slides](#lecture-slides)。最要紧的两处：① slides 29–31 说用 `git commit --no-verify` 跳过的 local checks 会在 remote CI 上再跑一遍；但这个 `ci.yml` 只重跑 Black 和 Flake8（而且只看 `api/`），7 个 hygiene hooks（包括 `detect-private-key`）在 CI 里根本不跑，所以用 `--no-verify` commit 进去的 key file 照样一路绿灯（§8 Ponder 5）。② slides 26–27 把 pipeline 画成一条直线，最后的 Summary 报告 pass/fail；实际上 `build` 之后四个 job 并行，`test-summary` 只看三个 test job、不看 lint，所以 Black fail 时整个 run 是红的，summary 却打印 "✅ All tests passed!"。

## At a glance

**What you build.** A GitHub Actions pipeline (`.github/workflows/ci.yml`) that, on every push to `main`/`develop` and every pull request into them, builds the cheese-app-ci-cd FastAPI image once on a fresh GitHub-hosted VM and hands it as an artifact to four parallel jobs on their own VMs (Black/Flake8, unit tests with coverage, integration tests, system tests over real HTTP), then collects their results in a summary job that can also post to Slack. You push the repo to a repository of your own, watch the first run go red on Black, fix `utils.py` to turn it green, see what `git commit --no-verify` lets through and CI catches, and optionally make the checks a merge gate with branch protection (Part 6) and add an endpoint under full CI (Part 7).

**Time needed** (estimate). About 1.5 h for Part 5: setting up the repo, the first push, reading `ci.yml` next to the run logs, and the red → green fix. A run takes about 2 minutes of wall-clock time (the README screenshot shows 54 s for the build, the four checks in parallel, then 4 s for the summary). Add about 30 min for the optional Slack step, about 1 h for Parts 6-7, and 1-2 h for the exercises in §8. If you skipped L09, add 1-1.5 h for Parts 1-4.

**Prerequisites.**
- A GitHub account and a repo **you can push to**: a fork of `dlops-io/cheese-app-ci-cd`, or your own copy (§2, §4 Step 0).
- Docker (Docker Desktop on macOS), Git, and Python 3.9+ with `pip` (README.md:5-9). Local Python is used only for `pre-commit` and the optional local commands.
- Parts 1-4 of the same repo (L09): the image, the three test levels, the pre-commit hooks.
- Credentials: none. No GCP, no service accounts, no JSON keys. Optional: a Slack workspace where you can create an app with an *Incoming Webhook*, stored as the repository secret `SLACK_WEBHOOK_URL`.

**What it costs.** Nothing on GCP. GitHub Actions on standard GitHub-hosted runners is free for public repos. On a private repo, each run costs about 6 billed minutes (6 jobs, each rounded up to a whole minute) out of GitHub Free's 2,000 minutes per month at the time of writing, plus artifact storage for the image tar (about 176 MB per run, kept 1 day).

**Tear down, exactly** (details in §2):
1. Local: `docker stop api-server && docker rm api-server` if it is still running (README.md:199), then the README's Docker Cleanup (README.md:568-574): `docker container ls`, stop leftovers (`api-server`, `cheese-app-api-service`), `docker system prune`, `docker image ls`.
2. GitHub, if the repo is private: Actions tab → "CI Pipeline" → "⋯" → *Disable workflow* (or delete the file), and delete old artifacts on each run page. The `docker-image` artifact expires after 1 day by itself (`ci.yml:38`); `coverage-report-unit` keeps the repo's default retention (and, as written, holds no files: §4 Step 8).
3. Nothing in the cloud: no billable cloud resources are created.

<details>
<summary><b>Versions and sources this guide was checked against</b></summary>

- **README sections this lecture covers.** The course site source `tutorials_demo.md:270-275` titles the lecture "Automating Software Development: CI/CD with GitHub Actions and other tools II" and links only README Part 5.
  - Primary: [`#part-5-github-actions-remote-ci`](https://github.com/dlops-io/cheese-app-ci-cd/blob/main/README.md#part-5-github-actions-remote-ci) (README.md:277-365)
  - Context (L09 covered Parts 1-4): `#part-1-understanding-the-codebase` (51-92), `#part-2-identifying-code-quality-issues` (95-128), `#part-3-testing-with-pytest` (132-228), `#part-4-automating-with-pre-commit-hooks` (232-273)
  - Natural follow-ons that need a working Part 5: `#part-6-branch-protection-optional` (369-397), `#part-7-student-exercise---add-a-new-endpoint-with-full-ci` (401-453)
- **Primary repo:** `dlops-io/cheese-app-ci-cd`, branch `main`, commit `b8458ff0cc1898700b32a873b4665f43f50df71e`, committed 2025-11-13 13:59:04 -0500 (message "demo class 1"). It has a single branch, and `git ls-remote` on 2026-11-06 still showed `refs/heads/main` = `b8458ff0…`.
- **Context-only repos (used in §7):**
  - `dlops-io/cheese-app-v3`, branch `main`, commit `3ecef56fea879ac480d260c0906cd95baf05179a`, 2025-11-28 16:00:06 -0500 (the API you deployed in L20)
  - `dlops-io/cheese-app-v4`, branch `main`, commit `033f18713b9e1e7985a3080e85edab3ff01cefef`, 2025-12-02 14:13:03 -0500 (the CD workflows used in L23)
- **Files read in full:** all 17 tracked files: `.github/workflows/ci.yml`, `.gitignore`, `.pre-commit-config.yaml`, `Dockerfile`, `README.md`, `assets/pipline.png`, `docker-entrypoint.sh`, `docker-shell.sh`, `pyproject.toml`, `pytest.ini`, `src/api-service/api/{__init__,service,utils}.py`, `tests/__init__.py`, `tests/{unit/test_utils,integration/test_api,system/test_system_api}.py`. The full git history (14 commits) was read too; it includes a deleted second workflow (`docker-build.yml`) and the in-class demo commits.
- **Captures (2026-11-06).** Every step was run live, in fresh containers; the files are in the video folder's [`assets/terminal/`](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l21-cicd-github-actions/assets/terminal), with provenance in [`ASSETS.md`](https://github.com/JunyiZhou-Conny/Explainer_Videos/blob/main/videos/ac215-l21-cicd-github-actions/ASSETS.md).
  - *Laptop* (`laptop/`): a fresh Docker 29.8.2 engine standing in for a laptop with Docker Desktop, git 2.54.0, Python 3.14.10, pre-commit 4.7.0 (with the config's pinned Black 24.1.1 and Flake8 7.0.0). A bare repository on the same machine stands in for "your repository" on GitHub, because the recording machine cannot push to GitHub.
  - *Runners* (`runner/run1`, `run2`, `run3`, `run-demo`, `noload`): every job of `ci.yml` in its **own** fresh container with an **empty** Docker engine, running the workflow's own `run:` scripts verbatim with GitHub's step rules (skip after a failure unless `if: always()`, `continue-on-error`, `needs`). The `uses:` steps (checkout, Buildx setup, artifact upload and download, Slack) need GitHub and were replaced by stand-ins (a `git archive` extract, `docker buildx version`, copying the tar). These are Alpine containers running as root, not GitHub's Ubuntu VMs, so their **timings are not GitHub's**; durations below come only from the README screenshot.
  - *act* (`laptop/60-63`): [nektos/act](https://github.com/nektos/act) 0.2.97 reading `ci.yml` and playing GitHub's runner on the laptop (all jobs share one Docker engine there). Same verdicts as the stand-in runners.
  - Versions inside the image (unpinned; yours may be newer): Python 3.11.18, black 26.10.1, flake8 7.5.0, pytest 9.2.0, pytest-cov 7.1.0, fastapi 0.162.0, uvicorn 0.54.0.
- **Not captured:** a hosted GitHub Actions run, the Actions tab, a Slack message, the Settings pages and a push refused by branch protection. What this guide says about them comes from `ci.yml`, the README (its screenshot `assets/pipline.png`, transcribed) and GitHub's documented behaviour, and is labelled *expected* or *recorded*.
- **Colab notebooks:** none for this lecture.
- **Ed lesson:** not accessible when these sources were checked; the lecture-to-tutorial mapping comes from the course site source above.

</details>

## Lecture slides

The instructor's deck for this lecture is *Lecture 21: Automating Software Development: CI/CD with GitHub Actions and other tools II*, 35 slides. Slide numbers are PDF page numbers; from slide 16 on, the numbers printed in the slide footers run ahead of them. The slides are not reproduced here; what follows is in our own words. The full slide digest and the cross-check with the planned video live in the Explainer_Videos repo, in `videos/ac215-l21-cicd-github-actions/SLIDES.md`. After a two-slide recap of L09's local hooks, the deck has four parts: remote Git hooks (4–7), GitHub webhooks (8–12), continuous integration (13–31) and continuous deployment, which it postpones (32–34).

**Map**

| This guide | Slides |
|---|---|
| At a glance; §7 Where this sits in the course | 2–3, 14–16 (L09's local hooks run only on your machine; CI runs the checks on the shared repository); 33–34 (CD comes later: L23) |
| §1 What you build (the diagram) | 26–27 (the five-stage pipeline); 21 (the CI loop) |
| §2 Prerequisites and costs (Actions minutes) | 24 (how often to run CI vs what it costs) |
| §3.1 Workflow anatomy; §4 Step 5 (triggers) | 22, 25 (CI defined; GitHub Actions on push or pull request); 23 (each merge is tested) |
| §3.2 Runners; §3.3 Build once | 16, 26–27 (Build Container comes first) |
| §3.4 The job graph | 26–27 (drawn as a straight line; the real graph fans out) |
| §3.5 Exit codes, Black and Flake8 | 14, 22, 27 |
| §3.6 Test altitudes | 27 |
| §3.7 Outputs and summaries | 16, 27 (Summary) |
| §3.8 Secrets; §4 Step 16 Slack | 7, 9–12 (webhooks; slide 11's imagined Slack message) |
| Checklist Parts 1–4; §4 Steps 1–4 (L09 context) | 2, 14 (local hooks) |
| Checklist Part 5; §4 Steps 12–14 (push, watch, turn green) | 21 (the loop: fix and push again); 28 (link to README Part 5) |
| Checklist Part 6; §4 Step 17 (branch protection) | 5–6 (`pre-receive` and `update`: rules enforced on the server) |
| Checklist *Skip the hooks*; §4 Step 15 (`--no-verify`, captured); §8 Ponder 5 (what CI actually checks) | 29–31 (`--no-verify`) |
| §5 Code tour, §6 Gotchas, §9 Errata | none (tutorial-only) |
| Background, not needed to finish the tutorial | 17–20 (non-determinism in ML, and four remedies: version everything, automate retraining and testing, monitor in production, controlled deployment); the ML half of 23 |

**Lecture ideas you need for this tutorial**
1. Local Git hooks run only where someone ran `pre-commit install`, and they stop at the push, so a team cannot rely on them (2–3, 14–15).
2. `git commit --no-verify` skips every local pre-commit check; whatever slips through can only be caught on the shared repository (29–31).
3. CI runs a series of scripts automatically whenever the code changes: integrate, test, enforce coding standards, run static analysis (16, 22, 25).
4. The CI loop: developers commit, the code is built and tested, the results go back to the developers, who fix and commit again (21). Your red → green run in §4 Steps 13–14 is one turn of it.
5. The course pipeline: a commit triggers it; build the container first, so every check runs in one environment; then Black and Flake8; then unit, integration and system tests; then a pass/fail summary (26–27).
6. Each merge into the shared repository should trigger the tests (23). On a pull request, this workflow tests the merge commit (§4 Step 5).
7. Server-side hooks enforce rules where code is received: `pre-receive` can refuse a push, `post-receive` runs after it is in (5–6). A push-triggered Actions run is the second kind; branch protection (Part 6) is the gate that refuses.
8. Webhooks carry repository events to outside services such as Slack, Jenkins or a deploy server (7, 9–12). This repo's Slack step works the other way round: your workflow calls a Slack incoming-webhook URL.
9. Running CI more often catches problems sooner but costs compute, so the setup depends on your resources (23–24). Here that means the branch filter, parallel jobs, and about 6 billed minutes per run on a private repo (§2).
10. CD automates the release once everything is tested and approved; it comes later, in L23 (33–34).

**Where the slides and today's tutorial differ** (in each case, follow the repo at `b8458ff`)
- Slide 2 says `pre-commit` runs before code is accepted on the server. It runs on your machine before each commit is created (README Part 4); "before the server accepts it" is `pre-receive` (slide 5).
- Slide 5 names GitHub Actions as one of the servers where remote hooks run and enforce rules. A push-triggered run starts after the push has been accepted and cannot refuse it; on GitHub.com the gate that refuses is branch protection with required checks (§4 Step 17).
- Slide 14's local chain is linters → formatters → tests. This repo's hooks run seven hygiene checks, then Black (format), then Flake8 (lint), and no tests; CI also runs Black first, and Flake8 is skipped when Black fails (§3.5).
- Slide 25 says the pipeline runs on every push or pull request. Only pushes to `main`/`develop` and PRs into them start a run; a feature-branch push runs nothing (§4 Step 5, §6 G2).
- Slides 26–27 draw one straight line ending in a Summary that reports pass/fail. After `build`, four jobs run in parallel, and `test-summary` reads only the three test jobs, so when Black fails the run is red while the summary says "✅ All tests passed!" (§3.4, §6 G10).
- Slides 9–12 have a GitHub webhook post to Slack on every push. No repository webhook exists: the last steps of `test-summary` call the Slack incoming-webhook URL stored as the secret `SLACK_WEBHOOK_URL`, only when it is set, and never when tests fail (§3.8, §6 G8).
- Slide 11's imagined message shows the failed step (`pre-commit run --all-files`), test and lint counts and the duration. The real message has repository, branch, commit, author, ✅/❌ for each test job and two links; this CI never runs pre-commit and reports nothing about lint (§4 Step 16).
- Slides 29–31 say the remote CI runs the checks again. Here it re-runs only Black and Flake8, on `api/`; the hygiene hooks, `detect-private-key` included, never run in CI, so a key file committed with `--no-verify` passes (§4 Step 15, §8 Ponder 5). A CI step running `pre-commit run --all-files` closes the gap.
- Slide 28's link ends in `#part-5-github-actions-remote-cicd`, the anchor of an old heading; the current one is `#part-5-github-actions-remote-ci` (see [Links](#links)).

## Command checklist

Commands in backticks are exactly as the README writes them (placeholders kept). Plain items are browser steps or edits. Items marked *(extra)* are not in the README; they come from §4 of this guide. Run everything from the repo root unless an item says "inside the container". Parts 1-4 are context from L09; Part 5 is this lecture.

### Before the README *(extra)*

Put the repo somewhere Actions can run it (§4 Step 0). The README only says "Clone or download from your repository" (README.md:19-20), but Actions runs only in a GitHub repo you can push to, and only from `.github/workflows/` at that repo's root. Use a **fresh** clone, not your L09 folder: if you committed the Black fix there, your first run comes out green and you miss the red one. If you use this workspace's `tools/sync_tutorials.py`, the clone is in `tutorials/cheese-app-ci-cd`: its own git repo (gitignored here, so no embedded-repo problem), but its `origin` is `dlops-io`, so you still need Route B's `git remote set-url` step before you can push (and, if you synced with `--pinned`, `git switch main` first, so your fix commits land on `main` rather than on a detached HEAD).

- [ ] `git ls-remote https://github.com/dlops-io/cheese-app-ci-cd.git` — *(extra)* `refs/heads/main` should still be `b8458ff0cc1898700b32a873b4665f43f50df71e` (it was on 2026-11-06; the `refs/pull/…` lines are pull requests, not branches).

*Route A: fork*
- [ ] Fork `dlops-io/cheese-app-ci-cd` on GitHub, open your fork's **Actions** tab and click the button that enables workflows (Actions is disabled on forks until you do).
- [ ] `git clone https://github.com/<you>/cheese-app-ci-cd.git` — *(extra)* clone your fork as its own repo, not inside another git repo (§6 G2, G3).
- [ ] `cd cheese-app-ci-cd` — *(extra)*

*Route B: your own empty repo*
- [ ] Create an empty repo such as `<you>/cheese-app-ci-cd` on GitHub.
- [ ] `git clone https://github.com/dlops-io/cheese-app-ci-cd.git` — *(extra)* the course repo, as its own clone.
- [ ] `cd cheese-app-ci-cd` — *(extra)*
- [ ] `git remote -v` — *(extra)* `origin` is still `https://github.com/dlops-io/cheese-app-ci-cd.git`: a push there is refused (permission denied).
- [ ] `git remote set-url origin https://github.com/<you>/cheese-app-ci-cd.git` — *(extra)* point `origin` at your repo. The README's own `git push` (Part 5) then sends `main` and starts the first run.

*Either route*
- [ ] `git log -3 --format='%h %ci %s'` — *(extra)* the top line is `b8458ff 2025-11-13 13:59:04 -0500 demo class 1`; the one below it, `c3b227f`, is the in-class demo commit (§4 Step 11).
- [ ] `ls -la .github/workflows/` — *(extra)* `ci.yml` is at the repo root, where GitHub looks.
- [ ] Checkpoint (after the first push): the Actions tab lists a workflow called **CI Pipeline** (`ci.yml:5`).

### Part 1: Understanding the Codebase *(context, L09)*

*Run the Application* (README.md:67-92)
- [ ] `sh docker-shell.sh` — builds image `cheese-app-api-service`, runs it with `-p 9000:9000` and opens bash inside it.
- [ ] `uvicorn api.service:app --host 0.0.0.0 --port 9000 --reload` — inside the container: starts the API on port 9000.
- [ ] Open `http://localhost:9000` — `{"message":"Welcome to the Cheese App CI/CD Tutorial!"}`.
- [ ] Open `http://localhost:9000/health` — `{"status":"healthy"}`.
- [ ] Open `http://localhost:9000/euclidean_distance/?x=3&y=4` — `distance` 5.0, plus a `"message"` field.
- [ ] `exit` — "Please exit and remove your container after this" (README.md:92); `--rm` removes it and frees port 9000.

### Part 2: Identifying Code Quality Issues *(context, L09)*

*Option A: Check with Docker* (README.md:103-113)
- [ ] `docker build -t cheese-app-api:local .` — the image every later local command uses; code and tests are baked in.
- [ ] `docker run --rm cheese-app-api:local flake8 --max-line-length=120 api/` — `api/utils.py:7:15: E231 …` and `api/utils.py:13:1: E303 …`.
- [ ] `docker run --rm cheese-app-api:local black --check --diff api/` — Black's default 88 columns: flags `utils.py` *and* `service.py` (CI at 120 flags only `utils.py`).

*Option B: Check Locally (if Python installed)* (README.md:116-125)
- [ ] `pip install black flake8` — on the host.
- [ ] `flake8 src/api-service/api/` — default 79 columns adds `service.py:15:80: E501 line too long (95 > 79 characters)`, which CI never flags.
- [ ] `black --check --diff src/api-service/api/` — default 88 columns.

### Part 3: Testing with Pytest *(context, L09)*

*Option 1: Run Unit & Integration Tests (Recommended)* (README.md:163-182)
- [ ] `docker build -t cheese-app-api:local .` — rebuild after every edit; code and tests are baked into the image.
- [ ] `docker run --rm cheese-app-api:local pytest tests/unit/ -v` — 11 unit tests.
- [ ] `docker run --rm cheese-app-api:local pytest tests/integration/ -v` — 10 integration tests.
- [ ] `docker run --rm cheese-app-api:local pytest tests/unit/ tests/integration/ -v` — both folders.
- [ ] `docker run --rm cheese-app-api:local pytest tests/unit/ --cov=api --cov-report=term` — `service.py` at 0%: unit tests never import it.

*Option 2: Run System Tests* (README.md:184-202)
- [ ] `docker build -t cheese-app-api:local .`
- [ ] `docker run -d --name api-server -p 9000:9000 -e DEV=1 cheese-app-api:local` — the server in the background.
- [ ] `docker run --rm --network host cheese-app-api:local pytest tests/system/ -v` — 5 passed; `1 passed, 4 skipped` means the server was unreachable.
- [ ] `docker run --rm --network container:api-server cheese-app-api:local pytest tests/system/ -v` — *(extra)* the robust alternative on Docker Desktop.
- [ ] `docker stop api-server && docker rm api-server` — clean up.
- [ ] `docker rm -f api-server` — *(extra)* only if "the container name "/api-server" is already in use".

*Option 3: Interactive Container Workflow* (README.md:204-228)
- [ ] `sh docker-shell.sh` — then the next four commands inside the container.
- [ ] `pytest tests/unit/ -v`
- [ ] `pytest tests/integration/ -v`
- [ ] `pytest tests/unit/ tests/integration/ -v`
- [ ] `pytest tests/unit/ --cov=api --cov-report=html` — writes `htmlcov/` inside the `--rm` container; gone when you `exit`.

### Part 4: Automating with Pre-commit Hooks *(context, L09)*

*(README.md:232-273)*
- [ ] `pip install pre-commit` — outside the container.
- [ ] `pre-commit install` — from the repo root; installs the Git hook.
- [ ] `git commit -m "Your commit message"` — from now on the hooks run automatically on every commit.
- [ ] `pre-commit run --all-files` — manual run on all files: the Black hook reports *Failed* ("files were modified by this hook") and rewrites `src/api-service/api/utils.py`; a second run passes.
- [ ] `git checkout -- src/api-service/api/utils.py` (or `git stash`) — *(extra)* undo that rewrite if you want to watch CI catch the problem first (§4 Steps 7 and 13).
- [ ] `pre-commit run` — manual run on staged files only.

### Part 5: GitHub Actions (Remote CI)

*CI Pipeline (`.github/workflows/ci.yml`)* (README.md:281-342) — read each block next to §4 and §5
- [ ] Trigger block `ci.yml:5-11` — push to `main`/`develop`, or a PR whose *base* is `main`/`develop`.
- [ ] `build` (`ci.yml:15-38`) — checkout, Buildx, `docker build -t cheese-app-api:${{ github.sha }} .`, `docker save`, upload artifact `docker-image` (kept 1 day).
- [ ] `lint-and-format` (`ci.yml:41-67`) — Black blocking, Flake8 advisory.
- [ ] `unit-tests` (`ci.yml:70-102`) — the pytest gate, an advisory coverage run, upload `coverage-report-unit`.
- [ ] `integration-tests` (`ci.yml:105-125`) — `TestClient`, no server.
- [ ] `system-tests` (`ci.yml:128-169`) — server container, `sleep 10` + `curl -f`, tests over `--network host`, logs and cleanup always.
- [ ] `test-summary` (`ci.yml:172-257`) — `if: always()`, reads the three test results, optional Slack.

*Push to GitHub* (README.md:344-349)
- [ ] `git add .` — stages everything, including generated files `.gitignore` misses (e.g. a `coverage/` folder). In a fresh clone: no output.
- [ ] `git commit -m "Add CI pipeline"` — in a fresh clone or fork this prints `nothing to commit, working tree clean` and exits 1: `ci.yml` is already committed. Harmless; go on.
- [ ] `git push` — to your own repo (Route B): `* [new branch]      main -> main`. This push is the event that starts **run 1**. With `origin` still on `dlops-io`, GitHub refuses it (permission denied).
- [ ] `git commit --allow-empty -m "Trigger CI"` then `git push` — *(extra)* only on a fork, where `git push` says `Everything up-to-date` and starts nothing. The workflow has no manual trigger (`ci.yml:7-11` lists only `push` and `pull_request`), so a run needs a new commit; the Black fix below works too.

*Watch GitHub Actions* (README.md:351-365)
- [ ] Go to your GitHub repository → "Actions" tab → the run → the graph view. Green checkmark = success, red X = failure.
- [ ] Expected at `b8458ff` (confirmed on the stand-in runners and with act): Build Docker Image ✓, **Lint and Format Check ✗** (Black `would reformat /app/api/utils.py`; Flake8 skipped), Unit Tests ✓, Integration Tests ✓, System Tests ✓, Test Summary ✓ (`✅ All tests passed!`), **overall run ✗**. This does not match the all-green `assets/pipline.png`, which shows an earlier code state.
- [ ] *(extra)* Click into each job and read every step's log; the artifacts (`docker-image`, `coverage-report-unit`) are listed at the bottom of the run summary page. In Unit Tests, open "Generate coverage report": it fails with a `PermissionError` while the job stays green (§4 Step 8).
- [ ] `act -l` — *(extra, optional; needs [act](https://github.com/nektos/act) installed)* lists the six jobs in three stages (0: build; 1: the four checks; 2: test-summary), read from `ci.yml`.
- [ ] `act push -P ubuntu-latest=-self-hosted --artifact-server-path /tmp/act-artifacts` — *(extra, optional)* plays the whole run on your laptop: same verdict as run 1, ending `Error: Job 'Lint and Format Check' failed`. With `-self-hosted` every job shares your Docker engine, so it does not show the fresh-machine point.

*Turn it green* *(extra, §4 Step 14)*
- [ ] `pip install pre-commit` and `pre-commit install` — Part 4 (L09), if this clone does not have the hook yet: `pre-commit installed at .git/hooks/pre-commit`.
- [ ] `pre-commit run --all-files` — the Black hook `Failed`, `reformatted src/api-service/api/utils.py`, exit 1. Run it again: all hooks `Passed`.
- [ ] `git diff` — *(extra)* `def power(base, exponent):` and one blank line removed.
- [ ] `git add .`, `git commit -m "Format utils.py with Black"` (any message), `git push` — **run 2**: all six jobs green, which now matches the screenshot.
- [ ] Option B instead of pre-commit: `docker run --rm -v "$(pwd)/src/api-service/api":/app/api cheese-app-api:local black --line-length 120 api/` — *(extra)* Black inside the image, writing to your host files. Needs `cheese-app-api:local` from Part 2; on a Linux host whose user is not uid 1000, use pre-commit or edit by hand.
- [ ] Option C: edit by hand — `def power(base, exponent):` and delete one of the three blank lines.

*Skip the hooks, meet CI* *(extra, lecture slides 29–31; §4 Step 15)*
- [ ] `sed -i 's/z = power(x, 2) + power(y, 2)/z=power(x,2)+power(y,2)/' src/api-service/api/service.py && git diff` — *(extra)* a hurried edit of `service.py:43`.
- [ ] `git add .` then `git commit -m "quick fix"` — the Black hook stops the commit (`Failed`, `reformatted src/api-service/api/service.py`, exit 1); `git status --short` shows `MM`.
- [ ] `git commit --no-verify -m "quick fix"` — the slide's command: the commit goes through with no hooks. `git push` → **run 3**: Lint and Format Check ✗ (`would reformat /app/api/service.py`), everything else ✓.
- [ ] Clean up the experiment — *(extra)* `git restore src/api-service/api/service.py` drops the hook's uncommitted rewrite; to undo the commit itself on your repo, fix the line (`pre-commit run --all-files`), commit and push again.

*Optional: Slack notifications* *(extra, §4 Step 16; the README never mentions Slack)*
- [ ] Create a Slack app with Incoming Webhooks and copy the webhook URL (it looks like `https://hooks.slack.com/services/<your-webhook-path>`; never commit it).
- [ ] Repo Settings → Secrets and variables → Actions → New repository secret → name `SLACK_WEBHOOK_URL`, paste the URL. (Not Settings → Webhooks: that is for GitHub calling out.)
- [ ] Push a new commit to `main` (or re-run the workflow) — expected: a Slack message headed "✅ CI Pipeline Passed". Failures send nothing (§6 G8).

### Part 6: Branch Protection (Optional)

*Configure Branch Rules* (README.md:371-379) — do the red → green fix first
- [ ] Go to **Settings** → **Branches** → **Add rule** (today labelled "Add classic branch protection rule", or use "rulesets"); branch name pattern `main`.
- [ ] Enable "Require a pull request before merging" and "Require status checks to pass before merging".
- [ ] Select the checks. The README lists `lint-and-format`, `unit-tests`, `integration-tests`, `system-tests` (job IDs); the picker shows the jobs' `name:` values: `Lint and Format Check`, `Unit Tests`, `Integration Tests`, `System Tests`. They appear only after they have run once.
- [ ] Save changes. Private repos need a paid plan for this; on GitHub Free it works on public repos.

*Test the Protection* (README.md:381-397)
- [ ] `git checkout -b feature/test-protection`
- [ ] `echo "def broken(): assert False" >> tests/unit/test_utils.py` — as written this breaks nothing: pytest never collects `broken` (captured: the image still reports `collected 11 items`, `11 passed`).
- [ ] `echo "def test_broken(): assert False" >> tests/unit/test_utils.py` — *(extra)* use this instead: `tests/unit/test_utils.py::test_broken FAILED`, `1 failed, 11 passed`, exit 1.
- [ ] `git add .`
- [ ] `git commit -m "Intentionally break tests"`
- [ ] `git push origin feature/test-protection` — triggers no run (push filter is `main`/`develop`).
- [ ] Create a pull request on GitHub into `main` — the run starts now; with `test_broken`, Unit Tests fails and merging is blocked (expected; not captured).

### Part 7: Student Exercise - Add a New Endpoint with Full CI

*(README.md:401-453)*
- [ ] Add the `/add/` endpoint snippet (README.md:405-410) to `src/api-service/api/service.py`.
- [ ] Add `test_add_endpoint` (README.md:413-419) to `tests/integration/test_api.py` at module level (it has no `self`), like `test_api_health_check`.
- [ ] `docker build -t cheese-app-api:local .` — rebuild: code and tests are baked in.
- [ ] `docker run --rm cheese-app-api:local pytest tests/ -v` — all unit and integration tests pass, including `test_add_endpoint`; system tests show 1 passed, 4 skipped (no server running).
- [ ] `docker run --rm cheese-app-api:local pytest tests/unit/ -v`
- [ ] `docker run --rm cheese-app-api:local pytest tests/integration/ -v`
- [ ] `docker run --rm cheese-app-api:local black --check --line-length 120 api/` — the CI-width Black check.
- [ ] `docker run --rm -v $(pwd)/src/api-service:/app cheese-app-api:local black --line-length 120 api/` — as written it hides `/app/docker-entrypoint.sh` and fails: `/bin/bash: docker-entrypoint.sh: No such file or directory`, exit 127 (checked for the exercises). Use the next item.
- [ ] `docker run --rm -v "$(pwd)/src/api-service/api":/app/api cheese-app-api:local black --line-length 120 api/` — *(extra)* the working version: mount only the package.
- [ ] `git add .`
- [ ] `git commit -m "Add addition endpoint with tests"`
- [ ] `git push`
- [ ] Watch the CI pipeline run automatically.

### Docker Cleanup

*(README.md:568-574)*
- [ ] `docker container ls` — what is still running?
- [ ] Stop any container that is running, in particular `docker stop api-server && docker rm api-server` (README.md:199) and `cheese-app-api-service`.
- [ ] `docker system prune`
- [ ] `docker image ls`
- [ ] *(extra)* Private repo: Actions → "CI Pipeline" → "⋯" → *Disable workflow*, and delete old artifacts on each run page.

*The README's Quick Command Reference and Troubleshooting sections (README.md:457-566) mostly repeat Parts 1-4 and 7, plus host-side variants such as `PYTHONPATH=src/api-service pytest tests/unit/ -v` (README.md:512); they are checklisted in the [L09 guide](L09-ci-testing-precommit.md#quick-command-reference-and-troubleshooting). Note §6 G11 and G18 before running them.*

---

## 1. What you build

You start with a tiny FastAPI service: three endpoints (`/`, `/health`, `/euclidean_distance/`), a `power()` helper, and 26 pytest tests at three levels (11 unit, 10 integration, 5 system). You get GitHub to check every push to `main`/`develop` and every pull request into them, with no one watching.

- The workflow file `.github/workflows/ci.yml` runs on GitHub-hosted Ubuntu VMs.
- It **builds the Docker image once**, tags it with the commit SHA and saves it as a tar.
- It then passes that tar as an **artifact** to four **parallel jobs**, each on its own fresh VM: Black/Flake8, unit tests with coverage, integration tests using FastAPI's `TestClient`, and system tests that start the real server in one container and call it over HTTP from a second container.
- A final **summary job** reads the three test jobs' results. If a `SLACK_WEBHOOK_URL` **repository secret** exists, it also posts to Slack.

You see the outcome as green or red checks on your commits and PRs. Part 6 turns those checks into a merge gate. Nothing here touches GCP, so there is no cloud bill.

```
 YOUR LAPTOP (Docker Desktop)                           GITHUB.COM
 +-------------------------------------+                  +-------------------------------------+
 | cheese-app-ci-cd/ (git work tree)   |    git push      | repo <you>/cheese-app-ci-cd         |
 | pre-commit hooks run here (Part 4)  | ---------------> | .github/workflows/ci.yml  (at ROOT) |
 | sh docker-shell.sh ->               | (main/develop    | Settings > Secrets and variables >  |
 |   container cheese-app-api-service  |  or open a PR)   |   Actions: SLACK_WEBHOOK_URL (opt.) |
 |   uvicorn :9000 <-> localhost:9000  | <--------------- | checks: green/red on commit & PR    |
 +-------------------------------------+  status checks   +-------------------------------------+
                                                                            | event: push / pull_request
                                                                            v
 GITHUB ACTIONS  (each box = a brand-new ubuntu-latest VM, destroyed when its job ends)
 +------------------------------------------------------------+
 | build: checkout -> docker build -t cheese-app-api:<sha> .  |
 |        -> docker save -o /tmp/cheese-app-api.tar           |
 +------------------------------------------------------------+
                               | upload-artifact "docker-image" (kept 1 day)
                               v
             [ artifact store: docker-image = cheese-app-api.tar ]
          download-artifact + docker load, separately in EACH job below
          |                   |                  |                             |
          v                   v                  v                             v
 +-----------------+  +---------------+  +--------------+  +----------------------------------------+
 | lint-and-format |  | unit-tests    |  | integration- |  | system-tests                           |
 |  black --check  |  |  pytest unit  |  | tests        |  |  +--------------+  HTTP  +-----------+ |
 |  flake8 (soft)  |  |  pytest --cov |  |  pytest +    |  |  | api-server   |<-------| pytest    | |
 +-----------------+  |  -> artifact  |  |  TestClient  |  |  | uvicorn      | :9000  | system    | |
                      |  coverage-    |  |  (no server) |  |  | -p 9000:9000 |        | --network | |
                      |  report-unit  |  +--------------+  |  +--------------+        | host      | |
                      +---------------+                    |                          +-----------+ |
                                                           +----------------------------------------+
  (lint is NOT an input to test-summary)
                              |                  |                             |
                              +------------------+-----------------------------+
                                                      | needs.<job>.result: success / failure / skipped / cancelled
                                                      v
                                       +-------------------------------+
                                       | test-summary  (if: always())  | --- HTTPS POST, only if the secret is set ---> Slack
                                       +-------------------------------+
```

---

## 2. Prerequisites and costs

**Accounts**
- A GitHub account. Required: Actions only runs on a repo **you** can push to.
- Optional: a Slack workspace where you can create an app with an *Incoming Webhook*, to try the notification step.
- No GCP, no service accounts, no JSON keys. Of the late-course tutorials, this is the one that runs entirely outside GCP.

**Local installs** (README.md:5-9): Docker (Docker Desktop on macOS), Git, and Python 3.9+ with `pip`.
- Local Python is used to install `pre-commit` for Part 4 (README.md:240), and optionally for Part 2's Option B (`pip install black flake8`, README.md:118) and the "Run Locally Without Docker" commands (README.md:499-514).
- The image itself uses `python:3.11-slim-bookworm` (Dockerfile:2). It is a multi-arch base, so on Apple Silicon it builds natively as arm64, while CI builds amd64. The dependencies are pure-Python or ship wheels, so this tutorial has no architecture pitfalls.

**A repo where Actions will run.** The README only says "Clone or download from your repository" (README.md:19-20). GitHub runs workflows **only** from `.github/workflows/` at the **root** of a repository. Your options:
- **Fork** `dlops-io/cheese-app-ci-cd` on GitHub. On forks, Actions is disabled until you click the "enable workflows" button on the Actions tab.
- Create a new empty repo such as `<you>/cheese-app-ci-cd`, point your clone's `origin` at it, and push `main`.
- If you keep everything in one monorepo (for example `JunyiZhou-Conny/MLOps_Learning` with this project in a subfolder), `ci.yml` inside the subfolder will **never run**. You must move it to the monorepo's root `.github/workflows/` and adapt it (see §6, G2). Also, copying a `git clone` (with its own `.git/`) into another repo makes Git record an *embedded repository* (a gitlink), not the files.

**Secrets (optional).**
- `SLACK_WEBHOOK_URL` is a repository secret. Create it under repo **Settings → Secrets and variables → Actions → New repository secret**.
- It is read in two places:
  - the shell check at `.github/workflows/ci.yml:197`
  - the Slack action's environment at `.github/workflows/ci.yml:255-257`, together with `SLACK_WEBHOOK_TYPE: INCOMING_WEBHOOK`.
- Nothing in this repo reads secrets from disk. `.gitignore:48-52` ignores `secrets/`, `*.key`, `*.pem` and `.env` anyway, and the pre-commit hook `detect-private-key` (`.pre-commit-config.yaml:25-26`) is a second guard.
- The README never mentions the Slack step or this secret.

**Costs and what to shut down**
- **GitHub Actions minutes:**
  - On standard GitHub-hosted runners, public repos are free.
  - Private repos use your plan's included minutes. At the time of writing, GitHub Free includes 2,000 minutes per month; check Settings → Billing.
  - GitHub bills each *job* separately and rounds it **up** to a whole minute. A full run has 6 jobs, so it costs about **6 billed minutes** even though it finishes in about 2 minutes of wall-clock time (the README screenshot shows 54 s + 22/18/20/39 s + 4 s).
- **Artifact storage:**
  - Each run uploads the image tar `docker-image`: about 176 MB in the captures (176,112,128 bytes on the stand-in runner; act's upload reported 174,794,992), large because the image includes `build-essential` (Dockerfile:15-16). It is kept for 1 day (`ci.yml:38`).
  - Each run also uploads `coverage-report-unit` with the repo's default retention.
  - On private repos these count toward your plan's storage quota. You can delete old artifacts on each run page.
- **To stop CI:** Actions tab → "CI Pipeline" → "⋯" → *Disable workflow*, or delete the file.
- **Local cleanup** (README.md:568-574): `docker container ls`, stop leftovers (in particular `docker stop api-server && docker rm api-server`, README.md:199), `docker system prune`, `docker image ls`.
- **No billable cloud resources** are created.

---

## 3. Concepts this tutorial teaches

### 3.1 Workflow anatomy: event → workflow → jobs → steps
- **Explanation:** A *workflow* is a YAML file in `.github/workflows/`. An *event* (`on:`), such as a push or a PR, starts a *run*. A run contains *jobs*, and each job is a list of *steps*. A step is either a shell script (`run:`) or a reusable *action* (`uses: actions/checkout@v4`).
- **Mental model:** A recipe card that GitHub executes whenever the doorbell (the event) rings. Jobs are separate cooks, and steps are the lines on each cook's card.
- **Analogy:** A restaurant ticket. The order comes in (event), the ticket (workflow) splits into stations (jobs), and each station follows its own checklist (steps).
- **Misconception:** "The workflow runs on my laptop" or "it runs once per file". It runs on GitHub's machines, once per triggering event, against the commit that event points to.

### 3.2 Runners are disposable machines; jobs share nothing
- **Explanation:** `runs-on: ubuntu-latest` asks for a fresh GitHub-hosted VM for **each job**. When the job ends, the VM is destroyed. Files, Docker images and environment variables do not carry over from one job to another. Within a job, steps share the same machine and filesystem.
- **Mental model:** Every job wakes up with amnesia in an empty room containing only Docker, Git and the tools GitHub pre-installs.
- **Analogy:** Hotel rooms. Housekeeping wipes everything between guests, so if you want something in the next room, you must carry it there.
- **Misconception:** "The image built in `build` is already there in `unit-tests`." It is not: on the captured stand-in runners, `docker images` in a fresh check job prints only its header, and a job that skips the load fails with `Unable to find image … locally` and `pull access denied for cheese-app-api, repository does not exist or may require 'docker login'`, exit 125 (`runner/noload/`). That is why every downstream job has `Download Docker image` + `Load Docker image` steps (`ci.yml:49-57`, `78-86`, `113-121`, `136-144`).

### 3.3 Build once, test the same bits (artifact + SHA tag)
- **Explanation:** The `build` job runs `docker build -t cheese-app-api:${{ github.sha }} .`, then `docker save` writes the image to a tar file, and `actions/upload-artifact@v4` stores it in GitHub (`ci.yml:25-38`). Each test job downloads the tar, runs `docker load`, and then runs the *same* image by the same tag. Tagging with the commit SHA makes the tag unique to that commit.
- **Mental model:** The image is a sealed, labelled suitcase. Every inspector opens an identical copy, so a pass in one job and a pass in another are statements about the *same* thing.
- **Analogy:** A factory makes a single prototype and ships identical copies of that finished prototype (not the blueprint) to four independent QA labs, so no lab rebuilds it. The blueprint is the Dockerfile; the prototype is the built image.
- **Misconception:** "CI checks the files I checked out." Here, lint and tests run **inside the image** against `/app/api` and `/app/tests`, which were copied in at build time (Dockerfile:38-41). The `actions/checkout` steps in the lint, integration and system jobs are not used by the checks themselves.
- **Second misconception:** "Docker Buildx gives us caching." Nothing caches between runs: the plain `docker build` runs on the default builder (the captured build log's first line is `building with "default" instance using docker driver`), there are no `cache-from`/`cache-to` settings, and each run rebuilds from scratch, including `apt-get upgrade` (Dockerfile:12-20). Exercise B6 (§8) shows the change that would cache.

### 3.4 The job graph: `needs`, fan-out/fan-in, result propagation, `if: always()`
- **Explanation:**
  - With no `needs`, jobs start in parallel.
  - `needs: build` makes the four check jobs wait for `build` (`ci.yml:44, 73, 108, 131`). This is the fan-out.
  - `test-summary` has `needs: [unit-tests, integration-tests, system-tests]` (`ci.yml:175`). This is the fan-in.
  - Normally, a job whose dependency failed is *skipped*. `if: always()` (`ci.yml:176`) makes `test-summary` run anyway, so it can read `needs.<job>.result`, which is one of `success`, `failure`, `cancelled` or `skipped`.
  - The same idea applies to steps: a step is skipped after an earlier step fails, unless it says `if: always()` (`ci.yml:102, 161, 166`).
- **Mental model:** A directed acyclic graph (DAG). Time flows left to right, and the longest path (`build` 54 s → `system-tests` 39 s → `test-summary` 4 s in the screenshot) sets the run time.
- **Analogy:** A relay race with one runner handing off to four runners at once, and a judge at the finish who reads all four stopwatches even if some runners fell.
- **Misconception:** "`if: always()` means it will pass." It only means it will *run*. The summary step then decides pass or fail itself (`ci.yml:185-188`).
- **Second misconception:** "The summary covers everything." `lint-and-format` is **not** in the `needs` list, so a Black failure never reaches the summary or Slack. Captured in run 1: a red run whose summary prints `✅ All tests passed!`.

### 3.5 Exit codes are the only language CI understands (formatter vs linter, `continue-on-error`)
- **Explanation:** A step fails if and only if its command exits with a non-zero code. A failed step fails the job, which fails the run.
  - `black --check` exits 1 if any file *would be reformatted*. It is a formatter: it rewrites layout deterministically.
  - `flake8` exits 1 on style or quality violations. It is a linter: it reports, but does not fix.
  - The workflow makes Black **blocking** (`continue-on-error: false`, `ci.yml:62`) and Flake8 **advisory** (`continue-on-error: true`, `ci.yml:67`). An advisory step can fail while its job stays green.
- **Mental model:** Each step is a gate that emits 0 (open) or non-zero (closed). Red propagates upward from step to job to run.
- **Analogy:** A spell-checker that auto-corrects (Black) versus a proofreader's margin notes (Flake8).
- **Misconception:** "The lint job ran Flake8 and only Black complained." If Black fails, the Flake8 step is **skipped** (it has no `if: always()`), so on a messy commit you never see Flake8's output in CI.

### 3.6 Test altitudes in CI: unit, integration, system (and "skip is not pass")
- **Explanation:**
  - *Unit* tests (`tests/unit/test_utils.py`) call `power()` directly.
  - *Integration* tests (`tests/integration/test_api.py:9-11`) call the FastAPI app in-process through `TestClient`, with no server and no network.
  - *System* tests (`tests/system/test_system_api.py`) make real HTTP calls to `http://localhost:9000`. CI starts the server container with `-p 9000:9000`, waits `sleep 10`, checks it with `curl -f`, and then runs the tests from a *second* container that shares the runner's network via `--network host` (`ci.yml:146-158`).
  - The system test class is decorated with `skipif(not is_api_running())` (`test_system_api.py:24`). If the server is unreachable, the four HTTP tests are **skipped**, and pytest still exits 0.
- **Mental model:** Each level up the pyramid swaps a fake for something real: a function call, then an in-process ASGI call, then a TCP connection to a separate process.
- **Analogy:** Testing a car's spark plug on a bench (unit), the engine on a stand (integration), and driving the car around the block (system).
- **Misconception:** "Green means the system tests ran." Without the `curl -f … || exit 1` guard (`ci.yml:154`), a server that never started would produce "1 passed, 4 skipped" and a green job.

### 3.7 Passing information around: step outputs, job results, job summaries
- **Explanation:**
  - A step writes `key=value` lines to the file named by `$GITHUB_OUTPUT` (`ci.yml:187, 191, 198, 200`). Later steps read them as `steps.<id>.outputs.<key>` (`ci.yml:204, 209`).
  - Jobs read other jobs' outcomes through `needs.<job>.result` (`ci.yml:181-185`).
  - What the code does **not** use is GitHub's *job summary* feature: Markdown appended to `$GITHUB_STEP_SUMMARY` shows up on the run's summary page. The "Test Summary" here is a *job*, and its report lives only in the job log (`echo` lines).
- **Mental model:** Steps pass sticky notes to later steps of the same job, jobs pass report cards to the jobs that `need` them, and `$GITHUB_STEP_SUMMARY` is the bulletin board on the run's front page.
- **Misconception:** "`echo` output appears on the run summary page." It appears only in the log. Exercise B2 (§8) adds a real job summary.

### 3.8 Secrets in Actions
- **Explanation:**
  - Repository secrets are stored encrypted, injected only at run time via `${{ secrets.NAME }}`, and **masked** as `***` in logs.
  - They are **not** given to workflows triggered by PRs from forks.
  - They cannot be referenced directly in `if:` conditions. The repo's own history shows this: commit `199abd9` tried `if: always() && secrets.SLACK_WEBHOOK_URL != ''`, and commit `1a5e363` replaced it with a separate step that tests the secret in shell and exports `enabled=true/false` (`ci.yml:194-201`) for the Slack step's `if:` (`ci.yml:204`).
- **Mental model:** A vault that lends a key to a specific job for its lifetime and blacks it out on every log page.
- **Analogy:** A hotel safe: the job can open it while checked in, and visitors (fork PRs) cannot.
- **Misconception:** "Masked means safe to interpolate anywhere." `${{ secrets.X }}` is pasted into the script text before bash runs. The more robust pattern passes it through `env:` and tests `"$SLACK_WEBHOOK_URL"` in shell.
- **Related bug:** the step at `ci.yml:194-201` has no `if: always()`, so it is skipped when tests fail. As a result, the "❌ CI Pipeline Failed" Slack message can never be sent (see §6, G8; captured on the class demo commit, §4 Step 11).

---

## 4. Step-by-step walkthrough

Paths are relative to the repo root `cheese-app-ci-cd/`. Commands in fenced blocks are verbatim from the README unless labelled **(not in README)**.

**About the outputs below.** Outputs labelled *captured* are real, trimmed with `…`, from the 2026-11-06 captures in the video folder's `assets/terminal/` (the file is named with each block; `[exit N]` lines are kept only where the exit code matters). `laptop/` is the student machine; `runner/run1/<job>/` is that job of run 1 on its own fresh stand-in runner, which ran the workflow's own `run:` scripts (§ *Versions and sources*, above). The hosted GitHub pages (the Actions tab, the run graph, Slack, Settings) could not be captured: what they show is labelled *expected* (from `ci.yml` and GitHub's documented behaviour) or *recorded* (the README's screenshot). Hashes, times and sizes will differ for you; versions may be newer.

### Step 0 — Put the repo somewhere Actions can run it (not in README)
- **Action:** fork `dlops-io/cheese-app-ci-cd`, or create an empty GitHub repo and point a fresh clone's `origin` at it. If you fork, open the **Actions** tab once and enable workflows.
- *Captured* (`laptop/01`, `02`, `03`, `04`, `13`; the PR refs trimmed):
  ```
  $ git ls-remote https://github.com/dlops-io/cheese-app-ci-cd.git
  b8458ff0cc1898700b32a873b4665f43f50df71e	HEAD
  b8458ff0cc1898700b32a873b4665f43f50df71e	refs/heads/main
  …
  $ git clone https://github.com/dlops-io/cheese-app-ci-cd.git
  Cloning into 'cheese-app-ci-cd'...
  $ git log -3 --format='%h %ci %s'
  b8458ff 2025-11-13 13:59:04 -0500 demo class 1
  c3b227f 2025-11-13 13:44:07 -0500 demo class 1
  1a5e363 2025-11-13 11:05:41 +0530 update ci.yml - add slack
  $ ls -la .github/workflows/
  …
  -rw-r--r--    1 student  student       8159 Nov  6 19:10 ci.yml
  $ git remote -v
  origin	https://github.com/dlops-io/cheese-app-ci-cd.git (fetch)
  origin	https://github.com/dlops-io/cheese-app-ci-cd.git (push)
  ```
- **Under the hood:** GitHub scans `.github/workflows/*.yml` at the repo root on every event. `origin` is the course's repo, which you cannot write to, so the README's `git push` (Step 12) needs `origin` to point at your own repo first. Route B: `git remote set-url origin https://github.com/<you>/cheese-app-ci-cd.git`. (In the captures a bare repository on the same machine stood in for yours: `laptop/20`, `21`.)
- **Checkpoint:** after the first push, the Actions tab lists a workflow called **CI Pipeline** (`ci.yml:5`).
- **If it fails:** no workflow listed means the file is not at the repo root (monorepo case, §6 G2), or Actions is disabled on the fork or in Settings → Actions.

*Steps 1-4 are Parts 1-4 of the README, followed live in L09 (its [study guide](L09-ci-testing-precommit.md) has the captured outputs). They are summarised here because Part 5 builds on them; skip to Step 5 if you did L09.*

### Step 1 — Part 1: run the API locally (README.md:67-92, context)
```bash
sh docker-shell.sh
```
- **Under the hood:** `docker-shell.sh:7-18` builds an image named `cheese-app-api-service` and runs it interactively with `-p 9000:9000`. Passing `/bin/bash` as an argument makes the entrypoint `exec` a shell (`docker-entrypoint.sh:10-13`) after it puts `/home/app/.local/bin` on `PATH` (`docker-entrypoint.sh:5`).
- Inside the container:
```bash
uvicorn api.service:app --host 0.0.0.0 --port 9000 --reload
```
- **Checkpoint:**
  - `http://localhost:9000` → `{"message":"Welcome to the Cheese App CI/CD Tutorial!"}` (service.py:28-30)
  - `/health` → `{"status":"healthy"}` (service.py:33-35)
  - `/euclidean_distance/?x=3&y=4` → `distance` 5.0, plus a `"message"` field (service.py:38-50)
- **If it fails:**
  - "port is already allocated" means another container is still running, often the `cheese-app-v2`/`v3` api-service, which also uses port 9000 and **the same image and container name** `cheese-app-api-service`. Stop it.
  - `--reload` does nothing useful here: the code is baked into the image and no volume is mounted, so after editing `src/` you must rerun `sh docker-shell.sh`.
- **Before Part 2:** the README says "Please exit and remove your container after this, before starting with the next Part" (README.md:92). Type `exit`. `docker-shell.sh` runs the container with `--rm` (`docker-shell.sh:15`), so exiting removes it and frees port 9000.

### Step 2 — Part 2: see the lint and format problems (README.md:95-128, context)
```bash
# Build the image first
docker build -t cheese-app-api:local .

# Check code quality
docker run --rm cheese-app-api:local flake8 --max-line-length=120 api/

# Check formatting with diff
docker run --rm cheese-app-api:local black --check --diff api/
```
- **Under the hood:**
  - The Dockerfile copies `pyproject.toml` first and runs `pip install --user .`. This installs every dependency, including black, flake8, pytest and pre-commit, into the image (Dockerfile:32-35; pyproject.toml:7-19).
  - It then copies `src/api-service/api/` to `/app/api` and `tests/` to `/app/tests` (Dockerfile:38-41).
  - Any arguments after the image name replace the default server command (`docker-entrypoint.sh:10-13`).
- **Checkpoint:** after the entrypoint banner lines `Container is running!!!` and `Executing command: …`, Flake8 prints (the same two lines CI's Flake8 command printed on the captured runner, flake8 7.5.0: `runner/run1/lint-and-format/x4`):
  ```
  api/utils.py:7:15: E231 missing whitespace after ','
  api/utils.py:13:1: E303 too many blank lines (3)
  ```
  `black --check --diff api/` uses Black's **default 88-column** limit here. It reports *two* files: `utils.py` (`def power(base,exponent):` and an extra blank line) and `service.py`, because line 15 is 95 characters long. CI uses 120 columns and flags only `utils.py`.
- **README vs code:**
  - Option B's local commands `flake8 src/api-service/api/` and `black --check --diff src/api-service/api/` (README.md:121, 124) use the defaults of 79 and 88 columns, so they also flag `service.py:15:80: E501 line too long (95 > 79 characters)`. CI never flags that line.
  - Neither `pyproject.toml` nor a `.flake8` file sets these limits; only the command lines do.

### Step 3 — Part 3: run tests in Docker (README.md:159-228, context from L9)
```bash
# Run unit tests only
docker run --rm cheese-app-api:local pytest tests/unit/ -v

# Run integration tests only
docker run --rm cheese-app-api:local pytest tests/integration/ -v
```
- **Under the hood:** `pytest.ini:9` sets `pythonpath = .`, which is `/app` in the image, so `from api.utils import power` works. `addopts` adds `-v --tb=short --strict-markers --disable-warnings -ra` (pytest.ini:12-17).
- **Checkpoint:** 11 unit tests (`tests/unit/test_utils.py`) and 10 integration tests (`tests/integration/test_api.py`) collected and passing (captured in CI on the stand-in runner: `11 passed`, `10 passed, 1 warning`; §4 Steps 8-9).
- The same README block also runs both folders together (README.md:178) and a terminal coverage report (README.md:181):
```bash
# Run both unit and integration tests
docker run --rm cheese-app-api:local pytest tests/unit/ tests/integration/ -v

# Run with coverage
docker run --rm cheese-app-api:local pytest tests/unit/ --cov=api --cov-report=term
```
  The coverage table lists `service.py` at 0%, because `--cov=api` covers the whole package and unit tests never import `service.py` (§8 B4).
- System tests need a live server:
```bash
# Start the API server
docker run -d --name api-server -p 9000:9000 -e DEV=1 cheese-app-api:local

# Run system tests against the live server
docker run --rm --network host cheese-app-api:local pytest tests/system/ -v

# Clean up when done
docker stop api-server && docker rm api-server
```
- **Checkpoint:** 5 passed. If you instead see `1 passed, 4 skipped` with the reason `API not running at localhost:9000`, the test container could not reach the server (test_system_api.py:15-24).
- **If it fails:**
  - On Docker Desktop, host networking behaves differently from Linux. A robust local alternative **(not in README)**: `docker run --rm --network container:api-server cheese-app-api:local pytest tests/system/ -v`, which joins the server container's own network namespace, so `localhost:9000` *is* the server.
  - "Conflict. The container name "/api-server" is already in use" means a previous run never cleaned up. Run `docker rm -f api-server` **(not in README)**.
- **Option 3 (README.md:204-228):** the same `pytest` commands typed inside `sh docker-shell.sh`. `pytest tests/unit/ --cov=api --cov-report=html` (README.md:225) writes `htmlcov/` *inside* the `--rm` container, so the report is gone when you exit.

### Step 4 — Part 4: pre-commit (README.md:232-273, context)
```bash
pip install pre-commit
```
```bash
# From the root directory
pre-commit install
```
```bash
# Run on all files
pre-commit run --all-files
```
- The README also shows the two other ways the hooks run (README.md:253-266): automatically on `git commit -m "Your commit message"`, or manually on staged files only with `pre-commit run`.
- **Under the hood:** `.pre-commit-config.yaml` pins the following:
  - generic hooks at `v4.5.0` (lines 9-26)
  - Black `24.1.1` with `--line-length 120` on `^src/.*\.py$` (lines 29-35)
  - Flake8 `7.0.0` with `--max-line-length=120 --extend-ignore=E203,W503` (lines 38-44)

  These are the same flags CI uses (`ci.yml:61, 66`).
- **Checkpoint:** the Black hook reports *Failed* with "files were modified by this hook" and rewrites `src/api-service/api/utils.py`. Run the hooks again and everything passes.
- **To watch CI catch the problem first** (Steps 7 and 13), **don't commit that fix yet**. Run `git stash` or `git checkout -- src/api-service/api/utils.py` **(not in README)** to undo the rewrite.

### Step 5 — Part 5: read the trigger block (README.md:281-283)
- **File:** `.github/workflows/ci.yml:5-11`. The run is called "CI Pipeline". It fires on `push` to `main` or `develop`, and on `pull_request` whose *base* is `main` or `develop`.
- **Under the hood:**
  - A push to `feature/x` triggers nothing until you open a PR into `main`.
  - For `pull_request` runs, `github.sha` is the SHA of a temporary **merge commit** (your PR merged into the base). That merged code is what gets built and tested (lecture slide 23: each merge is tested).
  - A `push` run starts **after** GitHub has accepted the push. It reports; it cannot refuse the push (Step 17).
- *Captured* (`laptop/61`, extra): act reads the same file and prints the job graph in stages.
  ```
  $ act -l
  …
  Stage  Job ID             Job name               Workflow name  Workflow file  Events
  0      build              Build Docker Image     CI Pipeline    ci.yml         push,pull_request
  1      integration-tests  Integration Tests      CI Pipeline    ci.yml         push,pull_request
  1      system-tests       System Tests           CI Pipeline    ci.yml         push,pull_request
  1      lint-and-format    Lint and Format Check  CI Pipeline    ci.yml         push,pull_request
  1      unit-tests         Unit Tests             CI Pipeline    ci.yml         pull_request,push
  2      test-summary       Test Summary           CI Pipeline    ci.yml         push,pull_request
  ```
- **README vs code:** the README (283) correctly says `main` and `develop`, while the comment at `ci.yml:2` says only "main branch".

*Steps 6-11 read the six jobs in README order. Their outputs are from **run 1**, the run started by the push in Step 12, at commit `b8458ff`.*

### Step 6 — The `build` job (README.md:289-294; ci.yml:15-38)
- **What it does:**
  - checkout (`ci.yml:19-20`)
  - `docker/setup-buildx-action@v3` (`22-23`)
  - `docker build -t cheese-app-api:${{ github.sha }} .` (`25-27`)
  - `docker save … -o /tmp/cheese-app-api.tar` (`29-31`)
  - upload as artifact `docker-image` with `retention-days: 1` (`33-38`)
- *Captured* (`runner/run1/build/03`, `05`, `x1`; the build log reduced to its first and last lines):
  ```
  $ docker build -t cheese-app-api:b8458ff0cc1898700b32a873b4665f43f50df71e .
  #0 building with "default" instance using docker driver
  …
  #16 naming to docker.io/library/cheese-app-api:b8458ff0cc1898700b32a873b4665f43f50df71e done
  …
  #16 DONE 19.8s
  $ ls -l /tmp/cheese-app-api.tar                     (stand-in for the upload step)
  -rw-------    1 root     root     176112128 Nov  6 19:34 /tmp/cheese-app-api.tar
  $ docker images
  IMAGE                                                     ID             DISK USAGE   CONTENT SIZE   EXTRA
  cheese-app-api:b8458ff0cc1898700b32a873b4665f43f50df71e   919f25bfbf08        721MB          176MB
  ```
  The tar is about 176 MB; act's real `upload-artifact` reported `Final size is 174794992 bytes` (`laptop/62`). The build also prints `BuildBackendWarning: File '/app/README.md' cannot be found` during `pip install --user .` (`laptop/50`): harmless, `README.md` is not copied before that layer.
- **Checkpoint (in the run log):** the Docker build ends with `naming to … cheese-app-api:<sha>`, and the artifact `docker-image` is listed on the run page. The README screenshot shows this job at 54 s (*recorded*).
- **If it fails:** `pip install` errors usually mean a dependency problem in `pyproject.toml`. Network flakiness during `apt-get upgrade` (Dockerfile:12-20) can be fixed by re-running the job.
- **README vs code:** "Uses Docker Buildx for efficient caching" (README.md:291). The first line of the build log says `building with "default" instance using docker driver`: the plain `docker build` does not use the builder that `setup-buildx-action` creates (act's log shows that action creating a `docker-container` builder, then the build running on `docker:default`), and no cache is imported or exported, so every run rebuilds every layer, `apt-get upgrade` included.

### Step 7 — The `lint-and-format` job (README.md:296-301; ci.yml:41-67)
- **What it does:** `needs: build`, downloads and loads the tar (`49-57`), then runs:
  - `black --check --line-length 120 api/`, blocking (`59-62`)
  - `flake8 --max-line-length=120 --extend-ignore=E203,W503 api/`, advisory (`64-67`)
- *Captured* (`runner/run1/lint-and-format/x1`, `03`, `04`, `00`): the fresh machine starts with no images; after the load, Black fails and Flake8 is skipped.
  ```
  $ docker images
  IMAGE   ID             DISK USAGE   CONTENT SIZE   EXTRA
  $ docker load -i /tmp/cheese-app-api.tar
  Loaded image: cheese-app-api:b8458ff0cc1898700b32a873b4665f43f50df71e
  $ docker run --rm cheese-app-api:b8458ff0cc1898700b32a873b4665f43f50df71e black --check --line-length 120 api/
  Container is running!!!
  Executing command: black --check --line-length 120 api/
  would reformat /app/api/utils.py

  Oh no! 💥 💔 💥
  1 file would be reformatted, 2 files would be left unchanged.
  [exit 1]

  job: lint-and-format (name: Lint and Format Check)
  01  success   Checkout code
  02  success   Download Docker image
  03  success   Load Docker image
  04  failure   Run Black formatter check
  05  skipped   Run Flake8 linter
  job result: failure
  ```
- **What the skipped Flake8 step would have printed** (*captured* as an extra, `runner/run1/lint-and-format/x4`):
  ```
  api/utils.py:7:15: E231 missing whitespace after ','
  api/utils.py:13:1: E303 too many blank lines (3)
  [exit 1]
  ```
- **Why:** `src/api-service/api/utils.py:7` (`def power(base,exponent):`) and the three blank lines at `utils.py:10-12`. Black 120 does not flag `service.py`; the default 88 columns of Part 2 would.

### Step 8 — The `unit-tests` job (README.md:303-308; ci.yml:70-102)
- **What it does:**
  - `pytest tests/unit/ -v --tb=short` (`88-90`). This is the gate.
  - A second, advisory pytest run with coverage, which mounts `${{ github.workspace }}/coverage` onto `/app/coverage` and writes the HTML report there (`92-95`).
  - Uploads `coverage/` as artifact `coverage-report-unit`, even after failures (`97-102`).
- *Captured* (`runner/run1/unit-tests/04`, `05`, `x3`, `06`, `00`):
  ```
  $ docker run --rm cheese-app-api:b8458ff… pytest tests/unit/ -v --tb=short
  …
  collecting ... collected 11 items
  tests/unit/test_utils.py::TestPower::test_power_positive_integers PASSED [  9%]
  …
  ============================== 11 passed in 0.04s ==============================

  $ docker run --rm -v /home/runner/work/cheese-app-ci-cd/cheese-app-ci-cd/coverage:/app/coverage cheese-app-api:b8458ff… pytest tests/unit/ --cov=api --cov-report=term --cov-report=xml --cov-report=html:coverage
  …
  INTERNALERROR> PermissionError: [Errno 13] Permission denied: 'coverage/style_cb_4667309f.css'
  ============================== 11 passed in 0.13s ==============================
  [exit 3]

  $ ls -la coverage/ && docker run --rm cheese-app-api:b8458ff… id
  drwxr-xr-x    2 root     root          4096 Nov  6 19:34 .
  …
  uid=1000(app) gid=1000(app) groups=1000(app)
  $ find coverage/ -type f | wc -l                    (what the upload step would find)
  0

  05  failure   Generate coverage report   (continue-on-error: the job stays green)
  06  success   Upload coverage report
  job result: success
  ```
  act's real upload step printed `::warning::No files were found with the provided path: coverage/. No artifacts will be uploaded.` (`laptop/62`).
- **Checkpoint:** `11 passed`, a green job, and (as written) a coverage step that failed quietly.
- **README vs code:** README.md:307-308 promises terminal, XML and HTML reports, all uploaded.
  - Docker creates the missing host folder `coverage/` as root, while the container runs as uid 1000 (Dockerfile:23-28), so the HTML write fails; `continue-on-error: true` (`ci.yml:95`) hides it, and the artifact is empty.
  - The XML report goes to `/app/coverage.xml` *inside* the container, outside the mount, and `--rm` deletes it.
  - Fix (§8 B3): `mkdir -p coverage && chmod 777 coverage` before the `docker run`, and `--cov-report=xml:coverage/coverage.xml --cov-report=html:coverage/html`.

### Step 9 — The `integration-tests` job (README.md:310-314; ci.yml:105-125)
- **What it does:** `pytest tests/integration/ -v --tb=short` (`123-125`) runs inside the image. `TestClient(app)` (test_api.py:11) calls the ASGI app in-process, so no port is involved.
- *Captured* (`runner/run1/integration-tests/04`):
  ```
  collecting ... collected 10 items
  tests/integration/test_api.py::TestAPIEndpoints::test_root_endpoint PASSED [ 10%]
  …
  tests/integration/test_api.py::test_api_health_check PASSED              [100%]
  ======================== 10 passed, 1 warning in 0.35s =========================
  ```

### Step 10 — The `system-tests` job (README.md:316-323; ci.yml:128-169)
- **What it does:**
  - Starts `api-server` detached in DEV mode. With no command arguments, the entrypoint starts `uvicorn … --reload --log-level debug` (docker-entrypoint.sh:16-19).
  - `sleep 10`, then `curl -f http://localhost:9000/ || exit 1` (`150-154`).
  - Runs the tests from a second container with `--network host` (`156-158`).
  - Always prints the server logs and always stops and removes the server (`160-169`).
- *Captured* (`runner/run1/system-tests/05`, `06`, `07`; curl's progress meter and the client addresses in the server log trimmed):
  ```
  $ echo "Waiting for server to start..."
  > sleep 10
  > curl -f http://localhost:9000/ || exit 1
  Waiting for server to start...
  …
  {"message":"Welcome to the Cheese App CI/CD Tutorial!"}
  $ docker run --rm --network host cheese-app-api:b8458ff… pytest tests/system/ -v --tb=short
  …
  collecting ... collected 5 items
  tests/system/test_system_api.py::TestAPIEndpoints::test_root_endpoint PASSED [ 20%]
  …
  tests/system/test_system_api.py::TestAPIWithoutServer::test_api_structure PASSED [100%]
  ============================== 5 passed in 0.36s ===============================
  $ docker logs api-server
  Container is running!!!
  Running in DEV mode
  …
  INFO:     Uvicorn running on http://0.0.0.0:9000 (Press CTRL+C to quit)
  …
  INFO:     … - "GET /health HTTP/1.1" 200 OK
  INFO:     … - "GET /euclidean_distance/?x=3&y=4 HTTP/1.1" 200 OK
  ```
- **Checkpoint:** `5 passed`, all eight steps green.
- **If it fails:** a `curl: (7) Failed to connect` (or `(56) Recv failure`) in the wait step means the server needed more than 10 s or crashed. Read the logs step, which runs because of `if: always()`. A `1 passed, 4 skipped` result means the tests could not reach the server (`skipif`, test_system_api.py:24); in CI the `curl -f` gate stops that from passing silently.

### Step 11 — The `test-summary` job (README.md:325-330; ci.yml:172-257)
- **What it does:**
  - `needs` the three test jobs and runs `if: always()`.
  - Echoes the three results, writes `status=success|failure` to `$GITHUB_OUTPUT`, and exits 1 if any result is not `success` (`178-192`).
  - Checks whether the secret exists (`194-201`) and, if so, posts a Block-Kit message through `slackapi/slack-github-action@v1.26.0` (`203-257`).
- *Captured* (`runner/run1/test-summary/01`, `00`): in the same run whose lint job is red.
  ```
  Unit Tests: success
  Integration Tests: success
  System Tests: success
  ✅ All tests passed!

  01  success   Check test results
  02  success   Check if Slack webhook is configured
  03  skipped   Send Slack notification   (steps.slack-check.outputs.enabled is 'false')
  job result: success
  ```
- **The class demo** (*captured*, `runner/run-demo/`, extra): commit `c3b227f` (one below the pin) computed `math.sqrt(2 * z)`. Run on the same stand-in runners: Unit Tests ✓ (unit tests cover only `power()`), Integration Tests ✗ (`assert 7.0710678118654755 == 5.0`, `1 failed, 9 passed, 1 warning`), System Tests ✗ (`2 failed, 3 passed`), Lint ✗ (still `utils.py`), and the summary:
  ```
  Unit Tests: success
  Integration Tests: failure
  System Tests: failure
  ❌ Some tests failed!
  [exit 1]

  01  failure   Check test results
  02  skipped   Check if Slack webhook is configured
  03  skipped   Send Slack notification   (steps.slack-check.outputs.enabled is '')
  job result: failure
  ```
  The second step was skipped after the failure, so a "❌ CI Pipeline Failed" message could never be sent, even with the secret set (§6 G8).
- **README vs code:** the README (325-330) does not mention Slack at all, and "Checks the results of all test jobs" omits that lint is not checked.

### Step 12 — Push (README.md:344-349)
```bash
git add .
git commit -m "Add CI pipeline"
git push
```
- *Captured* (`laptop/10`, `11`, `22`; the push went to the stand-in for your repo after `git remote set-url`):
  ```
  $ git add .
  $ git commit -m "Add CI pipeline"
  On branch main
  Your branch is up to date with 'origin/main'.

  nothing to commit, working tree clean
  [exit 1]
  $ git push
  To /home/student/github-standin/student/cheese-app-ci-cd.git
   * [new branch]      main -> main
  ```
- **Under the hood:** in a clone or fork, `ci.yml` is already committed, so there is nothing to add or commit; the push of `main` (commit `b8458ff`) to a repo that does not have it yet is the `push` event that starts run 1. On GitHub you would see `To https://github.com/<you>/cheese-app-ci-cd.git` instead of the local path.
- **Checkpoint (expected):** within seconds, a yellow dot appears next to the commit on GitHub, and the Actions tab shows a run named after the commit's message ("demo class 1" here).
- **If nothing starts:**
  - You pushed a branch other than `main`/`develop`, or the workflow is not at the repo root.
  - On a fork, the push sends nothing (`Everything up-to-date`), so no event fires. The workflow has no manual trigger (`ci.yml:7-11` lists only `push` and `pull_request`): create a commit, for example `git commit --allow-empty -m "Trigger CI"`, or do Step 14's fix, and push again.
  - `permission denied` / 403: `origin` still points at `dlops-io` (Step 0).
- **Gotcha:** `git add .` also stages anything you generated locally that `.gitignore` misses. For example, a `coverage/` folder is not ignored; for coverage output, `.gitignore:29-35` covers only `.coverage`, `htmlcov/`, `*.cover` and `coverage.xml`.

### Step 13 — Watch the run (README.md:351-365)
- **Action:** Actions tab → the run → the graph view.
- **What you should see at commit `b8458ff`** (*captured* on the stand-in runners, `runner/run1/results.txt`, and again with act, `laptop/62`):
  ```
  build=success
  lint-and-format=failure
  unit-tests=success
  integration-tests=success
  system-tests=success
  test-summary=success
  ```
  act ends the same way: its Test Summary job prints `✅ All tests passed!`, and the run ends with `Error: Job 'Lint and Format Check' failed`, exit 1. On GitHub: five green nodes, a red **Lint and Format Check**, and a red run badge.
- *Recorded* (README screenshot `assets/pipline.png`, transcribed): all six green; Build Docker Image 54 s, Unit Tests 18 s, Integration Tests 20 s, System Tests 39 s, Lint and Format Check 22 s, Test Summary 4 s. That screenshot was committed in `3dea317`, when `utils.py` and `service.py` were already messy (since `91eb786`), so it shows another code state, consistent with the clean code before `91eb786` (`140f138`). After Step 14 your run matches it.
- **Checkpoint:** you can click into each job and read every step's log. The artifacts are listed at the bottom of the run summary page.
- **Ponder:** the run is red. Is your push on `main`? Yes: the run started *because* GitHub accepted it (Step 17).

### Step 14 — Turn it green (not spelled out in the README)
- **Option A:** run `pre-commit run --all-files` (README.md:262), then commit the rewritten `utils.py` and push. *Captured* (`laptop/32`, `33`, `34`, `36`, `37`; the environment set-up lines of the first run trimmed):
  ```
  $ pre-commit run --all-files
  …
  Trim trailing whitespace.................................................Passed
  …
  Detect private keys......................................................Passed
  Format Python code with Black............................................Failed
  - hook id: black
  - files were modified by this hook

  reformatted src/api-service/api/utils.py

  All done! ✨ 🍰 ✨
  1 file reformatted, 2 files left unchanged.

  Check Python code with Flake8............................................Passed
  [exit 1]
  $ git diff
  …
  -def power(base,exponent):
  +def power(base, exponent):
  …
  -
   def unused_function():
  $ pre-commit run --all-files
  …
  Format Python code with Black............................................Passed
  Check Python code with Flake8............................................Passed
  [exit 0]
  $ git add .
  $ git commit -m "Format utils.py with Black"
  …
  [main 2289d89] Format utils.py with Black
   1 file changed, 1 insertion(+), 2 deletions(-)
  $ git push
  To /home/student/github-standin/student/cheese-app-ci-cd.git
     b8458ff..2289d89  main -> main
  ```
  The commit message is free; the README gives none for this step. Flake8 passes in the first hook run because it reads the copy Black has just rewritten.
- **Option B (not in README):** run Black inside the image, mounting only the `api` folder:
  ```bash
  docker run --rm -v "$(pwd)/src/api-service/api":/app/api cheese-app-api:local black --line-length 120 api/
  ```
  This needs the `cheese-app-api:local` image from Step 2. Black runs as uid 1000 inside the container and writes to your host files. On Docker Desktop (macOS) that works; on a Linux host whose user is not uid 1000 the write can fail with a permission error, so use Option A or C there.
- **Option C:** edit by hand. Change the signature to `def power(base, exponent):` and delete one of the three blank lines.
- **Checkpoint:** run 2 (*captured*, `runner/run2/`): all six jobs green; Black `All done! ✨ 🍰 ✨`, `3 files would be left unchanged.`, and Flake8 now runs and prints nothing (exit 0). This matches the screenshot.

### Step 15 — Skip the hooks, meet CI (not in README; lecture slides 29–31)
The lecture's "local conundrum": local hooks run only where someone ran `pre-commit install`, and `git commit --no-verify` skips them. *Captured* (`laptop/40`-`47`; diff context trimmed):
```
$ sed -i 's/z = power(x, 2) + power(y, 2)/z=power(x,2)+power(y,2)/' src/api-service/api/service.py && git diff
…
-    z = power(x, 2) + power(y, 2)
+    z=power(x,2)+power(y,2)
…
$ git add .
$ git commit -m "quick fix"
…
Format Python code with Black............................................Failed
- hook id: black
- files were modified by this hook

reformatted src/api-service/api/service.py
…
Check Python code with Flake8............................................Passed
[exit 1]
$ git status --short
MM src/api-service/api/service.py
$ git commit --no-verify -m "quick fix"
[main 2892b1b] quick fix
 1 file changed, 1 insertion(+), 1 deletion(-)
$ git push
To /home/student/github-standin/student/cheese-app-ci-cd.git
   2289d89..2892b1b  main -> main
```
- **Under the hood:** the hook stopped the commit and rewrote the file in your working tree (`MM`: staged messy copy, unstaged formatted copy); Flake8 passed because it read Black's rewrite. `--no-verify` committed the **staged**, messy copy without running any hook.
- **What CI did with it** (*captured*, `runner/run3/`): Lint and Format Check ✗, `would reformat /app/api/service.py`; everything else ✓, Test Summary `✅ All tests passed!`. The skipped Flake8 step would have printed `api/service.py:43:6: E225 missing whitespace around operator` and two `E231` on the same line (`runner/run3/lint-and-format/x4`).
- **What CI does not catch:** CI re-runs only Black and Flake8, on `api/`. The seven hygiene hooks (`.pre-commit-config.yaml:12-26`, `detect-private-key` among them) never run in CI, so a key file committed with `--no-verify` goes through (§8 Ponder 5).
- **Clean up:** `git restore src/api-service/api/service.py` drops the hook's uncommitted rewrite (`laptop/49`); to make `main` green again, fix the line, commit and push.

### Step 16 — (Optional) Slack notifications
1. Create a Slack app with Incoming Webhooks and copy the webhook URL (shape: `https://hooks.slack.com/services/<your-webhook-path>`).
2. In the repo, go to Settings → Secrets and variables → Actions → New repository secret, name it `SLACK_WEBHOOK_URL`, and paste the URL. Not Settings → Webhooks: a repository webhook is GitHub calling out (the lecture's slides 9–12); here your workflow calls Slack.
3. Push a new commit to `main` (or re-run the workflow).

- **Checkpoint (expected, not captured):** a Slack message headed "✅ CI Pipeline Passed", with repository, branch, commit, author, per-test results and links (`ci.yml:207-254`). The log prints the secret as `***`. Without the secret, "Check if Slack webhook is configured" writes `enabled=false` and the Slack step is skipped (*captured*, `runner/run1/test-summary/00`).
- **Known bug:** when tests fail, *no* message is sent (Step 11, §6 G8).
- **Known bug:** on PR runs, the "View Commit" link is empty, because `github.event.head_commit` exists only for push events. On the same runs the "Branch" field (`github.ref_name`, `ci.yml:227`) shows `<PR number>/merge` rather than your branch name.

### Step 17 — Part 6: branch protection (README.md:369-397), with fixes
- **Action:** Settings → Branches → add a rule for `main`, requiring a PR and passing status checks. GitHub's current UI labels this "Add classic branch protection rule" or offers "rulesets".
- **Why:** in the lecture's terms (slides 5–6), a push-triggered Actions run is a *post-receive* check: it reports after the push is in. Branch protection is GitHub.com's gate that refuses: it blocks the merge of a PR whose required checks fail, and direct pushes to `main`.
- **Choosing the checks:** the README says to select `lint-and-format`, `unit-tests`, … (README.md:378). Those are job **IDs**. The status checks GitHub lists use each job's **`name:`**:
  - `Lint and Format Check` (`ci.yml:42`)
  - `Unit Tests` (`71`)
  - `Integration Tests` (`106`)
  - `System Tests` (`129`)

  Checks appear in the picker only after they have run at least once.
- **Do Step 14 first.** If `Lint and Format Check` is required while `utils.py` is still messy, every PR is blocked by Black regardless of what the PR changes.
- **Plan limits:** protected branches on **private** repos need a paid plan (Pro, Team, …). On GitHub Free they are available for public repos.
- **The README's "break the tests" command doesn't break anything:**
```bash
echo "def broken(): assert False" >> tests/unit/test_utils.py
```
  *Captured* in the image (`laptop/51`-`53`): after a rebuild, `collected 11 items`, `11 passed`. `broken` does not match `python_functions = test_*` (pytest.ini:8), so pytest never collects it, and the PR stays green. Use **(not in README)** `echo "def test_broken(): assert False" >> tests/unit/test_utils.py`; *captured* (`laptop/55`-`57`):
  ```
  collecting ... collected 12 items
  …
  tests/unit/test_utils.py::test_broken FAILED                             [100%]
  …
  FAILED tests/unit/test_utils.py::test_broken - assert False
  ========================= 1 failed, 11 passed in 0.05s =========================
  [exit 1]
  ```
- **Also note:** pushing `feature/test-protection` triggers nothing (push filter). The run starts when you open the PR (`pull_request` into `main`). The protected-branch pages and the blocked merge were not captured here.

### Step 18 — Part 7: add `/add/` with tests (README.md:401-453)
- **Action:** add the endpoint snippet to `service.py` and the test function to `test_api.py` (README.md:405-419). Add `test_add_endpoint` at module level (it has no `self`), like `test_api_health_check`. Then rebuild, because code and tests are baked into the image, and run:
```bash
# Build the image first
docker build -t cheese-app-api:local .

# Run all tests
docker run --rm cheese-app-api:local pytest tests/ -v
```
- **Checkpoint:** all unit and integration tests pass, now including `test_add_endpoint`. The system tests show 1 passed and 4 skipped, because no server is running.
- **Then (README.md:445-453):** `git add .`, `git commit -m "Add addition endpoint with tests"`, `git push`, and watch the run.
- **README auto-format command is broken:**
```bash
docker run --rm -v $(pwd)/src/api-service:/app cheese-app-api:local black --line-length 120 api/
```
  It mounts `src/api-service` (which contains only `api/`) **over `/app`**. That hides `/app/docker-entrypoint.sh`, which the relative `ENTRYPOINT ["/bin/bash", "docker-entrypoint.sh"]` (Dockerfile:52) needs: `/bin/bash: docker-entrypoint.sh: No such file or directory`, exit 127 (checked for the exercises, `assets/exercise-checks/logs/image.log`). Use the Step 14 Option B command instead.

### Step 19 — Clean up (README.md:568-574)
- **Action:** `docker container ls`, stop leftovers (`api-server`, `cheese-app-api-service`), `docker system prune`, `docker image ls`.
- **Optional:** disable the workflow on GitHub if you don't want CI minutes used on a private repo. If you tried act, it also leaves a `moby/buildkit:buildx-stable-1` image behind (`laptop/63`).

---

## 5. Code tour

```
cheese-app-ci-cd/
├── .github/workflows/ci.yml        # THE lecture: 6-job CI pipeline (build → 4 checks → summary + Slack)
├── .pre-commit-config.yaml         # local mirror of CI's checks (Black/Flake8 @120 cols + hygiene hooks)
├── Dockerfile                      # python:3.11-slim image; non-root 'app'; bakes code + tests into /app
├── docker-entrypoint.sh            # args → exec them; no args → uvicorn (DEV=1: --reload, else 4 workers)
├── docker-shell.sh                 # local: build 'cheese-app-api-service' and open a bash shell, port 9000
├── pyproject.toml                  # unpinned deps: fastapi, uvicorn, pytest(+cov,+asyncio), black, flake8…
├── pytest.ini                      # testpaths, pythonpath=., default flags (-v --tb=short -ra …)
├── src/api-service/api/
│   ├── service.py                  # FastAPI app: /, /health, /euclidean_distance/
│   └── utils.py                    # power(); intentionally mis-formatted (makes Black fail)
├── tests/unit/test_utils.py        # 11 tests of power()
├── tests/integration/test_api.py   # 10 tests through TestClient (in-process)
├── tests/system/test_system_api.py # 5 tests; 4 hit http://localhost:9000 (skip if down)
└── assets/pipline.png              # screenshot of an all-green run graph
```

**`.github/workflows/ci.yml:5-11`**
```yaml
name: CI Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]
```
- `name` is the label you see in the Actions sidebar.
- `on.push.branches` filters by the branch you pushed **to**.
- `on.pull_request.branches` filters by the PR's **base** branch. The default PR activity types are opened, synchronize (new commits) and reopened.

**`.github/workflows/ci.yml:25-38`**
```yaml
      - name: Build Docker image
        run: |
          docker build -t cheese-app-api:${{ github.sha }} .

      - name: Save Docker image
        run: |
          docker save cheese-app-api:${{ github.sha }} -o /tmp/cheese-app-api.tar

      - name: Upload Docker image artifact
        uses: actions/upload-artifact@v4
        with:
          name: docker-image
          path: /tmp/cheese-app-api.tar
          retention-days: 1
```
- `${{ … }}` is an expression GitHub substitutes *before* the shell runs. `github.sha` is the 40-character commit (or merge-commit) SHA.
- `docker save` serialises all image layers and metadata into a single tar.
- `upload-artifact@v4` stores it under the run with the name `docker-image`. `retention-days: 1` keeps storage low, but it also means that re-running a single failed job more than a day later cannot download the image (§6 G13).

**`.github/workflows/ci.yml:43-57`**
```yaml
    runs-on: ubuntu-latest
    needs: build
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Download Docker image
        uses: actions/download-artifact@v4
        with:
          name: docker-image
          path: /tmp

      - name: Load Docker image
        run: |
          docker load -i /tmp/cheese-app-api.tar
```
- `needs: build` means: wait for `build`, and skip this job if `build` failed.
- `download-artifact@v4` with a `name` extracts the files straight into `path`, so `/tmp/cheese-app-api.tar` reappears on this VM.
- `docker load` restores the image with its original tag, `cheese-app-api:<sha>`.
- This same 15-line block is copy-pasted into four jobs. That is a natural candidate for a composite action or a reusable workflow later.

**`.github/workflows/ci.yml:59-67`**
```yaml
      - name: Run Black formatter check
        run: |
          docker run --rm cheese-app-api:${{ github.sha }} black --check --line-length 120 api/
        continue-on-error: false

      - name: Run Flake8 linter
        run: |
          docker run --rm cheese-app-api:${{ github.sha }} flake8 --max-line-length=120 --extend-ignore=E203,W503 api/
        continue-on-error: true
```
- `api/` resolves to `/app/api`, the WORKDIR (Dockerfile:29), so the checks lint the image's copy of the code.
- `--check` makes Black report instead of rewrite, exiting 1 if anything would change.
- `E203` (whitespace before `:`, e.g. in slices) and `W503` (line break before a binary operator) are the classic pycodestyle rules that conflict with Black's style. `W503` is already in Flake8's default ignore list, and `--extend-ignore` keeps that list, so in practice only `E203` changes anything here.
- `continue-on-error: false` is the default, written out for teaching. `true` lets Flake8 fail without failing the job, though Flake8 only runs at all if Black passed.

**`.github/workflows/ci.yml:88-102`**
```yaml
      - name: Run unit tests
        run: |
          docker run --rm cheese-app-api:${{ github.sha }} pytest tests/unit/ -v --tb=short

      - name: Generate coverage report
        run: |
          docker run --rm -v ${{ github.workspace }}/coverage:/app/coverage cheese-app-api:${{ github.sha }} pytest tests/unit/ --cov=api --cov-report=term --cov-report=xml --cov-report=html:coverage
        continue-on-error: true

      - name: Upload coverage report
        uses: actions/upload-artifact@v4
        with:
          name: coverage-report-unit
          path: coverage/
        if: always()
```
- The first step is the real gate.
- The second step runs the unit tests **again**, now measuring `api` with pytest-cov:
  - `term` prints a table.
  - `xml` writes `/app/coverage.xml`, which is not mounted and therefore lost.
  - `html:coverage` writes into the bind-mounted folder, which Docker created as root; on a Linux runner the uid-1000 container cannot write there (`PermissionError`, exit 3, §4 Step 8).
- Because `--cov=api` points at the package directory, coverage also lists files the unit tests never import (`service.py` at 0%).
- `if: always()` uploads even after a failure, which is good practice for diagnostics.

**`.github/workflows/ci.yml:146-158`**
```yaml
      - name: Start API server container
        run: |
          docker run -d --name api-server -p 9000:9000 -e DEV=1 cheese-app-api:${{ github.sha }}

      - name: Wait for server to be ready
        run: |
          echo "Waiting for server to start..."
          sleep 10
          curl -f http://localhost:9000/ || exit 1

      - name: Run system tests
        run: |
          docker run --rm --network host cheese-app-api:${{ github.sha }} pytest tests/system/ -v --tb=short
```
- `-d` detaches.
- `-p 9000:9000` publishes the container port on the runner's port 9000.
- `-e DEV=1` selects the `--reload` branch of the entrypoint.
- `curl -f` turns an HTTP error or connection failure into a non-zero exit, so the readiness check is a *gate*. `sleep 10` is a fixed guess; a retry loop is more robust (Exercise B5).
- `--network host` puts the test container in the runner's network namespace, so `localhost:9000` reaches the published port.

**`.github/workflows/ci.yml:174-187`**
```yaml
    runs-on: ubuntu-latest
    needs: [unit-tests, integration-tests, system-tests]
    if: always()
    steps:
      - name: Check test results
        id: test-results
        run: |
          echo "Unit Tests: ${{ needs.unit-tests.result }}"
          echo "Integration Tests: ${{ needs.integration-tests.result }}"
          echo "System Tests: ${{ needs.system-tests.result }}"

          if [ "${{ needs.unit-tests.result }}" != "success" ] || [ "${{ needs.integration-tests.result }}" != "success" ] || [ "${{ needs.system-tests.result }}" != "success" ]; then
            echo "❌ Some tests failed!"
            echo "status=failure" >> $GITHUB_OUTPUT
```
- The fan-in job. `if: always()` makes it run even when a dependency failed or was skipped. If `build` fails, all three are `skipped`, which is "not success", so the summary also fails.
- `id: test-results` names the step so later steps can read `steps.test-results.outputs.status`.
- `echo "key=value" >> $GITHUB_OUTPUT` is the current way to set a step output; the old `::set-output` command is deprecated.
- The step finishes with `exit 1` (line 188), which fails the job and makes it visibly red.
- `lint-and-format` is absent from `needs`, so formatting failures are invisible to this job.

**`.github/workflows/ci.yml:194-205`**
```yaml
      - name: Check if Slack webhook is configured
        id: slack-check
        run: |
          if [ -n "${{ secrets.SLACK_WEBHOOK_URL }}" ]; then
            echo "enabled=true" >> $GITHUB_OUTPUT
          else
            echo "enabled=false" >> $GITHUB_OUTPUT
          fi

      - name: Send Slack notification
        if: always() && steps.slack-check.outputs.enabled == 'true'
        uses: slackapi/slack-github-action@v1.26.0
```
- `if:` cannot read `secrets` directly, so this step converts "secret present?" into an ordinary step output.
- An unset secret expands to the empty string, which makes `-n` false.
- **Bug:** this check step has no `if: always()`. When the previous step exits 1, it is skipped, its output is empty, and the Slack step's condition is false, so failures are never announced.
- The action version `v1.26.0` uses the `SLACK_WEBHOOK_URL`/`SLACK_WEBHOOK_TYPE` env interface (`ci.yml:255-257`). Newer major versions changed their inputs.

**`Dockerfile:27-41`**
```dockerfile
# Switch to non-root user
USER app
WORKDIR /app

# Copy pyproject.toml first for better caching
COPY --chown=app:app pyproject.toml ./

# Install Python dependencies
RUN pip install --no-cache-dir --user .

# Copy application code
COPY --chown=app:app src/api-service/api/ ./api/
COPY --chown=app:app tests/ ./tests/
COPY --chown=app:app pytest.ini ./
COPY --chown=app:app docker-entrypoint.sh ./
```
- The image runs as the non-root user `app` (uid 1000, Dockerfile:23).
- Copying `pyproject.toml` before the code means a code-only change reuses the dependency layer. This helps locally, but CI rebuilds from scratch every run anyway.
- `pip install --user .` puts console scripts in `/home/app/.local/bin`. That folder is not on PATH by default, which is why the entrypoint exports it (`docker-entrypoint.sh:5`).
- Tests are **baked into the image**. That is why CI can run `pytest tests/...` with no mount.

**`docker-entrypoint.sh:10-24`**
```bash
if [ $# -gt 0 ]; then
  echo "Executing command: $@"
  exec "$@"
fi

# Otherwise, start the server
if [ "${DEV}" = "1" ]; then
  echo "Running in DEV mode"
  # Development: auto-reload on code changes
  uvicorn api.service:app --host 0.0.0.0 --port 9000 --reload --log-level debug
else
  echo "Running in PROD mode"
  # Production: optimized settings
  uvicorn api.service:app --host 0.0.0.0 --port 9000 --workers 4
fi
```
- This one script makes the same image serve every role in CI:
  - with arguments, it is a tool runner (`pytest …`, `black …`, `flake8 …`)
  - with no arguments, it is a server
- `exec` replaces bash, so the tool's exit code becomes the container's exit code, which becomes the step's exit code. That chain is exactly what CI needs.
- Note the different meaning of `DEV` compared with `cheese-app-v3`, where `DEV=1` drops you into a shell (§7).

**`tests/system/test_system_api.py:12-24`**
```python
API_BASE_URL = "http://localhost:9000"


def is_api_running():
    """Check if API is accessible"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=2)
        return response.status_code == 200
    except:
        return False


@pytest.mark.skipif(not is_api_running(), reason="API not running at localhost:9000")
```
- The URL is hard-coded.
- `is_api_running()` runs at **import or collection time**, once.
- The bare `except:` swallows every error, including DNS errors and timeouts.
- `skipif` turns "server down" into *skipped*, which pytest does not count as a failure. CI compensates with the `curl -f` gate.

**`src/api-service/api/utils.py:7-14`**
```python
def power(base,exponent):
    """Calculate base raised to the power of exponent"""
    return base**exponent



def unused_function():
    pass
```
- This is the deliberately messy code. It was re-added in commit `91eb786` ("readd messy code").
- Line 7 has a missing space after the comma (Flake8 E231, a Black rewrite). Lines 10-12 hold three blank lines (Flake8 E303, a Black rewrite).
- `unused_function` is dead code that neither tool flags. Flake8 reports unused *imports*, not unused functions.
- This file alone makes the lint job red at HEAD.

---

## 6. Gotchas and common errors

| # | Symptom | Cause | Fix |
|---|---|---|---|
| G1 | First run is red. "Lint and Format Check" fails at "Run Black formatter check" with `would reformat …/api/utils.py`, and Flake8 shows as skipped. | `src/api-service/api/utils.py:7` and `:10-12` are intentionally not Black-formatted. Black is blocking (`ci.yml:62`). | Run `pre-commit run --all-files` (README.md:262) or the mount command in §4 Step 14, then commit and push. |
| G2 | You pushed and **no run appears**. | One of three things: (a) the workflow is not at the repo root, e.g. it sits in `MLOps_Learning/<subfolder>/.github/workflows/`; (b) you pushed a branch other than `main`/`develop` (`ci.yml:7-11`); (c) Actions is disabled on a fork. | (a) Move it to the root `.github/workflows/`. Add `defaults: run: working-directory: <subfolder>` so `docker build … .` uses the right context, and optionally `on.push.paths: ['<subfolder>/**']`. The `-v ${{ github.workspace }}/coverage` mount and the `path: coverage/` upload both resolve to the workspace root, so they stay consistent. (b) Push to `main` or open a PR. (c) Enable workflows on the Actions tab. |
| G2b | In the monorepo, `pre-commit` never reformats `utils.py`, or the commit hook says no config was found *(reasoned, not run)*. | pre-commit works from the **git root**: the installed hook looks for `.pre-commit-config.yaml` there, and the `files: ^src/.*\.py$` patterns (`.pre-commit-config.yaml:35, 44`) are matched against paths relative to the root, so `<subfolder>/src/...` never matches. | Put one `.pre-commit-config.yaml` at the monorepo root with patterns like `^<subfolder>/src/.*\.py$`, or keep this project in its own repo. |
| G3 | `git add` warns "adding embedded git repository" and the files never reach GitHub. | You copied a `git clone` (with its `.git/`) into another repo, such as the monorepo. | Remove the inner `.git`, or use `git subtree`/a separate repo. A submodule's own workflows will not run in the parent. |
| G4 | README Part 7 auto-format fails: `/bin/bash: docker-entrypoint.sh: No such file or directory`, exit 127. | `-v $(pwd)/src/api-service:/app` (README.md:442) hides `/app/docker-entrypoint.sh`, which the relative ENTRYPOINT (Dockerfile:52) needs. | Mount only the package: `docker run --rm -v "$(pwd)/src/api-service/api":/app/api cheese-app-api:local black --line-length 120 api/`. |
| G5 | Part 6's "break the tests" PR is still green (captured in the image: `collected 11 items`, `11 passed`). | `def broken()` is never collected because `python_functions = test_*` (pytest.ini:8). | Append `def test_broken(): assert False` instead. |
| G6 | You can't find `lint-and-format`/`unit-tests` in the required-checks picker. | The checks are listed under the jobs' `name:` (`ci.yml:42, 71, 106, 129`), and only after they have run at least once. Private repos on GitHub Free cannot use protected branches. | Search for "Unit Tests", "Integration Tests", "System Tests", "Lint and Format Check". Make the repo public or use GitHub Pro (free via the Student Developer Pack). |
| G7 | The `coverage-report-unit` artifact is missing or empty ("No files were found with the provided path: coverage/"); the coverage step's log shows `PermissionError: [Errno 13] Permission denied: 'coverage/style_cb_4667309f.css'`, exit 3, under a green job (captured). | Docker creates the missing host dir `coverage/` as root, while the container user is uid 1000 (Dockerfile:23-28), so the HTML write fails, hidden by `continue-on-error: true` (`ci.yml:95`). `coverage.xml` is written to `/app` inside the container and discarded. On Docker Desktop for Mac, bind-mount ownership is relaxed, so the same command may work locally. | Add a step `mkdir -p coverage && chmod 777 coverage` before the run, and write XML into the mount: `--cov-report=xml:coverage/coverage.xml`. Optionally drop `continue-on-error` so problems are visible. |
| G8 | Slack only ever says "✅ Passed"; failures are silent. | "Check test results" exits 1 (`ci.yml:188`), so "Check if Slack webhook is configured" (`194-201`), which has no `if:`, is skipped (captured on the class demo commit: `02 skipped Check if Slack webhook is configured`). `steps.slack-check.outputs.enabled` is then empty and the Slack condition (`204`) is false. | Add `if: always()` to the `slack-check` step. Better still, pass the secret via `env:` and test `"$SLACK_WEBHOOK_URL"` in shell. |
| G9 | Slack step is skipped on PRs from forks, or the "View Commit" link is broken. | Secrets are not provided to workflows triggered from forks. `github.event.head_commit` exists only on `push` events (`ci.yml:231, 250`). | Expected behaviour. For links, use `${{ github.server_url }}/${{ github.repository }}/commit/${{ github.sha }}`. |
| G10 | The run is red but the summary job says "✅ All tests passed!" (and Slack "✅ CI Pipeline Passed"). | `test-summary` `needs` only the three test jobs (`ci.yml:175`); lint is not included. | Add `lint-and-format` to `needs` and to the check (Exercise B2). |
| G11 | Local Black/Flake8 disagree with CI. | Local commands use the default 88/79 columns: README.md:112, 121, 124, 495-496, 502-504, 528-531. CI uses 120 (`ci.yml:61, 66`). There is no `[tool.black]` in `pyproject.toml`. | Always pass `--line-length 120` / `--max-line-length=120`, or add `[tool.black]\nline-length = 120` to `pyproject.toml` and a `.flake8` file. |
| G12 | Pre-commit passes locally but CI's Black fails, or vice versa. | Pre-commit pins Black `24.1.1` (`.pre-commit-config.yaml:30`). The image installs whatever is newest that satisfies `black>=24.1.1` (pyproject.toml:8), so the two drift as Black's yearly style changes land. README.md:564 hints at this. | Pin the same version in both places, or lock the dependencies. |
| G13 | "Re-run failed jobs" the next day fails at "Download Docker image". | The image artifact expires after 1 day (`ci.yml:38`). | Use "Re-run all jobs", or raise the retention. |
| G14 | `Bind for 0.0.0.0:9000 failed: port is already allocated`, or the container name `cheese-app-api-service` is already in use. | `docker-shell.sh:7, 15-18` uses the **same image name, container name and port** as `cheese-app-v2`/`v3`'s `src/api-service/docker-shell.sh` (lines 7, 20, 23, 27 there). A leftover `api-server` from README.md:193 also holds 9000. | `docker ps`, then stop or remove the other container. Building here also overwrites the `cheese-app-api-service:latest` tag used by v2/v3, so rebuild that one before going back to it. |
| G15 | You edit `service.py`, but the server started with `--reload` in `docker-shell.sh` doesn't change. | No volume is mounted (`docker-shell.sh:15-18`); the code is baked into the image (Dockerfile:38). | Rerun `sh docker-shell.sh`, which rebuilds the image, or add `-v "$(pwd)/src/api-service/api":/app/api` yourself. |
| G16 | System tests show "1 passed, 4 skipped" and the job is green. | The server is unreachable from the test container, and `skipif` (test_system_api.py:24) hides it. In CI the `curl -f` gate (`ci.yml:154`) protects you; locally nothing does. | Read the `-ra` summary (pytest.ini:17). Locally, use `--network container:api-server`. |
| G17 | `docker run --entrypoint pytest …` → `executable file not found`. | Tools live in `/home/app/.local/bin`, which only the entrypoint adds to PATH (docker-entrypoint.sh:5). | Keep the default entrypoint and pass the command as arguments, as CI does. |
| G18 | Running the tests without Docker fails with `ModuleNotFoundError: No module named 'api'`, including the README's own Troubleshooting command `pytest tests/ -v` (README.md:537). | `pythonpath = .` (pytest.ini:9) is the repo root locally, but the package lives in `src/api-service/`. The `sys.path` insert in `test_system_api.py:70` points to `tests/src/api-service`, which does not exist. | Use `PYTHONPATH=src/api-service pytest …` (README.md:512-513). |
| G19 | Deprecation annotations on the run page. | The workflow pins `actions/*@v4` and `slackapi/slack-github-action@v1.26.0`. GitHub periodically retires the Node.js runtimes that action majors were built on. | If you see warnings, bump to the current major versions and read their changelogs. Slack v2 renamed its inputs. |
| G20 | The README's `git commit -m "Add CI pipeline"` prints `nothing to commit, working tree clean` (exit 1), and `git push` is refused (permission denied) or says `Everything up-to-date`. | In a clone or fork `ci.yml` is already committed; a clone's `origin` is `dlops-io`, which you cannot write to; a fork already has the commit, so nothing is sent and no event fires. | Push to your own repo (`git remote set-url origin https://github.com/<you>/cheese-app-ci-cd.git`); on a fork, make a commit (the Black fix, or `git commit --allow-empty -m "Trigger CI"`) and push. |
| G21 | `git commit` fails at the Black hook, `git status --short` shows `MM`, and committing again fails with `Stashed changes conflicted with hook auto-fixes... Rolling back fixes...`. | The hook checks the **staged** copy and rewrites your working copy; the staged copy is still unformatted. | Look at Black's change, `git add` it, then commit. Don't reach for `--no-verify`: CI's Black catches it anyway (run 3, §4 Step 15). |

---

## 7. Where this sits in the course

**Before (what you already have)**
- **L9 (CI, unit testing; guest lecture):** the *same repo's* Parts 3-4: the pytest pyramid and pre-commit hooks (`tutorials_demo.md:122-135`). Everything there ran **on your laptop**.
- **L18 (APIs + Frontend):** FastAPI services (`cheese-app-v2`). The CI repo's `service.py` is a stripped-down FastAPI app built the same way, with CORS middleware and async route handlers.
- **L20 (Pulumi deployment):** `cheese-app-v3` taught you to build and push images and stand up a VM automatically.

**What L21 adds:** the same checks, run **remotely and automatically** on every push or PR, on clean machines, with a visible pass/fail signal per commit. It also covers the plumbing of Actions: runners, artifacts, `needs`, conditions, outputs and secrets. This is the CI half that Milestone 4 asks for: "Implement CI using GitHub Actions … Automate building, linting, and testing on every commit or pull request" (`milestone4.md:55-58`), with "code coverage must be at least 50%" (`milestone4.md:104`).

**After**
- **L22 (Kubernetes in the cloud)** deploys `cheese-app-v3` to GKE.
- **L23 (Final deployment):** `cheese-app-v4` adds **CD**:
  - `.github/workflows/app-ci-cd-gcp.yml` triggers on push to `main` only if the commit message contains `/deploy-app` (`app-ci-cd-gcp.yml:9`).
  - It authenticates to GCP with a **secret** `GOOGLE_APPLICATION_CREDENTIALS` (`app-ci-cd-gcp.yml:21`), the same secrets mechanism you meet here with Slack.
  - It builds a deployment container and runs Pulumi/kubectl updates.

  The v4 README states that "The CI part is not implemented in this tutorial" (`cheese-app-v4/README.md:157`), so *this* repo's pipeline is the CI piece you are expected to combine with v4's CD (Milestone 5 asks for tests on PRs plus deploy on merge, at 70% coverage: `milestone5.md:41-48`).

**This is not a cheese-app version.** It is a standalone teaching repo, so there is no v(N-1)→vN diff. Two comparisons are useful instead.

*(a) The repo's own evolution:* `git diff --stat 140f138 HEAD`, from the first complete commit to HEAD:
```
 .github/workflows/ci.yml           |  69 +++++++-
 .github/workflows/docker-build.yml |  62 -------
 README.md                          | 348 ++++++++++++++++++++++++-------------
 assets/pipline.png                 | Bin 0 -> 95374 bytes
 src/api-service/api/service.py     |  20 +--
 src/api-service/api/utils.py       |   7 +-
 6 files changed, 306 insertions(+), 200 deletions(-)
```
The meaningful changes:
- `docker-build.yml` was deleted in `199abd9`. It was a second workflow with `paths:` filters that built the image and curl-tested the server.
- Slack and step outputs were added in `199abd9`, and the `if: secrets…` fix in `1a5e363`.
- Clean code was replaced with **messy code** in `91eb786` (`service.py` and `utils.py`).
- `c2dce32` deliberately introduced `math.sqrt(a)`, a NameError, which `8eb63fc` fixed.
- In class (`c3b227f`), the instructor cleaned `service.py` and introduced `math.sqrt(2 * z)` to make integration and system tests fail. The next commit (`b8458ff`) reverted that to `math.sqrt(z)`.
- `utils.py` was left messy, which is why HEAD's lint job is red.

*(b) Compared with the API service you deployed in L20 (`cheese-app-v3/src/api-service`):*

| Aspect | cheese-app-v3 api-service | cheese-app-ci-cd |
|---|---|---|
| Dependency install | `uv` with `uv.lock` and a venv at `/home/app/.venv` | `pip install --user .`, unpinned `>=` ranges, no lock |
| `DEV=1` meaning | entrypoint drops into an interactive shell | entrypoint runs `uvicorn --reload --log-level debug` |
| Args to the container | n/a (shell helpers such as `uvicorn_server`) | `exec "$@"`, which turns the image into a tool runner for CI |
| API surface | many routers (newsletter, podcast, llm_chat, …) | 3 toy endpoints + `power()` |
| Tests | ad-hoc (`_test.py`) | 26 tests in unit/integration/system folders, baked into the image |

---

## 8. Exercises

The exercises, with answers, are in [`exercises.md`](https://github.com/JunyiZhou-Conny/Explainer_Videos/blob/main/videos/ac215-l21-cicd-github-actions/exercises.md) in the video folder. Their outputs are the 2026-11-06 captures and extra checks run for them (`assets/exercise-checks/`); no hosted GitHub run was possible, so what only GitHub shows (the run page, Slack, the branch-protection pages) is answered from `ci.yml` and GitHub's documented behaviour, and the answers say so. Do them after watching, without re-watching first, then re-watch only the chapter you got wrong. Parts 1-4 have their own exercises in [L09's](https://github.com/JunyiZhou-Conny/Explainer_Videos/blob/main/videos/ac215-l09-ci-testing/exercises.md). A summary follows; open each answer only after you have committed to your own.

**The questions the video stops on** (each is answered right after its timer): You push three commits to `feature/login`, then open a PR into `main`: how many runs? · The run turns red: is your push on `main`, or did the red run refuse it? · Delete "Load Docker image" from `unit-tests`: which step fails, and with what error? · The demo commit computes `sqrt(2·z)`: which jobs turn red, and what does Test Summary say? · A teammate commits a private key file with `--no-verify` and pushes to `main`: which job catches it?

<details><summary>Answers to the five ponders</summary>

- **Ponder 1:** 0 runs for the three pushes (`push` fires only for `main`/`develop`, `ci.yml:8-9`); 1 when the PR opens (`ci.yml:10-11`), and 1 more for each later push to the branch while the PR is open. The PR run tests a temporary merge into `main`.
- **Ponder 2:** the push is on `main`. The run started because GitHub accepted it; a workflow cannot undo a push. Branch protection is the gate (Q5).
- **Ponder 3:** "Run unit tests": `Unable to find image … locally`, then `pull access denied for cheese-app-api, repository does not exist or may require 'docker login'`, exit 125 (`runner/noload/`). The summary fails too.
- **Ponder 4:** integration ✗ (`assert 7.0710678118654755 == 5.0`), system ✗ (`2 failed, 3 passed`), unit ✓, lint ✗ (still `utils.py`), Test Summary ✗ `❌ Some tests failed!`; and the Slack check step is skipped, so no failure message (`runner/run-demo/`).
- **Ponder 5:** none. `detect-private-key` is a local hook only; CI lints only `api/`. Checked with placeholder text: the hook stops the commit (`Private key found: id_rsa`), `--no-verify` goes through. Fix: a CI step running `pre-commit run --all-files`; and rotate any key that was pushed.
</details>

### Test yourself: the five questions from the end of the video

**Q1. Name two ways code reaches the shared repository without passing your local hooks. Which checks does this pipeline repeat, and which not?**
<details><summary>Answer</summary>

A teammate who never ran `pre-commit install`, and `git commit --no-verify` (run 3: `[main 2892b1b] quick fix`); also an edit made on GitHub's web page. CI repeats only Black (blocking) and Flake8 (advisory), at 120 columns, on `api/` (`ci.yml:61, 66`); the seven hygiene hooks (`.pre-commit-config.yaml:12-26`) never run in CI. In the other direction CI runs the three test levels, which no hook runs. The two Blacks differ: the hook pins 24.1.1, the image installed 26.10.1 at the time of recording; they agreed on this code.
</details>

**Q2. Which unit gets a fresh machine, a job or a step? Why does that force the image tar and a `docker load` in every check job?**
<details><summary>Answer</summary>

A job: each `runs-on: ubuntu-latest` is a new VM with an empty Docker engine (`docker images` prints only its header in a fresh check job, `runner/run1/lint-and-format/x1`); steps of one job share its machine. The image built in `build` dies with that machine, so `build` saves it (`ci.yml:31`) and uploads the tar as `docker-image` (`ci.yml:33-38`); every check job downloads it and runs `docker load -i /tmp/cheese-app-api.tar` (`ci.yml:57` and three copies). Rebuilding per job would be slower and would no longer test the same bits.
</details>

**Q3. Your run is red, but the summary says `✅ All tests passed!`. Why, and what is the fix?**
<details><summary>Answer</summary>

`test-summary` needs and checks only the three test jobs (`ci.yml:175, 185`); lint failed, but its result never reaches the summary (`runner/run1/test-summary/01`). Any failed job makes the run red. Fix: `needs: [lint-and-format, unit-tests, integration-tests, system-tests]` **and** the lint result in the script's check (B2); with `needs` alone the summary still tests three results.
</details>

**Q4. Why can Flake8 fail without failing its job, and why don't you see Flake8's output when Black fails?**
<details><summary>Answer</summary>

Flake8's step has `continue-on-error: true` (`ci.yml:67`), so its exit 1 is recorded and the job goes on; Black's has `false` (`ci.yml:62`). Steps run only if everything before succeeded, so after Black fails, Flake8 is skipped (`runner/run1/lint-and-format/00-steps.txt`: `05 skipped Run Flake8 linter`). What it would have printed: `api/utils.py:7:15: E231 …`, `api/utils.py:13:1: E303 …` (`x4`).
</details>

**Q5. In the lecture's terms, is a push-triggered Actions run a pre-receive or a post-receive check, and what turns it into a gate on GitHub.com?**
<details><summary>Answer</summary>

Post-receive: the `push` event fires after GitHub accepted the push. The gate is branch protection on `main` (README Part 6): "Require a pull request before merging" plus "Require status checks to pass before merging" with the jobs' names (`Lint and Format Check`, `Unit Tests`, `Integration Tests`, `System Tests`). What it refuses is the merge.
</details>

### Hands-on (predict, then run)

- **B1. Run the lint job before you push.** Build the image, run the lint job's two commands with your own tag, predict both exit codes and which would fail the CI job; fix with `pre-commit run --all-files`, rebuild, run again.
- **B2. Make the summary count lint.** Add `lint-and-format` to `needs` and to the check, and append a results table to `$GITHUB_STEP_SUMMARY`; predict what the summary prints for run 1's results.
- **B3. Make the coverage report real.** Run the coverage command the way the runner does, predict the exit code and how many files the upload would find, then fix the folder and the XML path.
- **B4. A coverage bar.** Add `--cov-fail-under=50`: pass or fail for unit tests only (14.29 %), then with integration tests too (90.48 %)? What else must change in `ci.yml`?
- **B5. Wait for the server, not for 10 seconds.** Replace `sleep 10` with a `curl -sf …/health` loop that gives up after 30 s and prints the server's log.
- **B6. Make "Buildx caching" true.** Replace the plain `docker build` with `docker/build-push-action` using `load: true` and the `gha` cache (only partly checked: the cache needs GitHub).

### Debugging

- **C1.** Slack only ever says "Passed": why the failure message never arrives, and the `if: always()` / `env:` fix.
- **C2.** The repo's first Slack attempt put `secrets.SLACK_WEBHOOK_URL` in an `if:`: what actionlint says about it.
- **C3.** "I pushed and no run appears": `nothing to commit`, then `Everything up-to-date` on a fork; three other reasons.
- **C4.** The hook stopped the commit, so you commit again: the `Stashed changes conflicted with hook auto-fixes... Rolling back fixes...` message, and the way out.
- **C5.** The protected branch that didn't protect: `def broken()` and the missing `unit-tests` in the picker.
- **C6.** One typo in `service.py`: which jobs turn red, and the log line that tells you why in each.
- **C7.** "Re-run failed jobs" the next day fails at "Download Docker image".

### Think

- **D1.** Where should each check live: local hook, CI job, branch protection, or a combination?
- **D2.** Count the runs for five pushes and PRs under the triggers of `ci.yml:7-11`.
- **D3.** Two minutes or six: wall-clock time vs billed minutes, and whether merging the test jobs saves money.
- **D4.** Require only "Test Summary" in branch protection: a good idea at `b8458ff`? After B2?
- **D5.** When the code trains a model (lecture slides 17–20): what belongs in push-triggered CI, and what not?

---

## 9. Errata and open questions

**Errata (with evidence)**
1. **The first run is red; the README's all-green screenshot does not match the code.** At `b8458ff`, Black fails on `src/api-service/api/utils.py:7` and `:10-12` (captured: `runner/run1/lint-and-format/04`, and act). `assets/pipline.png` was added in `3dea317` (2025-11-13 10:08 +0530), when `utils.py` and `service.py` were already messy (since `91eb786`), so the screenshot comes from another code state, most likely the clean code before `91eb786` (Black and Flake8 at 120 columns pass on the `140f138` copies and fail on the `3dea317` copies). After the Black fix, run 2 matches it. README Part 5 never warns that the first run will be red.
2. **`git commit -m "Add CI pipeline"` has nothing to commit** (README.md:347) in a clone or a fork: `nothing to commit, working tree clean`, exit 1 (`laptop/11`). The workflow is already committed.
3. **The README's `git push` (README.md:348) goes to the course's repo** when you cloned `dlops-io/cheese-app-ci-cd` (`origin`, `laptop/13`), and GitHub refuses it. Fork it, or `git remote set-url origin https://github.com/<you>/cheese-app-ci-cd.git`. On a fork, `git push` sends nothing and starts no run until you make a commit.
4. **Part 6's break-test command doesn't break tests.** `echo "def broken(): assert False"` (README.md:388) adds a function that pytest won't collect (`pytest.ini:8`, `python_functions = test_*`): still `11 passed` (`laptop/53`). `def test_broken` gives `1 failed, 11 passed` (`laptop/57`).
5. **Part 6 lists job IDs as status checks.** README.md:378 lists `lint-and-format`, `unit-tests`, … but the checks are named after the jobs' `name:` values (`ci.yml:42, 71, 106, 129`). The "Settings → Branches → Add rule" path (README.md:373) also predates GitHub's current "classic rule / ruleset" UI.
6. **Part 7's auto-format command hides the entrypoint.** README.md:442 mounts over `/app` and hides `docker-entrypoint.sh` (Dockerfile:52): `/bin/bash: docker-entrypoint.sh: No such file or directory`, exit 127 (exercise check).
7. **"Uses Docker Buildx for efficient caching"** (README.md:291). The build runs on the default builder (`building with "default" instance using docker driver`, `runner/run1/build/03`; act: `docker:default`), and no cache import/export is configured (`ci.yml:22-27`): every run rebuilds from scratch.
8. **Coverage claims.** README.md:307-308 says XML and HTML reports are generated and uploaded. On a Linux runner the HTML write fails with `PermissionError: [Errno 13] Permission denied: 'coverage/style_cb_4667309f.css'`, exit 3, because Docker creates `coverage/` as root while the container runs as uid 1000; `continue-on-error` (`ci.yml:95`) keeps the job green, and the upload finds 0 files (`runner/run1/unit-tests/05`, `06`, `x3`). The XML goes to `/app/coverage.xml` inside a `--rm` container and is lost (`ci.yml:94`).
9. **Slack failure notifications are unreachable.** `slack-check` (`ci.yml:194-201`) lacks `if: always()`, so it is skipped after a failing summary (captured: `runner/run-demo/test-summary/00-steps.txt`), and the "❌ CI Pipeline Failed" branch (`ci.yml:209, 215`) can never be sent.
10. **The test summary ignores lint.** `needs` (`ci.yml:175`) omits `lint-and-format`, so the summary prints `✅ All tests passed!` in a red run (`runner/run1/test-summary/01`), and Slack would say "passed". README.md:325-330 calls it a summary of all tests, which is literally true but misleading.
11. **The README never documents the Slack step or the `SLACK_WEBHOOK_URL` secret** (a grep for "slack|secret" in README.md finds nothing).
12. **Line-length inconsistency** between the README's local commands (default 88/79 columns: README.md:112, 121, 124, 495-496, 502-504, 528-531) and CI (120: `ci.yml:61, 66`). There is no `[tool.black]` in `pyproject.toml`.
13. **Unpinned Black in the image vs pinned Black in pre-commit:** `pyproject.toml:8` (`black>=24.1.1`, 26.10.1 at the time of recording) vs `.pre-commit-config.yaml:30` (`rev: 24.1.1`). They agreed on this code in the captures; they can drift.
14. **`ci.yml:2`** says "Runs on every push and pull request to main branch", but the triggers include `develop` (`ci.yml:9, 11`).
15. **`Dockerfile:1`** says "Multi-stage Dockerfile", but there is a single `FROM` (Dockerfile:2).
16. **`tests/system/test_system_api.py:2`** calls itself "Integration tests". Its `sys.path` insert (line 70) points to the non-existent `tests/src/api-service`; it works in Docker only because of `pytest.ini:9`.
17. **`pytest.ini:22`** describes the `integration` marker as "(require running services)", which contradicts README.md:147 ("No real HTTP server needed"). The markers are unused anyway.
18. **Outdated lecture references in comments:** `pytest.ini:2` ("from L18"), `tests/integration/test_api.py:4` ("Based on L18, Slide 11-12") and `.pre-commit-config.yaml:2, 28, 37` ("L17, Slide …") refer to an older numbering. In 2026 this material is L9.
19. **`--reload` has no effect in the README's Part 1 flow** (README.md:82): `docker-shell.sh:15-18` mounts no source.
20. **The course site's lecture numbering is inconsistent.** `tutorials_demo.md` has L19 = K8s (local), L20 = Pulumi, L22 = K8s (cloud), L23 = Final. `_modules/week-11.md`/`week-12.md`/`week-14.md` have L19 = Pulumi, L20 = K8s (cloud), L22 = Final. L21 is consistent in both (Nov 19 in `week-12.md:9-11`).
21. **README Troubleshooting "Tests fail locally"** (README.md:534-544) runs `pytest tests/ -v` from the project root without `PYTHONPATH`. Outside Docker that fails with `ModuleNotFoundError: No module named 'api'` (G18); the README's own working form is `PYTHONPATH=src/api-service pytest …` (README.md:512-513).
22. **The lecture slides and the repo differ in nine places** (pre-commit's timing, Actions as a "remote hook", the local chain, "every push", the straight-line pipeline, the webhook direction, the Slack message's content, what CI re-runs after `--no-verify`, and slide 28's link anchor): see [Lecture slides](#lecture-slides). In each case, follow the repo.

**Open questions / could not determine**
- **The Ed lesson itself** (recording, any extra steps) was not accessible. The in-class demo is inferred from commits `c3b227f`/`b8458ff` ("demo class 1") and was re-run on stand-in runners (`runner/run-demo/`).
- **The hosted run itself.** No push to GitHub was possible from the recording machine. Every job was run live on stand-in runners and with act, and both agree; the Actions tab, real durations, the Slack message, the protected-branch pages and a refused push are *expected*, not observed. Check your own run's log and annotations.
- **Coverage on Docker Desktop for Mac.** Bind-mount ownership is relaxed there, so the coverage command may succeed on your laptop while it fails on a Linux runner. Not checked.
- **Local `--network host` behaviour on your Docker Desktop version** (host networking is a newer, opt-in Docker Desktop feature). If system tests skip locally, use `--network container:api-server`.
- **Current Actions deprecations** (Node runtime of `actions/*@v4`, Slack action v1 vs v2) at the time you run this. Check the run annotations.

---

## Links

- README sections, `cheese-app-ci-cd` (pinned commit):
  - Lecture 21: [Part 5: GitHub Actions (Remote CI)](https://github.com/dlops-io/cheese-app-ci-cd/blob/b8458ff0cc1898700b32a873b4665f43f50df71e/README.md#part-5-github-actions-remote-ci) ([Push to GitHub](https://github.com/dlops-io/cheese-app-ci-cd/blob/b8458ff0cc1898700b32a873b4665f43f50df71e/README.md#push-to-github) · [Watch GitHub Actions](https://github.com/dlops-io/cheese-app-ci-cd/blob/b8458ff0cc1898700b32a873b4665f43f50df71e/README.md#watch-github-actions) · [CI Pipeline in Action](https://github.com/dlops-io/cheese-app-ci-cd/blob/b8458ff0cc1898700b32a873b4665f43f50df71e/README.md#ci-pipeline-in-action)) · the workflow file [`.github/workflows/ci.yml`](https://github.com/dlops-io/cheese-app-ci-cd/blob/b8458ff0cc1898700b32a873b4665f43f50df71e/.github/workflows/ci.yml) · latest README on [`main`](https://github.com/dlops-io/cheese-app-ci-cd#part-5-github-actions-remote-ci)
  - Follow-ons: [Part 6: Branch Protection (Optional)](https://github.com/dlops-io/cheese-app-ci-cd/blob/b8458ff0cc1898700b32a873b4665f43f50df71e/README.md#part-6-branch-protection-optional) · [Part 7: Student Exercise - Add a New Endpoint with Full CI](https://github.com/dlops-io/cheese-app-ci-cd/blob/b8458ff0cc1898700b32a873b4665f43f50df71e/README.md#part-7-student-exercise---add-a-new-endpoint-with-full-ci) · [Docker Cleanup](https://github.com/dlops-io/cheese-app-ci-cd/blob/b8458ff0cc1898700b32a873b4665f43f50df71e/README.md#docker-cleanup)
  - Context (L09): [Part 1: Understanding the Codebase](https://github.com/dlops-io/cheese-app-ci-cd/blob/b8458ff0cc1898700b32a873b4665f43f50df71e/README.md#part-1-understanding-the-codebase) · [Part 2: Identifying Code Quality Issues](https://github.com/dlops-io/cheese-app-ci-cd/blob/b8458ff0cc1898700b32a873b4665f43f50df71e/README.md#part-2-identifying-code-quality-issues) · [Part 3: Testing with Pytest](https://github.com/dlops-io/cheese-app-ci-cd/blob/b8458ff0cc1898700b32a873b4665f43f50df71e/README.md#part-3-testing-with-pytest) · [Part 4: Automating with Pre-commit Hooks](https://github.com/dlops-io/cheese-app-ci-cd/blob/b8458ff0cc1898700b32a873b4665f43f50df71e/README.md#part-4-automating-with-pre-commit-hooks)
- Context repos cited in §7 (pinned commits): [`dlops-io/cheese-app-v3` @ `3ecef56`](https://github.com/dlops-io/cheese-app-v3/tree/3ecef56fea879ac480d260c0906cd95baf05179a) · [`dlops-io/cheese-app-v4` @ `033f187`](https://github.com/dlops-io/cheese-app-v4/tree/033f18713b9e1e7985a3080e85edab3ff01cefef) (its CD workflow [`app-ci-cd-gcp.yml`](https://github.com/dlops-io/cheese-app-v4/blob/033f18713b9e1e7985a3080e85edab3ff01cefef/.github/workflows/app-ci-cd-gcp.yml))
- Ed lesson: [L21 · Automating Software Development: CI/CD with GitHub Actions II](https://edstem.org/us/courses/97373/lessons/166046/) · course [tutorials page](https://harvard-iacs.github.io/2026-AC215/tutorials_demo/)
- Colab notebooks: none for this lecture.
- Previous lecture: [L20 · Deployment: Pulumi](L20-deployment-pulumi.md) (`cheese-app-v3` on a VM)
- Next lecture: [L22 · Scaling: Kubernetes (cloud)](L22-kubernetes-cloud.md) (`cheese-app-v3` on GKE)
- Referenced in §7: [L09 · Automating Software Development: CI, unit testing](L09-ci-testing-precommit.md) (Parts 1-4 of this repo) · [L18 · APIs + Frontend](L18-apis-frontend.md) · [L23 · Final Deployment and Review](L23-final-cicd-deployment.md) (`cheese-app-v4` CD)
