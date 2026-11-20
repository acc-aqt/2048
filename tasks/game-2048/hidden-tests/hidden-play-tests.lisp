;;;; Hidden tests for the game-2048 task: play driven through string streams. They use only the
;;;; public interface from spec.md and call it as (funcall 'game-2048:name ...),
;;;; so names the implementation exports cannot clash with the helpers here.
;;;; `lisp-check --test` loads game-2048.asd from this file's directory first.

(eval-when (:compile-toplevel :load-toplevel :execute)
  (require :tester))

(defpackage :game-2048-hidden-play-tests
  (:use :cl :util.test))

(in-package :game-2048-hidden-play-tests)

;;; An error inside one assertion counts as that assertion failing, so the
;;; remaining assertions still run. TEST reads this variable when it is
;;; macroexpanded, so set it at compile time too.
(eval-when (:compile-toplevel :load-toplevel :execute)
  (setf *error-protect-tests* t))

(defparameter *seed* (make-random-state nil))

(defun seeded ()
  "Return a fresh copy of the fixed random state *SEED*."
  (make-random-state *seed*))

;;; play, driven through string streams. Only checks that it returns without
;;; an error and writes some output, never what the output says.

(defun play-output (lines)
  "Run PLAY on input made of LINES and return what it wrote."
  (let ((input (make-string-input-stream (format nil "~{~a~%~}" lines)))
        (output (make-string-output-stream)))
    (funcall 'game-2048:play :input input :output output :random-state (seeded))
    (get-output-stream-string output)))

(defun writes-output-p (lines)
  "True if PLAY on input made of LINES returns and writes some output."
  (plusp (length (play-output lines))))

(test t (writes-output-p '("q")))
(test t (writes-output-p '("a" "d" "w" "s" "q")))
(test t (writes-output-p '("x" "" "left" "q")))
(test t (writes-output-p (append (loop repeat 100 append (list "w" "a" "s" "d"))
                                 (list "q"))))
