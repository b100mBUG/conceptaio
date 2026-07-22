"""
models/lessons.py

The guided curriculum. Each challenge maps to a Lesson: an ordered list of
steps written the way a senior engineer would walk a junior through the
design: concept first, then *why*, then the edge cases people get bitten
by, then a concrete task on the canvas.

Steps can carry:
* `check(state) -> (done, feedback)`: evaluated live against the canvas so
  the guide can confirm "yes, that's right" and unlock Next.
* `autobuild(state)`: a "build it for me" action so learners can watch a
  reference design appear, run it, and study why it behaves the way it does.

This module is pure Python + AppState; no Rio imports.
"""

from __future__ import annotations

import typing as t
from dataclasses import dataclass, field

from models.node import NodeType

if t.TYPE_CHECKING:
    from app_state import AppState


# --------------------------------------------------------------------- checks
def _nodes_of(state: "AppState", node_type: NodeType) -> list:
    return [n for n in state.nodes if n.node_type == node_type]


def _has(state: "AppState", node_type: NodeType) -> bool:
    return bool(_nodes_of(state, node_type))


def _edge_between_types(
    state: "AppState", src: NodeType, dst: NodeType
) -> bool:
    types = {n.node_id: n.node_type for n in state.nodes}
    return any(
        types.get(e.source_id) == src and types.get(e.target_id) == dst
        for e in state.edges
    )


def _total_capacity(state: "AppState", node_type: NodeType) -> float:
    return sum(n.effective_capacity_qps for n in _nodes_of(state, node_type))


# ------------------------------------------------------------------ dataclass
@dataclass
class LessonStep:
    title: str
    # Main teaching text, markdown. The "here's the concept and why" part.
    body_md: str
    # Concrete instruction for the canvas. Empty = read-only step.
    task_md: str = ""
    # "Senior dev note": the edge cases and war stories.
    note_md: str = ""
    # Live check against the canvas. None = step is informational.
    check: t.Optional[t.Callable[["AppState"], tuple[bool, str]]] = None
    # Optional one-click reference build.
    autobuild: t.Optional[t.Callable[["AppState"], None]] = None
    autobuild_label: str = "Build this for me"


@dataclass
class Lesson:
    challenge_title: str
    intro: str
    steps: list[LessonStep] = field(default_factory=list)


# ----------------------------------------------------------------- autobuilds
def _build_naive_shortener(state: "AppState") -> None:
    state.clear_canvas()
    c = state.spawn_node(NodeType.CLIENT)
    a = state.spawn_node(NodeType.APP_SERVER)
    d = state.spawn_node(NodeType.DATABASE)
    c.x, c.y = 6, 26
    a.x, a.y = 40, 26
    d.x, d.y = 74, 26
    state.add_edge(c.node_id, a.node_id)
    state.add_edge(a.node_id, d.node_id)
    state.selected_node_id = None


def _build_scaled_shortener(state: "AppState") -> None:
    state.clear_canvas()
    c = state.spawn_node(NodeType.CLIENT)
    lb = state.spawn_node(NodeType.LOAD_BALANCER)
    a1 = state.spawn_node(NodeType.APP_SERVER)
    a2 = state.spawn_node(NodeType.APP_SERVER)
    a3 = state.spawn_node(NodeType.APP_SERVER)
    d = state.spawn_node(NodeType.DATABASE)
    c.x, c.y = 4, 30
    lb.x, lb.y = 26, 30
    a1.x, a1.y = 50, 12
    a2.x, a2.y = 50, 30
    a3.x, a3.y = 50, 48
    d.x, d.y = 82, 30
    for a in (a1, a2, a3):
        state.add_edge(lb.node_id, a.node_id)
        state.add_edge(a.node_id, d.node_id)
    state.add_edge(c.node_id, lb.node_id)
    state.selected_node_id = None


def _build_cached_shortener(state: "AppState") -> None:
    _build_scaled_shortener(state)
    apps = _nodes_of(state, NodeType.APP_SERVER)
    db = _nodes_of(state, NodeType.DATABASE)[0]
    cache = state.spawn_node(NodeType.CACHE)
    cache.x, cache.y = 68, 8
    cache.params.cache_hit_pct = 90
    # Reads go app -> cache -> db (misses only).
    state.edges = [
        e
        for e in state.edges
        if not (
            e.target_id == db.node_id
            and e.source_id in {a.node_id for a in apps}
        )
    ]
    for a in apps:
        state.add_edge(a.node_id, cache.node_id)
    state.add_edge(cache.node_id, db.node_id)
    state.selected_node_id = None


def _build_rate_limiter(state: "AppState") -> None:
    state.clear_canvas()
    c = state.spawn_node(NodeType.CLIENT)
    lb = state.spawn_node(NodeType.LOAD_BALANCER)
    rl = state.spawn_node(NodeType.CACHE)  # counter store
    a1 = state.spawn_node(NodeType.APP_SERVER)
    a2 = state.spawn_node(NodeType.APP_SERVER)
    rl.title = "Rate-Limit Store"
    rl.params.cache_hit_pct = 0  # counters always pass through
    c.x, c.y = 4, 28
    lb.x, lb.y = 28, 28
    rl.x, rl.y = 52, 8
    a1.x, a1.y = 52, 28
    a2.x, a2.y = 52, 46
    state.add_edge(c.node_id, lb.node_id)
    state.add_edge(lb.node_id, a1.node_id)
    state.add_edge(lb.node_id, a2.node_id)
    state.selected_node_id = None


# ------------------------------------------------------------------- lessons
_URL_SHORTENER = Lesson(
    challenge_title="Design a URL Shortener",
    intro=(
        "The classic first system-design problem, small enough to hold in "
        "your head, rich enough to teach scaling, caching and failure "
        "thinking."
    ),
    steps=[
        LessonStep(
            title="Understand the problem before touching the canvas",
            body_md=(
                "A URL shortener does two things:\n\n"
                "1. **Write**: take a long URL, return a short code.\n"
                "2. **Read**: take a short code, redirect to the long URL.\n\n"
                "The single most important observation: reads massively "
                "outnumber writes, often **100:1 or more**. A link is created "
                "once and clicked thousands of times. Our target here is "
                "**5,000 QPS**, nearly all of it reads.\n\n"
                "Everything you build should be shaped by that ratio. When a "
                "senior engineer says *'know your read/write ratio'*, this is "
                "why: it decides where caches help, where databases hurt, and "
                "what you optimize first."
            ),
            note_md=(
                "In a real interview, say the ratio out loud and derive the "
                "numbers: 5,000 QPS reads ≈ 432M redirects/day. Numbers earn "
                "trust; vibes don't."
            ),
        ),
        LessonStep(
            title="Build the naive version, on purpose",
            body_md=(
                "Every good design starts embarrassingly simple: "
                "**Client → App Server → Database**. That's it.\n\n"
                "Why start naive? Because you can't reason about *why* a "
                "component earns its place until you've seen the design fail "
                "without it. Adding a cache 'because interviews' is cargo "
                "culting; adding it because you watched the database melt is "
                "engineering."
            ),
            task_md=(
                "Add a **Client**, an **App Server** and a **Database**, then "
                "use **Link Nodes** to wire Client → App Server → Database."
            ),
            check=lambda s: (
                _has(s, NodeType.CLIENT)
                and _has(s, NodeType.APP_SERVER)
                and _has(s, NodeType.DATABASE)
                and _edge_between_types(s, NodeType.CLIENT, NodeType.APP_SERVER)
                and _edge_between_types(s, NodeType.APP_SERVER, NodeType.DATABASE),
                "Naive chain wired up: Client → App → DB.",
            ),
            autobuild=_build_naive_shortener,
        ),
        LessonStep(
            title="Now break it: run the simulation",
            body_md=(
                "Hit **Run Simulation** with the QPS at 5,000 and watch the "
                "numbers.\n\n"
                "The app server's default capacity is ~2,000 QPS per replica, "
                "so it gets buried: it can only serve 2,000 of the 5,000 "
                "requests hitting it. The other **3,000 QPS are dropped**, "
                "real users staring at spinners and error pages.\n\n"
                "This is the core loop of system design: *propose → load-test "
                "→ read the failure → fix the actual bottleneck*. Not "
                "guessing. Measuring."
            ),
            task_md="Press **Run Simulation** and read the failure in the metrics HUD and the Tech Lead panel.",
            check=lambda s: (
                s.last_result is not None,
                "You ran it and saw where it breaks. That's the habit.",
            ),
            note_md=(
                "Notice latency too: a node near 100% utilization doesn't "
                "just drop traffic, its latency explodes. Queueing theory in "
                "one sentence: **the last 10% of capacity costs you most of "
                "your latency budget.**"
            ),
        ),
        LessonStep(
            title="Scale out, not up: load balancer + replicas",
            body_md=(
                "You could buy a bigger server (*scale up*), but it's a dead "
                "end: prices grow faster than capacity, and one machine is "
                "still one failure away from an outage.\n\n"
                "Instead we *scale out*: several identical app servers behind "
                "a **load balancer** that splits traffic between them. Three "
                "servers × 2,000 QPS = 6,000 QPS of headroom, above our "
                "5,000 target.\n\n"
                "This only works because the app tier is **stateless**: any "
                "server can answer any request. Keep session state out of "
                "app servers and horizontal scaling stays this easy."
            ),
            task_md=(
                "Add a **Load Balancer** between Client and the app tier, and "
                "get total app-server capacity to **5,000+ QPS** (add servers "
                "or raise replica count in the Inspector). Re-run the sim."
            ),
            check=lambda s: (
                _has(s, NodeType.LOAD_BALANCER)
                and _edge_between_types(s, NodeType.LOAD_BALANCER, NodeType.APP_SERVER)
                and _total_capacity(s, NodeType.APP_SERVER) >= 5000,
                "App tier now has headroom behind a load balancer.",
            ),
            autobuild=_build_scaled_shortener,
            note_md=(
                "Edge cases seniors ask about: what if the LB itself dies? "
                "(Real systems run redundant LBs with health checks.) What "
                "about *sticky sessions*? If servers hold user state, the LB "
                "must pin users to servers, and your ability to scale just "
                "got worse. Stateless wins."
            ),
        ),
        LessonStep(
            title="Protect the database with a cache",
            body_md=(
                "Re-run after scaling and look downstream: now the **database** "
                "is the one drowning. Every redirect still costs a DB read.\n\n"
                "But short-link traffic is brutally skewed: a tiny fraction of "
                "links get almost all the clicks (the 80/20 rule, often more "
                "like 95/5). That's the perfect cache workload.\n\n"
                "Put a **cache** between app servers and the database. At a "
                "90% hit ratio, only 1 in 10 reads ever reaches the DB. You "
                "just multiplied your database's effective capacity by 10 "
                "without touching it."
            ),
            task_md=(
                "Add a **Cache**, route App Servers → Cache → Database, set "
                "its hit ratio (Inspector slider), and re-run. Watch the DB's "
                "incoming QPS collapse."
            ),
            check=lambda s: (
                _has(s, NodeType.CACHE)
                and _edge_between_types(s, NodeType.APP_SERVER, NodeType.CACHE)
                and _edge_between_types(s, NodeType.CACHE, NodeType.DATABASE),
                "Cache is on the read path. The DB only sees misses now.",
            ),
            autobuild=_build_cached_shortener,
            note_md=(
                "The classic traps: **cache invalidation** (what happens when "
                "a URL is updated or deleted?), **thundering herd** (a hot key "
                "expires and 10,000 requests stampede the DB at once. Fix "
                "with request coalescing or staggered TTLs), and **cold "
                "starts** (a freshly rebooted cache hits 0%, and your DB gets "
                "the full load, so size it to survive that, or warm the cache)."
            ),
        ),
        LessonStep(
            title="Hunt the single points of failure",
            body_md=(
                "Your design now *performs*. But performance and "
                "**reliability** are different properties.\n\n"
                "Ask about each node: *if this exact box died right now, what "
                "do users see?* A single-replica database means every request "
                "fails until someone restores it. A single cache means a cold "
                "stampede onto the DB.\n\n"
                "The fix is replication: run ≥2 replicas of anything stateful "
                "on the request path. The simulator flags single-replica "
                "stateful nodes as **SPOFs** after every run."
            ),
            task_md=(
                "Use the Inspector to give the Database and Cache **replica "
                "count ≥ 2**, re-run, and confirm the Tech Lead stops "
                "flagging SPOFs."
            ),
            check=lambda s: (
                all(
                    n.params.replica_count >= 2
                    for n in s.nodes
                    if n.node_type in (NodeType.DATABASE, NodeType.CACHE)
                )
                and _has(s, NodeType.DATABASE),
                "Stateful tiers are replicated. No single box takes you down.",
            ),
            note_md=(
                "Replication has its own edge cases: **replication lag** "
                "(a read replica may serve a stale URL for a few hundred ms, "
                "fine for redirects, fatal for bank balances) and **failover "
                "time** (promotion isn't instant; who serves writes during "
                "those 30 seconds?). Every nine of availability you promise "
                "makes these questions sharper."
            ),
        ),
        LessonStep(
            title="Do it yourself: survive 2× traffic",
            body_md=(
                "Training wheels off. A marketing campaign just doubled your "
                "traffic to **10,000 QPS**.\n\n"
                "Find the next bottleneck yourself: raise the QPS, run, read "
                "which node saturates first, fix *that* node, repeat. This "
                "loop, not any particular diagram, is the actual skill of "
                "system design.\n\n"
                "Target: **< 5% failure rate at 10,000 QPS.**"
            ),
            task_md=(
                "Set Client QPS to **10,000+**, iterate until failures are "
                "under 5%. The guide will confirm when you're there."
            ),
            check=lambda s: (
                s.client_qps >= 10000
                and s.last_result is not None
                and s.last_result.failure_rate_pct < 5.0,
                "Under 5% failures at double load. You scaled it yourself.",
            ),
            note_md=(
                "When you're done, try to *break* it in new ways: set the "
                "cache hit ratio to 30% (cold cache), or delete the LB. "
                "Reading failures is a skill you build by causing them "
                "somewhere safe."
            ),
        ),
    ],
)

_RATE_LIMITER = Lesson(
    challenge_title="Design a Rate Limiter",
    intro=(
        "Rate limiting is the art of saying 'no' cheaply, so the rest of "
        "your system can keep saying 'yes'."
    ),
    steps=[
        LessonStep(
            title="What a rate limiter actually protects",
            body_md=(
                "A rate limiter caps how many requests a client may make per "
                "time window (e.g. 100 req/min per API key). It exists to "
                "protect **your capacity** from abusive, buggy or just "
                "over-enthusiastic clients.\n\n"
                "The golden rule: **reject early and cheaply**. Every request "
                "you're going to refuse should burn as little of your system "
                "as possible. Ideally it dies at the edge, before touching "
                "an app server, let alone a database.\n\n"
                "Target load: **10,000 QPS**, some of which is traffic you "
                "*want* to drop."
            ),
            note_md=(
                "Common algorithms: **token bucket** (allows bursts, most "
                "popular), **sliding window log** (precise, memory-hungry), "
                "**fixed window** (cheap, but lets 2× the limit through at "
                "window borders, a classic edge case interviewers poke at)."
            ),
        ),
        LessonStep(
            title="Place the limiter at the edge",
            body_md=(
                "Build: **Client → Load Balancer → App Servers**, with a "
                "**Cache** node attached as the rate-limit *counter store*, "
                "in real life this is Redis holding per-key counters.\n\n"
                "Why a shared store at all? Because you have several app "
                "servers. If each one counts locally, a client with a "
                "100/min limit gets 100 × (number of servers). Counting must "
                "be **centralized (or at least shared)** to be correct."
            ),
            task_md=(
                "Build Client → Load Balancer → 2+ App Servers, and add a "
                "Cache node (rename it 'Rate-Limit Store' in the Inspector "
                "if you like)."
            ),
            check=lambda s: (
                _has(s, NodeType.CLIENT)
                and _has(s, NodeType.LOAD_BALANCER)
                and len(_nodes_of(s, NodeType.APP_SERVER)) >= 2
                and _has(s, NodeType.CACHE),
                "Edge tier plus a shared counter store. Correct shape.",
            ),
            autobuild=_build_rate_limiter,
            note_md=(
                "Edge case: the counter store adds latency to *every* "
                "request. Real systems batch counter updates or keep "
                "slightly-stale local counters and sync, trading a little "
                "accuracy for a lot of speed. 'Exactly correct' rate "
                "limiting is rarely worth its cost."
            ),
        ),
        LessonStep(
            title="Watch it fail without enough headroom",
            body_md=(
                "Run 10,000 QPS at your current design. If your app tier "
                "capacity is below the load, the sim drops requests, but "
                "notice *where*: at the app servers, **after** the load "
                "balancer already spent work routing them.\n\n"
                "That's what life without rate limiting looks like: overload "
                "hits your most expensive tier. A limiter converts that "
                "uncontrolled failure into controlled, cheap rejections at "
                "the edge, and your paying users keep getting served."
            ),
            task_md="Run the simulation at 10,000 QPS and study where the drops happen.",
            check=lambda s: (
                s.last_result is not None,
                "Seen. Uncontrolled overload fails in the worst place.",
            ),
        ),
        LessonStep(
            title="Give the surviving traffic headroom",
            body_md=(
                "Suppose the limiter rejects the worst 30% of traffic. The "
                "remaining ~7,000 QPS is legitimate and **must not fail**, "
                "otherwise the limiter just moved the outage.\n\n"
                "Scale the app tier for the *legitimate* load with margin "
                "(rule of thumb: run tiers at ≤70% utilization so spikes and "
                "failures don't instantly tip you over)."
            ),
            task_md=(
                "Get total App Server capacity to **10,000+ QPS** (replicas "
                "or more servers), re-run, and get failures to 0%."
            ),
            check=lambda s: (
                _total_capacity(s, NodeType.APP_SERVER) >= 10000
                and s.last_result is not None
                and s.last_result.failure_rate_pct == 0,
                "Zero drops with headroom to spare.",
            ),
            note_md=(
                "Return **429 Too Many Requests** with a `Retry-After` "
                "header. Well-behaved clients back off; that header is your "
                "limiter recruiting the clients into load management."
            ),
        ),
        LessonStep(
            title="Do it yourself: the counter store dies",
            body_md=(
                "Failure drill: your rate-limit store just went down. Two "
                "choices:\n\n"
                "* **Fail open**: stop limiting, let everything through. "
                "Risk: the flood you were blocking hits your backend.\n"
                "* **Fail closed**: reject everything. Risk: you just took "
                "yourself down more thoroughly than any attacker.\n\n"
                "Most APIs fail open *and* make the store redundant so the "
                "question rarely gets asked. Make your store survive: "
                "replicate it."
            ),
            task_md=(
                "Set the counter-store Cache to **replica count ≥ 2** and "
                "re-run cleanly."
            ),
            check=lambda s: (
                all(
                    n.params.replica_count >= 2
                    for n in _nodes_of(s, NodeType.CACHE)
                )
                and _has(s, NodeType.CACHE),
                "Redundant counter store: the fail-open/closed dilemma "
                "stays hypothetical.",
            ),
        ),
    ],
)

_NEWS_FEED = Lesson(
    challenge_title="Design a News Feed",
    intro=(
        "The feed problem is really one question wearing a trench coat: do "
        "you do the work on write, or on read?"
    ),
    steps=[
        LessonStep(
            title="Fan-out: the one decision that shapes everything",
            body_md=(
                "When someone posts, their followers must eventually see it. "
                "Two strategies:\n\n"
                "* **Fan-out on write** (push): at post time, write the post "
                "into every follower's precomputed feed. Reads are then dirt "
                "cheap: one lookup.\n"
                "* **Fan-out on read** (pull): store the post once; when a "
                "user opens the app, gather posts from everyone they follow "
                "and merge.\n\n"
                "At **20,000 QPS of reads**, precomputing wins for almost "
                "everyone: you pay once per post instead of on every single "
                "read."
            ),
            note_md=(
                "The celebrity edge case: one post by an account with 100M "
                "followers = 100M feed writes. Real systems go **hybrid**: "
                "push for normal users, pull-and-merge for celebrity "
                "content at read time. Remember this one. It's a famous "
                "interview follow-up."
            ),
        ),
        LessonStep(
            title="Build the read path first",
            body_md=(
                "Reads dominate, so design the read path first and make it "
                "boring: **Client → LB → App Servers → Cache → Database**.\n\n"
                "The cache holds rendered feed pages / recent timelines. Feed "
                "traffic is highly skewed toward active users and fresh "
                "content, so hit ratios of 90%+ are realistic."
            ),
            task_md=(
                "Build the full read chain: Client → Load Balancer → App "
                "Server(s) → Cache → Database. Then set QPS to 20,000 and "
                "run."
            ),
            check=lambda s: (
                _edge_between_types(s, NodeType.CLIENT, NodeType.LOAD_BALANCER)
                and _edge_between_types(s, NodeType.LOAD_BALANCER, NodeType.APP_SERVER)
                and _edge_between_types(s, NodeType.APP_SERVER, NodeType.CACHE)
                and _edge_between_types(s, NodeType.CACHE, NodeType.DATABASE),
                "Read path assembled, cache-first.",
            ),
        ),
        LessonStep(
            title="Absorb the write burst with a queue",
            body_md=(
                "Now the write path. Fan-out on write means one post can "
                "trigger thousands of feed insertions, and you do *not* want to "
                "do that synchronously while the poster waits.\n\n"
                "Put a **Queue** between accepting the post and doing the "
                "fan-out. The app server enqueues one message ('user X "
                "posted P') and returns instantly; workers drain the queue "
                "and write followers' feeds at their own pace.\n\n"
                "Queues **decouple** producer speed from consumer speed. "
                "That's their whole job."
            ),
            task_md=(
                "Add a **Queue** fed by an App Server, draining into the "
                "Database (App → Queue → Database)."
            ),
            check=lambda s: (
                _has(s, NodeType.QUEUE)
                and _edge_between_types(s, NodeType.APP_SERVER, NodeType.QUEUE)
                and _edge_between_types(s, NodeType.QUEUE, NodeType.DATABASE),
                "Writes are now asynchronous. Posters never wait on fan-out.",
            ),
            note_md=(
                "Queue edge cases: **backlog growth** (consumers slower than "
                "producers = ever-growing lag; alert on queue depth), "
                "**at-least-once delivery** (workers may see a message "
                "twice, so feed writes must be idempotent), and **ordering** "
                "(most queues only guarantee order per partition)."
            ),
        ),
        LessonStep(
            title="Do it yourself: hold 20k QPS healthy",
            body_md=(
                "Make the whole thing hold: **< 5% failures at 20,000 QPS**, "
                "no SPOFs on stateful tiers.\n\n"
                "Expect to iterate: scale the app tier, push the cache hit "
                "ratio up, replicate the database and cache, and re-run "
                "after each change. One change at a time; otherwise you "
                "won't know which one mattered."
            ),
            task_md=(
                "Reach < 5% failure rate at 20,000 QPS with DB and Cache at "
                "replica count ≥ 2."
            ),
            check=lambda s: (
                s.client_qps >= 20000
                and s.last_result is not None
                and s.last_result.failure_rate_pct < 5.0
                and all(
                    n.params.replica_count >= 2
                    for n in s.nodes
                    if n.node_type in (NodeType.DATABASE, NodeType.CACHE)
                ),
                "A feed that survives its own popularity.",
            ),
        ),
    ],
)

_CHAT = Lesson(
    challenge_title="Design a Chat System",
    intro=(
        "Chat looks like a feed until you notice the connections never "
        "close and the messages must arrive in order."
    ),
    steps=[
        LessonStep(
            title="Persistent connections change the math",
            body_md=(
                "HTTP request/response doesn't cut it for chat. You can't "
                "have the server 'respond' with a message that hasn't been "
                "sent yet. Real chat holds a **persistent connection** "
                "(WebSocket) per online user.\n\n"
                "That flips the scaling question: app servers are no longer "
                "limited by requests/sec but by **concurrent open "
                "connections** (memory + file descriptors). A box that "
                "handles 2,000 QPS of HTTP might hold 50k idle sockets, or "
                "choke on far fewer active ones.\n\n"
                "Target: **15,000 QPS** of message traffic."
            ),
            note_md=(
                "Edge case: load balancing WebSockets. Connections are "
                "long-lived, so the LB must route *new* connections evenly, "
                "and after a server dies, its thousands of clients all "
                "reconnect at once (**reconnect storm**). Jittered backoff "
                "on the client side is the standard defense."
            ),
        ),
        LessonStep(
            title="Build the gateway tier",
            body_md=(
                "Model the connection layer: **Client → LB → App Servers** "
                "(these are your WebSocket gateways). Give yourself at "
                "least 2 gateways. With one, every user disconnects when "
                "it restarts.\n\n"
                "Gateways should stay thin: hold the socket, authenticate, "
                "forward messages. Business logic lives behind them."
            ),
            task_md=(
                "Build Client → Load Balancer → **2+** App Servers, with "
                "total app capacity ≥ 15,000 QPS."
            ),
            check=lambda s: (
                _has(s, NodeType.LOAD_BALANCER)
                and len(_nodes_of(s, NodeType.APP_SERVER)) >= 2
                and _total_capacity(s, NodeType.APP_SERVER) >= 15000,
                "Gateway tier up, with room for everyone's sockets.",
            ),
        ),
        LessonStep(
            title="A queue makes delivery survivable",
            body_md=(
                "User A is connected to gateway 1; user B to gateway 7. A "
                "message from A must find B, and survive if B is offline "
                "or a gateway crashes mid-delivery.\n\n"
                "Route messages through a **Queue**: gateways publish "
                "incoming messages; delivery workers consume, persist to "
                "the **Database** (chat history is sacred), and push to the "
                "recipient's gateway. If anything crashes, the message is "
                "still in the queue, not lost in a dead process's memory."
            ),
            task_md=(
                "Add App Server → **Queue** → **Database** so every message "
                "is durably persisted."
            ),
            check=lambda s: (
                _has(s, NodeType.QUEUE)
                and _edge_between_types(s, NodeType.APP_SERVER, NodeType.QUEUE)
                and _edge_between_types(s, NodeType.QUEUE, NodeType.DATABASE),
                "Messages now outlive crashes.",
            ),
            note_md=(
                "Ordering edge case: global ordering across a group chat is "
                "expensive; per-conversation ordering (partition the queue "
                "by conversation ID) is what real systems guarantee. Also "
                "decide your delivery semantics: at-least-once + "
                "de-duplication by message ID is the pragmatic default."
            ),
        ),
        LessonStep(
            title="Do it yourself: no SPOFs, full load",
            body_md=(
                "Chat outages are *loud*. Everyone notices within seconds. "
                "Finish the design: replicate everything stateful, keep "
                "failures at 0% at 15,000 QPS, and make sure losing any "
                "single node wouldn't take the service down."
            ),
            task_md=(
                "Reach **0% failures at 15,000 QPS** with Queue, Database "
                "(and any Cache) at replica count ≥ 2."
            ),
            check=lambda s: (
                s.client_qps >= 15000
                and s.last_result is not None
                and s.last_result.failure_rate_pct == 0
                and all(
                    n.params.replica_count >= 2
                    for n in s.nodes
                    if n.node_type
                    in (NodeType.DATABASE, NodeType.QUEUE, NodeType.CACHE)
                ),
                "Resilient, ordered, durable. Ship it.",
            ),
        ),
    ],
)

LESSONS: dict[str, Lesson] = {
    lesson.challenge_title: lesson
    for lesson in (_URL_SHORTENER, _RATE_LIMITER, _NEWS_FEED, _CHAT)
}


def lesson_for(challenge_title: str) -> t.Optional[Lesson]:
    return LESSONS.get(challenge_title)
