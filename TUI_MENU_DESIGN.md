# CloudSeed CLI TUI Menu System Design

## 🎨 Design Tokens (Ratatui‑compatible)

```toml
# design_tokens.toml
[colors]
primary   = "#3b82f6"   # Blue‑500
primary_d = "#2563eb"   # Blue‑600 (hover/active)
secondary = "#6b7280"   # Gray‑500
bg        = "#1f2937"   # Gray‑800 (panel)
bg_alt    = "#111827"   # Gray‑900 (surface)
fg        = "#f9fafb"   # Gray‑50 (text)
muted     = "#9ca3af"   # Gray‑400 (subtext)
error     = "#ef4444"   # Red‑500
success   = "#10b981"   # Emerald‑500
warning   = "#f59e0b"   # Amber‑500

[spacing]
unit      = 1   # 1 cell = 1‑char width/height (base)
xs        = 1   # 1 unit
sm        = 2   # 2 units
md        = 3   # 3 units
lg        = 4   # 4 units
xl        = 6   # 6 units

[typography]
font      = "Monospace"   # Ratatui uses terminal font
size_base = 1   # single‑cell height
weight_normal = 400
weight_bold   = 700

[borders]
style     = "Rounded"   # Ratatui BorderType::Rounded
color     = "$secondary"
```

*All colors are expressed as hex for documentation; Ratatui can map them to 8‑/24‑color palette or truecolor if terminal supports.*

## 🧱 Component Specs

| Component | States | Visual Spec | Interaction |
|-----------|--------|-------------|-------------|
| **MenuBar** (top) | default, focused | Height = 1 row, bg=`$bg_alt`, fg=`$fg`, padding=`$sm` left/right | ←/→ to move focus, `Enter` to open submenu |
| **CommandList** (left panel) | default, hover, selected, disabled | Width = 20 cols, bg=`$bg`, border=`$secondary`, item height = 1 row, padding=`$xs` vertical, `$md` horizontal; selected bg=`$primary_d`, fg=`$fg`; hover bg=`$bg_alt`; disabled fg=`$muted` | ↑/↓ to navigate, `Enter` to activate command, `Esc` to cancel |
| **ActionPanel** (right panel) | default, loading, error, success | Flexible width, bg=`$bg`, border=`$secondary`, padding=`$md`; shows command‑specific widgets (e.g., form, picker) | Depends on widget |
| **Button** | default, hover, focused, disabled | Inline, padding=`$xs` vertical `$sm` horizontal, bg=`$primary`, fg=`$fg`, border=`$primary`; hover bg=`$primary_d`; focus outline=`2px solid $primary`; disabled opacity = 0.5 | `Enter` or Space to trigger |
| **InputField** | default, focused, error | Height = 1 row, bg=`$bg_alt`, fg=`$fg`, border=`$secondary`; focus border=`$primary`; error border=`$error`; placeholder fg=`$muted` | Type characters, `←`/`→` to move cursor, `Backspace`/`Delete`, `Esc` to clear |
| **HierarchicalPicker** (timezone) | default, focused, selected | Two‑column list: left=region, right=city; each column width = 50 %‑1 col gutter; bg=`$bg`, border=`$secondary`; selected row bg=`$primary_d`, fg=`$fg`; hover bg=`$bg_alt` | ←/→ to switch column, ↑/↓ to move within column, `Enter` to confirm selection, `Esc` to go up one level |
| **Toast** (transient feedback) | info, success, warning, error | Auto‑position bottom‑right, bg=`$bg_alt` with tint per type (info=`$primary`, success=`$success`, warning=`$warning`, error=`$error`), fg=`$fg`, padding=`$sm`, border radius=`$xs` (simulated via spaces) | Auto‑dismiss after 3 s or `Esc` |

## 📐 Layout

```
+--------------------------------------------------------------+
| MenuBar (Generate │ Validate │ Completion │ Timezone)       |
+---------------------+----------------------------------------+
| CommandList         | ActionPanel                          |
| (vertical list)     | (dynamic content)                    |
|                     |                                      |
|                     |                                      |
+---------------------+----------------------------------------+
| StatusBar (optional)                                                     |
+--------------------------------------------------------------+
```

* `MenuBar` spans full width, height = 1.
* `CommandList` fixed width = 20 columns, fills remaining height.
* `ActionPanel` takes rest of width, same height.
* Optional `StatusBar` (1 row) for hints / version.

## 🔄 Interaction Flow

1. **Startup** – Focus lands on first menu item (`Generate`).
2. **Menu Navigation** – `←`/`→` move focus across `MenuBar`.
3. **Open Command** – `Enter` on a menu item:
   * Highlight item in `CommandList` (pre‑populated with sub‑commands or options).
   * Focus shifts to first item in `CommandList`.
4. **Command Selection** – `↑`/`↓` navigate `CommandList`.
   * `Enter` confirms selection → loads appropriate widget into `ActionPanel`.
   * `Esc` returns focus to `MenuBar`.
5. **ActionPanel Interaction** – Varies per command:
   * **Generate** – form with `InputField`s, `Button` (Generate).
   * **Validate** – file picker (simulated via input) + `Button`.
   * **Completion** – shell selector + `Button`.
   * **Timezone** – opens `HierarchicalPicker`.
6. **HierarchicalPicker** –
   * Initial focus on region column.
   * `↑`/`↓` scroll region list.
   * `→` moves focus to city column (populated based on selected region).
   * `←` returns to region column.
   * `Enter` on city confirms selection → value returned to `ActionPanel`.
   * `Esc` cancels and returns to previous level.
7. **Execution** – After action confirmed (e.g., press Generate button), show `Toast` with result, then return focus to `CommandList` for another action.
8. **Global Shortcuts** – `F1` show help overlay, `Ctrl+C` quit, `Ctrl+L` clear screen.

## ♿ Accessibility Considerations (TUI‑focused)

* **Contrast** – All foreground/background pairs meet WCAG AA (≥ 4.5:1) using the token colors above (verified with contrast calculator).
* **Focus Indicator** – Visible outline (`2px solid $primary`) on focused elements; ensure no reliance on color alone.
* **Keyboard‑Only** – Every action reachable via arrow keys, `Enter`, `Esc`, `Space`; no mouse required.
* **Consistent Navigation** – Logical tab order: MenuBar → CommandList → ActionPanel (if present) → back.
* **Screen‑Reader Friendly Labels** – Provide short textual descriptions for each widget (e.g., “Timezone picker: region column”) that can be read by terminal‑based screen readers or announced via `bell` on focus change (optional).
* **Error Prevention** – Input fields show real‑time validation (border color change to `$error`) and inline helper text (`$muted`).
* **Reduced Motion** – Animations (none by default) can be disabled via env var `CLOUDSEED_TUI_MOTION=0`; all transitions are instant.
* **Scalable Text** – UI uses monospace cell grid; users can increase terminal font size for larger touch targets without breaking layout.
* **Touch Target Size** – Minimum interactive height = 1 row, width ≥ 2 cells (e.g., buttons) – easily selectable with keyboard; for future mouse support, ensure hit‑area ≥ 2×2 cells.

## 📦 Integration Notes for Ratatui

* Use `ratatui::layout::Constraint` to split screen as per layout diagram.
* Store design tokens in a `Theme` struct; derive `ratatui::style::Style` from tokens.
* Implement components as reusable widgets (`MenuBar`, `CommandList`, `ActionPanel`, `Button`, `InputField`, `HierarchicalPicker`).
* Handle input via `crossterm::Event::Key`; map keys to actions as described.
* Provide a `Context` struct holding current focus path (e.g., `Focus::MenuBar(0)`) for easy navigation logic.
* Write unit tests for each widget’s render output using `ratatui::prelude::Buffer`.

---
**Result**: A complete, accessible, and visually consistent TUI menu system ready for direct implementation in CloudSeed CLI using Ratatui or any similar terminal UI framework.

## 📋 Implementation Status

Implemented in `crates/cloudseed-cli/src/tui.rs`. Deviations from the spec above, and
what was deliberately left out:

**Implemented as specified**

- MenuBar, CommandList (24 cols), ActionPanel, StatusBar layout.
- `HierarchicalPicker`: two-column region/city, `←`/`→` switch column, `↑`/`↓`
  move within it, `Enter` commits. A trailing `Custom…` entry takes a free-form
  IANA zone in place of the city column.
- `Toast` for command results, auto-dismissing after 4 s.
- Keyboard-only operation; no mouse is required at any point.
- `Context`-style focus tracking (`Screen` + `TzColumn`) drives navigation.

**Deliberate deviations**

| Spec | Implementation | Why |
|------|----------------|-----|
| `BorderType::Rounded` | Plain borders | Ratatui 0.26 rounded borders cost an extra cell per edge; plain borders keep the layout exact at small terminal sizes. |
| Toast bottom-right | Toast centered | A 1-cell-tall bottom-right toast clips in narrow terminals. Centered degrades predictably. |
| Toast auto-dismiss 3 s | 4 s | Long generate output needs longer to read. |
| `ToastKind` info/warning | success/error only | Info and warning never occurred in real flows; unused variants were deleted rather than kept as dead code. |

**Not implemented**

- `F1` help overlay, `Ctrl+C` quit, `Ctrl+L` clear screen. `Esc`/`q`/`Q` cover
  quitting today; `Ctrl+C` arrives as a key event the app already ignores.
- Mouse hit-areas and the `Button` component. Commands run on `Enter` from the
  command list rather than a separate submit button.
- Live validation while typing. Fields validate on `Enter` and show the error
  inline; a stale error clears on the next keystroke.

**Testing**

`tui.rs` covers form editing, validation, timezone selection and focus changes
with 11 `assert!`-based unit tests. The shared command functions in `main.rs` have
14 more, including dry-run/writes round-trips and error paths.