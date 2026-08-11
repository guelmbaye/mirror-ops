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
— Casual / In between / Dressed up. It stays optional: without it the product
still decides, with less certainty, and says so.

Result:

| | wedding | interview | dinner | travel |
|---|---|---|---|---|
| **casual** | MISMATCH 51 | MISMATCH 50 | ALMOST 63 | **FIT 73** |
| **in between** | ALMOST 67 | ALMOST 67 | **FIT 77** | ALMOST 70 |
| **dressed up** | **FIT 84** | **FIT 85** | Close enough 72 | ALMOST 63 |

The diagonal reads at a glance, including *overdressed for travel* — a mismatch
in its own right.

## 2. A contradiction on screen — fixed

The same measurement revealed `travel` showing **FIT 73** *and* "Change the
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

## 4. The live try-on is verified

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

## 9. To arbitrate — product decisions that are yours

### 9.1 The journey captures no value

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

### 9.2 No user feedback on the decision

The product rules and never listens. A "that wasn't the right piece" on the final
screen would cost one button and would yield the only data that allows
calibrating the engine on evidence rather than intuition. It is also the first
thing an enterprise buyer will ask for.

Not done: it requires deciding what to measure, and where to store it.

### 9.3 The catalogue remains a crutch

Twelve generated flat shapes. "Try a piece of your own" sidesteps the problem and
is the best real-world use, but the default demo still goes through the
catalogue. Until it is replaced with real photographs, the nominal journey in
live mode fails (`error_editing_failed`).

`scripts/import_garments.py` does the work in one command — from a local folder
or from a manifest of URLs. It needs your images.

For the retail extension of positioning §10, the manifest is what matters: a
retailer already has product visuals online, and their catalogue becomes an
`id → URL` list with no further integration.

### 9.4 The skin signal is almost always absent in real conditions

Skin AI requires a face filling 60% of the width; MIRROR OPS photographs an
outfit. The server-side crop answers the problem, but fails as soon as the face
is under 140 px — a frequent case for a full-length photo. The journey continues
without a skin signal, which is honest, but the Skin AI integration is then
invisible to the jury, which scores it (criterion ① Technological
Implementation).

**To arbitrate**: accept it, or ask for a second close-up shot — which costs a
screen and contradicts the 90-second constraint.

---

## 10. Out of scope — accepted here, blocking in production

| Missing | Why it blocks elsewhere |
|---|---|
| No authentication, anonymous sessions | multi-tenant, GDPR, per-client quotas |
| No funnel telemetry | impossible to measure where people drop out |
| In-memory rate limiting | inoperative beyond one instance |
| No internationalisation | the interface is English only |
| No formal accessibility audit | contrast, tab order and screen readers were designed for, never measured |
| API cost not surfaced | a buyer wants to know the cost per journey |

---

## 11. What holds

The constraint is respected end to end: a single recommendation, never a list,
`NO_CHANGE` possible, no invented value, the fallback admitted in plain words,
the declared gap named before every decision. `scripts/audit_journey.py` verifies
38 invariants on the assembled system, including the on-screen contradictions
that previously only surfaced in use.
