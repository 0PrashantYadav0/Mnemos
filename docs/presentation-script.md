# Mnemos — 3-Minute Presentation Script

**Target: ~3:00 min · ~430 words · conversational pace (~145 wpm).**
Timings are cumulative. Each block maps to a slide in `presentation.html`.
Bracketed `[...]` notes are stage directions, not to be read aloud.

---

### Slide 1 — Title  ·  [0:00 – 0:20]

"Hi everyone. This is **Mnemos — The Town That Never Forgets**.

It's a narrative RPG, but the real project is underneath it: a memory engine
for game characters. The premise — *you* wake up with total amnesia, but the
town remembers you perfectly. Because every character's memory lives in a real,
typed **knowledge graph**."

---

### Slide 2 — The Problem  ·  [0:20 – 0:45]

"Here's the problem I wanted to solve. Game NPCs have goldfish memory. Usually
it's a boolean flag, or lately a flat vector store.

A vector store can tell you a scene *sounds similar* to a past one — but it
**can't** tell you who told whom, how a belief travelled, or that a rumor is
second-hand and might be distorted. So you end up with a town of independent
chatbots that don't feel alive."

---

### Slide 3 — The Idea  ·  [0:45 – 1:05]

"Mnemos makes memory the actual game mechanic. Three things:

Every NPC genuinely remembers what you did and how they feel. Deeds **spread**
between characters as gossip — so your reputation travels ahead of you. And your
choices compound: kindness and cruelty snowball into completely different
endings."

---

### Slide 4 — Graph vs Vectors  ·  [1:05 – 1:30]

"The core design decision: a graph, not vectors.

I have typed nodes — Player, NPC, Event, Rumor — and typed edges like *helped*,
*harmed*, *trusts*, *distrusts*. But the star is this one: **told-about** —
NPC-to-NPC gossip.

That edge encodes something a similarity score simply can't: that a belief is
second-hand, that it gets weaker with every hop, and that it travelled a real
social path. That's a *relationship*, not a lookup."

---

### Slide 5 — Architecture  ·  [1:30 – 1:55]

"Architecturally, the memory is a fully decoupled **NPC Brain**.

The web client — built in Phaser — talks to a FastAPI game server, which talks
to the Brain, which owns the graph. And the game only knows **four HTTP verbs**:
remember, recall, improve, and forget.

That means I can swap the client, or drop this Brain into a completely different
game, and it doesn't change. That decoupling is really the whole pitch."

---

### Slide 6 & 7 — The Verbs + Rumor Propagation  ·  [1:55 – 2:25]

"Those four verbs run everything. **Remember** writes an event and its edges —
and note, a betrayal shifts trust harder than a favor does.

But the magic moment is **improve**. Watch this: in Act 1 you help Mira. The
`improve` call spreads that as *told-about* edges to everyone in her district and
faction, with confidence decaying per hop. So in Act 2, a stranger you have
**never met** already greets you warmly — because the rumor reached them first.
In-game, you literally watch those gossip dots travel the graph."

---

### Slide 8 — forget()  ·  [2:25 – 2:40]

"And then the showpiece: the **Memory Potion**, which calls `forget`. It
surgically removes *one* grudge — the harm edge, the distrust, the seed event,
and the whole rumor cascade it spawned — while leaving every other memory
intact. It's the theme made mechanical: forgetting as a precise graph operation."

---

### Slide 9 & 10 — Endings + Tech  ·  [2:40 – 2:52]

"All of this drives five acts and four endings — from the town saving you, to
the town forgetting *you*, plus a secret ending.

And it runs anywhere: zero-CDN, Phaser vendored locally, all art procedurally
generated, local-first with an optional Cognee Cloud mirror, and tested all the
way through to every ending."

---

### Slide 11 — Close  ·  [2:52 – 3:00]

"So that's Mnemos — memory you can walk through. The Brain is decoupled, so it
can remember for *your* game next. Thanks!"

---

## Delivery tips
- **Breathe** at each `---`. Those are your natural pauses.
- The **rumor-propagation beat (Slide 7)** is your wow moment — slow down there.
- If you're running long, cut Slide 9/10's tech list to one sentence.
- If you have a live build, demo the Rumour Ticker on Slide 7 instead of reading it.
