(eval-when (:compile-toplevel :load-toplevel :execute)
  (require :tester))

(defpackage :game-2048-tests
  (:use :cl :util.test :game-2048))

(in-package :game-2048-tests)

(test '(4 4 0 0) (first (multiple-value-list (slide-row '(2 2 2 2)))) :test #'equal)
(test 8 (second (multiple-value-list (slide-row '(2 2 2 2)))))
(test '(4 2 0 0) (first (multiple-value-list (slide-row '(2 2 2 0)))) :test #'equal)
(test '(4 4 0 0) (first (multiple-value-list (slide-row '(2 2 4 0)))) :test #'equal)
(test '(2 4 8 16) (first (multiple-value-list (slide-row '(2 4 8 16)))) :test #'equal)

(test '(4 2 0 0) (first (multiple-value-list (slide-row '(0 2 2 2)))) :test #'equal)

(let ((board (make-array '(4 4) :initial-element 0)))
  (setf (aref board 0 0) 2
        (aref board 0 1) 2)
  (multiple-value-bind (result score changed) (move board :left)
    (test 4 (aref result 0 0))
    (test 4 score)
    (test t changed)
    (test 2 (aref board 0 0)))
  (multiple-value-bind (result score changed) (move board :right)
    (test 4 (aref result 0 3))
    (test 4 score)
    (test t changed)))

(let ((board (make-array '(4 4) :initial-element 0)))
  (setf (aref board 0 0) 2048)
  (test t (won-p board))
  (test nil (game-over-p board)))

(let ((board (make-array '(4 4) :initial-element 0)))
  (dotimes (row 4)
    (dotimes (column 4)
      (setf (aref board row column)
            (* 2 (+ 1 (* 4 row) column))))
  (test t (game-over-p board)))

(let* ((board (make-array '(4 4) :initial-element 0))
       (result (spawn-tile board (make-random-state 17)))
       (count (loop for row from 0 below 4
                    sum (loop for column from 0 below 4
                              count (plusp (aref result row column))))))
  (test 1 count)
  (test t (not (null (loop for row from 0 below 4
                thereis (loop for column from 0 below 4
                              thereis (member (aref result row column) '(2 4))))))))

(let ((output (make-string-output-stream)))
  (play :input (make-string-input-stream (format nil "q~%"))
        :output output
        :random-state (make-random-state 23))
  (test t (not (null (search "Score: 0" (get-output-stream-string output))))))
