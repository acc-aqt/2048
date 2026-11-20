;;;; Hidden tests for the game-2048 task: slide-row. They use only the
;;;; public interface from spec.md and call it as (funcall 'game-2048:name ...),
;;;; so names the implementation exports cannot clash with the helpers here.
;;;; `lisp-check --test` loads game-2048.asd from this file's directory first.

(eval-when (:compile-toplevel :load-toplevel :execute)
  (require :tester))

(defpackage :game-2048-hidden-slide-row-tests
  (:use :cl :util.test))

(in-package :game-2048-hidden-slide-row-tests)

;;; An error inside one assertion counts as that assertion failing, so the
;;; remaining assertions still run. TEST reads this variable when it is
;;; macroexpanded, so set it at compile time too.
(eval-when (:compile-toplevel :load-toplevel :execute)
  (setf *error-protect-tests* t))

(defun slide (&rest row)
  "Return the two values of SLIDE-ROW on ROW as a list."
  (multiple-value-list (funcall 'game-2048:slide-row row)))

(test '((0 0 0 0) 0) (slide 0 0 0 0) :test #'equal)
(test '((2 0 0 0) 0) (slide 0 0 0 2) :test #'equal)
(test '((2 4 8 16) 0) (slide 2 4 8 16) :test #'equal)
(test '((2 4 0 0) 0) (slide 0 2 0 4) :test #'equal)
(test '((4 0 0 0) 4) (slide 2 2 0 0) :test #'equal)
(test '((4 0 0 0) 4) (slide 2 0 2 0) :test #'equal)
(test '((16 0 0 0) 16) (slide 8 0 0 8) :test #'equal)
(test '((2048 0 0 0) 2048) (slide 0 1024 0 1024) :test #'equal)
(test '((4 4 0 0) 8) (slide 2 2 2 2) :test #'equal)
(test '((4 2 0 0) 4) (slide 2 2 2 0) :test #'equal)
(test '((4 4 2 0) 4) (slide 2 2 4 2) :test #'equal)
(test '((4 4 0 0) 4) (slide 2 2 4 0) :test #'equal)
(test '((4 4 0 0) 4) (slide 4 2 2 0) :test #'equal)
(test '((8 16 0 0) 24) (slide 4 4 8 8) :test #'equal)
(test '((8 4 0 0) 8) (slide 4 4 4 0) :test #'equal)

(defun row-after-slide (row)
  "Return ROW after calling SLIDE-ROW on it."
  (funcall 'game-2048:slide-row row)
  row)

(test '(2 2 0 4) (row-after-slide (list 2 2 0 4)) :test #'equal)
