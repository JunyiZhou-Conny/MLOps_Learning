# L01 · Virtual Environments and Virtual Machines — study guide

[Ed lesson](https://edstem.org/us/courses/97373/lessons/166027/) · Tutorials: [`dlops-io/ac215-setup`](https://github.com/dlops-io/ac215-setup) `main` @ [`61a7b9d`](https://github.com/dlops-io/ac215-setup/tree/61a7b9dd538e581a126117585db40c9e6b5d46b9) (Tutorial 0 · Setup & Installs) and [`dlops-io/simple-translate`](https://github.com/dlops-io/simple-translate) `main` @ [`62f821b`](https://github.com/dlops-io/simple-translate/tree/62f821bfe09fc1c2ecb0f14354b1f205777c0efa) (comparison branch `pipenv` @ [`3a354d8`](https://github.com/dlops-io/simple-translate/tree/3a354d81f787a064aea3ab061359c9a1e223e4d5)) · Video: [AC215 · L1 follow-along (≈30 min, English narration, Chinese/bilingual subtitles)](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l01-vms-venvs) · Made from the verified digest and real terminal captures, 2026-10-12

## 中文速览

- **做什么：** 在 GCP Compute Engine 上开一台 Debian VM，用 browser 里的 SSH 进去，把 `dlops-io/simple-translate` 这个 72 行的 CLI（`cli.py`，只依赖 `art` 和 `googletrans`）跑两遍：(A) 用 `sudo pip3 install --break-system-packages` 直接装进 system Python；(B) 换一台新 VM，装 `uv`，`uv sync` 建出 `.venv` 再跑。前置是 Tutorial 0（GCP project + free-trial credits）；这节课不需要 service account。
- **Idea 1 · VM 是一台用完就扔的机器：** hypervisor 从物理 server 上切一片给你，有自己的 kernel、vCPU/RAM，boot disk 是挂在 Google storage network 上的 persistent disk。CPU/RAM 只要 running 就按秒计费（idle 也算），disk 只要存在就计费。
- **Idea 2 · system Python 归 OS 管：** Debian 12/13 的 `/usr/bin/python3` 被标成 externally managed（PEP 668），所以 `pip3 install` 直接报 `error: externally-managed-environment`。`--break-system-packages` 绕过这个保护；`sudo pip3` 把 12 个包装进 `/usr/local/lib/python3.11/dist-packages`，它在 `sys.path` 上排在 apt 的 `/usr/lib/python3/dist-packages` 前面，会 shadow apt 的版本，影响所有用 system Python 的程序。
- **Idea 3 · venv 就是一个目录，三样东西：** `bin/python`（指向真实 interpreter 的 symlink）+ 自己的 `lib/python3.X/site-packages/` + `pyvenv.cfg`（`include-system-site-packages = false`）。它只隔离 Python packages，不隔离 OS、C library 和 driver；uv 建的 venv 里没有 `pip`（加包用 `uv add`）。
- **Idea 4 · activate 只改 PATH：** `source .venv/bin/activate` 把 `.venv/bin` 插到 PATH 最前面，设 `VIRTUAL_ENV`，prompt 变成 `(app)`，再定义 `deactivate`。不装包、不 load 包，只对当前这个 shell 有效。不 activate 也能跑：`uv run python cli.py` 或 `.venv/bin/python cli.py`。
- **Idea 5 · `uv sync` 一条命令做完四件事：** 选一个满足 `requires-python = ">=3.13"` 的 Python（Debian 12 只有 3.11.2，所以 2026-10-12 uv 0.13.0 下载了 CPython 3.15.0；Debian 13 自带 3.13.5，直接用）→ 建 `.venv` → resolve 整棵 dependency tree 并写出 `uv.lock`（13 个 entry）→ 装进 `.venv`（3.15 上 11 个包，3.13 上 12 个）。`>=3.13` 是 constraint 不是 pin；要 pin 用 `uv python pin 3.13`（写 `.python-version`）。
- **最费时间的坑：** ① 装完 uv 马上 `uv: command not found`：要 `source $HOME/.local/bin/env`，或者开一个新的 SSH 窗口。② 一长串红色 traceback 只看最后一行会被骗：`cli.py:32-37` 把所有 exception 都包成"network/IP"的 `RuntimeError`，要往上翻看第一个 exception。2026-10-12 的 capture 里 walkthrough A 真的收到 HTTP 429，而 `-d xx` 这种语言码 typo 是 `ValueError: invalid destination language`。③ SSH 窗口断线重连后 `(app)` 没了，要重新 `cd simple-translate` 再 `source .venv/bin/activate`。
- **README 的几个小 errata：** prompt 实际是 `(app)` 不是 `(simple-translate)`；repo 里根本没有 commit `uv.lock`（每个人第一次 `uv sync` 都重新 resolve）；activate 之后 `pip` 也不会指向 venv（uv venv 没有 pip）。
- **做完要删：** 每个 walkthrough 做完都 Delete VM（boot disk 默认跟着一起删）。是 delete 不是 stop：stop 之后 disk（还有 reserved static IP）照样计费。删完检查 VM instances 和 Disks 两页都是空的。

## At a glance

**What you build.** You rent a Debian VM on Google Compute Engine, SSH into it from the browser, and run the 72-line `simple-translate` CLI (`cli.py`, which needs the third-party packages `art` and `googletrans`) twice: first by `sudo pip3 install`-ing its dependencies straight into the operating system's Python, then, on a fresh VM, inside a project-local virtual environment that `uv sync` builds from `pyproject.toml`. Along the way you see why the OS refuses the first approach (PEP 668), what a venv physically is, what activation changes, and how `uv` picks a Python and writes a lockfile.

**Time needed** (estimate). Tutorial 0, once: 30-45 minutes (ac215-setup `README.md:12`). Each walkthrough: about 30 minutes, most of it creating the VM and waiting for apt. The follow-along video: about 30 minutes, in two parts (part 1: the VM and the manual install; part 2: venvs and uv). With the extras in §4 and the exercises, budget 2-2.5 hours.

**Prerequisites.**
- Tutorial 0 finished: a personal GCP account with the $300 free-trial credit, a first project (Project ID written down) and a budget alert; on your laptop, VS Code, Git, Docker Desktop and uv (ac215-setup `README.md:21-32`, simple-translate `README.md:20-21`).
- A web browser. Everything in L01 runs on the VM through the console's SSH-in-browser (`README.md:42-43`).
- Credentials: none. "You don't need GCP credentials (a service account) for this tutorial - that comes in a later one." (`README.md:23`).
- APIs: the Compute Engine API, which the console offers to enable the first time you open *VM instances*.

**What it costs.** A small e2 VM costs cents per hour (§2), so a one-hour lab is a few cents of free-trial credit. What adds up: a VM left running (it bills while idle), a *stopped* VM whose boot disk still bills, and a reserved static IP.

**Tear down, exactly** (`README.md:62`, `:98`):
1. After **each** walkthrough: Compute Engine → VM instances → select your instance → **Delete** (not Stop). The boot disk is deleted with the instance by default; that is a setting on the boot disk, chosen on the create form, so leave it as it is.
2. Check that *Compute Engine → VM instances* is empty and *Compute Engine → Disks* has no leftover disk. With the gcloud CLI on your laptop: `gcloud compute instances list` and `gcloud compute disks list`.
3. Nothing else: L01 creates no buckets, images, service accounts or keys.

<details>
<summary><b>Versions and sources this guide was checked against</b></summary>

- **README sections this lecture covers** (course site source `tutorials_demo.md:16-27`; lecture date Sep 3 per `_modules/week-01.md:5-7`), in `main`'s `README.md`:
  - `## 🛠️ Installing App on VM Manually`: `README.md:38-64`, GitHub anchor `#️-installing-app-on-vm-manually`, which the course site URL-encodes as `#%EF%B8%8F-installing-app-on-vm-manually` (`tutorials_demo.md:21`)
  - `## ⚡ Installing App on VM using UV`: `README.md:68-101`, anchor `#-installing-app-on-vm-using-uv` (`tutorials_demo.md:26`)
  - Context only: `README.md:1-34` (overview, prerequisites, contents). Sections 3-4 (Docker, `README.md:106-220`) belong to L02.
- **Primary repo:** `dlops-io/simple-translate`, branch `main`, commit `62f821bfe09fc1c2ecb0f14354b1f205777c0efa`, committed 2026-09-08 13:58:15 -0400 ("Handle translation exceptions with detailed error messages").
- **Comparison only:** `dlops-io/simple-translate`, branch `pipenv` (a tag named `pipenv` points at the same commit), commit `3a354d81f787a064aea3ab061359c9a1e223e4d5`, committed 2026-08-28 08:13:27 -0400. It is a separate root commit with no history shared with `main` (`git merge-base` finds nothing).
- **Tutorial 0:** `dlops-io/ac215-setup`, branch `main`, commit `61a7b9dd538e581a126117585db40c9e6b5d46b9`, committed 2026-05-25 19:33:32 -0400 ("Add Tutorial 0 Part A: Setup & Installs"). Part B (GCP Auth & Secrets) is linked later, from the first tutorial that needs credentials (ac215-setup `README.md:16-17`, `:246-247`).
- **Terminal captures (the strongest evidence in this guide).** Every README command of both walkthroughs, plus the extras in §4, was run on 2026-10-12 in fresh `debian:12` and `debian:13` containers given the baseline a Compute Engine Debian image already has (`python3`, `sudo`, `curl`, a user `student` with passwordless sudo). Versions seen: Debian 12 → Python 3.11.2, pip 23.0.1; Debian 13 → Python 3.13.5; the uv installer → uv 0.13.0; `uv sync` on Debian 12 → downloads CPython 3.15.0. Files: [`assets/terminal/`](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l01-vms-venvs/assets/terminal) (`debian12-part-a/`, `debian12-part-b/`, `debian13-part-b/`, `expected/`, with `capture.sh` and `run_steps.sh`); provenance in `ASSETS.md` in the same video folder.
- **An earlier scratch check, same day.** `pyproject.toml` was copied to a scratch directory and exercised with uv 0.11.32 (`uv lock`/`uv sync --no-build`, `--managed-python`, `--python 3.11/3.12`, `--locked` and `uv python pin`); no repository script, Dockerfile or `cli.py` was executed. It supplies the error messages for forced or pinned interpreters and for missing or stale lockfiles quoted in §3.6, §6 and §8. Where it disagrees with the captures (uv 0.11.32 downloaded CPython 3.14.6; uv 0.13.0 downloaded 3.15.0), this guide follows the captures.
- **googletrans 4.0.2** (third party), read as installed: `client.py`, `constants.py`, `urls.py`.
- **Colab notebooks:** none. The `colab/` folder has no L01 notebook. **Not used:** `simple-translate-aws` (the AWS track; out of scope).
- **Context repos cited in §7 only:** `llm-rag` main `e17a39f35bc07b440f573def480adaf4703f8b91` (2026-10-07), `mega-pipeline` main `c6bbc9ba88984e1234b68ccf5cdf7c00f7e9accc` (2026-09-27), `cheese-app-v0` main `cb6fb94576aa37bb0b94a8745e5e94e6a504f4bb` (2026-10-08).
- **Ed lesson:** its slides and notes were not accessible when these sources were checked; the course site source `tutorials_demo.md:16-27`, which links the two README sections above, was used instead.

</details>

## Command checklist

Commands in backticks are exactly as the README writes them (placeholders kept). Plain items are console clicks. Items marked *(extra)* are not in the README; they come from §4, where the real output of every captured command is shown. Your own username replaces `student`, and your VM name replaces `ac215-l01`.

### Tutorial 0 · Setup & Installs (`ac215-setup`, on your laptop, once)

*These run on your laptop and were not part of the 2026-10-12 captures.*

*1. Install a code editor (VS Code)* (ac215-setup `README.md:50-65`)
- [ ] Install VS Code and set line endings to `LF` (Settings → Text Editor → Files → Eol → `\n`).

*2. Install Git + create a GitHub account* (ac215-setup `README.md:69-82`)
- [ ] Install Git and create a free GitHub account.
- [ ] `git --version` — prints a version number (e.g. `git version 2.43.0`).

*3. Install Docker Desktop* (ac215-setup `README.md:86-108`)
- [ ] Install Docker Desktop and launch it (Windows: it needs WSL2).
- [ ] `docker run hello-world` — prints "Hello from Docker!"; Docker is used from L02 on.

*4. Install uv* (ac215-setup `README.md:112-136`)
- [ ] `curl -LsSf https://astral.sh/uv/install.sh | sh` — Mac / Linux; the same installer you run on the VM in walkthrough 2.
- [ ] `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"` — Windows (PowerShell) instead.
- [ ] `uv --version` — after closing and reopening the terminal; prints the installed version.

*5. Create a Google account for Colab* (ac215-setup `README.md:140-145`)
- [ ] Any Google account works.

*6. Set up Google Cloud Platform (GCP)* (ac215-setup `README.md:149-193`)
- [ ] Sign in at the [Cloud Console](https://console.cloud.google.com/) and accept the terms; create an individual account, not one under "Harvard Organization".
- [ ] Activate the $300 free trial at <https://cloud.google.com/free> (the course adds $50 of credits after the add/drop deadline).
- [ ] Create your first project (project dropdown → New Project → a name like `ac215` → Create), select it, and write down its **Project ID** (e.g. `ac215-456789`; tutorials call it `GCP_PROJECT`).

*7. Cost hygiene* (ac215-setup `README.md:197-212`)
- [ ] Billing → Budgets & alerts → Create budget, with a small amount (e.g. $25).

*8. (Optional) Install the gcloud CLI* (ac215-setup `README.md:216-222`)
- [ ] Install it from <https://cloud.google.com/sdk/docs/install>.
- [ ] `gcloud auth login` — signs the CLI in; needed only for the optional `gcloud` commands below.

*Getting the tutorial code* (ac215-setup `README.md:226-235`)
- [ ] `git clone https://github.com/dlops-io/simple-translate.git` — on your laptop (e.g. in `~/ac215/`), so you can read `cli.py` and `pyproject.toml` while you work on the VM.

### Before the README *(extra)*

- [ ] *(extra)* In the console, select your Tutorial 0 project and open *Compute Engine → VM instances*; click *Enable* if it asks to enable the Compute Engine API (Step 0).
- [ ] `gcloud services enable compute.googleapis.com` — *(extra)* the CLI equivalent, from your laptop.

### 🛠️ Installing App on VM Manually

*(`README.md:38-64`; video tracker A1-A10)*
- [ ] Create a VM Instance from [GCP](https://console.cloud.google.com/compute/instances) — the README gives no settings. Sensible ones: name `ac215-l01`, region us-central1 / zone us-central1-a, machine type e2-small, boot disk Debian 12 (Debian 13 works too), external IPv4 on (the default).
- [ ] `gcloud compute instances create ac215-l01 --zone=us-central1-a --machine-type=e2-small --image-family=debian-12 --image-project=debian-cloud` — *(extra)* the CLI alternative to the click, from your laptop.
- [ ] SSH into your newly created instance — click **SSH** in the instance row; click Authorize if it asks.
- [ ] `gcloud compute ssh ac215-l01 --zone=us-central1-a` — *(extra)* the CLI alternative to the SSH button.
- [ ] `cat /etc/os-release` — *(extra)* which OS you got: `Debian GNU/Linux 12 (bookworm)`.
- [ ] `python3 --version` — *(extra)* the system Python: `Python 3.11.2` on Debian 12, `Python 3.13.5` on Debian 13.
- [ ] `which python` — *(extra)* prints nothing: Debian has `python3` but no `python`.
- [ ] `sudo apt-get update` — downloads fresh package indexes; installs nothing.
- [ ] `sudo apt install git` — installs git; answer `Y` at "Do you want to continue? [Y/n]".
- [ ] `git clone https://github.com/dlops-io/simple-translate.git` — copies the repo into `~/simple-translate`.
- [ ] `cd simple-translate` — the prompt now ends in `~/simple-translate$`.
- [ ] `ls` — *(extra)* six files; no `uv.lock`, no `requirements.txt`, no `.python-version`.
- [ ] `git log -1 --oneline` — *(extra)* `62f821b Handle translation exceptions with detailed error messages`, or a newer commit.
- [ ] `sudo apt install python3-pip` — Debian's own pip for the system Python; answer `Y`.
- [ ] `pip3 --version` — *(extra)* `pip 23.0.1 from /usr/lib/python3/dist-packages/pip (python 3.11)` on Debian 12.
- [ ] `pip3 install googletrans==4.0.2 art` — *(extra)* meant to fail: `error: externally-managed-environment` (PEP 668).
- [ ] `python3 -c 'import sys; print("\n".join(sys.path))'` — *(extra)* the folders the system Python searches, in order.
- [ ] `sudo pip3 install --break-system-packages googletrans==4.0.2 art` — overrides the PEP 668 guard and installs 12 packages into `/usr/local/lib/python3.11/dist-packages`, shared by the whole OS.
  - Note: works as written on Debian 12 (captured: pip 23.0.1, exit 0). Debian 13 and Ubuntu 24.04 are PEP 668 images too, so they need the flag as well. On an older image whose pip is < 23.0.1 (e.g. Ubuntu 22.04's pip 22.0.2) it fails with `no such option: --break-system-packages`; such an image has no PEP 668 marker either, so run it without the flag: `sudo pip3 install googletrans==4.0.2 art`.
- [ ] `python3 -c 'import googletrans; print(googletrans.__file__)'` — *(extra)* `/usr/local/lib/python3.11/dist-packages/googletrans/__init__.py`.
- [ ] `python3 cli.py` — the AC215 banner, the parsed arguments, `Input: I love cheese`, `Output: Adoro il formaggio`.
  - Note: in the 2026-10-12 capture Google's unofficial endpoint answered this command and the next two with **HTTP 429**, so each ended in `RuntimeError: Translation request to Google Translate failed …`. Scroll up to the first exception: `Exception: Unexpected status code "429" …` means only the network said no; your install is fine. Wait and retry, try a VM in another region, or run it on your laptop. The same three runs from the uv venv succeeded a few minutes later.
- [ ] `python3 cli.py -t "Good morning. It is a good morning for cheese." -s "en" -d "es"` — Spanish: `Buen día. Es un buen día para el queso.`
- [ ] `python3 cli.py -t "Good afternoon. Would you like some cheese?" -s "en" -d "fr"` — French: `Bon après-midi. Veux-tu du fromage ?`
- [ ] `python3 cli.py --help` — *(extra)* lists the four options.
- [ ] `python3 cli.py -t hello -d xx` — *(extra)* a typo in the language code: the first exception is `ValueError: invalid destination language`, yet the last line still blames the network. Valid codes: the table at the bottom of the README (`README.md:225-288`; "Refer to language codes at the bottom of this page", `README.md:64`).
- [ ] Delete your VM when you're done. A running VM keeps charging even when idle. Go to [VM instances](https://console.cloud.google.com/compute/instances), select your instance, and click Delete.
- [ ] `gcloud compute instances delete ac215-l01 --zone=us-central1-a` — *(extra)* the CLI alternative to the Delete click.
- [ ] `gcloud compute instances list` and `gcloud compute disks list` — *(extra)* neither should still list `ac215-l01`.

### ⚡ Installing App on VM using UV

*(`README.md:68-101`; video tracker B1-B12)*
- [ ] Create a VM Instance from [GCP](https://console.cloud.google.com/compute/instances) — a fresh VM with the same settings. If the name is still taken, the old VM is still being deleted; wait a minute.
- [ ] SSH into your newly created instance
- [ ] `sudo apt-get update`
- [ ] `sudo apt install git`
- [ ] `git clone https://github.com/dlops-io/simple-translate.git`
- [ ] `cd simple-translate`
  - Note: this walkthrough never installs `python3-pip`; uv doesn't need it.
- [ ] `ls -a` — *(extra)* also shows `.git`, `.gitignore` and `.vscode`; still no `uv.lock`.
- [ ] `curl -LsSf https://astral.sh/uv/install.sh | sh` — downloads uv's official installer and runs it; `uv` and `uvx` land in `~/.local/bin` (uv 0.13.0 on 2026-10-12).
  - Note: the README tip (`README.md:81`) lists other ways, `pip install uv --break-system-packages` and, on macOS locally, `brew install uv`. On this VM the pip route fails with `pip: command not found` (no `python3-pip` here), and `brew` is for a Mac laptop. Use the curl line.
- [ ] `uv --version` — *(extra)* `uv: command not found`: this shell's `PATH` was set before `~/.local/bin` existed.
- [ ] `source $HOME/.local/bin/env` — puts `~/.local/bin` at the front of `PATH` in this shell. The README's other option, "Reload your shell", means opening a new SSH window, after which you `cd simple-translate` again.
- [ ] `uv --version` and `which uv` — *(extra)* `uv 0.13.0 (x86_64-unknown-linux-gnu)` and `/home/student/.local/bin/uv`.
- [ ] `uv python list --only-installed` — *(extra, not captured)* lists the Pythons uv already manages; predict what `uv sync` will use (exercise B2).
- [ ] `uv sync` — picks (or downloads) a Python ≥ 3.13, creates `.venv`, resolves the dependency tree into a new `uv.lock`, and installs it into `.venv`.
  - Note: works as written. Debian 12 downloads CPython 3.15.0 (35.9 MiB) and installs 11 packages; Debian 13 uses its own `/usr/bin/python3` (3.13.5) and installs 12. `` error: No `pyproject.toml` found in current directory or any parent directory `` means you are not in `simple-translate/`.
  - Note: the README tip (`README.md:87`) compares it with the classic `python -m venv .venv && pip install -r requirements.txt`. That line is a comparison, not a step: this repo has no `requirements.txt`.
- [ ] `ls -a` — *(extra)* `.venv` and `uv.lock` are new.
- [ ] `cat .venv/pyvenv.cfg` — *(extra)* `include-system-site-packages = false`, `prompt = app`.
- [ ] `ls -la .venv/bin` — *(extra)* `python` is a symlink, and there is no `pip`.
- [ ] `uv tree` — *(extra)* the resolved dependency tree.
- [ ] `head -30 uv.lock` — *(extra)* exact versions, download URLs and sha256 hashes.
- [ ] `git status` — *(extra)* `uv.lock` is untracked: it was made on this VM.
- [ ] `uv sync` — *(extra)* run it again: `Checked 11 packages in 0.14ms`; nothing changes.
- [ ] `which python` — *(extra)* still prints nothing before activation.
- [ ] `source .venv/bin/activate` — the prompt becomes `(app) student@ac215-l01:~/simple-translate$`.
  - Note: the README tip (`README.md:92`) says activation prepends `.venv/bin/` to `PATH`, sets `VIRTUAL_ENV=/path/to/.venv`, shows the prompt `(simple-translate) $` and defines `deactivate` (used below). On this repo the prompt is `(app)`: uv names it after `name = "app"` (`pyproject.toml:2`). And it has to be `source`, not `./activate`: the file isn't executable.
- [ ] `which python`, `python --version` and `which pip` — *(extra)* `/home/student/simple-translate/.venv/bin/python`; `Python 3.15.0` (Debian 13: `Python 3.13.5`); `which pip` prints nothing.
- [ ] `echo $PATH | tr ':' '\n' | head -3` — *(extra)* `.venv/bin` is now first.
- [ ] `python -c "import sys; print(sys.prefix)"` — *(extra)* prints the venv folder, `/home/<you>/simple-translate/.venv`.
- [ ] `python cli.py`
- [ ] `python cli.py -t "Good morning. It is a good morning for cheese." -s "en" -d "es"`
- [ ] `python cli.py -t "Good afternoon. Would you like some cheese?" -s "en" -d "fr"`
  - Note: these three succeeded in the 2026-10-12 capture with real translations (`Adoro il formaggio`, `Buen día. Es un buen día para el queso.`, `Bon après-midi. Veux-tu du fromage ?`). A 429 here means the same as in walkthrough 1. If you see the `Input:` line, your venv works.
- [ ] `uv run python cli.py` — *(extra)* runs the app in the venv without activation (uv syncs first if needed).
- [ ] `.venv/bin/python cli.py` — *(extra)* calls the venv's interpreter by its path; also no activation.
- [ ] `deactivate` — *(extra; named in the README tip at `README.md:92`)* undoes the activation; the prompt loses `(app)`.
- [ ] `python3 -c 'import googletrans'` — *(extra)* `ModuleNotFoundError`: on this VM the packages exist only in `.venv`.
- [ ] `uv run python -c 'import googletrans, sys; print(sys.prefix)'` — *(extra)* `/home/student/simple-translate/.venv`.
- [ ] Delete your VM when you're done. A running VM keeps charging even when idle. Go to [VM instances](https://console.cloud.google.com/compute/instances), select your instance, and click Delete.
- [ ] `gcloud compute instances list` and `gcloud compute disks list` — *(extra)* neither should still list `ac215-l01`.

### After the README *(extra, optional)*

*The `pipenv` branch, read-only, in your laptop clone* (§4 Part C)
- [ ] `git show origin/pipenv:Pipfile` — *(extra)* the pipenv equivalent of `pyproject.toml`.
- [ ] `git show origin/pipenv:README.md | sed -n 22,35p` — *(extra)* the old pipenv walkthrough (`pipenv install`, `pipenv shell`).

---

## 1. What you build

You rent a Linux computer in Google Cloud (a Compute Engine **VM**), SSH into it from the browser, clone a 72-line Python command-line app (`cli.py`), and get it running two ways.

- **Walkthrough A** is the "quick and dirty" way. You `sudo pip3 install` the two dependencies, `googletrans` and `art`, straight into the operating system's own Python, and you have to pass `--break-system-packages` to get past Debian/Ubuntu's PEP 668 guard.
- **Walkthrough B** is the clean way. You install `uv`, and `uv sync` reads `pyproject.toml`, finds or downloads a Python ≥ 3.13, creates a project-local **virtual environment** in `.venv/`, resolves the full dependency tree into `uv.lock`, and installs those exact versions into `.venv`. On 2026-10-12 a Debian 12 VM got a downloaded CPython 3.15.0, while a Debian 13 VM used its own Python 3.13.5. You activate the venv and run the same commands.

The app sends your text to Google's *unofficial* translate endpoint over HTTPS and prints an ASCII-art banner, the parsed arguments, the input and the translation. There are no containers, open ports, volumes, service accounts or secrets in this lecture. When you finish you **delete the VM**.

```
 YOUR LAPTOP                                GOOGLE CLOUD  (your project, one zone e.g. us-central1-a)
 +---------------------------+              +---------------------------------------------------------------+
 | Browser                   |  HTTPS       |  Compute Engine VM  (e2-*, Debian/Ubuntu boot disk)           |
 |  console.cloud.google.com |------------->|  vCPU + RAM (billed while RUNNING), boot disk (billed while   |
 |  /compute/instances       |  "SSH" btn   |  it EXISTS), ephemeral external IPv4                          |
 |  [Create] [SSH] [Delete]  |=============>|                                                               |
 +---------------------------+  (tcp/22,    |  /home/<you>/simple-translate/      <- git clone              |
                                 in-browser |     cli.py   pyproject.toml   README.md   Dockerfile.txt ...  |
                                 terminal)  |     uv.lock   (created by uv sync - NOT in the repo)          |
                                            |     .venv/    (created by uv sync)                            |
                                            |                                                               |
                                            |  Walkthrough A (manual)          Walkthrough B (uv)            |
                                            |  $ python3 cli.py ...           (app) $ python cli.py ...     |
                                            |        |                                |                     |
                                            |        v                                v                     |
                                            |  /usr/bin/python3 (OS Python)    .venv/bin/python -> some     |
                                            |  + /usr/local/lib/python3.X/      CPython >= 3.13 (system or  |
                                            |    dist-packages  <- sudo pip3    ~/.local/share/uv/python/)  |
                                            |    (shared with the whole OS)     + .venv/lib/python3.X/      |
                                            |                                     site-packages <- uv sync  |
                                            +-------------------------------+-------------------------------+
                                                                            | outbound HTTPS only; no inbound
                                                                            | ports are opened by this tutorial
      +------------------+------------------+---------------------+---------+---------------+-----------------------------+
      v                  v                  v                     v                         v                             v
 deb.debian.org     github.com         pypi.org +              astral.sh/uv/install.sh   python-build-standalone     translate.googleapis.com
 (apt-get update,   (git clone          files.pythonhosted.org (uv + uvx binaries ->     (managed CPython download,  /translate_a/single?client=gtx
  git, python3-pip)  dlops-io/          (googletrans, art,      ~/.local/bin)             only if no Python >= 3.13   (unofficial, no API key;
                     simple-translate)   httpx, h2, ...)                                  is installed)               may rate-limit cloud IPs)

 Call chain for one translation:
   shell -> python cli.py -t "..." -s en -d es
         -> argparse Namespace -> asyncio.run(main(args))           (cli.py:72, :12)
         -> googletrans.Translator(raise_exception=True)            (cli.py:25)  [httpx.AsyncClient, HTTP/2]
         -> GET https://translate.googleapis.com/translate_a/single (googletrans urls.py:7, constants.py:3)
         <- JSON -> result.text -> print("Output:", ...)            (cli.py:39)
```

---

## 2. Prerequisites and costs

**Accounts**
- A Google Cloud project with **billing enabled**, set up in "Tutorial 0 - Setup & Installs" (`README.md:20-21`, https://github.com/dlops-io/ac215-setup).
  - Tutorial 0 has you create a personal GCP account, "not under 'Harvard Organization'" (ac215-setup `README.md:157`), activate the **$300 free trial** (`:164-166`; Google asks for a card but won't charge during the trial, `:168-170`), create a first project and write down its Project ID (`:177-191`), and set a **budget alert** (`:201-202`). The course adds $50 of credits after the add/drop deadline (`:172-173`).
- No GitHub login is needed because the repo is public and cloned over HTTPS (`README.md:50`).
- No Docker Hub account is needed until L02.

**Local installs**
- For L01 you need only a web browser: everything runs on the VM through the console's in-browser SSH (`README.md:42-43`).
- Tutorial 0 also installs VS Code (line endings `LF`), Git, Docker Desktop and uv on your laptop (ac215-setup `README.md:50-136`). uv comes from the same unversioned installer the VM uses, so your laptop has whatever uv was newest the day you installed it.
- Optional: the `gcloud` CLI, if you'd rather drive the VM from your terminal. Tutorial 0 lists it as optional (ac215-setup `README.md:216-222`). The commands are below; they aren't in the README.

**GCP APIs**
- **Compute Engine API** (`compute.googleapis.com`). The console asks you to enable it the first time you open *VM instances*. From the CLI: `gcloud services enable compute.googleapis.com`. Nothing else is needed.

**Service accounts / keys / secrets / env vars**
- **None.** The README says so: "You don't need GCP credentials (a service account) for this tutorial - that comes in a later one." (`README.md:23`).
- `cli.py` reads no environment variables. `grep -n "os.environ\|getenv" cli.py` finds nothing.
- Console-created VMs get the Compute Engine default service account attached, but this code never uses it.

**Where the code expects things (paths)**

| Thing | Where | Set by |
|---|---|---|
| Repo checkout | `~/simple-translate` (your SSH user's home) | `git clone` + `cd simple-translate` (`README.md:50-51`, `:76-77`) |
| Working directory when you run the app | repo root (you run `python cli.py`; it has no other path assumptions; `-f FILE` is resolved relative to the cwd, `cli.py:19-21`) | you |
| Walkthrough A packages | `/usr/local/lib/python3.X/dist-packages/` (Debian's location for `sudo pip`; `python3.11` on Debian 12, captured) | `sudo pip3 install ...` (`README.md:53`) |
| `uv` / `uvx` binaries | `~/.local/bin/` | uv installer (`README.md:78`); `source $HOME/.local/bin/env` puts that directory on `PATH` (`README.md:83`) |
| Project definition | `./pyproject.toml` (`uv sync` searches the current directory and its parents) | repo |
| Lockfile | `./uv.lock`, **written on your VM by the first `uv sync`**; the repo has none | `uv sync` |
| Virtual environment | `./.venv/` (13 MB in the captures), which contains its own `.gitignore` holding `*` so git ignores it | `uv sync` |
| uv-managed Python (only if needed) | `~/.local/share/uv/python/` (116 MB after the Debian 12 download: `cpython-3.15.0-linux-x86_64-gnu` plus the minor-version link `cpython-3.15-linux-x86_64-gnu`) | `uv sync` (automatic download) |
| uv download cache | `~/.cache/uv/` | uv |

**Billable resources and how to shut them down**
- **VM vCPU/RAM:** billed per second while the VM is *running*, including when it sits idle. Rough on-demand list prices in us-central1 (approximate, not checked against the current price list, so look at the estimate panel on the console's create page): e2-micro ≈ $0.008/h, e2-small ≈ $0.017/h, e2-medium ≈ $0.034/h. A one-hour lab costs a few cents. e2-micro in us-west1/us-central1/us-east1 falls under GCP's always-free tier (one instance per month, standard persistent disk).
- **Boot disk (persistent disk):** billed per GB-month for as long as the disk *exists*, even while the VM is stopped (the console default is about 10 GB). It is a separate, network-attached disk, which is why it outlives a stop.
- **External IPv4 address:** billed per hour while assigned (around $0.005/h).
- **Network egress:** negligible here (a few MB).
- **Shut-down procedure:** the README says to delete the VM after *each* walkthrough (`README.md:62`, `:98`): "Go to VM instances, select your instance, and click Delete."
  - The boot disk is deleted with the instance by default. That is a property of the boot disk, set on the create form (Boot disk → deletion rule), not a box in the Delete dialog; if you changed it, the disk stays behind.
  - Then check:
    - *Compute Engine → VM instances* is empty
    - *Compute Engine → Disks* has no orphaned disk
    - CLI alternatives (not in the README): `gcloud compute instances list`, `gcloud compute disks list`, and `gcloud compute instances delete <name> --zone <zone>`
- **Stopping isn't deleting:** a *stopped* VM still pays for its disk (and for a static IP, if you reserved one). Tutorial 0 says the same: "Stop ≠ delete" (ac215-setup `README.md:205-206`).
- **Optional `gcloud` equivalents** (a suggestion, not from the README):
  ```bash
  gcloud compute instances create ac215-l01 --zone=us-central1-a --machine-type=e2-small \
      --image-family=debian-12 --image-project=debian-cloud
  gcloud compute ssh ac215-l01 --zone=us-central1-a
  gcloud compute instances delete ac215-l01 --zone=us-central1-a
  ```

---

## 3. Concepts this tutorial teaches

### 3.1 Virtual machine (VM)
- **Explanation.** A VM is a complete computer made of software:
  - virtual CPUs, RAM, a virtual disk and a network card, carved out of a physical server by a **hypervisor**. On Compute Engine the vCPUs and memory come from that server, while the boot disk is a persistent disk on Google's storage network, attached over the network.
  - its own operating system kernel on top (Debian, Ubuntu)
  - in GCP a VM is a *Compute Engine instance*, defined by a **machine type** (vCPU/RAM, e.g. e2-small), a **zone** (where it physically lives), a **boot disk image** (which OS it starts with) and a **network interface** (internal IP, optionally an external IP)

  You get root via `sudo`, and you pay by the second.
- **Mental model.** It's a disposable rented Linux box: it starts empty, you set it up, and you throw it away. Whatever you do inside can't hurt your laptop or anyone else's VM.
- **Analogy.** A hotel room in a big building. The building (physical server) and the front desk (hypervisor) are shared, but your room has its own lock, furniture and bathroom (kernel, disk, OS), and checkout (Delete) wipes it.
- **Common misconception.** "Stopping the VM stops all charges." Stopping only ends the CPU/RAM billing; the disk keeps billing until you delete it.
  A second one is "a VM is basically a container." A VM boots its own kernel; containers (L02) share the host's kernel.

### 3.2 The system Python and PEP 668 ("externally managed")
- **Explanation.**
  - Debian/Ubuntu ship a Python (`/usr/bin/python3`) that **the OS itself** relies on, and `apt` owns its packages in `/usr/lib/python3/dist-packages`.
  - Since PEP 668, the distribution drops a marker file `EXTERNALLY-MANAGED` next to the stdlib, and pip ≥ 23 refuses to install into that interpreter. Debian 12, Debian 13 and Ubuntu 24.04 all ship it (older images such as Ubuntu 22.04 and Debian 11 don't; §6 #2). The captured refusal on Debian 12 starts `error: externally-managed-environment` and suggests `apt install python3-xyz`, a venv, or `pipx` (`debian12-part-a/07-pip-refused.txt`, shown in §4 Step 6).
  - `--break-system-packages` overrides the refusal.
  - Run with `sudo`, pip writes into `/usr/local/lib/python3.X/dist-packages`, which comes *before* apt's directory on `sys.path` (captured on Debian 12: `/usr/local/lib/python3.11/dist-packages`, then `/usr/lib/python3/dist-packages`). Whenever pip needs a version that apt's copy doesn't satisfy, it puts a second copy on that higher shelf, and that copy silently shadows the apt one that some system tool depends on. Example: Debian 12's apt package of httpx is 0.23.3, while googletrans needs `httpx[http2]>=0.27.2`; if apt's httpx were installed, pip's 0.28.1 would hide it from every program that runs on the system Python. (If apt's copy already satisfies the requirement, pip prints `Requirement already satisfied` and adds nothing.) `README.md:55-56` explains the flag.
- **Mental model.** The system Python is a shared kitchen: the OS cooks in it, and if you rearrange the spice rack, the OS's recipes may break.
- **Analogy.** The landlord's fuse box: you *can* rewire it ("break system packages"), but it's not your building.
- **Common misconception.** "`--break-system-packages` only affects this project." It changes the interpreter every user and every system script on the machine shares.

### 3.3 Virtual environment (venv)
- **Explanation.** A venv is just a directory with these parts:
  1. `bin/python`: a **symlink** to a real interpreter. Captured on 2026-10-12: on Debian 12, `.venv/bin/python -> /home/student/.local/share/uv/python/cpython-3.15-linux-x86_64-gnu/bin/python3.15` (the Python uv downloaded); on Debian 13, `.venv/bin/python -> /usr/bin/python3` (the system one).
  2. Its own `lib/python3.X/site-packages/`, empty when uv creates it. (The classic `python3 -m venv` seeds `pip` into it.)
  3. `pyvenv.cfg`, which tells the interpreter "you are a venv; use *my* site-packages", with `include-system-site-packages = false`.

  When Python starts from `.venv/bin/python`, it builds `sys.path` with the venv's site-packages instead of the system one. Packages installed in the venv are invisible to the OS Python, and vice versa.
  - Debian 13 shows the switch most cleanly, because its venv links to the same `/usr/bin/python3`: the captured `sys.path` keeps `/usr/lib/python313.zip`, `/usr/lib/python3.13` and `/usr/lib/python3.13/lib-dynload`, then has only `/home/student/simple-translate/.venv/lib/python3.13/site-packages`. Both system dist-packages folders are gone.
  - On Debian 12 the venv runs a *different* interpreter (uv's 3.15.0), so its standard library comes from `~/.local/share/uv/python/cpython-3.15.0-linux-x86_64-gnu/lib/python3.15`, again followed only by the venv's site-packages.
- **Mental model.** Same engine, different toolbox: the interpreter is shared, the installed packages aren't.
- **Analogy.** A project-specific backpack. You don't empty the household toolbox into it; you pack exactly what this job needs.
- **Common misconception.** "A venv contains its own copy of Python." Usually it's a symlink (verified in both captures).
  A second one is "a venv isolates everything." It isolates *Python packages* only: not system libraries (e.g. `libpq`), not the OS, not GPU drivers. That's what containers and VMs are for.

### 3.4 Activation is just `PATH` (and a prompt)
- **Explanation.** `source .venv/bin/activate` runs a shell script *in your current shell*. It:
  - saves the old `PATH`, then prepends the venv's `bin` (generated `activate:97-99`; captured lines 97-98 are `_OLD_VIRTUAL_PATH="$PATH"` and `PATH="$VIRTUAL_ENV/bin:$PATH"`)
  - exports `VIRTUAL_ENV` (line 81 hard-codes it: `VIRTUAL_ENV='/home/student/simple-translate/.venv'`)
  - sets `VIRTUAL_ENV_PROMPT` to the venv's prompt name. For this repo that's `app` (line 102, `VIRTUAL_ENV_PROMPT="app"`), taken from `pyproject.toml:2`.
  - prefixes `PS1` so the prompt reads `(app) $`
  - defines `deactivate`

  Nothing else changes. You can skip activation entirely: `.venv/bin/python cli.py` or `uv run python cli.py` give the same result.
- **Mental model.** When you type `python`, the shell walks `PATH` from left to right and runs the first match. Activation puts `.venv/bin` at the front of the line. Captured before activation, `PATH` was `/home/student/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/local/games:/usr/games` and `which python` found nothing; after it, the first entry is `/home/student/simple-translate/.venv/bin`.
- **Analogy.** Changing which drawer you grab a screwdriver from first. The screwdrivers themselves don't move.
- **Common misconception.** "Activation installs or loads packages." It doesn't; it only changes lookup order.
  Another is "`./.venv/bin/activate` works too." The file isn't executable (`-rw-r--r--` in the Debian 12 capture, `-rw-rw-r--` in the Debian 13 one), and even run with `bash`, it would modify a *child* shell that exits immediately. That's why the README says `source` (`README.md:92`).
  A third is "activation is permanent." It lives in one shell: a new or reconnected SSH window starts without it. And while it is active, even `python3` is the venv's (`.venv/bin/python3 -> python`), so `deactivate` before testing the system Python.

### 3.5 Declared vs resolved dependencies; the lockfile
- **Explanation.**
  - `pyproject.toml` states **intent**: "I need `art>=6.5` and `googletrans==4.0.2`" (`pyproject.toml:7-10`).
  - Those two direct dependencies drag in **transitive** ones (`httpx[http2]` → `httpcore`, `h2`, `hpack`, `hyperframe`, `anyio`, `idna`, `certifi`, `h11`, `typing-extensions`).
  - The **resolver** picks one concrete version for each and writes the result, with sha256 hashes and download URLs, to **`uv.lock`**.
  - On 2026-10-12, 2 declared dependencies resolved to **13 lock entries** (`grep -c '^\[\[package\]\]' uv.lock` printed `13`): 12 packages plus the project itself, recorded as `source = { virtual = "." }`.
  - The lock is **universal**: it covers every Python that `requires-python = ">=3.13"` allows, not just the one on your VM. That is why the counts differ while the lock is the same:
    - Debian 12, CPython 3.15.0: `Resolved 13 packages`, `Installed 11 packages`. `anyio` needs `typing-extensions` only with `marker = "python_full_version < '3.15'"`, so it is skipped.
    - Debian 13, CPython 3.13.5: `Resolved 13 packages`, `Installed 12 packages`, including `typing-extensions==4.16.0`.
    - Walkthrough A, pip on Python 3.11: 12 packages, `typing_extensions-4.16.0` among them.
  - Anyone who runs `uv sync` *with that lockfile* gets byte-identical packages. `uv sync --locked` refuses to proceed if the lock is missing or stale; `--frozen` installs the lock as-is without checking it.
- **Mental model.** `pyproject.toml` is the shopping list ("some milk"); `uv.lock` is the receipt ("Brand X, 1 L, batch #…").
- **Analogy.** A recipe ("a cup of flour") vs a photo of the exact bags used.
- **Common misconception.** "Pinning `googletrans==4.0.2` makes the install reproducible." The *transitive* dependencies (httpx, certifi…) still float; only the lockfile freezes them.
  This repo also **doesn't commit a `uv.lock`** (`git ls-files` has none, `git log --all -- uv.lock` is empty), even though `README.md:70` says it "pins exact versions so the next person gets the same setup". Every student's first `uv sync` creates a fresh lock from whatever is newest on PyPI that day.

### 3.6 Python version: constraint vs pin
- **Explanation.**
  - `requires-python = ">=3.13"` (`pyproject.toml:6`) is a **constraint**, not a pin.
  - uv first looks for a compatible interpreter it already has: its own managed installs, then the system's.
  - If none is found, it **downloads** a standalone CPython build into `~/.local/share/uv/python/`: the newest stable release matching `>=3.13`, not 3.13. On 2026-10-12, uv 0.13.0 downloaded **CPython 3.15.0** on Debian 12 (`Downloading cpython-3.15.0-linux-x86_64-gnu (download) (35.9MiB)`; 116 MB on disk). The answer moves with time and with the uv version: the same day, uv 0.11.32 in a scratch check downloaded 3.14.6, and before 3.15 was released this command gave 3.14.x.
  - A real pin is a `.python-version` file written by `uv python pin 3.X`. This repo has none. `uv python pin 3.13` pins the 3.13 *series* (any 3.13.x); `uv python pin 3.13.5` pins one release.
  - Which Python you end up with therefore depends on the VM image:
    - Debian 12 ships 3.11.2, so uv downloads one (3.15.0 on 2026-10-12, captured)
    - Ubuntu 24.04 ships 3.12, so uv downloads one too
    - Debian 13 ships 3.13.5, inside the range, so uv uses `/usr/bin/python3` directly (captured: `Using CPython 3.13.5 interpreter at: /usr/bin/python3`)
- **Mental model.** A number line of Python versions with a shaded interval `[3.13, ∞)`. uv walks the interpreters it can find and keeps the first one inside the interval. If none qualifies, it fetches the newest stable release in the interval.
- **Analogy.** "Any flight that lands after 13:00." Without a specific booking (the pin), you get whatever the system finds.
- **Common misconception.** "uv uses the Python that came with the VM." Only when it satisfies `requires-python`. Otherwise uv quietly downloads another one, 35.9 MiB in the Debian 12 capture.
  Another is "requires-python is ignored." Force an older interpreter and uv errors out:
  ``error: The requested interpreter resolved to Python 3.11.17, which is incompatible with the project's Python requirement: `>=3.13` (from `project.requires-python`)`` (scratch check, uv 0.11.32).

### 3.7 uv as one tool instead of five (and how pipenv differs)
- **Explanation.** `uv` (Astral, written in Rust) replaces:
  - `python -m venv` (create a venv)
  - `pip` (install)
  - `pip-tools` / `pipenv lock` (resolve and lock)
  - `pyenv` (install Pythons)
  - `pipx` (tools)

  It keeps a global cache (`~/.cache/uv`) and hard-links or copies wheels from it, which is why re-syncs take milliseconds (captured: `Checked 11 packages in 0.14ms`). A **uv venv has no `pip` inside it**: the captured `.venv/bin` has `python`, `python3`, `python3.15` (Debian 13: `python3.13`), the `activate*` scripts and the packages' launchers `art`, `httpx`, `idna` and `translate`, but no `pip`. To add packages you use `uv add <pkg>`, which edits `pyproject.toml`, re-locks and syncs, or `uv pip install`.

  The **`pipenv` branch** shows the older way:

  | | uv (`main`) | pipenv (`pipenv` branch) |
  |---|---|---|
  | Project file | `pyproject.toml` | `Pipfile` |
  | Lockfile | `uv.lock` | `Pipfile.lock` (committed, with sha256 hashes) |
  | Python version | `requires-python` (constraint); uv can download Pythons itself | `[requires] python_version = "3.11"` (`origin/pipenv:Pipfile:12-13`); relies on the system or pyenv |
  | Where the venv lives | `.venv` in the project | `~/.local/share/virtualenvs/<name>-<hash>` by default |
  | Getting into it | `source .venv/bin/activate` modifies the current shell | `pipenv shell` spawns a *subshell*; you `exit` to leave |
  | Install command | `uv sync` | `pipenv install` (VM, `origin/pipenv:README.md:30`) or `pipenv sync` (Docker, `origin/pipenv:Dockerfile:20`) |
- **Mental model.** uv is a single fast binary that owns the whole "which Python + which packages" problem.
- **Common misconception.** "`pip install` inside an activated uv venv installs into the venv." `pip` isn't in the venv. You get the system `pip`, which then hits PEP 668, or "command not found" on a VM where `python3-pip` was never installed (captured: `which pip` prints nothing on the walkthrough B VM).

### 3.8 Why both: layers of isolation
- **Explanation.** Each layer isolates one kind of thing:
  - A **VM** isolates *hardware and OS*: a whole machine you can wreck and delete.
  - A **venv** isolates *Python packages* within one OS: two projects on the same VM can need different `httpx` versions. (The `pipenv` branch's `Pipfile.lock` pins `httpx` 0.13.3, while `main`'s `uv sync` installed 0.28.1: two versions of the same app that could not share one system Python, but can live in two venvs.)
  - **Containers** (L02) isolate a *filesystem + process tree* that shares the host kernel, and ship the venv along with the OS libraries.

  In this course you'll nest all three: a VM runs Docker, and the container runs a uv venv. `Dockerfile.txt:24` runs `uv sync` *inside* an image.
- **Mental model.** Russian dolls: VM ⊃ (container ⊃) venv.
- **Common misconception.** "If I use a VM I don't need a venv" (or the reverse). They solve different problems. A VM gives you a clean machine, and a venv keeps you from polluting the machine's Python so it stays clean.

---

## 4. Step-by-step walkthrough

Steps follow the README order. Commands in code spans are verbatim from the README unless marked *(extra)*. The video's top-left tracker numbers the README bullets A1-A10 and B1-B12; those numbers are given in brackets.

**About the outputs below.** They are real, trimmed (first and last lines, with `…` between) from the 2026-10-12 captures in `assets/terminal/` (file names given with each block; `[exit N]` lines omitted). The captures ran in fresh Debian containers with a Compute Engine image's baseline, so on a real VM:
- `sudo apt-get update` lists a few more sources (Google's own package repositories), and `apt install` pulls in fewer packages, because a GCP image already has more installed.
- apt prints ` Done` after `Reading package lists...` and the next two lines; without a terminal the capture lost it. The capture also answered apt's `[Y/n]` prompt automatically (`yes | sudo apt install …`); you type `Y`.
- A missing command reads `-bash: uv: command not found` in your login shell, not `bash: line 1: …`.
- `sudo pip3` may print `Requirement already satisfied` for a package apt already had, so your count can be below 12.
- Your username and VM name replace `student` and `ac215-l01`, and versions may be newer than these.

### Part 0: before you start

**Step 0. Project, billing, Compute Engine API.**
- **Action:** in the console, pick your AC215 project and open *Compute Engine → VM instances* (https://console.cloud.google.com/compute/instances). Click *Enable* if it asks to enable the Compute Engine API.
- **Under the hood:** this turns on `compute.googleapis.com` for the project; it can take a minute.
- **Checkpoint:** the VM instances page loads with a "Create instance" button.
- **If it fails:** "Billing account required" means you need to link billing (or the course credit) to the project.

### Part A: 🛠️ Installing App on VM Manually (`README.md:38-64`)

**Step 1. Create a VM** [A1] (`README.md:42`: "Create a VM Instance from [GCP](https://console.cloud.google.com/compute/instances)").
- **Action:** *Create instance*. The README gives no settings. Sensible choices:
  - a name, e.g. `ac215-l01`
  - region us-central1, any zone (e.g. us-central1-a)
  - machine type e2-small (e2-micro also works)
  - boot disk: Debian 12 (bookworm), the image the captures used; Debian 13 also works and changes which Python uv uses (Step 17)
  - **keep an external IPv4** (the default). Without it, and without extra network setup such as Cloud NAT, the VM can't reach the internet and every download below hangs.
- **Under the hood:** GCP allocates a slice of a host, copies the image onto a new persistent disk, boots it, and runs the guest agent, which sets up users and SSH keys.
- **Checkpoint:** a green check next to the instance and an External IP shown.
- **If it fails:**
  - "Quota exceeded": pick another region or a smaller machine type
  - "Compute Engine API has not been used": go back to Step 0

**Step 2. SSH in** [A2] (`README.md:43`).
- **Action:** click **SSH** in the instance row. The first time, it may ask you to authorize the connection: click Authorize.
- **Under the hood:** the browser SSH client pushes a temporary key (via OS Login or instance metadata) and opens a terminal as a Linux user derived from your Google account. Your home is `/home/<you>`.
- **Checkpoint:** a prompt like `<you>@ac215-l01:~$`.
- *(extra, recommended)* Look around: `cat /etc/os-release`, `python3 --version`, `which python` (on Debian this prints nothing: there's no `python` command). Captured, as one line:
  ```
  $ cat /etc/os-release | head -4; python3 --version; which python; echo which-python-exit:$?
  PRETTY_NAME="Debian GNU/Linux 12 (bookworm)"
  NAME="Debian GNU/Linux"
  VERSION_ID="12"
  VERSION="12 (bookworm)"
  Python 3.11.2
  which-python-exit:1
  ```
  On Debian 13 the same line prints `PRETTY_NAME="Debian GNU/Linux 13 (trixie)"` and `Python 3.13.5` (`debian13-part-b/00-os.txt`). Remember both numbers for Step 17.
- **If it fails:**
  - "Connection via Cloud Identity-Aware Proxy failed" or a timeout usually means a firewall rule for tcp:22 is missing in a non-default VPC. The default VPC has `default-allow-ssh`.

**Step 3. Update package lists** [A3] (`README.md:44`): `sudo apt-get update`
- **Under the hood:** downloads fresh package indexes from the Debian mirrors. Nothing is upgraded yet.
- `README.md:47-48` explains `apt-get` (scriptable) vs `apt` (interactive).
- **Checkpoint:** ends with "Reading package lists... Done". Captured (`debian12-part-a/01-apt-update.txt`):
  ```
  $ sudo apt-get update
  Get:1 https://deb.debian.org/debian bookworm InRelease [151 kB]
  …
  Fetched 9388 kB in 2s (4651 kB/s)
  Reading package lists...
  ```
- **If it fails / hangs:** the VM has no outbound internet. Check that it has an external IP (or Cloud NAT).

**Step 4. Install Git** [A4] (`README.md:45`): `sudo apt install git`
- **Checkpoint:** answer `Y` at "Do you want to continue? [Y/n]" (add `-y` to skip the prompt); `git --version` then prints a version. (Some images already have git; apt then says "git is already the newest version".) Captured (`debian12-part-a/02-git.txt`; the list is longer in a container than on a VM):
  ```
  $ sudo apt install git
  Reading package lists...
  Building dependency tree...
  Reading state information...
  The following additional packages will be installed:
  …
  1 upgraded, 25 newly installed, 0 to remove and 0 not upgraded.
  Need to get 21.7 MB of archives.
  After this operation, 109 MB of additional disk space will be used.
  Do you want to continue? [Y/n]
  …
  Setting up git (1:2.39.5-0+deb12u3) ...
  Processing triggers for libc-bin (2.36-9+deb12u14) ...
  ```
  Debian 13's apt uses a newer layout ("Installing:" / "Installing dependencies:") and installs git 1:2.47.3 (`debian13-part-b/02-git.txt`).

**Step 5. Clone and enter the repo** [A5, A6] (`README.md:50-51`): `git clone https://github.com/dlops-io/simple-translate.git` then `cd simple-translate`
- **Checkpoint:** the prompt ends in `~/simple-translate$`. `ls` shows `Dockerfile.txt  README.md  cli.py  docker-build-push.sh  docker-shell.sh  pyproject.toml` (`ls -a` also shows `.gitignore .vscode .git`). *(extra)* `git log -1 --oneline` shows `62f821b Handle translation exceptions with detailed error messages`, or a newer commit if the repo has changed since. Captured:
  ```
  $ git clone https://github.com/dlops-io/simple-translate.git
  Cloning into 'simple-translate'...
  $ ls
  Dockerfile.txt
  README.md
  cli.py
  docker-build-push.sh
  docker-shell.sh
  pyproject.toml
  ```
- Note: **no `uv.lock`, no `.python-version`, no `requirements.txt`.**

**Step 6. Install pip for the system Python** [A7] (`README.md:52`): `sudo apt install python3-pip`
- **Under the hood:** apt installs Debian's pip package (plus `python3-setuptools`, `python3-wheel`, and so on) for `/usr/bin/python3`. In the container it pulled in 107 new packages (`0 upgraded, 107 newly installed`), including `build-essential`; a VM image usually needs fewer.
- **Checkpoint:** `pip3 --version` prints something like `pip 23.x from /usr/lib/python3/dist-packages/pip (python 3.11)` on Debian 12. Captured:
  ```
  $ pip3 --version
  pip 23.0.1 from /usr/lib/python3/dist-packages/pip (python 3.11)
  ```
- *(extra, highly instructive)* Try the install **without** the flag first: `pip3 install googletrans==4.0.2 art`. You get `error: externally-managed-environment`, followed by the text of `/usr/lib/python3.X/EXTERNALLY-MANAGED` (Ubuntu 24.04's marker file begins with the same "To install Python packages system-wide, try apt install python3-xyz …" text). Captured on Debian 12 (`debian12-part-a/07-pip-refused.txt`, complete):
  ```
  $ pip3 install googletrans==4.0.2 art
  error: externally-managed-environment

  × This environment is externally managed
  ╰─> To install Python packages system-wide, try apt install
      python3-xyz, where xyz is the package you are trying to
      install.

      If you wish to install a non-Debian-packaged Python package,
      create a virtual environment using python3 -m venv path/to/venv.
      Then use path/to/venv/bin/python and path/to/venv/bin/pip. Make
      sure you have python3-full installed.

      If you wish to install a non-Debian packaged Python application,
      it may be easiest to use pipx install xyz, which will manage a
      virtual environment for you. Make sure you have pipx installed.

      See /usr/share/doc/python3.11/README.venv for more information.

  note: If you believe this is a mistake, please contact your Python installation or OS distribution provider. You can override this, at the risk of breaking your Python installation or OS, by passing --break-system-packages.
  hint: See PEP 668 for the detailed specification.
  ```
- *(extra)* Where will Python look for `import googletrans`? The folders on `sys.path`, searched top to bottom (`debian12-part-a/15-syspath.txt`; the empty first line is the current folder):
  ```
  $ python3 -c 'import sys; print("\n".join(sys.path))'

  /usr/lib/python311.zip
  /usr/lib/python3.11
  /usr/lib/python3.11/lib-dynload
  /usr/local/lib/python3.11/dist-packages
  /usr/lib/python3/dist-packages
  ```

**Step 7. Install the app's packages into the OS Python** [A8] (`README.md:53`): `sudo pip3 install --break-system-packages googletrans==4.0.2 art`
- **Under the hood:**
  - pip runs as root, skips the PEP 668 check (`README.md:55-56`), and resolves `googletrans==4.0.2` → `httpx[http2]>=0.27.2` plus its tree, and `art` (unpinned here, so the latest).
  - It installs everything into `/usr/local/lib/python3.X/dist-packages`, which every user and every system script on this VM shares, and which sits above apt's folder on `sys.path` (Step 6).
- **Checkpoint:**
  - "Successfully installed anyio-… art-… certifi-… googletrans-4.0.2 h11-… h2-… hpack-… httpcore-… httpx-… hyperframe-… idna-…" (exact list and versions vary), plus a **WARNING about running pip as the 'root' user**. Captured (`debian12-part-a/08-pip-break.txt`): 2 requested, 12 installed.
    ```
    $ sudo pip3 install --break-system-packages googletrans==4.0.2 art
    Collecting googletrans==4.0.2
      Downloading googletrans-4.0.2-py3-none-any.whl (18 kB)
    Collecting art
      Downloading art-6.5-py3-none-any.whl (610 kB)
    …
    Collecting httpx[http2]>=0.27.2
    …
    Installing collected packages: typing_extensions, idna, hyperframe, hpack, h11, certifi, art, httpcore, h2, anyio, httpx, googletrans
    Successfully installed anyio-4.15.1 art-6.5 certifi-2026.7.22 googletrans-4.0.2 h11-0.16.0 h2-4.4.1 hpack-4.2.0 httpcore-1.0.9 httpx-0.28.1 hyperframe-6.1.0 idna-3.20 typing_extensions-4.16.0
    WARNING: Running pip as the 'root' user can result in broken permissions and conflicting behaviour with the system package manager. It is recommended to use a virtual environment instead: https://pip.pypa.io/warnings/venv
    ```
  - *(extra)* `python3 -c "import googletrans; print(googletrans.__file__)"` shows `/usr/local/lib/python3.11/dist-packages/googletrans/__init__.py` (Debian 12). Captured:
    ```
    $ python3 -c 'import googletrans; print(googletrans.__file__)'
    /usr/local/lib/python3.11/dist-packages/googletrans/__init__.py
    ```
- **If it fails:**
  - `no such option: --break-system-packages`: your image has pip < 23.0.1 (e.g. Ubuntu 22.04's pip 22.0.2). That image also has no PEP 668 marker, so drop the flag.
  - Without `sudo`, pip prints "Defaulting to user installation because normal site-packages is not writeable" and installs to `~/.local/lib/python3.X/site-packages`. That still works for your user. The README's previous revision used no `sudo` (commit `e3bd74e` added it).

**Step 8. Run the app** [A9] (`README.md:58-61`):
```
python3 cli.py
python3 cli.py -t "Good morning. It is a good morning for cheese." -s "en" -d "es"
python3 cli.py -t "Good afternoon. Would you like some cheese?" -s "en" -d "fr"
```
- **Under the hood:**
  - argparse builds the `Namespace` (`cli.py:42-70`)
  - `asyncio.run` starts the event loop (`cli.py:72`)
  - `main` prints the banner, the args and the input (`cli.py:13-23`)
  - `Translator(raise_exception=True)` opens an `httpx.AsyncClient` and sends one HTTPS GET to `translate.googleapis.com` (`cli.py:25-31`)
  - the result text is printed (`cli.py:39`)
- **Checkpoint (first command).** What a successful run prints (`expected/10-run-default.txt`: the walkthrough A output up to `Input:`, plus the `Output:` line the venv run of Step 19 really printed):
  ```
  $ python3 cli.py


      _      ____  ____   _  ____
     / \    / ___||___ \ / || ___|
    / _ \  | |      __) || ||___ \
   / ___ \ | |___  / __/ | | ___) |
  /_/   \_\ \____||_____||_||____/



  Arguments: Namespace(text='I love cheese', file='', src='en', dest='it')

  Input: I love cheese
  Output: Adoro il formaggio
  ```
  The other two runs end with `Output: Buen día. Es un buen día para el queso.` and `Output: Bon après-midi. Veux-tu du fromage ?` (`expected/11-run-es.txt`, `expected/12-run-fr.txt`). `python3 cli.py --help` *(extra)* lists the options (`debian12-part-a/13-help.txt`):
  ```
  $ python3 cli.py --help
  usage: cli.py [-h] [-t TEXT] [-f FILE] [-s SRC] [-d DEST]

  A simple translation app

  options:
    -h, --help            show this help message and exit
    -t TEXT, --text TEXT  Text to translate
    -f FILE, --file FILE  File to translate
    -s SRC, --src SRC     Source language
    -d DEST, --dest DEST  Destination language
  ```
- **What the capture actually got.** On 2026-10-12 Google's unofficial endpoint answered all three walkthrough A runs with **HTTP 429** ("too many requests"). Real output (`debian12-part-a/10-run-default.txt`, trimmed):
  ```
  $ python3 cli.py
  …
  Arguments: Namespace(text='I love cheese', file='', src='en', dest='it')

  Input: I love cheese
  Traceback (most recent call last):
    File "/home/student/simple-translate/cli.py", line 27, in main
  …
    File "/usr/local/lib/python3.11/dist-packages/googletrans/client.py", line 137, in _translate
      raise Exception(
  Exception: Unexpected status code "429" from ['translate.googleapis.com']

  The above exception was the direct cause of the following exception:
  …
    File "/home/student/simple-translate/cli.py", line 33, in main
      raise RuntimeError(
  RuntimeError: Translation request to Google Translate failed (the server's network/IP may be rate-limited or blocked by Google's unofficial translate endpoint).
  ```
  This is a chained traceback. The last line is only the app's own wrapper (`cli.py:32-37`); the line "The above exception was the direct cause of the following exception" points up to the cause, `Exception: Unexpected status code "429"`, raised by googletrans (`client.py:136-141`). Reaching `Input: I love cheese` means the imports worked: the install is fine, and only the network said no.
- **If it fails:**
  - `RuntimeError: Translation request to Google Translate failed (the server's network/IP may be rate-limited or blocked by Google's unofficial translate endpoint).` **Scroll up to the first exception** in the chained traceback ("The above exception was the direct cause of…"):
    - `Exception: Unexpected status code "429" …` (or another non-200 code): Google is throttling the VM's IP. Wait and retry, try another region, or run it on your laptop.
    - `ValueError: invalid destination language`: you mistyped a code (see §6). Captured with `python3 cli.py -t hello -d xx` *(extra)* (`debian12-part-a/14-badlang.txt`, trimmed):
      ```
      $ python3 cli.py -t hello -d xx
      …
      Arguments: Namespace(text='hello', file='', src='en', dest='xx')

      Input: hello
      Traceback (most recent call last):
        File "/home/student/simple-translate/cli.py", line 27, in main
          result = await translator.translate(
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^
        File "/usr/local/lib/python3.11/dist-packages/googletrans/client.py", line 269, in translate
          raise ValueError("invalid destination language")
      ValueError: invalid destination language

      The above exception was the direct cause of the following exception:
      …
      RuntimeError: Translation request to Google Translate failed (the server's network/IP may be rate-limited or blocked by Google's unofficial translate endpoint).
      ```
  - `ModuleNotFoundError: No module named 'googletrans'`: Step 7 didn't install for this interpreter.
  - `python3: can't open file '…/cli.py'`: you are not in `~/simple-translate`; `cd simple-translate`.

**Step 9. Delete the VM** [A10] (`README.md:62`). Select it in *VM instances* and click **Delete**; then check *VM instances* and *Disks* (§2). Or *(extra)* keep it for Part B. Reusing it is instructive, because it shows the venv ignoring the polluted system Python. Remember to delete it at the end.

### Part B: ⚡ Installing App on VM using UV (`README.md:68-101`)

**Steps 10-14. New VM, SSH, `sudo apt-get update`, `sudo apt install git`, `git clone …` + `cd simple-translate`** [B1-B6] (`README.md:72-77`). These are identical to Steps 1-5. If the name `ac215-l01` is still taken, the old VM is still being deleted; wait a minute. Note that Part B never installs `python3-pip`; uv doesn't need it. Captured `ls -a` *(extra)* (`debian12-part-b/04-ls.txt`):
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
```

**Step 15. Install uv** [B7] (`README.md:78`): `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **Under the hood:**
  - `curl -L` follows redirects, `-s` is silent, `-S` still shows errors, `-f` fails on HTTP errors.
  - The `| sh` pipes the downloaded script straight into the shell, so you are running code from the internet: uv's official installer, which you can open and read first.
  - The script detects your CPU and OS, downloads the `uv` and `uvx` binaries into `~/.local/bin`, writes `~/.local/bin/env`, and appends a line that runs it to your startup files (captured: `. "$HOME/.local/bin/env"` at `~/.profile:29` and `~/.bashrc:115`).
  - Alternatives are in `README.md:80-81`. Its `pip install uv --break-system-packages` needs a pip, which this VM doesn't have.
- **Checkpoint:** output ending with "everything's installed!" and a hint to restart the shell or run `source $HOME/.local/bin/env`. Captured (`debian12-part-b/05-uv-install.txt`, complete):
  ```
  $ curl -LsSf https://astral.sh/uv/install.sh | sh
  downloading uv 0.13.0 x86_64-unknown-linux-gnu
  installing to /home/student/.local/bin
    uv
    uvx
  everything's installed!

  To add $HOME/.local/bin to your PATH, either restart your shell or run:

      source $HOME/.local/bin/env (sh, bash, zsh)
      source $HOME/.local/bin/env.fish (fish)
  ```
- *(extra)* Try it right away: `uv --version` fails, because this shell's `PATH` doesn't include `~/.local/bin` yet (`debian12-part-b/06-uv-missing.txt`; in your login shell the prefix is `-bash:`):
  ```
  $ uv --version
  bash: line 1: uv: command not found
  ```
- **If it fails:**
  - `curl: command not found` (rare on GCP images): `sudo apt-get install -y curl`
  - TLS or connection errors: check outbound internet

**Step 16. Put uv on PATH** [B8] (`README.md:83`): `source $HOME/.local/bin/env`
- **Under the hood:** the script prepends `$HOME/.local/bin` to `PATH` if it isn't there already. Its key line is `export PATH="$HOME/.local/bin:$PATH"` (line 9 of the installer-generated `~/.local/bin/env`; full file in §5). The README's other option, "Reload your shell", means a new SSH window, which starts in your home folder, so `cd simple-translate` again.
- **Checkpoint:** `uv --version` prints `uv 0.x.y`; `which uv` gives `/home/<you>/.local/bin/uv`. Captured (`debian12-part-b/07-uv-version.txt`):
  ```
  $ source $HOME/.local/bin/env; uv --version; which uv
  uv 0.13.0 (x86_64-unknown-linux-gnu)
  /home/student/.local/bin/uv
  ```
- **If it fails:** `uv: command not found` means you skipped this step or ran it as `sh ~/.local/bin/env`, which only changes a child shell. Open a new SSH tab or `source` it.

**Step 17. Create the environment** [B9] (`README.md:84`): `uv sync`
- **Under the hood** (`README.md:86-87` gives the README's version):
  1. Finds `pyproject.toml` in the current directory (`pyproject.toml:1-10`).
  2. Picks an interpreter satisfying `requires-python = ">=3.13"` (`pyproject.toml:6`). On a Debian 12 / Ubuntu 24.04 VM nothing qualifies, so uv **downloads a managed CPython**: the newest stable release ≥ 3.13, which was 3.15.0 with uv 0.13.0 on 2026-10-12. On Debian 13 the system's 3.13.5 qualifies and is used as is.
  3. Creates `.venv/`, whose prompt name comes from `name = "app"` at `pyproject.toml:2`.
  4. **Resolves** the dependency tree and **writes `uv.lock`**, because the repo has none.
  5. Installs the packages into `.venv`: 11 on Python 3.15, 12 on 3.13 (§3.5). The project itself is a "virtual" (non-installed) project because `pyproject.toml` has no `[build-system]`.
- **Checkpoint**, Debian 12 (`debian12-part-b/08-uv-sync.txt`, complete; versions will differ for you):
  ```
  $ uv sync
  Downloading cpython-3.15.0-linux-x86_64-gnu (download) (35.9MiB)
   Downloaded cpython-3.15.0-linux-x86_64-gnu (download)
  Using CPython 3.15.0
  Creating virtual environment at: .venv
  Resolved 13 packages in 218ms
  Prepared 11 packages in 1.08s
  Installed 11 packages in 13ms
   + anyio==4.15.1
   + art==6.5
   + certifi==2026.7.22
   + googletrans==4.0.2
   + h11==0.16.0
   + h2==4.4.1
   + hpack==4.2.0
   + httpcore==1.0.9
   + httpx==0.28.1
   + hyperframe==6.1.0
   + idna==3.20
  ```
  Debian 13, where the VM already has Python ≥ 3.13 (`debian13-part-b/08-uv-sync.txt`, trimmed):
  ```
  $ uv sync
  Using CPython 3.13.5 interpreter at: /usr/bin/python3
  Creating virtual environment at: .venv
  Resolved 13 packages in 1.43s
  Prepared 12 packages in 281ms
  Installed 12 packages in 26ms
  …
   + typing-extensions==4.16.0
  ```
  - `ls -a` now shows `.venv` and `uv.lock` (`debian12-part-b/09-ls-after.txt`)
  - `cat .venv/pyvenv.cfg` contains `include-system-site-packages = false` and `prompt = app`; on Debian 12 its `home` is the uv-managed interpreter's folder (Debian 13: `home = /usr/bin`). Captured (`debian12-part-b/10-pyvenv.txt`):
    ```
    $ cat .venv/pyvenv.cfg
    home = /home/student/.local/share/uv/python/cpython-3.15-linux-x86_64-gnu/bin
    implementation = CPython
    uv = 0.13.0
    version_info = 3.15
    include-system-site-packages = false
    prompt = app
    ```
  - `ls -la .venv/bin` *(extra)*: `python` is a symlink to the real interpreter, `python3` and `python3.15` link to it, the packages' launchers are there, and there is no `pip` (`debian12-part-b/11-venv-bin.txt`, trimmed):
    ```
    $ ls -la .venv/bin
    …
    -rw-r--r-- 1 student student 4095 Oct 12 02:25 activate
    …
    -rwxr-xr-x 1 student student  325 Oct 12 02:25 art
    …
    -rwxr-xr-x 1 student student  318 Oct 12 02:25 httpx
    -rwxr-xr-x 1 student student  321 Oct 12 02:25 idna
    …
    lrwxrwxrwx 1 student student   81 Oct 12 02:25 python -> /home/student/.local/share/uv/python/cpython-3.15-linux-x86_64-gnu/bin/python3.15
    lrwxrwxrwx 1 student student    6 Oct 12 02:25 python3 -> python
    lrwxrwxrwx 1 student student    6 Oct 12 02:25 python3.15 -> python
    -rwxr-xr-x 1 student student  334 Oct 12 02:25 translate
    ```
  - `git status` shows `uv.lock` as untracked; `.venv` stays hidden thanks to `.venv/.gitignore` (`debian12-part-b/19-git-status.txt`):
    ```
    $ git status
    On branch main
    Your branch is up to date with 'origin/main'.

    Untracked files:
      (use "git add <file>..." to include in what will be committed)
    	uv.lock

    nothing added to commit but untracked files present (use "git add" to track)
    ```
  - *(extra)* `uv tree` and `head -30 uv.lock` show the resolved tree and the lockfile (§5). Running `uv sync` again changes nothing (`debian12-part-b/23-resync.txt`):
    ```
    $ uv sync
    Resolved 13 packages in 1ms
    Checked 11 packages in 0.14ms
    ```
- **If it fails:**
  - `` error: No `pyproject.toml` found in current directory or any parent directory ``: you're not in `simple-translate/`.
  - `error: No interpreter found for Python >=3.13 in managed installations` with the hint "…Python downloads are set to 'never'": Python downloads are disabled (e.g. `UV_PYTHON_DOWNLOADS=never`). Unset that variable, or install a 3.13+ Python yourself.
  - Network errors: check egress to pypi.org and GitHub (the Python builds are fetched from python-build-standalone releases).

**Step 18. Activate** [B10] (`README.md:89`): `source .venv/bin/activate`
- **Under the hood:** see §3.4 and `README.md:91-92`.
- **Before** *(extra)*: `which python` finds nothing, and `PATH` starts with `~/.local/bin` (`debian12-part-b/12-python-before.txt`):
  ```
  $ which python; echo exit:$?; echo $PATH | tr ':' '\n'
  exit:1
  /home/student/.local/bin
  /usr/local/bin
  /usr/bin
  /bin
  /usr/local/games
  /usr/games
  ```
- **Checkpoint:**
  - The prompt becomes **`(app) <you>@ac215-l01:~/simple-translate$`**. The README's example `(simple-translate) $` is wrong for this repo (§9).
  - `which python` gives `/home/<you>/simple-translate/.venv/bin/python`
  - `python --version` gives `Python 3.15.0` on Debian 12 (Debian 13: `Python 3.13.5`)
  - `which pip` prints **nothing**, because uv venvs have no pip
  - Captured, as one line (`debian12-part-b/13-activate.txt`):
    ```
    $ source .venv/bin/activate; which python; python --version; which pip; echo pip-exit:$?; echo $PATH | tr ':' '\n' | head -3; echo VIRTUAL_ENV=$VIRTUAL_ENV
    /home/student/simple-translate/.venv/bin/python
    Python 3.15.0
    pip-exit:1
    /home/student/simple-translate/.venv/bin
    /home/student/.local/bin
    /usr/local/bin
    VIRTUAL_ENV=/home/student/simple-translate/.venv
    ```
- **If it fails:** `bash: .venv/bin/activate: No such file or directory` means Step 17 didn't finish or you're in the wrong directory.
- **Later:** activation lives in this one shell. If the SSH window reconnects, you are back in `~` without `(app)`: `cd simple-translate` and `source .venv/bin/activate` again (uv itself is still found, thanks to the startup files).

**Step 19. Run the app** [B11] (`README.md:94-97`):
```
python cli.py
python cli.py -t "Good morning. It is a good morning for cheese." -s "en" -d "es"
python cli.py -t "Good afternoon. Would you like some cheese?" -s "en" -d "fr"
```
- **Checkpoint:** the same output as Step 8. These runs succeeded in the capture, a few minutes after the 429s of Part A; real output, with the venv active (`debian12-part-b/14-run-default.txt`, then the last lines of `15-run-es.txt` and `16-run-fr.txt`):
  ```
  $ python cli.py


      _      ____  ____   _  ____
     / \    / ___||___ \ / || ___|
    / _ \  | |      __) || ||___ \
   / ___ \ | |___  / __/ | | ___) |
  /_/   \_\ \____||_____||_||____/



  Arguments: Namespace(text='I love cheese', file='', src='en', dest='it')

  Input: I love cheese
  Output: Adoro il formaggio
  $ python cli.py -t "Good morning. It is a good morning for cheese." -s "en" -d "es"
  …
  Input: Good morning. It is a good morning for cheese.
  Output: Buen día. Es un buen día para el queso.
  $ python cli.py -t "Good afternoon. Would you like some cheese?" -s "en" -d "fr"
  …
  Input: Good afternoon. Would you like some cheese?
  Output: Bon après-midi. Veux-tu du fromage ?
  ```
  The Debian 13 runs printed the same lines.
- **If it fails:**
  - `python: command not found`: the venv isn't active (Debian has no `python`). Re-run Step 18, or use `uv run python cli.py`, which needs no activation.
  - Translation errors: as in Step 8. If you see the `Input:` line, the venv works.
- *(extra)* Two ways without activation: `uv run python cli.py` (uv syncs the venv if needed, then runs inside it) and `.venv/bin/python cli.py` (the venv's interpreter by its path).

**Step 20 (extra). Prove the isolation.**
- `deactivate` first: while the venv is active, even `python3` is the venv's (`.venv/bin/python3 -> python`). Then `python3 -c "import googletrans"`. On a *fresh* Part B VM this raises `ModuleNotFoundError`, because the packages exist only in `.venv`. On a reused Part A VM it succeeds from `/usr/local/lib/...`. Captured on the fresh VM (`debian12-part-b/20-isolation.txt`):
  ```
  $ python3 -c 'import googletrans'
  Traceback (most recent call last):
    File "<string>", line 1, in <module>
  ModuleNotFoundError: No module named 'googletrans'
  ```
- `uv run python -c "import googletrans, sys; print(sys.prefix)"` prints the `.venv` path (`debian12-part-b/21-uv-run.txt`):
  ```
  $ uv run python -c 'import googletrans, sys; print(sys.prefix)'
  /home/student/simple-translate/.venv
  ```
- The venv interpreter's `sys.path` *(extra)*, with the venv active (`debian12-part-b/22-syspath-venv.txt`): the standard library of the interpreter it links to, then only the venv's own site-packages.
  ```
  $ source .venv/bin/activate; python -c 'import sys; print("\n".join(sys.path))'

  /home/student/.local/share/uv/python/cpython-3.15.0-linux-x86_64-gnu/lib/python315.zip
  /home/student/.local/share/uv/python/cpython-3.15.0-linux-x86_64-gnu/lib/python3.15
  /home/student/.local/share/uv/python/cpython-3.15.0-linux-x86_64-gnu/lib/python3.15/lib-dynload
  /home/student/simple-translate/.venv/lib/python3.15/site-packages
  ```
- Disk use *(extra)*: `du -sh .venv ~/.local/share/uv/python` gave `13M .venv` and `116M /home/student/.local/share/uv/python` on Debian 12 (`debian12-part-b/24-du.txt`); on Debian 13 there is no uv-managed Python at all.

**Step 21. Delete the VM** [B12] (`README.md:98`) and confirm the instance and its disk are gone (§2).

### Part C (optional, read-only comparison): the `pipenv` branch

**Step 22.** On your laptop clone (or on the VM):
- `git show origin/pipenv:Pipfile` and `git show origin/pipenv:README.md | sed -n 22,35p` *(extra)*
- The pipenv README's VM walkthrough is (`origin/pipenv:README.md:29-31`): `sudo apt install pipenv`, `pipenv install`, `pipenv shell`.
- **Caveat:** that README's clone command (`origin/pipenv:README.md:27`) clones the **default branch (`main`)**, which has no `Pipfile`. To try it for real you'd first need `git switch pipenv` *(extra)*.
- Whether the old `googletrans==4.0.0rc1` stack (`origin/pipenv:Pipfile:9`; it locks `httpx==0.13.3`) still works has not been verified.

---

## 5. Code tour

```
simple-translate/  (main @ 62f821b)
├── cli.py                 # the app: argparse -> asyncio -> googletrans -> print   (L01 core)
├── pyproject.toml         # project metadata, requires-python, 2 direct deps        (L01 core: read by uv sync)
├── README.md              # 4 walkthroughs; L01 = lines 38-101
├── Dockerfile.txt         # solution Dockerfile for L02 (uv sync inside python:3.12-slim-bookworm)
├── docker-shell.sh        # L02: build + run the image locally
├── docker-build-push.sh   # L02: multi-arch buildx build + push to dlops/simple-translate
├── .gitignore             # ignores .DS_Store, Dockerfile (student-made), /.idea/
└── .vscode/settings.json  # VS Code: Black as Python formatter
  (no uv.lock, no .python-version: both get created / are absent on your machine)

simple-translate/  (pipenv @ 3a354d8, comparison only)
├── Pipfile, Pipfile.lock  # pipenv equivalents of pyproject.toml / uv.lock (python 3.11, googletrans 4.0.0rc1)
├── cli.py                 # older synchronous version of the app
├── Dockerfile             # python:3.11-slim-buster + pipenv sync + "pipenv shell"
├── docker-shell.sh, tip.txt (sample text file for -f), README.md, .gitignore, .vscode/
```

**`pyproject.toml:1-10`**
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
- **L1:** `[project]` is the standard PEP 621 table that every modern Python tool reads.
- **L2:** `name = "app"` becomes the venv prompt (`(app)`) and the root of `uv tree`. Lines 2 and 4 are `uv init` boilerplate.
- **L6:** a *floor*, not a pin. It was changed from `">=3.12,<3.13"` to `">=3.13"` in commit `2827e2a` (2026-09-02); see §6 and §9.
- **L8:** `art>=6.5` allows any newer art.
- **L9:** `googletrans==4.0.2` is an exact pin, but only for this one package.
- There's no `[build-system]` table, so uv treats this as a *virtual project*: it installs the dependencies but not the project itself.

**`cli.py:5-9`** (imports)
```python
import argparse
import asyncio

from art import text2art
from googletrans import Translator
```
- `argparse` and `asyncio` are stdlib.
- `art` and `googletrans` are the only third-party imports, and they must come from *some* site-packages. Which one depends on the interpreter: system (Part A) or `.venv` (Part B).

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
- `async def` is needed because googletrans 4.x is an asyncio library.
- `text2art("AC215")` draws the banner. Printing `args` shows the whole parsed `Namespace`, which is a useful debugging habit.
- `-f/--file` overrides `-t`. The path is relative to your *current directory*.

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
- **L25:** `async with` closes the underlying `httpx.AsyncClient` on exit (googletrans `client.py:105-109`). `raise_exception=True` is crucial: the library default is `False` (googletrans `constants.py:461`), and with `False` a non-200 answer from Google silently returns the input text as the "translation" (`client.py:136-144`, excerpt below). Connection errors raise either way.
- **L27:** `await` performs one HTTPS GET.
- **L32-37:** catch *anything* and re-raise a friendlier `RuntimeError`, chained with `from error`. That also swallows non-network errors such as `ValueError("invalid destination language")`; see §6. Both cases were captured (§4 Step 8).
- **L39:** `result.text` is the translated string.

**`cli.py:65-72`** (CLI defaults and the event loop)
```python
    parser.add_argument(
        "-d",
        "--dest",
        default="it",
        help="Destination language",
    )

    asyncio.run(main(parser.parse_args()))
```
- The defaults (`-t "I love cheese"`, `-s en`, `-d it`; see `cli.py:45-70`) are why a bare `python cli.py` translates to Italian: `Output: Adoro il formaggio` in the capture.
- `asyncio.run` creates an event loop, runs `main` to completion and closes the loop.
- `python cli.py --help` lists all four options.

**googletrans 4.0.2 (third-party, installed into `.venv/lib/python3.X/site-packages/googletrans/`), `client.py:130-144`**
```python
        if r.status_code == 200:
            data = utils.format_json(r.text)
            if not isinstance(data, list):
                data = [data]  # Convert dict to list to match return type
            return data, r

        if self.raise_exception:
            raise Exception(
                'Unexpected status code "{}" from {}'.format(
                    r.status_code, self.service_urls
                )
            )

        DUMMY_DATA[0][0][0] = text
        return DUMMY_DATA, r
```
- This is why commit `62f821b` added `raise_exception=True` to `cli.py:25`. Without it, a 429/403 from Google produces `Output: <your original text>` and no error.
- The request goes to `https://{host}/translate_a/single` (`urls.py:7`) with host `translate.googleapis.com` (`constants.py:3`). That's an unofficial, keyless endpoint, *not* the paid Cloud Translation API.
- The captured 429 (§4 Step 8) was raised here: the traceback names `client.py`, line 137, `raise Exception(`.

**googletrans 4.0.2 `client.py:263-269`** (language validation, which runs *before* any network call)
```python
        if dest not in LANGUAGES:
            if dest in SPECIAL_CASES:
                dest = SPECIAL_CASES[dest]
            elif dest in LANGCODES:
                dest = LANGCODES[dest]
            else:
                raise ValueError("invalid destination language")
```
- Lines 252-253 first lowercase the code and cut it at `_`, so `zh-CN` from the README table (`README.md:238`) becomes `zh-cn`, which is valid.
- An unknown code raises `ValueError`, which `cli.py:32` then wraps in the misleading "network/IP" `RuntimeError`. The captured `-d xx` traceback names `client.py`, line 269.

**Generated by `uv sync`, not in the repo: `.venv/pyvenv.cfg`** (captured on Debian 12, `debian12-part-b/10-pyvenv.txt`)
```
home = /home/student/.local/share/uv/python/cpython-3.15-linux-x86_64-gnu/bin
implementation = CPython
uv = 0.13.0
version_info = 3.15
include-system-site-packages = false
prompt = app
```
and on Debian 13 (`debian13-part-b/10-pyvenv.txt`), where uv used the system interpreter:
```
home = /usr/bin
implementation = CPython
uv = 0.13.0
version_info = 3.13.5
include-system-site-packages = false
prompt = app
```
- `home` is the folder of the real interpreter; `.venv/bin/python` is a symlink into it (on Debian 12 via `cpython-3.15-linux-x86_64-gnu`, uv's minor-version link to `cpython-3.15.0-linux-x86_64-gnu`; on Debian 13 to `/usr/bin/python3`).
- `include-system-site-packages = false` is the isolation switch.
- `prompt = app` comes from `pyproject.toml:2`.

**Generated, not in the repo: `uv tree`** (captured on Debian 12 / CPython 3.15.0, `debian12-part-b/17-tree.txt`)
```
$ uv tree
Resolved 13 packages in 1ms
app v0.1.0
├── art v6.5
└── googletrans v4.0.2
    └── httpx[http2] v0.28.1
        ├── anyio v4.15.1
        │   └── idna v3.20
        ├── certifi v2026.7.22
        ├── httpcore v1.0.9
        │   ├── certifi v2026.7.22
        │   └── h11 v0.16.0
        ├── idna v3.20
        └── h2 v4.4.1 (extra: http2)
            ├── hpack v4.2.0
            └── hyperframe v6.1.0
```
On Debian 13 / CPython 3.13.5 (`debian13-part-b/17-tree.txt`) `anyio` has one more child, `typing-extensions v4.16.0`. 2 declared dependencies became 11 installed packages on 3.15 and 12 on 3.13. Everything below `googletrans` floats unless a `uv.lock` is shared.

**Generated, not in the repo: `uv.lock`, lines 1-30** (captured, `debian12-part-b/18-lock-head.txt`; the final `13` is the `grep -c` count of `[[package]]` entries)
```
$ head -30 uv.lock; grep -c '^\[\[package\]\]' uv.lock
version = 1
revision = 5
requires-python = ">=3.13"

[[package]]
name = "anyio"
version = "4.15.1"
source = { registry = "https://pypi.org/simple" }
dependencies = [
    { name = "idna" },
    { name = "typing-extensions", marker = "python_full_version < '3.15'" },
]
sdist = { url = "https://files.pythonhosted.org/packages/a9/d2/f4d173e22df740bc37b1db102b386ba719b66e95b0f0d751f556b387e6d2/anyio-4.15.1.tar.gz", hash = "sha256:9f28306018cbd6d329e64a36d58256edff76dd996fe423bc957326e578b82a94", size = 276966, upload-time = "2026-09-05T10:42:39.44Z" }
wheels = [
    { url = "https://files.pythonhosted.org/packages/12/b8/4bd346e22b28902df4d651910f5242c28d84e4a5c2435ca5c3f797ed7e2e/anyio-4.15.1-py3-none-any.whl", hash = "sha256:6152fdbbf9a77fdec97731721bebf7c4c44f7c29b424b0065826173efc7ed101", size = 132079, upload-time = "2026-09-05T10:42:37.923Z" },
]

[[package]]
name = "app"
version = "0.1.0"
source = { virtual = "." }
dependencies = [
    { name = "art" },
    { name = "googletrans" },
]

[package.metadata]
requires-dist = [
    { name = "art", specifier = ">=6.5" },
    { name = "googletrans", specifier = "==4.0.2" },
13
```
- Line 3 of `uv.lock` repeats `requires-python`: the lock is resolved for every allowed Python, which is why line 11's `marker` exists.
- Each package records its source registry, the exact version, and sha256 hashes of the sdist and wheels: the receipt.
- `app` is `source = { virtual = "." }`: the project itself, never downloaded. The file has 13 `[[package]]` entries.

**Generated by the uv installer: `~/.local/bin/env`** (captured, `debian12-part-b/26-startup-files.txt`; the first two `grep` hits, `~/.profile:25-26`, are Debian's stock `~/.profile`, the next two were added by the installer)
```
$ grep -n local/bin ~/.profile ~/.bashrc; cat ~/.local/bin/env
/home/student/.profile:25:if [ -d "$HOME/.local/bin" ] ; then
/home/student/.profile:26:    PATH="$HOME/.local/bin:$PATH"
/home/student/.profile:29:. "$HOME/.local/bin/env"
/home/student/.bashrc:115:. "$HOME/.local/bin/env"
#!/bin/sh
# add binaries to PATH if they aren't added yet
# affix colons on either side of $PATH to simplify matching
case ":${PATH}:" in
    *:"$HOME/.local/bin":*)
        ;;
    *)
        # Prepending path in case a system-installed binary needs to be overridden
        export PATH="$HOME/.local/bin:$PATH"
        ;;
esac
```
- Line 9 of the env file (`export PATH=…`) is the one that matters. `source $HOME/.local/bin/env` (`README.md:83`) runs it in your current shell.
- The installer also appended `. "$HOME/.local/bin/env"` to `~/.profile` (line 29) and `~/.bashrc` (line 115), so every new SSH session finds uv by itself.

**Generated by `uv sync`: `.venv/bin/activate`** (captured `grep -n` hits, `debian12-part-b/25-activate-file.txt`; each line starts with its line number in `activate`)
```
$ ls -l .venv/bin/activate; grep -n 'PATH=\|VIRTUAL_ENV_PROMPT=\|^VIRTUAL_ENV=' .venv/bin/activate | head
-rw-r--r-- 1 student student 4095 Oct 12 02:25 .venv/bin/activate
…
81:VIRTUAL_ENV='/home/student/simple-translate/.venv'
…
97:_OLD_VIRTUAL_PATH="$PATH"
98:PATH="$VIRTUAL_ENV/bin:$PATH"
102:    VIRTUAL_ENV_PROMPT="app"
```
- Lines 97-98 are the whole of "activation" for `python` lookups: save the old `PATH`, put the venv's `bin` first. Line 81 sets `VIRTUAL_ENV='/home/student/simple-translate/.venv'` (an absolute path, see §6 #17) and line 102 `VIRTUAL_ENV_PROMPT="app"`.

**`origin/pipenv:Pipfile:8-13`** (the pipenv equivalent)
```toml
[packages]
googletrans = "==4.0.0rc1"
art = "*"

[requires]
python_version = "3.11"
```
- Same idea, different file: `[packages]` corresponds to `dependencies`, and `[requires] python_version` is an *exact minor* requirement (3.11) where uv uses a range.
- The committed `Pipfile.lock` pins 14 packages with sha256 hashes, e.g. `httpx==0.13.3` and `art==6.2`.

**`origin/pipenv:cli.py:4-11`** (the old synchronous API)
```python
import argparse
from googletrans import Translator
from art import text2art

# Generate the inputs arguments parser
parser = argparse.ArgumentParser(description="Command description.")

translator = Translator()
```
- googletrans 4.0.0rc1 was synchronous: `translator.translate(...)` at `origin/pipenv:cli.py:30`, with no `await`.
- Moving to 4.0.2 forced the async rewrite on `main` (commit `e3bd74e`).
- Line 9 creates a parser that is never used; it's shadowed at line 38.

**`Dockerfile.txt:21-29`** (L02 preview: the same `uv sync`, inside an image)
```dockerfile
# Copy the source code
COPY . ./

RUN uv sync

# Entry point
ENTRYPOINT ["/bin/bash"]
# Get into the uv virtual environment shell
CMD ["-c", "source .venv/bin/activate && exec bash"]
```
- This is exactly Part B, baked into a container: `uv sync` builds the venv at build time.
- The container's default command `source`s the activate script, the same Step 18, so you land in an activated shell.

---

## 6. Gotchas and common errors

1. **`error: externally-managed-environment` from `pip3 install`.**
   - **Cause:** PEP 668. The Debian/Ubuntu system Python carries an `EXTERNALLY-MANAGED` marker (captured on Debian 12, §4 Step 6).
   - **Fix:** in Part A, add `--break-system-packages` exactly as `README.md:53` does; or better, use a venv (Part B).

2. **`no such option: --break-system-packages`.**
   - **Cause:** an old image with pip < 23.0.1, e.g. Ubuntu 22.04 (pip 22.0.2) or Debian 11. Those images have no PEP 668 marker either.
   - **Fix:** drop the flag, or choose a Debian 12 / Ubuntu 24.04 image.

3. **`bash: python: command not found`.**
   - **Cause:** Debian/Ubuntu provide only `python3`, which is why Part A uses `python3` (`README.md:59-61`). In Part B, `python` exists only once the venv is active. Captured: `which python` finds nothing on a fresh Debian 12 or 13 VM.
   - **Fix:** `source .venv/bin/activate` (`README.md:89`), or `uv run python cli.py`, or `.venv/bin/python cli.py`.

4. **`uv: command not found` right after installing.**
   - **Cause:** the installer put uv in `~/.local/bin`, which isn't on `PATH` in the current shell. Captured as `bash: line 1: uv: command not found`; your login shell words it `-bash: uv: command not found`.
   - **Fix:** `source $HOME/.local/bin/env` (`README.md:83`), or open a new SSH tab (the installer added the env file to `~/.profile` and `~/.bashrc`).

5. **`uv sync` downloads ~36 MB of "cpython-3.15.0".**
   - **Cause:** `pyproject.toml:6` requires `>=3.13`. Debian 12 ships 3.11.2 and Ubuntu 24.04 ships 3.12, so uv fetches the newest stable release in range. On 2026-10-12 that was 3.15.0, not 3.13 (captured with uv 0.13.0: `Downloading cpython-3.15.0-linux-x86_64-gnu (download) (35.9MiB)`; 116 MB on disk). Debian 13's 3.13.5 is in range, so there uv downloads nothing.
   - **Effect:** it isn't an error, but you're no longer running the OS Python, and two VMs with different images (or the same image on different dates) can end up on different interpreters, and even with different package counts (11 on 3.15, 12 on 3.13; §3.5).
   - **Fix (if you want determinism):** `uv python pin 3.13`, which writes `.python-version` and pins the 3.13 series (`uv python pin 3.13.5` pins one release). With the current `requires-python`, pinning 3.11 or 3.12 errors out: `` error: The requested Python version `3.11` is incompatible with the project `requires-python` value of `>=3.13`. `` (scratch check, uv 0.11.32).

6. **`` error: The requested interpreter resolved to Python 3.12.3, which is incompatible with the project's Python requirement: `>=3.13` (from `project.requires-python`) ``.**
   - **Cause:** you forced an old interpreter (`uv sync --python 3.12`, or `UV_PYTHON=3.12`).
   - **Fix:** drop the override, or relax `requires-python` if you really need an older interpreter.

7. **`error: No interpreter found for Python >=3.13 in managed installations` plus the hint "…Python downloads are set to 'never'".**
   - **Cause:** downloads are disabled, e.g. by `UV_PYTHON_DOWNLOADS=never` or a corporate config.
   - **Fix:** allow downloads, or install Python 3.13+ yourself.

8. **The README promises a lockfile, but the repo has none.**
   - **Symptom:** two students (or the same student a week later) get different `httpx`/`certifi` versions, and `uv.lock` shows up as an untracked file (captured in `git status`).
   - **Cause:** `uv.lock` was never committed (`git log --all -- uv.lock` is empty), contradicting `README.md:12` and `README.md:70`.
   - **Fix:** in your own repo, commit `uv.lock` and use `uv sync --locked` in CI/Docker. `llm-rag/Dockerfile:42-45` shows the pattern the course uses later: copy `pyproject.toml uv.lock*`, then `RUN uv sync --frozen`.

9. **The prompt shows `(app)`, not `(simple-translate)`.**
   - **Cause:** uv names the venv prompt after `[project].name` (`pyproject.toml:2`), as `.venv/pyvenv.cfg` `prompt = app` and generated `activate:101-102` show (captured: `VIRTUAL_ENV_PROMPT="app"` at line 102). `README.md:92` shows `(simple-translate) $`.
   - **Fix:** none needed. It's cosmetic; rename the project in `pyproject.toml` if it bothers you.

10. **`pip install X` "doesn't work" inside an activated uv venv.**
    - **Symptom:** `pip: command not found` (fresh Part B VM), or an `externally-managed-environment` error (reused Part A VM, where `/usr/bin/pip` is the system pip).
    - **Cause:** uv venvs ship no `pip` (the captured `.venv/bin` has none, and `which pip` prints nothing after activation), contrary to `README.md:92`, which says activation makes "`python` and `pip` resolve to the venv's binaries".
    - **Fix:** `uv add X` (updates `pyproject.toml` and `uv.lock`) or `uv pip install X` (venv only, not recorded).

11. **`./.venv/bin/activate` → `Permission denied`, or `bash .venv/bin/activate` "does nothing".**
    - **Cause:** the activate script isn't executable (`-rw-r--r--` in the capture), and running it in a child shell can't change your current shell.
    - **Fix:** `source .venv/bin/activate` (`README.md:92` explains why).

12. **Misleading network error for a typo in a language code.**
    - **Symptom:** `python cli.py -d xx` ends with `RuntimeError: Translation request to Google Translate failed (the server's network/IP may be rate-limited or blocked …)`.
    - **Cause:** googletrans raises `ValueError("invalid destination language")` *before* any network call (googletrans `client.py:263-269`), and `cli.py:32-37` catches every `Exception` and rewraps it. Captured in §4 Step 8.
    - **Fix:** read the first exception in the chained traceback, and use codes from the table at `README.md:225-288`. Case doesn't matter, and `zh-CN`/`zh-TW` work.

13. **Real rate-limiting / blocking from Google.**
    - **Symptom:** the same `RuntimeError`, but the cause is `Exception: Unexpected status code "<code>" from ['translate.googleapis.com']`. This happened in the 2026-10-12 captures: all three Part A runs got `Unexpected status code "429"`, and the Part B runs a few minutes later succeeded.
    - **Cause:** the app uses an unofficial, keyless endpoint (googletrans `constants.py:3`, `urls.py:7`). Requests from cloud-provider IPs are often throttled, and commit `62f821b`'s message and `cli.py:34-36` anticipate exactly this.
    - **Fix:** retry later, use a different region/VM, or run it on your laptop. The production-grade alternative is the official Cloud Translation API with credentials, which a later lecture's service-account work would enable. It has not been tested from a GCP IP.

14. **apt/git/curl hang or time out.**
    - **Cause:** the VM was created without an external IP (and has no Cloud NAT), so it has no outbound internet.
    - **Fix:** edit the VM's network interface to add an ephemeral external IP, or recreate the VM with the default networking.

15. **Surprise bills.**
    - **Cause:** you forgot to delete the VM; or you stopped it instead of deleting it (the disk still bills); or the boot disk's deletion rule was changed to keep the disk.
    - **Fix:** follow `README.md:62` and `:98`, then check *VM instances* and *Disks* (§2).

16. **Wrong directory.**
    - **Symptom:** `` error: No `pyproject.toml` found in current directory or any parent directory `` (from `uv sync`), or `python3: can't open file '…/cli.py'`.
    - **Fix:** `cd ~/simple-translate`.

17. **Moved or renamed the project folder after `uv sync`.**
    - **Cause:** the generated `activate` hard-codes the absolute venv path (`VIRTUAL_ENV='…/.venv'`, line 81 of the captured `activate`).
    - **Fix:** `rm -rf .venv && uv sync`. Venvs aren't relocatable; treat them as disposable build output.

18. **The pipenv branch doesn't work as documented.**
    - **Symptoms:**
      - `pipenv install` creates an empty Pipfile, because the branch README's `git clone` (`origin/pipenv:README.md:27`) checks out `main`, which has no Pipfile
      - pipenv may complain about Python 3.11 vs your system Python (`origin/pipenv:Pipfile:13`)
      - building its Dockerfile fails at `apt-get update`
    - **Cause:** that Dockerfile's base image is Debian 10 *buster* (`origin/pipenv:Dockerfile:2`, `python:3.11-slim-buster`), which is end-of-life and whose apt repositories have been moved to the archive. The failure is expected but was not tested.
    - **Fix:** `git switch pipenv` before `pipenv install`; treat the branch as a reading exercise.

19. **(Applies from L02 on) The Python version in `Dockerfile.txt` disagrees with `pyproject.toml`.**
    - **Cause:** `Dockerfile.txt:2` and `README.md:133-136` use `python:3.12-slim-bookworm`, but `pyproject.toml:6` needs ≥ 3.13.
    - **Effect:** `RUN uv sync` (`Dockerfile.txt:24`) skips the image's 3.12 and downloads a separate CPython (3.15.0 on 2026-10-12, §6 #5) at build time. That makes a bigger image whose base Python goes unused.
    - **Fix:** use a `python:3.13-slim` base or change `requires-python`.
    - **Platform:** the uv binaries and managed Pythons exist for both x86_64 and aarch64, so an Arm VM (t2a/c4a) works too. Apple Silicon issues (amd64 vs arm64 images) only appear in L02 (see the commented `--platform=linux/amd64` at `docker-shell.sh:12`).

20. **The SSH window reconnected and the venv is "gone".**
    - **Symptom:** after a long pause the browser SSH window reconnects; the prompt is back at `~` without `(app)`, `python cli.py` says `command not found`, and `source .venv/bin/activate` says `No such file or directory`.
    - **Cause:** activation lives in one shell (§3.4), and a new login shell starts in your home folder.
    - **Fix:** `cd simple-translate`, then `source .venv/bin/activate`. uv itself is still found, because the installer added its env file to your startup files.

21. **The isolation test "fails" because the venv is still active.**
    - **Symptom:** `python3 -c 'import googletrans'` works on the fresh Part B VM.
    - **Cause:** while the venv is active, `python3` is the venv's too (captured: `.venv/bin/python3 -> python`, and `.venv/bin` is first on `PATH`).
    - **Fix:** `deactivate` first (Step 20).

22. **Your output doesn't match this guide line for line.**
    - **Cause:** the captures ran in Debian containers, not on a Compute Engine VM, and versions move. On a VM, `apt-get update` shows Google's package sources too, `apt install` pulls in fewer packages, apt prints ` Done`, `sudo pip3` may say `Requirement already satisfied` for packages apt already had, and uv/Python/package versions may be newer.
    - **Fix:** compare the shape (the commands' exit, the key lines in §4), not every line.

---

## 7. Where this sits in the course

- **Before:**
  - **Tutorial 0 - Setup & Installs** (`README.md:20-21`) gives you the GCP account and project, VS Code, Git, Docker Desktop and uv on your laptop. It also sets a budget alert and the habit "Delete what you're not using … Stop ≠ delete" (ac215-setup `README.md:197-210`); credentials come later, in its Part B (ac215-setup `README.md:246-247`).
  - Lecture 1 is the first lecture with a tutorial (`tutorials_demo.md:16-27`); the course README lists "Virtual Environments and Virtual Machines" as the third theme, after the MLOps intro and LLM topics.
- **What L01 adds:**
  - Two isolation primitives, the VM (a disposable machine) and the venv (disposable package sets).
  - The vocabulary everything else uses: `pyproject.toml`, `uv sync`, `uv.lock`, `.venv`, `requires-python`, activation.
  - The habit of tearing down cloud resources.
- **Next (L02 Containers I, same repo, `tutorials_demo.md:31-42`):**
  - Walkthroughs 3-4 of this README (`README.md:106-220`) put the *same* `uv sync` inside a Docker image (`Dockerfile.txt:24`), run it locally (`docker-shell.sh:11-15`), and push it to Docker Hub.
  - Then you run the image on a fresh VM that has only Docker (`README.md:207-218`, `sudo docker run --rm -ti dlops/simple-translate`). The image `dlops/simple-translate` is built and pushed multi-arch by `docker-build-push.sh:11` and `:27`.
- **Later:**
  - **L03 mega-pipeline** has you author a `pyproject.toml` yourself with `uv init --bare` (`mega-pipeline/generate_text/README.md:22`) and `uv add` (`:104`). Its `generate_text/pyproject.toml:4` already requires `>=3.14`.
  - **cheese-app/llm-rag** uses the production pattern this repo lacks: a committed `uv.lock`, `UV_PROJECT_ENVIRONMENT=/.venv`, `UV_LINK_MODE=copy` and `uv sync --frozen` (`llm-rag/Dockerfile:17-18`, `:42-45`).
  - pipenv also survives in `cheese-app-v0/api-service` (`Pipfile`, `Dockerfile:44` `RUN pipenv sync`), so the comparison in Part C pays off.
- **Milestone 2** requires "Virtual Environment Setup" ("Create virtual machines/environments to support containers", `milestone2.md:39-41`) and "`pyproject.toml` (using `uv`) for each container" (`milestone2.md:78`).
- **Branch diff (`pipenv` → `main`, unrelated roots):** `git diff --stat origin/pipenv main` reports 11 files changed, 265 insertions, 247 deletions.

  | File | Change | Lines |
  |---|---|---|
  | `.gitignore` | +2 | |
  | `Dockerfile` | removed | −26 |
  | `Dockerfile.txt` | new | +29 |
  | `Pipfile` | removed | −13 |
  | `Pipfile.lock` | removed | −128 |
  | `README.md` | rewritten | ±186 |
  | `cli.py` | rewritten | ±81 |
  | `docker-build-push.sh` | new | +29 |
  | `docker-shell.sh` | changed | ±4 |
  | `pyproject.toml` | new | +10 |
  | `tip.txt` | removed | −4 |

  Meaningful changes:
  1. pipenv/Pipfile replaced by uv/pyproject (the lockfile was dropped along the way)
  2. googletrans 4.0.0rc1 (sync) → 4.0.2 (async), so `cli.py` now uses `asyncio.run` and `async with Translator(raise_exception=True)`
  3. Python 3.11 → ≥3.13 for the app (the Dockerfile still says 3.12)
  4. Debian buster → bookworm base image
  5. Docker build defaults to the native architecture (`docker-shell.sh:11`; the amd64 line at `:12` is commented out), plus a new multi-arch push script
  6. the README gained a narrative ("four ways, each removing a class of fragility", `README.md:9-16`) and tips on `apt` vs `apt-get`, PEP 668, `uv sync` and `activate`

  On `main` itself, history was reset on 2026-08-28 (`5a6849d`); since then `e3bd74e` made `cli.py` async and added `sudo`, `476aec1` bumped googletrans in the README, `2827e2a` bumped `requires-python`/googletrans in `pyproject.toml`, and `62f821b` added the `raise_exception`/`RuntimeError` wrapping.

---

## 8. Exercises

The exercises, with answers, are in [`exercises.md`](https://github.com/JunyiZhou-Conny/Explainer_Videos/blob/main/videos/ac215-l01-vms-venvs/exercises.md) in the video folder; their answers were checked against the 2026-10-12 captures. Do them after watching, without re-watching first, then re-watch only the part you got wrong. A summary follows; open each answer only after you have committed to your own.

### Test yourself: the five questions from the end of the video

**Q1. What does `--break-system-packages` break, and where did `sudo pip3` put the files?**
<details><summary>Answer</summary>

The system Python is externally managed (PEP 668): apt owns its packages in `/usr/lib/python3/dist-packages`, and the OS's own Python tools depend on those versions. The flag overrides pip's refusal. With `sudo`, pip installed into `/usr/local/lib/python3.11/dist-packages` (captured `googletrans.__file__`: `/usr/local/lib/python3.11/dist-packages/googletrans/__init__.py`), which comes **before** apt's folder on `sys.path`. A pip copy that differs from apt's hides apt's for every program on the system Python: what breaks is the guarantee that the OS's tools see the versions apt tested them with.
</details>

**Q2. Name the three parts of a venv.**
<details><summary>Answer</summary>

1. `bin/python`, a symlink to a real interpreter (Debian 12: `python -> /home/student/.local/share/uv/python/cpython-3.15-linux-x86_64-gnu/bin/python3.15`).
2. Its own `lib/python3.X/site-packages/`, empty at first.
3. `pyvenv.cfg` with `include-system-site-packages = false`, which makes Python build a `sys.path` with the venv's site-packages instead of the system's dist-packages.
</details>

**Q3. What does activation change? Name two ways to run the app without it.**
<details><summary>Answer</summary>

`source .venv/bin/activate` saves the old `PATH` and puts `.venv/bin` first (`PATH="$VIRTUAL_ENV/bin:$PATH"`, lines 97-98 of the generated script), exports `VIRTUAL_ENV`, prefixes the prompt with `(app)` and defines `deactivate`. It installs and loads nothing, and only in the current shell. Without it: `uv run python cli.py`, or `.venv/bin/python cli.py`.
</details>

**Q4. `pyproject.toml` lists 2 dependencies. Why were 11 packages installed, and which file makes everyone get the same ones?**
<details><summary>Answer</summary>

Dependencies have dependencies: `googletrans==4.0.2` needs `httpx[http2]`, which needs `anyio`, `certifi`, `httpcore` (→ `h11`), `idna` and `h2` (→ `hpack`, `hyperframe`); with `art`, that's 11. `uv sync` resolved 13 entries: those 11, `typing-extensions` (only for Python < 3.15, so skipped on 3.15 and installed on Debian 13's 3.13: 12 there) and the project itself. **`uv.lock`** freezes the exact versions; the tutorial repo doesn't commit one, so commit yours and use `uv sync --locked` in automated builds.
</details>

**Q5. Is `>=3.13` a pin? What would make the Python version deterministic?**
<details><summary>Answer</summary>

No: it's a constraint with no upper limit. uv uses an interpreter it already has if one fits (Debian 13's `3.13.5`), otherwise it downloads the newest release in range (CPython 3.15.0 on 2026-10-12; earlier the same command gave 3.14). `uv python pin 3.13` writes `.python-version`, and every `uv sync` then uses a 3.13.x (`uv python pin 3.13.5` for one exact release).
</details>

### Hands-on (predict, then run)

**B1 · Which shelf?** Run `python3 -c "import googletrans, sys; print(googletrans.__file__); print(sys.prefix)"` on the Part A VM, then the same with `.venv/bin/python` on the Part B VM.
<details><summary>Answer</summary>

System Python: `/usr/local/lib/python3.11/dist-packages/googletrans/__init__.py` and `/usr`. Venv Python: `/home/<you>/simple-translate/.venv/lib/python3.15/site-packages/googletrans/__init__.py` (or `python3.13` on Debian 13) and `/home/<you>/simple-translate/.venv`. Same import, different shelf, because each interpreter builds its own `sys.path`.
</details>

**B2 · Which Python will uv pick?** Before `uv sync`, run `python3 --version` and `uv python list --only-installed`; predict; run `uv sync` and `cat .venv/pyvenv.cfg`; then `uv python pin 3.13` and `uv sync` again.
<details><summary>Answer</summary>

Debian 12 (3.11.2, outside `>=3.13`): uv downloads the newest release in range, and `pyvenv.cfg`'s `home` points under `~/.local/share/uv/python/`. Debian 13 (3.13.5): `home = /usr/bin`. After the pin, `.python-version` contains `3.13`; on Debian 12 `uv sync` downloads a 3.13.x and rebuilds `.venv`. Pinning `3.11` fails: `` error: The requested Python version `3.11` is incompatible with the project `requires-python` value of `>=3.13`. `` To use 3.11 you must first relax `requires-python`; with `>=3.11` plus `uv python pin 3.11`, the scratch check printed "Using CPython 3.11.17 interpreter at: /usr/bin/python3.11".
</details>

**B3 · Make it reproducible.** In your own fork (or a copy), commit `uv.lock`, add `"rich"` to `dependencies` **by hand** (not with `uv add`), and run `uv sync --locked`. Predict, then fix.
<details><summary>Answer</summary>

uv refuses, because the lock no longer matches `pyproject.toml`: ``error: The lockfile at `uv.lock` needs to be updated, but `--locked` was provided.`` followed by ``hint: To update the lockfile, run `uv lock`.`` (scratch check; it resolved 17 packages before refusing). Fix with `uv lock` (or `uv sync` without `--locked`) and commit both files. With no `uv.lock` at all, `uv sync --locked` fails with `` error: Unable to find lockfile at `uv.lock`, but `--locked` was provided. To create a lockfile, run `uv lock` or `uv sync` without the flag. `` This is why later course Dockerfiles copy `uv.lock*` and run `uv sync --frozen` (`llm-rag/Dockerfile:42-45`).
</details>

**B4 · Read from a file.** Create `msg.txt` with two French sentences and run `python cli.py -f msg.txt -s auto -d en`. Predict the `Arguments:` and `Input:` lines.
<details><summary>Answer</summary>

`Arguments: Namespace(text='I love cheese', file='msg.txt', src='auto', dest='en')`: `-t` keeps its default, but `cli.py:19-21` replaces the text with the file's contents, so `Input:` shows your French. `src='auto'` is accepted because googletrans skips source validation for `auto` (`client.py:255`). A wrong path raises `FileNotFoundError` before any network call, and it isn't wrapped, because the file is read outside the `try`.
</details>

### Debugging

**C1 · "It says the network is down, but it isn't."** `python cli.py -t hello -d xx` ends in the network-flavoured `RuntimeError`. Is the network the problem?
<details><summary>Answer</summary>

No. The first exception in the chained traceback is `ValueError: invalid destination language` (captured, §4 Step 8), raised by googletrans before any request; `cli.py:32-37` catches every exception and re-raises one message. A real network problem looks like `Exception: Unexpected status code "429" from ['translate.googleapis.com']`. For a better program, catch `ValueError` separately or validate against `googletrans.LANGUAGES` first.
</details>

**C2 · `pip` inside the venv.** With `(app)` active on the Part B VM, `pip install rich` gives `pip: command not found`; on the Part A VM, in a venv made the same way, it gives `error: externally-managed-environment`. Explain both, and add `rich` properly.
<details><summary>Answer</summary>

A uv venv has no `pip`, so the shell keeps walking `PATH`. The fresh Part B VM never installed `python3-pip`, so nothing is found; on the Part A VM it finds the system `pip`, which belongs to the externally managed system Python. Use `uv add rich` (it updates `pyproject.toml` and `uv.lock` and installs into `.venv`); `uv pip install rich` would install without recording it.
</details>

**C3 · Activation mechanics.** `./.venv/bin/activate` gives `Permission denied`; `bash .venv/bin/activate` gives no error, but `which python` still prints nothing. Why?
<details><summary>Answer</summary>

`activate` isn't executable (`-rw-r--r--`), and `bash file` runs it in a child shell that changes its own `PATH` and exits. Activation must happen in your current shell: `source .venv/bin/activate` (`README.md:92`).
</details>

**C4 · `uv: command not found` right after installing uv.** Why, and what are two fixes?
<details><summary>Answer</summary>

The installer put `uv` in `~/.local/bin`, but your shell's `PATH` was set before that folder was added. Either `source $HOME/.local/bin/env`, or open a new SSH tab: the installer appended `. "$HOME/.local/bin/env"` to `~/.profile` and `~/.bashrc`.
</details>

### Think

**D1 · Pick the right isolation.** Venv, or VM/container? (a) two projects need different `pandas` versions; (b) your code needs the `libpq` C library and a particular CUDA driver; (c) a teammate on macOS must reproduce your exact Linux setup; (d) you want to try risky `sudo apt` changes without endangering your laptop.
<details><summary>Answer</summary>

(a) A venv per project. (b) A venv isolates only Python packages; system libraries and drivers need a container image (L02) or a VM image. (c) A venv plus `uv.lock` makes the Python packages identical but not the OS; a container gives the same Linux userland. (d) A VM: disposable, delete it when done.
</details>

**D2 · Stop or delete?** You stop your VM on Friday and come back two weeks later. What did you pay for in between, and what would delete have changed?
<details><summary>Answer</summary>

A stopped VM doesn't bill CPU and memory, but its boot disk still exists and bills per GB-month, and so would a reserved static IP. Deleting it (the boot disk goes with it by default) removes both. Then check that **VM instances** and **Disks** are empty.
</details>

---

## 9. Errata and open questions

**Errata (wrong, outdated, ambiguous or inconsistent)**

1. **The promised lockfile doesn't exist.**
   - The claim: `README.md:12` says "pinned in a lock file, so the next person gets the exact same versions", and `README.md:70` says "`uv.lock` pins exact versions so the next person gets the same setup".
   - The evidence: there's no `uv.lock` in the tree (`git ls-files`), and `git log --all -- uv.lock` is empty, so every `uv sync` on a fresh clone resolves anew (captured: `git status` lists `uv.lock` as untracked after `uv sync`). `README.md:87` hedges with "and `uv.lock` if present".
2. **Wrong prompt example.** `README.md:92` shows `(simple-translate) $`. With `name = "app"` (`pyproject.toml:2`), uv's venv prompt is `(app)`: the captures show `prompt = app` in `pyvenv.cfg` and `VIRTUAL_ENV_PROMPT="app"` at line 102 of `activate`.
3. **No pip in a uv venv.** `README.md:92` says activation makes "`python` and `pip` resolve to the venv's binaries". uv venvs contain no `pip` (captured `.venv/bin` listing; `which pip` prints nothing after activation).
4. **Miscount in the activate tip.** `README.md:92` says "Four things … so you can later run `deactivate` to undo all three". The count is internally inconsistent; this is cosmetic.
5. **Python version mismatch between app and Dockerfile.** `pyproject.toml:6` (`>=3.13`, changed in `2827e2a` on 2026-09-02 from `">=3.12,<3.13"`) disagrees with `Dockerfile.txt:2` and `README.md:133-136` (`python:3.12-slim-bookworm`, "Python 3.12 image"). This hits in L02, where uv will download another interpreter inside the image.
6. **"Pinned" isn't a pin.** `requires-python = ">=3.13"` isn't a version pin, and there's no `.python-version`. The README never says that `uv sync` may download a Python, which it does on Debian 12 / Ubuntu 24.04 images (3.15.0 with uv 0.13.0 on 2026-10-12, captured). That makes "the next person gets the same setup" (`README.md:70`) doubly untrue: neither the packages nor the interpreter are fixed. Even the package count depends on the interpreter (11 on 3.15, 12 on 3.13).
7. **Misleading error message.** `cli.py:32-37` wraps *every* exception, including `ValueError("invalid destination language")` from googletrans' validation (`client.py:263-269`), in a message blaming the network or IP (captured, §4 Step 8).
8. **Probably broken Contents links.** `README.md:31-32` use `#installing-app-on-vm-manually` and `#installing-app-on-vm-using-uv`. The course site uses the emoji-derived anchors `#%EF%B8%8F-installing-app-on-vm-manually` and `#-installing-app-on-vm-using-uv` (`tutorials_demo.md:21`, `:26`). The GitHub rendering could not be confirmed offline.
9. **The VM spec is underspecified.** `README.md:42` and `:72` give no machine type, zone, image or networking guidance. The outcome depends on the image: whether `--break-system-packages` exists (pip ≥ 23.0.1), and whether uv downloads a Python (Debian 12: yes; Debian 13: no, captured).
10. **Part A and Part B can get different `art` versions.** `README.md:53` installs `art` unpinned in Part A, while `pyproject.toml:8` says `art>=6.5`. The difference is small (both captures got `art` 6.5).
11. **The `pipenv` branch is stale as a runnable tutorial.**
    - Its README clones the default branch (`origin/pipenv:README.md:8`, `:27`), so the `Pipfile` isn't present unless you switch branches.
    - Its Docker base `python:3.11-slim-buster` (`origin/pipenv:Dockerfile:2`) is Debian 10, which is EOL.
    - It tags images as `…-e115` (`origin/pipenv:README.md:91`), a leftover from another course.
    - The AWS track still uses pipenv (`tutorials_demo.md:24-27`).
12. **Boilerplate metadata.** `pyproject.toml:4` (`description = "Add your description here"`) and `name = "app"` are `uv init` boilerplate. That's harmless, but it's why the prompt reads `(app)`.
13. **"Same VM" vs a new VM.** `README.md:12` ("Same VM, but with `uv`") and `README.md:70` ("same VM, but isolated") suggest reusing the walkthrough A machine, but `README.md:62` says to delete it and `README.md:72` starts by creating a new one. Following the bullets (a fresh VM of the same kind) is what the captures did.

**Open questions (couldn't be determined from the sources)**
- What the Ed lesson (slides, lecture notes) adds or changes relative to the README. The Ed content was not accessible.
- Which boot image the GCP console defaults to when students do the lab (Debian 12 vs 13). That decides whether uv uses the system Python or downloads one; the captures show both outcomes.
- Whether `translate.googleapis.com` rate-limits or blocks GCP egress IPs in particular. The captures (from containers, not a GCP VM) got HTTP 429 for the three Part A runs and real translations a few minutes later; commit `62f821b` and `cli.py:34-36` suggest blocking has happened. No run from a Compute Engine VM was made.
- Whether instructors intend a new VM per walkthrough (as written, `README.md:72`) or reuse of one VM (as `README.md:12` and `:70` suggest). Reuse is cheaper and demonstrates the isolation better.
- Whether the pipenv branch (`googletrans==4.0.0rc1`, `httpx==0.13.3`) still runs at all today. Not tested.

---

## Links

- README sections (pinned commit): [🛠️ Installing App on VM Manually](https://github.com/dlops-io/simple-translate/blob/62f821bfe09fc1c2ecb0f14354b1f205777c0efa/README.md#%EF%B8%8F-installing-app-on-vm-manually) · [⚡ Installing App on VM using UV](https://github.com/dlops-io/simple-translate/blob/62f821bfe09fc1c2ecb0f14354b1f205777c0efa/README.md#-installing-app-on-vm-using-uv) · latest README on [`main`](https://github.com/dlops-io/simple-translate?tab=readme-ov-file#%EF%B8%8F-installing-app-on-vm-manually) · the [`pipenv` branch](https://github.com/dlops-io/simple-translate/tree/pipenv)
- Tutorial 0: [AC215 · Tutorial 0 - Setup & Installs](https://github.com/dlops-io/ac215-setup/blob/61a7b9dd538e581a126117585db40c9e6b5d46b9/README.md)
- Ed lesson: [L1 · Virtual Environments and Virtual Machines](https://edstem.org/us/courses/97373/lessons/166027/) · course [tutorials page](https://harvard-iacs.github.io/2026-AC215/tutorials_demo/)
- Video and materials: [video folder](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l01-vms-venvs) · [exercises.md](https://github.com/JunyiZhou-Conny/Explainer_Videos/blob/main/videos/ac215-l01-vms-venvs/exercises.md) · [terminal captures](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l01-vms-venvs/assets/terminal)
- Next lecture: [L02 · Containers I](L02-containers-1.md) (the same `uv sync`, inside a Docker image)
- Referenced in §7: [L03 · Containers II (mega-pipeline)](L03-containers-2-mega-pipeline.md) · [L05 · Introduction to RAG (llm-rag)](L05-rag.md) · [L10 · Connecting to the Cloud (cheese-app-v0)](L10-cloud-connect-cheese-app-v0.md)
