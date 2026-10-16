# L05 · Introduction to RAG — study guide

[Ed lesson](https://edstem.org/us/courses/97373/lessons/182195/) · Tutorial: [`dlops-io/llm-rag`](https://github.com/dlops-io/llm-rag) `main` @ [`e17a39f`](https://github.com/dlops-io/llm-rag/tree/e17a39f35bc07b440f573def480adaf4703f8b91) (content identical to [`7a3c66b`](https://github.com/dlops-io/llm-rag/tree/7a3c66b777e7d4048b45f59b7223422325f1a281); comparison branch `pipenv` @ [`0b671ed`](https://github.com/dlops-io/llm-rag/tree/0b671ede29d4b37ecd530da493485b015adad4da)) · Colab: none for L05 · Video: planned · Made from the verified digest, 2026-10-13

## 中文速览

- **做什么：** 用 11 本 cheese 书（10 本 Project Gutenberg + Pavlos 写的 Tolminc 短篇故事）搭一个经典的两阶段 RAG。Indexing：chunk → embed（Vertex AI 上的 `gemini-embedding-001`，每个 chunk 一个 256 维 vector）→ load 进 ChromaDB；Query：embed 问题 → top-10 nearest chunks → 拼进 prompt → `gemini-3.1-flash-lite` 回答。每一步都是 `cli.py` 的一个 flag（`--chunk`、`--embed`、`--load`、`--query`、`--chat`），在 CLI container 里跑；ChromaDB 是另一个 container，两个都由 Docker Compose 起。
- **Idea 1 · RAG 不改 model：** retrieval 是你的代码做的，model 只看到 prompt 里贴进去的 chunks，weights 一点没变；删掉 collection，"知识"就没了。改 weights 的是 fine-tuning（L08）。
- **Idea 2 · chunking 是 trade-off：** `char-split` 是 350 字符的窗口、overlap 20、`separator=''`，会在单词中间切（共 8,248 个 chunk）；`recursive-split` 按段落 → 行 → 词切，但悄悄继承了 library 默认的 `chunk_overlap=200`（README 没说），所以切出 14,228 个 chunk（char-split 的 1.7 倍），要 embed 的字符量也是 char-split 的 1.4 倍。
- **Idea 3 · embedding 是方向：** `gemini-embedding-001` 原生 3,072 维，代码用 `output_dimensionality` 只要前 256 维。collection 用 `{"hnsw:space": "cosine"}` 建（Chroma 默认是 L2），返回的是 cosine distance，越小越近。Index 和 query 必须用同一个 model、同一个 dimension，否则要么报 dimension error，要么悄悄返回垃圾。
- **Idea 4 · filter 是 mask，不是 ranking：** `--query` 实际只跑 variant #4：`where={"book": "The Complete Book of Cheese"}` + `$contains "Italian"`，先过滤再排序，所以 10 个结果全是意大利 cheese，没有一个提到 Tolminc。这是在演示 filter，不是你做错了。`--chat` 才是不带 filter 的 top-10。
- **Idea 5 · ops 的形状：** 一次性的 CLI container `llm-rag-cli`（`--rm`）+ 常驻的 `llm-rag-chromadb` server，都在 Compose 建的 `llm-rag-network` 上，CLI 用 container name `llm-rag-chromadb:8000` 访问 DB；published 的 host port 8000 是给你的 browser 和 `curl` 用的。Chroma 的 `/data` bind-mount 到 `docker-volumes/chromadb/`，所以 restart 之后 index 还在；service account key 从 `../secrets` mount 到 `/secrets`，永远不放进 repo。
- **最费时间的两个坑：** ① folder 的名字和位置：clone 出来的 folder 必须叫 `llm-rag`（`docker-compose.yml:12` 写死了 `../llm-rag`），否则 container 一启动就报 `/bin/bash: docker-entrypoint.sh: No such file or directory`；`secrets/` 必须是它的 sibling（`docker-compose.yml:11` 写死了 `../secrets`），key 放错位置要到第一次 `--embed` 才报 `DefaultCredentialsError`，因为 char-split / recursive-split 的 `--chunk` 不调 API。② 403：忘了改 `docker-shell.sh:7` 的 `GCP_PROJECT`（默认是 `ac215-project`），或者没 enable Vertex AI API（README 根本没写这一步），`--embed` 就会报 `PERMISSION_DENIED` / `SERVICE_DISABLED`。（另外：Compose 只在 image 不存在时才 build，`git pull` 改了 dependencies 之后要自己 `docker compose build`。）
- **README 的 errata：** `SYSTEM_INSTRUCTION` 定义了但从来没传给 model（E1），所以 answer 的 grounding 比 README 说的弱；`out.txt` 是用旧版 Tolminc 书跑的 `--agent`（L06），别指望复现；`chromadb/chroma:latest` 没 pin（2026-10-12 是 1.5.9，client 是 1.1.0）；Storage Admin 这个 role 用不到。
- **做完要删：** `exit` 只删掉 CLI container，`llm-rag-chromadb` 还在跑、还占着 port 8000，要在 `llm-rag/` 里 `docker compose down`。Cloud 上没有要删的东西（只有 pay-per-call 的 Vertex AI，整个 tutorial 做两遍也远低于 $2）。可选：删 `outputs/` 和 `docker-volumes/`（Linux 上要 `sudo`）；课程结束后在 IAM 里删掉 JSON key。
- **Lecture slides：** 老师的两份 Lecture 5 slides（deck A "Introduction to RAG" 64 页，deck B "Advanced RAG" 89 页）和这份 guide 各节怎么对应、做 tutorial 需要的 10 个 lecture ideas，以及 slides 和今天的 code/captures 不一样的 9 处，都在下面的 [Lecture slides](#lecture-slides)。最要紧的三处：① slides 按 similarity 排序（越大越近），Chroma 返回的是 cosine distance（= 1 − similarity，越小越近）；② slides 把 metadata filtering 放在 ranking 之后，Chroma 的 `where` / `where_document` 是先过滤再排序，所以 `--query` 的 10 个结果里没有 Tolminc；③ slides 的 semantic chunking 用固定的 0.8 threshold，`semantic_splitter.py` 则是在所有 distance 的 95th percentile 处切。

## At a glance

**What you build.** A question-answering system over 11 cheese books: `cli.py` cuts the books into chunks, embeds each chunk into a 256-number vector with Vertex AI's `gemini-embedding-001`, loads them into a ChromaDB collection, and then answers a question by retrieving the 10 nearest chunks and pasting them under the question in a prompt for `gemini-3.1-flash-lite`. It is your first multi-container Compose app with a stateful service: a throw-away CLI container talks by name to a long-lived Chroma server container whose data lives in a bind-mounted folder on your laptop.

**Time needed** (estimate). Service account and key: about 15 minutes. The first `sh docker-shell.sh` builds the image, which takes a few minutes. Chunking takes seconds and makes no API call; embedding takes roughly 1-3 minutes per chunk type (char-split includes 55 s of deliberate sleeps); load, query and chat take about a minute each. Budget about 1-1.5 hours for the README's core sections, plus 10-20+ minutes of API calls for the optional semantic split and about an hour for the extras and exercises.

**Prerequisites.**
- A GCP project with credits/billing from Tutorial 0 (`ac215-setup/README.md:149-193`), created under an individual account, "not under Harvard Organization" (`ac215-setup/README.md:157`). Have its **Project ID** at hand (not the project name).
- Docker Desktop, or Docker Engine plus the Compose v2 plugin (the script calls `docker compose`), and `git`. No local Python: everything runs in the container. Chrome for the optional web tools.
- Background: service-account JSON keys and `GOOGLE_APPLICATION_CREDENTIALS` (L03); secrets outside the repo mounted at `/secrets`, Compose networks, DNS by container name and published ports (L04).
- Credentials: a service account `llm-service-account` with the Vertex AI User role ("Gemini Enterprise Agent Platform User" in the README) and its JSON key at `../secrets/llm-service-account.json`.
- APIs: the **Vertex AI API** (`aiplatform.googleapis.com`). The README never says to enable it (E6).

**What it costs.** Only per-call Vertex AI charges; nothing keeps running in GCP. Roughly $0.10 to embed char-split, $0.15 for recursive-split, about $0.40 for the optional semantic split (chunking plus embedding), and under a cent per query or chat. The whole tutorial, done twice, should cost well under $2 of credits (assumed prices; check the Vertex AI pricing page, §2). On your laptop, `llm-rag-chromadb` keeps running after you exit until you stop it, and `outputs/` grows to about 80 MB once both embedding sets are written (estimate, §4 Step 6).

**Tear down, exactly** (§2, §4 Step 14):
1. `exit` the container shell. The CLI container is removed (`--rm`), but `llm-rag-chromadb` keeps running.
2. On the host, in `llm-rag/`: `docker compose down`. It stops and removes the Chroma container and `llm-rag-network`; your index survives in `docker-volumes/chromadb/`.
3. Optional: delete `outputs/` and `docker-volumes/` to reclaim disk (both git-ignored). On Linux, `docker-volumes/` is owned by root: `sudo rm -rf docker-volumes`.
4. When the course ends: delete the JSON key under **IAM & Admin → Service accounts → KEYS**.
5. Nothing to delete in the cloud: no VM, bucket or endpoint is created.

<details>
<summary><b>Versions and sources this guide was checked against</b></summary>

- **README sections this lecture covers** (GitHub anchors on `main`; line numbers in `README.md`):
  - Intro and [What you'll build](https://github.com/dlops-io/llm-rag#what-youll-build) `README.md:1-23`
  - [Prerequisites](https://github.com/dlops-io/llm-rag#prerequisites) `README.md:45-48`, [Setup GCP Service Account](https://github.com/dlops-io/llm-rag#setup-gcp-service-account) `:52-69`
  - [Run LLM RAG Container](https://github.com/dlops-io/llm-rag#run-llm-rag-container) `README.md:75-85`
  - [Chunk Documents](https://github.com/dlops-io/llm-rag#chunk-documents) `README.md:91-116`
  - [Generate Embeddings](https://github.com/dlops-io/llm-rag#generate-embeddings) `README.md:122-138`
  - [Load Embeddings into Vector Database](https://github.com/dlops-io/llm-rag#load-embeddings-into-vector-database) `README.md:144-165`
  - [Query the Vector Database](https://github.com/dlops-io/llm-rag#query-the-vector-database) `README.md:171-186`
  - [Chat with LLM](https://github.com/dlops-io/llm-rag#chat-with-llm) `README.md:192-214`
  - [Advanced RAG: Semantic Chunking](https://github.com/dlops-io/llm-rag#advanced-rag-semantic-chunking-semantic-splitting) `README.md:220-236` (optional, advanced)
  - **Not covered here:** [Agents](https://github.com/dlops-io/llm-rag#agents) `README.md:242-271` (`--agent`, `agent_tools.py`) belongs to **L06** (`2026-AC215/tutorials_demo.md:83-89` links it as "LLM-Agents"). It is only previewed in §4 Step 13 and §7.
- **Primary repo:** `dlops-io/llm-rag`, branch **`main`** (default), commit `e17a39f35bc07b440f573def480adaf4703f8b91`, committed 2026-10-07 21:34:23 -0400 ("Merge pull request #2 from obalatel/revert-1-demo-podcast").
  - That merge reverts a "Demo podcast" PR, which had moved everything into `llmrag/` and added `api-service/` and `frontend-react/`. **`git diff 7a3c66b HEAD` is empty**, so the tutorial content is exactly commit `7a3c66b777e7d4048b45f59b7223422325f1a281` (2026-10-06 17:06:49 -0400, "updated for localhost"). That commit's only change was a second CORS origin in `docker-compose.yml:26`.
  - Commits that shape this year's version: `59a0f80` + `4a5f347` (2025-10-01, Pipenv → uv and `vertexai` SDK → `google-genai`); `51a2865` (2026-09-16, `GCP_LOCATION = "global"`, `GENERATIVE_MODEL = "gemini-3.1-flash-lite"`); `9a27441` + `500a99c` (2026-09-16, Compose now creates the network and builds the image: `9a27441` "Wed midnight" made the change, commented out the script's `docker network create`/`docker build` and moved Chroma's mount from `/chroma/chroma` to `/data`; `500a99c` only deleted the commented-out lines and rewrote the README); `74dba4a` (2026-09-17, `text-embedding-004` → `gemini-embedding-001`); `96d5fd7` (2026-09-20, chat query changed to the Tolminc question); `85bba32` (2026-09-22, Tolminc book rewritten and `out.txt` added).
- **Other branches, read for comparison only:** `pipenv` @ `0b671ede29d4b37ecd530da493485b015adad4da` (2025-03-04, last year's Pipenv version, used in §7); `demo-podcast` @ `96fef434536f6e58a5bd027f49916fc98cd467e1` (2026-10-07, API + React front end, material for a later lecture); `revert-1-demo-podcast` @ `b77a556560befb87e241d39965d68f2e77a6d2ad` (the revert PR's branch).
- **Context repos read for §7:** `dlops-io/cheese-app-v0` @ `cb6fb94` (L10; it ships a near-verbatim copy of this repo in `cheese-app-v0/llm-rag/`, see §7), `dlops-io/llm-agent-google-adk` @ `f89faa79de744f6a046e30dff24b3b6f1d73720b` (L06), `dlops-io/ac215-setup` @ `61a7b9d` (Tutorial 0).
- **Path convention:** paths without a prefix (`cli.py:23`, `README.md:84`) are inside `llm-rag/`. Course-site paths start with `2026-AC215/`, other repos with their repo name.
- **Method.** Nothing from the repo was built or run, and no GCP access was used. The facts and `path:line` references were verified against the repos on 2026-10-13 (adversarial check).
  - **Chunk counts** come from a separate script that calls the same `langchain-text-splitters 0.3.11` classes with the same arguments as `cli.py:184-205`, on the repo's book files, in a scratch venv.
  - **Library behaviour** comes from reading the source of `google-genai 1.39.1` and `chromadb 1.1.0`, the versions pinned in `uv.lock`.
  - **Docker Hub tags** for `chromadb/chroma` were looked up on 2026-10-12.
  - **"You should see" lines** are inferred from the `print` calls in the code, plus the one captured run in `out.txt`.
- **Ed lesson:** not accessible when these sources were checked; the course-site map `2026-AC215/tutorials_demo.md:71-79` was used instead. The weekly schedule lists "LLM - RAGs" on **Sep 15** but labels it "Lecture 4" (`2026-AC215/_modules/week-03.md:5-7`).
- **Colab notebooks:** none. The `colab/` folder has nothing for L05; the L06 notebooks are only cited in §7.

</details>

## Lecture slides

The instructor's slides for this lecture come in two decks:
- *Lecture 5: Introduction to RAG* (deck A, `L05_RAGs_I_fix`, 64 slides). It walks the naïve-RAG pipeline that this tutorial builds, one box at a time.
- *Lecture 5 suppl: Advanced RAG* (deck B, `Lec05b_RAG_II_added_j_suffix_in_RRF`, 89 slides). Its semantic-chunking walk-through matches §3.7. Query rewriting, hybrid search, re-ranking and Self-RAG have no code in this tutorial.

Slide numbers are PDF page numbers, written A12 or B46; the printed footers differ. Neither deck shows commands, Docker, ChromaDB or Gemini.

The slides are not reproduced here; what follows is in our own words. The full slide digest and the cross-check with the video are in the Explainer_Videos repo, in `videos/ac215-l05-rag/SLIDES.md`. This answers the slides part of §9 Q1.

**Map**

| This guide | Slides |
|---|---|
| At a glance; §1 What you build | A6–A16 (why RAG, the three options, what RAG is, the naïve-RAG pipeline); B5–B6 (its three phases) |
| §2 Prerequisites and costs | none. B61 explains the cost shape: the heavy embedding work happens once, up front, and each question costs one embedding. |
| §3.1 RAG = retrieval + generation | A6–A14, A61–A62; B68–B72 (what RAG doesn't guarantee; looking things up only when needed) |
| §3.2 Chunking; §4 Steps 4–5 | A19–A22, B13–B19 |
| §3.3 Embeddings and cosine similarity; §4 Step 6 | A24–A28, A40–A47; B59–B60 (one encoder for documents and queries) |
| §3.4 The vector database; §4 Step 7 | A30–A38 |
| §3.5 Retrieval: top-k and filters; §4 Steps 9, 11 | A39, A44, A48–A55 |
| §3.6 Augmented generation; §4 Step 10; §9 E1 | A57–A62; B78 (checking that the answer is supported) |
| §3.7 Semantic chunking; §4 Step 12 | B19–B34 |
| Command checklist; §3.8 The ops shape; §4 Steps 0–3, 8, 14; §5 Code tour; §6 Gotchas | none (tutorial-only) |
| §4 Step 13 (Agents preview); §7 Where this sits | A9 (fine-tuning comes later: L08); B35–B65 (query rewriting, hybrid search, re-ranking); B66–B88 (Self-RAG) |
| §8 Exercises | Ex 4 ↔ A58–A59; Ex 5 ↔ A44–A47; Ex 6 ↔ B60 |

**Lecture ideas you need for this tutorial**
1. **Why RAG.** LLMs have stale training data, lack domain knowledge, hallucinate and don't cite sources; RAG targets the first two. Pasting every document into the prompt gives garbage, and fine-tuning takes too long (A6–A10).
2. **Naïve RAG is two lanes.** Knowledge base → chunking → embedding model → vector database. Question → the same embedding model → the database → prompt → LLM. The three phases are Indexing, Retrieval, and Augmentation & Generation (A16, B5).
3. **One encoder, two moments.** The same embedding model embeds the documents ahead of time and the question when it arrives. That makes retrieval fast, and it's why the query and the chunks must use the same model and size (B59–B61).
4. **Chunk so retrieval can focus.** Fixed-size character splitting is the default; it cuts words in half and runs sections together. Chunks that follow the document's structure are better (A20–A21, B14–B19).
5. **Embeddings and similarity measures.** A whole chunk becomes one vector (a sentence embedding, not word embeddings). Cosine similarity compares directions; Euclidean distance and the dot product also count length. Cosine suits text embeddings (A25–A28, A42–A47).
6. **Why a vector database, and why an index.** SQL can't search by meaning, and comparing the query with millions of vectors one by one is too slow. An index (LSH, PQ or HNSW; Chroma builds HNSW) jumps to likely neighbours. The database returns the top K, with K fixed in advance (A31–A39, A48–A53).
7. **Optional post-processing.** Metadata filtering and re-ranking are optional. Metadata is data about the data, such as author, publication date and category (A54–A55).
8. **The final prompt** is a system prompt (how to behave), plus the user's query, plus the retrieved context (A57–A59).
9. **Semantic chunking.** Split the text into sentences, take each one with a window of neighbours, compare them by the cosine similarity of their embeddings, and join the similar ones (B19–B33).
10. **Limits and next steps** (no code here). Even advanced RAG doesn't guarantee relevant chunks or a supported answer, and it retrieves even when it needn't (B68). The lecture's levers: query rewriting, hybrid search (BM25 plus vectors, merged with Reciprocal Rank Fusion), re-ranking with a cross-encoder, and Self-RAG (B35–B88).

**Where the slides and today's tutorial differ** (the code and the 2026-10-16 captures decide)
- **Scores vs distances.** The slides rank by similarity: higher is closer (A48–A53). Chroma returns cosine distance, 1 − similarity: lower is closer, and a chunk's own vector comes back at 0.0000 (§3.3).
- **When filters apply.** The slides put metadata filtering after ranking (A54–A55). Chroma applies `where` and `where_document` first and picks the top 10 among the survivors. That's why `--query` returns Italian cheeses and no Tolminc (§3.5).
- **The system prompt.** The slides' final prompt starts with a system prompt (A58–A59). `cli.py` defines a cheese-expert `SYSTEM_INSTRUCTION` but never sends it (§9 E1).
- **The semantic-chunking rule.**
  - The slides move an anchor sentence along and join neighbours whose similarity clears a fixed 0.8 (B21–B33).
  - The code compares every pair of neighbouring three-sentence windows and cuts where the distance is above the 95th percentile.
  - The code also calls the embedding API already during `--chunk` (§3.7).
- **Overlap.** The slides' character-split pieces sit end to end, with no overlap (B14–B18). `char-split` repeats 20 characters at each cut. `recursive-split` repeats up to 200, a library default the README doesn't state (§3.2, §9 E14).
- **"Indexing".** It means the search structure on A32–A38, the whole offline phase on B5–B10, and better chunking on B13–B34. The README just says "Chunk -> Embed -> Load" (§1).
- **Who embeds the question.** On A12 the question itself goes to the vector database. In the code, Google embeds the question first, and Chroma receives only the vector. Passing text instead would make Chroma use its own, different embedding model (§3.4, §8 Ex 6).
- **How much RAG guarantees.** The slides claim only fresher and domain-specific knowledge (A7), and warn that answers may still be unsupported (B68). The README promises answers "grounded in your documents" (`README.md:21`). But the code sends no instruction to stay inside them, and it leaves the book names out of the prompt (§3.6).
- **Keyword search.** The slides' hybrid search ranks by keywords (BM25) and fuses the rankings (B42–B48). The tutorial's `where_document={"$contains": …}` only filters by a word, before the vector ranking (§3.5).

## Command checklist

Commands in backticks are exactly as the README writes them (placeholders kept). Plain items are console clicks or edits. Items marked *(extra)* are not in the README; they come from §4 and §6 of this guide. Every `python cli.py …` command runs **inside** the CLI container that `sh docker-shell.sh` opens (prompt in `/app`); items marked "host" run in a second terminal on your laptop.

### Prerequisites

*(`README.md:45-48`; §4 Step 0)*
- [ ] Have Docker installed: Docker Desktop, or Docker Engine plus the Compose v2 plugin (the script calls `docker compose`, with a space).
- [ ] Clone this repository to your local machine: <https://github.com/dlops-io/llm-rag>.
- [ ] `cd ~/Desktop/AC215` — *(extra)* or wherever you keep course repos; this parent folder will hold both `llm-rag/` and `secrets/`.
- [ ] `git clone https://github.com/dlops-io/llm-rag.git` — *(extra)* the folder must be named exactly `llm-rag` (`docker-compose.yml:12` mounts `../llm-rag`); rename a ZIP download's `llm-rag-main` (G1).
- [ ] `mkdir -p secrets` — *(extra)* creates `secrets/` as a **sibling** of `llm-rag/`, never inside it (G20).
- [ ] `ls` — *(extra)* in the parent folder: `llm-rag  secrets`.

### Setup GCP Service Account

*(`README.md:52-69`; §4 Step 1)*
- [ ] *(extra)* Enable the **Vertex AI API** in your project (APIs & Services). The README never says to (E6); without it the first embed fails with `SERVICE_DISABLED` (G4).
- [ ] `gcloud services enable aiplatform.googleapis.com --project=<YOUR_PROJECT_ID>` — *(extra)* the CLI equivalent of the click above.
- [ ] Go to the [GCP Console](https://console.cloud.google.com/home/dashboard), search for **"Service accounts"** in the top search box, or open **IAM & Admin → Service accounts** from the top-left menu.
- [ ] Create a new service account called `llm-service-account`.
- [ ] In **"Grant this service account access to project"** select **Storage Admin** and **Gemini Enterprise Agent Platform User** (listed as "Vertex AI User" in older projects). Only the Vertex role is used by the code; Storage Admin is unused (E5).
- [ ] Click the service account and open the **KEYS** tab.
- [ ] Click **ADD Key (Create New Key)** and select **JSON**; a private key JSON file downloads to your computer. If key creation is blocked by an org policy, you are probably in an organisation-managed project: use your personal one.
- [ ] Copy the JSON file into the **secrets** folder and rename it to `llm-service-account.json`.
- [ ] `ls ../secrets` — *(extra)* from inside `llm-rag/`: prints `llm-service-account.json`.
- [ ] `grep project_id ../secrets/llm-service-account.json` — *(extra)* shows the project the key belongs to; the next section must use the same ID.

### Run LLM RAG Container

*(`README.md:75-85`; §4 Steps 2-3)*
- [ ] Make sure you are inside the `llm-rag` folder and open a terminal at this location.
- [ ] Update `GCP_PROJECT` to your own project ID in `docker-shell.sh`: line 7, `export GCP_PROJECT="ac215-project" # CHANGE TO YOUR PROJECT ID`. Leave line 8 (`/secrets/llm-service-account.json`, an in-container path) alone. Skipping this gives a 403 `PERMISSION_DENIED` later (G3).
- [ ] `sh docker-shell.sh` — runs `docker compose run --rm llm-rag-cli`: creates `llm-rag-network`, builds `llm-rag-cli` on the first run only (a few minutes), starts `llm-rag-chromadb` on port 8000, then prints the `Container is running!!!` banner and a bash prompt in `/app` as user `app`.
- [ ] `docker ps` — *(extra, host)* lists `llm-rag-chromadb` with `0.0.0.0:8000->8000/tcp` and a CLI container.
- [ ] `curl http://localhost:8000/api/v2/heartbeat` — *(extra, host)* returns `{"nanosecond heartbeat": …}`.

### Chunk Documents

*(`README.md:91-116`; §4 Steps 4-5)*
- [ ] *(optional)* Open the chunking [visualization](https://ac215-llm-rag.dlops.io/chunkviz) in Chrome.
- [ ] `python cli.py --chunk --chunk_type char-split` — 350-character windows with a 20-character overlap, cut mid-word; writes `outputs/chunks-char-split-<book>.jsonl`; 8,248 chunks in total (Tolminc: 24). No API call.
- [ ] `python cli.py --chunk --chunk_type recursive-split` — cuts at paragraph, line, then word boundaries with the library's default 200-character overlap; 14,228 chunks in total (Tolminc: 35).
- [ ] `wc -l outputs/chunks-char-split-*.jsonl` — *(extra, host)* one line per chunk, so the counts match the CLI's `Number of chunks:` lines.

### Generate Embeddings

*(`README.md:122-138`; §4 Step 6)*
- [ ] `python cli.py --embed --chunk_type char-split` — sends the chunks to `gemini-embedding-001` in batches of 100 (~89 calls, plus a 5 s sleep per book) and writes `outputs/embeddings-char-split-<book>.jsonl` with a 256-float `embedding` column. The first command that needs the key.
- [ ] `python cli.py --embed --chunk_type recursive-split` — the same for the recursive chunks (~148 calls).

### Load Embeddings into Vector Database

*(`README.md:144-165`; §4 Steps 7-8)*
- [ ] `python cli.py --load --chunk_type char-split` — connects to `llm-rag-chromadb:8000`, deletes and recreates `char-split-collection` (cosine space) and inserts the records in batches of 500; `chroma.sqlite3` appears in `docker-volumes/chromadb/` on the host.
- [ ] `python cli.py --load --chunk_type recursive-split` — the same into `recursive-split-collection`.
- [ ] *(optional)* View your local vector database with the [Chroma UI Tool](https://ac215-llm-rag.dlops.io/chromaui) in Chrome.
- [ ] `exit`, then `sh docker-shell.sh` — *(extra)* restart test: skip straight to the query; it works without reloading, because the index persists on disk (Step 8).

### Query the Vector Database

*(`README.md:171-186`; §4 Steps 9 and 11)*
- [ ] `python cli.py --query --chunk_type char-split` — embeds "How is tolminc cheese made?" and runs only filter variant #4: the top 10 from *The Complete Book of Cheese* whose text contains "Italian". None of the results mentions Tolminc.
- [ ] `python cli.py --query --chunk_type recursive-split` — the same query against `recursive-split-collection`.
- [ ] *(extra)* On your laptop, uncomment variant #1 in `cli.py:325-331` and comment out #4, then rerun `--query` (no rebuild needed: the repo is bind-mounted).
- [ ] `python cli.py --get --chunk_type char-split` — *(extra)* undocumented flag: a plain metadata lookup (10 records from Bob Brown's book, no `distances`, no ranking) (Step 11).

### Chat with LLM

*(`README.md:192-214`; §4 Step 10)*
- [ ] `python cli.py --chat --chunk_type char-split` — embeds "How is tolminc cheese made??", takes the top 10 with no filter, pastes them under the question and prints `LLM Response:` from `gemini-3.1-flash-lite`.
- [ ] `python cli.py --chat --chunk_type recursive-split` — the same with recursive chunks; compare the two answers.
- [ ] *(optional)* Try the [Chat Tool](https://ac215-llm-rag.dlops.io/chat) in Chrome.

### Advanced RAG: Semantic Chunking (Semantic Splitting)

*(`README.md:220-236`, optional; §4 Step 12)*
- [ ] `python cli.py --chunk --embed --load --chunk_type semantic-split` — chunk, embed and load in one run; the chunking itself makes ~528 embedding calls, so budget 10-20+ minutes and expect 429 retries. To test cheaply, temporarily move all but one book out of `input-datasets/books/`.
- [ ] `python cli.py --chat --chunk_type semantic-split` — *(extra)* compare the answer with the two `--chat` runs above.

### Agents (preview only; covered in L06)

*(`README.md:242-271`; §4 Step 13)*
- [ ] `python cli.py --agent --chunk_type char-split` — Gemini function calling picks a retrieval tool (by author, or across all books), then answers. Details in L06.
- [ ] *(optional)* Try the [Cheese Agent Tool](https://ac215-llm-rag.dlops.io/agent) in Chrome.

### After the README *(extra)*

*Leave and clean up (§4 Step 14)*
- [ ] `exit` — *(extra)* leaves the CLI container, which is deleted (`--rm`); Chroma keeps running.
- [ ] `docker compose down` — *(extra, host, in `llm-rag/`)* stops `llm-rag-chromadb` and removes `llm-rag-network`; `docker-volumes/chromadb/` stays, so next time you can query straight away.
- [ ] `docker ps` — *(extra, host)* no `llm-rag-*` containers left.
- [ ] `sudo rm -rf docker-volumes` — *(extra, host, Linux, optional)* removes the root-owned Chroma data; delete `outputs/` too if you want the disk back (G14).
- [ ] *(extra)* When the course ends, delete the key under **IAM & Admin → Service accounts → KEYS**.

*Only when needed (§6)*
- [ ] `docker compose build` — *(extra, host)* after a `git pull` that changed `pyproject.toml`, `uv.lock` or the `Dockerfile`: Compose only builds when the image is missing (G9). One-step alternative: `docker compose run --build --rm llm-rag-cli`.
- [ ] `ls /secrets` — *(extra, in the container)* check that the key is mounted when the first embed fails with `DefaultCredentialsError` (G2).
- [ ] `docker stop <name>` — *(extra, host)* frees host port 8000 when `docker ps` shows another container holding it (G6).
- [ ] `docker rm -f llm-rag-chromadb` — *(extra, host)* clears a `container name "/llm-rag-chromadb" is already in use` conflict (G7).
- [ ] `mkdir outputs && chmod a+w outputs` — *(extra, host, Linux)* fixes `PermissionError … 'outputs'` when your host uid is not 1000 (G14).
- [ ] `git config --global core.autocrlf input` — *(extra, Windows)* then re-clone, so the `.sh` files keep LF endings (G22).

---

## 1. What you build

You build a **question-answering system over 11 cheese books** (10 Project Gutenberg texts plus Pavlos's short Tolminc story), the classic two-phase RAG pipeline (`README.md:5-21`). In the **indexing phase**, `cli.py` does three things:
1. **Chunk:** cut every book into ~350-character chunks with LangChain splitters.
2. **Embed:** send the chunks in batches to Google's `gemini-embedding-001` model on Vertex AI, which returns one **256-number vector** per chunk.
3. **Load:** store chunk text, vector and metadata (`book`, `author`, `year`) in a **ChromaDB** collection.

In the **query phase**, the same CLI embeds a question ("How is tolminc cheese made?"), asks Chroma for the 10 nearest chunks, pastes them under the question in a prompt, and sends that to `gemini-3.1-flash-lite`. The answer is grounded in the books instead of only the model's memory.

On the ops side this is your **first multi-container Compose app with a stateful service**:
- a throw-away **CLI container** (`llm-rag-cli`, built from this repo's Dockerfile, removed when you exit), and
- a long-lived **vector-database server container** (`llm-rag-chromadb`, the stock `chromadb/chroma` image).

The two containers share a Docker network, so the CLI reaches the DB **by container name** on port 8000. The DB writes to a **bind-mounted host folder**, so your index survives restarts. The only cloud pieces are two **pay-per-call Vertex AI model endpoints**, reached with a **service-account key** that is mounted from a `secrets/` folder outside the repo. Nothing on GCP keeps running (and billing) after you stop.

```
 YOUR LAPTOP  (Docker Desktop on macOS/Windows, or Docker Engine on Linux; Apple Silicon runs everything natively as arm64)
 +------------------------------------------------------------------------------------------------------------+
 |  AC215/                                    (any parent folder; the two children MUST be siblings)          |
 |  |-- llm-rag/   <- git clone; run `sh docker-shell.sh` from here                                           |
 |  |   |-- cli.py  semantic_splitter.py  agent_tools.py                                                      |
 |  |   |-- input-datasets/books/*.txt      11 books, ~2.7 M characters                                       |
 |  |   |-- outputs/                        (created) chunks-*.jsonl, embeddings-*.jsonl                      |
 |  |   `-- docker-volumes/chromadb/        (created) chroma.sqlite3 + HNSW index folders                     |
 |  `-- secrets/llm-service-account.json    (you create; never inside the repo)                               |
 |                                                                                                            |
 |   docker network "llm-rag-network"  (created by Compose, docker-compose.yml:1-3)                           |
 |   +------------------------------------------+            +------------------------------------------+     |
 |   | container llm-rag-cli   (run --rm)       |  HTTP      | container llm-rag-chromadb  (stays up!)  |     |
 |   | image llm-rag-cli  <- Dockerfile         |----------->| image chromadb/chroma:latest             |     |
 |   | python 3.12, deps in /.venv (uv sync)    | llm-rag-   | Chroma server listening on :8000         |     |
 |   | /app     <- bind ../llm-rag              | chromadb   | /data <- bind ./docker-volumes/chromadb  |     |
 |   | /secrets <- bind ../secrets              | :8000      | env CHROMA_CORS_ALLOW_ORIGINS            |     |
 |   | env GCP_PROJECT,                         |            +--------------------^---------------------+     |
 |   |     GOOGLE_APPLICATION_CREDENTIALS       |                published 8000:8000 (host port 8000)         |
 |   | you type:  python cli.py --<step> ...    |                                    |                        |
 |   +---------------------|--------------------+          localhost:8000  <--  Chrome tab on                 |
 |                         |                                                 https://ac215-llm-rag.dlops.io   |
 |                         |                                                 (/chromaui; CORS-allowed)        |
 +-------------------------|----------------------------------------------------------------------------------+
                           |  HTTPS + OAuth2 access token minted from the service-account key
                           v
 GOOGLE CLOUD  (your project = $GCP_PROJECT)   https://aiplatform.googleapis.com   location "global"  (cli.py:24)
    +-- publishers/google/models/gemini-embedding-001   ":predict"          text(s)  -> 256-float vector(s)
    +-- publishers/google/models/gemini-3.1-flash-lite  "generateContent"   prompt   -> answer text
    (pay per call; no VM, bucket or endpoint is created, so nothing to delete in the cloud)


 DATA FLOW
  Indexing (run once per chunk_type; slow, costs a little)
   books/*.txt --chunk--> outputs/chunks-*.jsonl --embed (Vertex, batches of 100)--> outputs/embeddings-*.jsonl
               --load--> Chroma collection "<chunk_type>-collection"  (cosine space)  --> docker-volumes/chromadb/
  Querying (every question; fast, costs ~nothing)
   question --embed (Vertex)--> 256-d vector --Chroma.query(n_results=10, optional filters)--> 10 chunks
            --> prompt = question + chunks --Gemini--> answer
```

---

## 2. Prerequisites and costs

**Accounts and local installs**
- A **GCP account and project with credits/billing**, set up in Tutorial 0 (`ac215-setup/README.md:149-193`).
  - Use an individual account, "not under Harvard Organization" (`ac215-setup/README.md:157`). Org policies there can block service-account key creation.
  - Note your **Project ID**, which differs from the project *name* (`ac215-setup/README.md:188-191`).
- **Docker Desktop** (or Docker Engine plus the Compose v2 plugin), because the script calls `docker compose` with a space (`docker-shell.sh:12`). The README only says "Have Docker installed" (`README.md:47`).
- **git**, to clone `https://github.com/dlops-io/llm-rag` (`README.md:48`).
- **No local Python is needed.** Everything runs in the container (Python 3.12, `Dockerfile:2`; `requires-python = ">=3.12"`, `pyproject.toml:6`).
- **Chrome** for the optional web visualisers (`README.md:95-98`, `:162-165`, `:211-214`).

**GCP APIs to enable**
- **Vertex AI API** (`aiplatform.googleapis.com`), in the console or with `gcloud services enable aiplatform.googleapis.com --project=<YOUR_PROJECT_ID>` (not in the README). **The README never says to enable it** (Errata E6).
- No other API is used. There is no Cloud Storage call anywhere in the code (`grep -n storage *.py` finds nothing).

**Service account, key and env vars: exactly where the code looks**

| What | Value | Set in / consumed by |
|---|---|---|
| SA name | `llm-service-account` | `README.md:55` |
| Roles | "Storage Admin" + "Gemini Enterprise Agent Platform User (listed as 'Vertex AI User' in older projects)" | `README.md:56-58`. Only the Vertex role is needed; Storage Admin is unused (E5) |
| Key file on host | `../secrets/llm-service-account.json`, a **sibling** of the `llm-rag/` folder | `README.md:62-69`, mount `../secrets:/secrets` at `docker-compose.yml:11` |
| Key path in container | `/secrets/llm-service-account.json` | `export GOOGLE_APPLICATION_CREDENTIALS=...` at `docker-shell.sh:8` → passed through at `docker-compose.yml:14` → read by `google.auth` on the first API call |
| Project ID | `export GCP_PROJECT="ac215-project" # CHANGE TO YOUR PROJECT ID` | `docker-shell.sh:7` → `docker-compose.yml:15` → `GCP_PROJECT = os.environ["GCP_PROJECT"]` at `cli.py:23` |
| Region | `GCP_LOCATION = "global"` (hard-coded) | `cli.py:24`. With `global`, google-genai calls `https://aiplatform.googleapis.com/` (no region prefix) |
| Chroma address | `CHROMADB_HOST = "llm-rag-chromadb"`, `CHROMADB_PORT = 8000` (hard-coded) | `cli.py:30-31`; this is the container name at `docker-compose.yml:20` |

`genai.Client(vertexai=True, project=GCP_PROJECT, location=GCP_LOCATION)` runs at **import time** (`cli.py:35-36`). Because `project` is given, google-genai 1.39.1 does **not** load credentials yet; it loads them lazily on the first request. So `--chunk` with `char-split`/`recursive-split` works even without a key file. But if `GCP_PROJECT` is missing (only possible outside Compose), it fails immediately with `KeyError: 'GCP_PROJECT'`. If it is *empty*, the client calls Application Default Credentials (`google.auth.default()`) at import (`_api_client.py:631-638` in the wheel). With a valid key file that would quietly take the key's own `project_id`; when you bypass the script, `GOOGLE_APPLICATION_CREDENTIALS` is empty too and the import fails (§6 G5).

**Billable resources and rough cost.** All charges are per call to Vertex AI. Nothing is left running in GCP.

| Run | API calls (from the code's batch sizes) | Input volume (measured) | Rough cost* |
|---|---|---|---|
| `--embed --chunk_type char-split` | 89 `embed_content` calls (8,248 chunks, batch 100, `cli.py:252-253`) | 2.88 M chars ≈ 0.7 M tokens | ~$0.10 |
| `--embed --chunk_type recursive-split` | 148 calls (14,228 chunks; the default 200-char overlap inflates the volume) | 4.10 M chars ≈ 1.0 M tokens | ~$0.15 |
| `--chunk --chunk_type semantic-split` | ~528 calls (26,080 "sentences", batch 50, `semantic_splitter.py:206`) | ~8.0 M chars of 3-sentence windows ≈ 2 M tokens | ~$0.30 |
| `--embed --chunk_type semantic-split` | ~90 calls (≈1,300 chunks, batch 15, `cli.py:249-250`; estimate) | ≈ 0.8 M tokens | ~$0.12 |
| `--query` / one `--chat` | 1 embed call (+1 generate call for chat with ~10 × 350 chars of context) | ~1 k tokens | < $0.01 |

\*Assumes about 4 characters per token and a list price of roughly $0.15 per 1 M input tokens for `gemini-embedding-001`. **Check the current Vertex AI pricing page**; prices were not verified for this guide. The whole tutorial, done twice, should cost well under $2 of credits.

**Shutting down afterwards**
1. `exit` the container shell. The CLI container is removed (`--rm`, `docker-shell.sh:12`), but **`llm-rag-chromadb` keeps running** because Compose started it as a dependency.
2. From `llm-rag/`, run `docker compose down`. This stops and removes the Chroma container and `llm-rag-network`. Your index survives in `docker-volumes/chromadb/`.
3. Optional: delete `outputs/` and `docker-volumes/` to reclaim disk. Both are git-ignored (`.gitignore:3-4`). On Linux, `docker-volumes/` needs `sudo`: the `chromadb/chroma` image sets no `USER` (per the 1.5.9 image config in the registry), so its files are owned by root. `outputs/` is owned by uid 1000, the container's `app` user.
4. Key hygiene: the JSON key is a long-lived credential. Keep it only in `secrets/`. When the course ends, delete the key under **IAM & Admin → Service accounts → KEYS**.

---

## 3. Concepts this tutorial teaches

### 3.1 RAG = retrieval + generation (an open-book exam)
- **Explanation.** An LLM only "knows" what was in its training data, frozen at a cutoff. It has never seen your private or niche documents, like Pavlos's Tolminc story. RAG does **not** change the model. At question time you **retrieve** the few passages most relevant to the question from your own corpus, then **generate** an answer with those passages pasted into the prompt. The README's two figures are exactly these two phases (`README.md:5-11`).
- **Mental model.** Two pipelines that meet at the database.
  - *Indexing* (offline, batch, slow, done once): chunk → embed → store.
  - *Querying* (online, per question, fast): embed question → nearest neighbours → prompt → LLM.
- **Analogy.** A closed-book exam versus an open-book exam where a librarian hands you the 10 most relevant pages first. The student (LLM) is the same; the pages make the difference.
- **Misconception.** "RAG trains or fine-tunes the model on my documents." No weights change. If you delete the collection, the "knowledge" is gone. Fine-tuning is L08.

### 3.2 Chunking: character, recursive, overlap
- **Explanation.** You cannot embed a 675,515-character book as one vector and expect a precise match to a narrow question, and you cannot paste all 11 books into the prompt. So you cut each book into chunks. Each chunk is the unit of retrieval and the unit pasted into the prompt.
  - **`char-split`** (`cli.py:184-194`): `CharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap, separator='', strip_whitespace=False)` with `chunk_size = 350` and `chunk_overlap = 20`. With an empty separator the text is split into single characters and greedily re-packed into 350-char windows that step forward 330 characters. The cuts land **mid-word**. Measured on the Tolminc book, chunk 0 ends `'…list of things she intended to ac'` and chunk 1 starts `'s she intended to accomplish during her '`; those 20 characters are the overlap.
  - **`recursive-split`** (`cli.py:196-205`): `RecursiveCharacterTextSplitter(chunk_size=chunk_size)` with `chunk_size = 350`. It tries separators in order `["\n\n", "\n", " ", ""]`, so it cuts at paragraph, then line, then word boundaries. It also inherits the library default **`chunk_overlap=200`** (`langchain_text_splitters/base.py`, `TextSplitter.__init__`), so neighbouring chunks share up to 200 characters. Chunks average ~288 characters instead of 350.
- **Numbers** (measured by running the same splitters on the repo's books):
  - char-split gives **8,248** chunks in total, recursive-split **14,228**.
  - The Tolminc book (7,808 chars) gives **24** char chunks and **35** recursive chunks.
  - For char-split, n ≈ ⌈(L − overlap)/(size − overlap)⌉ = ⌈7,788/330⌉ = 24.
- **Mental model.** Chunk size trades precision against context. Small chunks match narrow questions sharply but lose surrounding meaning. Large chunks carry context but blur the vector and eat prompt space. Overlap is insurance against cutting an idea in half.
- **Analogy.** Cutting a long scroll into index cards. char-split uses a ruler and scissors; recursive-split first looks for the gaps between paragraphs.
- **Misconception.** "Smaller chunks are always better" or "overlap is free." Overlap duplicates text. The recursive default of 200 characters is why it produces 1.7× as many chunks and 1.4× as many embedded characters.

### 3.3 Embeddings and cosine similarity
- **Explanation.** An embedding model maps text to a point in a high-dimensional space so that texts with similar *meaning* point in similar *directions*.
  - `gemini-embedding-001` natively returns 3,072 numbers. The code asks for **256** via `output_dimensionality` (`cli.py:25-26`, `:76-78`, `:101-102`). The model is trained so that a *prefix* of the vector is still a usable embedding (Matryoshka-style truncation).
  - Similarity is the cosine of the angle between two vectors. Chroma reports **cosine distance = 1 − cosine similarity**, so *smaller is closer*.
- **Mental model.** Every chunk is an arrow from the origin. The question is another arrow. Retrieval means "find the arrows with the smallest angle to mine."
- **Analogy.** GPS coordinates for meaning. Two restaurants on the same street have close coordinates even if their names share no letters.
- **Misconceptions.**
  - (a) "Embeddings are keyword matching." They are not. "curd" and "rennet" chunks can be close with no word in common, which is why `where_document={"$contains": ...}` exists as a separate *lexical* filter.
  - (b) "Any two 256-number vectors are comparable." Only vectors from the **same model, same dimension and same settings** live in the same space. Embedding the query with a different model gives a dimension error if the size differs and silent garbage if it matches.

### 3.4 The vector database: collection, records, index, persistence
- **Explanation.** Chroma stores **records**: `id`, `embedding`, `document` (the chunk text) and `metadata` (`{"book", "author", "year"}`, `cli.py:132-138`). Records are grouped in a **collection**, one per chunking strategy: `f"{method}-collection"` (`cli.py:277`).
  - The collection is created with `metadata={"hnsw:space": "cosine"}` (`cli.py:287-288`). That picks the distance function for the **HNSW** approximate-nearest-neighbour index. Chroma's default space is L2.
  - IDs are `hashlib.sha256(x.encode()).hexdigest()[:16]` of the book name, then `"-"`, then the row index (`cli.py:127-130`), so they are deterministic and unique per book.
  - `load` **deletes and recreates** the collection every time (`cli.py:280-289`). Loading is repeatable but all-or-nothing.
  - The server runs in its own container. Its storage directory `/data` is bind-mounted to `llm-rag/docker-volumes/chromadb` (`docker-compose.yml:23-24`, `README.md:160`). On disk that becomes `chroma.sqlite3` (documents, metadata, bookkeeping) plus one UUID-named folder per vector index, holding `data_level0.bin`, `header.bin`, `index_metadata.pickle`, `length.bin` and `link_lists.bin`. A staff commit accidentally committed exactly this layout (under `llmrag/`, with a 90.9 MB `chroma.sqlite3`) and then removed it: `git show --stat 58dd602`. That commit came from the `demo-podcast` PR, so it is also in `main`'s history even though the PR was later reverted.
- **Mental model.** A table of (id, text, metadata, vector), plus a "highway graph" over the vectors that finds nearest neighbours in roughly logarithmic time instead of scanning all 14k rows.
- **Analogy.** A library card catalogue that is shelved by topic-direction instead of by title.
- **Misconception.** "The vector DB understands text." In this tutorial Chroma never computes an embedding. Every vector comes from Vertex AI, and `add()`/`query()` receive explicit `embeddings=`/`query_embeddings=` (`cli.py:151-156`, `:354-359`). If you call `collection.query(query_texts=[...])` instead, Chroma silently uses its *own* default embedding function (a different model and dimension) and the query breaks (Exercise 6).

### 3.5 Retrieval: top-k, metadata filters and document filters
- **Explanation.** `collection.query(query_embeddings=[query_embedding], n_results=10)` (`cli.py:380-383`) returns the 10 nearest records. Two optional filters are applied **before** ranking:
  - `where={"book": "The Complete Book of Cheese"}` filters on metadata;
  - `where_document={"$contains": search_string}`, with `search_string = "Italian"` (`cli.py:353`), is a substring test on the chunk text.

  The result is a dict of **lists of lists**, one inner list per query: `ids`, `distances`, `metadatas`, `documents`, plus `embeddings`, `uris` and `data` (all `None` unless requested) and `included` (the default `["metadatas", "documents", "distances"]`; chromadb 1.1.0 `api/models/Collection.py:183-187`, `api/fastapi.py:653-662`). That is why the code reads `results["documents"][0]` (`cli.py:386`, `:390`).
- **Mental model.** Filters are a mask that greys out most of the points. Top-k then picks the nearest *among what is left*, however far away it is.
- **Analogy.** Asking a librarian for "the 10 pages most about Tolminc, but only from Bob Brown's book, and only pages containing the word *Italian*". You get 10 pages, and none of them is about Tolminc.
- **Misconception.** "Filters boost relevance." They constrain; they do not rank.
  - The active `--query` (`cli.py:352-361`) combines both filters. *The Complete Book of Cheese* contains **zero** occurrences of "tolminc" and 64 char-split chunks containing "Italian" (counted for this guide), so the 10 results are about Italian cheeses, not Tolminc (§4 step 9).
  - Top-k always returns k results, even when none is relevant. Nothing in this code applies a distance threshold.

### 3.6 Augmented generation: building the prompt
- **Explanation.** The "G" in RAG is ordinary prompt construction. `chat()` builds `INPUT_PROMPT` as the question followed by the 10 chunks joined with newlines (`cli.py:388-391`). It sends that as the user content to `gemini-3.1-flash-lite` (`cli.py:394-396`).
  - A carefully written `SYSTEM_INSTRUCTION` ("Your responses are based solely on the information provided in the text chunks…", `cli.py:40-58`) is **defined but never passed** to the model (Errata E1).
  - So the model sees "question + some cheese text" with **no instruction to stay inside the text**. It may blend in its own knowledge.
- **Mental model.** The LLM is a stateless function of its input tokens. Grounding is only as strong as (a) what you retrieved and (b) what you told the model to do with it.
- **Analogy.** Handing an expert a stack of photocopies with no note. Do they answer from the pages or from memory? You did not say.
- **Misconception.** "The LLM queries the vector DB." In plain RAG the *code* retrieves; the model never sees the database. Letting the model *decide* what and how to retrieve, via function calling, is the **agent** pattern of L06 (`cli.py:421-478`, `README.md:242-271`).

### 3.7 Semantic chunking
- **Explanation.** Instead of a ruler, cut where the *topic changes* (`semantic_splitter.py:99-109`, credited to Greg Kamradt at `semantic_splitter.py:102-105`):
  1. split the book into sentences with the regex `(?<=[.?!])\s+` (`semantic_splitter.py:118`, `:217`);
  2. for each sentence, build a window of itself plus one neighbour on each side (`buffer_size=1`, `combine_sentences`, `semantic_splitter.py:15-53`);
  3. embed every window through **the same Vertex function** (`embedding_function=generate_text_embeddings`, `cli.py:209-210`; called with `batch_size=50`, `semantic_splitter.py:206`);
  4. compute the cosine distance between consecutive windows (`semantic_splitter.py:56-85`);
  5. cut wherever the distance exceeds the **95th percentile** of all distances (`BREAKPOINT_DEFAULTS["percentile"] = 95`, `semantic_splitter.py:91-96`; threshold `:137-141`; cut points `:239-243`).

  So about 5% of sentence gaps become chunk boundaries, and chunk lengths vary widely.
- **Mental model.** A seismograph of meaning. Draw the distance-to-next-sentence curve over the book; the tallest 5% of spikes are the scene changes.
- **Analogy.** Splitting a podcast transcript wherever the hosts change topic instead of every 5 minutes.
- **Misconception.** "Semantic chunking is free and strictly better." Chunking itself now costs API calls: ~26,080 sentences ≈ 528 embedding calls for the corpus. Chunks also vary a lot in size; some will be thousands of characters. And since 5% of gaps are always cut, even a single-topic book gets the same *fraction* of cuts.

### 3.8 The ops shape: a two-container Compose app with mounts and secrets
- **Explanation.** `docker-shell.sh` exports the two GCP env vars (plus `IMAGE_NAME`) and runs `docker compose run --rm $IMAGE_NAME` with `IMAGE_NAME="llm-rag-cli"` (`docker-shell.sh:7-12`). Compose then:
  - creates the network `llm-rag-network` (`docker-compose.yml:1-3`);
  - builds `llm-rag-cli` from the Dockerfile **only if the image does not exist yet** (`:7-8`);
  - pulls and starts `chromadb` because of `depends_on` (`:16-17`), with the host port published (`8000:8000`, `:21-22`);
  - starts an interactive CLI container with the repo bind-mounted at `/app` and the secrets at `/secrets` (`:10-12`).

  Inside the network the CLI reaches the database at `http://llm-rag-chromadb:8000` by name (`cli.py:30-31`). The published host port exists for *you*: curl, the browser Chroma UI and scripts on the host. The CLI does not need it.
- **Why the venv lives at `/.venv`.** The Dockerfile installs dependencies into `/.venv` (`UV_PROJECT_ENVIRONMENT=/.venv`, `Dockerfile:18`; `uv sync --frozen`, `:45`). The bind mount of `../llm-rag` over `/app` therefore cannot hide them. You can edit `cli.py` on your laptop and rerun it in the container without rebuilding.
- **Mental model.** The CLI container is a disposable workbench; the DB container is a long-running appliance with its data on your disk. Secrets come in through a side door (a mount plus an env var) and are never baked into an image or committed.
- **Misconception.** "`--rm` cleans everything up." It removes only the CLI container. Chroma keeps running until `docker compose down`. A second misconception is "my index updates itself when the books change". It does not: the index is a snapshot, so re-run chunk → embed → load. The staff's own `out.txt` shows chunks from a version of the Tolminc book that no longer exists (E7).

---

## 4. Step-by-step walkthrough

Commands in `bash` blocks are copied verbatim from the README unless marked **(not in README)**. Run them in the order shown.

### Step 0. Lay out the folders (not in README beyond `README.md:48`, `:64-69`)
```bash
cd ~/Desktop/AC215                 # or wherever you keep course repos
git clone https://github.com/dlops-io/llm-rag.git
mkdir -p secrets
```
- **Under the hood.** `docker-compose.yml:11-12` mounts `../secrets` and **`../llm-rag`**, both relative to the compose file. So the repo folder must be named exactly `llm-rag`, and `secrets/` must sit next to it.
- **Checkpoint.** `ls` in the parent shows `llm-rag  secrets`.
- **If it fails.** If you downloaded a ZIP (folder `llm-rag-main`) or cloned under another name, rename it to `llm-rag`. Otherwise Docker mounts an empty folder over `/app` (§6 G1).

### Step 1. Service account and key (`README.md:52-69`)
1. Enable the **Vertex AI API** in your project (not in README, see §2).
2. In **IAM & Admin → Service accounts**, create `llm-service-account` (`README.md:54-55`).
3. Grant the roles in `README.md:56-58`. For this code, **Vertex AI User** (the README's "Gemini Enterprise Agent Platform User") is the one that matters.
4. Open **KEYS → ADD KEY → Create new key → JSON**, then copy the file into `secrets/` and rename it **`llm-service-account.json`** (`README.md:60-62`).
- **Checkpoint (not in README).** `ls ../secrets` from inside `llm-rag/` prints `llm-service-account.json`. `grep project_id ../secrets/llm-service-account.json` shows the project the key belongs to; the next step must use the same ID.
- **If it fails.** If "Create key" is greyed out or blocked by an org policy, you are probably in an organisation-managed project. Use your personal project (`ac215-setup/README.md:157`).

### Step 2. Point the script at your project (`README.md:79-80`)
- Edit **`docker-shell.sh:7`**: replace `ac215-project` in `export GCP_PROJECT="ac215-project" # CHANGE TO YOUR PROJECT ID` with your **Project ID**.
- Leave `docker-shell.sh:8` alone. It is the in-container path `/secrets/llm-service-account.json`.
- **If you skip this.** Every Vertex call goes to the course project `ac215-project`, where your SA has no rights, and you get a 403 PERMISSION_DENIED (§6 G3).

### Step 3. Start the containers (`README.md:75-85`)
```bash
sh docker-shell.sh
```
- **Under the hood.**
  1. `set -e` (`docker-shell.sh:4`), then the two env vars are exported (`:7-8`).
  2. `docker compose run --rm $IMAGE_NAME` with `IMAGE_NAME="llm-rag-cli"` (`:9`, `:12`); `IMAGE_NAME` happens to equal the *service* name. Compose then:
     - creates the network `llm-rag-network` (`docker-compose.yml:1-3`);
     - on the **first run only**, builds `llm-rag-cli` from the Dockerfile: `python:3.12-slim-bookworm` (`Dockerfile:2`), apt packages (`Dockerfile:4`, `:22-28`), `pip install uv` (`Dockerfile:30`), user `app` uid 1000 (`Dockerfile:31`), `uv sync --frozen` into `/.venv` (`Dockerfile:42-45`). This takes a few minutes.
     - pulls `chromadb/chroma:latest` (`docker-compose.yml:19`) and starts `llm-rag-chromadb` with `8000:8000` and `./docker-volumes/chromadb:/data` (`:20-24`). The `docker-volumes/chromadb` folder appears on your host.
     - starts the CLI container with `/app` and `/secrets` mounted and the two env vars passed through (`:10-15`). Its entrypoint (`Dockerfile:51`) runs `docker-entrypoint.sh`.
- **Checkpoint.** You should see the entrypoint's banner (`docker-entrypoint.sh:3-12`):
  ```
  Container is running!!!
  Architecture: aarch64          <- x86_64 on Intel/AMD machines
  Environment ready! Virtual environment activated.
  Python version: Python 3.12.x
  UV version: uv x.y.z
  Activating virtual environment...
  ```
  Then a bash prompt in `/app`, running as user `app` (`USER app` / `WORKDIR /app`, `Dockerfile:38-39`; the prompt is the `exec /bin/bash` at `docker-entrypoint.sh:15`).
- **Optional checks** (not in README), in a second host terminal:
  - `docker ps` should list `llm-rag-chromadb` with `0.0.0.0:8000->8000/tcp` and a CLI container;
  - `curl http://localhost:8000/api/v2/heartbeat` should return `{"nanosecond heartbeat": …}`. The chromadb 1.1.0 client uses the `/api/v2` prefix (`chromadb/config.py:96-97`, `:153` in the wheel).
- **If it fails.**
  - `port is already allocated`: see G6.
  - `container name "/llm-rag-chromadb" is already in use`: see G7.
  - `docker-entrypoint.sh: No such file or directory`: see G1.
  - Compose warns `The "GCP_PROJECT" variable is not set`: you ran `docker compose` directly instead of the script (G5).

### Step 4. Chunk: character splitting (`README.md:91-104`)
```bash
python cli.py --chunk --chunk_type char-split
```
- **Under the hood.**
  - `main()` prints the parsed args and calls `chunk("char-split")` (`cli.py:481-485`).
  - `chunk()` creates `outputs/` (`:168`), globs `input-datasets/books/*.txt` (`:171`) and derives `book_name = filename.split(".")[0]` (`:178`). That truncates one title (E8).
  - It splits with `CharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap, separator='', strip_whitespace=False)` with `chunk_size = 350` and `chunk_overlap = 20` (`:184-193`).
  - It writes `outputs/chunks-char-split-<book>.jsonl`, one JSON object `{"chunk": …, "book": …}` per line (`:217-227`).
  - **No API call is made.**
- **Checkpoint.**
  - `CLI Arguments: Namespace(chunk=True, embed=False, load=False, query=False, chat=False, get=False, agent=False, chunk_type='char-split')`, then `chunk()`, then `Number of files to process: 11`.
  - Then 11 blocks of `Processing file: input-datasets/books/….txt` / `Number of chunks: N` / `Shape: (N, 2)` / a DataFrame head. File order is whatever `glob` returns.
  - Expected N (from running the same splitter on the repo's books):

    | Book | N |
    |---|---|
    | Tolminc Cheese | 24 |
    | Cottage Cheese Recipe Book | 178 |
    | Hand-book on cheese making | 395 |
    | Cheese and its economical uses in the diet | 401 |
    | The book of The Cheese Being traits… | 522 |
    | Dairying exemplified… | 545 |
    | Theres Pippins and Cheese to Come | 636 |
    | Hints on cheese-making… | 640 |
    | The Complete Book of Cheese | 1355 |
    | Womans Institute Library of Cookery | 1505 |
    | The Book of Cheese | 2047 |
    | **Total** | **8,248** |

  - On your **host** (not in README): `wc -l outputs/chunks-char-split-*.jsonl` shows the same counts. pandas writes a trailing newline, so line count equals chunk count.
- **If it fails.**
  - `KeyError: 'GCP_PROJECT'` at `cli.py:23`: you are not in the container started by the script.
  - `PermissionError … 'outputs'` on Linux: see G14.
- **Optional:** the chunk visualiser at https://ac215-llm-rag.dlops.io/chunkviz (`README.md:95`).

### Step 5. Chunk: recursive splitting (`README.md:106-110`)
```bash
python cli.py --chunk --chunk_type recursive-split
```
- **Under the hood.** `RecursiveCharacterTextSplitter(chunk_size=chunk_size)` with `chunk_size = 350` (`cli.py:196-205`) with the library defaults: separators `["\n\n", "\n", " ", ""]`, `chunk_overlap=200`, `strip_whitespace=True`. It writes `outputs/chunks-recursive-split-<book>.jsonl`.
- **Checkpoint.** 14,228 chunks in total (Tolminc 35, The Book of Cheese 3,569). Chunks start at paragraph boundaries; Tolminc chunk 0 is the `Author: Pavlos Protopapas` header through "nobody hurried.". The README says nothing about the 200-character overlap.
- **If it fails.** Same as step 4.

### Step 6. Embed both chunk sets (`README.md:122-138`)
```bash
python cli.py --embed --chunk_type char-split
python cli.py --embed --chunk_type recursive-split
```
- **Under the hood.**
  - `embed()` (`cli.py:230-264`) reads each `chunks-<type>-*.jsonl` (`:234-235`) and calls `generate_text_embeddings(chunks, EMBEDDING_DIMENSION, batch_size=100)` (`:252-253`).
  - That function loops over batches of 100 (`:91-92`) and calls `llm_client.models.embed_content(...)` with `model=EMBEDDING_MODEL` (`"gemini-embedding-001"`), `contents=batch` and `config=types.EmbedContentConfig(output_dimensionality=dimensionality)` (256) (`:98-103`). On Vertex, google-genai 1.39.1 sends this as a `:predict` request with one instance per text.
  - On `errors.APIError` it retries up to 5 times with exponential backoff of 5, 10, 20, 40 and 80 s (`:108-119`).
  - It adds an `embedding` column, **sleeps 5 s per book** (`:256`) and writes `outputs/embeddings-<type>-<book>.jsonl` (`:262-264`).
- **Checkpoint.**
  - For each book: `Processing file: outputs/chunks-char-split-….jsonl`, then two DataFrame heads. The second has an `embedding` column of 256-float lists.
  - Expect ~89 calls plus 55 s of sleeps for char-split, and ~148 calls for recursive-split.
  - The `embeddings-*.jsonl` files are much bigger than the chunk files: 256 floats as JSON text add ~3.5 KB per row (pandas writes 10 significant digits). Estimated sizes: ~8 MB for *The Book of Cheese*, ~30 MB for all char-split files, ~50 MB for recursive-split.
- **If it fails.**
  - `DefaultCredentialsError: File /secrets/llm-service-account.json was not found.`: see G2.
  - 403 `PERMISSION_DENIED` / `SERVICE_DISABLED`: see G3 and G4.
  - Repeated `API error (code: 429)… Retrying in N seconds`: you hit quota. Wait, or lower `batch_size`.
  - A `400 INVALID_ARGUMENT` mentioning the number of instances: set `batch_size=1` (open question Q2).

### Step 7. Load into ChromaDB (`README.md:144-165`)
```bash
python cli.py --load --chunk_type char-split
python cli.py --load --chunk_type recursive-split
```
- **Under the hood.**
  - `load()` (`cli.py:267-306`) clears the client cache (`:271`) and connects with `chromadb.HttpClient(host=CHROMADB_HOST, port=CHROMADB_PORT)` (`:274`), i.e. `llm-rag-chromadb:8000`.
  - It tries `delete_collection` (`:280-285`), then `client.create_collection(name=collection_name, metadata={"hnsw:space": "cosine"})` (`:287-288`), where `collection_name = f"{method}-collection"` (`:277`).
  - For each `embeddings-<type>-*.jsonl` it calls `load_text_embeddings` (`:306`). That builds ids and per-book metadata (`:126-138`) and calls `collection.add(...)` in batches of 500 (`:142-158`).
  - Chroma persists everything under `/data`, which is `llm-rag/docker-volumes/chromadb/` on your host.
- **Checkpoint.**
  - `Creating collection: char-split-collection`.
  - Then `Collection 'char-split-collection' did not exist. Creating new.` (first time) or `Deleted existing collection 'char-split-collection'`.
  - Then `Created new empty collection 'char-split-collection'`, `Collection: Collection(name=char-split-collection)`, and per book `Inserted 500 items...` … `Finished inserting N items into collection 'char-split-collection'`, with N as in step 4.
  - On the host: `docker-volumes/chromadb/chroma.sqlite3` and UUID folders appear.
  - Optional: open https://ac215-llm-rag.dlops.io/chromaui in **Chrome** to browse your local DB (`README.md:162-165`). This presumably works because Chroma allows that origin via CORS (`docker-compose.yml:25-26`) and port 8000 is published.
- **If it fails.**
  - `ValueError: Could not connect to a Chroma server. Are you sure it is running?` means the Chroma container is down or you are running on the host (G11). Check `docker ps`.
  - `Number of files to process: 0` means you skipped step 6 for this chunk type.

### Step 8. (Restart test, not in README)
- `exit`, run `sh docker-shell.sh` again, and skip straight to step 9.
- **Checkpoint.** The query works without reloading, which demonstrates the persistence claim in `README.md:160`.

### Step 9. Query the vector DB, no LLM yet (`README.md:171-186`)
```bash
python cli.py --query --chunk_type char-split
python cli.py --query --chunk_type recursive-split
```
- **Under the hood.**
  - `query()` (`cli.py:309-361`) embeds `"How is tolminc cheese made?"` with `generate_query_embedding` (`:75-84`, `:318-319`) and opens the collection with `get_collection` (`:323`).
  - It runs **only variant #4** (`:352-361`): `n_results=10`, `where={"book": "The Complete Book of Cheese"}`, `where_document={"$contains": search_string}` with `search_string = "Italian"`. Variants #1-#3 are commented out (`:325-350`).
- **Checkpoint.**
  - It prints `load()` (a copy-paste label, `:310`), `Embedding values: [256 floats]`, `Query: How is tolminc cheese made?`, then `Results: {'ids': [[…10 ids…]], 'distances': [[…]], 'embeddings': None, 'metadatas': [[{'book': 'The Complete Book of Cheese', 'author': 'Bob Brown', 'year': 2024}, …]], 'documents': [[…]], 'uris': None, 'data': None, 'included': ['metadatas', 'documents', 'distances']}`. That key order is how the 1.1.0 HTTP client builds the dict (`chromadb/api/fastapi.py:653-662` in the wheel).
  - All 10 documents contain "Italian" and come from Bob Brown's book. **None mentions Tolminc**: that book never uses the word, and 64 char-split chunks of it contain "Italian".
  - **Try it** (edit on your laptop; no rebuild needed thanks to the bind mount): uncomment variant #1 (`cli.py:325-331`) and comment out #4. With no filter, expect `Tolminc Cheese` chunks among the top hits, but cheese-making passages from other books may compete: the current story uses the word "Tolminc" only 3 times (an expectation; not run).
- **If it fails.** A `NotFoundError` saying the collection does not exist means you have not run step 7 for this `--chunk_type` (G12).

### Step 10. Chat: the full RAG loop (`README.md:192-214`)
```bash
python cli.py --chat --chunk_type char-split
python cli.py --chat --chunk_type recursive-split
```
- **Under the hood.**
  - `chat()` (`cli.py:364-399`) embeds `"How is tolminc cheese made??"` (double "?", `:372`) and queries the top 10 with **no filter** (`:380-383`).
  - It builds `INPUT_PROMPT` as the question plus the 10 chunks joined by `"\n"` (`:388-391`). The `"\n"` inside an f-string expression needs Python 3.12 or newer.
  - It calls `llm_client.models.generate_content(model=GENERATIVE_MODEL, contents=INPUT_PROMPT)` (`:394-396`; `GENERATIVE_MODEL = "gemini-3.1-flash-lite"`, `:27`) and prints `LLM Response: <text>` (`:397-399`).
- **Checkpoint.**
  - `Query: How is tolminc cheese made??`, the embedding, the results dict, then `10`, then `INPUT_PROMPT:` with your chunks, then `LLM Response:` with a few paragraphs.
  - The current Tolminc book is a short *fictional* story ("A fictional tale inspired by Alpine cheesemaking", line 4 of the book). So the answer will likely draw on the story (Mara, her grandfather, milk becoming curd that is "cut, stirred"…). It will **not** match the PDO/transhumance text in `out.txt` (E7).
  - Compare the char-split and recursive-split answers.
  - Optional web version: https://ac215-llm-rag.dlops.io/chat (`README.md:211`).
- **If it fails.**
  - 404 / `NOT_FOUND` for the model: `gemini-3.1-flash-lite` may not be available to your project or at `global`; change `GENERATIVE_MODEL` at `cli.py:27` (Q3).
  - 429: quota, wait.

### Step 11. (Bonus, undocumented) `--get` (not in README)
```bash
python cli.py --get --chunk_type char-split
```
- **Under the hood.** `collection.get(where={"book": "The Complete Book of Cheese"}, limit=10)` (`cli.py:402-418`, flag at `:536-540`). This is a plain metadata lookup with **no similarity at all**.
- **Checkpoint.** 10 records from Bob Brown's book in storage order; there is no `distances` key in the output.
- Contrast this with step 9: `get` filters, while `query` filters *and* ranks.

### Step 12. (Advanced) Semantic chunking end to end (`README.md:220-236`)
```bash
python cli.py --chunk --embed --load --chunk_type semantic-split
```
- **Under the hood.** `main()` runs `chunk`, then `embed`, then `load` in sequence (`cli.py:484-491`).
  - **chunk:** `SemanticChunker(embedding_function=generate_text_embeddings)` (`:207-215`) splits sentences (`semantic_splitter.py:217`), embeds the 3-sentence windows 50 at a time (`:206`) and cuts at the 95th-percentile distance (`:229-243`). These are **real API calls**: ~26,080 sentences ≈ 528 calls.
  - **embed:** the same as step 6 but with `batch_size=15` (`cli.py:248-250`), because semantic chunks are long.
  - **load:** into `semantic-split-collection`.
- **Checkpoint.** Per book, `Number of chunks:` should be roughly 5% of its sentence count. The estimate is ~1,300 in total, and Tolminc (108 "sentences") gets about 6. Then `Finished inserting …` lines.
- **Follow-up (not in README).** `--chunk_type` is generic, so you can now run `python cli.py --chat --chunk_type semantic-split` and compare the answer with the two step-10 runs.
- **If it fails.** Expect 429s; the backoff handles brief ones. Budget 10-20+ minutes. To test cheaply, temporarily move all but one book out of `input-datasets/books/`.

### Step 13. Preview only: Agents (L06) (`README.md:242-271`)
```bash
python cli.py --agent --chunk_type char-split
```
- This sends the question "Describe where cheese making is important in Pavlos's book?" to Gemini with two function declarations (`agent_tools.py:9-81`), forcing a tool call (`mode="any"`, `cli.py:444-452`).
- It executes the chosen retrieval, for example `get_book_by_author(author="Pavlos Protopapas", …)`, a `where={"author": …}` query (`agent_tools.py:41-49`), and sends the results back for a final answer (`cli.py:456-478`).
- `out.txt` is a captured run of exactly this, from 2026-09-22 (`out.txt:1`, `:34`, `:120`). Leave the details to L06.

### Step 14. Leave and clean up (not in README)
```bash
exit                 # leaves the CLI container (it is deleted: --rm)
docker compose down  # run on the host, in llm-rag/: stops llm-rag-chromadb, removes llm-rag-network
```
- **Checkpoint.** `docker ps` shows no `llm-rag-*` containers. `docker-volumes/chromadb/` still exists, so next time you can query straight away.

---

## 5. Code tour

```
llm-rag/                          (= /app inside the CLI container, via the bind mount)
├── README.md                     tutorial: RAG steps (L05) + Agents section (L06)
├── docker-shell.sh               sets GCP_PROJECT / GOOGLE_APPLICATION_CREDENTIALS; `docker compose run --rm $IMAGE_NAME`
├── docker-compose.yml            services llm-rag-cli (built here) + chromadb (chromadb/chroma:latest); network llm-rag-network
├── Dockerfile                    python:3.12-slim-bookworm + uv; deps into /.venv; non-root user app (uid 1000)
├── docker-entrypoint.sh          prints arch/versions, activates /.venv, execs an interactive bash
├── pyproject.toml, uv.lock       chromadb 1.1.0, google-genai 1.39.1, langchain 0.3.27, langchain-text-splitters 0.3.11, pandas 2.3.3, ...
├── cli.py                        the whole pipeline: --chunk --embed --load --query --chat --get --agent, --chunk_type
├── semantic_splitter.py          SemanticChunker (sentence windows -> cosine distances -> percentile breakpoints)
├── agent_tools.py                L06: Gemini function declarations + executor for the --agent flow
├── input-datasets/books/         the corpus: 11 .txt books (Tolminc Cheese.txt = Pavlos's short story)
├── images/llm-rag-flow-{1,2,3}.png   README diagrams: index, query, agent
├── out.txt                       captured output of one --agent run (2026-09-22)
├── outputs/                      (git-ignored, created) chunks-*.jsonl, embeddings-*.jsonl
└── docker-volumes/chromadb/      (git-ignored, created by Chroma) chroma.sqlite3 + HNSW index folders
../secrets/llm-service-account.json   (you create; mounted read-write at /secrets)
```

**`docker-compose.yml:5-17`**
```yaml
services:
    llm-rag-cli:
        image: llm-rag-cli
        build: .
        container_name: llm-rag-cli
        volumes:
            - ../secrets:/secrets
            - ../llm-rag:/app
        environment:
            GOOGLE_APPLICATION_CREDENTIALS: $GOOGLE_APPLICATION_CREDENTIALS
            GCP_PROJECT: $GCP_PROJECT
        depends_on:
            - chromadb
```
- `image:` + `build: .`: Compose builds the Dockerfile in this folder and tags it `llm-rag-cli`, but **only if no such image exists**. Since `9a27441` (2026-09-16) the script no longer runs `docker build` itself, so rebuilding after dependency changes is up to you (G9).
- `container_name: llm-rag-cli`: a fixed name for the CLI container. The name that matters for DNS is the `chromadb` service's (next excerpt).
- `../secrets:/secrets` and `../llm-rag:/app`: both host paths are relative to *this file*. The second one means "this repo folder, **by name**". A plain `.:/app` would not depend on the folder name.
- `GOOGLE_APPLICATION_CREDENTIALS: $GOOGLE_APPLICATION_CREDENTIALS`: Compose *interpolates* these from the shell that ran `docker compose`, which is why you must go through `docker-shell.sh`.
- `depends_on: chromadb`: `run` starts the DB first. That means "container started", not "server ready".

**`docker-compose.yml:18-26`**
```yaml
    chromadb:
        image: chromadb/chroma:latest
        container_name: llm-rag-chromadb
        ports:
            - 8000:8000
        volumes:
            - ./docker-volumes/chromadb:/data
        environment:
            CHROMA_CORS_ALLOW_ORIGINS: '["https://ac215-llm-rag.dlops.io","http://localhost:3200"]'
```
- `chromadb/chroma:latest`: an unpinned server image. On 2026-10-12, `latest` was the same digest as `1.5.9` (Docker Hub; re-checked 2026-10-13: both `sha256:1e0b73a1…`, pushed 2026-05-05), while the Python client is pinned to 1.1.0 (`uv.lock:289-290`). It is multi-arch (amd64 and arm64).
- `container_name: llm-rag-chromadb`: this name is the **hostname** the CLI uses (`cli.py:30`).
- `8000:8000`: publishes the server on your laptop's port 8000, for the browser tools and curl. Container-to-container traffic does not need it.
- `./docker-volumes/chromadb:/data`: Chroma 1.x keeps its database in `/data`. Last year's `pipenv` branch (and `main` until `9a27441`) mounted `/chroma/chroma` (the 0.x path), so mixing old instructions with the new image loses persistence.
- `CHROMA_CORS_ALLOW_ORIGINS`: lets JavaScript on the course's web tool (and a local front end on port 3200, added in `7a3c66b`) call your local Chroma from the browser.

**`docker-shell.sh:6-12`**
```bash
# Set variables
export GCP_PROJECT="ac215-project" # CHANGE TO YOUR PROJECT ID
export GOOGLE_APPLICATION_CREDENTIALS="/secrets/llm-service-account.json"
export IMAGE_NAME="llm-rag-cli"

# Run all containers using docker compose run --rm
docker compose run --rm $IMAGE_NAME
```
- Line 7 is the one line you must edit; the comment says so.
- Line 8 is a path *inside* the container, matching the `/secrets` mount.
- Line 12: `run --rm` gives you an interactive one-off container that is deleted on exit. Dependencies (Chroma) are started and **left running**.

**`Dockerfile:37-51`**
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
- `USER app`: everything after this, including `uv sync`, runs as uid 1000 (created at `Dockerfile:31`). This matters for writing into bind mounts on Linux (G14).
- Copying `pyproject.toml uv.lock*` first and running `uv sync --frozen` before `COPY . ./` is layer caching: editing `cli.py` does not reinstall dependencies. `--frozen` installs exactly what `uv.lock` says and does not check whether the lock still matches `pyproject.toml` (that check is `--locked`); it errors only if `uv.lock` is missing, which the `uv.lock*` glob in the `COPY` would otherwise tolerate.
- `COPY . ./` copies the whole build context. There is **no `.dockerignore`**, so after a run `outputs/` and `docker-volumes/` (tens to hundreds of MB) are sent to the builder and baked into the image on any rebuild (G15). The bind mount hides this copy at run time anyway.
- `ENTRYPOINT ["/bin/bash","docker-entrypoint.sh"]` uses a *relative* script path resolved in `WORKDIR /app`, which is why an empty `/app` mount kills the container (G1).

**`cli.py:22-36`**
```python
# Setup
GCP_PROJECT = os.environ["GCP_PROJECT"]
GCP_LOCATION = "global"
EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSION = 256
GENERATIVE_MODEL = "gemini-3.1-flash-lite"
INPUT_FOLDER = "input-datasets"
OUTPUT_FOLDER = "outputs"
CHROMADB_HOST = "llm-rag-chromadb"
CHROMADB_PORT = 8000

#############################################################################
#                       Initialize the LLM Client                           #
llm_client = genai.Client(
    vertexai=True, project=GCP_PROJECT, location=GCP_LOCATION)
```
- Line 23 reads the env var at import; `os.environ[...]` raises `KeyError` if it is absent.
- Line 24: `"global"` routes to `https://aiplatform.googleapis.com/` (not `us-central1-…`). It was changed from `us-central1` in `51a2865`.
- Lines 25-27: the two models. `256` is the embedding size used for *both* the index and queries; they must match forever.
- Lines 30-31: the Chroma server's address on the Compose network. It is valid only inside containers on `llm-rag-network` (G11).
- Lines 35-36: one client object for embeddings and generation. Credentials are loaded lazily on the first call.

**`cli.py:183-194`**
```python
        text_chunks = None
        if method == "char-split":
            chunk_size = 350
            chunk_overlap = 20
            # Init the splitter
            text_splitter = CharacterTextSplitter(
                chunk_size=chunk_size, chunk_overlap=chunk_overlap, separator='', strip_whitespace=False)

            # Perform the splitting
            text_chunks = text_splitter.create_documents([input_text])
            text_chunks = [doc.page_content for doc in text_chunks]
            print("Number of chunks:", len(text_chunks))
```
- `separator=''` means "split into characters, then pack": a fixed-width window that ignores words.
- `chunk_overlap=20`: each chunk repeats the last 20 characters of the previous one.
- `strip_whitespace=False`: keeps leading and trailing spaces and newlines, so a chunk can start with `"\n\n"`.
- `create_documents([input_text])` returns LangChain `Document`s; the next line keeps only `.page_content`.

**`cli.py:96-106`**
```python
        while retry_count <= max_retries:
            try:
                response = llm_client.models.embed_content(
                    model=EMBEDDING_MODEL,
                    contents=batch,
                    config=types.EmbedContentConfig(
                        output_dimensionality=dimensionality),
                )
                all_embeddings.extend(
                    [embedding.values for embedding in response.embeddings])
                break
```
- `contents=batch`: up to 100 strings per request for char- and recursive-split (`cli.py:252-253`), 15 for semantic chunks, and 50 inside the semantic splitter.
- `output_dimensionality`: asks Vertex to return only the first 256 numbers of the embedding (`parameters.outputDimensionality` in the request).
- No `task_type` is sent, so documents and queries are embedded the same way (E16).
- `response.embeddings[i].values` is a list of floats in the same order as `batch`. `extend` keeps that alignment, and the DataFrame column assignment at `cli.py:254` relies on it.

**`cli.py:126-138`**
```python
    # Generate ids
    df["id"] = df.index.astype(str)
    hashed_books = df["book"].apply(
        lambda x: hashlib.sha256(x.encode()).hexdigest()[:16])
    df["id"] = hashed_books + "-" + df["id"]

    metadata = {
        "book": df["book"].tolist()[0]
    }
    if metadata["book"] in book_mappings:
        book_mapping = book_mappings[metadata["book"]]
        metadata["author"] = book_mapping["author"]
        metadata["year"] = book_mapping["year"]
```
- IDs: a 16-hex-character hash of the book name plus the row index, for example `3f1c…-0`. They are stable across reloads and unique across books.
- Metadata is computed **once per file** from the first row, which works because each JSONL file holds exactly one book. `author` and `year` are added only if the (truncated) book name is a key of `book_mappings` (`cli.py:60-72`). One book misses (E8).

**`cli.py:280-290`**
```python
    try:
        # Clear out any existing items in the collection
        client.delete_collection(name=collection_name)
        print(f"Deleted existing collection '{collection_name}'")
    except Exception:
        print(f"Collection '{collection_name}' did not exist. Creating new.")

    collection = client.create_collection(
        name=collection_name, metadata={"hnsw:space": "cosine"})
    print(f"Created new empty collection '{collection_name}'")
    print("Collection:", collection)
```
- The `try/except Exception` swallows Chroma's `NotFoundError` on first load, so either message is normal.
- `metadata={"hnsw:space": "cosine"}` is the legacy-style way (still accepted by chromadb 1.1.0, see `chromadb/api/collection_configuration.py` in the wheel) to choose cosine distance for the HNSW index. The default would be L2.
- Because the collection is dropped and recreated, a load is always a full rebuild.

**`cli.py:352-361`**
```python
    # 4: Query based on embedding value + lexical search filter
    search_string = "Italian"
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=10,
        where={"book": "The Complete Book of Cheese"},
        where_document={"$contains": search_string}
    )
    print("Query:", query)
    print("\n\nResults:", results)
```
- `query_embeddings=[query_embedding]` is a *list* of queries; the result has one inner list per query.
- `where` is an exact-match metadata filter; `where_document` with `$contains` is a case-sensitive substring filter on the chunk text.
- Both filters apply before nearest-neighbour ranking, so the result is "the 10 Bob Brown chunks containing 'Italian' that are least far from a Tolminc question".

**`cli.py:386-399`**
```python
    print(len(results["documents"][0]))

    INPUT_PROMPT = f"""
	{query}
	{"\n".join(results["documents"][0])}
	"""

    print("INPUT_PROMPT: ", INPUT_PROMPT)
    response = llm_client.models.generate_content(
        model=GENERATIVE_MODEL, contents=INPUT_PROMPT
    )
    generated_text = response.text

    print("LLM Response:", generated_text)
```
- `results["documents"][0]` holds the 10 chunk texts for the first (only) query.
- The f-string contains `"\n".join(...)` *inside* the braces, which is legal only from Python 3.12 (PEP 701). The lines inside the triple-quoted string start with tab characters, which are sent to the model as-is.
- `generate_content(model=..., contents=INPUT_PROMPT)` passes **no `config`**, hence no `system_instruction`, temperature or token limit (E1).
- `response.text` is the concatenated text of the first candidate.

**`semantic_splitter.py:229-243`**
```python
        distances, sentences = self._calculate_sentence_distances(single_sentences_list)
        if self.number_of_chunks is not None:
            breakpoint_distance_threshold = self._threshold_from_clusters(distances)
            breakpoint_array = distances
        else:
            (
                breakpoint_distance_threshold,
                breakpoint_array,
            ) = self._calculate_breakpoint_threshold(distances)

        indices_above_thresh = [
            i
            for i, x in enumerate(breakpoint_array)
            if x > breakpoint_distance_threshold
        ]
```
- `distances[i]` is the cosine distance between sentence window *i* and window *i+1*.
- With the default `"percentile"` / `95`, the threshold is the 95th percentile of all those distances, so roughly 5% of gaps become cuts.
- `indices_above_thresh` are the sentence indices after which a chunk ends. Lines 249-264 (not shown) join the sentences between cuts with single spaces, so the whitespace that separated sentences (including paragraph breaks) is replaced by one space.

---

## 6. Gotchas and common errors

Each entry: symptom → cause → fix.

**G1. Container exits immediately: `/bin/bash: docker-entrypoint.sh: No such file or directory`.**
- **Cause.** `docker-compose.yml:12` mounts `../llm-rag`. If your clone is named anything else (`llm-rag-main`, or a renamed folder inside a monorepo like `MLOps_Learning/`), Docker creates an empty `../llm-rag` directory and mounts it over `/app`. That hides the code, including the entrypoint script referenced at `Dockerfile:51`.
- **Fix.** Name the folder `llm-rag`, or change the mount to `.:/app`. Delete the stray empty `../llm-rag` folder.

**G2. `google.auth.exceptions.DefaultCredentialsError: File /secrets/llm-service-account.json was not found.` on the first embed, query or chat.**
- **Cause.** The key is not at `../secrets/llm-service-account.json`: wrong file name, wrong folder level, or `secrets/` created inside `llm-rag/`. Docker silently creates a missing bind-mount source as an empty directory. Chunking still works because no API call is made yet (§2).
- **Fix.** Place and rename the key exactly as in `README.md:62-69`. Then check from the container: `ls /secrets`.

**G3. `403 PERMISSION_DENIED` from aiplatform on embed or chat.**
- **Cause, option 1.** You did not edit `docker-shell.sh:7`, so the calls target `ac215-project`, not your project. That is the ID the L03 mega-pipeline hard-codes for the course's own project (`mega-pipeline/generate_text/cli.py:15`).
- **Cause, option 2.** The SA lacks the Vertex AI User role (`README.md:58`), or `GCP_PROJECT` is the project *name* instead of its ID.
- **Fix.** Use the ID that matches `project_id` in the key file and grant `roles/aiplatform.user`. Then `exit` and restart the script, because env vars are read at container start.

**G4. `403 … SERVICE_DISABLED` / "Vertex AI API has not been used in project … or it is disabled".**
- **Cause.** The README never says to enable the API (E6).
- **Fix.** Enable `aiplatform.googleapis.com` and wait a minute.

**G5. Compose prints `The "GCP_PROJECT" variable is not set. Defaulting to a blank string.` and Python fails even for `--chunk`.**
- **Cause.** You ran `docker compose run --rm llm-rag-cli` directly. `docker-compose.yml:14-15` interpolate from your shell, so both vars become empty strings.
- **What the code then does.** `cli.py:23` gets `""` (no `KeyError`). `genai.Client(project="")` treats the project as missing and calls `google.auth.default()` at import (google-genai `_api_client.py` in the wheel). `GOOGLE_APPLICATION_CREDENTIALS` is also the empty string, so google-auth 2.41.1 tries to open a file named `""` and fails at import with `google.auth.exceptions.DefaultCredentialsError: File  was not found.` (note the empty name between the two spaces; `google/auth/_default.py:343-349`, `:172-175` in the wheel).
- **Fix.** Always start through `sh docker-shell.sh`, or `export` both vars first.

**G6. `Bind for 0.0.0.0:8000 failed: port is already allocated`.**
- **Cause.** Something on your laptop already uses host port 8000: another Chroma (the L06 ADK repo's `llm-agent-google-adk/6-rag/2-custom-chromadb-rag/docker-compose.yml:8` also publishes `8000:8000`), a FastAPI dev server, or an old `llm-rag-chromadb`.
- **Fix.** Stop it (`docker ps`, then `docker stop <name>`). Or change the *left* side to `8001:8000` (`docker-compose.yml:22`). The CLI keeps working because it uses the container port over the network, but the web Chroma UI will need the new port.

**G7. `Conflict. The container name "/llm-rag-chromadb" is already in use …`.**
- **Cause.** The fixed `container_name` (`docker-compose.yml:20`) is still held by a container that belongs to a *different* Compose project, or to none (started by hand with `docker run --name`). Compose names the project after the folder that holds the compose file. Example: the `demo-podcast` branch keeps its compose file in `llmrag/` (project `llmrag`) but uses the same `container_name: llm-rag-chromadb` (`git show origin/demo-podcast:llmrag/docker-compose.yml`, line 21).
- **Not this error:** L10's `cheese-app-v0/llm-rag/docker-compose.yml` uses the same names, but its folder is also called `llm-rag`, so Compose treats both as the *same* project `llm-rag`. You get no conflict; Compose may instead reuse or recreate the running `llm-rag-chromadb`, so which `docker-volumes/` you are browsing depends on which copy started Chroma last (from Compose's project-naming rules; not tested).
- **Fix.** `docker rm -f llm-rag-chromadb`, or `docker compose down` in the folder that started it.

**G8. "I exited, but my laptop's fan is still on / port 8000 is still taken."**
- **Cause.** `--rm` removes only the CLI container (`docker-shell.sh:12`). Chroma stays up.
- **Fix.** `docker compose down` from `llm-rag/`.

**G9. After `git pull`, `ModuleNotFoundError` or old behaviour despite a changed `pyproject.toml` / `uv.lock` / `Dockerfile`.**
- **Cause.** Compose builds only when the image `llm-rag-cli` is missing (`docker-compose.yml:7-8`). The explicit `docker build` was commented out of the script in `9a27441` (and the comment deleted in `500a99c`). Your old image, with old `/.venv` dependencies, is reused. The bind mount gives you the *new* code with the *old* dependencies.
- **Fix.** `docker compose build` (or `docker compose run --build --rm llm-rag-cli`), then start again.

**G10. Behaviour differs between classmates, or a sudden Chroma API error after re-pulling.**
- **Cause.** `chromadb/chroma:latest` (`docker-compose.yml:19`) resolves to whatever was newest when *you* first pulled it (1.5.9 as of 2026-10-12), while the client is locked at 1.1.0 (`uv.lock:289-290`).
- **Fix.** Pin the server, for example `chromadb/chroma:1.5.9` (the tag exists, multi-arch), and only upgrade deliberately.

**G11. Running `python cli.py …` on your laptop instead of in the container.**
- **Symptoms.**
  - `KeyError: 'GCP_PROJECT'`;
  - `SyntaxError: f-string expression part cannot include a backslash` on Python ≤ 3.11 (`cli.py:388-391`);
  - `ValueError: Could not connect to a Chroma server. Are you sure it is running?`, because `llm-rag-chromadb` (`cli.py:30`) only resolves inside the Compose network.
- **Fix.** Use the container. If you really want host-side runs, use Python 3.12, export the env vars with a host path to the key, and change the host to `localhost`.

**G12. A `NotFoundError` saying the collection does not exist, from `--query`, `--chat` or `--get`.**
- **Cause.** Each `--chunk_type` has its own collection (`cli.py:277`, `:316`, `:370`, `:408`), and you have not loaded that one. Another cause: you deleted `docker-volumes/`.
- **Fix.** Run `--load` for that `--chunk_type` (and `--embed` first if `outputs/` is empty).

**G13. Semantic split is slow, eats quota and prints many `API error (code: 429)` retries.**
- **Cause.** Chunking itself embeds ~26k sentence windows, about 528 calls (`semantic_splitter.py:206`). The retry loop only catches `errors.APIError` (`cli.py:108`), and after 5 retries it re-raises and aborts the whole run.
- **Fix.** Try it on one book first. Re-running repeats every API call, because `chunk` does not cache.

**G14. `PermissionError: [Errno 13] Permission denied: 'outputs'` (Linux hosts).**
- **Cause.** The container runs as uid 1000 (`Dockerfile:31`, `:38`) and writes into your bind-mounted repo. If your host user is not uid 1000, it cannot create `outputs/`. Separately, the Chroma container runs as root (the image config sets no `USER`), so `docker-volumes/` ends up owned by root.
- **Fix.** `mkdir outputs && chmod a+w outputs` on the host, or match the uid. Use `sudo rm -rf docker-volumes` to clean up. macOS and Windows Docker Desktop map ownership for you.

**G15. Rebuilds become slow or the image balloons.**
- **Cause.** There is no `.dockerignore`, so `COPY . ./` (`Dockerfile:48`) includes `outputs/` and `docker-volumes/`.
- **Fix.** Add a `.dockerignore` with `outputs/`, `docker-volumes/` and `__pycache__/`.

**G16. Packages added with `uv add` disappear after you exit.**
- **Cause.** `uv add` inside the container edits `pyproject.toml` and `uv.lock` on your host (bind mount) but installs into `/.venv`, which lives in the throw-away container (`Dockerfile:18`).
- **Fix.** Rebuild the image (G9) after adding dependencies.

**G17. Filtering by the Woman's Institute book or author returns nothing.**
- **Cause.** `book_name = filename.split(".")[0]` (`cli.py:178`) cuts `Womans Institute Library of Cookery. Volume 2_ Milk, Butter and Cheese Eggs Vegetables.txt` at the first dot. The book is therefore stored as `"Womans Institute Library of Cookery"`, which does not match the `book_mappings` key at `cli.py:70`, so it gets no `author`/`year` metadata (`cli.py:135-138`).
- **Fix.** Use `os.path.splitext(filename)[0]`, then re-chunk, re-embed and re-load.

**G18. The answer talks about things that are not in the books any more (or misses new text).**
- **Cause.** The index is a snapshot. Editing `input-datasets/books/` changes nothing until you re-run chunk → embed → load. The staff hit this themselves: `out.txt` (captured 2026-09-22) retrieves "known as transhumance…" (`out.txt:73`). That text is in the *old* Tolminc book (`git show 85bba32^:"input-datasets/books/Tolminc Cheese.txt"`) but not the current one, which was replaced in the same commit.
- **Fix.** Rebuild the index whenever the corpus changes. Never mix embedding models or dimensions between index and query.

**G19. The web tools (chunkviz / chromaui / chat) do not load or show CORS errors.**
- **Cause.** The README insists on Chrome (`README.md:97-98`, `:164-165`, `:213-214`). Likely reason (an inference, not verified): the HTTPS page calls `http://localhost:8000` from your browser, and Safari blocks that mixed-content request. This also needs the published port and the allowed origin (`docker-compose.yml:21-22`, `:25-26`).
- **Fix.** Use Chrome, keep `8000:8000`, and make sure `llm-rag-chromadb` is running.

**G20. Secrets ending up in git or in an image.**
- **Cause.** If you put the key inside `llm-rag/` instead of `../secrets/`, it is *not* git-ignored (`.gitignore:1-5` has no `secrets` entry) and `COPY . ./` would bake it into the image.
- **Fix.** Keep `secrets/` a sibling. Before any push, check `git status`. If a key ever lands in a commit, delete the key in IAM; rewriting history is not enough.

**G21. Apple Silicon: nothing special is needed.**
- `python:3.12-slim-bookworm` and `chromadb/chroma` are multi-arch.
- Every locked package with native code ships `manylinux … aarch64` wheels. Per `uv.lock`, only `pypika` is source-only, and it is pure Python, which `build-essential` (`Dockerfile:4`) covers anyway.
- The banner prints `Architecture: aarch64`. Do **not** add `--platform linux/amd64`; emulation would just slow everything down.

**G22. Windows: `sh` not found, or the container dies with `$'\r': command not found`.**
- **Cause.** `sh docker-shell.sh` (`README.md:84`) needs a POSIX shell (Git Bash or WSL), not PowerShell/cmd. Separately, the repo has no `.gitattributes`, so Git for Windows with `core.autocrlf=true` checks the `.sh` files out with CRLF endings. Because the repo is bind-mounted over `/app`, the container runs those CRLF copies, and `docker-entrypoint.sh` breaks inside Linux bash.
- **Fix.** Run from WSL (clone inside the WSL filesystem) or Git Bash, and re-clone with `git config --global core.autocrlf input` (or convert the two scripts to LF).

**G23. Retrieval returns Project Gutenberg licence text.**
- **Cause.** Ten of the eleven books still carry the full Project Gutenberg header and licence (from `*** START OF THE PROJECT GUTENBERG EBOOK` / up to and after `*** END OF …`). Counted for this guide: ~19.5 k characters per book, ~195 k characters in total (7.2% of the corpus, ~600 char-split chunks). It is chunked, embedded (and paid for) and retrievable like any other text; nothing in `chunk()` (`cli.py:180-181`) strips it.
- **Fix.** Strip everything outside the START/END markers before chunking, then re-chunk, re-embed and re-load. This is a good "data cleaning matters" moment.

---

## 7. Where this sits in the course

**Before.**
- **L01-L02.** VMs, venvs and uv; one Dockerfile, `docker build` / `docker run`, images on Docker Hub.
- **L03 (`mega-pipeline` `main`).** Single-purpose containers calling Google AI APIs with `google-genai` on Vertex AI, authenticated by a service-account JSON via `GOOGLE_APPLICATION_CREDENTIALS`. The containers never talked to each other; a GCS bucket was the hand-off.
- **L04 (`mega-pipeline` `flexible-workflow` + `port_toy`).**
  - Secrets moved *outside* the repo and were mounted at `/secrets` by a `docker-shell.sh`.
  - Each student used their own SA.
  - `port_toy` taught Docker networks, DNS by container name, and published versus internal ports with Compose.
  - The [L04 guide](L04-containers-2b-flexible-workflow-ports.md) (§7) flags this repo as the first real consumer of those ideas (`docker-compose.yml:1-3`, `:20`; `cli.py:30-31`).

**What L05 adds.**
1. A **stateful service container**: a database server with a persistent bind-mounted data directory, started as a Compose dependency next to a disposable CLI container. It is the first time two of your containers talk over HTTP.
2. The **RAG pattern**: chunking strategies, embedding APIs and vector dimensions, cosine/HNSW indexes, metadata and lexical filters, top-k retrieval and prompt assembly.
3. A **two-phase pipeline** (offline index, online query) whose intermediate artefacts (`outputs/*.jsonl`) are inspectable files. This is the shape that Milestone 2 asks LLM teams to reproduce: "data collection, chunking, and vector database integration … at least one complete retrieval flow from query to retrieved context" (`2026-AC215/milestone2.md:22`, `:53-54`).

**Evolution of this repo** (`git diff --stat origin/pipenv main`, last year's version → this year's):
```
 .gitignore                              |    3 +-
 Dockerfile                              |   37 +-
 Pipfile                                 |   21 -
 Pipfile.lock                            | 3066 -------------------------------
 README.md                               |  278 ++-
 agent_tools.py                          |  120 +-
 cli.py                                  |  844 +++++----
 docker-compose.yml                      |    9 +-
 docker-entrypoint.sh                    |   18 +-
 docker-shell.sh                         |   33 +-
 input-datasets/books/Tolminc Cheese.txt |  311 ++--
 out.txt                                 |  137 ++
 pyproject.toml                          |   15 +
 uv.lock                                 | 2592 ++++++++++++++++++++++++++
 14 files changed, 3703 insertions(+), 3781 deletions(-)
```
Meaningful changes:
- Pipenv → uv, with the venv at `/.venv`.
- `vertexai` SDK (`TextEmbeddingModel`, `GenerativeModel(system_instruction=…)`) → `google-genai` `Client(vertexai=True)`. In this migration the system instruction stopped being applied (E1).
- Models: `text-embedding-004` + `gemini-1.5-flash-002` in `us-central1` → `gemini-embedding-001` + `gemini-3.1-flash-lite` at `global`.
- Chroma 0.x (`/chroma/chroma`, `IS_PERSISTENT=TRUE`, CORS `["*"]`) → Chroma 1.x (`/data`, an explicit CORS allow-list).
- The script no longer runs `docker network create` or `docker build`; Compose owns both.
- The Tolminc book was replaced by a short fictional story (`85bba32`).

**After: what builds on this.**
- **L06 (Agents I)**, `2026-AC215/tutorials_demo.md:83-98`.
  - The README's **Agents** section on this same repo: `--agent`, Gemini function calling over `get_book_by_author` / `get_book_by_search_content` (`agent_tools.py`).
  - The *Cheese Quiz* Colab, which frames retrieved documents as one layer of "model context" ("Step 3: Retrieve Relevant Documents (e.g. RAG)").
  - `llm-agent-google-adk/6-rag`, which re-does RAG with Vertex AI RAG Engine and with a custom ChromaDB on port 8000 (`6-rag/2-custom-chromadb-rag/`).
- **L07 (Agent harness).** **L08 (fine-tuning)** is the alternative to RAG for injecting knowledge: it changes the weights instead of the prompt.
- **L10 (`cheese-app-v0`).** Ships `cheese-app-v0/llm-rag/`, a **near-verbatim copy** of this repo. `diff -r` shows: all code, the Dockerfile, the books and `out.txt` are identical; `docker-compose.yml:11` becomes `../../secrets:/secrets`; the README points the four web tools at the local front end (`http://localhost:3200/chunkviz`, `/chromaui`, `/chat`, `/agent`) and shows the nested folder layout; and the copy has no `.gitignore`. It is wired to an `api-service` (`api-service/api/routers/rag.py`) and a `frontend-ai-chatbot` (published on host port 3200, `frontend-ai-chatbot/docker-shell.sh:11`), so the CLI you ran today becomes a backend. That front end is presumably why `7a3c66b` ("updated for localhost") added `http://localhost:3200` to Chroma's CORS list.
- **Later cheese-app versions (v2-v4)** carry a `src/vector-db/` service with an older variant of this `cli.py`. Note that `cheese-app-v2/src/vector-db/cli.py:27` still names `text-embedding-004`, which the README here says was retired (`README.md:138`).

---

## 8. Exercises

**Ex 1. Hands-on: bigger chunks.**
- *Task.* In `cli.py:185-186`, set `chunk_size = 700` and `chunk_overlap = 100`. Predict the number of char-split chunks for `Tolminc Cheese`, then run `python cli.py --chunk --chunk_type char-split` and check.
- *Answer.* The stride is 700 − 100 = 600, so ⌈(7,808 − 100)/600⌉ = ⌈12.8⌉ = **13** (running the same splitter gives 13; with 700/20 it is 12).
  - To use the new chunks in chat you must re-embed and re-load: `--embed` and `--load` for `char-split`. Otherwise the DB still holds 350-char chunks.
  - Expect each retrieved chunk to carry more context but fewer distinct passages per 10 results. The prompt is about twice as long.

**Ex 2. Debugging: the collection that wasn't there.**
- *Task.* A classmate runs `python cli.py --chat --chunk_type semantic-split` right after the char-split steps and gets a Chroma `NotFoundError` about a missing collection. Why, and what is the cheapest fix?
- *Answer.* Collections are per chunk type: `f"{method}-collection"` (`cli.py:370`), and `semantic-split-collection` was never created.
  - Either run `--chat --chunk_type char-split`, or build the semantic index with `python cli.py --chunk --embed --load --chunk_type semantic-split`. The latter costs roughly 600 API calls, so try it with one book first.

**Ex 3. Debugging: "Could not connect to a Chroma server".**
- *Task.* You open a terminal on your Mac, `cd llm-rag`, create a Python 3.12 venv, `export GCP_PROJECT=…`, and run `python cli.py --query`. Chroma is running (`docker ps` shows it). Why does it fail, and what two-line change makes it work from the host?
- *Answer.* `CHROMADB_HOST = "llm-rag-chromadb"` (`cli.py:30`) is a DNS name that exists only on the Compose network `llm-rag-network`. From the host you must use the **published** port: `chromadb.HttpClient(host="localhost", port=8000)`.
  - You would also need `GOOGLE_APPLICATION_CREDENTIALS` pointing at the key's *host* path, for example `../secrets/llm-service-account.json`.
  - A cleaner fix is to make the host configurable: `CHROMADB_HOST = os.environ.get("CHROMADB_HOST", "llm-rag-chromadb")`. That is exactly what the later `cheese-app-v2/src/vector-db/cli.py:32` does with `os.environ["CHROMADB_HOST"]`.

**Ex 4. Hands-on: turn the system instruction on.**
- *Task.* In `chat()`, change the query at `cli.py:372` to `"What is the capital of France?"`. Run `--chat` once as-is, then pass the existing `SYSTEM_INSTRUCTION` (fix in §9 E1) and run again. Predict the difference.
- *Answer.*
  - **Without it**, the model receives "What is the capital of France?" followed by 10 unrelated cheese chunks and no instruction. It will very likely just answer "Paris".
  - **With it**, the instruction says to answer only from the chunks and to "redirect the conversation back to cheese-related subjects" (`cli.py:41`, `:54`). Expect a polite refusal or redirect.
  - This is the cleanest demo that retrieval alone does not ground an answer; the instruction does part of the work.

**Ex 5. Conceptual: cosine vs L2.**
- *Task.* Suppose `load()` created the collection without `metadata={"hnsw:space": "cosine"}` (`cli.py:288`). Would rankings change? Under what condition would they *not* change?
- *Answer.* Chroma would use **L2** (squared Euclidean) distance. For unit-length vectors, ‖a − b‖² = 2 − 2·cos(a, b), so L2 and cosine rank identically. `gemini-embedding-001` vectors truncated to 256 dimensions are not guaranteed to be unit length, though; Google's guidance is to normalise truncated outputs (to verify in the docs). With L2 on unnormalised vectors, a chunk whose vector is merely *longer* can rank differently. Either keep cosine or L2-normalise every vector before `add`/`query`.

**Ex 6. Debugging: the dimension trap.**
- *Task.* A teammate "improves" retrieval by changing `EMBEDDING_DIMENSION` to `768` (`cli.py:26`) and reruns `--chat` without re-embedding. Then they try `collection.query(query_texts=[query], n_results=10)` instead. What happens each time?
- *Answer.*
  - **First case.** The query vector has 768 numbers but the collection's dimension was fixed at 256 on first insert (Chroma fixes a collection's dimension on first insert; the local implementation is `_validate_dimension` in `chromadb/api/segment.py` of the wheel, and the server enforces the same rule). The query is rejected with an embedding-dimension mismatch error.
  - **Second case.** Chroma embeds the text with *its own* default embedding function (a local model with a different dimension, 384 for its default MiniLM model), which also mismatches 256. Even if the sizes happened to match, the vectors would be in a different space and the results would be meaningless.
  - **Fix.** Change the dimension only together with a full re-embed and re-load.

**Ex 7. Ops: what is still running?**
- *Task.* After a session you type `exit` and then `docker ps -a`. List what you expect to see. Then explain what `docker compose down` removes and what it keeps.
- *Answer.*
  - You see `llm-rag-chromadb` still **Up** with `0.0.0.0:8000->8000/tcp`. The CLI container is gone (`--rm`).
  - `docker compose down` stops and removes `llm-rag-chromadb` and the network `llm-rag-network`.
  - It keeps the images (`llm-rag-cli`, `chromadb/chroma:latest`), the bind-mounted data in `docker-volumes/chromadb/` (bind mounts are not Docker volumes, so even `down -v` will not delete them) and your `outputs/`. The next `sh docker-shell.sh` can query immediately.

**Ex 8. Conceptual: why did `out.txt` find "transhumance"?**
- *Task.* `out.txt:73` shows a retrieved chunk "…known as transhumance, shaped not just the economic life…", but `grep -c transhumance "input-datasets/books/Tolminc Cheese.txt"` prints `0`. Explain.
- *Answer.* The run was captured against a ChromaDB loaded from the **previous** version of the book, which does contain it (`git show 85bba32^:"input-datasets/books/Tolminc Cheese.txt" | grep -c transhumance` → 3 matching lines). In the same commit `85bba32` the book file was replaced by a short fictional story. The DB is a snapshot; the source files are not consulted at query time. Re-running chunk → embed → load would make that text disappear from retrieval.

---

## 9. Errata and open questions

**Errata (with evidence)**

- **E1. The system instruction is never used, so "grounded" is weaker than the README implies.**
  - `SYSTEM_INSTRUCTION` is defined at `cli.py:40-58` but no call passes it: `grep -n SYSTEM_INSTRUCTION cli.py` finds only line 40.
  - `chat()` calls `generate_content(model=GENERATIVE_MODEL, contents=INPUT_PROMPT)` with no `config` (`cli.py:394-396`).
  - Last year's code applied it via `GenerativeModel(GENERATIVE_MODEL, system_instruction=[SYSTEM_INSTRUCTION])` (`git show 0b671ed:cli.py`, lines 62-64). It was commented out during the uv/genai migration (`59a0f80`, `4a5f347`) and never re-attached.
  - Meanwhile the README says the LLM "answers grounded in your documents, not its own training data" (`README.md:21`).
  - Suggested fix (not in the repo):
    ```python
    response = llm_client.models.generate_content(
        model=GENERATIVE_MODEL,
        contents=INPUT_PROMPT,
        config=types.GenerateContentConfig(system_instruction=SYSTEM_INSTRUCTION),
    )
    ```
- **E2. The README's description of `--query` does not match the code.**
  - The README says "Perform similarity searches in the vector database / Apply various types of filters on the queries" (`README.md:185-186`).
  - Only variant #4 runs (`cli.py:352-361`); #1-#3 are commented out (`cli.py:325-350`). #4 restricts results to *The Complete Book of Cheese* chunks containing "Italian", a book with zero mentions of Tolminc, so the sample query's results are unrelated to the question.
  - This is good for teaching filters, but confusing if unexplained.
- **E3. Wrong label.** `query()` prints `load()` (`cli.py:310`).
- **E4. Query text inconsistency.** The README says the chat sample query is "How is tolminc cheese made?" (`README.md:205`), while the code uses `"How is tolminc cheese made??"` (`cli.py:372`, changed in `96d5fd7`). `query()` uses a single "?" (`cli.py:318`). Harmless, but the printed output differs from the README.
- **E5. Over-privileged role.** The README asks for **Storage Admin** (`README.md:57`), but no code touches Cloud Storage. Only the Vertex AI role is needed. Least privilege says drop it.
- **E6. Missing step: enabling the Vertex AI API.** It is not mentioned anywhere in `README.md:45-69`. Without it, the first embed fails with SERVICE_DISABLED (G4).
- **E7. `out.txt` is stale and belongs to L06.** It is an `--agent` run (`out.txt:1`) captured 2026-09-22 (`out.txt:34`) against a DB loaded from the pre-`85bba32` Tolminc book. Its retrieved text ("transhumance", PDO rules) is absent from the current book (§8 Ex 8). Do not expect to reproduce it.
- **E8. Book-name truncation drops metadata for one book.**
  - `filename.split(".")[0]` (`cli.py:178`) turns `Womans Institute Library of Cookery. Volume 2_ Milk, Butter and Cheese Eggs Vegetables.txt` into `Womans Institute Library of Cookery`.
  - That no longer matches the key at `cli.py:70`, so the 1,505 char-split chunks of that book carry no `author`/`year`.
  - Relatedly, for L06, the agent's author enum (`agent_tools.py:19-29`) omits both "Milk Industry Foundation" and "Woman's Institute of Domestic Arts and Sciences".
- **E9. Unpinned server image.** `chromadb/chroma:latest` (`docker-compose.yml:19`) is 1.5.9 as of 2026-10-12, against a client locked at 1.1.0 (`uv.lock:289-290`). It works today per the staff's run, but different students can get different servers.
- **E10. Folder-name coupling.** `../llm-rag:/app` (`docker-compose.yml:12`) silently requires the clone to be named `llm-rag`. The README's folder diagram (`README.md:66-69`) shows this but never says it is mandatory.
- **E11. Unused dependencies and imports.** `openai` and `openai-agents` (`pyproject.toml:12-13`) are never imported. `GenerationConfig` and `ToolConfig` are imported at `cli.py:13`, but the code uses the `types.` versions. This only makes the image bigger.
- **E12. Cosmetic.** `docker-entrypoint.sh:6` prints "Virtual environment activated." before activation happens at line 12.
- **E13. Undocumented flag.** `--get` (`cli.py:499-500`, `:536-540`) exists but is not in the README.
- **E14. Hidden default overlap.** The README says chunks are "small, overlapping" (`README.md:17`, `:93`) but never states that recursive-split uses the library default `chunk_overlap=200`, more than half the 350-char chunk size, versus 20 for char-split.
- **E15. No `.dockerignore`.** `COPY . ./` (`Dockerfile:48`) will include generated data in rebuilds (G15).
- **E16. Possible quality improvement (not a bug).** Neither embedding call sets `task_type` (`cli.py:76-83`, `:98-103`), so chunks and questions are embedded identically. `gemini-embedding-001` supports asymmetric `RETRIEVAL_DOCUMENT` / `RETRIEVAL_QUERY` task types (google-genai sends `task_type` per instance when set, `_EmbedContentConfig_to_vertex` in the wheel), which usually improves retrieval. Vertex's default when it is unset is believed to be `RETRIEVAL_QUERY`; verify in the docs.
- **E17. Numbering mismatch on the course site.** `2026-AC215/tutorials_demo.md:71` calls this "Lecture 5", while `2026-AC215/_modules/week-03.md:5-7` lists "LLM - RAGs" on Sep 15 as "Lecture 4".
- **E18. Uncleaned corpus.** The ten Gutenberg books still include the Project Gutenberg header and licence, ~195 k characters (7.2% of the corpus) that are chunked, embedded and retrievable (G23). The README's "This will: Read each text file…" (`README.md:114`) does not mention any cleaning, and `chunk()` does none (`cli.py:180-181`).

**Open questions (could not determine from the sources)**

- **Q1.** What the Ed lesson adds (slides, quiz, extra instructions). The Ed lesson was not accessible.
- **Q2. Batch embedding with `gemini-embedding-001` on Vertex.** `generate_text_embeddings` sends up to 100 texts per `:predict` request (`cli.py:91-103`), and the comment claims "Max batch size is 250" (`cli.py:88`), a limit that dates from `text-embedding-004`. Early Vertex docs appear to have limited `gemini-embedding-001` to one input per request (not confirmed). The only staff evidence (`out.txt`) shows single-text query embeddings succeeding at `global`; the batch path (`--embed`, and the semantic splitter) was switched to this model in `74dba4a` with no captured run. If batch embed fails with `400 INVALID_ARGUMENT`, set the batch size to 1 (slower) in all three places: `cli.py:250` (15), `cli.py:253` (100) and `semantic_splitter.py:206` (50); or check the current limits.
- **Q3. Model availability.** `gemini-3.1-flash-lite` at location `global` worked for the staff on 2026-09-22 (`out.txt:34`, `model_version='gemini-3.1-flash-lite'`). Whether it is enabled for every student project, and for how long, could not be checked.
- **Q4. Role naming.** The README's "Gemini Enterprise Agent Platform User" (`README.md:58`) is presumably the renamed Vertex AI User role (`roles/aiplatform.user`). The console label was not confirmed.
- **Q5. The web tools.** `/chunkviz`, `/chromaui`, `/chat` and `/agent` on `ac215-llm-rag.dlops.io` are not in this repo. The CORS setting (`docker-compose.yml:25-26`) suggests that `/chromaui` talks to *your* local Chroma at `localhost:8000`. Supporting evidence from the L10 copy of these pages: in `cheese-app-v0/frontend-ai-chatbot`, the Chroma UI form defaults to `url: 'http://localhost:8000'` (`src/app/chromaui/page.jsx:24`) and calls Chroma's `/api/v2/...` endpoints straight from the browser (`src/services/DataService.js:22`, `:43`), while chat goes through the API service (`BASE_API_URL + "/rag/llm-response"`, `DataService.js:13`). Whether the hosted `ac215-llm-rag.dlops.io` site is built the same way, and why Chrome is required, could not be verified.
- **Q6. Long semantic chunks.** Semantic chunks can be several thousand characters, and `semantic_splitter.py` places no cap on them. It was not verified whether Vertex silently truncates over-long inputs for `gemini-embedding-001` (an `autoTruncate` default) or rejects them.
- **Q7. Exact prices.** The cost table in §2 uses an assumed ~$0.15 / 1 M tokens for embeddings and an approximate 4 characters per token. Check the current Vertex AI pricing page.

---

## Links

- README sections (pinned commit): [What you'll build](https://github.com/dlops-io/llm-rag/blob/e17a39f35bc07b440f573def480adaf4703f8b91/README.md#what-youll-build) · [Prerequisites](https://github.com/dlops-io/llm-rag/blob/e17a39f35bc07b440f573def480adaf4703f8b91/README.md#prerequisites) · [Setup GCP Service Account](https://github.com/dlops-io/llm-rag/blob/e17a39f35bc07b440f573def480adaf4703f8b91/README.md#setup-gcp-service-account) · [Run LLM RAG Container](https://github.com/dlops-io/llm-rag/blob/e17a39f35bc07b440f573def480adaf4703f8b91/README.md#run-llm-rag-container) · [Chunk Documents](https://github.com/dlops-io/llm-rag/blob/e17a39f35bc07b440f573def480adaf4703f8b91/README.md#chunk-documents) · [Generate Embeddings](https://github.com/dlops-io/llm-rag/blob/e17a39f35bc07b440f573def480adaf4703f8b91/README.md#generate-embeddings) · [Load Embeddings into Vector Database](https://github.com/dlops-io/llm-rag/blob/e17a39f35bc07b440f573def480adaf4703f8b91/README.md#load-embeddings-into-vector-database) · [Query the Vector Database](https://github.com/dlops-io/llm-rag/blob/e17a39f35bc07b440f573def480adaf4703f8b91/README.md#query-the-vector-database) · [Chat with LLM](https://github.com/dlops-io/llm-rag/blob/e17a39f35bc07b440f573def480adaf4703f8b91/README.md#chat-with-llm) · [Advanced RAG: Semantic Chunking](https://github.com/dlops-io/llm-rag/blob/e17a39f35bc07b440f573def480adaf4703f8b91/README.md#advanced-rag-semantic-chunking-semantic-splitting) · L06 preview: [Agents](https://github.com/dlops-io/llm-rag/blob/e17a39f35bc07b440f573def480adaf4703f8b91/README.md#agents) · latest README on [`main`](https://github.com/dlops-io/llm-rag#building-a-rag-system-with-vector-db-and-llm) · last year's [`pipenv` branch](https://github.com/dlops-io/llm-rag/tree/pipenv)
- Ed lesson: [L05 · Introduction to RAG](https://edstem.org/us/courses/97373/lessons/182195/) · course [tutorials page](https://harvard-iacs.github.io/2026-AC215/tutorials_demo/)
- Colab: none for L05. The L06 [Cheese Quiz (Colab)](https://colab.research.google.com/drive/14UKW-Z7kFPuCwVqyUFcLxeA1KF70fwfm?usp=sharing) is cited in §7.
- Web tools (optional, Chrome; not in the repo, see §9 Q5): [chunkviz](https://ac215-llm-rag.dlops.io/chunkviz) · [chromaui](https://ac215-llm-rag.dlops.io/chromaui) · [chat](https://ac215-llm-rag.dlops.io/chat) · [agent](https://ac215-llm-rag.dlops.io/agent)
- Previous lecture: [L04 · Containers II-b](L04-containers-2b-flexible-workflow-ports.md) (Compose networks, DNS by container name, published ports, secrets mounted at `/secrets`)
- Next lecture: [L06 · LLM: Agents I](L06-agents-1.md) (the README's Agents section on this same repo: `--agent` and function calling)
- Referenced in §7: [L01 · Virtual Environments and Virtual Machines](L01-vms-venvs.md) · [L02 · Containers I](L02-containers-1.md) · [L03 · Containers II](L03-containers-2-mega-pipeline.md) · [L07 · LLM: Agents II](L07-agents-2-harness.md) · [L08 · LLM: Finetuning](L08-llm-finetuning.md) · [L10 · Connecting to the Cloud: Networking, Authentication & Storage](L10-cloud-connect-cheese-app-v0.md)
