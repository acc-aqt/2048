;;; Tests for game-2048, using Allegro CL's tester module (package util.test).
;;; Each check is a util.test:test call that must return true.

(eval-when (:compile-toplevel :load-toplevel :execute)
  (require :asdf)
  (require :tester)
  ;; Make sure the game system is loadable when this file is loaded directly.
  (pushnew (make-pathname :name nil :type nil
                          :defaults (or *compile-file-truename* *load-truename*))
           asdf:*central-registry* :test #'equal)
  (asdf:load-system "game-2048"))

(defpackage :game-2048-tests
  (:use :common-lisp :game-2048))

(in-package :game-2048-tests)

(defmacro check-equal (expected form)
  "Pass if FORM is EQUAL to the literal EXPECTED."
  `(util.test:test t (equal ,form ',expected)))

(defun board (rows)
  "Make a 4x4 board from a list of four lists of four integers."
  (let ((b (make-array '(4 4) :initial-element 0)))
    (loop for row in rows
          for r from 0
          do (loop for v in row
                   for c from 0
                   do (setf (aref b r c) v)))
    b))

(defun board-list (b)
  (loop for r below 4 collect (loop for c below 4 collect (aref b r c))))

(defun run-play (input-string)
  (let ((out (make-string-output-stream)))
    (play :input (make-string-input-stream input-string)
          :output out
          :random-state (make-random-state t))
    (get-output-stream-string out)))

(defun count-occurrences (needle haystack)
  (loop with start = 0
        for pos = (search needle haystack :start2 start)
        while pos
        count t
        do (setf start (+ pos (length needle)))))

;;; slide-row

(check-equal ((4 4 0 0) 8) (multiple-value-list (slide-row (list 2 2 2 2))))
(check-equal ((4 2 0 0) 4) (multiple-value-list (slide-row (list 2 2 2 0))))
(check-equal ((4 0 0 0) 4) (multiple-value-list (slide-row (list 0 2 0 2))))
(check-equal ((2 4 8 16) 0) (multiple-value-list (slide-row (list 2 4 8 16))))
(check-equal ((4 4 0 0) 4) (multiple-value-list (slide-row (list 2 2 4 0))))
(check-equal ((0 0 0 0) 0) (multiple-value-list (slide-row (list 0 0 0 0))))
(check-equal ((2 0 0 0) 0) (multiple-value-list (slide-row (list 0 0 0 2))))

(check-equal (2 2 0 0)
             (let ((row (list 2 2 0 0)))
               (slide-row row)
               row))

;;; move

(check-equal (((4 4 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)) 8 t)
             (multiple-value-bind (b points changed)
                 (move (board '((2 2 2 2) (0 0 0 0) (0 0 0 0) (0 0 0 0))) :left)
               (list (board-list b) points changed)))

(check-equal (((0 0 2 4) (0 0 0 0) (0 0 0 0) (0 0 0 0)) 4 t)
             (multiple-value-bind (b points changed)
                 (move (board '((2 2 2 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))) :right)
               (list (board-list b) points changed)))

(check-equal (((4 0 0 0) (4 0 0 0) (0 0 0 0) (0 0 0 0)) 4 t)
             (multiple-value-bind (b points changed)
                 (move (board '((2 0 0 0) (2 0 0 0) (0 0 0 0) (4 0 0 0))) :up)
               (list (board-list b) points changed)))

(check-equal (((0 0 0 0) (0 0 0 0) (4 0 0 0) (4 0 0 0)) 4 t)
             (multiple-value-bind (b points changed)
                 (move (board '((2 0 0 0) (2 0 0 0) (0 0 0 0) (4 0 0 0))) :down)
               (list (board-list b) points changed)))

(check-equal (0 nil)
             (multiple-value-bind (b points changed)
                 (move (board '((2 4 8 16) (0 0 0 0) (0 0 0 0) (0 0 0 0))) :left)
               (declare (ignore b))
               (list points changed)))

(check-equal ((2 2 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))
             (let ((b (board '((2 2 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))))
               (move b :left)
               (board-list b)))

(util.test:test 1
                (let ((new (move (board '((2 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))
                                 :left)))
                  (loop for r below 4
                        sum (loop for c below 4 count (/= 0 (aref new r c))))))

;;; spawn-tile

(check-equal (5 t)
             (let* ((b (board '((2 4 0 0) (8 16 0 0) (0 0 0 0) (0 0 0 0))))
                    (new (spawn-tile b (make-random-state t))))
               (list
                ;; one more non-empty cell than before (4 before, 5 after)
                (loop for r below 4 sum (loop for c below 4 count (/= 0 (aref new r c))))
                ;; old tiles unchanged; the new tile is 2 or 4
                (loop for r below 4
                      always (loop for c below 4
                                   always (or (= (aref b r c) (aref new r c))
                                              (and (zerop (aref b r c))
                                                   (member (aref new r c) '(2 4)))))))))

(check-equal ((2 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))
             (let ((b (board '((2 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))))
               (spawn-tile b (make-random-state t))
               (board-list b)))

(util.test:test t
                (let* ((b (board '((2 0 0 0) (0 4 0 0) (0 0 0 0) (0 0 0 0))))
                       (rs (make-random-state t))
                       (copy (make-random-state rs)))
                  (equalp (spawn-tile b rs) (spawn-tile b copy))))

;;; won-p and game-over-p

(util.test:test t (won-p (board '((2048 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))))
(util.test:test t (not (won-p (board '((1024 1024 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))))))

(util.test:test t (game-over-p (board '((2 4 2 4) (4 2 4 2) (2 4 2 4) (4 2 4 2)))))
(util.test:test t (not (game-over-p (board '((2 4 2 4) (4 2 4 2) (2 4 2 4) (4 2 4 0))))))
(util.test:test t (not (game-over-p (board '((2 2 4 8) (4 8 16 32) (64 128 256 512) (1024 2048 4 2))))))

;;; play

(util.test:test t (progn (run-play (format nil "q~%")) t))
(util.test:test t (progn (run-play "") t))
(util.test:test t (not (null (search "Score: 0" (run-play (format nil "q~%"))))))
(util.test:test 2 (count-occurrences "Score: " (run-play (format nil "x~%q~%"))))
(util.test:test 5 (count-occurrences "Score: " (run-play (format nil "a~%d~%w~%s~%q~%"))))
