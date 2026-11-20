;;;; Hidden tests for the game-2048 task: won-p and game-over-p. They use only the
;;;; public interface from spec.md and call it as (funcall 'game-2048:name ...),
;;;; so names the implementation exports cannot clash with the helpers here.
;;;; `lisp-check --test` loads game-2048.asd from this file's directory first.

(eval-when (:compile-toplevel :load-toplevel :execute)
  (require :tester))

(defpackage :game-2048-hidden-won-game-over-tests
  (:use :cl :util.test))

(in-package :game-2048-hidden-won-game-over-tests)

;;; An error inside one assertion counts as that assertion failing, so the
;;; remaining assertions still run. TEST reads this variable when it is
;;; macroexpanded, so set it at compile time too.
(eval-when (:compile-toplevel :load-toplevel :execute)
  (setf *error-protect-tests* t))

;;; Boards are written as 4 lists of 4 values, the top row first.

(defun board (rows)
  "Return a fresh 4x4 board with the values in ROWS."
  (make-array '(4 4) :initial-contents rows))

(defparameter *mixed*
  '((2 0 2 4)
    (2 4 0 4)
    (0 4 2 8)
    (4 4 2 8)))

(defparameter *empty*
  '((0 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))

(defparameter *one-gap*
  '((2 4 2 4)
    (4 2 4 2)
    (2 4 0 4)
    (4 2 4 2)))

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
