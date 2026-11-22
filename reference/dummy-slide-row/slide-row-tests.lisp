(eval-when (:compile-toplevel :load-toplevel :execute)
  (require :tester))

(defpackage :slide-row-tests
  (:use :cl :util.test :slide-row))

(in-package :slide-row-tests)

(test '((4 4 0 0) 8) (multiple-value-list (slide-row '(2 2 2 2))) :test #'equal)
(test '((4 2 0 0) 4) (multiple-value-list (slide-row '(2 2 2 0))) :test #'equal)
(test '((2 0 0 0) 0) (multiple-value-list (slide-row '(0 0 0 2))) :test #'equal)
