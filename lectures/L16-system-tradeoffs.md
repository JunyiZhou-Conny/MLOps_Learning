# L16 lecture slides — System Tradeoffs: Performance, Cost, and Design Choices

Source: one deck, `L16_system_tradeoffs_updated` (81 slides; title slide: AC215 / E115, Pavlos Protopapas, SEAS / Harvard). These are the instructor's lecture slides (PDF), provided by the student for study; the PDFs are not in this repository; slide numbers are PDF page numbers (the page number printed in each slide's footer matches its PDF page, 1–81). L16 has no tutorial repo (`course/lectures.yaml` lists `tutorials: []`), so where this digest compares vocabulary it uses the neighbouring tutorials as our guides record them (L02/L04 Docker ports, L10 service accounts, L14 Cloud Run / Cloud Functions, L18 cheese app, L20 single VM + nginx, L22 GKE). Those comparisons are marked *ours*; everything else restates the slides in our own words.

**What kind of lecture this is.** It covers architecture and operations, with no code walkthrough. It builds one running example, a FastAPI `/predict` service (labelled "Python 3.14"), a ChromaDB vector store and a React/Vite or Next.js frontend, from a laptop process up to a three-subnet AWS VPC. It then compares the managed compute, frontend, data and identity services you could run them on, and ends with a five-step decision method. The examples are **AWS-first** (EC2, ECR, ALB, Route 53, ECS, Fargate, EKS, Lambda, CloudFront, RDS), with Google Cloud equivalents on slides 34, 50–51, 55–56, 59 and 68. The tutorials all use GCP. The title promises "Performance, Cost", but the slides give **no prices and no benchmark numbers**. Each trade-off appears as an *operating contract*: which layer the provider runs and which the team still configures.

## 中文速览

- **这一讲讲什么：** L16 没有 tutorial，也没有 video，只有一份 81 页的 slides（"System Tradeoffs: Performance, Cost, and Design Choices"）。全程用同一个例子：FastAPI 的 `/predict` service、ChromaDB 和一个 React/Vite 或 Next.js frontend，从 laptop 搬进一个分三层 subnet 的 AWS VPC，再比较 compute、frontend、data、identity 的各种 managed service，最后给一个五步的 decision method。例子以 AWS 为主（GCP 对照在 slides 34、50–51、55–56、59、68）。标题写了 "Performance, Cost"，但 slides 里没有一个价格或 benchmark 数字；每个 trade-off 都写成一份 operating contract：provider 管哪一层，team 还要自己配哪一层。
- **Idea 1 · 网络基础（4–16）：** 有 public IP 不等于 reachable，route 和 firewall 都要放行（4、13）。CIDR 的 address 数是 2^(32 − prefix)，`10.0.0.0/12` 有 1,048,576 个（7）。outbound 连接的 source port 由 OS 挑，reply 能回来是因为 stateful firewall（9）；自己的 app 要用一个明确的 user port（10）。security group 只有 allow rule（11）。route table 里 `0.0.0.0/0` 指向 Internet Gateway 就是 public subnet，指向 NAT Gateway 就是 private subnet（13）；NAT 只让 private server 往外连，不接 inbound（14）。VPC 分 public、private app、private data 三层（16）。
- **Idea 2 · container 上 cloud（17–26）：** image 只 build 一次，push 到 registry（ECR），每次 deploy 都 pull 同一个 tag `myapp:v1.4`（17、29）。`-p 8080:8000` 里 host port 和 container 里的 listener 分开配（19）；SSH 是 admin access，到的是 machine，HTTPS `:443` 是 client access，到的是 service（20）。config 在 startup 时注入，secret 从 secret manager 交给 workload identity，"Inject, Don't Bake"（21–22）。前门（Nginx 或 ALB）放在 public subnet，FastAPI 没有 public IP（23–24）；HTTPS 保护的是 public 那一段，TLS 在前门结束（25–26）。
- **Idea 3 · 一个 request 走三份 contract（27–32）：** 先 DNS（resolver → Route 53 → ALB 的 IP），再 browser →（HTTPS）→ ALB →（HTTP）→ FastAPI →（SQL）→ database（27–28）。browser 先下载 frontend 的 HTML/CSS/JS，然后是 browser 自己去 call API（30）。部署有两种 layout：两个 hostname，或者一个 hostname 按 path 分流（32）；cheese app 在 L20/L22 用的是后者（`/api-service`）。
- **Idea 4 · cloud service spectrum（34–59）：** compute capacity（EC2、Fargate）和 orchestration（ECS、Kubernetes）是两层（34）。ECS 一直把 actual state 拉回 desired count（43）；workload scaling（task 数）和 capacity scaling（有没有地方放）是两回事，capacity 跟不上，task 就 pending（45）。Cloud Run 把这几层合成一个 service（50）；function 适合 triggered、短小、bounded 的工作，warm instance 不是 durable state（53–54）。slide 58 的 ladder：越往右 provider 接手的层越多，但 security、tenancy、data、recovery 永远是你的。
- **Idea 5 · compute 以外（61–73）：** static frontend 放 CDN，在 VPC 外面，只有 API request 才进 ALB（62–64）。vector data 放哪里，决定谁来 operate 和 recover：自己在 VM 上跑 ChromaDB、managed PostgreSQL + pgvector，或者 vector search service（65–66）；managed database 的 HA 和 backup 要自己 configure，不是 default（67–68）。authentication（token 证明你是谁）≠ authorization（app 还要查 role 和 ownership）（69–70）。同一份 Next.js code 有 static export、Node/container、platform adapter 三种 contract，选最简单够用的那个（72–73）。
- **Idea 6 · 怎么选（75–81）：** trace the request → name the contract → choose the boundary → select a service → measure and revise（80）。先画 frontend → backend → data → identity，再谈 service 名字（75）；data 比 compute 活得久（76）；prototype 求 iteration，production 求 reliability，security 每个 stage 都要（77–78）；只有量出来真的需要，才加 complexity（80）。
- **和 tutorials 对上的地方：** tutorials 全在 GCP。security group ≈ L20 的 VPC firewall rule，NAT ≈ L22 的 Cloud NAT，ECS/EKS ≈ L22 的 GKE，Cloud Run 和 Cloud Run functions 在 L14，HTTPS 前门要到 L23 的 Google-managed certificate 才有。tutorials 没有 Secret Manager（本地 mount `secrets/` 里的 JSON key，cloud 上用 attached service account 或 L22 的 Workload Identity），没有 CDN，没有 Fargate 那样的 capacity，没有 managed PostgreSQL，cheese app 也没有 user sign-in。32 个 key ideas 里有 29 个在某个 tutorial 里用到；每个 idea 在哪个 guide 的哪一节，见文末的 [Where this shows up in the tutorials](#where-this-shows-up-in-the-tutorials)。

## Outline

- Slide 1 · title
- Slide 2 · outline (four sections; "Prerequisites" highlighted)
- **Section 1 — Prerequisites: slides 3–32**
  - Slide 3 · local laptop vs. deployed service (what deployment adds)
  - Slides 4–8 · IP addresses: private vs. public IP (4), CIDR notation (5), in-class CIDR question (6) and its answer (7), special and private address ranges, RFC 1918 (8)
  - Slides 9–11 · ports and firewalls: ports as doors, inbound vs. outbound vs. response (9), port number ranges (10), security groups (11)
  - Slides 12–16 · network layout: subnets as streets (12), public vs. private subnets and route tables (13), NAT gateway (14), VPC as a gated community (15), three-subnet VPC: public / private app / private data (16)
  - Slides 17–22 · containers in the cloud: container registry (ECR) as the deployment handoff (17), same image on laptop vs. EC2 (18), Docker port publishing (19), administrative vs. client access (20), runtime configuration (21), secrets: "Inject, Don't Bake" (22)
  - Slides 23–28 · the public front door and one request's path: Nginx on EC2 keeping FastAPI private (23), Nginx vs. ALB (24), HTTP readable on the public path (25), HTTPS encrypting it (26), DNS resolution to the ALB (27), one `/predict` request crossing three contracts (28)
  - Slide 29 · build once, deploy that exact image
  - Slides 30–32 · frontend + backend: page load then API call (30), what lives in one web project (31), two runtime layouts for one product (32)
- Slide 33 · outline divider (section 2 highlighted)
- **Section 2 — The Cloud Service Spectrum: slides 34–59**
  - Slide 34 · compute capacity (EC2, Fargate) vs. orchestration (ECS, Kubernetes)
  - Slides 35–37 · EC2: one VM per service (35), prototype with several services on one VM (36), the instance contract (37)
  - Slides 38–40 · Fargate: capacity that ECS/EKS schedules onto (38), what AWS operates vs. what the team configures (39), EC2 vs. Fargate on the same questions (40)
  - Slides 41–42 · task and pod as the scheduling wrapper (41), same wrapper on different capacity (42)
  - Slides 43–46 · ECS: reconciling desired state (43), what / how many / where (44), workload vs. capacity scaling (45), control plane outside your VPC (46)
  - Slides 47–49 · EKS: control plane outside your VPC (47), AWS-run vs. team-run parts (48), ECS or EKS (49)
  - Slides 50–51 · Cloud Run: Google runs routing, revisions and instances (50), Cloud Run vs. ECS/Fargate (51)
  - Slide 52 · scaling as signal → policy → desired count → capacity
  - Slides 53–56 · functions: triggered, bounded work (53), good and poor fits (54), Lambda vs. Cloud Run functions concurrency (55), runtime contracts compared (56)
  - Slides 57–59 · summary: match workload to runtime (57), what each service's provider operates (58), AWS ↔ Google Cloud approximate neighbours (59)
- Slide 60 · outline divider (section 3 highlighted)
- **Section 3 — Beyond Compute: Frontend, Databases & Services: slides 61–73**
  - Slide 61 · the names (Python, JavaScript, FastAPI, React, Vite, Next.js, CDN, CloudFront) describe different jobs
  - Slides 62–64 · static frontend: two browser paths (62), who assembles the delivery pipeline (63), frontend + VPC request paths (64)
  - Slides 65–68 · data: three ways to deploy vector data (65), their trade-offs (66), what managed PostgreSQL actually operates (67), PostgreSQL services on AWS and Google Cloud (68)
  - Slides 69–70 · identity: authentication (sign in, token, verify) (69) and authorization (70)
  - Slide 71 · complete picture from browser to data
  - Slides 72–73 · Next.js: three runtime contracts (72), choosing one (73)
- Slide 74 · outline divider (section 4 highlighted)
- **Section 4 — What Should I Use?: slides 75–80**
  - Slide 75 · step 1: draw the request path
  - Slide 76 · step 2: classify the data
  - Slide 77 · step 3: know the stage (prototype vs. production)
  - Slide 78 · step 4: assemble the architecture
  - Slide 79 · step 5: match components to requirements (blank worksheet)
  - Slide 80 · quick reference: the decision order
- Slide 81 · closing: "Thank you" and a prompt to sketch one request path

All 81 slides are covered above.

## Key ideas

1. **Deployment adds an endpoint and a lifecycle.** The same FastAPI app is the same code on a laptop or in the cloud. Deployment gives it a network endpoint other machines can reach (`https://app.example.com` instead of `http://localhost:8000`) and a lifetime tied to the provisioned service rather than to your laptop and process. — slide 3
2. **An address alone does not make a server reachable.** A machine can have a private IP (not routed on the internet) and a public IP (routable). Even a public IP is reachable only if routes and firewall rules allow it. `127.0.0.1` never leaves the machine, and `0.0.0.0` as a listen address means "every local interface". RFC 1918 reserves three private IPv4 ranges. — slides 4, 8
3. **CIDR counts addresses by counting the free bits.** In `IP/prefix` the prefix says how many of the 32 bits are fixed; the remaining bits vary, so the block holds 2^(32 − prefix) addresses (/32 = 1, /24 = 256, /16 = 65,536, /0 = everything). The in-class question works this out for `10.0.0.0/12`: 20 varying bits, 1,048,576 addresses (answer C). — slides 5–7
4. **Connection direction is set by whoever starts the connection.** An app listens on a port it chooses, such as `:8000` (inbound). When it calls out (to ChromaDB or OpenAI), the OS picks a temporary ephemeral source port. Replies come back because a stateful firewall remembers the connection. — slide 9
5. **Port ranges tell you which ports are safe to use.** 0–1023 are well-known ports (80, 443, 22) and usually need root. 1024–49151 are IANA user ports (8000, 5432, 6379, 3000). 49152–65535 are dynamic ports the OS hands out. The OS's own ephemeral range can reach down into the user-port range, so pick an explicit app port and check what is reserved. — slide 10
6. **A security group is an allow-list on the door.** It lets a connection in only if a rule matches it (protocol, port, source, e.g. "TCP 8000 from Nginx"). It has no deny rules: anything that matches no rule is blocked. Inbound starts empty, outbound starts allow-all, and replies to allowed connections are let back automatically. — slide 11
7. **A route table makes a subnet public or private.** A subnet is a block of addresses (e.g. `10.0.2.0/24`, 256 addresses) where servers live. It counts as "public" when its default route `0.0.0.0/0` points at an Internet Gateway and "private" when it points at a NAT Gateway. Even a public route is necessary but not sufficient: the server also needs a public IP mapping and matching firewall rules. — slides 12–13
8. **NAT lets private servers call out but not be called.** The NAT gateway sits in a public subnet. It rewrites the private source address, remembers the mapping and returns the replies. It never accepts new inbound connections. — slide 14
9. **A VPC is one private network carved into tiers.** The customer VPC (`10.0.0.0/16`) is split into /24 subnets: a public one for the entry point and NAT, a private app subnet (FastAPI, frontend server) and a private data subnet (ChromaDB / database). — slides 15–16
10. **The registry is the handoff between build and deploy.** A pipeline builds the image once, tests it, scans it for known vulnerabilities and tags it (`myapp:v1.4`). It pushes the image to a registry (ECR), and every deployment pulls that exact tag without rebuilding. Keep the registry in the same Region as the workload, and replicate it for multi-Region setups. — slides 17, 29
11. **The host port and the app's listen port are set separately.** With `docker run -p 8080:8000`, the laptop exposes `localhost:8080` and Docker forwards it to the container, where FastAPI listens on `0.0.0.0:8000` in a separate container network. On EC2 the same image runs unchanged, and VPC routes and security rules decide who can reach `10.0.2.5:8000`. — slides 18–19
12. **Administrative access and client access are different paths.** Operators reach the *machine* (SSH into an EC2 shell). Users reach the *service* (a public HTTPS endpoint on `:443` that forwards to target `:8000`). The app's listener does not change either way. — slide 20
13. **Use one immutable image and inject configuration and secrets at startup.** Development and production run the same image with different runtime values (`APP_ENV`, `LOG_LEVEL`, feature flags). Secrets come from a secret manager, delivered to the workload's identity and read with `os.getenv`. They never go in source code, images or Git, and each workload gets only the secrets it needs. — slides 21–22
14. **Put a front door in the public subnet and keep the app private.** Nginx on EC2 (or an ALB) takes HTTPS on `:443` in the public subnet and forwards over the internal network to FastAPI `:8000` in the private subnet. FastAPI has no public IP, and only the proxy may connect to it. Switching to an ALB moves the proxy hosts' operation (OS, scaling, replacement) to AWS, but the team still writes the routing rule. — slides 23–24
15. **HTTPS protects the public hop. The private subnet is protected by having no route in.** Over plain HTTP an on-path attacker can read and change the request body (cat.jpg → dog.jpg). With HTTPS they see only TLS ciphertext. TLS ends at the front door, and the hop inside the VPC is still HTTP. A direct attempt to reach FastAPI fails because the private subnet has no public route. — slides 25–26
16. **DNS comes before the connection.** The browser asks a resolver (Cloudflare `1.1.1.1`). The resolver asks the authoritative DNS (Route 53), whose `A` alias record for `api.example.com` points at the ALB. The ALB's IP comes back, and the browser then opens HTTPS to the ALB. — slide 27
17. **One request crosses three contracts.** A single `POST /predict` uses HTTPS from the browser to the ALB, HTTP from the ALB to FastAPI, and SQL from FastAPI to the database in the private data subnet. Each hop is a separate agreement you configure. — slide 28
18. **The browser first downloads the frontend and then calls the API.** It fetches HTML/CSS/JS from the frontend host. The running page then sends `POST /predict` to the API host and gets JSON back. A web project usually has a `frontend/` (React + Vite → static `dist/`, or Next.js → static files *or* a server) and a `backend/` (FastAPI process). It deploys in one of two layouts: two hostnames (static host + API front door), or one hostname whose front door routes by path to a Next.js server and FastAPI. — slides 30–32
19. **Compute capacity and orchestration are separate layers.** EC2 or Fargate supplies CPU and memory. ECS or Kubernetes (EKS on AWS, GKE on Google Cloud) decides what runs where, restarts failures and scales. The unit you schedule (ECS task / Kubernetes pod) wraps containers that move, restart and scale together, and that same wrapper can run on EC2 capacity or on Fargate capacity. — slides 34, 38, 41–42
20. **EC2 sells an instance contract, not hardware.** You ask for vCPU, memory, OS image, disk and subnet. AWS runs the physical fleet and virtualization. You patch the guest OS and your apps. One VM per service lets you scale or reboot each service alone but means three OSs to patch. All services on one VM (Docker network only, Nginx the only public port) is simpler, but one reboot stops everything and scaling means scaling the whole VM. — slides 35–37
21. **Fargate is capacity without a host to manage.** You describe a task (image, CPU, memory, private network, IAM role). ECS or EKS places it into AWS-run, isolated capacity, one task per "room". There is no host login. AWS patches the host OS, and the team still owns image, network, IAM, secrets, health and scaling, logs, data and recovery. — slides 38–40
22. **ECS keeps the actual state equal to the desired state.** The task definition says *what* runs (image, CPU, memory, ports). The ECS service says *how many* (desired count 3) and replaces a failed task. The launch type or capacity provider says *where* (EC2 or Fargate). Raising the task count (workload scaling) is separate from adding capacity to place the tasks on, and tasks stay pending when capacity lags. The ECS and EKS control planes run outside your VPC. — slides 43–47
23. **Choose ECS by default and EKS when you have a concrete reason.** EKS gives you the Kubernetes API and ecosystem, but AWS runs only the API servers and etcd. The team still runs nodes or Fargate profiles, add-ons, policy, upgrades and observability. — slides 47–49
24. **Cloud Run combines the layers.** It is one request-serving service in which Google routes requests and starts and stops instances, while the team sets the image, ingress, identity and scaling limits. Data and external services stay separate dependencies. Scaling in general is a chain: a signal (CPU, concurrent requests, queue depth), a policy (target, min, max), a desired count and enough capacity. Downstream limits such as the database still cap the result. — slides 50–52
25. **Functions suit triggered, short, bounded work.** An HTTP call, queue message or schedule runs a handler that produces one result. Webhooks, scheduled clean-ups and small bursty jobs fit well. Sustained HTTP concurrency, long or heavy startups and stateful connections need careful evaluation, and longer or multi-step work belongs in a job or workflow. A warm instance being reused helps latency, but it is not durable state. Lambda runs one request per environment, so overlapping requests create more environments. Cloud Run functions let several requests share an instance through configured concurrency. — slides 53–56
26. **A managed service hands over one named layer, not the whole job.** Moving from EC2 to ECS/EKS, Fargate, Cloud Run and Lambda, the provider takes over more layers (hardware → control plane → task hosts → routing and instances → event routing and runtime). Security, tenancy, data and recovery remain the team's job. AWS and Google Cloud services are only approximate neighbours (Cloud Run has a different contract from ECS + Fargate, and ECS + EC2 has no exact pair). — slides 57–59
27. **Static frontends sit outside the VPC.** HTML/CSS/JS can be served from a CDN close to users (AWS: CloudFront), while only API requests enter the VPC at the ALB. You can use a Git-connected hosting platform that builds and deploys for you, or assemble object storage plus edge delivery yourself. Either way you still set domains, cache rules and access. — slides 61–64
28. **Choosing where vector data lives means choosing who operates and recovers it.** ChromaDB on EC2 means you patch and back it up. PostgreSQL + pgvector as a managed service has the provider patching while you own schema and restore tests, and it holds vectors next to relational data. A dedicated vector search service follows its own contract, which you must verify and test. Managed PostgreSQL (RDS, Aurora, Cloud SQL, AlloyDB) still leaves network, access, backup/HA, schema, queries, migrations, connection pooling and restore tests to you. HA and recovery must be configured; they are off by default. — slides 65–68
29. **Authentication is not authorization.** The user signs in with an identity provider and receives a signed token. The backend checks its signature, issuer, audience and expiry. That proves *who* the user is. The application must still apply role and ownership rules to permit or reject each action. — slides 69–70
30. **The complete picture is a request path.** The browser downloads static files from a CDN and gets an identity token from the identity provider. It then sends API calls carrying the token to an ALB in the public subnet, which forwards to FastAPI tasks in the private app subnet and on to PostgreSQL + pgvector in the private data subnet. The slide shows one Availability Zone; production repeats the boundaries across zones. — slide 71
31. **One Next.js codebase can be deployed under three contracts.** A static export has no server at request time. A Node server/container runs the full framework. A platform adapter maps features onto a provider, within that provider's limits. If you need no request-time server, export statically; otherwise pick the least complex contract that works. — slides 72–73
32. **The decision method: trace the request, name the contract, choose the boundary, select a service, then measure and revise.** Draw frontend → backend → data → identity before naming any service. Classify the data (vector, relational, both). Data outlives compute. Match the stage (a prototype optimises for iteration, production for reliability, while security follows users and data at every stage). Add complexity only when measured needs justify it. — slides 75–81

## Diagrams

**The deck's visual vocabulary.** Most diagrams reuse one set of metaphors. A scene author can keep the mapping and redraw it in our own style:

| Picture on the slides | Stands for | First used |
|---|---|---|
| House with a name tag (e.g. "FastAPI (app) / Python 3.14") | a server / VM / service instance | 3 |
| Signpost on the house | its IP address(es) | 4, 12 |
| Door with a `:port` badge | a listening port (inbound) | 9 |
| Window with outgoing arrows | outbound connections from ephemeral ports | 9 |
| Smart lock (keypad / face scan) on the door | security group; later also the identity provider/token | 11, 69 |
| Road with lane markings, labelled with a CIDR | a subnet ("street") | 12 |
| Gated entrance + blue enclosure "CUSTOMER VPC 10.0.0.0/16" | the VPC ("gated community") | 15 |
| Router with a globe | Internet Gateway | 13 |
| Router with a "NAT" shield and up/down arrows | NAT Gateway | 14 |
| Warehouse full of shipping containers | container registry (ECR) | 17 |
| Single blue shipping container | a container image / container / Cloud Run service | 21, 41, 50 |
| Rack of servers with a load gauge | front door / proxy (Nginx or ALB) | 23 |
| Hotel with numbered rooms | Fargate capacity, one task per room | 38 |
| Man with a clipboard and a task list | a scheduler / control plane (ECS, EKS) | 38 |
| Cloud with a lightning bolt | a function (Lambda / Cloud Run functions) | 53 |
| Globe with "CDN" | content delivery network | 62 |
| Stacked cylinder | database | 28 |
| Safe | secret manager | 22 |
| Hooded figure "HACKER, on-path attacker" | eavesdropper on the public hop | 25 |

**Mechanism diagrams, slide by slide.**

- **Slide 3: local vs. deployed.** One house ("FastAPI (app), Python 3.14") on the left. Two bulleted columns compare Local Laptop and Deployed Service on four rows: lifetime, reachability, endpoint (`http://localhost:8000` vs. `https://app.example.com`), availability. A callout says deployment wraps the app in a network endpoint and an operating lifecycle. Purpose: the same app, but different reachability and lifetime.
- **Slide 4: two addresses on one house.** The FastAPI house has a two-armed signpost: a blue arm "Private IP: 10.0.2.5" and a green arm "Public IP: 34.120.45.67". Footer: private addresses are not routed publicly, and public ones still depend on routes and firewalls. Purpose: one machine can have both kinds of address.
- **Slide 5: CIDR bit layout.** The heading is `IP_ADDRESS / PREFIX_LENGTH`. Four octet boxes `10 · 0 · 1 · 5` sit above their binary forms (`00001010 00000000 00000001 00000101`), each labelled "8 bits", with "32 bits total" underneath. A small table lists prefix / fixed bits / varying bits / addresses for /32, /24, /16, /8, /0. A green note: /32 is one address, /0 is the whole internet. Purpose: a prefix length fixes the leading bits.
- **Slides 6–7: in-class question and answer.** Slide 6 is a multiple-choice card for `10.0.0.0/12` (A 256, B 4,096, C 1,048,576, D invalid). Slide 7 is a four-box arrow chain: "IPv4: 32 total bits" → "Prefix /12: 12 fixed bits" → "Remainder: 32 − 12 = 20 varying bits" → green "Answer C: 2²⁰ = 1,048,576 addresses". A rule banner sits underneath. Purpose: the worked method, ready to animate step by step.
- **Slide 8: address categories.** Three bullets (loopback `127.0.0.1`, bind-all `0.0.0.0`, public example `34.120.45.67`), then a 3-row table of RFC 1918 private ranges with their typical use: `10.0.0.0/8` cloud networks, `172.16.0.0/12` Docker bridge / enterprise, `192.168.0.0/16` home routers / small office.
- **Slide 9: the house with doors and windows.** The FastAPI house has its door labelled `:8000` (inbound listener). Two green arrows leave the window towards the cards "53421 → ChromaDB" and "52134 → OpenAI service" (outbound connections, OS-chosen source ports). A blue callout: direction is set by the initiator, and a stateful firewall lets replies back. A table maps Direction → Port → Configured by: inbound / configured listener or mapping / application or service; outbound / ephemeral source port / operating system; response / existing connection state / stateful firewall. Purpose: which side picks which port.
- **Slide 10: port-range number lines.** There are two horizontal bars from 0 to 65535. Top bar (IANA view): blue 0–1023 "well-known system services, 80, 443, 22, root usually required"; green 1024–49151 "IANA user ports, example application ports 8000, 5432, 6379, 3000"; red 49152–65535 "dynamic / private, OS assigns outbound source ports". Bottom bar refines the middle: green 1024–32767 user ports, then an **orange 32768–49151 "operating-system ephemeral range may overlap here"**, then red 49152–65535. A callout on the green segment says to configure an explicit application port and verify OS and runtime reservations. Purpose: why a fixed app port can collide with OS-chosen ports. (*Ours*: the Linux default ephemeral range is 32768–60999, which is the overlap the orange band warns about.)
- **Slide 11: security group as an equation.** PORT (a door `:8000`) **+** ALLOW RULE (smart lock + card "TCP, destination port 8000, allowed source: Nginx"; note "ALLOW rules only, no explicit DENY") **=** GUARDED PORT (the same door with the lock fitted; badge "MATCH: ALLOW | NO MATCH: BLOCK"). A grey strip below gives three defaults: INBOUND starts with no rules (add a matching allow), OUTBOUND starts allow-all (narrow it), STATEFUL means replies return automatically. Purpose: the port is where traffic enters, and the security group decides who may use it.
- **Slide 12: subnet as a street.** Three houses on one road labelled "PRIVATE SUBNET — 10.0.2.0/24 — 256 addresses": FastAPI (signpost 10.0.2.5, door :8000), ChromaDB (10.0.2.10, :8000), React/Vite (10.0.2.15, :5173). Footer analogy: the subnet is the street, the security group is the door lock. Note that FastAPI and ChromaDB both use port 8000 without clashing because their IPs differ.
- **Slide 13: public vs. private subnet.** There are two identical streets with the same three houses. Left: "PUBLIC SUBNET — 10.0.1.0/24" with an Internet-Gateway router icon and the note "direct route to an Internet Gateway". Right: "PRIVATE SUBNET — 10.0.2.0/24", "no direct route". Each street has a two-row route table: `10.0.0.0/16 → local route` in both, then `0.0.0.0/0 → Internet Gateway` (public) vs. `0.0.0.0/0 → NAT Gateway` (private). Footer: the public route is necessary but not sufficient. Purpose: the single route-table row that makes the difference.
- **Slide 14: NAT gateway path.** Left to right: the private-subnet street (`10.0.2.0/24`, three houses, label "Private Server") → arrow → NAT router on a short public-subnet road piece (`10.0.1.0/24`, label "NAT Gateway") → arrow → Internet Gateway router → "Internet". The private route table sits below, and a callout explains the translation and that NAT refuses unsolicited inbound connections. Purpose: one-way outbound access for private servers.
- **Slide 15: the VPC.** A blue enclosure with a gate icon, "CUSTOMER VPC 10.0.0.0/16". Inside, top: the public subnet road (`10.0.1.0/24`) with the NAT router on it. Below: the private subnet road (`10.0.2.0/24`) with FastAPI, ChromaDB and React/Vite. The Internet Gateway sits on the VPC's edge and points to "Internet". Callout: the /16 is divided into /24 subnets.
- **Slide 16: three-tier VPC.** Same enclosure with three roads: public (`10.0.1.0/24`, NAT only), private app (`10.0.2.0/24`, FastAPI + React/Vite), private data (`10.0.3.0/24`, ChromaDB). Purpose: the tier layout reused on every later slide.
- **Slide 17: registry handoff.** Top left: warehouse "Amazon Elastic Container Registry (ECR)". A box "Build and release pipeline, publishes the prepared image" points into it. A down-arrow "at deployment, workloads pull the image" leads into a VPC sketch (public subnet with NAT; FastAPI / ChromaDB / React/Vite on the private app subnet). Right side, three callouts: the pipeline packages, checks, scans and tags one image; the registry stores the approved image and deployments pull that exact version; keep the image in the workload's Region (replicate for multi-Region).
- **Slide 18: same container, different host.** A banner from REGISTRY: "Same approved image — myapp:v1.4 / Same FastAPI listener — 0.0.0.0:8000". Two panels below. LAPTOP (Docker host): `docker run -p 8080:8000 myapp:v1.4`, "LAPTOP NETWORK (HOST)", house with signpost `localhost:8080`, captioned "FastAPI container, published endpoint on the laptop". AMAZON EC2 ("cloud virtual machine on a remote Linux host"): "Docker maps VM :8000 to container :8000", then a VPC box with the FastAPI house, signpost `10.0.2.5:8000`, on the private app subnet; note that VPC routes and security rules govern access. Footer points ahead to the next slide. Purpose: the image is constant, and the host and its network change.
- **Slide 19: port publishing chain.** Inside a "LAPTOP NETWORK (HOST)" panel, three boxes joined by arrows: "Browser on the laptop, `localhost:8080`" → "Docker port publishing, laptop :8080 → container :8000 (forwards traffic into the container)" → a nested "CONTAINER NETWORK, separate from the laptop network" box holding the FastAPI house, "listens on 0.0.0.0:8000". Footer: endpoint and listener are configured independently, and their numbers needn't match.
- **Slide 20: two access paths to one workload.** Two rows end at the same "EC2 WORKLOAD" house. Row 1, ADMINISTRATIVE ACCESS: "Developer / operator" → SSH → "EC2 shell". Row 2, CLIENT ACCESS: "Internet client, api.example.com" → "PUBLIC HTTPS ENDPOINT :443 → target :8000" → "FastAPI listens on 0.0.0.0:8000 (application listener is unchanged)". Footer: admin access reaches the machine, client access reaches the service.
- **Slide 21: one image, two configurations.** One container icon "ONE IMMUTABLE IMAGE" branches into DEVELOPMENT and PRODUCTION panels. Each has a WORKLOAD house and a "RUNTIME VALUES" card (`APP_ENV`, `LOG_LEVEL`, `FEATURE_FLAG` with dev/debug/true vs. prod/info/false).
- **Slide 22: secret injection.** Safe "Secret manager" → green arrow "authorized delivery" → house labelled "workload identity" → green card "APPLICATION READS AT STARTUP `os.getenv("OPENAI_API_KEY")`". A red card lists where secrets must never go (source code, container images, Git), and a footer gives the least-privilege rule.
- **Slide 23: Nginx keeps FastAPI private.** VPC box. Browser "GET /predict" → `HTTPS :443` → Nginx/EC2 house (badge `:443`) on the public subnet road → green arrow "internal :8000" → FastAPI house (badge `:8000`) on the private app subnet road. A red callout on FastAPI: "No public IP / Only Nginx connects".
- **Slide 24: Nginx on EC2 vs. ALB.** Two panels with the same structure. Top half "TEAM OPERATES guest OS + Nginx, proxy instances + scaling" vs. "AWS OPERATES ALB nodes + replacement, service capacity + scaling". Bottom half "TEAM CONFIGURES THE ROUTE" in both, with an Nginx `location /api/` block vs. an ALB listener/path/target-group rule (see Commands). Footer: same route, and only proxy-host operations move. Purpose: what a managed load balancer does and does not take over.
- **Slides 25–26: HTTP vs. HTTPS (an animatable pair).** Same layout on both. Browser (`api.example.com`) → front door "Nginx / ALB" on the public subnet → HTTP → FastAPI on the private app subnet, all inside the VPC. A hacker below the browser has two red dashed arrows. One goes up to the browser→front-door link. On 25 it is labelled "READ / ALTER" with the body changing `{"image":"cat.jpg"}` → `{"image":"dog.jpg"}`; on 26 it reads only "CIPHERTEXT, TLS 1.3 record (hex) `17 03 03 00 2A 9F 6C …`". The other is "BYPASS ATTEMPT" towards the private subnet, ending in a red ✕ "NO PUBLIC ROUTE". On 26 the link is labelled HTTPS and the front door "TLS ends here", while the inner hop stays HTTP. Purpose: encryption protects the public hop, and routing protects the private tier.
- **Slide 27: DNS steps 1–5.** Left column: Browser (`api.example.com`) ↕ "Cloudflare resolver 1.1.1.1" ↕ ROUTE 53 box ("AWS authoritative DNS") with a record card `api.example.com / Type: A / Alias: Yes / Target: api-alb`. Arrows are numbered: 1 QUERY (browser → resolver), 2 QUERY AWS (resolver → Route 53), 3 ALB IP (back up), 4 ALB IP (to browser). Then a long arrow 5 HTTPS from the browser to "ALB • api-alb" in the VPC's public subnet, which forwards HTTP to FastAPI in the private app subnet.
- **Slide 28: three contracts.** Browser (`POST /predict`, `{"image":"cat.jpg"}`) → **1 HTTPS** → ALB (public subnet) → **2 HTTP** → FastAPI (private app subnet) → **3 SQL** (gold arrow, with an `INSERT INTO results …` statement) → Database cylinder (private data subnet). Purpose: name the protocol of each hop.
- **Slide 29: build once, run that image.** "SOURCE + DOCKERFILE" (`docker build -t myapp:v1.4 .`) → **1 BUILD + PUSH** → warehouse "ECR • myapp:v1.4" → **2 DEPLOY** (gold arrow down into the VPC, "pull + start myapp:v1.4") → FastAPI house tagged `myapp:v1.4` in the private app subnet. Separately: Browser `POST /predict` → **3 HTTPS REQUEST** → ALB → HTTP → the same FastAPI. Purpose: the build path and the request path meet at the same tagged image.
- **Slide 30: page load, then API call.** The slide is split by a dashed line. "LOAD THE PAGE": Browser → **1** `HTTPS GET /` `app.example.com` → FRONTEND box (HTML = page, CSS = style, JS = behavior) → **2** HTML + CSS + JavaScript returned. "USE THE PAGE": **3** "Choose cat.jpg" (the browser is now "frontend is running") → **4** `HTTPS POST /predict` to `api.example.com` with `{"image":"cat.jpg"}` → FastAPI house → **5** `{"label":"cat"}` back. Purpose: the API is called from the browser, not from the frontend host.
- **Slide 31: one web project tree.** Root `my-product/` (one repository) splits into `frontend/` and `backend/`. Frontend: "choose one frontend setup", either REACT + VITE (`App.jsx` or `App.tsx`; your code imports React; Vite = dev server + build tool) → `vite build` → `dist/` (HTML • CSS • JavaScript), OR NEXT.JS (`page.js` or `page.tsx`; a React component + routing + build + server options) → `next build / start` → "STATIC FILES or NEXT.JS SERVER". Backend: FASTAPI (`main.py`, `from fastapi import FastAPI`, Python web framework) → "python starts" → "FASTAPI API PROCESS, POST /predict → JSON".
- **Slide 32: two runtime layouts.** Banner "ONE PRODUCT • OFTEN ONE REPO • TWO DEPLOYMENTS". Panel A, React + Vite static frontend: Browser → `HTTPS GET /` `app.example.com` → "STATIC FILE HOST dist/"; Browser → `HTTPS POST /predict` `api.example.com` → FRONT DOOR (ALB or Nginx) → HTTP → FastAPI. Tag: "same browser • 2 hostnames • 2 deployments". Panel B, Next.js server + FastAPI: Browser → HTTPS `app.example.com` → FRONT DOOR, which forks: HTTP `GET /` → Next.js and HTTP `POST /predict` → FastAPI. Tag: "one hostname • path rules • 2 deployments".
- **Slide 35: one VM per service.** VPC with three tiers. Browser → HTTPS `app.example.com` → "Nginx / EC2, serves React/Vite, :443" (public) → HTTP `POST /predict` → "FastAPI / EC2" (private app) → query → "ChromaDB / EC2" (private data). Footer trade-off: scale or reboot each service alone, but patch and monitor three guest OSs.
- **Slide 36: prototype on one VM.** In the VPC, on the public subnet, one large box "ONE PUBLIC EC2 INSTANCE • guest OS + Docker" (with an "EC2 VM" house). Inside it: Nginx ("serves GET /, ONLY PUBLIC PORT :443") → HTTP `POST /predict` → FastAPI ("Docker network only, NO HOST PORT") → query → ChromaDB (same labels). Footer: one reboot stops all three, and scaling one service scales the whole VM. Purpose: contrast with 35.
- **Slide 37: instance contract.** "YOU REQUEST" card (2 vCPU + 4 GiB, Amazon Linux, 30 GiB EBS, private app subnet) → "REQUEST VM" → "AWS EC2 SERVICE (operates physical fleet + virtualization)" → "CREATES VM" → house "EC2 VM, guest OS + apps" on the private app subnet in the VPC. Footer: AWS repairs hardware and virtualization, the team patches guest OS and apps.
- **Slide 38: Fargate placement.** "YOU DEFINE: representative task request" card (`image: api:v1.4`, `cpu: 0.5 vCPU`, `memory: 1 GiB`, `network: private`, `role: api-role`) → SUBMIT → scheduler figure "ECS OR EKS schedules" → PLACE → a hotel "FARGATE CAPACITY" whose rooms are labelled TASK 1, TASK 2, TASK 3. Tag: "1 task / pod = 1 isolated room".
- **Slide 41: task and pod.** Two side-by-side panels, "ECS TASK" and "KUBERNETES POD", each holding two container icons. Captions: the task's containers move, restart and scale together, and the pod's containers share a lifecycle and a network namespace.
- **Slide 42: same wrapper, different capacity.** A top box "Task / Pod, workload wrapper" links via "capacity contract" to two boxes: a house "EC2 capacity, team patches and scales the VMs" and a hotel "Fargate capacity, AWS provisions isolated task capacity".
- **Slide 43: reconcile loop.** "TASK DEFINITION `api:v1.4`, DESIRED COUNT = 3" → scheduler figure "AWS-OPERATED ECS CONTROL PLANE" → three task boxes, each holding a container `api:v1.4`. Task 3 carries a red ✕ with the callout "ECS starts a replacement task". Purpose: desired vs. actual state, ideal for an animated failure and replacement.
- **Slide 44: what / how many / where.** Three panels. WHAT (warehouse icon): task definition, image `api:v1.4`, CPU + memory + ports. HOW MANY (scheduler): ECS service, desired count 3, maintains three tasks. WHERE (house + hotel): EC2 capacity / Fargate capacity, chosen by "LAUNCH TYPE / CAPACITY PROVIDER".
- **Slide 45: two kinds of scaling.** Left panel "WORKLOAD SCALING": desired tasks `3 → 6`, the controller changes the workload count. Right panel "CAPACITY SCALING": one house → arrow → three houses, "enough places for requested tasks". Footer: work stays pending when capacity lags.
- **Slides 46–47: control plane outside the VPC.** The scheduler figure floats above a VPC box (gate, "customer VPC 10.0.0.0/16"). On 46 ("AWS-operated ECS control plane"), the private workload subnet `10.0.2.0/24` holds a house tagged TASK (EC2 capacity) and a hotel tagged TASK (Fargate capacity), with "routing + security" written at the VPC side. On 47 ("AWS runs Kubernetes API servers + etcd"), the subnet holds three houses each labelled "node + pods", and a footer lists what the team still configures. Purpose: the managed brain sits outside, and your workloads, network and policy sit inside.
- **Slide 50: separate layers vs. Cloud Run.** Left panel "SEPARATE LAYERS": three icons, house = compute, clipboard man = scheduler, hotel = capacity, captioned "EC2 / ECS / Fargate". Right panel "CLOUD RUN SERVICE": one container icon. Google routes requests and starts/stops instances, and the team sets image, ingress, identity and scaling limits. Footer: data and external services are still separate.
- **Slide 52: scaling chain.** Four boxes with arrows: Signal (CPU use, concurrent requests or queue depth) → Policy (target, min and max workload count) → Desired count (more or fewer workloads) → Capacity (enough places to run). Footer: downstream limits still bound the result.
- **Slide 53: function shape.** A trigger box listing HTTP / Queue / Schedule → arrow → lightning-cloud labelled "handler" → arrow → green box "one focused result". Footer: longer or multi-step work belongs in a job or workflow.
- **Slide 55: concurrency models.** LAMBDA panel: two separate small boxes, each "one request at a time"; caption "overlap creates more busy environments". CLOUD RUN FUNCTIONS panel: one box "several requests may share one instance"; caption "configured concurrency changes instance count". Footer: concurrency changes active capacity and downstream pressure.
- **Slide 57: three runtime families.** Three cards: FUNCTION (lightning-cloud, "triggered, bounded work"), REQUEST-SERVING SERVICE (container; the provider runs routing and instance lifecycle, the team configures image and service policy), ORCHESTRATED (scheduler; the team configures tasks/pods, placement and network policy, and EC2 or Fargate decides host operations).
- **Slide 58: responsibility ladder.** Five icons left to right, each with a "provider:" line and a "team:" line. EC2 (house; AWS hardware + hypervisor / team guest OS + app). ECS/EKS + EC2 (house; AWS control plane / team nodes + workloads). Fargate (hotel; AWS control plane + task hosts / team task + network policy). Cloud Run (container; Google routing + instances / team service config + code). Lambda (lightning-cloud; AWS event routing + runtime / team function config + code). Header: each service moves a named layer. Footer: security, tenancy, data and recovery stay with you. Purpose: the central trade-off picture of section 2.
- **Slide 62: two browser paths.** "User browser" at the top with two arrows. A green arrow goes to a CDN globe: "PATH 1 — STATIC APPLICATION FILES", the browser downloads and caches HTML, CSS and JS; "cached copies near users"; "AWS example: CloudFront". A blue arrow goes into a VPC panel (gate → house on the private app subnet): "PATH 2 — REQUEST TO THE APPLICATION SERVICE".
- **Slide 64: frontend + VPC.** Browser at the top. A green arrow goes to a CDN globe *outside* the VPC, labelled "static path". A blue arrow goes into the VPC to the ALB on the public subnet ("accepts HTTPS requests"), which forwards to three hotels "FastAPI tasks ×3" on the private app subnet. Footer: static delivery stays outside the VPC, and application requests enter at the ALB.
- **Slide 65: three vector-data boundaries.** Three cards: CHROMADB ON EC2 (house; team patches VM + ChromaDB, designs backup + recovery), POSTGRESQL + PGVECTOR SERVICE (DB; provider patches DB infrastructure, team owns schema + restore testing), VECTOR SEARCH SERVICE (DB; provider operates the service, team owns index, access and recovery settings).
- **Slide 67: managed PostgreSQL.** House "application service" → green arrow "SQL over a private path" → DB "provider-operated PostgreSQL". A callout lists what the provider operates (hosts + storage, maintenance and patch workflow, backup and monitoring mechanisms). The footer lists what the team still sets and owns.
- **Slide 69: sign in, issue, verify.** Three cards with arrows: 1 User signs in (door; credentials go to the identity provider) → 2 Token issued (smart lock; signed identity claims) → 3 Backend verifies (server rack; signature, trusted issuer, intended audience, expiration). Red footer: a valid token proves identity, not permission.
- **Slide 71: complete picture.** Browser at the top. A green arrow goes to a CDN ("download static application files"). Red arrows go to and from a smart-lock "identity provider" ("sign in → receive identity token"). A blue arrow "request includes identity token" goes into the VPC, where the ALB ("HTTPS entry", public subnet `10.0.1.0/24`) → FastAPI tasks (two hotels, private app `10.0.2.0/24`) → PostgreSQL + pgvector (private data `10.0.3.0/24`). Footer: one Availability Zone shown. Purpose: the end-state reference architecture combining sections 1–3.
- **Slides 72–73: Next.js runtime choice.** Slide 72 has three cards: STATIC EXPORT (CDN; prebuilt files, no request-time server), NODE / CONTAINER (container; long-lived server, full framework runtime), PLATFORM ADAPTER (lightning-cloud; provider-mapped features, platform limits). Slide 73 is a decision tree: "Need request-time Next.js server behavior?" NO → static export (CDN); YES → "Which operating contract fits?" → Node/container or platform adapter. Footer: choose the least complex mode.
- **Slide 75: request-path skeleton.** Four cards chained by arrows, each with its key question: Frontend (static or server-rendered?) → Backend (HTTP, job, or trigger?) → Data (relational, vector, or both?) → Identity (who and which action?, outlined in red).
- **Slide 76: data classes.** Three DB cards: VECTOR (embeddings + similarity search), RELATIONAL (users + transactions + constraints), BOTH (often PostgreSQL + pgvector).
- **Slide 78: prototype vs. production.** Two panels. DEV / PROTOTYPE: browser → CDN "static", browser → one house "one service" → "data" cylinder; "optimize for iteration". PRODUCTION EXAMPLE: browser → CDN "static", browser → a VPC strip with gate, ALB on the public subnet → FastAPI hotel on private app → DB on private data; "optimize for reliability". Footer: identity follows users and data risk, not the environment label.
- **Slide 80: decision order.** Five numbered boxes chained by arrows: 1 Trace the request → 2 Name the contract → 3 Choose the boundary → 4 Select a service → 5 Measure and revise. Footer: add complexity only when measured needs justify it.

**Comparison tables (not mechanism drawings, but useful as on-screen tables):** 34 (EC2 vs. Fargate; ECS vs. Kubernetes), 39 and 48 (AWS operates vs. team configures, for Fargate and EKS), 40 (EC2 vs. Fargate on host access, OS patching, capacity, isolation, best fit), 49 (choose ECS when / choose EKS when), 51 (Cloud Run vs. ECS + Fargate on deploy unit, scaling, networking, what the team configures), 54 (functions: good fit vs. evaluate carefully), 56 (Lambda vs. Cloud Run functions on concurrency, duration, packaging, workload identity), 59 (AWS ↔ Google Cloud), 61 (names and their jobs), 63 (Git-connected hosting vs. object storage + edge), 66 (vector-data options on operations, data model, recovery), 68 (PostgreSQL services), 70 (identity provider handles vs. application enforces), 77 (dev/prototype vs. production), 79 (blank component/requirement/candidate/why worksheet).

## Terms the lecture uses

| Lecture term | Slides | Meaning in the lecture | Tutorial-side wording (*ours*) |
|---|---|---|---|
| "Deployed Service"; lifetime / reachability / endpoint / availability | 3 | the four properties that change when an app is deployed | tutorials say "deploy to a VM / Cloud Run / GKE" without naming these properties |
| Private IP / Public IP | 4, 8 | non-routed vs. internet-routable address | GCP tutorials say "internal IP" / "external IP" (L20 `http://<instance_ip>/`) |
| CIDR, prefix length, "fixed bits" / "varying bits" | 5–7 | address-block notation and how to count it | L22 uses the subnet `10.0.0.0/19` with no CIDR explanation |
| Loopback; "bind to every local interface" (`0.0.0.0`) | 8 | special addresses | L04/L18 guides explain `--host 0.0.0.0` for uvicorn inside containers |
| Configured listener; ephemeral source port; stateful firewall; initiator | 9 | who chooses which port | — |
| Well-known / IANA user ports / Dynamic-Private / OS ephemeral range | 10 | the port-number map | — |
| **Security group**; allow rule; guarded port; inbound / outbound / stateful | 11 | AWS instance-level allow-list | GCP tutorials use **VPC firewall rules** (L20 creates three, e.g. `allow-http`). Unlike a security group they can also deny, and they target instances by tag or service account |
| Subnet ("street"); public subnet; private subnet; route table; local route | 12–13 | address block + routing decides public vs. private | GCP subnets are regional and are not "public" or "private" in themselves; L22 makes nodes private by removing external IPs |
| Internet Gateway; NAT Gateway | 13–14 | default-route targets | L22: **Cloud Router + Cloud NAT** for private GKE nodes |
| Customer VPC ("gated community"); private app subnet; private data subnet | 15–16 | the tiered network | L20/L22 create a custom VPC (one subnet), with no app/data split |
| Container registry; ECR; "build and release pipeline"; "deployment handoff"; tag; Region | 17, 29 | where approved images wait for deployment | Docker Hub (L02, L20 manual part) and **Artifact Registry** (L14, L20, L22) |
| Docker host; port publishing; published endpoint; application listener; container network | 18–19 | `-p host:container` mechanics | L02/L04 guides say "port mapping" / `-p host:container` |
| Administrative access vs. client access | 20 | SSH to the machine vs. HTTPS to the service | L20 uses SSH via OS Login for admin, `http://<ip>/` for clients |
| Runtime values; immutable image | 21 | config injected at start | tutorials use `.env` files and `docker run -e` / env in compose |
| Secret manager; workload identity; "authorized delivery"; "Inject, Don't Bake" | 22 | secrets delivered at runtime to an identity | tutorials mount **service-account JSON key files** from a `secrets/` folder (L10, L18, L20). L22 switches to GKE **Workload Identity**, the lecture's model |
| Front door; Nginx; ALB; listener; target group (`fastapi-tg`) | 23–24, 32 | the public entry that forwards to private services | L20: **nginx reverse proxy** on port 80; L22: **NGINX Ingress Controller** behind a GCP network load balancer |
| On-path attacker; TLS; "TLS ends here"; ciphertext | 25–26 | why the public hop needs HTTPS | L20 and L22 end on plain HTTP (`http://<ip>/`, `http://<LB-IP>.sslip.io`); L22's HTTPS path exists in code but is switched off, and L23 switches it on (a Google-managed certificate) |
| Resolver; authoritative DNS; Route 53; `A` alias record | 27 | name → ALB IP | L22 uses `sslip.io` wildcard DNS instead of a real zone |
| "Three contracts" (HTTPS, HTTP, SQL) | 28 | one request, three protocols | — |
| Frontend / backend; React + Vite; Next.js; `dist/`; static files; app vs. api hostnames; path rules | 30–32, 61 | frontend build outputs and layouts | the cheese app uses a **Next.js** frontend (port 3000) and FastAPI `api-service` (port **9000**, not 8000). L20/L22 use one hostname with the path prefix `/api-service`, which is the lecture's layout B |
| Compute capacity vs. orchestration | 34, 50 | who supplies CPU vs. who places workloads | — |
| EC2; guest OS; "instance contract"; vCPU / GiB / EBS | 34–37 | AWS VM | GCP **Compute Engine** VM (`n2d-standard-2` in L20) |
| Fargate; "isolated room"; task request; role | 38–40 | serverless container capacity | no tutorial equivalent; L22 uses GKE Standard nodes |
| ECS task / Kubernetes pod ("scheduling wrapper", "workload wrapper") | 41–42 | the unit that gets scheduled | L22 uses Kubernetes Pods / Deployments |
| Task definition; ECS service; desired count; launch type / capacity provider | 43–44 | what / how many / where | Kubernetes Deployment `replicas` (L22) is the analogue |
| Workload scaling vs. capacity scaling; "pending" | 45 | count of tasks vs. room to run them | L22: Deployment replicas vs. node-pool autoscaling 1–2 nodes |
| Control plane; Kubernetes API servers; etcd; nodes; Fargate profiles; add-ons | 46–48 | what EKS manages vs. what you run | GKE (L22) |
| Cloud Run service; revisions; instances; ingress; concurrency; min/max | 50–51 | Google's request-serving runtime | L14 uses the same Cloud Run knobs (min/max instances, concurrency). L14 calls the warm-start trade-off **"cold start"**; the lecture says "warm reuse" (54) |
| Signal / policy / desired count / capacity; "downstream limits" | 52 | the scaling chain | — |
| Functions; handler; trigger (HTTP / Queue / Schedule); Lambda; **Cloud Run functions**; execution role vs. service account | 53–56 | event-triggered bounded work | the L14 tutorial says **"Cloud Function(s)"**, Google's earlier name for what the lecture calls Cloud Run functions |
| "Contract": instance / operating / runtime / deployment / data / capacity contract | 28, 37, 42, 49, 56, 58–59, 66, 72–73, 76, 79–80 | the lecture's central word: the split of duties a service or protocol defines | — |
| CDN; CloudFront; static path; Git-connected hosting platform; object storage + edge delivery; origin; invalidation | 61–64 | delivering static frontend files | the tutorials serve the frontend from a container (Next.js server or `http-server`); no CDN |
| PostgreSQL + pgvector; vector search service; RDS; Aurora; Cloud SQL; AlloyDB; HA; retention; pooling; migrations | 65–68 | managed data options | the tutorials run **ChromaDB** in a container (L05, L18, L20, L22) |
| Identity provider; token; claims; issuer; audience; expiration; MFA; authentication vs. authorization | 69–70 | user identity | the tutorials authenticate the *app* to Google with a service account (L10). The cheese app has no user sign-in |
| Availability Zone; Region | 17, 71, 77 | failure / placement domains | L22 uses a regional cluster with a zonal node pool |
| Static export; Node / container; platform adapter | 72–73 | Next.js deployment modes | L20/L22 run Next.js as a container |
| Dev / prototype vs. production | 77–78 | stage-dependent design | — |

## Commands and code on the slides

Short items, verbatim, with slide numbers. The slides contain no full programs.

- `http://localhost:8000` · `https://app.example.com`: slide 3
- `IP_ADDRESS / PREFIX_LENGTH`: slide 5
- `10.0.0.0/12`: slides 6–7
- `127.0.0.1` · `0.0.0.0` · `34.120.45.67`; private ranges `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`: slide 8
- `53421 → ChromaDB` · `52134 → OpenAI service`: slide 9
- `10.0.0.0/16` → `local route`; `0.0.0.0/0` → `Internet Gateway` / `NAT Gateway` (route-table rows): slides 13–14
- `docker run -p 8080:8000 myapp:v1.4`: slides 18, 19
- `localhost:8080` · `0.0.0.0:8000` · `10.0.2.5:8000`: slides 18–19
- `:443 → target :8000` · `api.example.com`: slide 20
- `APP_ENV=dev` · `LOG_LEVEL=debug` · `FEATURE_FLAG=true` (production: `APP_ENV=prod`, `LOG_LEVEL=info`, `FEATURE_FLAG=false`): slide 21
- `os.getenv("OPENAI_API_KEY")`: slide 22
- `GET /predict` · `HTTPS :443` · `internal :8000`: slide 23
- Nginx route: `location /api/ { proxy_pass http://10.0.2.5:8000; }`: slide 24
- ALB route: `listener :443` · `path /api/* -> fastapi-tg` · `fastapi-tg -> targets :8000`: slide 24
- `{"image":"cat.jpg"}` → `{"image":"dog.jpg"}`: slide 25
- `17 03 03 00 2A 9F 6C …` (TLS 1.3 record, hex): slide 26
- Route 53 record: `api.example.com` · `Type: A` · `Alias: Yes` · `Target: api-alb`; resolver `1.1.1.1`: slide 27
- `POST /predict` · `INSERT INTO results (label) VALUES ('cat')`: slide 28
- `docker build -t myapp:v1.4 .` (shown split over two lines with `\`) · `ECR • myapp:v1.4` · `pull + start myapp:v1.4`: slide 29
- `HTTPS GET /` · `HTTPS POST /predict` · `{"label":"cat"}`: slide 30
- `my-product/` · `frontend/` · `backend/` · `App.jsx` / `App.tsx` · `page.js` / `page.tsx` · `main.py` · `from fastapi import FastAPI` · `vite build` · `next build` / `start` · `dist/`: slide 31
- Fargate task request: `image: api:v1.4` · `cpu: 0.5 vCPU` · `memory: 1 GiB` · `network: private` · `role: api-role`: slide 38
- EC2 request: `2 vCPU + 4 GiB` · `Amazon Linux` · `30 GiB EBS` · `private app subnet`: slide 37
- `api:v1.4` · `DESIRED COUNT = 3`: slide 43; `image: api:v1.4` · `desired count: 3`: slide 44
- `3 → 6` (desired tasks): slide 45
- Example ports: `80, 443, 22` (well-known), `8000, 5432, 6379, 3000` (app ports): slide 10; `:5173` (React/Vite): slide 12

## What the lecture stresses

- **Reachability is never just "has a public IP".** Routes, the public-IP mapping and firewall rules all have to agree, and a public-subnet route is necessary but not sufficient. — slides 4, 8, 13
- **Pick an explicit application port** and check OS and runtime reservations, because the OS's ephemeral range can overlap user ports. — slide 10
- **Security groups only allow.** They start closed inbound and open outbound, so narrow outbound deliberately. Replies are stateful. — slide 11
- **NAT is outbound-only.** It never accepts unsolicited inbound connections. — slide 14
- **Tier the network:** a public entry tier and private app and data tiers. Internal services get no public IP, and only the proxy connects to FastAPI. — slides 16, 23, 35, 71
- **Build once and deploy that exact tag.** Scan and version the image, never rebuild at deploy time, and keep the registry in the workload's Region. — slides 17, 29
- **Host port and listener are independent** (`8080 → 8000`). Don't assume they match. — slide 19
- **Admin access ≠ client access.** SSH reaches the machine, HTTPS reaches the service. — slide 20
- **One immutable image per release, configured at startup.** — slide 21
- **Secrets: inject, don't bake.** Never put them in source code, images or Git, and grant only what each workload needs. — slide 22
- **A managed load balancer doesn't write your routes.** Only proxy-host operations move to AWS. — slide 24
- **Plain HTTP on the public path can be read and altered.** Use HTTPS; TLS terminates at the front door. — slides 25–26
- **Trade-off: one VM per service vs. all on one VM.** Separate VMs scale and reboot independently but mean more OSs to patch. One VM is simpler, but a reboot takes everything down and scaling is all-or-nothing. — slides 35–36
- **On EC2 you patch the guest OS.** Fargate removes host login and host patching but not your network, IAM, secrets, health, data or recovery work. — slides 37, 39–40
- **Scaling the workload is not scaling capacity.** Tasks wait as pending when capacity lags. — slide 45
- **"Default to ECS unless a concrete Kubernetes requirement exists."** — slide 49
- **Downstream limits still bound any autoscaling result.** — slide 52
- **Functions are for bounded work.** Long or multi-step work belongs in a job or workflow, and a warm instance is not durable state. Concurrency settings change both active capacity and pressure on downstream systems. — slides 53–55
- **Provider-operated infrastructure does not settle security, tenancy, data or recovery.** — slide 58
- **Cross-cloud mappings are approximate.** Cloud Run has a different contract, and ECS + EC2 has no exact pair, so compare requirements. — slide 59
- **Benchmark representative queries and failure recovery** before choosing a vector store. — slide 66
- **High availability and recovery are configurations, not defaults.** You own schema, migrations, pooling and restore tests even on a managed database. — slides 67–68
- **A valid token proves identity, not permission:** "Authenticated ≠ authorized." — slides 69–70
- **One Availability Zone is a simplification.** Production repeats the required boundaries across zones. — slide 71
- **One codebase does not define one deployment contract.** Choose the least complex mode that supports the required behaviour. — slides 72–73
- **Decide from boundaries and traffic, not service names.** Data outlives compute, security applies at every stage, identity follows users and data risk, and complexity should be added only when measured needs justify it. — slides 75–78, 80
- **Sketch one workload's request path before selecting services.** — slide 81
- *Ours, for guide authors:* the title says "Performance, Cost", but no slide gives a price, latency or throughput figure. Cost appears only as "fast iteration and low cost" for prototypes (slide 77), and performance only through scaling and concurrency (slides 45, 52, 55). The guide should add concrete numbers from the tutorials' own cost notes (L14, L20, L22) and label them as ours.

## Pointers

- **Tutorials:** none named on the slides. L16 has no tutorial repo in the course map.
- **Readings and standards named:** RFC 1918 (private IPv4 ranges), slide 8. IANA port registry ranges, slide 10.
- **In-class question:** CIDR address count for `10.0.0.0/12`, slide 6, answered on slide 7 (C, 1,048,576).
- **Exercise:** slide 79 is a blank worksheet (Component × Requirement × Candidate × "Why this contract?" for Frontend, Backend, Data, Identity). Slide 81 closes with the prompt to sketch one workload's request path before selecting services. These suit a study-guide exercise or a project milestone, but the slides attach no homework or milestone label to them.
- **Internal forward pointer:** slide 18's footer leads into slides 19–20 (trace the laptop port mapping, then add a public cloud endpoint).
- **Services named, for further reading:** AWS: ECR (17, 29), EC2 (18, 20, 23–24, 34–37, 40), ALB (24–29, 32, 64, 71), Route 53 (27), ECS (34, 38, 43–46, 49–51), Fargate (34, 38–40, 42, 44, 46, 51), EKS (34, 38, 47–49), Lambda (55–56, 58–59), CloudFront (61–62), RDS for PostgreSQL and Aurora PostgreSQL-compatible (68). Google Cloud: GKE (34, 59), Cloud Run (50–51, 58–59), Cloud Run functions (55–56, 59), Compute Engine (59), Cloud SQL for PostgreSQL and AlloyDB for PostgreSQL (68). Other: Cloudflare resolver `1.1.1.1` (27), pgvector (65–66, 71, 76).
- **No URLs or links** appear on the slides. `app.example.com` / `api.example.com` are placeholder hostnames.
- *Ours, cross-references within this series:* ports and `-p` → L02/L04 guides; service accounts and CORS → L10; Cloud Run, concurrency and cold starts → L14; FastAPI + Next.js cheese app → L18; single VM + nginx + firewall rules + Artifact Registry → L20; private GKE nodes, Cloud NAT, ingress and load balancer → L22. The section below maps every key idea to guide sections.

## Where this shows up in the tutorials

L16 has no tutorial and no video of its own, but nearly every slide names something that a deployment tutorial builds, on Google Cloud instead of AWS. The first table takes each key idea above and lists the study-guide sections where a tutorial puts it into practice. "[L20] §3.8" means section 3.8 of that lecture's study guide, "[L04] C7" concept C7 of the L04 guide, "§8 E5" exercise E5, "§6 item 12" gotcha 12, and "slide notes" the guide's *Lecture slides* section. Where the GCP service differs from the AWS one on the slide, the *Terms* table above has the details. The video folder for each guide is listed at the end.

### Key ideas → tutorials

| # | Key idea (slides) | Where the tutorials apply it |
|---|---|---|
| 1 | Deployment adds an endpoint and a lifecycle (3) | [L01] §3.1: a VM is rented, set up and deleted, so the app no longer lives and dies with your laptop. [L02] §4 Part C: the same image runs on a VM. The endpoints: a Cloud Run URL ([L14] At a glance), `http://<instance_ip>/` ([L20] §1), `http://<LB-IP>.sslip.io` ([L22] At a glance), and an HTTPS address only in [L23] §3.8. [L14] §3.1: on serverless the platform, not you, decides when an instance exists. |
| 2 | An address alone does not make a server reachable; loopback, bind-all, private ranges (4, 8) | Internal vs external IP: [L01] §3.1. [L20] §1: the VM has an external IP, yet the ports 3000, 8000 and 9000 it publishes stay unreachable because the firewall opens only 80, 443 and 22. [L22] §3.1: private nodes have no external IP at all. `0.0.0.0` vs `127.0.0.1` inside a container: [L10] §3.5, [L18] §3.3, [L14] §3.5, and [L04] §8 C2 (a "safer" `127.0.0.1` bind breaks the published port). Private ranges: Docker's `toynet` got `172.19.0.0/16` ([L04] C6), and [L22] §9 item 11 notes that the cluster's control-plane block `172.0.0.0/28` lies outside RFC 1918's `172.16.0.0/12`. |
| 3 | CIDR: count the varying bits (5–7) | Used, never explained. L22's subnet is `10.0.0.0/19` ([L22] §1, §4 Part C), so 13 varying bits and 8,192 addresses (*ours*), and the control plane gets a `/28` ([L22] §5 Excerpt 2). Docker's `toynet` bridge is a `/16` ([L04] C6). L20's VPC uses auto-mode subnets and writes no CIDR ([L20] §4 B10). |
| 4 | The initiator sets the direction; ephemeral source ports; stateful replies (9) | [L04] C7: the processor sees the source port the OS gave the gateway (captured 55620, then 55634). Outbound calls from the API to Vertex AI and Chroma: [L18] §3.5. Outbound-only Cloud NAT: [L22] §5 Excerpt 1. *Ours*: GCP firewall rules are stateful too, which is why L20 defines only inbound rules ([L20] §5 Excerpt 6) and the replies still get out. |
| 5 | Port ranges; choose an explicit application port (10) | Every service has a fixed port in the user range: API 9000, frontend 3000, Chroma 8000 ([L10] §3.5, [L18] §3.5). Cloud Run injects `PORT`, 8080 by default ([L14] §3.5, §8 E1). Host-port collisions ("port is already allocated"): [L04] C7. No guide discusses the OS's ephemeral range. |
| 6 | A security group is an allow-list on the door (11) | GCP's version is the VPC firewall rule: [L20] §5 Excerpt 6 (`allow-http`: tcp:80 from `0.0.0.0/0` to VMs tagged `http-server`), [L20] §4 A3 (the console's "Allow HTTP/HTTPS traffic" boxes add those tags), [L20] §1 (rules for 80, 443 and 22 only). [L20] §6 item 19: the SSH rule is open to `0.0.0.0/0`, the opposite of slide 11's "narrow it". GKE adds its own `k8s-…` rules for the load balancer ([L22] At a glance, teardown step 2). |
| 7 | A route table makes a subnet public or private (12–13) | GCP subnets are neither: a VM is public when it has an external IP and a firewall rule lets traffic in, as L20's does ([L20] §1). L22 makes the nodes private (`enable_private_nodes`, [L22] §3.1, §5 Excerpt 2) and reaches Google APIs through Private Google Access instead of a public route ([L22] §5 Excerpt 1). |
| 8 | NAT lets private servers call out but not be called (14) | [L22] §3.1 and §5 Excerpt 1: Cloud Router plus Cloud NAT let the private nodes pull images from Docker Hub and download from GitHub. Inbound traffic arrives only through the load balancer. |
| 9 | A VPC carved into tiers (15–16) | Both deployments create their own VPC: `cheese-app-network` with auto subnets ([L20] §4 B10) and `cheese-app-vpc` with one subnet ([L22] §1). Neither splits app and data into subnets. The tiers come from elsewhere: on the VM only nginx's ports pass the firewall ([L20] §1); on GKE only the ingress controller's Service has an external IP, while `frontend`, `api` and `vector-db` are ClusterIP ([L22] §3.3–3.4). |
| 10 | Build once; the registry is the deployment handoff (17, 29) | Push to a registry: [L02] §3.1 and §4 Part B (Docker Hub); [L14] §3.6 (Artifact Registry; a deploy pins the tag to a digest, §8 E8); [L20] §3.5 (timestamp tags handed to the VM stack through `StackReference`); [L23] §3.4 (a new tag rolls the Deployments) and §8 E8 (the same tag found in three places). Build once, test the same bits: [L21] §3.3 (one SHA-tagged image loaded by every job). Region: an Artifact Registry location is a region or a multi-region ([L14] §3.6); the cheese app pushes to the multi-region `us-docker.pkg.dev` ([L20] §1). No tutorial scans images. |
| 11 | The host port and the app's listen port are set separately (18–19) | `-p host:container`: [L04] C7 and §8 Q4 (`-p 127.0.0.1:8095:9100`), [L10] §3.5 (`3200→3000`), [L18] §3.5. Same image, different host: [L02] §4 Part C, plus the catch slide 18 leaves out, the CPU architecture ([L02] §3.7, §8 C4). On Cloud Run `-p` means nothing; the platform sets `PORT` ([L14] §3.5). L18 slide notes, idea 10: in production only the outer address and ports change. |
| 12 | Administrative access ≠ client access (20) | Admin: SSH from the browser ([L01] At a glance), SSH with OS Login as `sa_…` ([L20] §3.7), Pulumi driving Docker over SSH ([L20] §3.6). Client: the browser at `http://<ip>/` ([L20] §4 A9). On GKE the admin path is the Kubernetes API through `gke-gcloud-auth-plugin` and the client path is the load balancer ([L22] §3.7, §3.4). |
| 13 | One immutable image; configuration and secrets injected at startup (21–22) | Runtime values: `DEV=1` vs the production server in the same API image ([L18] §3.3); `ROOT_PATH` unset on the VM and `/api-service` on GKE ([L20] §3.8, [L22] §3.4). Counter-example: `NEXT_PUBLIC_BASE_API_URL` is compiled into the frontend image at build time ([L20] §3.8). Secrets mounted, not baked: [L10] §3.4, [L04] C4. How a key gets baked anyway: [L03] §3.8, [L02] §8 D3, and a W&B key in a job spec ([L13] §6 item 14, which suggests Secret Manager). CI: repository secrets ([L21] §3.8). No key file at all: [L14] §3.7, [L15] §3.8, and Workload Identity, the slide's "workload identity" ([L22] §3.7, §8 E7). Least privilege: [L10] §8 E6; [L20] §3.7 notes that the VM runs as the powerful `deployment` account. No tutorial uses Secret Manager. |
| 14 | A front door in the public tier keeps the app private (23–24) | nginx on port 80 in front of `api-service:9000` and `frontend:3000` ([L20] §3.8, §1); the NGINX Ingress controller behind a GCP network load balancer ([L22] §3.4); a Google HTTPS load balancer created from a `gce` Ingress ([L23] §3.8, §5 Excerpt 10). [L23] §3.8's "a doorman you hire" vs "Google's front desk" is slide 24's Nginx vs ALB: the provider takes over the proxy hosts, and you still write the path rules (`/api-service` → API, `/` → frontend). |
| 15 | HTTPS protects the public hop; TLS ends at the front door (25–26) | Only [L23] §3.8 and §5 Excerpt 10: a Google-managed certificate, an HTTP→HTTPS redirect, TLS ending at the load balancer and plain HTTP to the Pods behind it. L20 and L22 serve plain HTTP on port 80, although L20 opens 443 ([L20] §1). The app's own calls to Vertex AI always go over HTTPS with a bearer token ([L10] §3.2). |
| 16 | DNS comes before the connection (27) | [L22] §3.4 step 1: sslip.io answers with the IP written in the name. [L22] §8 E4: the raw IP gets an NGINX 404 because the Ingress matches the Host header. [L23] §3.8: the managed certificate is issued for `<ip>.sslip.io` or your domain. No tutorial creates a DNS zone. |
| 17 | One request crosses three contracts (28) | Trace exercises: [L20] §8 E5 (browser → firewall → nginx → Docker DNS → uvicorn) and [L22] §3.4 (DNS → load balancer → NGINX → Service → Pod). In the cheese app the data hop is Chroma's HTTP API on port 8000, not SQL ([L05] §3.8, [L18] §3.5, [L22] §3.3). |
| 18 | The browser loads the frontend, then calls the API itself; two runtime layouts (30–32) | The browser is the integrator: [L10] §3.6, [L18] §3.5, L18 slide notes idea 7 (two round trips). Static files vs a framework: [L18] §3.7 (`http-server` serves plain HTML/JS; the React app runs on Next.js). Layout B, one hostname with path rules: [L20] §3.8, [L22] §3.4 steps 3–6. In development the API and frontend sit on two origins, which is why CORS appears ([L18] §3.4). |
| 19 | Compute capacity and orchestration are separate layers; the task/pod wrapper (34, 38, 41–42) | [L22] §3.1 (a control plane plus node pools of VMs) and §3.2 (a Pod is the smallest schedulable unit: containers sharing one IP and volumes). |
| 20 | EC2 sells an instance contract; one VM per service vs all on one VM (35–37) | The contract: [L01] §3.1 (machine type, zone, boot image, network interface; you run `apt` yourself). Slide 36's prototype is L20: five containers on one `n2d-standard-2` VM behind nginx ([L20] §1). One reboot: [L20] §8 E7 and §6 item 12 (the frontend has no restart policy and stays down). L22 slide notes, idea 1: one VM is a single point of failure. One difference: L20 still publishes 3000, 8000 and 9000 on the host, where slide 36 publishes no host port; the firewall closes them instead ([L20] §1). |
| 21 | Fargate: capacity without a host to manage (38–40) | Not applied. L22 uses GKE Standard node pools, whose VMs you choose and pay for ([L22] §3.1). The nearest "no host to manage" runtimes in the course are Cloud Run ([L14] §3.1) and Vertex AI custom jobs, which create and delete a VM per job ([L13] §3.4). |
| 22 | ECS reconciles desired state; what / how many / where; workload vs capacity scaling (43–47) | Slide 43 on Kubernetes: delete a Pod and the ReplicaSet replaces it ([L22] §3.2, §8 E1). Slide 45: Pods stay Pending until the node autoscaler adds a node ([L22] §3.6, §8 E2). The control plane is Google's and is reached over HTTPS ([L22] §3.1). A laptop-sized reconciler: Docker Compose ([L04] C8). |
| 23 | Managed Kubernetes still leaves nodes, add-ons and policy to the team (47–49) | Everything `deploy_k8s` writes is slide 48's team column: the node pool and its autoscaler ([L22] §5 Excerpt 3), an add-on installed with Helm, the NGINX Ingress controller ([L22] §3.8), and IAM with Workload Identity, including a role the README forgets ([L22] §2, §3.7). The ECS-or-EKS choice itself has no GCP counterpart in the course. |
| 24 | Cloud Run merges the layers; scaling = signal → policy → desired count → capacity (50–52) | [L14] §3.1 (instances ≈ in-flight requests ÷ concurrency, clamped between min and max) and §3.2 (min instances vs cold starts). On GKE the chain is the HPA (CPU measured against the requests) plus the node autoscaler ([L22] §3.6, §8 E6); the repo itself has only the node autoscaler. A downstream limit: a ReadWriteOnce disk blocks a second API replica on another node ([L22] §3.5). |
| 25 | Functions suit triggered, short, bounded work (53–56) | [L14] §3.4 (a Cloud Run function is a container built for you), §3.8 (a Cloud Run job for run-to-completion work), §3.1 (instances are amnesiacs: warm is not durable), §3.2 (cold starts), §8 E6 (concurrency 80 vs 1 changes the instance count and the bill about 20×). |
| 26 | A managed service hands over one named layer, not the whole job (57–59) | The course climbs the same ladder on GCP; see the table after this one. |
| 27 | Static frontends sit outside the VPC, on a CDN (61–64) | Not applied. Every deployment serves the frontend from a container behind the same front door as the API ([L20] §1, [L22] §3.4). The simple frontend is plain static files that a CDN could serve ([L18] §3.7); the only CDN in the course is the one that page loads axios from. |
| 28 | Where vector data lives decides who operates and recovers it (65–68) | The course takes slide 65's first option, ChromaDB that you run: in Compose ([L05] §3.4, §3.8), on the VM with a 50 GB data disk ([L20] §1), on GKE with a PVC ([L22] §3.5). Running it yourself means recovery is your job, and [L20] §6 item 23 shows it silently failing: the data is not on the disk, and only the reloading loader hides that. No tutorial uses managed PostgreSQL or pgvector; L18's APIs deck lists a `postgres-db` service that v2 does not have (L18 slide notes). |
| 29 | Authentication is not authorization (69–70) | Applied to software, not to users: the cheese app has no sign-in. The split is the same. A key or token proves *who* (a missing key gives `DefaultCredentialsError` or a 401), IAM decides *what* (a 403): [L03] §3.6, [L04] C4, [L10] §3.2–3.3 and §8 E3. Cloud Run separates who may call the service from who the service is ([L14] §3.7, §8 E7). |
| 30 | The complete picture is a request path (71) | The course's end state is [L23] §3.8 on top of [L22] §1: a Google HTTPS load balancer, frontend and API Pods on private nodes, and ChromaDB on a persistent disk. Slide 71's one-zone caveat applies: L22's control plane is regional, but its node pool sits in one zone, `us-central1-a` ([L22] §3.1). |
| 31 | One Next.js codebase, three runtime contracts (72–73) | The course always takes the Node/container contract: a production Next.js server on port 3000 ([L20] §1; `node server.js` in the [L22] §1 diagram), and `next dev` in a container while developing ([L18] §3.8). Static export and platform adapters are not used. |
| 32 | The decision method: trace, contract, boundary, service, measure (75–81) | Not applied as a method: no tutorial asks for slide 79's worksheet. The course's own path is an instance of slides 77–78: one VM as the prototype ([L20]), then a cluster with private nodes ([L22]), then automation and HTTPS ([L23]). [L23] §7 maps which lecture built which box. |

29 of the 32 ideas are applied in at least one tutorial. Ideas 21 (Fargate), 27 (CDN) and 32 (the decision method as an exercise) are not.

### The slide 58 ladder on the course's runtimes

Slide 59 pairs the AWS services with their Google Cloud neighbours. This table goes one step further and names the tutorial that uses each rung.

| Rung (slide 58) | Provider operates (slide 58) | Where the course uses the GCP neighbour | What you still do there |
|---|---|---|---|
| EC2 | hardware, hypervisor | Compute Engine VM: [L01], [L02] §4 Part C, [L20] | the guest OS, Docker, the data disk, the containers, the firewall ([L20] §3.6, §4 B10) |
| ECS/EKS + EC2 | control plane | GKE Standard: [L22] | node pools and their autoscaler, the Ingress controller, Workload Identity, the PVCs ([L22] §3.1, §3.5, §3.7, §3.8) |
| Fargate | control plane, task hosts | none. Slide 59 pairs ECS + Fargate with Cloud Run, "different contract"; *ours*: GKE Autopilot would be the closer match | — |
| Cloud Run | routing, instances | Cloud Run service, path B of [L14] | the image, public access, the runtime service account, min and max instances, concurrency ([L14] §3.1–3.7) |
| Lambda | event routing, runtime | Cloud Run function, path A of [L14] | the source, the entry-point name, the dependency list ([L14] §3.4) |
| not on the slide | — | Vertex AI custom jobs ([L13] §3.4), endpoints ([L15] §3.2), Pipelines ([L15] §3.7), Gemini as an API ([L10] §3.8) | the job spec or pipeline code, the service accounts ([L13] §3.5, [L15] §3.8), undeploying and deleting endpoints ([L15] §3.2) |

### Slide 71's complete picture, box by box

| Box (slide 71) | Course counterpart |
|---|---|
| Browser | The same: it downloads the page and then calls the API itself ([L18] §3.5, [L22] §3.4 step 6) |
| CDN for static files | None. The frontend container serves the pages ([L20] §1, [L22] §1) |
| Identity provider and token | None for users. Software identities instead: service-account keys ([L10] §3.1–3.3) and Workload Identity ([L22] §3.7) |
| ALB, the HTTPS entry in the public subnet | nginx on the VM ([L20] §3.8), the NGINX Ingress controller behind a network load balancer ([L22] §3.4), a Google HTTPS load balancer ([L23] §3.8) |
| FastAPI tasks in the private app subnet | The `api-service` container on the VM ([L20] §1); the `api` Deployment on private nodes ([L22] §3.1–3.2) |
| PostgreSQL + pgvector in the private data subnet | ChromaDB as a container or Pod on a persistent disk ([L20] §1, [L22] §3.5) |
| Not drawn: the registry the tasks pull from (17) | Docker Hub ([L02] §4 Part B), Artifact Registry ([L14] §3.6, [L20] §3.5) |
| Not drawn: the NAT for outbound calls (14) | Cloud NAT ([L22] §5 Excerpt 1) |
| Not drawn: secret delivery (22) | `secrets/` mounts ([L10] §3.4), repository secrets ([L21] §3.8), Workload Identity ([L22] §3.7) |
| "One Availability Zone is shown" | A regional control plane with a one-zone node pool ([L22] §3.1) |

### What the title promises: the cost figures in the guides

The slides name cost only as "low cost" for a prototype (77). The guides give approximate list prices for each kind of contract the lecture compares. These are the guides' figures, not the slides'.

| Contract | Tutorial | What it costs, per the guide |
|---|---|---|
| Pay per call, nothing running | [L05], [L10] At a glance | only Vertex AI calls; under $2 for the whole L05 tutorial |
| Function or service that scales to zero | [L14] At a glance, §3.3 | a tiny fraction of Cloud Run's free tier with request-based billing and min instances 0. Min instances ≥ 1 or instance-based billing charge around the clock, and concurrency 1 instead of 80 needs about 20× the instances (§8 E6) |
| Run-to-completion job | [L13] At a glance | about $0.22/h for `n1-standard-4`, only while the job runs |
| Managed model endpoint | [L15] At a glance, [L23] At a glance | billed per node-hour, 24/7, even with no traffic; L23 estimates about $0.2/h per endpoint |
| One VM | [L20] At a glance | about $2/day for `n2d-standard-2`, plus about $4/month for two 50 GB disks |
| Managed Kubernetes | [L22] At a glance | about $5–8/day: the regional cluster fee, 1–2 nodes, the load balancer, Cloud NAT, disks |

### Questions to answer after the lecture

1. What two things does deploying add to an app that already runs on your laptop? Give the endpoint before and after. (3)
2. A VM has a public IP, but a request to its port 9000 times out. Name three things that can still block it. (4, 8, 11, 13) Compare with L20 §1, where 9000 is published on the host and still unreachable.
3. How many addresses do `10.0.0.0/12`, `10.0.2.0/24` and L22's `10.0.0.0/19` hold? Show the varying-bits method. (5–7)
4. FastAPI listens on `:8000` and calls ChromaDB. Who picks the source port of that call, and how does the reply get back in? Why pick an explicit application port, and where can it collide with the OS? (9–10)
5. A new security group has no rules. What can reach the instance, and what can it reach? Which route-table row makes a subnet public, and what does a NAT gateway refuse? (11, 13–14) Compare with L20's firewall rules and L22's Cloud NAT.
6. Draw the three-subnet VPC. In which tier do FastAPI, the frontend server, ChromaDB and the NAT gateway go? (15–16)
7. Why does a deployment pull a tagged image instead of rebuilding it, and what goes wrong with a reused tag such as `:latest`? (17, 29) Compare with L20 §3.5 and L23 §3.4.
8. In `docker run -p 8080:8000 myapp:v1.4`, which number does the browser use and which does FastAPI bind? Why must FastAPI listen on `0.0.0.0`? How do an operator and a user each reach the workload on EC2? (18–20)
9. Which values belong in the image and which are injected at startup? Where may a secret never go, and how does it reach the workload? (21–22) Compare with L22 §3.7.
10. What does an Nginx or ALB front door in the public subnet protect? What can an on-path attacker do to plain HTTP, what does HTTPS change, and why does the bypass attempt fail? (23–26)
11. List the DNS and connection steps from typing `api.example.com` to reaching FastAPI, and name the protocol on each hop of one `/predict` request. Which hop is not SQL in the cheese app? (27–28)
12. Who calls `POST /predict`, the frontend host or the browser? Sketch both runtime layouts and say which one L20 and L22 use. (30–32)
13. What do EC2 and Fargate provide, and what do ECS and Kubernetes provide? What is a task or a pod? (34, 41–42)
14. Compare one VM per service with all services on one VM. Who patches what on EC2? (35–37) Compare with L20 §8 E7.
15. What does AWS take over on Fargate, and what stays with the team? (38–40)
16. An ECS service has desired count 3 and one task fails. What happens? Then the desired count goes from 3 to 6 and no capacity is free. What happens now? (43–45)
17. When would you choose EKS over ECS, and what does EKS still leave to you? (47–49)
18. What does Cloud Run run for you that ECS + Fargate leaves to you? Follow the scaling chain from signal to capacity: what can still limit throughput? (50–52)
19. Which work fits a function and which does not? What happens to two overlapping requests on Lambda and on Cloud Run functions? (53–56)
20. For EC2, ECS/EKS + EC2, Fargate, Cloud Run and Lambda, name the layer the provider operates. What never moves to the provider, and why are cross-cloud pairs only approximate? (57–59)
21. Why can static frontend files stay outside the VPC, and which requests enter at the ALB? (61–64)
22. Compare ChromaDB on EC2, PostgreSQL + pgvector as a service, and a vector search service on operations, data model and recovery. What does managed PostgreSQL still leave to you, and is high availability on by default? (65–68) Compare with L20 §6 item 23.
23. A token's signature, issuer, audience and expiry all check out. Why may the request still be refused? (69–70) Compare with L10 §3.3.
24. Walk slide 71's picture from the browser to the data. What would change in production? (71)
25. Name the three ways to deploy one Next.js codebase and the question that picks between them. (72–73)
26. Fill in slide 79's worksheet for the cheese app as L22 and L23 deploy it. Which choices would you change for a prototype, and which for production? (75–80)

### Study guides and video folders

The guides are in this repository's `guides/`. The video folders are in the Explainer_Videos repository under `videos/`, and each one already holds the episode's `digest.md` and `SLIDES.md`. The course map in `README.md` shows which videos are out; when this was written, only L01's was.

| Lecture | Study guide | Video folder |
|---|---|---|
| L01 | [L01] `L01-vms-venvs.md` | `ac215-l01-vms-venvs` |
| L02 | [L02] `L02-containers-1.md` | `ac215-l02-containers-1` |
| L03 | [L03] `L03-containers-2-mega-pipeline.md` | `ac215-l03-mega-pipeline` |
| L04 | [L04] `L04-containers-2b-flexible-workflow-ports.md` | `ac215-l04-flexible-workflow-ports` |
| L05 | [L05] `L05-rag.md` | `ac215-l05-rag` |
| L10 | [L10] `L10-cloud-connect-cheese-app-v0.md` | `ac215-l10-cloud-connect` |
| L13 | [L13] `L13-training-workflows.md` | `ac215-l13-training-workflows` |
| L14 | [L14] `L14-serverless-deployment.md` | `ac215-l14-serverless-deployment` |
| L15 | [L15] `L15-vertex-ml-workflows.md` | `ac215-l15-vertex-ml-workflows` |
| L18 | [L18] `L18-apis-frontend.md` | `ac215-l18-apis-frontend` |
| L20 | [L20] `L20-deployment-pulumi.md` | `ac215-l20-deployment-pulumi` |
| L21 | [L21] `L21-cicd-github-actions.md` | `ac215-l21-cicd-github-actions` |
| L22 | [L22] `L22-kubernetes-cloud.md` | `ac215-l22-kubernetes-cloud` |
| L23 | [L23] `L23-final-cicd-deployment.md` | `ac215-l23-final-cicd` |

The guides for L06–L09 and L11 (agents, fine-tuning, testing, data labeling) touch none of this lecture's ideas and are not cited above.

[L01]: ../guides/L01-vms-venvs.md
[L02]: ../guides/L02-containers-1.md
[L03]: ../guides/L03-containers-2-mega-pipeline.md
[L04]: ../guides/L04-containers-2b-flexible-workflow-ports.md
[L05]: ../guides/L05-rag.md
[L10]: ../guides/L10-cloud-connect-cheese-app-v0.md
[L13]: ../guides/L13-training-workflows.md
[L14]: ../guides/L14-serverless-deployment.md
[L15]: ../guides/L15-vertex-ml-workflows.md
[L18]: ../guides/L18-apis-frontend.md
[L20]: ../guides/L20-deployment-pulumi.md
[L21]: ../guides/L21-cicd-github-actions.md
[L22]: ../guides/L22-kubernetes-cloud.md
[L23]: ../guides/L23-final-cicd-deployment.md
