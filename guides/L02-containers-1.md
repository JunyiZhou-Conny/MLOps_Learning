# L02 · Containers I — study guide

[Ed lesson](https://edstem.org/us/courses/97373/lessons/166028/) · Tutorial: [`dlops-io/simple-translate`](https://github.com/dlops-io/simple-translate) `main` @ [`62f821b`](https://github.com/dlops-io/simple-translate/tree/62f821bfe09fc1c2ecb0f14354b1f205777c0efa) (🐳 Developing App using Containers, with its 📤 Pushing Docker Image to Docker Hub part, and ☁️ Running App on VM using Docker; comparison only: branch `pipenv` @ [`3a354d8`](https://github.com/dlops-io/simple-translate/tree/3a354d81f787a064aea3ab061359c9a1e223e4d5)) · Video: [AC215 · L02 follow-along](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l02-containers-1) · Made from the verified digest and real terminal captures, 2026-10-13

## 中文速览

- **做什么：** 还是 L01 那个 `dlops-io/simple-translate` CLI（`cli.py` + `pyproject.toml`）。这次在自己的 **laptop** 上按 README 分五步写一个 `Dockerfile`（每一步都 build + run 一次），build 出 image `simple-translate`，用 `docker run --rm -ti simple-translate` 进 container 跑 `python cli.py -t "Good morning" -s "en" -d "es"`（capture 里是 `Output: Buen día`）；然后 `docker tag` + `docker push` 到 Docker Hub；最后开一台只装 `docker.io` 的 GCP VM，`sudo docker run --rm -ti dlops/simple-translate` 一条命令跑同一个 app：VM 上不用 `git clone`、`pip`、`uv`。这节课不需要 service account。
- **Idea 1 · image / layer / container / registry：** image 是一叠 read-only layer 加一张 config。`RUN`、`COPY` 各加一层（`docker history`：`uv sync` 125MB、`COPY . ./` 250kB、apt/pip 那步 97.5MB），`ENV`/`ENTRYPOINT`/`CMD` 只改 config（0B）。container = 同样的 layers + 一层薄薄的 writable layer + 一个 main process（这里 bash 是 PID 1，`echo $$` 打印 `1`）。`exit` 之后 container 停掉，`--rm` 连 writable layer 一起删，image 不变。`docker tag` 只是给同一个 image ID 多一个名字，不是 copy。
- **Idea 2 · ENTRYPOINT + CMD 拼成启动命令：** `/bin/bash -c "source .venv/bin/activate && exec bash"`。设了 `ENTRYPOINT` 会清掉 base image 继承来的 `CMD ["python3"]`。`docker run` 在 image 名后面写的参数只替换 CMD：`docker run --rm -ti simple-translate python cli.py` 实际跑的是 `/bin/bash python cli.py` → `cannot execute binary file`，exit 126。想一次跑完，用 `-c "source .venv/bin/activate && python cli.py -d fr"`。
- **Idea 3 · 一个 image 里两个 Python：** `FROM python:3.12-slim-bookworm`，但 `pyproject.toml` 要 `requires-python = ">=3.13"`，所以 build 时 `uv sync` 自己下载一个 CPython：2026-10-13 uv 0.13.0 下的是 3.15.0（35.9MiB），老师的 `dlops/simple-translate`（2026-09-16 build，uv 0.12.15）里是 3.14.7。`/usr/local/bin/python` 还是 base 的 3.12.15，只用来 `pip install uv`。repo 没有 `uv.lock`、`pip install uv` 也没 pin，所以每次 build 出来的版本都可能不一样。
- **Idea 4 · layer cache 和 build context：** 哪一步变了，它和它后面的所有步骤都重跑。`COPY . ./` 在 `RUN uv sync` 前面，`.` 是整个 folder（包括 `.git` 和你自己写的 `Dockerfile`，repo 里也没有 `.dockerignore`），所以改 `cli.py`、甚至只在 Dockerfile 末尾加一行，都会重跑 `uv sync`、重新下载 Python；用 `git checkout cli.py` 改回去 cache 也回不来（`.git/index` 变了）。改进：先 copy `pyproject.toml` → `uv sync` → 再 copy code，再加一个 `.dockerignore`。
- **Idea 5 · CPU platform：** image 里的每个 binary 只适用一种 CPU。Apple Silicon 上普通 `docker build` 出来的是 `linux/arm64`，默认的 GCP E2 VM 是 `amd64`，跑不了（`no matching manifest for linux/amd64 …` 或 `exec format error`）。解法：`--platform=linux/amd64`（就是 `docker-shell.sh` 第 12 行被注释掉的那行），或者用 `docker-build-push.sh` 的 buildx 同时 push 两个 platform；deploy 前用 `docker buildx imagetools inspect` 检查。README 里完全没提。
- **最费时间的坑：** ① VM 上 `sudo apt install docker.io` 报 `E: Unable to locate package docker.io`：这一节漏了 `sudo apt-get update`，先 update 再装（capture：Debian 12 装到 Docker 20.10.24，Debian 13 是 26.1.5）。② 不加 `sudo` 的 `docker` 命令报 `permission denied … docker.sock`。③ 没 login，或者名字前缀不是自己的 username，push 报 `push access denied … insufficient_scope`。④ Docker Hub 匿名 pull 有 rate limit，报 `toomanyrequests`：等一会儿，或者先 `docker login`。⑤ 跑过 `docker-build-push.sh` 之后当前 builder 变成 `multi-arch`，普通 `docker build` 的结果不会进本地 image list：`docker buildx use default`。
- **README 的几个小 errata：** Step 4 说 pull "the image you pushed"，命令却是老师的 `dlops/simple-translate`（它只有 `linux/amd64`，里面还是旧版 `cli.py`，没有 `raise_exception=True`，被 Google 拒绝时会把原文当成翻译打印出来）；`docker login -p` 会把 token 留在 shell history 里（Docker 自己也会 warning），改用 `docker login -u <USER NAME>` 再 paste；"Build the docker container" 其实 build 出来的是 image；`docker system prune` 不加 `-a` 只删 dangling images。
- **做完要删：** Delete VM（boot disk 默认一起删），再检查 VM instances 和 Disks 两页都是空的。Docker Hub repo 默认是 public，不需要就删掉或者设成 private。laptop 上用 `docker system prune -a` 回收空间；跑过 push script 的话再 `docker buildx rm multi-arch`。
- **Lecture slides：** 老师的 Lecture 2 slides（81 页）和这份 guide 各节怎么对应、做 tutorial 需要的 10 个 lecture ideas，以及 slides 和今天 repo/captures 不一样的 12 处，都在下面的 [Lecture slides](#lecture-slides)。最要紧的两处：① slide 64 的 run 命令多了 `--entrypoint /bin/bash`，它会连 CMD 一起换掉，venv 没有 activate，`python cli.py` 报 `ModuleNotFoundError`：照 README 用 `docker run --rm -ti simple-translate`。② slide 57 的 Dockerfile 是早期版本（`ADD . /`，CMD 里 source 的是 `/home/app/.venv/bin/activate`，但 `uv sync` 建的是 `/.venv`）：照 repo 的 `Dockerfile.txt` 来。slides 没讲 CPU platform（arm64/amd64），这部分只有 tutorial 里有。

## At a glance

**What you build.** You take the same 72-line `simple-translate` CLI from L01 and package it as a Docker **image** on your laptop. The README has you write the `Dockerfile` in five steps, building and running after each one, so you see what every instruction changes: a Python prompt, then a bare bash prompt, then the code inside the image without its packages, then a venv, then a container that starts with the venv active. You run the app in a throw-away **container**, give the image a Docker Hub name and push it to the **registry**. Then you create a fresh Compute Engine VM, install only Docker, and run the app there with one `docker run` (the README's command pulls the instructor's `dlops/simple-translate`, see §9). Along the way: what a layer is, why the container runs Python 3.15 although the Dockerfile says 3.12, why rebuilds keep re-running `uv sync`, and why an image built on an Apple Silicon Mac won't run on a default VM.

**Time needed** (estimate). The laptop part: 45-60 minutes; the first build with `uv sync` takes well under a minute (the captured final build: `Building 28.1s`), but there are six build-and-run rounds. Docker Hub: 10 minutes, most of it creating the account and token. The VM part: 15-20 minutes, most of it creating the VM and installing `docker.io`. The follow-along video: about half an hour, in two parts (part 1: write the Dockerfile, build and run it; part 2: what's inside the image, the build cache, Docker Hub, CPU platforms and the VM). With the extras in §4 and the exercises, budget 2-2.5 hours.

**Prerequisites.**
- L01 and Tutorial 0: Docker Desktop installed and **running** (the `docker run hello-world` check, `README.md:110-111`), VS Code, Git, and a GCP project with billing (`README.md:20-21`).
- A free **Docker Hub account** and an **access token** that can write (`README.md:188`).
- Credentials: no GCP service account and no key: "You don't need GCP credentials (a service account) for this tutorial" (`README.md:23`).
- APIs: the Compute Engine API, which the console offers to enable the first time you open *VM instances*.
- Know your laptop's CPU: `uname -m` prints `arm64` on Apple Silicon (read §3.7 and §6 #14 before you push) and `x86_64` on Intel/AMD.

**What it costs.** The VM bills while it runs and its boot disk while it exists: a small E2 machine costs a few US cents per hour at list price (the create page shows an estimate). Docker Hub is free, and a new repository is public. On the laptop the final image takes 518MB of disk (Docker 29's count, §4 Step 13), plus the base image and the build cache.

**Tear down, exactly** (`README.md:220`):
1. On the VM: `exit` the container. With `--rm` nothing is left (`sudo docker ps -a` prints only its header).
2. Compute Engine → VM instances → select your instance → **Delete** (not Stop). The boot disk is deleted with it by default. Then check that *VM instances* and *Disks* are both empty; with the gcloud CLI on your laptop, `gcloud compute instances list` and `gcloud compute disks list`.
3. Docker Hub: delete `<USER NAME>/simple-translate-ac215`, or make it private, if you don't want it public.
4. Laptop (optional): `docker system prune -a` frees the images and the build cache; `docker buildx rm multi-arch` if you ran `docker-build-push.sh`; `docker logout` if you like.

<details>
<summary><b>Versions and sources this guide was checked against</b></summary>

- **README sections this lecture covers** (course site source `tutorials_demo.md:31-42`; lecture date Sep 8 per `_modules/week-02.md:5-7`), in `main`'s `README.md`:
  - `## 🐳 Developing App using Containers`: `README.md:106-191`, including `### 📤 Pushing Docker Image to Docker Hub` at `README.md:186-191`. GitHub anchor `#-developing-app-using-containers`, the form the course site links (`tutorials_demo.md:36`).
  - `## ☁️ Running App on VM using Docker`: `README.md:203-220`, anchor `#%EF%B8%8F-running-app-on-vm-using-docker` (`tutorials_demo.md:41`).
  - Context only: `README.md:9-16` (the four-step ladder) and the clone command at `README.md:50`. The VM walkthroughs at `README.md:38-101` belong to L01.
- **Primary repo:** `dlops-io/simple-translate`, branch `main`, commit `62f821bfe09fc1c2ecb0f14354b1f205777c0efa`, committed 2026-09-08 13:58:15 -0400 ("Handle translation exceptions with detailed error messages"); still the head of `main` on 2026-10-13.
- **Comparison only:** branch `pipenv` @ `3a354d81f787a064aea3ab061359c9a1e223e4d5` (2026-08-28; a tag `pipenv` points at the same commit), an older Pipenv / Python 3.11 variant with no history shared with `main`.
- **Terminal captures (the strongest evidence in this guide).** Every README command of both sections was run exactly as written, in README order, on 2026-10-13 (01:43-02:00 UTC), each command's output in its own file, plus the extras in §4:
  - *laptop:* a fresh Docker Engine standing in for Docker Desktop: client and engine 29.8.2, buildx v0.37.2, containerd image store, builder `default`, linux/amd64, git 2.54.0;
  - *push:* a second fresh engine; without a Docker Hub account the real push is refused, and login and push were also run against a throwaway local registry standing in for Docker Hub;
  - *VM:* fresh `debian:12` and `debian:13` containers with the baseline a Compute Engine Debian image has (`python3`, `sudo`, `curl`, a user `student` with passwordless sudo).
  - Versions seen: base image `python:3.12-slim-bookworm` @ `sha256:34386ef0…` = Python 3.12.15 (built 2026-10-06), pip 25.0.1; `pip install uv` → uv 0.13.0; `uv sync` → CPython 3.15.0 and 11 packages; `docker.io` 20.10.24 (Debian 12) and 26.1.5 (Debian 13); the published `dlops/simple-translate:latest` @ `sha256:2454010b…` (linux/amd64 only, created 2026-09-16, CPython 3.14.7, uv 0.12.15).
  - Files: [`assets/terminal/`](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l02-containers-1/assets/terminal) (`laptop/`, `laptop-push/`, `vm-debian12/`, `vm-debian13/`, `expected/`, with `capture.sh` and `run_steps.sh`); provenance in `ASSETS.md` in the same video folder.
- **Exercise checks, same day.** The claims in `exercises.md` that go beyond the captures were checked in throwaway containers built from the README's Dockerfile (Docker Engine 29.8.2, uv 0.13.0); what was run is listed in the video folder's `assets/exercise-checks/README.md`. This guide quotes them in §6 and §8.
- **The digest's own sandbox build, same day** (Docker Engine 29.8.2, linux/amd64): it built `Dockerfile.txt` and the README's five versions and inspected the published image in disposable containers. It supplies the details the captures don't show (the `/etc/bash.bashrc` prompt, the image's `.git` contents, `UV_PYTHON_DOWNLOADS=never`). Where it disagrees with the captures, this guide follows the captures (see §9).
- **Colab notebooks:** none for this lecture. **Not used:** `simple-translate-aws` (the AWS track).
- **Context repos cited in §7 only:** `mega-pipeline` main `c6bbc9ba88984e1234b68ccf5cdf7c00f7e9accc` (2026-09-27), `port_toy` main `d190c71` (2026-09-20), `ml-workflow` main `972ffbb` (2025-10-23), `cheese-app-v4` main `033f187` (2025-12-02).
- **Ed lesson:** its slides and notes were not accessible (the course site links Lecture 2 as `/not-yet/`, `_modules/week-02.md:7`); the course site source `tutorials_demo.md:31-42`, which links the two README sections above, was used instead.

</details>

## Lecture slides

The instructor's deck for this lecture is *Lecture 2: Containers I*, 81 slides. Slide numbers are PDF page numbers. The slides are not reproduced here; what follows is in our own words. The full slide digest and the cross-check with the video live in the Explainer_Videos repo, in `videos/ac215-l02-containers-1/SLIDES.md`. The lecture's tutorial slides (52–73 and 77) walk through this repo and README. Its mounting slides (42–51) and debugging slides (74–76) go beyond the README. The deck never mentions CPU platforms (§3.7), so the Apple Silicon fix exists only in the repo's scripts (this answers one of the open questions in §9).

**Map**

| This guide | Slides |
|---|---|
| At a glance; §1 What you build | 5–7 (why not VMs or venvs), 26 (why containers), 54–55, 63, 66, 70, 72 (the tutorial checklist), 77 |
| Command checklist; §4 Steps 0–5 | 52–54 (install, `docker --version`, clone), 61–62, 65 (list images and containers), 73 (prune) |
| §3.1 Image, layer, container, registry | 30–31, 34–35, 38 |
| §3.2 Dockerfile and build context; §4 Steps 6–13; §5 `Dockerfile.txt` | 32–33, 56–58 |
| §3.3 The layer cache; §4 A+5 | 36, 58, 60 |
| §3.4 ENTRYPOINT + CMD; §4 A+4 | 32–33, 40–41, 64, 75 |
| §3.5 Lifecycle and `docker run` flags; §4 Steps 14–16 | 42, 63–65, 74 |
| §3.6 Containers vs VMs | 5–6, 9–24 (user space, namespaces, cgroups, security, the Mac/Windows VM) |
| §4 A+1–A+3 (history, inside, platform) | 34–37, 59; 14 (bash as PID 1) |
| §4 Part B (push) | 66–69 |
| §4 Part C (VM) | 70–72, 77 |
| §4 Part D; §6 #24 | 73 |
| §6 Gotchas | 74–76 (the lecture's debugging tools) |
| §7 Where this sits in the course | 42–51 (mounts, used from L03), 78–79 (the Cheese App split into containers) |
| §2 costs, §3.7 CPU platforms, §3.8 two Pythons | none (tutorial-only) |

**Lecture ideas you need for this tutorial**
1. VMs isolate well but are heavy. Venvs are light but share the host's OS. Containers aim for automatic setup, isolation, a small footprint and fast start-up (slides 5–7).
2. A container is user-space code: its own files, processes and network on the host's Linux kernel. That is why your image holds Debian's files and no kernel (slides 9–12, 22).
3. Kernel namespaces give each container its own view (PID, mount, network, IPC, UTS, user), and cgroups cap what it can use. Docker adds seccomp, AppArmor/SELinux and least privilege for security; these are not the same thing as cgroups. Because of the PID namespace, bash is process 1 in your container (`echo $$`, §4 A+2) (slides 13–21).
4. On macOS and Windows, Docker Desktop runs a small Linux VM to provide that kernel. On the GCP VM, Docker runs directly on its Linux (slides 23–24).
5. Dockerfile → build → image → run → container. The image is the class and the container an instance, and many containers can start from one image (slides 30–31, 38–40).
6. The instructions are FROM, RUN, COPY/ADD, ENV, WORKDIR, ENTRYPOINT and CMD. Each RUN adds a layer, and the words after the image name in `docker run` replace CMD (slides 32–33, 41).
7. An image is read-only layers on a base ("platform") image, and a container adds one writable layer. Layers are shared, cached, and pushed only when the registry lacks them (slides 34–37, 60).
8. `docker build -t simple-translate -f Dockerfile .` names the image, picks the recipe and sends the current folder (the final `.`). Each numbered step in the log is one instruction (slides 56, 58).
9. Containers are ephemeral: with `--rm`, everything written inside is gone at exit. Mounts keep code and outputs: bind mount, named volume, tmpfs; `-v` vs the safer `--mount`; `:ro` for read-only. You use them from L03 (slides 42–51).
10. When a container misbehaves, use `docker ps -a` (exit codes, if you ran it without `--rm`), `docker logs <name>`, `docker exec -it <name> /bin/bash`, `docker inspect <name>`, or start it with `--entrypoint /bin/bash` (slides 74–76).

**Where the slides and today's tutorial differ** (the 2026-10-13 captures show what runs today)
1. Slide 64's run command adds `--name simple-translate` and `--entrypoint /bin/bash`. Overriding the entrypoint also drops the image's CMD, so the venv isn't activated and `python cli.py` fails with `ModuleNotFoundError`. Use the README's `docker run --rm -ti simple-translate` (§3.4).
2. Slide 57's Dockerfile is an earlier draft of `Dockerfile.txt`: `ADD . /`, `build-essential git`, two commented-out uv `ENV` lines, and a CMD that sources `/home/app/.venv/bin/activate`. That path doesn't exist here, because `uv sync` creates `/.venv`. Build the repo's `Dockerfile.txt` (§4 Step 12).
3. The screenshots on slides 58–60 come from other builds: a `python:3.11-slim-buster` base, a 483MB image, and a history with `USER app`, `WORKDIR /app` and `ENTRYPOINT ["uv" "run"]`. Compare your output with §4's captures, not with these.
4. Slides 70–72 pull your own pushed image on the VM, but the README's command runs the instructor's `dlops/simple-translate` (amd64 only). An image built on Apple Silicon needs an amd64 build first, which the slides never mention (§9 E3, E4).
5. Slide 67 passes the token with `-p`, as the README does, and Docker warns that this is insecure. Type `docker login -u <USER NAME>` and paste the token (§9 E9).
6. Slide 73 cleans up with `docker system prune -a`; the README's `docker system prune` keeps named images. Both are right, and `-a` is the end-of-lab clean-up (§9 E8).
7. The checklist slides say "Build a container" and "Push container". The build makes an image, as slides 30 and 56 say (§9 E7).
8. Slide 34 says every command makes a layer, and slide 37 draws the kernel and a single Python as image layers. `docker history` shows that `ENV`, `ENTRYPOINT` and `CMD` are `0B`, the apt/pip/uv step is one layer, the code is a layer, the kernel is the host's, and the image holds two Pythons (§3.1, §3.8).
9. Slides 22 and 24 draw system calls going through the Docker daemon. In fact a container's own processes call the kernel directly; the daemon sets up their namespaces and cgroups (§3.6).
10. Slides 24 and 52 name HyperKit (Mac) and Hyper-V (Windows). Current Docker Desktop uses Apple's Virtualization framework on a Mac and WSL 2 on Windows, but the idea, a small Linux VM, is the same. This wasn't checked here: there is no Mac or Windows capture.
11. Slide 17 says root in a container is non-root on the host. That needs user-namespace remapping or rootless Docker, which a default install doesn't turn on, so treat the container's root as root (§6 #22).
12. The links on slides 72 and 77 end in `-t3` / `-t4`, anchors the README doesn't have, so they open the README at the top. Use the section links under Links.

## Command checklist

Commands in backticks are exactly as the README writes them (placeholders kept). Plain items are console clicks or editor actions. Items marked *(extra)* are not in the README; they come from §4, where the real output of every captured command is shown. `<USER NAME>` is your Docker Hub username (the captures use `student`), and `ac215-l02` stands for your VM's name. The video's trackers number the README bullets A1-A16 (laptop), B1-B4 (Docker Hub) and C1-C7 (VM).

### Before the README *(extra)*

- [ ] Start Docker Desktop and wait until it says the engine is running.
- [ ] `docker run hello-world` — *(extra; the Tutorial 0 check the README's note points back to, `README.md:110-111`)* prints "Hello from Docker!".
- [ ] `uname -m` — *(extra)* `arm64` = Apple Silicon, `x86_64` = Intel/AMD. Remember it for the push.

### 🐳 Developing App using Containers

*(`README.md:106-184`; video tracker A1-A16)*

*Make sure we do not have any running containers and clear up an unused images* (`README.md:113-118`)
- [ ] `docker container ls` — lists running containers; in a clean setup only the header row.
- [ ] Stop any container that is running — `docker stop <CONTAINER ID>` *(extra)* for each one listed.
- [ ] `docker system prune` — lists the four things it removes and asks `[y/N]`; type `y`. Captured: `Total reclaimed space: 0B`.
  - Note: it removes only *dangling* (untagged) images, not every unused image; `docker system prune -a` would (§9 E8).
- [ ] `docker image ls` — your images; captured: an empty table (Docker 29 columns `IMAGE  ID  DISK USAGE  CONTENT SIZE  EXTRA`).

*Clone the github repository* (`README.md:120-125`)
- [ ] Clone or download from [here](https://github.com/dlops-io/simple-translate) — on your **laptop**, not on last lecture's VM. The command (from `README.md:50`): `git clone https://github.com/dlops-io/simple-translate.git`
- [ ] `cd simple-translate` — (from `README.md:51`) everything below runs in this folder.
- [ ] `ls -a` — *(extra)* `Dockerfile.txt` is there; no file called `Dockerfile`, no `uv.lock`, no `.dockerignore`.
- [ ] `git log --oneline -1` — *(extra)* `62f821b Handle translation exceptions with detailed error messages`, or a newer commit.
- [ ] `docker build -t simple-translate -f Dockerfile .` — *(extra, run early on purpose)* fails with `failed to read dockerfile: open Dockerfile: no such file or directory`: you write that file next.

*Create Dockerfile* (`README.md:127-168`; "Do a Build + Run after each step", `README.md:130`, with the commands from `README.md:174` and `:180`)
- [ ] Inside the `simple-translate` folder create a file called `Dockerfile` — in VS Code; exactly `Dockerfile`, capital D, no extension.
- [ ] **Step 1** (`README.md:132-137`): `# Use the official Debian-hosted Python image` and `FROM python:3.12-slim-bookworm`
  - [ ] `cat Dockerfile` — *(extra)* shows the file.
  - [ ] Build: `docker build -t simple-translate -f Dockerfile .` — downloads the base image's four layers, ends with `naming to docker.io/library/simple-translate:latest`.
  - [ ] `docker image inspect simple-translate --format 'Entrypoint={{json .Config.Entrypoint}} Cmd={{json .Config.Cmd}} WorkingDir={{json .Config.WorkingDir}}'` — *(extra)* `Entrypoint=null Cmd=["python3"] WorkingDir=""`.
  - [ ] Run: `docker run --rm -ti simple-translate` — a Python REPL: `Python 3.12.15 (main, Oct  6 2026, 02:02:31) [GCC 12.2.0] on linux`; leave with `exit()`.
  - [ ] `git status` — *(extra)* `nothing to commit, working tree clean`: `.gitignore` line 3 hides your `Dockerfile`.
- [ ] **Step 2** (`README.md:139-143`): `ENTRYPOINT ["/bin/bash"]`
  - [ ] Build: `docker build -t simple-translate -f Dockerfile .` — the `FROM` step says `CACHED`; no new layer.
  - [ ] `docker image inspect simple-translate --format 'Entrypoint={{json .Config.Entrypoint}} Cmd={{json .Config.Cmd}}'` — *(extra)* `Entrypoint=["/bin/bash"] Cmd=null`.
  - [ ] Run: `docker run --rm -ti simple-translate` — a bare bash prompt like `root@f72851da4a58:/#`; type `exit`.
- [ ] **Step 3** (`README.md:145-152`): `# Install uv`, `RUN pip install uv`, `# Copy the source code`, `COPY . ./`
  - [ ] Build: `docker build -t simple-translate -f Dockerfile .` — `transferring context: 63.12kB`, `Successfully installed uv-0.13.0`, then `COPY . ./`.
  - [ ] Run: `docker run --rm -ti simple-translate`, then `ls` and `python cli.py` *(extra, at the container prompt)* — your files sit in `/`; `python cli.py` fails with `ModuleNotFoundError: No module named 'art'`; `exit`.
- [ ] **Step 4** (`README.md:154-158`): `RUN uv sync`
  - [ ] Build: `docker build -t simple-translate -f Dockerfile .` — `COPY . ./` runs again although you only added a line; `uv sync` downloads CPython 3.15.0 and installs 11 packages.
  - [ ] Run: `docker run --rm -ti simple-translate`, then `ls -a`, `python cli.py`, `.venv/bin/python --version` and `source .venv/bin/activate && python cli.py` *(extra)* — `.venv` and `uv.lock` are new; `python cli.py` still fails; `Python 3.15.0`; after `source`, the app works and the prompt starts with `(app)`; `exit`.
- [ ] **Step 5** (`README.md:160-165`): `# Get into the uv virtual environment shell` and `CMD ["-c", "source .venv/bin/activate && exec bash"]`
  - [ ] Build: `docker build -t simple-translate -f Dockerfile .` — `COPY . ./` and `uv sync` run again, for one added line.
  - [ ] `docker image inspect simple-translate --format 'Entrypoint={{json .Config.Entrypoint}} Cmd={{json .Config.Cmd}}'` — *(extra)* `Entrypoint=["/bin/bash"] Cmd=["-c","source .venv/bin/activate && exec bash"]`.
  - [ ] Run: `docker run --rm -ti simple-translate`, then `which python`, `python --version`, `echo $VIRTUAL_ENV` *(extra)* — `/.venv/bin/python`, `Python 3.15.0`, `/.venv`: the venv is active although the prompt shows no `(app)`; `exit`.
- [ ] **Solution Dockerfile:** `Dockerfile.txt` (`README.md:167-168`)
  - [ ] `diff Dockerfile Dockerfile.txt` — *(extra)* the three `ENV` lines, the `RUN set -ex; apt-get …` block, `ENTRYPOINT` moved to the end (add `-u` if your `diff` prints `<`/`>` lines).
  - [ ] `cp Dockerfile.txt Dockerfile` — *(extra; the README only names the file)* use the solution from here on.

*Build Docker Image* (`README.md:170-174`)
- [ ] In a terminal make sure you are the location of `simple-translate` — `pwd` *(extra)* if unsure.
- [ ] `docker build -t simple-translate -f Dockerfile .` — the compact view: `[+] Building 28.1s (9/9) FINISHED`, four steps.
- [ ] `docker image ls` — *(extra)* `simple-translate:latest`, `518MB` disk usage, `144MB` content size (Docker 29).

*Run Docker Container* (`README.md:176-184`)
- [ ] `docker run --rm -ti simple-translate` — the prompt `root@<id>:/#`.
- [ ] `python cli.py -t "Good morning" -s "en" -d "es"` — the AC215 banner, `Arguments: Namespace(text='Good morning', file='', src='en', dest='es')`, `Input: Good morning`, `Output: Buen día`.
  - Note: a `RuntimeError: Translation request to Google Translate failed …` means Google's unofficial endpoint refused the request; retry later or from another network. Docker is fine.
- [ ] Type `exit` from the Docker shell — back on your laptop.
- [ ] `docker ps -a` — *(extra)* only the header: `--rm` deleted the container.

### After the run, before the push *(extra)*

*Look inside the image* (§4 Part A+)
- [ ] `docker history simple-translate` — *(extra)* the layers: `uv sync` 125MB, `COPY . ./` 250kB, the apt/pip `RUN` 97.5MB, `ENV`/`ENTRYPOINT`/`CMD` 0B.
- [ ] `docker run --rm -ti simple-translate`, then `pwd`, `echo $$`, `which python`, `python --version`, `/usr/local/bin/python --version`, `ls /root/.local/share/uv/python`, `cat .venv/pyvenv.cfg`, `ls -a /` — *(extra)* `/`, `1`, `/.venv/bin/python`, `Python 3.15.0` vs `Python 3.12.15`, uv's own Python folder, `uv = 0.13.0`, the whole build context in `/`; `exit`.
- [ ] `uname -m; docker image inspect simple-translate --format '{{.Os}}/{{.Architecture}}'` — *(extra)* `x86_64` and `linux/amd64` on Intel/AMD; `linux/arm64` on Apple Silicon.

*The start-up command* (§3.4)
- [ ] `docker run --rm -ti simple-translate python cli.py` — *(extra, meant to fail)* `/usr/local/bin/python: /usr/local/bin/python: cannot execute binary file`, exit 126.
- [ ] `docker run --rm simple-translate -c "source .venv/bin/activate && python cli.py -d fr"` — *(extra)* one-shot run: `Output: j'adore le fromage`.

*The layer cache* (§3.3)
- [ ] `docker build --progress=plain -t simple-translate -f Dockerfile .` — *(extra)* nothing changed: every step `CACHED`.
- [ ] Change `default="I love cheese"` to `default="I love brie"` on line 49 of `cli.py`, then `git diff` — *(extra)*.
- [ ] `docker build --progress=plain -t simple-translate -f Dockerfile .` — *(extra)* the apt/pip step `CACHED`; `COPY . ./` and `RUN uv sync` run, CPython downloaded again.
- [ ] `git checkout cli.py`, then `docker build --progress=plain -t simple-translate -f Dockerfile .` — *(extra)* the cache does **not** come back: `.git/index` changed.
- [ ] `sh docker-shell.sh` — *(extra; a repo helper the README doesn't mention)* build + run in one go, with `--name simple-translate`; `exit`.

### 📤 Pushing Docker Image to Docker Hub

*(`README.md:186-191`; video tracker B1-B4)*
- [ ] Sign up in Docker Hub and create an [Access Token](https://hub.docker.com/settings/security) — give it write access; copy it right away.
- [ ] `docker login -u <USER NAME> -p <ACCESS TOKEN>` — prints `WARNING! Using --password via the CLI is insecure. Use --password-stdin.`, then `Login Succeeded`.
  - Note: works as written, but the token stays in your shell history. Safer: `docker login -u <USER NAME>` and paste the token at the prompt (§9 E9).
- [ ] `docker tag simple-translate <USER NAME>/simple-translate-ac215` — no output; a second name for the same image.
- [ ] `docker image ls` — *(extra)* two names, one image ID.
- [ ] `docker push <USER NAME>/simple-translate-ac215` — uploads the layers Docker Hub doesn't have and ends with `latest: digest: sha256:… size: …`.
  - Note: not logged in, or a name that doesn't start with your username: `push access denied, repository does not exist or may require authorization: server message: insufficient_scope: authorization failed` (captured).
  - Note: on Apple Silicon this pushes a `linux/arm64` image that a default GCP VM can't run. Push an amd64 or multi-platform build instead (next block).
- [ ] `docker buildx imagetools inspect <USER NAME>/simple-translate-ac215` — *(extra)* lists the platform(s) you pushed; it must include `Platform: linux/amd64` for a default VM.
- [ ] `docker buildx imagetools inspect dlops/simple-translate` — *(extra)* the instructor's image: a single `application/vnd.docker.distribution.manifest.v2+json`, not a multi-platform index.

*Apple Silicon only: publish an image the VM can run* *(extra, not in the README; §4 Step 21)*
- [ ] `docker build -t simple-translate --platform=linux/amd64 -f Dockerfile .` — *(extra; the commented-out `docker-shell.sh:12`)* then `docker tag` and `docker push` again as above.
- [ ] Or edit `docker-build-push.sh` (`IMAGE_NAME="simple-translate-ac215"` on line 7, your username on line 11) and run `bash docker-build-push.sh` — *(extra)* builds and pushes `linux/amd64` + `linux/arm64`.
- [ ] `docker buildx use default` — *(extra)* afterwards, so plain `docker build`s load into your image list again (`desktop-linux` on Docker Desktop; check `docker buildx ls`).

### ☁️ Running App on VM using Docker

*(`README.md:203-220`; video tracker C1-C7)*
- [ ] Create a VM Instance from [GCP](https://console.cloud.google.com/compute/instances) — the README gives no settings. Sensible ones: name `ac215-l02`, zone us-central1-a, machine type e2-small (E2 machines are amd64), boot disk Debian 12 or 13, external IPv4 on (the default).
- [ ] `gcloud compute instances create ac215-l02 --zone=us-central1-a --machine-type=e2-small --image-family=debian-12 --image-project=debian-cloud` — *(extra)* the CLI alternative, from your laptop.
- [ ] SSH into your newly created instance — the **SSH** button in the instance row (or `gcloud compute ssh ac215-l02 --zone=us-central1-a` *(extra)*).
- [ ] `uname -m` — *(extra)* `x86_64`.
- [ ] `sudo apt install docker.io` — Debian's packaged Docker engine; answer `Y`.
  - Note: in the capture (fresh Debian, empty package lists) it failed as written: `E: Unable to locate package docker.io` (Debian 13: `Error: Unable to locate package docker.io`), exit 100. The README skips the `sudo apt-get update` it used in L01 (`README.md:44`). If you see this, or `404 Not Found`, run the next line and repeat the install.
- [ ] `sudo apt-get update` — *(extra)* fresh package lists; then `sudo apt install docker.io` again: Debian 12 `1 upgraded, 92 newly installed`, `Need to get 107 MB`; Debian 13 `Upgrading: 1, Installing: 91`, `Download size: 118 MB`.
- [ ] `sudo docker --version` — `Docker version 20.10.24+dfsg1, build 297e128` (Debian 12) or `Docker version 26.1.5+dfsg1, build a72d7cd` (Debian 13).
- [ ] `docker ps` — *(extra)* without `sudo`: `permission denied while trying to connect to the Docker daemon socket at unix:///var/run/docker.sock: …`. That's why the README writes `sudo`.
- [ ] `sudo docker run --rm -ti dlops/simple-translate` — `Unable to find image 'dlops/simple-translate:latest' locally`, seven `Pull complete`, then the prompt `root@<id>:/#`.
  - Note: `toomanyrequests: You have reached your unauthenticated pull rate limit` (captured once) means Docker Hub's anonymous pull limit for your network address: wait, or `sudo docker login` first.
  - Note: this is the instructor's image, not the one you pushed (§9 E4). Yours: `sudo docker run --rm -ti <USER NAME>/simple-translate-ac215` *(extra)*, once it's built for amd64.
- [ ] `python cli.py` — the banner, `Arguments: Namespace(text='I love cheese', file='', src='en', dest='it')`, `Input: I love cheese`, `Output: Adoro il formaggio`.
  - Note: if `Output:` simply repeats `I love cheese`, Google refused the request; the published image's older `cli.py` doesn't raise an error (§6 #20).
- [ ] `python --version` — *(extra)* `Python 3.14.7`; then `exit`.
- [ ] `sudo docker ps -a` — *(extra)* only the header row.
- [ ] Delete your VM when you're done. A running VM keeps charging even when idle. Go to [VM instances](https://console.cloud.google.com/compute/instances), select your instance, and click Delete.
- [ ] `gcloud compute instances delete ac215-l02 --zone=us-central1-a` — *(extra)* the CLI alternative to the Delete click.
- [ ] `gcloud compute instances list` and `gcloud compute disks list` — *(extra)* neither should still list `ac215-l02`.

### After the README *(extra, optional)*

- [ ] `docker system prune -a` — frees the laptop's images and build cache (they download again when needed).
- [ ] `docker buildx rm multi-arch` — only if you ran `docker-build-push.sh`.
- [ ] `docker logout` — removes the stored Docker Hub credential.
- [ ] On hub.docker.com: delete `<USER NAME>/simple-translate-ac215` or make it private.

---

## 1. What you build

You package the small translator `cli.py` as a Docker **image**: a Debian 12 userland (files, not a kernel), the base image's Python 3.12, `uv`, a second CPython that uv downloads because `pyproject.toml` asks for ≥ 3.13 (3.15.0 on 2026-10-13), the app's virtual environment in `/.venv`, and the source code in `/`. You build it on your laptop, run it as a throw-away **container**, give it a Docker Hub name and push it to the **registry**. Then you create a Compute Engine VM, install only Docker, and run the app with one `docker run`: no `git clone`, no `pip`, no `uv` on the VM. The README's command pulls the instructor's `dlops/simple-translate`, not the image you pushed (§9 E4).

This is steps 3 and 4 of the README's four-step ladder (`README.md:9-16`); steps 1 and 2, the manual install and uv on a VM, were L01. The app has no web server, so no ports are published and no volumes are mounted. The only network traffic is the build's downloads and the app's HTTPS call to Google's unofficial translate endpoint.

```
 YOUR LAPTOP  (Apple Silicon = arm64, Intel/AMD = amd64)
 +--------------------------------------------------------------------------+
 |  ~/.../simple-translate/        (git clone, on the laptop)               |
 |    Dockerfile  (you write it; solution = Dockerfile.txt; git-ignored)    |
 |    cli.py  pyproject.toml  docker-shell.sh  docker-build-push.sh  .git/  |
 |       |                                                                  |
 |       |  docker build -t simple-translate -f Dockerfile .                |
 |       |  (the final "." = build context: the whole folder, sent to the   |
 |       v   builder; no .dockerignore, so .git/ and Dockerfile go too)     |
 |  +-- Docker Desktop: a hidden Linux VM (on Linux: the host kernel) --+   |
 |  |  dockerd + BuildKit, local image store                            |   |
 |  |  simple-translate:latest = 4 base layers (python:3.12-slim-       |   |
 |  |     bookworm) + 3 yours (apt/pip/uv 97.5MB, COPY 250kB,           |   |
 |  |     uv sync 125MB) + config (ENTRYPOINT/CMD)   518MB on disk      |   |
 |  |        | docker run --rm -ti simple-translate                     |   |
 |  |        v                                                          |   |
 |  |  [container] /bin/bash -c "source .venv/bin/activate && exec bash"|   |
 |  |   root@<id>:/# python cli.py -t "Good morning" -s "en" -d "es" ---+---+--> HTTPS translate.googleapis.com
 |  +-------------------------------------------------------------------+   |     (googletrans, unofficial endpoint)
 +--------------------------------|-----------------------------------------+
                                  | docker login / docker tag / docker push
                                  | (only layers the registry lacks are uploaded)
                                  v
                 +----------------------------------------------+
                 |  Docker Hub  (registry, docker.io)           |
                 |   <USER NAME>/simple-translate-ac215:latest  |  <- yours: arm64 if built
                 |   dlops/simple-translate:latest              |     plainly on an M-series Mac
                 |     (instructor's; linux/amd64 only)         |
                 +----------------------|-----------------------+
                                        | docker pull (implicit in docker run)
                                        v
 GOOGLE CLOUD PROJECT -> Compute Engine VM ac215-l02 (Debian 12/13, E2 = x86_64 = amd64)
 +--------------------------------------------------------------------------+
 |  sudo apt-get update  (extra)  +  sudo apt install docker.io  -> dockerd |
 |  sudo docker run --rm -ti dlops/simple-translate   (7 layers pulled)     |
 |    [container] root@<id>:/# python cli.py  -------------------------------+--> HTTPS translate.googleapis.com
 +--------------------------------------------------------------------------+
   No ports (-p), no volumes (-v), no service account, no secrets.

 Start-up command of every container from this image (Dockerfile.txt:27,29):
   ENTRYPOINT ["/bin/bash"]  +  CMD ["-c", "source .venv/bin/activate && exec bash"]
   = /bin/bash -c "source .venv/bin/activate && exec bash"
     -> PATH=/.venv/bin:...  -> python = /.venv/bin/python -> uv's CPython 3.15.0
        (/usr/local/bin/python = the base image's 3.12.15, used only for "pip install uv")
```

---

## 2. Prerequisites and costs

**Accounts**
- A **GCP project with billing enabled**, from Tutorial 0 (`README.md:20-21`). Only the **Compute Engine API** is used; the console asks you to enable it the first time you open *VM instances*.
- A **Docker Hub account** and an **access token**, used as the password for `docker login` (`README.md:188-189`). The README links `https://hub.docker.com/settings/security`; whether that page or a newer "personal access tokens" page is current could not be checked without an account (§9).
- No service account and no JSON key: "You don't need GCP credentials (a service account) for this tutorial" (`README.md:23`).

**Local installs** (from Tutorial 0, `README.md:110-111`)
- Docker Desktop, running. Check with `docker run hello-world`. VS Code and Git.
- `uv` is not needed on the laptop for L02: the image installs its own (`Dockerfile.txt:19`).
- Your CPU architecture matters from the push on: `uname -m` → `arm64` (Apple Silicon) or `x86_64` (Intel/AMD).

**GCP APIs**
- `compute.googleapis.com`; from the CLI: `gcloud services enable compute.googleapis.com`. Nothing else.

**Service accounts / keys / secrets / env vars**
- `cli.py` reads no environment variables and no secrets files.
- `Dockerfile.txt` sets three environment variables in the image: `DEBIAN_FRONTEND=noninteractive`, `LANG=C.UTF-8`, `PYTHONUNBUFFERED=1` (`Dockerfile.txt:5`, `:8`, `:11`).
- Your Docker Hub token is stored by `docker login`: on Docker Desktop through its credential helper; on a plain Linux engine it is written to `~/.docker/config.json`, and Docker warns about that (captured: `WARNING! Your credentials are stored unencrypted in '/home/student/.docker/config.json'.`). Never put it in the repo.

**Where the code expects things (paths)**

| Thing | Where | Set by |
|---|---|---|
| Repo checkout | a folder on your **laptop**, e.g. `~/ac215/simple-translate` | `git clone` (`README.md:123-125`, command at `:50`) |
| The recipe | `./Dockerfile` in the repo root, which you create; the repo ships only `Dockerfile.txt`, and `.gitignore:3` ignores `Dockerfile` | you (`README.md:128`) |
| Build context | `.` = the whole repo folder, `.git/` and `Dockerfile` included (no `.dockerignore`) | the last argument of `docker build` (`README.md:174`) |
| App inside the image | `/cli.py`, `/pyproject.toml`, … in the image's top folder: no `WORKDIR` | `COPY . ./` (`Dockerfile.txt:22`) |
| Lockfile inside the image | `/uv.lock`, written during the build (the repo has none) | `RUN uv sync` (`Dockerfile.txt:24`) |
| Virtual environment | `/.venv` (`VIRTUAL_ENV=/.venv`) | `RUN uv sync` |
| uv's downloaded Python | `/root/.local/share/uv/python/cpython-3.15.0-linux-x86_64-gnu` (+ the link `cpython-3.15-linux-x86_64-gnu`) | `RUN uv sync` |
| The base image's Python | `/usr/local/bin/python` (3.12.15) | `FROM python:3.12-slim-bookworm` (`Dockerfile.txt:2`) |
| Local image | `simple-translate:latest` (`docker.io/library/simple-translate:latest`) | `-t simple-translate` |
| Pushed image | `docker.io/<USER NAME>/simple-translate-ac215:latest` | `docker tag` + `docker push` (`README.md:190-191`) |
| Docker on the VM | Debian's `docker.io` package; the daemon socket `/var/run/docker.sock` (root and group `docker` only) | `sudo apt install docker.io` (`README.md:210`) |

**Billable resources and how to shut them down**

| Resource | Billed while | How to stop it |
|---|---|---|
| Compute Engine VM (any E2 type; e2-small costs a few US cents per hour at list price; the create page shows an estimate) | running, even idle | **Delete** the VM (`README.md:220`). Stopping keeps the disk billed. |
| Boot persistent disk (10 GB by default) | it exists, even while the VM is stopped | deleted with the VM by default (a setting on the boot disk, chosen on the create form) |
| Ephemeral external IPv4 | VM running | released when the VM is deleted |
| Docker Hub repository | free; public by default | optional: delete it, or make it private |
| Laptop disk (images, build cache, a buildx builder container) | n/a | `docker system prune -a`; `docker buildx rm multi-arch` if you ran `docker-build-push.sh` |

- After deleting, check that *Compute Engine → VM instances* and *Compute Engine → Disks* are empty (CLI: `gcloud compute instances list`, `gcloud compute disks list`; delete with `gcloud compute instances delete ac215-l02 --zone=us-central1-a`, not from the README).
- Installing `docker.io` uses about half a GB of the VM's disk (captured on Debian 12: `After this operation, 452 MB of additional disk space will be used.`; Debian 13: `Space needed: 499 MB`), well within the default disk.

---

## 3. Concepts this tutorial teaches

### 3.1 Image, layer, container, registry (and tag)
- **Explanation.**
  - An **image** is a read-only stack of filesystem **layers** plus a small JSON **config**: environment variables, entrypoint, default command, working directory, CPU architecture.
  - Each `RUN` or `COPY` instruction adds one layer: the files it added or changed. `ENV`, `ENTRYPOINT` and `CMD` only write on the config. Captured `docker history simple-translate` (`laptop/34`), read bottom-up = the Dockerfile top-down: the apt/pip `RUN` 97.5MB, `COPY . ./` 250kB, `RUN uv sync` 125MB, and `0B` for every `ENV`, `ENTRYPOINT` and `CMD` row. Below them sit the base image's rows, Debian bookworm (85.3MB) at the bottom.
  - A **container** is a running (or stopped) instance: the image's layers, shared and read-only, plus one thin **writable layer** on top, plus one main process. Here that process is bash with PID 1 (captured: `echo $$` prints `1`).
  - A **registry** (Docker Hub) stores layers and manifests under repository names. A **tag** such as `latest` is a movable name for one image, or for an index of per-platform images (§3.7). `docker tag` adds a second name to the same image ID (captured: `simple-translate:latest` and `student/simple-translate-ac215:latest`, both `b5c531a6b555`).
- **Mental model.** The image is a *class*; containers are *instances*. The registry is *PyPI for images*. A tag is like a *git branch name*: it points at a content hash and can move.
- **Analogy.** A frozen meal in a sealed tray, its ingredients stacked in the order they went in. A container is that meal heated on a plate: you can add salt, which only touches the plate, and when you throw the plate away (`--rm`), the tray in the freezer is unchanged.
- **Common misconception.** "`docker build` builds a container." The README says "Build the docker container" (`README.md:173`), but building makes an **image**; running makes a container.
  Another is "my changes inside the container are saved." They live only in that container's writable layer and disappear with `--rm`.

### 3.2 Dockerfile, build context and working directory
- **Explanation.** A Dockerfile is a recipe the builder (BuildKit) runs top to bottom:
  - `FROM` picks the starting image;
  - `ENV` sets environment variables in the config;
  - `RUN` runs a shell command in a temporary container and saves the result as a layer;
  - `COPY . ./` copies files from the **build context**: the folder you pass as the last argument of `docker build`, here `.`;
  - `ENTRYPOINT` and `CMD` record what runs when a container starts.

  The python base image sets no working directory (captured `docker image inspect`: `WorkingDir=""`), and the Dockerfile adds no `WORKDIR`, so relative paths mean `/`: `COPY . ./` puts `cli.py` at `/cli.py` (the traceback shows `File "//cli.py", line 8`), and `uv sync` creates `/.venv`.
- **Mental model.** `docker build` = "pack the folder `.` into a parcel, send it to the builder, replay the recipe, save a snapshot after each step."
- **Analogy.** A lab protocol: the context is the box of reagents you hand the technician, who can use nothing outside the box.
- **Common misconception.** "`COPY` copies only what my app needs." It copies *everything* in the context that a `.dockerignore` doesn't exclude, and this repo has none. Captured `ls -a /` in the container: `.git`, `.gitignore`, `.vscode`, `Dockerfile`, `Dockerfile.txt`, `README.md`, `docker-build-push.sh`, `docker-shell.sh` sit next to `bin`, `etc`, `usr`. The published `dlops/simple-translate` image carries the author's `.git` with its commit log, author names and e-mail addresses included.

### 3.3 The layer cache and instruction order
- **Explanation.** BuildKit reuses a step (`CACHED`) when its parent step and its instruction are unchanged and, for `COPY`, the copied files have the same checksum. The first step that changes runs again, **and so does every step after it**. In `Dockerfile.txt`, `COPY . ./` (line 22) comes before `RUN uv sync` (line 24). Captured with `--progress=plain`:
  - nothing changed: `[2/4] RUN set -ex; …`, `[3/4] COPY . ./` and `[4/4] RUN uv sync` all `CACHED` (`laptop/38`);
  - after changing one word in `cli.py`: `[2/4]` `CACHED`, but `COPY . ./` and `uv sync` run, CPython download included (`laptop/40`);
  - after `git checkout cli.py` to undo it: they run **again** (`laptop/41`). The files are back, but git rewrote `.git/index`, which is in the context too;
  - while following the README's five steps: the Step 4 build re-ran `COPY . ./` although only `RUN uv sync` was appended, and the Step 5 build re-ran `COPY . ./` and `uv sync`, CPython download included, for one added `CMD` line (`laptop/21`, `laptop/24`), because your `Dockerfile` is itself in the context.
- **Mental model.** A row of dominoes: a change knocks over its own domino and everything to its right, never anything to its left. Put the slow, rarely-changing steps on the left: copy `pyproject.toml` (and later `uv.lock`), run `uv sync`, then copy the code; keep `.git`, a local `.venv` and the Dockerfile out with a `.dockerignore`.
- **Analogy.** Redoing a recipe from the step where you changed an ingredient. Changing the garnish shouldn't make you bake the cake again.
- **Common misconception.** "Docker caches per file, so changing `cli.py` only re-copies `cli.py`." It re-runs every later instruction. A second one: "undoing the edit brings the cache back." Not when `.git` is in the context.

### 3.4 ENTRYPOINT + CMD = the container's command line
- **Explanation.** At start-up Docker runs `ENTRYPOINT` followed by `CMD`, as one argument list. Here: `["/bin/bash"]` + `["-c", "source .venv/bin/activate && exec bash"]` = `/bin/bash -c "source .venv/bin/activate && exec bash"` (`Dockerfile.txt:27`, `:29`; captured `docker image inspect`: `Entrypoint=["/bin/bash"] Cmd=["-c","source .venv/bin/activate && exec bash"]`).
  - `source` runs the venv's activate script in that first bash: `PATH` now starts with `/.venv/bin`, and `VIRTUAL_ENV=/.venv`.
  - `exec bash` *replaces* that bash with an interactive one that inherits the variables and gives you a prompt. It is PID 1, so `exit` ends the container.
  - Anything you type after the image name in `docker run IMAGE …` **replaces CMD only**. `--entrypoint` replaces the entrypoint (and clears the image's CMD).
  - Setting `ENTRYPOINT` also resets a `CMD` inherited from the base image. Captured: after Step 1 the config is `Entrypoint=null Cmd=["python3"]` (a Python REPL starts); after Step 2 it is `Entrypoint=["/bin/bash"] Cmd=null` (a bare bash starts).
- **Mental model.** ENTRYPOINT is the *program*, CMD its *default arguments*; `docker run` arguments are *replacement arguments*.
- **Analogy.** A coffee machine: ENTRYPOINT is "brew", CMD is the default "medium latte" button. Typing your own order replaces the latte, not the brewing.
- **Common misconception.** "`docker run --rm -ti simple-translate python cli.py` runs my script." It runs `/bin/bash python cli.py`. Bash takes `python` as the name of a shell script; there is no such file in `/`, so it searches `PATH`, where nothing has activated the venv, finds the base image's binary `/usr/local/bin/python`, and refuses to read a binary as a script. Captured (`laptop/36`): `/usr/local/bin/python: /usr/local/bin/python: cannot execute binary file`, exit 126.

### 3.5 Container lifecycle and the `docker run` flags
- **Explanation.**
  - `-i` keeps standard input open, so your keystrokes reach bash.
  - `-t` gives the container a terminal: a prompt, line editing.
  - `--rm` deletes the container, writable layer included, when its main process exits.
  - `--name simple-translate` (only in `docker-shell.sh:15`) gives it a fixed name, which must be unique among existing containers.
  - The container lives as long as its main process; typing `exit` stops it (`README.md:184`). `docker container ls` (= `docker ps`) lists running containers, `docker ps -a` stopped ones too (captured after the README's run: only the header).
  - `docker system prune` removes stopped containers, unused networks, **dangling** images and unused build cache (captured warning list); `-a` also removes every image no container uses.
- **Mental model.** A container is a process with its own view of the filesystem. When the process ends, the container stops.
- **Analogy.** A hotel room: `--rm` is "housekeeping wipes the room at checkout". Without it, the room (a stopped container) stays booked and keeps its mess.
- **Common misconception.** "A stopped container is gone." Without `--rm` it stays, writable layer and all, until `docker rm`; `docker start -ai <name>` even restarts it with your files still there (exercise B2).

### 3.6 Containers vs VMs (and why a Mac needs a hidden VM)
- **Explanation.** A VM virtualizes hardware and boots its own kernel. A container is an isolated *process* that shares the host's Linux kernel (namespaces and cgroups). Linux images need a Linux kernel, so Docker Desktop on macOS or Windows runs a small Linux VM and your containers run inside it. On the GCP VM, Docker runs directly on the VM's Debian kernel. Step 4 of the ladder stacks both: a container inside a cloud VM.
- **Mental model.** VM = a separate house. Container = a separate apartment in one building: own door and furniture, shared plumbing (the kernel).
- **Analogy.** A shipping container: the same sealed box rides on a truck, a train or a ship; the vehicle (the kernel and the CPU) still has to fit the box. Compared with L01's venv, which isolated only Python packages, the box also carries the operating system's files and libraries.
- **Common misconception.** "A container includes an OS kernel." It includes OS *userland files* (Debian's `/bin`, `/usr`, apt) but not a kernel. That's also why the CPU architecture still matters (§3.7).

### 3.7 CPU architecture and multi-platform images
- **Explanation.** Every program in an image (bash, CPython, uv) is machine code for one instruction set: `linux/amd64` (Intel/AMD, the default GCP E2 machines) or `linux/arm64` (Apple Silicon, GCP's Arm machine series such as T2A and C4A). A plain `docker build` makes an image for the machine it runs on: `arm64` on an M-series Mac. A tag can point at an **index** (manifest list): a menu of per-platform images, and `docker pull` picks the row that matches the host.
  - Captured `docker buildx imagetools inspect python:3.12-slim-bookworm`: an index with `linux/amd64`, `linux/arm/v7`, `linux/arm64/v8`, `linux/386` and `linux/ppc64le`, each with an `unknown/unknown` attestation manifest.
  - `dlops/simple-translate`: a single `application/vnd.docker.distribution.manifest.v2+json`, linux/amd64 only.
  - Your own push, with Docker 29's containerd image store: an `application/vnd.oci.image.index.v1+json` with one real row (your platform) plus an attestation (captured against the local stand-in registry: `Platform: linux/amd64` and `Platform: unknown/unknown`).
  - An image for the wrong CPU fails. Captured the other way round, an arm64 image on an amd64 machine without an emulator: `exec /usr/bin/uname: exec format error`, exit 255 (`laptop-push/12`). If the tag is an index with no amd64 row, the VM can't even pull it: `no matching manifest for linux/amd64 …` (§6 #14).
  - Two fixes in the repo, neither mentioned in the README: build for amd64 with `docker build -t $IMAGE_NAME --platform=linux/amd64 -f Dockerfile .` (commented out at `docker-shell.sh:12`), or build and push both platforms with `docker buildx build --platform linux/amd64,linux/arm64 --push …` (`docker-build-push.sh:27`). The foreign platform is built under emulation, which is slower.
- **Mental model.** A tag is a restaurant menu. The VM orders "amd64". If the menu lists only "arm64", there's nothing to serve.
- **Analogy.** A DVD region code: same movie, same disc format, but the player refuses the wrong region.
- **Common misconception.** "Containers run everywhere." They run on Linux hosts with the *same CPU architecture* (or with an emulator, which Docker Desktop has and a plain Linux VM doesn't).

### 3.8 Who actually provides Python inside this image?
- **Explanation.** The base image ships CPython **3.12** (`FROM python:3.12-slim-bookworm`, `Dockerfile.txt:2`), but `pyproject.toml:6` says `requires-python = ">=3.13"` (changed from `">=3.12,<3.13"` in commit `2827e2a`, 2026-09-02). `RUN uv sync` (`Dockerfile.txt:24`) finds no interpreter in range, so it **downloads** a standalone CPython into `/root/.local/share/uv/python/`, the newest stable release it knows in the range, and builds `/.venv` on it. The base image's 3.12 is used only to run `pip install uv`. Captured on 2026-10-13:
  - the build log: `Downloading cpython-3.15.0-linux-x86_64-gnu (download) (35.9MiB)`, `Using CPython 3.15.0`, `Creating virtual environment at: /.venv`, `Resolved 13 packages`, `Installed 11 packages`;
  - inside the container: `python --version` → `Python 3.15.0`, `/usr/local/bin/python --version` → `Python 3.12.15`; `.venv/pyvenv.cfg` has `uv = 0.13.0`, `version_info = 3.15`, `prompt = app`;
  - the instructor's `dlops/simple-translate`, built 2026-09-16 with uv 0.12.15: `.venv/bin/python -> /root/.local/share/uv/python/cpython-3.14-linux-x86_64-gnu/bin/python3.14`, and `python --version` → `Python 3.14.7`; its base is Python 3.12.14.
  - The exercise checks measured the cost: `112M` under `/root/.local/share/uv/python` against `6.9M` for `/.venv` itself, so most of the 125MB `uv sync` layer is the second Python. With `FROM python:3.13-slim-bookworm`, uv uses the image's own Python, installs 12 packages (`typing-extensions` is needed only below 3.15), and the image drops from 518MB to about 350MB.
- **Mental model.** The `FROM` line *offers* a Python; `pyproject.toml` plus the package manager decide which one runs.
- **Analogy.** L01's Debian 12 VM in a box: there too, uv downloaded a Python because the system's 3.11 was out of range.
- **Common misconception.** "The README says Python 3.12 (`README.md:133`), so the app runs on 3.12." It runs on whatever uv picked at build time: 3.15.0 in a build on 2026-10-13, 3.14.7 in the instructor's image. `ENV UV_PYTHON_DOWNLOADS=never` would make the mismatch fail loudly instead: `error: No interpreter found for Python >=3.13 in managed installations or search path` (exercise B1).

---

## 4. Step-by-step walkthrough

Steps follow the README order. Commands in code spans are verbatim from the README unless marked *(extra)*. The video's trackers number the README bullets A1-A16, B1-B4 and C1-C7; those numbers are given in brackets. Steps 1-16 and the extras after them run in a terminal on your **laptop**, Steps 17-21 on the laptop and on hub.docker.com, Steps 22-28 in the Cloud console and on the **VM**.

**About the outputs below.** They are real, trimmed (first and last lines, with `…` between) from the 2026-10-13 captures in `assets/terminal/` (file names given with each block; `[exit N]` lines omitted, exit codes mentioned where they matter). What differs on your machine:
- The "laptop" was a fresh Docker Engine 29.8.2 on linux/amd64, not Docker Desktop. On Docker Desktop the builder is called `desktop-linux` (the build log says `building with "desktop-linux" instance`, the compact view's right column `docker:desktop-linux`), and Desktop adds a `View build details:` link after each build. On Apple Silicon the image is `linux/arm64` and uv downloads an `aarch64` CPython.
- The recording machine reached the internet through a TLS-intercepting proxy. From Step 9 on, the builds used a copy of `python:3.12-slim-bookworm` with the proxy's certificate added, so their `FROM` lines show the digest `sha256:4fb3e77d…` where yours shows `sha256:34386ef0…` (as in Step 7's real pull), and `docker image ls` / `docker history` show a few extra rows from that copy. Those rows are left out below.
- Build logs are BuildKit's plain view (one line per event), because the commands ran without a terminal. In a terminal you see the compact view of Step 13; add `--progress=plain` to see the plain one.
- Container IDs in prompts (`root@f72851da4a58:/#`) change with every run. Versions (uv, the CPython uv picks, the base image's Python patch release, package versions, Docker) are those of 2026-10-13.
- The "VM" was a fresh `debian:12` / `debian:13` container with a Compute Engine image's baseline. apt prints ` Done` after `Reading package lists...` and the next two lines on a real terminal; without a terminal the capture lost it. The capture also answered apt's `[Y/n]` prompt automatically (`yes | sudo apt install docker.io`); you type `Y`. A VM's apt installs fewer packages than the container's, because a Compute Engine image already has more of them.

### Part 0: before you start

**Step 0. Docker is up; know your CPU.**
- **Action:** start Docker Desktop. *(extra)* `docker run hello-world` (Tutorial 0's check, `README.md:110-111`) and `uname -m`.
- **Checkpoint:** "Hello from Docker!"; `arm64` (Apple Silicon) or `x86_64` (Intel/AMD). The captured stand-in machine (`laptop/00-env.txt`):
  ```
  2026-10-13 01:43 UTC
  Linux x86_64
  Docker client 29.8.2, engine 29.8.2
  github.com/docker/buildx v0.37.2 2d379c0c3f22da0d2759d132a0ec81ca949098f0
  git version 2.54.0
  ```
- **If it fails:** `Cannot connect to the Docker daemon at unix:///…/docker.sock. Is the docker daemon running?` means Docker Desktop isn't started. Open it and wait for the engine.

### Part A: 🐳 Developing App using Containers (`README.md:106-184`)

**Step 1. List running containers** [A1] (`README.md:115`): `docker container ls`
- **Under the hood:** the same as `docker ps`: only *running* containers.
- **Checkpoint:** only the header row (`laptop/01-container-ls.txt`):
  ```
  $ docker container ls
  CONTAINER ID   IMAGE     COMMAND   CREATED   STATUS    PORTS     NAMES
  ```

**Step 2. Stop any container that is running** [A2] (`README.md:116`)
- **Action:** for each row of Step 1, `docker stop <CONTAINER ID>` *(extra)*. The capture had nothing to stop.

**Step 3. Prune** [A3] (`README.md:117`): `docker system prune`
- **Under the hood:** asks first, then deletes stopped containers, unused networks, **dangling** images (untagged ones) and unused build cache. Tagged images survive (add `-a` to remove every image no container uses). Your run may delete the stopped `hello-world` container from Tutorial 0.
- **Checkpoint:** captured (`laptop/02-system-prune.txt`, complete):
  ```
  $ docker system prune
  WARNING! This will remove:
    - all stopped containers
    - all networks not used by at least one container
    - all dangling images
    - unused build cache

  Are you sure you want to continue? [y/N] y
  Total reclaimed space: 0B
  ```

**Step 4. List images** [A4] (`README.md:118`): `docker image ls`
- **Checkpoint:** a table, maybe with `hello-world` (it has a name, so prune kept it). Docker 29's columns (`laptop/03-image-ls.txt`); older Docker versions show `REPOSITORY  TAG  IMAGE ID  CREATED  SIZE`:
  ```
  $ docker image ls
  IMAGE   ID             DISK USAGE   CONTENT SIZE   EXTRA
  ```

**Step 5. Clone on the laptop** [A5] (`README.md:120-125`): "Clone or download from [here]"; the command is the one from `README.md:50`, `git clone https://github.com/dlops-io/simple-translate.git`, then `cd simple-translate`.
- **Why on the laptop:** "If you cloned earlier on a VM, that doesn't help here — Docker Desktop runs on **your laptop**" (`README.md:123`).
- **Checkpoint:** `Cloning into 'simple-translate'...`. *(extra)* `ls -a` and `git log --oneline -1` (`laptop/05-ls.txt`, `06-git-log.txt`):
  ```
  $ ls -a
  .
  ..
  .git
  .gitignore
  .vscode
  Dockerfile.txt
  README.md
  cli.py
  docker-build-push.sh
  docker-shell.sh
  pyproject.toml
  $ git log --oneline -1
  62f821b Handle translation exceptions with detailed error messages
  ```
  No `Dockerfile`, no `uv.lock`, no `.dockerignore`.
- *(extra, instructive)* Run the build command now, before the file exists (`laptop/07-build-no-dockerfile.txt`):
  ```
  $ docker build -t simple-translate -f Dockerfile .
  #0 building with "default" instance using docker driver

  #1 [internal] load build definition from Dockerfile
  #1 transferring dockerfile: 2B done
  #1 DONE 0.0s
  ERROR: failed to build: failed to solve: failed to read dockerfile: open Dockerfile: no such file or directory
  ```
  Exit 1. The same error later means you're in the wrong folder or the file has another name.

**Step 6. Create the file** [A6] (`README.md:127-128`): "Inside the `simple-translate` folder create a file called `Dockerfile`".
- **Action:** in VS Code, a new file named exactly `Dockerfile`: capital D, no extension (an editor such as TextEdit can silently add `.rtf` or `.txt`).
- The README then asks for five steps, with "a Build + Run after each step" (`README.md:130`), using the build command of `README.md:174` and the run command of `README.md:180`.

**Step 7. Dockerfile Step 1: the base image** [A7] (`README.md:132-137`)
```
# Use the official Debian-hosted Python image
FROM python:3.12-slim-bookworm
```
- **Build:** `docker build -t simple-translate -f Dockerfile .`
  - `-t simple-translate` names the result `docker.io/library/simple-translate:latest`; `-f Dockerfile` picks the recipe (it's the default name, so this is explicit rather than needed); the final `.` is the **build context** (§3.2).
- **Checkpoint:** the base image's four layers are downloaded (3.34 MB, 15.97 MB, 28.25 MB, 249 B compressed) and the result is named. Captured (`laptop/09-build-v1.txt`, trimmed):
  ```
  $ docker build -t simple-translate -f Dockerfile .
  #0 building with "default" instance using docker driver
  …
  #2 [internal] load metadata for docker.io/library/python:3.12-slim-bookworm
  #2 DONE 1.4s
  …
  #4 [1/1] FROM docker.io/library/python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258
  …
  #5 naming to docker.io/library/simple-translate:latest done
  …
  #4 sha256:7fd1ebe418b5079d4aa36f416af9b143d127bc75b0155d71cb5fd559b5e04d39 28.25MB / 28.25MB 1.7s done
  #4 sha256:f9d2fb07d6f062d06ddc7aa58191cc5359c728f54af6cebe69a37d2c89e72a0d 249B / 249B 0.5s done
  #4 DONE 1.8s
  …
  #5 unpacking to docker.io/library/simple-translate:latest 4.8s done
  #5 DONE 4.9s
  ```
- *(extra)* What will it start? Read the config:
  ```
  $ docker image inspect simple-translate --format 'Entrypoint={{json .Config.Entrypoint}} Cmd={{json .Config.Cmd}} WorkingDir={{json .Config.WorkingDir}}'
  Entrypoint=null Cmd=["python3"] WorkingDir=""
  ```
  The command `python3` is inherited from the base image, and there's no working directory (`laptop/10-config-v1.txt`).
- **Run:** `docker run --rm -ti simple-translate` (`laptop/11-run-v1.txt`):
  ```
  $ docker run --rm -ti simple-translate
  Python 3.12.15 (main, Oct  6 2026, 02:02:31) [GCC 12.2.0] on linux
  Type "help", "copyright", "credits" or "license" for more information.
  >>> exit()
  ```
  A Python REPL; leave with `exit()` or Ctrl-D. The patch version depends on when the base image was pulled.
- *(extra)* `git status` says `nothing to commit, working tree clean` although you just made a file: `.gitignore` line 3 is `Dockerfile` (`laptop/12-git-status.txt`). To commit yours anyway: `git add -f Dockerfile`.

**Step 8. Dockerfile Step 2: the entrypoint** [A8] (`README.md:139-143`)
```
ENTRYPOINT ["/bin/bash"]
```
- **Build:** the same command. Only `FROM` is a step, and it says `CACHED`; no layer is added, only the config changes (`laptop/14-build-v2.txt`: `#4 CACHED`).
- *(extra)* The config now (`laptop/15-config-v2.txt`):
  ```
  $ docker image inspect simple-translate --format 'Entrypoint={{json .Config.Entrypoint}} Cmd={{json .Config.Cmd}}'
  Entrypoint=["/bin/bash"] Cmd=null
  ```
  Setting `ENTRYPOINT` cleared the inherited `CMD ["python3"]`, so bash starts with no arguments (§3.4).
- **Run** (`laptop/16-run-v2.txt`):
  ```
  $ docker run --rm -ti simple-translate
  root@f72851da4a58:/# exit
  exit
  ```
  Read the prompt: `root` (the container runs as root), `@f72851da4a58` (the container's ID), `/` (no working directory, so the top folder).

**Step 9. Dockerfile Step 3: install uv and copy the code** [A9] (`README.md:145-152`)
```
# Install uv
RUN pip install uv
# Copy the source code
COPY . ./
```
- **Under the hood:** `RUN` runs in a temporary container and saves the change as a layer. `COPY . ./` copies the whole context, `.git/` and your `Dockerfile` included, into `/`.
- **Build** (`laptop/18-build-v3.txt`, trimmed):
  ```
  $ docker build -t simple-translate -f Dockerfile .
  …
  #3 [internal] load .dockerignore
  #3 transferring context: 2B done
  …
  #4 [internal] load build context
  #4 transferring context: 63.12kB 0.0s done
  …
  #6 [2/3] RUN pip install uv
  #6 2.981 Collecting uv
  #6 3.588 Downloading uv-0.13.0-py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (17.9 MB)
  …
  #6 4.908 Successfully installed uv-0.13.0
  #6 4.908 WARNING: Running pip as the 'root' user can result in broken permissions and conflicting behaviour …
  #6 5.305 [notice] A new release of pip is available: 25.0.1 -> 26.2.1
  …
  #7 [3/3] COPY . ./
  #7 DONE 0.1s
  …
  #8 naming to docker.io/library/simple-translate:latest done
  ```
  `transferring context: 2B` for `.dockerignore` means there is none; the whole folder (63 kB here, mostly `.git`) travels to the builder. The root-user warning matters on a shared machine (L01); inside an image, the image itself is the isolation.
- **Run**, then *(extra)* `ls` and `python cli.py` at the container prompt (`laptop/19-run-v3.txt`):
  ```
  $ docker run --rm -ti simple-translate
  root@1f2c7df8735d:/# ls
  Dockerfile      cli.py                home   opt             sbin  var
  Dockerfile.txt  dev                   lib    proc            srv
  README.md       docker-build-push.sh  lib64  pyproject.toml  sys
  bin             docker-shell.sh       media  root            tmp
  boot            etc                   mnt    run             usr
  root@1f2c7df8735d:/# python cli.py
  Traceback (most recent call last):
    File "//cli.py", line 8, in <module>
      from art import text2art
  ModuleNotFoundError: No module named 'art'
  root@1f2c7df8735d:/# exit
  exit
  ```
  The repo's files sit next to the system's folders. uv is installed, but the app's packages aren't: you installed the installer.

**Step 10. Dockerfile Step 4: the venv** [A10] (`README.md:154-158`)
```
RUN uv sync
```
- **Under the hood:** uv reads `pyproject.toml`, finds no interpreter `>=3.13` in the image, downloads a standalone CPython, creates `/.venv`, resolves the dependencies into a new `/uv.lock` and installs them (§3.8).
- **Build** (`laptop/21-build-v4.txt`, trimmed):
  ```
  $ docker build -t simple-translate -f Dockerfile .
  …
  #6 [2/4] RUN pip install uv
  #6 CACHED

  #7 [3/4] COPY . ./
  #7 DONE 0.1s

  #8 [4/4] RUN uv sync
  #8 0.820 Downloading cpython-3.15.0-linux-x86_64-gnu (download) (35.9MiB)
  #8 3.461  Downloaded cpython-3.15.0-linux-x86_64-gnu (download)
  #8 3.842 Using CPython 3.15.0
  #8 3.842 Creating virtual environment at: /.venv
  #8 4.856 Resolved 13 packages in 1.01s
  #8 5.265 Prepared 11 packages in 400ms
  #8 5.283 Installed 11 packages in 22ms
  #8 5.283  + anyio==4.15.1
  #8 5.283  + art==6.5
  …
  #8 5.283  + httpx==0.28.1
  #8 5.283  + hyperframe==6.1.0
  #8 5.283  + idna==3.20
  #8 DONE 5.4s
  ```
  Look at `[3/4] COPY . ./`: it says `DONE`, not `CACHED`, although you only appended a line. Your `Dockerfile` is in the build context, so editing it changed what `COPY` copies (§3.3).
- **Run**, then *(extra)* `ls -a`, `python cli.py`, `.venv/bin/python --version`, `source .venv/bin/activate && python cli.py` (`laptop/22-run-v4.txt`, trimmed):
  ```
  $ docker run --rm -ti simple-translate
  root@01dca6d0f4d8:/# ls -a
  .           Dockerfile      docker-build-push.sh  mnt             srv
  ..          Dockerfile.txt  docker-shell.sh       opt             sys
  .dockerenv  README.md       etc                   proc            tmp
  .git        bin             home                  pyproject.toml  usr
  .gitignore  boot            lib                   root            uv.lock
  .venv       cli.py          lib64                 run             var
  .vscode     dev             media                 sbin
  root@01dca6d0f4d8:/# python cli.py
  Traceback (most recent call last):
    File "//cli.py", line 8, in <module>
      from art import text2art
  ModuleNotFoundError: No module named 'art'
  root@01dca6d0f4d8:/# .venv/bin/python --version
  Python 3.15.0
  root@01dca6d0f4d8:/# source .venv/bin/activate && python cli.py
  …
  Arguments: Namespace(text='I love cheese', file='', src='en', dest='it')

  Input: I love cheese
  Output: Adoro il formaggio
  (app) root@01dca6d0f4d8:/# exit
  exit
  ```
  `.venv` and `uv.lock` are new, but plain `python cli.py` still fails: nothing activated the venv, so `python` is the base image's `/usr/local/bin/python` (3.12), which has none of the packages. Activation is just `PATH` (L01): after `source`, it works and the prompt gains `(app)`.

**Step 11. Dockerfile Step 5: start inside the venv** [A11] (`README.md:160-165`)
```
# Get into the uv virtual environment shell
CMD ["-c", "source .venv/bin/activate && exec bash"]
```
- **Build:** `COPY . ./` and `uv sync` run again, with the 35.9 MiB CPython download, for one added line (`laptop/24-build-v5.txt`). *(extra)* The config (`laptop/25-config-v5.txt`):
  ```
  $ docker image inspect simple-translate --format 'Entrypoint={{json .Config.Entrypoint}} Cmd={{json .Config.Cmd}}'
  Entrypoint=["/bin/bash"] Cmd=["-c","source .venv/bin/activate && exec bash"]
  ```
- **Run**, then *(extra)* `which python`, `python --version`, `echo $VIRTUAL_ENV` (`laptop/26-run-v5.txt`):
  ```
  $ docker run --rm -ti simple-translate
  root@473b6edd3dab:/# which python
  /.venv/bin/python
  root@473b6edd3dab:/# python --version
  Python 3.15.0
  root@473b6edd3dab:/# echo $VIRTUAL_ENV
  /.venv
  root@473b6edd3dab:/# exit
  exit
  ```
  The venv is active although the prompt shows no `(app)`: the activate script does set the prefix, but the interactive bash started by `exec bash` reads Debian's `/etc/bash.bashrc`, which sets the prompt again.

**Step 12. Compare with the solution** [A12] (`README.md:167-168`): "**Solution Dockerfile:** `Dockerfile.txt`"
- *(extra)* `diff Dockerfile Dockerfile.txt` (`laptop/27-diff-solution.txt`, trimmed; BusyBox `diff` prints the unified form, add `-u` to yours):
  ```
  $ diff Dockerfile Dockerfile.txt
  --- Dockerfile
  +++ Dockerfile.txt
  @@ -1,14 +1,29 @@
   # Use the official Debian-hosted Python image
   FROM python:3.12-slim-bookworm

  -ENTRYPOINT ["/bin/bash"]
  +# Prevent apt from showing prompts
  +ENV DEBIAN_FRONTEND=noninteractive
  …
  +# Ensure we have an up to date baseline, install dependencies and
  +RUN set -ex; \
  +    apt-get update && \
  +    apt-get upgrade -y && \
  +    apt-get clean && \
  +    pip install --no-cache-dir --upgrade pip && \
  +    pip install uv
  +
   # Copy the source code
   COPY . ./

   RUN uv sync

  +# Entry point
  +ENTRYPOINT ["/bin/bash"]
   # Get into the uv virtual environment shell
  -CMD ["-c", "source .venv/bin/activate && exec bash"]
  +CMD ["-c", "source .venv/bin/activate && exec bash"]
  \ No newline at end of file
  ```
  The solution adds three `ENV` lines (no apt prompts, a UTF-8 locale, unbuffered output), folds your `pip install uv` into one bigger `RUN` that also updates and upgrades Debian's packages and pip, and moves `ENTRYPOINT` to the end (its position doesn't matter). The last two lines differ only in the missing final newline.
- *(extra)* `cp Dockerfile.txt Dockerfile` (no output): the README only names the file; the rest of this guide uses the solution.

**Step 13. Build the image** [A13] (`README.md:170-174`): `docker build -t simple-translate -f Dockerfile .`
- **Checkpoint:** in a terminal, the compact view (`laptop/29-build.txt`, trimmed):
  ```
  $ docker build -t simple-translate -f Dockerfile .

  [+] Building 28.1s (9/9) FINISHED                                                    docker:default
   => [internal] load build definition from Dockerfile                                           0.0s
   …
   => [2/4] RUN set -ex;     apt-get update &&     apt-get upgrade -y &&     apt-get clean &&   13.3s
   => [3/4] COPY . ./                                                                            0.0s
   => [4/4] RUN uv sync                                                                          4.9s
   => exporting to image                                                                         9.7s
   …
   => => naming to docker.io/library/simple-translate:latest                                     0.0s
   => => unpacking to docker.io/library/simple-translate:latest                                  2.8s
  ```
  The plain log of the same build (`laptop-push/capture-only/build.txt`) shows `apt-get upgrade` finding `0 upgraded` on a 7-day-old base, `Successfully installed pip-26.2.1`, `Successfully installed uv-0.13.0`, `Using CPython 3.15.0` and `Installed 11 packages`.
- *(extra)* `docker image ls` (`laptop/30-image-ls.txt`, the stand-in base row left out):
  ```
  $ docker image ls
  IMAGE                       ID             DISK USAGE   CONTENT SIZE   EXTRA
  simple-translate:latest     73e9ab822b0b        518MB          144MB
  ```
  With Docker 29's containerd image store, *content size* is the compressed layers (what travels to a registry) and *disk usage* adds the unpacked copy (about 374 MB). Older Docker versions show one `SIZE` column with the unpacked size. An arm64 build on a Mac differs a little.

**Step 14-16. Run, translate, exit** [A14-A16] (`README.md:176-184`): `docker run --rm -ti simple-translate`, then `python cli.py -t "Good morning" -s "en" -d "es"`, then type `exit`.
- **Checkpoint** (`laptop/31-run.txt`, complete):
  ```
  $ docker run --rm -ti simple-translate
  root@93d61f44d3d7:/# python cli.py -t "Good morning" -s "en" -d "es"


      _      ____  ____   _  ____
     / \    / ___||___ \ / || ___|
    / _ \  | |      __) || ||___ \
   / ___ \ | |___  / __/ | | ___) |
  /_/   \_\ \____||_____||_||____/



  Arguments: Namespace(text='Good morning', file='', src='en', dest='es')

  Input: Good morning
  Output: Buen día
  root@93d61f44d3d7:/# exit
  exit
  ```
  The banner (`cli.py:13-14`) proves `art` imported, i.e. the venv is active; `Arguments:` prints the parsed `Namespace` (`cli.py:15`); the translation goes from the container, through your laptop's network, to Google (`cli.py:25-39`). Google's wording can change.
- **Under the hood of `exit`:** bash, the container's main process, ends; the container stops; `--rm` deletes it. *(extra)* `docker ps -a` lists every container, stopped ones too: only the header (`laptop/32-ps-a.txt`). The image is untouched.
- **If it fails:** a traceback ending in `RuntimeError: Translation request to Google Translate failed (the server's network/IP may be rate-limited or blocked by Google's unofficial translate endpoint).` comes from `cli.py:32-37`: Google refused or couldn't be reached. Scroll up to the first exception for the cause; retry later or from another network. Your Docker setup is fine.

### Part A+ (extra): inside the image, the start-up command and the cache

None of these are README steps; they make §3 visible. Run them before you push.

**Step A+1. The layers** *(extra)*: `docker history simple-translate` (`laptop/34-history.txt`; the three stand-in rows from the proxy certificate left out, middle base rows trimmed):
```
$ docker history simple-translate
IMAGE          CREATED              CREATED BY                                      SIZE      COMMENT
73e9ab822b0b   19 seconds ago       CMD ["-c" "source .venv/bin/activate && exec…   0B        buildkit.dockerfile.v0
<missing>      19 seconds ago       ENTRYPOINT ["/bin/bash"]                        0B        buildkit.dockerfile.v0
<missing>      19 seconds ago       RUN /bin/sh -c uv sync # buildkit               125MB     buildkit.dockerfile.v0
<missing>      24 seconds ago       COPY . ./ # buildkit                            250kB     buildkit.dockerfile.v0
<missing>      24 seconds ago       RUN /bin/sh -c set -ex;     apt-get update &…   97.5MB    buildkit.dockerfile.v0
<missing>      24 seconds ago       ENV PYTHONUNBUFFERED=1                          0B        buildkit.dockerfile.v0
<missing>      24 seconds ago       ENV LANG=C.UTF-8                                0B        buildkit.dockerfile.v0
<missing>      24 seconds ago       ENV DEBIAN_FRONTEND=noninteractive              0B        buildkit.dockerfile.v0
…
<missing>      7 days ago           CMD ["python3"]                                 0B        buildkit.dockerfile.v0
…
<missing>      7 days ago           ENV PYTHON_VERSION=3.12.15                      0B        buildkit.dockerfile.v0
…
<missing>      8 days ago           # debian.sh --arch 'amd64' out/ 'bookworm' '…   85.3MB    debuerreotype 0.17
```
Read bottom-up, it's the Dockerfile top-down: three layers of yours, `0B` for config-only lines, then the base image's own rows down to Debian bookworm.

**Step A+2. Look around inside** *(extra)*: `docker run --rm -ti simple-translate`, then `pwd`, `echo $$`, `which python`, `python --version`, `/usr/local/bin/python --version`, `ls /root/.local/share/uv/python`, `cat .venv/pyvenv.cfg` (`laptop/33-inside.txt`, trimmed):
```
root@1d1fecf6ff8f:/# pwd
/
root@1d1fecf6ff8f:/# echo $$
1
root@1d1fecf6ff8f:/# which python
/.venv/bin/python
root@1d1fecf6ff8f:/# python --version
Python 3.15.0
root@1d1fecf6ff8f:/# /usr/local/bin/python --version
Python 3.12.15
root@1d1fecf6ff8f:/# ls /root/.local/share/uv/python
cpython-3.15-linux-x86_64-gnu  cpython-3.15.0-linux-x86_64-gnu
root@1d1fecf6ff8f:/# cat .venv/pyvenv.cfg
home = /root/.local/share/uv/python/cpython-3.15-linux-x86_64-gnu/bin
implementation = CPython
uv = 0.13.0
version_info = 3.15
include-system-site-packages = false
prompt = app
```
Two Pythons in one image (§3.8), bash as process 1, and `/` as the working directory. `ls -a /` in the same session lists the same build context as Step 10, `.git` included.

**Step A+3. The platform** *(extra)* (`laptop/35-platform.txt`):
```
$ uname -m; docker image inspect simple-translate --format '{{.Os}}/{{.Architecture}}'
x86_64
linux/amd64
```
On Apple Silicon: `arm64` and `linux/arm64` (§3.7).

**Step A+4. Arguments after the image name** *(extra)*. Predict first, then (`laptop/36-run-args.txt`, `laptop/37-run-c.txt`):
```
$ docker run --rm -ti simple-translate python cli.py
/usr/local/bin/python: /usr/local/bin/python: cannot execute binary file
```
Exit 126: the container ran `/bin/bash python cli.py` (§3.4). Replace CMD with a whole `-c` string instead:
```
$ docker run --rm simple-translate -c "source .venv/bin/activate && python cli.py -d fr"
…
Arguments: Namespace(text='I love cheese', file='', src='en', dest='fr')

Input: I love cheese
Output: j'adore le fromage
```
Another working form, not captured but checked in the exercise checks: `docker run --rm --entrypoint /.venv/bin/python simple-translate cli.py -d fr` replaces bash itself.

**Step A+5. The cache** *(extra)*. Rebuild with nothing changed, then after an edit, then after undoing it, each time with `docker build --progress=plain -t simple-translate -f Dockerfile .`:
- Nothing changed (`laptop/38-rebuild-same.txt`): `#6 [2/4] RUN set -ex; …` → `CACHED`, `#7 [3/4] COPY . ./` → `CACHED`, `#8 [4/4] RUN uv sync` → `CACHED`; `DONE 0.1s`.
- Change the default text on line 49 of `cli.py` (`laptop/39-edit-cli.txt`):
  ```
  $ git diff
  …
  @@ -46,7 +46,7 @@ if __name__ == "__main__":
           "-t",
           "--text",
           type=str,
  -        default="I love cheese",
  +        default="I love brie",
           help="Text to translate",
       )
  ```
  and rebuild (`laptop/40-rebuild-edited.txt`, trimmed):
  ```
  #6 [2/4] RUN set -ex;     apt-get update &&     apt-get upgrade -y &&     apt-get clean &&     pip install --no-cache-dir --upgrade pip &&     pip install uv
  #6 CACHED

  #7 [3/4] COPY . ./
  #7 DONE 0.0s

  #8 [4/4] RUN uv sync
  #8 0.874 Downloading cpython-3.15.0-linux-x86_64-gnu (download) (35.9MiB)
  …
  #8 4.181 Installed 11 packages in 5ms
  ```
- `git checkout cli.py` and rebuild (`laptop/41-rebuild-restored.txt`): `COPY . ./` → `DONE` and `uv sync` downloads CPython again. The files are as before, but git rewrote `.git/index`, which the context contains.
- The fix for your own projects (exercise Q4/B3): copy only `pyproject.toml` and `README.md`, `RUN uv sync`, then `COPY . ./`, plus a `.dockerignore` listing `.git`, `.venv`, `secrets/` and `Dockerfile`. Checked the same day: after editing `cli.py`, only the last `COPY` ran.

**Step A+6. The repo's helper** *(extra; not mentioned in the README)*: `sh docker-shell.sh` builds (`docker-shell.sh:11`) and runs (`docker-shell.sh:15`, with `--name simple-translate`) in one go. Captured (`laptop/42-docker-shell.txt`, trimmed): `[+] Building 0.2s (9/9) FINISHED`, `CACHED [2/4]`, `CACHED [3/4] COPY . ./`, `CACHED [4/4] RUN uv sync`, then `root@cbd2b3516e5f:/#`.

### Part B: 📤 Pushing Docker Image to Docker Hub (`README.md:186-191`)

The captures had no Docker Hub account. The real push to Docker Hub was run and refused; the login and the pushes that succeed went to a throwaway local registry (`registry:3` on `localhost:5000`) standing in for Docker Hub, so their names start with `localhost:5000/`. Don't type those; use the README's names.

**Step 17. Create an access token** [B1] (`README.md:188`): "Sign up in Docker Hub and create an [Access Token](https://hub.docker.com/settings/security)"
- **Action:** in your Docker Hub account settings, create a personal access token with **write** access (a read-only token can't push). Copy it right away: it is shown once, and it works like a password.

**Step 18. Log in** [B2] (`README.md:189`): `docker login -u <USER NAME> -p <ACCESS TOKEN>`
- **Under the hood:** the CLI checks the credential with the registry and stores it for later pushes and pulls.
- **Checkpoint:** `Login Succeeded`. Captured against the stand-in, same form with a placeholder password (`laptop-push/05-login-local.txt`):
  ```
  $ docker login localhost:5000 -u student -p not-a-real-token
  WARNING! Using --password via the CLI is insecure. Use --password-stdin.

  WARNING! Your credentials are stored unencrypted in '/home/student/.docker/config.json'.
  Configure a credential helper to remove this warning. See
  https://docs.docker.com/go/credential-store/

  Login Succeeded
  ```
  The first warning is about the README's `-p`: the token ends up in your shell history. Use `docker login -u <USER NAME>` and paste the token at the `Password:` prompt instead (or pipe it to `--password-stdin`). The second warning doesn't appear on Docker Desktop, which stores the token with a credential helper (on a Mac, the macOS keychain).

**Step 19. Tag** [B3] (`README.md:190`): `docker tag simple-translate <USER NAME>/simple-translate-ac215`
- **Under the hood:** adds a second **name** to the same image: no copy, no rebuild. The full name is `docker.io/<USER NAME>/simple-translate-ac215:latest`: registry (Docker Hub is the default), account, repository, tag. A name without an account, like `simple-translate`, belongs to `library`, the official images' namespace.
- **Checkpoint:** no output. *(extra)* `docker image ls` (`laptop/44-image-ls-tagged.txt`, `<USER NAME>` = `student`, the stand-in base row left out):
  ```
  $ docker image ls
  IMAGE                                   ID             DISK USAGE   CONTENT SIZE   EXTRA
  simple-translate:latest                 b5c531a6b555        518MB          144MB
  student/simple-translate-ac215:latest   b5c531a6b555        518MB          144MB
  ```
  Two names, one ID.

**Step 20. Push** [B4] (`README.md:191`): `docker push <USER NAME>/simple-translate-ac215`
- **Under the hood:** uploads only the layers the registry doesn't have yet, then the manifest; the last line names the image's digest.
- **Without a login** (or with a name that isn't yours), captured against the real Docker Hub (`laptop-push/03-push-no-login.txt`):
  ```
  $ docker push student/simple-translate-ac215
  Using default tag: latest
  The push refers to repository [docker.io/student/simple-translate-ac215]
  6e0ba8ba0487: Waiting
  cef1a1b4c9a2: Waiting
  44136fa355b3: Waiting
  7fd1ebe418b5: Waiting
  push access denied, repository does not exist or may require authorization: server message: insufficient_scope: authorization failed
  ```
  Exit 1. Log in, check that the name starts with **your** username, and that your token can write.
- **Logged in**, captured against the stand-in (`laptop-push/07-push-local.txt`, trimmed):
  ```
  $ docker push localhost:5000/student/simple-translate-ac215
  Using default tag: latest
  The push refers to repository [localhost:5000/student/simple-translate-ac215]
  cef1a1b4c9a2: Pushed
  7fd1ebe418b5: Pushed
  …
  e89227199569: Pushed
  latest: digest: sha256:2c302ec4c53645e102eaf2fcbd80f8838737a5b7325971c58eb28bff279a0b85 size: 856
  ```
  A second push of the same image (`laptop-push/08-push-local-again.txt`) prints `Layer already exists` for every layer and the same digest: only missing layers travel. On Docker Hub, the base image's layers may instead show `Mounted from library/python`, because Docker Hub already has them (not captured: no account).
- **Checkpoint:** the repository appears under your account on hub.docker.com, **public** by default.
- *(extra)* What did you push? (`laptop-push/09-imagetools-local.txt`, trimmed):
  ```
  $ docker buildx imagetools inspect localhost:5000/student/simple-translate-ac215
  Name:      localhost:5000/student/simple-translate-ac215:latest
  MediaType: application/vnd.oci.image.index.v1+json
  Digest:    sha256:2c302ec4c53645e102eaf2fcbd80f8838737a5b7325971c58eb28bff279a0b85
  …
    MediaType:   application/vnd.oci.image.manifest.v1+json
    Platform:    linux/amd64
  …
    MediaType:   application/vnd.oci.image.manifest.v1+json
    Platform:    unknown/unknown
  …
      vnd.docker.reference.type:   attestation-manifest
  ```
  An index with one real platform plus an attestation (a record of how the image was built). For yours: `docker buildx imagetools inspect <USER NAME>/simple-translate-ac215`.
- *(extra)* The instructor's image and the base image, for comparison (`laptop-push/10-imagetools-dlops.txt`, complete; `11-imagetools-python.txt`, platform lines only):
  ```
  $ docker buildx imagetools inspect dlops/simple-translate
  Name:      docker.io/dlops/simple-translate:latest
  MediaType: application/vnd.docker.distribution.manifest.v2+json
  Digest:    sha256:2454010bcf64b211d81805c38ae3dfc7842bff6fed558bb3bb6dc7659a63f916
  $ docker buildx imagetools inspect python:3.12-slim-bookworm
  …
    Platform:    linux/amd64
    Platform:    unknown/unknown
    Platform:    linux/arm/v7
    Platform:    unknown/unknown
    Platform:    linux/arm64/v8
    Platform:    unknown/unknown
    Platform:    linux/386
    Platform:    unknown/unknown
    Platform:    linux/ppc64le
    Platform:    unknown/unknown
  ```
  `dlops/simple-translate` is a single image (amd64, `vm-debian12/08`), not a menu; `python:3.12-slim-bookworm` is a menu of five platforms.

**Step 21. Apple Silicon only: publish an image the VM can run** *(extra, not in the README)*
- **Why:** a plain build on an M-series Mac is `linux/arm64`; a default E2 VM is amd64 and has no emulator (§3.7). The failure, captured the other way round on an amd64 machine (`laptop-push/12-arm64-on-amd64.txt`):
  ```
  $ docker run --rm --platform linux/arm64 debian:12 uname -m
  Unable to find image 'debian:12' locally
  12: Pulling from library/debian
  …
  Status: Downloaded newer image for debian:12
  exec /usr/bin/uname: exec format error
  ```
  Exit 255. Docker Desktop on a Mac has an emulator built in, so this exact command would work there.
- **Fix 1:** `docker build -t simple-translate --platform=linux/amd64 -f Dockerfile .` (the commented-out `docker-shell.sh:12`; slower, because it runs emulated), then the README's `docker tag` and `docker push` again.
- **Fix 2:** in `docker-build-push.sh`, set `IMAGE_NAME="simple-translate-ac215"` (line 7) and your username in `DOCKER_USERNAME` (line 11), log in, and run `bash docker-build-push.sh` (the file isn't executable). It creates a buildx builder `multi-arch` (line 23) and builds and pushes `linux/amd64` + `linux/arm64` under one tag (line 27). Afterwards `docker buildx use default` (`desktop-linux` on Docker Desktop; `docker buildx ls` marks the current builder with `*`), or later plain builds won't land in your image list (§6 #16).
- **Checkpoint:** `docker buildx imagetools inspect <USER NAME>/simple-translate-ac215` lists `Platform: linux/amd64`.

### Part C: ☁️ Running App on VM using Docker (`README.md:203-220`)

**Step 22. Create a VM** [C1] (`README.md:207`): "Create a VM Instance from [GCP](https://console.cloud.google.com/compute/instances)"
- **Action:** *Create instance*, as in L01. The README gives no settings. Sensible ones: name `ac215-l02`, zone us-central1-a, machine type e2-small (E2 machines are amd64), boot disk Debian 12 or 13, external IPv4 on (the default). Avoid the Arm series (T2A, C4A) unless your image is multi-platform.
- *(extra)* CLI alternative from your laptop: `gcloud compute instances create ac215-l02 --zone=us-central1-a --machine-type=e2-small --image-family=debian-12 --image-project=debian-cloud`
- **Cost:** from now on the VM bills per second while it runs, and its disk while it exists.

**Step 23. SSH in** [C2] (`README.md:208`): "SSH into your newly created instance"
- **Action:** the **SSH** button in the instance row (or *(extra)* `gcloud compute ssh ac215-l02 --zone=us-central1-a`).
- *(extra)* What's here (`vm-debian12/00-os.txt`): `PRETTY_NAME="Debian GNU/Linux 12 (bookworm)"`, `x86_64`, and `which docker` finds nothing. Debian 13 prints `13 (trixie)`.

**Step 24. Install Docker** [C3] (`README.md:209-210`): `sudo apt install docker.io`
- **Under the hood:** Debian's packaged Docker engine (`dockerd`, `containerd`, `runc`), which apt also starts as a service.
- **As written, on a fresh image it can fail.** Captured with empty package lists (`vm-debian12/01-apt-install-docker.txt`):
  ```
  $ sudo apt install docker.io
  Reading package lists...
  Building dependency tree...
  Reading state information...
  E: Unable to locate package docker.io
  E: Couldn't find any package by glob 'docker.io'
  ```
  Exit 100 (Debian 13: `Error: Unable to locate package docker.io`). The README skips the `sudo apt-get update` it used in L01 (`README.md:44`, `:74`). A Compute Engine image may ship package lists from its build date, so on your VM the command may work, fail like this, or fail with `404 Not Found` on stale lists.
- *(extra)* **Fix:** `sudo apt-get update` (`vm-debian12/02-apt-update.txt`, trimmed):
  ```
  $ sudo apt-get update
  Get:1 https://deb.debian.org/debian bookworm InRelease [151 kB]
  …
  Fetched 9388 kB in 2s (4549 kB/s)
  Reading package lists...
  ```
  then `sudo apt install docker.io` again and answer `Y` (`vm-debian12/03-apt-install-docker.txt`, trimmed):
  ```
  $ sudo apt install docker.io
  Reading package lists...
  Building dependency tree...
  Reading state information...
  The following additional packages will be installed:
    apparmor binutils binutils-common binutils-x86-64-linux-gnu cgroupfs-mount
  …
  1 upgraded, 92 newly installed, 0 to remove and 0 not upgraded.
  Need to get 107 MB of archives.
  After this operation, 452 MB of additional disk space will be used.
  Do you want to continue? [Y/n]
  …
  Setting up docker.io (20.10.24+dfsg1-1+deb12u1+b6) ...
  Adding group `docker' (GID 103) ...
  Done.
  …
  Processing triggers for libc-bin (2.36-9+deb12u14) ...
  ```
  Debian 13's apt prints a summary instead (`vm-debian13/03-apt-install-docker.txt`): `Upgrading: 1, Installing: 91, Removing: 0, Not Upgrading: 0`, `Download size: 118 MB`, `Space needed: 499 MB / 12.4 GB available`, `Continue? [Y/n]`, and later `Setting up docker.io (26.1.5+dfsg1-9+deb13u1) ...`. On a real VM, systemd starts the Docker service right away. The stand-in container has no systemd, so its log also has `invoke-rc.d: policy-rc.d denied execution of start.` lines, which a VM doesn't print, and its daemon was started by hand.

**Step 25. Check the version** [C4] (`README.md:212-213`): `sudo docker --version`
- **Checkpoint** (`vm-debian12/04-docker-version.txt`, `vm-debian13/04-docker-version.txt`):
  ```
  $ sudo docker --version
  Docker version 20.10.24+dfsg1, build 297e128
  ```
  On Debian 13: `Docker version 26.1.5+dfsg1, build a72d7cd`. Older than Docker Desktop's, and enough for this lecture.
- *(extra)* Why `sudo`? (`vm-debian12/05-docker-no-sudo.txt`):
  ```
  $ docker ps
  permission denied while trying to connect to the Docker daemon socket at unix:///var/run/docker.sock: Get "http://%2Fvar%2Frun%2Fdocker.sock/v1.24/containers/json": dial unix /var/run/docker.sock: connect: permission denied
  ```
  The socket belongs to root and the group `docker` (apt created it above), and your user is in neither. `sudo usermod -aG docker $USER` plus a new SSH session would also work (exercise C6).

**Step 26. Pull and run the image** [C5] (`README.md:214-215`): `sudo docker run --rm -ti dlops/simple-translate`
- **Under the hood:** the image isn't on the VM, so `docker run` pulls it from Docker Hub (seven layers, linux/amd64), then starts `/bin/bash -c "source .venv/bin/activate && exec bash"`. Docker runs directly on the VM's Linux kernel: no hidden VM here.
- **Checkpoint** (`vm-debian12/06-docker-run.txt`, first part):
  ```
  $ sudo docker run --rm -ti dlops/simple-translate
  Unable to find image 'dlops/simple-translate:latest' locally
  latest: Pulling from dlops/simple-translate
  a8ac7f6c67ab: Pull complete
  …
  c09a3265feca: Pull complete
  Digest: sha256:2454010bcf64b211d81805c38ae3dfc7842bff6fed558bb3bb6dc7659a63f916
  Status: Downloaded newer image for dlops/simple-translate:latest
  root@c7c280390994:/#
  ```
- **If it fails:** Docker Hub limits anonymous pulls per network address, and a classroom sharing one address can hit it. Captured on an earlier attempt (`vm-debian13/06-docker-run-rate-limited.txt`):
  ```
  $ sudo docker run --rm -ti dlops/simple-translate
  Unable to find image 'dlops/simple-translate:latest' locally
  docker: Error response from daemon: toomanyrequests: You have reached your unauthenticated pull rate limit. https://www.docker.com/increase-rate-limit.
  See 'docker run --help'.
  ```
  Exit 125. Wait a while, or log in first (`sudo docker login -u <USER NAME>`).
- **Your own image instead** *(extra)*: the README says "pull the image you pushed in step 3" (`README.md:205`) but runs the instructor's. Yours: `sudo docker run --rm -ti <USER NAME>/simple-translate-ac215`, which works on this VM only if it contains `linux/amd64` (Step 21).

**Step 27. Run the app** [C6] (`README.md:217-218`): `python cli.py`
- **Checkpoint** (`vm-debian12/06-docker-run.txt`, rest; the `python --version` line is an extra):
  ```
  root@c7c280390994:/# python cli.py
  …
  Arguments: Namespace(text='I love cheese', file='', src='en', dest='it')

  Input: I love cheese
  Output: Adoro il formaggio
  root@c7c280390994:/# python --version
  Python 3.14.7
  root@c7c280390994:/# exit
  exit
  ```
  The defaults come from `cli.py:49` (`I love cheese`), `:62` (`en`) and `:68` (`it`). No clone, no pip, no uv on this VM: Docker and one image.
- *(extra)* Facts about the published image (`vm-debian12/07`-`10`):
  ```
  $ sudo docker images
  REPOSITORY               TAG       IMAGE ID       CREATED       SIZE
  dlops/simple-translate   latest    8a968f7e6f7a   3 weeks ago   347MB
  $ uname -m; sudo docker image inspect dlops/simple-translate --format '{{.Os}}/{{.Architecture}} created {{.Created}}'
  x86_64
  linux/amd64 created 2026-09-16T21:28:58.17041481-04:00
  $ sudo docker run --rm dlops/simple-translate -c 'wc -c cli.py; grep -n Translator cli.py; ls -l .venv/bin/python; cat .venv/pyvenv.cfg'
  1266 cli.py
  9:from googletrans import Translator
  25:    async with Translator() as translator:
  lrwxrwxrwx 1 root root 73 Sep 17 01:28 .venv/bin/python -> /root/.local/share/uv/python/cpython-3.14-linux-x86_64-gnu/bin/python3.14
  …
  uv = 0.12.15
  version_info = 3.14
  …
  ```
  Its `docker history` (`vm-debian12/09-history.txt`, as Docker 20.10 counts): `uv sync` 114MB, `COPY . ./` 209kB, `RUN set -ex; apt-get …` 108MB, base `PYTHON_VERSION=3.12.14`. Two things to notice: it was built on 2026-09-16 with uv 0.12.15, which picked CPython 3.14.7 (your build: 3.15.0); and its `cli.py` (1266 bytes, `Translator()` without `raise_exception=True`) is older than the repo's. If Google refuses a request, this version prints your input back as the "translation" instead of raising an error (§6 #20).

**Step 28. Leave and delete the VM** [C7] (`README.md:220`): "Delete your VM when you're done. A running VM keeps charging even when idle. Go to [VM instances](https://console.cloud.google.com/compute/instances), select your instance, and click Delete."
- **Action:** `exit` the container. *(extra)* `sudo docker ps -a` shows only the header (`vm-debian12/11-ps-a.txt`): `--rm` left nothing behind. Then delete the VM in the console (or *(extra)* `gcloud compute instances delete ac215-l02 --zone=us-central1-a`).
- **Checkpoint:** *VM instances* and *Disks* are both empty.

### Part D (optional): clean up the laptop and Docker Hub

- `docker system prune -a` removes stopped containers, unused networks, every image no container uses and the build cache. The images download again when you next need them.
- If you ran `docker-build-push.sh`: `docker buildx rm multi-arch` removes its builder container, and `docker buildx use default` makes the default builder current again.
- `docker logout` removes the stored Docker Hub credential.
- On hub.docker.com, delete `<USER NAME>/simple-translate-ac215` or make it private: anyone can pull a public image, and everything `COPY . ./` copied is in it (exercise D3).

---

## 5. Code tour

```
simple-translate/            (main @ 62f821b)
├── README.md               the tutorial; L02 = lines 106-191 (containers + push) and 203-220 (VM + Docker)
├── Dockerfile.txt          the solution Dockerfile (29 lines, no final newline; mode 100755); copy it to "Dockerfile"
├── docker-shell.sh         dev helper: docker build + docker run --rm --name … -ti   (mode 100755)
├── docker-build-push.sh    buildx multi-platform (amd64 + arm64) build and push to dlops/…   (mode 100644: not executable)
├── cli.py                  the app: argparse -> async googletrans call -> print   (unchanged from L01)
├── pyproject.toml          uv project "app": art, googletrans==4.0.2; requires-python >=3.13   (unchanged from L01)
├── .gitignore              ignores .DS_Store, Dockerfile (the one you write), /.idea/
└── .vscode/settings.json   VS Code: Black as Python formatter (irrelevant to Docker)
  (no Dockerfile, no uv.lock, no .dockerignore, no .python-version)

simple-translate/  (pipenv @ 3a354d8, comparison only)
├── Dockerfile              python:3.11-slim-buster + "pipenv sync" + CMD ["-c", "pipenv shell"]
├── docker-shell.sh         the --platform=linux/amd64 build is the *active* line here
└── Pipfile, Pipfile.lock, cli.py, tip.txt, README.md, .gitignore, .vscode/
```

**`Dockerfile.txt:1-11`** (base image and environment)
```dockerfile
# Use the official Debian-hosted Python image
FROM python:3.12-slim-bookworm

# Prevent apt from showing prompts
ENV DEBIAN_FRONTEND=noninteractive

# Python wants UTF-8 locale
ENV LANG=C.UTF-8

# Tell Python to disable buffering so we don't lose any logs.
ENV PYTHONUNBUFFERED=1
```
- **L2:** an official multi-platform image: Debian 12 "bookworm", slim variant, CPython 3.12 (3.12.15 on 2026-10-13). Docker picks the platform that matches the build machine (§3.7).
- **L5:** stops apt from waiting for keyboard input during the build. Because it is `ENV`, not `ARG`, it also stays set in every container.
- **L8:** the base image already sets `LANG=C.UTF-8` (its `docker history` row `ENV LANG=C.UTF-8`), so this line repeats it; harmless.
- **L11:** `print` output appears immediately instead of sitting in a buffer, which matters once you read container logs.
- Each `ENV` writes only on the config: their `docker history` rows are `0B`.

**`Dockerfile.txt:13-24`** (OS update, uv, code, venv)
```dockerfile
# Ensure we have an up to date baseline, install dependencies and
RUN set -ex; \
    apt-get update && \
    apt-get upgrade -y && \
    apt-get clean && \
    pip install --no-cache-dir --upgrade pip && \
    pip install uv

# Copy the source code
COPY . ./

RUN uv sync
```
- **L13:** the comment stops mid-sentence ("install dependencies and").
- **L14-19:** one `RUN` = one layer (97.5MB in the captured build). `set -ex` stops at the first failing command and echoes each command into the build log (`+ apt-get update`, …). `apt-get clean` empties apt's `.deb` cache but not `/var/lib/apt/lists`, which stays in the image (about 19 MB per the digest's check; L03's Dockerfile adds `rm -rf /var/lib/apt/lists/*`). The first `pip install` has `--no-cache-dir`, the second (`pip install uv`, unpinned) doesn't.
- **L22:** `COPY . ./` copies the whole build context into `/` (no `WORKDIR`): `.git`, `.vscode`, `Dockerfile`, everything (§3.2).
- **L24:** creates `/.venv` and `/uv.lock` and, because of `pyproject.toml:6`, downloads a standalone CPython ≥ 3.13 (§3.8). Its place after line 22 is why every file change re-runs it (§3.3).

**`Dockerfile.txt:26-29`** (start-up command)
```dockerfile
# Entry point
ENTRYPOINT ["/bin/bash"]
# Get into the uv virtual environment shell
CMD ["-c", "source .venv/bin/activate && exec bash"]
```
- Both use the exec (JSON) form, so Docker runs the argument list directly, without wrapping it in `/bin/sh -c`. Together: `/bin/bash -c "source .venv/bin/activate && exec bash"`.
- `source` is a bash builtin; Debian's `/bin/sh` (dash) only has `.`, which is one reason the entrypoint is bash.
- `.venv` is relative to the working directory, `/`.
- `exec bash` replaces the `-c` shell, so the interactive bash is PID 1 (captured `echo $$` → `1`) and `exit` ends the container.

**`pyproject.toml:1-10`** (unchanged from L01)
```toml
[project]
name = "app"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "art>=6.5",
    "googletrans==4.0.2",
]
```
- **L2:** `name = "app"` becomes the venv's prompt name (`prompt = app` in the image's `pyvenv.cfg`).
- **L5:** names `README.md`, which matters if you copy only some files before `uv sync` (exercise B3).
- **L6:** `>=3.13` conflicts with the 3.12 base image and triggers the CPython download.
- **L8-9:** `art` has only a floor; `googletrans` is pinned and pulls in `httpx[http2]`. Resolved on 2026-10-13: 13 lock entries, 11 packages installed on Python 3.15 (`typing-extensions` is needed only below 3.15).
- No `[build-system]` table, so uv installs only the dependencies, not the project itself.

**`cli.py:12-23`** (start of `main`)
```python
async def main(args):
    print("\n")
    print(text2art("AC215"))
    print("\nArguments:", args)

    text = args.text

    if args.file:
        with open(args.file, encoding="utf-8") as file:
            text = file.read()

    print("\nInput:", text)
```
- The banner is a quick proof that `art` imported, i.e. that the venv is active.
- `-f/--file` (lines 19-21) opens a path **inside the container's filesystem**. A file on your laptop is invisible unless it was in the build context (then you see the copy from build time) or you mount it, which is L03's `-v`.

**`cli.py:25-39`** (the network call)
```python
    async with Translator(raise_exception=True) as translator:
        try:
            result = await translator.translate(
                text,
                src=args.src,
                dest=args.dest,
            )
        except Exception as error:
            raise RuntimeError(
                "Translation request to Google Translate failed "
                "(the server's network/IP may be rate-limited or blocked "
                "by Google's unofficial translate endpoint)."
            ) from error

    print("Output:", result.text)
```
- `raise_exception=True` (added in `62f821b` on 2026-09-08, the day of the lecture) turns a non-200 reply into an exception. Without it, googletrans 4.0.2 returns your input text as the "translation" (`googletrans/client.py:136-144` in the wheel), which is what the published `dlops/simple-translate` still does: its `cli.py` line 25 is `async with Translator() as translator:` (captured).
- The `RuntimeError` text points at the network, not at Docker. It wraps *every* exception, so scroll up to the first one for the real cause (L01 showed a language-code typo ending the same way).

**`cli.py:59-72`** (defaults and entry point)
```python
    parser.add_argument(
        "-s",
        "--src",
        default="en",
        help="Source language",
    )
    parser.add_argument(
        "-d",
        "--dest",
        default="it",
        help="Destination language",
    )

    asyncio.run(main(parser.parse_args()))
```
- English to Italian by default, with the text `I love cheese` (line 49): that's why the VM's plain `python cli.py` prints `Output: Adoro il formaggio`. Language codes: the table at `README.md:225-288`.

**`docker-shell.sh:6-15`** (the local helper; not mentioned in the README)
```bash
# Define some environment variables
export IMAGE_NAME="simple-translate"
export BASE_DIR=$(pwd)

# Build the image based on the Dockerfile
docker build -t $IMAGE_NAME -f Dockerfile .
#docker build -t $IMAGE_NAME --platform=linux/amd64 -f Dockerfile .

# Run the container
docker run --rm --name $IMAGE_NAME -ti $IMAGE_NAME
```
- Lines 11 and 15 are the README's build and run (`README.md:174`, `:180`), plus `--name`, which fails if a container of that name already exists (§6 #19).
- **L12:** the commented-out amd64 build, the Apple Silicon fix (§3.7). On the `pipenv` branch this was the active line.
- **L8:** `BASE_DIR` is unused here; later course scripts use it for `-v` mounts.

**`docker-build-push.sh:10-27`** (the multi-platform publisher; not mentioned in the README)
```bash
# Default values
DOCKER_USERNAME="dlops"

echo "Building production image..."

# Check if multi-arch builder exists and remove it if it does
if docker buildx inspect multi-arch >/dev/null 2>&1; then
    echo "Removing existing multi-arch builder..."
    docker buildx rm multi-arch
fi

# Setup multi architecture build
echo "Creating new multi-arch builder..."
docker buildx create --driver-opt network=host --use --name multi-arch

# Push
echo "Pushing multi-arch image to registry..."
docker buildx build --platform linux/amd64,linux/arm64 --push -t $DOCKER_USERNAME/$IMAGE_NAME -f Dockerfile .
```
- **L11:** the instructor's account. Change it to yours, or the push is refused (§6 #18). `IMAGE_NAME` is set on line 7 (`"simple-translate"`, not the README's `simple-translate-ac215`).
- **L16-19:** deletes an old `multi-arch` builder first, so the script can be re-run.
- **L23:** creates a builder that runs BuildKit in its own container and can build several platforms. `--use` makes it the **current** builder for later commands too, including plain `docker build`, whose results it doesn't load into your image list (§6 #16).
- **L27:** builds amd64 and arm64 (one natively, one emulated) and `--push`es one tag that points at an index of both. Nothing is loaded locally.
- The file is mode 100644, so run it with `bash docker-build-push.sh`.

**`.gitignore:1-4`**
```
# misc
.DS_Store
Dockerfile
/.idea/
```
- **L3** hides the `Dockerfile` you write (captured `git status`: `nothing to commit, working tree clean`). To keep it in your own fork: `git add -f Dockerfile`.
- `.gitignore` is read by git only. `docker build` ignores it: only a `.dockerignore` filters the build context.

**The `pipenv` branch, for comparison** (`origin/pipenv:Dockerfile:1-26`): `FROM python:3.11-slim-buster` (Debian 10, end-of-life), `ENV PYENV_SHELL=/bin/bash`, a `RUN` that also installs `build-essential git` and `pipenv`, `ADD . /`, `RUN pipenv sync` from a **committed** `Pipfile.lock`, and `CMD ["-c", "pipenv shell"]`. Its README tags the image `simple-translate-e115` (`origin/pipenv:README.md:91-92`, `:114`), a leftover from another course. The `main` version swapped pipenv for uv but dropped the lockfile.

---

## 6. Gotchas and common errors

Each item says whether the message was **captured** on 2026-10-13, checked in the exercise checks, or is the documented behaviour that couldn't be run here.

1. **`ERROR: failed to build: failed to solve: failed to read dockerfile: open Dockerfile: no such file or directory`** (captured, `laptop/07`).
   - **Cause:** the repo ships only `Dockerfile.txt`; you are meant to write `Dockerfile` (`README.md:128`). Or the terminal is in the wrong folder, or the file got another name (`Dockerfile.txt`, `dockerfile.rtf`).
   - **Fix:** `cd` into `simple-translate` (`README.md:172`) and create the file, or `cp Dockerfile.txt Dockerfile`.

2. **Your `Dockerfile` doesn't show up in `git status` or in your fork** (captured, `laptop/12`).
   - **Cause:** `.gitignore:3` ignores `Dockerfile`.
   - **Fix:** `git add -f Dockerfile`, or remove that line in your copy.

3. **`Cannot connect to the Docker daemon at unix:///…/docker.sock. Is the docker daemon running?`** on the laptop.
   - **Cause:** Docker Desktop isn't running.
   - **Fix:** start it and wait for the engine (`README.md:110-111`).

4. **`ERROR: docker: 'docker buildx build' requires 1 argument`** (exercise check C1).
   - **Cause:** the final `.` is missing. The build context is the one argument `docker build` requires; `-f` only picks the recipe.
   - **Fix:** `docker build -t simple-translate -f Dockerfile .`, dot included.

5. **`ModuleNotFoundError: No module named 'art'` inside the container** (captured, `laptop/19`, `laptop/22`).
   - **Cause:** before Step 4 there's no venv; after it, nothing has activated it, so `python` is the base image's `/usr/local/bin/python` (3.12) without the packages. The same happens with `docker run --rm simple-translate -c "python cli.py"`: your `-c` string replaced the CMD that activated the venv (exercise C2).
   - **Fix:** finish Step 5 (`CMD` activates the venv), or `source .venv/bin/activate`, or call `.venv/bin/python` directly.

6. **`/usr/local/bin/python: /usr/local/bin/python: cannot execute binary file`, exit 126** (captured, `laptop/36`).
   - **Cause:** `docker run --rm -ti simple-translate python cli.py`: words after the image name replace CMD, so the container runs `/bin/bash python cli.py` and bash tries to read the Python binary as a script (§3.4).
   - **Fix:** `docker run --rm simple-translate -c "source .venv/bin/activate && python cli.py -d fr"` (captured, `laptop/37`), or `docker run --rm --entrypoint /.venv/bin/python simple-translate cli.py -d fr`.

7. **"The prompt has no `(app)`, so the venv isn't active"** (captured, `laptop/26`).
   - **Cause:** it is active (`which python` → `/.venv/bin/python`, `echo $VIRTUAL_ENV` → `/.venv`). The activate script sets the `(app)` prefix, but `exec bash` starts a new interactive bash that reads Debian's `/etc/bash.bashrc`, which sets the prompt again.
   - **Fix:** nothing to fix; check with `which python`.

8. **`python --version` says 3.15.0 (or 3.14.7) although the Dockerfile and the README say 3.12** (captured, `laptop/33`, `vm-debian12/06`).
   - **Cause:** `pyproject.toml:6` (`>=3.13`) vs `Dockerfile.txt:2` (3.12): `uv sync` downloads a standalone CPython (35.9MiB compressed, `112M` on disk in the exercise check), and the image carries two Pythons (§3.8).
   - **Fix:** align them: `FROM python:3.13-slim-bookworm` (checked: no download, 12 packages, image about 350MB instead of 518MB), or a `requires-python` the base image meets. `ENV UV_PYTHON_DOWNLOADS=never` makes a mismatch fail loudly: `error: No interpreter found for Python >=3.13 in managed installations or search path` (exercise B1).

9. **Every rebuild re-runs `uv sync` and re-downloads Python** (captured, `laptop/21`, `24`, `40`, `41`).
   - **Cause:** `COPY . ./` precedes `RUN uv sync` (`Dockerfile.txt:22-24`), and the build context contains everything: editing `cli.py`, `README.md`, your `Dockerfile` (as in the README's step-by-step builds), or even running `git checkout` (which rewrites `.git/index`) changes what `COPY` copies.
   - **Fix:** while following the README, expected. In your own projects: copy `pyproject.toml` (and `uv.lock`) first, `RUN uv sync`, then `COPY . ./`, with a `.dockerignore` listing `.git`, `.venv`, `secrets/`, `Dockerfile` (exercise Q4/B3; checked: an edit to `cli.py` then re-runs only the last `COPY`).

10. **Two builds a few weeks apart contain different versions** (captured comparison).
    - **Cause:** nothing is pinned: no `uv.lock` in the repo (`git log --all -- uv.lock` is empty), `pip install uv` takes the latest uv, `requires-python` is open-ended, `art>=6.5` floats, `apt-get upgrade` takes the day's packages. The published image (2026-09-16) has uv 0.12.15 and CPython 3.14.7; the build of 2026-10-13 got uv 0.13.0 and CPython 3.15.0.
    - **Fix:** commit a `uv.lock` and use `uv sync --locked` (or `--frozen`); `pip install uv==<version>`; pin the base image by digest. And deploy the image you tested, by digest, rather than rebuilding (exercise D2).

11. **Your `.git` (commit history, names, e-mail addresses), a laptop `.venv` or, from L03 on, a `secrets/` folder ends up in a public image** (captured `ls -a /`; exercise D3).
    - **Cause:** no `.dockerignore`, and `COPY . ./` copies the whole context. The published `dlops/simple-translate` contains `/.git` with its `logs/`. Deleting a file in a later `RUN rm` doesn't help: it stays in the earlier layer (checked with a dummy token and `docker save`).
    - **Fix:** a `.dockerignore` before you build and push. `.gitignore` doesn't affect `docker build`.

12. **`invalid tag "…": repository name must be lowercase`** (from `docker build -t`) or **`invalid reference format: repository name (…) must be lowercase`** (from `docker run`) (the digest's check).
    - **Cause:** uppercase letters in an image name. Docker Hub usernames in image names are lowercase.
    - **Fix:** use lowercase names.

13. **`push access denied, repository does not exist or may require authorization: server message: insufficient_scope: authorization failed`** (captured, `laptop-push/03`).
    - **Cause:** not logged in; or the name doesn't start with **your** username (a typo, `student` copied from the video, a name without an account, which means `library`); or a token without write access.
    - **Fix:** `docker login -u <USER NAME>` and paste a token that can write; tag with your own username.

14. **On the VM, your image fails: `no matching manifest for linux/amd64 … in the manifest list entries`, or it pulls and then dies with `exec format error`** (not captured on a VM: no Mac and no Docker Hub account here; the exercise check got `no matching manifest for linux/amd64/v4 in the manifest list entries: no match for platform in manifest: not found` from Docker 29 on amd64; the `exec format error` was captured the other way round, `laptop-push/12`).
    - **Cause:** a plain `docker build` on Apple Silicon makes `linux/arm64`; default GCP VMs are amd64 without an emulator. The README never mentions platforms. With Docker's containerd image store your push is an index (your platform + an attestation), so an amd64 host finds no matching row; a single-manifest push pulls and then fails at `exec`.
    - **Fix:** `docker build -t simple-translate --platform=linux/amd64 -f Dockerfile .` (`docker-shell.sh:12`) and push again, or `docker-build-push.sh` for both platforms, or an Arm VM (T2A/C4A). Verify with `docker buildx imagetools inspect <USER NAME>/simple-translate-ac215`.

15. **`WARNING! Using --password via the CLI is insecure. Use --password-stdin.`** (captured, `laptop-push/05`).
    - **Cause:** `README.md:189` passes the token with `-p`, so it lands in your shell history.
    - **Fix:** `docker login -u <USER NAME>` and paste at the prompt, or `echo "$TOKEN" | docker login -u <USER NAME> --password-stdin`.

16. **After `docker-build-push.sh`, a plain build prints `WARNING: No output specified with docker-container driver. Build result will only remain in the build cache. To push result image into registry use --push or to load image into docker use --load`, and `docker run simple-translate` runs the old image** (exercise check C5).
    - **Cause:** `docker buildx create … --use` (`docker-build-push.sh:23`) made the `multi-arch` builder current; it keeps results in its own container.
    - **Fix:** `docker buildx use default` (`desktop-linux` on Docker Desktop; `docker buildx ls` marks the current one with `*`), or add `--load` to that build. Remove the builder with `docker buildx rm multi-arch` when done.

17. **`./docker-build-push.sh` → `permission denied`.**
    - **Cause:** the file is mode 100644 in git (`docker-shell.sh` is 100755).
    - **Fix:** `bash docker-build-push.sh`, or `chmod +x docker-build-push.sh`.

18. **`docker-build-push.sh` fails at the push with an authorization error** (expected; not run: no account).
    - **Cause:** `DOCKER_USERNAME="dlops"` is hard-coded (`docker-build-push.sh:11`); you can't push to the instructor's namespace.
    - **Fix:** put your username on line 11 (and `simple-translate-ac215` on line 7 if you want the README's name), and log in first.

19. **`docker: Error response from daemon: Conflict. The container name "/simple-translate" is already in use by container "…". You have to remove (or rename) that container to be able to reuse that name.`** (exercise check C7, exit 125).
    - **Cause:** `sh docker-shell.sh` runs with `--name simple-translate` (`docker-shell.sh:15`) while another container of that name still exists, e.g. open in a second terminal.
    - **Fix:** `exit` the other one, or `docker ps -a` and `docker rm -f simple-translate`. The README's own run command has no `--name` and never conflicts.

20. **On the VM, `Output:` repeats `Input:` with no error; or on your build, `RuntimeError: Translation request to Google Translate failed …`** (the 2026-10-13 runs translated normally; behaviour from the code).
    - **Cause:** Google's unofficial endpoint refused the request (rate limit, blocked address). The published `dlops/simple-translate` has the older `cli.py` with `Translator()`, i.e. `raise_exception=False` (captured: `25:    async with Translator() as translator:`), so googletrans returns your text as dummy data (`googletrans/client.py:136-144` in the 4.0.2 wheel). The repo's `cli.py:25-37` raises a clear error instead.
    - **Fix:** not a Docker problem: retry later or from another network. Build from the current repo to get the explicit error.

21. **`E: Unable to locate package docker.io`** (Debian 13: `Error: …`), or `404 Not Found` fetch errors, on the VM (captured, `vm-debian12/01`, `vm-debian13/01`, exit 100).
    - **Cause:** empty or stale package lists; `README.md:210` skips `apt-get update`.
    - **Fix:** `sudo apt-get update`, then `sudo apt install docker.io`.

22. **`permission denied while trying to connect to the Docker daemon socket at unix:///var/run/docker.sock`** on the VM (captured, `vm-debian12/05`).
    - **Cause:** your VM user isn't in the `docker` group; the socket is `srw-rw---- 1 root docker`.
    - **Fix:** `sudo`, as the README writes it (`README.md:213`, `:215`), or `sudo usermod -aG docker $USER` and a new SSH session (exercise C6). Membership in that group is as powerful as root.

23. **`docker: Error response from daemon: toomanyrequests: You have reached your unauthenticated pull rate limit.`** (captured, `vm-debian13/06-docker-run-rate-limited.txt`, exit 125).
    - **Cause:** Docker Hub limits anonymous pulls per network address, and a class behind one address shares the allowance.
    - **Fix:** wait and retry, or log in first: `sudo docker login -u <USER NAME>`.

24. **`docker system prune` freed almost nothing** (captured: `Total reclaimed space: 0B` on a clean engine).
    - **Cause:** without `-a` it removes only *dangling* images (its own warning says so); the README's heading promises "clear up an unused images" (`README.md:113`).
    - **Fix:** `docker system prune -a` removes every image no container uses; they download again next time.

25. **You edit `cli.py` on the laptop and the running container doesn't see it.**
    - **Cause:** the code was **copied** into the image at build time; nothing is mounted.
    - **Fix:** rebuild and run again, or wait for L03's `-v "$(pwd):/app"`.

26. **A prompt appears, but typing does nothing and Ctrl-C only prints a new prompt** (exercise check B4).
    - **Cause:** `docker run -t` without `-i`: a terminal, but your keyboard isn't connected. The container stays `Up`.
    - **Fix:** use `-ti` as the README does; stop the stuck one with `docker stop <CONTAINER ID>` from another terminal.

27. **Charges after the lab.**
    - **Cause:** the VM still runs, or you only stopped it and its boot disk still exists.
    - **Fix:** delete it (`README.md:220`) and check *VM instances* and *Disks*.

---

## 7. Where this sits in the course

- **Before: L01, Virtual Environments and Virtual Machines** (`tutorials_demo.md:16-27`), on the *same repo* (`README.md:38-101`): a manual install with `sudo pip3 install --break-system-packages …` on a VM, then `uv sync` + `source .venv/bin/activate` on a fresh VM. The pain point it leaves: every new VM needs `apt`, `git clone`, uv and `uv sync` again, and works only if the OS cooperates (Debian 12's Python 3.11 made uv download another one).
- **What L02 adds:**
  - an **image** that holds the OS userland, Python, the venv and the code;
  - a **registry** to ship it;
  - a **one-command deploy** on a VM that has only Docker;
  - the habits of reading build logs (`CACHED`), checking an image's platform, and keeping secrets out of the build context.
  - Files newly in play: `Dockerfile.txt` (→ your `Dockerfile`), `docker-shell.sh` and `docker-build-push.sh`. `cli.py` and `pyproject.toml` are reused unchanged.
- **Repo history relevant to L02** (`main`):
  ```
  62f821b 2026-09-08  cli.py: raise_exception=True + RuntimeError wrapper; .gitignore: add /.idea/
  2827e2a 2026-09-02  pyproject.toml: requires-python ">=3.12,<3.13" -> ">=3.13"; googletrans 4.0.0rc1 -> 4.0.2
  476aec1 2026-09-02  README: googletrans==4.0.2 in step 1, reworded PEP 668 tip
  e3bd74e 2026-09-02  cli.py rewritten async (googletrans 4.x API); README sudo pip3
  5a6849d 2026-08-28  initial uv-based version
  ```
  The three 2026-09-02 commits all have the message "new cli and new readme"; the summaries above describe their changes. The published `dlops/simple-translate` (2026-09-16) still carries the `cli.py` from before `62f821b`.
- **Next: L03, Containers II (mega-pipeline)** (`tutorials_demo.md:46-52`). The same Dockerfile skeleton, grown up (`mega-pipeline/transcribe_audio/README.md`, line numbers below):

  | simple-translate (L02) | mega-pipeline component (L03) |
  |---|---|
  | no `WORKDIR`, app in `/` | `WORKDIR /app` (line 77) |
  | runs as root | non-root `USER app` (line 76), `COPY --chown=app:app . ./` (line 82) |
  | venv in `/.venv` | `ENV UV_PROJECT_ENVIRONMENT=/home/app/.venv` (line 54) |
  | no credentials | `ENV GOOGLE_APPLICATION_CREDENTIALS=secrets/mega-pipeline.json` (line 55) and a service-account key |
  | code baked in; rebuild to change it | bind mount: `docker run --rm -ti -v "$(pwd):/app" transcribe_audio` (line 99) |
  | apt lists left in the image | `rm -rf /var/lib/apt/lists/*` in the same `RUN` (line 64) |
  | one container | five containers that hand work to each other through a GCS bucket |

- **L04** (`port_toy`, the flexible workflow) adds ports, networks and `docker compose`.
- **Later:** the multi-platform push from `docker-build-push.sh` comes back almost verbatim, e.g. `ml-workflow/src/data-collector/docker-shell-push.sh:25-33` and `cheese-app-v4/src/data-collector/docker-shell-push.sh:25-33`; `ml-workflow/README.md:137` has an explicit "If you are on M1/2 Macs" line with `--platform=linux/amd64/v2`. Image, cache, ENTRYPOINT/CMD and platform (§3.1, §3.3, §3.4, §3.7) are used in every later lecture.
- **Branch diff (`main` → `pipenv`, unrelated roots):** `git diff --stat main origin/pipenv` reports 11 files changed, 247 insertions, 265 deletions. For Docker the meaningful differences are: `python:3.11-slim-buster` vs `python:3.12-slim-bookworm`; `ADD . /` + `RUN pipenv sync` from a committed `Pipfile.lock` vs `COPY . ./` + `RUN uv sync` without a lockfile; `CMD ["-c", "pipenv shell"]` vs sourcing the venv; and the `--platform=linux/amd64` build active in `pipenv`'s `docker-shell.sh`, commented out in `main`'s.

---

## 8. Exercises

The exercises, with answers, are in [`exercises.md`](https://github.com/JunyiZhou-Conny/Explainer_Videos/blob/main/videos/ac215-l02-containers-1/exercises.md) in the video folder. Their outputs are the 2026-10-13 captures, or were checked the same day in throwaway containers built from the README's Dockerfile (Docker Engine 29.8.2, uv 0.13.0, Python 3.12.15 in the base image; what was run is listed in `assets/exercise-checks/README.md`). Do them after watching, without re-watching first; re-watch only the part you got wrong. A summary follows; open each answer only after you have committed to your own.

### Test yourself: the five questions from the end of the video

**Q1. What is the difference between an image and a container, and what does `--rm` delete?**
<details><summary>Answer</summary>

An image is a stack of read-only layers plus a config: `RUN uv sync` 125MB, `COPY . ./` 250kB, the apt/pip `RUN` 97.5MB, and `0B` rows for `ENV`, `ENTRYPOINT` and `CMD` (`docker history`, `laptop/34`). `docker run` makes a container: the same layers, shared, plus a thin writable layer and one main process (bash, PID 1). When that process ends (`exit`), the container stops; `--rm` then deletes it with its writable layer and every file you created inside. The image is untouched: after the README's run, `docker ps -a` lists nothing and `simple-translate` is still in `docker image ls`. That's why "Build the docker container" (`README.md:173`) is a slip: building makes an image.
</details>

**Q2. What command line does the container run at start-up, and what happens with `docker run --rm -ti simple-translate python cli.py`?**
<details><summary>Answer</summary>

ENTRYPOINT + CMD: `/bin/bash -c "source .venv/bin/activate && exec bash"` (captured config: `Entrypoint=["/bin/bash"] Cmd=["-c","source .venv/bin/activate && exec bash"]`). Words after the image name replace **CMD only**, so it runs `/bin/bash python cli.py`; bash looks for a script called `python`, finds the base image's binary `/usr/local/bin/python` on a `PATH` nobody activated, and refuses: `/usr/local/bin/python: /usr/local/bin/python: cannot execute binary file`, exit 126. Working forms: `docker run --rm simple-translate -c "source .venv/bin/activate && python cli.py -d fr"` (captured: `Output: j'adore le fromage`) or `docker run --rm --entrypoint /.venv/bin/python simple-translate cli.py -d fr`.
</details>

**Q3. The Dockerfile says `python:3.12`. Why does `python --version` print 3.15 (or 3.14), and what does `/usr/local/bin/python` print?**
<details><summary>Answer</summary>

`pyproject.toml:6` asks for `>=3.13`, which the base image's 3.12 doesn't meet, so `uv sync` downloads the newest stable CPython it knows in range: 3.15.0 with uv 0.13.0 on 2026-10-13 (`Downloading cpython-3.15.0-linux-x86_64-gnu (download) (35.9MiB)`), 3.14.7 in the instructor's image (built 2026-09-16 with uv 0.12.15). CMD activated the venv, so `python` is `/.venv/bin/python`, a link into uv's folder. `/usr/local/bin/python --version` prints the base image's `Python 3.12.15` (3.12.14 in the instructor's image); it only ran `pip install uv`. Most of the 125MB `uv sync` layer is that second Python (`112M`, against `6.9M` for `/.venv`).
</details>

**Q4. You edit one line of `cli.py`. Which build steps re-run, and how would you reorder the Dockerfile so `uv sync` stays cached?**
<details><summary>Answer</summary>

`FROM` and `[2/4] RUN set -ex; apt-get update …` are `CACHED`; `[3/4] COPY . ./` runs because the copied files changed, and so does every later step: `[4/4] RUN uv sync`, Python download included (`laptop/40`). Undoing the edit with `git checkout` doesn't bring the cache back, because `.git/index` changed (`laptop/41`). Reorder:

```dockerfile
# Copy only the files uv sync needs, then install the packages
COPY pyproject.toml README.md ./
RUN uv sync

# Copy the rest of the source code
COPY . ./
```

with a `.dockerignore` listing `.git`, `.venv`, `secrets/` and `Dockerfile` (the full file is in `exercises.md`). Checked: after editing `cli.py`, only the last `COPY . ./` ran. It's a pattern for your own projects, not the course solution.
</details>

**Q5. Name two ways to make an image built on Apple Silicon run on a default GCP VM.**
<details><summary>Answer</summary>

1. Build for the VM's platform: `docker build -t simple-translate --platform=linux/amd64 -f Dockerfile .` (the commented-out `docker-shell.sh:12`), then tag and push again.
2. Push both platforms with buildx: set your username (line 11) and image name (line 7) in `docker-build-push.sh`, log in, `bash docker-build-push.sh`; afterwards `docker buildx use default`.

Check with `docker buildx imagetools inspect <USER NAME>/simple-translate-ac215`: it must list `Platform: linux/amd64`. A third way changes the VM instead: an Arm machine series such as C4A runs arm64 images directly.
</details>

### Hands-on (predict, then run)

**B1 · Two Pythons, then one.** Predict `python --version`, `/usr/local/bin/python --version` and `ls -l .venv/bin/python` in the container; then build a copy of the solution with `ENV UV_PYTHON_DOWNLOADS=never` under `FROM`; then the same with `FROM python:3.13-slim-bookworm`.
<details><summary>Answer</summary>

`Python 3.15.0`, `Python 3.12.15`, and `.venv/bin/python -> /root/.local/share/uv/python/cpython-3.15-linux-x86_64-gnu/bin/python3.15`. With downloads forbidden, every step after the new `ENV` re-runs and `uv sync` fails: `error: No interpreter found for Python >=3.13 in managed installations or search path` and `hint: A managed Python download is available for Python >=3.13, but Python downloads are set to 'never'` (no image created). On the 3.13 base, uv uses the image's own Python (`Using CPython 3.13.16 interpreter at: /usr/local/bin/python3`), installs 12 packages (`typing-extensions` too), the `uv sync` layer drops from 125MB to about 8MB and the image from 518MB to about 350MB.
</details>

**B2 · Where did my file go?** `echo "Le fromage est bon" > /note.txt` in one `--rm` container, `cat /note.txt` in the next; then the same with `docker run -ti --name cheese simple-translate` (no `--rm`).
<details><summary>Answer</summary>

With `--rm`: `cat: /note.txt: No such file or directory`, because the first container's writable layer was deleted. Without it: `docker ps -a` lists `cheese` as `Exited (0)`; `docker start -ai cheese` restarts that same container and `cat /note.txt` prints `Le fromage est bon`; `docker diff cheese` lists `A /note.txt`. Clean up with `docker rm cheese`.
</details>

**B3 · Rebuild without the wait.** With the Q4 Dockerfile and its `.dockerignore`, predict which steps say `CACHED` after: the first build, a rebuild with no change, an edit to line 49 of `cli.py`, `git checkout -q cli.py`, a comment appended to the `Dockerfile`, an empty line added to `README.md`.
<details><summary>Answer</summary>

(1) The apt/pip `RUN` is `CACHED` if you built the solution before; the rest runs, and the context shrinks to `19.99kB` without `.git`. (2) Everything `CACHED`. (3) Only the last `COPY . ./` runs. (4) Everything `CACHED` (`.git/index` is no longer in the context). (5) Everything `CACHED` (the Dockerfile is ignored by `COPY` but still used for the build). (6) `COPY pyproject.toml README.md ./`, `uv sync` and the last `COPY` run; `COPY pyproject.toml ./` alone also works here (checked), because the project has no build system.
</details>

**B4 · What `-t` and `-i` each do.** (a) `docker run --rm simple-translate`; (b) `docker run --rm -t simple-translate`, then type `echo hi`; (c) `echo 'which python' | docker run --rm -i simple-translate`.
<details><summary>Answer</summary>

(a) No output, back at your prompt in under a second: bash read end-of-input and exited. (b) A prompt, but your keystrokes never reach it; the container stays `Up` until `docker stop`. (c) `/.venv/bin/python`: input is connected, so commands run in the activated venv, but with no terminal there's no prompt. `-ti` gives both.
</details>

**B5 · Two names, one image.** After `docker tag`, predict `docker image ls`, what `docker rmi <USER NAME>/simple-translate-ac215` deletes, and where `docker push simple-translate` would go.
<details><summary>Answer</summary>

Two rows, one ID (`b5c531a6b555` in `laptop/44`). `docker rmi` prints `Untagged: <USER NAME>/simple-translate-ac215:latest` and removes only that name. `docker push simple-translate` goes to `docker.io/library/simple-translate` and is refused with `push access denied, repository does not exist or may require authorization` (checked).
</details>

### Debugging

**C1 · Two ways the build won't start.** `docker build -t simple-translate -f Dockerfile` → `ERROR: docker: 'docker buildx build' requires 1 argument`; another build → `failed to read dockerfile: open Dockerfile: no such file or directory`.
<details><summary>Answer</summary>

The first is missing the final `.`, the build context. The second can't find `Dockerfile` in the context folder: wrong folder (`pwd`, `ls`; `README.md:172`), or a file named otherwise (`Dockerfile.txt` is the solution, not the recipe the command reads).
</details>

**C2 · "I replaced CMD and now `art` is missing."** `docker run --rm simple-translate -c "python cli.py"` → `ModuleNotFoundError: No module named 'art'`.
<details><summary>Answer</summary>

The `-c` string replaced the whole CMD, including `source .venv/bin/activate`, so `python` is the base image's 3.12 without packages. Use `-c "source .venv/bin/activate && python cli.py"` or `-c ".venv/bin/python cli.py"`.
</details>

**C3 · `push access denied`.** Name three causes of `push access denied, repository does not exist or may require authorization: server message: insufficient_scope: authorization failed`.
<details><summary>Answer</summary>

Not logged in (how the capture got it); a name that doesn't start with your username (a typo, the video's `student`, a name without an account, `DOCKER_USERNAME="dlops"` left in the script); a token that can't write.
</details>

**C4 · The VM won't run your image.** Built on an M-series Mac, pushed; on the VM: `no matching manifest for linux/amd64 in the manifest list entries`, while `dlops/simple-translate` works.
<details><summary>Answer</summary>

Your tag points at an index with `Platform: linux/arm64` plus an `unknown/unknown` attestation; the amd64 VM finds no row for itself. `dlops/simple-translate` is a single `linux/amd64` image (`laptop-push/10`, `vm-debian12/08`). Fix: Q5.
</details>

**C5 · "My changes don't show up any more."** After `docker-build-push.sh`, the README's build ends with `WARNING: No output specified with docker-container driver. …`, and `docker run` runs the old image.
<details><summary>Answer</summary>

`docker-build-push.sh:23` (`docker buildx create … --use --name multi-arch`) made a builder current that keeps its results to itself. `docker buildx use default` (`desktop-linux` on Docker Desktop), or `--load` for one build.
</details>

**C6 · `permission denied` on the VM.** Why does the README write `sudo`, and what's the alternative?
<details><summary>Answer</summary>

The socket `/var/run/docker.sock` is `srw-rw---- 1 root docker`, and your user is in neither. Alternative: `sudo usermod -aG docker $USER`, then a new SSH session (checked: `id -nG` then lists `docker`, and `docker ps` works). That group is as powerful as root.
</details>

**C7 · A name already in use.** `sh docker-shell.sh` in a second terminal → `Conflict. The container name "/simple-translate" is already in use …`, exit 125. Why does the README's run command never do this?
<details><summary>Answer</summary>

`docker-shell.sh:15` names every container `simple-translate`; the README's `docker run --rm -ti simple-translate` has no `--name`, so Docker invents one each time. Exit the other one, or `docker rm -f simple-translate`.
</details>

### Think

**D1 · Container or VM?** (a) two apps need different versions of a system library; (b) a different kernel or OS; (c) a GPU; (d) Linux containers on a Mac.
<details><summary>Answer</summary>

(a) Containers. (b) A VM: containers share the host's Linux kernel. (c) A container can use it, but the driver stays the host's. (d) Both: Docker Desktop runs your containers inside a hidden Linux VM.
</details>

**D2 · Same Dockerfile, a month apart.** What would you pin so a rebuild gives the same image, and how do you make the VM run exactly the image you tested?
<details><summary>Answer</summary>

The base image by digest (`FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258`), uv (`pip install uv==0.13.0`), the Python (a base that meets `requires-python`, `ENV UV_PYTHON_DOWNLOADS=never`), the packages (a committed `uv.lock` and `uv sync --locked`); `apt-get upgrade -y` still floats. Then deploy the image, not the recipe: run it by digest (`<USER NAME>/simple-translate-ac215@sha256:…`, from your push's `digest:` line) or with a version tag you never reuse.
</details>

**D3 · Before you push to a public repository.** What could your image tell a stranger, and what doesn't fix it?
<details><summary>Answer</summary>

Everything `COPY . ./` copied: `.git` with author names and e-mail addresses (the published image has `/.git` with its `logs/`), `.vscode`, any key or `secrets/` folder; plus every `RUN` line (`docker history`) and `ENV` value (`docker image inspect`). A later `RUN rm` doesn't remove a file from the earlier layer (checked with `docker save`), and a new `.dockerignore` doesn't change images already pushed: add it, rebuild, push again, and delete or make private any repository that leaked.
</details>

**D4 · What's still running after the lecture?**
<details><summary>Answer</summary>

The VM (bills while running) and its boot disk (while it exists): delete both and check *VM instances* and *Disks*. The Docker Hub repository: free but public. The laptop: a 518MB image plus base image and build cache (`docker system prune -a`). The `multi-arch` builder container if you ran the push script (`docker buildx rm multi-arch`, then `docker buildx use default`). Containers: none, if every run used `--rm` (`docker ps -a`, `sudo docker ps -a`). Optionally `docker logout`.
</details>

---

## 9. Errata and open questions

**Errata (wrong, outdated, ambiguous or inconsistent)**

1. **E1 · Python version mismatch.** `README.md:133` ("the official Debian-hosted Python 3.12 image") and `Dockerfile.txt:2` use Python 3.12, but `pyproject.toml:6` requires `>=3.13` (changed from `">=3.12,<3.13"` in `2827e2a`, 2026-09-02). `uv sync` therefore downloads a standalone CPython during the build: 3.15.0 on 2026-10-13 (captured), 3.14.7 in the published image. The README never mentions it, and the image carries two Pythons (§3.8).
2. **E2 · The promised lockfile doesn't exist.** `README.md:12` ("pinned in a lock file, so the next person gets the exact same versions") and `README.md:70` describe `uv.lock` pinning versions; `README.md:87` hedges with "(and `uv.lock` if present)". The repo has none and never had one (`git log --all -- uv.lock` is empty), so every build resolves anew, and `pip install uv` (`Dockerfile.txt:19`) floats too.
3. **E3 · CPU platforms are never covered.** `grep -n 'platform\|amd64\|arm64\|docker-shell\|docker-build-push' README.md` finds nothing. The only platform handling is the commented-out `docker-shell.sh:12` and the unreferenced `docker-build-push.sh`, so an Apple Silicon student's own image fails on a default VM (§6 #14).
4. **E4 · Step 4 deploys the wrong image.** `README.md:14` ("Pull what you just pushed") and `README.md:205` ("pull the image you pushed in step 3") promise your own image, but `README.md:215` runs the instructor's `dlops/simple-translate`, not `<USER NAME>/simple-translate-ac215` from `README.md:190-191`. The names also disagree with `docker-build-push.sh:7` (`IMAGE_NAME="simple-translate"`).
5. **E5 · The published image is not multi-platform and lags the repo.** `docker-build-push.sh` pushes an amd64 + arm64 index, but `dlops/simple-translate:latest` is a single `application/vnd.docker.distribution.manifest.v2+json`, linux/amd64 (captured, created 2026-09-16), so it wouldn't run on an Arm VM. It contains the `cli.py` from before `62f821b` (captured: 1266 bytes, `async with Translator() as translator:`), although it was built eight days after that commit.
6. **E6 · Probably broken in-page links.** The README's Contents links (`README.md:31-34`) use anchors like `#developing-app-using-containers`; for the emoji headings GitHub generates `#-developing-app-using-containers`, the form the course site links (`tutorials_demo.md:36`). The GitHub rendering could not be checked offline.
7. **E7 · Image vs container.** "copy source code into the container" (`README.md:146`) and "Build the docker container" (`README.md:173`) should both say *image*.
8. **E8 · Prune wording.** The heading "clear up an unused images" (`README.md:113`) promises more than `docker system prune` (`README.md:117`) does: it removes only *dangling* images unless you add `-a` (its own captured warning says "all dangling images").
9. **E9 · Insecure login.** `docker login -u <USER NAME> -p <ACCESS TOKEN>` (`README.md:189`) puts the token on the command line and in the shell history; Docker warns about it (captured).
10. **E10 · Missing `apt-get update`.** `README.md:210` installs `docker.io` without the `sudo apt-get update` of walkthroughs 1-2 (`README.md:44`, `:74`). On a fresh Debian with empty lists it fails with `E: Unable to locate package docker.io` (captured on Debian 12 and 13).
11. **E11 · Dockerfile hygiene.** In `Dockerfile.txt`: the comment on line 13 stops mid-sentence; `apt-get clean` (line 17) leaves `/var/lib/apt/lists` in the image; `pip install uv` (line 19) has no `--no-cache-dir`; `ENV LANG=C.UTF-8` (line 8) repeats the base image; there's no `WORKDIR`, so the app lives in `/`; and there's no `.dockerignore`, so `.git` and the `Dockerfile` itself are copied (line 22) and every edit re-runs `uv sync` (§6 #9, #11).
12. **E12 · Wrong prompt example (L01 section, low priority).** `README.md:92` shows `(simple-translate) $`; uv names the prompt after the project, `app` (`pyproject.toml:2`; `prompt = app` in the image's `pyvenv.cfg`). Inside the container even that prefix is replaced by Debian's `/etc/bash.bashrc` prompt.
13. **E13 · Placeholder metadata (cosmetic).** `pyproject.toml:2-4`: `name = "app"`, `description = "Add your description here"`.

**Where this guide follows the captures over the digest**
- `docker image ls` for the final image: `518MB` disk usage (captured, `laptop/30` and `44`; also the exercise checks), not the digest's 517MB; the unpacked part is therefore about 374 MB.
- The published image's layer sizes are given as the VM's Docker 20.10 / 26 count them (captured `vm-debian12/09`: `uv sync` 114MB, `COPY . ./` 209kB, apt/pip `RUN` 108MB, base Debian 74.8MB, base Python 3.12.14) instead of the digest's Docker 29 figures (127 MB, 0.5 MB, 111 MB, base about 141 MB); its size in `docker images` is the captured `347MB`.
- The fresh build's `COPY . ./` layer: `250kB` (captured `laptop/34`), not 0.26 MB.
- The message for a push without login: `push access denied, repository does not exist or may require authorization: server message: insufficient_scope: authorization failed` (captured `laptop-push/03`), not the digest's `denied: requested access to the resource is denied`. The digest's `Mounted from library/python` for a real Docker Hub push is kept only as a "may", since the captured pushes went to a local stand-in (all `Pushed`, then `Layer already exists`).
- `sudo docker --version`: the captured strings `Docker version 20.10.24+dfsg1, build 297e128` and `Docker version 26.1.5+dfsg1, build a72d7cd`; `sudo apt install docker.io` as written is shown failing on empty package lists (captured exit 100), with the update as the fix, rather than as a step that simply works.
- Tool versions: the captures' Docker 29.8.2 with buildx v0.37.2.
- Two captured facts the digest doesn't have: `git checkout cli.py` doesn't restore the cache (`laptop/41`), and Docker Hub's anonymous pull limit (`toomanyrequests`, `vm-debian13/06-docker-run-rate-limited.txt`).

**Open questions (couldn't be determined from the sources)**
- What the Ed lesson and the slides add; the course site links Lecture 2 as `/not-yet/` (`_modules/week-02.md:7`). They may already cover the Apple Silicon `--platform` issue the README omits.
- Which CPython a later build picks: it depends on the uv release `pip install uv` gets (3.14.7 with uv 0.12.15 on 2026-09-16, 3.15.0 with uv 0.13.0 on 2026-10-13).
- Whether Google's unofficial translate endpoint blocks Compute Engine addresses. The 2026-09-08 commit and the message at `cli.py:33-37` suggest it happened in class; every captured run on 2026-10-13 translated normally. No run was made from a real Compute Engine VM.
- Which Docker Hub page currently creates access tokens: `README.md:188` links `https://hub.docker.com/settings/security`; without an account it couldn't be checked.
- The default boot image students get (Debian 12 or 13), which decides the `docker.io` version, and whether a fresh Compute Engine image ships usable package lists (which decides whether `README.md:210` works without `apt-get update`).
- The exact output on macOS / Apple Silicon (`docker build` on Docker Desktop, the arm64 image's failure on a VM), and of a real `docker login` / `docker push` to Docker Hub: not run here. Docker's wording also differs between versions and between the classic and containerd image stores.
- The AWS variant (`simple-translate-aws`, `tutorials_demo.md:37`, `:42`) was not examined.

---

## Links

- README sections (pinned commit): [🐳 Developing App using Containers](https://github.com/dlops-io/simple-translate/blob/62f821bfe09fc1c2ecb0f14354b1f205777c0efa/README.md#-developing-app-using-containers) · [📤 Pushing Docker Image to Docker Hub](https://github.com/dlops-io/simple-translate/blob/62f821bfe09fc1c2ecb0f14354b1f205777c0efa/README.md#-pushing-docker-image-to-docker-hub) · [☁️ Running App on VM using Docker](https://github.com/dlops-io/simple-translate/blob/62f821bfe09fc1c2ecb0f14354b1f205777c0efa/README.md#%EF%B8%8F-running-app-on-vm-using-docker) · latest README on [`main`](https://github.com/dlops-io/simple-translate?tab=readme-ov-file#-developing-app-using-containers) · the [`pipenv` branch](https://github.com/dlops-io/simple-translate/tree/pipenv)
- Files quoted in §5 (pinned): [`Dockerfile.txt`](https://github.com/dlops-io/simple-translate/blob/62f821bfe09fc1c2ecb0f14354b1f205777c0efa/Dockerfile.txt) · [`docker-shell.sh`](https://github.com/dlops-io/simple-translate/blob/62f821bfe09fc1c2ecb0f14354b1f205777c0efa/docker-shell.sh) · [`docker-build-push.sh`](https://github.com/dlops-io/simple-translate/blob/62f821bfe09fc1c2ecb0f14354b1f205777c0efa/docker-build-push.sh) · [`pyproject.toml`](https://github.com/dlops-io/simple-translate/blob/62f821bfe09fc1c2ecb0f14354b1f205777c0efa/pyproject.toml) · [`cli.py`](https://github.com/dlops-io/simple-translate/blob/62f821bfe09fc1c2ecb0f14354b1f205777c0efa/cli.py)
- Ed lesson: [L2 · Containers I](https://edstem.org/us/courses/97373/lessons/166028/) · course [tutorials page](https://harvard-iacs.github.io/2026-AC215/tutorials_demo/)
- Video and materials: [video folder](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l02-containers-1) · [exercises.md](https://github.com/JunyiZhou-Conny/Explainer_Videos/blob/main/videos/ac215-l02-containers-1/exercises.md) · [terminal captures](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l02-containers-1/assets/terminal) · [digest.md](https://github.com/JunyiZhou-Conny/Explainer_Videos/blob/main/videos/ac215-l02-containers-1/digest.md)
- Docker Hub: the instructor's image [`dlops/simple-translate`](https://hub.docker.com/r/dlops/simple-translate) · the base image [`python`](https://hub.docker.com/_/python)
- Previous lecture: [L01 · Virtual Environments and Virtual Machines](L01-vms-venvs.md) (the same app, with a venv on a VM)
- Next lecture: [L03 · Containers II (mega-pipeline)](L03-containers-2-mega-pipeline.md) (five containers, `WORKDIR`, a non-root user, bind mounts) · then [L04 · Containers II-b (flexible workflow, ports)](L04-containers-2b-flexible-workflow-ports.md)
