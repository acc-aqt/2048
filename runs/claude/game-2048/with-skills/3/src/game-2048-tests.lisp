(eval-when (:compile-toplevel :load-toplevel :execute)
  (require :tester))

(defpackage :game-2048-tests
  (:use :cl :util.test :game-2048))

(in-package :game-2048-tests)

(defun make-board (rows)
  "Build a 4x4 board from a list of four row lists."
  (let ((board (make-array '(4 4) :initial-element 0)))
    (loop for row in rows
          for r from 0
          do (loop for v in row
                   for c from 0
                   do (setf (aref board r c) v)))
    board))

(defun copy-test-board (board)
  "Return a fresh copy of BOARD, to check that a function does not change it."
  (let ((new (make-array '(4 4) :initial-element 0)))
    (dotimes (r 4)
      (dotimes (c 4)
        (setf (aref new r c) (aref board r c))))
    new))

(defun board-row (board r)
  "Return row R of BOARD as a list."
  (loop for c below 4 collect (aref board r c)))

(defun board-column (board c)
  "Return column C of BOARD as a list."
  (loop for r below 4 collect (aref board r c)))

(defun count-tiles (board)
  "Return the number of non-zero cells in BOARD."
  (loop for r below 4
        sum (loop for c below 4 count (/= 0 (aref board r c)))))

(defun run-game (keys)
  "Play with KEYS as input and return the output text."
  (let ((out (make-string-output-stream)))
    (play :input (make-string-input-stream keys)
          :output out
          :random-state (make-random-state nil))
    (get-output-stream-string out)))

;; slide-row

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

;; move

(test '(0 0 2 4)
      (board-row (values (move (make-board '((2 2 2 0))) :right)) 0)
      :test #'equal)
(test '(4 2 0 0)
      (board-row (values (move (make-board '((2 2 2 0))) :left)) 0)
      :test #'equal)
(test '(4 0 0 0)
      (board-column (values (move (make-board '((0) (2) (0) (2))) :up)) 0)
      :test #'equal)
(test 4
      (nth-value 1 (move (make-board '((0) (2) (0) (2))) :up)))
(test '(0 0 0 4)
      (board-column (values (move (make-board '((2) (0) (0) (2))) :down)) 0)
      :test #'equal)
(test nil (nth-value 2 (move (make-board '((2)) ) :left)))
(test t (nth-value 2 (move (make-board '((0 2))) :left)))
(test 8
      (nth-value 1 (move (make-board '((2 2 2 2))) :left)))

(let* ((b (make-board '((2 2 0 0) (0 4 0 0))))
       (copy (copy-test-board b)))
  (move b :left)
  (test t (equalp b copy)))

(test nil (nth-value 2 (move (make-board '((2 4 8 16))) :left)))

;; spawn-tile

(let* ((b (make-board '((2 4 8 16) (32 64 128 256) (512 1024 2048 0) (0 0 0 0))))
       (rs (make-random-state nil))
       (new (spawn-tile b rs)))
  (test 12 (count-tiles new)))

(let* ((b (make-board '((2) (4))))
       (copy (copy-test-board b)))
  (spawn-tile b (make-random-state nil))
  (test t (equalp b copy)))

(let* ((b (make-board '((2) (4))))
       (rs (make-random-state nil))
       (seed (make-random-state rs)))
  (test t (equalp (spawn-tile b (make-random-state seed))
                  (spawn-tile b (make-random-state seed)))))

(defun tile-values (board)
  "Return the non-zero values of BOARD as a list."
  (loop for r below 4
        append (loop for c below 4
                     for v = (aref board r c)
                     unless (zerop v) collect v)))

(let ((new (spawn-tile (make-board '()) (make-random-state nil))))
  (test t (= 1 (length (tile-values new)))))

(test t (every (lambda (v) (member v '(2 4)))
               (tile-values (spawn-tile (make-board '()) (make-random-state nil)))))

;; won-p and game-over-p

(test t (won-p (make-board '((2048)))))
(test nil (won-p (make-board '((1024 1024)))))
(test t (game-over-p (make-board '((2 4 2 4) (4 2 4 2) (2 4 2 4) (4 2 4 2)))))
(test nil (game-over-p (make-board '((2 2 2 2) (4 2 4 2) (2 4 2 4) (4 2 4 2)))))
(test nil (game-over-p (make-board '((2 0 0 0)))))

;; play

(test t (not (null (search "Score: 0" (run-game (format nil "q~%"))))))
(test t (not (null (search "Score: 0" (run-game "")))))
(test t (not (null (search "Invalid key" (run-game (format nil "x~%q~%"))))))
(test t (not (null (search "Move (w a s d, q to quit)"
                           (run-game (format nil "q~%"))))))
