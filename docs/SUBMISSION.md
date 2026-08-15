# Submission kit — YouCam API Hackathon

Everything the rules require, ready to paste. Fenced blocks are the text to
submit as-is; the rest is guidance.

References: <https://youcam-api.devpost.com/> · <https://youcam-api.devpost.com/rules>

---

## 1. What the rules require, and where it is

| Requirement | State | Where |
|---|---|---|
| Repository URL, public **with licensing** | ✅ | `LICENSE` (MIT) + `NOTICE.md` |
| All source, assets and instructions to make it functional | ✅ | `README.md` §3 — two commands |
| Text description: features, functionality, consumer/retail value | ✅ | §2 below |
| Screenshots | ⬜ to produce | §4 — the six to take |
| 1–3 min demo video, end to end, on the target device | ⬜ to produce | §3 — timed script |
| Video explains the YouCam APIs used | ✅ in the script | §3, at 0:45 and 1:45 |
| Video public on YouTube | ⬜ | — |
| No third-party trademarks or copyrighted material | ⚠️ **check at edit time** | §3, closing note |
| Exit interview if selected | — | — |
| File upload (optional) | ✅ | `mirror-ops-onepager.pdf` — see §7 |

> If the repository stays private, share it with `contact_event@PerfectCorp.com`
> **before** the deadline, and verify the invitation went through.

---

## 2. Devpost description

### 2.1 — Title and tagline

```
MIRROR OPS — Fit the moment. One change.
```

```
A contextual appearance decision engine. It tells you whether your look fits
the moment you're about to enter and, when it doesn't, finds the ONE change
worth making — then uses YouCam to prove it before you act.
```
### 2.2 — Project story (paste into "About the project")

Devpost expects these exact headings. Everything below the rule goes in the
field, as-is.

---

```markdown
## Inspiration

Standing in front of a mirror ten minutes before something that matters, and
not knowing whether to change anything.

Every appearance tool we looked at answers the same question — *what should I
wear?* — and answers it with more: more outfits, more products, more
combinations. None of them answered the question we actually had, which was
narrower and harder:

> Will this look work **here**?

That distinction became the whole product. Checking your look is observation.
Deciding what is worth changing is a judgement, and it depends entirely on the
moment you're walking into. The same outfit is right for a dinner and wrong for
a wedding.

## What it does

MIRROR OPS is a **contextual appearance decision engine**.

1. **The moment** — occasion, goal, time available. Three taps.
2. **Your look** — one photo, which pieces you're wearing, how dressed up it is.
3. **Contextual fit** — the engine judges your look against *that* occasion,
   not against an abstract standard. Three verdicts:
   - `FIT` — You're good to go.
   - `ALMOST THERE` — Your outfit fits, but the shoes reduce the formality.
   - `MISMATCH` — This doesn't fit the moment.
4. **One change** — the single highest-value intervention. Change a piece, add
   one that's missing, or remove one too many. Never a list.
5. **The proof** — YouCam Apparel VTO shows the change on you, before you make
   it.
6. **Act** — everything else stays exactly as it was.

The same casual look scores **69 for travel and 47 for a wedding** — two
different verdicts on an unchanged photo. That difference *is* the product.

MIRROR OPS can also decide that nothing is worth changing. `NO CHANGE` is a
real outcome and consumes no try-on credit. A decision engine that cannot
decide to do nothing isn't a decision engine — it's a recommendation generator.

## How we built it

**Next.js 14 + FastAPI + PostgreSQL**, joined by a shared TypeScript contract
that mirrors the Pydantic schemas.

The decision engine is a **pure domain module**: it imports no HTTP client, no
ORM, no LLM. It is deterministic and testable without network, database or
YouCam. Seven weighted features produce a 0–100 score for each candidate
intervention — goal alignment (0.25), context fit (0.20), visual impact (0.20),
current gap, time fit, data confidence, try-on feasibility. Every table is
configurable, because they encode product heuristics meant to be calibrated,
not scientific truths.

**YouCam sits inside the decision loop, not beside it.**

*Skin AI informs the decision* — `/s2s/v2.0/{file,task}/skin-analysis`. Its
influence is capped at 0.08 and only applies past explicit materiality
thresholds. A test verifies that heavily marked skin does not change the
clothing decision.

*Apparel VTO proves the decision* — `/s2s/v2.0/{file,task}/cloth`. Candidates
are scored; only the winner is rendered. One journey costs one skin analysis
and one try-on, enforced by input-aware idempotency keys and by a test that
counts provider calls.

Users can also photograph a garment they're actually considering and see it on
themselves — which is the real moment of hesitation. Not a catalogue: a
specific jacket.

## Challenges we ran into

**Ten occasions, one verdict.** Our first working build returned
`ALMOST_THERE` with a score between 60 and 65 for *all ten* occasions. A judge
testing "wedding" then "travel" would have seen the same screen twice and
concluded, rightly, that the occasion did nothing. The thesis was true in the
engine and invisible on screen — because the interface only declared which
pieces were present, so every look got the same neutral prior. One extra
question, three answers, fixed it.

**Skin AI needs a close-up; we photograph an outfit.** Skin AI rejects images
where the face fills less than 60% of the width. Asking for a second photo
would have added a screen to a 90-second flow. So the server detects and crops
the face from the same shot and sends only that; the original goes untouched to
the try-on.

**Health scores versus severity.** YouCam returns *health* scores — higher is
better. Our engine reasons in *severity*. Getting that backwards would have
made flawless skin read as a problem, and pushed decisions the wrong way.

**A screen that contradicted itself.** One occasion produced a `FIT` verdict
*and* "Change the jacket" — "you're ready", then "change the jacket". Two lines that
disagree destroy credibility faster than any crash. The verdict and the action
are now reconciled by construction, and a test walks every occasion and
dressiness level to prove no screen can promise readiness while demanding a
change.

**Phone photos processed sideways.** Browsers apply EXIF orientation; PIL does
not. Users saw their photo upright while the server analysed it rotated 90° —
which made faces undetectable and poses unreadable. It was invisible in tests
until we fabricated EXIF data.

**An error code that meant something else.** Skin AI kept answering
`error_src_face_too_small`. We widened the crop, twice. Then we measured across
three real photographs: the rejected one carried a **906 px** face, the accepted
one **289 px**. Size was never the issue — the rejected photo had sunglasses,
which defeat frontal face detection. We had been optimising the wrong variable
for two days.

**A dependency that imported and did not work.** `opencv-python-headless` with no
upper bound installed OpenCV 5.0, which removed Haar cascades outright. It
imports cleanly and fails on every call, so nothing at startup reported it and
face detection was silently dead.

**Configuration that depended on where you stood.** Our diagnostic probe reported
"live mode" and then failed on a missing API key: the settings file was resolved
relative to the working directory, so tooling launched from the repository root
read a different file than the API did. Half our diagnostics had been worthless.

**Going back changed nothing.** After adding back-navigation, correcting the
occasion or the outfit left the result identical. Two independent causes: a
duplicate moment row tie-broken by a random UUID, and an idempotency key that
depended only on the session. Both were optimisations that had stopped being
keyed on everything the result depends on.

## Accomplishments that we're proud of

**The constraint held.** Through every iteration, the product never became a
list. When we added "Try another", we made it swap the *piece* and never the
*decision* — and wrote two tests that fail if a `listbox`, a `combobox` or a
selection verb ever appears on that screen.

**Honesty is enforced by tests, not by intention.** Offline previews are
watermarked and flagged `simulated: true` all the way to the UI. The fit verdict
names the weakest piece only when one genuinely stands out — when everything is
equal, it says so rather than inventing a culprit. Undeclared garments get an
explicit prior *and* lower confidence.

**Every refusal has a remedy.** We removed a refusal that had none: it told
users to retake a perfectly good photo because their *outfit* was undescribed,
which no amount of retaking could fix.

**An audit that catches what unit tests can't.** 320 backend tests and 34
frontend tests, plus a 42-check end-to-end audit against the assembled system.
It verifies that a piece declared absent is never listed as "kept", that a FIT
verdict never coexists with a demanded change, and that media URLs actually
resolve — a class of failure that returns HTTP 201 while showing nothing.

**Both integrations are verified live, not assumed.** Skin AI returns redness,
radiance, oiliness and texture on a real full-length photograph; Apparel VTO
returns a genuine render with `simulated: false`. Getting there settled two
things we could not have guessed: a photo cropped into a 1:3.12 strip breaks the
try-on, and `error_src_face_too_small` usually means "I cannot find a face" —
the rejected photo carried a 906 px face while the accepted one carried 289 px.
The difference was sunglasses.

Every try-on failure now reports whether the garment came from the catalogue or
from the user, so diagnosis takes one line instead of one afternoon. And because
some references are refused for reasons no check of ours predicts, a failed
render falls back once to the next piece in the same category — the decision
never changes, only the piece used as proof.

## What we learned

**Measure before you claim.** We believed the contextual thesis was working
because the engine's tables said so. It took one measurement across all ten
occasions to discover that users saw one identical answer. A property that is
true in the code and invisible on screen doesn't exist.

**A refusal without a remedy is a dead end.** Error messages should name a
gesture the user can actually perform. Anything else sends people in circles.

**Any optimisation that memoises must be keyed on everything the result depends
on** — otherwise it silently turns a user's correction into an illusion.

**A deliverable must never write where the user writes.** Our project archive
contained placeholder garment images, so updating the project deleted the user's
imported photos. Their catalogue now lives outside the source tree.

**Honesty is a feature, and it costs less than it looks.** Saying "we don't know
this" and lowering a confidence score is cheaper to build than pretending, and
far cheaper than being caught.

## What's next for MIRROR OPS

**Feedback on the decision.** The product rules and never listens. One button —
"that wasn't the right piece" — would give the only signal that lets the scoring
model be calibrated on evidence rather than on our judgement. It's also the
first thing an enterprise buyer asks for.

**Retail catalogues via URL manifest.** A retailer already has product visuals
online. Their catalogue becomes an `id → URL` list, imported in one command,
with no further integration. The decision layer is the product; the catalogue is
just an input.

**A second look at the Skin AI framing.** On a full-length shot the face is
often too small even after cropping. That's a real constraint, and it deserves
to be designed around rather than hidden — possibly by making the skin signal an
explicit, optional close-up step rather than a silent best-effort.
```
### 2.3 — Built with

```
next.js, react, typescript, fastapi, python, postgresql, docker, nginx,
youcam-skin-ai, youcam-apparel-vto, opencv, pillow
```

### 2.4 — Elevator pitch (200 characters max)

```
MIRROR OPS decides whether your look fits the moment you're about to enter — and when it doesn't, finds the ONE change worth making, then uses YouCam to prove it before you act.
```

177 characters. If the field rejects it, Devpost may be counting the em dash as
two: replace `—` with `,` and it drops to 175 without losing the meaning.

Shorter alternative, 156 characters:

```
MIRROR OPS tells you whether your look fits the moment you're about to enter, finds the ONE change worth making, and uses YouCam to prove it before you act.
```

### 2.5 — Text description (features, functionality, value)

```markdown
**MIRROR OPS is a contextual appearance decision engine.** It answers one
question — *will this look work here?* — and, when the answer is no, names the
single change worth making and proves it visually before you act.

## Features

- **Moment framing.** Occasion (ten of them, from interview to wedding to
  travel), goal, and time available. Three taps. The engine treats "under five
  minutes" as a hard constraint: it will not suggest something you cannot
  actually do before you leave.
- **Contextual fit verdict.** `FIT` / `ALMOST THERE` / `MISMATCH`, scored 0–100
  against *that* occasion, with the weakest piece named — but only when one
  genuinely stands out.
- **ONE CHANGE.** A single intervention, chosen from a closed space of eight
  actions. It can *change* a piece, *add* one that is missing, or *remove* one
  too many. It comes with a reason derived from the factors that actually
  dominated the scoring, and an explicit list of everything that stays.
- **NO CHANGE.** A legitimate outcome. The product will tell you you're ready
  and consume no try-on credit doing it.
- **Visual proof.** YouCam Apparel VTO renders the chosen change on your own
  photo. A drag slider compares before and after.
- **Your own garment.** Photograph the jacket you are actually hesitating over
  and see it on yourself, instead of a catalogue piece.
- **Decision confidence.** Stated as low / medium / high, never as a falsely
  precise percentage, and lowered automatically when the product knows less.

## How it works

One photo and a short declaration of what you're wearing feed an appearance
context. YouCam Skin AI adds visual signals from the same shot. A pure,
deterministic decision engine scores every candidate intervention on seven
weighted features — goal alignment, context fit, visual impact, current gap,
time fit, data confidence, try-on feasibility — and returns exactly one. YouCam
Apparel VTO then renders that one, and only that one.

The whole journey runs in under 90 seconds, with no account and no wardrobe to
set up. Photos are anonymous, time-limited, and deleted on expiry.

## Consumer value

People generally know what they like. They don't always know whether it suits
the situation they are walking into, and that uncertainty peaks exactly when
there is no time left to resolve it. MIRROR OPS replaces browsing with a
decision, and replaces guessing with proof.

Its restraint is the point. There is no catalogue to scroll, no list to compare,
no chatbot. One moment in, one decision out — and sometimes the decision is that
nothing needs to change.

## Retail value

The decision layer is the product; a catalogue is only an input. A retailer's
existing product visuals become MIRROR OPS garments through a manifest of
`id → URL`, imported in one command with no further integration.

That places the try-on at the moment of **hesitation** rather than the moment of
browsing: uncertainty → one change → visual proof → decision confidence. The
same loop serves clienteling in store, where an associate can justify a single
recommendation with a rendered before/after instead of an opinion.

We deliberately do not claim reduced returns. It is a plausible second-order
effect, and we have no evidence for it.
```

### 2.6 — Was there a moment where the API surprised you?

```markdown
Twice, in opposite directions.

**The good surprise: an error message that documented the API better than the
documentation.** Our try-on calls kept failing, and we were guessing at the
payload shape. Then a 400 came back enumerating exactly what it would accept:
*"ref_file_url is required but wasn't included in your request., or
src_file_url is required..., or ref_file_id is required..."*. That single
response told us the endpoint accepts either a URL pair or an ID pair, and that
we had been sending an array where it wanted a scalar. We fixed it in one
iteration. Error messages that teach the contract are rarer than they should be.

The other pleasant surprise was discovering that API v2 has **no authentication
endpoint at all** — the key goes straight into a Bearer header. We had already
implemented the v1 flow, RSA-encrypting the client secret into an `id_token`,
and were able to delete the whole path from the critical route.

**The frustrating one: `error_editing_failed`.** For photo problems, the API is
genuinely helpful — `error_pose`, `error_multiple_people`, `error_no_shoulder`,
`error_unsupport_ratio` each name something the user can fix. But when the
render itself fails, `error_editing_failed` says only that it failed. It cost us
several rounds to work out that our *reference garment* was the problem, not the
source photo, because nothing in the response distinguished the two inputs.

We solved it on our side by instrumenting our own errors: every try-on failure
now reports whether the garment came from the catalogue or from the user, and
its identifier. Diagnosis went from an afternoon to one line. A hint of that
shape from the API — *which input was rejected* — would have saved everyone the
detour.
```

### 2.7 — Industries or use cases nobody is talking about

```markdown
The conversation around appearance APIs is almost entirely about beauty retail
and fashion e-commerce. Four directions look underserved to us.

**Dress-code and uniform readiness.** Hospitality, aviation, healthcare and
client-facing services all run on appearance standards that are checked
informally, inconsistently, and often awkwardly by a supervisor. A pre-shift
self-check that says *fits the standard* or *one thing to adjust* moves that
conversation from interpersonal to objective. The decision framing matters here
more than the try-on: nobody wants twenty options before a shift.

**Employability and interview preparation.** Career services, public employment
programmes and reintegration schemes work with people who have no stylist and no
network to ask. "Does this work for an interview?" is a question with real
economic consequences and almost no accessible answer. It is also a use case
where a *contextual* engine matters far more than a catalogue — the point is to
work with the clothes someone already owns.

**Accessibility.** For someone with a visual impairment, an objective read on
whether an outfit suits an occasion is genuinely useful, and it is rarely
discussed in this space. It would demand serious work on screen-reader output
and on how a verdict is phrased — but the underlying signals already exist in
these APIs.

**Secondhand and resale platforms.** Every listing is a single unit, often
photographed on a hanger or flat. "How will this look on me?" is precisely the
uncertainty that kills a secondhand purchase, and there is no size run to fall
back on. A try-on placed at the moment of hesitation seems more valuable there
than on fast fashion, where the cost of being wrong is lower.

We would flag one adjacent direction to approach carefully: anything that drifts
toward skin *diagnosis*. Our own product deliberately frames Skin AI output as a
visual observation and caps its influence on the decision, because the line
between a cosmetic signal and a medical claim is thinner than it looks from the
engineering side.
```

### 2.8 — Where did you hit a wall technically?

```markdown
**The wall: two requirements that could not share one photograph.**

YouCam Skin AI rejects any image where the face fills less than 60% of the
width. MIRROR OPS photographs an *outfit* — head to knees at least, where the
face is small by construction. Every skin analysis came back
`error_src_face_too_small`.

The obvious fix was to ask for a second, closer photo. We refused it: the whole
product is a 90-second decision, and adding a screen to satisfy an API contract
would have been the API dictating the product.

**The workaround:** the server detects the face in the outfit photo with an
OpenCV Haar classifier, crops a region sized so the face fills about 68% of the
frame, upscales to the minimum short side, and sends *that* to Skin AI. The
original photo goes untouched to the try-on and to the screen. One shot, two
framings, no extra screen.

Three deliberate limits came with it. We use SD actions rather than HD, because
a crop from a full-length photo rarely reaches HD's 1080 px short side. A face
detected under 140 px wide produces no call at all — enlarging it would only
manufacture interpolated pixels, and analysing an invention is worse than
analysing nothing. And when no face is found, we skip the call entirely rather
than spend a credit on a certain rejection.

Crucially, the journey continues either way. Skin AI *informs* the decision, it
does not make it, so its absence lowers the stated confidence and is reported as
`skin_source: "unavailable_no_face"` rather than failing the request.

**A related wall, worth mentioning:** phone photos were being processed
sideways. Browsers apply EXIF orientation; the Python imaging library does not.
Users saw their photo upright while the server analysed a 90°-rotated image —
which made faces undetectable and poses unreadable, and quietly degraded both
APIs. It was invisible in our tests until we started fabricating EXIF data on
purpose. Straightening on ingest fixed both integrations at once.
```

---

## 3. Video — timed script (2 min 40)

Shoot **on a phone, in portrait**: that is the device the product is built for,
and the rules ask for footage on that device.

| Time | On screen | Voice-over |
|---|---|---|
| 0:00–0:12 | Home, logo, signature | *Ten minutes before something that matters, you don't need twenty outfit ideas. You need to know whether what you're wearing works — and if not, what one thing to change.* |
| 0:12–0:24 | Moment: **interview · professional · under 5 min** | *So Mirror Ops starts with the moment, not the wardrobe.* |
| 0:24–0:40 | Full-length photo · tick all five pieces · **In between** | *One photo, head to feet. What you're wearing, and how dressed up it is.* |
| 0:40–0:56 | **Fit verdict** — "Almost there." 64/100, gauge settles | *First answer: does this look fit the moment? Almost there. YouCam Skin AI reads the visual signals from that same photo — and because it needs a close-up while we shot a full-length, the server crops the face itself.* |
| 0:56–1:12 | **ONE CHANGE** — "Change the jacket for something sharper." + Keep ledger (top, bottom, shoes, accessories) | *Then the decision. One change — not a list. It even says which way: sharper, not just different. And everything else stays, explicitly.* |
| 1:12–1:42 | Try-on: button, **cut**, **Before/After** dragged | *YouCam Apparel Virtual Try-On proves it. Only the winning change is rendered — one journey, one try-on.* |
| 1:42–2:00 | **Back to Moment → dinner · elegant**, nothing else touched: "You're good to go." 74 and **"Don't change it."** | *Same look, same photo. Different moment — and now there's nothing worth changing.* |
| 2:00–2:12 | **→ travel · approachable**: "Change the jacket for something **easier**." | *And the direction follows the moment too. Sharper for the interview, easier for the flight — same jacket.* |
| 2:12–2:24 | Ready screen, result shown, "Save this" | *One change. That's all you needed.* |

**Every line is measured**, on a real full-length photograph, through the live
integration, with the honest dressiness answer for a blazer and chinos. Nothing
here is staged: declaring the outfit "casual" would have produced a sharper
contrast and would have been a lie on camera.

The 2:00 segment is the strongest fifteen seconds in the film and the easiest to
drop if time runs short. It shows the recommendation **reversing direction** on
an unchanged look — the one thing no outfit generator can imitate.

**Measured latencies, on the live integration:** Skin AI answers in about 6.5 s,
the decision is instant, and the try-on takes 13 to 15 s. That try-on wait is
roughly 10% of the whole video — cut to the result, or keep talking over it, but
do not film thirty seconds of a spinner.

**Every line above is what the screen actually shows**, measured on a real
full-length photograph through the live integration — dressed up, all five
pieces ticked, shoes flagged. Verify on your own photo before shooting:

```bash
python scripts/probe_skin.py your-photo.jpg      # framing, crop, Skin AI
python scripts/probe_vto.py your-photo.jpg jacket_02   # one try-on, raw response
python scripts/demo_pairs.py --dressiness 0.88   # rank the moment pairs
```

**The photo must be full-length.** It is what makes the shoes recommendable at
all: a waist-up shot removes them and the bottom from the decision, and the
sharpest verdict in the product — naming the piece that holds the look back —
goes with them.

**The complete arc lands by 1:40.** That is deliberate. Judges are not required
to watch past three minutes, but they decide much earlier than that: if the
payoff arrives at 2:00, someone who stops at 60 seconds has seen a form and a
spinner. Problem, decision and proof must all be past before anyone would think
of leaving.

The two segments after 1:40 are the differentiators, not the demo: the occasion
flip proves the contextual claim, and the user's own garment shows the real
moment of hesitation. Cut either if the recording runs long — the product is
already fully explained.

### The occasion flip is not optional — and the pair matters

It is the only fifteen seconds that *prove* the thesis rather than assert it.
Everything else in the video could describe an AI stylist; a verdict and a
decision both changing on an unchanged photo could not.

**Use interview / professional → dinner / elegant**, dressiness "In between":

```
interview / professional   Almost there.       64   Change the jacket for something sharper.
dinner    / elegant        You're good to go.  74   Don't change it.
travel    / approachable   Almost there.       67   Change the jacket for something easier.
```

Verdict flips, decision flips, and the third line reverses the *direction* on the
same look. Measured on a real photograph through the live integration — and the
jacket is the piece to demo because it is the one verified end to end.

Nothing about the look changes between the two screens — same photo, same
shoes, same declaration. Only the moment moves, and the product goes from naming
a specific fault to refusing to touch anything.

Change **both** answers. The moment is occasion *and* goal *and* time: keeping
"professional" for the second run flips the score without flipping the
decision, and the two screens look nearly identical.

**Flag the shoes as more casual than the rest.** That optional tap is what lets
the verdict name a piece rather than say "as a whole, this look sits below…".
Without it the sentence is generic, and the demo loses its sharpest moment.

Verdict flips, action flips, and the second screen is the product **refusing to
recommend anything** — the single best argument that this is a decision engine.

**Do not use interview → wedding.** They are the two closest occasions in the
system (formality 0.90 and 0.88) and produce two identical screens. Same for
business. Verify any pairing before shooting:

```bash
python scripts/demo_pairs.py                 # ranks every pair
python scripts/demo_pairs.py --dressiness 0.85
```

Shoot it as one take: tap back, change the occasion, let the screen land. Do not
narrate over the change itself.

**Answer "How dressed up is it?"** — it is required, and for good reason: without
it every look reads as mid-formality, an interview and a flight land two points
apart, and the flip shows nothing.

Answer it **honestly**, and check the pairing rather than assuming. The middle
level is equidistant from the formal and casual extremes, so some pairs collapse
on it — an interview at 64 against a flight at 67, the same recommendation on
both. Others separate cleanly: the same look reads 64 for an interview and 74
for a dinner, a change against a "good to go".

`scripts/demo_pairs.py --dressiness 0.55` ranks them. Choosing a dressiness that
misdescribes the outfit to force a contrast would be staging the demo.

**Tick every piece you're wearing**, jacket included. Nothing is pre-selected —
deliberately, so an empty box is a statement rather than an oversight. If the
jacket is left undeclared, the recommendation becomes "Add a jacket" for every
formal occasion and the flip loses its force: the decision is then driven by the
missing piece rather than by the moment.

### The comprehension test comes first

Show the still frames — moment, fit verdict, ONE CHANGE, before/after — to two
people who have never heard of the product, and ask what it does. If the answer
isn't close to *"it tells me what to change so I fit the situation"*, the screens
are not carrying the idea and narration won't rescue it. Details in
`docs/DEMO_RUNBOOK.md` §2 bis.

### Before recording

```powershell
.\scripts\mirror-ops.ps1 audit      # 0 FAIL expected
.\scripts\mirror-ops.ps1 garments   # "all usable by a real try-on"
```

- `YOUCAM_MODE=live` — otherwise previews carry "simulated", visible on camera
- Catalogue replaced with real photographs, or `error_editing_failed` follows
- Five clean journeys in a row before recording
- The try-on takes 13 to 15 seconds: plan a cut, or fill the wait with narration
- **No copyrighted music.** Voice-over alone, or explicitly royalty-free music.
  Check that no third-party trademark appears in frame either — logoed garments
  included.

---

## 4. Screenshots (six)

Taken on a phone, in portrait, in live mode.

1. **Home** — the signature *Fit the moment. One change.*
2. **Moment** — the three questions, one option selected in each
3. **Your look** — photo, outfit chips, and the line
   *"Mirror Ops will read this as… — and no jacket"*
4. **Verdict + ONE CHANGE** — the one that matters: "Almost there", the fit
   gauge, the verdict, and the Keep ledger
5. **Before / After** — slider mid-way, both tags visible
6. **Ready** — the result shown and the closing line

Avoid: the word `simulated`, a placeholder catalogue, `confidence: low` when a
better-informed journey would read higher.

---

## 5. What to be able to answer

**Why a single change?** The problem isn't a shortage of options, it's
uncertainty at the moment of deciding. We don't redesign the person; we fix the
mismatch.

**How do you know it doesn't fit?** The look is projected onto what the occasion
demands, not judged in the abstract. Change "travel" to "wedding" on screen 2 and
the verdict changes in front of you.

**Why Skin AI on a clothing product?** It gives visual context signals. Its
influence is capped at 0.08 and tested: heavily marked skin does not change the
clothing decision. It informs; it does not decide.

**What if nothing should change?** The verdict is FIT, the action is NO CHANGE,
and no try-on credit is consumed.

**What isn't ready?** There is no user feedback on the decision, and the shipped
catalogue is a fallback. `docs/PRODUCT_REVIEW.md` records twenty-odd defects
found and fixed during live testing, each with what it was, why it happened, and
the test that now prevents it — including several where the first diagnosis was
wrong. Better said than found out.

---

## 6. Links to provide

| Devpost field | Value |
|---|---|
| Repository URL | `https://github.com/…/mirror-ops` |
| Demo / try it out | `https://mirror-ops.vylantic.com` |
| Video URL | YouTube, public — unlisted is not accepted |

---

## 7. The uploaded file

Devpost's file field is optional. **Do not upload the code archive**: it
duplicates the repository and goes stale on the next commit.

What earns its place is a sheet a judge can absorb in sixty seconds while
comparing dozens of projects — carrying only what the video cannot show at a
glance:

```bash
python scripts/build_onepager.py     # → mirror-ops-onepager.pdf
```

Two A4 pages:

1. The thesis **measured** — the same look scored against four different
   moments, so the contextual claim is visible rather than asserted — the
   journey, and the boundaries of what the product is not.
2. Where YouCam sits in the decision loop, the four integration decisions that
   were not obvious, what is verified, and **the limits we state ourselves**.

That last block is deliberate. A jury that reads a project admitting its own
gaps trusts the rest of the page more, not less.

Regenerate it after any change to the numbers it quotes — test counts, fit
scores, try-on latency. A figure that can be checked in one second is the worst
place to be wrong.
