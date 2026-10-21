# L06 · LLM: Agents I — study guide

[Ed lesson](https://edstem.org/us/courses/97373/lessons/166030/) · Tutorials: [`dlops-io/llm-rag`](https://github.com/dlops-io/llm-rag) `main` @ [`e17a39f`](https://github.com/dlops-io/llm-rag/tree/e17a39f35bc07b440f573def480adaf4703f8b91) (README section "Agents", plus the L05 steps it stands on; tree identical to [`7a3c66b`](https://github.com/dlops-io/llm-rag/tree/7a3c66b777e7d4048b45f59b7223422325f1a281)) and [`dlops-io/llm-agent-google-adk`](https://github.com/dlops-io/llm-agent-google-adk) `main` @ [`f89faa7`](https://github.com/dlops-io/llm-agent-google-adk/tree/f89faa79de744f6a046e30dff24b3b6f1d73720b) (the whole README and the module READMEs) · Colab: [Cheese Quiz](https://colab.research.google.com/drive/14UKW-Z7kFPuCwVqyUFcLxeA1KF70fwfm?usp=sharing) · [Travel Planner](https://colab.research.google.com/drive/1I_jJEHJsVkGxNoSC1c4wEoVF2QL6vCVY?usp=sharing) · [Cheese Newsletter · Harness](https://colab.research.google.com/drive/1nnHrJ4Si3tpgUQl6HqlcwxKymV1-ecPv?usp=sharing) · Video: [AC215 · L06 follow-along](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l06-agents-1) · Made from the verified digest and real terminal captures, 2026-10-13

## 中文速览

- **做什么：** L05 里 retrieval 是你写死的 top-10；L06 让 **LLM 自己决定怎么 retrieve**，分三步：(1) **手写**：在 `llm-rag` container 里跑 `python cli.py --agent --chunk_type char-split`，Gemini 3.1 Flash-Lite 拿到两个手写的 function declaration（按 author 搜一本书 / 搜全部的书），你的 Python 去查 L05 建好的 `char-split-collection`，再调第二次 Gemini 写答案；(2) **framework**：在本机用 uv 跑 Google ADK（`uv run adk web`），六个 module：SequentialAgent travel planner、LiteLLM、MCP filesystem tools、FastAPI、custom agent、RAG；(3) **harness**：三个 OpenAI Colab：Cheese Quiz（LLM → workflow → agent → context → tools/MCP → 六个 agent 的 Guild）、Travel Planner、Cheese Newsletter。2026-10-18 的 captures 没有任何 key：Docker、Chroma、uv、ADK web server 和两个 MCP server 是真跑的，model 的回答都来自 staff 存下来的 output。
- **Idea 1 · 谁握方向盘：** workflow 的 `if`/`for` 写在你的 code 里；agent 的 control flow 由 model 决定，你的 code 只是一个听话的 loop。Cheese Quiz 三次跑的都是同一个 `gpt-4o`，变的只是 loop 和 tools。
- **Idea 2 · function calling：** model 只"写" call（`{name, args}`），你的 code 才"执行"它。call 1 的 request 里有 `"toolConfig": {"functionCallingConfig": {"mode": "ANY"}}` 和 `"temperature": 0.0`：`mode="any"` 是**强制** function call，model 只能选搜哪本书，不能选搜不搜。call 2 送回三样东西：question、model 自己那一轮（原封不动，带 `thoughtSignature`）、你的 `functionResponse`（10 个 chunk 拼成一个 string），这次没有 `toolConfig`。Gemini 从来没碰过你 `localhost` 上的 ChromaDB；`cli.py:40-58` 的 system instruction 定义了，但两次 call 都没送出去。
- **Idea 3 · agent loop：** 停止规则是 model 回了一个没有 function call 的 reply（ADK 的 `is_final_response()`）；framework 再加一个上限：OpenAI Agents SDK 的 `max_turns`（notebook 设成 12，超过就 `MaxTurnsExceeded`），Microsoft Agent Framework 的 `max_iterations`（Newsletter 设成 16）。`llm-rag --agent` 不是 loop，只跑一圈：一次强制的 tool call 加一次回答。lecture 里的 dynamic control 就是 framework 替你写的这个 loop。
- **Idea 4 · state 和 MCP：** ADK 里 `output_key="x"` 把 agent 的 final text 写进 session state 的 `x`，下一个 agent instruction 里的 `{x}` 会被替换成这个值；sub-agents 之间不直接传 message。`adk web` 把每个 agent 的 sessions 存在 `<agent>/.adk/session.db`。MCP 把 tool 做成可插拔的 server：ADK 用 `npx` 起一个 stdio child process（filesystem server 提供 14 个 tool，`tool_filter` 只放进来 3 个），Cheese Quiz 连一个 remote HTTP server（browser 直接 GET 拿到 406，不代表 server 挂了）。MCP 不给 model 网络权限：跟 server 说话的是你的 client process。
- **Idea 5 · harness：** model 选 action，Python 决定这个 action 算不算数。Travel Planner 的价格全部由 Python 算（6,000 的 budget 里用 2,690 dollars，可以手算验证），`finalize_itinerary` 只产生 pending proposal，要下一轮 human 输入 "yes" 才 approve；Newsletter 的成功 = 有 `receipt` 而且 HTML file 真的在 disk 上，不是 model 说 "done"。只写在 prompt 里、没有 code 检查的规则（"no embedded URLs"）靠不住：saved run 的 HTML 里照样出现了 `Promotion URL: https://…`。
- **最费时间的坑：** ① ADK repo 没有 lockfile，README 的 `uv sync` 在一台没有 Python 的 laptop 上（或 uv 已经装过 3.15 时）会选 CPython 3.15.0，然后因为 `onnxruntime` 没有 cp315 wheel 直接失败：先 `uv python pin 3.13` 再 `uv sync`（今天装的是 google-adk 2.12.0，`.venv` 1.6 GB，Linux PC 上另加约 3 GB CUDA packages）。② dev UI 里选 `1-baseline` 报 `Invalid agent name`：agent 名必须是 Python identifier；pin `google-adk<1.28`（1.27.5）也没用，只是换成 `Invalid app name`；能用的办法是改 folder 名：`mv 1-baseline baseline; mv 3-mcp-tools mcp_tools; mv 5-custom-agent custom_agent`。③ code 的 fallback `gemini-2.0-flash` 已经 shut down，`.env.example` 的 `gemini-2.5-flash` 只开放给以前用过的人：在 root `.env` 里写 `GEMINI_MODEL=gemini-3.1-flash-lite`，也别照 module README 再 `cp .env.example .env`（ADK 只 load 离 agent 最近的那一个 `.env`）。④ port 8000：`adk web` 和 llm-rag 的 ChromaDB 都要它，`exit` container 之后 `llm-rag-chromadb` 还在跑，要 `docker compose down`，或者 `uv run adk web --port 8080`。另外：README 的 `cd google-adk-tutorial` 这个 folder 不存在（是 `cd llm-agent-google-adk`）；ADK 2.12 第一次 `adk web` 会问 telemetry，直接按 Enter 等于 yes（之后可以 `adk telemetry disable`）。
- **先有 index，再跑 agent：** README 的 Agents section 没写它需要 L05 的 collection；fresh clone 上 `--agent` 在 `cli.py:429` 就报 `NotFoundError: Collection [char-split-collection] does not exist`，还没调用 Gemini。先 chunk、embed、`python cli.py --load --chunk_type char-split`（load 完一共 8,248 个 chunk，Tolminc 那本只占 24 个）。别拿 `out.txt` 对答案：它的答案（Soča Valley、transhumance）是用 2026-09-22 改写 Tolminc 那本书之前的旧 index 跑的，今天的书讲的是 Mara 的故事；2026-09-22 之前 load 过的要重建。
- **做完要删：** llm-rag `exit` 之后在 `llm-rag/` 里 `docker compose down`（index 留在 `docker-volumes/chromadb`）；`adk web` / `uvicorn` 用 Ctrl+C；不用了就删掉 1.6 GB 的 `.venv`；`<agent>/.adk/` 里的 sessions 没被 `.gitignore` 盖住，别 commit（在 `.gitignore` 加一行 `.adk/`）；6-rag 的 ChromaDB `docker compose down`（加 `-v` 连 volume 一起删）；做了 `6-rag/1-vertex-rag-engine` 的话，用 `setup_corpus.py` 的 option 5 删掉 corpus（要打完整的 `yes`），隔天看一下 billing；三个 Colab 都 *Runtime → Disconnect and delete runtime*；service-account key 留在 `llm-rag/` 旁边的 `secrets/`，AI Studio 和 OpenAI 的 key 课程结束后删掉或设限额。
- **Lecture slides：** 老师的 Lecture 6 slides（56 页）和这份 guide 各节怎么对应、做 tutorial 需要的 10 个 lecture ideas，以及 slides 和今天的 repo/notebook 不一样的 7 处，都在下面的 [Lecture slides](#lecture-slides)。最要紧的两处：① slide 26 说 agent 会自己一直跑到任务完成，但 `llm-rag --agent` 只有一次强制的 tool call 加一次回答，没有 loop，loop 要到 ADK 和 notebook 里才有；② slides 10、13、33 里 model 可以决定**不** retrieve，而 `mode="any"`（`cli.py:449`）逼 Gemini 每次都 call tool：它只能选搜哪本书，不能选搜不搜（§8 的 B2 把这个选择还给它）。

## At a glance

**What you build.** An agent that lets Gemini choose how to search your L05 ChromaDB collection through function calling (`python cli.py --agent` inside the `llm-rag` container), then the same idea with Google's Agent Development Kit run locally (`uv run adk web`: a sequential travel planner that shares session state, MCP filesystem tools, a FastAPI wrapper, custom routing agents) and in three OpenAI Colab notebooks that climb from a single LLM call to a six-agent quiz guild. The last two notebooks add a harness, where Python owns the arithmetic, a human approval gate and the definition of success (a receipt for a file on disk).

**Time needed** (estimate).
- Cheese Quiz: about 1 h (dozens of model calls; the two guild runs take a while).
- llm-rag Agents: 15-30 min if L05's `char-split-collection` is current. The first `sh docker-shell.sh` builds the image (40.5 s in the captures, after the base-image download); loading the 8,248 stored vectors took about 10 s; embedding them again needs Vertex AI and a few minutes.
- ADK repo: 1-1.5 h for the root README, `1-baseline` and `3-mcp-tools`. The first successful `uv sync` builds a 1.6 GB `.venv` (PyTorch comes with `sentence-transformers`); on a Linux PC uv also adds about 3 GB of CUDA packages. Modules 2 and 4-6 add about an hour.
- Travel Planner and Newsletter: about 30-45 min each.
- The follow-along video: about 30-35 minutes, in two parts (part 1: what an agent is, and function calling by hand with llm-rag; part 2: ADK, MCP, many agents and the harness).
- Exercises: 1-2 h more.

**Prerequisites.**
- L05 done: the `llm-rag` clone next to `secrets/llm-service-account.json` (the service account has the Vertex AI User role, now listed as "Gemini Enterprise Agent Platform User"), the Vertex AI API enabled, `docker-shell.sh:7` pointing at your project, and a loaded `char-split-collection` (or the time to rebuild it, §4 B2).
- Docker with Compose v2, `uv`, Node.js + npm (`npx`), Git. You do not need a Python of your own: uv downloads one (§4 C1).
- Keys: a Google AI Studio API key (ADK repo) and an OpenAI API key with billing (Colab secret `OPENAI_API_KEY`; also ADK `2-litellm`).
- Background: Compose networks, ports and mounted secrets (L04); chunking, embeddings and the vector DB (L05); uv, `pyproject.toml` and `.python-version` (L01).

**What it costs.** Small, but not zero (§2). Each `--agent` question makes two Gemini calls and one embedding call (247 + 1,269 tokens in the staff's recorded run). Pennies for Vertex embeddings if you rebuild the collection. Cents to low dollars of OpenAI per full notebook run; the hosted web search tool is billed per call on top of tokens. The Gemini API free tier may cover the ADK exercises. The optional Vertex AI RAG Engine corpus (`6-rag/1-vertex-rag-engine`) stays in your project until you delete it.

**Tear down, exactly** (§2):
1. llm-rag: `exit` the container shell, then `docker compose down` in `llm-rag/`. `exit` alone leaves `llm-rag-chromadb` running and holding port 8000 (captured, G4). The index stays on disk in `docker-volumes/chromadb`.
2. `adk web` / `uvicorn`: Ctrl+C.
3. ADK repo: don't commit the sessions in `<agent>/.adk/` (add `.adk/` to `.gitignore`, G22); delete the 1.6 GB `.venv` when you are done with the course (`uv sync` rebuilds it).
4. `6-rag/2-custom-chromadb-rag`: `docker compose down` (add `-v` to also delete the `chroma_data` volume).
5. `6-rag/1-vertex-rag-engine`, if you ran it: `uv run python setup_corpus.py`, option `5. Delete corpus`, then the full word `yes`; check the console's RAG Engine page and the billing report a day later (§8 C7).
6. Each Colab notebook: *Runtime → Disconnect and delete runtime*.
7. Keys: keep the service-account key in `secrets/` beside `llm-rag/`, never inside; rotate or delete keys you no longer need (IAM → Service accounts → Keys; AI Studio; OpenAI).

<details>
<summary><b>Versions and sources this guide was checked against</b></summary>

- **Lecture-to-tutorial mapping:** the course-site source `2026-AC215/tutorials_demo.md:83-98`, at site commit `12dfbffcf117b5e67c1784863d7c31adf53fd365` (2026-10-08). The Ed lesson itself could not be opened; the lecture slides are digested in [Lecture slides](#lecture-slides).
- **Repo 1:** `dlops-io/llm-rag`, branch `main`, commit `e17a39f35bc07b440f573def480adaf4703f8b91`, committed 2026-10-07 21:34:23 -0400 ("Merge pull request #2 from obalatel/revert-1-demo-podcast"), still the head of `main` on 2026-10-18. That merge reverts a same-day "demo podcast" merge, so the tree is byte-identical to `7a3c66b` (2026-10-06, "updated for localhost").
  - Other branches, not used here: `pipenv` `0b671ede29d4b37ecd530da493485b015adad4da` (2025-03-04, the old `vertexai` SDK version), `demo-podcast` `96fef434536f6e58a5bd027f49916fc98cd467e1` (2026-10-07, the restructure that was merged and then reverted on `main`), `revert-1-demo-podcast` `b77a556560befb87e241d39965d68f2e77a6d2ad` (2026-10-07, the PR branch of the revert; its tree is identical to `main`).
  - README section for this lecture: [`#agents`](https://github.com/dlops-io/llm-rag?tab=readme-ov-file#agents) (`llm-rag/README.md:242-271`).
  - It stands on L05's sections *Prerequisites* and *Setup GCP Service Account* (`README.md:45-69`), *Run LLM RAG Container* (`:75-85`) and *Chunk Documents* through *Load Embeddings into Vector Database* (`:91-165`): the agent queries the collection you built there.
  - Quoted for comparison only: `68e0bde` (2026-10-07; the staff's committed chunk and embedding files under `llmrag/outputs/`, still in `main`'s history) and `96d5fd7` (2026-09-20; the instructor's book before `85bba32` rewrote it).
- **Repo 2:** `dlops-io/llm-agent-google-adk`, branch `main` (its only branch), commit `f89faa79de744f6a046e30dff24b3b6f1d73720b`, committed 2025-12-02 14:02:38 -0500 ("fix bugs and clean readme"), still the head on 2026-10-18. It has **no lockfile**: `uv.lock` is git-ignored (`llm-agent-google-adk/.gitignore:34`).
- **Colab notebooks** (local JSON copies downloaded 2026-10-17; Colab links at `2026-AC215/tutorials_demo.md:88, 94, 98`; notebooks have no commit):
  - `L06_cheese_quiz.ipynb`, "Cheese Quiz". 79 cells. OpenAI API + OpenAI Agents SDK + FastMCP. Last saved run: 2026-09-23 (the tool outputs carry `generated_at: 1790132526`); cell 57's saved banner says `FastMCP 4.0.5`.
  - `L06_travel_planner.ipynb`, "Travel Planner". 31 cells. OpenAI Agents SDK `0.3.2`.
  - `L06_cheese_newsletter_harness.ipynb`, "Cheese Newsletter - Harness". 33 cells. Microsoft Agent Framework. Last saved run: 2026-09-20 13:27 UTC (footer of the saved HTML).
  - Cell numbers in this guide are 0-based indices in the `.ipynb` JSON. Colab shows no numbers, so each cell's `# @title` or first line is given too.
- **Terminal captures (the strongest evidence in this guide).** On 2026-10-18 (22:58-23:33 UTC), every README command of the llm-rag Agents section and of the ADK root README was run as written, plus the extras in §4, on fresh machines and **without any key** (no Google Cloud, no AI Studio, no OpenAI):
  - *llm-rag laptop:* Linux x86_64, user `student`, workspace `~/AC215` holding `llm-rag/` and an empty `secrets/`; Docker Engine 29.8.2 (API 1.56), Docker Compose v5.6.0, git 2.54.0. The `llm-rag-cli` image built from the tutorial's `Dockerfile`: Python 3.12.15, uv 0.13.1, chromadb 1.1.0, google-genai 1.39.1, google-auth 2.41.1; Chroma server `chromadb/chroma:latest` as pulled that day. `--embed` needs Vertex AI, so the staff's committed embeddings (`68e0bde`, made from today's book) stood in for it; the `--load` and everything after it are real runs.
  - *ADK laptop:* Debian 12 (bookworm), x86_64, **no Python of its own**, uv 0.13.1, git 2.39.5, Node.js v24.22.0 with npm 11.19.1. After `uv python pin 3.13`, `uv sync` installed CPython 3.13.16, google-adk 2.12.0, google-genai 2.31.0, litellm 1.106.0, fastapi 0.141.1, uvicorn 0.54.0, mcp 2.3.0, chromadb 1.5.9, sentence-transformers 6.1.0, onnxruntime 1.31.0 and torch 2.14.1 (the capture used PyTorch's CPU-only wheel to save disk; a Mac gets no CUDA packages either); `.venv` 1.6 GB. `npx` fetched `@modelcontextprotocol/server-filesystem` 1.0.0.
  - *Remote MCP server* (Cheese Quiz cell 54): spoken to with `curl` from the ADK laptop.
  - Files: [`assets/terminal/`](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l06-agents-1/assets/terminal) (`laptop/`, `cli-container/`, `adk-laptop/`, `mcp-remote/`, and `expected/` for the README text, the staff's `out.txt` and the notebooks' saved outputs), with `capture.sh` and `run_steps.sh`; provenance in `ASSETS.md` in the same video folder. File names with `x-` are extras, not README steps.
- **Exercise checks** (2026-10-19), in throwaway containers with the tutorials' own lockfile and versions, with hand-written stand-in replies where a model reply was needed (never model output): [`assets/exercise-checks/`](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l06-agents-1/assets/exercise-checks). They supply the module 4, router, MCP filter, `.env`, `.adk/` and telemetry results quoted in §4, §6 and §8.
- **Third-party code read to check claims** (downloaded wheels, unzipped, read only): `google-adk` 1.19.0 (current on the repo's last commit date), 1.27.5, 1.28.0, 2.11.0 and 2.12.0 (released 2026-10-13; what `uv sync` resolves on 2026-10-18 for Python ≥ 3.11, while Python 3.10 gets 2.11.0); `google-genai` 1.39.1 (pinned by llm-rag's `uv.lock:496-497`); `chromadb` 1.1.0; `openai-agents` 0.3.2, 0.22.3, 0.23.1 and 0.24.0; `fastmcp-slim` 4.1.0; the npm package `@modelcontextprotocol/server-filesystem` 1.0.0. Google's Gemini API deprecation page and OpenAI's deprecation page were re-checked on 2026-10-18.
- **Method:** every repo `path:line` was checked with `sed -n` / `grep -n` against the pinned commits; the digest was adversarially verified on 2026-10-18. Claims reasoned out but not run are marked *(reasoned, not run)*. **Where the digest and the captures disagree, this guide follows the captures:** the digest's fix for G1, pinning `google-adk<1.28`, does **not** make `1-baseline` runnable, while renaming the folders does (G1); on a machine with no Python the README's `uv sync` fails first on CPython 3.15, which the digest's resolution check (run on a Python 3.12 image) did not meet (G20); ADK 2.12's dropdown lists seven entries, not the digest's four (§4 C2); the wording of ADK's errors and of the remote MCP server's replies is copied from the captures. (The earlier version of this guide said `uv sync` installs google-adk 2.11.0; on 2026-10-18 it was 2.12.0.)
- **Path convention:** `cli.py`, `agent_tools.py`, `out.txt`, `docker-*.sh` and `docker-compose.yml` without a prefix are in `llm-rag/`; module paths such as `1-baseline/agent.py` are in `llm-agent-google-adk/` at the pinned commit (after the rename in §4 C2 your copies are `baseline/`, `mcp_tools/`, `custom_agent/`). A bare `README.md` is the README of the repo the surrounding part is about (llm-rag in Part B, the ADK repo in Part C). Third-party paths start with the package name and version, notebook references with the notebook name and cell number.

</details>

## Lecture slides

The instructor's deck for this lecture is *Lecture 6: LLM: Agents I*, 56 slides. Slide numbers are PDF page numbers. The slides are not reproduced here; what follows is in our own words. The deck has no code: it teaches with box diagrams and annotated screenshots of a chat assistant. The full slide digest and the cross-check with the video live in the Explainer_Videos repo, in `videos/ac215-l06-agents-1/SLIDES.md`.

**Map**

| This guide | Slides |
|---|---|
| At a glance; §1 What you build | 20–22 (why agents), 13–14 (agentic RAG), 26–27 (definition, anatomy) |
| §3.1 LLM vs workflow vs agent; §4 Part A4 | 4–5 (plain LLM), 16–18 (the multi-call "Reasoning LLM"), 26–27 |
| §3.2 Function calling; §4 Part B; checklist *llm-rag · Agents* | 13–14, 39, 51 |
| §3.3 The agent loop | 26, 37–41 (the decision maker's cycle; dynamic control) |
| §3.4 Context engineering; §4 Part A5 | 36, 40–41 (the full topic is in Lecture 7, slides 11–18) |
| §3.5 Tools, schemas and MCP; §4 Parts A6–A7, C5 | 51–53 |
| §3.6 ADK's runtime objects; §4 Parts C1–C3 | 35–36, 40–41 (the blocks you configure) |
| §3.7 Multi-agent patterns; §4 Parts A8, C7 | 38 (planner), 44–49 (a research agent with sub-agents), 51 (orchestration tools) |
| §3.8 The harness; §4 Parts D–E | 20–22 (the travel planner), 36–37 (success criteria, guardrails) |
| §8 B2 (let the model skip retrieval); B3 (turn the two calls into a capped loop) | 10, 13, 33 (deciding whether to retrieve); 26, 37–40 (running until done) |
| §2 costs and teardown, §5 code tour, §6 gotchas, the other exercises, §9 errata | none (tutorial-only) |
| — (background) | 6–12 (L05's RAG variants recapped), 28–33 and 42–49 (the chat-assistant demos) |

**Lecture ideas you need for this tutorial**
1. A plain LLM or RAG cannot act: it has no contact with live systems, no tools that change anything, and no autonomy to adapt. Agents add these (slides 20–22).
2. Agentic RAG puts an LLM in front of retrieval to choose how to retrieve. `llm-rag --agent` is exactly this, with a menu of two search tools (slides 13–14).
3. An agent is an LLM with instructions and tools that keeps running on its own until the task is done (slide 26).
4. An agent has five parts: LLM core, instructions, dynamic control, tools, memory. You configure four of them; dynamic control emerges from the model plus the prompt, and in code it is the framework's loop (slides 27, 37, 41).
5. Choosing the LLM core is a design decision: the model, its sampling parameters (`temperature`, top-p, max tokens) and the response format. Here that is `GEMINI_MODEL`, `temperature=0` and the JSON schema (slide 35).
6. Instructions give the core a role, constraints, goals with success criteria, and an output format (slide 36).
7. The decision maker cycles through a planner, tools and memory. That cycle is the agent loop that ADK and the Agents SDK run for you (slides 37–40).
8. Tools are functions with schemas. The agent must pick the right one, format its inputs and interpret its outputs. There are three families: data tools (search), action tools (change something) and orchestration tools (hand work to another agent) (slides 39, 51).
9. MCP replaces one custom integration per tool with one standard protocol: the agent is a host with clients, and each external system sits behind a server (slides 52–53).
10. An agent can direct sub-agents: a lead agent makes a plan and sends several search agents out in parallel, then writes one report (slides 44–49).

**Where the slides and today's tutorial differ** (for what the code does, the repos at `e17a39f` / `f89faa7` and the notebooks decide; the "memory" and "reasoning" items are differences of wording)
- Slide 26's agent runs until the task is done. `llm-rag --agent` makes one forced tool call and one answer, with no loop (§3.3). The loop arrives with ADK and the notebooks.
- On slides 10, 13 and 33 the model may decide not to retrieve (Self RAG's retrieval decision, agentic RAG's menu, the chat assistant skipping web search). `mode="any"` (`cli.py:449`) forces a tool call every time, so the llm-rag agent picks which search, never whether (§8 B2).
- Slide 40's memory lasts across sessions. The ADK README uses "Memory" for per-session state (E12), and the Travel Planner's `SQLiteSession` ends with the runtime.
- Slide 53 draws one "MCP" box in front of every server. In code each server is its own connection: an HTTP URL, a thread on port 8001, an `npx` child process over stdio (§3.5).
- Slides 20–22's planner books a Paris trip through live systems and replans for weather or delays. The notebook uses a three-city mock catalog with no weather tool and books nothing; ADK's `1-baseline` has no tools at all, so its prices are the model's guesses.
- "Reasoning" means three things on the slides: a multi-call system (16–18), the model's own thinking (31–33) and the LLM core (27). The Cheese Quiz's `ReasoningLLM` is the first kind, with Python ordering the calls (§3.1).
- Slides 36–37 leave success criteria and guardrails to the agent: the instructions state them (36) and the decision maker weighs them (37). The harness notebooks check them in code (the approval gate, the receipt), and a rule left only in the prompt slipped through (E15; §3.8).

The 2026-10-18 captures confirm the first, second, fourth and fifth points: the two requests `--agent` builds are its whole conversation with Gemini, and call 2 carries no tool config; call 1's request carries `"mode": "ANY"`; the filesystem server runs as a child process over stdio, while the remote server answers over HTTP with its own session id; and the Travel Planner's saved run books nothing ("Nothing has been booked"), while the agent tree `adk web` loads for `baseline` (the renamed `1-baseline`) holds three `LlmAgent`s and no tools (§4 B3, C3, C5, D4).

## Command checklist

Commands in backticks are exactly as the README or notebook writes them (placeholders kept; multi-line commands are joined onto one line). Plain items are console clicks, file edits or notebook cells (0-based cell index, plus the cell's `# @title` or first line). Items marked *(extra)* are not in the tutorial; they come from §4, where the real output of every captured command is shown. Where a command fails today, it stays as written and a note gives the working variant. The order follows the course site: Cheese Quiz → llm-rag Agents → ADK → Travel Planner → Newsletter. All `python cli.py …` commands run **inside** the container that `sh docker-shell.sh` opens (prompt `app@<id>:/app$`); items marked "host" run in a second terminal on your laptop. The captures used `~/AC215` as the folder that holds the clones; use yours.

### Cheese Quiz (Colab)

*(Tutorial 1a; §4 Part A. Not run here: no OpenAI key. The checkpoints are the staff's saved outputs.)*
- [ ] Open the [Cheese Quiz](https://colab.research.google.com/drive/14UKW-Z7kFPuCwVqyUFcLxeA1KF70fwfm?usp=sharing) and click *File → Save a copy in Drive* (cell 1); the tab title starts with "Copy of".
- [ ] Colab left sidebar → 🔑 *Secrets* → add `OPENAI_API_KEY` → toggle *Notebook access* (G15).
- [ ] `!pip -q install fastmcp openai-agents > /dev/null 2>&1` — cell 10 (`# @title Install Packages`): unpinned, output hidden. If cell 11 cannot import `agents` or `fastmcp`, rerun it without `> /dev/null 2>&1` (G16).
- [ ] Cell 11 (`# @title Imports`) and cell 12 (`# @title Set Up OpenAI Key`) — reads `userdata.get('OPENAI_API_KEY')` and builds `client = OpenAI(...)`.
- [ ] `!gdown 1dxvxGZZ-yYEEHQuaoP4HwaYxsbOC4XEh` — cell 13 (`# @title Download`): saved output `To: /content/quiz-schema.json` … `2.10k`.
- [ ] `!gdown 1OykEQrwa5cnZgPIVrOdnDeq3txots3H0` — cell 13: saved output `To: /content/quiz-ui.html` … `10.8k`. Cell 62 needs both files.
- [ ] Cells 17-21 (`# Define the LLM model and question`, `# @title Define BaseLLM`, `# Initialize`) — one `chat.completions.create` call; saved output `Tokens: 293, Time: 2.81s`.
- [ ] Cells 24-26 (`# @title Define ReasoningLLM`, `# Initialize`, `steps = reasoning_result["reasoning_steps"]`) — 11 calls per question; eleven `🧠 BaseLLM: Making single API call...` lines, `Sub-questions explored: 4`, `Total tokens: 701, Time: 39.34s`. The token total is approximate.
- [ ] Cells 30-31 (`# @title Define SimpleAgent`, `# Initialize`) — an Agents-SDK `Agent` with `WebSearchTool`; saved output ends `Tools used: 1` and `Time: 13.29s`. "Tools used: 1" counts configured tools, not calls.
- [ ] Cells 37-44 (`model = "gpt-4o"`, `# @title Step 1: Basic prompt` … `# @title Step 7: Structured Output`) — seven context layers. Step 2 (cell 39, lines 18-21) swaps the `user` and `system` roles (E1).
- [ ] Cells 46-50 (`# Define the LLM model and question`, `# --- Fun Facts data ---`, `# System Prompt`, `# If you want to list all the tools called in the agent run`) — `@function_tool(name_override="pavlos_fun_fact_tool")`; saved output `1. pavlos_fun_fact_tool  args={}` three times.
- [ ] Cell 54 (`# MCP Server`) — `MCPServerStreamableHttp` to `https://pavlos-fun-facts.dlops.io/mcp`, passed as `mcp_servers=`.
- [ ] `curl -si --suppress-connect-headers https://pavlos-fun-facts.dlops.io/mcp | sed 's/^\(mcp-session-id: \).*/\1<id>/' | head -12` — *(extra, host)* what a browser gets: `HTTP/2 406`, "Client must accept text/event-stream". The server is up; it speaks MCP, not web pages. The `initialize`, `tools/list` and `tools/call` requests are in §4 A7.
- [ ] Cells 57-59 *(optional)* — your own FastMCP server in a daemon thread at `http://127.0.0.1:8001/mcp`; expect `"POST /mcp HTTP/1.1" 200 OK` and `Pavlos Fun Fact Tool Called`. Do not rerun cell 57 in the same runtime (§8 C6).
- [ ] Cells 62-71 (`# @title Some Utils`, the specialists, `# Agents-as-tools for orchestration`, `orchestrator = Agent(`, `async def run_guild`) — Pydantic contracts, `.as_tool(...)`, `Runner.run(orchestrator, prompt, max_turns=12)`.
- [ ] `await run_guild("Cheeses from Star Wars")` — cell 75: an interactive quiz widget (the saved run also printed three `ERROR:openai.agents:Error getting response` lines).
- [ ] `await run_guild("Greek cheeses")` — cell 77: a second quiz.

### llm-rag · Prerequisites and Setup GCP Service Account (from L05)

*(`README.md:45-69`; §4 Part B0. Skip what you already did in L05.)*
- [ ] `git clone https://github.com/dlops-io/llm-rag.git` — `README.md:48` asks for a clone ("Cloned this repository to your local machine") without printing the command; captured: `Cloning into 'llm-rag'...`.
- [ ] Console: service account `llm-service-account` with **Storage Admin** and **Gemini Enterprise Agent Platform User** ("Vertex AI User" in older projects), a JSON key copied into `secrets/` and renamed `llm-service-account.json` (`README.md:52-62`).
- [ ] `mkdir secrets; ls` — *(extra)* `llm-rag  secrets`: the two folders side by side, as `README.md:64-69` draws them (G8).

### llm-rag · Run LLM RAG Container (from L05)

*(`README.md:75-85`; §4 Part B1)*
- [ ] `cd llm-rag` — "Make sure you are inside the `llm-rag` folder and open a terminal at this location" (`README.md:79`; the command itself is not printed).
- [ ] `git log --oneline -1` — *(extra)* `e17a39f Merge pull request #2 from obalatel/revert-1-demo-podcast`, the pinned commit (or a newer one).
- [ ] Update `GCP_PROJECT` to your own project ID in `docker-shell.sh` (`README.md:80`; line 7: replace `"ac215-project"`).
- [ ] `git diff docker-shell.sh` — *(extra)* exactly one changed line, `export GCP_PROJECT="…" # CHANGE TO YOUR PROJECT ID`.
- [ ] `sh docker-shell.sh` — Compose creates `llm-rag-network` and `llm-rag-chromadb`, prints a harmless `pull access denied for llm-rag-cli` (or `failed to resolve reference … not found` on Docker Desktop), builds the image, then the banner (`Python version: Python 3.12.15`, `UV version: uv 0.13.1 …` at the time of recording) and a prompt like `app@abcf218747d0:/app$`.
- [ ] `docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}'` — *(extra, host)* the one-off `llm-rag-llm-rag-cli-run-<id>` and `llm-rag-chromadb` with `0.0.0.0:8000->8000/tcp`.

### llm-rag · Chunk, Embed, Load (from L05: only if your `char-split-collection` is missing or older than 2026-09-22)

*(`README.md:91-165`; §4 Part B2. The agent reads `char-split-collection` only; the README's `recursive-split` lines are L05's and optional here.)*
- [ ] `python cli.py --chunk --chunk_type char-split` — `README.md:103`.
- [ ] `python cli.py --chunk --chunk_type recursive-split` — `README.md:109`; optional for L06.
- [ ] `python cli.py --embed --chunk_type char-split` — `README.md:129`; needs your key (Vertex AI, paid).
- [ ] `python cli.py --embed --chunk_type recursive-split` — `README.md:130`; optional for L06.
- [ ] `python cli.py --load --chunk_type char-split` — `README.md:151`: `Number of files to process: 11` … `Finished inserting 24 items into collection 'char-split-collection'` for the Tolminc book; 8,248 chunks in all (captured, on the staff's committed embeddings).
- [ ] `python cli.py --load --chunk_type recursive-split` — `README.md:152`; optional for L06.
- [ ] `python cli.py --get --chunk_type char-split` — *(extra)* `Results: {'ids': ['1021665fac86c5a5-0', …], …, 'metadatas': [{'author': 'Bob Brown', 'book': 'The Complete Book of Cheese', 'year': 2024}, …`: the collection answers. No model call, so it works without a key.
- [ ] `git show --stat --format='%h %ad %s' --date=short 85bba32; head -4 'input-datasets/books/Tolminc Cheese.txt'` — *(extra, host)* the 2026-09-22 commit rewrote `Tolminc Cheese.txt` and added `out.txt`; today's book starts `# Tolminc: A Cheese, a Valley, and the Art of Waiting` (G7).

### llm-rag · Agents

*(`README.md:242-271`; §4 Parts B3-B6)*
- [ ] `python cli.py --agent --chunk_type char-split` — call 1 forces a function call (`mode="any"`), your code queries Chroma, call 2 writes the answer. The printout has the structure of `out.txt` but not its content (G7).
  - Note: on a fresh clone it fails at once with `chromadb.errors.NotFoundError: Collection [char-split-collection] does not exist` (`cli.py:429`, before any Gemini call; captured): load the collection first (section above, G6).
  - Note: without a key in `secrets/` it prints the question, then fails at the first model call with `google.auth.exceptions.DefaultCredentialsError: File /secrets/llm-service-account.json was not found.` (`cli.py:441`; captured, G5).
- [ ] *(extra)* Print call 1's request without sending it, check what `mode="any"` becomes, run the staff's recorded call through the dispatcher, and count the chunks per enum author: four scripts typed at the container prompt, in §4 B3 and B2.
- [ ] *(optional)* Try the [Cheese Agent Tool](https://ac215-llm-rag.dlops.io/agent) (`README.md:268`; the README recommends Chrome).
- [ ] `curl -s -o /dev/null -w '%{http_code} %{content_type}\n' https://ac215-llm-rag.dlops.io/agent` — *(extra, host)* `200 text/html; charset=utf-8`: the hosted tool was up on 2026-10-18.
- [ ] `exit` — *(extra)* leaves the one-off container, which is removed (`--rm`).
- [ ] `docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}'` — *(extra, host)* `llm-rag-chromadb` is **still up** on port 8000 (G4).
- [ ] `docker compose down` — *(extra, host, in `llm-rag/`)* two harmless `WARN[0000] The "…" variable is not set. Defaulting to a blank string.` lines, then `Container llm-rag-chromadb Removed` and `Network llm-rag-network Removed`. The data stays in `./docker-volumes/chromadb`.
- [ ] `git status --short` — *(extra, host)* ` M docker-shell.sh` only: your Project ID edit.

### llm-agent-google-adk · Getting Started

*(ADK `README.md:72-107`; §4 Part C1)*
- [ ] `cd ~/AC215` — *(extra)* wherever you keep your clones; no Docker in this part.
- [ ] `git clone <repository-url>` — the README's placeholder; run `git clone https://github.com/dlops-io/llm-agent-google-adk.git` (captured: `Cloning into 'llm-agent-google-adk'...`).
- [ ] `cd google-adk-tutorial` — as written it fails: `cd: google-adk-tutorial: No such file or directory` (captured, E8).
  - Note: run `cd llm-agent-google-adk`.
- [ ] `ls -a` — *(extra)* six numbered module folders, `QUICKSTART.md`, `pyproject.toml`, `.env.example`, and no `uv.lock` (git-ignored).
- [ ] `cp .env.example .env` — the root `.env` that every module uses.
- [ ] `grep -v '^#' .env | grep .` — *(extra)* `GOOGLE_API_KEY=your_google_ai_api_key_here`, `AWS_OPENAI_API_KEY=…`, `GEMINI_MODEL=gemini-2.5-flash`, `ENVIRONMENT=development`.
- [ ] Edit `.env` and add your `GOOGLE_API_KEY` (`README.md:85`): visit [Google AI Studio](https://aistudio.google.com/app/apikey), create an API key, paste it after `GOOGLE_API_KEY=` (`README.md:88-94`).
- [ ] *(extra)* In the same root `.env`, set `GEMINI_MODEL=gemini-3.1-flash-lite`. The file's `gemini-2.5-flash` is limited to earlier users and the code's `gemini-2.0-flash` fallback is shut down (G2).
- [ ] `uv sync` — `README.md:100`, "From repository root".
  - Note: on a laptop with no Python (or where uv already has CPython 3.15) it fails: `Using CPython 3.15.0` … `Resolved 189 packages` … ``error: Distribution `onnxruntime==1.31.0 …` can't be installed because it doesn't have a source distribution or wheel for the current platform`` (captured, G20). Fix below.
- [ ] `uv python pin 3.13` — *(extra, the fix)* ``Pinned `.python-version` to `3.13` ``; any of 3.11-3.14 works.
- [ ] `uv sync` — *(again)* `Using CPython 3.13.16` … `google-adk==2.12.0` … a 1.6 GB `.venv` (plus about 3 GB of CUDA packages on a Linux PC, G13).
- [ ] `uv run adk --version` — *(extra)* `adk, version 2.12.0` at the time of recording.
  - Note: the earlier version of this guide suggested `uv add "google-adk>=1.8.0,<1.28"`. Captured: it installs 1.27.5, but `1-baseline` still fails in `adk web` (`Invalid app name`). Don't use it; rename the folders instead (next section, G1).

### llm-agent-google-adk · Running Agents

*(ADK `README.md:109-119`; §4 Part C2)*
- [ ] `uv run adk web` — from the repository root. ADK 2.12 first asks `Enable telemetry? [Y/n]:`; Enter means **yes** (G21). Then `ADK Web Server started` and `Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)`.
- [ ] `uv run adk telemetry disable` — *(extra, optional)* `Telemetry collection has been disabled.`
- [ ] Open http://localhost:8000 and select a tutorial folder in the agent dropdown (`README.md:119`).
- [ ] `curl -s -o /dev/null -w '%{http_code} -> %{redirect_url}\n' http://localhost:8000/` — *(extra, host)* `307 -> http://localhost:8000/dev-ui/`.
- [ ] `curl -s http://localhost:8000/list-apps; echo` — *(extra, host)* seven entries: `1-baseline`, `2-litellm`, `3-mcp-tools`, `4-production-ready.app`, `5-custom-agent`, `6-rag.1-vertex-rag-engine`, `6-rag.2-custom-chromadb-rag`.
- [ ] Pick `1-baseline` — the page refuses it. `curl -s http://localhost:8000/dev/apps/1-baseline/build_graph; echo` *(extra, host)* shows why: `Invalid agent name: '1-baseline'. Agent names must be valid Python identifiers …` (G1).
- [ ] Ctrl+C, then `mv 1-baseline baseline; mv 3-mcp-tools mcp_tools; mv 5-custom-agent custom_agent; ls` — *(extra, the fix)* folder names ADK accepts. Rename `2-litellm` too if you want it (not to `litellm`, §8 B7).
- [ ] `uv run adk web` — again; pick `baseline`. The log says `Loaded .env file for baseline at …/llm-agent-google-adk/.env` and `Found root_agent in baseline.agent`.
- [ ] `uv run adk web --port 8080` — *(extra)* if llm-rag's ChromaDB still holds port 8000: otherwise `[Errno 98] … address already in use` (G3).

### 1-baseline · Travel Planner

*(`1-baseline/README.md:52-92`; §4 Part C3. Your folder is now `baseline/`.)*
- [ ] `uv sync` — already done at the root; run inside the module folder it builds an extra venv (G13).
- [ ] `cp .env.example .env` — skip it if the root `.env` is set: a copied module `.env` becomes the nearest one, and then the agent runs on the retired `gemini-2.0-flash` with a placeholder key (G2, §8 C1).
- [ ] `uv run adk web` — then select `1-baseline` (yours: `baseline`).
- [ ] `curl -s http://localhost:8000/dev/apps/baseline/build_graph | uv run python -c "import json, sys; r = json.load(sys.stdin)['root_agent']; print(r['name'], '|', r['description']); [print('  ', a['name'], '| model', a['model'], '| output_key', a['output_key'], '|', a['instruction']) for a in r['sub_agents']]"` — *(extra, host)* the agent tree: `TravelPlannerPipeline` with `ItineraryValidator`, `TravelPlanner`, `TripSummarizer`, each with its model and `output_key`.
- [ ] `curl -s -X POST http://localhost:8000/apps/baseline/users/student/sessions; echo` — *(extra, host)* a new session: `"state":{},"events":[]`.
- [ ] *(extra)* Type a trip request (the README gives no example), e.g. "2 adults, Boston to Montreal, Oct 30 - Nov 2, 1500 dollars, train preferred" — three agent replies in order; the State tab shows `itinerary_validation`, `travel_plan`, `trip_summary`. With the placeholder key: `Internal Server Error`, and the server log says `400 INVALID_ARGUMENT … API key not valid` (captured).

### 2-litellm · Multi-Model Support

*(`2-litellm/README.md:22-88`; §4 Part C4)*
- [ ] `uv sync` — "From repository root".
- [ ] `cp .env.example .env` — the `.env.example` key `AWS_OPENAI_API_KEY` is read by no code; `litellm_config.py:28` reads `OPENAI_API_KEY` (G11). Same nearest-`.env` caveat as above.
- [ ] `uv run adk` — as written it prints the usage and command list and starts nothing (captured, G10): run `uv run adk web`, after giving the folder a valid name (G1).
- [ ] `cd 2-litellm` — "Option 2: Test LiteLLM Configuration".
- [ ] `uv run python litellm_config.py` — prints nothing, whatever keys you set: the file has no `__main__` block (G19).
- [ ] `uv run --project .. python -c "from litellm_config import configure_litellm; configure_litellm()"` — *(extra, reasoned, not run)* prints `✓ OpenAI configured` if `OPENAI_API_KEY` is set. §8 B7 makes the module really use LiteLLM.

### 3-mcp-tools · MCP & Tools

*(`3-mcp-tools/README.md:29-94`; §4 Part C5. Your folder is now `mcp_tools/`.)*
- [ ] `uv sync` — from the root.
- [ ] `cp .env.example .env` — same caveat as in 1-baseline, and worse here: the filesystem server can read that file (§8 C1).
- [ ] `brew install node` — macOS.
- [ ] `sudo apt install nodejs npm` — Ubuntu (Windows: download from https://nodejs.org/).
- [ ] `node --version; npx --version` — *(extra)* `v24.22.0` and `11.19.1` at the time of recording.
- [ ] `npx -y @modelcontextprotocol/server-filesystem .` — *(extra, optional)* warms the npx cache so the first agent run does not hit `timeout=10`. It then waits on stdin; stop it with Ctrl+C (G12).
- [ ] `uv run adk` — as written it prints a usage screen: run `uv run adk web` and select `3-mcp-tools` (yours: `mcp_tools`) (G10).
- [ ] *(extra)* The toolset check in §4 C5 (no model involved): `tools the agent sees: ['list_directory', 'read_file', 'search_files']`, `tools the server offers: 14`.
- [ ] Ask "List files in this directory", "Read the README.md file", "What Python files are here?", "Search for files containing 'agent'" — function-call events for `list_directory` and `read_file`; the folder's four tracked files plus `__pycache__`. `search_files` matches file names, not contents (§8 B8).

### 4-production-ready · FastAPI

*(`4-production-ready/README.md:9-52`; §4 Part C6)*
- [ ] `cd 4-production-ready`
- [ ] `uv sync` — builds a second venv with `google-adk[all]`; you can skip it and use the root venv instead.
- [ ] `uv run uvicorn app.main:app --reload --port 8080` — as written (module venv).
- [ ] `uv run --project .. uvicorn app.main:app --port 8080` — *(extra)* the same server from the root venv (checked 2026-10-19, §8 B6).
- [ ] Open http://localhost:8080/docs — FastAPI's Swagger UI (HTTP 200); `GET /health` returns `{"status":"healthy"}`.
- [ ] `curl -X POST http://localhost:8080/chat -H "Content-Type: application/json" -d '{"user_message": "Hello!"}'` — returns `{"response":"..."}` with your key; without one, `Internal Server Error` (500, §8 C5). Every request gets a new random session.
- [ ] `curl -X POST http://localhost:8080/chat/stream -H "Content-Type: application/json" -d '{"user_message": "Tell me a story"}'` — NDJSON `{"chunk": …}` lines; final-response events only, not token streaming.
- [ ] Ctrl+C — *(extra)* stops uvicorn.
- [ ] `docker build -t adk-agent .` — builds the module's image.
- [ ] `docker run -p 8080:8080 -e GOOGLE_API_KEY=your_google_api_key adk-agent` — as written; add `-e GEMINI_MODEL=gemini-3.1-flash-lite`, or the image falls back to the retired default (`app/agent.py:12`).

### 5-custom-agent · Custom Agents

*(`5-custom-agent/README.md:93-153`; §4 Part C7. Your folder is now `custom_agent/`.)*
- [ ] `uv sync` — already done at the root; run inside the module folder it builds an extra venv (G13).
- [ ] `cp .env.example .env` — "Add your GOOGLE_API_KEY". This module's `.env.example:5` sets `GEMINI_MODEL=gemini-2.0-flash` (shut down): change it in the copy, or skip the copy (G2).
- [ ] `uv run adk` — as written it prints a usage screen: run `uv run adk web` and select `5-custom-agent` (yours: `custom_agent`); the final reply gets a 🤖 prefix (G10).
- [ ] `cd 5-custom-agent` — yours: `cd custom_agent`.
- [ ] `uv run python simple_custom_agent.py` — prints `Agent: 🤖 [Bot]: …`.
- [ ] `uv run --project .. python simple_custom_agent.py` — *(extra)* the same from the root venv (G13).
- [ ] `cd 5-custom-agent` — Option 3 repeats it; skip it if you are already in the folder.
- [ ] `uv run python conditional_agent.py` — prints `→ Routed to: SimpleHandler` / `ComplexHandler` / `ClarificationHandler`, then `Response:` for each of three test queries.
- [ ] `uv run --project .. python conditional_agent.py` — *(extra)* the same from the root venv (checked, §8 B5: plain `uv run` in the folder "Would install 276 packages").

### 6-rag · RAG (optional)

*(`6-rag/README.md:102-141`; §4 Part C8. Each sub-folder also has its own, longer README, e.g. creating a service account with `gcloud`; those setups are not covered in this guide.)*

*Option 1: Vertex RAG Engine* (creates a managed corpus in your GCP project; delete it afterwards)
- [ ] `cd 1-vertex-rag-engine` — from `6-rag/`.
- [ ] `uv sync`
- [ ] `cp .env.example .env` — then edit `.env` with your Google Cloud project details and service account.
- [ ] `uv run python setup_corpus.py` — creates the RAG corpus and imports documents (`setup_corpus.py:41-64`).
- [ ] `uv run python agent.py` — runs queries (recommended). It hard-codes `gemini-2.5-flash` and ignores `GEMINI_MODEL` (`6-rag/1-vertex-rag-engine/agent.py:47`, E7).
- [ ] `uv run adk web` — or use the web UI.
- [ ] `uv run python setup_corpus.py` — *(extra)* when done, choose option `5. Delete corpus`, paste the full corpus name and type the whole word `yes` (`y` cancels; §8 C7).

*Option 2: Custom ChromaDB*
- [ ] `cd 2-custom-chromadb-rag` — from `6-rag/`.
- [ ] `docker compose up -d` — starts ChromaDB on port 8000; stop llm-rag's ChromaDB first (G3). It stays "unhealthy" (G14).
- [ ] `uv sync`
- [ ] `cp .env.example .env` — its `.env.example:10` sets `GEMINI_MODEL=gemini-2.0-flash`, and this copy becomes the nearest `.env`: fix it (G2).
- [ ] `curl http://localhost:8000/api/v2/heartbeat` — *(extra)* the README's v1 heartbeat returns HTTP 410 from today's server (G14).
- [ ] `uv run python ingest_documents.py` — run it before `agent.py`, which calls `get_collection` at import time (the README's comment "assumes RAG is already populated" is wrong, E13).
- [ ] `uv run python agent.py` — runs queries (recommended).
- [ ] `uv run adk web` — in this folder it does not find the agent (G14); use `uv run python agent.py`.
- [ ] `docker compose down` — *(extra)* add `-v` to also delete the `chroma_data` volume.

### Travel Planner (Colab)

*(Tutorial 2; §4 Part D. Not run here; checkpoints are the staff's saved outputs.)*
- [ ] Open the [Travel Planner](https://colab.research.google.com/drive/1I_jJEHJsVkGxNoSC1c4wEoVF2QL6vCVY?usp=sharing), *File → Save a copy in Drive*, and give the copy access to the `OPENAI_API_KEY` secret.
- [ ] `%pip install -q "openai-agents==0.3.2"` — cell 8 (`# @title Install OpenAI Agents SDK`).
- [ ] Cells 9-10 (`# @title Imports`, `# @title Setup OpenAI Key`).
- [ ] Cells 12-16 (`# @title Catalog Data & Utils`, `# @title Search Tools`, `# @title Finalize Plan Tool`, `# Test`) — mock catalog in cents, five search tools, the gated `finalize_plan`. Cell 16 should print `LAX-OBSERVATORY` (0.0) and `LAX-MUSEUM` (25.0) (expected from the code; no saved output).
- [ ] Cells 18, 20, 21 (`# @title Business Logic`, `# @title Travel Agent Instructions`, `# @title Travel Agent`) — `check_itinerary`, `run_turn`, and `build_agent()` with `gpt-5.6-luna`, six tools and `SQLiteSession("travel-planner")`.
- [ ] Cell 24 (`# Build the Agent`, Turn 1) — `Kind: clarification`, asking "San Francisco or Los Angeles?" and for the allowances.
- [ ] Cell 25 (Turn 2) — five tool calls, then `Kind: options`.
- [ ] Cell 26 (Turn 3) — `[tool] finalize_plan: …`, then `Kind: clarification` with the exact JSON proposal.
- [ ] Cell 27 (Turn 4, `"yes"`) — `Kind: itinerary`, `"total_usd": 2690.0`, `"remaining_usd": 3310.0`. An `AssertionError` on `reply.kind` means the model took another plausible path: rerun the turn.
- [ ] Cell 28 (`# @title Start an interactive conversation`) — defines the chat loop.
- [ ] `await chat_loop()` — cell 29: end a message with a blank line or `/send`; `exit` or `quit` leaves. It starts a fresh session.

### Cheese Newsletter · Harness (Colab)

*(Tutorial 3; §4 Part E. Not run here; checkpoints are the staff's saved outputs.)*
- [ ] Open the [Cheese Newsletter · Harness](https://colab.research.google.com/drive/1nnHrJ4Si3tpgUQl6HqlcwxKymV1-ecPv?usp=sharing), *File → Save a copy in Drive*, and give the copy access to the `OPENAI_API_KEY` secret.
- [ ] `%pip install -qU "agent-framework-core==1.18.0" "agent-framework-openai==1.14.3" "opentelemetry-api==1.42.1"` — cell 8 (`# @title Install Microsoft Agent Framework`).
- [ ] Cells 9-10 (`# @title Imports`, `# @title Setup OpenAI Key`).
- [ ] Edit `USERS` in cell 16 (`# @title Catalog Data & Utils`, lines 7-12): replace the course staff's names and addresses with yours and a friend's, and keep at least two readers (cell 31 displays `receipts[1]`). Write "Somerville" if you mean Somerville, MA.
- [ ] Run cells 16-25 (`# @title Catalog Data & Utils` … `# @title Orchestrator Agent`) — contracts, validation, rendering, the researcher and editor as `@tool`s, the orchestrator (`max_iterations: 16`, `allow_multiple_tool_calls: False`).
- [ ] `receipts = await run_demo()` — cell 27 (`# @title Run Demo`): per reader `[tool] researcher_agent`, `[tool] editor_agent`, `[tool] send_email: validating and saving HTML (mock)` and `Saved HTML: …`; a fresh run ends with `Created 2 mock emails. No email was sent.`
- [ ] Cells 30-31 — render the saved HTML previews and file links.

### After the tutorials *(extra)*

*Clean up (§2)*
- [ ] Ctrl+C — stops `adk web` and `uvicorn`.
- [ ] `git status --short; git status --short --ignored | grep '^!!'` — *(in `llm-agent-google-adk/`)* the renamed folders show as deleted + untracked, `?? .python-version`; ignored: `.env`, `.venv/`, `uv.lock`, `__pycache__/`. Your sessions in `baseline/.adk/` are **not** ignored (G22).
- [ ] `echo ".adk/" >> .gitignore` — *(in `llm-agent-google-adk/`)* keeps the session files out of any commit; `git check-ignore -v baseline/.adk/session.db` confirms (§8 B11).
- [ ] `rm -rf .venv` — *(in `llm-agent-google-adk/`, when you are done)* frees 1.6 GB; `uv sync` rebuilds it.
- [ ] `docker compose down` — *(host)* in `llm-rag/` if it is still running, and in `6-rag/2-custom-chromadb-rag/` (add `-v` there to delete the `chroma_data` volume).
- [ ] In each Colab notebook: *Runtime → Disconnect and delete runtime*.
- [ ] IAM → Service accounts → Keys: rotate or delete any key you no longer need; delete or cap the AI Studio and OpenAI keys when the course ends.
- [ ] Before the first `git add` in any parent repo that holds your clones: make sure its `.gitignore` covers `secrets/`, `**/.env` and key files (G18).

---

## 1. What you build

In L05 you built a RAG pipeline: chunk → embed → load into ChromaDB → retrieve → answer. In L06 the **LLM decides how to retrieve**. You do this in three settings, from "by hand" to "framework" to "harness":

1. **`llm-rag --agent` (Docker, Gemini on Vertex AI).** Gemini 3.1 Flash-Lite receives two *function declarations*: "search one author's book" and "search all books". It is **forced** to answer with a function call (`mode="any"`). Your Python code runs that call against ChromaDB, sends the chunks back, and a second Gemini call writes the answer. Two LLM calls, no loop.
2. **`llm-agent-google-adk` (uv on your laptop, Gemini API).** Google's Agent Development Kit runs the *agent loop* for you: call the model → run the tools it asked for → call the model again, until it gives a final answer. The repo has six modules:
   - a sequential travel-planner pipeline that shares *state*
   - LiteLLM for other model providers
   - an MCP filesystem tool server
   - a FastAPI deployment
   - custom agents that route between sub-agents
   - two RAG agents

   Today's ADK (2.12.0) refuses the hyphenated module folder names, so you rename the three you run (`baseline`, `mcp_tools`, `custom_agent`; §4 C2).
3. **Three Colab notebooks (OpenAI).**
   - *Cheese Quiz* climbs the ladder plain LLM → hand-written reasoning workflow → agent with web search → context layers → tools and MCP → a six-agent "Cheese Quiz Guild".
   - *Travel Planner* lets the model choose tools, but Python owns the money arithmetic and a human-approval gate.
   - *Cheese Newsletter* is an orchestrator with sub-agents-as-tools. Python decides whether the run succeeded, through a *receipt*.

```
YOUR LAPTOP  (~/AC215 in the captures: wherever you keep your clones)
+-----------------------------------------------------------------------------------------------+
| (B) llm-rag/   sh docker-shell.sh  ->  docker compose run --rm llm-rag-cli                     |
|     docker network "llm-rag-network"                                                          |
|     +-- one-off container llm-rag-llm-rag-cli-run-<id> (image llm-rag-cli, venv /.venv) --+  |
|     | /app     <- bind ../llm-rag        /secrets <- bind ../secrets                        |  |
|     | $ python cli.py --agent --chunk_type char-split                                     |  |
|     |   (1) generate_content(question, tools, mode=ANY) -------------------------------+  |  |
|     |   (2) execute_function_calls(): embed(search_content) -> collection.query() --+ |  |  |
|     |   (3) generate_content(question + model's call + function responses) ---------+-+->+-+--HTTPS--+
|     +-----------------------------------------------------------------|---------------+  |         |
|                         http://llm-rag-chromadb:8000 (container DNS)  v                  |         |
|     +------------- container llm-rag-chromadb (chromadb/chroma:latest) -------------+   |         |
|     | collection "char-split-collection" (cosine, metadata: book, author, year)    |   |         |
|     | /data <- bind ./docker-volumes/chromadb (persists between runs)              |<--+-- host :8000 (browser Chroma UI)
|     +-------------------------------------------------------------------------------+   |         |
|                                                                                            |         |
| (C) llm-agent-google-adk/   uv run adk web  ->  FastAPI + dev UI on http://127.0.0.1:8000 (!) |       |
|     loads <folder>/agent.py :: root_agent ; reads nearest .env (GOOGLE_API_KEY, GEMINI_MODEL) --HTTPS--> Gemini API
|     keeps each agent's sessions in <folder>/.adk/session.db                                |         |
|     mcp_tools: spawns child process `npx -y @modelcontextprotocol/server-filesystem <dir>` (stdio) |
|     4-production-ready: uvicorn app.main:app :8080  (POST /chat, /chat/stream)              |         |
+-----------------------------------------------------------------------------------------------+       |
                                                                                                        |
GOOGLE CLOUD (your project)   Vertex AI, location "global": gemini-embedding-001 (256-d), gemini-3.1-flash-lite <-+
                              auth: GOOGLE_APPLICATION_CREDENTIALS=/secrets/llm-service-account.json

GOOGLE COLAB VM (browser)     notebook --HTTPS--> OpenAI API (gpt-4o, gpt-5.6-luna, hosted web_search tool)
                              Cheese Quiz --HTTP--> https://pavlos-fun-facts.dlops.io/mcp  (remote MCP server)
                              Cheese Quiz: FastMCP thread on 127.0.0.1:8001/mcp inside the Colab VM
                              Newsletter: writes /content/newsletter_output/*.html (no email is sent)
```

(!) `adk web` and the llm-rag ChromaDB both want port **8000** on your laptop. See G3.
`docker compose run` ignores `container_name: llm-rag-cli` (`docker-compose.yml:9`): the one-off container is named `llm-rag-llm-rag-cli-run-<id>` (captured `docker ps`). Only `llm-rag-chromadb` keeps its fixed name.

---

## 2. Prerequisites and costs

**Accounts and keys, and where the code expects them**

| What | Used by | Where the code looks |
|---|---|---|
| GCP project with billing; **Vertex AI API** (`aiplatform.googleapis.com`) enabled | llm-rag | `GCP_PROJECT` is exported in `llm-rag/docker-shell.sh:7` (edit `"ac215-project"`), passed through `docker-compose.yml:15`, read with `os.environ["GCP_PROJECT"]` at `cli.py:23`. The client uses `vertexai=True, location="global"` (`cli.py:24, 35-36`); the captured request goes to `https://aiplatform.googleapis.com/v1beta1/projects/<your-project>/locations/global/publishers/google/models/gemini-3.1-flash-lite:generateContent`. |
| Service account `llm-service-account` with **Gemini Enterprise Agent Platform User** (listed as "Vertex AI User" in older projects) | llm-rag | `README.md:52-62`. The JSON key goes to `../secrets/llm-service-account.json`, a sibling of `llm-rag/` (`README.md:64-69`). It is mounted at `/secrets` (`docker-compose.yml:11`), and `GOOGLE_APPLICATION_CREDENTIALS=/secrets/llm-service-account.json` (`docker-shell.sh:8`). The README also grants **Storage Admin** (`README.md:57`). Nothing in the L06 code path touches Cloud Storage, so the agent does not need it. |
| A loaded Chroma collection `char-split-collection` | llm-rag `--agent` | `cli.py:427-429` calls `get_collection(f"{method}-collection")`. You build it with L05's `--chunk`, `--embed`, `--load`. |
| **Google AI Studio API key** | ADK repo | `GOOGLE_API_KEY` in `llm-agent-google-adk/.env` (`.env.example:5`). Alternative: Vertex mode via `GOOGLE_GENAI_USE_VERTEXAI=true`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION` (`1-baseline/.env.example:10-12`, commented out). |
| A **current Gemini model name** | ADK repo | Read as `GEMINI_MODEL` from `.env` (root `.env.example:21` says `gemini-2.5-flash`). Every Gemini `agent.py` falls back to `gemini-2.0-flash` when `GEMINI_MODEL` is unset (e.g. `1-baseline/agent.py:12`), and that model is **shut down**. The exceptions: `6-rag/1-vertex-rag-engine/agent.py:47` hard-codes `gemini-2.5-flash`, and `2-litellm/agent.py:26` uses `"gpt-4"`. See G2. |
| **OpenAI API key** with billing | all three notebooks; ADK `2-litellm` | Colab **Secrets** panel, name `OPENAI_API_KEY`, with notebook access on. Read via `userdata.get('OPENAI_API_KEY')`: Cheese Quiz cell 12 (`# @title Set Up OpenAI Key`), Travel Planner cell 10, Newsletter cell 10. In ADK, `litellm_config.py:28` reads `OPENAI_API_KEY` from the root `.env`. |

**Local installs** (versions at the time of the captures, 2026-10-18):
- Docker with the Compose plugin (`docker compose`), for llm-rag. The captures used Docker Engine 29.8.2 and Compose v5.6.0.
- `uv`, for the ADK repo (0.13.1 in the captures). `README.md:61` asks for "Python 3.10+ installed on your system", but you don't need one: uv downloads a Python, and the version it picks matters (G20).
- **Node.js + npm (`npx`)**, for `3-mcp-tools` (`3-mcp-tools/README.md:53-64`); v24.22.0 and npm 11.19.1 in the captures.
- Git.
- Disk: the llm-rag image and Chroma data from L05, plus 1.6 GB for the ADK `.venv` (and about 3 GB of CUDA packages on a Linux PC, G13).

**Platform:** `python:3.12-slim-bookworm` and `chromadb/chroma` are multi-arch images, and llm-rag's `uv.lock` pins chromadb 1.1.0 wheels for `manylinux_2_17_aarch64` as well as x86_64. So Apple Silicon runs natively; the entrypoint prints `Architecture: aarch64` on an M-series Mac (`docker-entrypoint.sh:4`) where the captures show `x86_64`.

**Costs (all small, but not zero):**
- *Per `--agent` question:* two Gemini calls and one embedding call (the search text), all on Vertex AI. The staff's recorded run used 247 + 1,269 tokens (`out.txt:49`, `out.txt:135`). Negligible.
- *Vertex embeddings (only if you rebuild the collection).* char-split produces **8,248 chunks** of ≤350 characters (captured `--load`; Tolminc has 24): about 2.9 M characters. `embed()` batches per book file, up to 100 chunks per request (`cli.py:239-253`), so that is 89 embedding requests (the sum of ⌈chunks/100⌉ over the 11 books). That costs pennies.
- *OpenAI.* The Cheese Quiz makes dozens of model calls. Most name `gpt-4o`; the "Reasoning LLM" alone made 11 calls for one question in the saved run (cell 25). Cheddar, Mozzarella, Cashew, Ricotta and the Guild orchestrator (cells 66, 70) set no `model=`, so they run on the Agents SDK's default model (`gpt-5.6-luna` in openai-agents 0.22.3-0.24.0). The hosted **web search** tool is billed by OpenAI per call on top of tokens; Stilton, Cashew and SimpleAgent use it. The Newsletter runs a researcher with web search at least once per reader. Expect cents to low dollars per full run.
- *Gemini API (AI Studio):* free-tier limits may cover the ADK exercises. Each `baseline` request is three model calls. Check your quota page.
- *Optional `6-rag/1-vertex-rag-engine`:* creates a managed **Vertex AI RAG Engine corpus** in your project (`setup_corpus.py:41-64`). Delete it when done (§8 C7), and check the RAG Engine page: Google's documentation says its default Spanner mode keeps a provisioned instance until you switch the tier to *Unprovisioned*.

**Shut down afterwards:**
- llm-rag: `exit` the container shell, then run `docker compose down` in `llm-rag/`. `compose run` leaves `llm-rag-chromadb` running (G4).
- `adk web` / `uvicorn`: Ctrl+C.
- ADK repo: keep `<agent>/.adk/` out of git (G22); delete `.venv` when you are done.
- `6-rag/2-custom-chromadb-rag`: `docker compose down` (add `-v` to also delete the `chroma_data` volume).
- Colab: *Runtime → Disconnect and delete runtime*.
- Rotate or delete any key you no longer need (IAM → Service accounts → Keys; AI Studio; OpenAI).

---

## 3. Concepts this tutorial teaches

### 3.1 LLM vs workflow vs agent: who holds the steering wheel?
- **Explanation:** The Cheese Quiz notebook asks the same question ("What's the best cheese for a grilled cheese sandwich?") three ways.
  - *Base LLM:* one call (cell 20, `# @title Define BaseLLM`). Saved run: `Tokens: 293, Time: 2.81s`.
  - *"Reasoning LLM":* **your Python** decides the steps. Analyse → decompose → answer each sub-question → verify → synthesise (cell 24, `# @title Define ReasoningLLM`). With at most 4 sub-questions (`questions[:4]`, cell 24 line 41) that is at most 1 + 1 + 4 × 2 + 1 = 11 calls, which is what the saved run made (`Sub-questions explored: 4`, `Total tokens: 701, Time: 39.34s`).
  - *Agent:* **the model** decides what to do next, including when to call `web_search` and when to stop (cell 30, `# @title Define SimpleAgent`; definition in cell 8: "a component that uses an LLM with instructions and tools that can run autonomously"). Saved run: `Time: 13.29s`.
- **Mental model:** The difference is *who controls the control flow*. In a workflow, the `if`/`for` live in your code. In an agent, they live in the model's next-token choices, and your code is a loop that obeys.
- **Analogy:** A recipe card (workflow) vs a chef who reads the order and decides which station to visit (agent).
- **Misconception:** "An agent is a smarter model." The model is the same `gpt-4o` in all three runs. What changes is the loop and the tools around it. (And "reasoning" here means a workflow of calls ordered by Python, not a model that thinks inside one call; Gemini's `thought_signature` in §3.2 is the second kind.)

### 3.2 Function (tool) calling: the model *writes* the call, your code *makes* it
- **Explanation:** You send the model a JSON-schema description of functions it may call: `FunctionDeclaration` with name, description and parameters (`llm-rag/agent_tools.py:9-38, 52-66`). The model never runs anything. It replies with a structured `function_call` part, for example `name='get_book_by_author', args={'author': 'Pavlos Protopapas', 'search_content': 'cheese making importance location'}` (`out.txt:20-27`). **Your code** looks at the name, runs the real Python function (`agent_tools.py:84-127`), wraps the result in a `function_response` part (`agent_tools.py:103-110`) and sends everything back. The model then writes the answer.
- **What travels, exactly** (the two request bodies, printed by the captures instead of being sent):
  - *Call 1:* `contents` = the question (role `user`); `tools[0].functionDeclarations` = both declarations, with the 9-name `enum`; `"toolConfig": {"functionCallingConfig": {"mode": "ANY"}}`; `"generationConfig": {"temperature": 0.0}`. No `systemInstruction`.
  - *Call 2:* three contents: the question (role `user`); the model's own turn, unchanged (role `model`), with its `functionCall` (`id`, `args`, `name`) and a `"thoughtSignature"`; and your `functionResponse` (`name`, `response: {content: …}`) with no role and no `id`. The tools go along again, but there is no `toolConfig` (so the mode is AUTO) and `"generationConfig": {}`.
- **Mental model:** The model is a manager who can only write sticky notes ("please run X with Y"). You are the assistant who runs X and staples the result to the note.
- **Analogy:** Ordering at a counter. You fill out the order form (schema). The kitchen (your code) cooks. The server (the model) presents the dish.
- **Misconception:** "Gemini queried my ChromaDB." It could not have: ChromaDB is on `localhost`, inside Docker. Gemini only produced arguments. Also, `mode="any"` (`cli.py:447-451`) does not mean "maybe call a tool": it **forces** a function call. In google-genai's own words, ANY means the "Model is constrained to always predicting function calls only" (google-genai 1.39.1 `types.py:500-501`). The lower-case string becomes the enum value: `FunctionCallingConfig(mode="any")` prints `mode=<FunctionCallingConfigMode.ANY: 'ANY'>` (captured).

### 3.3 The agent loop and its stopping rule
- **Explanation:** Real agents repeat §3.2 until the model stops asking for tools. The stop rule: a reply with no function call is the final response. In ADK the core is literally `while True:`. Run one LLM step (which may execute tools), then break if the last event `is_final_response()` (google-adk 1.19.0 `flows/llm_flows/base_llm_flow.py:343-352`; the same ten lines in 1.27.5 at 755-764). An event counts as final when it has no function calls, no function responses, is not partial and has no trailing code-execution result (`events/event.py:82-97`; also true when a tool set `skip_summarization` or is long-running; in 2.12.0 an event that carries an error code is final too, §8 C5).
- **The caps** a framework adds, in case the model never stops:

| Framework | Cap | Default | In the tutorial | When it is hit |
|---|---|---|---|---|
| OpenAI Agents SDK | `max_turns` (model calls of one `Runner.run`) | 10 | 12: Cheese Quiz cell 71, Travel Planner cell 21 | raises `MaxTurnsExceeded` |
| Microsoft Agent Framework | `max_iterations` (model round trips) | 40 | 16 for the Newsletter's orchestrator (cell 25, line 8) | no error: one last response is requested with tools disabled |
| ADK | `RunConfig.max_llm_calls` | 500 | not set | |

- **Mental model:** A `while` loop whose exit condition is decided by the model, plus a hard iteration cap decided by you.
- **Analogy:** A detective who keeps sending the intern for evidence until ready to name the culprit, with a deadline.
- **Misconception:** "`llm-rag --agent` is an agent loop." It is a fixed two-call pipeline: forced tool call → answer (`cli.py:439-478`). If the second call asked for another tool, the code would just print that request: `cli.py:478` prints a response whose part is a `function_call` (no text), and the program ends (§8 C2). ADK's loop would execute that call and call the model again until `is_final_response()`.

### 3.4 Context engineering: the model knows only what is in the request
- **Explanation:** "LLMs are stateless functions" (Cheese Quiz cell 35). The notebook keeps the model and question fixed and adds one context layer at a time (cells 38-44): basic prompt → system prompt → retrieved documents (RAG) → short-term memory (prior turns) → long-term memory (user profile) → tool outputs → structured output (JSON schema, `strict: True`). In the saved run the top pick moves with the inputs: cheddar (step 1), American (steps 2-3), mild cheddar and mozzarella for kids (step 4), Havarti (step 5), the Whole Foods Mild Cheddar from the tool output (step 6), and the same pick as strict JSON, `"top_recommendation": "Whole Foods Mild Cheddar"` (step 7).
- **Mental model:** Every call is a fresh envelope. Memory, RAG and tool results are just more paper you put inside it.
- **Analogy:** Briefing a consultant who has amnesia between meetings.
- **Misconception:** "The model remembers the last cell." It does not. Step 4 *re-sends* the whole message history (cell 41).
  - Watch the roles: Step 2 accidentally sends the system prompt as a `user` message and the question as a `system` message (cell 39, lines 18-21). See E1 in §9.
  - The ADK README also blurs two terms: it calls per-session state "Memory" (`llm-agent-google-adk/README.md:140`). In ADK, *state* is per session and *memory* is a separate cross-session service (§8 D3).

### 3.5 Tools, schemas and MCP
- **Explanation:** A tool is a name, a description and a parameter schema, plus code. Frameworks can build the schema for you from a Python signature and docstring:
  - OpenAI Agents SDK: `@function_tool` (Cheese Quiz cell 48)
  - ADK: plain functions in `tools=[...]` (`6-rag/2-custom-chromadb-rag/agent.py:73-121`)
  - Microsoft Agent Framework: `@tool` (Newsletter cell 20)

  By contrast, llm-rag writes the JSON schema by hand (`agent_tools.py:9-38`).

  **MCP** (Model Context Protocol) standardises *where tools live*. A server lists its tools, and any client can call them over **stdio** (a child process) or **HTTP**. There are three plugs in this lecture:
  - the Cheese Quiz's remote server by URL (cell 54, `https://pavlos-fun-facts.dlops.io/mcp`). Captured with `curl`: `initialize` answers `"protocolVersion":"2025-06-18"` and `"serverInfo":{"name":"Pavlos Cheese MCP","version":"1.16.0"}`; `tools/list` returns one tool, `pavlos_fun_fact_mcp`; a plain GET (what a browser does) gets `HTTP/2 406` (§4 A7);
  - the Cheese Quiz's own FastMCP server in a thread on port 8001 (cells 57-59), with a tool of the same name;
  - ADK `3-mcp-tools`, which spawns the npm filesystem server over stdio. The server offers 14 tools; `tool_filter` lets three through (`3-mcp-tools/agent.py:20-29`; captured, §4 C5).
- **Mental model:** Tool = function + contract. MCP = a USB standard for plugging tool servers into any agent.
- **Analogy:** A universal power socket. The appliance (tool server) does not care which house (agent framework) it is plugged into.
- **Misconception:** "MCP gives the model network access." The *client process* talks to the server. The model still only emits a function call, and `tool_filter` (`3-mcp-tools/agent.py:28`) limits what it can even ask for.
- **The lecture's three families** (slide 51), sorted with this lecture's tools: *data* tools fetch (the two book searches, `web_search`, `list_directory`, `read_file`); *action* tools change something (`finalize_itinerary`, `send_email`; the filesystem's `write_file`, which the filter removes); *orchestration* tools hand work to another agent (`.as_tool` specialists, the Newsletter's researcher and editor). The harness's checks sit on the action tools (§8 D1).

### 3.6 ADK's runtime objects: Agent, Runner, Session, State, Event; `output_key` and `{key}`
- **Explanation:**
  - An **`LlmAgent`** (alias `Agent`) bundles model + instruction + tools.
  - A **Runner** executes an agent for a `(user_id, session_id)`, streams **Events**, and appends each event to the **Session** (`4-production-ready/app/runner.py:16-46`).
  - A session holds **state**, a dict. When an `LlmAgent` has `output_key="x"`, its final text is written into `state["x"]` (google-adk 1.19.0 `agents/llm_agent.py:795-816`).
  - Any later instruction containing `{x}` gets that value pasted in before the call. A missing key raises `KeyError: Context variable not found` unless you write `{x?}` (`utils/instructions_utils.py:81-124`; §8 C4).
  - `SequentialAgent` runs sub-agents in order (`1-baseline/agent.py:35-39`). `ParallelAgent` runs them concurrently on separate *branches* but with shared state (`agents/parallel_agent.py`, `_create_branch_ctx_for_sub_agent`).
  - ADK 2.12 also passes the earlier agents' replies to each `LlmAgent` in the sequence as quoted history ("For context: … [ItineraryValidator] said: …"), so in `1-baseline` the plan reaches the summarizer twice: through the state and through the session's events (§8 Q4).
  - `adk web` imports `<folder>/agent.py`, looks for `root_agent`, and loads **only the nearest** `.env`, walking up from that folder, with `override=True` (`cli/utils/envs.py`, `load_dotenv_for_agent`). A module `.env` therefore hides the root one completely. Captured log line: `Loaded .env file for baseline at /home/student/AC215/llm-agent-google-adk/.env`.
  - `adk web` 2.12 keeps each agent's sessions on disk, in `<agent>/.adk/session.db` (captured: `Creating local session service at …/baseline/.adk/session.db`). Restarting the server does not remove them (§8 B4).
- **Mental model:** A shared whiteboard (state). Each agent reads cells off the board through `{placeholders}` and writes its answer into one named cell.
- **Analogy:** A relay race where the baton is a labelled envelope pinned to a corkboard.
- **Misconception:** "Sub-agents pass messages directly to each other." They do not. Data flows through session state (and the shared event history), which is why `output_key` names matter.

### 3.7 Multi-agent patterns: workflow agents, agents-as-tools, custom routers
- **Explanation:** There are three ways to compose agents in this lecture, and they differ in *who plans the order* (the lecture's planner, slide 38):
  - (a) **The code: workflow agents.** `SequentialAgent`, `ParallelAgent` and `LoopAgent`. Deterministic orchestration, LLM inside each step. Only `SequentialAgent` is in runnable code (`1-baseline/agent.py:35-39`); `ParallelAgent` appears only as a README snippet (`1-baseline/README.md:138-145`) and `LoopAgent` only in `5-custom-agent/README.md:232-259`.
  - (b) **The model: agents-as-tools.** Each specialist is wrapped with `.as_tool(name, description)`, and an orchestrator LLM decides which one to call (Cheese Quiz cells 64-71: Stilton, Cashew, Brie, Cheddar, Mozzarella, Ricotta). The Newsletter wraps the researcher and editor as `@tool` functions (cells 21-22).
  - (c) **Python reading the model's label: custom agents.** Subclass `BaseAgent` and write `_run_async_impl` with ordinary `if` statements (`5-custom-agent/conditional_agent.py:72-104`).
- **Mental model:** (a) is an assembly line, (b) is a manager with a phone book of specialists, (c) is code that you write yourself.
- **Analogy:** A factory line, a general contractor, and your own hand-written SOP.
- **Misconception:** "More agents means better answers." Each hop adds latency, cost and failure points. In the saved run, three `ERROR:openai.agents:Error getting response` lines appear in each of the two quiz runs (Cheese Quiz cells 75 and 77), yet both still render a quiz; the log does not say which call failed. The Guild's "at most 2 total review rounds" (cell 70, line 11) is a rule in prose; only the 12-turn cap is enforced (§8 D4).

### 3.8 The harness: Python owns state, approvals, validation and the definition of success
- **Explanation:** In the last two notebooks the model chooses actions, but deterministic code decides what those actions are *allowed* to mean.
  - **Travel Planner.** Python computes all prices (`check_itinerary`, cell 18). The model's `finalize_itinerary` call only produces a *pending proposal* until a **later human turn** literally says "yes": `apply_confirmation` (cell 18, lines 55-65, called on the human's message before the agent runs, line 106) and the `proposal != approved_proposal` gate (cell 15, lines 33-42). What the user sees is rendered from checked state, not from the model's prose (cell 18, lines 122-131): an itinerary without a same-turn check raises an error (a *hard* guardrail), and a dollar amount in the model's prose only prints a warning (a *soft* one, lines 133-135).
  - **Newsletter.** Sources are registered only from search citation metadata (cell 20, `collect_evidence`). Drafts are validated (`validate_newsletter`, cell 18), and validation errors go back to the orchestrator as the tool's result. Success means a `receipt` exists **and the file is on disk** (cell 18, lines 118-125), never "the model said it's done".
- **Mental model:** The LLM is a powerful but untrusted planner inside a sandbox whose walls, gauges and exit door are code.
- **Analogy:** A pilot with autopilot: the plane suggests, but the checklist and the co-pilot's signature are required before take-off.
- **Misconception:** "Put the rule in the prompt and it will be followed." The prompt says "no monetary amounts" (cell 20). The code still checks with a regex and warns (cell 18, lines 133-135). The Newsletter editor is told "no embedded URLs" (cell 22, line 16), yet the saved HTML contains `Promotion URL: https://…` inside an offer summary, because `validate_newsletter` does not check for URLs (§8 B10 makes it a check).

---

## 4. Step-by-step walkthrough

This follows the course-site order (`tutorials_demo.md:86-98`): Tutorial 1 = Cheese Quiz Colab + llm-rag Agents + ADK, Tutorial 2 = Travel Planner, Tutorial 3 = Newsletter. If you are working from your local clones first, do Part B, then Part C, then the Colabs. (The video takes the Cheese Quiz idea by idea: its first sections before llm-rag, its MCP and Guild sections next to ADK.)

**About the outputs below.** Every block is labelled:
- *Captured*: a real run on 2026-10-18, trimmed (first and last lines, with `…` between), from the video folder's [`assets/terminal/`](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l06-agents-1/assets/terminal) (file name given; `[exit N]` lines omitted, exit statuses mentioned where they matter).
- *Recorded*: real output saved by the course staff: llm-rag's committed `out.txt` (2026-09-22) and the notebooks' saved outputs. Never typed by hand here.
- *Expected*: README text, or what the code prints, where nothing was run.

On your laptop:
- **There was no key in the captures.** Every model call stops before sending, or is refused. With your keys, the same commands do their job; §4 says what to look for.
- The llm-rag laptop ran Linux as user `student` in `~/AC215` with Docker Engine 29.8.2 and Compose v5.6.0. Docker Desktop's progress display and a few messages differ (for example its "pull access denied" line reads `failed to resolve reference … not found`). On Apple Silicon the banner says `Architecture: aarch64`.
- The ADK laptop was a fresh Debian 12 with no Python. To save disk, the capture let uv take PyTorch's CPU-only wheel: your `uv sync` says `Resolved 189 packages` and installs `torch==2.14.1` (plus, on a Linux PC, about 3 GB of `nvidia-*` CUDA packages; a Mac gets none), where the capture shows 171 packages and `torch==2.14.1+cpu`. Nothing else ADK does depends on it.
- Container ids, session ids, times, the MCP fun fact and the order of metadata keys change on every run. Versions are those of 2026-10-18.

### Part A — Tutorial 1a: Cheese Quiz (Colab)

**A1. Open and copy.** Open the Colab link (`tutorials_demo.md:88`), then *File → Save a copy in Drive* (cell 1). *Checkpoint:* the tab title starts with "Copy of".

**A2. Add your OpenAI key.**
- *Action:* Colab left sidebar → 🔑 *Secrets* → add `OPENAI_API_KEY` → toggle *Notebook access*. Cell 12 (`# @title Set Up OpenAI Key`) runs `api_key = userdata.get('OPENAI_API_KEY')` and builds `client = OpenAI(...)`.
- *If it fails:* a `SecretNotFoundError` / notebook-access error means the secret name or the toggle is wrong.

**A3. Install, import, download.**
- *Cells 10-13.* Cell 10 runs `!pip -q install fastmcp openai-agents > /dev/null 2>&1`. These are **unpinned** (fastmcp 4.1.1 and openai-agents 0.24.0 on 2026-10-18), and errors are hidden by the redirect, so if cell 11 fails to import `agents` or `fastmcp`, rerun the install without `> /dev/null 2>&1` to see why (G16).
- *Cell 13* runs `!gdown` twice. Recorded (`expected/colab-cheese-quiz-c13-download.txt`):
  ```
  Downloading...
  From: https://drive.google.com/uc?id=1dxvxGZZ-yYEEHQuaoP4HwaYxsbOC4XEh
  To: /content/quiz-schema.json
  100% 2.10k/2.10k [00:00<00:00, 8.24MB/s]
  Downloading...
  From: https://drive.google.com/uc?id=1OykEQrwa5cnZgPIVrOdnDeq3txots3H0
  To: /content/quiz-ui.html
  100% 10.8k/10.8k [00:00<00:00, 65.7MB/s]
  ```
  `quiz-schema.json` is a strict JSON Schema for the quiz (questions with an integer `id`, `text`, `options` lettered a-d and an `answer`, `additionalProperties: false` at every level); `quiz-ui.html` is the widget template that cell 62's `render_quiz_html` fills. Cell 62 needs both.

**A4. LLM → Reasoning LLM → Agent** (cells 17-31).
- *Under the hood:*
  - `BaseLLM.generate` makes one `chat.completions.create` call (cell 20).
  - `ReasoningLLM.reason` chains up to 11 calls: 1 analyse + 1 decompose + (up to 4) × (answer + verify) + 1 synthesise (cell 24).
  - `SimpleAgent` gives a `WebSearchTool` to an Agents-SDK `Agent` and calls `Runner.run` (cell 30).
- *Recorded* (cells 21, 25, 31; `expected/colab-cheese-quiz-c21-base-llm.txt`, `-c25-reasoning-llm.txt`, `-c31-simple-agent.txt`):
  ```
  🧠 BaseLLM: Making single API call...
  ==================================================
  BASE LLM: gpt-4o
  …
  Tokens: 293, Time: 2.81s
  ```
  ```
  🔧 ReasoningLLM: Processing 'What's the best cheese for a grilled cheese sandwich?'
  🔧 ReasoningLLM: Step 1 - Analyzing query...
  🧠 BaseLLM: Making single API call...
  🔧 ReasoningLLM: Step 2 - Decomposing problem...
  🧠 BaseLLM: Making single API call...
  …
  🔧 ReasoningLLM: Step 5 - Synthesizing final response...
  🧠 BaseLLM: Making single API call...
  …
  Sub-questions explored: 4
  Total tokens: 701, Time: 39.34s
  ```
  ```
  🤖 SimpleAgent: Running with web_search for 'What's the best cheese for a grilled cheese sandwich?'
  …
  Tools used: 1
  Time: 13.29s
  ```
- *Read critically:*
  - "Total tokens: 701" is an approximation: the code adds `100` per sub-question (cell 24, `total_tokens += 100  # Approximate token usage`).
  - "Tools used: 1" counts *configured* tools (`self.agent.tools`), not calls. The answer itself reports two searches.

**A5. Managing LLM inputs** (cells 37-44). Run the seven steps and compare answers.
- *Under the hood:* Steps 1-6 only change `messages`. Step 7 adds `response_format={"type": "json_schema", … "strict": True}` and then parses with `json.loads`.
- *Recorded:* the top pick moves with the inputs (§3.4): cheddar, American, mild cheddar and mozzarella for kids, Havarti, the Whole Foods Mild Cheddar, then JSON with `"top_recommendation": "Whole Foods Mild Cheddar"`.
- *Watch:* Step 2 swaps the roles (cell 39, lines 18-21). Fix it before drawing conclusions about "prompt engineering" (E1 in §9):
  ```python
      messages=[
          {"role": "user", "content": system_prompt},
          {"role": "system", "content": user_prompt}
      ],
  ```

**A6. Your first tool** (cells 46-50).
- `@function_tool(name_override="pavlos_fun_fact_tool")` turns an async function into a tool (cell 48, lines 21-25). The instruction says to call it 2-3 times (cell 49).
- *Recorded* (cell 50, `expected/colab-cheese-quiz-c50-tools-called.txt`): because the facts are drawn with `random.choice`, a duplicate can appear, and it did:
  ```
  Tools called:
  1. pavlos_fun_fact_tool  args={}
  2. pavlos_fun_fact_tool  args={}
  3. pavlos_fun_fact_tool  args={}

  Tool outputs:
  1. {'fact': 'Salt helps control moisture and rind formation during cheesemaking.', 'generated_at': 1790132531}
  2. {'fact': 'High-moisture cheeses (young gouda, fontina, jack) melt especially evenly.', 'generated_at': 1790132531}
  3. {'fact': 'Salt helps control moisture and rind formation during cheesemaking.', 'generated_at': 1790132531}
  ```

**A7. MCP** (cells 51-59).
- Cell 54 connects `MCPServerStreamableHttp(params={"url": "https://pavlos-fun-facts.dlops.io/mcp"})` and passes it as `mcp_servers=` (not `tools=`).
- *(extra)* You can speak to the same server yourself, with no model and no key. Captured from a laptop terminal (`mcp-remote/01`-`04`; the session id is shown as `<id>`). What a browser does, a plain GET:
  ```
  $ curl -si --suppress-connect-headers https://pavlos-fun-facts.dlops.io/mcp | sed 's/^\(mcp-session-id: \).*/\1<id>/' | head -12
  HTTP/2 406
  content-type: application/json
  mcp-session-id: <id>
  …
  {"jsonrpc":"2.0","id":"server-error","error":{"code":-32600,"message":"Not Acceptable: Client must accept text/event-stream"}}
  ```
  The server is up; it speaks MCP, not web pages. Then the protocol's three steps, `initialize`, `tools/list` and `tools/call`:
  ```bash
  curl -s -D /tmp/mcp-headers -X POST https://pavlos-fun-facts.dlops.io/mcp -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"8"}}}'; echo; grep -i '^mcp-session-id' /tmp/mcp-headers | sed 's/: .*/: <id>/'
  SID=$(grep -i '^mcp-session-id' /tmp/mcp-headers | cut -d' ' -f2 | tr -d '\r'); curl -s -X POST https://pavlos-fun-facts.dlops.io/mcp -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" -H "mcp-session-id: $SID" -H 'mcp-protocol-version: 2025-06-18' -d '{"jsonrpc":"2.0","method":"notifications/initialized"}'; curl -s -X POST https://pavlos-fun-facts.dlops.io/mcp -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" -H "mcp-session-id: $SID" -H 'mcp-protocol-version: 2025-06-18' -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'; echo
  SID=$(grep -i '^mcp-session-id' /tmp/mcp-headers | cut -d' ' -f2 | tr -d '\r'); curl -s -X POST https://pavlos-fun-facts.dlops.io/mcp -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" -H "mcp-session-id: $SID" -H 'mcp-protocol-version: 2025-06-18' -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"pavlos_fun_fact_mcp","arguments":{}}}'; echo
  ```
  Captured answers (one `data:` line each, trimmed):
  ```
  event: message
  data: {"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-06-18","capabilities":{…,"tools":{"listChanged":true}},"serverInfo":{"name":"Pavlos Cheese MCP","version":"1.16.0"}}}
  …
  data: {"jsonrpc":"2.0","id":2,"result":{"tools":[{"name":"pavlos_fun_fact_mcp","description":"Return one random fun fact from Pavlos about cheese. Call multiple times if you want several facts.","inputSchema":{"properties":{},"type":"object"},…}]}}
  …
  data: {"jsonrpc":"2.0","id":3,"result":{"content":[{"type":"text","text":"{\"fact\":\"Fresh cheeses (ricotta, chèvre) soften but don’t stretch like mozzarella.\",\"generated_at\":1792366391}"}],"structuredContent":{…},"isError":false}}
  ```
  One tool, one random fact per call: the agent in cell 54 does exactly this through `MCPServerStreamableHttp`.
- Cell 57 starts **your own** FastMCP server in a daemon thread at `http://127.0.0.1:8001/mcp`. The comment in that cell says port 8000 and so does its saved output (`FastMCP server starting on http://127.0.0.1:8000/mcp`, from an older version of the cell); the code uses 8001.
- *Recorded* (cell 59): uvicorn log lines interleaved with the tool's own print:
  ```
  INFO:     127.0.0.1:49802 - "POST /mcp HTTP/1.1" 200 OK
  INFO:     127.0.0.1:49802 - "POST /mcp HTTP/1.1" 200 OK
  Pavlos Fun Fact Tool Called
  INFO:     127.0.0.1:49802 - "POST /mcp HTTP/1.1" 200 OK
  Pavlos Fun Fact Tool Called
  …
  ```
- *If it fails:* rerunning cell 57 in the same runtime prints `Server thread alive: True` and then fails to bind 8001 ("address already in use"): the **old** server keeps answering (§8 C6). Restart the runtime, or use another port.

**A8. The Cheese Quiz Guild** (cells 60-77).
- Cell 62 defines the Pydantic contracts and the custom output schema `QuizAgentOutputSchema`, which validates against `quiz-schema.json`.
- Cells 64-66 define the six specialists (64 Stilton, 65 Brie, 66 Cheddar + Mozzarella + Cashew + Ricotta). Only Stilton and Brie name a model (`gpt-4o`); the other four and the orchestrator use the SDK default (`gpt-5.6-luna` with today's openai-agents). Cell 68 wraps them with `.as_tool(...)`. Cell 70 builds the orchestrator with `output_type=QuizAgentOutputSchema()`. Cell 71 runs `Runner.run(orchestrator, prompt, max_turns=12)` and renders the HTML quiz.
- *Run:* `await run_guild("Cheeses from Star Wars")` (cell 75), then `await run_guild("Greek cheeses")` (cell 77).
- *Recorded* (cell 75; cell 77 is the same shape): an interactive quiz widget, preceded on stderr by
  ```
  ERROR:openai.agents:Error getting response
  ERROR:openai.agents:Error getting response
  ERROR:openai.agents:Error getting response
  ```
  and still a quiz. The log does not say which call failed.
- *If it fails:* `MaxTurnsExceeded` means raise `max_turns`, or simplify the topic. `ModelBehaviorError: JSON failed schema validation` comes from the guardrail in cell 62.

### Part B — Tutorial 1b: llm-rag "Agents" (local Docker)

**B0. Clone and lay out the folders** (`README.md:45-69`). Skip if your L05 clone is still there.
```bash
cd ~/AC215                                           # wherever you keep your clones
git clone https://github.com/dlops-io/llm-rag.git    # README.md:48 asks for a clone; the command is not printed
mkdir secrets; ls                                    # (extra)
```
Captured (`laptop/01`, `laptop/02`):
```
Cloning into 'llm-rag'...
llm-rag  secrets
```
Copy your service-account key into `secrets/` as `llm-service-account.json` (`README.md:52-62`). `llm-rag/` and `secrets/` must sit side by side: `docker-compose.yml:11-12` mounts `../secrets` and `../llm-rag` (G8). The captures had an **empty** `secrets/`.

**B1. Start the container** (`README.md:75-85`).
- *First* (`README.md:79-80`): open a terminal in the `llm-rag` folder and edit `docker-shell.sh:7`, replacing `"ac215-project"` with your own GCP project ID.
- Captured (`laptop/04`, `laptop/05`; the captures used the placeholder `your-project-id`):
  ```
  $ cd llm-rag
  $ git log --oneline -1
  e17a39f Merge pull request #2 from obalatel/revert-1-demo-podcast
  $ git diff docker-shell.sh
  …
  -export GCP_PROJECT="ac215-project" # CHANGE TO YOUR PROJECT ID
  +export GCP_PROJECT="your-project-id" # CHANGE TO YOUR PROJECT ID
   export GOOGLE_APPLICATION_CREDENTIALS="/secrets/llm-service-account.json"
   export IMAGE_NAME="llm-rag-cli"
  ```
- *Run:* `sh docker-shell.sh`
- *Under the hood:*
  - `docker-shell.sh:7-9` exports `GCP_PROJECT`, `GOOGLE_APPLICATION_CREDENTIALS` and `IMAGE_NAME`.
  - Line 12 runs `docker compose run --rm $IMAGE_NAME`. Compose starts the `chromadb` dependency first (`docker-compose.yml:16-17`), tries to pull `llm-rag-cli` from Docker Hub (there is no such image: harmless), then builds it (`docker-compose.yml:8`; `Dockerfile:45` runs `uv sync --frozen` into `/.venv`).
  - It bind-mounts `../secrets` and `../llm-rag` (`docker-compose.yml:10-12`).
  - The entrypoint prints a banner, activates the venv and execs bash (`docker-entrypoint.sh:3-15`; the "activated" line is printed before the venv is actually activated at line 12).
- *Checkpoint.* Captured (`laptop/06-docker-shell.txt`, the build log trimmed):
  ```
  $ sh docker-shell.sh
  [+] run 8/8
   ✔ Image chromadb/chroma:latest Pulled                                     13.4s
   ✔ Network llm-rag-network      Created                                     0.0s
   ✔ Container llm-rag-chromadb   Created                                     2.0s
  Image llm-rag-cli Pulling
  Image llm-rag-cli pull access denied for llm-rag-cli, repository does not exist or may require 'docker login': denied: requested access to the resource is denied
  Image llm-rag-cli Building
  [+] Building 40.5s (13/13) FINISHED
  …
   => [5/6] RUN uv sync --frozen                                            12.7s
   => [6/6] COPY --chown=app:app . ./                                        0.8s
  …
  Image llm-rag-cli Built
  Container llm-rag-llm-rag-cli-run-61b50b7d6730 Creating
  Container llm-rag-llm-rag-cli-run-61b50b7d6730 Created
  Container is running!!!
  Architecture: x86_64
  Environment ready! Virtual environment activated.
  Python version: Python 3.12.15
  UV version: uv 0.13.1 (x86_64-unknown-linux-gnu)
  Activating virtual environment...
  app@abcf218747d0:/app$
  ```
  The part after `app@` is the container's id, new on every run.
- *(extra, second terminal on the host)* Captured (`laptop/07`):
  ```
  $ docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}'
  NAMES                                  IMAGE                    PORTS
  llm-rag-llm-rag-cli-run-61b50b7d6730   llm-rag-cli
  llm-rag-chromadb                       chromadb/chroma:latest   0.0.0.0:8000->8000/tcp
  ```
  Chroma publishes port 8000 on your laptop. Remember that for Part C (G3).
- *(extra, at the container prompt)* `whoami; pwd; which python; python --version` printed `app`, `/app`, `/.venv/bin/python`, `Python 3.12.15` (`cli-container/00`), and `uv pip list` showed chromadb 1.1.0, google-auth 2.41.1 and google-genai 1.39.1, as `uv.lock` pins them (`cli-container/01`).
- *If it fails:* see G5 (project / key) and G8 (folder names).

**B2. Make sure the collection exists and is current.** The Agents section doesn't say so, but the agent needs L05's `char-split-collection`.
- *On a fresh clone*, the README's command fails at once. Captured (`cli-container/10`, traceback trimmed):
  ```
  $ python cli.py --agent --chunk_type char-split
  CLI Arguments: Namespace(chunk=False, embed=False, load=False, query=False, chat=False, get=False, agent=True, chunk_type='char-split')
  agent()
  Traceback (most recent call last):
    File "/app/cli.py", line 551, in <module>
      main(args)
    File "/app/cli.py", line 503, in main
      agent(method=args.chunk_type)
    File "/app/cli.py", line 429, in agent
      collection = client.get_collection(name=collection_name)
  …
  chromadb.errors.NotFoundError: Collection [char-split-collection] does not exist
  ```
  That is `cli.py:429`, before any call to Gemini (exit 1). `python cli.py --get --chunk_type char-split` fails the same way at `cli.py:411` (`cli-container/11`). The Chroma data lives in `llm-rag/docker-volumes/chromadb`, which is git-ignored (`llm-rag/.gitignore:3`), so a fresh clone has none.
- *Kept L05's database?* It is still in `docker-volumes/chromadb`. **Rebuild it anyway if you chunked before 2026-09-22**: that day Pavlos's book `Tolminc Cheese.txt` was rewritten into a fictional story (commit `85bba32`).
- *Otherwise* chunk, embed and load (`README.md:103`, `:129`, `:151`; the three flags may also be combined, because `main()` checks them in order, `cli.py:484-491`):
  ```bash
  python cli.py --chunk --chunk_type char-split
  python cli.py --embed --chunk_type char-split
  python cli.py --load --chunk_type char-split
  ```
  `--embed` needs your key. The captures had none, so the staff's committed embeddings stood in for it: commit `68e0bde` (2026-10-07, still in `main`'s history) has the 11 `embeddings-char-split-*.jsonl` files under `llmrag/outputs/`, made from today's book (`laptop/08`: `11` files, `31M total`). The load itself is real. Captured (`cli-container/20`, trimmed):
  ```
  $ python cli.py --load --chunk_type char-split
  CLI Arguments: Namespace(chunk=False, embed=False, load=True, query=False, chat=False, get=False, agent=False, chunk_type='char-split')
  load()
  Creating collection: char-split-collection
  Collection 'char-split-collection' did not exist. Creating new.
  Created new empty collection 'char-split-collection'
  Collection: Collection(name=char-split-collection)
  Number of files to process: 11
  Processing file: outputs/embeddings-char-split-The Complete Book of Cheese.jsonl
  Shape: (1355, 3)
  …
  Processing file: outputs/embeddings-char-split-Tolminc Cheese.jsonl
  Shape: (24, 3)
                                                 chunk  ...                                          embedding
  0  Author: Pavlos Protopapas\n\n# Tolminc: A Chee...  ...  [0.013855794400000001, 0.0074510882, 0.0098504...
  …
  Inserted 24 items...
  Finished inserting 24 items into collection 'char-split-collection'
  ```
  11 books, **8,248** chunks in all; the instructor's story is just 24 of them. `load` drops and recreates the collection (`cli.py:280-289`), so rerunning it is safe.
- *(extra)* `python cli.py --get --chunk_type char-split` fetches 10 documents `where={"book": "The Complete Book of Cheese"}` (`cli.py:402-418`) and makes no Vertex AI call. Captured (`cli-container/21`, trimmed; the order of metadata keys varies):
  ```
  Results: {'ids': ['1021665fac86c5a5-0', '1021665fac86c5a5-1', …], 'embeddings': None, 'metadatas': [{'author': 'Bob Brown', 'book': 'The Complete Book of Cheese', 'year': 2024}, …
  ```
  Empty lists (`'ids': []`) would mean the collection exists but is empty: the load never succeeded.
- *(extra)* Which books can `get_book_by_author` reach? A script typed at the container prompt counts the chunks per enum author:
  ```bash
  python - <<'EOF'
  import cli, agent_tools
  c = cli.chromadb.HttpClient(host=cli.CHROMADB_HOST, port=cli.CHROMADB_PORT).get_collection("char-split-collection")
  enum = agent_tools.get_book_by_author_func.parameters.properties["author"].enum
  metas = c.get(include=["metadatas"])["metadatas"]
  print("chunks in char-split-collection:", len(metas))
  print("author (enum value)                          chunks")
  for a in enum:
      print(f"  {a:<42} {sum(m.get('author') == a for m in metas):>5}")
  print("books whose chunks no enum value can select:")
  for b in sorted({m["book"] for m in metas if m.get("author") not in enum}):
      n = sum(m["book"] == b for m in metas)
      print(f"  {b!r}: {n} chunks, author = {next(m.get('author') for m in metas if m['book'] == b)!r}")
  EOF
  ```
  Captured (`cli-container/34`, trimmed):
  ```
  chunks in char-split-collection: 8248
  author (enum value)                          chunks
    C. F. Langworthy and Caroline Louisa Hunt    401
  …
    Pavlos Protopapas                             24
  books whose chunks no enum value can select:
    'Cottage Cheese Recipe Book': 178 chunks, author = 'Milk Industry Foundation'
    'Womans Institute Library of Cookery': 1505 chunks, author = None
  ```
  Two of the 11 books can never be reached by author, for two different reasons (E4); both stay reachable through `get_book_by_search_content`.

**B3. Run the agent** (`README.md:257-259`).
```bash
python cli.py --agent --chunk_type char-split
```
- *Under the hood* (`cli.py:421-478`):
  1. Connect to `llm-rag-chromadb:8000` and get `char-split-collection` (`cli.py:425-429`).
  2. Build the user turn "Describe where cheese making is important in Pavlos's book?" (`cli.py:432-437`).
  3. **Call 1:** `generate_content` with `temperature=0`, `tools=[agent_tools.cheese_expert_tool]` and `FunctionCallingConfig(mode="any")` (`cli.py:441-453`).
  4. Extract `function_call` parts (`cli.py:457`) and execute them. `get_book_by_author` embeds `search_content` and queries Chroma with `n_results=10, where={"author": author}` (`agent_tools.py:41-49`). The 10 chunks are joined into one string, wrapped with `Part.from_function_response(name=…, response={"content": …})` (`agent_tools.py:103-110`).
  5. **Call 2:** send [user turn, the model's own function-call content *unchanged*, the function responses] (`cli.py:465-477`).
- *Without a key* (the captures). With the collection loaded, the lookup passes and the question prints; then the first model call asks for credentials. Captured (`cli-container/30`, traceback trimmed):
  ```
  $ python cli.py --agent --chunk_type char-split
  CLI Arguments: Namespace(chunk=False, embed=False, load=False, query=False, chat=False, get=False, agent=True, chunk_type='char-split')
  agent()
  …
  user_prompt_content:  parts=[Part(
    text="Describe where cheese making is important in Pavlos's book?"
  )] role='user'
  Traceback (most recent call last):
  …
    File "/app/cli.py", line 441, in agent
      response = llm_client.models.generate_content(
  …
  google.auth.exceptions.DefaultCredentialsError: File /secrets/llm-service-account.json was not found.
  ```
  google-genai loads credentials lazily, on the first request.
- *(extra)* **What Gemini receives in call 1.** This script runs `cli.agent()` unchanged, but replaces the SDK's HTTPS request with a function that prints the URL and the JSON body and stops. Nothing is sent. Type it at the container prompt:
  ```bash
  python - <<'EOF'
  import json, cli
  api = cli.llm_client._api_client
  def show(method, path, body, http_options=None):     # stands in for the HTTPS request
      req = api._build_request(method, path, body, http_options)
      print(method.upper(), req.url)
      print(json.dumps(body, indent=2))
      raise SystemExit("-- stopped here: nothing was sent to Vertex AI --")
  api.request = show
  cli.agent(method="char-split")
  EOF
  ```
  Captured (`cli-container/31`, trimmed):
  ```
  POST https://aiplatform.googleapis.com/v1beta1/projects/your-project-id/locations/global/publishers/google/models/gemini-3.1-flash-lite:generateContent
  {
    "contents": [
      {
        "parts": [
          {
            "text": "Describe where cheese making is important in Pavlos's book?"
          }
        ],
        "role": "user"
      }
    ],
    "tools": [
      {
        "functionDeclarations": [
          {
            "description": "Get the book chunks filtered by author name",
            "name": "get_book_by_author",
  …
                  "enum": [
                    "C. F. Langworthy and Caroline Louisa Hunt",
  …
                    "Pavlos Protopapas"
                  ],
  …
            "name": "get_book_by_search_content",
  …
    "toolConfig": {
      "functionCallingConfig": {
        "mode": "ANY"
      }
    },
    "generationConfig": {
      "temperature": 0.0
    }
  }
  -- stopped here: nothing was sent to Vertex AI --
  ```
  One envelope: the question, both declarations with the enum, mode ANY, temperature 0, and **no system instruction** (E3). And `python -c 'from google.genai import types; print(repr(types.FunctionCallingConfig(mode="any")))'` *(extra)* prints `mode=<FunctionCallingConfigMode.ANY: 'ANY'>` (`cli-container/32`).
- *Recorded: what the staff saw* (`out.txt:14-67`, trimmed). The model's whole answer to call 1 is a function call:
  ```
  LLM Response: sdk_http_response=HttpResponse(
    headers=<dict len=10>
  ) candidates=[Candidate(
    content=Content(
      parts=[
        Part(
          function_call=FunctionCall(
            args={
              'author': 'Pavlos Protopapas',
              'search_content': 'cheese making importance location'
            },
            id='call_1212960',
            name='get_book_by_author'
          ),
          thought_signature=b'\x01\x8f=k_:\x12\xee…'
        ),
      ],
      role='model'
    ),
  …
    total_token_count=247,
  …
  ) automatic_function_calling_history=[] parsed=None
  …
  Function calls: [FunctionCall(
  …
  )]
  Function: get_book_by_author


  Calling function with args: Pavlos Protopapas , cheese making importance location
  ```
  Four words of search text, although the parameter's description asks the model to "Expand the search term to a a sentence or two" (`agent_tools.py:33`). `automatic_function_calling_history=[]`: the SDK ran nothing, because it was given declarations, not Python functions.
- *(extra)* **Your code makes the call, and call 2.** This script takes the staff's recorded function call, runs it through the tutorial's own `agent_tools.execute_function_calls` against your collection, then prints call 2's request the same way. One stand-in: without Vertex AI the search text cannot be embedded, so `embed_func` returns the stored vector of a Tolminc chunk that mentions "curd"; *which* 10 of the book's 24 chunks come back is therefore not what the real query would return.
  ```bash
  python - <<'EOF'
  import ast, json, re, cli, agent_tools
  from google.genai import types
  from google.genai.types import Content, Part
  collection = cli.chromadb.HttpClient(host=cli.CHROMADB_HOST, port=cli.CHROMADB_PORT).get_collection("char-split-collection")
  t = collection.get(where={"book": "Tolminc Cheese"}, include=["embeddings", "documents"])
  i = next(k for k, d in enumerate(t["documents"]) if "curd" in d)
  print("stand-in embed_func: returns the stored vector of chunk", t["ids"][i], "(Tolminc Cheese)")
  stand_in = lambda text: t["embeddings"][i]
  # the model's turn, from the staff's recorded run
  rec = open("out.txt").read().splitlines()
  sig = ast.literal_eval(rec[27].strip().removeprefix("thought_signature=").rstrip(","))
  call = types.FunctionCall(id="call_1212960", name="get_book_by_author",
                            args={"author": "Pavlos Protopapas", "search_content": "cheese making importance location"})
  model_turn = Content(role="model", parts=[Part(function_call=call, thought_signature=sig)])
  print("Function calls:", [call])
  function_responses = agent_tools.execute_function_calls([call], collection, embed_func=stand_in)
  print()
  print("function_responses: %d part, name=%r, response keys=%s, %d characters" % (
      len(function_responses), function_responses[0].function_response.name,
      list(function_responses[0].function_response.response), len(function_responses[0].function_response.response["content"])))
  print()
  api = cli.llm_client._api_client
  def show(method, path, body, http_options=None):     # stands in for the HTTPS request
      req = api._build_request(method, path, body, http_options)
      print(method.upper(), req.url)
      print(json.dumps(body, indent=2))
      raise SystemExit("-- stopped here: nothing was sent to Vertex AI --")
  api.request = show
  user_prompt_content = Content(role="user", parts=[Part(text="Describe where cheese making is important in Pavlos's book?")])
  cli.llm_client.models.generate_content(          # the call of cli.py:465-477, with the same arguments
      model=cli.GENERATIVE_MODEL,
      contents=[user_prompt_content, model_turn, Content(parts=function_responses)],
      config=types.GenerateContentConfig(tools=[agent_tools.cheese_expert_tool]))
  EOF
  ```
  Captured (`cli-container/33`, trimmed):
  ```
  Function: get_book_by_author


  Calling function with args: Pavlos Protopapas , cheese making importance location


  Response: is ready?” Mara asked.

  “For what?”
  …
  Mara tasted a piece. It was firm at first, then softer as she chewed. …

  function_responses: 1 part, name='get_book_by_author', response keys=['content'], 3509 characters

  POST https://aiplatform.googleapis.com/v1beta1/projects/your-project-id/locations/global/publishers/google/models/gemini-3.1-flash-lite:generateContent
  {
    "contents": [
      {
        "parts": [ { "text": "Describe where cheese making is important in Pavlos's book?" } ],
        "role": "user"
      },
      {
        "parts": [
          {
            "thoughtSignature": "AY89a186Eu6171rjNqS7…",
            "functionCall": {
              "id": "call_1212960",
              "args": { "author": "Pavlos Protopapas", "search_content": "cheese making importance location" },
              "name": "get_book_by_author"
            }
          }
        ],
        "role": "model"
      },
      {
        "parts": [
          {
            "functionResponse": {
              "name": "get_book_by_author",
              "response": { "content": "is ready?” Mara asked.\n\n“For what?” …" }
            }
          }
        ]
      }
    ],
    "tools": [ … the same two declarations … ],
    "generationConfig": {}
  }
  -- stopped here: nothing was sent to Vertex AI --
  ```
  (Short JSON objects are joined onto one line here.) Call 2 carries three contents: the question, the model's own turn unchanged with its `thoughtSignature`, and your function response, with no role and no `id` (it is matched by name). The tools go along again, but there is **no `toolConfig`**: the mode is back to AUTO.
- *Recorded: the staff's answer* (`out.txt:98-135`, trimmed):
  ```
  LLM Response: sdk_http_response=HttpResponse(
  …
          text="""In Pavlos Protopapas's work, cheese-making—specifically that of **Tolminc cheese**—is highlighted as fundamentally important to the **Alpine region, particularly the Soča Valley.**
  …
  *   **Survival and Tradition:** The production of Tolminc cheese was essential for the region's traditional lifestyle, known as *transhumance* (the seasonal movement of livestock), …
  …
    total_token_count=1269,
  …
  ```
  Two model calls (247 and 1,269 tokens) and one embedding call per question, all paid.
- **Expect different content than `out.txt`.** The recorded run retrieved and answered from the book *before* `85bba32`: the commit that added `out.txt` also rewrote the book. Captured (`laptop/09`, `laptop/10`):
  ```
  $ git show --stat --format='%h %ad %s' --date=short 85bba32; head -4 'input-datasets/books/Tolminc Cheese.txt'
  85bba32 2026-09-22 llm and agent with updated pavlos book

   input-datasets/books/Tolminc Cheese.txt | 311 ++++++++++++++++++++------------
   out.txt                                 |  93 ++++++++++
   2 files changed, 291 insertions(+), 113 deletions(-)
  Author: Pavlos Protopapas

  # Tolminc: A Cheese, a Valley, and the Art of Waiting
  *A fictional tale inspired by Alpine cheesemaking*
  ```
  ```
  $ for w in transhumance 'Soča' 'Monastic' 'cultural artifact'; do printf '%-18s out.txt %2s   book today %2s   book before 85bba32 %2s\n' "$w" "$(grep -c "$w" out.txt)" "$(grep -c "$w" 'input-datasets/books/Tolminc Cheese.txt')" "$(git show '85bba32^:input-datasets/books/Tolminc Cheese.txt' | grep -c "$w")"; done
  transhumance       out.txt  2   book today  0   book before 85bba32  3
  Soča              out.txt  3   book today  0   book before 85bba32  7
  Monastic           out.txt  1   book today  0   book before 85bba32  1
  cultural artifact  out.txt  2   book today  0   book before 85bba32  1
  ```
  With today's book you get passages about Mara, her grandfather, the curd and the wheels. The README diagram's sample answer ("…a traditional cheese made in the Slovenian Alps…", `images/llm-rag-flow-3.png`) also comes from the old book. An index answers from what was loaded.
- *With your key, look for* (no values invented here): `user_prompt_content:` (`cli.py:440`); the first `LLM Response:` whose part is a `function_call` (`cli.py:454`); `Function calls: [FunctionCall(` (`cli.py:458`); `Function: get_book_by_author` and `Calling function with args: …` (`agent_tools.py:87-93`); `Response:` with 10 chunks (`agent_tools.py:101`); the second `LLM Response:` with `text=` (`cli.py:478`).
- *If it fails:*
  - `KeyError: 'GCP_PROJECT'`: you are not inside the container started by `docker-shell.sh`.
  - `NotFoundError … does not exist` at `cli.py:429`: the collection is missing (B2, G6).
  - `DefaultCredentialsError: File /secrets/llm-service-account.json was not found.` at `cli.py:441`: the key is missing or in the wrong folder (G5, G8).
  - `403 PERMISSION_DENIED`: the service-account role is missing, the Vertex AI API is disabled, or `GCP_PROJECT` is still `ac215-project`. Unlike `--embed`, the agent's calls have no retry loop, so the error is immediate.
  - `404 … model`: the project cannot see `gemini-3.1-flash-lite` in location `global`. Check model availability.

**B4. Read the output like a debugger.** Find the three objects of §3.2: the `FunctionCall` (with an `id='call_…'`), your `Response:` block, and the final text. `cli.py:478` prints the whole response object, although the README says "Displays the LLM's response" (E5): `print(response.text)` shows only the answer. If call 2 answers with another function call instead of text, `response.text` is `None` and nothing runs that call (§8 C2).

**B5. (Optional) Hosted demo.** The "Cheese Agent Tool" at https://ac215-llm-rag.dlops.io/agent (`README.md:268`; use Chrome). Captured (`laptop/11`, *extra*):
```
$ curl -s -o /dev/null -w '%{http_code} %{content_type}\n' https://ac215-llm-rag.dlops.io/agent
200 text/html; charset=utf-8
```
The compose file whitelists that origin for browser access to your local Chroma (`docker-compose.yml:25-26`), which is how the hosted **Chroma UI** (`README.md:162`) can read `localhost:8000`.

**B6. Exit and tear down.** Captured (`laptop/06` end, `laptop/12`-`14`):
```
app@abcf218747d0:/app$ exit
exit
$ docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}'
NAMES              IMAGE                    PORTS
llm-rag-chromadb   chromadb/chroma:latest   0.0.0.0:8000->8000/tcp
$ docker compose down
WARN[0000] The "GOOGLE_APPLICATION_CREDENTIALS" variable is not set. Defaulting to a blank string.
WARN[0000] The "GCP_PROJECT" variable is not set. Defaulting to a blank string.
[+] down 2/2
 ✔ Container llm-rag-chromadb Removed                                       0.2s
 ✔ Network llm-rag-network    Removed                                       0.2s
$ git status --short
 M docker-shell.sh
```
`exit` removes only the one-off container (`--rm`); Chroma keeps running on port 8000 until `docker compose down` (G4). The two warnings are harmless: outside `docker-shell.sh` those variables are not set. Your index stays on disk in `./docker-volumes/chromadb`, and Part C needs port 8000.

### Part C — Tutorial 1c: Google ADK (`llm-agent-google-adk`, local uv)

No Docker in this part: ADK runs in a uv environment on your laptop.

**C1. Clone and configure** (`README.md:72-94`). Captured (`adk-laptop/01`-`06`):
```
$ git clone https://github.com/dlops-io/llm-agent-google-adk.git
Cloning into 'llm-agent-google-adk'...
$ cd google-adk-tutorial
bash: line 1: cd: google-adk-tutorial: No such file or directory
$ cd llm-agent-google-adk
$ ls -a
.             .git        2-litellm           5-custom-agent  README.md
..            .gitignore  3-mcp-tools         6-rag           demo.gif
.env.example  1-baseline  4-production-ready  QUICKSTART.md   pyproject.toml
$ cp .env.example .env
$ grep -v '^#' .env | grep .
GOOGLE_API_KEY=your_google_ai_api_key_here
AWS_OPENAI_API_KEY=your_aws_openai_api_key_here
GEMINI_MODEL=gemini-2.5-flash
ENVIRONMENT=development
```
- The README writes `git clone <repository-url>` and then `cd google-adk-tutorial` (`README.md:77-78`); the folder is named after the repo (E8).
- No `uv.lock`: it is git-ignored (`.gitignore:34`), so everyone resolves fresh versions. `pyproject.toml:9-20` asks for `google-adk>=1.8.0` with no upper bound, plus LiteLLM, FastAPI, MCP, the Vertex SDK, **chromadb and sentence-transformers (which pulls PyTorch)**.
- *Do:* create a key in [Google AI Studio](https://aistudio.google.com/app/apikey) and paste it after `GOOGLE_API_KEY=` (`README.md:85-94`). Also change the model line: `GEMINI_MODEL=gemini-3.1-flash-lite` (the model llm-rag uses, `cli.py:27`). Google lists the code's fallback `gemini-2.0-flash` as shut down and limits `gemini-2.5-flash` to earlier users (G2). Keep everything in this **root** `.env`: ADK loads only the nearest one.

**C1, continued: `uv sync` fails, then the fix** (`README.md:96-103`).
- *Captured on a laptop with no Python* (`adk-laptop/00`: `no python3 on PATH`; `adk-laptop/07`, wrapped lines joined):
  ```
  $ uv sync
  Using CPython 3.15.0
  Creating virtual environment at: .venv
  Resolved 189 packages in 3.46s
  error: Distribution `onnxruntime==1.31.0 @ registry+https://pypi.org/simple` can't be installed because it doesn't have a source distribution or wheel for the current platform

  hint: You're using CPython 3.15 (`cp315`), but `onnxruntime` (v1.31.0) only has wheels with the following Python ABI tags: `cp311`, `cp312`, `cp313`, `cp313t`, `cp314`, `cp314t`
  ```
  Exit 2. With no Python around, uv downloads the newest CPython (as in L01). `onnxruntime` comes in through `chromadb` and has wheels only up to 3.14. The same happens on a laptop *with* an older Python if uv already manages a 3.15 (uv prefers its own Pythons; §8 C3). The failed sync left a `.venv` on CPython 3.15 and a `uv.lock` of 189 packages (`adk-laptop/08`).
- *The fix* *(extra, not in the README)*: pin a Python the wheels support (any of 3.11-3.14), then sync again. Captured (`adk-laptop/09`, `12`, `13`, `14`; the package list trimmed):
  ```
  $ uv python pin 3.13
  Pinned `.python-version` to `3.13`
  $ uv sync
  Using CPython 3.13.16
  Removed virtual environment at: .venv
  Creating virtual environment at: .venv
  …
   + chromadb==1.5.9
  …
   + google-adk==2.12.0
  …
   + onnxruntime==1.31.0
  …
  $ uv run adk --version
  adk, version 2.12.0
  $ uv pip list 2>/dev/null | grep -E '^(google-adk|google-genai|litellm|fastapi|uvicorn|mcp|chromadb|sentence-transformers|torch|onnxruntime) '; du -sh .venv
  chromadb                                 1.5.9
  fastapi                                  0.141.1
  google-adk                               2.12.0
  google-genai                             2.31.0
  litellm                                  1.106.0
  mcp                                      2.3.0
  onnxruntime                              1.31.0
  sentence-transformers                    6.1.0
  torch                                    2.14.1+cpu
  uvicorn                                  0.54.0
  1.6G	.venv
  ```
  On your laptop the sync says `Resolved 189 packages` and installs plain `torch==2.14.1`; `uv sync --dry-run` on a Linux PC lists `torch==2.14.1`, `triton==3.8.0` and 15 `nvidia-*` packages (about 3 GB more; `adk-laptop/10`). Versions at the time of recording.
- *Not a fix:* the earlier version of this guide (and the digest) suggested `uv add "google-adk>=1.8.0,<1.28"`. Captured (`adk-laptop/21`-`26`): it installs `google-adk==1.27.5`, but the dev UI still can't run `1-baseline` (C2 below). `git checkout pyproject.toml; uv sync --upgrade-package google-adk` undoes it (`adk-laptop/27`).

**C2. Run the web UI, and the folder names** (`README.md:109-119`).
```bash
uv run adk web
```
- *Captured* (`adk-laptop/15`, wrapped lines joined, warnings trimmed). ADK 2.12 first asks a question the README doesn't mention:
  ```
  $ uv run adk web
  Help improve the ADK (CLI and Web UI) by allowing Google to collect pseudonymized usage data?
  …
  This is OFF by default. You can opt out at any time using the 'adk telemetry disable' command or Web UI user settings.

  Enable telemetry? [Y/n]: n
  …
  INFO:     Started server process [3865]
  INFO:     Waiting for application startup.

  +-----------------------------------------------------------------------------+
  | ADK Web Server started                                                      |
  |                                                                             |
  | For local testing, access at http://127.0.0.1:8000.                         |
  +-----------------------------------------------------------------------------+

  INFO:     Application startup complete.
  INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
  ```
  The capital `Y` means that pressing Enter answers **yes**, although the text says telemetry is off by default (G21). Answer as you like; `uv run adk telemetry disable` changes it later (it writes `{"telemetry": false}` to `~/.adk/config.json`).
- *Open* http://localhost:8000. *(extra)* From a second terminal, captured (`adk-laptop/16`, `17`):
  ```
  $ curl -s -o /dev/null -w '%{http_code} -> %{redirect_url}\n' http://localhost:8000/
  307 -> http://localhost:8000/dev-ui/
  $ curl -s http://localhost:8000/list-apps; echo
  ["1-baseline","2-litellm","3-mcp-tools","4-production-ready.app","5-custom-agent","6-rag.1-vertex-rag-engine","6-rag.2-custom-chromadb-rag"]
  ```
  The dropdown lists seven entries, nested ones included.
- *Pick `1-baseline`* (as `1-baseline/README.md:86` says) and the page refuses. Captured (`adk-laptop/18`, the request the page makes):
  ```
  $ curl -s http://localhost:8000/dev/apps/1-baseline/build_graph; echo
  {"detail":"Invalid agent name: '1-baseline'. Agent names must be valid Python identifiers or paths separated by dots (letters, digits, underscores, and dots)."}
  ```
  Each folder name becomes the app's name, and a Python identifier holds only letters, digits and underscores and never starts with a digit. `1-baseline` breaks both rules (G1).
- *An older ADK doesn't help* (captured "what if", `adk-laptop/21`-`26`): after `uv add "google-adk>=1.8.0,<1.28"`, `uv run adk --version` says `adk, version 1.27.5`, the list shows only `["1-baseline","2-litellm","3-mcp-tools","5-custom-agent"]`, and picking `1-baseline` returns `Internal Server Error`; the server log says
  ```
  pydantic_core._pydantic_core.ValidationError: 1 validation error for App
    Value error, Invalid app name '1-baseline': must be a valid identifier consisting of letters, digits, and underscores. …
  ```
- *What works: rename the folders* *(extra, not in the README)*. Stop the server with Ctrl+C, then (captured, `adk-laptop/28`):
  ```
  $ mv 1-baseline baseline; mv 3-mcp-tools mcp_tools; mv 5-custom-agent custom_agent; ls
  2-litellm
  4-production-ready
  6-rag
  QUICKSTART.md
  README.md
  baseline
  custom_agent
  demo.gif
  mcp_tools
  pyproject.toml
  uv.lock
  ```
  Start `uv run adk web` again and pick `baseline`. Captured (`adk-laptop/29`, `30`):
  ```
  … - INFO - envs.py:83 - Loaded .env file for baseline at /home/student/AC215/llm-agent-google-adk/.env
  … - INFO - agent_loader.py:189 - Found root_agent in baseline.agent
  INFO:     127.0.0.1:42412 - "GET /dev/apps/baseline/build_graph HTTP/1.1" 200 OK
  … - INFO - local_storage.py:65 - Creating local session service at /home/student/AC215/llm-agent-google-adk/baseline/.adk/session.db
  ```
  ```
  $ curl -s http://localhost:8000/list-apps; echo
  ["2-litellm","4-production-ready.app","6-rag.1-vertex-rag-engine","6-rag.2-custom-chromadb-rag","baseline","custom_agent","mcp_tools"]
  ```
  The root `.env` is the one loaded, and the sessions live in a file inside the agent's folder (G22).
- *Two more slips* (captured): `QUICKSTART.md:24`'s `uv run adk web 1-baseline/agent.py` passes a file where a folder is expected (`Error: Invalid value for '[AGENTS_DIR]': Directory '1-baseline/agent.py' is a file.`, exit 2; `adk-laptop/19`, G9), and the module READMEs' `uv run adk` (without `web`) prints the usage and command list, then exits 2 (`adk-laptop/20`, G10).
- *The port clash* (captured "what if", `adk-laptop/36`): with a Chroma server on port 8000, `adk web` prints its banner, then
  ```
  ERROR:    [Errno 98] error while attempting to bind on address ('127.0.0.1', 8000): address already in use
  ```
  and shuts down (exit 3). Run `docker compose down` in `llm-rag/` first, or `uv run adk web --port 8080` (captured: `Uvicorn running on http://127.0.0.1:8080`, and the list answers on 8080; `adk-laptop/37`, `38`). G3.

**C3. Module 1: the travel-planner pipeline** (`1-baseline/README.md:76-92`, `1-baseline/agent.py:14-39`; your copy is `baseline/agent.py`).
- *Skip the module README's own Setup* (`1-baseline/README.md:52-74`: `uv sync` and `cp .env.example .env`). The same two steps appear in `2-litellm/README.md:22-48`, `3-mcp-tools/README.md:29-51` and `5-custom-agent/README.md:93-99`. Run inside a module, `cp` creates a module `.env`, and ADK then loads only that file: checked (§8 C1), the log then says `Loaded .env file for baseline at …/baseline/.env` and every agent shows `model gemini-2.0-flash` with the placeholder key.
- *(extra)* The agent tree the UI loads, captured from a second terminal (`adk-laptop/31`):
  ```
  $ curl -s http://localhost:8000/dev/apps/baseline/build_graph | uv run python -c "import json, sys; r = json.load(sys.stdin)['root_agent']; print(r['name'], '|', r['description']); [print('  ', a['name'], '| model', a['model'], '| output_key', a['output_key'], '|', a['instruction']) for a in r['sub_agents']]"
  TravelPlannerPipeline | Sequential itinerary planning pipeline
     ItineraryValidator | model gemini-2.5-flash | output_key itinerary_validation | You validate trip requests. Extract traveler count, origin, destinations, dates, budget, and constraints from the input.
     TravelPlanner | model gemini-2.5-flash | output_key travel_plan | Using {itinerary_validation}, design a realistic multi-day travel plan with routing, daily schedule, estimated costs, and key booking recommendations.
     TripSummarizer | model gemini-2.5-flash | output_key trip_summary | Provide a concise, traveler-friendly summary based on {travel_plan}. Include total estimated cost and a highlights list.
  ```
  Three `LlmAgent`s with a model (from your root `.env`; the captures kept the file's `gemini-2.5-flash`: set yours), an instruction and an output key, and **no tools**: the planner's prices are the model's guesses.
- *(extra)* A new session, captured (`adk-laptop/32`):
  ```
  $ curl -s -X POST http://localhost:8000/apps/baseline/users/student/sessions; echo
  {"id":"df359f87-50e3-41fd-8409-2c4296b4ba20","appName":"baseline","userId":"student","state":{},"events":[],"lastUpdateTime":1792366364.9382024}
  ```
  An empty whiteboard: no state, no events yet.
- *Do:* type a trip request (the README gives no example), e.g. "2 adults, Boston to Montreal, Oct 30 - Nov 2, 1500 dollars, train preferred".
- *Under the hood:* `SequentialAgent` runs `ItineraryValidator` → `TravelPlanner` → `TripSummarizer`. Each `output_key` lands in session state, and `{itinerary_validation}` / `{travel_plan}` are filled into the next instruction (§3.6).
- *Without a real key* (captured, `adk-laptop/33` and the server log `29`): sending that request through `POST /run` returns `Internal Server Error`, and the log says why:
  ```
  google.genai.errors.ClientError: 400 INVALID_ARGUMENT. {'error': {'code': 400, 'message': 'API key not valid. Please pass a valid API key.', 'status': 'INVALID_ARGUMENT', …
  ```
  `adk web` starts and loads agents with the placeholder key; it fails only when a message reaches Google (G2).
- *With your key, look for:* three replies in order, and three entries in the State tab: `itinerary_validation`, `travel_plan`, `trip_summary`. Each request is three model calls. The session is stored in `baseline/.adk/session.db` and survives a restart of `adk web` (§8 B4).
- *If it fails* with `404 … models/gemini-2.0-flash`: your `.env` has no `GEMINI_MODEL`, or a module `.env` overrides it (G2).

**C4. Module 2: LiteLLM** (`2-litellm/README.md:67-88`).
- *As written* it cannot work: the folder name is refused (G1), `root_agent = LlmAgent(model="gpt-4", …)` (`2-litellm/agent.py:25-29`) is a bare model name, and the `.env.example` key `AWS_OPENAI_API_KEY` is read by no code (`litellm_config.py:28` reads `OPENAI_API_KEY`). On ADK 2.12.0 a bare `"gpt-4"` resolves to ADK's own `OpenAILlm` class, not to LiteLLM; on 1.x it raised `Model gpt-4 not found.` (G11).
- *Fix:* §8 B7 (copy the folder to a valid name such as `litellm_agent`, not `litellm`, which clashes with the package; use `LiteLlm(model="openai/gpt-5.6-luna")` and `OPENAI_API_KEY`).
- *Optional check:* the README's `uv run python litellm_config.py` (`2-litellm/README.md:81-88`) prints **nothing**, whatever keys you set: the module only defines `configure_litellm()` and `get_available_models()` and has no `__main__` block (G19).

**C5. Module 3: MCP filesystem tools** (`3-mcp-tools/README.md:53-94`; your copy is `mcp_tools/`).
- *Prereq:* Node.js. Captured (`adk-laptop/34`, *extra*): `node --version; npx --version` → `v24.22.0`, `11.19.1`.
- *Under the hood:* `MCPToolset(StdioConnectionParams(StdioServerParameters(command='npx', args=['-y', '@modelcontextprotocol/server-filesystem', ALLOWED_PATH]), timeout=10), tool_filter=[...])` (`3-mcp-tools/agent.py:20-29`). ADK spawns the Node server as a **child process** and talks MCP over its stdin/stdout. `ALLOWED_PATH` defaults to the module folder (`agent.py:17-18`).
- *(extra)* Ask the agent's own toolset for its tools, with no model involved. From the repository root:
  ```bash
  uv run python - <<'EOF'
  import asyncio, importlib.util
  spec = importlib.util.spec_from_file_location("mcp_tools_agent", "mcp_tools/agent.py")
  agent = importlib.util.module_from_spec(spec); spec.loader.exec_module(agent)
  async def main():
      tools = await agent.toolset.get_tools()
      print("tools the agent sees:", [t.name for t in tools])
      session = await agent.toolset._mcp_session_manager.create_session()
      listed = await session.list_tools()
      print("tools the server offers:", len(listed.tools), [t.name for t in listed.tools])
      result = await session.call_tool("list_directory", {"path": agent.ALLOWED_PATH})
      print("list_directory", agent.ALLOWED_PATH, "->")
      print(result.content[0].text)
      await agent.toolset.close()
  asyncio.run(main())
  EOF
  ```
  Captured (`adk-laptop/35`, `[EXPERIMENTAL]` warnings and an `npm notice` trimmed):
  ```
  Secure MCP Filesystem Server running on stdio
  Client does not support MCP Roots, using allowed directories set from server args: [ '/home/student/AC215/llm-agent-google-adk/mcp_tools' ]
  …
  tools the agent sees: ['list_directory', 'read_file', 'search_files']
  tools the server offers: 14 ['read_file', 'read_text_file', 'read_media_file', 'read_multiple_files', 'write_file', 'edit_file', 'create_directory', 'list_directory', 'list_directory_with_sizes', 'directory_tree', 'move_file', 'search_files', 'get_file_info', 'list_allowed_directories']
  list_directory /home/student/AC215/llm-agent-google-adk/mcp_tools ->
  [FILE] .env.example
  [FILE] README.md
  [DIR] __pycache__
  [FILE] agent.py
  [FILE] pyproject.toml
  ```
  The server offers 14 tools, including `write_file` and `edit_file`; the filter lets three through.
- *Do (with your key):* in the UI pick `mcp_tools` and ask "List files in this directory", then "Read the README.md file" (`3-mcp-tools/README.md:88-92`). Look for function-call events for `list_directory` and `read_file` in the Events tab. The README's fourth prompt, "Search for files containing 'agent'", exercises `search_files`, which matches file **names** with a glob pattern, not contents (§8 B8).
- *If it fails:* `npx: command not found` → install Node. The first run downloads the package; on a slow network the 10 s `timeout` gives a connection timeout, so retry (G12).

**C6. Module 4: FastAPI deployment** (`4-production-ready/README.md:9-52`).
- Its `app/` package is not an `adk web` agent folder (it appears in 2.12's list as `4-production-ready.app`).
- *Run from the root venv* (the README's per-module `uv sync` builds a second venv with `google-adk[all]`):
  ```bash
  cd 4-production-ready
  uv run --project .. uvicorn app.main:app --port 8080
  curl -X POST http://localhost:8080/chat \
    -H "Content-Type: application/json" \
    -d '{"user_message": "Hello!"}'
  ```
- *Checked on 2026-10-19 without a key* (§8 B6, `b6-a-module4-api.log`): `GET /health` → `{"status":"healthy"}` (`app/main.py:23-25`); `/docs` → `200` (FastAPI's Swagger UI, `README.md:22`); `/chat` → `Internal Server Error` (500); a body with `"message"` instead of `"user_message"` → `422` and `"msg":"Field required"`. With your key `/chat` returns `{"response":"..."}`.
- *Under the hood:*
  - `/chat` calls `AgentRunner.run`, which creates a **new random session and user per request** (`app/runner.py:24-33`) and returns the last `is_final_response()` text (`runner.py:45-46`). A second question remembers nothing of the first (§8 B6).
  - `/chat/stream` yields NDJSON `{"chunk": …}` lines (`app/main.py:35-44`). It is not token-level streaming: only final-response events are yielded (`runner.py:72-73`).
  - When the model call fails, ADK yields a final event with no content, and `runner.py:46` trips over it: the log ends in `AttributeError: 'NoneType' object has no attribute 'parts'`. Read the first error, not the last (§8 C5).
- *Docker variant:* `docker build -t adk-agent .` then `docker run -p 8080:8080 -e GOOGLE_API_KEY=… -e GEMINI_MODEL=gemini-3.1-flash-lite adk-agent`. Pass `GEMINI_MODEL`, or the image falls back to the retired default (`app/agent.py:12`).

**C7. Module 5: Custom agents** (`5-custom-agent/README.md:113-153`; your copy is `custom_agent/`).
- In the UI, `custom_agent` prefixes 🤖 to the final reply (`5-custom-agent/agent.py:36-42`).
- Scripts, from the module folder with the root venv:
  ```bash
  cd custom_agent
  uv run --project .. python simple_custom_agent.py
  uv run --project .. python conditional_agent.py
  ```
  Plain `uv run` in the folder would build a second environment from the module's own `pyproject.toml` (`google-adk[all]`: "Would install 276 packages", §8 B5).
- *With your key, look for:*
  - `simple_custom_agent.py` prints `Agent: 🤖 [Bot]: …` (`simple_custom_agent.py:84-94`).
  - `conditional_agent.py` prints `→ Routed to: SimpleHandler` / `ComplexHandler` / `ClarificationHandler`, once per handler event, then `Response:` for each of the three test queries (`conditional_agent.py:138-147`, queries at 243-247). Its `logging.basicConfig(level=logging.INFO)` (line 24) also prints `INFO:__main__:  Classification: …` lines.
- The router compares the classifier's raw text exactly (`conditional_agent.py:85-102`): `Simple` or `complex` plus a line break goes to clarification. §8 B5 fixes it two ways.

**C8. Module 6: RAG agents (optional; RAG was L05's topic).**
- `6-rag/2-custom-chromadb-rag`: `docker compose up -d`, `uv sync`, `cp .env.example .env`, `uv run python ingest_documents.py`, then `uv run python agent.py` (`6-rag/README.md:122-141`). That module's `.env.example:10` sets `GEMINI_MODEL=gemini-2.0-flash`, and the copied `.env` becomes the nearest one, so fix it (G2). `agent.py` connects to Chroma and calls `get_collection` at import time (lines 42-43), so ingest first.
- Its ChromaDB also publishes port 8000 (`6-rag/2-custom-chromadb-rag/docker-compose.yml:7-8`), so stop llm-rag's first. Checked against the Chroma image the course pulled as `latest` (§8 C8): `/api/v1/heartbeat` → `410 {"error":"Unimplemented","message":"The v1 API is deprecated. Please use /v2 apis"}`, `/api/v2/heartbeat` → `200`; the healthcheck runs `curl`, which the image doesn't have, so the container stays "unhealthy"; and the data goes to `/data`, not the mounted `/chroma/chroma`, so `docker compose down` loses it (G14).
- `uv run adk web` *in that folder* does not find the agent: ADK looks for subfolders, and the module imports `agent_tools` relative to itself (G14).
- `6-rag/1-vertex-rag-engine` creates a managed corpus in your project; §8 C7 covers deleting it.

**C9. Stop.** Ctrl+C the servers, `docker compose down` any ChromaDB you started. Captured (`adk-laptop/39`):
```
$ git status --short; git status --short --ignored | grep '^!!'
 D 1-baseline/.env.example
…
 D 5-custom-agent/simple_custom_agent.py
?? .python-version
?? baseline/
?? custom_agent/
?? mcp_tools/
!! .env
!! .venv/
!! baseline/__pycache__/
!! mcp_tools/__pycache__/
!! uv.lock
```
The renamed folders and your Python pin show up; `.env`, `.venv` and `uv.lock` are ignored. The sessions in `baseline/.adk/` are **not** in the repo's `.gitignore`: once a session exists, `git add --all --dry-run` lists `add 'baseline/.adk/session.db'`, a file that holds every message of every session (§8 B11). Add `.adk/` to `.gitignore`, and delete the 1.6 GB `.venv` when you are done.

### Part D — Tutorial 2: Travel Planner (Colab)

**D1.** Copy the notebook (`tutorials_demo.md:94`). Add the `OPENAI_API_KEY` secret. Run cell 8 (`%pip install -q "openai-agents==0.3.2"`), then cells 9-10.

**D2. Catalog and tools** (cells 12-16).
- *Under the hood:*
  - Mock catalog: 3 cities and 6 hotels, with prices in **cents** (cell 12).
  - Five search functions print `[tool]` and `[catalog]` lines (cell 14).
  - `finalize_plan` computes a proposal and gates it (cell 15).
- *Checkpoint:* cell 16 prints LA attractions `LAX-OBSERVATORY` (0.0) and `LAX-MUSEUM` (25.0). (Expected from the code; this cell has no saved output.)

**D3. Business logic and instructions** (cells 18-21).
- `check_itinerary` does all arithmetic. `run_turn` applies the human's confirmation first, adds a corrective retry, and decides what the user sees from state (cell 18, lines 91-138).
- `build_agent()` uses model `gpt-5.6-luna`, six tools, `SQLiteSession("travel-planner")` and `output_type=PlannerReply` (cell 21).
- The model-visible tool is `finalize_itinerary`, a `@function_tool` wrapper (cell 21, lines 3-10) around `finalize_plan` (cell 15). The `[tool]` log line is printed inside `finalize_plan`, so the output says `[tool] finalize_plan: …` even though the model called `finalize_itinerary`.

**D4. Run the scripted four-turn example** (cells 24-27). Each cell asserts the reply kind. Recorded (`expected/colab-travel-planner-c24`…`c27`, trimmed):
```
Kind: clarification
Which supported California city would you like: San Francisco or Los Angeles? Please also provide your separate food allowance per person per calendar day and local-transport allowance for the whole trip.
```
```
  [tool] flight_search: Seattle -> San Francisco, 2026-11-06
  [catalog] flight_search:
…
  [tool] flight_search: San Francisco -> Seattle, 2026-11-10
…
  [tool] hotel_search: San Francisco, 4 nights, pet-friendly=True
…
  [tool] attraction_search: San Francisco
…
  [tool] restaurant_search: San Francisco, all cuisines
…
Kind: options
San Francisco options found for Nov 6–10, 2026. Outbound: SEA-SFO-20261106-1 or SEA-SFO-20261106-2. …
```
```
  [tool] finalize_plan: validating selections and calculating costs
Kind: clarification
Please review this exact proposed plan and reply with 'yes' to approve it, or tell me what to change. …
{
  "outbound_id": "SEA-SFO-20261106-1",
  "return_id": "SFO-SEA-20261110-1",
  "hotel_id": "SFO-BAY",
  "travelers": 2,
  "budget_usd": 6000,
  …
}
```
```
  [tool] finalize_plan: validating selections and calculating costs
Kind: itinerary
Your checked round trip from Seattle to San Francisco is ready for 2 traveler(s), with Bay Area Suite and Golden Gate Bridge, Bay Art Museum. Budget report is shown below. Nothing has been booked.
Budget report (computed by Python; fictional planning only):
{
  "status": "within_budget",
…
  "costs_usd": {
    "round_trip_flights": 880.0,
    "hotel": 1000.0,
    "food_allowance": 600.0,
    "local_transport_allowance": 150.0,
    "attractions": 60.0
  },
  "total_usd": 2690.0,
  "budget_usd": 6000,
  "remaining_usd": 3310.0,
  …
}
```
In turn 3 the model calls the finalize tool and gets only a pending proposal (the reply shows the exact plan and asks for a yes); in turn 4 the human's "yes" approves that exact proposal and Python builds the budget. *Verify the 2690 yourself:*

| Item | Calculation | Amount |
|---|---|---|
| Flights | 2 people × (220 + 220) | $880 |
| Hotel | 4 nights × 250 | $1000 |
| Food | 60 × 2 people × 5 calendar days | $600 |
| Transport | whole-trip allowance | $150 |
| Attractions | Bay Art Museum 30 × 2 people + Golden Gate Bridge 0 | $60 |
| **Total** | | **$2690** |

- *If it fails:* an `AssertionError` on `reply.kind` means the model took a different but plausible path, for example asking one more question. Rerun the turn or continue interactively.

**D5. Interactive chat** (cells 28-29). Recorded (cell 29): `Travel Planner (interactive). Enter one or more lines, then use a blank line or /send to submit. Commands: 'exit' or 'quit' to leave.` `chat_loop()` calls `build_agent()` again, so it starts with a fresh session and `TravelContext`, not the scripted conversation. `SQLiteSession` defaults to an in-memory database (`openai-agents 0.3.2 agents/memory/sqlite_session.py:21-24`), so history lasts only for this runtime.

### Part E — Tutorial 3: Cheese Newsletter Harness (Colab)

**E1. Install.** Copy the notebook (`tutorials_demo.md:98`), add the secret, run cell 8 (`agent-framework-core==1.18.0`, `agent-framework-openai==1.14.3`, `opentelemetry-api==1.42.1`), then cells 9-10.

**E2. Edit `USERS`** (cell 16, lines 7-12). Replace the course staff's names and addresses with yours and a friend's. Email is **preview-only**: `send_email` writes HTML, and `Settings` only validates the address format.
- Keep at least two readers, because cell 31 displays `receipts[1]`.
- `"Summerville"` was researched as **Summerville, South Carolina** in the saved output. If you mean Somerville, MA, spell it that way.

**E3. Run cells 16-25,** which define contracts, validation, rendering, the researcher (with web search) and editor sub-agents as `@tool`s, and the orchestrator (three tools: `researcher_agent`, `editor_agent`, `send_email`; `max_iterations: 16`, `allow_multiple_tool_calls: False`).

**E4. Generate** (cell 27, `# @title Run Demo`). Recorded (`expected/colab-cheese-newsletter-c27-run-demo.txt`; readers' names replaced by `<reader1>`…):
```
[agent] Building orchestrator...
Generating newsletter for Summerville · 2026-09
  [tool] researcher_agent
  [tool] editor_agent
  [tool] editor_agent
  [tool] editor_agent
  [tool] editor_agent
  [tool] send_email: validating and saving HTML (mock)
Saved HTML: /content/newsletter_output/<reader1>-2026-09-25fd23e3.html (8005 bytes). No email sent.
Generating newsletter for Charlotte · 2026-09
  [tool] researcher_agent
  [tool] editor_agent
  [tool] send_email: validating and saving HTML (mock)
Saved HTML: /content/newsletter_output/<reader2>-2026-09-25fd23e3.html (5696 bytes). No email sent.
…
Created 4 mock emails. No email was sent.
```
- The editor may run several times: Summerville took four `editor_agent` calls, because validation errors are fed back as tool results.
- The saved output covers **four** readers (Summerville, Charlotte, Atlanta, Cambridge). The current cell 16 comments two of them out (lines 10-11), so a fresh run makes two newsletters and ends with `Created 2 mock emails. No email was sent.`
- *If it fails:*
  - `RuntimeError: No successful tool receipt…` means the orchestrator ended without a valid `send_email` (cell 18, lines 119-120). Read the reply text it includes.
  - A `ValueError` about the month or email comes from `Settings.__post_init__` (cell 16).

**E5. View** (cells 30-31). Each cell renders a saved HTML preview and shows file links. Recorded (cell 30): the preview is headed `LOCAL EMAIL PREVIEW · NOT SENT`, and the Summerville letter's offers include `Promotion URL: https://shop.lowesfoods.com/promotions/…`, `Store URL: …` and `Product URL: …` lines, although the editor was told "no embedded URLs" (E15).

---

## 5. Code tour

**llm-rag/** (only the files that matter for L06)
```
llm-rag/
├── README.md              # L05+L06 tutorial; Agents = lines 242-271
├── cli.py                 # all steps; agent() at 421-478; flags at 511-547
├── agent_tools.py         # 2 FunctionDeclarations, 2 Python tools, the dispatcher
├── out.txt                # a recorded `--agent` run (2026-09-22, made against the OLD book)
├── docker-shell.sh        # sets GCP_PROJECT + credentials path, `docker compose run --rm llm-rag-cli`
├── docker-compose.yml     # llm-rag-cli + chromadb services, bind mounts, CORS for hosted UIs
├── Dockerfile             # python:3.12-slim-bookworm, uv sync --frozen into /.venv, user app
├── docker-entrypoint.sh   # prints info, activates /.venv, exec bash
├── pyproject.toml/uv.lock # google-genai 1.39.1, chromadb 1.1.0, langchain 0.3.27 ...
├── input-datasets/books/  # 11 .txt books; "Tolminc Cheese.txt" is "Pavlos's book"
└── images/llm-rag-flow-3.png  # the 6-step agent flow diagram
```

**llm-agent-google-adk/** (after §4 C2 your copies of `1-baseline/`, `3-mcp-tools/`, `5-custom-agent/` are `baseline/`, `mcp_tools/`, `custom_agent/`)
```
llm-agent-google-adk/
├── README.md, QUICKSTART.md      # overview; QUICKSTART is stale (G9)
├── pyproject.toml, .env.example  # root env used by `uv run adk web`
├── 1-baseline/agent.py           # SequentialAgent travel planner (root_agent)
├── 2-litellm/agent.py, litellm_config.py   # multi-provider (broken as written, G11)
├── 3-mcp-tools/agent.py          # MCPToolset over stdio (npx filesystem server)
├── 4-production-ready/app/{agent,runner,main}.py, Dockerfile  # FastAPI wrapper
├── 5-custom-agent/{agent,simple_custom_agent,conditional_agent}.py  # BaseAgent subclasses
└── 6-rag/{1-vertex-rag-engine, 2-custom-chromadb-rag}/   # RAG agents (managed vs ChromaDB)
```

**Excerpt 1. A tool's contract, written by hand**

`llm-rag/agent_tools.py:9-19`
```python
get_book_by_author_func = types.FunctionDeclaration(
    name="get_book_by_author",
    description="Get the book chunks filtered by author name",
    # Function parameters are specified in OpenAPI JSON schema format
    parameters={
        "type": "object",
        "properties": {
            "author": {
                "type": "string",
                "description": "The author name",
                "enum": [
```
- `name` is what the model will write in its `function_call`. It must match the `if function_call.name == …` branches in the dispatcher (`agent_tools.py:88, 111`).
- `description` (here and on each property) is the **only** documentation the model sees. Both functions' `search_content` descriptions even coach the model: "Expand the search term to a a sentence or two to get better matches" (typo in the source; `agent_tools.py:33, 61`).
- `enum` (lines 19-29) restricts `author` to 9 strings. Constrained decoding means the model cannot invent an author spelling that fails the metadata filter. It also means it cannot target the two books whose authors are missing from the list: 178 and 1,505 chunks in the captured collection (E4 in §9).
- `required` (line 36) forces both arguments to be present.

**Excerpt 2. The real function behind the contract**

`llm-rag/agent_tools.py:41-49`
```python
def get_book_by_author(author, search_content, collection, embed_func):

    query_embedding = embed_func(search_content)

    # Query based on embedding value
    results = collection.query(
        query_embeddings=[query_embedding], n_results=10, where={"author": author}
    )
    return "\n".join(results["documents"][0])
```
- `collection` and `embed_func` are **not** in the schema. Your code injects them, so the model only controls `author` and `search_content`.
- `where={"author": author}` is a metadata filter on the `author` key, which `load_text_embeddings` added per book (`cli.py:132-138`).
- `n_results=10` returns 10 of the **24** char-split chunks of the current Tolminc book.
- The return value is a single string. The model never sees chunk IDs or distances.

**Excerpt 3. Call 1: force the model to pick a tool**

`llm-rag/cli.py:439-453`
```python
    # Step 1: Prompt LLM to find the tool(s) to execute to find the relevant chunks in vector db
    print("\n\n\n\nuser_prompt_content: ", user_prompt_content)
    response = llm_client.models.generate_content(
        model=GENERATIVE_MODEL,
        contents=user_prompt_content,
        config=types.GenerateContentConfig(
            temperature=0,
            tools=[agent_tools.cheese_expert_tool],
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    mode="any"
                )
            )
        )
    )
```
- `temperature=0` makes tool selection as repeatable as possible.
- `tools=[cheese_expert_tool]` is one `types.Tool` holding both declarations (`agent_tools.py:79-81`).
- `mode="any"` is case-insensitively mapped to `ANY` (google-genai `_common.py:482-492`). The model **must** answer with one or more function calls.
- No `system_instruction` is passed. `SYSTEM_INSTRUCTION` at `cli.py:40-58` is defined but used nowhere (E3 in §9).
- The captured request body (§4 B3) shows what these settings become on the wire: `"toolConfig": {"functionCallingConfig": {"mode": "ANY"}}` and `"generationConfig": {"temperature": 0.0}`, with no `systemInstruction`.

**Excerpt 4. Call 2: send back the call and its results**

`llm-rag/cli.py:464-477`
```python
        # Call LLM with retrieved responses
        response = llm_client.models.generate_content(
            model=GENERATIVE_MODEL,
            contents=[
                user_prompt_content,  # User prompt
                response.candidates[0].content,  # Function call response
                Content(
                    parts=function_responses
                ),
            ],
            config=types.GenerateContentConfig(
                tools=[agent_tools.cheese_expert_tool]
            )
        )
```
- The history is three turns: the user question, **the model's own turn unchanged**, and your function responses.
- Re-sending `response.candidates[0].content` verbatim preserves the `thought_signature` (out.txt:28); in the captured request it travels as `"thoughtSignature"`. The Gemini API thinking guide (ai.google.dev, "Stateless mode") says you must resend all thought blocks "exactly as they were received from the model".
- `tools=` is passed again but without `tool_config`, so the mode is AUTO (captured: no `toolConfig`, `"generationConfig": {}`). The model *may* call another tool, and this code has no loop to handle it (§3.3, §8 C2).
- Line 478 prints the whole response object. To see only the answer, print `response.text`.

**Excerpt 5. Packaging a tool result**

`llm-rag/agent_tools.py:103-110`
```python
            parts.append(
                types.Part.from_function_response(
                    name=function_call.name,
                    response={
                        "content": response,
                    },
                ),
            )
```
- A function response is a `Part` whose `name` echoes the call. `response` must be a JSON object, so the chunk string is wrapped as `{"content": …}`.
- The call's `id` (`out.txt:25`) is not echoed. Matching is by name, which works because each tool is called at most once here.

**Excerpt 6. The agent loop inside ADK** (third-party library, not in either repo)

`google-adk 1.19.0 · google/adk/flows/llm_flows/base_llm_flow.py:343-352`
```python
    while True:
      last_event = None
      async with Aclosing(self._run_one_step_async(invocation_context)) as agen:
        async for event in agen:
          last_event = event
          yield event
      if not last_event or last_event.is_final_response() or last_event.partial:
        if last_event and last_event.partial:
          logger.warning('The last event is partial, which is not expected.')
        break
```
- One "step" is one LLM call plus any tool executions it triggers.
- Every event is streamed out with `yield`. That is what `adk web` displays, and what your `async for event in runner.run_async(...)` receives.
- The exit test is `is_final_response()`: no function calls, no function responses, not partial (`events/event.py:82-97`). This is exactly the loop llm-rag hand-codes with only two iterations.
- google-adk 1.27.5 has the same ten lines at `base_llm_flow.py:755-764`. ADK 2.11/2.12 keep the same `while True` shape and add `is_aborted` checks (2.11: `base_llm_flow.py:322-343`; 2.12, what `uv sync` installs today: 332-353).

**Excerpt 7. A pipeline that communicates through state**

`llm-agent-google-adk/1-baseline/agent.py:14-26`
```python
validator = LlmAgent(
    name="ItineraryValidator",
    model=GEMINI_MODEL,
    instruction="You validate trip requests. Extract traveler count, origin, destinations, dates, budget, and constraints from the input.",
    output_key="itinerary_validation"
)

processor = LlmAgent(
    name="TravelPlanner",
    model=GEMINI_MODEL,
    instruction="Using {itinerary_validation}, design a realistic multi-day travel plan with routing, daily schedule, estimated costs, and key booking recommendations.",
    output_key="travel_plan"
)
```
- `output_key` stores this agent's final text in `session.state["itinerary_validation"]`.
- `{itinerary_validation}` is replaced with that value *before* the TravelPlanner's call. Without the validator's output in state, you would get `KeyError: Context variable not found`.
- `GEMINI_MODEL` comes from `.env`, with fallback `"gemini-2.0-flash"` (line 12; retired, G2).
- Lines 35-39 wrap the three agents in `SequentialAgent(... sub_agents=[validator, processor, summarizer])` and name it `root_agent`. That variable name is what `adk web` looks for.

**Excerpt 8. Plug in someone else's tools via MCP**

`llm-agent-google-adk/3-mcp-tools/agent.py:20-29`
```python
toolset = MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command='npx',
            args=['-y', '@modelcontextprotocol/server-filesystem', ALLOWED_PATH]
        ),
        timeout=10
    ),
    tool_filter=['read_file', 'list_directory', 'search_files']
)
```
- `StdioServerParameters(command='npx', …)` means ADK launches the server as a child process and speaks JSON-RPC over its stdin/stdout.
- `ALLOWED_PATH` is the only directory the server will touch. It defaults to this module's folder (lines 17-18).
- `tool_filter` exposes 3 of the server's 14 tools (captured, §4 C5). The current server (npm 1.0.0) still registers `read_file`, but marks it deprecated in favour of `read_text_file`. If a future release drops it, the filter silently leaves the agent without a read tool.

**Excerpt 9. A custom agent that routes with plain Python**

`llm-agent-google-adk/5-custom-agent/conditional_agent.py:84-97`
```python
        # Get classification result
        complexity = ctx.session.state.get("query_complexity", "simple")
        logger.info(f"  Classification: {complexity}")

        # Step 2: Route based on complexity
        if complexity == "simple":
            logger.info("  Step 2: Routing to simple handler...")
            async for event in self.simple_handler.run_async(ctx):
                yield event

        elif complexity == "complex":
            logger.info("  Step 2: Routing to complex handler...")
            async for event in self.complex_handler.run_async(ctx):
                yield event
```
- The classifier (lines 158-172) writes its text to `state["query_complexity"]` via `output_key`. The runner applies the state change as soon as the classifier's final event is yielded, so it is visible on the next line.
- The comparison is **exact**. ADK stores the raw joined text (google-adk 1.19.0 `agents/llm_agent.py:802-816`), so `"Simple"` or `"simple\n"` would fall through to the `else` (clarification) branch. §8 B5 covers this.
- `async for … yield event` re-emits every sub-agent event, so the runner and UI still see everything.

**Excerpt 10. The approval gate (harness)**

`L06_travel_planner.ipynb` · cell 15 (`# @title Finalize Plan Tool`), lines 33-42 of the cell
```python
    # A model tool call can propose a plan, but only a later human turn can
    # approve that exact proposal. This prevents the model from silently
    # inventing requirements or treating its own suggestion as confirmation.
    if proposal != travel_context.approved_proposal:
        travel_context.pending_proposal = proposal
        return {
            "status": "needs_confirmation",
            "requirements": proposal,
            "message": "Stop and wait for the user's next chat reply.",
        }
```
- `approved_proposal` is set only by `apply_confirmation(prompt, context)`. That runs **before** the agent, on the human's raw text, and accepts only `y`/`yes`/`confirm`/… (cell 18). This is why the model cannot approve its own proposal by calling `finalize_itinerary` a second time in the same turn: in turn 3 `approved_proposal` is still `None`, so every call returns `needs_confirmation`.
- Any difference in IDs, traveller count or allowances creates a new pending proposal. Attraction IDs are sorted, so order does not matter (cell 15, line 30).
- The tool *returns* a `needs_confirmation` status instead of raising. The model sees it as a normal tool result, and the instructions tell it to stop (cell 20).

**Excerpt 11. Success is a receipt, not a sentence**

`L06_cheese_newsletter_harness.ipynb` · cell 18 (`# @title Business Logic`), lines 118-125 of the cell
```python
    reply = await invoke_agent(agent, json.dumps(request), context)
    if context.receipt is None:
        raise RuntimeError(f"No successful tool receipt. Orchestrator response: {reply}")

    receipt = context.receipt
    if not Path(receipt["path"]).is_file():
        raise RuntimeError("The mock email receipt points to a file that does not exist.")
    print(f"Saved HTML: {receipt['path']} ({receipt['bytes']} bytes). No email sent.")
```
- `invoke_agent` passes the application context to every tool through `function_invocation_kwargs` (cell 20, lines 19-25). Tools read it with `ctx.kwargs` and never receive it as a model-visible argument.
- `context.receipt` is set only inside `save_newsletter` after validation and rendering succeed (cell 16).
- The model's own claims (`reply`) are used only in the error message. The file system is the source of truth.

**Excerpt 12. Agents as tools**

`L06_cheese_quiz.ipynb` · cell 68, lines 1-8 of the cell
```python
# Agents-as-tools for orchestration
stilton_tool = stilton_agent.as_tool(
    "research_facts", "Find ~5 concise, citable facts for a topic."
)
brie_tool = brie_agent.as_tool("write_quiz", "Convert facts into a 5-question MCQ quiz.")
cheddar_tool = cheddar_agent.as_tool("review_quiz", "QA the quiz against the facts.")
mozzarella_tool = mozzarella_agent.as_tool("format_quiz", "Format quiz into Markdown.")
ricotta_tool = ricotta_agent.as_tool("format_quiz_json", "Format quiz into JSON.")
```
- `.as_tool(name, description)` turns an entire agent, with its own model, tools and `output_type`, into a single function the orchestrator can call with a text input (`openai-agents` 0.23.1 and 0.24.0 `agents/agent.py:606`; 0.22.3: line 583). Lines 9-11 of the cell (not shown) wrap Cashew as `vegan_specialist`.
- The orchestrator (cell 70) decides the order. The "assembly line" lives only in its instructions, so nothing in code enforces "at most 2 review rounds". Compare ADK's `SequentialAgent`, where the order *is* code.
- `mozzarella_tool` is defined but not given to the orchestrator (cell 70, tools list).

---

## 6. Gotchas and common errors

| # | Symptom | Cause | Fix |
|---|---|---|---|
| G1 | The dev UI lists `1-baseline`, `2-litellm`, `3-mcp-tools`, `5-custom-agent`…, but picking one fails: `Invalid agent name: '1-baseline'. Agent names must be valid Python identifiers or paths separated by dots (letters, digits, underscores, and dots).` (captured, ADK 2.12.0) | No lockfile (`.gitignore:34`). `google-adk>=1.8.0` (`pyproject.toml:10`) resolves to **2.12.0** on 2026-10-18 (2.11.0 on Python 3.10). Since **1.28.0** (2026-03-26) the agent loader validates folder names against `^[a-zA-Z0-9_]+$` (`cli/utils/agent_loader.py`: line 191 in 1.28.0, 255 in 2.12.0). **Pinning an older ADK does not help:** with `uv add "google-adk>=1.8.0,<1.28"` (→ 1.27.5) the loader accepts `1-baseline`, but the web server wraps the agent in `App(name=…)`, and that fails with `Invalid app name '1-baseline': must be a valid identifier consisting of letters, digits, and underscores.` (captured). The wheels of 1.19.0 (current at the repo's last commit), 1.21.0, 1.23.0, 1.25.0 and 1.27.5 all have this check (read, not run). | Rename the folders: `mv 1-baseline baseline; mv 3-mcp-tools mcp_tools; mv 5-custom-agent custom_agent`, then `uv run adk web` and pick `baseline` (captured, works with 2.12.0). Symlinks under valid names were tried and do not work (1.27.5: `resolves outside base directory` when a session is created; 2.12: not listed). Undo a pin with `git checkout pyproject.toml; uv sync --upgrade-package google-adk`. |
| G2 | `404 NOT_FOUND … models/gemini-2.0-flash is not found` (or a "no access" error for 2.5), or `400 INVALID_ARGUMENT … API key not valid` although the root `.env` has a good key | Every Gemini agent falls back to `gemini-2.0-flash` when `GEMINI_MODEL` is unset (e.g. `1-baseline/agent.py:12`, `4-production-ready/app/agent.py:12`), and `5-custom-agent/.env.example:5` sets it explicitly. Google's deprecation page lists its shutdown date as **2026-06-01**. The root `.env.example:21` uses `gemini-2.5-flash`, which Google now limits "to users who have actively used them in the past". ADK loads **only the nearest** `.env`, with `override=True`, so a module `.env` made by a module README's `cp .env.example .env` replaces the root one entirely: `GEMINI_MODEL` unset or 2.0-flash, and a placeholder `GOOGLE_API_KEY` (checked, §8 C1). | In the root `.env` set `GEMINI_MODEL=gemini-3.1-flash-lite` (the model llm-rag uses, `cli.py:27`; Google lists its earliest shutdown as 2027-05-07). Don't copy module `.env.example` files; if you did, delete those `.env` files or fix both `GEMINI_MODEL` and `GOOGLE_API_KEY` in them. The log line `Loaded .env file for <agent> at …` tells you which file won. |
| G3 | `adk web` prints its banner, then `ERROR:    [Errno 98] error while attempting to bind on address ('127.0.0.1', 8000): address already in use` and exits 3 (captured, Linux; macOS reports `[Errno 48]` *(reasoned, not run)*) | `adk web` defaults to `127.0.0.1:8000`. llm-rag's ChromaDB publishes `8000:8000` (`docker-compose.yml:21-22`), and so does `6-rag/2-custom-chromadb-rag/docker-compose.yml:7-8`. | `docker compose down` in `llm-rag/`, or `uv run adk web --port 8080` (captured). |
| G4 | Port 8000 is still busy after you `exit`ed the llm-rag shell | `docker compose run --rm llm-rag-cli` (`docker-shell.sh:12`) starts the `chromadb` dependency (`docker-compose.yml:16-17`), but `--rm` removes only the one-off CLI container. Captured: after `exit`, `docker ps` still lists `llm-rag-chromadb` with `0.0.0.0:8000->8000/tcp`. | `docker compose down` (or `docker stop llm-rag-chromadb`). |
| G5 | `KeyError: 'GCP_PROJECT'`, `DefaultCredentialsError: File /secrets/llm-service-account.json was not found.` (captured, at `cli.py:441`), `403 PERMISSION_DENIED` | `cli.py:23` requires `GCP_PROJECT`, which only `docker-shell.sh:7` sets. The key must exist at `../secrets/llm-service-account.json`, and the service account needs the Vertex AI User role. google-genai loads credentials lazily, so a missing key shows up only at the first model call. | Always start via `sh docker-shell.sh`; edit line 7; check `ls ../secrets`; grant the role; enable the Vertex AI API. |
| G6 | `--agent` fails at once: `chromadb.errors.NotFoundError: Collection [char-split-collection] does not exist` (captured, `cli.py:429`) | The agent uses the L05 collection (`cli.py:427-429`), and the Agents section doesn't say so. ChromaDB data lives in `llm-rag/docker-volumes/chromadb`, which is git-ignored (`llm-rag/.gitignore:3`), so a fresh clone has none. | Chunk, embed and load (`python cli.py --load --chunk_type char-split` after the other two). Or run with the chunk type you did load (`--chunk_type recursive-split`). |
| G7 | Your answer is about "Mara" and her grandfather, not the Soča Valley as in `out.txt` and the README diagram | `Tolminc Cheese.txt` was rewritten on 2026-09-22 (`85bba32`), the same commit that added `out.txt`, which was recorded against an index built from the old file (captured word counts, §4 B3). | Expected. Rebuild your index if you loaded before 2026-09-22. Changing source docs means re-running chunk → embed → load. |
| G8 | `sh docker-shell.sh` ends with `/bin/bash: docker-entrypoint.sh: No such file or directory` (exit 127); or `DefaultCredentialsError` although you have a key | Bind mounts are relative and name-dependent: `../llm-rag:/app` and `../secrets:/secrets` (`docker-compose.yml:11-12`). A clone in a folder not named `llm-rag` makes Docker create an empty, root-owned `../llm-rag` and mount that over `/app`; a `secrets/` folder inside the repo is not where `../secrets` points. | Layout must be `llm-rag/` and `secrets/` side by side (`README.md:64-69`). Remove the stray empty `llm-rag` folder Docker created. |
| G9 | `QUICKSTART.md` commands fail: `Error: Invalid value for '[AGENTS_DIR]': Directory '1-baseline/agent.py' is a file.` (captured); `No such file` for `sequential_example.py`, `story_flow_agent.py` …; `3-mcp-connections` not found | `adk web` takes a directory (`file_okay=False`). The scripts named at `QUICKSTART.md:70-72, 79, 85, 91-92` never existed in this repo's git history (only `conditional_agent.py`, line 93, exists). The module has been called `3-mcp-tools` since the initial commit `f24b771`. | Use `uv run adk web` from the repo root and pick the folder in the UI. Use the README module instructions, not QUICKSTART. |
| G10 | `uv run adk` prints the usage and command list (`api_server`, `create`, `deploy`, `eval`, `run`, `telemetry`, `web`, …) and nothing starts (exit 2, captured) | `2-litellm/README.md:74`, `3-mcp-tools/README.md:85` and `5-custom-agent/README.md:120` omit the `web` subcommand. | `uv run adk web`. |
| G11 | `2-litellm` fails on the first message: an OpenAI credentials error on ADK 2.12, `Model gpt-4 not found.` on 1.x | Besides its folder name (G1), `model="gpt-4"` (`2-litellm/agent.py:26`) is a bare name. On google-adk 2.12.0 it resolves to ADK's own `OpenAILlm` class, **not** LiteLLM (checked, §8 B7); 1.19.0 registers only Gemini/Gemma/Apigee names, and 1.27.5 registers `LiteLlm` only for provider-prefixed names such as `openai/…`. `AWS_OPENAI_API_KEY` is read nowhere; `litellm_config.py:28` reads `OPENAI_API_KEY`. | §8 B7: copy the folder to `litellm_agent` (not `litellm`, which clashes with the package), `LiteLlm(model="openai/gpt-5.6-luna")`, `OPENAI_API_KEY` in the root `.env`. |
| G12 | `3-mcp-tools`: `npx: command not found`, or "connection timeout" | Needs Node.js. The first `npx -y` download can exceed `timeout=10` (`3-mcp-tools/agent.py:26`). | Install Node (`brew install node`), run `npx -y @modelcontextprotocol/server-filesystem .` once to warm the cache (it then waits on stdin; stop it with Ctrl+C), retry. |
| G13 | `uv sync` in the ADK repo downloads gigabytes / takes many minutes | The root `pyproject.toml:18-19` includes `chromadb` and `sentence-transformers`, which pull PyTorch (`torch==2.14.1` on 2026-10-18). The captured `.venv` is 1.6 GB with the CPU-only wheel; on a Linux PC uv also installs `triton` and 15 `nvidia-*` CUDA packages, about 3 GB more (captured `uv sync --dry-run`). The README's per-module `uv sync` creates *additional* venvs; module `pyproject.toml`s ask for `google-adk[all]` ("Would install 276 packages", §8 B5). | Sync once at the root and run module scripts with `uv run --project .. …`. Be patient the first time; delete `.venv` when you are done. |
| G14 | `6-rag/2-custom-chromadb-rag`: the container stays `unhealthy`; the README's `curl http://localhost:8000/api/v1/heartbeat` returns `{"error":"Unimplemented","message":"The v1 API is deprecated. Please use /v2 apis"}`; documents gone after `down`/`up`; no agent appears in `adk web` | The healthcheck and README use the v1 API (`6-rag/2-custom-chromadb-rag/docker-compose.yml:16`, `6-rag/2-custom-chromadb-rag/README.md:33`). Today's `chromadb/chroma:latest` answers v1 with HTTP 410, and its image has no `curl`, so the healthcheck fails either way. The server keeps its data in `/data`, so the volume at `/chroma/chroma` and `IS_PERSISTENT`/`PERSIST_DIRECTORY` (`docker-compose.yml:9-14`, from older images) persist nothing (checked, §8 C8). `adk web` run inside that folder lists *subfolders*, and `6-rag/2-custom-chromadb-rag/agent.py:29` imports `agent_tools` as a top-level module. | Check with `curl http://localhost:8000/api/v2/heartbeat`. Ignore the health status (or drop the healthcheck). Mount the volume at `/data`. Run the agent with `uv run python agent.py`, the README's "recommended" path. |
| G15 | Colab: `SecretNotFoundError` / `NotebookAccessError`; or `FileNotFoundError: quiz-ui.html` in cell 62 | The secret must be named exactly `OPENAI_API_KEY` with notebook access on. Cell 13's `gdown` from Google Drive can fail (quota or permission) and then `open("quiz-ui.html")` fails. | Fix the secret. Rerun cell 13 and check the two `To: /content/...` lines. |
| G16 | Colab Cheese Quiz: import errors or API changes | Cell 10 installs `fastmcp` and `openai-agents` **unpinned**, with all output hidden. On 2026-10-18 that means fastmcp 4.1.1 and openai-agents 0.24.0. The names cell 11 imports from `agents` still exist in 0.23.1 and 0.24.0 (static check of the wheels). The notebook was last run on 2026-09-23, with FastMCP 4.0.5 (cell 57's banner) and, by date, openai-agents ≤ 0.22.3. | If something breaks, pin what worked then: `pip install "fastmcp==4.0.5" "openai-agents==0.22.3"`, and remove the `> /dev/null 2>&1` to see errors. |
| G17 | Copying `await …` cells into a `.py` file gives `SyntaxError: 'await' outside function` | Colab/Jupyter allow top-level `await`; Python scripts do not. | Wrap the code in `async def main(): …` and call `asyncio.run(main())`, as `5-custom-agent/simple_custom_agent.py:97-99` does. |
| G18 | A key ends up on GitHub | `secrets/` lives *outside* `llm-rag/` and is not covered by llm-rag's `.gitignore`. ADK `.env` files are ignored only by the ADK repo's own `.gitignore:24, 48`. If the folder that holds your clones is itself a git repo, its own `.gitignore` decides. | `MLOps_Learning`'s top-level `.gitignore` already ignores `tutorials/`, `secrets/`, `**/secrets/`, `.env`, `.env.*`, `*service-account*.json` and `*-key.json`; any other parent repo needs the same lines before the first `git add`. Never paste keys into notebooks; use Colab Secrets. |
| G19 | `cd 2-litellm && uv run python litellm_config.py` ("Test LiteLLM Configuration", `2-litellm/README.md:81-88`) prints nothing, even with keys set | `litellm_config.py` only defines `configure_litellm()` and `get_available_models()`; there is no `if __name__ == "__main__":` block. (Run from `2-litellm/`, plain `uv run` also builds that module's own venv.) | `uv run --project .. python -c "from litellm_config import configure_litellm; configure_litellm()"` *(reasoned, not run)*. |
| G20 | The README's `uv sync` fails: `Using CPython 3.15.0` … `error: Distribution onnxruntime==1.31.0 … can't be installed because it doesn't have a source distribution or wheel for the current platform` / `hint: You're using CPython 3.15 (cp315), but onnxruntime (v1.31.0) only has wheels with the following Python ABI tags: cp311, cp312, cp313, cp313t, cp314, cp314t` (captured, exit 2) | `requires-python = ">=3.10"` has no upper bound. With no Python on the machine, uv 0.13.1 downloads the newest CPython (3.15.0); and uv prefers the Pythons it manages, so a laptop with a system Python 3.12 picks 3.15 too once uv has installed it (checked, §8 C3). `onnxruntime` (through `chromadb`) has no cp315 wheel yet. | `uv python pin 3.13` (any of 3.11-3.14; it writes `.python-version`), then `uv sync`. `uv python list --only-installed` shows what uv can choose from. |
| G21 | `uv run adk web` stops at `Enable telemetry? [Y/n]:` and seems to hang; or telemetry is on although the text says it is "OFF by default" | ADK 2.12 asks once, in a terminal, before the server starts; the capital `Y` makes Enter mean yes. The README does not mention it (captured). | Type `n` (or `y`). Change it later with `uv run adk telemetry disable` / `enable` / `status`; the answer is stored in `~/.adk/config.json`. |
| G22 | `git status` shows nothing new, but `git add --all` picks up `baseline/.adk/session.db` | `adk web` 2.12 stores each agent's sessions in `<agent>/.adk/session.db` (captured log); the repo's `.gitignore` covers `.env`, `.venv` and `uv.lock`, not `.adk/`. The file holds every message and reply of every session. | `echo ".adk/" >> .gitignore`; check with `git check-ignore -v baseline/.adk/session.db`. If you already committed one: `git rm --cached baseline/.adk/session.db` (§8 B11). |
| G23 | After changing `cli.py:478` to `print(response.text)`, the program prints `None` | Call 2 is in AUTO mode, so the model may answer with another function call instead of text; `response.text` joins only text parts, and google-genai warns "there are non-text parts in the response: ['function_call'] …" (checked with a stand-in reply, §8 C2). Nothing runs that second call. | Look at `response.candidates[0].content.parts`; run new calls in a loop with a cap (§8 B3), or keep the original print. |

---

## 7. Where this sits in the course

**What L05 (Introduction to RAG) gave you:**
- The `llm-rag` container: Python 3.12 + uv, Vertex AI through a service-account key, ChromaDB as a second container with a persistent bind mount.
- The pipeline `--chunk` → `--embed` (gemini-embedding-001, 256-d) → `--load` (cosine collections with `book`/`author`/`year` metadata) → `--query` → `--chat` (`README.md:91-215`).

**What L06 adds:**
- **Agency.** The LLM picks the retrieval strategy (function calling) instead of you hard-coding "top-10 by similarity". It reuses the same collection, and the author metadata from `cli.py:132-138` suddenly matters, because it is what `where={"author": …}` filters on. L05's file-name slip (`cli.py:178`) now costs a whole book (E4).
- **Frameworks that own the loop:**
  - Google ADK: Runner/Session/State/Events, workflow agents, MCP, custom agents, a FastAPI wrapper.
  - OpenAI Agents SDK: `Runner.run`, `function_tool`, `as_tool`, sessions, structured outputs.
  - Microsoft Agent Framework: `@tool`, `function_invocation_kwargs`, `max_iterations`.
- **Harness ideas:** approval gates, Python-owned arithmetic, validated outputs, receipts.
- **uv again (L01).** The ADK repo is a uv project without a lockfile; `uv python pin` (L01's fix for a moving Python) is what makes its `uv sync` work today.

**How the llm-rag agent evolved** (`git log -- agent_tools.py cli.py`):

| Date | Commit | Change |
|---|---|---|
| 2024-09-25 | `64aa948` | Agent tools added |
| 2025-10-01 | `59a0f80` | "Migrated to uv and genai" (its parent is the `pipenv` branch tip `0b671ed`): `vertexai.generative_models.FunctionDeclaration` → `google.genai.types.FunctionDeclaration`; `gemini-1.5-flash-002` → `gemini-2.0-flash-001`; a `genai.Client(vertexai=True, …)`. The `GenerativeModel(..., system_instruction=[SYSTEM_INSTRUCTION])` wrapper was commented out (E3). `agent()` itself still used the old `ToolConfig.FunctionCallingConfig.Mode.ANY` call at that commit. |
| 2025-10-07 | `629fdd9` | "added missing imports": `agent()` ported to `llm_client.models.generate_content(..., types.FunctionCallingConfig(mode="any"))`, today's shape |
| 2026-09-16 | `51a2865` | "Model fix": `gemini-2.0-flash-001` → `gemini-3.1-flash-lite` |
| 2026-09-17 | `74dba4a` | Embedding model `text-embedding-004` → `gemini-embedding-001` |
| 2026-09-22 | `85bba32` / `2079962` | New instructor's book + `out.txt` (these touch `input-datasets/`, `out.txt` and `README.md`, so they are not in the `git log -- agent_tools.py cli.py` above) |

`git diff --stat origin/pipenv origin/main` touches 14 files (+3703/−3781), mostly the Pipfile → uv swap.

**What comes next:**
- **L07 (Agents II):** the `dlops-io/agent-harness` repo plus an "Agent Harness on Google Colab" notebook (`tutorials_demo.md:102-108`), repo last commit 2026-09-28. Docker, Python 3.13, OpenAI. Six "acts" turn this lecture's harness ideas into the main topic: recap of agent + tools, context engineering, a controlled workflow, planning/memory/compaction/review, skills, agent systems, and evaluation with traces (agent-harness `README.md`, table at the top). Lecture 7's slides also sketch the handoffs that this lecture's slide 51 lists.
- **L18 (APIs + Frontend):** `cheese-app-v2` ships a byte-identical copy of this lecture's `agent_tools.py` at `src/vector-db/agent_tools.py`, plus `src/api-service/api/routers/llm_agent_chat.py`. The agent you ran from a CLI becomes an API endpoint behind the React app (§8 D6).

---

## 8. Exercises

The exercises, with answers, are in [`exercises.md`](https://github.com/JunyiZhou-Conny/Explainer_Videos/blob/main/videos/ac215-l06-agents-1/exercises.md) in the video folder. Their outputs come from the 2026-10-18 captures or were checked on 2026-10-19 in throwaway containers with the tutorials' own versions ([`assets/exercise-checks/`](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l06-agents-1/assets/exercise-checks)); where a check needed a model's reply, a hand-written stand-in drove the tutorial's unchanged code down one path, and items marked *with your key* need one. Do them after watching, without re-watching first, then re-watch only the chapter you got wrong. A summary follows; open each answer only after you have committed to your own.

### Test yourself: the five questions from the end of the video

**Q1. In function calling, who runs the function, and what travels back to the model in call 2?**
<details><summary>Answer</summary>

**Your code runs it**, never the model. Call 1's answer is only an order: a `function_call` part with `name='get_book_by_author'`, the arguments and an `id` (`out.txt:20-27`), plus a `thought_signature` (`out.txt:28`); `automatic_function_calling_history=[]` (`out.txt:51`). `cli.py:457-460` hands the calls to `agent_tools.execute_function_calls`, which matches the name, calls the real function with the model's two arguments plus two it never sees (`collection`, `embed_func`), and wraps the 10 chunks as `Part.from_function_response(name=…, response={"content": …})`. Call 2 then sends the question (role `user`), **the model's own turn, unchanged**, with its `thoughtSignature` (role `model`), and your `functionResponse` (no role, no `id`; matched by name), plus the tools but no `toolConfig` (§4 B3). Per question: two Gemini calls and one embedding call, all paid.
</details>

**Q2. What does `mode="any"` change, and why only on call 1?**
<details><summary>Answer</summary>

It becomes `"toolConfig": {"functionCallingConfig": {"mode": "ANY"}}`: "Model is constrained to always predicting function calls only" (google-genai 1.39.1 `types.py:500-501`). Retrieval is guaranteed; the model chooses only *which* search and its arguments, never *whether* (the decision the lecture's Self-RAG starts with, slides 10-11). Only call 1, because call 2 must answer in **text**, and under ANY every reply would be a function call. Call 2 has no tool config, so it is AUTO: the model may answer, or ask for another tool, which `cli.py` would print and never run (§8 C2). `temperature=0` is likewise set only on call 1 (`cli.py:445`).
</details>

**Q3. What ends an agent loop, what cap do frameworks add, and which lecture block is that?**
<details><summary>Answer</summary>

The stop rule: a reply with no function call is the final response (ADK: `Event.is_final_response()`, google-adk 2.12.0 `events/event.py:286-308`; an event with an error code counts as final too). The caps (§3.3): the Agents SDK's `max_turns` (default 10, 12 in the notebooks, raises `MaxTurnsExceeded`), Microsoft Agent Framework's `max_iterations` (default 40, 16 for the Newsletter; no error, one last response with tools disabled), ADK's `RunConfig.max_llm_calls` (500, not set here). The block is **dynamic control**, the steering wheel (slides 25-27); slide 41 grays it out because the framework writes the loop. llm-rag has no loop: one lap.
</details>

**Q4. How does `TripSummarizer` get the travel plan without a message from `TravelPlanner`?**
<details><summary>Answer</summary>

Through the **session**. `TravelPlanner` has `output_key="travel_plan"` (`1-baseline/agent.py:25`), so its final text goes into the session state; `TripSummarizer`'s instruction contains `{travel_plan}` (line 31), which ADK fills from the state just before the call. The `SequentialAgent` (lines 35-39) only runs the three in order. Checked with ADK's Runner and stand-in models: the summarizer's instruction arrived with the planner's reply pasted in, and the state ended with `itinerary_validation`, `travel_plan`, `trip_summary`. ADK 2.12 also passes the earlier replies as quoted history ("[TravelPlanner] said: …"), so the plan arrives twice. A new session starts empty (`state {}`).
</details>

**Q5. In the last two notebooks, what decides that a run succeeded, and why not the model's final text?**
<details><summary>Answer</summary>

**Python state that only the checked path can set.** Travel Planner: `finalize_plan` stores the plan as *pending* until a later human turn approves that exact proposal (`apply_confirmation`, cell 18 lines 55-65, run on the human's message before the agent, line 106); what the user sees comes from that state (lines 122-131), an unchecked "itinerary" raises (hard guardrail) and money in prose only warns (soft). Newsletter: success needs `context.receipt`, set only by `save_newsletter` after validation and rendering, **and** the file on disk (cell 18, lines 118-125). Checked with stand-ins: an orchestrator that just says "Newsletter sent successfully!" gets `RuntimeError: No successful tool receipt. Orchestrator response: Newsletter sent successfully!`. The model's words are a claim: it may never have called the tool, or ignored an error result.
</details>

### Hands-on (predict, then run)

**B1 · Steer the tool choice** *(llm-rag, with your key)*. Change the question on `cli.py:435` to "What does George E. Newell say about rennet?", then "Which books mention goat cheese?"; predict the function, its arguments and which books the 10 chunks can come from.
<details><summary>Answer</summary>

Newell: `get_book_by_author` with `author='George E. Newell'` (an enum value, `agent_tools.py:22`); the filter keeps that author's 395 chunks, all from *Hand-book on cheese making*. Goat cheese: no author, so `get_book_by_search_content` over all 8,248 chunks. The dispatcher was checked with both calls written by hand (10 of 10 from Newell's book; 6 and 4 from two books across all). Which function the model picks needs your key. `/app` is your folder, mounted, so edits are live; undo with `git checkout cli.py`.
</details>

**B2 · Let the model skip retrieval.** Delete the `tool_config=…` block (`cli.py:447-451`), ask "Hi! Who are you?", and predict what is sent and printed.
<details><summary>Answer</summary>

The request has no `toolConfig` (still `"temperature": 0.0`); the mode is AUTO. If the model answers in text, `cli.py` prints the whole object (line 454), then `Function calls: []` and `Function calls did not result in any responses...` (line 462), and there is **no call 2** (checked with a stand-in reply). ANY guarantees retrieval and takes away the decision; AUTO gives it back (Q2, D2).
</details>

**B3 · Turn the two calls into a capped loop** *(stretch)*. Replace `cli.py:439-478` with a loop of at most 5 steps (code in `exercises.md`). Predict how many contents each call sends if the model searches twice and then answers, and what happens if it never stops.
<details><summary>Answer</summary>

1, then 3, then 5 contents (`user`; `user, model, user`; `user, model, user, model, user`): each lap adds the model's turn and your function responses. A reply with no function call prints `Answer:` and stops; a model that never stops ends after 5 calls with `Gave up after 5 steps`. Checked with scripted stand-in replies on the real collection. Compare ADK's `while True` with `max_llm_calls`.
</details>

**B4 · Watch the whiteboard** *(ADK, with your key)*. In the dev UI pick `baseline`, send "2 adults, Boston to Montreal, Oct 30 - Nov 2, 1500 dollars, train preferred", open the State and Events tabs; then start a new session, then restart `adk web`.
<details><summary>Answer</summary>

Three state keys from the three `output_key`s; the planner's instruction reaches the model with `{itinerary_validation}` filled in. A new session starts with `state {}` and no events. Restarting `adk web` does **not** remove sessions: they are in `baseline/.adk/session.db`, and `GET /apps/baseline/users/student/sessions` still lists them. Each request is three Gemini calls.
</details>

**B5 · Fix the router two ways.** In `custom_agent/conditional_agent.py`, make (a) line 85 end in `.strip().lower()`, and (b) give the classifier `output_schema=` with a `Literal["simple", "complex", "ambiguous"]` field. Predict the routes for `Simple` and for `complex` plus a line break.
<details><summary>Answer</summary>

As committed both go to **ClarificationHandler**: `output_key` stores the raw text, and `complexity == "simple"` is exact (`conditional_agent.py:85-102`). (a) routes them to Simple/Complex; (b) rules them out (the schema goes to the model as the response schema, and a reply that breaks it raises `ValidationError` instead of silently picking clarification). Checked with stand-in classifier replies. Run with `uv run --project .. python conditional_agent.py`: plain `uv run` in the folder "Would install 276 packages" into a second environment.
</details>

**B6 · Your agent as a web API** *(module 4)*. Start `uv run --project .. uvicorn app.main:app --port 8080` from `4-production-ready/`; predict `/health`, `/docs`, the README's `/chat` request, the same with `"message"` as the field name; with your key, send "My name is Sam." then "What is my name?".
<details><summary>Answer</summary>

`{"status":"healthy"}`; `200`; without a key `Internal Server Error` (500, C5); `422` with `"msg":"Field required"`. The second question gets no memory of the first: `AgentRunner.run` makes a new random session and user per request (`app/runner.py:24-32`). The Docker variant needs `-e GEMINI_MODEL=…` too.
</details>

**B7 · Make module 2 really use LiteLLM** *(with an OpenAI key)*. Copy the folder to a name ADK accepts, put `OPENAI_API_KEY=…` in the root `.env`, use `LiteLlm(model="openai/gpt-5.6-luna")`. Predict what ADK 2.12 does with the bare `"gpt-4"`, and which folder name to choose.
<details><summary>Answer</summary>

`"gpt-4"` resolves to ADK's own `OpenAILlm`, not LiteLLM; `"openai/gpt-5.6-luna"` resolves to `LiteLlm`. Folder names: `2-litellm` → `Invalid agent name`; `litellm` → `No root_agent found for 'litellm'` (the real LiteLLM package is imported instead); `litellm_agent` loads. Without the key the first message fails locally with `OpenAIError: Missing credentials …`.
</details>

**B8 · MCP: the filter, and a tool on its way out.** Add `'read_text_file'` to `tool_filter` in a copy of `mcp_tools/agent.py`; predict the tools, what the server says about `read_file`, and what `search_files` returns for `agent` and for `**/*agent*`.
<details><summary>Answer</summary>

Four tools instead of three. The server describes `read_file` as "… DEPRECATED: Use read_text_file instead."; a filter naming a tool the server no longer has raises no error, the agent just sees fewer tools. `search_files` matches **file names** with globs: `agent` → "No matches found"; `**/*agent*` → `mcp_tools/__pycache__/agent.cpython-313.pyc` and `mcp_tools/agent.py`. A `read_file` of the repo's `.env`, one folder up, is refused: "Access denied - path outside allowed directories".
</details>

**B9 · Travel Planner: try to approve your own plan** *(no model calls)*. After the cells up to *Travel Agent*, call `finalize_plan` twice, then `apply_confirmation("Yes!", ctx)`, then `finalize_plan` again (snippet in `exercises.md`). Predict the three lines, which replies approve (`Yes!`, `yes please`, `Yes, please.`, `y`, `Confirm.`, `OK`, `sure`, `Yes go ahead`), and two variants.
<details><summary>Answer</summary>

`needs_confirmation`, `needs_confirmation`, `2690.0`. Only `apply_confirmation` approves, and it runs on the human's message before the agent. It strips, lower-cases and drops trailing `.`, `!` and spaces, then compares with six exact strings: `Yes!`, `yes please`, `y`, `Confirm.` approve; `Yes, please.`, `OK`, `sure`, `Yes go ahead` don't, and any other reply drops the pending proposal. The 15:00 outbound flight → total 2,790; hotel `SFO-GATE` with `pet_friendly=True` → `ValueError` (not pet-friendly); with `pet_friendly=False` → 2,410, but `needs_confirmation` again (the yes approved a different proposal). Free: no model calls.
</details>

**B10 · Newsletter: make the URL rule a check.** Add a URL regex to `validate_newsletter` (cell 18; code in `exercises.md`) and predict what the editor's tool and `send_email` return for a draft with "Promotion URL: https://…".
<details><summary>Answer</summary>

As committed such a draft passes (`{'status': 'ready'}`) and is saved. With the check, `review_draft` returns `{'status': 'error', 'message': 'Remove embedded URLs from the newsletter text; sources are linked by ID.'}` and `send_email` returns the same error with no receipt. Links still appear: the renderer adds each story's sources from the registry. With your key, expect more (billed) editor calls. A rule that matters belongs in code.
</details>

**B11 · Keep your sessions out of git.** After the rename and one session, predict what `git add --all --dry-run` adds; then add `.adk/` to `.gitignore` and run `git check-ignore -v baseline/.adk/session.db`.
<details><summary>Answer</summary>

It lists `add 'baseline/.adk/session.db'` with your renamed folders: the repo ignores `.env`, `.venv` and `uv.lock`, not `.adk/`. After `echo ".adk/" >> .gitignore`, `git check-ignore -v` answers `.gitignore:73:.adk/  baseline/.adk/session.db`. Already committed: `git rm --cached baseline/.adk/session.db`.
</details>

### Debugging

**C1 · "My baseline runs on `gemini-2.0-flash` and says the API key is not valid, but my root `.env` is right."** A classmate followed `1-baseline/README.md`'s Setup inside the folder. What happened, and what else could that file leak?
<details><summary>Answer</summary>

ADK loads only the nearest `.env`: the log switches from `Loaded .env file for baseline at …/llm-agent-google-adk/.env` to `… at …/baseline/.env`, and every agent shows `model gemini-2.0-flash` (the module file has the placeholder key and `GEMINI_MODEL` commented out). Delete the module `.env` files and skip the module Setup steps. The leak: a `.env` copied into `mcp_tools/` sits inside the folder the filesystem server may read; `read_file` returned the whole file in the check.
</details>

**C2 · "`print(response.text)` on line 478 printed `None`."**
<details><summary>Answer</summary>

Call 2 answered with another function call (AUTO mode allows it); `response.text` joins only text parts, and google-genai warns about non-text parts. Nothing runs that call (G23). Look at `response.candidates[0].content.parts`, or loop (B3).
</details>

**C3 · "`uv sync` fails with `onnxruntime` and `cp315`, although my laptop has Python 3.12."**
<details><summary>Answer</summary>

uv prefers the Pythons it manages. With only a system 3.12.15, `uv sync --dry-run` used it; after `uv python install 3.15` (an earlier project, or a first failed sync, leaves one behind) the same command said `Using CPython 3.15.0` and failed on `onnxruntime==1.31.0`. Fix: `uv python pin 3.13`, then `uv sync` (G20).
</details>

**C4 · `` KeyError: "Context variable not found: `itinerary_validation` in agent 'TravelPlanner'." ``**
<details><summary>Answer</summary>

Nothing wrote that key before the planner's instruction was filled: the validator's `output_key` was renamed, or the planner ran alone. Keep `output_key` and `{placeholder}` names identical; or write `{itinerary_validation?}`, which sends "Using , design …" with an empty value: it runs, but plans from nothing.
</details>

**C5 · Module 4's `/chat` answers `Internal Server Error`, and the log ends with `AttributeError: 'NoneType' object has no attribute 'parts'`.** Is the bug in FastAPI?
<details><summary>Answer</summary>

No: read the first error. The model call failed (placeholder key, or no network); ADK turns that into a final event with no content (`error_code` set), and `app/runner.py:46` reads `event.content.parts[0].text`. Fix the key, then make the wrapper check `event.error_code` before reading the content.
</details>

**C6 · Cheese Quiz: "I edited the MCP tool, reran *Build your own MCP Server*, and the agent still returns the old facts."**
<details><summary>Answer</summary>

The first server still holds port 8001 in the same runtime. The rerun prints `Server thread alive: True` before the new server tries to bind, then fails with `[Errno 98] … address already in use`; the old function keeps answering. *Runtime › Restart session* and rerun the setup cells, or use another port.
</details>

**C7 · Cleaning up `6-rag/1-vertex-rag-engine`.** `setup_corpus.py` stopped at `Error: GOOGLE_CLOUD_PROJECT environment variable not set.`, and later option 5 answered `Cancelled.` after you typed `y`.
<details><summary>Answer</summary>

`load_dotenv()` finds your root `.env`, where `GOOGLE_CLOUD_PROJECT` is commented out: put it in the module's `.env` or export it. The delete prompt accepts only the whole word `yes` (`y` cancels). Then check the console's RAG Engine page and the billing report: per Google's documentation the default Spanner mode keeps a provisioned instance until you switch the tier to *Unprovisioned*.
</details>

**C8 · `6-rag/2-custom-chromadb-rag`: unhealthy, v1 heartbeat error, documents gone after `down`/`up`.**
<details><summary>Answer</summary>

Chroma is up (`/api/v2/heartbeat` → 200; v1 → 410). The healthcheck runs `curl`, which the image lacks, on the v1 path: ignore it or drop it. The data went to `/data`, not the mounted `/chroma/chroma`, so `down` removed it: mount the volume at `/data` (G14).
</details>

### Think

**D1 · Data, action, orchestration.** Sort the lecture's tools into the three families of slide 51, and say where the checks sit. Who decides what `ask_head_cheesemonger` returns?
<details><summary>Answer</summary>

Data: the two book searches, `web_search`, `list_directory`, `read_file`. Action: `write_file` (filtered out), `finalize_itinerary`, `send_email`. Orchestration: the `.as_tool` specialists, `researcher_agent`, `editor_agent`. The decisive checks sit on the action tools. `ask_head_cheesemonger(prompt, default_decision=True)` (Cheese Quiz cell 62) returns an argument **the model writes**: the "human decision" is the model answering itself.
</details>

**D2 · Force the search, or let the model choose?** Name a question where `ANY` helps and one where it hurts; what would a Self-RAG-style agent add?
<details><summary>Answer</summary>

`ANY` helps when the answer must come from your books, and hurts on "Hi! Who are you?" (a paid embedding and ten unrelated chunks). AUTO handles greetings but may skip the search for a question the model thinks it knows, and without the (never sent) system instruction nothing tells it to prefer the books. Self-RAG adds grading steps: decide whether to retrieve, then check relevance, support and usefulness, and retrieve again if needed.
</details>

**D3 · Session state is not memory.** What would an agent need to remember *you* next time, in the lecture's sense (slides 40-41)?
<details><summary>Answer</summary>

A store keyed by user, a write step that decides what to keep, and a read step that puts it back in the envelope. Today's runs show only pieces: the Cheese Quiz's step 5 pastes a profile; ADK's state lasts one session (sessions persist in `.adk/session.db`, but they are transcripts); module 4 makes a new session per request; the Travel Planner's `SQLiteSession` is in-memory. ADK has a separate memory service (`memory_service`, `load_memory`/`preload_memory`) that none of the tutorial's code uses.
</details>

**D4 · Every hop costs.** Count the Guild orchestrator's turns on the longest path its instructions allow. Is `max_turns=12` enough? How would you enforce "at most 2 reviews" in code?
<details><summary>Answer</summary>

Research, vegan specialist, write, review, rewrite, review, ask the head cheesemonger, JSON format, final answer: 9 model calls, so 12 leaves 3 spare. `max_turns` counts only the orchestrator's calls; each agent-as-tool runs its own `Runner.run` with its own default budget of 10, so one quiz can make dozens of calls. Enforce the rule with a counting `review_quiz` tool of your own, or a fixed sequence in Python.
</details>

**D5 · Fix the enum, or fix the data?** Would adding the two missing authors to the enum make both books reachable by author?
<details><summary>Answer</summary>

Only one. *Cottage Cheese Recipe Book*'s chunks carry `author: 'Milk Industry Foundation'`, so the filter works. The Woman's Institute book's chunks have no author at all (L05's `filename.split(".")[0]` slip, `cli.py:178`): filtering returns 0 results and an empty function response. Fix the data first (L05's exercise: `os.path.splitext`, then chunk, embed and load again), then the enum.
</details>

**D6 · Put the agent behind a web page.** L18's app reuses this `agent_tools.py`. If anyone can type the question, what can they control, what does each question cost, and what would you change first?
<details><summary>Answer</summary>

Only the question: `author` is limited to the enum, `search_content` is only embedded, `n_results` is fixed. Each question costs at least two Gemini calls and one embedding call, with no per-user limit. First changes: send the system instruction; cap calls per question and per user; return only `response.text` with the empty and function-call cases handled; treat retrieved text as data, never as instructions.
</details>

---

## 9. Errata and open questions

**Errors and inconsistencies (with evidence)**

- **E1. Cheese Quiz Step 2 swaps roles.** Cell 39, lines 18-21 send `{"role": "user", "content": system_prompt}` and `{"role": "system", "content": user_prompt}`. The "prompt engineering" comparison therefore tests a malformed conversation. Step 3 onward uses the correct order (cell 40).
- **E2. `out.txt` and the README diagram come from the old instructor's book.** The recorded retrieval mentions "cultural artifact", "transhumance", "Monastic orders", "within two milkings" and "Soča Valley". The captured counts: `transhumance`, `Soča`, `Monastic`, `cultural artifact` appear 2/3/1/2 times in `out.txt`, **0** times in today's `input-datasets/books/Tolminc Cheese.txt`, and 3/7/1/1 times in `85bba32^`. Your run will differ.
- **E3. `SYSTEM_INSTRUCTION` is dead code.** It is defined at `llm-rag/cli.py:40-58`, but neither `chat()` (`cli.py:394-396`) nor `agent()` passes it, so "answer only from chunks" is never enforced: the captured request bodies of both calls have no `systemInstruction`. The legacy `pipenv` branch did use it (`GenerativeModel(GENERATIVE_MODEL, system_instruction=[SYSTEM_INSTRUCTION])`, `origin/pipenv:cli.py:62-65`). The `59a0f80` migration to google-genai commented that wrapper out, and no later commit passes the instruction to `generate_content`.
- **E4. Two of eleven books are unreachable by author.** "Milk Industry Foundation" (`cli.py:62`) and "Woman's Institute…" (`cli.py:70`) are missing from the enum (`agent_tools.py:19-29`). In addition, `filename.split(".")[0]` (`cli.py:178`) turns "Womans Institute Library of Cookery. Volume 2_ …" into "Womans Institute Library of Cookery", so that book's chunks get no `author`/`year` metadata (`cli.py:135-138`). Captured on the loaded collection: 178 chunks with `author = 'Milk Industry Foundation'` and 1,505 with `author = None`. Both books stay reachable through `get_book_by_search_content`.
- **E5. README says "Displays the LLM's response"** (`README.md:266`). The code prints the entire SDK response object (`cli.py:478`; see `out.txt:98-137`), so the answer is buried in metadata. Print `response.text` (and see G23).
- **E6. ADK repo dependency drift.**
  - No lockfile (`.gitignore:34`), and every pin is open-ended (`pyproject.toml:9-20`). On 2026-10-18 this yields google-adk 2.12.0 (2.11.0 on Python 3.10), which rejects every hyphenated module folder name (G1), and on a machine where uv picks CPython 3.15 the sync fails outright (E17).
  - The `pyproject.toml:2` comment "google-adk[all] extra doesn't exist" was true for 1.x (the 1.19.0 and 1.27.5 METADATA have no `all` extra) but is false for 2.x (2.12.0 has one), while the module `pyproject.toml`s still request `google-adk[all]`.
  - Module `pyproject.toml`s point hatch at a non-existent `src/adk_tutorial_baseline` (e.g. `5-custom-agent/pyproject.toml:16-17`). A toy project with the same build settings still builds and installs (an empty package).
- **E7. Retired model defaults.** `gemini-2.0-flash` is hard-coded as the fallback in 8 places (e.g. `1-baseline/agent.py:12`, `2-litellm/litellm_config.py:62`), set in 4 `.env.example` files (e.g. `5-custom-agent/.env.example:5`) and suggested in 3 more as comments (`1-baseline/.env.example:16`, `3-mcp-tools/.env.example:14`, `2-litellm/.env.example:22` as `FALLBACK_MODEL`). Google's deprecation page lists its shutdown as 2026-06-01. `6-rag/1-vertex-rag-engine/agent.py:47` hard-codes `gemini-2.5-flash` and ignores `GEMINI_MODEL`. The module READMEs' code samples also use `gemini-2.0-flash` (e.g. `1-baseline/README.md:111`, `3-mcp-tools/README.md:120`).
- **E8. Wrong folder name, and QUICKSTART.md is stale throughout.**
  - `cd google-adk-tutorial` (`README.md:78`, `QUICKSTART.md:10`) fails: the clone is `llm-agent-google-adk` (captured).
  - File paths passed to `adk web` (`QUICKSTART.md:24, 32, 42, 57`; captured error, G9).
  - A `3-mcp-connections` folder that never existed in this repo (`QUICKSTART.md:42, 84`); `2-litellm/README.md:238` also links to `../3-mcp-connections/`.
  - Scripts that never existed (`QUICKSTART.md:70-72, 79, 85, 91-92`).
  - Wrong descriptions: Tutorial 2 "auto-selected based on your API keys" with `AWS_OPENAI_API_KEY` (`QUICKSTART.md:34-36`; the code hard-codes `model="gpt-4"`), and Tutorial 5 as a "Custom Story Agent" with critique/revision/tone analysis (`QUICKSTART.md:55-61`; `5-custom-agent/agent.py` only prefixes 🤖).
- **E9. `uv run adk` without `web`** at `2-litellm/README.md:74`, `3-mcp-tools/README.md:85`, `5-custom-agent/README.md:120`: it prints the command list and exits 2 (captured).
- **E10. 2-litellm cannot work as written.**
  - `model="gpt-4"` (`2-litellm/agent.py:26`) has no provider prefix: ADK 1.x does not route it to LiteLLM, and ADK 2.11/2.12 resolve bare `gpt-*` names through a native `OpenAILlm` class (2.12 `models/__init__.py:80-81`), not LiteLLM.
  - `AWS_OPENAI_API_KEY` (`2-litellm/.env.example:5`) is unused.
  - "Option 2: Test LiteLLM Configuration" (`2-litellm/README.md:81-88`, also `QUICKSTART.md:78`) runs `litellm_config.py` as a script, but the file has no `__main__` block, so it prints nothing (G19).
  - "ADK supports LiteLLM model names natively" (`2-litellm/README.md:195`) is inaccurate for bare names.
- **E11. 5-custom-agent README uses attributes that do not exist.** `ctx.history` (`5-custom-agent/README.md:80, 288`) and `ctx.session_id` (`5-custom-agent/README.md:81`) are not `InvocationContext` attributes in google-adk 1.19 (fields at `agents/invocation_context.py:144-206`; there is a `user_id` property at line 324). Use `ctx.session.events`, `ctx.user_content` and `ctx.session.id`.
- **E12. "Memory" vs "state."** `llm-agent-google-adk/README.md:140` defines "Memory" as per-session structured state and says "separate sessions do not share memory". In ADK, per-session data is *state*. *Memory* is the separate, cross-session `memory_service` (`invocation_context.py:146`). The Cheese Quiz's own definitions (cells 41-42) use the standard meaning.
- **E13. 6-rag/2-custom-chromadb-rag details.**
  - v1 heartbeat (`6-rag/2-custom-chromadb-rag/docker-compose.yml:16`, `6-rag/2-custom-chromadb-rag/README.md:33`) against a v2-era server: HTTP 410 today, and the image has no `curl` for the healthcheck (G14).
  - The collection is created with the default distance (L2) (`6-rag/2-custom-chromadb-rag/ingest_documents.py:130-133`), yet results are reported as `"similarity": 1 - distance` (`6-rag/2-custom-chromadb-rag/agent_tools.py:151`). That is not a cosine similarity and can be negative.
  - `6-rag/README.md:133` says "ingest documents (assumes RAG is already populated)", which contradicts the command it precedes.
- **E14. Notebook nits.**
  - All three notebook banners link to `2025-AC215` while saying "Fall 2026" (cell 0 of each).
  - Cheese Quiz cell 57's comment says port 8000 but the code uses 8001. The saved output of that cell (from an older version) prints 8000.
  - Cheese Quiz cell 49's saved output shows `I am a tool` lines that the current tool code no longer prints.
  - Cheese Quiz cell 70 asks the orchestrator to "update context.fact_cache[topic]", but no context object is passed to `Runner.run` (cell 71) and no tool can write it.
  - The Newsletter's cell 23 markdown ("six tools… clarification, options, a checked itinerary…") is copied from the Travel Planner. The orchestrator has three tools (cell 25, lines 12-16).
  - The Newsletter's `USERS` list contains real course-staff names and email addresses (cell 16). Nothing is sent, but replace them before running or sharing outputs.
  - The Newsletter's saved Run Demo output (cell 27) shows four readers, but two of them are now commented out in cell 16 (lines 10-11). The saved output therefore does not match what the current code produces.
- **E15. The harness does not enforce "plain text, no URLs".** `EDITOR_INSTRUCTIONS` (cell 22, line 16) forbids embedded URLs, but `validate_newsletter` (cell 18) doesn't check, and the saved Summerville preview contains `Promotion URL: https://shop.lowesfoods.com/...` (plus `Store URL:` and `Product URL:` lines) inside offer summaries. A soft (prompt) rule vs a hard (code) rule; §8 B10 makes it a check.
- **E16. The README's agent diagram simplifies step 5.** `images/llm-rag-flow-3.png` shows step 5 as "User question + chunks to build prompt". The code does not rebuild a prompt: the second call sends three contents, the question, the model's own function-call turn (with its thought signature) and a `function_response` part holding the chunks (`cli.py:465-477`; captured request, §4 B3). The diagram's search text "cheese making" also differs from the recorded call's `'cheese making importance location'` (`out.txt:23`).
- **E17. The ADK README's `uv sync` fails on a fresh machine today.** The README asks for "Python 3.10+ installed on your system" (`README.md:61`) and then `uv sync` (`README.md:100`), with no Python pin and no lockfile. On a laptop with no Python, uv 0.13.1 downloads CPython 3.15.0 and the sync stops because `onnxruntime` 1.31.0 has no cp315 wheel (captured, G20). Fix: `uv python pin 3.13`.
- **E18. The module folders can't be agent names.** `1-baseline/README.md:86` says to "select this tutorial folder (`1-baseline`)" in the dev UI; today's ADK (2.12.0) refuses the name in its agent loader, and the older versions checked (1.19.0, current at the repo's last commit, through 1.27.5) refuse it in the web server's app-name check (G1). The digest's earlier suggestion, a version pin, does not fix it; renaming the folders does (captured).
- **E19. ADK 2.12's telemetry question is not mentioned.** The first `uv run adk web` in a terminal stops at `Enable telemetry? [Y/n]:`, where Enter means yes although the text says "This is OFF by default" (captured, G21).
- **E20. Sessions are written inside the repo and not ignored.** `adk web` stores `<agent>/.adk/session.db` in each agent folder; the repo's `.gitignore` does not list `.adk/` (captured `git status --ignored`, G22).
- **E21. Small llm-rag slips.** The Agents section (`README.md:242-271`) doesn't say it needs L05's `char-split-collection` (G6); both search-text descriptions say "Expand the search term to a a sentence or two" (doubled "a", `agent_tools.py:33, 61`), and the recorded run sent four words anyway (`out.txt:23`).

**Open questions (could not determine from the sources)**

- What the Ed lesson itself contains beyond the slides (the recorded lecture, announcements about version pins or folder names). Ed could not be opened; the lecture slides are digested in [Lecture slides](#lecture-slides).
- How the course intends students to run the ADK modules today: with renamed folders (what works in the captures), or a fixed version of the repo. Neither README mentions version constraints, and the repo predates ADK 1.28/2.x.
- What backend the hosted "Cheese Agent Tool" (https://ac215-llm-rag.dlops.io/agent) calls, and whether it needs your local ChromaDB. The page loads (HTTP 200 on 2026-10-18, captured), but its client bundle reveals no endpoint.
- Whether the whole `mcp_tools` agent (Gemini + `MCPToolset` + `@modelcontextprotocol/server-filesystem` 1.0.0, which declares JSON-Schema-2020 input and output schemas) answers end to end; the toolset part was captured, the model part needs a key.
- Whether `gemini-3.1-flash-lite` is enabled for every student project in location `global`. It worked for the course staff on 2026-09-22 (`out.txt:34`). Availability can vary by project and organisation policy.
- OpenAI model lifecycles (deprecations page re-checked 2026-10-18): `gpt-5.6-luna` (Travel Planner, Newsletter, and the Agents SDK default) is listed only as a recommended replacement, so it is current. The `gpt-4o-2024-05-13` snapshot shuts down 2026-10-23. On 2026-10-14 OpenAI announced that GPT-4o (`gpt-4o-2024-08-06`, `gpt-4o-2024-11-20`), GPT-4o mini, GPT-4.1 and GPT-4.1 mini shut down on **2027-01-14** (replacement `gpt-6-luna`). The page does not name the bare `gpt-4o` alias the Cheese Quiz uses; expect it to stop working by then, after the Fall 2026 term.

---

## Links

- README sections, `dlops-io/llm-rag` (pinned commit): [Agents](https://github.com/dlops-io/llm-rag/blob/e17a39f35bc07b440f573def480adaf4703f8b91/README.md#agents) · from L05, needed here: [Prerequisites](https://github.com/dlops-io/llm-rag/blob/e17a39f35bc07b440f573def480adaf4703f8b91/README.md#prerequisites) · [Run LLM RAG Container](https://github.com/dlops-io/llm-rag/blob/e17a39f35bc07b440f573def480adaf4703f8b91/README.md#run-llm-rag-container) · [Chunk Documents](https://github.com/dlops-io/llm-rag/blob/e17a39f35bc07b440f573def480adaf4703f8b91/README.md#chunk-documents) · [Generate Embeddings](https://github.com/dlops-io/llm-rag/blob/e17a39f35bc07b440f573def480adaf4703f8b91/README.md#generate-embeddings) · [Load Embeddings into Vector Database](https://github.com/dlops-io/llm-rag/blob/e17a39f35bc07b440f573def480adaf4703f8b91/README.md#load-embeddings-into-vector-database) · latest README on `main` as the course site links it: [#agents](https://github.com/dlops-io/llm-rag?tab=readme-ov-file#agents)
- README sections, `dlops-io/llm-agent-google-adk` (pinned commit): [Prerequisites](https://github.com/dlops-io/llm-agent-google-adk/blob/f89faa79de744f6a046e30dff24b3b6f1d73720b/README.md#prerequisites) · [Getting Started](https://github.com/dlops-io/llm-agent-google-adk/blob/f89faa79de744f6a046e30dff24b3b6f1d73720b/README.md#getting-started) · [Running Agents](https://github.com/dlops-io/llm-agent-google-adk/blob/f89faa79de744f6a046e30dff24b3b6f1d73720b/README.md#running-agents) · [Key Concepts: Session, Memory, Runner](https://github.com/dlops-io/llm-agent-google-adk/blob/f89faa79de744f6a046e30dff24b3b6f1d73720b/README.md#key-concepts-session-memory-runner) · [Sequential Agent Data Flow](https://github.com/dlops-io/llm-agent-google-adk/blob/f89faa79de744f6a046e30dff24b3b6f1d73720b/README.md#sequential-agent-data-flow)
- Module READMEs (pinned commit): [1-baseline](https://github.com/dlops-io/llm-agent-google-adk/blob/f89faa79de744f6a046e30dff24b3b6f1d73720b/1-baseline/README.md) · [2-litellm](https://github.com/dlops-io/llm-agent-google-adk/blob/f89faa79de744f6a046e30dff24b3b6f1d73720b/2-litellm/README.md) · [3-mcp-tools](https://github.com/dlops-io/llm-agent-google-adk/blob/f89faa79de744f6a046e30dff24b3b6f1d73720b/3-mcp-tools/README.md) · [4-production-ready](https://github.com/dlops-io/llm-agent-google-adk/blob/f89faa79de744f6a046e30dff24b3b6f1d73720b/4-production-ready/README.md) · [5-custom-agent](https://github.com/dlops-io/llm-agent-google-adk/blob/f89faa79de744f6a046e30dff24b3b6f1d73720b/5-custom-agent/README.md) · [6-rag](https://github.com/dlops-io/llm-agent-google-adk/blob/f89faa79de744f6a046e30dff24b3b6f1d73720b/6-rag/README.md) · `QUICKSTART.md` is stale, skip it (G9, E8)
- Ed lesson: [L06 · LLM: Agents I](https://edstem.org/us/courses/97373/lessons/166030/) · course [tutorials page](https://harvard-iacs.github.io/2026-AC215/tutorials_demo/)
- Colab: [Cheese Quiz](https://colab.research.google.com/drive/14UKW-Z7kFPuCwVqyUFcLxeA1KF70fwfm?usp=sharing) · [Travel Planner](https://colab.research.google.com/drive/1I_jJEHJsVkGxNoSC1c4wEoVF2QL6vCVY?usp=sharing) · [Cheese Newsletter · Harness](https://colab.research.google.com/drive/1nnHrJ4Si3tpgUQl6HqlcwxKymV1-ecPv?usp=sharing)
- Hosted demo (optional, Chrome): [Cheese Agent Tool](https://ac215-llm-rag.dlops.io/agent)
- Video and materials: [video folder](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l06-agents-1) · [exercises.md](https://github.com/JunyiZhou-Conny/Explainer_Videos/blob/main/videos/ac215-l06-agents-1/exercises.md) · [terminal captures](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l06-agents-1/assets/terminal) · [exercise checks](https://github.com/JunyiZhou-Conny/Explainer_Videos/tree/main/videos/ac215-l06-agents-1/assets/exercise-checks)
- Previous lecture: [L05 · Introduction to RAG](L05-rag.md) (the `llm-rag` container, the chunk → embed → load pipeline and the `char-split-collection` this agent queries)
- Next lecture: [L07 · LLM: Agents II](L07-agents-2-harness.md) (the `agent-harness` repo: this lecture's harness ideas become the main topic)
- Referenced in §7: [L01 · Virtual Environments and Virtual Machines](L01-vms-venvs.md) (uv and `uv python pin`) · [L18 · APIs + Frontend](L18-apis-frontend.md) (`cheese-app-v2` serves this agent behind an API)
