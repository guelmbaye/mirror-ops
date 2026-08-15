# MIRROR OPS — interface

Next.js 14 (App Router), strict TypeScript, mobile-first (390 × 844).
The interface holds **no decision logic**: it displays what the engine chose, and
never talks to YouCam directly.

## Running it

```bash
npm install                     # from the repository root
npm run dev                     # http://localhost:3000
```

The API must be running alongside (`make dev-api`) and must allow
`http://localhost:3000` in `CORS_ORIGINS`.

| Variable | Role |
|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | MIRROR OPS API root (default `http://localhost:8000`) |
| `NEXT_PUBLIC_SITE_URL` | public site origin, for social images |

Both are **compiled into the client bundle**: changing them requires a rebuild.
No YouCam key appears here, and none ever should.

## Screens

```
/            Home         the thesis and a single button
/moment      Moment       occasion + goal + time
/look        Your look    camera or upload, what you're wearing, how dressed up
/analyzing   Analyzing    analysis then decision, orchestrated server-side
/one-change  ONE CHANGE   the fit verdict, then the change
/compare     Before/After the visual proof · "Keep it / Try another"
/ready       Ready        the way out
```

One API call carries each transition, in the order enforced by the backend state
machine. Skipping a step returns `409`: the interface then sends the user back to
the missing screen rather than showing a technical error.

## Structure

```
src/
├── app/                   one folder per screen + layout, error, not-found
├── components/
│   ├── Stage.tsx          shared frame: header, step rail, back link
│   ├── Action.tsx         buttons (primary / ghost / quiet)
│   ├── ChoiceGroup.tsx    single-select choice groups
│   ├── CameraCapture.tsx  real photo capture, with an honest fallback
│   ├── Verdict.tsx        ★ verdict plate, impact needle, ledger
│   ├── BeforeAfter.tsx    comparator (mouse, touch, keyboard)
│   └── Notice.tsx         failure states and the "simulated" stamp
└── lib/
    ├── api.ts             typed client, normalised errors
    ├── session.ts         session id + input-aware idempotency keys
    ├── photo.ts           the photo lives in memory, for one journey
    └── format.ts          display conversions
```

Types come from `@mirror-ops/types` (a mirror of the Pydantic schemas) and copy
from `@mirror-ops/config`. The backend returns stable identifiers; how to name
them to the user belongs to the interface.

## Implementation choices

**The authoritative state lives server-side.** Only the session id is kept in the
browser (`sessionStorage`). Every screen re-reads `GET /sessions/{id}`: a refresh
recovers exactly the same decision — which matters as much for a demo as for
trust.

**Nothing is pre-selected on *Your look*.** The outfit chips start empty, so an
unticked piece means the user went through the list and said no — not that they
skipped the question. Mixed defaults previously made the product announce
"Add a jacket" to someone wearing one: a default is a claim made on the user's
behalf, acceptable for a preference and never for a fact about them.

**The photo does not persist.** It lives in an in-memory module for the length of
one journey. Tab reloaded before the analysis → the screen says so and asks
again, rather than analysing something else.

**The analysing screen cannot stall.** It is the only screen that chains two
asynchronous calls before navigating, so the only one that can freeze if a
promise never returns. A watchdog re-reads the session state every 8 seconds and
resumes wherever the server actually is: decision already made → go; analysis
done but decision missing → request it; nothing after four attempts → an explicit
message rather than a spinner. It is a plain `GET`: no API credit consumed.

**A double-click doesn't cost two credits.** The expensive calls (analysis,
try-on) carry an `Idempotency-Key` derived from the session **and the inputs**.
Identical inputs keep the same key; a corrected outfit produces a new one, so the
correction is genuinely applied.

**The fallback is visible.** When a preview comes from local composition
(`simulated: true`), the Before/After screen says so. A result that didn't come
from YouCam never pretends it did.

## Trying your own piece

The **"Try a piece of your own"** button appears on **two** screens, deliberately.
It first existed only on Before/After — that is, behind a successful try-on. But
that is exactly when the catalogue fails that someone needs it, and they are then
on the decision screen. An escape hatch placed behind the stuck door is not one.

## "Try another" without betraying ONE CHANGE

The positioning calls for a "Keep it / Try another" screen. Rule 3 nonetheless
forbids turning ONE CHANGE into a list of recommendations. The two hold together
on one condition: **"Try another" swaps the piece, never the decision.**

The button only queries the catalogue within the category the engine chose, it
disappears when no alternative exists, and the idempotency key includes the
garment — retrying the same piece costs nothing, switching costs one preview, at
the user's explicit request and never automatically.

## Design

The palette derives from the logo. The rule predates it and does not move: **one
signal colour, reserved for what changes.**

| Token | Value | Use |
|---|---|---|
| `--porcelain` | `#F0F1F3` | background |
| `--ink` | `#0B1A2E` | primary text (the logo navy pushed to a text value) |
| `--navy` | `#0A326E` | logo blue · "Before" tag |
| `--graphite` | `#5C6675` | secondary text |
| `--mercury` | `#D3D6DC` | rules, tracks, the "kept" state |
| `--signal` | `#C1005C` | **the change**, in type |
| `--signal-bright` | `#E6006E` | **the change**, in strokes (needle, rules) |
| `--sky` | `#46AAE6` | the **before** state, and nothing else |

Two magenta values because the brand magenta yields 4.05:1 on porcelain — below
the AA threshold. Small caps of 10 to 12 px therefore use the darkened version
(5.4:1); the brand magenta stays on strokes, where text contrast does not apply.

The logo's light blue has exactly one job: marking the **before** state on the
impact needle. It is the counterpoint to the signal, not decoration — which gives
the brand's third tone real work rather than an ornamental role.

Fraunces for the verdict, Archivo for the interface, JetBrains Mono for data. The
families load remotely, with an explicit fallback stack: offline, the layout
holds.

The signature element is the **impact needle**: one axis, a thin tick for the
current state, a solid one for the projected state. The movement *is* the
information — neither a radial gauge, nor a radar, nor a dashboard. Below it, the
**ledger**: one offset line in magenta for the piece that changes, all the others
in mercury marked "Keep". The visual hierarchy carries the product thesis.

Quality floor: responsive down to 320 px, visible keyboard focus,
`prefers-reduced-motion` honoured, comparator drivable with arrow keys.

### Brand assets

| File | Use |
|---|---|
| `public/logo-mirror-ops.png` · `@2x` | header (26 px) and home (44–54 px) |
| `public/mark-mirror-ops.png` | the symbol alone, for material outside the app |
| `src/app/icon.png` · `favicon.ico` · `apple-icon.png` | icons, auto-detected by Next |
| `src/app/opengraph-image.png` · `twitter-image.png` | share preview (1200 × 630) |
| `src/app/manifest.ts` | web app manifest (home-screen install) |

Icons sit on a porcelain background rather than transparency: the symbol's navy
would vanish against dark browser chrome.

## Verifying

```bash
npm run test          # vitest + jsdom
npm run typecheck     # application AND tests, two passes
npm run build         # production build
```

`next build` type-checks everything `tsconfig.json` includes. Tests and their
configuration are therefore **excluded**: without that, compiling for production
would fail as soon as a development dependency is missing — the normal case on a
build server. They stay verified separately, with the same rigour, through
`tsconfig.test.json`.

`tests/analyzing.test.tsx` mounts the analysing screen **under StrictMode** —
the development conditions where React mounts, unmounts and remounts every
component. That sequence once silently killed the orchestration. A fourth test
deliberately blocks the analysis promise and checks that the watchdog recovers
the journey from server state.
