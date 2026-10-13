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
