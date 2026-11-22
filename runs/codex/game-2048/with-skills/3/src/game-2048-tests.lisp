(eval-when (:compile-toplevel :load-toplevel :execute)
  (require :tester))

(defpackage :game-2048-tests
  (:use :cl :util.test :game-2048))

(in-package :game-2048-tests)

(test '(4 4 0 0) (first (multiple-value-list (slide-row '(2 2 2 2)))) :test #'equal)
(test 8 (second (multiple-value-list (slide-row '(2 2 2 2)))))
(test '(4 2 0 0) (first (multiple-value-list (slide-row '(2 2 2 0)))) :test #'equal)
(test 4 (second (multiple-value-list (slide-row '(2 2 2 0)))))
(test '(4 4 0 0) (first (multiple-value-list (slide-row '(2 2 4 0)))) :test #'equal)
(test '(4 0 0 0) (first (multiple-value-list (slide-row '(0 2 0 2)))) :test #'equal)
(test '(2 4 8 16) (first (multiple-value-list (slide-row '(2 4 8 16)))) :test #'equal)

(defparameter *board* (make-array '(4 4) :initial-element 0))
(setf (aref *board* 0 0) 2
      (aref *board* 0 1) 2)
(test '(4 0 0 0)
      (loop for column below 4
            collect (aref (first (multiple-value-list (move *board* :left))) 0 column))
      :test #'equal)
(test 4 (second (multiple-value-list (move *board* :left))))
(test t (third (multiple-value-list (move *board* :left))))
(test '(2 2 0 0)
      (loop for column below 4 collect (aref *board* 0 column))
      :test #'equal)
(test nil (third (multiple-value-list (move *board* :up))))
(test '(0 0 2 4)
      (let ((board (make-array '(4 4) :initial-element 0)))
        (setf (aref board 0 0) 2
              (aref board 0 1) 2
              (aref board 0 2) 2)
        (let ((moved (first (multiple-value-list (move board :right)))))
          (loop for column below 4 collect (aref moved 0 column))))
      :test #'equal)
(test '(0 0 2 4)
      (let ((board (make-array '(4 4) :initial-element 0)))
        (setf (aref board 0 0) 2
              (aref board 1 0) 2
              (aref board 2 0) 2)
        (let ((moved (first (multiple-value-list (move board :down)))))
          (loop for row below 4 collect (aref moved row 0))))
      :test #'equal)

(test t (won-p (let ((board (make-array '(4 4) :initial-element 0)))
                 (setf (aref board 2 3) 2048)
                 board)))
(test nil (won-p *board*))
(test t (game-over-p
         (make-array '(4 4) :initial-contents
                     '((2 4 2 4) (4 2 4 2) (2 4 2 4) (4 2 4 2)))))
(test nil (game-over-p *board*))

(test t (let* ((empty (make-array '(4 4) :initial-element 0))
               (state-a (make-random-state nil))
               (state-b (make-random-state nil))
               (first-board (spawn-tile empty state-a))
               (same-board (spawn-tile empty state-b)))
          (and (equalp first-board same-board)
               (= 1 (loop for row below 4 sum
                          (loop for column below 4 count
                                (plusp (aref first-board row column))))))))
(test t (let ((output (make-string-output-stream)))
          (play :input (make-string-input-stream (format nil "q~%"))
                :output output :random-state (make-random-state 1))
          (not (null (search "Score: 0" (get-output-stream-string output))))))
