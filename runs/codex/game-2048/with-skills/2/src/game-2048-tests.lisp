(eval-when (:compile-toplevel :load-toplevel :execute)
  (require :tester))

(defpackage :game-2048-tests
  (:use :cl :util.test :game-2048))

(in-package :game-2048-tests)

(test '(4 4 0 0) (multiple-value-bind (row score)
                       (slide-row '(2 2 2 2))
                     (declare (ignore score))
                     row)
      :test #'equal)
(test 8 (nth-value 1 (slide-row '(2 2 2 2))))
(test '(4 2 0 0) (multiple-value-bind (row score)
                       (slide-row '(2 2 2 0))
                     (declare (ignore score))
                     row)
      :test #'equal)
(test '(4 4 0 0) (multiple-value-bind (row score)
                       (slide-row '(2 2 4 0))
                     (declare (ignore score))
                     row)
      :test #'equal)

(test '(4 4 0 0)
      (multiple-value-bind (board score changed)
          (move #2a((2 2 2 2) (0 0 0 0) (0 0 0 0) (0 0 0 0)) :left)
        (declare (ignore score changed))
        (loop for column from 0 below 4 collect (aref board 0 column)))
      :test #'equal)
(test 8 (nth-value 1
                  (move #2a((2 2 2 2) (0 0 0 0) (0 0 0 0) (0 0 0 0)) :left)))
(test t (nth-value 2
                   (move #2a((2 2 2 2) (0 0 0 0) (0 0 0 0) (0 0 0 0)) :left)))
(test nil (nth-value 2
                     (move #2a((2 4 8 16) (0 0 0 0) (0 0 0 0) (0 0 0 0))
                              :left)))

(test t (won-p #2a((2048 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))))
(test nil (won-p #2a((2 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))))
(test t (game-over-p #2a((2 4 2 4) (4 2 4 2) (2 4 2 4) (4 2 4 2))))
(test nil (game-over-p #2a((2 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))))

(test t
      (let* ((board #2a((2 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))
             (state (make-random-state t))
             (spawned (spawn-tile board state)))
        (and (equalp board #2a((2 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))
             (= 2 (aref spawned 0 0))
             (if (member (loop for row from 0 below 4
                               sum (loop for column from 0 below 4
                                         sum (aref spawned row column)))
                         '(4 6))
                 t
                 nil))))
