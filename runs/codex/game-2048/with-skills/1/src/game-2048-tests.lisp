(eval-when (:compile-toplevel :load-toplevel :execute)
  (require :tester))

(defpackage :game-2048-tests
  (:use :cl :util.test :game-2048))

(in-package :game-2048-tests)

(test 8 (nth-value 1 (slide-row '(2 2 2 2))))
(test '(4 4 0 0) (nth-value 0 (slide-row '(2 2 2 2))) :test #'equal)
(test '(4 2 0 0) (nth-value 0 (slide-row '(2 2 2 0))) :test #'equal)
(test 4 (nth-value 1 (slide-row '(2 2 2 0))))
(test '(4 4 0 0) (nth-value 0 (slide-row '(2 2 4 0))) :test #'equal)
(test 4 (nth-value 1 (slide-row '(2 2 4 0))))
(test '(2 4 8 16) (nth-value 0 (slide-row '(2 4 8 16))) :test #'equal)
(test 0 (nth-value 1 (slide-row '(2 4 8 16))))

(let ((board (make-array '(4 4) :initial-element 0)))
  (setf (aref board 0 0) 2
        (aref board 0 1) 2)
  (multiple-value-bind (moved score changed) (move board :left)
    (test 4 (aref moved 0 0))
    (test 4 score)
    (test t changed)
    (test 2 (aref board 0 0)))
  (test nil (game-over-p board)))

(let ((board (make-array '(4 4) :initial-element 0)))
  (setf (aref board 3 3) 2048)
  (test t (won-p board)))

(let* ((board (make-array '(4 4) :initial-element 0))
       (state-a (make-random-state t))
       (state-b (make-random-state state-a))
       (spawned-a (spawn-tile board state-a))
       (spawned-b (spawn-tile board state-b)))
  (test t (equalp spawned-a spawned-b))
  (test 1 (loop for row from 0 below 4
                sum (loop for column from 0 below 4
                          count (plusp (aref spawned-a row column)))))
  (test t (not (null (member (loop for row from 0 below 4
                                    thereis (loop for column from 0 below 4
                                                  for value = (aref spawned-a row column)
                                                  when (plusp value) return value))
                              '(2 4))))))

(let* ((input (make-string-input-stream (format nil "a~%q~%")))
       (output (make-string-output-stream)))
  (play :input input :output output :random-state (make-random-state t))
  (test 0 (search "Score:" (get-output-stream-string output)) :test (lambda (wanted got)
                                                                       (declare (ignore wanted))
                                                                       (eql got 0))))
