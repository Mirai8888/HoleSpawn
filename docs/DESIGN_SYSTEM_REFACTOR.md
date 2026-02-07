# Design System Refactor: AI-Generated Psychological Capture

## Goal

Single "AI design system" pipeline that all builders use. Design is an **active component of the psychological trap**, not just aesthetic dressing.

---

## Core framing (system prompt)

**Frame design as capture, not decoration:**

- **Do:** "Generate a design system that will psychologically capture this person. The aesthetic should feel personally resonant, guide their attention to engagement hooks, and make exploration feel more natural than leaving."
- **Not:** "Generate a beautiful design that matches their style."

The design system generator must be explicitly prompted to create aesthetics that **function as psychological traps**, not just "look nice."

---

## Required additions to the design system generator prompt

### 1. Aesthetic manipulation tactics

- Use **colors/typography** that create specific emotional states (e.g. calm vs anxious, curious vs satisfied) based on profile.
- Design **information hierarchy** that guides attention to hooks identified in the profile (obsessions, pet_peeves, susceptibilities).
- Create **visual rhythm** that matches their browsing patterns so they stay in flow state (doom_scroller vs deep_diver vs scanner, etc.).
- Use **whitespace/density** to overwhelm or soothe as appropriate to the profile (content_density_preference, intensity, sentiment).

### 2. Friction design

- **Navigation:** Feel natural for exploration, but unclear for exit.
- Make "back" or "home" **less visually prominent** than "deeper" links (e.g. lower contrast, smaller, or de-emphasized).
- Use **visual weight** to pull toward content and deeper paths, not toward leaving.

### 3. Uncanny personalization

- When the profile has **strong aesthetic signals**, lean into them so it feels "made for me."
- Use **visual callbacks** to themes in their posts without being obvious (color, phrasing in UI, tone of microcopy).
- Create a feeling of **"this understands me"** through design choices, not just surface style match.

---

## Implementation checklist (for agent)

When implementing the expanded design system generator:

- [ ] **Framing:** System prompt opens with the capture framing above (psychological capture, exploration > leaving).
- [ ] **Aesthetic manipulation:** Prompt includes the four tactics (emotional states, hierarchy → hooks, visual rhythm, whitespace/density).
- [ ] **Friction design:** Prompt specifies navigation that favors exploration over exit, and de-emphasized back/home vs prominent "deeper" links and content pull.
- [ ] **Uncanny personalization:** Prompt instructs AI to lean into strong signals, use subtle visual callbacks, and create "understands me" through design.
- [ ] All of this is **in addition to** the existing refactor requirements (layout, color, typography, interactions, density, quality control, profile fields).

---

## Reference: full refactor scope

- Single canonical design system in `pure_generator` (or dedicated module); all builders use it.
- Profile fields: color_palette, layout_style, typography_vibe, browsing_style, content_density_preference, visual_preference, communication_style, sentence/word length; add engagement style if needed.
- AI outputs: layout system (scattered/structured/flowing → CSS), colors (with contrast constraints), typography, interactions, information density.
- Quality control: examples of beautiful sites, WCAG AA, typographic scale, hierarchy, web-safe fonts, accessibility.
- Architecture choice (feed/hub/wiki/thread/gallery) stays separate; visual design of that architecture comes from AI.
- Remove `aesthetic.py` lookups; everything goes through AI generation.

This document adds the **psychological trap** requirements to that scope.
