---
name: CAESAR Course Check
description: A seat monitor that reads like a station on the CTA Purple Line out of Evanston.
colors:
  line-purple: "#4e2a84"
  line-purple-hover: "#3d206a"
  line-purple-night: "#7c52d6"
  line-purple-night-hover: "#8e66e6"
  focus: "#6b3fc0"
  focus-night: "#b9a1ef"
  sign-white: "#f8f8fa"
  sign-sunken: "#eeeef3"
  sign-rule: "#d9d8e2"
  sign-ink: "#17151f"
  sign-muted: "#5c5a6c"
  night: "#0e0d13"
  night-sunken: "#171620"
  night-rule: "#2b2a38"
  night-ink: "#efeef6"
  night-muted: "#a3a1b6"
  ok: "#137a45"
  ok-night: "#4cc88a"
  warn: "#9a5a00"
  warn-night: "#f0b43c"
  bad: "#c0281b"
  bad-night: "#ff7a6c"
typography:
  count:
    fontFamily: "'Helvetica Neue', -apple-system, BlinkMacSystemFont, 'Segoe UI Variable', 'Segoe UI', system-ui, sans-serif"
    fontSize: "46px"
    fontWeight: 700
    lineHeight: 0.9
    letterSpacing: "-0.035em"
    fontFeature: "tnum"
  title:
    fontFamily: "'Helvetica Neue', -apple-system, BlinkMacSystemFont, 'Segoe UI Variable', 'Segoe UI', system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 700
    lineHeight: 1.4
  wordmark:
    fontFamily: "'Helvetica Neue', -apple-system, BlinkMacSystemFont, 'Segoe UI Variable', 'Segoe UI', system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 700
    lineHeight: 1.4
    letterSpacing: "0.005em"
  body:
    fontFamily: "'Helvetica Neue', -apple-system, BlinkMacSystemFont, 'Segoe UI Variable', 'Segoe UI', system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.4
  label:
    fontFamily: "'Helvetica Neue', -apple-system, BlinkMacSystemFont, 'Segoe UI Variable', 'Segoe UI', system-ui, sans-serif"
    fontSize: "11px"
    fontWeight: 600
    lineHeight: 1.4
  mono:
    fontFamily: "ui-monospace, 'SF Mono', Menlo, Consolas, monospace"
    fontSize: "12px"
    fontWeight: 500
    lineHeight: 1.4
    fontFeature: "tnum"
rounded:
  base: "4px"
  pill: "999px"
spacing:
  "1": "4px"
  "2": "8px"
  "3": "12px"
  "4": "16px"
components:
  button-primary:
    backgroundColor: "{colors.line-purple}"
    textColor: "#ffffff"
    rounded: "{rounded.base}"
    padding: "0 16px"
    height: "36px"
  button-primary-hover:
    backgroundColor: "{colors.line-purple-hover}"
  button-outline:
    backgroundColor: "transparent"
    textColor: "{colors.sign-ink}"
    rounded: "{rounded.base}"
    padding: "0 16px"
    height: "36px"
  roundel:
    backgroundColor: "{colors.line-purple}"
    textColor: "#ffffff"
    rounded: "{rounded.pill}"
    padding: "6px 12px"
  field:
    backgroundColor: "{colors.sign-sunken}"
    textColor: "{colors.sign-ink}"
    rounded: "{rounded.base}"
    padding: "0 8px"
    height: "30px"
  header-band:
    backgroundColor: "{colors.line-purple}"
    textColor: "#ffffff"
    height: "44px"
---

# Design System: CAESAR Course Check

## Overview

**Creative North Star: "The Purple Line Platform"**

A 340x520 tray popover dressed as transit wayfinding: a saturated Northwestern-purple band across the top, signage-white (light) or night-platform near-black (dark) ground, a white-on-purple roundel naming the course, and a route strip whose stations carry state. The scene is a glance at a platform sign: which class, is the line running, what is the count, when is the next check. It is recognizable with the text removed: band, roundel, line with stations.

Density is compact and calm. Humanist transit sans with tabular numerals does all the work; colour is spent on one line colour (purple) and three status colours. Light and dark follow the OS and are two times of day on the same platform, not two themes.

**Key Characteristics:**
- Purple band header is the only fully saturated surface; the rest is near-neutral tinted toward violet.
- One line colour (purple) for action, selection, the route and the activity rail.
- Status colours (ok, warn, bad) appear only as the status dot, the alert state, and error text.
- Flat: no elevation shadows, depth by tonal sunken fields and 2px rules.
- Tabular numerals for every count and time.

## Colors

A violet-tinted neutral ground with one purple line colour; day and night each carry their own tuned values rather than inverting.

### Primary
- **Line Purple** (`line-purple`, #4e2a84): header band, roundel, primary button, active tab underline, route fill, train and station rings, activity rail. In dark mode the accent lifts to **Night Line Purple** (`line-purple-night`, #7c52d6) while the band stays #4e2a84.
- **Line Purple Hover** (`line-purple-hover` #3d206a light, `line-purple-night-hover` #8e66e6 dark): primary button hover.
- **Focus Violet** (`focus` #6b3fc0, `focus-night` #b9a1ef): focus rings and focused-field underline.

### Neutral
- **Sign White** (#f8f8fa) ground, **Sign Sunken** (#eeeef3) field fill and hover, **Sign Rule** (#d9d8e2) dividers and the route track, **Sign Ink** (#17151f) text, **Sign Muted** (#5c5a6c) labels, placeholders and secondary text.
- **Night** (#0e0d13) ground, **Night Sunken** (#171620), **Night Rule** (#2b2a38), **Night Ink** (#efeef6), **Night Muted** (#a3a1b6): the dark-mode counterparts.

### Status
- **Ok** (#137a45 / #4cc88a): monitoring dot, alert count and filled route.
- **Warn** (#9a5a00 / #f0b43c): signing in, starting.
- **Bad** (#c0281b / #ff7a6c): captcha needed, error text.

### Named Rules
**The One Line Rule.** Purple is the only brand colour; it marks what is active or actionable. Status colours never decorate and never appear as button fills.
**The Day/Night Pair Rule.** Every semantic colour has a light and a dark value defined together in app.css; new colours are added as a pair and contrast-checked on both grounds.

## Typography

**Display / Body Font:** Helvetica Neue (with -apple-system, BlinkMacSystemFont, Segoe UI Variable, Segoe UI, system-ui, sans-serif)
**Mono Font:** ui-monospace, SF Mono, Menlo, Consolas

**Character:** One humanist sans at tight sizes, bold for hierarchy, mono only for clock times and the activity count.

### Hierarchy
- **Count** (700, 46px, 0.9, -0.035em, tabular): the enrollment number; the loudest element.
- **Title** (700, 15px): status headline (h2).
- **Wordmark** (700, 14px, 0.005em): header band title.
- **Body** (400-500, 13px, 1.4): inputs, tabs, buttons.
- **Secondary** (400, 12px): messages, notes, "enrolled / alert below N", activity entries.
- **Label** (600, 11px, muted): field labels, route-label captions.
- **Mono** (500, 11-12px, tabular): route clock times and activity timestamps (24h, en-GB).

### Named Rules
**The Tabular Rule.** Any number that changes (count, countdown, clock) uses tabular numerals so the layout does not shift between polls.

## Layout

A single column, `max-width: 560px` centred in a browser, full-bleed in the popover (`?view=popover`, fixed 100vh). Header 44px, scrolling main, sticky footer with a 2px rule above. Spacing runs on a 4/8/12/16 scale (`--space-1..4`): 16px outer padding, 12px between blocks, 8px/12px grid gaps. Course fields sit in a 2-column grid. Buttons are 36px tall, fields 30px.

## Elevation & Depth

Flat. Depth comes from tonal steps (ground, sunken field), 2px rules, and the band. The only shadows are small rings used as geometry on route markers (the train gets a 3px ground-coloured halo to separate it from the track) and a focused-field 1px rule ring. Motion is short: 140ms ease-out (`cubic-bezier(.22, 1, .36, 1)`) for state changes, a 2s ping on the monitoring dot, a 520ms scale-in when the terminal station lights; all disabled under `prefers-reduced-motion`.

## Shapes

Small, practical corners: 4px for buttons and fields (fields round top corners only, over a muted bottom rule like a sign slot), full pill (999px) for the roundel and the activity count badge, circles for stations, dots and the train. Tabs and footer are divided by 2px rules.

## Components

### Header band
44px purple band, white 14px bold wordmark left; right side holds a verification status and (popover only) a Quit text button, 12px at 82% white, hover fills 16% white, white focus outline.

### Buttons
- **Shape:** 4px radius, 36px high, 16px side padding, bold.
- **Primary:** line purple fill, white text; hover darkens (`line-purple-hover`). Used for Start monitoring, Open CAESAR, Solve captcha.
- **Outline (Stop, Monitor again):** transparent with a 1.5px inset muted ring, ink text, sunken fill on hover. Stop is deliberately neutral, not red.
- **States:** 1px press nudge, 2px focus outline offset 2px, disabled at 40% opacity.

### Roundel
Pill with the course code (e.g. subject + catalog number), white bold 12px on line purple. One per screen.

### Fields
Sunken fill, 30px high, 1px transparent border with muted bottom rule, 4px top corners. Hover tints 8% purple; focus switches to a 2px focus-violet bottom rule on the ground colour; disabled goes transparent with a dashed bottom rule and keeps full-contrast ink. Placeholders are muted (not faded) at weight 400.

### Tabs
Course | Activity, bold 13px; active has ink text and a 3px purple underline over the 2px rule; arrow keys move between tabs. Activity carries a mono count pill.

### Route strip (signature)
4px track on a rule colour, purple fill, hollow 12px station bullets at each end (3px purple ring), three quarter ticks, and a 10px train that moves left to right with time elapsed since the last check. Labels beneath: Last check (left), Next check countdown (right). On alert, the strip fills in ok green, the terminal station enlarges to a filled 20px green bullet, and the right label reads "Seat / open".

### Activity rail
A 3px purple vertical line with a hollow station dot per entry; mono timestamp then message at 12px.

## Do's and Don'ts

### Do:
- **Do** keep the purple band, roundel and route strip as the three constants of any new screen.
- **Do** use purple (accent) only for what is active or actionable; use status colours only for status.
- **Do** define any new colour as a light/night pair and set it as a CSS custom property in app.css.
- **Do** use tabular numerals for all changing numbers and 24h en-GB clocks.
- **Do** keep placeholders, disabled fields and muted text at the muted token values so they stay legible.
- **Do** disable animation under `prefers-reduced-motion`.

### Don't:
- **Don't** make the Stop button red or fill it with a status colour.
- **Don't** add elevation shadows, gradients or pastel status cards; depth is tonal.
- **Don't** introduce a second brand hue or a neutral-gray accent.
- **Don't** hard-code colour hex values in components when a token exists.

## Known gaps (build carries, not system rules)

- The route strip is time-only; it does not draw count against threshold.
- The alert terminal-station ring is a zero-offset coloured halo (`box-shadow: 0 0 0 4px` at 30% ok), flagged as decoration by the craft floor. Do not reuse it for new surfaces.
- The Windows flyout (`tray_win.py`) and the Windows type fallback (Segoe UI Variable in place of Helvetica Neue) are untested.
- Token drift: `--danger-bg` and `--on-bad` are defined but unused; `#fff`, `#ffffff`, and `--accent-hover` / `--focus` literals are used in the band and button rules rather than named tokens.
