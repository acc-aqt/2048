;;;; Hidden tests for the game-2048 task: spawn-tile with a fixed random state. They use only the
;;;; public interface from spec.md and call it as (funcall 'game-2048:name ...),
;;;; so names the implementation exports cannot clash with the helpers here.
;;;; `lisp-check --test` loads game-2048.asd from this file's directory first.

(eval-when (:compile-toplevel :load-toplevel :execute)
  (require :tester))

(defpackage :game-2048-hidden-spawn-tile-tests
  (:use :cl :util.test))

(in-package :game-2048-hidden-spawn-tile-tests)

;;; An error inside one assertion counts as that assertion failing, so the
;;; remaining assertions still run. TEST reads this variable when it is
;;; macroexpanded, so set it at compile time too.
(eval-when (:compile-toplevel :load-toplevel :execute)
  (setf *error-protect-tests* t))

;;; Boards are written as 4 lists of 4 values, the top row first.

(defun board (rows)
  "Return a fresh 4x4 board with the values in ROWS."
  (make-array '(4 4) :initial-contents rows))

(defun rows (board)
  "Return the values of BOARD as 4 lists of 4 values, the top row first."
  (loop for row below 4
        collect (loop for column below 4
                      collect (aref board row column))))

(defparameter *mixed*
  '((2 0 2 4)
    (2 4 0 4)
    (0 4 2 8)
    (4 4 2 8)))

(defparameter *top-left*
  '((2 4 0 0)
    (4 2 0 0)
    (0 0 0 0)
    (0 0 0 0)))

;;; Every call gets its own copy of one fixed random state.

(defparameter *seed* (make-random-state nil))

(defun seeded ()
  "Return a fresh copy of the fixed random state *SEED*."
  (make-random-state *seed*))

(defun new-tiles (rows result)
  "Return the (row column value) cells where RESULT differs from ROWS, for
cells that were empty in ROWS, and :changed for any other difference."
  (loop for row below 4
        for before in rows
        append (loop for column below 4
                     for old in before
                     for new = (aref result row column)
                     unless (eql old new)
                       collect (if (zerop old) (list row column new) :changed))))

(defun spawned (rows)
  "Return the new tiles that SPAWN-TILE adds to the board ROWS."
  (new-tiles rows (funcall 'game-2048:spawn-tile (board rows) (seeded))))

(defun one-new-tile-p (rows)
  "True if SPAWN-TILE adds exactly one tile of value 2 or 4 to an empty cell
of ROWS and leaves every other cell as it was."
  (let ((tiles (spawned rows)))
    (and (= 1 (length tiles))
         (consp (first tiles))
         (member (third (first tiles)) '(2 4))
         t)))

(defparameter *empty*
  '((0 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))

(defparameter *one-gap*
  '((2 4 2 4)
    (4 2 4 2)
    (2 4 0 4)
    (4 2 4 2)))

(test t (one-new-tile-p *empty*))
(test t (one-new-tile-p *mixed*))
(test t (one-new-tile-p *top-left*))
(test 2 (first (first (spawned *one-gap*))))
(test 2 (second (first (spawned *one-gap*))))
(test t (one-new-tile-p *one-gap*))

(defun rows-after-spawn (rows)
  "Return ROWS as the board passed to SPAWN-TILE looks after the call."
  (let ((board (board rows)))
    (funcall 'game-2048:spawn-tile board (seeded))
    (rows board)))

(defun fresh-after-spawn-p (rows)
  "True if SPAWN-TILE returns a different array than it was given."
  (let ((board (board rows)))
    (not (eq board (funcall 'game-2048:spawn-tile board (seeded))))))

(test *mixed* (rows-after-spawn *mixed*) :test #'equal)
(test t (fresh-after-spawn-p *mixed*))
(test t (equal (spawned *mixed*) (spawned *mixed*)))
(test t (equal (spawned *empty*) (spawned *empty*)))

;;; Over many spawns from one random state, every cell gets a tile and about
;;; 10% of the tiles are 4s. The bounds are more than 5 standard deviations
;;; wide, so a correct implementation fails them with negligible probability.

(defparameter *spawn-count* 1000)

(defun many-spawns ()
  "Return the new tiles of *SPAWN-COUNT* spawns on an empty board, all
drawn from one copy of the fixed random state."
  (let ((state (seeded)))
    (loop repeat *spawn-count*
          append (new-tiles *empty*
                            (funcall 'game-2048:spawn-tile (board *empty*) state)))))

(defun cells-hit (tiles)
  "Return how many different cells TILES cover."
  (length (remove-duplicates (mapcar (lambda (tile) (subseq tile 0 2)) tiles)
                             :test #'equal)))

(defparameter *many-spawns* (ignore-errors (many-spawns)))

(test *spawn-count* (length *many-spawns*))
(test 16 (cells-hit *many-spawns*))
(test t (<= 50 (count 4 *many-spawns* :key #'third) 150))
(test *spawn-count* (count-if (lambda (value) (member value '(2 4)))
                              *many-spawns* :key #'third))
