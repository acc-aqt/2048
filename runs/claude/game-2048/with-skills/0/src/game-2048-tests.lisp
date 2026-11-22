(eval-when (:compile-toplevel :load-toplevel :execute)
  (require :tester))

(defpackage :game-2048-tests
  (:use :cl :util.test :game-2048))

(in-package :game-2048-tests)

(defun board-from-rows (rows)
  "Return a board whose rows are the lists in ROWS."
  (let ((b (make-array '(4 4) :initial-element 0)))
    (loop for row in rows
          for r from 0
          do (loop for v in row
                   for c from 0
                   do (setf (aref b r c) v)))
    b))

(defun board-rows (board)
  "Return the rows of BOARD as a list of lists."
  (loop for r from 0 to 3
        collect (loop for c from 0 to 3 collect (aref board r c))))

(defun count-tiles (board)
  "Return how many non-empty cells BOARD has."
  (loop for r from 0 to 3
        sum (loop for c from 0 to 3 count (/= 0 (aref board r c)))))

(defparameter *empty-rows* '((0 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))

;;; slide-row

(test '(4 4 0 0) (values (slide-row (list 2 2 2 2))) :test #'equal)
(test 8 (nth-value 1 (slide-row (list 2 2 2 2))))
(test '(4 2 0 0) (values (slide-row (list 2 2 2 0))) :test #'equal)
(test 4 (nth-value 1 (slide-row (list 2 2 2 0))))
(test '(4 0 0 0) (values (slide-row (list 0 2 0 2))) :test #'equal)
(test 4 (nth-value 1 (slide-row (list 0 2 0 2))))
(test '(2 4 8 16) (values (slide-row (list 2 4 8 16))) :test #'equal)
(test 0 (nth-value 1 (slide-row (list 2 4 8 16))))
(test '(4 4 0 0) (values (slide-row (list 2 2 4 0))) :test #'equal)
(test '(0 0 0 0) (values (slide-row (list 0 0 0 0))) :test #'equal)

;;; move

(let ((b (board-from-rows '((2 2 2 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))))
  (test '((4 2 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))
        (board-rows (move b :left)) :test #'equal)
  (test '((0 0 2 4) (0 0 0 0) (0 0 0 0) (0 0 0 0))
        (board-rows (move b :right)) :test #'equal)
  (test 4 (nth-value 1 (move b :left)))
  (test t (nth-value 2 (move b :left)))
  ;; move does not modify its argument
  (test '((2 2 2 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))
        (board-rows b) :test #'equal))

(let ((b (board-from-rows '((2 0 0 0) (2 0 0 0) (0 0 0 0) (4 0 0 0)))))
  (test '((4 0 0 0) (4 0 0 0) (0 0 0 0) (0 0 0 0))
        (board-rows (move b :up)) :test #'equal)
  (test '((0 0 0 0) (0 0 0 0) (4 0 0 0) (4 0 0 0))
        (board-rows (move b :down)) :test #'equal)
  (test 4 (nth-value 1 (move b :up))))

(let ((b (board-from-rows '((2 4 8 16) (0 0 0 0) (0 0 0 0) (0 0 0 0)))))
  (test nil (nth-value 2 (move b :left)))
  (test 0 (nth-value 1 (move b :left))))

(test '((4 4 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))
      (board-rows (move (board-from-rows '((2 2 2 2) (0 0 0 0) (0 0 0 0) (0 0 0 0))) :left))
      :test #'equal)
(test 8 (nth-value 1 (move (board-from-rows '((2 2 2 2) (0 0 0 0) (0 0 0 0) (0 0 0 0))) :left)))

;;; spawn-tile

(let* ((b (board-from-rows '((2 4 8 16) (2 4 8 16) (2 4 8 16) (2 4 8 0))))
       (rs (make-random-state nil))
       (new (spawn-tile b rs)))
  (test 16 (count-tiles new))
  (test '((2 4 8 16) (2 4 8 16) (2 4 8 16) (2 4 8 0))
        (board-rows b) :test #'equal)
  (test t (and (member (aref new 3 3) '(2 4)) t)))

(let* ((b (board-from-rows *empty-rows*))
       (seed (make-random-state nil))
       (copy (make-random-state seed)))
  (test (board-rows (spawn-tile b seed))
        (board-rows (spawn-tile b copy))
        :test #'equal)
  (test 1 (count-tiles (spawn-tile b (make-random-state nil)))))

;;; won-p

(test t (won-p (board-from-rows '((2048 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))))
(test nil (won-p (board-from-rows '((1024 512 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))))

;;; game-over-p

(test t (game-over-p (board-from-rows '((2 4 2 4) (4 2 4 2) (2 4 2 4) (4 2 4 2)))))
(test nil (game-over-p (board-from-rows '((2 4 2 4) (4 2 4 2) (2 4 2 4) (4 2 4 0)))))
(test nil (game-over-p (board-from-rows '((2 2 2 2) (4 2 4 2) (2 4 2 4) (4 2 4 2)))))
(test nil (game-over-p (board-from-rows '((2 4 2 4) (2 2 4 2) (2 4 2 4) (4 2 4 2)))))

;;; play

(defun play-to-string (input-text &optional (seed (make-random-state nil)))
  "Run PLAY on INPUT-TEXT with a copy of SEED. Return the output as a string."
  (let ((out (make-string-output-stream)))
    (play :input (make-string-input-stream input-text)
          :output out
          :random-state (make-random-state seed))
    (get-output-stream-string out)))

(test t (if (search "Score: 0" (play-to-string (format nil "q~%"))) t nil))
(test t (if (search "Invalid key" (play-to-string (format nil "x~%q~%"))) t nil))
(test t (if (search "Score: 0" (play-to-string "")) t nil))
(test t (if (search "Game over" (play-to-string "")) nil t))

(let ((seed (make-random-state nil)))
  (test (play-to-string (format nil "a~%d~%w~%s~%q~%") seed)
        (play-to-string (format nil "a~%d~%w~%s~%q~%") seed)
        :test #'string=))

(test t (if (search "Score:" (play-to-string (format nil "a~%d~%w~%s~%q~%"))) t nil))
