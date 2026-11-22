;;;; game-2048-tests.lisp -- tests for the game-2048 system.
;;;; Uses Allegro CL's built-in tester module (package util.test).
;;;; (util.test::test EXPECTED FORM &key test multiple-values ...)

(eval-when (:compile-toplevel :load-toplevel :execute)
  (require :tester))

(defpackage #:game-2048-tests
  (:use #:common-lisp)
  (:export #:run-tests))

(in-package :game-2048-tests)

(defun make-board (rows)
  "Build a 4x4 board from a list of 4 lists of 4 integers."
  (let ((board (make-array '(4 4) :initial-element 0)))
    (loop for r from 0 for row in rows
          do (loop for c from 0 for v in row
                   do (setf (aref board r c) v)))
    board))

(defun board-rows (board)
  (loop for r from 0 below 4
        collect (loop for c from 0 below 4 collect (aref board r c))))

(defun count-tiles (board)
  (loop for r from 0 below 4
        sum (loop for c from 0 below 4 count (/= 0 (aref board r c)))))

(defun sum-tiles (board)
  (loop for r from 0 below 4
        sum (loop for c from 0 below 4 sum (aref board r c))))

(defun run-play (input-string)
  "Run PLAY on INPUT-STRING with string streams; return the output text."
  (with-output-to-string (out)
    (game-2048:play :input (make-string-input-stream input-string)
                    :output out
                    :random-state (make-random-state t))))

;;; slide-row

(util.test::test '((4 4 0 0) 8)
                 (multiple-value-list (game-2048:slide-row (list 2 2 2 2)))
                 :test #'equal)

(util.test::test '((4 2 0 0) 4)
                 (multiple-value-list (game-2048:slide-row (list 2 2 2 0)))
                 :test #'equal)

(util.test::test '((4 0 0 0) 4)
                 (multiple-value-list (game-2048:slide-row (list 0 2 0 2)))
                 :test #'equal)

(util.test::test '((2 4 8 16) 0)
                 (multiple-value-list (game-2048:slide-row (list 2 4 8 16)))
                 :test #'equal)

(util.test::test '((4 4 0 0) 4)
                 (multiple-value-list (game-2048:slide-row (list 2 2 4 0)))
                 :test #'equal)

(util.test::test '(2 2 0 0)
                 (let ((row (list 2 2 0 0)))
                   (game-2048:slide-row row)
                   row)
                 :test #'equal)

(util.test::test t
                 (let ((row (list 0 0 0 0)))
                   (not (eq row (game-2048:slide-row row))))
                 :test #'eq)

;;; move

(util.test::test '(((4 4 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)) 8 t)
                 (multiple-value-bind (b pts changed)
                     (game-2048:move (make-board '((2 2 2 2) (0 0 0 0) (0 0 0 0) (0 0 0 0)))
                                     :left)
                   (list (board-rows b) pts changed))
                 :test #'equal)

(util.test::test '(((0 0 2 4) (0 0 0 0) (0 0 0 0) (0 0 0 0)) 4 t)
                 (multiple-value-bind (b pts changed)
                     (game-2048:move (make-board '((2 2 2 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))
                                     :right)
                   (list (board-rows b) pts changed))
                 :test #'equal)

(util.test::test '(((4 0 0 0) (8 0 0 0) (0 0 0 0) (0 0 0 0)) 12 t)
                 (multiple-value-bind (b pts changed)
                     (game-2048:move (make-board '((2 0 0 0) (2 0 0 0) (4 0 0 0) (4 0 0 0)))
                                     :up)
                   (list (board-rows b) pts changed))
                 :test #'equal)

(util.test::test '(((0 0 0 0) (0 0 0 0) (0 0 0 0) (4 0 0 0)) 4 t)
                 (multiple-value-bind (b pts changed)
                     (game-2048:move (make-board '((2 0 0 0) (2 0 0 0) (0 0 0 0) (0 0 0 0)))
                                     :down)
                   (list (board-rows b) pts changed))
                 :test #'equal)

(util.test::test '(((2 4 8 16) (0 0 0 0) (0 0 0 0) (0 0 0 0)) 0 nil)
                 (multiple-value-bind (b pts changed)
                     (game-2048:move (make-board '((2 4 8 16) (0 0 0 0) (0 0 0 0) (0 0 0 0)))
                                     :left)
                   (list (board-rows b) pts changed))
                 :test #'equal)

(util.test::test '((2 2 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))
                 (let ((b (make-board '((2 2 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))))
                   (game-2048:move b :left)
                   (board-rows b))
                 :test #'equal)

;;; spawn-tile

(util.test::test '(1 2 t t)
                 (let* ((b (make-board '((2 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))))
                        (new (game-2048:spawn-tile b (make-random-state t)))
                        (added (- (sum-tiles new) (sum-tiles b))))
                   (list (count-tiles b) (count-tiles new)
                         (and (member added '(2 4)) t)
                         (not (eq b new))))
                 :test #'equal)

(util.test::test t
                 (let* ((b (make-board '((2 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))))
                        (rs (make-random-state t)))
                   (equalp (board-rows (game-2048:spawn-tile b (make-random-state rs)))
                           (board-rows (game-2048:spawn-tile b (make-random-state rs)))))
                 :test #'eq)

;;; won-p and game-over-p

(util.test::test t
                 (game-2048:won-p (make-board '((2048 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))))
                 :test #'eq)

(util.test::test nil
                 (game-2048:won-p (make-board '((1024 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))))
                 :test #'eq)

(util.test::test t
                 (game-2048:game-over-p
                  (make-board '((2 4 2 4) (4 2 4 2) (2 4 2 4) (4 2 4 2))))
                 :test #'eq)

(util.test::test nil
                 (game-2048:game-over-p
                  (make-board '((2 4 2 4) (4 2 4 2) (2 4 2 4) (4 2 4 4))))
                 :test #'eq)

(util.test::test nil
                 (game-2048:game-over-p
                  (make-board '((2 4 2 4) (4 2 4 2) (2 4 2 4) (4 2 4 0))))
                 :test #'eq)

;;; play (string streams only)

(util.test::test t
                 (and (search "Score: 0" (run-play (format nil "q~%"))) t)
                 :test #'eq)

(util.test::test t
                 (and (search "Score: 0" (run-play "")) t)
                 :test #'eq)

(util.test::test t
                 (and (search "Invalid key" (run-play (format nil "x~%q~%"))) t)
                 :test #'eq)

(util.test::test t
                 (and (search "Move (" (run-play (format nil "a~%d~%w~%s~%q~%"))) t)
                 :test #'eq)

(util.test::test t
                 (if (search "Invalid key" (run-play (format nil "  q  ~%"))) nil t)
                 :test #'eq)

(defun run-tests ()
  "Print the tester summary and return the number of unexpected failures."
  (format t "~&Unexpected test failures: ~D~%"
          util.test::*test-unexpected-failures*)
  util.test::*test-unexpected-failures*)
