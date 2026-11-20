;;;; Hidden tests for the dummy slide-row task. Never visible during a run.
;;;; Every assertion is one top-level tester form: the grader counts them.

(eval-when (:compile-toplevel :load-toplevel :execute)
  (require :tester))

(defpackage :slide-row-hidden-tests
  (:use :cl :util.test :slide-row))

(in-package :slide-row-hidden-tests)

(defun slide (row)
  (multiple-value-list (slide-row row)))

(test '((0 0 0 0) 0) (slide (list 0 0 0 0)) :test #'equal)
(test '((2 4 8 16) 0) (slide (list 2 4 8 16)) :test #'equal)
(test '((2 4 0 0) 0) (slide (list 0 2 0 4)) :test #'equal)
(test '((8 0 0 0) 8) (slide (list 0 4 0 4)) :test #'equal)
(test '((4 4 0 0) 4) (slide (list 2 0 2 4)) :test #'equal)
(test '((4 2 0 0) 4) (slide (list 0 2 2 2)) :test #'equal)
(test '((4 4 0 0) 8) (slide (list 2 2 2 2)) :test #'equal)
(test '((8 4 0 0) 12) (slide (list 4 4 2 2)) :test #'equal)
(test '((8 8 0 0) 8) (slide (list 4 4 8 0)) :test #'equal)
(test '((2 8 2 0) 8) (slide (list 2 4 4 2)) :test #'equal)
(test '(2 2 4 0)
      (let ((row (list 2 2 4 0)))
        (slide row)
        row)
      :test #'equal)
