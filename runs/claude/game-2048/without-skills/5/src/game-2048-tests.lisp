;;;; game-2048-tests.lisp -- tests for the 2048 game, using Allegro's tester.

(eval-when (:compile-toplevel :load-toplevel :execute)
  (require :tester))

(defpackage #:game-2048-tests
  (:use #:common-lisp #:game-2048 #:util.test))

(in-package #:game-2048-tests)

(defun make-board (rows)
  "Build a board from a list of four lists of four integers."
  (let ((b (make-array '(4 4) :initial-element 0)))
    (loop for row in rows
          for r from 0
          do (loop for v in row
                   for c from 0
                   do (setf (aref b r c) v)))
    b))

(defun board-rows (board)
  "The rows of BOARD as a list of lists."
  (loop for r below 4
        collect (loop for c below 4 collect (aref board r c))))

(defun slide-result (row)
  (multiple-value-list (slide-row row)))

(defun move-result (board direction)
  (multiple-value-bind (new points changed) (move board direction)
    (list (board-rows new) points changed)))

(defun run-play (input-string &optional (seed (make-random-state nil)))
  "Run PLAY on INPUT-STRING with a copy of SEED; return the output as a string."
  (let ((out (make-string-output-stream)))
    (play :input (make-string-input-stream input-string)
          :output out
          :random-state (make-random-state seed))
    (get-output-stream-string out)))

(defun contains (needle haystack)
  (not (null (search needle haystack))))

(defmacro check-equal (expected form)
  "Assert that FORM is EQUAL to the literal EXPECTED (the tester uses EQL on lists)."
  `(test t (equal ,form ',expected)))

;;; slide-row

(check-equal ((4 4 0 0) 8) (slide-result (list 2 2 2 2)))
(check-equal ((4 2 0 0) 4) (slide-result (list 2 2 2 0)))
(check-equal ((4 0 0 0) 4) (slide-result (list 0 2 0 2)))
(check-equal ((2 4 8 16) 0) (slide-result (list 2 4 8 16)))
(check-equal ((4 4 0 0) 4) (slide-result (list 2 2 4 0)))
(check-equal ((0 0 0 0) 0) (slide-result (list 0 0 0 0)))

(test t
      (let ((row (list 2 2 0 0)))
        (slide-row row)
        (equal row '(2 2 0 0))))

(test t
      (let* ((row (list 2 4 8 16))
             (result (slide-row row)))
        (and (equal result '(2 4 8 16)) (not (eq result row)))))

;;; move

(check-equal (((4 4 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)) 8 t)
      (move-result (make-board '((2 2 2 2) (0 0 0 0) (0 0 0 0) (0 0 0 0)))
                   :left))

(check-equal (((0 0 2 4) (0 0 0 0) (0 0 0 0) (0 0 0 0)) 4 t)
      (move-result (make-board '((2 2 2 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))
                   :right))

(check-equal (((4 0 0 0) (2 0 0 0) (0 0 0 0) (0 0 0 0)) 4 t)
      (move-result (make-board '((2 0 0 0) (2 0 0 0) (2 0 0 0) (0 0 0 0)))
                   :up))

(check-equal (((0 0 0 0) (0 0 0 0) (2 0 0 0) (4 0 0 0)) 4 t)
      (move-result (make-board '((2 0 0 0) (2 0 0 0) (2 0 0 0) (0 0 0 0)))
                   :down))

(check-equal (((2 4 2 4) (4 2 4 2) (2 4 2 4) (4 2 4 2)) 0 nil)
      (move-result (make-board '((2 4 2 4) (4 2 4 2) (2 4 2 4) (4 2 4 2)))
                   :left))

(test t
      (let ((b (make-board '((2 2 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))))
        (move b :left)
        (equal (board-rows b) '((2 2 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))))

;;; spawn-tile

(test t
      (let* ((b (make-board '((2 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))))
             (new (spawn-tile b (make-random-state nil)))
             (changed (loop for r below 4
                            sum (loop for c below 4
                                      count (/= (aref new r c) (aref b r c))))))
        (and (= changed 1)
             (member (loop for r below 4
                           sum (loop for c below 4 sum (aref new r c)))
                     '(4 6)
                     :test #'=)
             t)))

(test t
      (let ((b (make-board '((2 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))))
        (spawn-tile b (make-random-state nil))
        (equal (board-rows b) '((2 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))))

(test t
      (let* ((seed (make-random-state nil))
             (b (make-board '((2 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))))
        (equal (board-rows (spawn-tile b (make-random-state seed)))
               (board-rows (spawn-tile b (make-random-state seed))))))

;;; won-p

(test t (won-p (make-board '((2048 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))))
(test nil (won-p (make-board '((1024 1024 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))))

;;; game-over-p

(test t (game-over-p (make-board '((2 4 2 4) (4 2 4 2) (2 4 2 4) (4 2 4 2)))))
(test nil (game-over-p (make-board '((2 4 2 4) (4 2 4 2) (2 4 2 4) (4 2 4 4)))))
(test nil (game-over-p (make-board '((2 4 2 4) (4 2 4 2) (2 4 2 4) (4 2 4 0)))))

;;; play

(test t (contains "Score: 0" (run-play (format nil "q~%"))))
(test t (contains "Score: 0" (run-play "")))
(test t (contains "Invalid key: x" (run-play (format nil "x~%q~%"))))

(test t
      (let ((out (run-play (format nil "a~%d~%w~%s~%q~%"))))
        (and (not (contains "Invalid" out))
             (contains "Score:" out))))

(test t
      (let ((seed (make-random-state nil)))
        (equal (run-play (format nil "a~%s~%d~%w~%q~%") seed)
               (run-play (format nil "a~%s~%d~%w~%q~%") seed))))

(test t
      (integerp (play :input (make-string-input-stream (format nil "q~%"))
                      :output (make-string-output-stream)
                      :random-state (make-random-state nil))))
