(eval-when (:compile-toplevel :load-toplevel :execute)
  (require :tester))

(defpackage :game-2048-tests
  (:use :common-lisp :util.test :game-2048))
(in-package :game-2048-tests)

(multiple-value-bind (row score) (slide-row '(2 2 2 2))
  (util.test:test t (equal row '(4 4 0 0)))
  (util.test:test 8 score))
(multiple-value-bind (row score) (slide-row '(2 2 2 0))
  (util.test:test t (equal row '(4 2 0 0)))
  (util.test:test 4 score))

(let ((board (make-array '(4 4) :initial-element 0)))
    (setf (aref board 0 0) 2 (aref board 0 1) 2)
    (multiple-value-bind (result score changed) (move board :left)
      (util.test:test 4 (aref result 0 0))
      (util.test:test 4 score)
      (util.test:test t changed)
      (util.test:test 2 (aref board 0 0))))

(let ((board (make-array '(4 4) :initial-element 0)))
    (let ((spawned (spawn-tile board (make-random-state t))))
      (util.test:test 1 (count-if (lambda (x) (not (zerop x))) (loop for r below 4 append
                 (loop for c below 4 collect (aref spawned r c))))))
    (util.test:test nil (won-p board))
    (util.test:test t (game-over-p board)))

(let ((output (make-string-output-stream)))
    (play :input (make-string-input-stream (format nil "q~%"))
          :output output :random-state (make-random-state t))
    (util.test:test 0 (search "Score: 0" (get-output-stream-string output))))
