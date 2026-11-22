;;;; Tests for the game-2048 system, as a run's own tests file would be.
;;;; `lisp-check --test` loads game-2048.asd first.

(eval-when (:compile-toplevel :load-toplevel :execute)
  (require :tester))

(defpackage :game-2048-tests
  (:use :cl :util.test :game-2048))

(in-package :game-2048-tests)

(defun board (rows)
  "Return a 4x4 board with the values in ROWS, the top row first."
  (make-array '(4 4) :initial-contents rows))

(test '(4 4 0 0) (values (slide-row (list 2 2 2 2))) :test #'equal)
(test 8 (nth-value 1 (slide-row (list 2 2 2 2))))
(test '(4 2 0 0) (values (slide-row (list 2 2 2 0))) :test #'equal)
(test '(0 0 0 0) (values (slide-row (list 0 0 0 0))) :test #'equal)

(defparameter *board*
  (board '((2 2 0 0) (0 0 0 0) (0 0 0 2) (0 0 0 2))))

(test (board '((4 0 0 0) (0 0 0 0) (2 0 0 0) (2 0 0 0)))
      (values (move *board* :left)) :test #'equalp)
(test (board '((2 2 0 4) (0 0 0 0) (0 0 0 0) (0 0 0 0)))
      (values (move *board* :up)) :test #'equalp)
(test nil (nth-value 2 (move (board '((2 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))) :left)))

(defparameter *spawned*
  (spawn-tile (board '((2 4 2 4) (4 2 4 2) (2 4 2 4) (4 2 4 0)))
              (make-random-state t)))

(test t (if (member (aref *spawned* 3 3) '(2 4)) t nil))

(test t (won-p (board '((2048 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))))
(test t (game-over-p (board '((2 4 2 4) (4 2 4 2) (2 4 2 4) (4 2 4 2)))))
(test nil (game-over-p (board '((2 2 2 4) (4 2 4 2) (2 4 2 4) (4 2 4 2)))))

(test t (plusp (length (with-output-to-string (output)
                         (play :input (make-string-input-stream (format nil "a~%q~%"))
                               :output output
                               :random-state (make-random-state t))))))
