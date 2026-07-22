# Concepta.io

A system design playground you can actually break things in.

You drag infrastructure components onto a canvas, wire them together, and
push traffic through them. The simulation tells you what held, what
drowned, and why. It is built for backend engineers who want to practice
system design the way it actually gets learned: by watching a design fail
and then fixing it.

Built by Neptune Developers And Consultants.
Source: https://github.com/b100mBUG/conceptaio

## Running it

```bash
pip install -r requirements.txt
rio run
```

Or `python main.py` if you just want it to open in your browser.

## How it works

Pick a challenge from the landing page. Four of them come with guided
lessons, written the way a senior dev would walk a junior through the
problem: here is the concept, here is why it matters, here is the edge
case that will bite you in an interview. Each step gives you a task, and
the guide watches your canvas and unlocks the next step when you have
done it. If you would rather see the answer first, "Build this for me"
drops a working reference design you can run and pick apart.

The freeform sandbox has no guide. Just you, the canvas, and a QPS number.

### The canvas

Spawn clients, load balancers, app servers, caches, databases and queues
from the left panel. Drag them wherever you want. Hit Link Nodes, tap a
source, tap a target, and you have a connection with an arrow on it.
Select any node to edit it on the right: name, capacity, replicas,
connection pools, sharding keys, cache strategy and hit ratio. Changes
apply as you type.

### The simulation

Set your client QPS and hit Run. Traffic flows from clients through your
graph. Load splits across a node's children, replicas multiply capacity,
and caches absorb their hit ratio so only the misses reach whatever sits
behind them. Latency climbs as a node approaches its limit, and the P99
you see is summed along the slowest path, because that is how real
requests experience your system.

After a run, every node shows its utilization, overloaded nodes turn
red, and the edges feeding the bottleneck light up.

### The Tech Lead

The panel on the right reads your results and tells you plainly what is
wrong: which node is drowning, how much traffic is being dropped, what
is dead weight, and which single box takes the whole thing down with it.
Then it asks the kind of questions an interviewer would. It is a local
rule engine, no network calls, and the whole thing works offline.

### Saving

The save button in the top bar writes your design to
`~/.sysdesign_rio/saves/` as plain JSON. Load brings it back, including
your QPS setting.

## Project layout

```
main.py                  app entry, pages, theme, footer
theme.py                 the teal light and dark themes
app_state.py             shared state, challenges, user settings
models/                  nodes, simulation engine, lesson content
services/                storage and the mentor rule engine
components/              canvas, nodes, palette, inspector, HUD, guide, footer
pages/                   the challenges page and the playground
```

The models and services layers have no UI imports, so you can unit test
the simulation or swap the mentor for a hosted model without touching
any component code.

## Notes

Dark mode is the default. The toggle lives in the top bar and your
choice is remembered between sessions. Designs, likewise, live on your
machine and nowhere else.
