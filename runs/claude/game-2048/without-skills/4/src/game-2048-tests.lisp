;;;; game-2048-tests.lisp

(eval-when (:compile-toplevel :load-toplevel :execute)
  (require :tester))

(defpackage :game-2048-tests
  (:use :common-lisp :game-2048))

(in-package :game-2048-tests)

(defun board-from-rows (rows)
  "Make a 4x4 board from a list of four lists of four integers."
  (let ((board (make-array '(4 4) :initial-element 0)))
    (loop for row in rows
          for r from 0
          do (loop for value in row
                   for c from 0
                   do (setf (aref board r c) value)))
    board))

(defun board-rows (board)
  (loop for r from 0 below 4
        collect (loop for c from 0 below 4 collect (aref board r c))))

(defun move-summary (board direction)
  "Run MOVE and return (rows points changed) as one list."
  (multiple-value-bind (new points changed) (move board direction)
    (list (board-rows new) points changed)))

(defun slide-summary (row)
  (multiple-value-list (slide-row row)))

;;; slide-row

(util.test::deftest slide-row.all-pairs
    (slide-summary (list 2 2 2 2))
  '((4 4 0 0) 8))

(util.test::deftest slide-row.three-of-a-kind
    (slide-summary (list 2 2 2 0))
  '((4 2 0 0) 4))

(util.test::deftest slide-row.gaps
    (slide-summary (list 0 2 0 2))
  '((4 0 0 0) 4))

(util.test::deftest slide-row.no-merge
    (slide-summary (list 2 4 8 16))
  '((2 4 8 16) 0))

(util.test::deftest slide-row.no-double-merge
    (slide-summary (list 2 2 4 0))
  '((4 4 0 0) 4))

(util.test::deftest slide-row.empty
    (slide-summary (list 0 0 0 0))
  '((0 0 0 0) 0))

(util.test::deftest slide-row.does-not-modify-input
    (let ((row (list 2 2 0 0)))
      (slide-row row)
      row)
  '(2 2 0 0))

;;; move

(util.test::deftest move.left-merges
    (move-summary (board-from-rows '((2 2 2 2) (0 0 0 0) (0 0 0 0) (0 0 0 0)))
                  :left)
  '(((4 4 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)) 8 t))

(util.test::deftest move.right-merges
    (move-summary (board-from-rows '((2 2 2 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))
                  :right)
  '(((0 0 2 4) (0 0 0 0) (0 0 0 0) (0 0 0 0)) 4 t))

(util.test::deftest move.up-merges-columns
    (move-summary (board-from-rows '((2 0 0 0) (2 0 0 0) (4 0 0 0) (0 0 0 0)))
                  :up)
  '(((4 0 0 0) (4 0 0 0) (0 0 0 0) (0 0 0 0)) 4 t))

(util.test::deftest move.down-merges-columns
    (move-summary (board-from-rows '((2 0 0 0) (2 0 0 0) (0 0 0 0) (4 0 0 0)))
                  :down)
  '(((0 0 0 0) (0 0 0 0) (0 0 0 0) (4 0 0 0)) 4 t))

(util.test::deftest move.no-change-reports-nil
    (move-summary (board-from-rows '((2 4 8 16) (0 0 0 0) (0 0 0 0) (0 0 0 0)))
                  :left)
  '(((2 4 8 16) (0 0 0 0) (0 0 0 0) (0 0 0 0)) 0 nil))

(util.test::deftest move.does-not-modify-board
    (let ((board (board-from-rows '((2 2 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))))
      (move board :left)
      (board-rows board))
  '((2 2 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))

;;; spawn-tile

(util.test::deftest spawn-tile.adds-one-tile
    (let* ((board (board-from-rows '((2 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))))
           (new (spawn-tile board (make-random-state nil)))
           (added 0))
      (dotimes (r 4)
        (dotimes (c 4)
          (when (and (zerop (aref board r c)) (/= 0 (aref new r c)))
            (incf added))))
      added)
  '1)

(util.test::deftest spawn-tile.keeps-existing-tiles
    (let* ((board (board-from-rows '((2 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))))
           (new (spawn-tile board (make-random-state nil))))
      (aref new 0 0))
  '2)

(util.test::deftest spawn-tile.does-not-modify-board
    (let ((board (board-from-rows '((2 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))))
      (spawn-tile board (make-random-state nil))
      (board-rows board))
  '((2 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0)))

(util.test::deftest spawn-tile.deterministic-with-same-state
    (let* ((board (board-from-rows '((2 0 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))))
           (state (make-random-state nil)))
      ;; Two copies of the same state must give the same board.
      (equalp (board-rows (spawn-tile board (make-random-state state)))
              (board-rows (spawn-tile board (make-random-state state)))))
  'T)

(util.test::deftest spawn-tile.fills-only-empty-cell
    (let* ((board (board-from-rows '((2 4 8 0) (2 4 8 16) (2 4 8 16) (2 4 8 16))))
           (new (spawn-tile board (make-random-state t))))
      (loop for r below 4
            always (loop for c below 4
                         always (or (= (aref new r c) (aref board r c))
                                    (and (zerop (aref board r c))
                                         (member (aref new r c) '(2 4)))))))
  'T)

;;; won-p and game-over-p

(util.test::deftest won-p.true-with-2048
    (won-p (board-from-rows '((0 0 0 0) (0 2048 0 0) (0 0 0 0) (0 0 0 0))))
  'T)

(util.test::deftest won-p.false-without-2048
    (won-p (board-from-rows '((1024 1024 0 0) (0 0 0 0) (0 0 0 0) (0 0 0 0))))
  'NIL)

(util.test::deftest game-over-p.full-no-merges
    (game-over-p (board-from-rows '((2 4 2 4) (4 2 4 2) (2 4 2 4) (4 2 4 2))))
  'T)

(util.test::deftest game-over-p.empty-cell-is-not-over
    (game-over-p (board-from-rows '((2 4 2 4) (4 2 4 2) (2 4 2 4) (4 2 4 0))))
  'NIL)

(util.test::deftest game-over-p.merge-available
    (game-over-p (board-from-rows '((2 4 2 4) (4 2 4 2) (2 4 2 4) (4 2 4 4))))
  'NIL)

;;; play

(defun run-play (keys)
  "Run PLAY with KEYS (a list of lines) as input. Returns the output as a string."
  (with-output-to-string (out)
    (play :input (make-string-input-stream
                  (format nil "~{~A~%~}" keys))
          :output out
          :random-state (make-random-state t))))

(util.test::deftest play.quit-prints-score
    (let ((text (run-play '("q"))))
      (if (search "Score: 0" text) 'T 'NIL))
  'T)

(util.test::deftest play.end-of-input-returns
    (stringp (run-play '()))
  'T)

(util.test::deftest play.invalid-key-reported
    (if (search "Invalid key" (run-play '("x" "q"))) 'T 'NIL)
  'T)

(util.test::deftest play.returns-score-after-quit
    (with-input-from-string (in (format nil "q~%"))
      (play :input in
            :output (make-broadcast-stream)
            :random-state (make-random-state t)))
  0)

(util.test::deftest play.starts-with-two-tiles
    (let* ((text (run-play '("q")))
           (tiles (loop for ch across text count (member ch '(#\2 #\4)))))
      (if (>= tiles 2) 'T 'NIL))
  'T)
