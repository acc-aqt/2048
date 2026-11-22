(eval-when (:compile-toplevel :load-toplevel :execute)
  (require :tester))

(defpackage :game-2048-tests
  (:use :cl :util.test :game-2048))

(in-package :game-2048-tests)

(test t (multiple-value-bind (row score) (slide-row '(2 2 2 2))
          (and (equal row '(4 4 0 0)) (= score 8))))
(test t (multiple-value-bind (row score) (slide-row '(2 2 2 0))
          (and (equal row '(4 2 0 0)) (= score 4))))
(test t (multiple-value-bind (row score) (slide-row '(0 2 0 2))
          (and (equal row '(4 0 0 0)) (= score 4))))
(test t (multiple-value-bind (row score) (slide-row '(2 4 8 16))
          (and (equal row '(2 4 8 16)) (= score 0))))

(test t (multiple-value-bind (board score changed)
            (move #2A((2 2 2 2) (0 0 0 0) (0 0 0 0) (0 0 0 0)) :left)
          (and (equalp board #2A((4 4 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))
               (= score 8) changed)))
(test nil (third (multiple-value-list
                  (move #2A((2 4 8 16) (16 8 4 2) (2 4 8 16) (16 8 4 2)) :left))))
(test t (won-p #2A((0 0 0 0) (0 2048 0 0) (0 0 0 0) (0 0 0 0))))
(test nil (won-p (make-array '(4 4) :initial-element 0)))
(test t (game-over-p #2A((2 4 2 4) (4 2 4 2) (2 4 2 4) (4 2 4 2))))
(test nil (game-over-p (make-array '(4 4) :initial-element 0)))

(test t (let* ((board (make-array '(4 4) :initial-element 0))
               (state-a (make-random-state t))
               (state-b (make-random-state state-a))
               (spawn-a (spawn-tile board state-a))
               (spawn-b (spawn-tile board state-b)))
          (and (equalp spawn-a spawn-b)
               (zerop (aref board 0 0))
               (= 1 (loop for row below 4
                          sum (loop for column below 4
                                    count (not (zerop (aref spawn-a row column)))))))))

(test t (let* ((output (make-string-output-stream))
               (input (make-string-input-stream (format nil "q~%")))
               (state (make-random-state t)))
          (play :input input :output output :random-state state)
          (> (length (get-output-stream-string output)) 0)))
