# Left4Translate — Improvement Plan

**Date:** 2026-07-09 · **Executed:** 2026-07-10
**Goal:** Make the app look better, work better, and wind up bug free.

> **Status: implemented.** Every milestone (M1–M6) has been executed on this
> branch; see `CHANGELOG.md` (Unreleased) for the user-facing summary and the
> commit history for per-item details. All 25 numbered bugs are fixed with
> regression tests (124 tests, plus ruff, running in the new CI workflow).
> Deliberately deferred, in case a later pass wants them:
> - Tab icons (needs proper icon assets; Qt's standard pixmaps look worse
>   than no icons).
> - Overlay message fade-out timer (the overlay gained font-size controls,
>   click-through, and snap-to-edge instead).
> - Clipboard restore-after-N-seconds option.
> - mypy in CI (ruff landed; mypy adds little until annotations are tightened).
> - `pip install -e .` entry points — would require repackaging the flat
>   `src/` imports into a proper package, which PyInstaller specs and every
>   import site depend on; too invasive for this pass.
**Scope:** Full review of `src/` (engine), `gui/` (desktop app), config, tests, and CI. Every bug below was confirmed by reading the code, with file/line references so each item can be picked up independently.

This plan supersedes `plans/improvement-suggestions.md` (an earlier pass whose completed items are already merged). Items still open from that document are folded in here.

---

## User-reported issues (2026-07-10)

Three reports from real use, triaged against the code:

**A. "Sometimes the app exits and closes with no errors."**
Diagnosis: the GUI is a windowed PyInstaller build (`Left4Translate-gui.spec:133`, `console=False`) and the codebase installs **no `sys.excepthook`, no `threading.excepthook`, and no `faulthandler`** — so any uncaught Python exception on a background thread, and any native fault (Qt DLLs, PortAudio, the pynput Win32 mouse hook, pyserial), terminates the process with nothing shown anywhere. `StreamTee` mirrors stderr into the Logs tab widget only — tracebacks never reach `logs/app.log`, and the tab dies with the process. On top of that, two code paths make crashes *likelier*: the close/stop path blocks the GUI thread ("Not Responding" → Windows or the user kills it, which looks identical to a silent exit), and a timed-out stop leaks a live engine whose duplicated global mouse hook / file watcher / audio stream can destabilize a second start. → **Phase 1 items 21–24** (new).

**B. "The scroll wheel changes settings values too easily — even hovering without focus."**
Diagnosis: Qt default behavior. `QSpinBox` and `QComboBox` accept wheel events on hover (`Qt.WheelFocus`), so scrolling the Settings page silently edits whatever field the cursor crosses — baud rate, brightness, cache size. → **Phase 1 item 25** (new; it's a data-corrupting UX bug, not polish).

**C. "Some settings need comboboxes rather than typed values."**
Already planned as the Phase 2 "Settings tab" block (COM port, microphone, languages, trigger button as dropdowns) — now **confirmed by user request and pulled forward into milestone M3**.

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
    `gui/engine_controller.py:85` joins the engine thread (up to 4s) on the GUI thread, and the engine's main loop (`src/main.py:357`) polls `running` at 1s granularity. Folded into item 22 below — the freeze is also a likely cause of the reported "silent exits" (frozen window gets killed).

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

### User-reported (2026-07-10) — silent exits and settings-form input

21. **No crash reporting at all — silent exits are by construction.** *(root cause of report A)*
    Nothing installs `sys.excepthook`, `threading.excepthook`, `faulthandler`, or a Qt message handler, and the GUI exe has no console. Fix, in `gui/app.py` at startup:
    - `faulthandler.enable(open(logs/crash.log, "a"))` — captures native faults (Qt, PortAudio, pynput hook, pyserial) with a Python-level stack.
    - `sys.excepthook` + `threading.excepthook` → log the traceback to `logs/app.log`, and (GUI thread only, via a queued signal) show a "Left4Translate hit an unexpected error" dialog instead of vanishing.
    - `qInstallMessageHandler` → route Qt warnings/fatals into `logging`.
    - Point `StreamTee` at the log file as well as the Logs tab, so stderr output survives the process.
    After this lands, any remaining crash stops being "no errors" and becomes a stack trace in `logs/crash.log` we can actually fix.

22. **Close/stop blocks the GUI thread → "Not Responding" → killed app looks like a silent exit.** *(contributor to report A; supersedes the wording of item 14)*
    `MainWindow.closeEvent` (`gui/main_window.py:301`) and the tray Quit path call `EngineController.stop()`, which joins the engine thread for up to 4s (`gui/engine_controller.py:85`) while the engine itself takes up to 1s to notice (`src/main.py:357-358`) plus screen/reader teardown. A user (or Windows) killing the frozen window is indistinguishable from a crash. Fix: event-based engine loop (`threading.Event.wait()`), and make quit asynchronous — hide the window immediately, stop the engine on a worker, exit the app when the thread confirms (with a hard deadline).

23. **Timed-out stop leaks a live engine; the next Start doubles global native hooks.** *(contributor to report A)*
    `EngineController.stop()` nulls `_thread`/`_engine` even when the 4s join times out — the old engine keeps running with its pynput **global mouse hook**, watchdog observer, serial port, and audio stream. `start()` then happily builds a second engine: two low-level Win32 mouse hooks and duplicated native resources are a classic hard-crash recipe. Fix: refuse to start while the old thread is alive (surface "still stopping…"), keep the reference until the thread actually exits.

24. **Blocking I/O inside the PortAudio realtime callback.** *(contributor to report A)*
    `VoiceRecorder._audio_callback` (`src/audio/voice_recorder.py:308-329`) does numpy math and synchronous `logger.info` file writes inside the audio callback — explicitly warned against by sounddevice; can glitch or abort the stream host-side. Fix: callback only copies the buffer; level computation/logging move to the consumer thread (which also gives the Voice tab its live meter, Phase 2).

25. **Scroll wheel edits settings on hover without focus.** *(report B)*
    Every `QSpinBox`/`QComboBox` in the Settings form (`gui/settings_tab.py:213-231`) — and the header mode combo — accepts wheel events while merely hovered, so scrolling the page mutates values silently; combined with Save, wrong values land in `config.json` unnoticed. Fix: shared `NoScrollSpinBox`/`NoScrollComboBox` subclasses (or one event filter) in `gui/widgets.py`: `Qt.StrongFocus` + ignore wheel events unless the widget has focus. Use them everywhere in the Settings tab and header.

---

## Phase 2 — Work better (behavior improvements)

**Engine**
- **Auto-detected source-language display**: surface `detectedSourceLanguage` in the feed/overlay payload (the `locals().get("source_lang")` hack at `src/main.py:289` goes away with item 7).
- **Slang dictionary as data**: move `SPANISH_SLANG_DICT` to `config/slang_es.json`, loaded at startup with the built-in dict as fallback — users can extend it without editing code. (Carried over from the previous plan.)
- **Persistent translation cache** (optional flag): write the LRU cache to disk on shutdown to save quota across sessions.
- **Friendly startup errors**: `setup_logging()` (`src/main.py:30`) reads config.json before the FileNotFoundError guard — a missing config crashes with a traceback before the helpful "copy config.sample.json" message can print. Reorder.
- **Single-instance guard** for the GUI (a second launch focuses the existing window instead of fighting over the serial port and log file).

**Settings tab (biggest usability win — comboboxes explicitly requested by user, report C)**
- **COM port dropdown** via `serial.tools.list_ports` (with refresh button) instead of a free-text field.
- **Microphone dropdown** via `sounddevice.query_devices()` instead of typing a device name.
- **Language dropdowns** (common Google Translate codes with names, editable for exotic codes) for `translation.targetLanguage`, `voice_translation.translation.target_language`, and `voice_translation.speech_to_text.language`.
- **Trigger-button dropdown** — exactly five valid values exist (`left`/`right`/`middle`/`button4`/`button5`, see `src/input/mouse_handler.py:42-50`); free text just invites typos that silently fall back to button4.
- **Clipboard format dropdown** (`translated`/`original`/`both`) and **speech model dropdown** (`default`/`command_and_search`/`phone_call`/`video`) — both are closed sets today typed as free text.
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
| **M1 — Safety net** | Phase 0 (CI, tests, ruff) **+ item 21 (crash reporting) + item 25 (wheel guard)** | Every later change is gated by tests; the next "silent exit" leaves a stack trace in `logs/crash.log`; scrolling Settings can no longer corrupt values. Item 21 moves first deliberately — it converts the unreproducible report A into actionable crash logs while the rest of the work proceeds. |
| **M2 — Bug-free core** | Phase 1 items 1–12 (critical + high) **+ items 22–24 (stop-path freeze, double-start leak, audio-callback I/O)**, each with a regression test | The advertised features actually work, and the known crash/freeze contributors are gone |
| **M3 — Settings UX** | Phase 2 settings-tab work (dropdowns per report C, test buttons) | Setup goes from "read the README and logs" to point-and-click |
| **M4 — Paper cuts** | Phase 1 items 13–20 + Phase 2 engine/voice/overlay items | No startup stalls, half the API quota, live mic meter |
| **M5 — Visual pass** | Phase 3 + screenshot/docs refresh | Consistent look in both themes, polished overlay |
| **M6 — Structure** | Phase 4 | Maintainable for the next round |

Notes on verification: M2 items are all unit-testable without hardware or live APIs (mock `requests`/`speech`); the reader-truncation and settings-save tests are plain filesystem tests; screen-expiry logic tests can drive `ScreenController` with `display.is_connected` stubbed — the existing `tests/test_voice_screen_guard.py` shows the pattern.
