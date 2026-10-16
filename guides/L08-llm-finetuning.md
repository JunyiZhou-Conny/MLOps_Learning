# L08 · LLM: Finetuning — study guide

[Ed lesson](https://edstem.org/us/courses/97373/lessons/166032/) · Tutorial: [`dlops-io/llm-finetuning`](https://github.com/dlops-io/llm-finetuning) `main` @ [`44ef6f0`](https://github.com/dlops-io/llm-finetuning/tree/44ef6f0a70315aa0a551b8565ca862679a87c1eb) (whole README; last year's branch `pipenv` @ [`fb0073a`](https://github.com/dlops-io/llm-finetuning/tree/fb0073a87ec81ad1e5acb0adc58f3c1a6c307341), read for comparison only) · Colab: [Tutorial - Finetuning with QLoRA](https://colab.research.google.com/drive/1oX3ADMHphW2v7mwV7zkEWD5oYewJZEAC) · Video: planned · Made from the verified digest, 2026-10-13

## 中文速览

- **做什么：** 两条 track，目标都是把 model 教成用 "Pavlos style" 回答 cheese 问题。**Track A（repo，managed fine-tuning）**：在 laptop 上跑两个 Docker container。`dataset-creator` 里 `python cli.py --generate` 让 Gemini（`gemini-3.1-flash-lite`，`location="global"`）生成 5 批、每批 20 个 Q&A，`--prepare` 去重 + 90/10 split，写出 Gemini 格式的 `train.jsonl`/`test.jsonl`，`--upload` 传到你自己的 GCS bucket；`gemini-finetuner` 里 `--train` 向 Vertex AI（现在改名叫 "Agent Platform"）提交一个 supervised tuning job，`--chat` 调你自己的 tuned endpoint。**Track B（Colab，open-source PEFT）**：用 QLoRA 微调 `Qwen/Qwen3-0.6B`（4-bit NF4 + LoRA r=8），900 条数据、450 steps，A100 上约 3.5 分钟。
- **Idea 1 · fine-tuning 改的是 weights，学到的是 style 不是 facts：** prompting 改 prompt，RAG（L05）改 input 里的 context，fine-tuning 改 weights。它擅长 tone、persona、format，但不能可靠地注入新 facts。stored run 里问 "Why is the sky blue?"，fine-tuned model 开口就是 "Yello - this is Pavlos your cheese monker…"，物理却照样是错的（怪到 water molecules 头上）。
- **Idea 2 · synthetic data 和数据格式：** teacher LLM + 一个很长的 system prompt + `response_schema`（structured output）批量造 training data，teacher 的 hallucination 也会被 student 一起学走。同一个 Q&A pair 依次变成 CSV row → Gemini JSONL（`role` 是 `user`/`model`）→ Qwen3 的 chat template（`<|im_start|>`、空的 `<think></think>`、EOS `<|im_end|>`）→ token IDs。training 和 inference 用的 template 必须一致。
- **Idea 3 · managed tuning 是一个 async job：** `tunings.tune(...)` 只是一个 HTTPS POST 到 `us-central1`，Google 在自己的 hardware 上训练一个 adapter（`ADAPTER_SIZE_FOUR`），你最后拿到的是 endpoint（`projects/<num>/locations/us/endpoints/<id>`），拿不到 weights。一共三个 location：generation 用 `global`，tuning 用 `us-central1`，serving 用 multi-region `us`（google-genai 1.39.1 需要 `base_url` override）。`--train` 打印 `Tuned model info: None` 是正常的：`main()` 写死了 `wait_for_job=False`，要去 console 看 job 状态。
- **Idea 4 · QLoRA = 4-bit quantization + LoRA：** NF4 把每个 weight 存成 16 个 level 之一的 4-bit index（double quant 再压缩 per-block constants，算的时候 dequantize 成 fp16）；LoRA 学 `ΔW = (α/r)·B·A`，B 初始化为 0，PEFT 对 Qwen3 默认只挂在 `q_proj`/`v_proj` 上，所以是 1,146,880 个 trainable params（0.30%），adapter 只有 4.6 MB。`print` 出来是 375.8 M 而不是 596 M，因为两个 4-bit weight 打包进一个 byte。
- **Idea 5 · 怎么判断 work 了：** 同样 100 条 test data，adapter 关掉 vs 打开：loss 2.65 → 1.39，perplexity 14.15 → 4.00。但 loss 算的是所有 token（包括 question 和 template），所以它主要衡量 style fit，不代表答案更正确。
- **最费时间的坑：** ① README 没说要改 code：`env.dev` 里的 `GCP_PROJECT`/`GCS_BUCKET_NAME`，`gemini-finetuner/cli.py:10-11` 写死的 `gs://cheese-dataset/...`，还有 `:107` 的 `MODEL_ENDPOINT`（instructor 的 endpoint）都要换成你自己的；bucket 要自己建，Vertex AI API 要自己 enable。② Ubuntu/Debian/WSL 上 `sh docker-shell.sh` 报 `source: not found`（`/bin/sh` 是 dash），改用 `bash docker-shell.sh`。③ `--generate` 把所有 error 都吞掉：key 没放在 repo **旁边**的 `secrets/llm-service-account.json`，五批全部失败，接着 `--prepare` 报 `KeyError: 'question'`。每一行输出都要读。
- **Colab 的坑：** 别跳过 `!uv pip uninstall torchao`（否则 nb cell 86 merge 时会报 ImportError；这是读 peft source 推断的，没有实测）；别删 nb cell 72 的 fp32 cast（`fp16=True` 没法 unscale bf16 gradients）；改了 LoRA config 想重训，先重跑 nb cell 36 重新 load model。
- **做完要删：** `gcloud storage rm -r gs://<bucket>/llm-finetune-dataset-small`（或者删整个 bucket）；tuned model/endpoint 在 console 里删（L10 `cheese-app-v0` 还要用，可以留到 L10 之后）；不用的 SA key 删掉；本地 `docker image rm llm-dataset-creator gemini-finetuner`；Colab 用 *Runtime → Disconnect and delete runtime*，Drive 空间不够就删 `MyDrive/LLM_cache`。
- **Lecture slides：** 老师的 Lecture 8 slides（`L08_FineTuning_v2`，73 页）讲的是 Track B 背后的理论：instruction fine-tuning、full fine-tuning 的显存账（10B model 约 120 GB）、LoRA，再到 QLoRA（4-bit NF4 + paged optimizer，10B 约 12 GB）；Track A（Gemini managed tuning）不在 slides 里。这份 guide 各节和 slides 怎么对应、做 tutorial 需要的 10 个 lecture ideas，以及 slides 和 notebook 不一样的 8 处，都在下面的 [Lecture slides](#lecture-slides)。最要紧的两处：① slides 用 BF16 计算，notebook 为了 T4 用 FP16，并把 adapters 转回 FP32；② slides 跳过了 double quantization，notebook 打开了 `bnb_4bit_use_double_quant=True`。

## At a glance

**What you build.** In Track A (the repo), two Docker containers on your laptop have Gemini write about 100 synthetic cheese Q&A pairs in Pavlos' voice, convert them to Gemini's JSONL tuning format, upload them to your Cloud Storage bucket and submit a managed supervised tuning job, which leaves a tuned-Gemini endpoint in your project that you then chat with. In Track B (Colab), you fine-tune `Qwen/Qwen3-0.6B` yourself with QLoRA (a frozen 4-bit NF4 base plus LoRA adapters), compare loss and perplexity with the adapter off and on, and save a 4.6 MB adapter and a 1.2 GB merged model to Google Drive.

**Time needed** (estimate). Track A: about 1-1.5 h of hands-on time (the service account and key are reused from L05 if you have them; the first image build takes several minutes), plus the wait for the tuning job, whose duration for a ~90-example, 1-epoch job is an open question (§9). Track B: about 1 h; training itself takes "~3.5 min on A100, ~4.5 min on L4, ~6-7 min on T4" (nb cell 75:2). The exercises (§8) add 1-2 h.

**Prerequisites.**
- Track A: a GCP project with billing enabled; the service account `llm-service-account` with **Storage Admin** and **Agent Platform User** (`roles/aiplatform.user`), its JSON key in `<parent>/secrets/` next to the repo (the same SA and folder as L05); the Vertex AI API enabled; a bucket of your own.
- Locally: Docker, `git`, a shell that understands `source` (`bash`), optionally the `gcloud` CLI.
- Track B: a Google account (Colab and Drive), a free Hugging Face account and access token, a GPU runtime (the free T4 works).
- Background: containers, bind mounts and `docker-shell.sh` scripts (L02-L04); the `llm-rag` container, service account and google-genai client (L05); structured output (L06-L07).

**What it costs.** Track A: dataset generation costs cents (5 calls), Cloud Storage is negligible, and the tuning job is billed per training token × epochs. At the README's stale price ($0.008 per 1k tokens), a ~24k-token dataset × 1 epoch ≈ $0.19; check the current price. Managed tuned-Gemini endpoints are understood to be billed per request/token with no per-hour node charge (not verified, §9). Track B: free on a T4; A100/L4 need Colab Pro or compute units. A few GB of Drive; a private Hugging Face repo is free.

**Tear down, exactly** (§2):
1. `gcloud storage rm -r gs://<bucket>/llm-finetune-dataset-small`, or delete the bucket.
2. Delete the tuned model/endpoint in the console (Agent Platform / Vertex AI → Tuning, Model Registry, Endpoints) once you're done with it. Keep it until after L10 if you want to use it in `cheese-app-v0`.
3. Delete old service-account keys you no longer use.
4. Locally: `docker image rm llm-dataset-creator gemini-finetuner`.
5. Colab: Runtime → Disconnect and delete runtime. Delete `MyDrive/LLM_cache` if you need the space.

<details>
<summary><b>Versions and sources this guide was checked against</b></summary>

- **Lecture-to-tutorial mapping:** the course-site source `2026-AC215/tutorials_demo.md:112-118`. The weekly schedule lists "LLM - Finetuning" on **Oct 1** but labels it "Lecture 7" (`2026-AC215/_modules/week-05.md:11-13`). The Ed lesson itself was not accessible, so this guide is built from the repo and the Colab notebook.
- **Repo:** `dlops-io/llm-finetuning`, branch **`main`** (default), commit `44ef6f0a70315aa0a551b8565ca862679a87c1eb`, committed 2026-10-05 22:52:07 -0400 ("remove pipfile from gemini-finetuning"). This is also the course map's pin (`MLOps_Learning/course/lectures.yaml:27`).
  - Commits that shape this year's version:
    - `c9b52dd` (2025-10-14): Pipenv → uv, `vertexai` SDK → `google-genai`; generator and tuning base both moved from Gemini 1.5 Flash to `gemini-2.0-flash-001`
    - `1947094` (2026-09-26): tuning base model `gemini-2.0-flash-001` → `gemini-3.1-flash-lite`
    - `aee790a` (2026-09-26): separate train/chat clients, with tuning in `us-central1` and serving in multi-region `us`
    - `6e4c3f7` (2026-09-30, the night before the lecture): dataset generator moved to `gemini-3.1-flash-lite` at `location="global"`; new answer openers in the system prompt; `dataset-creator/data/.gitkeep` deleted
    - `3b9f6a3` + `0ce885e` (2026-10-04): README rewritten for the Vertex AI → "Agent Platform" rename and the location of the secrets folder
- **Other branch, read for comparison only:** `pipenv` @ `fb0073a87ec81ad1e5acb0adc58f3c1a6c307341` (2025-03-10). This is last year's version (Pipenv, `vertexai.preview.tuning.sft`, `gemini-1.5-flash-002`). It's an ancestor of `main`.
- **README sections this lecture covers:** the whole README (`README.md:1-316`):
  - [Prerequisites](https://github.com/dlops-io/llm-finetuning#prerequisites) `README.md:31-69`, including [Setup GCP Service Account](https://github.com/dlops-io/llm-finetuning#setup-gcp-service-account) `:38-69`
  - [Generate Question Answer Dataset](https://github.com/dlops-io/llm-finetuning#generate-question-answer-dataset) `README.md:75-222`:
    - [Run Container](https://github.com/dlops-io/llm-finetuning#run-container) `:79-94`
    - [Generate Text](https://github.com/dlops-io/llm-finetuning#generate-text) `:98-155`, which includes System Prompt, Input Prompt and Number of Iterations
    - [Sample Question Answers](https://github.com/dlops-io/llm-finetuning#sample-question-answers) `:159-175`
    - [Prepare Dataset](https://github.com/dlops-io/llm-finetuning#prepare-dataset) `:179-212`
    - [Upload Dataset](https://github.com/dlops-io/llm-finetuning#upload-dataset) `:216-222`
  - [Fine-tune Gemini](https://github.com/dlops-io/llm-finetuning#fine-tune-gemini) `README.md:228-316`:
    - [Run Container](https://github.com/dlops-io/llm-finetuning#run-container-1) `:232-247`
    - [Fine-tune Model](https://github.com/dlops-io/llm-finetuning#fine-tune-model) `:251-261`
    - [Cost of Fine-tuning](https://github.com/dlops-io/llm-finetuning#cost-of-fine-tuning) `:265-278`
    - [Chat with Fine-tuned Model](https://github.com/dlops-io/llm-finetuning#chat-with-fine-tuned-model) `:282-316`
  - **Not covered by the README:** the `autotrain-runner/` folder (an older open-source path, see §6 and §9).
- **Colab notebook:** "Tutorial - Finetuning with QLoRA", https://colab.research.google.com/drive/1oX3ADMHphW2v7mwV7zkEWD5oYewJZEAC (the course site calls it "LLM Fine Tuning Notebook"), read from a downloaded JSON copy, `colab/L08_llm_finetuning.ipynb`.
  - 91 cells, cited as **nb cell N**, where N is the 0-based index in the notebook JSON (Colab shows no numbers); "nb cell 70:2-18" means lines 2-18 of that cell.
  - Stored outputs come from a run on an **A100** (`metadata.colab.gpuType`). That run used Python 3.13.15 (nb cell 8 output) and torch 2.11.0+cu128, transformers 5.16.1, peft 0.20.0, trl 1.14.0 and bitsandbytes 0.50.2 (nb cell 12 output).
- **Library behaviour** was checked by reading the sources of the exact versions the code uses:
  - `google-genai` 1.39.1, the version pinned in `dataset-creator/uv.lock:566-567`
  - `transformers` 5.16.1, `trl` 1.14.0 and `peft` 0.20.0, the versions the notebook installs
  - `google-auth` 2.41.1, the version locked in `dataset-creator/uv.lock:502-503`, for error strings (2.62.0 has the same message, but at `_default.py:179` instead of `:174`)
  - for comparison only: `google-genai` 2.30.0, found installed in a local Docker image layer (not the version this repo locks)
- **Method:** the PyPI wheels were unpacked and read, not run. Small stand-alone snippets were run: a pydantic coercion test, a pandas empty-frame test, argparse help rendering and a `dash` vs `bash` `source` test; the adversarial checks added a Python `str`-enum f-string test, a parse of `uv.lock` for cp312 Linux aarch64 wheels, and re-runs of the `dash` `source`, argparse and empty-DataFrame tests. No repository script, Dockerfile or notebook was executed, and no cloud resources were created, so no tuning job was run. Verified against the repos on 2026-10-13.
- **Path convention:** unprefixed `_api_client.py`, `_common.py`, `_transformers.py` and `types.py` are google-genai 1.39.1 files (`google/genai/…`) unless another version is named; `_default.py` is google-auth. `trl/…`, `peft/…` and `transformers/…` paths are in those packages at the versions above. `cli.py`, `Dockerfile` and `docker-shell.sh` without a folder are the files of the container the surrounding step is about.

</details>

## Lecture slides

The instructor's deck for this lecture is *Lecture 8: LLM Finetuning* (`L08_FineTuning_v2`), 73 slides. Slide numbers are PDF page numbers; the printed footers differ, because the deck was cut from a longer one. The slides are not reproduced here; what follows is in our own words. The full slide digest and the cross-check with the video live in the Explainer_Videos repo, in `videos/ac215-l08-llm-finetuning/SLIDES.md`. The deck is the theory behind **Track B**, the QLoRA notebook: instruction tuning, the memory bill of full fine-tuning, LoRA, then QLoRA. **Track A** (Gemini, managed tuning) is not on the slides; the one shared idea is the instruction dataset. The slides answer §9's open question about what the lecture adds, except for double quantization, which they skip.

**Map**

| This guide | Slides |
|---|---|
| §1 What you build; §3.1 | 4, 6–8 (instruction fine-tuning; a tuned model's learned opener vs plain next-word prediction) |
| §3.2; §4 Steps 6–7; checklist *Generate Question Answer Dataset* | 4–5 (the instruction dataset) |
| §3.3 | 5, 8 (the JSONL and chat-template formats are tutorial-only) |
| §3.4; §4 Steps 9–13; checklist *Fine-tune Gemini* | none (Track A is not on the slides); 13–16 show why full fine-tuning is hard to do yourself |
| §3.5; §4 Steps 19–21; §5 Excerpt 9; checklist *Part B* | 43–55 (buckets, absmax, NF4), 68–69 (stored in 4 bits, computed in 16) |
| §3.6; §4 Step 23; §5 Excerpt 11; §8 E1 | 18–35 (PEFT, LoRA, the parameter table), 41 |
| §3.7; §5 Excerpt 12; §6.14 | 11–15, 37–39 (memory bills), 57–65 (gradient checkpointing, paged optimizer), 66–72 (BF16, QLoRA) |
| §3.8; §4 Step 25; §8 E7 | 9–10, 36 (catastrophic forgetting), 40 (LoRA vs full fine-tuning), 51 (quantization error) |
| §4 Step 26 | 30 (merging) |
| §2, §6 (except 6.14), §7, §9; the Track A setup | none (tutorial-only) |

Lecture-only: multi-task fine-tuning (10), the GPT-4 training-cost aside (11–12) and the PEFT family map beyond LoRA (19–20).

**Lecture ideas you need for this tutorial**
1. Fine-tuning usually means instruction fine-tuning: training on pairs of an instruction and its answer, sometimes with context. The tutorial's `instruct-dataset.csv` is the two-field case (slides 4–5).
2. Tuning leaves habits you can see: a chat-tuned model opens with "Sure, here's…", where plain next-word prediction, the slides argue, would give just the haiku. The Pavlos openers are this on purpose (slides 7–8).
3. Full fine-tuning of a 10B model in FP16 needs about 120 GB: 20 GB of weights, 20 GB of gradients and 80 GB of FP32 Adam states (slides 13–15).
4. LoRA freezes W₀ and learns ΔW = (α/r)·B·A in a branch beside it. B starts at zero, so training starts from the pretrained model. Here r = 8 and α = 16 (slides 22, 26–28).
5. A low-rank pair has far fewer numbers than the matrix it updates, and only the pair trains. The slides' table treats a model as one layer; the notebook's exact count is 1,146,880 (slides 23–25, 31–35).
6. LoRA still keeps the 16-bit base in GPU memory (about 40 GB for 10B), so QLoRA shrinks the base (slides 37–39, 43).
7. Quantization sorts numbers into buckets: scale by the absolute maximum, round, and accept a small error when you scale back (slides 44–51).
8. NF4 has 16 buckets, each holding an equal share of the bell-shaped weights, so precision is densest near zero (slides 54–55).
9. Gradient checkpointing stores only some activations and recomputes the rest; the paged optimizer moves optimizer state to CPU RAM when the GPU fills up (slides 57–65).
10. QLoRA stores W in NF4, dequantizes it to 16 bits for each matrix multiply, trains only the adapters, and can merge them into the weights at the end. A 10B model drops to about 12 GB (slides 30, 68–72).

**Where the slides and the tutorial differ** (in each case, the notebook's stored run and PEFT 0.20.0 show what the code does)
- Slides 66–70 and 72 compute in BF16 with BF16 adapters. The notebook computes in FP16 (`bnb_4bit_compute_dtype="float16"`, `fp16=True`) so that T4s work, and casts the adapters to FP32 (nb cells 31, 34, 70, 72; §3.7).
- Slide 53 skips double quantization. The notebook turns it on with `bnb_4bit_use_double_quant=True` (§3.5).
- Slides 27–30 draw A from a normal distribution. PEFT's default draws A from a Kaiming-uniform distribution (`"gaussian"` is opt-in). B = 0 in both, so the update still starts at zero (§3.6).
- Slides 22 and 41 add adapters "to each layer". PEFT's Qwen3 default adapts only `q_proj` and `v_proj` in each of the 28 layers (§3.6; E1 for `all-linear`).
- Slides 45–51 use one absmax constant for a whole array and round to Int8. bitsandbytes uses one constant per small block and 16 NF4 levels (§3.5).
- Slide 29 says the backward pass doesn't use the pretrained weights, and slides 29 and 70 say gradients flow only through the adapters. W₀ gets no gradient and no update, but gradients still pass through it to earlier layers (§3.7).
- Slide 30 merges the update into the weights. The notebook merges into a freshly loaded FP16 base, not the 4-bit one, and recommends keeping the 4.6 MB adapter (nb cells 83–86; §4 Step 26).
- Slide 25 says a higher rank gives better performance. Poll 3 (nb cell 68) adds the cost: more trainable parameters and slower training, for "potentially" better results (§3.6).

## Command checklist

Commands in backticks are exactly as the README, the code or the notebook writes them (placeholders kept). Plain items are console clicks, file edits or notebook cells (nb cell N = 0-based index). Items marked *(extra)* are not in the tutorial; they come from §4 of this guide. All `python cli.py …` commands run **inside** the container that `docker-shell.sh` opens; items marked "host" run in a second terminal on your laptop. Track B (Colab) does not need GCP, so you can do it first.

### Prerequisites

*Clone* (`README.md:31-34`)
- [ ] `git clone https://github.com/dlops-io/llm-finetuning.git` — *(extra)* run it in the parent folder that will also hold `secrets/`; the README only links the repo (`README.md:34`).
- [ ] `git -C llm-finetuning log -1 --oneline` — *(extra)* expect `44ef6f0 remove pipfile from gemini-finetuning`, or newer.

*Setup GCP Service Account* (`README.md:38-69`; skip the SA and key if you have them from L05)
- [ ] GCP Console → IAM & Admin → Service accounts: create `llm-service-account`.
- [ ] In "Grant this service account access to project" select **Storage Admin** and **Agent Platform User** (formerly Vertex AI User; role ID `roles/aiplatform.user`).
- [ ] Open the service account → **KEYS** tab → **ADD Key (Create New Key)** → **JSON**. The key file downloads.
- [ ] Create a folder `secrets` **next to** the `llm-finetuning` repository (not inside it), copy the key into it and rename it to exactly `llm-service-account.json`.
- [ ] `ls <parent>/secrets` — *(extra)* shows `llm-service-account.json`, not `…json.json`.

### Before the containers *(extra)*

- [ ] Edit `env.dev`: `GCP_PROJECT` (`:6`), `GCS_BUCKET_NAME` (`:7`) and the project part of `GCP_SERVICE_ACCOUNT` (`:9`) — implied by the "CHANGE TO YOUR …" comments.
- [ ] `gcloud services enable aiplatform.googleapis.com storage.googleapis.com` — *(extra)* enables Vertex AI and Cloud Storage; the README never says to.
- [ ] `gcloud storage buckets create gs://<bucket> --location=us-central1` — *(extra)* `--upload` needs an existing bucket; use the same name as in `env.dev:7`.
- [ ] `gcloud storage ls` — *(extra)* lists your bucket.
- [ ] Edit `gemini-finetuner/cli.py:10-11` — *(extra; required)* replace `gs://cheese-dataset/...` with `gs://<bucket>/llm-finetune-dataset-small/train.jsonl` and `.../test.jsonl`. No rebuild needed: `/app` is a bind mount.
- [ ] `mkdir -m 777 dataset-creator/data` — *(extra, host, Linux only)* lets the container user (uid 1000) write `data/` (§6.6).

### Generate Question Answer Dataset

*Run Container* (`README.md:79-94`)
- [ ] `cd dataset-creator` — *(extra)* the README only says "Make sure you are inside the `dataset-creator` folder" (`README.md:83`).
- [ ] `sh docker-shell.sh` — sources `../env.dev`, builds image `llm-dataset-creator`, opens an interactive bash in `/app`. On Ubuntu/Debian/WSL use `bash docker-shell.sh` (§6.1).
- [ ] `ls -la /secrets` — the Prerequisites tip (`README.md:69`), run here because it needs the container: the key must be listed.
- [ ] `which python` — *(extra)* `/.venv/bin/python`.
- [ ] `python cli.py --help` — prints `usage: cli.py [-h] [--generate] [--prepare] [--upload]`.
- [ ] `docker rm -f llm-dataset-creator` — *(extra, host)* only if you hit `Conflict. The container name "/llm-dataset-creator" is already in use`.
- [ ] `docker exec -it llm-dataset-creator bash` — *(extra, host)* a second shell into the running container; it skips the entrypoint, so run the next item first.
- [ ] `source /.venv/bin/activate` — *(extra)* in that second shell, otherwise `python cli.py` fails with `ModuleNotFoundError`.

*Generate Text* (`README.md:98-155`)
- [ ] `python cli.py --generate` — 5 Gemini calls → `data/cheese_qa_0.txt` … `cheese_qa_4.txt`. Errors are printed per batch, not raised: read every line.
- [ ] `ls dataset-creator/data` — *(extra, host)* five `cheese_qa_*.txt` files, each a JSON array of ~20 objects.
- [ ] Optional, for a larger dataset: change `NUM_ITERATIONS = 5` (`README.md:154`; in the code at `dataset-creator/cli.py:170`) and re-run `python cli.py --generate`. The README's "default parameters" (`README.md:106`) are module constants, not CLI flags.

*Sample Question Answers* (`README.md:159-175`)
- [ ] Open one `data/cheese_qa_*.txt` and compare it with the README sample. Expect different openers (§6.8).

*Prepare Dataset* (`README.md:179-212`)
- [ ] `python cli.py --prepare` — dedupe, 90/10 split; writes `instruct-dataset.csv`, `train.csv`/`test.csv`, `train.jsonl`/`test.jsonl`. Expect `Number of errors: 0`.
- [ ] `head -c 300 data/train.jsonl` — *(extra)* `{"contents":[{"role":"user","parts":[{"text":"...`.
- [ ] `wc -l data/*.jsonl` — *(extra)* one line per example.

*Upload Dataset* (`README.md:216-222`)
- [ ] `python cli.py --upload` — five files to `gs://$GCS_BUCKET_NAME/llm-finetune-dataset-small/`.
- [ ] `gcloud storage ls gs://<bucket>/llm-finetune-dataset-small/` — *(extra, host)* the five objects.
- [ ] `python cli.py --generate --prepare --upload` — *(extra)* the flags combine and run in that order (`cli.py:300-307`).

### Fine-tune Gemini

*Run Container* (`README.md:232-247`)
- [ ] `exit` — *(extra)* leave the dataset container (`--rm` deletes it).
- [ ] `cd ../gemini-finetuner` — *(extra)* the README only says "Make sure you are inside the `gemini-finetuner` folder" (`README.md:236`).
- [ ] `sh docker-shell.sh` — builds image `gemini-finetuner` (fast: the layers up to `uv sync` are cached). `bash docker-shell.sh` on dash systems.
- [ ] `python cli.py --help` — prints `usage: cli.py [-h] [--train] [--chat]`.

*Fine-tune Model* (`README.md:251-261`)
- [ ] `python cli.py --train` — submits the tuning job and prints `Job name: projects/<project-number>/locations/us-central1/tuningJobs/<id>`; after ~60 s it prints `Tuned model info: None` (normal) and exits.
- [ ] Console: [Agent Platform (formerly Vertex AI) → Tuning](https://console.cloud.google.com/agent-platform/tuning/managed). Watch the job until **Succeeded**, and check that its dataset URI is your bucket.
- [ ] Optional *(extra)*: change `gemini-finetuner/cli.py:126` to `train(wait_for_job=True)` so the CLI polls every minute.

*Cost of Fine-tuning* (`README.md:265-278`)
- [ ] Read the table, then check the current price on the [pricing page](https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing). The table prices Gemini 1.5 Flash at 3 epochs; the code tunes `gemini-3.1-flash-lite` for 1 epoch.

*Chat with Fine-tuned Model* (`README.md:282-316`)
- [ ] *(extra; required)* Copy your tuned model's endpoint (`projects/<num>/locations/us/endpoints/<id>`) from the console into `MODEL_ENDPOINT` at `gemini-finetuner/cli.py:107`.
- [ ] `python cli.py --chat` — asks "How is cheese made in Greece? Answer pavlos style?" and prints `Fine-tuned LLM Response: …`.
- [ ] Optional: try the hosted [Pavlos Cheese Model](https://ac215-llm-rag.dlops.io/finetunechat) (Chrome recommended).
- [ ] Console: on the job's detail page, look at the "Training Monitor" curves and the "Data distribution" tab.

### Clean up Track A *(extra)*

- [ ] `gcloud storage rm -r gs://<bucket>/llm-finetune-dataset-small` — *(extra)* or delete the bucket.
- [ ] *(extra)* Console: delete the tuned model/endpoint (Agent Platform / Vertex AI → Tuning, Model Registry, Endpoints), after L10 if you use it in `cheese-app-v0`.
- [ ] *(extra)* Delete old service-account keys you no longer use.
- [ ] `docker image rm llm-dataset-creator gemini-finetuner` — *(extra, host)* removes both images.
- [ ] `uv remove chromadb langchain langchain-community openai openai-agents` — *(extra, optional)* trims the unused dependencies before a rebuild (§6.9).

### Colab: Tutorial - Finetuning with QLoRA

*Part A: Setup / Environment* (nb cells 1-16)
- [ ] File → Save a copy in Drive; Runtime → Change runtime type → GPU (T4 is fine) (nb cells 1-2).
- [ ] `!uv pip install transformers==5.16.1 tokenizers==0.23.1 huggingface-hub==1.29.0 bitsandbytes==0.50.2` — nb cell 8.
- [ ] `!uv pip install trl==1.14.0` — nb cell 8.
- [ ] `!uv pip uninstall torchao` — nb cell 8; do not skip it (§6.13).
- [ ] Colab Secrets (key icon): add `HF_TOKEN` and turn on "Notebook access" (nb cell 9).
- [ ] Nb cell 10: `userdata.get('HF_TOKEN')` and `login(token=hf_token)`. Expect `Hugging Face token successfully loaded.`
- [ ] Nb cell 12 (imports). Expect `torch 2.11.0+cu128 | transformers 5.16.1 | peft 0.20.0 | trl 1.14.0 | bitsandbytes 0.50.2`.
- [ ] Nb cell 14: `drive.mount('/content/drive')`; the cache is `/content/drive/MyDrive/LLM_cache`.
- [ ] `!hf download --repo-type model --quiet --cache-dir {cache_dir} facebook/opt-350m --exclude "*.h5" --exclude "*.msgpack"` — nb cell 16.
- [ ] `!hf download --repo-type model --quiet --cache-dir {cache_dir} Qwen/Qwen3-0.6B` — nb cell 16.

*Part B: The 'Q' in QLoRA* (nb cells 17-28)
- [ ] Nb cell 18: load OPT-350m with the 4-bit bnb config. Poll 1 (nb cell 20): the main advantage is memory.
- [ ] Nb cell 21: `print(model)` shows `Linear4bit` layers; `lm_head` stays `Linear`.
- [ ] Nb cells 23, 25: tokenize "Hello my cheese name is".
- [ ] Nb cell 27: generate 20 tokens.
- [ ] Nb cell 28: read the "Deeper Dive" notes (markdown only).

*Part C: Fine-Tuning Qwen3 0.6B with QLoRA* (nb cells 29-90)
- [ ] Step 1, nb cells 31-36: GPU check, model name, bnb config, tokenizer + model + `prepare_model_for_kbit_training`.
- [ ] Step 2, nb cells 38-48: parameter count (375.84896 millions), `use_cache = False`, config, baseline generation, `print_trainable_parameters(base_model)` → 0 trainable.
- [ ] `!gdown 1b5hFsjpCqI3ZXvraIF0w7eW-mRO7Ecao` — nb cell 51; downloads `train_16k.jsonl` (23.2 MB).
- [ ] Step 3, nb cells 53-64: sample 1000 rows, `extract_qa`, HF `Dataset`, chat template, 900/100 split, verify one example, token-length histogram.
- [ ] Step 4, nb cells 66-72: Polls 2-3, `LoraConfig` (nb cell 67), `SFTConfig` (nb cell 70), `SFTTrainer` + fp32 cast (nb cell 72) → `trainable params: 1146880`.
- [ ] Nb cell 75: `trainer.train()` — 450 steps; Poll 4 is nb cell 74.
- [ ] `%load_ext tensorboard` — nb cell 77.
- [ ] `%tensorboard --logdir results/runs` — nb cell 77.
- [ ] Step 5, nb cells 80, 82: loss/perplexity with the adapter off and on; side-by-side generations.
- [ ] Step 6, nb cells 84, 86, 88: save adapters, merge into FP16 and save, optional private Hugging Face upload (needs a `write` token).
- [ ] Nb cells 89-90: the QLoRA flow diagram (fetched from `mermaid.ink`) and further reading.

*Clean up Track B*
- [ ] Runtime → Disconnect and delete runtime.
- [ ] Delete `MyDrive/LLM_cache` in Drive if you need the space.

---

## 1. What you build

This lecture has two tracks. Both teach a model to answer "Pavlos style", e.g. "Yello - this is Pavlos your cheese monker…" (the README's sample output and the Colab dataset). The *current* generator prompt's list of openers no longer includes "Yello…"; it asks for openers like "Good question", "Glad you ask" and "I have slides for that" (`dataset-creator/cli.py:84-89`). The sample JSON at the end of the same prompt still opens its three example answers with the old phrases "Welcome welcome welcome, cheese lovers!…", "Yello - this is Pavlos your cheese monker…" and "Welcome welcome to AC215…" (`dataset-creator/cli.py:133`, `:137`, `:140`), so generated data may still use them.

- **Track A (the repo, managed fine-tuning)** runs two Docker containers on your laptop.
  - In `dataset-creator`, `cli.py --generate` asks Gemini (`gemini-3.1-flash-lite`, `location="global"`) five times for 20 cheese Q&A pairs in Pavlos' voice. A JSON schema forces the format.
  - `--prepare` deduplicates the pairs and splits them 90/10. It writes CSVs plus Gemini-format `train.jsonl`/`test.jsonl`.
  - `--upload` copies everything to `gs://<your bucket>/llm-finetune-dataset-small/`.
  - In `gemini-finetuner`, `cli.py --train` submits a **supervised tuning job** to Vertex AI (now branded "Agent Platform") in `us-central1`. Google trains a small adapter on top of `gemini-3.1-flash-lite` on its own hardware. The result is a **tuned-model endpoint** in *your* project (`projects/<num>/locations/us/endpoints/<id>`).
  - `cli.py --chat` sends a question to that endpoint through the multi-region `us` service address.

  You never see the weights; you get an endpoint.
- **Track B (Colab, open-source PEFT)** runs on a Colab GPU. It:
  - loads `Qwen/Qwen3-0.6B` in **4-bit NF4** with bitsandbytes
  - attaches **LoRA** adapters (r=8 on `q_proj`/`v_proj`, which makes 1,146,880 trainable numbers, 0.30% of the stored parameters)
  - trains for 2 epochs (450 steps, about 3.5 minutes on an A100) on 900 Pavlos Q&As sampled from a 16k-example file in the same Gemini JSONL format Track A produces
  - compares loss and perplexity with the adapter switched off and on (stored: 2.65 → 1.39 loss, 14.15 → 4.00 perplexity)
  - saves a 4.6 MB adapter and a 1.2 GB merged FP16 model to Google Drive, optionally pushing it to a private Hugging Face repo

  Here you own the weights.

The tuned Gemini endpoint from Track A is used again in L10 (`cheese-app-v0`, `/finetunechat`).

```
 TRACK A — managed tuning (repo dlops-io/llm-finetuning @ 44ef6f0)

 YOUR LAPTOP (Docker Desktop / Engine)                              GOOGLE CLOUD (project = $GCP_PROJECT)
 <parent>/                                                          +--------------------------------------------+
 ├── secrets/llm-service-account.json ----bind mount----+           | IAM: llm-service-account                   |
 │                                  (read-write; no :ro)  |           |   Storage Admin + roles/aiplatform.user    |
 └── llm-finetuning/                                    |           +--------------------------------------------+
     ├── env.dev  (sourced by docker-shell.sh: GCP_PROJECT, GCS_BUCKET_NAME, GOOGLE_APPLICATION_CREDENTIALS ...)
     │                                                  v
     ├── dataset-creator/ ==bind mount==> /app   +-------------------------------------------+
     │    data/  (created at runtime, gitignored)| container "llm-dataset-creator"           |
     │                                           | python:3.12-slim-bookworm, user app (1000)|
     │                                           | venv /.venv (uv sync --frozen), /secrets  |
     │                                           |                                           |
     │   python cli.py --generate  --------------+--HTTPS--> aiplatform.googleapis.com        |
     │      5 x generate_content(JSON schema)    |           .../locations/global/publishers/google/models/
     │      -> data/cheese_qa_{0..4}.txt  <------+---------  gemini-3.1-flash-lite:generateContent
     │   python cli.py --prepare (local only)    |
     │      -> instruct-dataset.csv train.csv test.csv train.jsonl test.jsonl
     │   python cli.py --upload  ----------------+--HTTPS--> Cloud Storage  gs://$GCS_BUCKET_NAME/
     │                                           +-------------------------------------------+   llm-finetune-dataset-small/*.jsonl,*.csv
     │                                                                                                  |
     └── gemini-finetuner/ ==bind mount==> /app  +-------------------------------------------+          | read by Google's
                                                 | container "gemini-finetuner" (same image   |          | tuning service
                                                 | recipe, same uv.lock)                      |          v
         python cli.py --train  -----------------+--HTTPS--> us-central1-aiplatform.googleapis.com  POST .../tuningJobs
             (returns after ~60 s; job keeps     |           TuningJob: base gemini-3.1-flash-lite, 1 epoch,
              running in Google's cloud)         |           ADAPTER_SIZE_FOUR -> tuned model + endpoint
                                                 |                                  projects/<num>/locations/us/endpoints/<id>
         python cli.py --chat   -----------------+--HTTPS--> aiplatform.us.rep.googleapis.com
             (MODEL_ENDPOINT hard-coded!)        |           .../locations/us/endpoints/<id>:generateContent
                                                 +-------------------------------------------+
     No ports are published; nothing listens. Containers are interactive shells (--rm -ti).

 TRACK B — QLoRA in Colab (notebook 1oX3ADMHphW2v7mwV7zkEWD5oYewJZEAC)

 Browser --> Colab VM (GPU: T4 / L4 / A100; Python 3.13, torch 2.11)
   Colab Secrets: HF_TOKEN --login--> huggingface.co
   hf download --> /content/drive/MyDrive/LLM_cache  (Google Drive mount; models persist across sessions)
   gdown 1b5hFsj... --> /content/train_16k.jsonl --sample 1000--> chat template --> 900 train / 100 test
   Qwen3-0.6B --BitsAndBytesConfig(nf4, double quant, fp16 compute)--> 4-bit base (frozen)
        + LoraConfig(r=8, alpha=16) on q_proj,v_proj  --SFTTrainer 2 epochs, bs 4, 450 steps-->
   adapters  LLM_cache/Qwen0.6B-finetune_cheese/          (~4.6 MB)
   merged    LLM_cache/Qwen0.6B-finetune_cheese_merged/   (~1.2 GB fp16) --optional--> HF Hub private repo
```

---

## 2. Prerequisites and costs

**Accounts**
- **Track A:**
  - A GCP project with **billing enabled** (the course project, e.g. `ac215-project`, per `env.dev:6`).
  - Permission to create service accounts, keys and buckets.
- **Track B:**
  - A Google account for Colab and Drive.
  - A free **Hugging Face** account and access token (nb cell 9). "Read" is enough for Steps 1-6.2; "write" is needed for the optional upload in Step 6.3. Both models are public, so the token is strictly needed only for the upload. It also avoids anonymous rate limits.

**Local installs (Track A)**
- **Docker** (`README.md:33`).
- **A shell that understands `source`.** The README says `sh docker-shell.sh` (`README.md:87`, `:240`), but the script's `source ../env.dev` (`dataset-creator/docker-shell.sh:8`, `gemini-finetuner/docker-shell.sh:7`) fails under `dash`, which is `/bin/sh` on Ubuntu/Debian/WSL. Use `bash docker-shell.sh` there (§6.1). On macOS, `/bin/sh` is bash and the README command works.
- `git` to clone `https://github.com/dlops-io/llm-finetuning` (`README.md:34`).
- Optional: the `gcloud` CLI, for the bucket and API commands below.

**GCP APIs to enable (Track A).** The README doesn't list these.
- **Vertex AI API** `aiplatform.googleapis.com`, used for generation, tuning and chat.
- **Cloud Storage** `storage.googleapis.com`, which is usually on by default.
- CLI: `gcloud services enable aiplatform.googleapis.com storage.googleapis.com`.

**Service account and key (Track A)**, per `README.md:38-69`.
- Name: `llm-service-account` (`README.md:41`). It's the same SA as L05 `llm-rag` and L10 `cheese-app-v0`, so reuse it if you have it.
- Roles: **Storage Admin** and **Agent Platform User**. The latter was formerly "Vertex AI User"; its role ID is `roles/aiplatform.user` (`README.md:43-46`).
- Key: a JSON key renamed to exactly `llm-service-account.json`, placed in `<parent>/secrets/` **next to** the repo, not inside it (`README.md:50-62`).

**Where the code expects things**

| Thing | Where | Set by |
|---|---|---|
| Key on your laptop | `<parent>/secrets/llm-service-account.json` | you (`README.md:50`) |
| Key inside the container | `/secrets/llm-service-account.json` | `SECRETS_DIR=$(pwd)/../../secrets/` (`env.dev:5`), mounted by `-v "$SECRETS_DIR":/secrets` (`dataset-creator/docker-shell.sh:18`, `gemini-finetuner/docker-shell.sh:17`) |
| `GOOGLE_APPLICATION_CREDENTIALS` | `"/secrets/llm-service-account.json"` | `env.dev:8`, passed with `-e` (`docker-shell.sh:19` / `:18`); read lazily by google-auth on the first API call |
| `GCP_PROJECT` | `"ac215-project"`, **change it** | `env.dev:6`; required, `os.environ["GCP_PROJECT"]` at `dataset-creator/cli.py:17` and `gemini-finetuner/cli.py:9` |
| `GCS_BUCKET_NAME` | `"cheese-dataset"`, **change it** (bucket names are global and this one belongs to the course) | `env.dev:7`; required by `dataset-creator/cli.py:21`. Passed to gemini-finetuner but **not read there** |
| Training data URIs (Gemini) | `gs://cheese-dataset/llm-finetune-dataset-small/{train,test}.jsonl`, **hard-coded; edit them** | `gemini-finetuner/cli.py:10-11` |
| Tuned endpoint for `--chat` | `projects/129349313346/locations/us/endpoints/7655908260297310208`, the **instructor's endpoint; replace with yours** | `gemini-finetuner/cli.py:107` |
| `GCP_SERVICE_ACCOUNT`, `LOCATION` | defined but unused by these two containers | `env.dev:9-10` (only `autotrain-runner/docker-shell.sh:20` passes `GCP_SERVICE_ACCOUNT`) |
| Code inside the container | `/app` is a **bind mount** of the folder you ran the script from, so host edits are live without a rebuild | `-v "$BASE_DIR":/app` (`docker-shell.sh:17` / `:16`), `BASE_DIR=$(pwd)` (`env.dev:4`) |
| Python venv | `/.venv`, outside `/app` so the bind mount doesn't hide it | `ENV UV_PROJECT_ENVIRONMENT=/.venv` (`Dockerfile:18`) |
| Generated data | `dataset-creator/data/` on the host (`/app/data` in the container); gitignored | `OUTPUT_FOLDER = "data"` (`dataset-creator/cli.py:20`), `.gitignore:8` |
| Colab cache | `/content/drive/MyDrive/LLM_cache` | nb cell 14:3 |
| Colab secret | `HF_TOKEN` in Colab Secrets, with "Notebook access" on | nb cell 9, read at nb cell 10:5 |

**A bucket.** The README never says to create one, but `--upload` needs it to exist: `upload()` calls `storage_client.bucket(GCS_BUCKET_NAME)` (`dataset-creator/cli.py:280`) and never creates it. Suggested command (not in the README):
```bash
gcloud storage buckets create gs://<your-unique-bucket> --location=us-central1
```
Then put that name in `env.dev:7` **and** in `gemini-finetuner/cli.py:10-11`.

**Billable resources (Track A)**
- **Dataset generation:** 5 calls to `gemini-3.1-flash-lite` (`dataset-creator/cli.py:170`, `:184-192`), each returning up to 8,192 tokens (`:176`). That costs cents.
  - `README.md:151` says "approximately $2.0 for 1000 iterations". That estimate predates the current model (§9).
- **Cloud Storage:** a few hundred KB, so negligible.
- **Tuning job:** billed per training token × epochs.
  - The README prices it at "Gemini 1.5 Flash Tuning is 0.008 USD per 1,000 tokens" (`README.md:269`), but the code tunes `gemini-3.1-flash-lite` (`gemini-finetuner/cli.py:15`) for **1 epoch** (`:53`), not the 3 epochs in the README table (`README.md:271-274`).
  - At the README's (stale) price, a ~24k-token dataset × 1 epoch ≈ $0.19.
  - Check the current price on the pricing page linked at `README.md:278`.
- **Tuned endpoint:** Google's managed tuned-Gemini endpoints are understood to be billed per request/token like the base model, with no per-hour node charge. This could not be verified for gemini-3.1-flash-lite (§9). Unlike L15's custom model endpoints, nothing here is a VM you have to stop.
- **Clean-up:**
  - `gcloud storage rm -r gs://<bucket>/llm-finetune-dataset-small`, or delete the bucket.
  - Delete the tuned model/endpoint in the console (Agent Platform / Vertex AI → Tuning, Model Registry, Endpoints) once you're done with it. Keep it until after L10 if you want to use it in `cheese-app-v0`.
  - Delete old SA keys you no longer use.
  - Locally: `docker image rm llm-dataset-creator gemini-finetuner`.

**Costs (Track B)**
- **GPU:** free Colab gives a T4 when available. A100/L4 need Colab Pro or compute units. The notebook times training at "~3.5 min on A100, ~4.5 min on L4, ~6-7 min on T4" (nb cell 75:2).
- **Drive space:** a few GB, made up of the OPT-350m and Qwen3-0.6B downloads, the merged model (~1.2 GB, nb cell 83) and the adapters (~4.6 MB). The `--exclude` flags in nb cell 16:1 save 1.3 GB (nb cell 15).
- **Hugging Face private repo:** free.
- **Clean-up:** disconnect and delete the runtime (Runtime → Disconnect and delete runtime). Delete `MyDrive/LLM_cache` if you need the space.

---

## 3. Concepts this tutorial teaches

### 3.1 Prompting vs RAG vs fine-tuning: style is learnable, facts are not guaranteed
- **Explanation.** There are three ways to change what an LLM says:
  1. **Prompting** changes the *input* each time: a system prompt asking for "Pavlos style".
  2. **RAG** (L05) adds retrieved text to the input. It gives the model facts it can quote, and no weights change.
  3. **Fine-tuning** changes the *weights*. You show the model many (input, desired output) pairs and nudge its parameters so those outputs become more likely.

  Fine-tuning is best at **behaviour**: tone, persona, format, length, domain vocabulary. It's unreliable for injecting **new facts**.
- **Evidence from the stored run** (nb cell 82 output, prompt "Why is the sky blue?", greedy decoding):
  - Base model: "**Light Refraction**: When sunlight enters the atmosphere, it bends (refracts)…"
  - Fine-tuned model: "Yello - this is Pavlos your cheese monker, ready to unravel the mystery of the sky's blue! … The blue color of the sky is due to the scattering of light by the water molecules in the atmosphere."
  - The persona transferred to a non-cheese question. The physics didn't improve; both (truncated) answers contain a physics error: the base model leads with refraction, the fine-tuned one blames water molecules (the real answer is Rayleigh scattering by N₂/O₂ molecules). The two columns are also different models: an FP16 base vs the 4-bit fine-tuned one (§3.8).
- **Mental model.** Fine-tuning moves the model's *default voice*. RAG changes the *open book on the desk*.
- **Analogy.** Accent coaching vs handing someone notes. After coaching, they sound like Pavlos on any topic, but they don't know more.
- **Common misconception.** "Fine-tune on my documents and the model will know them." It learns how the documents *sound* much faster than what they *say*. And the deployed L10 app combines both: its "Pavlos Cheese Model" page is "the same RAG flow as Chat, answered by a fine-tuned model" (`cheese-app-v0/README.md:245`), and the API sends the prompt plus the RAG system instruction to the tuned endpoint (`cheese-app-v0/api-service/api/routers/rag.py:110-120`).

### 3.2 Synthetic instruction data: an LLM teacher writes the curriculum
- **Explanation.** `dataset-creator/cli.py` uses a strong model to *manufacture* training data. It has three parts:
  1. A long **system instruction** defines the persona and content rules: 11 numbered sections, with signature phrases like "Remember rule number 672…" (`cli.py:36-144`).
  2. A short **input prompt** asks for 20 pairs (`cli.py:169`).
  3. A **response schema** (`cli.py:146-160`) plus `response_mime_type="application/json"` (`cli.py:179`) make Gemini return a JSON array of `{question, answer}` objects. Structured output does the format enforcement that the prompt's "use single quotes, escape apostrophes" rules (`cli.py:118-125`) used to attempt.

  `temperature=0.9` (`cli.py:174`) keeps the 5 batches diverse. Duplicate questions are dropped later (`cli.py:233`).
- **Mental model.** Distillation of a *persona*: teacher (big model + prompt) → examples → student (tuned model, no prompt needed).
- **Analogy.** A screenwriter writes 100 practice scenes so an understudy can learn the lead's mannerisms.
- **Common misconception.** "Synthetic data is free of errors." The teacher's hallucinations become training targets, and the system prompt even asks for "specific data such as optimal pH levels" (`cli.py:45`). The student inherits whatever the teacher got wrong.

### 3.3 From Q&A pairs to JSONL to tokens: what the model is actually trained on
- **Explanation.** The same pair takes four shapes on its way into training:
  1. **Row:** `question, answer` (`instruct-dataset.csv`, `cli.py:237-238`).
  2. **Plain text:** `"human: …\nbot: …"` in `train.csv`/`test.csv` (`cli.py:241-247`, `:263-264`). Track A doesn't use it; it suits the old HF/AutoTrain path (`autotrain-runner/configs/llm_config_mistral.yaml:12-13` reads a `text` column).
  3. **Gemini JSONL:** one line per example, `{"contents":[{"role":"user","parts":[{"text":…}]},{"role":"model","parts":[{"text":…}]}]}` (`cli.py:249-257`, `:270-273`). Gemini's tuning service reads this.
  4. **Chat-template text** (Track B): `tokenizer.apply_chat_template` turns the turns into Qwen3's special-token layout. Stored example (nb cell 63): `<|im_start|>user\nCan you explain the process of 'affioratura' …<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\nWelcome welcome, cheese lovers! …<|im_end|>`. The empty `<think></think>` block is Qwen3's "answer without thinking" layout (nb cell 58).
- **Why the template matters.** At inference, `generate_response` builds the prompt with the same template plus `add_generation_prompt=True` **and `enable_thinking=False`** (nb cell 82:19, :22-27). With thinking disabled, Qwen3's template ends the prompt with `<|im_start|>assistant\n<think>\n\n</think>\n\n`, exactly the prefix every training answer had, so the model continues straight into the answer. The model has learned "after `<|im_start|>assistant` comes a Pavlos answer, then `<|im_end|>`". A mismatched template at training vs inference is a classic silent failure.
- **The EOS detail.** `.removesuffix("\n")` (nb cell 59:13) makes every example end in `<|im_end|>`, Qwen3's EOS token (`eos_token_id` 151645, nb cell 42 output). TRL's "Adding EOS" pass appends EOS only when the text doesn't already end with it (`trl/trainer/sft_trainer.py:1524-1526` in trl 1.14.0), so the model learns to stop exactly once.
- **Mental model.** A conveyor belt. The same Q&A pair gets repackaged at each station, and only the last package (token IDs) reaches the GPU.
- **Common misconception.** "The model sees the question and answer as two fields." It sees one token stream. With a plain `text` dataset, TRL computes loss on **every** token, question included; `completion_only_loss` applies only to prompt/completion datasets (`trl/trainer/sft_config.py:96`). The notebook says the same about its evaluation (nb cell 79).

### 3.4 Managed tuning: you submit a job, Google trains, you get an endpoint
- **Explanation.** `train_client.tunings.tune(...)` (`gemini-finetuner/cli.py:61-65`) sends one HTTPS request.
  - It's a `POST` to `https://us-central1-aiplatform.googleapis.com/v1beta1/projects/<P>/locations/us-central1/tuningJobs`. The google-genai client prefixes `projects/{project}/locations/{location}/` onto relative paths (`google/genai/_api_client.py:1008-1014`) and picks the `{location}-aiplatform` host (`:654-656`).
  - It returns a **TuningJob** whose `state` moves through `JOB_STATE_PENDING`/`RUNNING` to `SUCCEEDED`/`FAILED`/`CANCELLED`, among others (`types.py:381-403`).
  - Training happens on Google's hardware while your container sits idle, or is even gone.
  - The job reads `gs://…/train.jsonl` itself, not through your container or your key: the tuning workload runs as the job's `service_account`, and "If not specified, the Vertex AI Secure Fine-Tuned Service Agent in the project will be used" (`types.py:10224-10227`, the `TuningJob.service_account` field). So the bucket must be readable by your project's Google-managed agent. A bucket in someone else's project (the default `cheese-dataset`) normally isn't. Whether the course bucket is publicly readable was not checked; if it were, the job would quietly train on the instructor's data instead of yours.
  - Hyperparameters (`cli.py:52-58`): `epoch_count=1`, `learning_rate_multiplier=1.0` (a multiplier on Google's default LR, not an LR), and `adapter_size="ADAPTER_SIZE_FOUR"`. Allowed values are `ADAPTER_SIZE_ONE` … `ADAPTER_SIZE_THIRTY_TWO` (`types.py:418-433`). This is presumably the rank of a LoRA-style adapter: the managed analogue of Track B's `r=8`.
  - The tuned model is served from an **endpoint** in your project.
- **Three locations, three hosts** (`cli.py:12-15`, `:19-33` and `dataset-creator/cli.py:18`):
  - generation: `global` → `aiplatform.googleapis.com` (`_api_client.py:648-649`)
  - tuning: `us-central1` → `us-central1-aiplatform.googleapis.com`
  - serving the tuned model: multi-region `us` → explicitly `https://aiplatform.us.rep.googleapis.com` through `HttpOptions(base_url=...)`. Without the override, google-genai 1.39.1 would build `https://us-aiplatform.googleapis.com/` (`_api_client.py:654-656`).
- **Mental model.** A dry cleaner. You drop off (submit), get a ticket (job name), go home, and come back for the garment (endpoint). The CLI's 60-second wait (`cli.py:71`) is just a look over the counter.
- **Common misconceptions.**
  - "`--train` finished, so my model is ready." `main()` calls `train(wait_for_job=False)` (`cli.py:126`), so the polling loop (`:84-87`) never runs. The print at `:89` almost always shows `Tuned model info: None`.
  - "I can download the tuned Gemini." You can't; you only get an endpoint.

### 3.5 Quantization: 16 buckets per weight (NF4, double quantization, compute dtype)
- **Explanation.** Loading with `BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=...)` (nb cell 18:7-12, nb cell 34:1-6) replaces each `nn.Linear` with `Linear4bit` (nb cell 21 output for OPT-350m: `(q_proj): Linear4bit(in_features=1024, out_features=1024, bias=True)`; its `lm_head` stays `Linear`). It has three parts:
  - **The storage format.** Each weight is replaced by a 4-bit index into **16 levels**, scaled per small block of weights by an "absmax" constant.
  - **NF4 ("NormalFloat4").** Its 16 levels are spaced so that each is equally likely for normally distributed weights: denser near 0, sparser in the tails (QLoRA paper). The bitsandbytes default is FP4 (nb cell 28).
  - **Double quantization** quantizes the per-block constants themselves. Per the QLoRA paper, that saves about 0.37 bits per parameter: roughly 20 MB on Qwen3-0.6B's 440 M quantized weights.
  - **Compute dtype** is what the weights are *dequantized to* for each matmul: `float16` here, so it also works on T4s, which lack fast bf16 (nb cell 30-31).
- **What gets quantized.** The stored run shows it isn't everything:
  - Qwen3-0.6B has 596 M parameters. The 440.4 M linear weights are packed two per byte, so `numel()` reports 220.2 M.
  - The 155.6 M embedding weights and the small norms stay unquantized.
  - Hence "Number of parameters: 375.84896 millions." (nb cell 38 output, explained in nb cell 39).
  - The arithmetic checks out against the stored config (nb cell 42). Per layer, the linear weights are 15,728,640 (in×out: q 1024×2048, k/v 1024×1024, o 2048×1024, gate/up 1024×3072, down 3072×1024); × 28 layers = 440,401,920. The embedding is 151,936×1024 = 155,582,464. Norms are 65,536. Total: 220,200,960 + 155,582,464 + 65,536 = 375,848,960 ✓.
- **Mental model.** Rounding every weight to the nearest of 16 crayons, with a separate "brightness knob" for every block of 64 weights.
- **Analogy.** Saving a photo as a 16-colour GIF with a smart palette: most of the picture survives at ⅛ of the size of 32-bit floats (¼ of fp16).
- **Common misconception.** "A 4-bit model does 4-bit arithmetic." Storage is 4-bit; the math runs in the compute dtype after on-the-fly dequantization. Another: "4-bit makes it faster" (Poll 1, nb cell 20). The main win is **memory**; dequantization can make it slower.

### 3.6 LoRA: learn a thin correction instead of the whole matrix
- **Explanation.** For a frozen weight `W` (d_out × d_in), LoRA learns `ΔW = (α/r)·B·A`, where `A` is r × d_in and `B` is d_out × r.
  - `B` starts at zero, so the model is unchanged at step 0.
  - Here r=8 and α=16, so the scale is 2 (nb cell 67:2-7).
  - `LoraConfig` doesn't list `target_modules`, so PEFT uses its default for Qwen3: `["q_proj", "v_proj"]` (`peft/utils/constants.py:102`, peft 0.20.0).
- **Counting the trainable numbers** (the stored output checks this exactly):
  - q_proj: 8×(1024+2048) = 24,576
  - v_proj: 8×(1024+1024) = 16,384
  - per layer: 40,960; × 28 layers = **1,146,880**
  - matches "trainable params: 1146880 || all params: 376995840 || trainable%: 0.3042155584528466" (nb cell 72 output). The all-params count is 375,848,960 + 1,146,880.
  - In fp32 that's 4.6 MB (nb cell 83).
- **Mental model.** The fine-tune lives on a low-dimensional "steering wheel" bolted onto each attention projection. The engine (base weights) is untouched.
- **Analogy.** A transparent overlay on a printed map. You draw a few routes on the overlay; peel it off and the map is pristine. *Merging* (nb cell 86) is photocopying the map with the overlay on.
- **Common misconception.** "LoRA trains a separate small model." The adapters sit *inside* existing layers and are added to their outputs. Another: "higher r is always better" (Poll 3, nb cell 68). More rank means more capacity and more memory and time; for style transfer, r=8 on two projections is plenty.

### 3.7 QLoRA training mechanics: frozen 4-bit base + higher-precision adapters
- **Explanation.** QLoRA = §3.5 + §3.6:
  1. `prepare_model_for_kbit_training` (nb cell 36:18) freezes all parameters, casts non-4-bit fp16/bf16 parameters to fp32, and enables gradient checkpointing (`peft/utils/other.py:186-202`, `use_gradient_checkpointing=True` at `:152`). That's why trainable = 0 before LoRA (nb cell 48 output).
  2. `SFTTrainer(..., peft_config=peft_config)` (nb cell 72:2-8) injects LoRA, then prepares the data. The stored progress bars show the stages in order (nb cell 72 output): "Adding EOS", "Tokenizing", "Building labels" (with no completion/assistant mask, labels are a copy of `input_ids`, so every token is a target; `trl/trainer/sft_trainer.py:1627-1647`), "Truncating" (to `max_length=512`, nb cell 70:3) and "Dropping fully masked examples".
  3. **The dtype dance.** For quantized models TRL casts LoRA weights to **bf16** (`trl/trainer/sft_trainer.py:1160-1167`). The notebook trains with `fp16=True` (nb cell 70:12) so T4s work, and fp16 AMP can't unscale bf16 gradients. So the notebook casts the adapters back to fp32 (nb cell 72:10-14).
  4. `optim="paged_adamw_32bit"` (nb cell 70:7) is the QLoRA paper's paged optimizer, which can spill optimizer state to CPU memory under pressure.
  5. Steps: 900 examples / batch 4 = 225 steps per epoch, × 2 epochs = **450 steps**, matching `global_step=450` (nb cell 75 output).
- **Mental model.** The heavy base is a frozen, compressed reference. Only the light adapters receive gradients and live in full precision.
- **Common misconception.** "QLoRA trains the 4-bit weights." Gradients flow *through* the dequantized base weights into the adapters; the base never changes.

### 3.8 Did it work? Loss, perplexity and the adapter switch
- **Explanation.** Perplexity is `exp(mean token loss)`: the effective number of equally likely next tokens the model is choosing among.
  - The notebook scores the same 100 test examples twice (nb cell 80:51-55): with LoRA on, and inside `with trainer.model.disable_adapter():`.
  - Stored results (nb cell 80 output):

    ```
                                  Loss  Perplexity
    Base (4-bit)                2.6498       14.15
    Fine-tuned (4-bit + LoRA)   1.3872        4.00
    ```
  - Training loss fell from 2.007381 at step 50 to 1.350437 at step 450 (nb cell 75 HTML table).
  - Qualitatively (nb cell 82), every fine-tuned answer opens with a Pavlos phrase: the two cheese answers with "Welcome welcome welcome, cheese lovers! This is your lecturer Pavlos Protopapas here…", the sky answer with "Yello - this is Pavlos your cheese monker…".
- **Track A.** The console shows the same kind of curves for Gemini: "Total loss" and "Fraction of correct next step preds" for training and validation (`README.md:310-316`, `images/training-1.png`).
- **Mental model.** Perplexity measures how *surprised* the model is by Pavlos-style text. The drop from 14 to 4 says "now this style is what it expects", not "now it's more correct".
- **Common misconceptions.**
  - "Lower perplexity = better answers." Here the loss counts every token, including the question and chat-template tokens (nb cell 79). It mostly measures style fit: compare the sky-blue answer in §3.1.
  - In 5.2 the "Base Model" column is an **FP16, unquantized** Qwen (nb cell 82:55-61, `quantization_config` commented out), while 5.1's base is the 4-bit model with its adapter off. These are two different baselines.

---

## 4. Step-by-step walkthrough

Commands in code spans are verbatim from the README, code or notebook unless marked *(extra)*. Track A runs on your laptop; Track B runs in Colab, and you can do it first if you have no GCP access yet.

### Part 0: before you start (Track A)

**Step 0. Clone, folder layout, key** (`README.md:31-69`).
- **Action:** in some parent folder:
  1. `git clone https://github.com/dlops-io/llm-finetuning.git` *(extra; the README only links the repo, `README.md:34`)*.
  2. In the GCP Console (IAM & Admin → Service accounts), create `llm-service-account`, grant **Storage Admin** and **Agent Platform User** (`roles/aiplatform.user`), then on its **KEYS** tab use **ADD Key → Create New Key → JSON** to download a key (`README.md:40-49`). Skip this if you already have this SA from L05.
  3. Create `secrets/` **next to** the repo and put the key there as `llm-service-account.json` (`README.md:50`). The layout must match `README.md:54-62`.
- **Under the hood:** `env.dev:5` computes `SECRETS_DIR=$(pwd)/../../secrets/`. `$(pwd)` is evaluated when the script sources it, while you're inside `dataset-creator/` or `gemini-finetuner/`, so `../../secrets` is `<parent>/secrets`. That's the same folder L05's `docker-compose.yml` mounts as `../secrets` from the repo root.
- **Checkpoint:** *(extra)* `ls <parent>/secrets` shows `llm-service-account.json`, not `…json.json` (`README.md:67`). *(extra)* `git -C llm-finetuning log -1 --oneline` shows `44ef6f0 remove pipfile from gemini-finetuning`, or newer.
- **If it fails:** a key inside the repo would be ignored by `.gitignore:7` (`*.json`), but it would **not be mounted**. Move it.

**Step 1. Edit `env.dev`** *(implied by the "CHANGE TO YOUR …" comments)*.
- **Action:** set `GCP_PROJECT` (`env.dev:6`), `GCS_BUCKET_NAME` (`:7`) and the project part of `GCP_SERVICE_ACCOUNT` (`:9`).
- **Under the hood:** `docker-shell.sh` exports these and passes three of them into the container with `-e` (`dataset-creator/docker-shell.sh:19-21`).

**Step 2. Enable the API and create the bucket** *(extra; not in the README)*.
- **Action:** `gcloud services enable aiplatform.googleapis.com storage.googleapis.com`, then `gcloud storage buckets create gs://<bucket> --location=us-central1`.
- **Checkpoint:** `gcloud storage ls` lists your bucket.

**Step 3. Point the Gemini trainer at your bucket** *(extra; required)*.
- **Action:** edit `gemini-finetuner/cli.py:10-11`, replacing `gs://cheese-dataset/...` with `gs://<bucket>/llm-finetune-dataset-small/train.jsonl` and `.../test.jsonl`. The lines say "# Replace with your dataset".
- **Why now:** `/app` is a bind mount, so editing on the host is enough. There's no rebuild.

### Part A: Generate Question Answer Dataset (`README.md:75-222`)

**Step 4. Build and enter the dataset container** (`README.md:83-88`): `cd dataset-creator` *(extra; the README says "Make sure you are inside the `dataset-creator` folder")*, then `sh docker-shell.sh`.
- **Under the hood:**
  1. `set -e` (`docker-shell.sh:4`) aborts on the first error.
  2. `source ../env.dev` (`:8`) loads the variables.
  3. `docker build -t $IMAGE_NAME -f Dockerfile .` (`:13`) builds `llm-dataset-creator`. The Dockerfile:
     - starts from `python:3.12-slim-bookworm` (`Dockerfile:2`)
     - apt-installs `build-essential curl libpq5` (`:4`, `:22-28`), then `pip install uv` (`:30`)
     - creates user `app` (uid 1000, `:31`)
     - copies `pyproject.toml uv.lock*` (`:42`) and runs `uv sync --frozen` (`:45`). That installs exactly the versions `uv.lock` pins into `/.venv` (`:18`). The lock has 136 `[[package]]` entries, but on Linux the Windows-only `pywin32` and `pyreadline3` (both behind `sys_platform == 'win32'` markers, `uv.lock:801`, `:1089`) are skipped and the virtual project `app` itself (`source = { virtual = "." }`, `uv.lock:106-108`) is not installed as a package.
     - copies the source (`:48`)
  4. `docker run --rm --name … -ti` (`:16-22`) mounts the folder and the secrets and starts `docker-entrypoint.sh`.
- **Checkpoint:** the entrypoint prints (`docker-entrypoint.sh:3-12`):
  ```
  Container is running!!!
  Architecture: x86_64            (aarch64 on Apple Silicon)
  Environment ready! Virtual environment activated.
  Python version: Python 3.12.x
  UV version: uv <version>        (whatever `pip install uv` fetched at build time; not pinned)
  Activating virtual environment...
  ```
  Then you get an interactive bash in `/app`, like `app@<container-id>:/app$`. The venv's `(app)` prefix (from `name = "app"`, `pyproject.toml:2`) may not show, because the new bash started by `exec /bin/bash` (`:15`) re-reads Debian's bashrc, which resets `PS1`; the same happens in L02. The venv is still active through the exported `PATH`. *(extra)* Check with `which python` → `/.venv/bin/python`. The "activated" line prints *before* activation happens (`:6` vs `:12`), which is cosmetic. `ls -la /secrets` should list the key (`README.md:69`).
- **If it fails:**
  - `docker-shell.sh: 8: source: not found`: you're on dash. Run `bash docker-shell.sh` (§6.1).
  - `../env.dev: No such file or directory`: you ran it from the wrong folder (`README.md:68`).
  - `Conflict. The container name "/llm-dataset-creator" is already in use`: another shell has it open. Exit it, or `docker rm -f llm-dataset-creator`.
  - The first build takes several minutes. The lock pulls `chromadb`, `onnxruntime`, `langchain` and `openai-agents`, which this code never imports (§6.9).

**Step 5. Smoke test** (`README.md:90-94`): `python cli.py --help`
- **Expected** (argparse in Python 3.12, rendered from an identical parser):
  ```
  usage: cli.py [-h] [--generate] [--prepare] [--upload]

  CLI

  options:
    -h, --help  show this help message and exit
    --generate  Generate data
    --prepare   Prepare data
    --upload    Upload data to bucket
  ```
- **Under the hood:** importing `cli.py` already reads `GCP_PROJECT` and `GCS_BUCKET_NAME` (`cli.py:17`, `:21`) and builds the genai client (`:25`). The client loads credentials **lazily**, so `--help` succeeds even if the key is missing. It only proves the env vars exist.
- **If it fails:** `KeyError: 'GCP_PROJECT'` means the `-e` flags didn't pass, i.e. `env.dev` wasn't sourced.

**Step 6. Generate** (`README.md:100-104`): `python cli.py --generate`
- **Under the hood** (`cli.py:163-201`):
  - `os.makedirs(OUTPUT_FOLDER, exist_ok=True)` (`:167`), with `OUTPUT_FOLDER = "data"` (`:20`)
  - 5 iterations (`NUM_ITERATIONS = 5`, `:170`) of `generate_content`, each with the system instruction, the JSON schema, `temperature=0.9`, `top_p=0.95` and `max_output_tokens=8192` (`:173-181`)
  - safety filters set to `OFF` (`:28-33`)
  - each response's text saved raw to `data/cheese_qa_{i}.txt` (`:196-199`)
  - the request goes to `…/locations/global/publishers/google/models/gemini-3.1-flash-lite:generateContent` (the model name is expanded by `google/genai/_transformers.py:181-182`)
- **Checkpoint:**
  ```
  CLI Arguments: Namespace(generate=True, prepare=False, upload=False)
  generate()
  Generating batch: 0
  ...
  Generating batch: 4
  ```
  On the host, `ls dataset-creator/data` shows `cheese_qa_0.txt` … `cheese_qa_4.txt`, each a JSON array of ~20 objects.
- **If it fails:**
  - Errors are **caught and printed per batch** (`:200-201`), so the command "succeeds" anyway. Read the lines, e.g. `Error occurred while generating content: File /secrets/llm-service-account.json was not found.` (google-auth's message, `google/auth/_default.py:174` in the locked google-auth 2.41.1), or 403/`PERMISSION_DENIED`, which means a missing role or the API isn't enabled.
  - `PermissionError … 'data'` on a Linux host: the container user (uid 1000) can't write to your bind-mounted folder (§6.6).
- **README vs code:**
  - The README's "System Prompt" excerpt (`README.md:114-135`) shows the *old* openers ("Welcome welcome welcome, cheese lovers! …", "Let us do system3"). The code now lists "Good question", "Glad you ask", "I have slides for that" and "I knew you will ask this, I have slides coming", plus new phrases "Look at this horse" and "Best thing after sliced bread" (`cli.py:83-101`, changed in `6e4c3f7`). The prompt's own sample JSON was not updated: its example answers still open with "Welcome welcome welcome, cheese lovers!…", "Yello - this is Pavlos your cheese monker…" and "Welcome welcome to AC215…" (`cli.py:133`, `:137`, `:140`).
  - The README says "Change any of the default parameters" (`README.md:106`), but there are no CLI parameters: you edit `NUM_ITERATIONS` (`cli.py:170`) in the file.

**Step 7. Prepare** (`README.md:181-187`): `python cli.py --prepare`
- **Under the hood** (`cli.py:204-273`):
  1. Glob and sort `data/cheese_qa_*.txt`.
  2. Strip any `` ```json `` fences (`:219`), then `json.loads` each file; failures go into `errors` (`:221-226`).
  3. Build a DataFrame, drop duplicate questions and NaNs, and save `instruct-dataset.csv` (`:232-238`).
  4. Add a `text` column (`human:/bot:`) and a `contents` column (Gemini turns) (`:241-257`).
  5. `train_test_split(test_size=0.1, random_state=42)` (`:260-262`), then write `train.csv`/`test.csv` (text only) and `train.jsonl`/`test.jsonl` (contents only). The test set is capped at 256 rows, Gemini's validation limit (`:266-273`).
- **Checkpoint:** "Processing file: data/cheese_qa_0.txt" … then `Number of errors: 0`, `[]`, `Shape: (N, 2)` with N ≈ 100 (fewer after deduplication), and the DataFrame head. With 100 rows the split is 90/10.
  - *(extra)* `head -c 300 data/train.jsonl` shows `{"contents":[{"role":"user","parts":[{"text":"...`. pandas may write `/` as `\/`, which is valid JSON.
  - *(extra)* `wc -l data/*.jsonl`.
- **If it fails:**
  - `KeyError: 'question'` right after `Shape: (0, 0)` means every generation batch failed in Step 6, so the DataFrame has no columns (reproduced with pandas). Go back and read Step 6's error lines.
  - `Number of errors: 1` with "Unterminated string…" means a batch was cut off at the 8,192-token limit. The others still work.

**Step 8. Upload** (`README.md:218-222`): `python cli.py --upload`
- **Under the hood:** `storage.Client()` uses the SA key (`cli.py:279`). The project comes from the key file, not from `GCP_PROJECT`. The code uploads `*.jsonl` + `*.csv`, sorted (`:283-286`), to `llm-finetune-dataset-small/<file>` (`:291`) with a 300 s timeout (`:281`, `:294`).
- **Checkpoint:**
  ```
  upload()
  Uploading file: data/instruct-dataset.csv llm-finetune-dataset-small/instruct-dataset.csv
  Uploading file: data/test.csv llm-finetune-dataset-small/test.csv
  Uploading file: data/test.jsonl llm-finetune-dataset-small/test.jsonl
  Uploading file: data/train.csv llm-finetune-dataset-small/train.csv
  Uploading file: data/train.jsonl llm-finetune-dataset-small/train.jsonl
  ```
  *(extra)* `gcloud storage ls gs://<bucket>/llm-finetune-dataset-small/`.
- **If it fails:**
  - `404 … The specified bucket does not exist.`: create it (Step 2), or fix `env.dev:7`.
  - `403 … does not have storage.objects.create access`: the bucket belongs to someone else (e.g. the default `cheese-dataset`), or the SA lacks Storage Admin.
- **Tip:** flags combine. `python cli.py --generate --prepare --upload` runs all three in order (`cli.py:300-307`).

### Part B: Fine-tune Gemini (`README.md:228-316`)

**Step 9. Enter the second container** (`README.md:236-247`): `exit`, then `cd ../gemini-finetuner` *(both extra; the README says "Make sure you are inside the `gemini-finetuner` folder")*, `sh docker-shell.sh`, `python cli.py --help`.
- **Under the hood:** this is the same Dockerfile and the same `uv.lock`, byte-identical to dataset-creator's (`diff` shows no difference). Docker's layer cache reuses every layer up to and including `uv sync` (same base, same commands, same `pyproject.toml`/`uv.lock` content); only the final `COPY . ./` differs, so this build is fast. The image is `gemini-finetuner` (`docker-shell.sh:9`). The two `docker-shell.sh` files differ only in `IMAGE_NAME` and one blank line, which is why `source` is on line 7 here and line 8 in dataset-creator.
- **Checkpoint:** `usage: cli.py [-h] [--train] [--chat]` with `--train  Train model` and `--chat  Chat with model`.
- **If it fails:** the same as Step 4 (`gemini-finetuner/docker-shell.sh:7` is the `source` line).

**Step 10. Start tuning** (`README.md:253-257`): `python cli.py --train`
- **Under the hood** (`cli.py:44-99`):
  1. Build `TuningDataset(gcs_uri=TRAIN_DATASET)` and `TuningDataset(gcs_uri=VALIDATION_DATASET)` (`:48-49`).
  2. Create the config: 1 epoch, LR multiplier 1.0, adapter size four, display name `pavlos-cheese-demo-v3.1` (`:52-58`).
     - The validation field is typed `TuningValidationDataset` (`types.py:10541`). Passing a `TuningDataset` still works because google-genai's pydantic base model has `from_attributes=True` (`_common.py:434-445`); the coercion was confirmed with a toy pydantic 2 model.
  3. `train_client.tunings.tune(...)` (`:61-65`), print the job name, sleep 60 s, re-fetch (`:71-72`).
  4. `wait_for_job` is False (`:126`), so the code skips the polling loop and prints.
- **Checkpoint (expected shape):**
  ```
  CLI Arguments: Namespace(train=True, chat=False)
  train()
  Training job started. Monitoring progress...

  Job name: projects/<project-number>/locations/us-central1/tuningJobs/<id>

  Tuned model info: None
  Experiment: ...
  ```
  `Tuned model info` is `None` because the job is still running. Then watch the job in the console: Agent Platform → Tuning (`README.md:261`). Its detail page shows "Tuning progress", "Training metrics" and "Validation metrics" (Fraction of correct next step preds, Num predictions, Total loss) and a "Data distribution" tab (`images/training-1.png`, `images/training-2.png`). In the README's screenshot the mean output length is 267 tokens per example.
- **If it fails:**
  - `403`/`PERMISSION_DENIED` reading `gs://cheese-dataset/...`: you skipped Step 3. (The read is done by your project's tuning service agent, not your key, so granting your SA more roles won't fix it; §3.4.) If there's *no* error, still check the job's dataset URI in the console: a publicly readable course bucket (not verified) would mean you trained on the instructor's data.
  - `PERMISSION_DENIED` on `tuningJobs.create`: the SA lacks `roles/aiplatform.user`.
  - A 400 naming the base model: `gemini-3.1-flash-lite` isn't tunable in your region/project (§9). Check the console's list of tunable models.
  - Want the CLI to wait? Change `:126` to `train(wait_for_job=True)`. It then prints `Job in progress... State: JobState.JOB_STATE_RUNNING` every minute until a terminal state.

**Step 11. Get your endpoint** *(extra; the README skips this)*.
- **Action:** when the job shows **Succeeded**, copy the tuned model's endpoint (`projects/<num>/locations/us/endpoints/<id>`) from the console and paste it into `MODEL_ENDPOINT` at `gemini-finetuner/cli.py:107`.
- Lines `:93-96` print exactly this instruction, but only when `tuned_model` is already set, which the default flow doesn't reach.

**Step 12. Chat** (`README.md:284-286`): `python cli.py --chat`
- **Under the hood:** it calls `chat_client.models.generate_content(model=MODEL_ENDPOINT, contents=query, config=generation_config)` (`:113-117`).
  - The model path starts with `projects/`, so it's used as-is (`_transformers.py:173-177`). The URL is `https://aiplatform.us.rep.googleapis.com/v1beta1/<MODEL_ENDPOINT>:generateContent`.
  - The query is `"How is cheese made in Greece? Answer pavlos style?"` (`:109`).
  - Generation uses `max_output_tokens=3000`, `temperature=0.75` and `top_p=0.95` (`:37-41`).
- **Checkpoint:**
  ```
  CLI Arguments: Namespace(train=False, chat=True)
  chat()
  query:  How is cheese made in Greece? Answer pavlos style?
  Using serving location: us
  Fine-tuned LLM Response: <a Pavlos-style answer>
  ```
  The README's example (`README.md:295-301`) uses an older query, "How is cheese made?", and an answer opening "Yello - this is Pavlos your cheese monker…".
- **If it fails:** `403 PERMISSION_DENIED` or `404 NOT_FOUND` on `projects/129349313346/...` means you're still calling the instructor's endpoint. Do Step 11.

**Step 13. Try the hosted demo and look at the metrics** (`README.md:303-316`). The README links "[Pavlos Cheese Model](https://ac215-llm-rag.dlops.io/finetunechat)". It notes "it is assumed you have your vector database that is running locally", which refers to the RAG app of L05/L10, not this repo. A note recommends Chrome for that page (`README.md:305-306`). The README ends with the two console screenshots, "Training Monitor" and "Data distribution" (`README.md:310-316`).

### Part C: QLoRA in Colab (notebook)

**Step 14. Copy and pick a GPU** (nb cells 1-2). File → Save a copy in Drive; Runtime → Change runtime type → GPU (T4 is fine).

**Step 15. Install** (nb cell 8): `!uv pip install transformers==5.16.1 tokenizers==0.23.1 huggingface-hub==1.29.0 bitsandbytes==0.50.2`, `!uv pip install trl==1.14.0`, `!uv pip uninstall torchao`.
- **Stored output:** `Using Python 3.13.15 environment at: /usr`, `+ bitsandbytes==0.50.2`, `+ trl==1.14.0`, `- torchao==0.10.0`. Only these changed; Colab already had the other pinned versions.
- **Why uninstall torchao:** peft 0.20.0 raises `ImportError` "Found an incompatible version of torchao. Found version 0.10.0, but only versions above 0.16.0 are supported" when it probes torchao (`peft/import_utils.py:131-151`). As the cell's comment says ("peft refuses to add LoRA layers to a full-precision model while it is installed", nb cell 8:6), the probe only happens for non-quantized layers. PEFT tries its LoRA dispatchers in order and the first match wins: bitsandbytes 4-bit before torchao (`peft/tuners/lora/model.py:403-432`). So the 4-bit training in nb cell 72 never reaches the probe; the error would surface in nb cell 86, where `PeftModel.from_pretrained` adds the adapter to the FP16 model (`peft/tuners/lora/torchao.py:160`). *(Read from the source; not reproduced.)*

**Step 16. HF token** (nb cells 9-10): add the secret `HF_TOKEN` and turn on Notebook access, then run `userdata.get('HF_TOKEN')` and `login(token=hf_token)`. Expected output: `Hugging Face token successfully loaded.`

**Step 17. Imports** (nb cell 12). Expected output: `torch 2.11.0+cu128 | transformers 5.16.1 | peft 0.20.0 | trl 1.14.0 | bitsandbytes 0.50.2`. If a later cell fails, compare these versions first (nb cell 7).

**Step 18. Mount Drive and pre-download** (nb cells 14, 16).
- **Commands:** `drive.mount('/content/drive')`, then
  - `!hf download --repo-type model --quiet --cache-dir {cache_dir} facebook/opt-350m --exclude "*.h5" --exclude "*.msgpack"`
  - `!hf download --repo-type model --quiet --cache-dir {cache_dir} Qwen/Qwen3-0.6B`
- **Stored output:** the snapshot paths `/content/drive/MyDrive/LLM_cache/models--facebook--opt-350m/snapshots/08ab08cc4b72ff5593870b5d527cf4230323703c` and `/content/drive/MyDrive/LLM_cache/models--Qwen--Qwen3-0.6B/snapshots/c1899de289a04d12100db370d81485cdf75e47ca`.

**Step 19. Part B of the notebook: quantize OPT-350m** (nb cells 17-28).
- Load OPT-350m with the bnb config (nb cell 18). Poll 1 (nb cell 20) asks for the main advantage of 4-bit loading; the answer is memory. Then `print(model)`. You should see `Linear4bit` layers; `lm_head` stays `Linear` (nb cell 21 output).
- Tokenize "Hello my cheese name is" → `input_ids tensor([[    2, 31414,   127,  7134,   766,    16]], device='cuda:0')` (nb cell 25 output).
- Generate 20 tokens. Stored output: "Hello my cheese name is cheese.\nI'm not sure if you're joking or not.\nI'm not sure if" (nb cell 27).
- Read the "Deeper Dive" notes on compute dtype, FP4 vs NF4 and double quantization (nb cell 28; markdown only, nothing to run).

**Step 20. Load Qwen3-0.6B in 4-bit** (nb cells 31-36). The GPU check prints "Your GPU supports bfloat16. This notebook still trains in float16, so the same settings also work on T4 GPUs." (stored, A100). The bnb config is in nb cell 34; tokenizer, model and `prepare_model_for_kbit_training` are in nb cell 36.

**Step 21. Inspect** (nb cells 38-48).
- Parameter count: "Number of parameters: 375.84896 millions." (§3.5 explains it).
- `use_cache = False` (nb cell 40).
- The config prints `"quant_method": "bitsandbytes"`, `"bnb_4bit_quant_type": "nf4"` and `"tie_word_embeddings": true` (nb cell 42).
- Baseline generation (nb cell 45). The stored output ("what is your name ? I'm trying to get the correct answers…") doesn't start with the prompt, although `decode(outputs[0])` would include it (§9). Expect your output to begin with "Hello my cheese name is".
- Trainable count: "trainable params: 0 || all params: 375848960 || trainable%: 0.0" (nb cell 48).

**Step 22. Data** (nb cells 51-63).
- `!gdown 1b5hFsjpCqI3ZXvraIF0w7eW-mRO7Ecao` downloads `train_16k.jsonl` (23.2 MB).
- Sample 1000 rows with `random_state=42` → `(1000, 1)`. The single column, `contents`, is exactly Track A's Gemini format.
- `extract_qa` turns rows back into question/answer (nb cell 55), then into a HF `Dataset` (nb cell 57).
- The chat template is applied (nb cell 59).
- `train_test_split(test_size=0.10, shuffle=True, seed = 42)` → `(900, 3)` / `(100, 3)` (nb cell 61).
- Verify one example (nb cell 63, quoted in §3.3) and plot the token-length histogram (nb cell 64).

**Step 23. Configure and train** (nb cells 65-75).
- Polls along the way: Poll 2 (nb cell 66, LoRA trains only small adapter matrices), Poll 3 (nb cell 68, raising `r` to 64 adds trainable parameters and slows training), Poll 4 (nb cell 74, the model adopts the training style even on unrelated questions while keeping most general knowledge).
- `LoraConfig` (nb cell 67), `SFTConfig` (nb cell 70), `SFTTrainer` + fp32 cast (nb cell 72), whose output is "trainable params: 1146880 || all params: 376995840 || trainable%: 0.3042155584528466".
- Then `trainer.train()`. The stored progress was `[450/450 03:36, Epoch 2/2]`, with training loss 2.007381 (step 50) → 1.629233 (100) → 1.509897 (150) → 1.467495 (200) → 1.407929 (250) → 1.354591 (300) → 1.376134 (350) → 1.364813 (400) → 1.350437 (450). It ended with `TrainOutput(global_step=450, training_loss=1.4964344957139757, …)`.
- A one-time warning `[transformers] The tokenizer has new PAD/BOS/EOS tokens that differ from the model config and generation config. … Updated tokens: {'bos_token_id': None}.` is harmless.

**Step 24. TensorBoard** (nb cell 77): `%load_ext tensorboard`, `%tensorboard --logdir results/runs`. transformers writes to `output_dir/runs/<date>_<host>` by default (`transformers/integrations/integration_utils.py:574`, `:620-621`), so `results/runs` is right. The stored output is hidden.

**Step 25. Evaluate** (nb cells 80, 82).
- The loss/perplexity table is quoted in §3.8. Each evaluation pass takes about 9 s on an A100.
- Side-by-side generations for 3 prompts with `max_new_tokens=100` and greedy decoding (nb cell 82:19-44). That's why the stored answers stop mid-sentence ("…A fresh cheese, like a Pecor").

**Step 26. Save** (nb cells 84, 86, 88).
- **Adapters:** saved to `LLM_cache/Qwen0.6B-finetune_cheese`.
- **Merged model:** reload FP16 → `PeftModel.from_pretrained` → `merge_and_unload()` → save to `…_merged`. The stored outputs list `tokenizer_config.json`, `chat_template.jinja` and `tokenizer.json` paths.
- **Optional:** a private HF repo `<user>/Qwen0.6B-finetune_cheese_merged`. Stored output: "✓ Detected Hugging Face username: rashmi" and "Model successfully uploaded to https://huggingface.co/rashmi/Qwen0.6B-finetune_cheese_merged".
- **Wrap-up:** nb cell 89 renders a "QLoRA Fine-Tuning Steps" flow diagram by sending Mermaid code to `https://mermaid.ink` (needs internet); nb cell 90 lists further reading.

---

## 5. Code tour

```
llm-finetuning/  (main @ 44ef6f0)
├── README.md                      # the tutorial (Track A); 316 lines
├── env.dev                        # shared settings, sourced by each docker-shell.sh (GCP_PROJECT, bucket, key path)
├── .gitignore                     # ignores *.csv, *.json, dataset-creator/data/*, .DS_Store, .idea
├── dataset-creator/               # container 1: make + upload the Q&A dataset
│   ├── cli.py                     #   --generate (Gemini, JSON schema) / --prepare (csv+jsonl, split) / --upload (GCS)
│   ├── Dockerfile                 #   python:3.12-slim-bookworm + uv sync --frozen into /.venv, user app (identical to llm-rag's)
│   ├── docker-shell.sh            #   source ../env.dev; docker build; docker run -v .:/app -v secrets:/secrets
│   ├── docker-entrypoint.sh       #   prints arch/versions, activates /.venv, exec bash
│   ├── pyproject.toml, uv.lock    #   llm-rag's deps + google-cloud-storage + scikit-learn (136 lock entries)
│   └── data/                      #   (runtime) cheese_qa_*.txt, instruct-dataset.csv, train/test .csv/.jsonl
├── gemini-finetuner/              # container 2: submit tuning job + chat with endpoint
│   ├── cli.py                     #   --train (tunings.tune in us-central1) / --chat (endpoint via us multi-region)
│   └── Dockerfile, docker-shell.sh, docker-entrypoint.sh, pyproject.toml, uv.lock   # byte-identical copies; docker-shell.sh differs in IMAGE_NAME and one blank line
├── autotrain-runner/              # NOT in README: old HF AutoTrain (Mistral-7B, conda, --gpus all); stale (§6, §9)
└── images/training-1.png, training-2.png   # console screenshots: metrics + data distribution

Colab: L08_llm_finetuning.ipynb    # QLoRA on Qwen3-0.6B: Part A setup, Part B quantization, Part C fine-tune/eval/save
```

**Excerpt 1: `dataset-creator/docker-shell.sh:13-22`** (how the container sees your files)
```bash
docker build -t $IMAGE_NAME -f Dockerfile .

# Run Container
docker run --rm --name $IMAGE_NAME -ti \
-v "$BASE_DIR":/app \
-v "$SECRETS_DIR":/secrets \
-e GOOGLE_APPLICATION_CREDENTIALS=$GOOGLE_APPLICATION_CREDENTIALS \
-e GCP_PROJECT=$GCP_PROJECT \
-e GCS_BUCKET_NAME=$GCS_BUCKET_NAME \
$IMAGE_NAME
```
- **L13:** the build context is `.`, the folder you're in. That's why you must `cd` into it first.
- **L16:**
  - `--rm` deletes the container on exit
  - `--name` makes a second simultaneous run collide
  - `-ti` gives you an interactive TTY
- **L17:** your host folder *replaces* the image's `/app`. `cli.py` edits are live, and `data/` lands on your disk. The image's `COPY . ./` (`Dockerfile:48`) is effectively shadowed at runtime.
- **L18:** `<parent>/secrets` appears as `/secrets`. If the folder doesn't exist, Docker creates an empty one (`README.md:64`).
- **L19-21:** the only configuration the Python code sees. `GOOGLE_APPLICATION_CREDENTIALS` is a *container* path. No `-p` flag: nothing is served.

**Excerpt 2: `dataset-creator/Dockerfile:37-51`**
```dockerfile
# Switch to the new user
USER app
WORKDIR /app

# Copy dependency files first for better layer caching
COPY --chown=app:app pyproject.toml uv.lock* ./

# Install dependencies in a separate layer for better caching
RUN uv sync --frozen

# Copy the rest of the source code
COPY --chown=app:app . ./

# Entry point
ENTRYPOINT ["/bin/bash","docker-entrypoint.sh"]
```
- **L38:** the app runs as non-root `app` (uid 1000, created at `:31`). That affects bind-mount write permissions on Linux (§6.6).
- **L42-45:** the dependency layer depends only on `pyproject.toml` + `uv.lock`, so code edits don't trigger a reinstall. `--frozen` installs the lock as-is without re-resolving.
- **L45:** together with `ENV UV_PROJECT_ENVIRONMENT=/.venv` (`:18`), the venv lives at `/.venv`, which survives the `/app` bind mount.
- **L51:** the entrypoint activates the venv and `exec`s an interactive bash (`docker-entrypoint.sh:12-15`).

**Excerpt 3: `dataset-creator/cli.py:184-199`** (the generation loop)
```python
    for i in range(0, NUM_ITERATIONS):
        print(f"Generating batch: {i}")
        try:

            response = llm_client.models.generate_content(
                model=GENERATIVE_MODEL,
                contents=INPUT_PROMPT,
                config=GENERATION_CONFIG,
            )
            generated_text = response.text

            # Create a unique filename for each iteration
            file_name = f"{OUTPUT_FOLDER}/cheese_qa_{i}.txt"
            # Save
            with open(file_name, "w") as file:
                file.write(generated_text)
```
- **L184:** `NUM_ITERATIONS` (`:170`) is the dataset-size knob: about 20 pairs per iteration.
- **L188-192:** `llm_client` is `genai.Client(vertexai=True, project=GCP_PROJECT, location=GCP_LOCATION)` (`:25`), with `GCP_LOCATION = "global"` (`:18`). `GENERATION_CONFIG` (`:173-181`) bundles the system instruction, `response_mime_type="application/json"` and `response_schema` (`:146-160`). Gemini therefore *must* emit `[{"question":…, "answer":…}, …]`.
- **L193:** `response.text` is the raw JSON string, which gets saved untouched. Parsing is deferred to `--prepare`, so a bad batch never blocks the others.
- **L196:** the files are named by iteration index. Re-running **overwrites** `cheese_qa_0..4`; it doesn't add to them.
- The `except` at `:200-201` swallows every error, including auth and quota. Read the output.

**Excerpt 4: `dataset-creator/cli.py:249-262`** (Gemini format + split)
```python
    # Gemini Data prep: https://cloud.google.com/vertex-ai/generative-ai/docs/models/gemini-supervised-tuning-prepare
    # {"contents":[{"role":"user","parts":[{"text":"..."}]},{"role":"model","parts":[{"text":"..."}]}]}
    output_pairs_df["contents"] = output_pairs_df.apply(
        lambda row: [
            {"role": "user", "parts": [{"text": row["question"]}]},
            {"role": "model", "parts": [{"text": row["answer"]}]},
        ],
        axis=1,
    )

    # Test train split
    df_train, df_test = train_test_split(
        output_pairs_df, test_size=0.1, random_state=42
    )
```
- **L250:** the one-line spec of a Gemini SFT example: a list of turns, each with a `role` (`user`/`model`, not `assistant`) and `parts`.
- **L251-257:** builds a Python list per row. `to_json(orient="records", lines=True)` at `:271`/`:273` serializes `{"contents": [...]}` per line.
- **L260-262:** a seeded 90/10 split. The 10% becomes the **validation** set Google evaluates during tuning (`gemini-finetuner/cli.py:11`, `:57`), capped at 256 rows (`:266-267`).

**Excerpt 5: `dataset-creator/cli.py:283-294`** (upload to GCS)
```python
    data_files = glob.glob(os.path.join(OUTPUT_FOLDER, "*.jsonl")) + glob.glob(
        os.path.join(OUTPUT_FOLDER, "*.csv")
    )
    data_files.sort()

    # Upload
    for index, data_file in enumerate(data_files):
        filename = os.path.basename(data_file)
        destination_blob_name = os.path.join("llm-finetune-dataset-small", filename)
        blob = bucket.blob(destination_blob_name)
        print("Uploading file:", data_file, destination_blob_name)
        blob.upload_from_filename(data_file, timeout=timeout)
```
- **L283-286:** five files (two JSONL, three CSV), sorted alphabetically by path.
- **L291:** the "folder" prefix is hard-coded and must match `gemini-finetuner/cli.py:10-11`.
- **L292-294:** a blob is just a name in a bucket. `upload_from_filename` streams the file, authenticated by the SA key through ADC.

**Excerpt 6: `gemini-finetuner/cli.py:19-33`** (two clients, two locations)
```python
train_client = genai.Client(
    vertexai=True,
    project=GCP_PROJECT,
    location=TUNING_LOCATION,
)

# Chat client: multi-region "us" — required to call tuned Gemini 3.1 endpoints
chat_client = genai.Client(
    vertexai=True,
    project=GCP_PROJECT,
    location=SERVING_LOCATION,
    http_options=types.HttpOptions(
        base_url="https://aiplatform.us.rep.googleapis.com",
    ),
)
```
- **L19-23:** `TUNING_LOCATION = "us-central1"` (`:13`) → host `us-central1-aiplatform.googleapis.com`. Tuning jobs are created in a single region.
- **L26-33:** `SERVING_LOCATION = "us"` (`:14`). google-genai 1.39.1 would turn that into `https://us-aiplatform.googleapis.com/` (`_api_client.py:654-656`). The explicit `base_url` overrides it with the multi-region "rep" (regional endpoint) host (`_api_client.py:673-677`).
- Neither client touches credentials at construction; they load on the first call.

**Excerpt 7: `gemini-finetuner/cli.py:51-65`** (the tuning request)
```python
    # Create tuning job config
    tuning_config = types.CreateTuningJobConfig(
        epoch_count=1,
        learning_rate_multiplier=1.0,
        adapter_size="ADAPTER_SIZE_FOUR",
        tuned_model_display_name="pavlos-cheese-demo-v3.1",
        validation_dataset=validation_dataset,
    )

    # Start supervised fine-tuning
    tuning_job = train_client.tunings.tune(
        base_model=GENERATIVE_SOURCE_MODEL,
        training_dataset=training_dataset,
        config=tuning_config,
    )
```
- **L53-55:** the three knobs you'd change:
  - **epochs:** the README's cost table assumes 3
  - **LR multiplier:** e.g. 0.5 to be gentler
  - **adapter size:** `ADAPTER_SIZE_ONE`…`THIRTY_TWO`, the rank-like capacity
- **L56:** the display name you'll look for in the console. Change it per run.
- **L57:** a `TuningDataset` object passed where a `TuningValidationDataset` is declared. pydantic coerces it (Step 10).
- **L61-65:** one HTTPS POST. The returned job object is a *snapshot*, which is why `:72` re-fetches it with `tunings.get(name=...)`.

**Excerpt 8: `gemini-finetuner/cli.py:104-119`** (chatting with the tuned model)
```python
    # Get the model endpoint from Vertex AI Tuning UI after the job succeeds.
    # For gemini-3.1-flash-lite serving, use locations/us/endpoints/...
    # https://console.cloud.google.com/vertex-ai/studio/tuning?project=ac215-project
    MODEL_ENDPOINT = "projects/129349313346/locations/us/endpoints/7655908260297310208"

    query = "How is cheese made in Greece? Answer pavlos style?"
    print("query: ", query)
    print("Using serving location:", SERVING_LOCATION)

    response = chat_client.models.generate_content(
        model=MODEL_ENDPOINT,
        contents=query,
        config=generation_config,
    )
    generated_text = response.text
    print("Fine-tuned LLM Response:", generated_text)
```
- **L107:** a full resource name that includes the **instructor's project number**. Because it starts with `projects/`, the client doesn't prepend *your* project (`_api_client.py:1008-1014`). Leave it unchanged and you're calling someone else's endpoint.
- **L109:** no system prompt. The persona must come from the weights. Compare L10's app, which *adds* a RAG system instruction on top (`cheese-app-v0/api-service/api/routers/rag.py:110-120`).
- **L113-117:** the same `generate_content` API as the base model; a tuned endpoint is a drop-in model name.

**Excerpt 9: nb cell 34:1-6** (QLoRA quantization config)
```python
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype="float16",
    bnb_4bit_use_double_quant=True,
)
```
- **L2:** store linear weights in 4 bits (§3.5).
- **L3:** NF4 levels, tuned for bell-shaped weights. The default would be `"fp4"` (nb cell 28).
- **L4:** dequantize to fp16 for matmuls, chosen over bf16 for T4 compatibility (nb cell 30).
- **L5:** also quantize the per-block scale constants.
- Passed as `quantization_config=bnb_config` with `device_map={"":0}` (everything on GPU 0) in nb cell 36:8-13.

**Excerpt 10: nb cell 59:10-15** (chat-template formatting)
```python
def transform_conversation(example):
    messages = [{"role": "user", "content": example["question"]},
                {"role": "assistant", "content": example["answer"]}]
    return {"text": tokenizer.apply_chat_template(messages, tokenize=False).removesuffix("\n")}

dataset = dataset_df.map(transform_conversation)
```
- **L11-12:** OpenAI-style message dicts. Note `assistant` here vs `model` in Gemini JSONL; each ecosystem has its own role names.
- **L13:** the tokenizer's own Jinja template writes `<|im_start|>`/`<|im_end|>` and the empty `<think>` block. That's safer than the hand-written f-string kept commented out at nb cell 59:1-8. `.removesuffix("\n")` leaves `<|im_end|>` (EOS) as the last token, so TRL doesn't append a second EOS (§3.3).
- **L15:** adds a `text` column, which `SFTConfig`'s default `dataset_text_field="text"` picks up (`trl/trainer/sft_config.py:181`).

**Excerpt 11: nb cell 67:2-7** (LoRA config); see also nb cell 70 for `SFTConfig`
```python
peft_config = LoraConfig(lora_alpha=16, # The LoRA scaling parameter
                        lora_dropout=0.1, # Dropoput probability in the LoRa layers
                        r=8, # Rank of the LoRA
                        bias="none", # Do not update any bias
                        task_type="CAUSAL_LM", # Type of model to train
                    )
```
- **L2, L4:** scale α/r = 2; rank 8.
- **No `target_modules`:** PEFT's per-architecture default applies, `q_proj`+`v_proj` for Qwen3. That gives exactly 1,146,880 parameters (§3.6). `target_modules="all-linear"` would give 5,046,272 (Exercise E1).
- **L3:** dropout on the LoRA input path only.
- **L5:** biases stay frozen.
- **L6:** tells PEFT to wrap the model as a causal-LM `PeftModel`.
- The companion `SFTConfig` (nb cell 70:2-18):
  - `max_length=512`
  - 2 epochs, batch size 4
  - `paged_adamw_32bit`, LR `2e-4` with cosine schedule
  - `fp16=True`
  - `train_sampling_strategy="group_by_length"` (the transformers 5 name for length bucketing, `transformers/training_args.py:1355`)
  - `save_strategy="no"`, `report_to="tensorboard"`

**Excerpt 12: nb cell 72:2-16** (trainer + the dtype fix)
```python
trainer = SFTTrainer(
    model=base_model,             # Model to be fine-tunned
    train_dataset=train_dataset,  # The dataset to train with
    peft_config=peft_config,      # LoRA configuration
    args=training_arguments,      # Trainig arguments defined before

)

# trl converts the LoRA weights of a 4-bit model to bfloat16. fp16 training (fp16=True above) cannot
# unscale bfloat16 gradients on the GPU, so keep the LoRA weights in float32.
for param in trainer.model.parameters():
    if param.requires_grad:
        param.data = param.data.float()

print_trainable_parameters(trainer.model)
```
- **L2-6:**
  - `SFTTrainer` injects LoRA **into `base_model`'s modules in place**. That's why nb cell 82 can call `generate_response(base_model, …)` and get the fine-tuned behaviour ("base_model is the fine-tuned model here", nb cell 82).
  - It also tokenizes, adds EOS and truncates (the stored progress bars).
  - There's no `eval_dataset`; evaluation is done by hand in nb cell 80.
- **L10-14:**
  - Undoes TRL's bf16 cast for quantized models (`trl/trainer/sft_trainer.py:1160-1167`), so fp16 AMP's gradient scaler can unscale fp32 gradients.
  - Only `requires_grad` parameters, i.e. the LoRA A/B matrices, are touched.
  - This is also why the saved adapter is ~4.6 MB (4 bytes × 1.15 M).
- **L16:** prints the 0.30% line.

---

## 6. Gotchas and common errors

1. **`docker-shell.sh: 8: source: not found` (Ubuntu, Debian, WSL).**
   - **Cause:** the README says `sh docker-shell.sh` (`README.md:87`, `:240`). On those systems `/bin/sh` is `dash`, which has no `source` builtin, and `set -e` then stops the script. The exact message was reproduced with a stand-in script.
   - **Line numbers:** line 8 in `dataset-creator/docker-shell.sh`, line 7 in `gemini-finetuner/docker-shell.sh`.
   - **Fix:** `bash docker-shell.sh`, or change the line to `. ../env.dev`. macOS's `/bin/sh` is bash, so the README works there.

2. **`../env.dev: No such file or directory`.**
   - **Cause:** running the script from the repo root (`bash dataset-creator/docker-shell.sh`). Paths are relative to the current directory (`README.md:68`), so `source ../env.dev` looks one level *above* the repo and fails, and `set -e` stops the script there. (Even if it found an `env.dev`, `BASE_DIR=$(pwd)` (`env.dev:4`) would mount the wrong folder as `/app` and `docker build … .` would use the wrong context.)
   - **Fix:** `cd dataset-creator` first.

3. **Key not found.**
   - **Symptoms:** `--generate` prints `Error occurred while generating content: File /secrets/llm-service-account.json was not found.` five times. `--prepare` then prints `Shape: (0, 0)` and crashes with `KeyError: 'question'`.
   - **Cause:** the key isn't at `<parent>/secrets/llm-service-account.json`, or it's named `…json.json` (`README.md:67`). Docker silently mounts an empty, auto-created folder (`README.md:64`). The errors are swallowed by `cli.py:200-201`.
   - **Fix:** `ls -la /secrets` inside the container (`README.md:69`).

4. **403 on upload or tuning.**
   - **Upload:** `env.dev:7` still says `cheese-dataset`, a bucket in the instructor's project.
   - **Tuning:** `gemini-finetuner/cli.py:10-11` still points at `gs://cheese-dataset/...`. The tuning job reads the data as your project's Vertex AI tuning service agent (`types.py:10224-10227`), which normally has no access to the course bucket, whatever roles your own SA has. (Not verified; if the course bucket were public, there would be no 403 and the job would train on the instructor's data.)
   - Also: the SA lacks Storage Admin or `roles/aiplatform.user` (`README.md:43-44`), or `aiplatform.googleapis.com` isn't enabled.
   - **Fix:** use your own bucket in both places; grant the roles; enable the API (§2).

5. **`--chat` returns 403/404 for `projects/129349313346/...`.**
   - **Cause:** `MODEL_ENDPOINT` is hard-coded to the instructor's endpoint (`gemini-finetuner/cli.py:107`). L10's `cheese-app-v0/api-service/api/routers/rag.py:22` has the same trap.
   - **Fix:** paste your endpoint from the console after the job succeeds (Step 11).

6. **`PermissionError: [Errno 13] Permission denied: 'data'` (Linux hosts).**
   - **Cause:** the container runs as uid 1000 (`Dockerfile:31`, `:38`) and writes into your bind-mounted folder (`docker-shell.sh:17`). `dataset-creator/data/.gitkeep` was deleted in `6e4c3f7`, so a fresh clone has no `data/` and the container must create it. If your host uid isn't 1000 and the folder isn't group/world-writable, that fails. Docker Desktop (macOS/Windows) maps permissions and isn't affected. *(Reasoned from the files; not reproduced.)*
   - **Fix:** `mkdir -m 777 dataset-creator/data` on the host, or `chmod o+w dataset-creator`.

7. **"My tuned model is `None`".**
   - **Cause:** `main()` hard-codes `train(wait_for_job=False)` (`gemini-finetuner/cli.py:126`). After 60 s, `tuning_job.tuned_model` is still empty, so `Tuned model info: None` prints and the "paste that endpoint" hint (`:93-96`) never does.
   - **Fix:** watch the console (`README.md:261`), or set `wait_for_job=True`.

8. **The README's system prompt and outputs don't match what you get.**
   - **Cause:** the README excerpt (`README.md:114-135`) and the samples (`:163-175`, `:295-301`) predate commit `6e4c3f7`, which changed the openers in `dataset-creator/cli.py:83-101` and the chat query in `gemini-finetuner/cli.py:109`.
   - **Fix:** trust the code, but expect a mix: the old openers are gone from the opener list, yet the prompt's sample JSON still uses them (`dataset-creator/cli.py:133`, `:137`, `:140`). Also expect the Colab's 16k dataset to use the *old* openers, e.g. "Yello - this is Pavlos your cheese monker" and "Welcome students, this is Pavlos…" (nb cell 55 output) or "Welcome welcome, cheese lovers! This is your lecturer Pavlos Protopapas…" (nb cell 63 output). None of the stored samples use the new "Good question"/"Glad you ask" openers. ("Remember rule number 672…" appears in both the old and the new prompt.)

9. **Slow first build and a big image.**
   - **Cause:** `pyproject.toml:8-16` is llm-rag's dependency list (`chromadb`, `langchain`, `langchain-community`, `openai`, `openai-agents`) plus `google-cloud-storage` and `scikit-learn`. The code imports only pandas, sklearn, google-cloud-storage and google-genai (`dataset-creator/cli.py:1-14`; `gemini-finetuner/cli.py:1-6`). Two images also get built.
   - **Fix (optional):** trim the dependencies with `uv remove chromadb langchain langchain-community openai openai-agents`, then rebuild.
   - **Apple Silicon is fine:** every locked package with platform wheels also ships a Linux aarch64 wheel; a parse of `uv.lock` confirms it. The only exception is Windows-only `pywin32`. (`pypika` ships only an sdist, which uv builds at install time; it's pure Python, so it works on both architectures.)

10. **Truncated generations (`Number of errors: 1`).**
    - **Cause:** 20 long answers must fit in `max_output_tokens=8192` (`dataset-creator/cli.py:176`). The README's own screenshot shows a mean of 267 output tokens per answer (`images/training-2.png`), so 20 answers come to ~5.5k+ tokens and usually fit. A verbose batch can hit the limit and produce invalid JSON, which `prepare()` skips (`:221-226`).
    - **Fix:** ask for 10 pairs per call, or raise the limit.

11. **Container name conflict.**
    - **Symptom:** `docker: Error response from daemon: Conflict. The container name "/llm-dataset-creator" is already in use`.
    - **Cause:** a second terminal running the same script (`--name $IMAGE_NAME`, `docker-shell.sh:16`).
    - **Fix:** exit the other shell, or attach a second shell with `docker exec -it llm-dataset-creator bash`. That new shell does **not** run `docker-entrypoint.sh`, so the venv isn't activated (`/.venv/bin` isn't on `PATH`; the Dockerfile never sets it). Run `source /.venv/bin/activate` first, or `python cli.py` will fail with `ModuleNotFoundError`.

12. **Colab: `SecretNotFoundError` / `NotebookAccessError` at `userdata.get('HF_TOKEN')`.**
    - **Cause:** the secret is missing, has the wrong name, or "Notebook access" is off (nb cell 9).
    - **Fix:** add `HF_TOKEN` and toggle access on. The public models download without a token, so only Step 6.3 truly needs it.

13. **Colab: torchao `ImportError`.**
    - **Symptom:** "Found an incompatible version of torchao. Found version 0.10.0, but only versions above 0.16.0 are supported".
    - **Cause:** you skipped `!uv pip uninstall torchao` (nb cell 8:7); peft 0.20.0 requires torchao ≥ 0.16.0 if it's installed (`peft/import_utils.py:135-150`).
    - **When:** not during 4-bit training. PEFT only probes torchao for layers that no earlier dispatcher (such as bitsandbytes 4-bit) claimed (`peft/tuners/lora/model.py:403-432`), so expect it at nb cell 86, where the adapter is loaded onto the FP16 model for merging. *(Read from the source; not reproduced.)*
    - **Fix:** run that cell, then restart the session if peft was already imported.

14. **Colab: removing the fp32 cast (nb cell 72:12-14) with `fp16=True`.**
    - **Symptom:** with `fp16=True` and bf16 LoRA weights, the AMP grad scaler fails. The expected error is PyTorch's `"_amp_foreach_non_finite_check_and_unscale_cuda" not implemented for 'BFloat16'`; not reproduced.
    - **Cause:** TRL casts QLoRA adapters to bf16 (`trl/trainer/sft_trainer.py:1160-1167`).
    - **Fix:** keep the cast. Or, on Ampere+ GPUs, use `bf16=True, fp16=False`.

15. **Colab: re-running the trainer cell (nb cell 72) without reloading the model.**
    - **Symptom:** PEFT warns "You are trying to modify a model with PEFT for a second time. If you want to reload the model with a different config, make sure to call `.unload()` before." (`peft/mapping_func.py:71-75`, peft 0.20.0).
    - **Cause:** `SFTTrainer` injected the LoRA layers into `base_model`'s modules in place (that's why nb cell 82 can use `base_model` as the fine-tuned model), so a second `SFTTrainer(model=base_model, peft_config=...)` calls `get_peft_model` again (`trl/trainer/sft_trainer.py:1134`; `base_model` itself is not a `PeftModel`, so TRL's own guard at `:1093-1098` doesn't fire) and PEFT finds LoRA layers already there. Typical when you change `r` or `lora_alpha` in nb cell 67 and re-run from there. *(Warning condition read from the source; the effect on the already-trained adapter was not reproduced.)*
    - **Fix:** re-run nb cell 36 (reload and `prepare_model_for_kbit_training`) before nb cells 67-72. Note also that nb cell 86 rebinds `base_model` to a fresh FP16 model that gets merged, so re-running Step 5 cells after Step 6.2 compares different objects.

16. **Colab: downloads repeat each session.**
    - **Cause:** the tokenizer calls don't pass `cache_dir` (nb cell 36:2-4, nb cell 86:14). The tokenizer files go to the ephemeral `~/.cache/huggingface`; the stored output shows `config.json`, `tokenizer_config.json`, `vocab.json`, `merges.txt` and `tokenizer.json` downloading in nb cell 36.
    - **Effect:** harmless (a few MB), but inconsistent with the "persist in Drive" design (nb cell 15).

17. **Colab: `gdown` fails ("Too many users have viewed or downloaded this file recently" or permission denied).**
    - **Cause:** Google Drive quota or sharing on file `1b5hFsjpCqI3ZXvraIF0w7eW-mRO7Ecao` (nb cell 51).
    - **Fix:** retry later, or build your own JSONL with Track A (`train.jsonl` has the same `contents` format), and change the file name in nb cell 53:1.

18. **`autotrain-runner/` is a trap if you wander in.** It isn't referenced by the README and doesn't run as committed:
    - `trainer.sh:17` runs `autotrain --config some_ml.yaml`, but the only config is `configs/llm_config_mistral.yaml`
    - `gcp-push.py:7` opens `llm_training_config.yaml`
    - `gcp-pull.py:33-36` reads `csv_downloaded`/`yaml_downloaded`, which are only assigned inside the loop (`:23`, `:28`); if no `.csv` (or no `.yaml`) blob exists, that read raises `UnboundLocalError` (a `NameError` subclass). `gcp-pull.py:20` also downloads CSVs into `./data/`, which exists only because of `autotrain-runner/data/.gitkeep`
    - the bucket `autotrain_trainer` is hard-coded (`gcp-pull.py:39`, `gcp-push.py:34`)
    - `environment_droplet.yml:260` pins `prefix: /home/karthik_rathod/anaconda3/envs/autotrain-env`
    - `docker-shell.sh:15` needs `--gpus all` (an NVIDIA GPU)
    - `Dockerfile:2` uses `continuumio/miniconda3:latest`

    Read it as history only.

---

## 7. Where this sits in the course

**What the previous lectures gave you**
- **L05 RAG** (`llm-rag`, see the [L05 guide](L05-rag.md)):
  - the container pattern that L08 reuses verbatim: **`dataset-creator/Dockerfile` is byte-identical to `llm-rag/Dockerfile`** (`diff` is empty)
  - the same SA `llm-service-account` and key location
  - the same google-genai client style: `genai.Client(vertexai=True, project=…, location="global")` and `gemini-3.1-flash-lite`
  - the idea of changing an LLM's behaviour *without* touching weights (retrieved context)
- **L06-L07 Agents:** tool calls and structured outputs. L08 reuses structured output (`response_schema`) for data generation.

**What L08 adds**
- **Weights change:**
  - supervised fine-tuning as a *managed cloud job* (Track A)
  - as hands-on PEFT/QLoRA code you control end to end (Track B)
- **Data engineering for LLMs:** synthetic data from a teacher model; the CSV → JSONL → chat-template pipeline; train/validation split.
- **Cloud Storage as a hand-off point** between your container and a cloud service: the first time a Google-run job reads *your* bucket.
- **Async cloud jobs:** submit, poll and retrieve an artifact (an endpoint).
- **Location awareness:** `global` vs `us-central1` vs multi-region `us`, and custom `base_url`.

**Concrete diff vs `llm-rag` (L05)**

| | `llm-rag` (L05) | `llm-finetuning` (L08) |
|---|---|---|
| Containers | 1 CLI container + ChromaDB via `docker compose run` (`llm-rag/docker-shell.sh:12`) | 2 separate CLI containers via plain `docker build` + `docker run` |
| Settings | exported in `docker-shell.sh:7-9` | shared `env.dev` sourced by both shells |
| Secrets mount | `../secrets:/secrets` from the repo root (`docker-compose.yml:11`) | `../../secrets` from a subfolder (`env.dev:5`): the same physical folder |
| Dependencies | `pyproject.toml` | the same list + `google-cloud-storage>=3.4.1` + `scikit-learn>=1.7.2` |
| New APIs | embeddings, ChromaDB | `models.generate_content` with `response_schema`, GCS uploads, `tunings.tune`/`tunings.get`, tuned-endpoint calls |

**Diff vs last year (`pipenv` branch, `fb0073a`, 2025-03-10)**
- **Dependencies:** Pipfile → uv (`c9b52dd`).
- **SDK:** `vertexai.preview.tuning.sft.train(source_model="gemini-1.5-flash-002", adapter_size=4, …)` → `google-genai` `tunings.tune(base_model="gemini-3.1-flash-lite", config=CreateTuningJobConfig(adapter_size="ADAPTER_SIZE_FOUR", …))` (`origin/pipenv:gemini-finetuner/cli.py:8-39` vs `main:gemini-finetuner/cli.py:44-65`).
- **Generator:** `gemini-1.5-flash-001` in `us-central1` → `gemini-3.1-flash-lite` in `global`. Last year's generator had no `response_schema`/`response_mime_type`; JSON structured output arrived with the uv/google-genai rewrite (`c9b52dd`).
- **Clients:** one → two (separate train and chat clients).
- **Stale leftovers:** the README's cost section and screenshots are from that era.

**What comes next**
- **L09 (CI/testing):** unrelated to fine-tuning.
- **L10 `cheese-app-v0`:** **consumes your tuned endpoint**. Its README Step 5 says "Update `FINE_TUNE_GENERATIVE_MODEL` in `api-service/api/routers/rag.py` to your own fine-tuned model endpoint (from the llm-finetuning tutorial)" (`cheese-app-v0/README.md:247`). The `/finetunechat` page is "the same RAG flow as Chat, answered by a fine-tuned model" (`cheese-app-v0/README.md:245-249`); on the API side the route `/fine-tune-llm-response` (`rag.py:257-265`) calls the endpoint with the RAG system instruction via `genai.Client(vertexai=True, project=GCP_PROJECT, location="us")` (`rag.py:110-120`). That client has **no** `base_url` override and uses google-genai 2.28.0 (`api-service/Pipfile.lock`) rather than 1.39.1. Newer SDKs map the multi-regions `us`/`eu` to `https://aiplatform.{location}.rep.googleapis.com/` themselves (checked in 2.30.0; §9).
- **L13 (training workflows: W&B, multi-GPU, serverless training on Vertex AI):** generalizes Track B (GPU training loops, experiment tracking), and its serverless training is the closest analogue of Track A's submit-a-job pattern.
- **L14-L15 (serverless/Vertex AI):** turn "submit a job to Google" into pipelines and deployed endpoints. Unlike tuned Gemini endpoints, L15's custom-model endpoints run billable nodes.

---

## 8. Exercises

**E1. Count before you train (conceptual + hands-on)**
- In nb cell 67, predict `trainable params` for (a) `r=16`, and (b) `r=8, target_modules="all-linear"`. Then run nb cells 67-72 to check. Use the config from nb cell 42: hidden 1024, 16 heads × 128 = 2048 for q, 8 KV heads × 128 = 1024 for k/v, intermediate 3072, 28 layers.
- *Worked answer:*
  - (a) The count is linear in r: 2 × 1,146,880 = **2,293,760**.
  - (b) For each linear layer, r × (d_in + d_out). That's q 8×3072, k 8×2048, v 8×2048, o 8×3072, gate 8×4096, up 8×4096, down 8×4096, for 8 × 22,528 = 180,224 per layer. × 28 = **5,046,272**, or about 1.3% of the stored parameters. PEFT's `all-linear` excludes the output head; it's also tied to the embedding here.
  - Memory and time grow accordingly. For pure style transfer, the gain is usually small.

**E2. "source: not found" (debugging)**
- On Ubuntu, `sh docker-shell.sh` in `gemini-finetuner/` prints `docker-shell.sh: 7: source: not found` and nothing else happens. Why line 7, why "not found", and why didn't Docker run?
- *Worked answer:*
  - `/bin/sh` is `dash`, which lacks the bash-only `source` builtin. Line 7 is `source ../env.dev` (`gemini-finetuner/docker-shell.sh:7`); in `dataset-creator` it's line 8.
  - `set -e` (`:4`) aborts on the failure (exit status 127) before `docker build`.
  - Fix: `bash docker-shell.sh`, or use the POSIX `. ../env.dev`.

**E3. The silent failure chain (debugging)**
- `python cli.py --generate` prints five lines of `Error occurred while generating content: File /secrets/llm-service-account.json was not found.` and exits normally. `python cli.py --prepare` then prints `Shape: (0, 0)` and dies with `KeyError: 'question'`. Explain each step and the fix.
- *Worked answer:*
  - The genai client only loads ADC on the first request. google-auth reads `GOOGLE_APPLICATION_CREDENTIALS=/secrets/llm-service-account.json` and raises "File … was not found." (`google/auth/_default.py:174`, google-auth 2.41.1).
  - `generate()` catches and prints it per batch (`cli.py:200-201`), so no `cheese_qa_*.txt` is written.
  - `prepare()` builds an empty DataFrame. `drop_duplicates` on an empty frame is a no-op, so `Shape: (0, 0)` prints; then `output_pairs_df["question"]` at `:243` raises `KeyError`. This was reproduced with pandas.
  - Fix: the key belongs in `<parent>/secrets/` with the exact name; check `ls -la /secrets` in the container.
  - Lesson: an `except Exception: print(...)` turns hard errors into soft ones.

**E4. Grow the dataset (hands-on, predict-then-run)**
- Set `NUM_ITERATIONS = 10` (`dataset-creator/cli.py:170`) and run `--generate --prepare`. Predict the number of files, the rows, the split sizes and the number of lines in `train.jsonl`. What happens to the files from the previous 5-iteration run?
- *Worked answer:*
  - 10 files, `cheese_qa_0..9.txt`. Files 0-4 are **overwritten** (`:196`), not appended.
  - About 200 rows before deduplication, likely somewhat fewer after `drop_duplicates(subset=["question"])` (`:233`).
  - `train_test_split(test_size=0.1)` gives ceil(0.1·N) test rows, e.g. 20 test and 180 train for N=200.
  - `train.jsonl` has one line per training row.
  - No edit is needed in `gemini-finetuner`, since the GCS object names stay the same after `--upload`. At the README's (stale) rate, tuning cost doubles with the token count.

**E5. Wait for the job (hands-on)**
- Change `gemini-finetuner/cli.py:126` to `train(wait_for_job=True)` and also print `tuning_job.state` and the elapsed minutes inside the loop. Predict what the loop prints and when it ends. Is there a state that would make it loop forever?
- *Worked answer:*
  - It prints `Job in progress... State: JobState.JOB_STATE_RUNNING` (str-enum members print with the class name) every 60 s until the state is one of `JOB_STATE_SUCCEEDED`, `JOB_STATE_FAILED` or `JOB_STATE_CANCELLED` (`:78-82`). The comparison works because `JobState` is a `str` enum (`_common.py:482`). On success, `:90-96` prints the model and endpoint and the "paste into MODEL_ENDPOINT" hint.
  - `JOB_STATE_PAUSED` (`types.py:397`) and `JOB_STATE_EXPIRED` (`:399`) aren't in the set, so the loop would spin forever. More robust: the SDK's `tuning_job.has_ended` property (`types.py:10233-10236`), which also counts `JOB_STATE_EXPIRED` (`:6453-6458`), plus a timeout for the paused case.

**E6. Whose endpoint? (debugging + conceptual)**
- `python cli.py --chat` returns `403 PERMISSION_DENIED`. Your `GCP_PROJECT` is correct and your SA has `roles/aiplatform.user`. What's wrong, and why doesn't `project=GCP_PROJECT` in the client fix it?
- *Worked answer:*
  - `MODEL_ENDPOINT` (`cli.py:107`) is the instructor's resource `projects/129349313346/…`.
  - For model names starting with `projects/`, google-genai uses the path as-is (`_transformers.py:173-177`) and skips prefixing your project (`_api_client.py:1008-1014`). The request goes to the instructor's project, where your SA has no rights.
  - Paste your own endpoint (`projects/<your-number>/locations/us/endpoints/<id>`) from the console.

**E7. Two baselines (conceptual, Colab)**
- In 5.1 (nb cell 80) the "Base" is `trainer.model` inside `disable_adapter()`; in 5.2 (nb cell 82) the "Base Model" is `base_model_comparison`. Are they the same model? Would you expect the 5.1 base perplexity (14.15) to change if computed on the 5.2 base?
- *Worked answer:*
  - No. The 5.1 base is Qwen3-0.6B **4-bit NF4** with LoRA switched off; the 5.2 base is the **FP16, unquantized** model (`quantization_config` commented out at nb cell 82:57).
  - Quantization adds small errors, so the FP16 base would probably score slightly lower (better) perplexity than 14.15 on the same text. The gap to the fine-tuned 4.00 would remain large, because the style shift dominates.
  - For a clean ablation, compare like with like.

**E8. Make the trainer read your bucket (hands-on refactor)**
- Change `gemini-finetuner/cli.py:10-11` so the dataset URIs come from the `GCS_BUCKET_NAME` env var that `docker-shell.sh:20` already passes in. What fails if the env var is missing, and when?
- *Worked answer:*
  - ```python
    GCS_BUCKET_NAME = os.environ["GCS_BUCKET_NAME"]
    TRAIN_DATASET = f"gs://{GCS_BUCKET_NAME}/llm-finetune-dataset-small/train.jsonl"
    VALIDATION_DATASET = f"gs://{GCS_BUCKET_NAME}/llm-finetune-dataset-small/test.jsonl"
    ```
  - Without the env var, `KeyError: 'GCS_BUCKET_NAME'` fires at **import**, even for `--help`, exactly like `GCP_PROJECT` today.
  - This removes the hidden coupling between `env.dev:7` and hard-coded constants. You can't edit both and get them out of sync.

---

## 9. Errata and open questions

**Errata (wrong, outdated, ambiguous or inconsistent)**

1. **The README doesn't tell you to edit the code.**
   - `gemini-finetuner/cli.py:10-11` (dataset URIs in the course's `cheese-dataset` bucket) and `:107` (the instructor's endpoint `projects/129349313346/…`) must be changed. The README only says "Change any of the default parameters if needed" (`README.md:259`).
   - `env.dev:6-7` also needs editing; only its inline comments say so.
2. **Missing setup steps:** the README never says to enable the Vertex AI API or create a bucket (Prerequisites at `README.md:31-69` cover only Docker, the clone and the SA). `upload()` assumes the bucket exists (`dataset-creator/cli.py:280`).
3. **`sh docker-shell.sh` fails on dash systems** (`README.md:87`, `:240` vs `docker-shell.sh:8`/`:7`). It should be `bash docker-shell.sh`, or the scripts should use `.`.
4. **Stale system-prompt excerpt.** `README.md:116-133` shows openers ("Welcome welcome welcome, cheese lovers!…", "Let us do system3") that commit `6e4c3f7` removed from the opener list in `dataset-creator/cli.py:83-101`. The same commit left the prompt's sample JSON (`cli.py:129-142`) unchanged, so the prompt now contradicts itself: the list asks for "Good question"-style openers while the examples open with "Welcome welcome welcome…", "Yello…" and "Welcome welcome to AC215…".
5. **Stale chat example.** `README.md:296` uses "How is cheese made?"; the code asks "How is cheese made in Greece? Answer pavlos style?" (`gemini-finetuner/cli.py:109`).
6. **Stale cost section.**
   - `README.md:269` prices "Gemini 1.5 Flash Tuning" at $0.008/1k tokens, and the table (`:271-274`) assumes 3 epochs.
   - The code tunes `gemini-3.1-flash-lite` (`cli.py:15`) for 1 epoch (`:53`).
   - `README.md:151` ("$2.0 for 1000 iterations") also predates the current generator.
   - The screenshots (`images/*.png`, added 2024-09-29 in `d03f044`) come from a ~16k-example run of the old setup.
7. **"Parameters" are constants, not flags.** `README.md:106` and `:259` say "Change any of the default parameters". There are no CLI options beyond the three/two flags; the values are module constants (`dataset-creator/cli.py:170`, `gemini-finetuner/cli.py:52-58`).
8. **The CLI never waits.** `main()` hard-codes `wait_for_job=False` (`gemini-finetuner/cli.py:126`), so the polling loop and the endpoint hint (`:74-96`) are dead code in the documented flow.
9. **Type mismatch that happens to work.** A `TuningDataset` is passed as `validation_dataset` (`gemini-finetuner/cli.py:49`, `:57`), which is typed `TuningValidationDataset` (`google/genai/types.py:10541`). pydantic's `from_attributes=True` (`_common.py:437`) coerces it. `types.TuningValidationDataset(gcs_uri=...)` would be correct.
10. **Mangled prompt instructions.**
    - `dataset-creator/cli.py:123` asks the model to escape apostrophes "with a backslash (\')". In a non-raw Python string, `\'` becomes `'`, so the model actually reads "(')".
    - The example JSON in the prompt is invalid: its third entry (`:139-140`) has no `{ }`. The closing note then says the sample "includes only two Q&A pairs for brevity" (`:144`), although it has three.
    - Structured output (`:179-180`) makes both moot, but they're confusing to read.
11. **Unused dependencies and variables.**
    - `pyproject.toml:8-16` includes `chromadb`, `langchain`, `langchain-community`, `openai` and `openai-agents`, copied from `llm-rag/pyproject.toml`; nothing imports them.
    - Unused imports: `time`, `Content, Part, GenerationConfig, ToolConfig` and `errors` in `dataset-creator/cli.py:5`, `:13-14`. The import `errors` is then shadowed by a local list at `:213`.
    - Unused: `storage` in `gemini-finetuner/cli.py:4`; `GCS_BUCKET_NAME` is passed to gemini-finetuner but unused; `GCP_SERVICE_ACCOUNT` and `LOCATION` in `env.dev:9-10` are unused by these containers.
    - `pyproject.toml:5` declares `readme = "README.md"`, but neither subfolder has one. That's harmless, because no `[build-system]` means a virtual project.
12. **Misleading entrypoint message.** "Environment ready! Virtual environment activated." prints before `source /.venv/bin/activate` (`docker-entrypoint.sh:6` vs `:12`).
13. **The `data/` folder was removed.** `6e4c3f7` deleted `dataset-creator/data/.gitkeep` while `.gitignore:8-9` (duplicated line) still references the folder. On Linux hosts with uid ≠ 1000 the container may not be able to create it (§6.6).
14. **Irrelevant line.** "Also it is assumed you have your vector database that is running locally." (`README.md:303`) is a leftover from the RAG app context.
15. **`autotrain-runner/` is undocumented and broken** (§6.18). It has a two-line README (`autotrain-runner/README.md:1-2`), and the config's `project_name: autotrain-llama3-8b-sft-unsloth` doesn't match its `base_model: mistralai/Mistral-7B-Instruct-v0.2` (`configs/llm_config_mistral.yaml:2-3`).
16. **Typos.** "go over approaches to fine LLM models" (`README.md:3`), "can been seen", "LLm" (`:112`), "files are consolidate it" (`:187`), "Dropoput" (nb cell 67:3), "fine-tunned"/"Trainig" (nb cell 72:3, :6).
17. **Notebook output/code mismatch.** nb cell 45's stored output begins "what is your name ? …". `tokenizer.decode(outputs[0], …)` includes the prompt, so a fresh run should begin "Hello my cheese name is…". The execution counts around it jump (21 → 24), so the output probably came from an earlier version of the cell.
18. **Notebook inconsistencies.**
    - The tokenizer is loaded without `cache_dir` (nb cell 36:2-4, nb cell 86:14), unlike the models.
    - The 5.1 and 5.2 baselines are different models (§3.8, E7).
    - nb cell 2 says an HF token is "Required", but both models are public; it's needed only for the Step 6.3 upload.
19. **Lecture numbering.** `tutorials_demo.md:112` calls this "Lecture 8", while `_modules/week-05.md:11-13` lists "LLM - Finetuning" on Oct 1 as "Lecture 7". Also, the L10 entry in `tutorials_demo.md:142` is headed "### LLM-Fine Tuning" although it describes Cheese-app-V0, a copy-paste leftover.

**Open questions (could not be determined from the sources)**
- Whether `gemini-3.1-flash-lite` is currently tunable in `us-central1` for a student project, how long a ~90-example, 1-epoch job takes, and its current price per training token. No job was run.
- Whether tuned-Gemini endpoints have any idle cost, and whether students should delete them after L10.
- Whether the course bucket `gs://cheese-dataset` is publicly readable. If it is, a student who skips Step 3 gets no 403 and silently tunes on the instructor's data (§3.4, Step 10).
- Whether `gemini-3.1-flash-lite` spends "thinking" tokens by default and whether they count against `max_output_tokens=8192` (`dataset-creator/cli.py:176`). The code sets no thinking config, and if they do count, truncated batches (§6.10) would be more likely than the README-screenshot arithmetic suggests.
- Whether the multi-region `us` endpoint really needs `base_url="https://aiplatform.us.rep.googleapis.com"`.
  - With google-genai 1.39.1 (this repo's lock), the default would be `https://us-aiplatform.googleapis.com/` (`_api_client.py:654-656`), so for this lock the override is needed.
  - Newer SDKs do it themselves: google-genai 2.30.0 has `_MULTI_REGIONAL_LOCATIONS = {'us', 'eu'}` and builds `https://aiplatform.{location}.rep.googleapis.com/` for them (its `_api_client.py:99`, `:828-834`). That is why L10's `cheese-app-v0` (google-genai 2.28.0, `location="us"`, no override) can call the same kind of endpoint. 2.30.0 and 2.29.0 (the same logic at its `_api_client.py:809-815`) were checked, not 2.28.0 itself.
- Which console URL is current. The README uses `https://console.cloud.google.com/agent-platform/tuning/managed` (`README.md:261`, `:308`); the code comment uses `…/vertex-ai/studio/tuning?project=ac215-project` (`gemini-finetuner/cli.py:106`).
- What the Ed lesson and slides add. The notebook defers NF4 and double quantization details to the "lecture notes" (nb cell 28).
- Provenance of the Drive file `train_16k.jsonl` (`1b5hFsjpCqI3ZXvraIF0w7eW-mRO7Ecao`). Its answers use the *old* openers (nb cell 55 output), and it matches the README's "16,444 documents" row (`README.md:273`), so it was probably produced by an earlier `dataset-creator`. Not confirmed.
- Whether the hosted demo `https://ac215-llm-rag.dlops.io/finetunechat` (`README.md:303`) is still live.
- Exact Docker image size and build time; no image was built.

_Verified against the repos on 2026-10-13 (adversarial check)._

---

## Links

- README sections (pinned commit): [Prerequisites](https://github.com/dlops-io/llm-finetuning/blob/44ef6f0a70315aa0a551b8565ca862679a87c1eb/README.md#prerequisites) ([Setup GCP Service Account](https://github.com/dlops-io/llm-finetuning/blob/44ef6f0a70315aa0a551b8565ca862679a87c1eb/README.md#setup-gcp-service-account)) · [Generate Question Answer Dataset](https://github.com/dlops-io/llm-finetuning/blob/44ef6f0a70315aa0a551b8565ca862679a87c1eb/README.md#generate-question-answer-dataset) ([Run Container](https://github.com/dlops-io/llm-finetuning/blob/44ef6f0a70315aa0a551b8565ca862679a87c1eb/README.md#run-container), [Generate Text](https://github.com/dlops-io/llm-finetuning/blob/44ef6f0a70315aa0a551b8565ca862679a87c1eb/README.md#generate-text), [Sample Question Answers](https://github.com/dlops-io/llm-finetuning/blob/44ef6f0a70315aa0a551b8565ca862679a87c1eb/README.md#sample-question-answers), [Prepare Dataset](https://github.com/dlops-io/llm-finetuning/blob/44ef6f0a70315aa0a551b8565ca862679a87c1eb/README.md#prepare-dataset), [Upload Dataset](https://github.com/dlops-io/llm-finetuning/blob/44ef6f0a70315aa0a551b8565ca862679a87c1eb/README.md#upload-dataset)) · [Fine-tune Gemini](https://github.com/dlops-io/llm-finetuning/blob/44ef6f0a70315aa0a551b8565ca862679a87c1eb/README.md#fine-tune-gemini) ([Run Container](https://github.com/dlops-io/llm-finetuning/blob/44ef6f0a70315aa0a551b8565ca862679a87c1eb/README.md#run-container-1), [Fine-tune Model](https://github.com/dlops-io/llm-finetuning/blob/44ef6f0a70315aa0a551b8565ca862679a87c1eb/README.md#fine-tune-model), [Cost of Fine-tuning](https://github.com/dlops-io/llm-finetuning/blob/44ef6f0a70315aa0a551b8565ca862679a87c1eb/README.md#cost-of-fine-tuning), [Chat with Fine-tuned Model](https://github.com/dlops-io/llm-finetuning/blob/44ef6f0a70315aa0a551b8565ca862679a87c1eb/README.md#chat-with-fine-tuned-model)) · latest README on [`main`](https://github.com/dlops-io/llm-finetuning#llm-fine-tuning) · last year's [`pipenv` branch](https://github.com/dlops-io/llm-finetuning/tree/pipenv)
- Ed lesson: [L08 · LLM: Finetuning](https://edstem.org/us/courses/97373/lessons/166032/) · course [tutorials page](https://harvard-iacs.github.io/2026-AC215/tutorials_demo/)
- Colab: [Tutorial - Finetuning with QLoRA](https://colab.research.google.com/drive/1oX3ADMHphW2v7mwV7zkEWD5oYewJZEAC)
- Hosted demo (optional, Chrome; may not be live): [Pavlos Cheese Model](https://ac215-llm-rag.dlops.io/finetunechat) · Console: [Agent Platform Tuning](https://console.cloud.google.com/agent-platform/tuning/managed)
- Context repos (pinned commits): [`llm-rag` @ `e17a39f`](https://github.com/dlops-io/llm-rag/tree/e17a39f35bc07b440f573def480adaf4703f8b91) · [`cheese-app-v0` @ `cb6fb94`](https://github.com/dlops-io/cheese-app-v0/tree/cb6fb94576aa37bb0b94a8745e5e94e6a504f4bb)
- Previous lecture: [L07 · LLM: Agents II](L07-agents-2-harness.md)
- Next lecture: [L09 · Automating Software Development: CI, unit testing](L09-ci-testing-precommit.md)
- Referenced in §4 and §7: [L02 · Containers I](L02-containers-1.md) · [L05 · Introduction to RAG](L05-rag.md) · [L06 · LLM: Agents I](L06-agents-1.md) · [L10 · Connecting to the Cloud: Networking, Authentication & Storage](L10-cloud-connect-cheese-app-v0.md) (uses your tuned endpoint) · [L13 · Advanced Training Workflows: experiment tracking (W&B), multi-GPU, serverless training (Vertex AI)](L13-training-workflows.md) · [L14 · Serverless Deployment: Cloud Functions, Cloud Run](L14-serverless-deployment.md) · [L15 · ML Workflows with Vertex AI](L15-vertex-ml-workflows.md)
