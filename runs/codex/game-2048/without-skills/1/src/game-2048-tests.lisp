(eval-when (:compile-toplevel :load-toplevel :execute)
  (require :tester))

(defpackage :game-2048-tests
  (:use :common-lisp :util.test))

(in-package :game-2048-tests)

(defun %board (&rest values)
  (make-array '(4 4) :initial-contents
              (loop for row below 4
                    collect (loop for column below 4
                                  collect (nth (+ (* row 4) column) values)))))

(test t (progn
  (multiple-value-bind (row points) (game-2048:slide-row '(2 2 2 2))
    (assert (equal row '(4 4 0 0)))
    (assert (= points 8)))
  (multiple-value-bind (row points) (game-2048:slide-row '(2 2 2 0))
    (assert (equal row '(4 2 0 0)))
    (assert (= points 4)))
  (multiple-value-bind (row points) (game-2048:slide-row '(0 2 0 2))
    (assert (equal row '(4 0 0 0)))
    (assert (= points 4)))
  t))

(test t (progn
  (let ((board (%board 2 2 2 0  0 0 0 0  0 0 0 0  0 0 0 0)))
    (multiple-value-bind (moved score changed) (game-2048:move board :left)
      (assert (= score 4))
      (assert changed)
      (assert (= (aref moved 0 0) 4))
      (assert (= (aref moved 0 1) 2))
      (assert (= (aref board 0 0) 2)))
    (multiple-value-bind (moved score changed) (game-2048:move board :right)
      (declare (ignore score))
      (assert changed)
      (assert (= (aref moved 0 2) 2))
      (assert (= (aref moved 0 3) 4))))
  t))

(test t (progn
  (let* ((board (%board 0 0 0 0  0 0 0 0  0 0 0 0  0 0 0 0))
         (state-a (make-random-state t))
         (state-b (make-random-state state-a))
         (spawn-a (game-2048:spawn-tile board state-a))
         (spawn-b (game-2048:spawn-tile board state-b)))
    (assert (equalp spawn-a spawn-b))
    (assert (= (loop for row below 4 sum
                 (loop for col below 4 count (plusp (aref spawn-a row col)))) 1)))
  (assert (game-2048:won-p (%board 0 0 0 0  0 2048 0 0  0 0 0 0  0 0 0 0)))
  (assert (not (game-2048:won-p (%board 0 0 0 0  0 2 0 0  0 0 0 0  0 0 0 0))))
  (assert (game-2048:game-over-p
           (%board 2 4 8 16  32 64 128 256  512 1024 2 4  8 16 32 64)))
  (assert (not (game-2048:game-over-p
                (%board 2 4 2 4  4 2 4 2  2 4 2 4  4 2 4 0))))
  t))

(test t (progn
  (let ((output (make-string-output-stream)))
    (game-2048:play :input (make-string-input-stream (format nil "x~%q~%"))
                    :output output
                    :random-state (make-random-state t))
    (let ((printed (get-output-stream-string output)))
      (assert (search "Score: 0" printed))
      (assert (>= (count #\| printed) 8))))
  t))
