# RuscaPinball — manual

1980s-style pinball for RuscaLinux. The table, “Amethyst”, is seen in perspective like the pinball games of the 1980s home computers: the tilted table with its cabinet, raised bumpers and flippers, the scores at the sides. Original table, graphics and sounds.

The screen alternates the high scores with a demo game; press Space to play.

## Launch

From the applications menu (search for "RuscaPinball") or from a terminal with `ruscapinball`.
Options: `--fullscreen`, `--version`.

## Controls

| Action | Keyboard | Gamepad |
|---|---|---|
| Left flipper | Z, Left Shift, Left Ctrl, ← | LB |
| Right flipper | M, Right Shift, Right Ctrl, → | RB |
| Launch | hold Space or ↓, then release | A or B |
| Nudge | N | Y |
| Pause | P (Esc while paused ends the game) | Start |
| TV effect | F2 | — |
| Sound | F3 | — |
| Fullscreen | F11 | — |
| About | I (from the menu) | — |
| Quit | Esc from the menu, Ctrl+Q always | — |

## Rules

- Three balls per game. During the first 6 seconds after launch a lost ball is returned (blinking lamp above the flippers).
- **Bumpers**: 100 points, rising up to 500 by completing the lanes; the lights on the arc at the top left show their value.
- **Centre target** (the oval between the two upper bumpers): 750 points and one step of bonus; it lights the **lightning**, which doubles the bumpers for 15 seconds (it blinks fast in the last 3).
- **Dome** (below the centre bumper): bounces the ball back towards the bumpers, 50 points.
- **Bonus button** (the star above the ring): 300 points and one step of bonus, two with the lightning lit.
- **Inlanes** (between the wall and the slingshots): 500 points each; both lit: 2,500 points and bonus multiplier.
- **Top lanes** (four): 500 points each; the flippers move the lit lamps. All four lit: 5,000 points and richer bumpers.
- **Bonus trap** (top left, the arrow points at it): a ball rolling over it slowly enough is caught, then kicked back towards the bumpers. 2,000 points plus 1,000 per multiplier step, and three steps of bonus.
- **Drop targets** (left): 500 points each; all down: 2,500 points and bonus multiplier (up to 5×, shown at the right; the inlanes raise it too).
- **R-U-S-C-A letters** (right): 1,000 points each; they stay lit between balls. Completed: 15,000 points and an extra ball.
- **Bonus ring** (centre): lanes, targets and letters light the lamps 1–9 and 10, 20, 30, up to 39. At the end of each ball the lamps go out one by one, 1,000 points each, times the multiplier.
- **SPECIAL**: with the bonus at 39 the SPECIAL lamp lights up; the bonus trap then gives 25,000 points and an extra ball.
- Extra balls: at most two per game and one per ball. The **EXTRA BALL** lamp at the left stays lit until you play it.
- **Tilt**: nudging helps, but three quick nudges switch the flippers off and the bonus is lost.

## Data

High scores in `~/.local/share/ruscapinball/scores.json`, settings in `~/.config/ruscapinball/settings.json`.
The game does not use the network.

License GNU GPL 3.0 — www.ruscalinux.org — info@ruscalinux.org
