(eval-when (:compile-toplevel :load-toplevel :execute)
  (require :tester))

(defpackage :game-2048-tests
  (:use :cl :util.test :game-2048))

(in-package :game-2048-tests)

(test '((4 4 0 0) 8) (multiple-value-list (slide-row '(2 2 2 2))) :test #'equal)
(test '((4 2 0 0) 4) (multiple-value-list (slide-row '(2 2 2 0))) :test #'equal)
(test '((4 4 0 0) 4) (multiple-value-list (slide-row '(2 2 4 0))) :test #'equal)
(test '((4 0 0 0) 4) (multiple-value-list (slide-row '(0 2 0 2))) :test #'equal)

(test '(8 t t)
      (multiple-value-bind (board points changed)
          (move #2A((2 2 2 2) (0 0 0 0) (0 0 0 0) (0 0 0 0)) :left)
        (list points changed
              (equalp board #2A((4 4 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))))
      :test #'equal)
(test nil (game-over-p #2A((0 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))))
(test t (won-p #2A((2048 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))))
(test nil (won-p #2A((2 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))))

(test t
      (let* ((board #2A((2 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))
             (spawned (spawn-tile board (make-random-state 7))))
        (and (equalp board #2A((2 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))
             (= 1 (loop for row below 4 sum
                        (loop for column below 4
                              count (and (zerop (aref board row column))
                                         (not (zerop (aref spawned row column))))))))))

(test t
      (let* ((output (make-string-output-stream))
             (random-state (make-random-state 9)))
        (play :input (make-string-input-stream (format nil "a~%q~%"))
              :output output :random-state random-state)
        (not (null (search "Score:" (get-output-stream-string output))))))
