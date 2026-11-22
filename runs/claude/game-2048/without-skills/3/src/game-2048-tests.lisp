;;;; game-2048-tests.lisp -- tests for the 2048 game, using Allegro's tester
;;;; module (package util.test).

(defpackage :game-2048-tests
  (:use :common-lisp :game-2048))

(in-package :game-2048-tests)

(eval-when (:compile-toplevel :load-toplevel :execute)
  (require :tester))

(defmacro check (form expected)
  "Test that FORM evaluates to a value EQUAL to EXPECTED."
  `(util.test:test t (equal ,form ',expected)))

(defun board-from-rows (rows)
  (let ((board (make-array '(4 4) :initial-element 0)))
    (loop for row in rows for r from 0
          do (loop for v in row for c from 0
                   do (setf (aref board r c) v)))
    board))

(defun board-rows (board)
  (loop for r from 0 below 4
        collect (loop for c from 0 below 4 collect (aref board r c))))

(defun count-tiles (board)
  (loop for r below 4 sum (loop for c below 4 count (/= 0 (aref board r c)))))

(defun all-tile-values (board)
  (loop for r below 4
        append (loop for c below 4
                     unless (zerop (aref board r c))
                       collect (aref board r c))))

(defun run-play (input-string &optional (seed 1))
  "Run PLAY on INPUT-STRING. Returns the output text and the score."
  (let* ((out (make-string-output-stream))
         (score (play :input (make-string-input-stream input-string)
                      :output out
                      :random-state (make-random-state seed))))
    (values (get-output-stream-string out) score)))

;;; slide-row

(check (multiple-value-list (slide-row (list 2 2 2 2))) ((4 4 0 0) 8))
(check (multiple-value-list (slide-row (list 2 2 2 0))) ((4 2 0 0) 4))
(check (multiple-value-list (slide-row (list 0 2 0 2))) ((4 0 0 0) 4))
(check (multiple-value-list (slide-row (list 2 4 8 16))) ((2 4 8 16) 0))
(check (multiple-value-list (slide-row (list 2 2 4 0))) ((4 4 0 0) 4))
(check (multiple-value-list (slide-row (list 0 0 0 0))) ((0 0 0 0) 0))

(check (let ((row (list 2 2 0 0)))
         (slide-row row)
         row)
       (2 2 0 0))

;;; move

(check (multiple-value-bind (b points changed)
           (move (board-from-rows '((2 2 2 2) (0 0 0 0) (0 0 0 0) (0 0 0 0)))
                 :left)
         (list (board-rows b) points changed))
       (((4 4 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)) 8 t))

(check (board-rows
        (move (board-from-rows '((2 2 2 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))
              :right))
       ((0 0 2 4) (0 0 0 0) (0 0 0 0) (0 0 0 0)))

(check (board-rows
        (move (board-from-rows '((2 0 0 0) (2 0 0 0) (0 0 0 0) (0 0 0 0)))
              :up))
       ((4 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))

(check (board-rows
        (move (board-from-rows '((2 0 0 0) (2 0 0 0) (0 0 0 0) (0 0 0 0)))
              :down))
       ((0 0 0 0) (0 0 0 0) (0 0 0 0) (4 0 0 0)))

(check (nth-value 2 (move (board-from-rows '((2 4 8 16) (0 0 0 0)
                                             (0 0 0 0) (0 0 0 0)))
                          :left))
       nil)

(check (let ((b (board-from-rows '((2 2 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))))
         (move b :left)
         (board-rows b))
       ((2 2 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))

;;; spawn-tile

(check (let* ((b (board-from-rows '((2 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))))
              (new (spawn-tile b (make-random-state 7))))
         (list (count-tiles b) (count-tiles new) (aref new 0 0)))
       (1 2 2))

(check (let ((b (board-from-rows '((2 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))))
         (spawn-tile b (make-random-state 7))
         (board-rows b))
       ((2 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))

(check (let ((b (board-from-rows '((0 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))))
             (rs (make-random-state 3)))
         (loop repeat 50
               always (every (lambda (v) (member v '(2 4)))
                             (all-tile-values (spawn-tile b rs)))))
       t)

(check (equal (board-rows (spawn-tile (board-from-rows '((0 0 0 0) (0 0 0 0)
                                                         (0 0 0 0) (0 0 0 0)))
                                      (make-random-state 42)))
              (board-rows (spawn-tile (board-from-rows '((0 0 0 0) (0 0 0 0)
                                                         (0 0 0 0) (0 0 0 0)))
                                      (make-random-state 42))))
       t)

;;; won-p and game-over-p

(check (won-p (board-from-rows '((2048 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))))
       t)
(check (won-p (board-from-rows '((1024 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))))
       nil)
(check (game-over-p (board-from-rows '((2 4 2 4) (4 2 4 2) (2 4 2 4) (4 2 4 2))))
       t)
(check (game-over-p (board-from-rows '((2 2 2 4) (4 2 4 2) (2 4 2 4) (4 2 4 2))))
       nil)
(check (game-over-p (board-from-rows '((2 4 2 4) (4 2 4 2) (2 4 2 4) (4 2 4 0))))
       nil)

;;; play

(check (nth-value 1 (run-play (format nil "q~%"))) 0)
(check (nth-value 1 (run-play "")) 0)
(check (and (search "Score: 0" (run-play (format nil "q~%"))) t) t)
(check (and (search "Invalid key" (run-play (format nil "x~%q~%"))) t) t)
(check (and (search "Score: 0" (run-play (format nil "a~%d~%w~%s~%"))) t) t)
