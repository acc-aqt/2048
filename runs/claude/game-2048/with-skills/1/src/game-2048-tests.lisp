(eval-when (:compile-toplevel :load-toplevel :execute)
  (require :tester))

(defpackage :game-2048-tests
  (:use :cl :util.test :game-2048))

(in-package :game-2048-tests)

(defun board-from-rows (rows)
  "Build a 4x4 board from a list of 4 row lists."
  (let ((b (make-array '(4 4))))
    (loop for row in rows
          for r from 0
          do (loop for v in row
                   for c from 0
                   do (setf (aref b r c) v)))
    b))

(defun board-rows (board)
  "Return BOARD as a list of 4 row lists."
  (loop for r from 0 below 4
        collect (loop for c from 0 below 4 collect (aref board r c))))

(defun tile-list (board)
  "Return every cell of BOARD as a flat list."
  (loop for r from 0 below 4
        append (loop for c from 0 below 4 collect (aref board r c))))

(defun move-summary (rows direction)
  "Move ROWS in DIRECTION; return (rows points changed)."
  (multiple-value-bind (b points changed)
      (move (board-from-rows rows) direction)
    (list (board-rows b) points changed)))

(defun contains-p (needle haystack)
  "True if NEEDLE occurs in HAYSTACK."
  (if (search needle haystack) t nil))

(defun play-output (input random-state)
  "Run play on the string INPUT; return its output as a string."
  (let ((out (make-string-output-stream)))
    (play :input (make-string-input-stream input)
          :output out
          :random-state random-state)
    (get-output-stream-string out)))

(defun play-score (input)
  "Run play on the string INPUT with a fresh random state; return the score."
  (play :input (make-string-input-stream input)
        :output (make-string-output-stream)
        :random-state (make-random-state nil)))

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

(test '(((4 2 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)) 4 t)
      (move-summary '((2 2 2 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)) :left)
      :test #'equal)

(test '(((0 0 2 4) (0 0 0 0) (0 0 0 0) (0 0 0 0)) 4 t)
      (move-summary '((2 2 2 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)) :right)
      :test #'equal)

(test '(((4 0 0 0) (2 0 0 0) (0 0 0 0) (0 0 0 0)) 4 t)
      (move-summary '((2 0 0 0) (2 0 0 0) (2 0 0 0) (0 0 0 0)) :up)
      :test #'equal)

(test '(((0 0 0 0) (0 0 0 0) (2 0 0 0) (4 0 0 0)) 4 t)
      (move-summary '((2 0 0 0) (2 0 0 0) (2 0 0 0) (0 0 0 0)) :down)
      :test #'equal)

(test '(((2 4 8 16) (2 4 8 16) (0 0 0 0) (0 0 0 0)) 0 nil)
      (move-summary '((2 4 8 16) (2 4 8 16) (0 0 0 0) (0 0 0 0)) :left)
      :test #'equal)

(test '(((4 4 0 0) (4 4 0 0) (0 0 0 0) (0 0 0 0)) 16 t)
      (move-summary '((2 2 2 2) (2 2 2 2) (0 0 0 0) (0 0 0 0)) :left)
      :test #'equal)

(test nil (nth-value 2 (move (board-from-rows '((0 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))) :up)))

(let ((b (board-from-rows '((2 2 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))))
  (move b :left)
  (test '((2 2 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))
        (board-rows b)
        :test #'equal))

;;; spawn-tile

(test 1 (count-if-not #'zerop
                      (tile-list (spawn-tile (make-array '(4 4) :initial-element 0)
                                             (make-random-state nil)))))

(test t (let ((rs (make-random-state nil)))
          (loop repeat 200
                always (every (lambda (x) (member x '(0 2 4)))
                              (tile-list (spawn-tile (make-array '(4 4) :initial-element 0) rs))))))

(test 16 (count-if-not #'zerop
                       (tile-list (spawn-tile (board-from-rows '((2 4 2 4) (4 2 4 2) (2 4 2 4) (4 2 4 0)))
                                              (make-random-state nil)))))

(test '((2 4 2 4) (4 2 4 2) (2 4 2 4) (4 2 4 0))
      (let ((b (board-from-rows '((2 4 2 4) (4 2 4 2) (2 4 2 4) (4 2 4 0)))))
        (spawn-tile b (make-random-state nil))
        (board-rows b))
      :test #'equal)

(test t (let ((rs1 (make-random-state nil)))
          (equalp (spawn-tile (make-array '(4 4) :initial-element 0) rs1)
                  (spawn-tile (make-array '(4 4) :initial-element 0) (make-random-state nil)))))

;;; won-p and game-over-p

(test t (won-p (board-from-rows '((2048 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))))
(test nil (won-p (board-from-rows '((1024 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))))

(test t (game-over-p (board-from-rows '((2 4 2 4) (4 2 4 2) (2 4 2 4) (4 2 4 2)))))
(test nil (game-over-p (board-from-rows '((2 4 2 4) (4 2 4 2) (2 4 2 4) (4 2 4 0)))))
(test nil (game-over-p (board-from-rows '((2 2 4 8) (16 32 64 128) (2 4 8 16) (32 64 128 256)))))

;;; play

(test 0 (values (play-score (format nil "q~%"))))
(test 0 (values (play-score "")))
(test t (contains-p "Score: 0" (play-output (format nil "q~%") (make-random-state nil))))
(test t (contains-p "Invalid key" (play-output (format nil "x~%q~%") (make-random-state nil))))
(test nil (contains-p "Game over" (play-output (format nil "q~%") (make-random-state nil))))
(test t (contains-p "Score: 0" (play-output "" (make-random-state nil))))

(test t (let ((rs (make-random-state nil)))
          (string= (play-output (format nil "a~%d~%w~%s~%q~%") rs)
                   (play-output (format nil "a~%d~%w~%s~%q~%") (make-random-state nil)))))
