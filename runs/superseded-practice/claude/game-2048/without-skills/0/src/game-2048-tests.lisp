;;;; game-2048-tests.lisp

(eval-when (:compile-toplevel :load-toplevel :execute)
  (require :tester))

(defpackage :game-2048-tests
  (:use :common-lisp :util.test :game-2048))

(in-package :game-2048-tests)

;;; Helpers (all return a single value)

(defun board-from-rows (rows)
  (let ((b (make-array '(4 4) :initial-element 0)))
    (loop for row in rows
          for r from 0
          do (loop for v in row
                   for c from 0
                   do (setf (aref b r c) v)))
    b))

(defun board-rows (board)
  (loop for r from 0 below 4
        collect (loop for c from 0 below 4 collect (aref board r c))))

(defun contains (needle haystack)
  (and (search needle haystack) t))

(defun run-play (input-string)
  "Run PLAY on INPUT-STRING with a fixed random state; return the transcript."
  (let ((out (make-string-output-stream)))
    (play :input (make-string-input-stream input-string)
          :output out
          :random-state (make-random-state nil))
    (get-output-stream-string out)))

(defun slide-cells (row)
  (values (slide-row row)))

(defun slide-points (row)
  (nth-value 1 (slide-row row)))

(defun move-cells (rows direction)
  (board-rows (values (move (board-from-rows rows) direction))))

(defun move-points (rows direction)
  (nth-value 1 (move (board-from-rows rows) direction)))

(defun move-changed (rows direction)
  (nth-value 2 (move (board-from-rows rows) direction)))

(defun spawned-cells (rows)
  (board-rows (spawn-tile (board-from-rows rows) (make-random-state nil))))

;;; slide-row

(test '(4 4 0 0) (slide-cells (list 2 2 2 2)) :test #'equal)
(test 8 (slide-points (list 2 2 2 2)))
(test '(4 2 0 0) (slide-cells (list 2 2 2 0)) :test #'equal)
(test 4 (slide-points (list 2 2 2 0)))
(test '(4 0 0 0) (slide-cells (list 0 2 0 2)) :test #'equal)
(test 4 (slide-points (list 0 2 0 2)))
(test '(2 4 8 16) (slide-cells (list 2 4 8 16)) :test #'equal)
(test 0 (slide-points (list 2 4 8 16)))
(test '(4 4 0 0) (slide-cells (list 2 2 4 0)) :test #'equal)
(test 4 (slide-points (list 2 2 4 0)))
(test '(0 0 0 0) (slide-cells (list 0 0 0 0)) :test #'equal)

(let ((row (list 2 2 0 0)))
  (slide-row row)
  (test '(2 2 0 0) row :test #'equal))

;;; move

(test '((4 0 0 0) (0 0 0 0) (8 0 0 0) (2 0 0 0))
      (move-cells '((2 0 2 0) (0 0 0 0) (4 4 0 0) (0 0 0 2)) :left)
      :test #'equal)
(test 12 (move-points '((2 0 2 0) (0 0 0 0) (4 4 0 0) (0 0 0 2)) :left))

(test '((0 0 2 4) (0 0 0 0) (0 0 0 0) (0 0 0 0))
      (move-cells '((2 2 2 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)) :right)
      :test #'equal)
(test 4 (move-points '((2 2 2 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)) :right))

(test '((4 0 0 0) (2 0 0 0) (0 0 0 0) (0 0 0 0))
      (move-cells '((2 0 0 0) (2 0 0 0) (2 0 0 0) (0 0 0 0)) :up)
      :test #'equal)
(test 4 (move-points '((2 0 0 0) (2 0 0 0) (2 0 0 0) (0 0 0 0)) :up))

(test '((0 0 0 0) (0 0 0 0) (2 0 0 0) (4 0 0 0))
      (move-cells '((2 0 0 0) (2 0 0 0) (2 0 0 0) (0 0 0 0)) :down)
      :test #'equal)
(test 4 (move-points '((2 0 0 0) (2 0 0 0) (2 0 0 0) (0 0 0 0)) :down))

(test 8 (move-points '((2 2 2 2) (0 0 0 0) (0 0 0 0) (0 0 0 0)) :left))
(test t (move-changed '((0 2 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)) :left))
(test nil (move-changed '((2 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)) :left))

(let ((b (board-from-rows '((2 2 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))))
  (move b :left)
  (test '((2 2 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))
        (board-rows b)
        :test #'equal))

;;; spawn-tile

(defun count-tiles (board)
  (loop for r below 4
        sum (loop for c below 4 count (/= 0 (aref board r c)))))

(test 2 (count-tiles (spawn-tile (board-from-rows '((2 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))
                                 (make-random-state nil))))

(test t (let ((rs (make-random-state nil)))
          (loop repeat 50
                always (let* ((n (spawn-tile (make-array '(4 4) :initial-element 0) rs))
                              (total (loop for r below 4
                                           sum (loop for c below 4 sum (aref n r c)))))
                         (and (member total '(2 4)) t))))
  :test #'eql)

(let ((b (board-from-rows '((2 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))))
  (spawn-tile b (make-random-state nil))
  (test '((2 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))
        (board-rows b)
        :test #'equal))

(test (board-rows (spawn-tile (board-from-rows '((2 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))
                              (make-random-state 7)))
      (board-rows (spawn-tile (board-from-rows '((2 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))
                              (make-random-state 7)))
      :test #'equal)

;;; won-p and game-over-p

(test t (won-p (board-from-rows '((2048 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))))
      :test #'eql)
(test nil (won-p (board-from-rows '((1024 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))))
      :test #'eql)
(test t (game-over-p (board-from-rows '((2 4 2 4) (4 2 4 2) (2 4 2 4) (4 2 4 2))))
      :test #'eql)
(test nil (game-over-p (board-from-rows '((2 4 2 4) (4 2 4 2) (2 4 2 4) (4 2 4 4))))
      :test #'eql)
(test t (game-over-p (board-from-rows '((0 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))))
      :test #'eql)

;;; play

(test t (contains "Score: 0" (run-play (format nil "q~%"))) :test #'eql)
(test nil (contains "Game over" (run-play (format nil "q~%"))) :test #'eql)
(test t (contains "Score: 0" (run-play "")) :test #'eql)
(test t (contains "Invalid key" (run-play (format nil "x~%q~%"))) :test #'eql)
(test t (contains "Invalid key" (run-play (format nil "Q~%q~%"))) :test #'eql)
(test t (contains "Score:" (run-play (format nil "a~%d~%w~%s~%q~%"))) :test #'eql)
