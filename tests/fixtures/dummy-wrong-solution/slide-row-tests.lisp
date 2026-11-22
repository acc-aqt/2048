(eval-when (:compile-toplevel :load-toplevel :execute)
  (require :tester))

(defpackage :slide-row-tests
  (:use :cl :util.test :slide-row))

(in-package :slide-row-tests)

(test '((2 0 0 0) 0) (multiple-value-list (slide-row '(0 0 0 2))) :test #'equal)
