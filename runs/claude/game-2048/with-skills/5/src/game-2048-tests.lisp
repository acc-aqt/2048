(eval-when (:compile-toplevel :load-toplevel :execute)
  (require :tester))

(defpackage :game-2048-tests
  (:use :cl :util.test :game-2048))

(in-package :game-2048-tests)

(defun board-from (rows)
  "Build a 4x4 board from a list of 4 row lists."
  (let ((b (make-array '(4 4) :initial-element 0)))
    (loop for row in rows
          for r from 0
          do (loop for v in row
                   for c from 0
                   do (setf (aref b r c) v)))
    b))

(defun board-rows (board)
  "Return the rows of BOARD as a list of lists."
  (loop for r below 4
        collect (loop for c below 4 collect (aref board r c))))

(defun slide-points (row)
  "Return only the points from slide-row."
  (nth-value 1 (slide-row row)))

(defun run-game (script &optional (seed nil))
  "Play a scripted game and return its output as a string."
  (let ((out (make-string-output-stream))
        (rs (make-random-state seed)))
    (play :input (make-string-input-stream script)
          :output out
          :random-state rs)
    (get-output-stream-string out)))

(defun contains-p (needle haystack)
  "True if NEEDLE occurs in HAYSTACK."
  (and (search needle haystack) t))

(defun count-occurrences (needle haystack)
  "Count how many times NEEDLE occurs in HAYSTACK."
  (loop with start = 0
        for pos = (search needle haystack :start2 start)
        while pos
        count t
        do (setf start (+ pos (length needle)))))

;;; slide-row

(test '(4 4 0 0) (values (slide-row (list 2 2 2 2))) :test #'equal)
(test 8 (slide-points (list 2 2 2 2)))
(test '(4 2 0 0) (values (slide-row (list 2 2 2 0))) :test #'equal)
(test 4 (slide-points (list 2 2 2 0)))
(test '(4 0 0 0) (values (slide-row (list 0 2 0 2))) :test #'equal)
(test 4 (slide-points (list 0 2 0 2)))
(test '(2 4 8 16) (values (slide-row (list 2 4 8 16))) :test #'equal)
(test 0 (slide-points (list 2 4 8 16)))
(test '(4 4 0 0) (values (slide-row (list 2 2 4 0))) :test #'equal)
(test 4 (slide-points (list 2 2 4 0)))
(test '(0 0 0 0) (values (slide-row (list 0 0 0 0))) :test #'equal)

(let ((row (list 2 2 0 0)))
  (slide-row row)
  (test '(2 2 0 0) row :test #'equal))

;;; move

(test '((4 4 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))
      (board-rows (values (move (board-from '((2 2 2 2) (0 0 0 0) (0 0 0 0) (0 0 0 0))) :left)))
      :test #'equal)

(test '((0 0 2 4) (0 0 0 0) (0 0 0 0) (0 0 0 0))
      (board-rows (values (move (board-from '((2 2 2 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))) :right)))
      :test #'equal)

(test '((4 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))
      (board-rows (values (move (board-from '((2 0 0 0) (2 0 0 0) (0 0 0 0) (0 0 0 0))) :up)))
      :test #'equal)

(test '((0 0 0 0) (0 0 0 0) (0 0 0 0) (4 0 0 0))
      (board-rows (values (move (board-from '((2 0 0 0) (2 0 0 0) (0 0 0 0) (0 0 0 0))) :down)))
      :test #'equal)

(test 4 (nth-value 1 (move (board-from '((2 0 0 0) (2 0 0 0) (0 0 0 0) (0 0 0 0))) :up)))

(test 8 (nth-value 1 (move (board-from '((2 2 2 2) (0 0 0 0) (0 0 0 0) (0 0 0 0))) :left)))

(test nil (nth-value 2 (move (board-from '((2 4 8 16) (0 0 0 0) (0 0 0 0) (0 0 0 0))) :left)))

(test t (nth-value 2 (move (board-from '((0 2 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))) :left)))

(let ((b (board-from '((2 2 2 2) (0 0 0 0) (0 0 0 0) (0 0 0 0)))))
  (move b :left)
  (test '((2 2 2 2) (0 0 0 0) (0 0 0 0) (0 0 0 0)) (board-rows b) :test #'equal))

;;; spawn-tile

(defun nonzero-count (board)
  "Count the tiles on BOARD."
  (loop for r below 4 sum (loop for c below 4 count (/= 0 (aref board r c)))))

(defun board-sum (board)
  "Add up every cell of BOARD."
  (loop for r below 4 sum (loop for c below 4 sum (aref board r c))))

(test t (let* ((b (board-from '((2 4 8 16) (2 4 8 16) (2 4 8 16) (2 4 8 0))))
               (new (spawn-tile b (make-random-state nil))))
          (and (= 1 (- (nonzero-count new) (nonzero-count b)))
               (member (- (board-sum new) (board-sum b)) '(2 4))
               t)))

(test t (let* ((b (board-from '((0 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))))
               (new (spawn-tile b (make-random-state nil))))
          (and (= 1 (nonzero-count new))
               (member (board-sum new) '(2 4))
               t)))

(test t (let* ((rs1 (make-random-state nil))
               (rs2 (make-random-state rs1))
               (b (board-from '((2 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))))
          (equalp (spawn-tile b rs1) (spawn-tile b rs2))))

(test t (let* ((b (board-from '((2 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))))
                 (before (board-rows b)))
            (spawn-tile b (make-random-state nil))
            (equal before (board-rows b))))

;;; won-p and game-over-p

(test t (won-p (board-from '((0 0 0 0) (0 2048 0 0) (0 0 0 0) (0 0 0 0)))))
(test nil (won-p (board-from '((1024 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))))

(test t (game-over-p (board-from '((2 4 2 4) (4 2 4 2) (2 4 2 4) (4 2 4 2)))))
(test nil (game-over-p (board-from '((2 4 2 4) (4 2 4 2) (2 4 2 4) (4 2 4 0)))))
(test nil (game-over-p (board-from '((2 4 2 4) (4 2 4 2) (2 4 2 4) (4 2 4 4)))))

;;; play

(test t (contains-p "Score: 0" (run-game (format nil "q~%") 1)))

(test t (contains-p "Invalid key" (run-game (format nil "x~%q~%") 1)))

(test t (contains-p "Score: 0" (run-game "" 1)))

(test t (let ((out (run-game (format nil "a~%s~%w~%d~%q~%") 7)))
          (contains-p "Score:" out)))

(test t (equal (run-game (format nil "a~%s~%w~%d~%q~%") 42)
               (run-game (format nil "a~%s~%w~%d~%q~%") 42)))

(test 0 (play :input (make-string-input-stream (format nil "q~%"))
              :output (make-string-output-stream)
              :random-state (make-random-state nil)))

(test t (let ((out (run-game (format nil "x~%") 1)))
          (and (contains-p "Invalid key" out)
               (= 2 (count-occurrences "Score:" out))
               t)))
