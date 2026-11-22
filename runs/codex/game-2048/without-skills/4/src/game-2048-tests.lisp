(eval-when (:compile-toplevel :load-toplevel :execute)
  (require :tester))

(defpackage :game-2048-tests
  (:use :common-lisp :util.test)
  (:import-from :game-2048 #:slide-row #:move #:spawn-tile #:won-p
                #:game-over-p #:play))

(in-package :game-2048-tests)

(defun check-equal (expected actual)
  (test expected actual :test #'equal))

(test t t)

(with-tests (:name "slide-row-merges")
  (multiple-value-bind (row score) (slide-row '(2 2 2 2))
    (check-equal '(4 4 0 0) row)
    (check-equal 8 score))
  (multiple-value-bind (row score) (slide-row '(2 2 2 0))
    (check-equal '(4 2 0 0) row)
    (check-equal 4 score))
  (multiple-value-bind (row score) (slide-row '(0 2 0 2))
    (check-equal '(4 0 0 0) row)
    (check-equal 4 score)))

(with-tests (:name "move-directions-and-immutability")
  (let ((board (make-array '(4 4) :initial-element 0)))
    (setf (aref board 0 0) 2
          (aref board 0 1) 2)
    (multiple-value-bind (result score changed) (move board :left)
      (check-equal 4 (aref result 0 0))
      (check-equal 4 score)
      (check-equal t changed)
      (check-equal 2 (aref board 0 0)))))

(with-tests (:name "spawn-win-and-game-over")
  (let ((board (make-array '(4 4) :initial-element 0)))
    (let ((spawned (spawn-tile board (make-random-state 17))))
      (check-equal 1 (count-if (lambda (x) (not (zerop x)))
                              (coerce (loop for r below 4 append
                                        (loop for c below 4 collect (aref spawned r c)))
                                      'vector))))
    (setf (aref board 2 2) 2048)
    (check-equal t (won-p board))
    (dotimes (r 4)
      (dotimes (c 4)
        (setf (aref board r c) (+ 2 (* 2 (mod (+ r c) 2))))))
    (check-equal nil (game-over-p board))))

(with-tests (:name "play-uses-string-streams")
  (let ((output (make-string-output-stream)))
    (play :input (make-string-input-stream (format nil "q~%"))
          :output output :random-state (make-random-state 23))
    (check-equal 0 (search "Score: 0" (get-output-stream-string output)))))
