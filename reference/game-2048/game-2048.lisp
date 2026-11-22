;;;; The 2048 game: board moves, new tiles and the text game loop.

(in-package :game-2048)

(defconstant +size+ 4
  "The number of rows and columns of a board.")

(defun merge-tiles (tiles)
  "Merge equal neighbours of TILES, a list of non-zero values, starting at
the front. Each tile merges at most once. Return the merged list and the
points gained."
  (let ((merged '())
        (points 0))
    (loop while tiles
          do (let ((tile (pop tiles)))
               (when (and tiles (= tile (first tiles)))
                 (pop tiles)
                 (setf tile (* 2 tile))
                 (incf points tile))
               (push tile merged)))
    (values (nreverse merged) points)))

(defun slide-row (row)
  "Slide ROW, a list of 4 integers, toward its first element. Return a
fresh list of 4 integers and the points gained."
  (multiple-value-bind (merged points) (merge-tiles (remove 0 row))
    (values (append merged (make-list (- +size+ (length merged)) :initial-element 0))
            points)))

(defun line-cells (direction index)
  "Return the (row column) cells of line INDEX for a move in DIRECTION,
starting with the cell on the side moved toward."
  (loop for step below +size+
        for far = (- +size+ 1 step)
        collect (ecase direction
                  (:left (list index step))
                  (:right (list index far))
                  (:up (list step index))
                  (:down (list far index)))))

(defun move (board direction)
  "Slide every line of BOARD toward DIRECTION, one of :left, :right, :up or
:down. Return a fresh board, the points gained and whether anything moved."
  (let ((result (make-array (list +size+ +size+)))
        (points 0)
        (changed nil))
    (dotimes (index +size+)
      (let* ((cells (line-cells direction index))
             (line (loop for (row column) in cells
                         collect (aref board row column))))
        (multiple-value-bind (slid gained) (slide-row line)
          (incf points gained)
          (unless (equal slid line)
            (setf changed t))
          (loop for (row column) in cells
                for value in slid
                do (setf (aref result row column) value)))))
    (values result points changed)))

(defun copy-board (board)
  "Return a fresh board with the values of BOARD."
  (let ((copy (make-array (list +size+ +size+))))
    (dotimes (row +size+ copy)
      (dotimes (column +size+)
        (setf (aref copy row column) (aref board row column))))))

(defun empty-cells (board)
  "Return the (row column) cells of BOARD that hold 0."
  (loop for row below +size+
        append (loop for column below +size+
                     when (zerop (aref board row column))
                       collect (list row column))))

(defun spawn-tile (board random-state)
  "Return a fresh board equal to BOARD plus one new tile in a random empty
cell: 2 with probability 90%, 4 with probability 10%. All randomness comes
from RANDOM-STATE."
  (let* ((copy (copy-board board))
         (cells (empty-cells board))
         (cell (nth (random (length cells) random-state) cells))
         (value (if (< (random 10 random-state) 9) 2 4)))
    (setf (aref copy (first cell) (second cell)) value)
    copy))

(defparameter *directions* '(:left :right :up :down)
  "The four directions a move can go.")

(defun won-p (board)
  "True if BOARD contains a 2048 tile."
  (loop for index below (array-total-size board)
        thereis (= 2048 (row-major-aref board index))))

(defun game-over-p (board)
  "True if no move in any direction would change BOARD."
  (notany (lambda (direction) (nth-value 2 (move board direction)))
          *directions*))

(defparameter *keys* '(("w" . :up) ("a" . :left) ("s" . :down) ("d" . :right))
  "The input line for each direction.")

(defun new-game (random-state)
  "Return an empty board plus 2 new tiles."
  (spawn-tile (spawn-tile (make-array (list +size+ +size+) :initial-element 0)
                          random-state)
              random-state))

(defun print-board (board score output)
  "Write BOARD and SCORE to the stream OUTPUT."
  (dotimes (row +size+)
    (dotimes (column +size+)
      (let ((value (aref board row column)))
        (if (zerop value)
            (format output "~6@a" ".")
            (format output "~6d" value))))
    (format output "~%"))
  (format output "Score: ~d~%" score))

(defun read-command (input output)
  "Prompt on OUTPUT and read one line from INPUT. Return a direction keyword,
:quit for q or the end of INPUT, or nil for any other line."
  (format output "Move (w a s d, q quits): ")
  (force-output output)
  (let ((line (read-line input nil nil)))
    (cond ((null line) :quit)
          ((string= (string-trim " " line) "q") :quit)
          (t (cdr (assoc (string-trim " " line) *keys* :test #'string=))))))

(defun play (&key (input *standard-input*) (output *standard-output*)
               (random-state (make-random-state t)))
  "Run the 2048 text game, reading moves from INPUT and writing to OUTPUT.
New tiles take their randomness from RANDOM-STATE."
  (let ((board (new-game random-state))
        (score 0)
        (announced-win nil))
    (print-board board score output)
    (loop
      (let ((command (read-command input output)))
        (when (eq command :quit)
          (format output "~%Bye.~%")
          (return))
        (if (null command)
            (format output "~%Use w, a, s or d to move, q to quit.~%")
            (multiple-value-bind (next points changed) (move board command)
              (when changed
                (setf board (spawn-tile next random-state))
                (incf score points))))
        (print-board board score output)
        (when (and (won-p board) (not announced-win))
          (setf announced-win t)
          (format output "You reached 2048! Keep playing or press q.~%"))
        (when (game-over-p board)
          (format output "Game over. Final score: ~d~%" score)
          (return))))
    (values)))
