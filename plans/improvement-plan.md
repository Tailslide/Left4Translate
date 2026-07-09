# Left4Translate — Improvement Plan

**Date:** 2026-07-09
**Goal:** Make the app look better, work better, and wind up bug free.
**Scope:** Full review of `src/` (engine), `gui/` (desktop app), config, tests, and CI. Every bug below was confirmed by reading the code, with file/line references so each item can be picked up independently.

This plan supersedes `plans/improvement-suggestions.md` (an earlier pass whose completed items are already merged). Items still open from that document are folded in here.

---

## Phase 0 — Safety net first (CI + regression tests)

Do this before touching bugs, so every later fix lands with proof.

| # | Item | Detail |
|---|------|--------|
| 0.1 | **Add a CI test workflow** | The only workflow is `bump-version.yml`. Add `.github/workflows/ci.yml`: run `pytest` on push/PR (Windows + Linux matrix, Python 3.11/3.12), with `QT_QPA_PLATFORM=offscreen` for the GUI tests. Gate the auto-version-bump on CI passing. |
| 0.2 | **Consolidate tests under `tests/`** | `src/tools/test_*.py` mixes pytest tests with standalone scripts that need live API keys/hardware. Move real unit tests into `tests/`, mark live/hardware ones with `@pytest.mark.live` / `@pytest.mark.hardware` and exclude them by default via `pyproject.toml` pytest config. |
| 0.3 | **Add a linter** | Add `ruff` (fast, zero-config) to CI to catch the unused-variable/shadowing class of bug (several found below). |

---

## Phase 1 — Bug fixes (each with a regression test)

### Critical — features silently broken

1. **Voice target language is ignored — always translates to Spanish.**
   `src/audio/voice_translation_manager.py:109` — `_init_components()` receives the already-scoped `voice_translation` section, then reads `config.get("voice_translation", {}).get("translation", {})`, which is always `{}`. So `target_language` always falls back to `"es"`, and the Settings-tab field `voice_translation.translation.target_language` does nothing. Fix: read `config.get("translation", {})` (the sibling `translation_config` variable on line 108 is already correct but unused). Note `update_config()` (line 383) reads it correctly — the two paths disagree.

2. **Short slang never translates ("si", "va", "nel", "f", "x", "izi", "rip", "tio", "ptm"…).**
   `src/translator/translation_service.py:51` — `is_untranslatable_content()` bails on `len(text) <= 3` and `translate()` checks it (line 287) *before* the slang dictionary is consulted (line 303). Meanwhile `detect_language()` happily reports these as Spanish via the slang dict. Fix: check the slang dictionary before the untranslatable check, and add a regression test for every ≤3-char slang key.

3. **Chat reading silently stops when `console.log` is truncated.**
   `src/reader/message_reader.py:89` — `f.seek(self.last_position)` after the game truncates the log (the README itself recommends `-conclearlog`, and every game restart truncates) leaves `last_position` beyond EOF; `readlines()` returns nothing forever until the file grows past its old size. Fix: if `os.path.getsize(path) < self.last_position`, reset to 0 and re-read. Also handle the file being deleted/recreated (watchdog `on_created`).

4. **Voice on-screen messages never expire with the default config.**
   `src/display/screen_controller.py:271` — expiry pruning only runs when the *controller-wide* `message_timeout > 0`, but the sample config ships `messageTimeout: 0` (keep chat forever) while voice passes a per-message `clear_after=5000`. Result: voice translations and voice *error* messages stick on the Turing screen permanently. Fix: prune any message whose own `expiry` is set, regardless of the global default; keep `expiry=None` messages forever.

5. **Settings tab can wipe config.json.**
   `gui/settings_tab.py:293-296` — on a JSON parse error, `reload()` sets `self._raw = {}` and returns; if the user then hits **Save**, the file is rewritten with only the ~19 form fields — destroying `game.messageFormat` (the chat regex) and the `logging` section, which the engine's `validate_config()` then rejects. Fix: disable Save while the file is unparsable (show an error banner), and write a timestamped `.bak` before every save.

### High — correctness and reliability

6. **`TranslationService` is not thread-safe.**
   The watchdog reader thread and voice worker threads share one instance: `LRUCache` (`translation_service.py:175`) and `RateLimiter.acquire()` (line 19) have unsynchronized read-modify-write. Add a `threading.Lock` around token accounting and cache access.

7. **Every chat message costs two API calls.**
   `src/main.py:249` calls `detect_language()` and then `translate()`. The v2 translate endpoint returns `detectedSourceLanguage` when you omit `source` — a single call can do both. Halves quota usage (relevant: the free tier is 500k chars/month) and removes a failure point. Fold detection into `translate()` and drop the pre-detect in `_handle_message`.

8. **Rate-limit waits happen on the reader callback thread and can spin indefinitely.**
   `translation_service.py:430` (`while not self.rate_limiter.acquire(): sleep(0.1)`) and the retry loop at line 396-397 block the watchdog thread, stalling all chat processing behind one message. Give the wait a deadline (e.g. give up after N seconds, show original text) and log once, not per-tick.

9. **Slang post-substitution can corrupt translations.**
   `translation_service.py:367` — `zip(original_words, translated_words)` assumes the translation has the same word count/order as the source; when it doesn't, words are compared at the wrong indices and substitutions land on wrong positions. Restrict the pass to slang tokens Google left *unchanged* by searching `translated_words` for the token itself rather than zipping by index.

10. **Reader shutdown/startup edge crashes.**
    `message_reader.py:238` — `stop_monitoring()` calls `observer.stop(); observer.join()` even if `start_monitoring()` failed before `observer.start()` → `RuntimeError: cannot join thread before it is started`. Also `on_modified()` (line 53) calls `os.path.samefile()` which raises if the log was deleted between event and check. Guard both.

11. **Speech transcription drops everything after the first utterance.**
    `src/audio/speech_to_text.py:183` — only `response.results[0]` is used; Google returns multiple results for longer clips. Concatenate all `results[*].alternatives[0].transcript`.

12. **"Recording…" state is unreachable in the GUI.**
    `gui/voice_tab.py:146` maps a `recording` state, but the engine never emits it — `VoiceTranslationManager` has no status callback, and `main.py` only emits `armed`/`error`/`idle`. Thread a status callback into the manager (`_on_button_press` → `recording`, release → `armed`, plus `transcribing`) so the pill and tray reflect reality.

### Medium — annoyances and paper cuts

13. **Mic volume check blocks startup for ~2s and grabs the microphone.**
    `src/audio/voice_recorder.py:109` — the constructor records a 2-second test clip synchronously. In the GUI this delays every engine start; it also fires on `update_config`. Make it lazy (first use), move it off the construction path, or make it an explicit "Test mic" action in the Voice tab.

14. **GUI freezes up to ~5s on Stop / quit.**
    `gui/engine_controller.py:85` joins the engine thread (up to 4s) on the GUI thread, and the engine's main loop (`src/main.py:357`) polls `running` at 1s granularity. Use an `threading.Event` with a short wait in the engine loop, and stop the engine from a worker (or `QTimer`-polled join) so the window never blocks.

15. **`VoiceRecorder.update_config` always thinks the device changed.**
    `voice_recorder.py:377` — `_find_device()` rewrites `self.device` from the configured *name* to an *index*, so the next `update_config(device="default")` compares int to str and restarts recording needlessly. Keep the configured name and resolved index in separate fields.

16. **`ConfigManager.get_setting` returns wrong defaults mid-path.**
    `src/config/config_manager.py:158` — a missing intermediate key substitutes `default` and keeps traversing into it. Return `default` immediately when a segment is missing.

17. **`ScreenController.connect` imports from `main`.**
    `screen_controller.py:118` — `from main import __version__` couples the "reusable display library" to the app entrypoint (breaks reuse, risks circular imports in frozen builds). Pass the version string into the constructor.

18. **Modifier keys are accepted in config but never enforced.**
    `src/input/mouse_handler.py:148` — `modifier_keys` is documented, stored, surfaced in config… and a TODO. Either implement with `pynput.keyboard` state tracking or remove it from config/docs until real.

19. **Message dropped instead of displayed when it alone exceeds screen height.**
    `screen_controller.py:234` — a very long message that doesn't fit even on an empty screen is silently discarded. Truncate with an ellipsis instead.

20. **Version drift.**
    README title says v1.2.7, the badge says 1.2.6 (`README.md:7`), and `__version__` lives in `src/main.py:16` independent of `pyproject.toml`. Single-source the version (read from `importlib.metadata` or one constants module) and let bump-my-version touch one place.

---

## Phase 2 — Work better (behavior improvements)

**Engine**
- **Auto-detected source-language display**: surface `detectedSourceLanguage` in the feed/overlay payload (the `locals().get("source_lang")` hack at `src/main.py:289` goes away with item 7).
- **Slang dictionary as data**: move `SPANISH_SLANG_DICT` to `config/slang_es.json`, loaded at startup with the built-in dict as fallback — users can extend it without editing code. (Carried over from the previous plan.)
- **Persistent translation cache** (optional flag): write the LRU cache to disk on shutdown to save quota across sessions.
- **Friendly startup errors**: `setup_logging()` (`src/main.py:30`) reads config.json before the FileNotFoundError guard — a missing config crashes with a traceback before the helpful "copy config.sample.json" message can print. Reorder.
- **Single-instance guard** for the GUI (a second launch focuses the existing window instead of fighting over the serial port and log file).

**Settings tab (biggest usability win)**
- **COM port dropdown** via `serial.tools.list_ports` (with refresh button) instead of a free-text field.
- **Microphone dropdown** via `sounddevice.query_devices()` instead of typing a device name.
- **Language dropdowns** (common Google Translate codes with names) for target/voice/speech languages.
- **Trigger-button dropdown** (left/right/middle/button4/button5) instead of free text.
- **Validate + Test buttons**: "Test translation" (one API round-trip), "Test screen" (connect + splash), "Test mic" (level meter for 2s) — turning the current log-spelunking diagnostics into one-click checks.
- **Apply on save**: offer "Restart engine now?" when saving while running, instead of the current passive "Stop and Start to apply" hint.

**Voice**
- **Live level meter while recording**: wire `VoiceRecorder.on_data_callback` through to the Voice tab so the meter moves during capture, not after (`gui/voice_tab.py` currently shows only the last clip's level).
- **Minimum/maximum clip guards**: ignore <300ms accidental taps; cap clips at ~30s (sync `recognize` has a 60s limit).
- **Clipboard restore option**: optionally restore the previous clipboard contents after N seconds.

**Overlay**
- **Font size controls** (`A-`/`A+` next to opacity) and a **click-through mode** (`WS_EX_TRANSPARENT`) so it can sit over the crosshair area without eating mouse input.
- **Message fade-out timer** (mirror `clear_after`) and **snap-to-edge** when dragged near screen borders.

**Logs tab**
- **Search/filter box** and a **Save to file…** button.

---

## Phase 3 — Look better (visual polish)

- **Light theme parity**: dark mode has a full QSS identity (`gui/styles.py`); Light/System fall back to bare Fusion, so half the widgets lose the product look (`gui/theme.py:61-67`). Build a light token set mirroring `DARK_QSS`, or drop the Light option rather than ship it half-styled.
- **Dashboard feed empty state**: show a hint ("Start the engine and join a game…") in the empty table; today it's just a void.
- **Feed row ergonomics**: word-wrap toggle or row expansion for long messages (currently truncated with tooltip only); a colored team chip in the Type column instead of colored text alone (better accessibility).
- **Header status pills**: add tooltips with the detail string (currently `detail` replaces the label text and can get long, e.g. "Screen: Screen not connected"); consider icons per component.
- **Tab icons** (dashboard/mic/gear/scroll) — cheap, and makes the window read at a glance.
- **Overlay title bar**: replace the text glyphs (`–`, `+`, `⌫`, `✕`) with proper icons and hover tooltips already exist — plus the font-size controls from Phase 2.
- **README/docs**: move the changelog to `CHANGELOG.md`, refresh screenshots after the visual pass, add a Troubleshooting section (COM port busy, mic level, API 403s — the answers already exist as log messages).

---

## Phase 4 — Code quality and structure

- **Logging consistency**: `translation_service.py` logs on the root logger (`logging.debug(...)`) while everything else uses `logging.getLogger(__name__)`; several modules `print()` errors. Standardize on module loggers. (Carried over.)
- **Remove dead/duplicated logic**: `_translate_slang()` checks `lower_text in slang_dict` three times (`translation_service.py:213,235,241`); `_get_slang_translations()` is now a pass-through that can be inlined; `_check_audio_quality` return annotation says `-> None` but returns `str` (`voice_translation_manager.py:406`).
- **Two sources of truth for the chat regex**: `_is_system_message()` hardcodes a chat pattern (`message_reader.py:120`) that must be kept in sync with `config.json`'s `messageFormat.regex`. Derive one from the other, or match against the configured pattern.
- **`setup.py` is a dev bootstrap script, not packaging** — rename to `scripts/dev_setup.py`, and give `pyproject.toml` real `[project]` metadata + entry points (`left4translate`, `left4translate-gui`) so `pip install -e .` works. (Carried over.)
- **Type checking**: the codebase is mostly annotated already; add `mypy` (lenient to start) to CI for `src/`.
- **Docs refresh**: `docs/architecture.md` and `docs/requirements.md` predate the GUI/overlay refactor. (Carried over.)

---

## Suggested sequencing

| Milestone | Contents | Outcome |
|---|---|---|
| **M1 — Safety net** | Phase 0 (CI, test consolidation, ruff) | Every later change is gated by tests |
| **M2 — Bug-free core** | Phase 1 items 1–12 (critical + high), each with a regression test | The advertised features actually work: voice target language, short slang, log truncation, message expiry, config safety, thread safety |
| **M3 — Paper cuts** | Phase 1 items 13–20 + Phase 2 engine/voice items | No startup stalls, no UI freezes, half the API quota |
| **M4 — Settings UX** | Phase 2 settings-tab work (dropdowns, test buttons) | Setup goes from "read the README and logs" to point-and-click |
| **M5 — Visual pass** | Phase 3 + screenshot/docs refresh | Consistent look in both themes, polished overlay |
| **M6 — Structure** | Phase 4 | Maintainable for the next round |

Notes on verification: M2 items are all unit-testable without hardware or live APIs (mock `requests`/`speech`); the reader-truncation and settings-save tests are plain filesystem tests; screen-expiry logic tests can drive `ScreenController` with `display.is_connected` stubbed — the existing `tests/test_voice_screen_guard.py` shows the pattern.
