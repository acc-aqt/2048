# Task: slide-row

Write a tiny Common Lisp project for Allegro CL 11.0 (`alisp`, ANSI mode) in the current folder. Use only standard Common Lisp and Allegro's built-in `asdf` and `tester` modules. Do not use Quicklisp or any other library.

## Files

Put all four files directly in the current folder, not in a subfolder.

| File | Contents |
|---|---|
| `slide-row.asd` | ASDF system `"slide-row"` with `:serial t` and the components `"package"` then `"slide-row"`. A second system `"slide-row/tests"` that depends on `"slide-row"` and `(:require "tester")`, with the component `"slide-row-tests"`. |
| `package.lisp` | `(defpackage :slide-row (:use :cl) (:export #:slide-row))` |
| `slide-row.lisp` | Starts with `(in-package :slide-row)` and defines the function `slide-row`. |
| `slide-row-tests.lisp` | Your own tests: `(require :tester)` inside `eval-when`, a package `:slide-row-tests` that uses `:cl`, `:util.test` and `:slide-row`, and top-level `(test ...)` forms. |

## The function

`(slide-row row)`

- `row` is a list of 4 non-negative integers. 0 means an empty cell.
- Slide every tile toward the first element of the list, as in the game 2048.
- Two equal tiles that end up next to each other merge into one tile with twice the value.
- Each tile merges at most once per call. Merging starts from the first element.
- Return two values: a fresh list of 4 integers (padded with 0 at the end), and the points gained, which is the sum of the values of the new merged tiles.
- Do not modify `row`.

| Call | First value | Second value |
|---|---|---|
| `(slide-row '(0 0 0 0))` | `(0 0 0 0)` | 0 |
| `(slide-row '(0 0 0 2))` | `(2 0 0 0)` | 0 |
| `(slide-row '(2 2 0 0))` | `(4 0 0 0)` | 4 |
| `(slide-row '(2 2 2 0))` | `(4 2 0 0)` | 4 |
| `(slide-row '(2 2 2 2))` | `(4 4 0 0)` | 8 |
| `(slide-row '(4 4 8 8))` | `(8 16 0 0)` | 24 |

## Done

The task is done when `lisp-check package.lisp`, `lisp-check slide-row.lisp` and `lisp-check --test slide-row-tests.lisp` each print OK.
