# L09 · Automating Software Development: CI, unit testing — study guide

[Ed lesson](https://edstem.org/us/courses/97373/lessons/166034/) · Tutorial: [`dlops-io/cheese-app-ci-cd`](https://github.com/dlops-io/cheese-app-ci-cd) `main` @ [`b8458ff`](https://github.com/dlops-io/cheese-app-ci-cd/tree/b8458ff0cc1898700b32a873b4665f43f50df71e) (Part 3 · Testing with Pytest, Part 4 · Automating with Pre-commit Hooks) · Guest lecture (Rahul Dave): [`rahuldave/babykev-walk`](https://github.com/rahuldave/babykev-walk) `main` @ [`82adb14`](https://github.com/rahuldave/babykev-walk/tree/82adb14c0f3e73a0a836a3655f7dc4ffcdf76670) (slides / tutorial app) and [`rahuldave/babykev`](https://github.com/rahuldave/babykev) `main` @ [`4a14085`](https://github.com/rahuldave/babykev/tree/4a14085bb25620f37dca5c2bfeb27843c82dbe9e) (project, tags `step-00` … `step-05b`) · Colab: none for L09 · Video: planned · Made from the verified digest, 2026-10-13

## 中文速览

- **做什么：** 这节课不写新 app。拿一个很小的 FastAPI service（`api.service:app`，唯一做计算的 endpoint `/euclidean_distance/` 调 `api/utils.py` 里的 `power()`），给它加三层 test：unit、integration、system，全部在同一个 Docker image `cheese-app-api:local` 里跑。然后在 host 上装 pre-commit hook：每次 `git commit` 之前先跑 9 个 hook（trailing whitespace、end-of-file、YAML、JSON、>1000 KB 大文件、private key、merge marker、black 120、flake8 120），全部通过 commit 才会生成。Guest lecture（Rahul Dave）的 `babykev` 把同一个 gate 用在真实的 ML project 上：`uv.lock` 锁环境，`just` 给每个 task 起名字，项目自己的检查全收进一个 hook：`just check`。全程不用 GCP，不花钱。
- **Idea 1 · testing pyramid 按"跑了什么"来分：** unit = 直接调 `power()`；integration = 用 FastAPI 的 `TestClient` in-process 调整个 app（routing、validation、handler、`power()`，没有 socket）；system = 真 HTTP 打 `localhost:9000` 上的 uvicorn。文件夹名字不决定 test 类型，这个 repo 自己就把 system test 叫成了 "Integration tests"。
- **Idea 2 · skipped ≠ passed：** system tests 用 `skipif(not is_api_running())`，而且只在 import（collection）时探测一次 `/health`。server 没起来就是 `1 passed, 4 skipped`，整个 run 还是绿的，一定要看 `-ra` 的 summary。CI 先用 `curl -f` 卡住，server 不在就直接 fail。babykev 的做法是 marker：非 hermetic 的 test 默认 deselect（`-m 'not system'`），要跑就 `just test -m system`，必须 pass，不能 skip。
- **Idea 3 · formatter vs linter：** black 负责改写 layout，flake8 只负责报告问题。black 删不掉 unused import（F401），也拆不开长字符串（E501），这些要人来改。两个 tool 的 line length 必须一致：hook 和 CI 都是 120，但 black 默认 88、flake8 默认 79，README 里好几条命令没传宽度，所以结果对不上。
- **Idea 4 · git hook 是 commit 前的闸门：** `pre-commit install` 写出 `.git/hooks/pre-commit`。`.git/hooks/` 不会被 commit，也不会跟着 clone 下来，所以每个 clone 都要重新 install（babykev 的 `just setup` 顺手装好）；`git commit --no-verify` 也能跳过它，所以 CI（L21）要在 server 上再跑一遍。hook 改了文件（black、end-of-file-fixer）就算 Failed：`git diff` → `git add -u` → 再 commit。pre-commit 用的是它自己 pin 的 `rev`（black 24.1.1），不是你装的 black。hook 和 `ci.yml` 都只认 repo root：别把 `cheese-app-ci-cd` 放进 `MLOps_Learning` 这种 monorepo 里，否则 black/flake8 根本不会跑（G12）。
- **Idea 5 · coverage 不等于 correctness：** babykev 的 step-05 是 92 tests、94% coverage、全绿，`branch_mask` 却是错的（question 2 能 attend 到 question 1）。step-05a 用 hypothesis 写 property-based test 才抓到，还把 counter-example shrink 到 `shape = (1, [1, 1, 1])`。
- **Idea 6 · 一个 environment，一条命令：** cheese 靠 Docker image 保证环境一致（code 是 `COPY` 进去的，测的就是要 ship 的那个 artifact）；babykev 靠 `uv.lock`（`UV_LOCKED=1`）加 `just check`，人、hook、agent 和以后的 CI 都跑同一个动词。dev 依赖放在 `[dependency-groups]`，不跟 runtime 混在一起。
- **最费时间的坑：** ① code 和 tests 是 `COPY` 进 image 的，没有 volume mount：改了 `utils.py` 或 test 不 rebuild（`docker build -t cheese-app-api:local .`）就什么都不变（G1）。② fresh clone 上 `black --check --line-length 120 api/` 直接 fail：`utils.py` 是故意留脏的（G23），不是你 Part 7 的 `/add/` 代码有问题。
- **README 的几个 errata：** README:442 的 auto-format 命令把 `src/api-service` mount 到 `/app`，盖掉了 `docker-entrypoint.sh`，必报 `No such file or directory`（E1、G2）；`/euclidean_distance/` 返回的是 JSON object，不是 `5.0`；"What Gets Checked?" 只列了 5 个 hook，config 里其实有 9 个；Part 6 的 `def broken(): assert False` 不会让任何 test 变红（只有 `test_*` 会被 collect）；Option 3 说"另开一个 terminal 起 server"，会和 `docker-shell.sh` 抢 9000 端口。
- **做完要删：** `docker stop api-server && docker rm api-server`，然后 `docker container ls`、`docker system prune`、`docker image ls`（`cheese-app-api:local`、`cheese-app-api-service` 这种有 tag 的 image 要自己 `docker image rm`）；`pre-commit uninstall` 加 `pre-commit clean`（删 `~/.cache/pre-commit/`）；babykev 的 `.venv`（CPU torch，几百 MB）、`~/.cache/huggingface` 里的 Qwen2.5-0.5B（约 1 GB）、step-05b 的 images（`just image stop` 再 `docker image rm`）。

## At a glance

**What you build.** You take a small FastAPI service from the cheese app and put a gate in front of it: three layers of pytest tests (unit, integration through `TestClient`, system over real HTTP), all run inside the same Docker image that serves the app, plus a pre-commit hook that formats, lints and checks every commit before it is allowed to exist. The guest lecture's `babykev` builds the same gate around a real ML model with `uv` and `just`, adds type checking, docs checks, a coverage floor and property-based tests, and shows how a fully green gate can still let a wrong model through.

**Time needed** (estimate). Parts 1–4 of the cheese tutorial: about 1.5–2 h, including the first `docker build` and the first `pre-commit run`, which downloads the hook environments. Part 7 as an exercise: about 30 min. The guest-lecture walk, steps 00–05a: about 2–3 h (step 05's `just setup` downloads torch, a few hundred MB). The optional step-05b (Docker, the 1 GB model): about 1 h more.

**Prerequisites.**
- Docker Desktop (Mac/Windows) or Docker Engine (Linux), Git, Python 3.9+ and a GitHub account (README:5-9). `pre-commit` on the **host**, not in the container (README:238).
- A GitHub account is needed only to push your own copy, which needs a fork (Parts 5–7). Part 4 works entirely on your machine.
- Guest lecture: uv, git, just, Quarto (1.4 or newer) and a recent browser (`babykev-walk/README.md:10-14`). Docker only for the optional step-05b.
- Background: the `docker-shell.sh` / `docker-entrypoint.sh` / non-root-user Dockerfile pattern from L02–L04, and uv from L01.
- Credentials: none. No GCP account, no cloud keys, no APIs to enable.

**What it costs.** Nothing billable on GCP. What you spend is disk and bandwidth: the Docker images (python slim + build-essential + dependencies), the pre-commit hook environments in `~/.cache/pre-commit/`, babykev's `.venv` with CPU torch (a few hundred MB) and, only if you run `just smoke local` or `just test -m system`, about 1 GB of Qwen2.5-0.5B weights. GitHub Actions (L21) is free for public repos.

**Tear down, exactly** (details in §2):
1. `docker stop api-server && docker rm api-server` (README:199), if the Option 2 server is still running.
2. README "Docker Cleanup" (README:568-574): `docker container ls`, stop any container still running, `docker system prune`, `docker image ls`. `docker system prune` leaves tagged images, so remove `cheese-app-api:local`, `cheese-app-api-service` and (if you built it) `cheese-app-test` with `docker image rm`.
3. `pre-commit uninstall` (removes `.git/hooks/pre-commit`) and `pre-commit clean` (removes `~/.cache/pre-commit/`). Neither is in the README.
4. babykev: delete `.venv/`; delete the Qwen2.5-0.5B weights from `~/.cache/huggingface`; for step-05b, `just image stop`, then `docker image rm` the run and dev images.

<details>
<summary><b>Versions and sources this guide was checked against</b></summary>

- **README sections this lecture covers** (course site source `tutorials_demo.md:122-135`), in `cheese-app-ci-cd`'s `README.md`:
  - `#part-3-testing-with-pytest` (README:132-228) and `#part-4-automating-with-pre-commit-hooks` (README:232-273): the core.
  - `#part-1-understanding-the-codebase` and `#part-2-identifying-code-quality-issues` (README:51-128): setup context.
  - `#part-7-student-exercise---add-a-new-endpoint-with-full-ci` (README:401-453): used as an exercise.
  - `#part-5-github-actions-remote-ci` is lecture 21 (`tutorials_demo.md:275`). It is only mentioned here.
- **Primary repo:** `dlops-io/cheese-app-ci-cd`, branch `main`, commit `b8458ff0cc1898700b32a873b4665f43f50df71e`, committed 2025-11-13 13:59:04 -0500.
- **Guest lecture:** Rahul Dave, "Software Development for Machine Learning" (`tutorials_demo.md:125-127`).
  - Slides and step notes: `rahuldave/babykev-walk`, branch `main`, commit `82adb14c0f3e73a0a836a3655f7dc4ffcdf76670`, committed 2026-10-06 11:59:51 -0400 (`slides/*.md`, `walk.md`).
  - The project: `rahuldave/babykev`, branch `main`, commit `4a14085bb25620f37dca5c2bfeb27843c82dbe9e`, committed 2026-10-06 10:47:24 -0400. It is built up step by step under the tags `step-00` … `step-05b`, one per step of the guest lecture (`step-05b` = `47b43c0916ac186e3efdf42e15dbcf1f04edb1a0`; `HEAD` only adds a README table on top of it). A `gh-pages` branch (`f1ea639aad03beb4291e2e2ddcd59f08817a1d57`) holds the published docs site.
- **How the facts were checked** (verified on 2026-10-13 against the repos): every file cited in this guide was read in full, and line references were checked with `sed -n` or `grep -n`. Lint results come from running `flake8 --isolated` and `black --check` on copies of the source files, outside the repo (flake8 7.3.0, black 26.5.1). The hooks pin older versions (black 24.1.1, flake8 7.0.0), but these files give the same findings. **No repository code, tests, Dockerfiles or scripts were executed.** Expected test counts and outputs come from reading the code.
- **Colab notebooks:** none for L09.
- **Ed lesson:** its text was not readable when these sources were checked; the repos and the course site were used instead.

</details>

## Command checklist

Commands in backticks are exactly as the README (or, for the guest lecture, `walk.md`) writes them, placeholders kept. Plain items are browser or editor steps. Items marked *(extra)* are not in the README; they come from §4 of this guide. Run everything from the repo root unless an item says "inside the container".

### Before the README *(extra)*

*Get the code* (§4 A0; the README only says "Clone or download from your repository", README:20)
- [ ] `cd /Users/conny/Desktop/AC215` — *(extra)* your course folder. Keep each course repo as its own clone here, not inside another git repo (G12).
- [ ] `git clone https://github.com/dlops-io/cheese-app-ci-cd.git` — *(extra)* the URL comes from the course site (`tutorials_demo.md:131`).
- [ ] `cd cheese-app-ci-cd` — *(extra)*
- [ ] `git log -1 --format='%H %ci'` — *(extra)* expect `b8458ff0cc1898700b32a873b4665f43f50df71e 2025-11-13 ...`.
- [ ] `git log --oneline` — *(extra, optional)* the story of the class demo: `91eb786` "readd messy code", `c2dce32` "with wrong variable", `8eb63fc` "fixed the a problem", `c3b227f`/`b8458ff` "demo class 1".

### Part 1: Understanding the Codebase

*Run the Application* (README:67-92)
- [ ] `sh docker-shell.sh` — builds image `cheese-app-api-service` and opens bash in it as user `app`; expect `Container is running!!!`, `Executing command: /bin/bash`, then a prompt like `app@<id>:/app$`.
- [ ] `uvicorn api.service:app --host 0.0.0.0 --port 9000 --reload` — inside the container: starts the API on port 9000, published to your host.
- [ ] Open `http://localhost:9000` — `{"message":"Welcome to the Cheese App CI/CD Tutorial!"}`.
- [ ] Open `http://localhost:9000/health` — `{"status":"healthy"}`.
- [ ] Open `http://localhost:9000/euclidean_distance/?x=3&y=4` — a JSON object with `"x":3.0`, `"y":4.0`, `"distance":5.0` and a `"message"`, not the bare `5.0` the README promises.
- [ ] Ctrl-C, then `exit` — "Please exit and remove your container after this" (README:92); `--rm` deletes the container.

### Part 2: Identifying Code Quality Issues

*Option A: Check with Docker* (README:103-113)
- [ ] `docker build -t cheese-app-api:local .` — builds the image every later part uses; the code and tests are copied in (baked), not mounted.
- [ ] `docker run --rm cheese-app-api:local flake8 --max-line-length=120 api/` — expect `api/utils.py:7:15: E231 missing whitespace after ','` and `api/utils.py:13:1: E303 too many blank lines (3)`; non-zero exit, on purpose.
- [ ] `docker run --rm cheese-app-api:local black --check --diff api/` — at black's default width 88: `would reformat` both `utils.py` and `service.py`, ending `2 files would be reformatted, 1 file would be left unchanged.`

*Option B: Check Locally (if Python installed)* (README:116-125)
- [ ] `pip install black flake8` — on the host; on a Homebrew Python it may fail with `externally-managed-environment` (G10).
- [ ] `flake8 src/api-service/api/` — at flake8's default 79 you get one extra finding: `service.py:15:80: E501 line too long (95 > 79 characters)`.
- [ ] `black --check --diff src/api-service/api/` — at 88, black also wants to fold `service.py:15`.

### Part 3: Testing with Pytest

*Option 1: Run Unit & Integration Tests (Recommended)* (README:163-182)
- [ ] `docker build -t cheese-app-api:local .` — rebuild after every edit to code or tests (G1).
- [ ] `docker run --rm cheese-app-api:local pytest tests/unit/ -v` — expect **11 passed**.
- [ ] `docker run --rm cheese-app-api:local pytest tests/integration/ -v` — expect **10 passed** (7 + 2 + 1 async).
- [ ] `docker run --rm cheese-app-api:local pytest tests/unit/ tests/integration/ -v` — expect **21 passed**.
- [ ] `docker run --rm cheese-app-api:local pytest tests/unit/ --cov=api --cov-report=term` — `api/service.py` at **0%** (unit tests never import it); `api/utils.py` misses line 14.

*Option 2: Run System Tests* (README:184-202)
- [ ] `docker build -t cheese-app-api:local .`
- [ ] `docker run -d --name api-server -p 9000:9000 -e DEV=1 cheese-app-api:local` — starts uvicorn in the background; `DEV=1` selects `--reload --log-level debug`.
- [ ] `until curl -sf http://localhost:9000/health; do sleep 1; done` — *(extra)* waits until the server answers, as CI does (`ci.yml:150-154`).
- [ ] `docker run --rm --network host cheese-app-api:local pytest tests/system/ -v` — expect **5 passed**. `1 passed, 4 skipped` means the server was not reachable when the tests were collected (G3).
- [ ] `docker exec api-server python -m pytest tests/system/ -v` — *(extra)* the fallback if `--network host` doesn't reach the server on Docker Desktop (Q2).
- [ ] `docker stop api-server && docker rm api-server` — clean up.
- [ ] `docker rm -f api-server` — *(extra)* only if a leftover container still holds the name `api-server` (G5).

*Option 3: Interactive Container Workflow* (README:204-228)
- [ ] `sh docker-shell.sh` — rebuilds `cheese-app-api-service` and opens bash in it.
- [ ] `pytest tests/unit/ -v` — inside the container; 11 passed.
- [ ] `pytest tests/integration/ -v` — inside the container; 10 passed.
- [ ] `pytest tests/unit/ tests/integration/ -v` — inside the container; 21 passed.
- [ ] `pytest tests/unit/ --cov=api --cov-report=html` — writes `/app/htmlcov/` inside a `--rm` container with no mount: gone on `exit`, and your host browser can't open it (G13).
- [ ] `pytest tests/unit/ --cov=api --cov-report=term-missing` — *(extra)* lists the missed lines in the terminal instead.
- [ ] `uvicorn api.service:app --host 0.0.0.0 --port 9000 &` — *(extra)* starts the server in this same container. README:228's "another terminal" collides on port 9000 and can't be reached from here anyway (G4, E7).
- [ ] `pytest tests/system/ -v` — *(extra)* now runs against that server.
- [ ] `exit` — *(extra)* leaves the container; `--rm` deletes it.

### Part 4: Automating with Pre-commit Hooks

*Install Pre-commit Framework* (README:236-241)
- [ ] `pip install pre-commit` — outside the container, on the host. If PEP 668 refuses it, use `brew install pre-commit`, `pipx install pre-commit` or `uv tool install pre-commit` *(extra)*.

*Install the Hooks* (README:243-249)
- [ ] `pre-commit install` — from the repo root; expect `pre-commit installed at .git/hooks/pre-commit`.

*Run the Hooks* (README:251-266)
- [ ] `git commit -m "Your commit message"` — git runs the hook before it creates the commit; the commit is created only if every hook passes and none modified a file. On a fresh clone nothing is staged yet, so there is nothing to commit: the commit is repeated below, after the manual run (§4 A9-A10).
- [ ] `pre-commit run --all-files` — the first run downloads `pre-commit-hooks` v4.5.0, black 24.1.1 and flake8 7.0.0 into `~/.cache/pre-commit` (needs internet). Expect `Format Python code with Black … Failed`, `- files were modified by this hook`, `reformatted src/api-service/api/utils.py`; flake8 then passes; `Check JSON syntax` shows `(no files to check)Skipped`.
- [ ] `git diff` — *(extra)* `def power(base, exponent):` and one blank line removed.
- [ ] `pre-commit run` — staged files only; with nothing staged, every hook prints `(no files to check)Skipped`.
- [ ] `git add -u` — *(extra)* stages black's fix; a commit needs something staged.
- [ ] `git commit -m "Your commit message"` — *(extra: the README commit again)* the hooks now run on the staged `utils.py`, which black already fixed, so the commit is created. It stays local (§2).
- [ ] *(extra)* Add `import os` back at the top of `service.py`, stage it and commit: flake8 blocks it with `F401 'os' imported but unused`, which black can't fix. Remove the line again.

*(Parts 5 and 6, GitHub Actions and branch protection, belong to L21.)*

### Part 7: Student Exercise - Add a New Endpoint with Full CI

*(README:401-453; exercise, §4 A11)*
- [ ] Add the `/add/` endpoint (README:406-409) to `src/api-service/api/service.py`.
- [ ] Add `test_add_endpoint` (README:415-418) to `tests/integration/test_api.py`.
- [ ] `docker build -t cheese-app-api:local .`
- [ ] `docker run --rm cheese-app-api:local pytest tests/ -v` — with no server running: **23 passed, 4 skipped**.
- [ ] `docker run --rm cheese-app-api:local pytest tests/unit/ -v`
- [ ] `docker run --rm cheese-app-api:local pytest tests/integration/ -v` — 11 passed with your new test.
- [ ] `docker run --rm cheese-app-api:local black --check --line-length 120 api/` — fails on a fresh clone with `would reformat api/utils.py`, before you change anything (G23).
- [ ] `docker run --rm -v $(pwd)/src/api-service:/app cheese-app-api:local black --line-length 120 api/` — as written it fails: `/bin/bash: docker-entrypoint.sh: No such file or directory` (G2). Don't use it.
- [ ] `docker run --rm -v "$(pwd)/src/api-service/api:/app/api" cheese-app-api:local black --line-length 120 api/` — *(extra)* the working version: mount only the package.
- [ ] `git add .` — (README:448)
- [ ] `git commit -m "Add addition endpoint with tests"` — the pre-commit hook runs first.
- [ ] `git push` — rejected on a plain dlops-io clone; needs a fork or your own remote (E18). Watching CI is L21.

### Quick Command Reference and Troubleshooting

*Commands not already listed above* (README:457-566)
- [ ] `docker run --rm cheese-app-api:local pytest tests/ -v` — (README:467) all three folders; with no server: 22 passed, 4 skipped.
- [ ] `docker run --rm cheese-app-api:local black --check --line-length 120 api/` — (README:478) the CI-width black; together with README:479's flake8 at 120, both flag only `utils.py`.
- [ ] `black --check api/` and `black api/` — (README:495-496) inside the container, at black's default 88 (E5). `black api/` edits only the container's copy, which a `--rm` container without a mount throws away (G1).
- [ ] `python3 -m flake8 src/api-service/api/` — (README:502) on the host, at flake8's default 79 (E5).
- [ ] `python3 -m black --check src/api-service/api/` and `python3 -m black src/api-service/api/` — (README:503-504) at 88; pass `--line-length 120` to match the hook (G9).
- [ ] `PYTHONPATH=src/api-service pytest tests/unit/ -v` — (README:512) on the host; needs `pytest` installed (G7).
- [ ] `PYTHONPATH=src/api-service pytest tests/integration/ -v` — (README:513) also needs `fastapi`, `httpx` and `pytest-asyncio` (G8).
- [ ] `python3 -m black src/api-service/api/` and `python3 -m black --check --diff src/api-service/api/` — (README:528, 531, Troubleshooting "Black formatting conflicts") also at black's default 88 (E5); add `--line-length 120`.
- [ ] `pytest tests/ -v`, `pytest tests/ -vv --tb=long`, `pytest tests/integration/test_api.py -v` — (README:537-543) on the host these fail with `No module named 'api'` without `PYTHONPATH=src/api-service` (E6, G7).
- [ ] `docker build -t cheese-app-test . --no-cache` — (README:548) builds a third image name; it does not update `cheese-app-api:local` (E15).
- [ ] `docker ps` and `docker logs <container-name>` — (README:554, 557) is the server up, and what did it log?

### Docker Cleanup

*(README:568-574)*
- [ ] `docker stop api-server && docker rm api-server` — if it is still running (README:199).
- [ ] `docker container ls` — then stop any container that is still running.
- [ ] `docker system prune` — removes stopped containers, unused networks and dangling images.
- [ ] `docker image ls` — see what is left.
- [ ] `docker image rm cheese-app-api:local cheese-app-api-service` — *(extra)* tagged images survive `docker system prune`; add `cheese-app-test` if you built it.
- [ ] `pre-commit uninstall` — *(extra)* removes `.git/hooks/pre-commit`.
- [ ] `pre-commit clean` — *(extra)* removes the hook environments in `~/.cache/pre-commit/`.

### Guest lecture · `babykev-walk` README

*Start* (`babykev-walk/README.md:16-34`)
- [ ] Fork `rahuldave/babykev-walk` on GitHub so you can save your own notes, then clone your fork.
- [ ] `git clone https://github.com/<you>/babykev-walk`
- [ ] `cd babykev-walk`
- [ ] `just present` — runs `just setup` first (the first time it clones babykev into `repo/`, your fork if you have one, and fetches the `step-*` tags), then starts timewalk; expect `setup: repo/ is ..., with 9 steps from rahuldave/babykev` and an address to open.
- [ ] Open the address that timewalk prints.
- [ ] `just setup url=<address>` — only to clone babykev from another address; run it before the first `just present`.

*The page* (`babykev-walk/README.md:48-62`)
- [ ] Work in the **Main** tab (`repo/`): the **At this step** and **Runs** terminals use `worktree/`, which is reset when you move to another step (G21).
- [ ] `just pdf` — makes `build/walk.pdf`, the slides one page each.
- [ ] On Linux, read `sed -i ''` as `sed -i` and `open` as `xdg-open` (`babykev-walk/README.md:66`).

### Guest lecture · `babykev` README

*What you need, Running it* (`babykev/README.md:43-90`)
- [ ] `just setup` — installs Python 3.13 and everything else from `uv.lock` (torch's CPU build), and installs the git hook.
- [ ] `just test` — every hermetic test.
- [ ] `just fmt` — formats the code.
- [ ] `just lint` — checks it against the rules in `pyproject.toml`.
- [ ] `just check` — everything a commit must pass (the hook runs exactly this).
- [ ] `just` — lists the tasks.
- [ ] `just help VERB` — explains one task.
- [ ] `uv run babykev help` — the program's own help.
- [ ] `just test -k render` — extra arguments go to the tool behind a recipe.
- [ ] `just docs` — builds the docs site into `docs/_site/`; open `docs/_site/index.html`.
- [ ] `just docs publish` — pushes the site to the `gh-pages` branch of `origin`; only on your own fork.
- [ ] `just docs list` — every module, class and function with its summary.
- [ ] `just docs module api` — prints one module.
- [ ] `just docs check` — counts what is typed and documented and lists every gap.
- [ ] `just smoke local` — the whole thing end to end on the real Qwen2.5-0.5B (about 1 GB the first time).
- [ ] `just test -m system` — the one non-hermetic test (the Hub, the weights, a device).
- [ ] `just types` — ty, the type checker.

*In Docker* (`babykev/README.md:102-116`; step-05b only)
- [ ] `just image build dev` — builds the dev image.
- [ ] `just image shell` — a shell in a new container with this folder mounted at `/work`; run `just check` there.
- [ ] `just image start` — keeps one dev container running in the background.
- [ ] `just image stop` — removes it.
- [ ] `just image build run` — builds the run image.
- [ ] `just image run smoke` — the smoke in the run image, on the CPU.
- [ ] `just image build run --platform linux/amd64` — the architecture most platforms run; emulated and about 3.5× slower on Apple Silicon (G22).
- [ ] `just image shell --network none` — a shell with no network, where `just check` still passes.

*How the history is organised* (`babykev/README.md:148-150`)
- [ ] `git tag -n1 --list 'step-*'` — the steps, one line each.
- [ ] `git show step-00` — a step's full note, and what it changed.
- [ ] `git switch --detach step-00` — the project as it was at that step.
- [ ] `just setup` — *(extra)* after each switch; most steps add packages, and from step-03 on it also reinstalls the hook.

### Guest lecture · the walk, step by step (`walk.md`)

*The walk page has many more commands than these; this list keeps the ones §4 Track B walks through. Numbers in parentheses are `walk.md` lines.*

*step-00: environment and interface*
- [ ] `uv sync --locked` — (22) creates `.venv` from `uv.lock`, with Python 3.13 from `.python-version`.
- [ ] `just --show setup` — (26) shows the command behind a recipe.
- [ ] `just` — (33) lists the recipes.

*step-01: the contract and its tests*
- [ ] `uv run pytest` — (65) **52 runs, 2 fail**, "and the tests are right".
- [ ] `just test -k "score_confidence_is_zero or rounded_probabilities"` — (71) just the two failures.

*step-02: format and lint*
- [ ] `just setup` — (112) adds ruff.
- [ ] `just test -k score_confidence_is_zero` — (120) the first fixed test passes.
- [ ] `just test -k rounded_probabilities` — (124) the second fixed test passes.
- [ ] `just test` — (137) 52 passed; `api.py` has **1 missed** line (90), the new `if L == 1` branch.
- [ ] `uv run ruff format --check` — (150) "1 file would be reformatted".
- [ ] `just fmt` — (158)
- [ ] `uv run ruff check --statistics` — (181) 70 findings.
- [ ] `just lint --fix` — (190) 69 left.
- [ ] `just lint --fix --unsafe-fixes` — (195) 37 left, which "need a person".

*step-03: the hook*
- [ ] `uv run pre-commit install` — (224) writes the git hook.
- [ ] `ls "$(git rev-parse --git-path hooks)"` — (229) shows it.
- [ ] `just check` — (249) format check, lint, tests with `--cov-fail-under=90`, config lint.
- [ ] `just test -k confidence --cov-fail-under=90` — (253) fails the floor (49.40%).
- [ ] `uv run yamllint --strict .` — (259) the walk then breaks `.pre-commit-config.yaml` with a `sed`, shows the error and restores it with `git restore` (259-262).
- [ ] `uv run validate-pyproject pyproject.toml` — (266) same pattern for `pyproject.toml` (266-269).
- [ ] `uv lock --check` — (273) same pattern for a stale lockfile (273-276).
- [ ] `just --fmt --check --unstable` — (280) same pattern for the `justfile` (280-283).
- [ ] `just lint-config` — (288) all four config checks in one recipe.
- [ ] `perl -pi -e 's/^(from typing)/import os\n$1/' src/babykev/api.py` — (296) adds an unused import.
- [ ] `git commit -am "try"` — (297) `just check...Failed`, F401.
- [ ] `git restore src/babykev/api.py` — (302) undo.
- [ ] `echo X=1 > .env && git add -f .env` — (306) stage a secret on purpose.
- [ ] `git commit -m "try"` — (307) `no .env file...Failed`.
- [ ] `git rm --cached -q .env && rm .env` — (311) undo.

*steps 04/04b: docs as a check (skim)*
- [ ] `just docs check` — counts the gaps; from step-04b it is part of `just check`, so a missing docstring or comment blocks a commit.

*step-05: green but wrong*
- [ ] `uv run python -c "from babykev.model import branch_mask; m = branch_mask([0, 0, 1, 1, 2, 2], 'cpu')[0, 0] == 0; print('\n'.join(''.join('#' if x else '.' for x in r) for r in m))"` — (589) rows 5-6 print `#####.` / `######`; they should be `##..#.` / `##..##`.

*step-05a: tests that could tell*
- [ ] `just test` — (623) 103 passed.
- [ ] `perl -pi -e 's/^    same = \(s\[None, :\] == s\[:, None\]\) \| \(s\[None, :\] == 0\)$/    same = (s[None, :] == s[:, None]) | (s[None, :] == 0) | (s[None, :] < s[:, None] - 1)/' src/babykev/model.py` — (651) injects a wrong "fix".
- [ ] `just test -k no_question_sees_another` — (653) hypothesis shrinks the counter-example to `shape = (1, [1, 1, 1])`.
- [ ] `git restore src/babykev/model.py` — (654)
- [ ] `perl -pi -e 's/^    same = \(s\[None, :\] == s\[:, None\]\) \| \(s\[None, :\] == 0\)$/    same = torch.ones_like(causal) | (s[None, :] == 0)/' src/babykev/model.py` — (667) puts step 05's mask line back.
- [ ] `just test` — (668) **8 failed, 95 passed** (3 mask tests, 4 isolation tests, the notebook test).
- [ ] `git restore src/babykev/model.py` — (669)
- [ ] `just types` — (679) ty passes after the two guards.
- [ ] `just --show check` — (683) `types` now sits between `lint` and the tests.

*step-05b (optional): non-hermetic tests behind a marker, and Docker*
- [ ] `docker build --target run --tag babykev-run .` — (719) the run image.
- [ ] `docker build --target dev --tag babykev-dev .` — (736) the dev image.
- [ ] `just image build dev` — (758) the same through the recipe.
- [ ] `just image build run` — (759)
- [ ] `just test` — (813) "103 passed, 1 deselected".
- [ ] `just test -m system` — (814) loads the real model (about 1 GB the first time).
- [ ] `just image shell --network none` — (818) a dev container with no network.
- [ ] `just check` — (822) inside it: green.
- [ ] `just test -m system` — (826) passes too, but only because the model is in the mounted cache.
- [ ] `HF_HOME=/tmp/empty just test -m system` — (830) fails: it can't reach the Hub.
- [ ] `exit` — (831)
- [ ] `just image stop` — (the walk runs it at 772) removes a dev container started with `just image start`; then `docker image rm` the babykev images when you are done.

---

## 1. What you build

The tutorial and the guest lecture teach one idea: **every change must pass a gate before it lands**. You don't build a new app. You take a small FastAPI service, `api.service:app`, whose one maths endpoint `/euclidean_distance/` calls a helper `power()` in `api/utils.py`. You surround it with three test layers:

- **unit**: `power()` called directly
- **integration**: the FastAPI app called in-process through `TestClient`
- **system**: real HTTP to a live uvicorn server on port 9000

All three run inside the same Docker image that serves the app. You then add a **pre-commit hook**. On every `git commit` it trims whitespace, fixes the end of each file, validates YAML/JSON, blocks files over 1000 KB, private keys and merge markers, auto-formats with **black** (120 columns) and lints with **flake8**, all before the commit is allowed to exist.

The guest lecture's `babykev` shows the same gate on a real ML project, with no Docker until the last step. There `uv` pins the environment, `just` gives each task one name, and the hook runs one command, `just check`: format check, lint, type check, tests with a coverage floor, docs check and config linting. It also shows why a fully green gate can still let a wrong model through.

```
 YOUR LAPTOP  (e.g. /Users/conny/Desktop/AC215/cheese-app-ci-cd, a git clone)
 ┌────────────────────────────────────────────────────────────────────────────────────┐
 │  working tree ──git commit──► .git/hooks/pre-commit   (written by `pre-commit install`)│
 │       │                              │ reads .pre-commit-config.yaml                  │
 │       │                              ▼                                                │
 │       │            ~/.cache/pre-commit/  isolated envs, downloaded on first run:      │
 │       │            pre-commit-hooks v4.5.0 │ black 24.1.1 │ flake8 7.0.0              │
 │       │                              │                                                │
 │       │               all Passed ────┴──── any Failed / files modified                │
 │       │                  ▼                         ▼                                  │
 │       │            commit created            commit ABORTED (re-stage, retry)         │
 │       │                                                                               │
 │       │  docker build -t cheese-app-api:local .      (build context = repo root)      │
 │       ▼                                                                               │
 │  Docker Engine (Linux) / Docker Desktop VM (Mac, Windows)                             │
 │  ┌─ image cheese-app-api:local  (FROM python:3.11-slim-bookworm, USER app uid 1000) ─┐ │
 │  │  /app/api/  /app/tests/  /app/pytest.ini  /app/docker-entrypoint.sh  (COPY'd,    │ │
 │  │  i.e. BAKED IN, no volume)   /home/app/.local/bin: uvicorn pytest black flake8   │ │
 │  └──────────────────────────────────────────────────────────────────────────────────┘ │
 │   (a) docker run --rm cheese-app-api:local pytest tests/unit/ | tests/integration/      │
 │        ┌ container ───────────────────────────────┐                                  │
 │        │ pytest ─► power()           (unit)        │   no network, no server         │
 │        │ pytest ─► TestClient ─► app (in-process)  │                                  │
 │        └───────────────────────────────────────────┘                                  │
 │   (b) docker run -d --name api-server -p 9000:9000 -e DEV=1 cheese-app-api:local       │
 │        ┌ container "api-server" ───────┐   host:9000 ◄── browser http://localhost:9000│
 │        │ uvicorn api.service:app :9000 │◄──────────────────────────────┐              │
 │        └───────────────────────────────┘                                │              │
 │   (c) docker run --rm --network host cheese-app-api:local pytest tests/system/ -v      │
 │        ┌ container (shares host network) ┐  HTTP GET localhost:9000 ────┘              │
 │        │ pytest + requests               │  (skips 4 tests if unreachable)            │
 │        └─────────────────────────────────┘                                            │
 └────────────────────────────────────────────────────────────────────────────────────┘
        │ git push (lecture 21)
        ▼
 GitHub Actions .github/workflows/ci.yml:  build ─► {lint-and-format, unit-tests,
 integration-tests, system-tests} ─► test-summary (─► optional Slack via SLACK_WEBHOOK_URL)

 GUEST LECTURE (no Docker until step-05b)
 babykev-walk/  ── just present ── uvx timewalk ──► browser page: steps 00..05b, notes, terminals
   ├─ repo/      clone of babykev (`just setup` makes it)  ──┐
   └─ worktree/  timewalk's replay copy at a step         ──┤
                                                           ▼
 babykev/  uv sync --locked ─► .venv (Python 3.13)     git commit ─► .git/hooks/pre-commit
           just fmt | lint | types | test | docs | lint-config      ├ check-added-large-files
                       └──────────── just check ◄──────────────────┤ check-merge-conflict
                                                                    ├ no-env-file (language: fail)
                                                                    └ just check (always_run)
```

---

## 2. Prerequisites and costs

**Accounts**

- A GitHub account. You need it only to push your own copy; Part 4 works entirely on your machine. A fresh `git clone` of `dlops-io/cheese-app-ci-cd` has `origin` pointing at dlops-io, so any `git push` (README Parts 5–7) is rejected. Use a fork, or point the code at your own repo, e.g. your planned `JunyiZhou-Conny/MLOps_Learning`. See gotcha G12 before you nest the course repos inside it.
- No GCP account and no cloud keys are needed for L09.
- Optional, for lecture 21 only: a Slack incoming webhook stored as the GitHub secret `SLACK_WEBHOOK_URL` (`.github/workflows/ci.yml:197`, `:256`).

**Local installs (cheese-app-ci-cd)** — README lines 5–9: "Have Docker installed", "Python 3.9+ installed locally", "Git installed", "GitHub account".

- Docker Desktop (Mac/Windows) or Docker Engine (Linux). The base image `python:3.11-slim-bookworm` (`Dockerfile:2`) is multi-arch, so it builds natively on Apple Silicon.
- `pre-commit` on the **host**, not in the container (README:238 says "Outside the container"). The container image does include `pre-commit` (`pyproject.toml:12`), but it has no `.git` folder, so it can't install hooks there.
- Optional, for README Part 2 "Option B" and the "Run Locally" section: `black`, `flake8`, and for local pytest `pytest`, `fastapi`, `httpx`, `pytest-asyncio`, `requests`. The README only tells you to install black and flake8. See gotchas G7 and G8.

**Local installs (guest lecture)** — `babykev-walk/README.md:10-14`:

- uv, git, just, Quarto (1.4 or newer; `babykev-walk/justfile:47-52`) and a recent browser. Docker only for the optional step-05b (walk.md:701-841); the walk README does not list it.
- Everything else comes from `uv.lock` through babykev's own `just setup` (`babykev/justfile:28-34`, run inside `repo/`, not the walk's `setup` recipe): pydantic, pytest, ruff, pre-commit, torch (CPU build), ty, hypothesis, hadolint and the rest (`babykev-walk/slides/00-start.md:137-138`).
- The walk's commands are written for macOS. "On Linux, `sed -i ''` is `sed -i`, and `open` is `xdg-open`" (`babykev-walk/README.md:66`).

**Secrets and keys:** none are needed. Know where they would be caught:

- cheese `.gitignore:48-52` ignores `secrets/`, `*.key`, `*.pem`, `.env`.
- The cheese hook `detect-private-key` (`.pre-commit-config.yaml:25-26`) blocks files containing private-key headers. A GCP service-account JSON contains `-----BEGIN PRIVATE KEY-----`, which matters from L10 onward, where the app expects keys in `../../../secrets/` (e.g. `cheese-app-v1/src/api-service/docker-shell.sh:9`).
- babykev's hook refuses any `.env` (`babykev/.pre-commit-config.yaml:14-18`).

**Costs and clean-up:** there is nothing billable on GCP. What you spend is disk and bandwidth:

| Resource | Size / cost | How to remove |
|---|---|---|
| `cheese-app-api:local`, `cheese-app-api-service` (from `docker-shell.sh`), maybe `cheese-app-test` (README:548) | python slim + build-essential + deps | `docker stop api-server && docker rm api-server` (README:199), then README "Docker Cleanup" (lines 568-574): `docker container ls`, stop containers, `docker system prune`, `docker image ls` |
| pre-commit hook environments | `~/.cache/pre-commit/` | `pre-commit uninstall` (removes `.git/hooks/pre-commit`), `pre-commit clean` (removes the cache). Neither command is in the README. |
| babykev `.venv` with CPU torch | "a few hundred megabytes" (`babykev-walk/README.md:68-69`) | delete `.venv/` |
| Qwen2.5-0.5B weights (only for `just smoke local` / `just test -m system`) | "about 1 GB" (`babykev-walk/README.md:69-70`) | delete it from `~/.cache/huggingface` |
| babykev images (step-05b) | run 1.15 GB, dev 1.84 GB (walk.md step-05b, "Two images from one lockfile") | `just image stop`, then `docker image rm` |
| GitHub Actions (lecture 21) | free for public repos; private repos use the account's monthly minutes | — |

---

## 3. Concepts this tutorial teaches

### 3.1 The testing pyramid: unit → integration → system (and smoke, acceptance)

- **Explanation.** A test exercises some slice of the program.
  - **Unit:** one function alone (`power(2, 3) == 8`).
  - **Integration:** several of *our* parts together. Here: routing, validation, the handler and `power()`, called through FastAPI's `TestClient`, which calls the ASGI app in-process with no socket.
  - **System / end-to-end:** the real running program over real HTTP (`requests.get("http://localhost:9000/...")`).
  - babykev adds two more. **Smoke**: does the whole thing start and answer at all? **Acceptance**: is a promise to users kept, e.g. a 50 ms answer? babykev has a smoke (`just smoke local` from step-05, and from step-05b the `system`-marked `tests/system/test_real_model.py`), but no acceptance test yet ("Acceptance: none yet", walk.md:797; `slides/05b-images.md:109`).
- **Mental model.** Each layer widens the box of code that runs. Lower layers are fast, numerous and precise about *where* a bug is. Higher layers are slow, few, and realistic about *whether* the system works. Stacked, they form a pyramid: its width is the number of tests, its height the cost per test.
- **Analogy.** Testing a car: unit = bench-test the spark plug; integration = run the engine on a stand; system = drive it round the block.
- **Common misconception.** "The file name or folder decides the kind." babykev says explicitly: "A test's name says what it calls, not what kind of test it is … when you call a test an integration test, say what runs in it" (walk.md step-05 "G. Kinds of tests"). The cheese repo shows the confusion itself:
  - `tests/system/test_system_api.py:2` calls its system tests "Integration tests".
  - `pytest.ini:22` defines `integration` as tests that "require running services", which is the opposite of README:147.

### 3.2 pytest mechanics

- **Explanation.**
  - pytest **discovers** tests by convention, set in `pytest.ini:5-8`: files `test_*.py`, classes `Test*`, functions `test_*`.
  - It **rewrites `assert`** so a failure shows both values.
  - `pytest.approx` compares floats with a tolerance; `pytest.raises` asserts that an exception happens.
  - **Markers** (`@pytest.mark.skipif`, `@pytest.mark.asyncio`, babykev's `system`, applied to a whole file with `pytestmark = pytest.mark.system` in `babykev/tests/system/test_real_model.py:14`) tag or condition tests. `-m` selects by marker and `-k` by name.
  - **Fixtures** are named arguments that pytest builds and injects: built-ins like `monkeypatch` and `capsys`, and your own in `conftest.py`, each with a scope.
  - `@pytest.mark.parametrize` turns one function into N tests.
  - `addopts` in `pytest.ini:12-17` (or babykev's `pyproject.toml:56`) adds flags to every run.
- **Mental model.** pytest is a collector plus a dependency-injection container. It finds functions, works out what each one asks for, builds it, calls the test, and reports.
- **Analogy.** A lab technician with a checklist. They find every form labelled `test_`, fetch the requested equipment (fixtures) from the stock room (`conftest.py`), run the experiment, and record pass, fail or skip.
- **Misconception.** "A function in a test file is a test." Only `test_*` names are collected. README Part 6 (line 388) relies on this misconception without noticing (see Errata E2).

### 3.3 Hermetic vs environment-dependent tests: "skipped" is not "passed"

- **Explanation.** A test is *hermetic* when only your code can make it fail: no network, no download, no GPU, no running server.
  - cheese unit and integration tests are hermetic.
  - cheese system tests are not. They need a server on `localhost:9000`, and they protect themselves with `@pytest.mark.skipif(not is_api_running(), ...)` (`tests/system/test_system_api.py:24`). So if the server is down or unreachable, 4 tests are **skipped** and the run is still green.
  - babykev makes this the rule for what may go in the commit hook: "can anything but our code make it fail? Only the checks where the answer is no belong in the hook" (`slides/05b-images.md`, "What should not go in the hook?").
  - babykev proves it by running `just check` in a container started with `--network none` (walk.md step-05b, section I).
- **Mental model.** Each test has a list of things it depends on. Hermetic tests depend on your code alone, so they are safe to run on every commit. The rest go behind a marker (`-m system`) or into CI with explicit set-up (CI waits for the server with `curl -f`, `ci.yml:150-154`, so with no server the run fails loudly instead of skipping).
- **Analogy.** A smoke detector that switches itself off when the battery is missing will never beep, and that is not the same as "no fire".
- **Misconception.** "Green means everything ran." Read the `-ra` summary (`pytest.ini:17`): it lists SKIPPED tests and their reasons.

### 3.4 Formatter vs linter (and why their settings must agree)

- **Explanation.**
  - A **formatter** (black; ruff format in babykev) *rewrites* code into one canonical layout and never changes behaviour.
  - A **linter** (flake8; ruff check) *reports* problems: style (E/W codes), likely bugs (F401 unused import, F821 undefined name), complexity.
  - The formatter fixes what is mechanical. The linter flags what needs a person.
  - The two must share settings. The cheese repo uses 120 columns in the hook and CI (`.pre-commit-config.yaml:34`, `:43`; `ci.yml:61`, `:66`), but black's default is 88 and flake8's is 79. Several README commands pass no width (README:112, 121, 124, 495-496, 502-504), so they give different answers. babykev sets `line-length = 100` once in `pyproject.toml:65`, shared by the formatter and the linter.
  - Concretely: line 15 of `service.py` is 95 characters. At width 88 black folds it into three lines; at width 120 black joins it back into one (there is no magic trailing comma). Two tools at different widths undo each other's work.
- **Mental model.** The formatter is a deterministic function `f(code) → code`: run it twice and nothing changes the second time. The linter is a predicate `g(code) → findings`. Run the formatter first, then the linter.
- **Analogy.** The formatter is a spell-checker's auto-correct for layout. The linter is the copy-editor's red pen, saying "this sentence is ambiguous".
- **Misconception.** "black fixes everything flake8 reports."

  Measured on the repo's pre-demo messy version (`git show 8eb63fc:src/api-service/api/service.py`), flake8 at 120 reports: F401 `os` unused, E302 ×2, E225, E231 ×2, E501 (187 > 120), W391 in `service.py`; E231 and E303 in `utils.py`. After `black --line-length 120`, two remain:

  ```
  api/service.py:10:1: F401 'os' imported but unused
  api/service.py:48:121: E501 line too long (147 > 120 characters)
  ```

  black cannot delete an import or split a string. The class demo commit `c3b227f` fixed exactly these two by hand: it commented out `import os` and shortened the message.

  babykev tells the same story at a larger scale: 79 findings, then 70 after `just fmt`, 69 after `--fix`, 37 after `--unsafe-fixes`. The remaining 37 "need a person" (`slides/02-format-lint.md`).

### 3.5 Git hooks and the pre-commit framework (the gate)

- **Explanation.**
  - Before git creates a commit, it runs the executable `.git/hooks/pre-commit` if it exists. A non-zero exit aborts the commit.
  - `pre-commit install` writes that file. The file only hands over to the pre-commit tool, telling it which config to read (`babykev-walk/slides/03-check.md:14-31`, "What `pre-commit install` writes").
  - The pre-commit tool reads `.pre-commit-config.yaml`. It downloads each `repo:` at its pinned `rev` into an isolated environment the first time. Then it runs every hook on the **staged** files that match each hook's `files:` regex, after stashing unstaged changes.
  - A hook that *modifies* a file (black, end-of-file-fixer, trailing-whitespace) is reported as Failed ("files were modified by this hook"). You inspect the change, `git add` it and commit again.
  - `pre-commit run --all-files` runs the same thing on every tracked file without committing.
  - babykev collapses the project checks into a single local hook, `entry: just check` with `always_run: true` and `pass_filenames: false`, "so the hook and the terminal run the same thing" (`babykev/.pre-commit-config.yaml:3-4`).
- **Mental model.** A turnstile in front of history. The hook folder lives in `.git/`, which is not part of the repository, so every clone must run `pre-commit install` again. babykev's `just setup` does it for you (`babykev/justfile:33`).
- **Analogy.** Airport security. You can walk up and argue, but nothing boards until every scanner passes. If a scanner tidies your bag (black), you must re-pack it (`git add`) and queue again.
- **Misconceptions.**
  - "The hook config is shared, so everyone's commits are checked." No: each clone must install the hook, and anyone can skip it with `git commit --no-verify`. That's why CI (lecture 21) repeats the checks on the server.
  - "pre-commit uses my installed black." No: it uses its own pinned `rev` (black 24.1.1, `.pre-commit-config.yaml:30`). The container uses whatever `black>=24.1.1` resolves to (`pyproject.toml:8`).

### 3.6 Coverage is not correctness; properties beat examples

- **Explanation.**
  - Coverage measures which lines *ran* during the tests, not whether their results were checked.
  - `--cov=api` in the cheese repo; babykev runs `--cov=babykev --cov-report=term-missing` on every run (`babykev/pyproject.toml:56`) and adds a floor `--cov-fail-under=90` in `just check` (`babykev/justfile:152`). Milestone 5 requires at least 70% (`milestone5.md:48`).
  - babykev at step-05 is "All green, and the mask is wrong" (walk.md:587; the tag's own message is "A second file: model.py"): 92 tests, 94% coverage, 139/139 documented, and `branch_mask` still lets question 2 attend to question 1. Lines 137-141 of `model.py` at `step-05` hold the mask code; line 140 is the bug:

    ```
    same = torch.ones_like(causal) | (s[None, :] == 0)
    ```

  - In the mask grid for six tokens `[0, 0, 1, 1, 2, 2]` (state = tokens 1-2, question 1 = tokens 3-4, question 2 = tokens 5-6), coverage counts every line of `branch_mask` as run, yet rows 5-6 come out `#####.` / `######` instead of `##..#.` / `##..##` (§4 B7).
  - Step 05a adds **property-based tests** with hypothesis (`tests/unit/test_mask.py:10`, `:58-65`). They state the rule for any shape. When a deliberately wrong "fix" is injected, hypothesis finds and *shrinks* a counter-example to `shape = (1, [1, 1, 1])` (walk.md step-05a D).
  - babykev's view of the `Missing` column: "It is a list of lines nobody has asked a question about", not "a score to maximise" (walk.md step-02 A).
- **Mental model.** Coverage is a *necessary* signal (unrun code is untested code) but never a *sufficient* one.
- **Analogy.** Coverage shows that a proof-reader looked at every page, not that they understood any of them.
- **Misconception.** "100% coverage means bug-free." Also: "write a test just to hit the line". babykev deletes or justifies, it doesn't pad.

### 3.7 One environment, one command: reproducibility for the gate

- **Explanation.** A check is only trustworthy if every person, the hook and CI run it in the same environment with the same command.
  - The cheese repo gets the same environment from the **Docker image**. "All tests run inside Docker containers to ensure consistency with the CI environment" (README:161). CI builds the image once and tags it with the commit SHA (`ci.yml:27`).
  - babykev gets it from **`uv.lock`**: `uv sync --locked`, with `UV_LOCKED=1` exported in `justfile:9`. It gets the one command from **`just`**: the hook, people and agents all call `just check`. babykev has no CI workflow yet; its dev image is meant for "checking it the way a CI runner would" (`babykev/README.md:99`), so CI would call the same `just check` later.
  - babykev separates **dev dependencies** (`[dependency-groups]` test/lint/dev, `pyproject.toml:26-40`) from runtime ones. The cheese `pyproject.toml:7-19` installs black, flake8, pre-commit and pytest *as runtime dependencies* of the production image.
- **Mental model.** Environment = (base OS image or Python version) + locked dependency set + the exact command. Change any of the three and "it works on my machine" returns.
- **Analogy.** A recipe card (just recipe) cooked in a standard kitchen (image or lockfile) gives the same dish everywhere.
- **Misconception.** "`pip install -r` or `>=` pins is reproducible." `black>=24.1.1` gives a different black next month. babykev's `uv lock --check` (`justfile:127`) fails if the lockfile is stale.

### 3.8 What belongs where: hook vs CI vs manual

- **Explanation.** Fast, hermetic checks run on every commit (cheese: formatting and lint only; babykev: everything in `just check`, ~2–25 s). Slow or environment-dependent checks run in CI or by hand: cheese system tests run in CI against a started server; babykev's `-m system` runs only on request. Other hook moments, such as `pre-push` for slower checks, are listed in `slides/03-check.md` ("Other moments git can run a hook").
- **Mental model.** A ladder: editor → pre-commit hook → CI on push or PR → branch protection (README Part 6) → deploy (L23). Each rung is slower and more trusted.
- **Misconception.** The course site says the pre-commit hooks run "linters, formatters and tests" (`tutorials_demo.md:134`). The cheese config has no test hook; only babykev's does (through `just check`).

---

## 4. Step-by-step walkthrough

Commands copied from the README are marked **(README:line)**. Commands this guide adds are marked *(suggested, not in README)*. Run everything from the repo root unless the step says "inside the container".

### Track A — `cheese-app-ci-cd` (Parts 1-4)

**A0. Get the code.**
- The README only says "Clone or download from your repository" (README:20). The URL comes from `tutorials_demo.md`. *(suggested, not in README)*:
  ```bash
  cd /Users/conny/Desktop/AC215
  git clone https://github.com/dlops-io/cheese-app-ci-cd.git
  cd cheese-app-ci-cd
  git log -1 --format='%H %ci'      # expect b8458ff0cc1898700b32a873b4665f43f50df71e 2025-11-13 ...
  ```
- Checkpoint: the project tree matches README:23-47 (the README tree leaves out `.gitignore`, `README.md`, `assets/pipline.png` and `tests/__init__.py`, which are also there).
- Optional: `git log --oneline` shows the story of the class demo. `91eb786` "readd messy code", then `c2dce32` "with wrong variable" (`math.sqrt(a)`), then `8eb63fc` "fixed the a problem", then `c3b227f`/`b8458ff` "demo class 1" (service.py cleaned, a bug `math.sqrt(2 * z)` injected and then removed).

**A1. Part 1 — build and enter the dev container.** **(README:73)**
```bash
sh docker-shell.sh
```
- Under the hood, `docker-shell.sh:7` sets `IMAGE_NAME="cheese-app-api-service"`. Line 11 runs `docker build -t $IMAGE_NAME -f Dockerfile .`. Lines 15-18 run `docker run --rm -ti --name $IMAGE_NAME -p 9000:9000 $IMAGE_NAME /bin/bash`.
- The image (`Dockerfile:2-52`):
  - installs `build-essential` and `curl`, then creates user `app` uid 1000 (lines 12-28)
  - copies only `pyproject.toml` and runs `pip install --no-cache-dir --user .` (lines 32-35), so the dependencies land in `/home/app/.local`
  - copies `src/api-service/api/` to `/app/api/`, plus `tests/`, `pytest.ini` and the entrypoint (lines 38-41)
- `ENTRYPOINT ["/bin/bash", "docker-entrypoint.sh"]` (line 52) puts `/home/app/.local/bin` on `PATH` (`docker-entrypoint.sh:5`). Because an argument (`/bin/bash`) was passed, it `exec`s that (lines 10-13).
- **You should see** `Container is running!!!`, then `Executing command: /bin/bash`, then a prompt like `app@<id>:/app$`.
- If it fails:
  - "Cannot connect to the Docker daemon": start Docker Desktop.
  - "port is already allocated": something already uses 9000 (G4).

**A2. Start the server inside the container.** **(README:82)**
```bash
uvicorn api.service:app --host 0.0.0.0 --port 9000 --reload
```
- `api.service:app` resolves because the working directory is `/app` and `api/` sits there. `--host 0.0.0.0` makes the server reachable through the published port.
- **Check in a browser** (README:88-90):
  - `http://localhost:9000` gives `{"message":"Welcome to the Cheese App CI/CD Tutorial!"}` (`service.py:28-30`)
  - `/health` gives `{"status":"healthy"}` (`service.py:33-35`)
  - `/euclidean_distance/?x=3&y=4` gives a JSON object, not a bare number: `"x":3.0`, `"y":4.0`, `"distance":5.0`, and a `"message"` (`service.py:38-50`). README:90 says "returns 5.0".
- Note: `--reload` watches `/app` *inside the container*. Your Mac's files are **not mounted**, so editing on the host changes nothing here (G1).
- Stop with Ctrl-C, then `exit`. `--rm` deletes the container. README:92: "Please exit and remove your container after this".

**A3. Part 2, Option A — lint inside a fresh image.** **(README:106, 109, 112)**
```bash
docker build -t cheese-app-api:local .
docker run --rm cheese-app-api:local flake8 --max-line-length=120 api/
docker run --rm cheese-app-api:local black --check --diff api/
```
- Under the hood, `docker run IMAGE flake8 ...` goes through the entrypoint's `exec "$@"` branch (`docker-entrypoint.sh:10-13`).
- **You should see** (measured on copies of the HEAD files):
  ```
  api/utils.py:7:15: E231 missing whitespace after ','
  api/utils.py:13:1: E303 too many blank lines (3)
  ```
  black, with no `--line-length` and therefore its default of 88, reports `would reformat .../utils.py` **and** `would reformat .../service.py` (it wants to fold `service.py:15`, 95 characters), ending `2 files would be reformatted, 1 file would be left unchanged.`
- Both commands exit non-zero. That's expected: the "messy" `utils.py:7-14` is left in the repo on purpose.
- README vs code: flake8 is told 120 here but black is not. At the hook's width (120), black would only reformat `utils.py` (Errata E5). The README's Quick Command Reference has the CI-width pair (README:478-479): `docker run --rm cheese-app-api:local black --check --line-length 120 api/` and `docker run --rm cheese-app-api:local flake8 --max-line-length=120 api/`. With those, both tools flag only `utils.py`.

**A4. Part 2, Option B — the same on the host.** **(README:118, 121, 124)**
```bash
pip install black flake8
flake8 src/api-service/api/
black --check --diff src/api-service/api/
```
- With the defaults (79 and 88) you get one extra finding: `service.py:15:80: E501 line too long (95 > 79 characters)`. black wants to fold line 15.
- On a Homebrew Python, `pip install` may fail with `externally-managed-environment` (G10).

**A5. Part 3, Option 1 — unit and integration tests in the container.** **(README:169-181)**
```bash
# Build the image first
docker build -t cheese-app-api:local .

# Run unit tests only
docker run --rm cheese-app-api:local pytest tests/unit/ -v

# Run integration tests only
docker run --rm cheese-app-api:local pytest tests/integration/ -v

# Run both unit and integration tests
docker run --rm cheese-app-api:local pytest tests/unit/ tests/integration/ -v

# Run with coverage
docker run --rm cheese-app-api:local pytest tests/unit/ --cov=api --cov-report=term
```
- Under the hood, pytest reads `/app/pytest.ini`:
  - `pythonpath = .` (line 9) makes `import api` work.
  - `addopts` (lines 12-17) adds `-v --tb=short --strict-markers --disable-warnings -ra`.
- Unit tests `tests/unit/test_utils.py` exercise `power()` with integers, zero and negative exponents, floats, nan and inf, booleans, and `TypeError` on bad types (lines 13-90).
- Integration tests `tests/integration/test_api.py` build `client = TestClient(app)` once at module level (line 11) and call routes in-process. They cover 404 and 405, and CORS headers with an `Origin` header (lines 70-80).
- **Expected counts** (from reading the code; 11 / 10 / 5 `def test_` per file):
  - unit: **11 passed**
  - integration: **10 passed** (7 + 2 + 1 async)
  - both: **21 passed**
  - coverage: `api/service.py` at **0%**, because unit tests never import it; `api/utils.py` misses line 14 (`pass` in `unused_function`)
- If it fails:
  - you edited code and see the old behaviour: rebuild the image (G1)
  - `'asyncio' not found in markers`: only possible outside the image (G8)

**A6. Part 3, Option 2 — system tests against a live server.** **(README:190-199)**
```bash
# Build image first
docker build -t cheese-app-api:local .

# Start the API server
docker run -d --name api-server -p 9000:9000 -e DEV=1 cheese-app-api:local

# Run system tests against the live server
docker run --rm --network host cheese-app-api:local pytest tests/system/ -v

# Clean up when done
docker stop api-server && docker rm api-server
```
- Under the hood:
  - With no command, the entrypoint takes the server branch. `DEV=1` selects `uvicorn ... --reload --log-level debug` (`docker-entrypoint.sh:16-19`). Without it you get PROD, `--workers 4` (line 23).
  - The test container shares the host's network namespace, so `localhost:9000` in `test_system_api.py:12` reaches the published port.
  - `is_api_running()` (lines 15-21) probes `/health` with a 2 s timeout *at import time*, and decides the class-level `skipif` (line 24).
- **You should see 5 passed**: 4 in `TestAPIEndpoints` plus `TestAPIWithoutServer::test_api_structure`.
- If you see `1 passed, 4 skipped` plus a `SKIPPED ... API not running at localhost:9000` line from `-ra`, the server wasn't reachable when the tests were *collected*. Check `docker ps` and `docker logs api-server`.
  - Wait for readiness *(suggested, not in README; mirrors `ci.yml:150-154`)*:
    ```bash
    until curl -sf http://localhost:9000/health; do sleep 1; done
    ```
  - Or run the tests inside the server's own container *(suggested)*: `docker exec api-server python -m pytest tests/system/ -v`. Use `python -m pytest` because `docker exec` doesn't go through the entrypoint's PATH line (G6).
- README:202 notes the skip behaviour ("System tests will skip if the server isn't running").

**A7. Part 3, Option 3 — interactive.** **(README:210, 216-225)**
```bash
sh docker-shell.sh
```
then inside the container:
```bash
pytest tests/unit/ -v
pytest tests/integration/ -v
pytest tests/unit/ tests/integration/ -v
pytest tests/unit/ --cov=api --cov-report=html
```
- The HTML report goes to `/app/htmlcov/` inside a `--rm` container with no mount. It disappears on `exit`, and your host browser can't open it (G13). Prefer `--cov-report=term-missing` *(suggested)*.
- README:228 says to start the server "in another terminal" for system tests. Starting `api-server` from Option 2 now collides with this container's `-p 9000:9000` (G4). Even without the collision, this container was not started with `--network host` (`docker-shell.sh:15-18`), so `localhost:9000` inside it is the container itself, not the other server, and the 4 live-server tests would skip.
- What works instead *(suggested)*: inside this same container, run `uvicorn api.service:app --host 0.0.0.0 --port 9000 &`, then `pytest tests/system/ -v`.

**A8. Part 4 — install pre-commit on the host.** **(README:240, 246)**
```bash
pip install pre-commit
```
```bash
# From the root directory
pre-commit install
```
- Under the hood, `pre-commit install` writes `.git/hooks/pre-commit`. **You should see** `pre-commit installed at .git/hooks/pre-commit`.
- It must run inside the git clone. The README says "From the root directory"; pre-commit itself moves to the repository's top level and reads `.pre-commit-config.yaml` there, which is why nesting matters (G12).
- If `pip install` is refused (PEP 668), use `brew install pre-commit`, `pipx install pre-commit` or `uv tool install pre-commit` *(suggested)*.

**A9. Run all hooks once.** **(README:262)**
```bash
pre-commit run --all-files
```
- Order: the README shows the `git commit` example first (README:255) and this manual run after it (README:262). It is done first here so that black's fix of `utils.py` doesn't surprise you on your first commit.
- Under the hood, the first run clones `pre-commit/pre-commit-hooks@v4.5.0`, `psf/black@24.1.1` and `PyCQA/flake8@7.0.0` into `~/.cache/pre-commit` and builds their environments (`[INFO] Initializing environment for ...`). This needs internet the first time.
- Then it runs the 9 hooks in `.pre-commit-config.yaml:12-44`. black and flake8 only see files matching `^src/.*\.py$` (lines 35, 44).
- **Expected on HEAD** (derived from the file contents, not executed):
  - All the hygiene hooks pass: no trailing whitespace, every file ends with exactly one newline (checked), the YAML parses. `Check JSON syntax` shows `(no files to check)Skipped`.
  - **"Format Python code with Black … Failed"**, with `- files were modified by this hook` and `reformatted src/api-service/api/utils.py`.
  - flake8 runs *after* black on the now-reformatted file, so it should **pass**: black fixes both E231 and E303.
- `git diff` then shows `def power(base, exponent):` and one blank line removed.
- `pre-commit run` (no `--all-files`, README:265) only checks **staged** files. With nothing staged, every hook prints `(no files to check)Skipped`.

**A10. The commit loop.** **(README:255)**
```bash
git commit -m "Your commit message"
```
- You need something staged first, e.g. `git add -u` after A9 *(suggested)*.
- Under the hood, git runs the hook. pre-commit stashes unstaged changes and runs the hooks on the staged files. If any hook fails or modifies a file, the commit is **not created**. Review with `git diff`, `git add` again, and re-commit.
- To see flake8 block a commit *(suggested)*:
  - Add `import os` back at the top of `service.py` and stage it. You get `F401 'os' imported but unused`, which black can't fix.
  - Or, as in history `c2dce32`, use an undefined name, `math.sqrt(a)`, to get `F821 undefined name 'a'`. The linter catches a crash before runtime.
- The commit stays local. Pushing a dlops-io clone fails (§2).

**A11. (Exercise) Part 7.**
- **(README:406-409, 415-418)** Add the `/add/` endpoint and its test, then **(README:426-433)** rebuild and run `pytest tests/ -v`.
- Without a server, expect **23 passed, 4 skipped** on HEAD: 11 unit + 10 integration + the new `test_add_endpoint` + `TestAPIWithoutServer::test_api_structure`, with the 4 live-server tests skipped. Without the Part 7 test it is 22 passed, 4 skipped.
- The README:439 format check (`black --check --line-length 120 api/`) fails on a fresh clone even before you add anything: `would reformat api/utils.py` (G23). Your `/add/` code is not the cause.
- Don't use the README:442 auto-format command as written (G2).

**A12. Part 5 (lecture 21, mention only).** `.github/workflows/ci.yml` runs the same commands on GitHub. It builds the image once (lines 15-38), then runs four jobs in parallel (lint, unit, integration, system) and a summary job (lines 171-257: the result check at 178-192, the optional Slack message at 194-257).

**A13. Clean up.**
- **(README:199)** `docker stop api-server && docker rm api-server`, then README:571-574 (`docker container ls`, `docker system prune`, `docker image ls`).
- Optional: `pre-commit uninstall` *(suggested)*.

### Track B — guest lecture (`babykev-walk` + `babykev`)

**B0. The replay page** (`babykev-walk/README.md:22-26`):
```
git clone https://github.com/<you>/babykev-walk
cd babykev-walk
just present
```
- `present` depends on `setup` (`babykev-walk/justfile:16`). The first time, `setup` clones babykev into `repo/` — your fork if you have one, otherwise `rahuldave/babykev` — and fetches the `step-*` tags (lines 24-46).
- `present` then runs timewalk from GitHub, unpinned (lines 8-9, 21). timewalk keeps a replay copy in `worktree/` and starts with `--discard-edits`: "a move to another step throws away your edits there" (README:55-56).
- **You should see** `setup: repo/ is ..., with 9 steps from rahuldave/babykev` and an address to open.

**B1. Without the page** (`babykev/README.md:148-150`):
```
git tag -n1 --list 'step-*'     # the steps, one line each
git show step-00                # a step's full note, and what it changed
git switch --detach step-00     # the project as it was at that step
```
After each switch, run `just setup` *(suggested; the walk starts every step with it)*. Most steps add packages (step-01, 02, 03, 04, 05, 05b); 04b and 05a add none (walk.md:411, 608). From step-03 on, `just setup` also reinstalls the hook.

**B2. step-00: environment and interface.**
- `$ uv sync --locked` (walk.md:22) creates `.venv` from `uv.lock`, with Python 3.13 from `.python-version`.
- `just` lists the recipes; `just --show setup` shows the command behind one.

**B3. step-01: the contract and its tests.**
- `$ uv run pytest` (walk.md:65) gives **52 runs, 2 fail**, "and the tests are right". The two failures:
  - `score_confidence([1/3]*3)` returns 0.5 instead of 0 (`git show step-01:src/babykev/api.py`, lines 82-86)
  - 77 options rounded to 2 decimals sum to 0.77 (lines 89-90 and 99)
- Run just those two: `$ just test -k "score_confidence_is_zero or rounded_probabilities"` (walk.md:71).
- Fixtures and parametrize: `run` / `test_help_is_printed_for_help_and_for_no_words` (`step-01:tests/unit/test_cli.py:8-18`).

**B4. step-02: format and lint.** (walk.md order)
- `$ just setup` (walk.md:112) adds ruff. The two fixed tests pass: `just test -k score_confidence_is_zero` (120), `just test -k rounded_probabilities` (124).
- `$ just test` (137) → 52 passed, and `api.py` has **1 missed** line (90): the new `if L == 1` branch (`git show step-02:src/babykev/api.py`, lines 88-91).
- `$ uv run ruff format --check` (150) → "1 file would be reformatted".
- `$ just fmt` (158).
- `$ uv run ruff check --statistics` (181) → 70 findings, then `$ just lint --fix` (190) → 69, then `$ just lint --fix --unsafe-fixes` (195) → 37 left that "need a person".

**B5. step-03: the hook.**
- `$ uv run pre-commit install` (walk.md:224); then `$ ls "$(git rev-parse --git-path hooks)"` (229).
- `$ just check` (249) runs `fmt --check`, `lint`, tests with `--cov-fail-under=90`, and `lint-config`.
- `$ just test -k confidence --cov-fail-under=90` (253) fails the floor (49.40%).
- Config files are checked too (walk.md:255-288). `just lint-config` runs `yamllint --strict .`, `validate-pyproject pyproject.toml`, `uv lock --check` and `just --fmt --check --unstable`. The walk breaks each once with a `sed`, shows the error, and restores it with `git restore` (259-283). Then `$ just lint-config` (288). At step-05b hadolint joins this recipe (`babykev/justfile:120-128` at HEAD).
- A bad commit:
  ```
  $ perl -pi -e 's/^(from typing)/import os\n$1/' src/babykev/api.py
  $ git commit -am "try"
  ```
  (walk.md:296-297) → `just check...Failed`, F401. Restore with `git restore src/babykev/api.py`.
- A secret:
  ```
  $ echo X=1 > .env && git add -f .env
  $ git commit -m "try"
  ```
  (306-307) → `no .env file...Failed`. Undo with `$ git rm --cached -q .env && rm .env` (311).

**B6. steps 04/04b: docs as a check.** Skim this. `babykev docs check` joins `just check`, so a missing docstring or comment blocks a commit.

**B7. step-05: green but wrong.** 92 tests pass at 94% coverage. Then:
```
$ uv run python -c "from babykev.model import branch_mask; m = branch_mask([0, 0, 1, 1, 2, 2], 'cpu')[0, 0] == 0; print('\n'.join(''.join('#' if x else '.' for x in r) for r in m))"
```
(walk.md:589) prints rows 5-6 as `#####.` / `######`; they should be `##..#.` / `##..##`.

**B8. step-05a: tests that could tell.**
- `just test` → 103 passed.
- Inject the wrong fix (walk.md:651), then `$ just test -k no_question_sees_another` (653). hypothesis shrinks the counter-example to `shape = (1, [1, 1, 1])`.
- `git restore src/babykev/model.py` (654). The real fix is `model.py:151` at HEAD.
- Put step 05's mask line back (667) and `$ just test` (668): **8 failed, 95 passed** (3 mask tests, 4 isolation tests, the notebook test). Then `git restore` (669).
- ty joins the gate: `$ just types` (679) passes after the two guards, and `just --show check` (683) now has `types` between `lint` and the tests.

**B9. step-05b (optional): non-hermetic tests behind a marker, and Docker.**
- `just test` → "103 passed, 1 deselected". `$ just test -m system` (814) loads the real model (about 1 GB the first time).
- The run image (`Dockerfile:11-39`) and dev image (`Dockerfile:41-77`) are built here (walk.md:719, 736, or `just image build dev|run`, 758-759). The walk ends there: "Running on the platforms is a different class" (walk.md:848).
- Hermetic by experiment: `$ just image shell --network none` (818), then `$ just check` (822) is green. `$ HF_HOME=/tmp/empty just test -m system` (830) fails because it can't reach the Hub.

---

## 5. Code tour

### Key files — `cheese-app-ci-cd`
```
cheese-app-ci-cd/
├── Dockerfile                   one image for dev, tests and serving (python:3.11, pip --user, non-root "app")
├── docker-shell.sh              build + interactive bash, -p 9000:9000, NO volume mount
├── docker-entrypoint.sh         PATH fix; runs "$@" if given, else uvicorn (DEV=1 → --reload)
├── pyproject.toml               deps (runtime and dev tools mixed), no [build-system], no tool config
├── pytest.ini                   discovery rules, pythonpath=., addopts, (unused) markers
├── .pre-commit-config.yaml      9 hooks: 7 hygiene + black(120) + flake8(120), black/flake8 only on ^src/
├── .github/workflows/ci.yml     lecture 21: build once → lint | unit | integration | system → summary (+Slack)
├── src/api-service/api/
│   ├── service.py               FastAPI app: /, /health, /euclidean_distance/
│   └── utils.py                 power(); intentionally messy (E231, E303) + dead unused_function
└── tests/
    ├── unit/test_utils.py       11 tests of power()
    ├── integration/test_api.py  10 tests via TestClient (in-process)
    └── system/test_system_api.py 5 tests; 4 skip unless localhost:9000 answers
```

### Key files — `babykev` (HEAD = step-05b + README)
```
babykev/
├── pyproject.toml          project + dependency-groups (test/lint/dev) + pytest/ruff config
├── uv.lock, .python-version exact environment; Python 3.13
├── justfile                the interface: setup fmt lint lint-config types test check docs smoke image
├── .pre-commit-config.yaml 4 hooks; the last is `just check`
├── src/babykev/            api.py (contract), cli.py, docs.py, model.py (mask, pointer head), smoke.py
├── tests/unit/             hermetic tests (tiny model); tests/system/ = real-model test, marker `system`
├── tests/conftest.py, tests/tiny.py   fixtures; in-memory tiny tokenizer + backbone
└── Dockerfile, .dockerignore          dev and run images from uv.lock (step-05b)
```

### Excerpts

**`cheese-app-ci-cd/Dockerfile:27-41`**
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
- `USER app`: everything after this line runs as uid 1000, not root. That's good practice, but it matters for bind-mount write permissions on Linux.
- `COPY pyproject.toml` comes before the code, so code edits don't invalidate the slow `pip install` layer.
- `pip install --user .` installs the project's *dependencies* into `/home/app/.local`. There is no package code yet: only `pyproject.toml` is present at that point. The scripts land in `/home/app/.local/bin`, which is not on the default `PATH`; hence the entrypoint.
- The four `COPY` lines **bake** the code and tests into the image. Every edit means a rebuild (G1). It also means the *same artifact* is tested and shipped, which is what CI relies on.

**`cheese-app-ci-cd/docker-entrypoint.sh:5-19`**
```bash
export PATH="/home/app/.local/bin:$PATH"

echo "Container is running!!!"

# If arguments are passed, execute them instead of starting the server
if [ $# -gt 0 ]; then
  echo "Executing command: $@"
  exec "$@"
fi

# Otherwise, start the server
if [ "${DEV}" = "1" ]; then
  echo "Running in DEV mode"
  # Development: auto-reload on code changes
  uvicorn api.service:app --host 0.0.0.0 --port 9000 --reload --log-level debug
```
- Line 5 is the only place that makes `pytest`, `black` and `uvicorn` findable. `docker exec` skips it (G6).
- `exec "$@"` replaces the shell with your command, so its exit code becomes the container's exit code. That's how `docker run ... pytest` fails a CI step.
- With no arguments, the container becomes a server. `DEV=1` adds hot reload. (PROD, line 23, uses `--workers 4`.)

**`cheese-app-ci-cd/pytest.ini:4-17`**
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
pythonpath = .

# Add options for verbose output
addopts =
    -v
    --tb=short
    --strict-markers
    --disable-warnings
    -ra
```
- `python_functions = test_*` means only these names are tests (relevant to Errata E2).
- `pythonpath = .` is the *rootdir*: `/app` in the image, but the repo root on your laptop, where `api/` does **not** live (G7).
- `--strict-markers` turns an unknown marker into an error (G8).
- `-ra` prints a summary of every non-pass, including SKIPPED with reasons. Read it.

**`cheese-app-ci-cd/tests/unit/test_utils.py:69-76`**
```python
    def test_power_invalid_inputs(self):
        """Test that invalid inputs raise TypeError"""
        with pytest.raises(TypeError):
            power("3", 4)
        with pytest.raises(TypeError):
            power(3, "4")
        with pytest.raises(TypeError):
            power(None, 4)
```
- `pytest.raises` inverts the test: it passes only if the block raises `TypeError`.
- These tests pin *behaviour Python gives for free* (`"3"**4` raises). They document the contract that `power` doesn't coerce strings. Compare lines 86-90: `power(True, 5) == 1` pins that booleans *are* accepted.

**`cheese-app-ci-cd/tests/integration/test_api.py:31-38`** (the client comes from line 11, `client = TestClient(app)`)
```python
    def test_euclidean_distance_endpoint(self):
        """Test the euclidean_distance endpoint"""
        response = client.get("/euclidean_distance/?x=3&y=4")
        assert response.status_code == 200
        data = response.json()
        assert data["x"] == 3
        assert data["y"] == 4
        assert data["distance"] == 5.0
```
- `client.get` goes through FastAPI routing and query validation (`"3"` becomes float `3.0`), the handler, `power()`, and JSON serialization, with no server and no port.
- This is the test that would have caught the demo bug `math.sqrt(2 * z)` (commit `c3b227f`): it returns 7.07…, not 5.0.
- `data["x"] == 3` passes because `3.0 == 3` in Python.

**`cheese-app-ci-cd/tests/system/test_system_api.py:11-25`**
```python
# Base URL for the API (assumes API is running)
API_BASE_URL = "http://localhost:9000"


def is_api_running():
    """Check if API is accessible"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=2)
        return response.status_code == 200
    except:
        return False


@pytest.mark.skipif(not is_api_running(), reason="API not running at localhost:9000")
class TestAPIEndpoints:
```
- The URL is hard-coded to `localhost`, which is why the README needs `--network host` and why a Docker network with a service name wouldn't work without editing this line.
- `skipif(...)` is evaluated **when the module is imported (collection)**, not per test. A server that comes up a second later still leaves everything skipped.
- The bare `except:` (flake8 E722) swallows *every* error, even a typo, and turns it into "skip". flake8 never sees it because the hooks and CI lint only `src/`.

**`cheese-app-ci-cd/.pre-commit-config.yaml:28-44`**
```yaml
  # Black formatter - L17, Slide 12
  - repo: https://github.com/psf/black
    rev: 24.1.1
    hooks:
      - id: black
        name: Format Python code with Black
        args: ['--line-length', '120']
        files: ^src/.*\.py$

  # Flake8 linter - L17, Slide 8
  - repo: https://github.com/PyCQA/flake8
    rev: 7.0.0
    hooks:
      - id: flake8
        name: Check Python code with Flake8
        args: ['--max-line-length=120', '--extend-ignore=E203,W503']
        files: ^src/.*\.py$
```
- `repo` + `rev`: pre-commit installs exactly this tag in its own environment, independent of your system black.
- `args` hard-code width 120. These match CI (`ci.yml:61`, `:66`) but not several README commands (E5).
- `files: ^src/.*\.py$` is a regex on the path **relative to the git root**. Tests are excluded, and the hook stops matching if this folder is nested in another repo (G12).
- `--extend-ignore=E203,W503` silences two pycodestyle rules that contradict black's slicing and line-break style.

**`cheese-app-ci-cd/.github/workflows/ci.yml:146-158`** (lecture 21, shown for the skip lesson)
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
- CI does what the README's local Option 2 skips: it waits, then `curl -f` *fails the job* if the server is down. A silent skip can't pass CI.
- The image tag is the commit SHA, so the tested artifact equals the built artifact.

**`babykev/.pre-commit-config.yaml:5-22`**
```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v6.0.0
    hooks:
      - id: check-added-large-files
        args: [--maxkb=1000]
      - id: check-merge-conflict
  - repo: local
    hooks:
      - id: no-env-file
        name: no .env file
        entry: A .env file holds the settings and secrets of one machine. It is never committed
        language: fail
        files: (^|/)\.env$
      - id: check
        name: just check
        entry: just check
        language: system
```
(The file continues: `pass_filenames: false` and `always_run: true`, lines 23-24.)
- `repo: local` hooks are defined in this file rather than downloaded.
- `language: fail` always fails for any matching file, and prints `entry` as the message. It's a policy, not a program.
- `language: system` runs `just` from your `PATH`. That's simple, but it requires `just` in the commit environment (G16).
- `always_run` + `pass_filenames: false` run the *whole* project check on every commit, whatever files changed.

**`babykev/justfile:142-154`**
```just
# Everything a commit must pass: format, lint, types, the tests over the coverage floor, the docs, the config files
[group('quality')]
[no-exit-message]
check *args:
    #!/usr/bin/env sh
    set -e
    if [ "$*" = help ]; then just help check; exit 0; fi
    just fmt --check
    just lint
    just types
    just test -q --cov-fail-under=90
    just docs check
    just lint-config
```
- The *definition* of "acceptable commit" is in one place. People, the hook and (later) CI call the same verb.
- `set -e` stops at the first failing line. The order puts cheap checks first: format, lint, types, then tests.
- `--cov-fail-under=90` is set here and not in `pyproject.toml`, "so that `just test -k name` still works on a few tests" (walk.md step-03 C).

**`babykev/tests/unit/test_mask.py:58-65`**
```python
@given(shapes)
def test_no_question_sees_another_question(
    shape: tuple[int, list[int]],  # The lengths of a state and of its questions
) -> None:
    """A token of one question never attends to a token of another."""
    seg = torch.tensor(segments(*shape))
    siblings = (seg[:, None] != seg[None, :]) & (seg[:, None] > 0) & (seg[None, :] > 0)
    assert not (allowed(seg.tolist()) & siblings).any()
```
- `@given(shapes)` draws random request shapes from line 10: state 1–6 tokens, up to 4 questions of 1–5 tokens. The test runs up to 100 times by default and shrinks failures.
- `siblings` is a boolean matrix: "token i and token j are in two different questions".
- The assertion is a **rule**, not an example: no allowed pair may be a sibling pair.

**`babykev/tests/conftest.py:16-27`**
```python
@pytest.fixture(scope="session")
def tok() -> PreTrainedTokenizerFast:  # The tiny tokenizer, built once for the whole test run
    """Provide the tiny tokenizer."""
    return tiny_tokenizer()


@pytest.fixture
def model(
    tok: PreTrainedTokenizerFast,  # The tiny tokenizer
) -> DecisionModel:  # A decision model on the tiny backbone, with no adapter, ready to answer
    """Provide a fresh tiny model for each test, on the CPU."""
    return DecisionModel("tiny", "cpu", backbone=tiny_backbone(len(tok))).eval()
```
- A fixture is injected by name.
- `scope="session"` means one `tok` per run. The default (function) scope gives each test a fresh `model`, so no test can spoil the next.
- A fixture can ask for another fixture (`model(tok)`).
- The *tiny* model (2 layers, random fixed weights) makes model tests hermetic: no download, no GPU.
- The cheese repo's equivalent is the module-global `client = TestClient(app)` (`test_api.py:11`). A `@pytest.fixture` returning a `TestClient` would be the idiomatic upgrade (Exercise 8.7).

**`babykev/pyproject.toml:50-57`**
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."] # so that a test can import its helpers as tests.tiny
# Every run measures how much of src/babykev the tests touch and lists the lines they do not. A test
# marked system needs something besides our code (the Hub, the real weights, a device) and runs
# only when asked for: just test -m system
addopts = "--cov=babykev --cov-report=term-missing -m 'not system'"
markers = ["system: needs the network, the real model or a device; run with -m system"]
```
- This is the babykev answer to the cheese system-test problem. Instead of *skipping* at runtime, non-hermetic tests are **deselected by default** (`-m 'not system'`) and **selected explicitly** (`just test -m system`), where they must pass, not skip.
- The marker is declared (line 57), so `--strict-markers`-style checking would accept it.

---

## 6. Gotchas and common errors

| # | Symptom | Cause | Fix |
|---|---|---|---|
| G1 | You edit `utils.py` or a test, re-run `docker run --rm cheese-app-api:local pytest ...` or the `docker-shell.sh` container, and nothing changes. | Code and tests are **copied** into the image (`Dockerfile:38-41`). `docker-shell.sh:15-18` mounts no volume, so `--reload` (README:82) has nothing to reload. | Rebuild: `docker build -t cheese-app-api:local .`. Note that `sh docker-shell.sh` rebuilds its own `cheese-app-api-service` image but not `cheese-app-api:local`. Or mount just the code, `-v "$(pwd)/src/api-service/api:/app/api"` *(suggested)*. |
| G2 | README:442 auto-format command fails: `/bin/bash: docker-entrypoint.sh: No such file or directory`. | `-v $(pwd)/src/api-service:/app` hides the whole `/app` directory. The `ENTRYPOINT ["/bin/bash", "docker-entrypoint.sh"]` (`Dockerfile:52`) is relative to `/app` and is now gone, along with `tests/` and `pytest.ini`. | Mount only the package: `docker run --rm -v "$(pwd)/src/api-service/api:/app/api" cheese-app-api:local black --line-length 120 api/` *(suggested)*. On Linux, also check uid 1000 can write. Or simply let pre-commit's black do it. |
| G3 | `pytest tests/system/` is green but shows `4 skipped`. | `skipif(not is_api_running())` (`test_system_api.py:24`) probes once at import. The server was not up yet, `api-server` crashed, or the test container can't see it. | `docker ps`, `docker logs api-server`. Wait with `until curl -sf http://localhost:9000/health; do sleep 1; done` *(suggested)*. If Docker Desktop host networking is the problem, run `docker exec api-server python -m pytest tests/system/ -v` *(suggested)*. Always read the `-ra` summary. |
| G4 | `Bind for 0.0.0.0:9000 failed: port is already allocated`. | `docker-shell.sh:17` publishes 9000, and so does Option 2 (README:193). README:228 suggests combining them. A local uvicorn or another course app may also hold 9000. | `docker ps` → stop the other container, or `lsof -i :9000` on macOS *(suggested)*. |
| G5 | `Conflict. The container name "/api-server" is already in use`. | A previous Option 2 run wasn't cleaned up. The README:199 clean-up only runs if you reach it. | `docker rm -f api-server` *(suggested)*. |
| G6 | `docker exec -it <container> bash` then `pytest` gives `command not found`. | `PATH` gets `/home/app/.local/bin` only from `docker-entrypoint.sh:5`, and `docker exec` bypasses the entrypoint. | `python -m pytest ...`, or `export PATH=/home/app/.local/bin:$PATH` *(suggested)*. |
| G7 | On the host, `pytest tests/ -v` gives `ModuleNotFoundError: No module named 'api'`. | `pytest.ini:9` `pythonpath = .` points at the repo root, but the package is at `src/api-service/api`. The README Troubleshooting command (line 537) omits the fix. | `PYTHONPATH=src/api-service pytest tests/unit/ -v` (README:512) and install the deps (`pip install .` in a venv *(suggested)*). |
| G8 | On the host: `'asyncio' not found in markers configuration option`. | `test_api.py:83` uses `@pytest.mark.asyncio`, `--strict-markers` is on (`pytest.ini:15`), and `pytest-asyncio` isn't installed (the README's local section never installs it). | Install `pytest-asyncio` (it's in `pyproject.toml:13`), or run in the container. |
| G9 | black and flake8 disagree, or black keeps re-folding `service.py:15`. | Widths differ: 120 in hook and CI, black's 88 default in README:112/495-496, flake8's 79 default in README:121/502. There's no `[tool.black]` or `.flake8` config to unify them. | Always pass 120, or add `[tool.black] line-length = 120` to `pyproject.toml` and `max-line-length = 120` to a `.flake8` file *(suggested)*. black reads `pyproject.toml`; flake8 doesn't. |
| G10 | `pip install pre-commit` (README:240) gives `error: externally-managed-environment`. | Homebrew/system Python on macOS is PEP 668-protected. | `brew install pre-commit`, `pipx install pre-commit`, or `uv tool install pre-commit` *(suggested)*. |
| G11 | A commit is "Failed" though you fixed nothing wrong: `files were modified by this hook`. | black, trailing-whitespace or end-of-file-fixer **rewrote** a staged file, so the commit is aborted on purpose. | `git diff` → `git add -u` → commit again. |
| G12 | In your own monorepo (e.g. `MLOps_Learning/cheese-app-ci-cd/...`), `git commit` says `No .pre-commit-config.yaml file was found`, or black and flake8 never run, and GitHub never runs `ci.yml`. | pre-commit and GitHub Actions look only at the **repository root**. `files: ^src/.*\.py$` (`.pre-commit-config.yaml:35,44`) is relative to the root, so `cheese-app-ci-cd/src/...` never matches. Workflows must be in the root `.github/workflows/`. | Keep each course repo as its own git clone under `AC215/` (your notes repo can link to them or use submodules). If you must vendor them, move the config to the root and change the regex to `^cheese-app-ci-cd/src/.*\.py$` *(suggested)*. |
| G13 | `pytest ... --cov-report=html` (README:225): no report on your Mac. | Written to `/app/htmlcov` inside a `--rm` container with no mount. | `--cov-report=term-missing`, or mount `-v "$(pwd)/htmlcov:/app/htmlcov"` *(suggested)*. |
| G14 | The hook's black and CI's black disagree after an upgrade. | The hook pins `rev: 24.1.1` (`.pre-commit-config.yaml:30`). The image installs `black>=24.1.1` (`pyproject.toml:8`), i.e. the newest. (README:564 names this as a common issue.) | Pin the same version in both, and use `pre-commit autoupdate` deliberately *(suggested)*. |
| G15 | Messy tests never get flagged. `test_system_api.py:8` has an unused `import time` (F401); line 20 has a bare `except:` (E722). | Hooks and CI lint only `src/` (`.pre-commit-config.yaml:35,44`; `ci.yml:61,66` lint `api/`). | Widen `files:` to `^(src\|tests)/.*\.py$` *(suggested)* and fix the two findings. |
| G16 | babykev commits from a GUI (VS Code, GitHub Desktop) fail with `Executable just not found`. | `language: system` + `entry: just check` (`babykev/.pre-commit-config.yaml:20-22`) needs `just` on the GUI's `PATH`. | Start the editor from a terminal, or put Homebrew's bin on the GUI `PATH`. |
| G17 | babykev: `error: The lockfile at uv.lock needs to be updated, but --check was provided.` (or `--locked` refuses). | `UV_LOCKED=1` (`babykev/justfile:9`) refuses a stale lockfile on purpose (walk.md step-03 E). | `uv lock` on purpose, then commit `uv.lock`. |
| G18 | babykev: hypothesis `DeadlineExceeded` / `FlakyFailure`. | The first torch call can exceed hypothesis's 200 ms default, especially in containers. | Already handled by `tests/conftest.py:43-51` (deadline off). If you copy the pattern into your project, copy this too. |
| G19 | babykev walk commands fail on Linux (`sed: can't read ...`). | `sed -i ''` is BSD/macOS syntax (`babykev-walk/README.md:66`). | Use `sed -i` on Linux. |
| G20 | The walk page behaves differently from last week. | timewalk is deliberately unpinned: "each run fetches the newest" (`babykev-walk/justfile:8-9`). | Set `TIMEWALK` to a fixed source (same lines) if you need stability. |
| G21 | Your edits in the walk's terminals vanish. | `--discard-edits` (`babykev-walk/justfile:21`): moving to another step resets `worktree/`. | Work in the **Main** tab (`repo/`) and commit there (`babykev-walk/README.md:57-58`). |
| G22 | Apple Silicon. | The images here are multi-arch, so the cheese tutorial has no issue. babykev step-05b's `--platform linux/amd64` build runs under emulation, about 3.5× slower (walk.md step-05b J). | Build natively for local work; build amd64 only for deploy targets. |
| G23 | On a fresh clone, `black --check --line-length 120 api/` (README:439, :478, and CI's lint job, `ci.yml:61`) exits 1 with `would reformat api/utils.py`, before you change anything. | `utils.py:7` (`power(base,exponent)`) and the three blank lines before `utils.py:13` are left messy on purpose. Measured on copies with black 26.5.1. | Run `pre-commit run --all-files` (A9) or `black --line-length 120 src/api-service/api/` on the host, then rebuild the image. |

---

## 7. Where this sits in the course

- **Before L09.**
  - L01 taught VMs and virtual environments (uv). L02–L04 taught containers: the `docker-shell.sh` / `docker-entrypoint.sh` / non-root-user Dockerfile pattern reused here (`tutorials_demo.md:16-67`).
  - L05–L08 were the LLM block (RAG, agents, fine-tuning).
  - The numbering conflicts. `tutorials_demo.md:112` says L08 = "LLM: Finetuning" and line 139 says L10 = "Connecting to the Cloud". `_modules/week-06.md:7` calls "Connecting to the Cloud" Lecture 8 (Oct 6) and line 13 calls CI Lecture 9 (Oct 8).
- **What L09 adds.** For the first time the course is about *the process of changing code safely* rather than about running something:
  - test layers with pytest
  - formatter and linter
  - local commit gates (pre-commit)
  - the idea of a single trusted command (babykev's `just check`)
  - hermetic vs non-hermetic tests
  - coverage as a question list
- **After L09.**
  - **L10** `cheese-app-v0`: cloud credentials. This is where `detect-private-key` / `.env` hooks start to matter.
  - **L18** `cheese-app-v1/v2`: the real FastAPI backend, the same `service.py` skeleton (CORS middleware, `@app.get("/")`, compare `cheese-app-v1/src/api-service/api/service.py:1-20`). That's what you'll be testing for the milestones.
  - **L21** the *same* repo's Part 5: `.github/workflows/ci.yml` runs these hooks and tests remotely.
  - **L23** `cheese-app-v4` CI/CD (`.github/workflows/app-ci-cd-gcp.yml`, `ml-ci-cd-gcp.yml`).
  - **Milestone 4** requires CI that builds, lints and tests on every commit or PR, with unit and end-to-end tests run in CI (`milestone4.md:55-63`; its overview at line 25 names unit, integration and system tests). **Milestone 5** requires at least 70% line coverage on API and backend code (`milestone5.md:48`).
  - babykev's slide `00-start.md` says `serve.py` arrives "class on ci/cd with github actions", so babykev is likely to come back in L21.
- **Diff vs the previous version.** `cheese-app-ci-cd` is a **standalone repo**, not a branch of v0–v4. Its closest ancestor is the `cheese-app-v1` api-service skeleton. Concretely (conceptual diff, different repos):

  | Aspect | `cheese-app-v1/src/api-service` | `cheese-app-ci-cd` |
  |---|---|---|
  | Dockerfile location / context | inside `src/api-service/` | repo root (so it can `COPY tests/` and `pytest.ini`) |
  | Dependency install | `uv sync --frozen` from `uv.lock` (`Dockerfile:39-42`) | `pip install --user .` from `pyproject.toml` with `>=` pins (`Dockerfile:32-35`) — no lockfile |
  | Entrypoint | activates venv, `exec /bin/bash` | dispatcher: run `"$@"` or start uvicorn (DEV/PROD) |
  | Code in container | bind-mounted `-v "$BASE_DIR":/app` (live edits) | baked in by `COPY` (rebuild per edit) |
  | New files | — | `tests/{unit,integration,system}`, `pytest.ini`, `.pre-commit-config.yaml`, `.github/workflows/ci.yml`, `api/utils.py` |

  The repo's own history (`git diff --stat 140f138 HEAD`): `ci.yml` (69 lines changed), `docker-build.yml` deleted (62 lines), README rewritten (348 lines changed), `service.py` (20) and `utils.py` (7) changed, `assets/pipline.png` added. The meaningful code changes:
  - `91eb786` re-introduced mess on purpose (`import os`, `z=power(x,2)+power(y,2)`, a 187-character line).
  - `c2dce32` added a crash (`math.sqrt(a)`).
  - `8eb63fc` fixed it.
  - In class, `c3b227f` formatted `service.py`, commented out `import os`, shortened the string, and **injected** `math.sqrt(2 * z)` (caught by `test_euclidean_distance_endpoint`). `b8458ff` reverted it.

  `utils.py` stays messy at HEAD, so the first hook run has something to fix.
- **How the two lecture sources relate.** babykev slide `00-start.md` introduces cheese-app-ci-cd as "The second example: the cheese app … A FastAPI app in Docker, with linters, formatters, tests and pre-commit hooks". The cheese repo is the **Docker-first, course-app** version of the same ideas. babykev is the **uv/just, ML-model** version, which goes further: type checking (ty), docs as a check, property tests, a coverage floor, config linting, and marker-based non-hermetic tests.

---

## 8. Exercises

Predict first, then run or check. The worked answers are folded; open each one only after committing to your own.

**8.1 (hands-on: predict, then run). Re-inject the class demo bug.**
- Change `src/api-service/api/service.py:44` to `result = math.sqrt(2 * z)`, rebuild, and run unit, integration and system tests (server started from the new image). Predict which tests fail first.

<details><summary>Worked answer</summary>

- **Unit:** 0 failures. `power()` is untouched.
- **Integration:** exactly 1 failure, `test_euclidean_distance_endpoint`. It expects 5.0 and gets √50 ≈ 7.071 (`test_api.py:38`). `..._default_parameters` only checks the key exists (line 45) and `..._with_floats` only checks the type (line 54), so both still pass.
- **System:** 2 failures. `default` expects ≈2.236 and gets √10 ≈ 3.162 (`test_system_api.py:51`); `custom_values` expects 5.0.
- Lesson: two of the three distance tests check the *shape* of the answer but not its *value*, which is weak assertions.
- If nothing fails, you forgot to rebuild (G1).
</details>

**8.2 (debugging). README Part 7's auto-format command.**
- `docker run --rm -v $(pwd)/src/api-service:/app cheese-app-api:local black --line-length 120 api/` prints `/bin/bash: docker-entrypoint.sh: No such file or directory`. Why, and what's the minimal fix?

<details><summary>Worked answer</summary>

- The bind mount replaces the image's `/app` with your `src/api-service` folder, which contains only `api/`.
- `ENTRYPOINT ["/bin/bash", "docker-entrypoint.sh"]` (`Dockerfile:52`) resolves `docker-entrypoint.sh` relative to `WORKDIR /app` (`Dockerfile:29`), so bash can't find it.
- Mount the sub-folder instead: `-v "$(pwd)/src/api-service/api:/app/api"`. The entrypoint, `PATH` and `pytest.ini` survive.
</details>

**8.3 (hands-on: predict). Make Part 6 actually break the build.**
- README:388 appends `def broken(): assert False`. Predict `pytest tests/unit/ -v`, then change the line so it really fails.

<details><summary>Worked answer</summary>

- Still **11 passed**. `pytest.ini:8` collects only `test_*` functions, and `broken` is never called.
- Use `def test_broken(): assert False`. Then 1 failed, 11 passed, and the unit-tests job (and branch protection) goes red.
- The pre-commit hook doesn't notice either way, because black and flake8 only look at `^src/`.
</details>

**8.4 (debugging). Running on the host.**
- From the repo root: `pip install pytest fastapi httpx requests`, then `pytest tests/ -v`. You get `ModuleNotFoundError: No module named 'api'`. You fix that with `PYTHONPATH=src/api-service`, and now get `'asyncio' not found in markers configuration option`. Explain both.

<details><summary>Worked answer</summary>

- (1) `pytest.ini:9` adds the rootdir (`.`) to `sys.path`, but `api/` lives in `src/api-service/`. In the image it was copied to `/app/api` (`Dockerfile:38`), which is why it works there.
- (2) `test_api.py:83` uses `@pytest.mark.asyncio`. That marker is only registered by the `pytest-asyncio` plugin, and `--strict-markers` (`pytest.ini:15`) turns an unregistered marker into an error.
- Fix: `pip install pytest-asyncio` (listed at `pyproject.toml:13`), or install the whole project in a venv.
</details>

**8.5 (hands-on). Unify the line length.**
- Add `[tool.black]` with `line-length = 120` to `pyproject.toml`, and a `.flake8` with `max-line-length = 120`. Predict how README:112 (`black --check --diff api/` in the image) and README:121 (`flake8 src/api-service/api/` on the host) change.

<details><summary>Worked answer</summary>

- black finds its config in `pyproject.toml`. But the image only copies `pyproject.toml` to `/app` (`Dockerfile:32`), which is also the project root there, so the in-image black now uses 120 and reports **only** `utils.py`.
- The host flake8 reads `.flake8` from the repo root, so `service.py:15` E501 disappears. Only E231 and E303 in `utils.py` remain.
- The in-image flake8 does **not** see `.flake8`, because the Dockerfile doesn't copy it. Add `COPY --chown=app:app .flake8 ./` to make the environments match.
- Lesson: config files are part of the environment.
</details>

**8.6 (conceptual). Where should each check live?**
- Classify each into "pre-commit hook", "CI only" or "manual": the cheese unit tests, the cheese system tests, `detect-private-key`, babykev `just test -m system`, black.

<details><summary>Worked answer</summary>

- Hook: black and `detect-private-key` (fast, hermetic, file-level).
- Cheese unit tests: hermetic and under a second, so they *could* join the hook (babykev puts all hermetic tests there via `just check`). The cheese config chooses not to.
- Cheese system tests: CI, where `ci.yml:146-158` starts a server and fails loudly if it's down.
- babykev `-m system`: manual or scheduled. It needs the Hub, about 1 GB of weights and a device, so it's not hermetic (`tests/system/test_real_model.py:1-8`).
</details>

**8.7 (hands-on). Turn the module-global client into a fixture.**
- Replace `client = TestClient(app)` (`test_api.py:11`) with a `tests/conftest.py` fixture, and update one test to use it.

<details><summary>Worked answer</summary>

Create `tests/conftest.py`:

```python
import pytest
from fastapi.testclient import TestClient
from api.service import app

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
```

Then change a test signature to `def test_root_endpoint(self, client):`.
- The `with` form runs FastAPI startup and shutdown events.
- `yield` gives a teardown point, as described in walk.md step-05 "Writing a fixture".
- Function scope gives each test a fresh client. Use `scope="session"` only if building it is expensive and the tests can't affect each other through it.
</details>

**8.8 (hands-on, babykev). Let hypothesis find the size.**
- At `step-05a` (or HEAD), run the walk.md:651 `perl` line, then `just test -k no_question_sees_another`. Before running, predict the shrunk counter-example. Then `git restore src/babykev/model.py`.

<details><summary>Worked answer</summary>

- The wrong fix allows a token to see any question *more than one* before its own. So the smallest failing request needs three questions: one state token and three 1-token questions, `shape = (1, [1, 1, 1])` (walk.md step-05a D).
- The hand-drawn six-token test (`test_mask.py:28-39`) can't see this bug, because it has only two questions. That's the argument for properties over examples.
</details>

---

## 9. Errata and open questions

**Errata (with evidence)**

- **E1.** README:442 `docker run --rm -v $(pwd)/src/api-service:/app ... black ...` can't work. The mount hides `/app/docker-entrypoint.sh`, which the `ENTRYPOINT` needs (`Dockerfile:52`). See G2.
- **E2.** README:388 `echo "def broken(): assert False" >> tests/unit/test_utils.py` does not break anything. `broken` isn't collected (`pytest.ini:8`), so no test job goes red and README:396's "You'll see: ❌ Tests must pass before merging!" won't be caused by it. If the PR is blocked anyway, the cause is the pre-existing `lint-and-format` failure on `utils.py` (G23, E19), not the "broken" test.
- **E3.** README:268-273 "What Gets Checked?" lists 5 hooks. The config runs 9 (`.pre-commit-config.yaml:12-44`): it also has check-added-large-files, check-json, check-merge-conflict and detect-private-key. The README doesn't say black and flake8 only apply to `^src/.*\.py$`.
- **E4.** `tutorials_demo.md:134` says the hooks "run linters, formatters and tests before each commit". The cheese config has no test hook. Only babykev's hook (`just check`) runs tests. Likewise `tutorials_demo.md:130` promises "Unit, integration, system and acceptance tests with pytest", but cheese-app-ci-cd has no acceptance tests (and babykev has "none yet", walk.md:797).
- **E5.** Line-length inconsistency:
  - 120 in the hook and CI (`.pre-commit-config.yaml:34,43`; `ci.yml:61,66`; README:439, 478-479).
  - Default 88 (black) at README:112, 124, 495-496, 503-504, 528, 531.
  - Default 79 (flake8) at README:121, 502.
  - README:109 runs flake8 at 120 and black at 88 in the same "Option A".
- **E6.** README:537 (Troubleshooting) `pytest tests/ -v` fails on the host without `PYTHONPATH=src/api-service` (see README:512 and G7). The local section (README:499-514) also never installs the test dependencies (`pytest-asyncio` etc.).
- **E7.** README:228 says to start the system-test server "in another terminal … (see Option 2)" while `docker-shell.sh` already publishes 9000. That gives a port conflict (G4). And the `docker-shell.sh` container has no `--network host`, so its `localhost:9000` would not reach a server in another container anyway; the live-server tests would skip.
- **E8.** README:225 `--cov-report=html` inside a `--rm`, unmounted container leaves no report on the host.
- **E9.** README:190-196 runs system tests straight after `docker run -d`, without waiting. CI waits (`ci.yml:150-154`). A not-yet-ready server gives silent skips.
- **E10.** `tests/system/test_system_api.py:70`: `Path(__file__).parent.parent / "src" / "api-service"` resolves to `tests/src/api-service`, which doesn't exist. It should be `.parent.parent.parent`. The test only passes because `api` is importable some other way.
- **E11.** Test-kind labels are inconsistent:
  - `test_system_api.py:2` and `:26` call system tests "Integration tests".
  - `pytest.ini:22` defines `integration` as "require running services", contradicting README:147 ("No real HTTP server needed").
  - The markers `unit`, `integration` and `slow` (`pytest.ini:21-23`) are never used.
- **E12.** Stale references to last year's lecture numbers: `pytest.ini:2` ("from L18"); `.pre-commit-config.yaml:2,28,37` ("L17, Slide …"); `tests/integration/test_api.py:4` ("L18, Slide 11-12"). The repo's last commit is 2025-11-13, from the previous offering.
- **E13.** `service.py:1-5` still says "Messy Version", but `service.py` was cleaned in the demo; only `utils.py` is messy. `service.py:49`'s message claims the line "exceeds 120 characters", but the line is 79 characters.
- **E14.** `Dockerfile:1` says "Multi-stage Dockerfile" but there's a single `FROM` (`Dockerfile:2`).
- **E15.** Image names are inconsistent: `cheese-app-api-service` (`docker-shell.sh:7`), `cheese-app-api:local` (README Parts 2-7), `cheese-app-test` (README:548). Rebuilding one doesn't update the others.
- **E16.** README:90 says the endpoint "returns 5.0". It returns a JSON object with `x`, `y`, `distance` and `message` (`service.py:45-50`).
- **E17.** README:92-93: the sentence immediately followed by `---` renders on GitHub as a setext **heading**, not a paragraph and a rule.
- **E18.** README:20 gives no clone URL. Parts 5-7 assume you can `git push`, which isn't possible on a dlops-io clone without a fork or a new remote.
- **E19 (lecture 21, noted only).**
  - README:291 says Buildx gives "efficient caching", but `ci.yml:22-27` sets up Buildx and then runs plain `docker build` with no cache options.
  - The `test-summary` job's `needs` (`ci.yml:175`) omits `lint-and-format`, so lint failures aren't in the summary or Slack message.
  - `ci.yml:2` says "main branch", but lines 8-11 also trigger on `develop`.
  - At HEAD the `lint-and-format` job's black step (`ci.yml:59-62`, `continue-on-error: false`) would fail on `utils.py` (G23). The `test-summary` job and its Slack message would still say "passed", because they ignore `lint-and-format`. Branch protection set up as in README:378 does require `lint-and-format`, so a PR would be blocked by this pre-existing failure. The README screenshot `assets/pipline.png` (added in `3dea317`) shows every job green, including "Lint and Format Check". The lint job is unchanged since `140f138`, so the screenshot most likely comes from a run on the clean code from before `91eb786` re-introduced the mess, not from HEAD. Derived from the code; no workflow was run.
  - README:320 says the system job waits with a "health check with `curl`". The step (`ci.yml:150-154`) sleeps a fixed 10 s, then makes one `curl -f` to `/`, not `/health`, with no retry.
- **E20.** `pyproject.toml:7-19` mixes dev tools (black, flake8, pre-commit, pytest, pytest-cov) into the runtime dependencies, so they ship in the production image. There's no lockfile, and every pin is `>=`, so builds aren't reproducible. Compare babykev's `[dependency-groups]` (`babykev/pyproject.toml:26-40`) and `uv.lock`.
- **E21 (babykev-walk).** walk.md:63, 114 and 183 point to `sundry/the-two-bugs.md` and `sundry/lint-codes.md`. Neither file exists in babykev at any `step-*` tag or at HEAD (`git ls-tree -r --name-only <tag> | grep -i sundry` is empty).
- **E22 (babykev-walk).** `README.md:68-71` mentions "steps that run on Modal" and a `.env.example`. Neither exists in babykev at HEAD; they presumably belong to later steps.
- **E23 (babykev).** `README.md:41` lists "training, experiment tracking" among what the repo rebuilds, but the code stops at step-05b (no training code yet). The `00-start.md` slide confirms `data.py`, `train.py` and `evaluate.py` arrive in a later class.
- **E24 (course site).** Lecture numbering conflicts between `tutorials_demo.md:112,139` and `_modules/week-06.md:7,13` (see §7).

**Open questions (couldn't be determined from the sources)**

- **Q1.** The Ed lesson's own text, and any cheese-specific slides for L09, weren't accessible. This guide relies on the repos and the course site.
- **Q2.** Without Docker Desktop's (beta) host-networking setting, does `docker run --network host ...` on macOS reach a port published by another container through `localhost:9000`? It joins the Docker VM's network namespace, not the Mac's. This couldn't be tested. If the system tests skip on a Mac, use `docker exec api-server python -m pytest tests/system/ -v`.
- **Q3.** `Dockerfile:32-35` builds the project with only `pyproject.toml` present, while `pyproject.toml:5` declares `readme = "README.md"` and there's no `[build-system]`. Historically setuptools only *warns* about a missing readme, and CI evidently built successfully in Nov 2025. Whether a 2026 setuptools still tolerates this wasn't verified.
- **Q4.** `ci.yml:94` bind-mounts `${{ github.workspace }}/coverage` into a container running as uid 1000. Whether the HTML report can be written there (directory ownership on the runner) wasn't verified. The step is `continue-on-error: true` (line 95), which may hide a failure.
- **Q5.** The pinned hook versions (black 24.1.1, flake8 7.0.0 with its pycodestyle) date from early 2024. Their behaviour on a host whose default Python is 3.13 or 3.14 wasn't tested. If odd errors appear, `pre-commit autoupdate`.
- **Q6.** Test counts and outputs in §4 come from reading the code. No repository code was executed: 11/10/5 tests per file; 21 passed; 23 passed + 4 skipped with Part 7 and no server; flake8 and black findings measured on copies. Exact pytest timing and coverage percentages weren't measured.
- **Q7.** Whether babykev and babykev-walk will be updated for later lectures (the slide says `serve.py` arrives in the GitHub Actions class). The commits pinned above are a snapshot as of 2026-10-06.

---

## Links

- README sections, `cheese-app-ci-cd` (pinned commit): [Part 3: Testing with Pytest](https://github.com/dlops-io/cheese-app-ci-cd/blob/b8458ff0cc1898700b32a873b4665f43f50df71e/README.md#part-3-testing-with-pytest) · [Part 4: Automating with Pre-commit Hooks](https://github.com/dlops-io/cheese-app-ci-cd/blob/b8458ff0cc1898700b32a873b4665f43f50df71e/README.md#part-4-automating-with-pre-commit-hooks)
  - Context: [Part 1: Understanding the Codebase](https://github.com/dlops-io/cheese-app-ci-cd/blob/b8458ff0cc1898700b32a873b4665f43f50df71e/README.md#part-1-understanding-the-codebase) · [Part 2: Identifying Code Quality Issues](https://github.com/dlops-io/cheese-app-ci-cd/blob/b8458ff0cc1898700b32a873b4665f43f50df71e/README.md#part-2-identifying-code-quality-issues) · exercise [Part 7: Student Exercise - Add a New Endpoint with Full CI](https://github.com/dlops-io/cheese-app-ci-cd/blob/b8458ff0cc1898700b32a873b4665f43f50df71e/README.md#part-7-student-exercise---add-a-new-endpoint-with-full-ci) · [Quick Command Reference](https://github.com/dlops-io/cheese-app-ci-cd/blob/b8458ff0cc1898700b32a873b4665f43f50df71e/README.md#quick-command-reference) · [Troubleshooting](https://github.com/dlops-io/cheese-app-ci-cd/blob/b8458ff0cc1898700b32a873b4665f43f50df71e/README.md#troubleshooting) · [Docker Cleanup](https://github.com/dlops-io/cheese-app-ci-cd/blob/b8458ff0cc1898700b32a873b4665f43f50df71e/README.md#docker-cleanup)
  - Lecture 21: [Part 5: GitHub Actions (Remote CI)](https://github.com/dlops-io/cheese-app-ci-cd/blob/b8458ff0cc1898700b32a873b4665f43f50df71e/README.md#part-5-github-actions-remote-ci) · latest README on [`main`](https://github.com/dlops-io/cheese-app-ci-cd#part-3-testing-with-pytest)
- Guest lecture (pinned commits): [`babykev-walk` README](https://github.com/rahuldave/babykev-walk/blob/82adb14c0f3e73a0a836a3655f7dc4ffcdf76670/README.md) · [`walk.md`](https://github.com/rahuldave/babykev-walk/blob/82adb14c0f3e73a0a836a3655f7dc4ffcdf76670/walk.md) · [`slides/`](https://github.com/rahuldave/babykev-walk/tree/82adb14c0f3e73a0a836a3655f7dc4ffcdf76670/slides) · [`babykev` README](https://github.com/rahuldave/babykev/blob/4a14085bb25620f37dca5c2bfeb27843c82dbe9e/README.md) ([In Docker](https://github.com/rahuldave/babykev/blob/4a14085bb25620f37dca5c2bfeb27843c82dbe9e/README.md#in-docker), [How the history is organised](https://github.com/rahuldave/babykev/blob/4a14085bb25620f37dca5c2bfeb27843c82dbe9e/README.md#how-the-history-is-organised)) · the last step, [`step-05b`](https://github.com/rahuldave/babykev/tree/step-05b)
- Ed lesson: [L09 · Automating Software Development: CI, unit testing](https://edstem.org/us/courses/97373/lessons/166034/) · course [tutorials page](https://harvard-iacs.github.io/2026-AC215/tutorials_demo/)
- Colab notebooks: none for this lecture.
- Previous lecture: [L08 · LLM: Finetuning](L08-llm-finetuning.md)
- Next lecture: [L10 · Connecting to the Cloud: Networking, Authentication & Storage](L10-cloud-connect-cheese-app-v0.md) (`cheese-app-v0`, where `detect-private-key` starts to matter)
- Referenced in §7: [L01 · Virtual Environments and Virtual Machines](L01-vms-venvs.md) · [L02 · Containers I](L02-containers-1.md) · [L03 · Containers II](L03-containers-2-mega-pipeline.md) · [L04 · Containers II-b](L04-containers-2b-flexible-workflow-ports.md) · [L18 · APIs + Frontend](L18-apis-frontend.md) · [L21 · Automating Software Development: CI/CD with GitHub Actions II](L21-cicd-github-actions.md) · [L23 · Final Deployment and Review](L23-final-cicd-deployment.md)
