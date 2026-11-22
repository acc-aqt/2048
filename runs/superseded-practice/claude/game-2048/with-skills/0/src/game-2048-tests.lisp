(eval-when (:compile-toplevel :load-toplevel :execute)
  (require :tester))

(defpackage :game-2048-tests
  (:use :cl :util.test :game-2048))

(in-package :game-2048-tests)

(defun board-from-rows (rows)
  "Make a board from a list of four lists of four integers."
  (let ((board (make-array '(4 4) :initial-element 0)))
    (loop for row in rows
          for i from 0
          do (loop for value in row
                   for j from 0
                   do (setf (aref board i j) value)))
    board))

(defun board-rows-of (board)
  "Return the rows of BOARD as a list of lists."
  (loop for i below 4
        collect (loop for j below 4 collect (aref board i j))))

(defun move-summary (board direction)
  "Return the rows, points and changed flag of a move, as one list."
  (multiple-value-bind (new points changed) (move board direction)
    (list (board-rows-of new) points changed)))

(defun play-output (input-string)
  "Run PLAY on INPUT-STRING with a seeded random state; return the output text."
  (with-output-to-string (out)
    (play :input (make-string-input-stream input-string)
          :output out
          :random-state (make-random-state nil))))

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

(let ((row (list 2 2 0 0)))
  (slide-row row)
  (test '(2 2 0 0) row :test #'equal))

;;; move

(defvar *sample* (board-from-rows '((2 2 2 0)
                                    (0 0 0 0)
                                    (2 0 2 0)
                                    (0 0 0 0))))

(test '(((4 2 0 0) (0 0 0 0) (4 0 0 0) (0 0 0 0)) 8 t)
      (move-summary *sample* :left)
      :test #'equal)
(test '(((0 0 2 4) (0 0 0 0) (0 0 0 4) (0 0 0 0)) 8 t)
      (move-summary *sample* :right)
      :test #'equal)
(test '(((0 0 0 0) (0 0 0 0) (0 0 0 0) (4 2 4 0)) 8 t)
      (move-summary *sample* :down)
      :test #'equal)

(test '(((4 0 0 0) (4 0 0 0) (0 0 0 0) (0 0 0 0)) 4 t)
      (move-summary (board-from-rows '((2 0 0 0) (2 0 0 0) (0 0 0 0) (4 0 0 0)))
                    :up)
      :test #'equal)
(test '(((0 0 0 0) (0 0 0 0) (4 0 0 0) (4 0 0 0)) 4 t)
      (move-summary (board-from-rows '((2 0 0 0) (2 0 0 0) (0 0 0 0) (4 0 0 0)))
                    :down)
      :test #'equal)
(test '(((0 0 0 0) (0 0 0 0) (0 0 0 0) (4 0 0 0)) 0 nil)
      (move-summary (board-from-rows '((0 0 0 0) (0 0 0 0) (0 0 0 0) (4 0 0 0)))
                    :down)
      :test #'equal)
(test '(((4 4 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)) 8 t)
      (move-summary (board-from-rows '((2 2 2 2) (0 0 0 0) (0 0 0 0) (0 0 0 0)))
                    :left)
      :test #'equal)

;;; spawn-tile

(let* ((board (board-from-rows '((2 2 2 2) (2 2 2 2) (2 2 2 2) (0 2 2 2))))
       (spawned (spawn-tile board (make-random-state nil))))
  (test '(2 2 2 2) (loop for j below 4 collect (aref spawned 0 j)) :test #'equal)
  (test 0 (aref board 3 0))
  (test t (and (member (aref spawned 3 0) '(2 4)) t)))

(let ((state (make-random-state nil)))
  (test (board-rows-of (spawn-tile (make-array '(4 4) :initial-element 0)
                                   (make-random-state state)))
        (board-rows-of (spawn-tile (make-array '(4 4) :initial-element 0)
                                   (make-random-state state)))
        :test #'equal))

;;; won-p and game-over-p

(test t (won-p (board-from-rows '((2048 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))))
(test nil (won-p (board-from-rows '((1024 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))))
(test nil (game-over-p (board-from-rows '((2 4 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))))
(test t (game-over-p (board-from-rows '((2 4 2 4) (4 2 4 2) (2 4 2 4) (4 2 4 2)))))
(test nil (game-over-p (board-from-rows '((2 4 2 4) (4 2 4 2) (2 4 2 4) (4 2 4 4)))))

;;; play

(test t (and (search "Score: 0" (play-output (format nil "q~%"))) t))
(test t (and (search "Invalid key: x" (play-output (format nil "x~%q~%"))) t))
(test t (and (search "Score: 0" (play-output "")) t))
(test nil (search "Invalid" (play-output (format nil "q~%"))))
(test t (let ((text (play-output (format nil "zz~%q~%"))))
          (and (search "Invalid key: zz" text) t)))
(test t (let ((state (make-random-state nil)))
          (string= (with-output-to-string (out)
                     (play :input (make-string-input-stream (format nil "a~%s~%d~%w~%q~%"))
                           :output out
                           :random-state (make-random-state state)))
                   (with-output-to-string (out)
                     (play :input (make-string-input-stream (format nil "a~%s~%d~%w~%q~%"))
                           :output out
                           :random-state (make-random-state state))))))
