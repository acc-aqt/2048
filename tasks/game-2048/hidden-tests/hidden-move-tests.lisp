;;;; Hidden tests for the game-2048 task: move in all four directions. They use only the
;;;; public interface from spec.md and call it as (funcall 'game-2048:name ...),
;;;; so names the implementation exports cannot clash with the helpers here.
;;;; `lisp-check --test` loads game-2048.asd from this file's directory first.

(eval-when (:compile-toplevel :load-toplevel :execute)
  (require :tester))

(defpackage :game-2048-hidden-move-tests
  (:use :cl :util.test))

(in-package :game-2048-hidden-move-tests)

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
