(eval-when (:compile-toplevel :load-toplevel :execute)
  (require :tester))

(defpackage :game-2048-tests
  (:use :cl :util.test :game-2048))

(in-package :game-2048-tests)

(defun make-board (rows)
  "Return a board whose top rows are the lists in ROWS, the rest empty."
  (let ((board (make-array '(4 4) :initial-element 0)))
    (loop for r from 0
          for row in rows
          do (loop for c from 0
                   for v in row
                   do (setf (aref board r c) v)))
    board))

(defun board-rows (board)
  "Return the board as a list of row lists."
  (loop for r below 4
        collect (loop for c below 4 collect (aref board r c))))

(defun board-sum (board)
  "Return the sum of all cells of BOARD."
  (loop for r below 4 sum (loop for c below 4 sum (aref board r c))))

(defun count-filled (board)
  "Return how many cells of BOARD are not empty."
  (loop for r below 4
        sum (loop for c below 4 count (/= 0 (aref board r c)))))

(defun run-play (text &optional (random-state (make-random-state nil)))
  "Run play on the keys in TEXT. Return the score and the output as a string."
  (let* ((out (make-string-output-stream))
         (score (play :input (make-string-input-stream text)
                      :output out
                      :random-state random-state)))
    (values score (get-output-stream-string out))))

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
(test '(4 8 0 0) (values (slide-row (list 2 2 4 4))) :test #'equal)
(test 12 (nth-value 1 (slide-row (list 2 2 4 4))))
(test 4 (length (slide-row (list 2 0 0 0))))
(test '(2 0 0 0) (values (slide-row (list 0 0 0 2))) :test #'equal)

(let ((row (list 2 2 2 2)))
  (slide-row row)
  (test '(2 2 2 2) row :test #'equal))

;;; move

(test '((4 4 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))
      (board-rows (values (move (make-board '((2 2 2 2))) :left)))
      :test #'equal)
(test 8 (nth-value 1 (move (make-board '((2 2 2 2))) :left)))
(test t (nth-value 2 (move (make-board '((2 2 2 2))) :left)))
(test '((0 0 2 4) (0 0 0 0) (0 0 0 0) (0 0 0 0))
      (board-rows (values (move (make-board '((2 2 2 0))) :right)))
      :test #'equal)
(test '((4 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))
      (board-rows (values (move (make-board '((2 0 0 0) (2 0 0 0))) :up)))
      :test #'equal)
(test '((0 0 0 0) (0 0 0 0) (0 0 0 0) (4 0 0 0))
      (board-rows (values (move (make-board '((2 0 0 0) (2 0 0 0))) :down)))
      :test #'equal)
(test nil (nth-value 2 (move (make-board '((2 4 8 16))) :left)))
(test 0 (nth-value 1 (move (make-board '((2 4 8 16))) :left)))

(let* ((board (make-board '((2 2 0 0) (4 0 4 0))))
       (before (board-rows board)))
  (move board :left)
  (test before (board-rows board) :test #'equal))

;;; spawn-tile

(test t (let ((b (spawn-tile (make-board '()) (make-random-state nil))))
          (and (= 1 (count-filled b))
               (member (board-sum b) '(2 4))
               t)))

(let* ((original (make-board '((2 0 0 0))))
       (before (board-rows original)))
  (spawn-tile original (make-random-state nil))
  (test before (board-rows original) :test #'equal))

(let ((seed (make-random-state nil)))
  (test t (equal (board-rows (spawn-tile (make-board '((2))) (make-random-state seed)))
                 (board-rows (spawn-tile (make-board '((2))) (make-random-state seed))))))

(test 4 (count-filled (spawn-tile (make-board '((2 2 2))) (make-random-state nil))))

;;; won-p and game-over-p

(test t (won-p (make-board '((2048 0 0 0)))))
(test nil (won-p (make-board '((1024 1024 0 0)))))
(test nil (won-p (make-board '())))
(test t (game-over-p (make-board '((2 4 2 4) (4 2 4 2) (2 4 2 4) (4 2 4 2)))))
(test nil (game-over-p (make-board '((2 2 4 8) (4 8 16 32) (2 4 8 16) (4 8 16 32)))))
(test nil (game-over-p (make-board '((2 0 0 0)))))

;;; play

(test 0 (values (run-play (format nil "q~%"))))
(test 0 (values (run-play "")))
(test t (if (search "Score: 0" (nth-value 1 (run-play (format nil "q~%")))) t nil))
(test t (if (search "Invalid key" (nth-value 1 (run-play (format nil "x~%q~%")))) t nil))
(test nil (if (search "Game over" (nth-value 1 (run-play (format nil "w~%q~%")))) t nil))

(let ((seed (make-random-state nil)))
  (test (nth-value 1 (run-play (format nil "a~%s~%d~%w~%q~%") (make-random-state seed)))
        (nth-value 1 (run-play (format nil "a~%s~%d~%w~%q~%") (make-random-state seed)))
        :test #'string=))

(test 0 (values (run-play (format nil "x~%y~%"))))
