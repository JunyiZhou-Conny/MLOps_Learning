# L03 · Containers II — Mega Pipeline App — study guide

[Ed lesson](https://edstem.org/us/courses/97373/lessons/166033/) · Tutorial: [`dlops-io/mega-pipeline`](https://github.com/dlops-io/mega-pipeline) `main` @ [`c6bbc9b`](https://github.com/dlops-io/mega-pipeline/tree/c6bbc9ba88984e1234b68ccf5cdf7c00f7e9accc) (Mega Pipeline App: the whole main README and the five component READMEs it sends you to; comparison only: branch `solution` @ [`8083187`](https://github.com/dlops-io/mega-pipeline/tree/8083187ec0e022ba34440892689145ff703a34e0)) · Video: [AC215 · L03 follow-along](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l03-mega-pipeline) · Made from the verified digest and real terminal captures, 2026-10-13

## 中文速览

- **做什么：** 用 `dlops-io/mega-pipeline`（branch `main`）搭一个 AI podcast pipeline。五个 component folder：`transcribe_audio`（A）、`generate_text`（B）、`synthesis_audio_en`（C）、`translate_text`（D）、`synthesis_audio`（E），每个都有一个给好的 `cli.py`，但**没有 Dockerfile，要你自己写**。每个 component 一个 image、一个 container：从全班共用的 GCS bucket `mega-pipeline-bucket` 拿 input，调一个 Google 的 managed AI API（Speech-to-Text、Vertex AI 上的 Gemini、Text-to-Speech、Translation），再把 output 写回 bucket。认证用 Canvas 上下载的 service account key `mega-pipeline.json`，所有调用都记在课程的 GCP project 上，不花你自己的钱。
- **Idea 1 · bucket 就是 message bus：** container 之间从不直接通信，只靠 object name 的约定交接：`input_audios/` → A → `text_prompts/<group>/` → B → `text_paragraphs/<group>/` → C（写 `text_audios/<group>/`）和 D（写 `text_translated/<group>/`）→ E（写 `output_audios/<group>/`）。GCS 里没有真正的 folder，只有 prefix。`group_name`（默认 `"pavlos"`，没有 assert）是唯一把各组分开的东西，五个 `cli.py` 里必须写成一样的。没有任何东西会自动触发下一步，每个 stage 都是你手动跑。
- **Idea 2 · Dockerfile 一行一行自己写：** `FROM python:3.12-slim-bookworm` + `ARG DEBIAN_PACKAGES`（只有 A 需要 `ffmpeg`）+ 六个 `ENV` + 一个大 `RUN`（apt 装包、删 apt list、`pip install uv`、建 non-root user `app`，uid 1000）+ `USER app` / `WORKDIR /app` + `COPY --chown=app:app . ./` + `RUN uv sync` + `ENTRYPOINT`/`CMD`。README 只说 "Build your docker image and give your image the name `transcribe_audio`"，没给命令，用 `docker build -t transcribe_audio .`。2026-10-13 的 capture 里，A 第一次 build 的 apt 那一步装了 237 个 package（205 MB），46.9 s，image 1.35 GB。
- **Idea 3 · bind mount 是一扇窗：** `docker run --rm -ti -v "$(pwd):/app" transcribe_audio` 把笔记本上的 component folder 盖在 container 的 `/app` 上。VS Code 里改 `cli.py` 立刻生效；写在 `/app` 下的东西（`pyproject.toml`、`uv.lock`、下载的数据）直接落在 host 上，`--rm` 之后还在。venv 在 `/home/app/.venv`（`ENV UV_PROJECT_ENVIRONMENT`），在 mount 外面，所以不会被盖住。prompt 是 `app@<container-id>:/app$`，没有 `(transcribe-audio)` 前缀，但 venv 是 active 的：`which python` → `/home/app/.venv/bin/python`。
- **Idea 4 · `uv add` → exit → rebuild：** 在 container 里 `uv add google-cloud-storage google-cloud-speech ffmpeg-python` 装了 26 个 package，但它们在 container 的 writable layer 里，`exit` 时跟着 `--rm` 一起没了，只有 `pyproject.toml` 和 `uv.lock`（138,445 bytes）留在 host 上。再开一个新 container 又是 `ModuleNotFoundError: No module named 'google'`。必须 rebuild 一次：`COPY` 把新的 `pyproject.toml`/`uv.lock` 带进去，`uv sync` 把 26 个 package 装进 image（rebuild 后 1.48 GB）。
- **Idea 5 · ADC 怎么找到 key：** 代码里从来不传 key。`storage.Client()` 这类 client 会调 `google.auth.default()`（Application Default Credentials），它第一站就看 `GOOGLE_APPLICATION_CREDENTIALS=secrets/mega-pipeline.json`。这是一个 **relative path**，只有 cwd 是 `/app` 时才指得到你 folder 里的 `secrets/`；找不到就是 `DefaultCredentialsError: File secrets/mega-pipeline.json was not found.`。C、D、E 在 import 时就建 client，所以没有 key 连 `python cli.py --help` 都报这个错；A 和 B 的 `--help` 不需要 key。
- **最费时间的坑：** ① `uv init --bare` 写进 `requires-python` 的版本取决于你笔记本上的 Python（capture 的笔记本是 3.11.2，所以是 `>=3.11`）。如果是 `>=3.13` 或更高，image 里 3.12 不满足，`uv sync` 会悄悄下载另一个 CPython：`generate_text` 自带的 `>=3.14` 在 capture 里就下载了 CPython 3.15.0。改成 `>=3.12`。② `generate_text` 已经 commit 了 `pyproject.toml`，`uv init --bare` 直接报 `Project is already initialized`（exit 2），跳过这一步。③ Linux 上 folder 的 owner 不是 uid 1000（比如你是 root），`uv add` 报 `Permission denied (os error 13)`。④ `docker run … transcribe_audio python cli.py -d` 不能这么用：`ENTRYPOINT ["/bin/bash"]` 会把 `python` 当成 shell script，exit 126。⑤ B 的默认 model `gemini-2.5-flash-lite` 在 Vertex AI 上 2026-10-20 退役，之后启动 container 时加 `-e GEMINI_MODEL=<current model>`。
- **安全坑：** `.gitignore` 只管 Git，不管 Docker。`COPY --chown=app:app . ./` 会把 `secrets/mega-pipeline.json` 一起拷进 image（capture 里用一个 placeholder 文件验证过），README 最后 optional 的 Docker Hub push 就等于把 key 公开。在每个 component 里加一个 `.dockerignore`，内容就一行 `secrets/`，再 rebuild；run 的时候 mount 照样把 key 带进 container。
- **README 的小 errata：** component README 里的 Canvas 链接（file `23163432`）比主 README 的（`25687801`）旧，用主 README 的；`synthesis_audio_en`、`synthesis_audio` 的文字说 "keep `ffmpeg`"，但给的 `ARG` 里没有 ffmpeg，以 code block 为准；appendix 的 sample Dockerfile 是 `build-essential curl`，也没有 ffmpeg，不要直接贴进 `transcribe_audio`；四个 component 的 `.gitignore` 把你写的 `Dockerfile`、`pyproject.toml`、`uv.lock` 都 ignore 了，放进自己的 repo 要 `git add -f`。
- **做完要删：** GCP 上没有你建的东西（没有 VM、bucket、service account），不用删；你的 output 留在 shared bucket 里你组的 prefix 下。本地：`docker image rm transcribe_audio generate_text synthesis_audio_en translate_text synthesis_audio`，再 `docker image prune -f` 和 `docker builder prune`（加 `.dockerignore` 之前的旧 build 里有 key）。key 不要进任何 repo；如果 push 过带 key 的 image，删掉并告诉 staff。

## At a glance

**What you build.** An "AI podcast factory" made of five small, separate Docker containers, one per folder of the repo. Each runs a given `cli.py` (120–154 lines) that pulls its input from a class-wide Google Cloud Storage bucket, calls one managed Google AI API (Speech-to-Text, Gemini on Vertex AI, Text-to-Speech or Cloud Translation) and leaves its output in the bucket under the next "folder" (prefix), scoped by your team's `group_name`. The containers never talk to each other: the bucket is the hand-off (`README.md:60-67`). Unlike L02, no Dockerfile is given. You write one per component from the component README's pieces, scaffold `pyproject.toml` with `uv init --bare`, build, run with your folder bind-mounted at `/app`, `uv add` the packages inside the container, and rebuild to bake them in.

**Time needed** (estimate). On the recording machine (2026-10-13, Docker Engine 29.8.2): A's first build about two minutes (the apt step 46.9 s, then exporting the image); B's first build 54.0 s; C, D and E about a second each, because they reuse B's apt layer; every rebuild after `uv add` 8–18 s. With the course key, Speech-to-Text waits up to 90 s per recording (`transcribe_audio/cli.py:78`) and Text-to-Speech up to 300 s (`synthesis_audio_en/cli.py:90`). The follow-along video is about half an hour, in two parts (part 1: the pipeline and your first Dockerfile; part 2: packages, the key and all five components). With the extras in §4 and the exercises, budget 3 hours.

**Prerequisites.**
- Tutorial 0 finished: a GCP account and project, VS Code, Git, **Docker Desktop** and **uv** (`README.md:24`). In this lecture uv runs on your laptop too (`uv init --bare`), not only in the image.
- **Credentials, for the first time in the course:** "Unlike Tutorial 0, you **will** need GCP credentials (a service account key) for this tutorial" (`README.md:26`). The key, `mega-pipeline.json`, is on Canvas (HarvardKey login), linked at `README.md:99`.
- Your **team's group name** (e.g. `group-01`): the tutorial is done in groups, and progress shows on a public leaderboard (`README.md:50-56`).
- APIs to enable: none. The key belongs to the course's project, where the staff have enabled them (L04 has you do it yourself).
- Optional: a Docker Hub account and access token (the optional push), an ElevenLabs account and API key (the bonus in `synthesis_audio`).

**What it costs.** Nothing on your own GCP bill: the bucket, Speech-to-Text, Gemini, Text-to-Speech and Translation are all used through the course's key and project. The ElevenLabs bonus uses your own ElevenLabs quota. Docker Hub public repos are free. Locally, the five images list at 1.48 GB (`transcribe_audio`) and 842–846 MB each (the other four); they share their base layers.

**Tear down, exactly** (none of this is in the README; it is all *(extra)*):
1. `docker image rm transcribe_audio generate_text synthesis_audio_en translate_text synthesis_audio` (captured, §4 Step 26).
2. `docker image prune -f` and `docker builder prune`: older builds and the build cache can still hold your key (§6 G1, §8 B5). Not captured.
3. Nothing in GCP: you created no VM, bucket or service account. Your outputs stay in the shared bucket under your group's prefix.
4. The key: keep it out of every repository (including your own study repo, §6 G14). If you ever pushed an image that contains it, delete that Docker Hub repository and tell the staff so the key can be rotated.

<details>
<summary><b>Versions and sources this guide was checked against</b></summary>

- **README sections this lecture covers** (course site source `tutorials_demo.md:46-52`, which links only the repo; lecture date Sep 10 per `_modules/week-02.md:13-15`), in `main`'s `README.md`:
  - `## Prerequisites` `:22-26`; `## Clone this Repository` `:30-37` (anchor `#clone-this-repository`); `## What You’ll Learn` `:41-46`; `## 👥 You'll work in teams — and there's a leaderboard 🏆` `:50-56`
  - `## Connecting the Pipeline Components` `:60-67`, `### GCS Bucket Details` `:71-86`
  - `## GCP Credentials File` `:90-101`, `### 🔑 Important Note on Secrets` `:103-106`
  - `## 🚀 Time to Build — The Five Components` `:110-124`, which sends you to the five component READMEs: `transcribe_audio/README.md`, `generate_text/README.md`, `synthesis_audio_en/README.md`, `translate_text/README.md`, `synthesis_audio/README.md`. Each has the sections *Project Setup*, *GCP Credentials File*, *Create pyproject.toml*, *Create Dockerfile*, *Docker Build & Run*, *Python packages required*, *CLI to interact with your code*, *Testing your code locally* and *OPTIONAL: Push Container to Docker Hub*; `synthesis_audio` adds *OPTIONAL: Synthesize with ElevenLabs (Pavlos' voice)* (`synthesis_audio/README.md:132-156`).
  - `## Quick Reference — Running Each Component` `:128-165`; `## Appendix` `:169` with `### Sample Dockerfile` `:171-225` and `### Notes for running on Windows` `:227-236`; `## Solutions` `:238-239`.
- **Primary repo:** `dlops-io/mega-pipeline`, branch `main`, commit `c6bbc9ba88984e1234b68ccf5cdf7c00f7e9accc`, committed 2026-09-27 06:42:25 -0400 ("fix for Google Speech-to-Text automatically breaks longer audio files into chunks separated by natural pauses."; it changes only `transcribe_audio/cli.py`). It was still the head of `main` on 2026-10-13. On lecture day `main` moved from `86c6fb8` ("before lecture") to `07e14b9` ("Update README.md", the Canvas link at `README.md:99`).
- **Other branches, read for comparison only:** `solution` @ `8083187ec0e022ba34440892689145ff703a34e0` (2025-09-22, last year's full solution: a Dockerfile, a four-mode `docker-shell.sh`, `pyproject.toml` and `uv.lock` per component, secrets mounted from outside the repo); `simple` @ `7805aee4ec52f337c0160cd6f449fd7b0b85d9f5` (2025-09-23); `pipenv` @ `84b2d64fcdf2af16c50e3257eac8ae3e02e24501` (2025-02-06); `flexible-workflow` @ `cc67f3b8fc471f4fe1afe73d03e89466bae7d485` (2026-09-18), the L04 tutorial, cited in §7 only.
- **Terminal captures (the strongest evidence in this guide).** Every README command that can run without the course key was run on 2026-10-13 (01:42–01:51 UTC), in README order, exactly as written, plus the extras in §4:
  - "the laptop": a fresh `debian:12` container per command (Debian 12, Python 3.11.2, git 2.39.5, user `student`, uid 1000), with the README's curl installer giving **uv 0.13.0**;
  - "the laptop's Docker": Docker Engine 29.8.2 (linux/amd64, containerd image store, BuildKit);
  - inside the images: `python:3.12-slim-bookworm` (Python 3.12.15, Debian 12), pip upgraded 25.0.1 → 26.2.1, uv 0.13.0 from the Dockerfile's `pip install uv`.
  
  No course key existed, so no command that talks to Google could succeed: those outputs are described from the code and labelled *expected*. Files: [`assets/terminal/`](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l03-mega-pipeline/assets/terminal) (`laptop/`, one folder per component, `expected/`, `files/`, with `capture.sh` and `run_steps.sh`); provenance in `ASSETS.md` in the same video folder.
- **The digest's fact-check, the same day.** The README's component Dockerfile was built in disposable containers and `uv add`, `--help`, the `ENTRYPOINT` misuse and the secret check were run there; `uv init --bare` and `uv` with Python downloads disabled were tried with uv 0.11.32 on copies of `pyproject.toml`; the public wheels of `google-cloud-translate` 3.28.0, `google-genai` 2.29.0, `google-cloud-texttospeech` 2.38.0, `google-cloud-speech` 2.41.0, `google-auth` 2.61.0 and `ffmpeg-python` 0.2.0 were read (not executed) to confirm when credentials load and what the API enums mean. Where the digest and the captures disagree (uv 0.11.32 vs 0.13.0, `>=3.13` vs `>=3.11`, image and lockfile sizes, google-genai 2.29.0 vs 2.30.0), this guide follows the captures.
- **Exercise checks:** the claims in `exercises.md` (§8) were checked in throwaway containers built from the README's Dockerfile on the same Docker Engine.
- **Colab notebooks:** none for L03. **Not examined:** the AWS track `dlops-io/mega-pipeline-aws`, and the leaderboard app at `http://ac215-mega-pipeline.dlops.io/` (its code is not in the repo).
- **Ed lesson:** its slides and notes were not accessible when these sources were checked; the course site source `tutorials_demo.md:46-52` was used instead.

</details>

## Command checklist

Commands in backticks are exactly as the README writes them (placeholders kept). Plain items are actions (download a file, edit a line). Items marked *(extra)* are not in the README; their real output is in §4. Each component README lists its CLI steps in short form (`python cli.py -d`), and the main README's *Quick Reference* (`README.md:128-165`) gives the same commands in long form (`python cli.py --download`); both spellings are shown together, in the order both READMEs give them. Commands after `app@…:/app$` in §4 run **inside** the container; everything else runs on your laptop, from inside the component folder. Your container id, user name and group name replace `5b4d4981ec25`, `student` and `group-01`.

### Before the README *(extra)*

- [ ] `docker version` — *(extra)* the client and the engine both answer (Docker Engine 29.8.2 at the time of recording). If the server part errors, start Docker Desktop.
- [ ] `docker pull python:3.12-slim-bookworm; docker run --rm python:3.12-slim-bookworm python --version` — *(extra)* fetches the base image once; prints `Python 3.12.15` (at the time of recording).

### README.md · Clone this Repository (`README.md:30-37`)

*(video tracker R1–R2)*
- [ ] `git clone https://github.com/dlops-io/mega-pipeline.git` — copies the repo into `./mega-pipeline` (branch `main`).
- [ ] `cd mega-pipeline`
- [ ] `ls; git log --oneline -1; git branch` — *(extra)* the five component folders and two PNGs; `c6bbc9b fix for Google Speech-to-Text …` (or a newer commit); `* main`.
- [ ] `ls -a transcribe_audio generate_text synthesis_audio_en translate_text synthesis_audio` — *(extra)* each has `README.md`, `cli.py` and `secrets/`, and **none has a Dockerfile**; `generate_text/` also has `pyproject.toml` and `main.py` and no `.gitignore`; `synthesis_audio/` also has `cli_11.py`.

### README.md · GCP Credentials File (`README.md:90-106`)

- [ ] Download `mega-pipeline.json` from Canvas with the link at `README.md:99` (file `25687801`) and place it inside each component's `secrets/` folder (`README.md:97`). The name must be exactly `mega-pipeline.json` (a browser may save `mega-pipeline (1).json`).
- [ ] `for d in transcribe_audio generate_text synthesis_audio_en translate_text synthesis_audio; do cp ~/Downloads/mega-pipeline.json "$d/secrets/"; done` — *(extra, not captured)* one way to put a copy in all five folders; adjust the download path.

### README.md · Time to Build — The Five Components (`README.md:110-124`)

- [ ] Work through the five component READMEs **in order** A → E (`README.md:114-120`), and set your group name in each `cli.py` before you run it (`README.md:124`).

### Task A · `transcribe_audio` (`transcribe_audio/README.md`)

*(video tracker A1–A13)*

*Project Setup* (`:11-13`) and *GCP Credentials File* (`:15-17`)
- [ ] `cd transcribe_audio` — "`cd` into the `transcribe_audio` folder" [A1].
- [ ] Save `mega-pipeline.json` inside `transcribe_audio/secrets/` [A2].
  - Note: this README links Canvas file `23163432` (`:17`); the main README's link (`25687801`, `README.md:99`) is the newer one. Use that.
- [ ] `ls secrets; git status --short; git check-ignore -v secrets/mega-pipeline.json` — *(extra)* the key is there and Git ignores it: `transcribe_audio/.gitignore:3:/secrets	secrets/mega-pipeline.json` (captured with a stand-in file).

*Create pyproject.toml* (`:19-34`)
- [ ] `uv init --bare` — writes only `pyproject.toml` [A3]; captured: ``Initialized project `transcribe-audio` ``.
  - Note: if `uv --version` says `uv: command not found`, install uv with one of the next three commands first, restart your terminal and re-run `uv init --bare` (`:26-34`).
- [ ] `curl -LsSf https://astral.sh/uv/install.sh | sh` — macOS / Linux, only if uv is missing; captured: `downloading uv 0.13.0 x86_64-unknown-linux-gnu`, `installing to /home/student/.local/bin`.
- [ ] `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"` — Windows (PowerShell) instead. Not captured.
- [ ] `pip install uv` — the README's alternative. Not captured.
  - Note: on Linux with Debian's or Ubuntu's own Python, pip refuses with `error: externally-managed-environment` (PEP 668, seen in L01). Use the curl line there.
- [ ] Restart your terminal, `cd` back into `transcribe_audio`, and re-run `uv init --bare` (`:34`).
- [ ] `cat pyproject.toml` — *(extra)* `requires-python = ">=3.11"` on the recording laptop (its Python is 3.11.2), `dependencies = []`.
  - Note: the number comes from **your** laptop's Python. If yours says `>=3.13` or higher, change it to `requires-python = ">=3.12"` (or delete the file and run `uv init --bare --python 3.12`). This fix is not in the README; without it, the image's `uv sync` downloads a different Python (§6 G3).

*Create Dockerfile* (`:36-92`)
- [ ] Create a file named `Dockerfile` (no extension) [A4]: the line `FROM python:3.12-slim-bookworm` (named in the text at `:41`), then the six code blocks in order: `:45`, `:50-55`, `:60-69`, `:76-77`, `:82-83`, `:88-89`. The assembled 30-line file is in §4 Step 7.
  - Note: the appendix's sample (`README.md:175-225`) has `ARG DEBIAN_PACKAGES="build-essential curl"` (`README.md:179`), with no `ffmpeg`. Don't paste it unchanged into `transcribe_audio` (§6 G8).
- [ ] `ls -a; git status` — *(extra)* `Dockerfile` and `pyproject.toml` are there, and Git still says `nothing to commit, working tree clean`: `transcribe_audio/.gitignore:5-6` ignores both (§6 G14).

*Docker Build & Run* (`:94-102`)
- [ ] Build your docker image and give your image the name `transcribe_audio` (`:95`) [A5]: `docker build -t transcribe_audio .`
  - Note: the README names the image but gives no command; this is the standard one, run from `transcribe_audio/`. The first build takes about two minutes; it ends with one warning, `SecretsUsedInArgOrEnv … (ENV "GOOGLE_APPLICATION_CREDENTIALS") (line 10)`, which is harmless here.
- [ ] `docker images transcribe_audio` — *(extra)* `1.35GB` disk usage (`357MB` content) before any Python package is baked in.
- [ ] `docker run --rm -ti -v "$(pwd):/app" transcribe_audio` [A6] — the prompt becomes `app@<container-id>:/app$`. Windows: see the Appendix item at the end of the checklist (`winpty`).
- [ ] `which python`, `python --version`, `ls -a`, `echo $GOOGLE_APPLICATION_CREDENTIALS` — *(extra, inside)* `/home/app/.venv/bin/python`, `Python 3.12.15`, your laptop's files, `secrets/mega-pipeline.json`.
- [ ] `python cli.py --help` — *(extra, inside, before step 7)* `ModuleNotFoundError: No module named 'google'`: the packages aren't added yet.

*Python packages required* (`:104-110`)
- [ ] `uv add google-cloud-storage google-cloud-speech ffmpeg-python` — *inside* [A7]. The README lists the three packages under "`uv add` the following" (`:105-108`); one `uv add` with all three does it. Captured: `Resolved 27 packages`, `Installed 26 packages`.
  - Note: the package is `ffmpeg-python`; `ffmpeg` and `python-ffmpeg` are other projects (§6 G9). On a Linux laptop whose folder isn't owned by uid 1000, this fails with `Permission denied (os error 13)` (§6 G7).
- [ ] `cat pyproject.toml`, `ls -la`, `uv tree --depth 1`, `echo $VIRTUAL_ENV` — *(extra, inside)* three dependencies with lower bounds, a `uv.lock` of 138,445 bytes owned by `app`, and the venv at `/home/app/.venv`.
- [ ] "After exiting the container, re-build the image" (`:110`) — done at step A13 below.

*CLI to interact with your code* (`:112-127`)
- [ ] On your laptop, in VS Code, change `group_name = "pavlos"` in `cli.py` (line 21) to your team's name, e.g. `group-01` [A8] (`:114`).
- [ ] `grep -n "^group_name" cli.py` — *(extra, inside)* `21:group_name = "group-01" # This needs to be …`: the container sees the edit at once.
- [ ] `python cli.py --help` — *inside* [A9]; matches the README's block (`:117-127`) line for line. Needs no key.

*Testing your code locally* (`:129-134`) · *Quick Reference: Transcribe Audio* (`README.md:132-137`)
- [ ] `python cli.py -d` = `python cli.py --download` — *inside*, with your key [A10]: downloads every recording under `input_audios/` into `input_audios/` on your laptop.
  - Note: needs the key. Without it (as recorded): `Args: Namespace(download=True, transcribe=False, upload=False)`, `download`, then `google.auth.exceptions.DefaultCredentialsError: File secrets/mega-pipeline.json was not found.` (§6 G5).
- [ ] `python cli.py -t` = `python cli.py --transcribe` — *inside*, with your key [A11]: MP3 → FLAC with ffmpeg, then Speech-to-Text; writes `text_prompts/<group>/input-….txt`.
- [ ] `python cli.py -u` = `python cli.py --upload` — *inside*, with your key [A12]: uploads `text_prompts/<group>/input-*.txt` to the bucket.
- [ ] Verify that your uploaded data shows up in the [Mega Pipeline App](http://ac215-mega-pipeline.dlops.io/) leaderboard (`:134`).
- [ ] `exit` — leave the container [A13]; `--rm` deletes it, and the 26 installed packages with it.
- [ ] `docker run --rm -ti -v "$(pwd):/app" transcribe_audio`, then `python cli.py --help`, then `exit` — *(extra)* a new container from the image you built before `uv add`: `ModuleNotFoundError` again, because the packages lived only in the old container (§6 G10).
- [ ] `docker build -t transcribe_audio .` again — "re-build the image so the dependencies are baked in" (`:110`) [A13]: build steps 2–3 `CACHED`, `uv sync` installs the 26 locked packages; 9.9 s.
- [ ] `docker images transcribe_audio` and `docker history transcribe_audio` — *(extra)* `1.48GB` after the rebuild; one row per Dockerfile line, the apt `RUN` at 842MB, `uv sync` at 105MB.
- [ ] `python -c "import google.cloud.storage, google.cloud.speech, ffmpeg; print(\"imports ok\")"; uv --version; python --version` — *(extra, in a container of the rebuilt image)* `imports ok` with no `uv add`.

*OPTIONAL: Push Container to Docker Hub* (`:136-140`; video tracker H1–H3)
- [ ] Sign up in Docker Hub and create an [Access Token](https://hub.docker.com/settings/security) (`:137`).
- [ ] `docker login -u <USER NAME> -p <ACCESS TOKEN>` — logs in to Docker Hub. Not captured.
  - Note: works, but the token stays in your shell history and Docker warns that `--password` on the command line is insecure. Prefer `docker login -u <USER NAME>` and paste the token at the prompt (§6 G13).
- [ ] `docker tag transcribe_audio <USER NAME>/transcribe_audio` — not captured.
- [ ] `docker push <USER NAME>/transcribe_audio` — not captured.
  - Note: **stop first.** Built as the README says, the image contains `/app/secrets/mega-pipeline.json` (captured with a stand-in file, §4 Step 23). Do the `.dockerignore` steps under *After the README* and rebuild before any push. An image built on Apple Silicon is `linux/arm64` only (§6 G6).

### Task B · `generate_text` (`generate_text/README.md`)

*(video tracker B1–B13)*
- [ ] `cd generate_text` — "`cd` into the `generate_text` folder" (`:13`) [B1]; from `transcribe_audio/` that is `cd ../generate_text`.
- [ ] Save `mega-pipeline.json` inside `generate_text/secrets/` (`:16-17`) [B2].
- [ ] `ls -a; cat pyproject.toml` — *(extra)* this folder already has a `pyproject.toml` (`requires-python = ">=3.14"`, both packages listed) and a `main.py`, and no `.gitignore`.
- [ ] `uv init --bare` (`:22`) [B3]
  - Note: fails as written today: ``error: Project is already initialized in `/home/student/mega-pipeline/generate_text` (`pyproject.toml` file exists)``, exit 2. Skip it. Instead edit the committed file to `requires-python = ">=3.12"` **before** the first build (§6 G3, G4).
- [ ] The "Don't have uv installed?" block again (`:26-34`): `curl -LsSf https://astral.sh/uv/install.sh | sh`, `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`, `pip install uv` — skip, uv is installed by now.
- [ ] Create the `Dockerfile` [B4]: the same as A's, except `ARG DEBIAN_PACKAGES="build-essential"` (`:45`); "no `ffmpeg` (this component doesn't touch audio)" (`:38`).
- [ ] Build your docker image and give it the name `generate_text` (`:95`) [B5]: `docker build -t generate_text .`
  - Note: with the committed `>=3.14`, the full log shows `uv sync` downloading `cpython-3.15.0-linux-x86_64-gnu (download) (35.9MiB)` and building the venv on it; the compact view shows only `[5/5] RUN uv sync 5.9s`. 54.0 s in all.
- [ ] `docker run --rm -ti -v "$(pwd):/app" generate_text` (`:99`) [B6]
- [ ] `which python; python --version; readlink -f $(which python)` — *(extra, inside)* `Python 3.15.0` from `/home/app/.local/share/uv/python/…` if `requires-python` wasn't fixed; `Python 3.12.15` from `/usr/local/bin/python3.12` after the fix.
- [ ] `uv add google-cloud-storage google-genai` — *inside* (`:104-106`) [B7]; captured: `Resolved 35 packages`, `Checked 34 packages`: nothing new, both were already listed; it only writes `uv.lock`.
- [ ] Change `group_name = "pavlos"` in `cli.py` (line 19) (`:112`) [B8].
- [ ] `python cli.py --help` — *inside* (`:115`) [B9]; matches the README's block (`:116-124`). Needs no key.
- [ ] `python cli.py -d` = `python cli.py --download` — *inside*, with your key (`:129`; `README.md:141`) [B10]: fetches `text_prompts/<group>/input-*.txt`.
- [ ] `python cli.py -g` = `python cli.py --generate` — *inside*, with your key (`:130`; `README.md:142`) [B11]: Gemini on Vertex AI writes `text_paragraphs/<group>/input-….txt`.
  - Note: the default model is `gemini-2.5-flash-lite` (`generate_text/cli.py:73`), which Vertex AI retires on 2026-10-20. From then on, start the container with a current model id: `docker run --rm -ti -e GEMINI_MODEL=<current model> -v "$(pwd):/app" generate_text` *(extra)*.
- [ ] `python cli.py -u` = `python cli.py --upload` — *inside*, with your key (`:131`; `README.md:143`) [B12].
- [ ] Verify on the [Mega Pipeline App](http://ac215-mega-pipeline.dlops.io/) leaderboard (`:132`).
- [ ] `exit`, then `docker build -t generate_text .` again (`:108`) [B13].
- [ ] `grep -n requires-python pyproject.toml; git status --short .` — *(extra)* after the fix: `4:requires-python = ">=3.12"`, ` M pyproject.toml`, `?? Dockerfile`, `?? uv.lock` (no `.gitignore` here).
- [ ] *OPTIONAL push* (`:134-138`): `docker login -u <USER NAME> -p <ACCESS TOKEN>`, `docker tag generate_text <USER NAME>/generate_text`, `docker push <USER NAME>/generate_text` — same notes as in A.

### Task C · `synthesis_audio_en` (`synthesis_audio_en/README.md`)

*(video tracker C1–C12)*
- [ ] `cd synthesis_audio_en` — "`cd` into the `synthesis_audio_en` folder" (`:13`) [C1].
- [ ] Save `mega-pipeline.json` inside `synthesis_audio_en/secrets/` (`:16-17`) [C2].
- [ ] `uv init --bare` (`:22`) [C3]; captured: ``Initialized project `synthesis-audio-en` ``, `requires-python = ">=3.11"`.
  - Note: if yours says `>=3.13` or higher, change it to `>=3.12` (§6 G3). The same applies in D and E.
- [ ] The "Don't have uv installed?" block (`:26-34`): `curl -LsSf https://astral.sh/uv/install.sh | sh`, `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`, `pip install uv` — skip.
- [ ] Create the `Dockerfile` with `ARG DEBIAN_PACKAGES="build-essential"` (`:45`) [C4].
  - Note: the text at `:38` says "keep `ffmpeg` in the system packages", but the code block leaves it out, and the code block is right: `synthesis_audio_en/cli.py` never uses ffmpeg (§9 E3).
- [ ] Build your docker image and give it the name `synthesis_audio_en` (`:95`) [C5]: `docker build -t synthesis_audio_en .` — captured: `CACHED [2/5]` and `Building 0.6s`, because the Dockerfile is identical to B's up to that line.
- [ ] `docker run --rm -ti -v "$(pwd):/app" synthesis_audio_en` (`:99`) [C6]
- [ ] `uv add google-cloud-storage google-cloud-texttospeech` — *inside* (`:104-106`) [C7]; captured: `Resolved 25 packages`, `Installed 24 packages` (`google-cloud-texttospeech==2.38.0`).
- [ ] Change `group_name = "pavlos"` in `cli.py` (line 18) (`:112`) [C8].
- [ ] `python cli.py --help` — *inside* (`:115`) [C9]; with the key in `secrets/`, the README's block (`:116-124`, *expected*).
  - Note: without the key it fails at import: `cli.py` line 22 builds the Text-to-Speech client, which raises `DefaultCredentialsError: File secrets/mega-pipeline.json was not found.` (captured).
- [ ] `python cli.py -d` = `python cli.py --download` — *inside*, with your key (`:128`; `README.md:148`) [C10]: fetches `text_paragraphs/<group>/input-*.txt`.
- [ ] `python cli.py -s` = `python cli.py --synthesis` — *inside*, with your key (`:129`; `README.md:149`) [C11]: Text-to-Speech writes `text_audios/<group>/input-….mp3` straight into the bucket. There is no `--upload` (`README.md:151`).
- [ ] Verify on the [Mega Pipeline App](http://ac215-mega-pipeline.dlops.io/) leaderboard (`:130`).
- [ ] The README's optional ElevenLabs note (`:132-135`: a file `11lab_api_key.txt` in `secrets/` containing `XI_API_KEY=<API_KEY>`) — skip here: `cli_11.py` exists only in `synthesis_audio/` (§9 E4).
- [ ] `exit`, then `docker build -t synthesis_audio_en .` again (`:108`) [C12]; captured: `Resolved 25 packages`, `Installed 24 packages`, 10.1 s.
- [ ] *OPTIONAL push* (`:138-142`): `docker login -u <USER NAME> -p <ACCESS TOKEN>`, `docker tag synthesis_audio_en <USER NAME>/synthesis_audio_en`, `docker push <USER NAME>/synthesis_audio_en` — same notes as in A.

### Task D · `translate_text` (`translate_text/README.md`)

*(video tracker D1–D13)*
- [ ] `cd translate_text` — "`cd` into the `translate_text` folder" (`:13`) [D1].
- [ ] Save `mega-pipeline.json` inside `translate_text/secrets/` (`:16-17`) [D2].
- [ ] `uv init --bare` (`:22`) [D3]; captured: ``Initialized project `translate-text` ``, `requires-python = ">=3.11"`.
- [ ] The "Don't have uv installed?" block (`:26-34`): `curl -LsSf https://astral.sh/uv/install.sh | sh`, `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`, `pip install uv` — skip.
- [ ] Create the `Dockerfile` with `ARG DEBIAN_PACKAGES="build-essential"` (`:45`; "No audio here, so drop `ffmpeg`", `:38`) [D4].
- [ ] Build your docker image and give it the name `translate_text` (`:95`) [D5]: `docker build -t translate_text .` — captured: `CACHED [2/5]`, `Building 0.6s`.
- [ ] `docker run --rm -ti -v "$(pwd):/app" translate_text` (`:99`) [D6]
- [ ] `uv add google-cloud-storage google-cloud-translate` — *inside* (`:104-106`) [D7]; captured: `Resolved 26 packages`, `Installed 25 packages` (`google-cloud-translate==3.28.0`, which contains `translate_v2`).
- [ ] Change `group_name = "pavlos"` in `cli.py` (line 18) (`:112`) [D8].
- [ ] `python cli.py --help` — *inside* (`:115`) [D9]; with the key, the README's block (`:116-125`, *expected*).
  - Note: without the key it fails at import (`cli.py` line 20, `translate.Client()`), captured.
- [ ] `python cli.py -d` = `python cli.py --download` — *inside*, with your key (`:129`; `README.md:155`) [D10]: fetches `text_paragraphs/<group>/input-*.txt`, the same input as C.
- [ ] `python cli.py -t` = `python cli.py --translate` — *inside*, with your key (`:130`; `README.md:156`) [D11]: English → French, saved to `text_translated/<group>/`.
- [ ] `python cli.py -u` = `python cli.py --upload` — *inside*, with your key (`:131`; `README.md:157`) [D12].
- [ ] Verify on the [Mega Pipeline App](https://ac215-mega-pipeline.dlops.io/) leaderboard (`:132`; this README links it with `https://`, the others with `http://`).
- [ ] `exit`, then `docker build -t translate_text .` again (`:108`) [D13]; captured: `Resolved 26 packages`, `Installed 25 packages`, 8.3 s.
- [ ] *OPTIONAL push* (`:134-138`): `docker login -u <USER NAME> -p <ACCESS TOKEN>`, `docker tag translate_text <USER NAME>/translate_text`, `docker push <USER NAME>/translate_text` — same notes as in A.

### Task E · `synthesis_audio` (`synthesis_audio/README.md`)

*(video tracker E1–E12; bonus X1–X3)*
- [ ] `cd synthesis_audio` — "`cd` into the `synthesis_audio` folder" (`:13`) [E1].
- [ ] Save `mega-pipeline.json` inside `synthesis_audio/secrets/` (`:16-17`) [E2].
- [ ] `uv init --bare` (`:22`) [E3]; captured: ``Initialized project `synthesis-audio` ``, `requires-python = ">=3.11"`.
- [ ] The "Don't have uv installed?" block (`:26-34`): `curl -LsSf https://astral.sh/uv/install.sh | sh`, `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`, `pip install uv` — skip.
- [ ] Create the `Dockerfile` with `ARG DEBIAN_PACKAGES="build-essential"` (`:45`) [E4].
  - Note: the text at `:38` says "Audio again, so keep `ffmpeg`"; the code block, which is right, leaves it out (§9 E3).
- [ ] Build your docker image and give it the name `synthesis_audio` (`:95`) [E5]: `docker build -t synthesis_audio .` — captured: `CACHED [2/5]`, `Building 0.7s`.
- [ ] `docker run --rm -ti -v "$(pwd):/app" synthesis_audio` (`:99`) [E6]
- [ ] `uv add google-cloud-storage google-cloud-texttospeech` — *inside* (`:104-106`) [E7]; captured: `Resolved 25 packages`, `Installed 24 packages`.
- [ ] Change `group_name = "pavlos"` in `cli.py` (line 18), and in `cli_11.py` (line 19) if you do the bonus (`:112`) [E8].
- [ ] `python cli.py --help` — *inside* (`:115`) [E9]; with the key, the README's block (`:116-124`, *expected*), except that the real description line reads `Transcribe audio file to text` (`synthesis_audio/cli.py:105`, §9 E6).
  - Note: without the key it fails at import (`cli.py` line 21), captured.
- [ ] `python cli.py -d` = `python cli.py --download` — *inside*, with your key (`:128`; `README.md:162`) [E10]: fetches `text_translated/<group>/input-*.txt`.
- [ ] `python cli.py -s` = `python cli.py --synthesis` — *inside*, with your key (`:129`; `README.md:163`) [E11]: French audio straight into `output_audios/<group>/`; no `--upload` (`README.md:165`).
- [ ] Verify on the [Mega Pipeline App](http://ac215-mega-pipeline.dlops.io/) leaderboard (`:130`).

*OPTIONAL: Synthesize with ElevenLabs (Pavlos' voice)* (`:132-156`)
- [ ] Create an account at elevenlabs.io and generate an API key (`:138`) [X1].
- [ ] Create `secrets/11lab_api_key.txt` containing the one line `XI_API_KEY=your_api_key_here` with your key, no spaces around `=` (`:139-142`) [X1].
- [ ] `uv add requests` — *inside* (`:146`) [X2]; captured: `Resolved 25 packages`, `Checked 24 packages`: `requests` was already installed as a dependency of `google-cloud-storage`; this records `"requests>=2.34.2"` in `pyproject.toml`.
- [ ] `python cli_11.py --download` — *inside*, with both keys (`:151`) [X3].
  - Note: without `secrets/11lab_api_key.txt` even this fails, at import: `FileNotFoundError: [Errno 2] No such file or directory: 'secrets/11lab_api_key.txt'` (captured).
- [ ] `python cli_11.py --synthesis` — *inside* (`:152`): calls ElevenLabs and saves the audio locally under `output_audios_pp/<group>/` (`:156`). If the API refuses, it just prints the response body and carries on: read the output.
- [ ] `python cli_11.py --upload` — *inside* (`:153`): uploads it to `output_audios_pp/<group>/` in the bucket.
- [ ] `exit`, then `docker build -t synthesis_audio .` again (`:108`) [E12]; captured: `Resolved 25 packages`, `Installed 24 packages`, 7.6 s.
- [ ] *OPTIONAL push* (`:158-162`): `docker login -u <USER NAME> -p <ACCESS TOKEN>`, `docker tag synthesis_audio <USER NAME>/synthesis_audio`, `docker push <USER NAME>/synthesis_audio` — same notes as in A.

### README.md · Appendix (`README.md:169-239`)

- [ ] *Sample Dockerfile* (`:171-225`): compare yours with it. It adds `set -ex;` and a loop that recreates man-page folders, and its `ARG` is `"build-essential curl"`, without `ffmpeg`.
- [ ] `winpty docker run --rm -ti -v "$(pwd)":/app generate_text` — Windows only, from Git BASH, if `docker run` says `the input device is not a TTY` (`:230-235`); put each component's name in place of `generate_text`. Not captured.
- [ ] *Solutions* (`:238-239`): "Solutions to this tutorial will be posted here after the assignment deadline."

### After the README *(extra, recommended)*

*Keep the key out of the image* (§4 Steps 22–24)
- [ ] `docker run --rm --entrypoint ls transcribe_audio -la /app/secrets` — *(extra)* with no mount, lists `mega-pipeline.json`: the key is **inside** the image.
- [ ] `printf 'secrets/\n' > .dockerignore` in each of the five component folders, then `cat .dockerignore` — *(extra)* one line, `secrets/`.
- [ ] `docker build -t transcribe_audio .` (and the other four) — *(extra)* rebuild with the `.dockerignore` in place.
- [ ] `docker run --rm --entrypoint ls transcribe_audio -la /app/secrets` — *(extra)* `ls: cannot access '/app/secrets': No such file or directory`. The app still finds the key at run time through the mount.

*One-shot runs* (§6 G16)
- [ ] `docker run --rm -v "$(pwd):/app" transcribe_audio python cli.py -d` — *(extra)* meant to fail: `/usr/local/bin/python: /usr/local/bin/python: cannot execute binary file`, exit 126.
- [ ] `docker run --rm -v "$(pwd):/app" transcribe_audio -c "source /home/app/.venv/bin/activate && python cli.py --help"` — *(extra)* the working form.

*Clean up* (§4 Steps 25–26)
- [ ] `cd ..` — *(extra)* back to the repo root.
- [ ] `docker image ls --filter reference=transcribe_audio --filter reference=generate_text --filter reference=synthesis_audio_en --filter reference=translate_text --filter reference=synthesis_audio` — *(extra)* the five images and their sizes.
- [ ] `git status` — *(extra)* only `generate_text/` and your edited `cli.py` files show; the other four folders hide their Dockerfiles and project files. In your own repo, `git add -f` them; never stop ignoring `secrets/`.
- [ ] `docker image rm transcribe_audio generate_text synthesis_audio_en translate_text synthesis_audio` — *(extra)* `Untagged: …` and `Deleted: sha256:…` for each.
- [ ] `docker image prune -f` and `docker builder prune` — *(extra, not captured)* remove untagged older builds and the build cache, which can still contain the key.

---

## 1. What you build

Five programs that never send each other a single message turn a rough English recording into an English podcast and a French one. The README frames it as a simulated microservice architecture, "where each component runs as its own containerized service" (`README.md:7`), joined by a shared bucket instead of APIs, which the course covers later (`README.md:61-67`).

- **Five components, five folders, five images.** `transcribe_audio` (A), `generate_text` (B), `synthesis_audio_en` (C), `translate_text` (D), `synthesis_audio` (E). Each folder holds a given `cli.py` of 120–154 lines and its own README; **none holds a Dockerfile** ("none of them come with a `Dockerfile` already written", `README.md:114`).
- **Each `cli.py` does up to three things**, one flag each: pull its inputs from the bucket (`-d`), call one managed Google AI API (`-t`, `-g`, `-s`), push its outputs back (`-u`). The two Google Text-to-Speech stages have no upload: the TTS service writes the audio into the bucket itself (`README.md:151`, `:165`).
- **You write the Dockerfile** for each component from its README's pieces, scaffold `pyproject.toml` with `uv init --bare` on your laptop, build the image, and run it with the component folder bind-mounted at `/app`. Inside, you `uv add` the packages `cli.py` imports; then you exit and rebuild to bake them in.
- **Authentication** uses one service-account key from Canvas, `mega-pipeline.json`, copied into each component's `secrets/`. The Google libraries find it through `GOOGLE_APPLICATION_CREDENTIALS`. Every API call and every stored byte is billed to the course's GCP project: the bucket belongs to it, and Gemini and TTS name `gcp_project` explicitly (`generate_text/cli.py:23-25`, `synthesis_audio_en/cli.py:77`).
- **Progress** shows on a class leaderboard at `http://ac215-mega-pipeline.dlops.io/` (`README.md:54`).
- **Not here:** no ports (`-p`), no web servers, no Docker networks, no Compose, no VM. Those come in L04.

```
 YOUR LAPTOP  (Docker Desktop; Apple Silicon builds linux/arm64 images, Intel/most PCs linux/amd64)
 +--------------------------------------------------------------------------------------------------+
 |  ~/.../mega-pipeline/   (git clone, branch main)                                                 |
 |   transcribe_audio/  generate_text/  synthesis_audio_en/  translate_text/  synthesis_audio/       |
 |     cli.py (given)   Dockerfile (YOU write)   pyproject.toml + uv.lock (uv init / uv add)        |
 |     secrets/mega-pipeline.json  (from Canvas, git-ignored -- but NOT docker-ignored)             |
 |                                                                                                  |
 |   $ docker build -t transcribe_audio .        $ docker run --rm -ti -v "$(pwd):/app" transcribe_audio
 |                                                                                                  |
 |   +--------------- one container per component, started by hand, one at a time ---------------+  |
 |   |  user "app" (uid 1000)        WORKDIR /app  <==== bind mount of THIS component folder (rw)  |  |
 |   |  /home/app/.venv   <- built by `uv sync` at build time, lives OUTSIDE the mount            |  |
 |   |  ENV GOOGLE_APPLICATION_CREDENTIALS=secrets/mega-pipeline.json   (relative to cwd /app)    |  |
 |   |  app@<id>:/app$ python cli.py --download | --transcribe | --upload    (venv active)        |  |
 |   +--------------------------------------------------------------------------------------------+  |
 |   no -p ports, no docker network, no compose                                                     |
 +--------------------------------------------------------------------------------------------------+
            |  HTTPS via the google-cloud-* client libraries
            |  (google.auth reads the JSON key -> short-lived access token -> Authorization header)
            v
 GOOGLE CLOUD  -- the course's project (hard-coded as gcp_project in every cli.py)
 +--------------------------------------------------------------------------------------------------+
 |  Cloud Storage bucket  gs://mega-pipeline-bucket                                                 |
 |   input_audios/input-*.mp3                   shared by everyone (no group folder)                |
 |   text_prompts/<group>/input-*.txt           A uploads    -> B downloads                         |
 |   text_paragraphs/<group>/input-*.txt        B uploads    -> C and D download                    |
 |   text_audios/<group>/input-*.mp3            written by the TTS *service* for C                  |
 |   text_translated/<group>/input-*.txt        D uploads    -> E (and the bonus) download          |
 |   output_audios/<group>/input-*.mp3          written by the TTS *service* for E                  |
 |   output_audios_pp/<group>/input-*.mp3       bonus: cli_11.py uploads (ElevenLabs voice)         |
 |                                                                                                  |
 |  Speech-to-Text v1 (A)   Gemini on Vertex AI, us-central1 (B)   Cloud Translation v2 (D)         |
 |  Text-to-Speech Long Audio, projects/<gcp_project>/locations/us-central1 (C, E)                  |
 +--------------------------------------------------------------------------------------------------+
            ^ reads the bucket (presumably; its code is not in the repo)       api.elevenlabs.io (bonus only)
   Leaderboard  http://ac215-mega-pipeline.dlops.io/
```

The data flow (each arrow is "uploaded by one container, downloaded by the next"):

```
 input_audios/ --A transcribe--> text_prompts/<g>/ --B generate--> text_paragraphs/<g>/ --+--C synth EN--> text_audios/<g>/
   (Speech-to-Text)                 (Gemini)                                            |    (TTS writes to GCS itself)
                                                                                        +--D translate--> text_translated/<g>/ --E synth FR--> output_audios/<g>/
                                                                                             (Translation v2)      |               (TTS writes to GCS itself)
                                                                                                                   +--bonus cli_11.py--> output_audios_pp/<g>/
```

C and D both depend only on B, so they can run in either order, or at the same time. E needs D.

What changes since L02 (where one given `Dockerfile.txt` packaged one small CLI):

| | L02 · simple-translate | L03 · mega-pipeline `main` |
|---|---|---|
| Who writes the Dockerfile | given (`simple-translate/Dockerfile.txt`) | **you**, from the component README's pieces |
| Images | 1 | **5**, one per stage |
| OS packages | none installed (`Dockerfile.txt:14-19` only updates and upgrades) | `ARG DEBIAN_PACKAGES` + `apt-get install` (`ffmpeg` for A) |
| User | root | non-root `app`, uid 1000 (`README.md:208`, `:213`) |
| Code and venv | `COPY . ./` with no `WORKDIR` (cwd `/`), venv `.venv` next to the code (`Dockerfile.txt:22-29`) | `WORKDIR /app`; venv at `/home/app/.venv` via `UV_PROJECT_ENVIRONMENT` |
| Run command | `docker run --rm --name $IMAGE_NAME -ti $IMAGE_NAME` (`docker-shell.sh:15`) | `docker run --rm -ti -v "$(pwd):/app" <name>`: a **bind mount** for live code |
| Dependencies | `pyproject.toml` given | `uv init --bare` + `uv add` *inside* the container, then rebuild |
| Cloud | none (an unofficial translate endpoint, no key) | a GCS bucket, four managed Google AI APIs, a service-account key |
| Data flow | arguments → stdout | containers hand off through a shared bucket |

---

## 2. Prerequisites and costs

**Accounts**
- **Tutorial 0** (`README.md:24`): a GCP account and project, VS Code, Git, Docker Desktop and uv. Your own GCP project is not used in this lecture: all traffic goes through the course's key and project.
- **Canvas** (HarvardKey) to download `mega-pipeline.json` (`README.md:97-99`).
- **Your team's group name.** The tutorial is done in groups, and "every team's progress is published live on a public leaderboard" (`README.md:52-54`).
- Optional: **Docker Hub** account and access token for the push (`transcribe_audio/README.md:136-140`); **ElevenLabs** account and API key for the bonus (`synthesis_audio/README.md:136-142`).

**Local installs**
- **Docker Desktop**, running. Docker builds the five images and runs the containers.
- **uv on the laptop.** `uv init --bare` runs on the host (`transcribe_audio/README.md:19-24`); without a `pyproject.toml` the image's `RUN uv sync` fails (captured, §6 G21). The README gives three installers (`:26-34`).
- **Windows:** run Docker commands from **Git BASH**, always quote `"$(pwd)"`, and prefix `winpty` if you see `the input device is not a TTY` (`README.md:227-236`).

**GCP APIs**
- Nothing to enable. The key belongs to the course's project, where Cloud Storage, Speech-to-Text, Vertex AI, Cloud Translation and Text-to-Speech are already on. In L04 you enable these five yourself in your own project (`flexible-workflow:README.md:187-198`).

**Service accounts / keys / secrets / env vars**

| What | Where you put it on the host | How the code finds it | Cited |
|---|---|---|---|
| GCP service-account key | `<component>/secrets/mega-pipeline.json`, a copy **in each of the 5 folders** | Dockerfile `ENV GOOGLE_APPLICATION_CREDENTIALS=secrets/mega-pipeline.json`, a **relative** path resolved against the process's cwd (`/app`); `google.auth.default()` reads it | `README.md:97`, `README.md:195`, `transcribe_audio/README.md:16`, `:55` |
| ElevenLabs key (bonus) | `synthesis_audio/secrets/11lab_api_key.txt` containing `XI_API_KEY=your_api_key_here` | `cli_11.py` opens `'secrets/11lab_api_key.txt'` **at import time** and copies the value into `os.environ['XI_API_KEY']` | `synthesis_audio/README.md:139-142`, `synthesis_audio/cli_11.py:30-39` |
| Team name (not secret, but critical) | edit `group_name = "pavlos"` in every `cli.py` | becomes the `<group>` segment of every object name | `transcribe_audio/cli.py:21`, `generate_text/cli.py:19`, `synthesis_audio_en/cli.py:18`, `translate_text/cli.py:18`, `synthesis_audio/cli.py:18`, `synthesis_audio/cli_11.py:19` |
| Gemini model (optional) | `-e GEMINI_MODEL=<model id>` on `docker run` | `os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")` | `generate_text/cli.py:73` |

- Git keeps the key out of history: the root `.gitignore:4` has `secrets/`, and each component `.gitignore` has `/secrets` (e.g. `transcribe_audio/.gitignore:3`; `generate_text/` has no `.gitignore` of its own, so the root rule protects it).
- **There is no `.dockerignore` anywhere on `main`**, so `COPY --chown=app:app . ./` copies `secrets/` into the image (§6 G1).
- Hard-coded in every `cli.py`: `gcp_project` (the course's project id) and `bucket_name = "mega-pipeline-bucket"` (e.g. `transcribe_audio/cli.py:17-18`). Nothing else is read from the environment apart from `GOOGLE_APPLICATION_CREDENTIALS` (library side), `GEMINI_MODEL` and, in the bonus, `XI_API_KEY`.

**Where the code expects things (paths)**

| Thing | Where | Set by |
|---|---|---|
| Repo checkout | `./mega-pipeline` wherever you cloned it (with this repo's sync script: `~/Desktop/AC215/tutorials/mega-pipeline`) | `git clone` (`README.md:33`) |
| Working directory for `docker build` and `docker run` | **the component folder** (e.g. `mega-pipeline/transcribe_audio`): `.` is the build context, and `"$(pwd)"` becomes `/app` | you |
| Dockerfile, `pyproject.toml`, `uv.lock` | in each component folder, on your laptop | you; `uv init --bare`; `uv add` (through the mount) |
| Code inside the container | `/app` = your component folder (bind mount) | `-v "$(pwd):/app"` (`transcribe_audio/README.md:99`) |
| The venv inside the container | `/home/app/.venv`, outside the mount | `ENV UV_PROJECT_ENVIRONMENT=/home/app/.venv` (`README.md:192`) + `RUN uv sync` |
| uv's download cache in the image | `/home/app/.cache/uv` (about half of the 105 MB `uv sync` layer, §8 B4) | uv |
| Downloaded inputs and outputs | `input_audios/`, `text_prompts/<group>/`, `text_paragraphs/<group>/`, `text_translated/<group>/` in the component folder, i.e. on your laptop | each `cli.py`; the local path mirrors the object name |
| uv on the laptop | `~/.local/bin/uv` (Linux/macOS curl installer) | `curl -LsSf https://astral.sh/uv/install.sh \| sh` (`transcribe_audio/README.md:29`) |

**Billable resources and how to shut them down**
- **GCP: nothing is billed to you.** Speech-to-Text, Gemini tokens, Translation characters, Text-to-Speech characters and the bucket's storage all bill to the course's project, whose key you borrow. You create no VM, bucket or service account, so there is nothing to shut down in GCP.
  - Do not leak the key (§6 G1): anyone holding it can spend the course's money and do whatever its IAM roles allow to the shared bucket.
  - Your outputs stay in the shared bucket under your group's prefix. Everyone writes with the same key and the code has no guard, so a wrong `group_name` writes into (and can overwrite) another team's objects (§6 G2).
- **ElevenLabs (bonus):** counts against your own ElevenLabs plan.
- **Docker Hub (optional):** free public repositories; a pushed image is public by default.
- **Local disk** (captured, Docker Engine 29.8.2 with the containerd image store): `transcribe_audio` 1.35 GB before any package is baked in and 1.48 GB after; the other four 842–846 MB each. They share layers (C, D and E reuse B's apt layer), and Docker Desktop shows one size per image, so your numbers can differ. The apt `RUN` layer alone is 842 MB for `build-essential ffmpeg`.
- **Shut-down procedure** (none of it in the README):
  ```bash
  docker image rm transcribe_audio generate_text synthesis_audio_en translate_text synthesis_audio
  docker image prune -f      # untagged older builds (they can hold the key)
  docker builder prune       # the build cache (it can hold the old COPY layer with the key)
  ```
  No containers are left behind: every run uses `--rm`. `python:3.12-slim-bookworm` stays; remove it with `docker image rm python:3.12-slim-bookworm` if you don't need it (L04 uses `python:3.14-slim-bookworm`).

---

## 3. Concepts this tutorial teaches

### 3.1 A pipeline of independent stages joined by shared storage ("the bucket is the message bus")
- **Explanation.** Each stage is a separate program in a separate container with one job. It doesn't know who produced its input or who will consume its output; all it knows is a **naming contract**, for example "I read `text_paragraphs/<group>/input-*.txt` and I write `text_translated/<group>/input-*.txt`" (`translate_text/cli.py:37`, `:81-85`). Because the contract is "files in a bucket" rather than "function calls", you can rerun, swap or replace one stage without touching the others. The README presents it as a stand-in for the API-based microservices that come later (`README.md:60-67`).
- **Mental model.** A relay race where the runners never meet. Each runner drops the baton in a numbered locker (a prefix), and the next runner opens that locker whenever they arrive. The pipeline's whole "wiring" is the table of prefixes in §1.
- **Analogy.** A restaurant kitchen's pass: the grill cook puts the plate on the pass and the expediter picks it up; neither waits on the other's phone call.
- **Common misconception.** "The containers form a pipeline, so starting one triggers the next." Nothing triggers anything: you run each container, and each verb (`--download`, `--transcribe`, `--upload`), by hand. Running the whole pipeline with one command is what Milestone 2 asks of your project ("runnable with one command (e.g., `docker compose up` or `make run`)", `milestone2.md:46-48`).

### 3.2 Namespacing a shared bucket: prefixes, `group_name`, "folders that aren't folders"
- **Explanation.** Cloud Storage is a flat key → bytes store. `text_prompts/group-01/input-1.txt` is one object name; the "folders" in the console are only a view of the `/`-separated prefixes. Each `cli.py` builds names with `os.path.join(<prefix>, group_name, filename)` (e.g. `transcribe_audio/cli.py:112`) and lists objects by prefix (`transcribe_audio/cli.py:39`) or by glob (`generate_text/cli.py:42`, `match_glob=f"{text_prompts}/{group_name}/input-*.txt"`). `group_name` is the only thing that keeps the teams apart in one bucket.
  - `input_audios/` has **no** group segment: every team transcribes the same recordings (`transcribe_audio/cli.py:39`).
  - The file name is part of the contract too: uploads and downloads only match `input-*.txt` (`transcribe_audio/cli.py:108`, `generate_text/cli.py:42`). A file with another name is silently never handed on (§8 D2).
- **Mental model.** One giant shared drive where everyone agreed to save inside a folder named after their team.
- **Analogy.** Shared office mailboxes: one cabinet, one slot per team label.
- **Common misconception.** "If I forget to set `group_name`, I'll get an error." On `main` the default is `"pavlos"` with no guard (`transcribe_audio/cli.py:21`), so your `--upload` silently writes into (and overwrites) the instructor's namespace. Last year's `solution` branch asserted that the name had been changed, and L04's `flexible-workflow` brings an `assert` back (`flexible-workflow:README.md:134`). The README only warns: "Double-check before every run." (`README.md:124`).

### 3.3 A Dockerfile, line by line, and image layers
- **Explanation.** Each instruction produces either a filesystem layer (`RUN`, `COPY`, `WORKDIR`) or only metadata (`ENV`, `ARG`, `USER`, `ENTRYPOINT`, `CMD`); the captured `docker history transcribe_audio` shows `0B` for every metadata row. The component Dockerfile (`transcribe_audio/README.md:41-90`, assembled in §5):
  1. `FROM python:3.12-slim-bookworm`: Debian 12 with CPython 3.12 already installed in `/usr/local` (Python 3.12.15 at the time of recording).
  2. `ARG DEBIAN_PACKAGES="build-essential ffmpeg"`: the OS packages, as a build-time variable. `ffmpeg` is needed only by A.
  3. Six `ENV`s:
     - `DEBIAN_FRONTEND=noninteractive`: apt never prompts.
     - `LANG=C.UTF-8`: a UTF-8 locale.
     - `PYTHONUNBUFFERED=1`: `print()` output appears at once (useful while a 300 s Text-to-Speech request runs).
     - `UV_LINK_MODE=copy`: uv copies package files from its cache into the venv instead of hard-linking them. Hard links only fail (uv then warns and falls back to copying) when cache and venv are on different filesystems, e.g. with a BuildKit cache mount. Here both live under `/home/app`, so the line is a harmless default (the digest's fact-check: with the variable unset, a `uv sync --reinstall` hard-linked 26 packages with no warning).
     - `UV_PROJECT_ENVIRONMENT=/home/app/.venv`: build the venv **outside** `/app` (3.4).
     - `GOOGLE_APPLICATION_CREDENTIALS=secrets/mega-pipeline.json` (3.6).
  4. One big `RUN … && …`: update apt, install the packages, `apt-get clean` and delete `/var/lib/apt/lists/*` **in the same layer** (so the package index never takes space in the image), upgrade pip, `pip install uv`, create user `app` (uid 1000, home `/home/app`) and a folder `/app` it owns. Plain `pip install` works here because the official Python image's interpreter is not marked "externally managed", unlike Debian's system Python in L01; pip prints a harmless `WARNING: Running pip as the 'root' user …`.
  5. `USER app`, `WORKDIR /app`.
  6. `COPY --chown=app:app . ./`, then `RUN uv sync`, which builds `/home/app/.venv` from `pyproject.toml` (and `uv.lock`, once there is one).
  7. `ENTRYPOINT ["/bin/bash"]` + `CMD ["-c", "source /home/app/.venv/bin/activate && exec bash"]`: the container starts as an interactive bash with the venv active.
- **Mental model.** An image is a stack of transparent sheets, each recording only what its step changed. Docker caches each sheet, keyed by the instruction, everything below it and the files it consumed. Change something and every sheet **above** it is redrawn.
- **Analogy.** A recipe card where each step was photographed. Change step 4 and you re-cook steps 4–7; steps 1–3 come from the photo album.
- **Common misconception.** "Editing `cli.py` only rebuilds a tiny layer." Here `COPY . ./` comes **before** `RUN uv sync`, so changing any file in the folder (even `group_name`) re-runs `uv sync` on the next build (captured: after the `cli.py` edit and `uv add`, build steps 2–3 were `CACHED` and steps 4–5 ran). Later tutorials copy `pyproject.toml` and `uv.lock` first for exactly this reason (`llm-rag/Dockerfile:42-48`: `COPY --chown=app:app pyproject.toml uv.lock* ./`, `RUN uv sync --frozen`, then `COPY --chown=app:app . ./`; §8 B3). During development you rarely rebuild for code changes anyway, because the bind mount (3.4) shows them at once.

### 3.4 Image vs container vs bind mount: where does state live?
- **Explanation.** An **image** is the read-only stack. A **container** is a running process with a thin writable layer on top; `--rm` deletes that layer on exit. `-v "$(pwd):/app"` **overlays** your laptop folder onto `/app`, hiding whatever the image had there (the `COPY`'d files). Three consequences:
  1. Editing `cli.py` in VS Code changes it inside the container immediately (`transcribe_audio/README.md:102`; captured: `grep -n "^group_name" cli.py` inside showed the laptop's edit).
  2. Anything written under `/app` (`pyproject.toml`, `uv.lock`, downloaded inputs, outputs) lands in **your laptop's folder** and survives `--rm`.
  3. Anything written elsewhere, for example `uv add` installing into `/home/app/.venv`, lives in the container's writable layer and **vanishes** on exit.

  That is why the Dockerfile moves the venv to `/home/app/.venv` (`README.md:192`). In L02's image the venv was `.venv` next to the code (`simple-translate/Dockerfile.txt:29`); mounting over that would hide the venv, or expose a laptop `.venv` built for another operating system.
- **Mental model.** The container is a stage set and the image the permanent scenery. `/app` is a window cut through the set that looks straight into your laptop's folder. Things placed in the window are on your desk; things placed on the set are swept away when the show ends (`--rm`).
- **Analogy.** A hotel room (the container) with one drawer that is magically connected to your desk drawer at home (the bind mount). Whatever you leave in the rest of the room is cleaned out at checkout.
- **Common misconception.** "`uv add` inside the container installed the package, so it's in my image now." It is in that container's venv only until you exit. Captured: a new container from the image built before `uv add` failed again with `ModuleNotFoundError: No module named 'google'`. `pyproject.toml` and `uv.lock` (on your laptop, through the mount) remember the packages; a **rebuild** bakes them in (`transcribe_audio/README.md:110`).
  A second one: "the prompt has no `(transcribe-audio)`, so the venv isn't active." `exec bash` starts a new interactive shell that reads `/home/app/.bashrc`, which resets the prompt; the exported `VIRTUAL_ENV` and `PATH` survive (captured: `which python` → `/home/app/.venv/bin/python`).

### 3.5 The uv dependency loop inside a container
- **Explanation.** The tutorial's loop:
  1. `uv init --bare` on the laptop gives a `pyproject.toml` with `dependencies = []`;
  2. build the image (`uv sync` installs nothing yet: captured `Resolved 1 package`, the project itself);
  3. run it, and inside `uv add google-cloud-storage google-cloud-speech ffmpeg-python`, which writes `pyproject.toml` and a new `uv.lock` **on the laptop** and installs into the live venv (captured: `Resolved 27 packages`, `Installed 26 packages`);
  4. run the code;
  5. exit and rebuild, so `COPY` brings the lockfile in and `uv sync` installs the same 26 packages into the image (`transcribe_audio/README.md:19-24`, `:104-110`).

  A shortcut the README doesn't mention: run `uv add …` on the laptop right after `uv init --bare`, and the first build already has everything.
- **Mental model.** `pyproject.toml` is the shopping list, `uv.lock` the itemised receipt, the venv the fridge. `uv add` writes the list, prints a receipt and stocks the fridge; `uv sync` restocks a fridge from the receipt.
- **Analogy.** Trying a recipe in a rental kitchen (the container): you buy the ingredients there, but you also write them on your own list, so your own kitchen (the image) can be stocked next time.
- **Common misconception.** "`uv init --bare` is harmless boilerplate." It stamps `requires-python = ">=X.Y"`, where X.Y is the Python uv finds **on your laptop**. Captured: `>=3.11` on a laptop with Python 3.11.2, which the image's 3.12 satisfies. A laptop with Python 3.13 (or a uv-managed 3.13+) gets `>=3.13` (the digest's check with uv 0.11.32), and then the image's `uv sync` silently **downloads the newest matching CPython** and builds the venv on it. `generate_text`'s committed `requires-python = ">=3.14"` shows it in the captures: `Downloading cpython-3.15.0-linux-x86_64-gnu (download) (35.9MiB)`, `Using CPython 3.15.0` (§6 G3). Set it to `>=3.12`.

### 3.6 Service accounts and Application Default Credentials (ADC)
- **Explanation.** Google checks every request twice (`README.md:92-95`):
  - **Authentication** (who is calling?): the service account whose private key is in `mega-pipeline.json`.
  - **Authorisation** (may it do this?): the IAM roles of that service account on the project or bucket.

  Your code never passes the key. `storage.Client()`, `translate.Client()`, `TextToSpeechLongAudioSynthesizeClient()` and `speech.SpeechClient()` call `google.auth.default()`, which first checks the env var `GOOGLE_APPLICATION_CREDENTIALS` and loads the JSON file it names (captured traceback: `google/cloud/client/__init__.py`, line 218, `credentials, _ = google.auth.default(scopes=scopes)` for `translate.Client()`). On the first request the credentials sign a JWT with the key and exchange it for a short-lived access token, sent as an `Authorization: Bearer …` header. The Gemini client `genai.Client(vertexai=True, project=…)` is the exception: it loads credentials lazily, on the first request (captured: B's `--help` works without a key).
- **Mental model.** The JSON key is a key-card encoder. ADC is the front desk that cuts you a short-lived key card (the access token) when asked. IAM is the lock on each door, deciding whether that card opens it.
- **Analogy.** A company badge for a robot employee: the robot (your app) badges in, not you.
- **Common misconception.** "The key file is just a config file." It is a long-lived password to the course's project: whoever holds it can run these APIs on the course's bill.
  A second one: "`GOOGLE_APPLICATION_CREDENTIALS=secrets/mega-pipeline.json` always works." It is a **relative** path, so it works only while the current directory is `/app` (§6 G5, §8 C2). Captured, without a key: `google.auth.exceptions.DefaultCredentialsError: File secrets/mega-pipeline.json was not found.`, raised at `google/auth/_default.py`, line 178.

### 3.7 Managed AI APIs and long-running operations (LROs)
- **Explanation.** Each stage outsources its ML to a hosted API:
  - **Speech-to-Text v1** (A): ffmpeg converts the MP3 to FLAC first, because v1 doesn't take MP3 (MP3 is "a Beta feature and only available in v1p1beta1", per `google-cloud-speech` 2.41.0's `speech_v1/types/cloud_speech.py:561-563`) and FLAC carries its own sample rate. Then `long_running_recognize` with the audio bytes inline, waiting up to 90 s (`transcribe_audio/cli.py:65-78`). Automatic punctuation is off by default, so the raw transcript is unpunctuated, one reason B rewrites it.
  - **Gemini on Vertex AI** (B), through `google-genai`: `client.models.generate_content(model=…, contents=prompt)` (`generate_text/cli.py:23-25`, `:73-77`).
  - **Cloud Translation v2** (D): `translate_client.translate(…, source_language="en", target_language="fr", format_="text")` (`translate_text/cli.py:58-63`).
  - **Text-to-Speech Long Audio** (C, E): `synthesize_long_audio` with an `output_gcs_uri`, so the **TTS service writes the audio object straight into the bucket**. That is why C and E have no `--upload` (`synthesis_audio_en/cli.py:77-91`; `README.md:151`).

  A long-running call returns an `operation` handle immediately; `.result(timeout=…)` waits, polling, until the server finishes.
- **Mental model.** Dropping off dry cleaning: you get a ticket (the operation) and come back later. With Long Audio TTS you even ask the cleaner to deliver to your locker (the bucket), so you never carry it home.
- **Analogy.** Ordering delivery to a friend's address versus picking it up yourself. `cli_11.py` picks the ElevenLabs audio up locally and then uploads it; Google TTS delivers it directly.
- **Common misconception.** "Synthesis produces a local `.mp3` I can play." No local file is created ("no local file is created", `synthesis_audio_en/README.md:8`), so the local "skip if it exists" check at `synthesis_audio_en/cli.py:57-58` can never fire. Also, the object is named `.mp3` but the request asks for `LINEAR16` (`synthesis_audio_en/cli.py:73`), which the TTS library documents as uncompressed PCM that "also contains a WAV header" (`texttospeech_v1/types/cloud_tts.py:90-93`, google-cloud-texttospeech 2.38.0). See §9 E7.

### 3.8 Secrets hygiene: `.gitignore` is not `.dockerignore`
- **Explanation.** The README promises the key won't reach GitHub because of `.gitignore` (`README.md:103-106`), and for Git that is true. But `docker build` sends the **whole folder** (the build context) to the builder, and `COPY . ./` copies all of it, `secrets/` included, into an image layer. On `main` no `.dockerignore` excludes it, so the optional `docker push` (`transcribe_audio/README.md:136-140`) would publish the key. Captured with a stand-in file: `docker run --rm --entrypoint ls transcribe_audio -la /app/secrets` lists `mega-pipeline.json`; after adding a `.dockerignore` with `secrets/` and rebuilding, the same command says `ls: cannot access '/app/secrets': No such file or directory`, and the app still finds the key through the mount at run time. The README's "canonical (best) way" (`README.md:106`), keeping secrets outside the repo, is what `solution` and L04's `flexible-workflow` do: a `secrets/` folder two levels up from the component, mounted at `/secrets` at **run** time (`origin/solution:transcribe_audio/docker-shell.sh:9-10`, `:96-99`).
- **Mental model.** `.gitignore` filters what goes into the *history book*; `.dockerignore` filters what goes into the *shipping box*. Different boxes.
- **Analogy.** You kept your house key out of the photo album (Git) but packed it in the moving box (the image) you're about to mail to strangers (Docker Hub).
- **Common misconception.** "Docker reads `.gitignore`." It doesn't. And the build's `SecretsUsedInArgOrEnv` warning doesn't catch this: it only flags the *name* of the variable on Dockerfile line 10, not the copied file.

---

## 4. Step-by-step walkthrough

Steps follow the README order: the main README (clone, key), then the five component READMEs, A → E (`README.md:114-120`). Commands in code spans are verbatim from the README unless marked *(extra)*. The video's top-left tracker numbers the README bullets (R1–R2, A1–A13, B1–B13, C1–C12, D1–D13, E1–E12, H1–H3 for the push, X1–X3 for the bonus); those numbers are given in brackets. Run every `docker` command **from inside the component folder**.

**About the outputs below.** They are real, trimmed (first and last lines, with `…` between) from the 2026-10-13 captures in `assets/terminal/` (file names given with each block; `[exit N]` lines omitted, exit codes mentioned where they matter). What differs from your laptop:
- The laptop was Debian 12 Linux (Python 3.11.2, user `student`). On macOS your prompt ends in `%` and Docker Desktop runs the containers; the commands are the same.
- The builds ran with `--network host` and from a capture-only copy of the base image that adds the recording machine's network certificate and https apt sources (its line 1 named that copy; every other line was the README's). The blocks below leave out the lines that show this. Your first build pulls `docker.io/library/python:3.12-slim-bookworm`, and apt fetches from `http://deb.debian.org`.
- Your terminal shows BuildKit's compact live view (`[+] Building …`, one row per step). Blocks of `#N …` lines are the same build's full log (what `--progress=plain` prints) and are labelled "full log".
- After the first interactive session (`transcribe_audio/01-docker-run-tty.txt`), the in-container commands were piped into a container started like the README's `docker run`, so their files have no prompt; it is written in front of each command below as `app@…:/app$`. The part after `app@` is the container's id and differs on every run.
- **No course key existed.** Every step that calls Google is described from the code and marked *expected*; the missing-key errors shown are real.
- The recording laptop's folder belonged to uid 1000, the same uid as `app` in the image (§6 G7). The group name was set to `group-01`, the README's example.
- Versions are those of 2026-10-13 (uv 0.13.0, pip 26.2.1, Python 3.12.15, CPython 3.15.0, the package versions); yours may be newer.

### Part 0: before you start

**Step 0. Docker and uv are ready** (`README.md:22-26`).
- **Action:** start Docker Desktop. *(extra)* `docker version` checks that both the client and the engine answer (`laptop/01-docker-version.txt`):
  ```
  $ docker version
  Client: Docker Engine - Community
   Version:           29.8.2
   API version:       1.56
  …
  Server: Docker Engine - Community
   Engine:
    Version:          29.8.2
  …
  ```
  *(extra)* Pull the base image once (`laptop/02-base-image.txt`):
  ```
  $ docker pull python:3.12-slim-bookworm; docker run --rm python:3.12-slim-bookworm python --version
  3.12-slim-bookworm: Pulling from library/python
  Digest: sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258
  Status: Image is up to date for python:3.12-slim-bookworm
  docker.io/library/python:3.12-slim-bookworm
  Python 3.12.15
  ```
- **Checkpoint:** `uv --version` prints a version (Tutorial 0). If it says `command not found`, Step 5 shows the README's installers.
- **If it fails:** a client block followed by an error instead of a `Server:` block means the engine isn't running: start Docker Desktop and wait until it says it is running.

### Part 1: the main README

**Step 1. Clone** [R1] (`README.md:32-35`).
```
$ git clone https://github.com/dlops-io/mega-pipeline.git
Cloning into 'mega-pipeline'...
```
(`laptop/03-clone.txt`)
- **Under the hood:** this gets branch `main`: five component folders, each with `README.md`, `cli.py`, `secrets/.gitkeep` and (except `generate_text/`) a `.gitignore`.

**Step 2. `cd mega-pipeline`, and look around** [R2] (`README.md:34`).
- *(extra)* The files, the commit and the branch (`laptop/04-ls.txt`):
  ```
  $ ls; git log --oneline -1; git branch
  README.md
  generate_text
  mega-pipeline-bucket.png
  mega-pipeline-flow.png
  synthesis_audio
  synthesis_audio_en
  transcribe_audio
  translate_text
  c6bbc9b fix for Google Speech-to-Text automatically breaks longer audio files into chunks separated by natural pauses.
  * main
  ```
- *(extra)* All five folders (`laptop/05-ls-components.txt`, trimmed):
  ```
  $ ls -a transcribe_audio generate_text synthesis_audio_en translate_text synthesis_audio
  generate_text:
  .
  ..
  README.md
  cli.py
  main.py
  pyproject.toml
  secrets

  synthesis_audio:
  .
  ..
  .gitignore
  README.md
  cli.py
  cli_11.py
  secrets
  …
  transcribe_audio:
  .
  ..
  .gitignore
  README.md
  cli.py
  secrets
  …
  ```
- **Checkpoint:** no `Dockerfile` in any folder ("none of them come with a `Dockerfile` already written", `README.md:114`). Remember two differences: `generate_text/` already has `pyproject.toml` and `main.py` but no `.gitignore` (Step 15), and `synthesis_audio/` has the bonus `cli_11.py` (Step 23).

**Step 3. The key, into every component** (`README.md:90-106`).
- **Action:** download `mega-pipeline.json` with the Canvas link at `README.md:99` (HarvardKey login) and put a copy inside each component's `secrets/` folder (`README.md:97`). The copy loop in the checklist is one way.
- **Under the hood:** the file is the private key of a service account in the course's project: a robot Google identity your code acts as (3.6). Git ignores it (`.gitignore:4` at the root, `/secrets` in each component's `.gitignore`).
- **Checkpoint:** `ls transcribe_audio/secrets` shows `mega-pipeline.json`, and `git status` stays clean.
- **If it fails:**
  - The code expects exactly `mega-pipeline.json` (`README.md:195`); browsers sometimes save `mega-pipeline (1).json`.
  - The component READMEs link Canvas file `23163432` (e.g. `transcribe_audio/README.md:17`), the main README `25687801` (`README.md:99`, updated on lecture day). Use the main README's (§9 E5).
- Never `cat` the key, paste it into a chat or commit it anywhere.

### Part A: 📝 Task A · `transcribe_audio` (`transcribe_audio/README.md`)

**Step 4. `cd transcribe_audio`; the key in `secrets/`** [A1, A2] (`:11-17`).
- *(extra)* Check that the key is there and that Git ignores it. Recorded with an 82-byte stand-in file in place of the key, after Step 10's edit to `cli.py` (`laptop/20-g1-git-ignores-key.txt`):
  ```
  $ ls secrets; git status --short; git check-ignore -v secrets/mega-pipeline.json
  mega-pipeline.json
   M cli.py
  transcribe_audio/.gitignore:3:/secrets	secrets/mega-pipeline.json
  ```
- **Under the hood:** `git check-ignore -v` names the rule that ignores a path: line 3 of this folder's `.gitignore`.

**Step 5. `uv init --bare`** [A3] (`:19-34`).
- **If uv is missing** (`:26-34`, "Don't have `uv` installed?"). The recording laptop had none (`laptop/06-uv-missing.txt`, `07-uv-install.txt`, `08-uv-version.txt`):
  ```
  $ uv --version
  bash: line 1: uv: command not found
  $ curl -LsSf https://astral.sh/uv/install.sh | sh
  downloading uv 0.13.0 x86_64-unknown-linux-gnu
  installing to /home/student/.local/bin
    uv
    uvx
  everything's installed!

  To add $HOME/.local/bin to your PATH, either restart your shell or run:

      source $HOME/.local/bin/env (sh, bash, zsh)
  …
  ```
  Then, in a **new** terminal, `cd` back into `transcribe_audio`:
  ```
  $ uv --version
  uv 0.13.0 (x86_64-unknown-linux-gnu)
  ```
  On Windows use the PowerShell line (`:32`); `pip install uv` (`:34`) is the third option.
- **Action** (`laptop/09-uv-init.txt`, `10-cat-pyproject.txt`):
  ```
  $ uv init --bare
  Initialized project `transcribe-audio`
  $ cat pyproject.toml
  [project]
  name = "transcribe-audio"
  version = "0.1.0"
  requires-python = ">=3.11"
  dependencies = []
  ```
  (`cat` is *(extra)*.)
- **Under the hood:** `--bare` writes only `pyproject.toml` (no `main.py`, no README, no `git init`). The project name comes from the folder name, with `_` turned into `-`. `requires-python` comes from the Python uv finds on **your laptop**: 3.11.2 here, hence `>=3.11`.
- **Checkpoint:** `requires-python` is `>=3.12` or lower, so the image's Python 3.12 satisfies it. If yours says `>=3.13` or higher, change it to `requires-python = ">=3.12"` now (not in the README; §6 G3).
- **If it fails:** `uv: command not found` right after installing means this shell's `PATH` predates `~/.local/bin`: open a new terminal, or run `source $HOME/.local/bin/env` as the installer says. `git status` won't list the new file: `transcribe_audio/.gitignore:6` ignores `pyproject.toml` (§6 G14).

**Step 6. Write the Dockerfile** [A4] (`:36-92`).
- **Action:** create a file named `Dockerfile` (no extension) in `transcribe_audio/`. The README gives the `FROM` line in its text ("base it from `python:3.12-slim-bookworm`", `:41`) and the rest as six code blocks (`:45`, `:50-55`, `:60-69`, `:76-77`, `:82-83`, `:88-89`). In order, with blank lines between them, that is the 30-line file the recording built (`files/transcribe_audio.Dockerfile`):
  ```dockerfile
  FROM python:3.12-slim-bookworm

  ARG DEBIAN_PACKAGES="build-essential ffmpeg"

  ENV DEBIAN_FRONTEND=noninteractive
  ENV LANG=C.UTF-8
  ENV PYTHONUNBUFFERED=1
  ENV UV_LINK_MODE=copy
  ENV UV_PROJECT_ENVIRONMENT=/home/app/.venv
  ENV GOOGLE_APPLICATION_CREDENTIALS=secrets/mega-pipeline.json

  RUN apt-get update && \
      apt-get upgrade -y && \
      apt-get install -y --no-install-recommends $DEBIAN_PACKAGES && \
      apt-get clean && \
      rm -rf /var/lib/apt/lists/* && \
      pip install --no-cache-dir --upgrade pip && \
      pip install uv && \
      useradd -ms /bin/bash app -d /home/app -u 1000 && \
      mkdir -p /app && \
      chown app:app /app

  USER app
  WORKDIR /app

  COPY --chown=app:app . ./
  RUN uv sync

  ENTRYPOINT ["/bin/bash"]
  CMD ["-c", "source /home/app/.venv/bin/activate && exec bash"]
  ```
- **Under the hood:** §3.3 explains each line; §5 compares it with the appendix's sample. The line numbers above (3 = `ARG`, 9 = `UV_PROJECT_ENVIRONMENT`, 10 = `GOOGLE_APPLICATION_CREDENTIALS`, 26 = `COPY`, 27 = `uv sync`, 29 = `ENTRYPOINT`) are the ones Docker's warnings and errors refer to.
- **Checkpoint** *(extra)* (`laptop/11-ls-before-build.txt`):
  ```
  $ ls -a; git status
  .
  ..
  .gitignore
  Dockerfile
  README.md
  cli.py
  pyproject.toml
  secrets
  On branch main
  Your branch is up to date with 'origin/main'.

  nothing to commit, working tree clean
  ```
  The new `Dockerfile` and `pyproject.toml` are invisible to Git: `transcribe_audio/.gitignore:5-6` (§6 G14).
- **If it fails:** an editor that adds `.txt` (Windows hides extensions) leaves you without a file named `Dockerfile`, and `docker build` can't find one. Don't paste the appendix's version unchanged: its `ARG` has `curl`, not `ffmpeg` (`README.md:179`; §6 G8).

**Step 7. Build the image** [A5] (`:94-95`).
- **Action:** the README says "Build your docker image and give your image the name `transcribe_audio`" and gives no command. The standard one, from `transcribe_audio/`:
  ```bash
  docker build -t transcribe_audio .
  ```
- **Captured** (the full log, trimmed; `laptop/12-build.txt`, 1,406 lines):
  ```
  #1 [internal] load build definition from Dockerfile
  #1 WARN: SecretsUsedInArgOrEnv: Do not use ARG or ENV instructions for sensitive data (ENV "GOOGLE_APPLICATION_CREDENTIALS") (line 10)
  …
  #6 [internal] load build context
  #6 transferring context: 11.84kB 0.0s done
  …
  #5 [2/5] RUN apt-get update &&     apt-get upgrade -y &&     apt-get install -y --no-install-recommends build-essential ffmpeg &&     apt-get clean && …
  …
  #5 6.775 0 upgraded, 237 newly installed, 0 to remove and 0 not upgraded.
  #5 6.775 Need to get 205 MB of archives.
  #5 6.775 After this operation, 786 MB of additional disk space will be used.
  …
  #5 33.48 update-alternatives: warning: skip creation of /usr/share/man/man1/lzma.1.gz because associated file /usr/share/man/man1/xz.1.gz (of link group lzma) doesn't exist
  …
  #5 41.72 Successfully installed pip-26.2.1
  #5 41.73 WARNING: Running pip as the 'root' user can result in broken permissions and conflicting behaviour with the system package manager, …
  …
  #5 46.08 Successfully installed uv-0.13.0
  …
  #5 DONE 46.9s

  #7 [3/5] WORKDIR /app
  #7 DONE 0.1s

  #8 [4/5] COPY --chown=app:app . ./
  #8 DONE 0.0s

  #9 [5/5] RUN uv sync
  #9 0.143 Using CPython 3.12.15 interpreter at: /usr/local/bin/python3
  #9 0.143 Creating virtual environment at: /home/app/.venv
  #9 0.147 Resolved 1 package in 2ms
  #9 0.148 Checked in 0.00ms
  #9 DONE 0.2s
  …
  #10 naming to docker.io/library/transcribe_audio:latest done
  …
   1 warning found (use docker --debug to expand):
   - SecretsUsedInArgOrEnv: Do not use ARG or ENV instructions for sensitive data (ENV "GOOGLE_APPLICATION_CREDENTIALS") (line 10)
  ```
  *(extra)* (`laptop/13-images.txt`):
  ```
  $ docker images transcribe_audio
  IMAGE                     ID             DISK USAGE   CONTENT SIZE   EXTRA
  transcribe_audio:latest   1d55dcc2f1a2       1.35GB          357MB
  ```
- **Under the hood:**
  - The `.` is the **build context**: the whole folder is sent to the builder (11.84 kB here), secrets included if they are there (§3.8).
  - Five build steps: `[1/5] FROM` (your first build pulls the base image for your machine's architecture), `[2/5]` the one big `RUN` (237 apt packages, a 205 MB download, then pip and uv: 46.9 s), `[3/5] WORKDIR`, `[4/5] COPY`, `[5/5] RUN uv sync` with the image's own Python 3.12.15. `Resolved 1 package` is the project itself: nothing third-party yet.
  - The ten `update-alternatives: warning: skip creation of /usr/share/man/man1/…` lines are harmless: slim images ship without man pages. The appendix's `for i in $(seq 1 8); do mkdir -p "/usr/share/man/man${i}"; done` (`README.md:200`) recreates those folders, which some packages' install scripts need.
  - The `SecretsUsedInArgOrEnv` warning fires because the variable's *name* sounds secret. Its value is only a path, so it is harmless, and it appears on every build.
- **Checkpoint:** `naming to docker.io/library/transcribe_audio:latest`, and `[5/5]` says `Using CPython 3.12.15 interpreter at: /usr/local/bin/python3`.
- **If it fails:**
  - Skipped Step 5 (captured with a copy of the folder without `pyproject.toml`, `laptop/26-g21-no-pyproject.txt`):
    ```
    #9 [5/5] RUN uv sync
    #9 0.077 error: No `pyproject.toml` found in current directory or any parent directory
    #9 ERROR: process "/bin/sh -c uv sync" did not complete successfully: exit code: 2
    …
    Dockerfile:27
    --------------------
      25 |     
      26 |     COPY --chown=app:app . ./
      27 | >>> RUN uv sync
      28 |     
      29 |     ENTRYPOINT ["/bin/bash"]
    --------------------
    ERROR: failed to build: failed to solve: process "/bin/sh -c uv sync" did not complete successfully: exit code: 2
    ```
    Run `uv init --bare` in this folder and build again (§6 G21).
  - `Downloading cpython-…` / `Using CPython 3.1x.x` (anything but 3.12.15) in `[5/5]` means `requires-python` is above 3.12 (§6 G3).

**Step 8. Run the container** [A6] (`:97-102`).
- **Captured in a real terminal** (`transcribe_audio/01-docker-run-tty.txt`; all commands after the prompt are *(extra)* checks):
  ```
  $ docker run --rm -ti -v "$(pwd):/app" transcribe_audio
  app@5b4d4981ec25:/app$ which python
  /home/app/.venv/bin/python
  app@5b4d4981ec25:/app$ python --version
  Python 3.12.15
  app@5b4d4981ec25:/app$ ls -a
  .  ..  .gitignore  Dockerfile  README.md  cli.py  pyproject.toml  secrets
  app@5b4d4981ec25:/app$ echo $GOOGLE_APPLICATION_CREDENTIALS
  secrets/mega-pipeline.json
  app@5b4d4981ec25:/app$ python cli.py --help
  Traceback (most recent call last):
    File "/app/cli.py", line 9, in <module>
      from google.cloud import storage
  ModuleNotFoundError: No module named 'google'
  app@5b4d4981ec25:/app$ exit
  exit
  ```
- **Under the hood:**
  - `-ti` gives an interactive terminal; `--rm` deletes the container (and its writable layer) on exit; `-v "$(pwd):/app"` lays your current folder over the image's `/app` (3.4). The README: "when you change a source code file using VSCode from your host machine, the files are automatically changed inside the container" (`:102`).
  - The container runs `/bin/bash -c "source /home/app/.venv/bin/activate && exec bash"`: activate, then replace itself with an interactive bash. That bash reads `/home/app/.bashrc`, which resets the prompt, so you see `app@<id>:/app$` without a `(transcribe-audio)` prefix; the venv is still active (`which python`).
  - `ls -a` shows your laptop's files. `python cli.py --help` fails because the Google packages aren't installed yet: that is Step 9.
- **Checkpoint:** the prompt `app@<id>:/app$` and `which python` → `/home/app/.venv/bin/python`.
- **If it fails:**
  - Windows: run it in Git BASH, keep the quotes around `$(pwd)`, and if Docker says `the input device is not a TTY`, put `winpty` in front (`README.md:227-236`).
  - `/app` looks empty or shows the whole repo: you ran `docker run` from the wrong folder. `"$(pwd)"` must be the component folder.

**Step 9. `uv add` the packages, inside the container** [A7] (`:104-110`).
- **Action:** the README lists `google-cloud-storage`, `google-cloud-speech` and `ffmpeg-python` under "`uv add` the following" (`:105-108`); one command adds all three (`transcribe_audio/02-uv-add.txt`):
  ```
  app@…:/app$ uv add google-cloud-storage google-cloud-speech ffmpeg-python
  Resolved 27 packages in 1.07s
  Downloading cryptography (4.5MiB)
  Downloading grpcio (6.8MiB)
   Downloaded cryptography
   Downloaded grpcio
  Prepared 26 packages in 920ms
  Installed 26 packages in 99ms
   + certifi==2026.7.22
   + cffi==2.1.1
  …
   + ffmpeg-python==0.2.0
  …
   + google-cloud-speech==2.41.0
   + google-cloud-storage==3.17.0
  …
   + urllib3==2.8.0
  ```
- *(extra)* Where everything landed (`transcribe_audio/03-cat-pyproject.txt`, `04-ls.txt`, `09-uv-tree.txt`, `10-venv-where.txt`):
  ```
  app@…:/app$ cat pyproject.toml
  [project]
  name = "transcribe-audio"
  version = "0.1.0"
  requires-python = ">=3.11"
  dependencies = [
      "ffmpeg-python>=0.2.0",
      "google-cloud-speech>=2.41.0",
      "google-cloud-storage>=3.17.0",
  ]
  app@…:/app$ ls -la
  total 176
  drwxr-xr-x 3 app  app    4096 Oct 13 01:47 .
  drwxr-xr-x 1 root root   4096 Oct 13 01:47 ..
  -rw-r--r-- 1 app  app     104 Oct 13 01:42 .gitignore
  -rw-r--r-- 1 app  app     801 Oct 13 01:42 Dockerfile
  -rw-r--r-- 1 app  app    6161 Oct 13 01:42 README.md
  -rw-r--r-- 1 app  app    4417 Oct 13 01:47 cli.py
  -rw-r--r-- 1 app  app     199 Oct 13 01:47 pyproject.toml
  drwxr-xr-x 2 app  app    4096 Oct 13 01:45 secrets
  -rw-r--r-- 1 app  app  138445 Oct 13 01:47 uv.lock
  app@…:/app$ uv tree --depth 1
  Resolved 27 packages in 1ms
  transcribe-audio v0.1.0
  ├── ffmpeg-python v0.2.0
  ├── google-cloud-speech v2.41.0
  └── google-cloud-storage v3.17.0
  app@…:/app$ which python; echo $VIRTUAL_ENV; ls /home/app/.venv/lib/python3.12/site-packages | head -5
  /home/app/.venv/bin/python
  /home/app/.venv
  __pycache__
  _cffi_backend.cpython-312-x86_64-linux-gnu.so
  certifi
  certifi-2026.7.22.dist-info
  cffi
  ```
- **Under the hood:** three packages asked for, 26 installed: each brings its own dependencies (`grpcio`, `protobuf`, `google-auth`, `requests` …), and `Resolved 27` counts the project too. The list (`pyproject.toml`, each with a lower bound) and the receipt (`uv.lock`, 138,445 bytes) are written under `/app`, i.e. **into your laptop's folder**. The 26 packages went into `/home/app/.venv`, on the container's throwaway layer (3.4).
- **Checkpoint:** on your laptop, `pyproject.toml` lists three dependencies and `uv.lock` exists.
- **If it fails:**
  - On a Linux laptop whose component folder isn't owned by uid 1000 (captured with a root-owned copy, `transcribe_audio/13-g7-root-owned.txt`):
    ```
    app@…:/app$ ls -ld /app; id; uv add requests
    drwxr-xr-x 5 root root 4096 Oct 13 01:48 /app
    uid=1000(app) gid=1000(app) groups=1000(app)
    error: failed to create file `/app/pyproject.toml`: Permission denied (os error 13)
    ```
    Fix on the laptop: `sudo chown -R 1000:1000 .` in the component folder (§6 G7). Docker Desktop on macOS and Windows handles ownership for you.
  - The package is `ffmpeg-python`. `uv add ffmpeg` installs a different project, and `cli.py` then fails with `AttributeError: module 'ffmpeg' has no attribute 'input'` (§6 G9).
- The README adds: "After exiting the container, re-build the image so the dependencies are baked in for future runs" (`:110`). That is Step 14.

**Step 10. Set your group name; check the CLI** [A8, A9] (`:112-127`).
- **Action:** on your laptop, in VS Code, change line 21 of `cli.py`, `group_name = "pavlos"`, to your team's name (`:114`). The README warns: "get it wrong and your work lands under the wrong team, or overwrites someone else's" (`README.md:124`).
- *(extra)* The container sees the edit at once, through the mount (`transcribe_audio/06-group-name.txt`):
  ```
  app@…:/app$ grep -n "^group_name" cli.py
  21:group_name = "group-01" # This needs to be your Group name e.g: group-01, group-02, group-03, group-04, group-05, ...
  ```
- **Action** [A9] (`transcribe_audio/05-help.txt`):
  ```
  app@…:/app$ python cli.py --help
  usage: cli.py [-h] [-d] [-t] [-u]

  Transcribe audio file to text

  options:
    -h, --help        show this help message and exit
    -d, --download    Download audio files from GCS bucket
    -t, --transcribe  Transcribe audio files to text
    -u, --upload      Upload transcribed text to GCS bucket
  ```
- **Checkpoint:** identical, line for line, to the README's block (`:117-127`). A's `--help` needs no key: its clients are created inside the functions.
- Use **the same** group name in all five `cli.py` files (and `cli_11.py` for the bonus): each stage downloads `<prefix>/<group_name>/…`, written by the stage before (§6 G2).

**Step 11. Download** [A10] (`:131`; `README.md:134`).
- **Action:** `python cli.py -d`, or in long form `python cli.py --download`, with your key in `secrets/`.
- **Recorded without the key** (`transcribe_audio/07-download.txt`; this is what a missing or misplaced key looks like):
  ```
  app@…:/app$ python cli.py --download
  Args: Namespace(download=True, transcribe=False, upload=False)
  download
  Traceback (most recent call last):
    File "/app/cli.py", line 154, in <module>
      main(args)
    File "/app/cli.py", line 122, in main
      download()
    File "/app/cli.py", line 36, in download
      client = storage.Client()
               ^^^^^^^^^^^^^^^^
  …
    File "/home/app/.venv/lib/python3.12/site-packages/google/cloud/_helpers/__init__.py", line 170, in _determine_default_project
      _, project = google.auth.default()
                   ^^^^^^^^^^^^^^^^^^^^^
  …
    File "/home/app/.venv/lib/python3.12/site-packages/google/auth/_default.py", line 178, in load_credentials_from_file
      raise exceptions.DefaultCredentialsError(
  google.auth.exceptions.DefaultCredentialsError: File secrets/mega-pipeline.json was not found.
  ```
  Read it from the top: your code (line 36) built a storage client; the client asked `google.auth.default()` for credentials; that function looked for the file `GOOGLE_APPLICATION_CREDENTIALS` names, relative to `/app`, and didn't find it (3.6). Even this failed run left two empty folders on your laptop, `input_audios/` and `text_prompts/group-01/` (`transcribe_audio/08-ls-after-download.txt`): `makedirs()` runs before the client is built.
- **Under the hood** (`transcribe_audio/cli.py:29-43`): delete the local `input_audios/`, recreate it and `text_prompts/<group>/`, `storage.Client()` (ADC), `get_bucket("mega-pipeline-bucket")`, list every object under `input_audios/` (shared by all groups), skip the zero-byte "folder" object, and download each file to the same relative path.
- **Expected with your key** (from the code; not recorded): `Args: …`, `download`, then one line per object name (`print(blob.name)`, line 41), such as `input_audios/input-….mp3`; the recordings appear in `input_audios/` on your laptop.
- **If it fails:** `DefaultCredentialsError: File secrets/mega-pipeline.json was not found.` has three usual causes: the key isn't in *this* component's `secrets/`, you `cd`'d away from `/app`, or you ran `docker run` from the wrong laptop folder (§6 G5). A `403 … does not have storage.buckets.get access` would mean the key lacks rights on the bucket: ask the staff.

**Step 12. Transcribe** [A11] (`:132`; `README.md:135`).
- **Action:** `python cli.py -t` / `python cli.py --transcribe`, with your key.
- **Under the hood** (`transcribe_audio/cli.py:46-96`), for each file in `input_audios/`:
  1. the `uuid` is the file name without `.mp3`;
  2. skip it if `text_prompts/<group>/<uuid>.txt` already exists (`:61-62`);
  3. convert MP3 to FLAC with ffmpeg in a temporary folder (`:65-69`);
  4. send the bytes inline to `long_running_recognize` with `language_code="en-US"` and wait up to 90 s (`:75-78`);
  5. join the transcript of every result segment (`:84-91`; the `c6bbc9b` fix: long audio comes back in several pieces) and write the `.txt` (`:95-96`).
- **Expected with your key** (from the code; not recorded): `transcribe`, `Transcribing: input_audios/input-….mp3`, ffmpeg's log, `response: results { alternatives { transcript: "…" …`, then the joined transcript.
- **Checkpoint:** open `text_prompts/<group>/input-….txt` on your laptop: words, not the literal `None` (§6 G20).
- **If it fails:** `FileNotFoundError: [Errno 2] No such file or directory: 'ffmpeg'` means the `ffmpeg` program isn't in the image (line 3, §6 G8); `ModuleNotFoundError: No module named 'ffmpeg'` means Step 9 was skipped or the image was never rebuilt (§6 G10); an `ffmpeg.Error` on a file that isn't audio means a stray file such as `.DS_Store` in `input_audios/` (§6 G17).

**Step 13. Upload** [A12] (`:133`; `README.md:136`).
- **Action:** `python cli.py -u` / `python cli.py --upload`, with your key.
- **Under the hood** (`transcribe_audio/cli.py:99-115`): glob `text_prompts/<group>/input-*.txt` and upload each file under the identical object name; `upload_from_filename` overwrites an existing object of that name.
- **Expected with your key** (from the code): `upload`, then `Uploading: text_prompts/<group>/input-….txt text_prompts/<group>/input-….txt` per file.
- **Checkpoint:** your group's transcribe cell lights up on the [leaderboard](http://ac215-mega-pipeline.dlops.io/) (`:134`).
- **Tip:** the flags combine: `python cli.py -d -t -u` runs all three, in that order (`transcribe_audio/cli.py:121-126`).

**Step 14. Exit, and bake the packages in** [A13] (`:110`).
- **Action:** `exit`. `--rm` removes the container and its throwaway layer, and the 26 packages with it.
- *(extra)* Back on the laptop, everything written under `/app` survived (`laptop/14-host-after-uv-add.txt`, trimmed):
  ```
  $ ls -a; cat pyproject.toml; head -c 300 uv.lock; echo; wc -c uv.lock; git status --short
  .
  ..
  .gitignore
  Dockerfile
  README.md
  cli.py
  input_audios
  pyproject.toml
  secrets
  text_prompts
  uv.lock
  [project]
  name = "transcribe-audio"
  …
  version = 1
  revision = 5
  requires-python = ">=3.11"
  resolution-markers = [
      "python_full_version >= '3.14'",
      "python_full_version < '3.14'",
  ]
  …
  138445 uv.lock
   M cli.py
  ```
  `git status` shows only `cli.py`: the `.gitignore` hides the rest (§6 G14).
- *(extra)* **The trap.** A new container from the image built in Step 7 (`transcribe_audio/11-g10-new-container.txt`):
  ```
  app@…:/app$ python cli.py --help
  Traceback (most recent call last):
    File "/app/cli.py", line 9, in <module>
      from google.cloud import storage
  ModuleNotFoundError: No module named 'google'
  ```
  The packages lived only in the old container (§6 G10).
- **Action:** rebuild with the same command. Captured live view (`laptop/15-rebuild.txt`, trimmed):
  ```
  $ docker build -t transcribe_audio .
  [+] Building 9.9s (10/10) FINISHED                               docker:default
   => [internal] load build definition from Dockerfile                       0.0s
  …
   => => transferring context: 143.47kB                                      0.0s
   => CACHED [2/5] RUN apt-get update &&     apt-get upgrade -y &&     apt-  0.0s
   => CACHED [3/5] WORKDIR /app                                              0.0s
   => [4/5] COPY --chown=app:app . ./                                        0.0s
   => [5/5] RUN uv sync                                                      2.9s
   => exporting to image                                                     6.8s
  …
  ```
  The same build's full log (`laptop/15-rebuild.plain.txt`): `Using CPython 3.12.15 interpreter at: /usr/local/bin/python3`, `Resolved 27 packages in 1ms`, `Prepared 26 packages in 2.47s`, `Installed 26 packages in 174ms`.
- **Under the hood:** build steps 2 and 3 come from the cache. Build step 4 copies the changed folder (`cli.py`, the new `pyproject.toml` and `uv.lock`, the downloaded folders), so step 5 runs again, and `uv sync` installs exactly the locked versions into the image.
- *(extra)* (`laptop/16-images-after.txt`, `17-history.txt`; the history's rows below `ARG` belong to the base image and are cut):
  ```
  $ docker images transcribe_audio
  IMAGE                     ID             DISK USAGE   CONTENT SIZE   EXTRA
  transcribe_audio:latest   55af020104ea       1.48GB          388MB
  $ docker history transcribe_audio
  IMAGE          CREATED          CREATED BY                                      SIZE      COMMENT
  55af020104ea   8 seconds ago    CMD ["-c" "source /home/app/.venv/bin/activa…   0B        buildkit.dockerfile.v0
  <missing>      8 seconds ago    ENTRYPOINT ["/bin/bash"]                        0B        buildkit.dockerfile.v0
  <missing>      8 seconds ago    RUN |1 DEBIAN_PACKAGES=build-essential ffmpe…   105MB     buildkit.dockerfile.v0
  <missing>      11 seconds ago   COPY --chown=app:app . ./ # buildkit            193kB     buildkit.dockerfile.v0
  <missing>      4 minutes ago    WORKDIR /app                                    4.1kB     buildkit.dockerfile.v0
  <missing>      4 minutes ago    USER app                                        0B        buildkit.dockerfile.v0
  <missing>      4 minutes ago    RUN |1 DEBIAN_PACKAGES=build-essential ffmpe…   842MB     buildkit.dockerfile.v0
  <missing>      4 minutes ago    ENV GOOGLE_APPLICATION_CREDENTIALS=secrets/m…   0B        buildkit.dockerfile.v0
  <missing>      4 minutes ago    ENV UV_PROJECT_ENVIRONMENT=/home/app/.venv      0B        buildkit.dockerfile.v0
  <missing>      4 minutes ago    ENV UV_LINK_MODE=copy                           0B        buildkit.dockerfile.v0
  <missing>      4 minutes ago    ENV PYTHONUNBUFFERED=1                          0B        buildkit.dockerfile.v0
  <missing>      4 minutes ago    ENV LANG=C.UTF-8                                0B        buildkit.dockerfile.v0
  <missing>      4 minutes ago    ENV DEBIAN_FRONTEND=noninteractive              0B        buildkit.dockerfile.v0
  <missing>      4 minutes ago    ARG DEBIAN_PACKAGES=build-essential ffmpeg      0B        buildkit.dockerfile.v0
  …
  ```
  One row per instruction, newest first. Metadata rows are `0B`; the apt `RUN` is 842 MB of compilers, ffmpeg and their libraries; the `uv sync` layer is 105 MB (the packages plus uv's download cache, §8 B4).
- **Checkpoint** *(extra)*, in a container of the rebuilt image (`transcribe_audio/12-after-rebuild.txt`):
  ```
  app@…:/app$ python -c "import google.cloud.storage, google.cloud.speech, ffmpeg; print(\"imports ok\")"; uv --version; python --version
  imports ok
  uv 0.13.0 (x86_64-unknown-linux-gnu)
  Python 3.12.15
  ```
- Because `COPY . ./` comes before `RUN uv sync`, every later edit in the folder, even the group name, re-runs `uv sync` on the next build (3.3, §8 B3).

### Part B: 🗒️ Task B · `generate_text` (`generate_text/README.md`)

Same recipe, two surprises.

**Step 15. `cd`, the key, and `uv init --bare` fails** [B1–B3] (`:11-24`).
- **Action:** `cd ../generate_text` and copy the key into its `secrets/` (`:13-17`).
- *(extra)* Look first (`laptop/30-b-ls.txt`):
  ```
  $ ls -a; cat pyproject.toml
  .
  ..
  README.md
  cli.py
  main.py
  pyproject.toml
  secrets
  [project]
  name = "generate-text"
  version = "0.1.0"
  requires-python = ">=3.14"
  dependencies = [
      "google-cloud-storage>=3.12.0",
      "google-genai>=2.8.0",
  ]
  ```
- **Action** [B3], as the README says (`:22`; `laptop/31-b-uv-init.txt`):
  ```
  $ uv init --bare
  error: Project is already initialized in `/home/student/mega-pipeline/generate_text` (`pyproject.toml` file exists)
  ```
  Exit status 2. The README still says to run it, and even promises "no sample `main.py`" (`:24`) next to a committed `main.py`. Skip this step and ignore `main.py` (a leftover that prints `Hello from generate-text!`).
- **Fix now** (not in the README): edit `pyproject.toml` line 4 to `requires-python = ">=3.12"` **before** the first build. The recording kept `>=3.14` until Step 19 to show what happens without the fix.

**Step 16. Dockerfile and build** [B4, B5] (`:36-95`).
- **Action:** the same Dockerfile as A's, with one line changed: line 3 becomes `ARG DEBIAN_PACKAGES="build-essential"` (`:45`), because "this component doesn't touch audio" (`:38`). Then `docker build -t generate_text .`
- **Captured** live view (`laptop/32-b-build.txt`, trimmed):
  ```
  $ docker build -t generate_text .
  [+] Building 54.0s (10/10) FINISHED                              docker:default
  …
   => [2/5] RUN apt-get update &&     apt-get upgrade -y &&     apt-get in  22.8s
   => [3/5] WORKDIR /app                                                     0.1s
   => [4/5] COPY --chown=app:app . ./                                        0.0s
   => [5/5] RUN uv sync                                                      5.9s
  …
  ```
  The live view hides what `uv sync` did; the full log shows it (`laptop/32-b-build.plain.txt`):
  ```
  #9 [5/5] RUN uv sync
  #9 0.669 Downloading cpython-3.15.0-linux-x86_64-gnu (download) (35.9MiB)
  #9 3.049  Downloaded cpython-3.15.0-linux-x86_64-gnu (download)
  #9 3.266 Using CPython 3.15.0
  #9 3.266 Creating virtual environment at: /home/app/.venv
  #9 4.407 Resolved 35 packages in 1.13s
  …
  #9 5.613 Installed 34 packages in 312ms
  …
  #9 5.613  + google-genai==2.30.0
  …
  ```
- **Under the hood:** the apt step runs again (a different package list: 46 packages, 73.8 MB, 22.8 s). The image's Python 3.12 is outside `>=3.14`, so uv downloaded the newest Python in range, CPython 3.15.0 at the time of recording, and built the venv on it (3.5, §6 G3). Both packages were already listed, so the first build already installs them.

**Step 17. Run, `uv add`, group name, `--help`** [B6–B9] (`:97-125`).
- **Action:** `docker run --rm -ti -v "$(pwd):/app" generate_text` (`:99`).
- *(extra)* Which Python the venv got (`generate_text/01-python-version.txt`):
  ```
  app@…:/app$ which python; python --version; readlink -f $(which python)
  /home/app/.venv/bin/python
  Python 3.15.0
  /home/app/.local/share/uv/python/cpython-3.15.0-linux-x86_64-gnu/bin/python3.15
  ```
- **Action** [B7] (`:104-106`; `generate_text/02-uv-add.txt`):
  ```
  app@…:/app$ uv add google-cloud-storage google-genai
  Resolved 35 packages in 14ms
  Checked 34 packages in 0.61ms
  ```
  Nothing new: `pyproject.toml` stays as it was (`generate_text/03-cat-pyproject.txt`); `uv add` only writes `uv.lock`.
- **Action** [B8]: set `group_name` on line 19 of `generate_text/cli.py`.
- **Action** [B9] (`generate_text/04-help.txt`):
  ```
  app@…:/app$ python cli.py --help
  usage: cli.py [-h] [-d] [-g] [-u]

  Generate text from prompt

  options:
    -h, --help      show this help message and exit
    -d, --download  Download text prompts from GCS bucket
    -g, --generate  Generate a text paragraph
    -u, --upload    Upload paragraph text to GCS bucket
  ```
  Identical to the README's block (`:116-124`), and it needs no key: the Gemini client, created at import (`generate_text/cli.py:23-25`), loads credentials only on its first request.

**Step 18. Download, generate, upload** [B10–B12] (`:127-132`; `README.md:139-144`).
- **Action:** `python cli.py -d`, `python cli.py -g`, `python cli.py -u` (long forms `--download`, `--generate`, `--upload`), with your key.
- **Under the hood:**
  - `--download` deletes the **whole** local `text_prompts/` and fetches only `text_prompts/<group>/input-*.txt` (`generate_text/cli.py:33-44`). If A hasn't uploaded for your group, nothing comes down, without an error.
  - `--generate` wraps each transcript in a fixed prompt ("Create a transcript for the podcast about cheese with 1000 or more words", `:65-72`) and calls Gemini on Vertex AI in `us-central1` with the model in `$GEMINI_MODEL`, default `gemini-2.5-flash-lite` (`:73-77`). It skips any transcript whose output already exists (`:57-58`).
  - `--upload` pushes `text_paragraphs/<group>/input-*.txt` (`:88-104`).
- **Expected with your key** (from the code; not recorded): the prompt printed, three blank lines, `Generated text:` and a long podcast script; then `upload` and one `Uploading: text_paragraphs/<group>/…` line per file.
- **Model retirement.** Vertex AI retires `gemini-2.5-flash-lite` on **2026-10-20**. After that date the default fails; start the container with a current model id instead *(extra)*:
  ```bash
  docker run --rm -ti -e GEMINI_MODEL=<current model> -v "$(pwd):/app" generate_text
  ```
- **If it fails:** `404 … Publisher Model … not found` means a retired or misspelled model; `429 RESOURCE_EXHAUSTED` means the class is sharing one project's quota: wait and retry (§6 G12).

**Step 19. Exit, fix `requires-python`, rebuild** [B13] (`:108`).
- The rebuild without the fix (`laptop/33-b-rebuild.plain.txt`) downloads CPython 3.15.0 **again** (`Downloading cpython-3.15.0-linux-x86_64-gnu (download) (35.9MiB)`) and installs 34 packages on it.
- *(extra)* After setting line 4 to `>=3.12` (`laptop/34-b-fix-requires-python.txt`):
  ```
  $ grep -n requires-python pyproject.toml; git status --short .
  4:requires-python = ">=3.12"
   M pyproject.toml
  ?? Dockerfile
  ?? uv.lock
  ```
  This folder has no `.gitignore`, so Git sees your `Dockerfile` and `uv.lock`, and the edited, tracked `pyproject.toml` (§9 E12).
- **Action:** `docker build -t generate_text .` Captured: `Building 10.4s` with `CACHED [2/5]`; the full log (`laptop/35-b-rebuild-312.plain.txt`):
  ```
  #9 [5/5] RUN uv sync
  #9 0.241 Using CPython 3.12.15 interpreter at: /usr/local/bin/python3
  #9 0.241 Creating virtual environment at: /home/app/.venv
  #9 1.741 Resolved 35 packages in 1.49s
  …
  #9 3.202 Installed 34 packages in 310ms
  ```
- **Checkpoint** *(extra)*, in a new container (`generate_text/05-python-version-312.txt`):
  ```
  app@…:/app$ python --version; readlink -f $(which python)
  Python 3.12.15
  /usr/local/bin/python3.12
  ```
  `python cli.py --help` prints the same block as before (`generate_text/06-help-312.txt`).

### Part C: 🔊 Task C · `synthesis_audio_en` (`synthesis_audio_en/README.md`)

**Step 20. The speed round begins** [C1–C12].
- **Action:** `cd ../synthesis_audio_en`, key into `secrets/`, then `uv init --bare` (`laptop/40-c-uv-init.txt`):
  ```
  $ uv init --bare; cat pyproject.toml
  Initialized project `synthesis-audio-en`
  [project]
  name = "synthesis-audio-en"
  version = "0.1.0"
  requires-python = ">=3.11"
  dependencies = []
  ```
  If yours stamps `>=3.13` or newer, change it to `>=3.12` (here, and in D and E).
- **Action:** the Dockerfile is B's (line 3 `ARG DEBIAN_PACKAGES="build-essential"`, `:45`). The text above it says "keep `ffmpeg` in the system packages" (`:38`); the code block, which leaves it out, is right: this `cli.py` never uses ffmpeg (§9 E3).
- **Action:** `docker build -t synthesis_audio_en .` (`laptop/41-c-build.txt`, trimmed):
  ```
  $ docker build -t synthesis_audio_en .
  [+] Building 0.6s (10/10) FINISHED                               docker:default
  …
   => CACHED [2/5] RUN apt-get update &&     apt-get upgrade -y &&     apt-  0.0s
   => CACHED [3/5] WORKDIR /app                                              0.0s
   => [4/5] COPY --chown=app:app . ./                                        0.0s
   => [5/5] RUN uv sync                                                      0.2s
  …
  ```
  0.6 s: C's Dockerfile is identical to B's up to line 21, so Docker reuses B's apt layer.
- **Action:** `docker run --rm -ti -v "$(pwd):/app" synthesis_audio_en` (`:99`), then (`synthesis_audio_en/01-uv-add.txt`, trimmed):
  ```
  app@…:/app$ uv add google-cloud-storage google-cloud-texttospeech
  Resolved 25 packages in 1.16s
  …
  Installed 24 packages in 223ms
  …
   + google-cloud-storage==3.17.0
   + google-cloud-texttospeech==2.38.0
  …
  ```
- **Action:** set `group_name` on line 18, then `python cli.py --help`. **Recorded without the key** (`synthesis_audio_en/03-help.txt`, trimmed):
  ```
  app@…:/app$ python cli.py --help
  Traceback (most recent call last):
    File "/app/cli.py", line 22, in <module>
      client = texttospeech.TextToSpeechLongAudioSynthesizeClient()
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  …
  google.auth.exceptions.DefaultCredentialsError: File secrets/mega-pipeline.json was not found.
  ```
  Line 22 builds the Text-to-Speech client as soon as the script starts, before argparse reads any flag, so even `--help` needs the key. **Expected** with the key, the README's block (`synthesis_audio_en/README.md:115-123`, `expected/synthesis_audio_en-help.txt`):
  ```
  $ python cli.py --help
  usage: cli.py [-h] [-d] [-s]

  Synthesis audio from text

  options:
    -h, --help       show this help message and exit
    -d, --download   Download paragraph of text from GCS bucket
    -s, --synthesis  Synthesis audio
  ```
- **Action:** `python cli.py -d` and `python cli.py -s` (`--download`, `--synthesis`; `README.md:147-151`), with your key.
- **Under the hood** (`synthesis_audio_en/cli.py:30-91`):
  - `--download` fetches `text_paragraphs/<group>/input-*.txt`, B's output.
  - `--synthesis` checks, per file, whether `text_audios/<group>/<uuid>.mp3` **already exists in the bucket** (`blob.exists()`, `:69`). If not, it sends a `SynthesizeLongAudioRequest` (voice `en-US-Standard-B`, `LINEAR16`, `output_gcs_uri=gs://mega-pipeline-bucket/text_audios/<group>/<uuid>.mp3`, `:77-86`) and waits up to 300 s for the operation (`:88-90`). Google's service writes the audio straight into the bucket, so C has no `--upload` ("synthesis writes audio directly to GCS — no separate `--upload` step needed", `README.md:151`).
- **Expected with your key** (from the code): `synthesis`, then `Audio file will be saved to GCS bucket automatically.` (`:91`) per file, and no new local audio file.
- **Action:** `exit`, `docker build -t synthesis_audio_en .` again: `Resolved 25 packages`, `Installed 24 packages`, `Building 10.1s` (`laptop/42-c-rebuild.*`).

### Part D: 🇫🇷 Task D · `translate_text` (`translate_text/README.md`)

**Step 21. Translate** [D1–D13].
- **Action:** `cd ../translate_text`, key, `uv init --bare` (``Initialized project `translate-text` ``, `>=3.11`, `laptop/50-d-uv-init.txt`), B's Dockerfile (`:45`; "No audio here, so drop `ffmpeg`", `:38`), `docker build -t translate_text .` (`CACHED [2/5]`, `Building 0.6s`), `docker run --rm -ti -v "$(pwd):/app" translate_text` (`:99`).
- **Action** (`translate_text/01-uv-add.txt`, trimmed):
  ```
  app@…:/app$ uv add google-cloud-storage google-cloud-translate
  Resolved 26 packages in 1.61s
  …
  Installed 25 packages in 181ms
  …
   + google-cloud-translate==3.28.0
  …
   + grpc-google-iam-v1==0.14.5
  …
  ```
  `google.cloud.translate_v2`, which `cli.py` imports (`translate_text/cli.py:9`), ships inside `google-cloud-translate`.
- **Action:** `group_name` on line 18; `python cli.py --help`. Recorded without the key it fails at import, like C (`translate_text/03-help.txt`, trimmed):
  ```
  app@…:/app$ python cli.py --help
  Traceback (most recent call last):
    File "/app/cli.py", line 20, in <module>
      translate_client = translate.Client()
                         ^^^^^^^^^^^^^^^^^^
  …
    File "/home/app/.venv/lib/python3.12/site-packages/google/cloud/client/__init__.py", line 218, in __init__
      credentials, _ = google.auth.default(scopes=scopes)
  …
  google.auth.exceptions.DefaultCredentialsError: File secrets/mega-pipeline.json was not found.
  ```
  Expected with the key: the README's block (`translate_text/README.md:115-124`): `usage: cli.py [-h] [-d] [-t] [-u]`, `Translate English to French`, and the three options.
- **Action:** `python cli.py -d`, `python cli.py -t`, `python cli.py -u` (`--download`, `--translate`, `--upload`; `README.md:153-157`), with your key.
- **Under the hood** (`translate_text/cli.py:28-88`): D reads `text_paragraphs/<group>/`, the **same** input as C, not C's output. It calls Translation v2 with `source_language="en"`, `target_language="fr"`, `format_="text"` (`:58-63`), prints `result["translatedText"]`, saves it to `text_translated/<group>/<uuid>.txt`, and `--upload` pushes those files. Translation answers at once, with no operation to wait on, so D needs its own upload.
- **Expected with your key** (from the code): `translate` and the French text, printed; then `upload` and one `Uploading: text_translated/<group>/…` line per file.
- **Action:** `exit`, `docker build -t translate_text .` again: `Resolved 26 packages`, `Installed 25 packages`, `Building 8.3s` (`laptop/52-d-rebuild.*`).

### Part E: 🔊 Task E · `synthesis_audio` (`synthesis_audio/README.md`)

**Step 22. Synthesize the French** [E1–E12].
- **Action:** `cd ../synthesis_audio`, key, `uv init --bare` (``Initialized project `synthesis-audio` ``, `>=3.11`, `laptop/60-e-uv-init.txt`), B's Dockerfile (`:45`; the text at `:38` again says "keep `ffmpeg`": ignore it), `docker build -t synthesis_audio .` (`CACHED [2/5]`, `Building 0.7s`), `docker run --rm -ti -v "$(pwd):/app" synthesis_audio` (`:99`).
- **Action:** `uv add google-cloud-storage google-cloud-texttospeech` (`:104-106`): `Resolved 25 packages`, `Installed 24 packages` (`synthesis_audio/01-uv-add.txt`).
- **Action:** `group_name` on line 18; `python cli.py --help`. Without the key it fails at import (line 21, `synthesis_audio/03-help.txt`). Expected with the key: the README's block (`synthesis_audio/README.md:115-123`), except one line: the README shows `Synthesis audio from text`, but the code's description is `"Transcribe audio file to text"` (`synthesis_audio/cli.py:105`), pasted from A, so that is what a real run prints (§9 E6).
- **Action:** `python cli.py -d`, `python cli.py -s` (`README.md:160-165`), with your key.
- **Under the hood** (`synthesis_audio/cli.py:29-90`): identical to C, but it reads `text_translated/<group>/`, uses voice `fr-FR-Standard-C` (`:47-48`) and writes `output_audios/<group>/<uuid>.mp3` straight into the bucket. No `--upload` (`README.md:165`).
- **Action:** `exit`, `docker build -t synthesis_audio .` again: `Resolved 25 packages`, `Installed 24 packages`, `Building 7.6s` (`laptop/62-e-rebuild.*`).
- **Checkpoint:** with all five done, your group's row on the leaderboard is complete.

**Step 23. Bonus: ElevenLabs, in the instructor's voice** [X1–X3] (`:132-156`).
- **Action:** create an ElevenLabs account and API key (`:138`); create `secrets/11lab_api_key.txt` with the line `XI_API_KEY=your_api_key_here` (`:139-142`), your key in place of the placeholder, with no spaces around `=`; set `group_name` on line 19 of `cli_11.py` (`:112`); then, inside (`synthesis_audio/04-bonus-uv-add-requests.txt`):
  ```
  app@…:/app$ uv add requests
  Resolved 25 packages in 12ms
  Checked 24 packages in 0.63ms
  ```
  `requests` was already installed (a dependency of `google-cloud-storage`); this records it as a direct dependency, `"requests>=2.34.2"` (`files/synthesis_audio.pyproject.toml`). That is still right: `cli_11.py` imports `requests` itself (`cli_11.py:8`).
- **Action:** `python cli_11.py --download`, `python cli_11.py --synthesis`, `python cli_11.py --upload` (`:150-154`). **Recorded without the key file** (`synthesis_audio/05-bonus-cli11-download.txt`):
  ```
  app@…:/app$ python cli_11.py --download
  Traceback (most recent call last):
    File "/app/cli_11.py", line 33, in <module>
      with open(secrets_file_path) as f:
           ^^^^^^^^^^^^^^^^^^^^^^^
  FileNotFoundError: [Errno 2] No such file or directory: 'secrets/11lab_api_key.txt'
  ```
  The script reads the key file at import (`cli_11.py:30-39`), so without it every flag fails, even `--download`.
- **Under the hood** (`cli_11.py:60-133`): POST each translated text to `https://api.elevenlabs.io/v1/text-to-speech/<VOICE_ID>/stream` with model `eleven_multilingual_v2`, stream the audio into `output_audios_pp/<group>/<uuid>.mp3` on your laptop ("saves audio **locally first**", `:156`), then `--upload` pushes those files under the same names. If ElevenLabs refuses, `--synthesis` just prints the response body and carries on (`:111-113`): read its output.
- **Costs:** your own ElevenLabs quota. Whether your account may use the instructor's voice id is an open question (§9 Q5).

### Part F: after the README

**Step 24. Is the key inside your image?** *(extra)*
- **Action:** with a key in `secrets/` and the image rebuilt, list `/app/secrets` **inside the image**, with no mount. Recorded with an 82-byte stand-in file (`laptop/22-g1-key-in-image.txt`):
  ```
  $ docker run --rm --entrypoint ls transcribe_audio -la /app/secrets
  total 12
  drwxr-xr-x 2 app app 4096 Oct 13 01:48 .
  drwxr-xr-x 1 app app 4096 Oct 13 01:47 ..
  -rw-r--r-- 1 app app    0 Oct 13 01:42 .gitkeep
  -rw-r--r-- 1 app app   82 Oct 13 01:47 mega-pipeline.json
  ```
- **Under the hood:** `--entrypoint ls` replaces bash, so the arguments after the image name go to `ls`. Without `-v`, `/app` is what `COPY . ./` put in the image: the whole build context, `secrets/` included. Docker doesn't read `.gitignore` (3.8). With the README's order (key in Step 4, build in Step 7), every image you built today contains your key.

**Step 25. Keep it out: `.dockerignore`** *(extra)*
- **Action:** in each of the five component folders, create a file `.dockerignore` with one line, `secrets/` (`laptop/23-g1-dockerignore.txt`):
  ```
  $ cat .dockerignore
  secrets/
  ```
  Then rebuild each image (`docker build -t transcribe_audio .` etc.) and list again (`laptop/25-g1-key-not-in-image.txt`):
  ```
  $ docker run --rm --entrypoint ls transcribe_audio -la /app/secrets
  ls: cannot access '/app/secrets': No such file or directory
  ```
  Exit status 2.
- **Checkpoint:** the app still works: at run time the bind mount brings your `secrets/` folder in, and `GOOGLE_APPLICATION_CREDENTIALS` still points at `secrets/mega-pipeline.json` under `/app`.
- **Then:** remove the older builds, which still hold the key (`docker image prune -f`, `docker builder prune`, Step 27 and §8 B5).

**Step 26. Optional: push to Docker Hub** [H1–H3] (`transcribe_audio/README.md:136-140`; the same section in every component README). Not captured.
- **Action:** sign up and create an access token (`:137`), then:
  ```bash
  docker login -u <USER NAME> -p <ACCESS TOKEN>
  docker tag transcribe_audio <USER NAME>/transcribe_audio
  docker push <USER NAME>/transcribe_audio
  ```
- **Before you push:**
  - Only push images built **after** Step 25. If you ever pushed one with the key, delete that Docker Hub repository and tell the staff so the key can be rotated.
  - Prefer `docker login -u <USER NAME>` and paste the token at the prompt; after `-p` it stays in your shell history (§6 G13).
  - An image built on Apple Silicon is `linux/arm64` and won't run on an amd64 VM; build both with `docker buildx build --platform linux/amd64,linux/arm64 … --push` (§6 G6).
- **Under the hood:** `docker tag` gives the local image a second name in your Docker Hub namespace; `docker push` uploads the layers that Docker Hub doesn't have yet. A new repository on Docker Hub is public by default.

**Step 27. Clean up** *(extra; not in the README)*.
- **Action** (`laptop/70-images-all.txt`, from the repo root after `cd ..`):
  ```
  $ docker image ls --filter reference=transcribe_audio --filter reference=generate_text --filter reference=synthesis_audio_en --filter reference=translate_text --filter reference=synthesis_audio
  IMAGE                       ID             DISK USAGE   CONTENT SIZE   EXTRA
  generate_text:latest        66b13d455fc8        846MB          212MB
  synthesis_audio:latest      b56ca53bbd2d        842MB          216MB
  synthesis_audio_en:latest   67635b572cbb        842MB          216MB
  transcribe_audio:latest     42dc79356e2b       1.48GB          388MB
  translate_text:latest       2c1279b01d87        845MB          216MB
  ```
- **Keep your work** (`laptop/71-git-status.txt`):
  ```
  $ git status
  On branch main
  Your branch is up to date with 'origin/main'.

  Changes not staged for commit:
  …
  	modified:   generate_text/pyproject.toml
  	modified:   transcribe_audio/cli.py

  Untracked files:
  …
  	generate_text/Dockerfile
  	generate_text/uv.lock
  …
  ```
  The recording set `group_name` only in `transcribe_audio`; yours also lists the other `cli.py` files and, with your key, `generate_text`'s downloaded `text_prompts/` and `text_paragraphs/`. The other four folders' Dockerfiles, `pyproject.toml` and `uv.lock` don't appear at all: their `.gitignore` hides them (§6 G14). To keep them in your own repository, `git add -f` them; never stop ignoring `secrets/`.
- **Action** (`laptop/72-cleanup.txt`, trimmed):
  ```
  $ docker image rm transcribe_audio generate_text synthesis_audio_en translate_text synthesis_audio
  Untagged: transcribe_audio:latest
  Deleted: sha256:42dc79356e2bb7a36092573b2883b11eae823ee2f215158736ee97d96978de97
  Untagged: generate_text:latest
  Deleted: sha256:66b13d455fc87701012c17ac772f0ba7f91170edc7b18fca9b84695d602de993
  …
  Untagged: synthesis_audio:latest
  Deleted: sha256:b56ca53bbd2d4b62a0701ff537bc0baae57c7cc002b469a6c68eba656f1177b5
  ```
  Then `docker image prune -f` and `docker builder prune` (not captured): with the classic image store, older builds stay behind as untagged images, each holding the key; with the containerd image store, the old `COPY` layer stays in the build cache (§8 B5).
- **Checkpoint:** no containers are left (every run used `--rm`); in GCP there is nothing to delete.

---

## 5. Code tour

```
mega-pipeline/  (main @ c6bbc9b)
├── README.md                 overview, bucket prefixes, credentials, the five tasks, quick reference, sample Dockerfile
├── .gitignore                ignores secrets/, .vscode, outputs and staff-only folders (/api-service, /deployment, /frontend …)
├── mega-pipeline-flow.png    the six-step flow diagram (record → transcribe → generate → synth EN / translate → synth FR)
├── mega-pipeline-bucket.png  a screenshot of the bucket's prefixes
├── transcribe_audio/   A  README.md · cli.py (Speech-to-Text) · .gitignore (also ignores Dockerfile, pyproject.toml, uv.lock!) · secrets/.gitkeep
├── generate_text/      B  README.md · cli.py (Gemini) · pyproject.toml (requires-python >=3.14!) · main.py (uv init leftover) · secrets/.gitkeep   [no .gitignore]
├── synthesis_audio_en/ C  README.md · cli.py (Text-to-Speech Long Audio, en-US) · .gitignore · secrets/.gitkeep
├── translate_text/     D  README.md · cli.py (Translation v2) · .gitignore · secrets/.gitkeep
└── synthesis_audio/    E  README.md · cli.py (Text-to-Speech Long Audio, fr-FR) · cli_11.py (ElevenLabs bonus) · .gitignore · secrets/.gitkeep
   + what YOU add in each folder: Dockerfile, pyproject.toml + uv.lock, secrets/mega-pipeline.json, (recommended) .dockerignore
```

**1. Your Dockerfile vs the appendix's sample** (`README.md:175-225`)

Your 30-line file is in §4 Step 6. The appendix's version adds comments and three differences:
```dockerfile
# README.md:179
ARG DEBIAN_PACKAGES="build-essential curl"
# README.md:199-200
RUN set -ex; \
    for i in $(seq 1 8); do mkdir -p "/usr/share/man/man${i}"; done && \
```
- `"build-essential curl"`: no `ffmpeg`, so pasted into `transcribe_audio` it breaks `--transcribe` (§6 G8). For B–E, `curl` is simply unused.
- `set -ex`: print each command and stop at the first failure.
- The `mkdir … man${i}` loop recreates the man-page folders that slim images delete; some packages' install scripts (Java's is the classic case) fail without them. Without it, `ffmpeg`'s install only prints the harmless `update-alternatives: warning: skip creation of /usr/share/man/man1/…` lines (§4 Step 7).
- Its comments explain the `ENV` block: "Tell uv to copy packages from the wheel into the site-packages" for `UV_LINK_MODE=copy` (`README.md:190-191`) and "This is done for the tutorial only" for `GOOGLE_APPLICATION_CREDENTIALS` (`README.md:194-195`). L04's Dockerfiles drop that `ENV` and pass the path at run time instead (`flexible-workflow:README.md:372`).

**2. Stage A, download: listing a prefix**

```python
# transcribe_audio/cli.py:29-43
def download():
    print("download")

    # Clear
    shutil.rmtree(input_audios, ignore_errors=True, onerror=None)
    makedirs()

    client = storage.Client()
    bucket = client.get_bucket(bucket_name)

    blobs = bucket.list_blobs(prefix=input_audios+"/")
    for blob in blobs:
        print(blob.name)
        if not blob.name.endswith("/"):
            blob.download_to_filename(blob.name)
```
- `shutil.rmtree(input_audios, …)` starts clean, but only for the *inputs*: outputs in `text_prompts/` survive, which is what makes reruns skip finished work.
- `storage.Client()` (line 36) is the first credentials lookup (ADC). No key path appears anywhere in the code; line 36 is where the captured `DefaultCredentialsError` traceback starts (§4 Step 11).
- `client.get_bucket(...)` makes an API call (it needs `storage.buckets.get`). The uploads and the other stages use `storage_client.bucket(...)`, which only builds a local handle.
- `list_blobs(prefix="input_audios/")`: Cloud Storage has no folders; this means "every object whose name starts with …". There is no group in this prefix: all teams transcribe the same audio.
- `endswith("/")` skips the zero-byte placeholder object the console creates for a "folder".
- `download_to_filename(blob.name)`: the local path mirrors the object name, and the bind mount puts it on your laptop.

**3. Stage A, transcribe: ffmpeg, then a long-running Speech request**

```python
# transcribe_audio/cli.py:64-78
        print("Transcribing:", audio_path)
        with TemporaryDirectory() as audio_dir:
            flac_path = os.path.join(audio_dir, "audio.flac")
            stream = ffmpeg.input(audio_path)
            stream = ffmpeg.output(stream, flac_path)
            ffmpeg.run(stream)

            with io.open(flac_path, "rb") as audio_file:
                content = audio_file.read()

            # Transcribe
            audio = speech.RecognitionAudio(content=content)
            config = speech.RecognitionConfig(language_code="en-US")
            operation = client.long_running_recognize(config=config, audio=audio)
            response = operation.result(timeout=90)
```
- `ffmpeg.input/output/run` (`ffmpeg-python`) only builds a command line and starts the **`ffmpeg` program** with `subprocess`. That is why `ffmpeg` must be in the Dockerfile's `ARG` (line 3), not only in `pyproject.toml`.
- Why FLAC: Speech-to-Text v1 doesn't take MP3, and for FLAC the encoding and sample rate come from the file's header, so `RecognitionConfig` needs only `language_code`.
- `RecognitionAudio(content=…)`: the bytes travel **inline** in the request (the alternative is a `uri="gs://…"`).
- `long_running_recognize(...)` returns an operation handle at once; `.result(timeout=90)` blocks, polling, for up to 90 s.
- Lines 80–96 (not shown) start from `text = "None"`, then concatenate `result.alternatives[0].transcript` for **every** result with `"".join` (line 90; the `c6bbc9b` fix: the API splits long audio at pauses, and the old code kept only the first piece, still visible as comments at lines 81–83), and write the `.txt`. If the API returns no results, the file says `None` (§6 G20).

**4. Stage A, upload: the hand-off contract**

```python
# transcribe_audio/cli.py:104-115
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)

    # Get the list of text file
    text_files = glob.glob(os.path.join(text_prompts, group_name, "input-*.txt"))

    for text_file in text_files:
        filename = os.path.basename(text_file)
        destination_blob_name = os.path.join(text_prompts, group_name, filename)
        blob = bucket.blob(destination_blob_name)
        print("Uploading:",destination_blob_name, text_file)
        blob.upload_from_filename(text_file)
```
- The glob `input-*.txt` is half of the contract; B downloads with the matching `match_glob=f"{text_prompts}/{group_name}/input-*.txt"` (`generate_text/cli.py:42`). A file not named `input-…` is never handed on (§8 D2).
- `os.path.join(text_prompts, group_name, filename)` is the object name, with the group as the namespace. `upload_from_filename` overwrites any existing object of that name: a wrong `group_name` can clobber another team's work.

**5. Stage B: one LLM call**

```python
# generate_text/cli.py:64-78
        # Generate output
        input_prompt = f"""
            Create a transcript for the podcast about cheese with 1000 or more words.
            Use the below text as a starting point for the cheese podcast.
            Output the transcript as paragraphs and not with who is talking or any "Sound" or any other extra information.
            Do not highlight or make words bold.
            The host's name is Pavlos Protopapas.
            {input_text}
        """
        model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")
        print(input_prompt,"\n\n\n")
        response = client.models.generate_content(
            model=model_name, contents=input_prompt
        )
        paragraph = response.text
```
- The prompt is a plain f-string with the rough transcript appended. The instructions push for text a TTS voice can read: no speaker labels, no "Sound" cues, no bold.
- `os.environ.get("GEMINI_MODEL", …)` is the one runtime knob: `-e GEMINI_MODEL=…` on `docker run` changes the model without editing code. Needed after 2026-10-20, when Vertex AI retires the default (§4 Step 18).
- `client` was created at import as `genai.Client(vertexai=True, project=gcp_project, location='us-central1')` (`generate_text/cli.py:23-25`): Gemini **on Vertex AI**, billed to the course's project and authenticated with the same key. It loads credentials only on its first request, so a missing key shows up at `--generate`, not at `--help`.
- `response.text` is the text of the first candidate.

**6. Stages C and E: the TTS service writes straight to the bucket**

```python
# synthesis_audio_en/cli.py:77-91
            parent = f"projects/{gcp_project}/locations/us-central1"
            output_gcs_uri = f"gs://{bucket_name}/{audio_blob_name}"

            request = texttospeech.SynthesizeLongAudioRequest(
                parent=parent,
                input=input,
                audio_config=audio_config,
                voice=voice,
                output_gcs_uri=output_gcs_uri,
            )

            operation = client.synthesize_long_audio(request=request)
            # Set a deadline for your LRO to finish. 300 seconds is reasonable, but can be adjusted depending on the length of the input.
            result = operation.result(timeout=300)
            print("Audio file will be saved to GCS bucket automatically.")
```
- `parent`: the Long Audio API is a project- and region-scoped resource (`us-central1`).
- `output_gcs_uri`: the destination object; the service writes it, never your container. Hence no `--upload` in C and E.
- Just above (`:63-69`), `blob.exists()` checks the bucket first: that GCS check, not the local `os.path.exists` at `:57`, is the real "already done" test. To regenerate, delete the object in the bucket (§8 D1).
- `synthesis_audio/cli.py:76-90` is the same block, with voice `fr-FR-Standard-C` (`:47-48`) and the prefix `output_audios`.

**7. Stage D: Translation v2**

```python
# translate_text/cli.py:58-65
        result = translate_client.translate(
            input_text,
            source_language="en",
            target_language="fr",
            format_="text",
        )
        translated_text = result["translatedText"]
        print(translated_text)
```
- `translate_client = translate.Client()` was built at **import** (`translate_text/cli.py:20`), from `google.cloud.translate_v2`, so the credentials lookup runs before argparse: even `--help` needs the key (§4 Step 21).
- `format_="text"` (with a trailing underscore, because `format` is a Python builtin): treat the input as plain text rather than HTML, so the API doesn't HTML-escape apostrophes and the like.
- The response is a dict; `translatedText` is the French string. Change `target_language` (and E's voice) to retarget everything downstream (§8 D1).

**8. The bonus reads its key at import time**

```python
# synthesis_audio/cli_11.py:29-39
#Define the path to the secrets file
secrets_file_path = 'secrets/11lab_api_key.txt'

# Read the file and set the environment variable
with open(secrets_file_path) as f:
    for line in f:
        if 'XI_API_KEY' in line:
            key, value = line.strip().split('=')
            os.environ[key] = value

XI_API_KEY = os.environ['XI_API_KEY']  
```
- Module-level code runs on every invocation, including `--download`: no key file means `FileNotFoundError` at line 33 (captured, §4 Step 23).
- `split('=')` assumes exactly one `=`; `strip()` removes a trailing `\r` from a Windows editor. A second `=` on the line raises `ValueError: too many values to unpack (expected 2)`.
- Spaces matter: `XI_API_KEY = abc` sets a variable named `'XI_API_KEY '` (with a trailing space), and line 39 then raises `KeyError: 'XI_API_KEY'`.

**9. What Git will and won't keep**

```gitignore
# transcribe_audio/.gitignore:1-9
# misc
.DS_Store
/secrets
docker-shell.sh
Dockerfile
pyproject.toml
uv.lock
/input_audios
/text_prompts
```
- `/secrets`: the key stays out of Git.
- `docker-shell.sh`, `Dockerfile`, `pyproject.toml`, `uv.lock`: so the course repo never receives students' solutions, **your own work is invisible to `git status`** (§6 G14).
- `/input_audios`, `/text_prompts`: downloaded data and outputs. `synthesis_audio_en/.gitignore:8`, `translate_text/.gitignore:8-9` and `synthesis_audio/.gitignore:8-10` do the same for their folders. `generate_text/` has **no** `.gitignore`, so its Dockerfile, `uv.lock` and data folders show up as untracked (captured, §4 Step 27); the root `.gitignore:4` (`secrets/`) still protects its key.

**10. Where the course goes next: the secret mounted at run time**

```bash
# origin/solution:transcribe_audio/docker-shell.sh:95-100
    # Run Container
    docker run --rm --name $IMAGE_NAME -ti \
    -v "$BASE_DIR":/app \
    -v "$SECRETS_DIR":/secrets \
    -e GOOGLE_APPLICATION_CREDENTIALS=$GOOGLE_APPLICATION_CREDENTIALS \
    $CONTAINER_IMAGE
```
- Not used on `main`; last year's solution, and the shape of L04. `BASE_DIR=$(pwd)`, `SECRETS_DIR=$(pwd)/../../secrets/` and `GOOGLE_APPLICATION_CREDENTIALS=/secrets/mega-pipeline.json` are set at `:8-10`.
- The second `-v` mounts a `secrets/` folder that sits **next to the repo** (two levels up from the component) at `/secrets`. The key is never in the build context, so it can't be baked into an image, and the absolute `/secrets/…` path works from any directory.
- `--name $IMAGE_NAME` gives the container a predictable name; `$CONTAINER_IMAGE` is the local image if there is one, else `dlops/<name>` from Docker Hub (`:86-93`). The script's `prod` mode builds `linux/amd64,linux/arm64` with `docker buildx` and pushes (`:51-72`).

---

## 6. Gotchas and common errors

**G1. The service-account key gets baked into your image.**
- **Symptom:** `docker run --rm --entrypoint ls transcribe_audio -la /app/secrets` (no mount) lists `mega-pipeline.json` (captured with a stand-in, §4 Step 24). The build's `SecretsUsedInArgOrEnv` warning does not catch it: it fires on the variable's name, not on the copied file.
- **Cause:** `COPY --chown=app:app . ./` (`README.md:217`; `transcribe_audio/README.md:82`) and no `.dockerignore` anywhere on `main` (nor on `simple`, `solution` or `flexible-workflow`). `.gitignore` doesn't apply to Docker builds. The optional push (`transcribe_audio/README.md:136-140`) would publish the key.
- **Fix:** a `.dockerignore` containing `secrets/` in every component, then rebuild (captured: `ls: cannot access '/app/secrets': No such file or directory`, §4 Step 25). Prune the older builds (§8 B5). If you already pushed, delete the Docker Hub repository and **tell the staff so the key can be rotated**. Long term: keep secrets outside the repo and mount them at run time (§5 excerpt 10).

**G2. Wrong or default `group_name`.**
- **Symptom:** your leaderboard row stays empty, or your uploads land under `…/pavlos/…`; a later stage downloads nothing, with no error.
- **Cause:** the default is `"pavlos"` with no assert (`transcribe_audio/cli.py:21` and the corresponding line in every `cli.py`). Each stage downloads `<prefix>/<group_name>/…`, written by the previous one, so the value must be **identical in all five** files (and `cli_11.py`).
- **Fix:** set it everywhere before the first run (`README.md:124`); `grep -n "^group_name" */cli.py` from the repo root shows all of them at once.

**G3. `requires-python` newer than the image's Python 3.12.**
- **Symptom:** during `docker build`, `RUN uv sync` either
  - **silently downloads a separate CPython** and builds the venv on it. Captured with `generate_text`'s committed `>=3.14`: `Downloading cpython-3.15.0-linux-x86_64-gnu (download) (35.9MiB)`, `Using CPython 3.15.0`, and in the container `readlink -f $(which python)` → `/home/app/.local/share/uv/python/cpython-3.15.0-linux-x86_64-gnu/bin/python3.15`. The build succeeds, but the `python:3.12` base is now pointless, the image is bigger, every rebuild downloads it again, and you run on a Python nobody tested; or,
  - if Python downloads are disabled (`UV_PYTHON_DOWNLOADS=never`), **fails** with `error: No interpreter found for Python >=3.14 in managed installations or search path` and the hint that downloads are set to `'never'` (the digest's check).
- **Cause:** `uv init --bare` stamps the Python it finds on **your laptop** (captured: `>=3.11` on Python 3.11.2; a 3.13 laptop gets `>=3.13`); `generate_text/pyproject.toml:4` is committed as `>=3.14`.
- **Fix:** `requires-python = ">=3.12"` (last year's README pinned `">=3.12,<3.13"`, `origin/solution:transcribe_audio/README.md:36`), or `uv init --bare --python 3.12`. **Checkpoint:** the `uv sync` build step says `Using CPython 3.12.15 interpreter at: /usr/local/bin/python3` (captured after the fix, §4 Step 19).

**G4. `uv init --bare` fails in `generate_text`.**
- **Symptom:** ``error: Project is already initialized in `/home/student/mega-pipeline/generate_text` (`pyproject.toml` file exists)``, exit status 2 (captured).
- **Cause:** `generate_text/pyproject.toml` and `main.py` are committed, yet `generate_text/README.md:20-24` still says to run `uv init --bare`.
- **Fix:** skip the step; edit `requires-python` (G3); `main.py` can be ignored or deleted.

**G5. `DefaultCredentialsError: File secrets/mega-pipeline.json was not found.`**
- **Cause:** the env var is a relative path (`README.md:195`), checked relative to the current directory (raised at `google/auth/_default.py`, line 178, in the captured tracebacks). It appears if:
  - the key isn't in *this* component's `secrets/` (each folder needs its own copy);
  - you `cd`'d away from `/app` inside the container (§8 C2);
  - you ran `docker run` from the repo root or another folder, so `/app` isn't the component folder.

  In `translate_text`, `synthesis_audio_en` and `synthesis_audio` the client is created at import (`translate_text/cli.py:20`, `synthesis_audio_en/cli.py:22`, `synthesis_audio/cli.py:21`), so even `--help` fails (all three captured). In `transcribe_audio` it appears at the first command that builds a client (captured at `--download`, line 36); in `generate_text`, at `--generate`.
- **Fix:** `cd /app`, check that `ls secrets/` shows the key, and run `docker run` from inside the component folder.

**G6. An Apple Silicon image pushed to Docker Hub won't run on an amd64 VM.**
- **Symptom:** on the VM, `exec format error`, or a warning that the image's platform (`linux/arm64`) does not match the host's (`linux/amd64`).
- **Cause:** `docker build` on an M-series Mac produces `linux/arm64` (`python:3.12-slim-bookworm` exists for both). Locally everything works.
- **Fix:** `docker buildx build --platform linux/amd64,linux/arm64 -t <USER NAME>/<name> --push .`, which is what `origin/solution:transcribe_audio/docker-shell.sh:62-70` does in `prod` mode (§8 D3).

**G7. ``error: failed to create file `/app/pyproject.toml`: Permission denied (os error 13)`` from `uv add` on a Linux laptop or VM.**
- **Cause:** the container runs as uid 1000 (`README.md:208`), but on native Linux the bind-mounted folder keeps your laptop's ownership. Captured with a root-owned copy of the folder (`ls -ld /app` → `root root`, `id` → `uid=1000(app)`). The first user on most Linux desktops is uid 1000, so it usually works; it breaks when you work as root (e.g. on a VM) or as another uid. Docker Desktop on macOS and Windows maps ownership for you. The same cause gives `PermissionError: [Errno 13] Permission denied` when `cli.py` creates `input_audios/`.
- **Fix** (not from the README): `sudo chown -R 1000:1000 .` in the component folder on the laptop, or `chmod -R a+rwX` it. Running with `-u "$(id -u):$(id -g)"` is not a clean fix: that uid has no home folder in the image and doesn't own `/home/app/.venv` (the digest's check: `uv add` then failed with `` Failed to initialize cache at `/.cache/uv` `` and `Permission denied (os error 13)`).

**G8. `FileNotFoundError: [Errno 2] No such file or directory: 'ffmpeg'` at `transcribe_audio/cli.py:69`.**
- **Cause:** the Debian `ffmpeg` program isn't in the image. The usual way to get here: copying the appendix's Dockerfile (`ARG DEBIAN_PACKAGES="build-essential curl"`, `README.md:179`) or B's.
- **Fix:** `ARG DEBIAN_PACKAGES="build-essential ffmpeg"` (`transcribe_audio/README.md:45`), exit, rebuild. The big `RUN` step runs again, because its package list changed (§8 C4).

**G9. `AttributeError: module 'ffmpeg' has no attribute 'input'` or `ModuleNotFoundError: No module named 'ffmpeg'`.**
- **Cause:** `uv add ffmpeg` or `uv add python-ffmpeg` (different PyPI projects, also imported as `ffmpeg`), or the package was never added.
- **Fix:** inside the container, `uv remove ffmpeg` (or `python-ffmpeg`), `uv add ffmpeg-python` (`transcribe_audio/README.md:108`), then exit and rebuild (§8 C3).

**G10. `ModuleNotFoundError: No module named 'google'` the next day.**
- **Cause:** you ran `uv add` in an earlier `--rm` container but never rebuilt, so the packages lived in that container's writable layer (captured: a new container failed again, §4 Step 14).
- **Fix:** `docker build -t <name> .` again: `COPY` brings the new `pyproject.toml`/`uv.lock`, and `uv sync` installs them into the image (`transcribe_audio/README.md:110`).

**G11. Re-running does nothing.**
- **Symptom:** `--transcribe`, `--generate` or `--translate` prints nothing new; `--synthesis` prints nothing.
- **Cause:** skip-if-exists logic. Local outputs persist on your laptop across container runs (`transcribe_audio/cli.py:61-62`, `generate_text/cli.py:57-58`, `translate_text/cli.py:52-53`), and synthesis skips if the **bucket** object exists (`synthesis_audio_en/cli.py:69`, `synthesis_audio/cli.py:68`).
- **Fix:** delete the local output file (or, for synthesis, the object in the bucket) to force a redo.

**G12. Quota or model errors on the shared project.**
- `429 RESOURCE_EXHAUSTED` from Gemini, Speech-to-Text or Text-to-Speech: the whole class shares one project's quotas during the lecture. Wait a minute and retry.
- `404 … Publisher Model … was not found` from `--generate`: the model id is retired or misspelled. `gemini-2.5-flash-lite`, the default at `generate_text/cli.py:73`, is retired on Vertex AI on 2026-10-20. Start the container with `-e GEMINI_MODEL=<current model id>`.

**G13. Docker Hub login leaks your token into shell history.**
- **Cause:** `docker login -u <USER NAME> -p <ACCESS TOKEN>` (`transcribe_audio/README.md:138`); Docker itself warns that a password on the command line is insecure.
- **Fix:** `docker login -u <USER NAME>` and paste the token at the prompt, or `echo "$TOKEN" | docker login -u <USER NAME> --password-stdin`.

**G14. Your Dockerfiles and `pyproject.toml` "disappear" when you commit to your own repo.**
- **Cause:** the component `.gitignore` files ignore them (`transcribe_audio/.gitignore:4-7`, and the same lines in `synthesis_audio_en`, `translate_text` and `synthesis_audio`). Captured: after all five components, `git status` lists only `generate_text/` and the edited `cli.py` (§4 Step 27).
- **Fix:** `git add -f transcribe_audio/Dockerfile transcribe_audio/pyproject.toml transcribe_audio/uv.lock` (and the same for the other folders), or remove those lines in your own copy. Never remove `/secrets`, and don't commit the downloaded data.

**G15. The run command misbehaves on Windows.**
- **Symptoms:** `the input device is not a TTY`, or a path split at a space.
- **Fix:** use Git BASH, quote `"$(pwd)"`, and prefix `winpty` (`README.md:230-235`). If `/app` still looks empty, Git BASH may have rewritten the path; prefixing the command with `MSYS_NO_PATHCONV=1` is a common workaround (not from the README, not checked).

**G16. `docker run … transcribe_audio python cli.py -d` fails instead of running the CLI.**
- **Symptom** (captured, `laptop/18-g16-entrypoint.txt`):
  ```
  $ docker run --rm -v "$(pwd):/app" transcribe_audio python cli.py -d
  /usr/local/bin/python: /usr/local/bin/python: cannot execute binary file
  ```
  Exit status 126.
- **Cause:** `ENTRYPOINT ["/bin/bash"]` (`README.md:222`). Words after the image name replace `CMD`, so the container runs `/bin/bash python cli.py -d`: bash treats `python` as a script file to read, finds the binary on `PATH` (the image's own `/usr/local/bin/python`, since nothing activated the venv) and refuses.
- **Fix** (captured with `--help`, `laptop/19-g16-fix.txt`, which printed the usage block):
  ```bash
  docker run --rm -v "$(pwd):/app" transcribe_audio -c "source /home/app/.venv/bin/activate && python cli.py -d"
  ```
  or `docker run --rm -v "$(pwd):/app" --entrypoint /home/app/.venv/bin/python transcribe_audio cli.py -d`. `-ti` isn't needed when nothing is interactive (§8 C1).

**G17. `ffmpeg.Error` on a file that isn't audio.**
- **Cause:** `transcribe()` processes **every** file in `input_audios/` (`transcribe_audio/cli.py:54-56`). On a Mac, opening the bind-mounted folder in Finder can create `.DS_Store` there.
- **Fix:** delete stray files, or re-run `--download`, which wipes the folder first (`transcribe_audio/cli.py:33`).

**G18. Ports and leftover containers.** Neither applies here: nothing is published with `-p`, and `--rm` removes every container on exit. If `docker ps -a` shows leftovers, they came from runs without `--rm`; remove them with `docker rm <id>`.

**G19. "The venv isn't active" because the prompt has no `(transcribe-audio)` prefix.**
- **Symptom:** the prompt is just `app@<id>:/app$` (captured).
- **Cause:** `exec bash` starts a new interactive shell that reads `/home/app/.bashrc`, which resets the prompt; the exported `VIRTUAL_ENV` and `PATH` survive.
- **Fix:** nothing to fix. Check with `which python` (`/home/app/.venv/bin/python`) or `echo $VIRTUAL_ENV`.

**G20. A transcript that says `None`.**
- **Cause:** `text = "None"` (`transcribe_audio/cli.py:80`) is written unchanged when Speech-to-Text returns no results (`:84`, `:95-96`), e.g. for silence or the wrong audio. The file then counts as done (skip-if-exists, `:61-62`), and `--upload` ships it to B.
- **Fix:** `cat` the `.txt` before uploading; delete it and re-run `--transcribe` if it says `None` (§8 C5).

**G21. `docker build` fails at `RUN uv sync` with ``error: No `pyproject.toml` found in current directory or any parent directory``.**
- **Cause:** you skipped `uv init --bare`, or ran it in another folder (captured, §4 Step 7: `Dockerfile:27`, `exit code: 2`).
- **Fix:** run `uv init --bare` in the component folder (check `requires-python`, G3) and build again.

---

## 7. Where this sits in the course

- **Before:**
  - **L01 · Virtual environments and VMs** (`dlops-io/simple-translate`): venvs, `pyproject.toml`, `uv sync`, `uv.lock`, `requires-python` as a constraint that can make uv download a Python. All of it reappears here, inside an image.
  - **L02 · Containers I** (`dlops-io/simple-translate` `main` @ `62f821b`): one tiny CLI containerised with a **given** `Dockerfile.txt`, run with no mounts and no secrets, pushed to Docker Hub and pulled onto a VM. The comparison table in §1 lists what L03 adds: you write the Dockerfile, five images, a non-root user, a venv outside `/app`, a bind mount, `uv add` inside the container, a shared bucket, managed AI APIs and a service-account key.
- **What L03 adds:**
  - Writing a Dockerfile from scratch, line by line, and reading a build log.
  - The bind-mount development loop: code on the laptop, environment in the image, `uv add` → exit → rebuild.
  - Credentials: a service account, ADC and `GOOGLE_APPLICATION_CREDENTIALS`, and the difference between keeping a key out of Git and keeping it out of an image.
  - A multi-stage pipeline whose stages communicate only through storage.
- **Next: L04 · Containers II-b** (`tutorials_demo.md:56-67`): the same repo, branch `flexible-workflow` (`git diff --stat main origin/flexible-workflow` → `42 files changed, 4227 insertions(+), 625 deletions(-)`), plus the `port_toy` Docker Compose app. What changes:
  - **Your own resources:** your own bucket and service account, and you enable the five APIs yourself (`flexible-workflow:README.md:187-198`).
  - **Blank identifiers:** `gcp_project`, `bucket_name` and `group_name` must be set, and the CLIs `assert` that `group_name` was changed (`flexible-workflow:README.md:127-134`).
  - **Dockerfiles provided, on Python 3.14:** `FROM python:3.14-slim-bookworm` (`flexible-workflow:README.md:325`), with a committed `pyproject.toml` and `uv.lock` per component.
  - **The key moves out of the repo and out of the image:** the Dockerfile no longer bakes `GOOGLE_APPLICATION_CREDENTIALS` in (`flexible-workflow:README.md:372`); `docker-shell.sh` mounts a `secrets/` folder from beside the repo at `/secrets` (the pattern of §5 excerpt 10).
  - **`docker-shell.sh` with four modes** (`flexible-workflow:README.md:212-215`):
    ```bash
    ./docker-shell.sh          # build the image locally and run it (default)
    ./docker-shell.sh dev      # only build the local image
    ./docker-shell.sh run      # run from a prebuilt image (falls back to DockerHub)
    ./docker-shell.sh prod     # build multi-arch (amd64 + arm64) and push to DockerHub
    ```
  - Before switching branches in the same clone, save what you wrote here: the untracked `generate_text/Dockerfile` and `uv.lock` can block the checkout, and the git-ignored Dockerfiles of the other four folders are overwritten (see the L04 guide).
- **Later:**
  - The "copy the lockfile first" Dockerfile order (`llm-rag/Dockerfile:42-48`, `uv sync --frozen`) from L05 on (§8 B3).
  - Milestone 2 asks your project to "Containerize each component" and make the pipeline "runnable with one command (e.g., `docker compose up` or `make run`)" (`milestone2.md:46-48`), with "`pyproject.toml` (using `uv`) for each container" (`milestone2.md:78`). That is the orchestration gap this tutorial leaves open on purpose.
- **This repo's branch history:** `pipenv` (2025-02, Pipenv); `simple` and `solution` (2025-09, uv + Python 3.12, secrets outside the repo, `assert group_name`); `main` (2026-09: build-your-own Dockerfile, secrets inside each component, `google-cloud-translate` v2, `group_name = "pavlos"` default, Gemini model via `GEMINI_MODEL`, the multi-segment transcript fix); `flexible-workflow` (2026-09, L04). `git diff --stat origin/solution main` → `49 files changed, 574 insertions(+), 3838 deletions(-)`: most of the deletions are the solution's Dockerfiles, lockfiles and scripts, which `main` deliberately withholds.

---

## 8. Exercises

The exercises, with answers, are in [`exercises.md`](https://github.com/JunyiZhou-Conny/Explainer_Videos/blob/main/videos/ac215-l03-mega-pipeline/exercises.md) in the video folder. Its outputs are the 2026-10-13 captures, or were checked the same day in throwaway containers built from the README's Dockerfile (Docker Engine 29.8.2, uv 0.13.0, Python 3.12.15 in the image). Parts B and C run **without** the course key unless an item says "with your key". Do them after watching, without re-watching first; re-watch only the part you got wrong. A summary follows; open each answer only after committing to your own.

### Test yourself: the five questions from the end of the video

**Q1. Which prefix does `translate_text` read, and which stage wrote it?**
<details><summary>Answer</summary>

D reads `text_paragraphs/<group_name>/input-*.txt` (`translate_text/cli.py:37`). B, `generate_text`, wrote those objects: its upload takes every `text_paragraphs/<group>/input-*.txt` and uploads it under the same name (`generate_text/cli.py:97-104`). C reads the same objects (`synthesis_audio_en/cli.py:39`), which is why C and D can run side by side; E reads `text_translated/`, which D writes (`synthesis_audio/cli.py:38`). If D's `group_name` differs from B's, D's download matches nothing: no error, just nothing to translate.
</details>

**Q2. Why doesn't the mount hide the packages? What breaks without `UV_PROJECT_ENVIRONMENT`?**
<details><summary>Answer</summary>

`-v "$(pwd):/app"` covers only `/app`, and Dockerfile line 9 makes `uv sync` build the venv in `/home/app/.venv`, outside it (build log: `Creating virtual environment at: /home/app/.venv`; inside, `echo $VIRTUAL_ENV` → `/home/app/.venv`). Without line 9, uv uses `.venv` in the project folder, `/app/.venv`. With the README's `CMD` unchanged the container then stops at once, mount or not: `/bin/bash: line 1: /home/app/.venv/bin/activate: No such file or directory`. If you also point `CMD` at `/app/.venv` (L02's layout), it works without the mount, but with the mount your laptop's folder covers `/app/.venv` and you get the same `No such file or directory`; a `.venv` of your own laptop's in that folder would be a venv for the wrong operating system (both checked).
</details>

**Q3. After `uv add` in a `--rm` container: what survives, what is lost, what makes it permanent?**
<details><summary>Answer</summary>

Survives: everything written under `/app`, i.e. your laptop's folder: `pyproject.toml` with the three dependencies, `uv.lock` (138,445 bytes), and the `input_audios/` and `text_prompts/` folders (`laptop/14-host-after-uv-add.txt`). Lost: the 26 packages, installed into `/home/app/.venv` on the container's writable layer, which `--rm` deletes on exit; a new container fails with `ModuleNotFoundError: No module named 'google'` (`transcribe_audio/11-g10-new-container.txt`). Permanent: `docker build -t transcribe_audio .`, where `COPY` brings in the lockfile and `uv sync` installs it (`Resolved 27 packages`, `Installed 26 packages`); a fresh container then prints `imports ok` with no `uv add`.
</details>

**Q4. Which variable tells the libraries where the key is, and why only from `/app`?**
<details><summary>Answer</summary>

`GOOGLE_APPLICATION_CREDENTIALS`, set by Dockerfile line 10 to `secrets/mega-pipeline.json`. `storage.Client()` asks `google.auth.default()` for credentials (ADC), whose first stop is this variable. The value is **relative**, and google-auth checks it with `os.path.exists`, so it resolves from the current directory: `WORKDIR /app` starts the shell in `/app`, where `secrets/` is your folder's `secrets/` through the mount. Anywhere else it points at nothing (checked with a stand-in file: found from `/app`, `was not found.` after `cd /tmp`). Stay in `/app`, or use an absolute path, as last year's solution does (`GOOGLE_APPLICATION_CREDENTIALS=/secrets/mega-pipeline.json`, `docker-shell.sh:10`).
</details>

**Q5. How can an image contain a git-ignored key? The fix?**
<details><summary>Answer</summary>

`.gitignore` is read by Git only. `docker build … .` sends the whole folder as the build context, and `COPY --chown=app:app . ./` (Dockerfile line 26) copies all of it, `secrets/` included (`laptop/22-g1-key-in-image.txt`). The `SecretsUsedInArgOrEnv` warning only flags the variable's name on line 10. Fix: a `.dockerignore` with the line `secrets/` in each component folder, then rebuild (`ls: cannot access '/app/secrets': No such file or directory`, `laptop/25-g1-key-not-in-image.txt`); the app still finds the key through the mount. Then prune the older builds (B5), never push an image built before the fix, and if you did, delete it and tell the staff.
</details>

### Hands-on (predict, then run)

- **B1 · Three notes, three places.** In a container, `touch /app/note-app.txt /tmp/note-tmp.txt /home/app/note-home.txt`, `exit`; which notes exist on your laptop, and in a new container? <details><summary>Answer</summary>Only `note-app.txt`, on your laptop (`git status --short` shows `?? note-app.txt`). The other two were on the container's throwaway layer, like the packages from `uv add`. Delete `note-app.txt` afterwards.</details>
- **B2 · Who asked for `requests`?** `uv tree --depth 1`, then `uv tree --invert --package requests`. <details><summary>Answer</summary>Three direct dependencies (`ffmpeg-python`, `google-cloud-speech`, `google-cloud-storage`); `requests v2.34.2` is pulled in by `google-api-core` and by `google-cloud-storage`. That's why E's bonus `uv add requests` prints `Checked 24 packages` and installs nothing; adding it is still right, because `cli_11.py` imports it itself.</details>
- **B3 · Copy the lock first.** Replace Dockerfile lines 26–27 with `COPY --chown=app:app pyproject.toml uv.lock ./`, `RUN uv sync`, `COPY --chown=app:app . ./`; build, change only `group_name`, build again. Which steps say `CACHED`? <details><summary>Answer</summary>Six build steps now; after the edit, `[2/6]` to `[5/6]` (apt, `WORKDIR`, the lockfile copy, `uv sync`) are `CACHED` and only `[6/6] COPY . ./` runs. In a folder without `uv.lock` yet (before step 7), the build stops with `failed to compute cache key: … "/uv.lock": not found`, which is why the README's simpler order suits a first Dockerfile and later tutorials use this one (`llm-rag/Dockerfile:42-48`, with `uv.lock*`).</details>
- **B4 · A smaller `uv sync` layer.** `du -sh /home/app/.venv /home/app/.cache/uv`, then `RUN uv sync --no-cache`. <details><summary>Answer</summary>About `50M` for the venv and `51M` for uv's cache; with `--no-cache` the layer drops from 105 MB to 52.4 MB and the image from 1.48 GB to 1.42 GB (checked on the recording's Docker Engine).</details>
- **B5 · Old builds and the key.** After the `.dockerignore` fix, is the old image gone? Run `docker info | grep -iE "storage driver|driver-type"` and `docker images --filter dangling=true`. <details><summary>Answer</summary>Classic store (`Storage Driver: overlay2`): the previous build stays as an untagged image that still contains `mega-pipeline.json`; `docker image prune -f` deletes it. containerd image store (`driver-type: io.containerd.snapshotter.v1`, as in the recording): no untagged copy is listed, but the old `COPY` layer, key included, stays in the build cache (delete `.dockerignore`, rebuild, and that step says `CACHED`); `docker builder prune -f` removes it. Run both.</details>

### Debugging

- **C1 · A one-shot run.** `docker run --rm -v "$(pwd):/app" transcribe_audio python cli.py -d` → `cannot execute binary file`, exit 126. <details><summary>Answer</summary>`ENTRYPOINT ["/bin/bash"]` makes it `/bin/bash python cli.py -d`; bash reads `python` as a script. Use `… transcribe_audio -c "source /home/app/.venv/bin/activate && python cli.py -d"` or `--entrypoint /home/app/.venv/bin/python … cli.py -d` (G16). `-c "python cli.py -d"` alone fails with `ModuleNotFoundError`: without activation, `python` is the image's own.</details>
- **C2 · "But my key is right there."** In `translate_text`, `cd /tmp && python /app/cli.py --help` → `DefaultCredentialsError: File secrets/mega-pipeline.json was not found.` <details><summary>Answer</summary>`translate.Client()` runs at import (`translate_text/cli.py:20`) and calls `google.auth.default()` before argparse sees `--help` (C and E likewise, at `:22` and `:21`; A and B don't). And the path is relative: from `/tmp` it means `/tmp/secrets/…`. `cd /app`.</details>
- **C3 · `AttributeError: module 'ffmpeg' has no attribute 'input'`** at `cli.py` line 67. <details><summary>Answer</summary>The wrong PyPI project (`ffmpeg` or `python-ffmpeg`, both imported as `ffmpeg`). `uv remove ffmpeg`, `uv add ffmpeg-python`, exit, rebuild (G9). Reproducible without a key: `python -c "import ffmpeg; ffmpeg.input('x')"`.</details>
- **C4 · `FileNotFoundError: [Errno 2] No such file or directory: 'ffmpeg'`** at `ffmpeg.run(stream)`, line 69. <details><summary>Answer</summary>`ffmpeg-python` starts the `ffmpeg` program, which comes from Debian through line 3. A line 3 without `ffmpeg` (the appendix's or B's) gives exactly this error. Fix line 3, exit, rebuild; the big `RUN` step runs again (G8).</details>
- **C5 · "Transcribe does nothing."** One transcript says `None`; `-t` again prints `Args: …`, `transcribe` and nothing more. <details><summary>Answer</summary>No results from Speech-to-Text leave the placeholder `text = "None"` (lines 80, 84, 95–96), and a re-run skips every recording whose `.txt` exists (lines 61–62). Delete that `.txt`, run `-t` again, and `cat` the result before `-u` (G20).</details>

### Think

- **D1 · Make it Spanish.** Which lines change, what must you delete, and do you rebuild? <details><summary>Answer</summary>`translate_text/cli.py:61` → `target_language="es"`; `synthesis_audio/cli.py:47-48` → `"es-ES"` and a Spanish voice. No rebuild (code only, through the mount). Delete `text_translated/<group>/*.txt` on your laptop before `-t` (`translate_text/cli.py:52-53`), and the French audio under `output_audios/<group>/` in the bucket before `-s`, because synthesis skips existing objects (`blob.exists()`, line 68).</details>
- **D2 · A recording called `podcast.mp3`.** How far does it get? <details><summary>Answer</summary>Downloaded (`list_blobs` takes everything, `transcribe_audio/cli.py:39-43`), transcribed to `text_prompts/<group>/podcast.txt`, never uploaded (the glob is `input-*.txt`, `:108`), and B would ignore it anyway (`generate_text/cli.py:42`). It stops after A's local output, with no error: file names are part of the interface.</details>
- **D3 · From a Mac to a VM.** A teammate builds `generate_text` on Apple Silicon and pushes it; you run it on an amd64 VM. <details><summary>Answer</summary>The image is `linux/arm64`; an amd64 machine without emulation gives `exec format error`. Build both platforms: `docker buildx build --platform linux/amd64,linux/arm64 -t <USER NAME>/generate_text --push .` (as the solution's `prod` mode does, `docker-shell.sh:62-70`), and only with the `.dockerignore` fix.</details>
- **D4 · A bucket instead of APIs.** What does it give, what does it cost? <details><summary>Answer</summary>Gains: stages needn't run at the same time; every intermediate result is a file you can inspect and redo; teams share one pipeline separated by prefixes; the leaderboard can read the same storage. Costs: nothing triggers the next stage; mistakes are silent (a wrong name or group matches nothing); two runs with one group overwrite each other; every stage needs bucket credentials. With APIs a call answers at once and can return an error, but every service must be up.</details>
- **D5 · Three ways to hand a container the key.** (a) the README as written, (b) with `.dockerignore`, (c) last year's solution (one `secrets/` outside the repo, mounted at `/secrets`). In the image? Git? After `cd /tmp`? Copies on your laptop? <details><summary>Answer</summary>(a) in every image; ignored by Git; fails after `cd /tmp`; five copies. (b) not in the image; ignored; fails after `cd /tmp`; five copies. (c) not in the image; outside the repo, nothing to ignore; works from anywhere (`/secrets/mega-pipeline.json`); one copy. (c) is where the course goes next (L04).</details>

---

## 9. Errata and open questions

**Errata (wrong, outdated, ambiguous or inconsistent)**

1. **E1 · `generate_text` ships a `pyproject.toml` that contradicts the tutorial.**
   - `generate_text/pyproject.toml:4` says `requires-python = ">=3.14"`, while the image is `python:3.12-slim-bookworm` (`generate_text/README.md:41`). Captured: `uv sync` downloads CPython 3.15.0 and builds the venv on it (§4 Step 16).
   - The README still says to run `uv init --bare` (`generate_text/README.md:20-24`), which fails because the file exists (captured, exit 2), and promises "no sample `main.py`" (`:24`) next to a committed `main.py` (`print("Hello from generate-text!")`), a leftover of a non-bare `uv init`.
   - **Fix:** skip `uv init --bare`; set `requires-python = ">=3.12"`.
2. **E2 · `uv init --bare` makes `requires-python` depend on the laptop.** No component README says that it writes `>=<your laptop's Python>` (captured: `>=3.11` on Python 3.11.2; the digest's check: `>=3.13` on a 3.13 host). Anything above 3.12 makes the image's `uv sync` download another CPython, or fail when Python downloads are disabled (G3). Last year's README pinned `">=3.12,<3.13"` (`origin/solution:transcribe_audio/README.md:36`). **Fix:** check `cat pyproject.toml` after `uv init --bare`; use `>=3.12`.
3. **E3 · "Keep ffmpeg" vs the given `ARG`.** `synthesis_audio_en/README.md:38` ("keep `ffmpeg` in the system packages") and `synthesis_audio/README.md:38` ("Audio again, so keep `ffmpeg`") contradict the `ARG DEBIAN_PACKAGES="build-essential"` a few lines below (`:45` in both). Neither synthesis `cli.py` imports ffmpeg. **The code block is right.**
4. **E4 · `cli_11.py` referenced in the wrong folder.** `synthesis_audio_en/README.md:132-135` tells you to use `cli_11.py`, which exists only in `synthesis_audio/`.
5. **E5 · Two different Canvas links for the key.** `README.md:99` links file `25687801` (updated on lecture day, commit `07e14b9`); all five component READMEs still link `23163432` (e.g. `transcribe_audio/README.md:17`), probably last year's file. **Use the main README's link.**
6. **E6 · Wrong `--help` description in E.** `synthesis_audio/cli.py:105` says `"Transcribe audio file to text"` (pasted from A); the README shows "Synthesis audio from text" (`synthesis_audio/README.md:118`). Harmless.
7. **E7 · `.mp3` names, WAV contents.** Both synthesis stages request `AudioEncoding.LINEAR16` (`synthesis_audio_en/cli.py:73`, `synthesis_audio/cli.py:72`) but name the objects `….mp3` (`:66` / `:65`). The TTS library documents that "Audio content returned as LINEAR16 also contains a WAV header" (`texttospeech_v1/types/cloud_tts.py:90-93`), so the files are most likely WAV with an `.mp3` extension (not checked on a real output: no bucket access). Most players sniff the header; tools that trust the extension may not.
8. **E8 · Dead idempotency check.** `synthesis_audio_en/cli.py:55-58` and `synthesis_audio/cli.py:54-57` test a local `…/<uuid>.mp3` that the code never writes. The real check is `blob.exists()` (`:69` / `:68`).
9. **E9 · Transcript segments glued with `""`.** `transcribe_audio/cli.py:90` joins segments with no separator. If segment transcripts don't start with a space, words at the boundaries run together; whether they do could not be confirmed (no key). `" ".join` would be safer; the LLM stage probably smooths it over.
10. **E10 · Outdated mentions of OpenAI/GPT2.** `generate_text/README.md:7` says "(or OpenAI)" and `:130` "Gemini or GPT2 API", but the code only calls Gemini on Vertex AI (`generate_text/cli.py:23-25`, `:75-77`).
11. **E11 · The key leaks into images.** `README.md:103-106` presents `.gitignore` as the protection for the key, but the build copies it into the image (`README.md:217`, no `.dockerignore`; captured with a stand-in, §4 Step 24), and the optional push (`transcribe_audio/README.md:136-140`) would publish it. The most consequential omission. **Fix:** `.dockerignore` with `secrets/` (§4 Step 25).
12. **E12 · Your work is git-ignored.** The component `.gitignore` files ignore `Dockerfile`, `pyproject.toml`, `uv.lock` and `docker-shell.sh` (`transcribe_audio/.gitignore:4-7`, etc.); the README doesn't mention it, so students who commit their work silently miss their Dockerfiles (captured, §4 Step 27). `generate_text/` has no `.gitignore` at all, inconsistent with the other four.
13. **E13 · No build command.** The component READMEs say "Build your docker image and give your image the name `transcribe_audio`" (`transcribe_audio/README.md:95`) but never give the command. It is `docker build -t transcribe_audio .`, from the component folder.
14. **E14 · `group_name` has no guard.** The default is `"pavlos"` with no assert (`transcribe_audio/cli.py:21` and peers), whereas last year's `solution` asserted it had been changed and `flexible-workflow` re-adds an assert (`flexible-workflow:README.md:134`). The README only warns (`README.md:124`).
15. **E15 · "For each paragraph" is inaccurate.** `README.md:78` says `text_audios/` holds "synthesized English audio clips for each paragraph"; the code synthesises one audio file per input text file (`synthesis_audio_en/cli.py:52-66`).
16. **E16 · Leaderboard link scheme.** `http://` in `README.md:54` and most component READMEs, `https://` in `translate_text/README.md:132`.
17. **E17 · Incomplete bucket screenshot.** `mega-pipeline-bucket.png` shows `input_audios/`, `text_audios/`, `text_paragraphs/`, `text_prompts/` and `text_translated/`, but not `output_audios/` and `output_audios_pp/` (listed at `README.md:79-80`), presumably because it predates any synthesis run.
18. **E18 · Ambiguous flow diagram.** In `mega-pipeline-flow.png`, the line that links the English "Synthesise Audio" box (step 4) to the bucket runs through the "Translate Text" box (step 5), so it reads as "Translate → Synthesise (EN)". The code reads `text_paragraphs/` (`synthesis_audio_en/cli.py:39`), Generate's output.
19. **E19 · Course-site inconsistency (context).** `tutorials_demo.md:56` calls Lecture 4 "Containers II-b" (flexible-workflow + port_toy), while the course schedule (`_modules/week-03.md:5-7`) lists Lecture 4 as "LLM - RAGs".
20. **E20 · The prompt has no venv prefix.** Expect `app@<id>:/app$`, not `(transcribe-audio) app@…`: `exec bash` re-reads `~/.bashrc` (captured, G19). Not a README error, but students look for the prefix.
21. **Time-sensitive: the default Gemini model.** `generate_text/cli.py:73` defaults to `gemini-2.5-flash-lite`, which Vertex AI retires on 2026-10-20 (Google's model-versions page, checked 2026-10-13). After that date `--generate` needs `-e GEMINI_MODEL=<current model>` (§4 Step 18).

**Open questions (couldn't be determined from the sources)**
- **Q1.** What the leaderboard reads and what counts as "success" for a stage. Its code isn't in this repo (the root `.gitignore:11-13` ignores `/api-service`, `/deployment` and `/frontend`, which suggests a staff-only copy). Presumably it lists `<prefix>/<group>/` objects.
- **Q2.** The size, length, channel count and exact names of the recordings in `input_audios/` (no bucket access). It matters because inline `RecognitionAudio(content=…)` is subject to Speech-to-Text's content limits, `operation.result(timeout=90)` may be too short for long audio, and stereo FLAC may need extra settings. The `c6bbc9b` commit message says the audio is long enough to be split into several segments.
- **Q3.** Whether Text-to-Speech Long Audio accepts `MP3` output (the code uses `LINEAR16`; the client library's docstring doesn't say).
- **Q4.** Which IAM roles the shared Canvas key has (beyond writing every prefix, which the tutorial relies on), whether it may delete objects (needed for §8 D1), and whether the staff rotate it after the lecture.
- **Q5.** Whether a student's own ElevenLabs key can use the voice id `TG3keNw5JZvsEiTtWt7t` (`synthesis_audio/cli_11.py:28`); voices are usually owned per account or shared through a library, and the README doesn't say how this one is shared.
- **Q6.** What the Ed lesson (slides, recording) adds or changes relative to the README; it was not accessible.
- **Q7.** Whether the AWS track (`dlops-io/mega-pipeline-aws`) differs materially; not examined.
- **Not recorded here at all:** any output of a command that talks to Google with a valid key (`--download`, `--transcribe`, `--generate`, `--translate`, `--synthesis`, `--upload`), the leaderboard, and the Docker Hub push. The "expected" lines in §4 come from reading the code.

---

## Links

- README (pinned commit): [main README](https://github.com/dlops-io/mega-pipeline/blob/c6bbc9ba88984e1234b68ccf5cdf7c00f7e9accc/README.md) ([Clone this Repository](https://github.com/dlops-io/mega-pipeline/blob/c6bbc9ba88984e1234b68ccf5cdf7c00f7e9accc/README.md#clone-this-repository) · [GCS Bucket Details](https://github.com/dlops-io/mega-pipeline/blob/c6bbc9ba88984e1234b68ccf5cdf7c00f7e9accc/README.md#gcs-bucket-details) · [GCP Credentials File](https://github.com/dlops-io/mega-pipeline/blob/c6bbc9ba88984e1234b68ccf5cdf7c00f7e9accc/README.md#gcp-credentials-file) · [Sample Dockerfile](https://github.com/dlops-io/mega-pipeline/blob/c6bbc9ba88984e1234b68ccf5cdf7c00f7e9accc/README.md#sample-dockerfile)) · component READMEs: [transcribe_audio](https://github.com/dlops-io/mega-pipeline/blob/c6bbc9ba88984e1234b68ccf5cdf7c00f7e9accc/transcribe_audio/README.md) · [generate_text](https://github.com/dlops-io/mega-pipeline/blob/c6bbc9ba88984e1234b68ccf5cdf7c00f7e9accc/generate_text/README.md) · [synthesis_audio_en](https://github.com/dlops-io/mega-pipeline/blob/c6bbc9ba88984e1234b68ccf5cdf7c00f7e9accc/synthesis_audio_en/README.md) · [translate_text](https://github.com/dlops-io/mega-pipeline/blob/c6bbc9ba88984e1234b68ccf5cdf7c00f7e9accc/translate_text/README.md) · [synthesis_audio](https://github.com/dlops-io/mega-pipeline/blob/c6bbc9ba88984e1234b68ccf5cdf7c00f7e9accc/synthesis_audio/README.md) · latest README on [`main`](https://github.com/dlops-io/mega-pipeline)
- Comparison: last year's [`solution` branch](https://github.com/dlops-io/mega-pipeline/tree/8083187ec0e022ba34440892689145ff703a34e0) ([`transcribe_audio/docker-shell.sh`](https://github.com/dlops-io/mega-pipeline/blob/8083187ec0e022ba34440892689145ff703a34e0/transcribe_audio/docker-shell.sh))
- Ed lesson: [L3 · Containers II](https://edstem.org/us/courses/97373/lessons/166033/) · course [tutorials page](https://harvard-iacs.github.io/2026-AC215/tutorials_demo/) · leaderboard: [ac215-mega-pipeline.dlops.io](http://ac215-mega-pipeline.dlops.io/)
- Video and materials: [video folder](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l03-mega-pipeline) · [exercises.md](https://github.com/JunyiZhou-Conny/Explainer_Videos/blob/main/videos/ac215-l03-mega-pipeline/exercises.md) · [terminal captures](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l03-mega-pipeline/assets/terminal) · [digest](https://github.com/JunyiZhou-Conny/Explainer_Videos/blob/main/videos/ac215-l03-mega-pipeline/digest.md)
- Previous: [L01 · Virtual Environments and Virtual Machines](L01-vms-venvs.md) · [L02 · Containers I](L02-containers-1.md) · Next: [L04 · Containers II-b (flexible workflow, ports)](L04-containers-2b-flexible-workflow-ports.md)
