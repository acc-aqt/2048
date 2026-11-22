(defpackage :game-2048-tests
  (:use :common-lisp))

(in-package :game-2048-tests)

(eval-when (:compile-toplevel :load-toplevel :execute)
  (require :tester))

(eval-when (:compile-toplevel :load-toplevel :execute)
  (import '(util.test:test)))

(defun check-equal (expected actual)
  (test (if (equal expected actual) t nil) t))
(defun check-true (value) (test (if value t nil) t))
(defun check-false (value) (test (if value nil t) t))

(defun test-slide-row-merges ()
  (multiple-value-bind (row score) (game-2048:slide-row '(2 2 2 2))
    (check-equal '(4 4 0 0) row) (check-equal 8 score))
  (multiple-value-bind (row score) (game-2048:slide-row '(2 2 4 0))
    (check-equal '(4 4 0 0) row) (check-equal 4 score))
  (multiple-value-bind (row score) (game-2048:slide-row '(0 2 0 2))
    (check-equal '(4 0 0 0) row) (check-equal 4 score)))

(defun test-moves-copy-score-and-noop ()
  (let ((board (make-array '(4 4) :initial-element 0)))
    (setf (aref board 0 0) 2 (aref board 0 1) 2)
    (multiple-value-bind (result score changed) (game-2048:move board :left)
      (check-equal 4 (aref result 0 0)) (check-equal 4 score)
      (check-true changed) (check-equal 2 (aref board 0 0)))
    (multiple-value-bind (result score changed) (game-2048:move board :up)
      (check-equal 0 score) (check-false changed)
      (check-true (not (eq result board))))))

(defun test-spawn-is-reproducible ()
  (let* ((board (make-array '(4 4) :initial-element 0))
         (first (game-2048:spawn-tile board (make-random-state 123)))
         (second (game-2048:spawn-tile board (make-random-state 123))))
    (check-true (equalp first second))
    (check-true (loop for row below 4 thereis
                  (loop for column below 4 thereis
                    (member (aref first row column) '(2 4)))))))

(defun test-win-and-game-over ()
  (let ((board (make-array '(4 4) :initial-element 2))
        (full (make-array '(4 4) :initial-element 2)))
    (setf (aref board 1 1) 2048)
    (check-true (game-2048:won-p board))
    (check-false (game-2048:game-over-p full))
    (dotimes (row 4)
      (dotimes (column 4)
        (setf (aref full row column) (if (evenp (+ row column)) 2 4))))
    (check-true (game-2048:game-over-p full))))

(defun test-play-uses-streams ()
  (let ((output (make-string-output-stream)))
    (game-2048:play :input (make-string-input-stream (format nil "x~%q~%"))
                    :output output :random-state (make-random-state 42))
    (let ((text (get-output-stream-string output)))
      (check-true (search "Score: 0" text))
      (check-true (search "Invalid key." text)))))

(defun run-tests ()
  (test-slide-row-merges)
  (test-moves-copy-score-and-noop)
  (test-spawn-is-reproducible)
  (test-win-and-game-over)
  (test-play-uses-streams))

(run-tests)
