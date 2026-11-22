(eval-when (:compile-toplevel :load-toplevel :execute)
  (require :tester))

(defpackage :game-2048-tests
  (:use :cl :util.test :game-2048))

(in-package :game-2048-tests)

(defun make-board (rows)
  "Build a board from a list of four row lists."
  (let ((board (make-array '(4 4) :initial-element 0)))
    (loop for row in rows
          for r from 0
          do (loop for v in row
                   for c from 0
                   do (setf (aref board r c) v)))
    board))

(defun board-rows (board)
  "Return the rows of BOARD as a list of lists."
  (loop for r below 4
        collect (loop for c below 4 collect (aref board r c))))

(defun nonzero-count (board)
  "Count the tiles on BOARD."
  (count-if-not #'zerop (loop for r below 4
                              nconc (loop for c below 4 collect (aref board r c)))))

(defun board-cells (board)
  "Return every cell of BOARD as a flat list."
  (loop for r below 4
        nconc (loop for c below 4 collect (aref board r c))))

(defun contains-p (string sub)
  "True if SUB occurs in STRING."
  (not (null (search sub string))))

(defun play-to-string (input &optional (random-state (make-random-state nil)))
  "Run play on the string INPUT and return everything it printed."
  (with-output-to-string (out)
    (play :input (make-string-input-stream input)
          :output out
          :random-state random-state)))

;;; slide-row

(test (list 4 4 0 0) (values (slide-row (list 2 2 2 2))) :test #'equal)
(test 8 (nth-value 1 (slide-row (list 2 2 2 2))))
(test (list 4 2 0 0) (values (slide-row (list 2 2 2 0))) :test #'equal)
(test 4 (nth-value 1 (slide-row (list 2 2 2 0))))
(test (list 4 0 0 0) (values (slide-row (list 0 2 0 2))) :test #'equal)
(test 4 (nth-value 1 (slide-row (list 0 2 0 2))))
(test (list 2 4 8 16) (values (slide-row (list 2 4 8 16))) :test #'equal)
(test 0 (nth-value 1 (slide-row (list 2 4 8 16))))
(test (list 4 4 0 0) (values (slide-row (list 2 2 4 0))) :test #'equal)

(let ((row (list 2 2 0 0)))
  (slide-row row)
  (test (list 2 2 0 0) row :test #'equal))

;;; move

(test '((4 4 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))
      (board-rows (values (move (make-board '((2 2 2 2) (0 0 0 0) (0 0 0 0) (0 0 0 0))) :left)))
      :test #'equal)
(test 8 (nth-value 1 (move (make-board '((2 2 2 2) (0 0 0 0) (0 0 0 0) (0 0 0 0))) :left)))
(test t (nth-value 2 (move (make-board '((2 2 2 2) (0 0 0 0) (0 0 0 0) (0 0 0 0))) :left)))

(test '((0 0 2 4) (0 0 0 0) (0 0 0 0) (0 0 0 0))
      (board-rows (values (move (make-board '((2 2 2 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))) :right)))
      :test #'equal)

(test '((4 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))
      (board-rows (values (move (make-board '((2 0 0 0) (2 0 0 0) (0 0 0 0) (0 0 0 0))) :up)))
      :test #'equal)
(test 4 (nth-value 1 (move (make-board '((2 0 0 0) (2 0 0 0) (0 0 0 0) (0 0 0 0))) :up)))

(test '((0 0 0 0) (0 0 0 0) (0 0 0 0) (4 0 0 0))
      (board-rows (values (move (make-board '((2 0 0 0) (2 0 0 0) (0 0 0 0) (0 0 0 0))) :down)))
      :test #'equal)

(test nil (nth-value 2 (move (make-board '((2 4 8 16) (0 0 0 0) (0 0 0 0) (0 0 0 0))) :left)))

(let* ((board (make-board '((2 2 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))))
       (before (board-rows board)))
  (move board :left)
  (test before (board-rows board) :test #'equal))

;;; spawn-tile

(let* ((board (make-board '((2 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))))
       (before (board-rows board))
       (new (spawn-tile board (make-random-state nil))))
  (test 2 (nonzero-count new))
  (test before (board-rows board) :test #'equal))

(let ((ok t)
      (rs (make-random-state nil)))
  (dotimes (i 200)
    (let ((new (spawn-tile (make-board '((0 0 0 0) (0 0 0 0) (0 0 0 0) (2 0 0 0))) rs)))
      (unless (and (= 2 (nonzero-count new))
                   (every (lambda (v) (member v '(0 2 4))) (board-cells new)))
        (setf ok nil))))
  (test t ok))

(let ((a (make-random-state nil)))
  (test (board-rows (spawn-tile (make-board '((2 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))) (make-random-state a)))
        (board-rows (spawn-tile (make-board '((2 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))) (make-random-state a)))
        :test #'equal))

;;; won-p and game-over-p

(test t (won-p (make-board '((2048 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))))
(test nil (won-p (make-board '((1024 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))))

(test t (game-over-p (make-board '((2 4 2 4) (4 2 4 2) (2 4 2 4) (4 2 4 2)))))
(test nil (game-over-p (make-board '((2 4 2 4) (4 2 4 2) (2 4 2 4) (4 2 4 0)))))
(test nil (game-over-p (make-board '((2 4 2 4) (4 2 4 2) (2 4 2 4) (4 2 4 4)))))

;;; play

(test t (contains-p (play-to-string (format nil "q~%")) "Score: 0"))
(test t (stringp (play-to-string "")))
(test t (contains-p (play-to-string (format nil "x~%q~%")) "Invalid key"))
(test nil (contains-p (play-to-string (format nil "q~%w~%")) "Invalid key"))

(let ((a (make-random-state nil)))
  (test (play-to-string (format nil "w~%a~%s~%d~%q~%") (make-random-state a))
        (play-to-string (format nil "w~%a~%s~%d~%q~%") (make-random-state a))
        :test #'string=))

(test t (contains-p (play-to-string (with-output-to-string (s)
                                      (dotimes (i 3000)
                                        (dolist (k '("a" "s" "d" "w"))
                                          (write-line k s)))))
                    "Game over"))
