;;;; Hidden tests for the game-2048 task. They use only the public interface
;;;; from spec.md. They call it as (funcall 'game-2048:name ...), so names the
;;;; implementation exports cannot clash with the helpers here, and a missing
;;;; function fails its assertions instead of the whole file at compile time.
;;;; `lisp-check --test` loads game-2048.asd from this file's directory first.

(eval-when (:compile-toplevel :load-toplevel :execute)
  (require :tester))

(defpackage :game-2048-hidden-tests
  (:use :cl :util.test))

(in-package :game-2048-hidden-tests)

;;; An error inside one assertion counts as that assertion failing, so the
;;; remaining assertions still run and the failure count stays meaningful.
;;; TEST reads this variable when it is macroexpanded, so set it at compile
;;; time too.
(eval-when (:compile-toplevel :load-toplevel :execute)
  (setf *error-protect-tests* t))

(defun slide (&rest row)
  "Return the two values of SLIDE-ROW on ROW as a list."
  (multiple-value-list (funcall 'game-2048:slide-row row)))

;;; slide-row

(test '((0 0 0 0) 0) (slide 0 0 0 0) :test #'equal)
(test '((2 0 0 0) 0) (slide 0 0 0 2) :test #'equal)
(test '((2 4 8 16) 0) (slide 2 4 8 16) :test #'equal)
(test '((2 4 0 0) 0) (slide 0 2 0 4) :test #'equal)
(test '((4 0 0 0) 4) (slide 2 2 0 0) :test #'equal)
(test '((4 0 0 0) 4) (slide 2 0 2 0) :test #'equal)
(test '((16 0 0 0) 16) (slide 8 0 0 8) :test #'equal)
(test '((2048 0 0 0) 2048) (slide 0 1024 0 1024) :test #'equal)
(test '((4 4 0 0) 8) (slide 2 2 2 2) :test #'equal)
(test '((4 2 0 0) 4) (slide 2 2 2 0) :test #'equal)
(test '((4 4 2 0) 4) (slide 2 2 4 2) :test #'equal)
(test '((4 4 0 0) 4) (slide 2 2 4 0) :test #'equal)
(test '((4 4 0 0) 4) (slide 4 2 2 0) :test #'equal)
(test '((8 16 0 0) 24) (slide 4 4 8 8) :test #'equal)
(test '((8 4 0 0) 8) (slide 4 4 4 0) :test #'equal)

(defun row-after-slide (row)
  "Return ROW after calling SLIDE-ROW on it."
  (funcall 'game-2048:slide-row row)
  row)

(test '(2 2 0 4) (row-after-slide (list 2 2 0 4)) :test #'equal)

;;; Boards are written as 4 lists of 4 values, the top row first.

(defun board (rows)
  "Return a fresh 4x4 board with the values in ROWS."
  (make-array '(4 4) :initial-contents rows))

(defun rows (board)
  "Return the values of BOARD as 4 lists of 4 values, the top row first."
  (loop for row below 4
        collect (loop for column below 4
                      collect (aref board row column))))

(defun moved (rows direction)
  "Return the three values of MOVE on the board ROWS as a list. The third
value becomes T or NIL."
  (multiple-value-bind (result points changed)
      (funcall 'game-2048:move (board rows) direction)
    (list (rows result) points (if changed t nil))))

(defun rows-after-move (rows direction)
  "Return ROWS as the board passed to MOVE looks after the call."
  (let ((board (board rows)))
    (funcall 'game-2048:move board direction)
    (rows board)))

(defun fresh-after-move-p (rows direction)
  "True if MOVE returns a different array than it was given."
  (let ((board (board rows)))
    (not (eq board (funcall 'game-2048:move board direction)))))

;;; move in each direction

(defparameter *mixed*
  '((2 0 2 4)
    (2 4 0 4)
    (0 4 2 8)
    (4 4 2 8)))

(test '(((4 4 0 0) (2 8 0 0) (4 2 8 0) (8 2 8 0)) 20 t)
      (moved *mixed* :left) :test #'equal)
(test '(((0 0 4 4) (0 0 2 8) (0 4 2 8) (0 8 2 8)) 20 t)
      (moved *mixed* :right) :test #'equal)
(test '(((4 8 4 8) (4 4 2 16) (0 0 0 0) (0 0 0 0)) 40 t)
      (moved *mixed* :up) :test #'equal)
(test '(((0 0 0 0) (0 0 0 0) (4 4 2 8) (4 8 4 16)) 40 t)
      (moved *mixed* :down) :test #'equal)

;;; merging starts from the side moved toward

(test '(((0 0 2 4) (0 0 0 0) (0 0 0 0) (0 0 0 0)) 4 t)
      (moved '((2 2 2 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)) :right) :test #'equal)
(test '(((4 0 0 0) (2 0 0 0) (0 0 0 0) (0 0 0 0)) 4 t)
      (moved '((2 0 0 0) (2 0 0 0) (2 0 0 0) (0 0 0 0)) :up) :test #'equal)
(test '(((0 0 0 0) (0 0 0 0) (2 0 0 0) (4 0 0 0)) 4 t)
      (moved '((2 0 0 0) (2 0 0 0) (2 0 0 0) (0 0 0 0)) :down) :test #'equal)

;;; a slide without a merge changes the board and gains no points

(defparameter *single*
  '((0 0 0 0)
    (0 2 0 0)
    (0 0 0 0)
    (0 0 0 0)))

(test '(((0 0 0 0) (2 0 0 0) (0 0 0 0) (0 0 0 0)) 0 t)
      (moved *single* :left) :test #'equal)
(test '(((0 0 0 0) (0 0 0 2) (0 0 0 0) (0 0 0 0)) 0 t)
      (moved *single* :right) :test #'equal)
(test '(((0 2 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)) 0 t)
      (moved *single* :up) :test #'equal)
(test '(((0 0 0 0) (0 0 0 0) (0 0 0 0) (0 2 0 0)) 0 t)
      (moved *single* :down) :test #'equal)

;;; a move that changes nothing

(defparameter *top-left*
  '((2 4 0 0)
    (4 2 0 0)
    (0 0 0 0)
    (0 0 0 0)))

(defparameter *bottom-right*
  '((0 0 0 0)
    (0 0 0 0)
    (0 0 2 4)
    (0 0 4 2)))

(test (list *top-left* 0 nil) (moved *top-left* :left) :test #'equal)
(test (list *top-left* 0 nil) (moved *top-left* :up) :test #'equal)
(test (list *bottom-right* 0 nil) (moved *bottom-right* :right) :test #'equal)
(test (list *bottom-right* 0 nil) (moved *bottom-right* :down) :test #'equal)
(test t (fresh-after-move-p *top-left* :left))

;;; move does not modify its input

(test *mixed* (rows-after-move *mixed* :left) :test #'equal)
(test *mixed* (rows-after-move *mixed* :right) :test #'equal)
(test *mixed* (rows-after-move *mixed* :up) :test #'equal)
(test *mixed* (rows-after-move *mixed* :down) :test #'equal)
(test t (fresh-after-move-p *mixed* :down))

;;; spawn-tile. Every call gets its own copy of one fixed random state.

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

;;; won-p and game-over-p. Their results become T or NIL.

(defun won (rows)
  "Return WON-P of the board ROWS as T or NIL."
  (if (funcall 'game-2048:won-p (board rows)) t nil))

(defun over (rows)
  "Return GAME-OVER-P of the board ROWS as T or NIL."
  (if (funcall 'game-2048:game-over-p (board rows)) t nil))

(defparameter *stuck*
  '((2 4 2 4)
    (4 2 4 2)
    (2 4 2 4)
    (4 2 4 2)))

(defparameter *full-row-merge*
  '((2 4 2 4)
    (4 2 4 2)
    (2 4 4 8)
    (4 2 8 2)))

(defparameter *full-column-merge*
  '((2 4 2 4)
    (4 2 4 2)
    (2 8 2 4)
    (4 8 4 2)))

(defparameter *with-2048*
  '((2 4 2 4)
    (4 2048 4 2)
    (2 4 2 4)
    (4 2 4 2)))

(defparameter *almost*
  '((1024 1024 0 0)
    (512 0 0 0)
    (0 0 0 0)
    (0 0 0 0)))

(test nil (won *empty*))
(test nil (won *almost*))
(test nil (won *stuck*))
(test t (won *with-2048*))
(test t (won '((0 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 2048))))

(test nil (over *mixed*))
(test nil (over *one-gap*))
(test t (over *stuck*))
(test t (over *with-2048*))
(test nil (over *full-row-merge*))
(test nil (over *full-column-merge*))

;;; play, driven through string streams. Only checks that it returns without
;;; an error and writes some output, never what the output says.

(defun play-output (lines)
  "Run PLAY on input made of LINES and return what it wrote."
  (let ((input (make-string-input-stream (format nil "~{~a~%~}" lines)))
        (output (make-string-output-stream)))
    (funcall 'game-2048:play :input input :output output :random-state (seeded))
    (get-output-stream-string output)))

(defun writes-output-p (lines)
  "True if PLAY on input made of LINES returns and writes some output."
  (plusp (length (play-output lines))))

(test t (writes-output-p '("q")))
(test t (writes-output-p '("a" "d" "w" "s" "q")))
(test t (writes-output-p '("x" "" "left" "q")))
(test t (writes-output-p (append (loop repeat 100 append (list "w" "a" "s" "d"))
                                 (list "q"))))
