# Product, UX and business review

This review is not about code quality — the tests handle that. It is about what
the user experiences and what the product is worth. It is deliberately severe:
what works needs no writing down.

Each finding carries a state: **fixed**, **to arbitrate** (a product decision
that is yours), or **out of scope** (accepted here, blocking for a real
deployment).

---

## 1. The most serious defect — fixed

**Finding.** Measured, not assumed: with what the interface was sending, **all
ten occasions returned the same verdict**.

```
interview     ALMOST_THERE  61   presentation  ALMOST_THERE  62
wedding       ALMOST_THERE  61   travel        ALMOST_THERE  63
dinner        ALMOST_THERE  65   conference    ALMOST_THERE  62
…10 / 10 identical, always "Nothing is off"
```

The product's thesis — *the same look is judged differently by the moment* — was
true in the engine and **invisible on screen**. A judge testing "wedding" then
"travel" sees the same thing twice and concludes, rightly, that the occasion
does nothing.

**Cause.** The interface only declared which pieces were *present*, so the engine
applied the neutral prior (0.58) to everyone.

**Fix.** One question, three answers, on *Your look*: **"How dressed up is it?"**
— Casual / In between / Dressed up.

It was optional at first, and that was wrong. Left unanswered, every look reads
as mid-formality: an interview scores 61 and a flight 63, with the same verdict
and the same recommendation. The defect returned in a quieter form — the demo
could fail silently while every screen looked correct. The question is now
required, because it is not a refinement: it is what makes the product's thesis
observable at all.

A second, related trap: the **goal** counts as much as the occasion. Flipping to
`travel` while keeping `professional` changes the verdict but not the decision.
The moment is all three answers, and `scripts/demo_pairs.py` now prints the goal
alongside each occasion so a demo pairing is chosen from measurement.

Result:

| | wedding | interview | dinner | travel |
|---|---|---|---|---|
| **casual** | **MISMATCH 47** | **MISMATCH 46** | ALMOST 60 | ALMOST 69 |
| **in between** | ALMOST 64 | ALMOST 64 | **FIT 74** | ALMOST 67 |
| **dressed up** | **FIT 81** | **FIT 81** | ALMOST 68 | ALMOST 60 |

The diagonal reads at a glance, including *overdressed for travel* — a mismatch
in its own right, 21 points below the same outfit at a wedding.

These figures are produced by **exactly what the interface sends**: presence and
dressiness, nothing more. An earlier version of this table was computed with
garment attributes the UI never transmits, and read 2 to 4 points higher
throughout. Numbers a judge can check are the worst place to be approximate.

## 2. A contradiction on screen — fixed

The same measurement revealed `travel` showing **FIT** *and* "Change the
jacket". "You're ready", then "change the jacket". Two lines that contradict each
other destroy credibility faster than any technical error.

The verdict is now **reconciled with the decision by construction**: FIT if and
only if nothing is to be changed. The in-between case — nothing worth changing on
an imperfect look — has its own wording, *"Close enough."*, instead of being
dressed up as success. A test walks ten occasions and four dressiness levels to
guarantee no screen ever promises readiness while demanding a change.

## 3. An intention that didn't say what it would do — fixed

A live test produced: action `CHANGE_COLOR`, label "Adjust the colour balance",
`keep` containing **top** — while the preview replaced precisely the top. The
screen announced "Keep · Top" while the image changed the top.

One root cause: the product conflated the **intention** (work on colour) with the
**element actually touched** (the top). Fixed via `MATERIALISED_ELEMENT`, and the
label now announces what the proof will show — *"Change the top for a better
colour"*. A parameterised test checks, for every action, that the modified piece
is never listed as kept.

## 4. Both YouCam integrations are verified live

**Skin AI**, on a real photo, after the crop was widened to 80% on both axes:

```
skin_face_cropped   face_ratio 0.8   1061x1188
skin_ai_completed   latency_ms 6595
observations        redness, radiance, oiliness, texture
provider            youcam_skin_ai   simulated: false
```

Two factors had to be fixed together. The crop targeting 68% of the width left
the face at 51% of the height and was rejected; and the first test photo had
sunglasses, which defeat frontal face detection — ours and, most likely,
theirs. Widening the crop and using a photo without sunglasses produced a clean
analysis with all four metrics.

The whole journey then behaves as designed on that photo: framing measured as
`chest`, so bottom and shoes are excluded from the decision, and the moment
drives the outcome — `CHANGE_JACKET 76.05`, then `NO_CHANGE 73.2` after a
dressiness change, then `CHANGE_COLOR 66.39` for a dinner.

## 4 bis. The live try-on is verified

Real trace, same session:

| Garment | Result |
|---|---|
| catalogue (`top_01`, placeholder) | `error_editing_failed` |
| uploaded piece | **201 · `simulated: false` · 14.4 s · YouCam render** |

Confirmed afterwards on another session: `jacket_01`, **replaced by a real
photograph**, succeeds from the catalogue; `top_01`, still a flat shape, fails.
The nature of the visual is therefore the single cause — and `GET /garments` now
exposes `placeholder` per piece so that diagnosis requires no manual inspection.

Note that **14 seconds** of waiting in a 90-second journey is substantial: the
button now announces the expected duration.

## 5. Two paths to the proof, without a catalogue to browse — arbitrated

On the decision screen, two buttons led to the same proof without their
difference being legible: "See the difference" (catalogue) and "Try a piece of
your own" (upload).

**Distinguishing them: yes.** Each action now announces what it will do — the
first names the chosen piece (*"We'll use our Structured Neutral Jacket"*), the
second says it expects a photo.

**A catalogue picker: no.** Letting someone browse twelve jackets would turn the
signature screen into a shop window — the *browse, compare, choose* territory the
positioning explicitly excludes, and rule 3 with it. The product *announces* its
piece; it does not offer to elect another. "Try another", on the next screen,
swaps one piece at a time without ever showing a list: that compromise was
already made, and it suffices.

Two tests hold the boundary: the piece must be named, and no `listbox`,
`combobox` or selection verb may appear.

## 6. Three usability fixes

**EXIF orientation was not applied.** Phones often store a portrait photo as
landscape, with a tag indicating the rotation. Browsers apply it, PIL does not:
the user saw their image upright while the server processed it **sideways**.
Cascading consequences — an undetectable face (hence the `unavailable_no_face`
results), an unreadable pose for the try-on, image quality assessed on the wrong
dimensions. Invisible in tests until you fabricate EXIF; eight tests now cover
it, formats and mirrored orientations included.

**There was no way back.** A wrongly chosen occasion forced a full restart. A
discreet arrow now links each screen to the previous one — the journey moves
forward, but no longer traps.

**The final screen did not show the proof.** Ending on text deprives the journey
of the only thing that demonstrates anything. The result is now displayed, with a
button to take it away — which finally gives content to the "ACT" of the
positioning diagram.

## 7. Updates were destroying user data — fixed

Symptom: a try-on succeeds, then fails again on the same piece, with nothing
changed. Cause: the project archive contains the twelve placeholder visuals;
extracting it over the project **overwrote the imported photos**.

Imports now live in `apps/api/var/garments/`, outside the source tree and
git-ignored. The service resolves each garment by looking for the user's photo
first, then the shipped visual. Added pieces follow the same path, through
`catalog.extra.json`, without ever modifying the repository catalogue.

The general rule that was missing: **a deliverable must never write where the
user writes.**

## 8. Going back changed nothing — fixed

The back navigation added in §6 revealed that the rest of the system did not
anticipate it. Correcting the occasion or the outfit, then re-running, left the
result unchanged. Two independent causes:

**A duplicate moment.** Each `POST /moments` created a row, and reads took "the
most recent" — tie-broken, within the same second, by a random UUID. The
correction was therefore ignored half the time. A session now carries **one**
moment, updated in place.

**An idempotency key deaf to the inputs.** It depended only on the session:
re-running the analysis returned the previous one, corrected outfit included. It
now covers the photo *and* the declaration. Two clicks on identical inputs keep
the same key — double-click protection is intact, which a test verifies
explicitly.

General lesson: **any optimisation that memoises must be keyed on everything the
result depends on**, or it turns a correction into an illusion.

---

## 9. Defaults that asserted things the user never said — fixed

*"Photo with a jacket, jacket left unticked → **Add a jacket**."*

Technically correct: the engine was told there was no jacket. As a product, it
is the worst thing MIRROR OPS can do — describe the user's own body wrongly.

The cause was **mixed defaults**. Top, bottom and shoes came pre-ticked; jacket
and accessories did not. That teaches the user that the defaults are right, so
they never audit the empty boxes — and an absence they never affirmed reached
the engine as a statement of fact.

Nothing is pre-selected any more. Every piece needs a tap, so an empty box means
*"I went through the list and I'm not wearing that"*. And because the absence is
the assertion that produces a false claim, it is now spelled out twice: the
summary line names it in the signal colour, and a warning appears beneath —
*"If you are wearing a jacket, tap it above — otherwise Mirror Ops may tell you
to add one."*

The rule underneath: **a default is a claim made on the user's behalf.** It is
acceptable for a preference, never for a fact about them.

## 10. The product's sharpest sentence was unreachable — fixed

Every document quoted the same example: *"Your outfit fits the occasion, but the
shoes reduce the level of formality."* It could not happen. The interface sent
one dressiness value for every piece, so no piece could ever stand out, and the
verdict was permanently stuck on the generic *"as a whole, this look sits
below…"*.

One optional tap now fixes it — **"Anything more casual than the rest?"** — and
the engine does more than repeat the answer: it decides whether that gap matters
*for this moment*. Sneakers cost nothing on a flight.

That exposed a deeper fault. With the shoes flagged, the verdict named the shoes
and the decision said **"Change the jacket"** — because the jacket yields a
higher average gain for a professional goal. Defensible arithmetic, incoherent
screen, and a direct contradiction of *"don't redesign your look, fix the
mismatch"*: the engine was optimising uplift instead of repairing the anomaly.

Two changes, both bounded and explicit:

- `ANOMALY_BONUS` lifts the lever that repairs a piece standing clearly below its
  peers. On a homogeneous outfit it is exactly zero, so the published matrix is
  untouched.
- The tie-breaker now ranks anomaly repair **before** least effort. Without that,
  the jacket kept winning every near-tie on simplicity alone — the same failure
  mode that once made `NO_CHANGE` win everything.

And a display guard: the verdict names a piece only when the decision actually
addresses it. When the engine is prevented — changing a bottom is unrealistic in
under five minutes — it falls back to the neutral phrasing rather than promising
a fix that isn't coming.

Fourteen tests cover it, including one parameterised over every element and both
time budgets.

## 11. Recommending what the photo cannot show — fixed

*"Even with the shoes ticked, the photo stops at the belly. There are no shoes
in it."*

The product recommended "Replace the shoes" and then promised to **prove** it.
The try-on would have rendered a shoe change on a waist-up photo: a before/after
where nothing moves. Deciding and explaining were fine; the third pillar broke
in silence, at the exact moment it mattered.

`full_look_visible` had been inferred from the **aspect ratio** alone, so any
portrait-shaped selfie passed for a full-length shot. Framing is now measured
from the detected face — 35% of the image height is a chest shot, 8% is
full-length — and elements outside the frame are filtered out of the decision
with the reason `not_visible_in_photo`. The screen says so plainly rather than
leaving the user to suspect an oversight.

**And that measurement exposed a worse defect.** On the very photo that raised
the question, the default Haar classifier returned a box at 66% of the image
height — inside the jacket. Sunglasses defeat frontal detection, which leans
heavily on the eye region. So the product had been cropping a piece of fabric
and sending it to Skin AI as a face.

Four cascades are now tried in order of observed reliability, and every
detection must be geometrically plausible: in the upper part of the frame, and
neither tiny nor covering everything. `alt2` finds the real face on that photo
where `default` invents one elsewhere.

Twelve tests cover both, including the exact false box that was being accepted.

## 12. Two questions that read as one — fixed

*"Duplicate, no?"* — and yes. The outfit chips and the "anything more casual
than the rest?" chips were the same five words, in the same grid, in the same
style. Two different questions cannot look identical and expect to be read as
two.

The second row is now visibly secondary: smaller, dashed outline, and marked in
the signal colour with a downward arrow when selected. One line makes the
relationship explicit — *"Same pieces, different question: which one sits below
the rest."*

**And a trap worth naming.** *In between* is the one dressiness level that
produces no contrast at all: it is equidistant from every occasion by
construction, so an interview lands at 64 and a flight at 67 with the same
recommendation. That is the correct answer, not a bug — but a tester who picks
it concludes the occasion does nothing, which is exactly the wrong lesson. The
demo documentation now rules it out explicitly, and a test records why.

## 13. An action that was never evaluated — found by sweeping

Every defect so far surfaced the same way: someone tried a combination by hand
and the screen said something wrong. That does not scale — the input space runs
to tens of thousands of combinations, and the interesting ones are rarely the
ones a person happens to try.

`scripts/sweep_decisions.py` walks the whole space — occasion × goal × time ×
dressiness × declared pieces × flagged piece × framing — and checks nine
invariants on each. First run: **43,200 decisions, 0 crashes, 0 violations**, and
one line that mattered more than the zeros:

```
REMOVE_ACCESSORY   0   0.0%
```

`REMOVE_ACCESSORY` was in the enum, in the labels, in the positioning document
and in its own tests — but never in `CHANGE_ACTIONS`. The engine had never
evaluated it. Nothing flagged it, because an action missing from the candidate
list raises no error; it simply disappears. Every test that touched it checked
it in isolation, which is exactly the blind spot.

Adding it exposed two further gaps — `TIME_FIT` and `ELEMENT_NOUN` had no entry
either, both of which would have crashed the engine the first time the action
was scored. The tables now assert their own completeness at import time.

It now wins where it should: an accessory badly out of place before an interview
scores 86.6, ahead of every alternative, and asks for no try-on.

Two permanent guards followed: one test asserts that the declared action set and
the evaluated action set are identical, another that **every** action can win
somewhere — an action that never wins is dead code that believes itself alive.

## 14. The same recommendation, whatever the moment — fixed

*"Once 'Change the jacket' appears for an image, the following combinations tend
to give 'Change the jacket' too."*

Correct, and not a statistical impression. Through the API, the four runs
returned **the same `analysis_id`**: the analysis was served from cache while
only the moment changed.

The analysis is moment-dependent by construction —
`item_suitability(item, moment)` scores each piece *against the occasion*. Its
idempotency key covered the photo and the outfit, and not the moment. So
changing the occasion re-read an analysis frozen on the first one, and the
decision faithfully repeated itself.

This is the **second** time the same rule was broken, in the same file, after I
had written it down: *any memoisation must be keyed on everything the result
depends on, or it turns a correction into an illusion.* Both keys now carry the
moment — server-side and in the interface — and three tests hold it, including
one that asserts suitability genuinely differs between an interview and a
flight.

Worth noting what did **not** cause it: there is no cached recommendation. Each
decision was recomputed, correctly, from stale inputs. A defect can be perfectly
downstream of the layer that produced it.

## 15. One sentence for two opposite situations — fixed

Six runs on one photo, reported by a tester:

```
interview / casual      → "Change the jacket"
interview / in between  → "Change the jacket"
travel    / casual      → "Change the jacket"
travel    / in between  → "Change the jacket"
travel    / dressed up  → "Change the jacket"
```

The first case is **underdressed** for an interview. The last is **overdressed**
for a flight. Opposite problems, identical sentence — and no way for the reader
to know whether to go up or down. Three different dressiness settings produced
one headline, so the product looked deaf to what it had just been told.

The direction now lives in the headline, where it is read:

```
"Change the jacket for something sharper."   (underdressed)
"Change the jacket for something easier."    (overdressed)
```

It appears only when the level is genuinely the issue — within ±0.12 of the
occasion's target, the piece itself is the problem and the plain label is
correct. A parameterised test asserts the direction never points the wrong way.

**What this does not fix:** `CHANGE_JACKET` is still 55.4% of all decisions.
That is structural rather than a bug — the interface collects one dressiness
value for every piece, so all pieces score identically and the highest-capability
lever wins by construction. The "anything more casual than the rest?" tap exists
precisely to break that tie, and it is the single most useful thing a tester can
do to see the engine reason rather than default.

## 16. A dependency that imported but did not work — fixed

Production logs, on every single analysis:

```
face_detection_failed  reason: module 'cv2' has no attribute 'CascadeClassifier'
```

The cause was **OpenCV 5.0**, released with Haar cascades removed outright:
`CascadeClassifier` is gone, and `cv2.data.haarcascades` still resolves but the
directory is empty. `requirements.txt` asked for `opencv-python-headless>=4.9.0`
with no upper bound, so pip installed 5.x. It imports cleanly and fails on every
call.

Our capability probe checked only that the import succeeded, so nothing at
startup reported it. Skin AI was never called, framing was never measured, and
the only trace was a warning repeated per request.

My first diagnosis was wrong — I blamed an unrelated PyPI package named `cv2`.
The install log said otherwise, and installing OpenCV 5 in a throwaway
environment settled it: no `CascadeClassifier` anywhere, seventeen cascade files
replaced by an empty directory. Its successor, `FaceDetectorYN`, is a better
detector but needs an ONNX model that ships separately — a first-use network
download this project deliberately avoids.

The requirement is now pinned `>=4.10,<5`, and `opencv_status()` verifies that
`CascadeClassifier` and the cascade files are actually present. It names the
version in its message, reports the failure **once** at startup with the exact
fix command, and exposes `"face_detection"` in `/health/dependencies`. The audit
fails on it. Four tests cover it, including one asserting the pin itself.

The same logs showed detection running **twice per analysis** — once for the
Skin AI crop, once for framing — at 560 ms each on a full-resolution photo. The
result is memoised on the image digest: the second call now costs 1.2 ms.

## 17. A refusal that sent the user in circles — fixed

A full-length photo was rejected with:

> *We need a clearer, larger view of your look. Try retaking the photo.*

The image was a **screenshot**, 143 pixels wide against a 320 minimum. The
message blamed clarity, so the natural response — retake it in better light —
produced exactly the same refusal. The rule from §9 again: a refusal must open
onto a gesture that can actually work.

It now names the measurement and the remedy:

> *This image is only 143 pixels wide — we need at least 320. Send the original
> photo rather than a screenshot or a cropped copy.*

**And the screen never recovered.** The analysing watchdog kept polling
`GET /sessions` every eight seconds — thirteen times over two minutes in the
captured logs — while the user watched a frozen screen. The safety net exists
for an orchestration that is *stuck*; one that has failed outright has nothing
left to recover. Marking the failure as settled stops it, and a test with fake
timers advances sixty seconds and asserts no further request is made. Removing
the guard makes that test fail, which is how it was verified.

## 18. Configuration that depended on where you stood — fixed

A probe run from the repository root reported `mode : live` and then failed
three times with `Missing YOUCAM_API_KEY`. My conclusion blamed the photo and
suggested removing sunglasses.

`Settings` declared `env_file=".env"` — a **relative** path, resolved against
the working directory. The API launched from `apps/api` read the right file; any
script launched from the repository root read the docker-compose one, which
carries no key. Half the tooling was silently unconfigured, and every diagnosis
it produced was worthless.

Same defect as the idempotency keys, in a different disguise: **a result that
depends on where you stand is a wrong result half the time.** The path is now
absolute and anchored on the package, verified identical from three different
directories, with process environment variables still taking precedence — which
Docker relies on.

Two older tests had to be rewritten: they asserted `env_file == ".env"`, which
encoded the defect rather than the intent.

And the probe no longer accuses the photograph when the failure is elsewhere. It
reads the error class and says which of the three things is actually wrong:
configuration, face size, or our own parsing of the response.

## 19. Calibrating against the API instead of the documentation

With the configuration finally loading, `probe_skin.py` answered in one run what
four exchanges of guessing had not: on a full-length photo, **all three crop
ratios are accepted**. The crop was never the problem.

That reframes the setting entirely. Conformity does not decide, so quality does:
a tighter crop starts below the minimum short side and must be enlarged, and
`texture` is one of the metrics being measured — enlargement degrades exactly
what we are reading. `TARGET_FACE_RATIO` moved from 0.80 to **0.72**, keeping
both axes above 60% while cutting the enlargement from 1.33× to 1.20×.

The measurement also produced an uncomfortable fact worth publishing rather than
hiding: **the values move with the crop.** Radiance read 0.63 to 0.71 on the
same face across the three ratios. Skin observations are relative, not absolute,
which is precisely why their influence on the decision is capped at 0.08.

**And the error code was misleading us.** Across three real photos, the one that
was rejected for a face "too small" carried a **906 px** face; the one that
passed carried **289 px**. The rejected photo had sunglasses. The code means "I
cannot find a usable face", and the guidance now says what actually helps —
face the camera, no sunglasses, even light — instead of "move a bit closer",
which would have made things worse.

## 20. Both integrations proven, and a garment we cannot vet

The try-on is verified live end to end: a real YouCam render, 225 KB,
`simulated: false`, on a full-length photo of a person.

Getting there took two more fixes worth recording.

**The source photo was a strip.** 1306 × 4080 — a ratio of 1:3.12, nearly twice
as elongated as a phone portrait. The try-on expects a person in a frame, not in
a column. Anything past 1:2.1 is now letterboxed to 9:16 with the average edge
colour. Cropping was rejected as a fix: on a full-length shot, removing height
removes the shoes, which is a piece the product may recommend.

**And the probe was not testing the product.** It sent the raw file bytes — no
EXIF straightening, no bounding, no aspect handling — so it exercised a path the
application never takes and its verdict said nothing about it. It now applies
the same preparation, and a test asserts it keeps doing so.

**What remains cannot be vetted from here.** `jacket_01` fails where `jacket_02`
succeeds, on the same photo. Both are real photographs, neither shows a person,
both are well defined. We cannot predict which reference a renderer will refuse.

So the product survives the encounter instead of trying to prevent it: a
rendering failure now falls back **once** to the next-best piece in the same
category. The decision is untouched — same action, same category — only the
piece used as proof differs, which is exactly the "Try another" semantics
applied automatically. A user's own uploaded piece is never swapped: they chose
it. And two failures in a row stop the process, because that points at the photo
or the pose rather than the garment.

One implementation note worth keeping: the first version nested the retry inside
an `except` block, where a second failure escapes the surrounding handlers
entirely and reaches the client untranslated. It is written as a bounded loop
for that reason.

## 21. A before/after that compared two different framings — fixed

The comparator works end to end on a real YouCam render. One thing was wrong in
it: the *before* looked zoomed next to the *after*.

The before served the **original** photo while the after came from the
**prepared** one — letterboxed from 1:3.12 to 9:16 before being sent. Two
different framings, overlaid in the same box: the difference on screen included
a reframing, and a visual proof must differ by the garment and nothing else.

The prepared image is now stored and served as the before state. A photo that
needed no preparation is not duplicated — one test checks the framings match to
within 2%, another checks a normal photo still produces a single stored asset.

Both were verified by breaking the fix and watching the first test fail.

## 22. The preview was cropping the photo — fixed

The same "zoom" was visible one screen earlier, on *Your look*: the preview
itself. `object-fit: cover` inside a 3/4 frame crops any photo that is more
elongated — which a full-length shot usually is.

That is worse than a comparator artefact. The instruction directly above says
*"show as much of your look as you can"*, and the preview was hiding part of it.
The photographer was shown something other than what would be analysed, and
could not check their own framing.

The preview now shows the whole image, and the frame adapts to the photo rather
than the reverse, with a height cap so a very elongated shot does not push the
controls off screen. The live camera view keeps its fixed frame and fills it —
a video stream that changes shape while you are framing yourself would be worse
than useless.

Three CSS assertions cover it, verified by flipping the rule back and watching
the first one fail.

## 23. Two domain fields that never crossed the database — fixed

Testing for the video, nothing on the decision screen matched the script: no
"sharper", no "easier", just "Change the jacket." The natural assumption was a
stale deployment. It was not — the API itself returned the plain label.

`element_formality` is computed during analysis and is what lets the engine say
which *way* to change. `signals_from_analysis` — which rebuilds the signals from
the stored analysis, and runs on every decision — never restored it. The
decision received an empty map, so the direction could never be computed. The
same omission had silenced `visible_elements`: the framing restriction was inert
the moment the decision re-read the analysis, which is to say always.

Both were added to the domain object and followed as far as the *first* code
path, not as far as the object is **reconstructed**. Two tests now walk the full
round trip: same photo, two moments, and the labels must read "sharper" and
"easier". Removing the restoration makes the first fail.

Worth noting how close this came to shipping: the unit tests passed, the sweep
passed, the audit passed. All of them build signals in memory. Only a journey
through the database exposed it — which is exactly what the end-to-end audit
exists for, and it was not checking this.

## 24. Flagging a piece over-interpreted what the user said — fixed

Testing the script, an interview and a flight both returned *"Change the jacket
for something sharper"* — the opposite of what the demo needs.

The engine was right and the modelling was wrong. Flagging a piece as "more
casual than the rest" subtracted a **flat 0.4** from its formality, which on an
already-casual outfit lands on the floor at 0.10. A jacket at 0.10 is more
casual than even a flight calls for, so "sharper" was correct — and useless.

The user said *more casual than the rest*, not *as casual as possible*. A
flagged piece now drops **one notch in the scale they were shown**: Dressed up →
In between, In between → Casual. The gap stays wide enough for the verdict to
name the piece, without inventing a claim the user never made.

With the fix, a "Dressed up" look with the jacket flagged reads *sharper* for an
interview and *easier* for a flight — the demo pair works with the flag on.

A general form worth keeping: **an input converted into a number must not say
more than the person did.** The scale shown to the user is the scale their
answer belongs to.

## 25. To arbitrate — product decisions that are yours

### 25.1 The journey captures no value

The *Ready* screen ends on "Start another moment". The positioning document §10
nonetheless mentions a retail extension: *uncertainty → ONE CHANGE → proof →
conversion*. No hook exists.

Options, by increasing cost: a "where to find a piece like this" link (cheap, but
brushes against the shopping assistant the positioning forbids) · saving the
decision for later (requires an account, which the product deliberately avoids) ·
doing nothing and owning it.

**My recommendation: do nothing for the hackathon.** Rule 10 — add nothing that
dilutes the idea — is worth more than an improvised business hook, and the jury
scores *decision confidence*, not conversion.

### 25.2 No user feedback on the decision

The product rules and never listens. A "that wasn't the right piece" on the final
screen would cost one button and would yield the only data that allows
calibrating the engine on evidence rather than intuition. It is also the first
thing an enterprise buyer will ask for.

Not done: it requires deciding what to measure, and where to store it.

### 25.3 The catalogue remains a crutch

Twelve generated flat shapes. "Try a piece of your own" sidesteps the problem and
is the best real-world use, but the default demo still goes through the
catalogue. Until it is replaced with real photographs, the nominal journey in
live mode fails (`error_editing_failed`).

`scripts/import_garments.py` does the work in one command — from a local folder
or from a manifest of URLs. It needs your images.

For the retail extension of positioning §10, the manifest is what matters: a
retailer already has product visuals online, and their catalogue becomes an
`id → URL` list with no further integration.

### 25.4 The skin signal is almost always absent in real conditions

Skin AI requires a face filling 60% of the width; MIRROR OPS photographs an
outfit. The server-side crop answers the problem, but fails as soon as the face
is under 140 px — a frequent case for a full-length photo. The journey continues
without a skin signal, which is honest, but the Skin AI integration is then
invisible to the jury, which scores it (criterion ① Technological
Implementation).

**To arbitrate**: accept it, or ask for a second close-up shot — which costs a
screen and contradicts the 90-second constraint.

---

## 26. Out of scope — accepted here, blocking in production

| Missing | Why it blocks elsewhere |
|---|---|
| No authentication, anonymous sessions | multi-tenant, GDPR, per-client quotas |
| No funnel telemetry | impossible to measure where people drop out |
| In-memory rate limiting | inoperative beyond one instance |
| No internationalisation | the interface is English only |
| No formal accessibility audit | contrast, tab order and screen readers were designed for, never measured |
| API cost not surfaced | a buyer wants to know the cost per journey |

---

## 27. What holds

The constraint is respected end to end: a single recommendation, never a list,
`NO_CHANGE` possible, no invented value, the fallback admitted in plain words,
the declared gap named before every decision. `scripts/audit_journey.py` verifies
38 invariants on the assembled system, including the on-screen contradictions
that previously only surfaced in use.
