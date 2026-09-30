# Manual tests (for Nathan)

Agents: when you need one of these tests, tell Nathan which protocol to run, which files to use, and
exactly what to report. Keep each test under ~10 minutes. Record the result in `docs/STATUS.md`.

## A. Open a .vox file in MagicaVoxel

1. Open MagicaVoxel 0.99.7.2, then `File > Open` (or drag the file into the window) and pick the file
   given by the agent (in `workspace/`).
2. Check and report:
   - Does it open without an error message?
   - Press **TAB** (scene mode) and open the scene outline: are the object names the expected ones?
   - Do the colors look as described by the agent?
   - Palette: are the material names shown next to the palette rows? (If hidden, click the small arrow at
     the top of the palette.)
3. **Do not save** the file from MagicaVoxel (it would rewrite it in its own format).
4. Report: OK / not OK, plus a screenshot if something looks wrong.

## B. Test a mod in Teardown

1. Copy the mod folder given by the agent from `workspace/` into `Documents\Teardown\mods\`.
2. Start Teardown, open **Mods**, check the mod is listed and enabled.
3. Start a sandbox map, open the **spawn menu**, find the mod's category and spawn the object.
4. Check what the agent asked for (typical vehicle checklist):
   - Does it appear, at the right size, right way up, facing forward?
   - Do the wheels touch the ground (not floating, not sunk)? Do they turn and steer?
   - Can you enter and drive it? Does it tip over easily?
   - Break it (hammer, gun, explosives): do glass/metal parts react as expected?
5. Quit the game, then send the agent the end of the log file:
   `%LOCALAPPDATA%\Teardown\log.txt` (or let the agent read it).
6. Report: answers to the checklist, screenshots (`Documents\Teardown\screenshots`) if useful.
7. Remove the mod folder from `Documents\Teardown\mods\` afterwards if the agent says so.
