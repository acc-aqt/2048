;;;; game-2048-tests.lisp -- tests for the game-2048 system.
;;;; Uses Allegro's tester module: each top-level (test expected form ...) is one check.

(eval-when (:compile-toplevel :load-toplevel :execute)
  (require :tester))

(defpackage #:game-2048-tests
  (:use #:common-lisp #:game-2048 #:util.test))

(in-package :game-2048-tests)

(defun make-board (rows)
  "Build a board from a list of 4 lists of 4 integers."
  (let ((b (make-array '(4 4) :initial-element 0)))
    (loop for row in rows
          for r from 0
          do (loop for v in row
                   for c from 0
                   do (setf (aref b r c) v)))
    b))

(defun board-rows (b)
  (loop for r below 4
        collect (loop for c below 4 collect (aref b r c))))

(defun count-tiles (b)
  (loop for r below 4 sum (loop for c below 4 count (/= 0 (aref b r c)))))

(defun contains (needle haystack)
  (not (null (search needle haystack))))

(defun count-occurrences (needle haystack)
  (loop with start = 0
        for pos = (search needle haystack :start2 start)
        while pos
        count t
        do (setf start (1+ pos))))

;;; slide-row

(test '((4 4 0 0) 8) (multiple-value-list (slide-row (list 2 2 2 2))) :test #'equal)
(test '((4 2 0 0) 4) (multiple-value-list (slide-row (list 2 2 2 0))) :test #'equal)
(test '((4 0 0 0) 4) (multiple-value-list (slide-row (list 0 2 0 2))) :test #'equal)
(test '((2 4 8 16) 0) (multiple-value-list (slide-row (list 2 4 8 16))) :test #'equal)
(test '((4 4 0 0) 4) (multiple-value-list (slide-row (list 2 2 4 0))) :test #'equal)
(test '((0 0 0 0) 0) (multiple-value-list (slide-row (list 0 0 0 0))) :test #'equal)
(test '(2 2 0 0)
      (let ((row (list 2 2 0 0)))
        (slide-row row)
        row)
      :test #'equal)

;;; move

(test '(((4 4 0 0) (0 0 0 0) (4 0 0 0) (8 0 0 0)) 20 t)
      (multiple-value-bind (b pts changed)
          (move (make-board '((2 2 2 2) (0 0 0 0) (2 0 2 0) (4 0 0 4))) :left)
        (list (board-rows b) pts changed))
      :test #'equal)

(test '(((0 0 2 4) (0 0 0 0) (0 0 0 0) (0 0 0 0)) 4 t)
      (multiple-value-bind (b pts changed)
          (move (make-board '((2 2 2 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))) :right)
        (list (board-rows b) pts changed))
      :test #'equal)

(test '(((4 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)) 4 t)
      (multiple-value-bind (b pts changed)
          (move (make-board '((2 0 0 0) (0 0 0 0) (2 0 0 0) (0 0 0 0))) :up)
        (list (board-rows b) pts changed))
      :test #'equal)

(test '(((0 0 0 0) (0 0 0 0) (0 0 0 0) (4 0 0 0)) 4 t)
      (multiple-value-bind (b pts changed)
          (move (make-board '((2 0 0 0) (0 0 0 0) (2 0 0 0) (0 0 0 0))) :down)
        (list (board-rows b) pts changed))
      :test #'equal)

(test '(((2 4 8 16) (0 0 0 0) (0 0 0 0) (0 0 0 0)) 0 nil)
      (multiple-value-bind (b pts changed)
          (move (make-board '((2 4 8 16) (0 0 0 0) (0 0 0 0) (0 0 0 0))) :left)
        (list (board-rows b) pts changed))
      :test #'equal)

(test '((2 2 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))
      (let ((orig (make-board '((2 2 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))))
        (move orig :left)
        (board-rows orig))
      :test #'equal)

;;; spawn-tile

(test '(1 2 t)
      (let* ((orig (make-board '((2 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))))
             (new (spawn-tile orig (make-random-state nil))))
        (list (count-tiles orig) (count-tiles new)
              (loop for r below 4
                    always (loop for c below 4
                                 always (or (= (aref orig r c) (aref new r c))
                                            (and (zerop (aref orig r c))
                                                 (member (aref new r c) '(2 4))))))))
      :test #'equal)

(test 1
      (let ((orig (make-board '((2 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))))
        (spawn-tile orig (make-random-state nil))
        (count-tiles orig)))

(test t
      (let ((s (make-random-state nil)))
        (equalp (board-rows (spawn-tile (make-board nil) (make-random-state s)))
                (board-rows (spawn-tile (make-board nil) (make-random-state s)))))
      :test #'equal)

;;; won-p and game-over-p

(test t (won-p (make-board '((2048 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))))
      :test #'equal)
(test nil (won-p (make-board '((1024 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))))
      :test #'equal)
(test t (game-over-p (make-board '((2 4 2 4) (4 2 4 2) (2 4 2 4) (4 2 4 2))))
      :test #'equal)
(test nil (game-over-p (make-board '((2 4 2 4) (4 2 4 2) (2 4 2 4) (4 2 4 4))))
      :test #'equal)
(test nil (game-over-p (make-board '((2 4 2 4) (4 2 4 2) (2 4 2 4) (4 2 4 0))))
      :test #'equal)

;;; play (string streams only)

(defun run-play (input-string &optional seed)
  (let ((out (make-string-output-stream)))
    (play :input (make-string-input-stream input-string)
          :output out
          :random-state (if seed (make-random-state seed) (make-random-state t)))
    (get-output-stream-string out)))

(test t (contains "Score: 0" (run-play (format nil "q~%")))
      :test #'equal)
(test t (contains "Score: 0" (run-play ""))
      :test #'equal)
(test t (contains "Invalid key" (run-play (format nil "x~%y~%q~%")))
      :test #'equal)
;; start board is printed once, then once more after the invalid key; no extra tile
(test 2 (count-occurrences "Score: 0"
                           (run-play (format nil "x~%q~%") (make-random-state nil))))
(test t (let ((seed (make-random-state nil)))
          (string= (run-play (format nil "a~%d~%w~%s~%q~%") seed)
                   (run-play (format nil "a~%d~%w~%s~%q~%") seed)))
      :test #'equal)
(test t (contains "Score:" (run-play (format nil "a~%q~%") (make-random-state nil)))
      :test #'equal)
