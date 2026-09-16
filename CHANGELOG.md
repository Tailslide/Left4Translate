# Changelog

## Unreleased

### Fixed
- **Turing screen froze and stopped showing new messages** (usually after the
  PC had been left alone for a while), with chat still being translated and
  logged and no error anywhere. Two things caused it, and neither raised an
  exception:
  * The display loop re-sent the whole 480x320 frame (~300 KB) five times a
    second whether or not anything had changed, keeping the serial link
    saturated. When a write eventually came back short, the Turing library
    swallowed it — `WARNING turing: (Write line) Too fast! Slow down!` is the
    only trace — and the lost bytes left the panel waiting for the tail of a
    bitmap forever, so every later frame was consumed as pixel data and the
    picture never changed again. Frames are now only sent when they actually
    differ (an idle screen sends nothing at all), dropped bytes are detected
    instead of ignored, and the link is rebuilt when they happen.
  * The port is opened with hardware flow control, so a screen that stops
    asserting CTS blocks the write forever and the display thread never comes
    back. A watchdog now aborts a write that has been stuck for 15s and
    reconnects.

  Recovery is logged (`Screen stopped accepting data … - reconnecting`,
  `Screen reconnected`) and reported to the GUI, which shows the **Screen**
  pill amber while it retries (`src/display/turing_display.py`,
  `src/display/screen_controller.py`).
- **The whole app could die silently over a COM port**: the Turing library
  calls `sys.exit(0)`/`os._exit(0)` when it cannot open the screen's port, and
  it reopens the port from inside its own write error handling — so a USB
  dropout could take the app down, or end the display thread with nothing in
  the log. Opening the port is now handled by Left4Translate, which raises an
  error the app can report and recover from (`src/display/turing_display.py`).
- **Settings device combos looked broken**: the ↻ re-scan buttons beside the
  Serial port and Microphone device fields inherited the wide default button
  padding, which crushed the glyph into an unreadable vertical sliver, and the
  combo boxes showed no drop-down arrow at all (styling `QComboBox::drop-down`
  suppresses Qt's native arrow). The re-scan buttons are now compact icon
  buttons that render the glyph cleanly, every combo shows a theme-colored
  drop-down chevron so it reads as a combo box, and clicking re-scan now
  reports how many devices were found instead of silently doing nothing
  (`gui/styles.py`, `gui/settings_tab.py`).
- **Translation failed with 403 `API_KEY_IP_ADDRESS_BLOCKED` on IPv6**: an
  API key restricted to an IPv4 address was rejected because, on a dual-stack
  host, `requests`/urllib3 prefers IPv6 and the call went out over IPv6.
  Outbound Translation API connections are now pinned to IPv4 by default so
  they match the key's restriction. Toggle with the new `translation.forceIPv4`
  config option (default `true`) or the "Force IPv4" checkbox in Settings →
  Translation; set it `false` to allow IPv6 (`src/translator/translation_service.py`).
- **Native crash (access violation) once the dashboard feed filled up**: the
  crash from the earlier GC fix recurred in the field, and both crash logs
  fault at the same place — trimming the oldest feed row (`removeRow`) after
  500 translations, where Qt destroys that row's five C++ `QTableWidgetItem`
  objects. The feed is now a `QTableView` over a plain-Python model
  (`FeedModel`): rows are tuples in a deque, and inserting/trimming rows no
  longer allocates or destroys any per-cell C++ objects, removing the crash
  site entirely (`gui/dashboard_tab.py`).
- **Overlay hardened the same way**: a later crash log caught the same native
  fault while the overlay was constructing a new message QLabel. The overlay
  now keeps a fixed pool of labels and reuses them (set text / toggle
  visibility) instead of destroying and recreating widgets on every
  translation (`gui/overlay_window.py`).
- **Random native crash (access violation) during long GUI sessions**:
  Python's cyclic garbage collector could run on an engine worker thread and
  destroy Qt objects that belong to the GUI thread, corrupting Qt and killing
  the process mid-translation (crash.log showed the fault inside the
  dashboard feed's table update). Automatic GC is now disabled in the GUI and
  collections run from a timer on the GUI thread instead (`gui/gc_guard.py`).
- **Silent exits**: the GUI now installs global crash reporting — uncaught
  errors are written to `logs/app.log`, native faults (Qt, PortAudio, mouse
  hook, serial) to `logs/crash.log`, and an error dialog is shown instead of
  the app just vanishing.
- **Voice target language was ignored** — it always fell back to Spanish
  regardless of `voice_translation.translation.target_language`.
- **Short slang never translated** ("si", "f", "va", "nel", "izi", "rip",
  "tio"): the length check ran before the slang dictionary.
- **Chat monitoring stopped after a game restart**: truncated `console.log`
  (including `-conclearlog`) left the reader stuck past the end of file.
- **Voice messages never left the Turing screen** with the default
  `messageTimeout: 0`; per-message expiry (voice `clear_after`) now works.
- **Settings could destroy config.json**: saving while the file was unparsable
  rewrote it with only the form fields. Save is now blocked until the file
  parses, and every save writes a `config.json.bak` first.
- **Scroll wheel changed settings on hover**: spinboxes/combos now only react
  to the wheel once clicked into.
- **UI froze up to ~5s on Stop/quit** (thread join on the GUI thread); stop is
  now asynchronous and quit has a hard deadline.
- **Double-start after a slow stop** could duplicate the global mouse hook,
  log watcher, serial port, and audio stream; starting is refused until the
  previous engine fully exits.
- Speech-to-text dropped everything after the first pause (only the first
  result was read); results are now concatenated.
- Thread-safety fixes in the shared translation service (rate limiter + cache).
- Blocking log I/O removed from the PortAudio realtime callback.
- Translation/detect API calls now carry a 10-second network timeout.
- Reader shutdown no longer raises when monitoring never started; log-file
  deletion mid-event no longer kills the watchdog thread.
- Messages taller than the screen are shortened with an ellipsis instead of
  silently dropped.
- `ConfigManager.get_setting` returned wrong values when an intermediate key
  was missing.
- README version badge corrected; version is now single-sourced in
  `src/version.py`.

### Added
- **Settings dropdowns**: COM port (live scan + refresh), microphone (live
  scan + refresh), languages, trigger button, clipboard format, speech model.
- **Diagnostics** in Settings: Test translation, Test screen, Test microphone.
- **Restart prompt** when saving config while the engine is running.
- **Live mic level meter** while recording (was: level of the last clip only).
- "Recording…" / "Transcribing…" status states in the GUI.
- **Overlay**: font-size controls (persisted), click-through mode on Windows
  (session-only), snap-to-edge when dragging.
- **Logs tab**: text filter and Save-to-file.
- **Single-instance guard**: a second launch raises the running window.
- **User slang overrides** via `config/slang_es.json` (sample shipped).
- **Optional persistent translation cache** (`translation.persistCache`) to
  save API quota across sessions.
- Voice clips shorter than 0.3s are ignored; clips longer than 55s keep the
  most recent 55s (synchronous recognition limit).
- One API call per chat message instead of two (translate reports the detected
  source language itself).
- Full light theme (previously fell back to unstyled Fusion).
- CI (pytest + ruff on Linux/Windows) and a consolidated test suite.

### Changed
- The constructor-time 2-second microphone probe is gone (engine starts are no
  longer delayed); use Settings → Diagnostics → Test microphone instead.
- `google-cloud-translate` dependency removed (the REST API is used directly).

## v1.2.7
- Refactored display module to separate reusable TuringDisplay library from Left4Translate-specific ScreenController
- TuringDisplay now supports multiple hardware revisions (Rev A, B, C, D)
- Added text wrapping, font loading, and drawing helpers to reusable library
- Fixed issue where chat messages weren't showing on the Turing screen at startup
- Added "Registered" to system message prefixes to properly filter out system messages
- Fixed message processing to correctly handle both team chat and regular chat formats
- Improved message filtering to ensure only actual chat messages are displayed

## v1.2.6 and earlier
- Added an always-on-top translation overlay as a software stand-in for the
  Turing Smart Screen, with a `screen.enabled` config flag to run without
  hardware.
- Added the full Windows desktop GUI (PySide6) alongside the console app.

## v1.2.1
- Fixed voice translation error: Corrected parameter name mismatch in TranslationService.translate() call
- Voice translation now correctly passes source_language instead of target_language parameter
- Fixed target language configuration in voice translation manager to use the correct configuration section
- Changed default clipboard format to only copy translated text instead of both original and translated

## v1.2.0
- Initial release with voice translation feature
