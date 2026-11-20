# Task: a 2048 game in Common Lisp

Write the game 2048 as a text game in Common Lisp for Allegro CL 11.0 (`alisp`, ANSI mode). Write all files in the current directory.

## Project

An ASDF project with these four files, all in the current directory:

| File | Contents |
|---|---|
| `game-2048.asd` | the system `"game-2048"` and a separate system `"game-2048/tests"` that depends on it |
| `package.lisp` | the package `game-2048`, exporting the six functions listed under Interface |
| `game-2048.lisp` | the game, starting with `(in-package :game-2048)` |
| `game-2048-tests.lisp` | your tests, using Allegro CL's built-in `tester` module (package `util.test`) |

- Use only ANSI Common Lisp and Allegro CL's built-in modules (`asdf`, `tester`). No third-party libraries, no Quicklisp.
- Loading the system `"game-2048"` must not start the game or read input.

## Interface

The package `game-2048` exports these six functions, with exactly these arguments and return values.

### The board

A board is a 4×4 two-dimensional array of integers, created with `(make-array '(4 4) ...)`. `(aref board row column)` is one cell. Row 0 is the top row, column 0 is the left column. 0 means an empty cell; any other number is a tile.

### `(slide-row row)`

`row` is a list of 4 integers. `slide-row` slides the row toward its first element and merges tiles by the rules below. It returns two values: a fresh list of 4 integers, and the points gained. It does not modify `row`.

```lisp
(slide-row (list 2 2 2 2))  ; => (4 4 0 0), 8
(slide-row (list 2 2 2 0))  ; => (4 2 0 0), 4
(slide-row (list 0 2 0 2))  ; => (4 0 0 0), 4
(slide-row (list 2 4 8 16)) ; => (2 4 8 16), 0
```

### `(move board direction)`

`direction` is one of the keywords `:left`, `:right`, `:up`, `:down`. `move` slides every row (for `:left` and `:right`) or every column (for `:up` and `:down`) toward that side. It returns three values:

1. a fresh board with the result,
2. the points gained,
3. true if any cell changed, false (`nil`) if the move changed nothing.

`move` does not modify `board`, and it never adds a new tile.

### `(spawn-tile board random-state)`

`random-state` is a Common Lisp random state. `spawn-tile` returns a fresh board equal to `board` plus one new tile in a randomly chosen empty cell. The new tile is 2 with probability 90% and 4 with probability 10%. It does not modify `board`. Take all randomness from `random-state`, for example `(random 16 random-state)`, so the same random state gives the same result. `spawn-tile` is only called on a board with at least one empty cell.

### `(won-p board)`

True if the board contains a 2048 tile, otherwise false.

### `(game-over-p board)`

True if no move in any of the four directions would change the board, otherwise false.

### `(play &key input output random-state)`

Runs the game as a text game. `input` is the stream it reads from, `output` the stream it writes to, `random-state` the random state used for every new tile. Defaults: `*standard-input*`, `*standard-output*` and a fresh random state, `(make-random-state t)`. So `(game-2048:play)` starts a game in the terminal.

## Rules

Standard 2048.

- The game starts with an empty board plus 2 new tiles, placed as by `spawn-tile`. The score starts at 0.
- `play` prints the board and the score at the start and after every turn.
- Each turn, `play` reads one line from `input`:
  - `w` moves up, `a` left, `s` down, `d` right.
  - `q` quits: `play` returns.
  - Any other line is an invalid key: the board stays as it is and no tile spawns.
- At the end of `input`, `play` returns as if it had read `q`.
- A move slides all tiles as far as possible toward the side moved to. Two tiles with the same value that meet merge into one tile with their sum.
- Each tile merges at most once per move. Merging starts from the side being moved toward. Examples, moving left:
  - `[2 2 2 2]` becomes `[4 4 0 0]`.
  - `[2 2 2 0]` becomes `[4 2 0 0]`.
  - `[2 2 4 0]` becomes `[4 4 0 0]` (the new 4 does not merge again in the same move).
  - Moving right, `[2 2 2 0]` becomes `[0 0 2 4]`.
- Each merge adds the value of the new tile to the score: `[2 2 2 2]` moving left gains 4 + 4 = 8 points.
- After a move that changed the board, one new tile spawns (as by `spawn-tile`). After a move that changed nothing, or an invalid key, no tile spawns.
- When the board first contains a 2048 tile, `play` tells the player they won. The player can keep playing.
- When no move would change the board, `play` tells the player the game is over and returns.

## Tests

Write your own tests in `game-2048-tests.lisp`, in a package of their own named `game-2048-tests`. Test `play` by passing string streams, for example `(make-string-input-stream (format nil "a~%q~%"))` and `(make-string-output-stream)`, never with the terminal.
