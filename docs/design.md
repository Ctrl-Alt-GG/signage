# Design: what the screen looks like

This document fixes the visual rules so an agent can build the display page
without taste decisions. Coordinates are in the 1920x1080 design space of
`assets/background.svg`. Everything on screen is dark mode; there is no light
theme.

## 1. The background

`assets/background.svg` is the organizers' artwork. It is a 1920x1080 SVG
with an oversized base field so letterboxed or slightly mis-scaled screens
stay filled. The copy in this repository is the drawing only: the original
file also carried a C2PA `<metadata>` block (a content-credential signature)
that cannot be reproduced by hand without breaking the signature, so it was
left out. If provenance matters, drop the original file over this one; the
drawing is byte-for-byte the same. Do not edit the SVG; the app references
it as a static file.

| Element | Where (x, y, width, height) | Notes |
|---|---|---|
| Base field | whole canvas, fill `#130404` | Oversized rect, covers 3920x3080 around the canvas. |
| Logo (Ctrl-Alt-GG wordmark and GG badge) | about 96, 64, 420, 80 | White text, red `#aa0000` badge. Top-left anchor of the page. |
| URL "ctrl-alt-gg.hu" | about 1635, 110, 188, 29 | Muted `#a89494`, right-aligned to x=1822. |
| Keyboard, four rows | rows start at y 688, 792, 896, 1000 | Hungarian ISO layout, keycaps `#1c0707` on `#260d0d`, legends `#7a4d4d`. |
| Keyboard fade mask | opacity 0 at y=752, 0.3 at y=867, 1 at y=1007 | Keys above y=752 are invisible; they fade in towards the bottom edge. |
| Held keys: G, Ctrl, Alt | G at 698, 792, 97, 97; Ctrl at 100, 1000, 123, 97; Alt at 360, 1000, 123, 97 | Not masked. Red `#770000` caps with `#aa0000` tops and a soft red glow behind them. |
| Content-safe area | 96, 204, 1728, 564 | Dashed guide in the SVG, hidden by default (`display="none"`). |

The safe area is the only region content may use: x from 96 to 1824, y from
204 to 768. Above it sits the logo row; below it the keyboard starts to show
and the lit G key draws the eye. Nothing text-like goes outside the safe area,
ever. A DOM test enforces this (section 9).

## 2. Stage and scaling

The display page is a fixed 1920x1080 "stage" scaled to the viewport:

```css
.stage {
  position: absolute; left: 50%; top: 50%;
  width: 1920px; height: 1080px;
  transform: translate(-50%, -50%) scale(var(--stage-scale, 1));
  transform-origin: center;
  background: #130404 url("/static/signage/background.svg") center / cover no-repeat;
  overflow: hidden;
}
```

A few lines of JavaScript set `--stage-scale` to
`min(innerWidth / 1920, innerHeight / 1080)` on load and on resize. The page
body is `#130404` so letterbox bars match the artwork. Every layout then uses
absolute pixel values inside the stage; no responsive breakpoints are needed
and screenshots are reproducible.

Inside the stage, the safe area is one container:

```html
<main class="safe" style="position:absolute; left:96px; top:204px; width:1728px; height:564px;">
```

## 3. Tokens

Mirror these in the Tailwind 4 `@theme` block of the app stylesheet. The
brand values are the ones shared by the homepage, Care and Spawn; the surface
values come from the artwork.

```css
@import "tailwindcss";
@source "../templates/**/*.html";

@theme {
  --font-sans: "Inter", system-ui, "Segoe UI", Roboto, "Noto Sans", sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, "Cascadia Mono", Consolas, monospace;

  --color-brand-300: #ff7676;
  --color-brand-400: #f14848;
  --color-brand-500: #dd2525;
  --color-brand-600: #aa0000;
  --color-brand-700: #770000;
  --color-brand-800: #560000;
  --color-accent-400: #e8b923;
  --color-accent-500: #c8960c;

  --color-field: #130404;
  --color-key: #1c0707;
  --color-key-top: #260d0d;
  --color-ink: #ffffff;
  --color-ink-muted: #a89494;
  --color-ink-dim: #7a4d4d;

  --color-surface: color-mix(in srgb, #ffffff 6%, transparent);
  --color-surface-border: color-mix(in srgb, #ffffff 10%, transparent);

  --radius-card: 24px;
  --radius-pill: 9999px;
  --shadow-card: 0 2px 4px rgb(0 0 0 / 0.3), 0 20px 50px rgb(0 0 0 / 0.35);
}
```

Fonts are self-hosted, never fetched from a CDN: the venue may be offline.
Use `@fontsource-variable/inter` (both `latin` and `latin-ext` subsets; Hungarian
needs `ő` and `ű`) and `@fontsource-variable/jetbrains-mono`, copied into
static files at build time. Fall back to system fonts if the files are missing;
the layout must not depend on exact metrics.

Semantic colours:

| Use | Token |
|---|---|
| Titles, body text | `ink` |
| Kickers, footers, clock | `ink-muted` |
| Separators, inactive dots | `ink-dim` |
| Primary accent, highlight schedule rows, live dot, urgent takeover | `brand-600` (text on it: white) |
| Break schedule rows, warning announcements | `accent-400` (text on it: `field`) |
| Cards | `surface` fill, `surface-border` 1px border, `radius-card` |

## 4. Type scale

Base size is for 1920 wide; the stage scales everything together.

| Role | Size / line height | Weight | Max lines | Notes |
|---|---|---|---|---|
| Display title (hero, countdown) | 112 / 1.05 | 800 | 2 | `text-wrap: balance`, letter-spacing -0.02em |
| Title (list, split, qr, live) | 72 / 1.1 | 800 | 1 | Truncate with ellipsis if longer |
| Column title | 48 / 1.15 | 700 | 1 | |
| Body (hero) | 44 / 1.3 | 500 | 3 | |
| List item | 40 / 1.3 | 500 | 2 | Six items max |
| Kicker | 32 / 1.2 | 600 | 1 | Uppercase, letter-spacing 0.12em, `ink-muted` |
| Footer, meta, clock | 30 / 1.2 | 500 | 1 | `ink-muted` |
| Credentials (SSID, password) | 64 / 1.2 mono | 600 | 1 | Tabular numerals |
| Countdown digits | 160 / 1 mono | 700 | 1 | Tabular numerals |
| Stacked English line | 70 percent of the Hungarian role | 500 | same | `ink-muted` |

Nothing readable is smaller than 28px in stage space. Numbers use
`font-variant-numeric: tabular-nums`. Hyphenation is off. No all-caps body
text; the only shouted word is "STAFF" in the safety slide.

## 5. Layouts

All layouts live inside the safe area (1728x564). Padding is 48px on each
side unless stated. "Card" means the surface token set from section 3.

### `hero`

```
+----------------------------------------------------------------------+
| KICKER                                                               |
| Display title up to two lines                                        |
| Body up to three lines, 44px                                         |
|                                                     [stacked EN line]|
+----------------------------------------------------------------------+
```

Left aligned, vertically centred as a block. In `stacked` mode the English
title follows the Hungarian title at 70 percent size in `ink-muted`, and the
English body follows the Hungarian body the same way. Max width 1400px for
the text block so lines stay readable.

### `list`

```
+-------------------------+--------------------------------------------+
| KICKER                  | 1  Item text up to two lines               |
| Title                   | 2  Item text                               |
|                         | 3  Item text                               |
| footer (muted)          | 4  Item text                               |
|                         | 5  Item text                               |
|                         | 6  Item text                               |
+-------------------------+--------------------------------------------+
```

Left column 560px wide (kicker, title, optional footer at the bottom). Right
column holds up to six items, 40px, with a 48px-wide number or icon in
`brand-600`. Items are spaced evenly in the available height. With four or
fewer items the font may grow to 44px.

### `split`

```
+------------------------------------+-----------------------------------+
| Column title A                     | Column title B                    |
| - item                             | - item                            |
| - item                             | - item                            |
| - item                             | - item                            |
| - item                             | - item                            |
+------------------------------------+-----------------------------------+
Title above both cards (72px); the two cards are 824px wide each with a 32px gap.
```

Each column is a card with a 48px column title and up to four items at 38px.

### `qr`

```
+--------------------------------------------------+-------------------+
| KICKER                                           |                   |
| Title                                            |   [ QR 360x360 ]  |
| - item          (up to six, 38px)                |                   |
| - item                                           |   label (30px)    |
+--------------------------------------------------+-------------------+
```

QR panel is a white 420x420 card with the code at 360px inside (32px quiet
zone), the label under it in `ink-muted`. QR codes are generated server-side
as SVG with error correction level M; never load them from an external
service. Left block takes the remaining 1240px.

### `credentials`

Hero-style title at the top left, then two mono lines in a card
(`Hálózat: SSID` and `Jelszó: ...` at 64px), the Wi-Fi QR (`WIFI:T:WPA;S:...;P:...;;`)
in a 420px white card on the right, and the note line (44px) under the card.
If the SSID is still `CHANGE-ME` the slide is excluded from rotation and the
admin shows a warning; never put a placeholder on the wall.

### `now_next`

```
+----------------------+-----------------------+-----------------------+
| MOST                 | KÖVETKEZIK            | KÉSŐBB                |
| 20:00                | 22:00                 | 22:15                 |
| Indul a CS2-verseny  | CS2-díjátadó          | Egy kis hülyülés...   |
| [Counter-Strike 2]   | note                  | [Garry's Mod]         |
+----------------------+-----------------------+-----------------------+
Title (72px) above the three cards; footer (guideline disclaimer) under them.
```

"Now" is the latest entry whose time is at or before the current time, "Next"
the first entry after now, "Later" the one after that. Two entries sharing a
time (the 20:00 pair) render in the same card, stacked. Cards use the row
type accent on their left border (6px): play `brand-600` at 60 percent, break
`accent-400`, highlight `brand-600` full with a soft glow. Empty state replaces
the three cards with the `empty` text at 44px.

### `schedule`

A single-column timeline: the current entry plus the next seven, each a row
with the time (mono 40px, accent colour), a dot on a vertical rail, the title
(40px), the label pill (30px) and the note (30px muted) when present. Rows
that are over are not shown. Footer carries the disclaimer. Same accents as
`now_next`.

### `servers`

Up to eight cards in a 4x2 grid, 400x230 each, 32px gaps. Card header 64px
tall in the game colour from `content/games.yaml` with the game short name;
body shows the server name (36px, two lines max) and the player count
(mono 44px, bottom right) as `online / max`, or `max: N` when the upstream
reports no count. Cards are ordered by the fourth octet of the first address,
like Projectile's own list. More than eight servers: show eight, footer says
"+N további a servers.ctrl-alt-gg.hu oldalon" / "+N more at servers.ctrl-alt-gg.hu".
No addresses, no player names: they are too small to read from a distance and
Projectile's own wall already shows them.

### `tournament`

Title row, then three sections stacked left to right:

```
+--------------------------+--------------------------+-----------------+
| MOST JÁTSZANAK           | KÖVETKEZŐ MECCSEK        | EREDMÉNYEK      |
| Team A        vs  Team B | 20:30  Team C vs Team D  | A 16 : 9  B     |
| round label, started hh  | 21:00  Team E vs Team F  | C 13 : 16 D     |
| (live dot, pulsing)      | 21:30  ...               | ...             |
+--------------------------+--------------------------+-----------------+
```

Live matches (up to two) fill the left card with team names at 44px and a
pulsing `brand-600` dot. Upcoming lists up to four with start times. Results
lists up to three with scores in mono. A section with nothing to show renders
its label and a short muted line, never an empty box. Footer links to Bracket.

### `streams`

Up to four cards in a row, 400px wide: 16:9 thumbnail (from the Streams API
`thumbnail_url`, served through the signage host as a proxy so the kiosk never
needs direct access), channel name (36px), an "audio" badge for audio-only
channels. Only `status == "live"` channels appear. Empty state uses the
`empty` text centred at 44px.

### `countdown`

Kicker, display title, then four mono blocks (days, hours, minutes, seconds)
at 160px with 32px labels beneath, then the body line. Days block is hidden
when zero. Updates every second from the client clock; the server only sends
the target timestamp.

## 6. Chrome around the slides

- Clock: `HH:MM` in the venue time zone, 44px mono, `ink-muted`, anchored
  to the safe area's top-right corner (right edge x=1824, baseline about
  y=240). The current slide's layout must leave the top-right 240x60 free;
  all layouts above already do because their first row is left-aligned.
- Language indicator: a 30px pill ("HU" or "EN") left of the clock, visible
  only in `alternate` mode.
- Progress: a 4px bar along the bottom edge of the safe area (y 764 to 768)
  filling from left to right over the slide's duration, `brand-600` at 60
  percent opacity. It tells the room a change is coming without a jolt.
- Announcement bar (`takeover: false`): 80px tall, pinned to the bottom of
  the safe area, pushing the slide content to a 204 to 680 band (the layouts
  shrink their vertical spacing; fonts stay). Fill: `surface` for info,
  `accent-400` for warning (text in `field`), `brand-600` for urgent. Text at
  36px, one line, no scrolling. Both languages stacked when the text is short
  enough to fit, otherwise alternate every 8 seconds.
- Takeover (`takeover: true`): replaces the slide area with a card filling
  the safe area, level colour as a 12px left border and a tinted fill, the
  text at 72px (two lines max), both languages stacked. Stays until the
  announcement window ends, then rotation resumes where it left off.
- Offline dot: when the player cannot refresh its bundle for more than
  60 seconds, a 16px `ink-dim` dot appears at the safe area's top-left
  corner. Nothing else changes; the last good bundle keeps rotating.

## 7. Motion

- Slide change: 400 ms crossfade, nothing slides in from the side.
- Live dot: 1 Hz opacity pulse.
- Countdown digits: no flip animation, they just change.
- Honour `prefers-reduced-motion`: crossfade becomes a cut, the pulse stops.
- No marquee, no auto-scrolling lists. If content does not fit, show less.

## 8. Readability rules

1. Minimum text size 28px in stage space; body text 40px or larger.
2. Six bullets per slide at most, two lines per bullet at most. Truncate
   with an ellipsis rather than overflow; the lint in `scripts/render_content.py`
   caps the item count, the template caps the lines with `line-clamp`.
3. Contrast at least 7:1 for text on the field or on cards (white on
   `#130404` is about 18:1; `ink-muted` on `#130404` is about 8.3:1; `ink-dim`
   is decoration only, never text).
4. One idea per slide. A slide that needs a second screen is two slides.
5. Hungarian first. In `alternate` mode the Hungarian pass comes first; in
   `stacked` mode Hungarian is the large line.
6. No emoji in text. Icons come from an SVG set the agent vendors into the
   repo (Lucide is fine) and are rendered inline, in `brand-600` or
   `ink-muted`.

## 9. QA that must exist

- A Playwright script (`scripts/screenshots.py`, Chromium, 1920x1080,
  `deviceScaleFactor` 1) that opens `/display/main/?preview=<slide_id>&lang=<hu|en>`
  for every slide in `content/slides.yaml` in both languages and writes PNGs
  to `docs/screenshots/`. Run it before any PR that touches templates or CSS
  and commit the PNGs.
- A DOM test in the same run: every element with visible text must have its
  bounding box inside the safe area rectangle (96, 204, 1824, 768) in stage
  coordinates, with a 2px tolerance. The clock and progress bar are the only
  allowed exceptions, and they too stay inside the rectangle.
- A test that no text node overflows its container (`scrollWidth` and
  `scrollHeight` within `clientWidth` and `clientHeight`).
