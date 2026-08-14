VISUAL PINBALL CABINET - FRONT-END + TABLE MANAGER
==================================================

Two small python desktop apps for a Visual Pinball X (VPX) cabinet whose 4K
playfield monitor runs landscape in Windows but is mounted in portrait.

FILES
-----
  pinball_frontend.py   The cabinet front-end (read-only launcher).
  table_manager.py      Admin tool that writes config.json + tables.json.
  config.json           App settings (managed by the Table Manager).
  tables.json           Curated table list (managed by the Table Manager).
  requirements.txt      Python dependencies (PyQt6).
  VPX_LAUNCH_NOTES.txt  Research on launching VPX and returning cleanly.

INSTALL
-------
  python -m venv .venv
  .venv\Scripts\activate            (Windows)
  pip install -r requirements.txt

STEP 1 - CURATE (Table Manager)
-------------------------------
  python table_manager.py

  * Browse to your VPinballX.exe, Tables folder and Media folder.
  * Choose rotation (90 or 270), list font size and window size (3840x2160).
  * Press "Rescan Folders" - it lists every *.vpx alphabetically, scans the
    media folder, and auto-matches images to tables by file name.
  * Edit display names, tick/untick Visible, or "Pick Image..." to override a
    preview manually.
  * Press "Save" to write config.json and tables.json.

STEP 2 - RUN THE CABINET (Front-End)
------------------------------------
  python pinball_frontend.py

  Controls:
    UP / DOWN     move the selection
    RIGHT         launch the highlighted table in VPX
    LEFT          quit the front-end

  The front-end shows white table names on black at your configured font size,
  with a preview image on the right (max 1/3 width, scaled to fit). It starts
  on the first visible table, rotates the whole UI 90/270 degrees, and hides
  itself while VPX runs, restoring after a short grace period when you exit.

Both apps create default config.json / tables.json on first run if missing.

Why two apps? The front-end stays tiny and instant because it only reads two
JSON files. All editing - paths, rotation, font size, table curation, media
matching - lives in the Table Manager, so nothing in the play experience can
be changed by accident.


VPX LAUNCH RESEARCH NOTES
=========================

Goal: launch a table from the front-end, then return cleanly when the player
exits, without the arrow keys colliding between the game and the launcher.

1. COMMAND LINE
---------------
Visual Pinball X is launched with the table file passed to the -Play argument:

    VPinballX.exe -Play "C:\vPinball\Visual Pinball\Tables\MyTable.vpx"

Notes:
  * Modern VPX builds (10.7+, 10.8, and the VPinballX_GL/64 variants) use the
    dash form "-Play". Older builds also accepted the slash form "/play".
    This is exposed as "vpx_launch_arg" in config.json so you can switch if
    your build differs.
  * Use the 64-bit exe name your install ships (e.g. VPinballX64.exe or
    VPinballX_GL.exe) - just point vpx_exe_path at it.
  * Related args that front-ends sometimes use:
      -Minimized "table.vpx"   start minimized
      -PovEdit / -Pov          point-of-view editor (not for launching)
  * This is the same pattern used by the big front-ends: PinballX, PinUP
    Popper, LaunchBox (Visual Pinball is added as an emulator whose default
    command line is essentially -Play plus the .vpx ROM), and RetroBat
    (its visualpinball config invokes VPinballX with the table path).

2. GRACEFUL EXIT / RETURN OF FOCUS
----------------------------------
There is NO special "exit" flag required. VPX runs as a normal process and
terminates when the player quits the table (the in-VPX Exit key, default is the
key bound in VPX's Keys settings - often the right-flipper + start, or ESC ->
Exit). When that process ends, our launcher's QProcess.finished signal fires
and the front-end restores itself.

Sequence the front-end uses:
  a. showMinimized() the front-end window so VPX owns the display.
  b. QProcess.start(vpx_exe, ["-Play", table_path]).
  c. Wait for QProcess.finished (non-blocking, keeps the UI responsive).
  d. Wait exit_grace_ms (default 500 ms) so Windows settles focus.
  e. showFullScreen(), raise_(), activateWindow(), setFocus().

3. KEYBOARD CONFLICT (up/down/left/right)
-----------------------------------------
The same arrow keys drive both the front-end (navigate/launch/exit) and are
used in-game. This is NOT a conflict in practice because:
  * While VPX runs it grabs exclusive fullscreen keyboard input, and the
    front-end window is minimized and unfocused, so it receives no key events.
  * After VPX exits we wait exit_grace_ms before re-enabling the front-end so a
    key still held from the last moment of play does not leak into navigation.
If you ever run VPX windowed (non-exclusive) the safest fix is to keep it in
exclusive fullscreen, which -Play does by default.

4. DISPLAY ROTATION
-------------------
The cabinet's 4K playfield panel is set to landscape in Windows but mounted in
portrait. The front-end draws its UI at the logical portrait size and rotates
the whole widget tree 90 or 270 degrees (config.rotation_angle) via a
QGraphicsView so it reads upright. VPX itself handles its own rotation in its
video settings, independent of the front-end.
