(in-package :game-2048)

(defun slide-row (row)
  "Slide ROW toward its first element and return the row and merge score."
  (let* ((tiles (remove 0 row))
         (merged nil)
         (score 0))
    (loop while tiles
          for tile = (pop tiles)
          do (if (and tiles (= tile (first tiles)))
                 (let ((combined (+ tile (pop tiles))))
                   (push combined merged)
                   (incf score combined))
                 (push tile merged)))
    (let ((result (nreverse merged)))
      (values (append result
                      (make-list (- 4 (length result)) :initial-element 0))
              score))))

(defun copy-board (board)
  "Return a fresh copy of the four by four BOARD."
  (let ((copy (make-array '(4 4) :initial-element 0)))
    (dotimes (row 4 copy)
      (dotimes (column 4)
        (setf (aref copy row column) (aref board row column))))))

(defun move (board direction)
  "Move BOARD in DIRECTION, returning the new board, score, and change flag."
  (unless (member direction '(:left :right :up :down))
    (error "Unknown direction: ~a" direction))
  (let ((result (make-array '(4 4) :initial-element 0))
        (score 0))
    (dotimes (index 4)
      (let* ((line (loop for offset from 0 below 4
                         collect (if (member direction '(:left :right))
                                     (aref board index
                                           (if (eq direction :left) offset (- 3 offset)))
                                     (aref board
                                           (if (eq direction :up) offset (- 3 offset))
                                           index))))
             (slid-values (multiple-value-list
                           (slide-row (if (member direction '(:right :down))
                                          (reverse line)
                                          line))))
             (slid (first slid-values)))
        (incf score (second slid-values))
        (when (member direction '(:right :down))
          (setf slid (reverse slid)))
        (dotimes (offset 4)
          (if (member direction '(:left :right))
              (setf (aref result index offset)
                    (nth offset slid))
              (setf (aref result
                          offset
                          index)
                    (nth offset slid))))))
    (values result score (not (equalp board result)))))

(defun spawn-tile (board random-state)
  "Return a copy of BOARD with a randomly placed 2 or 4."
  (let ((empty (loop for row from 0 below 4
                     append (loop for column from 0 below 4
                                  when (zerop (aref board row column))
                                  collect (cons row column)))))
    (when (null empty)
      (error "Cannot spawn a tile on a full board."))
    (let* ((copy (copy-board board))
           (cell (nth (random (length empty) random-state) empty))
           (tile (if (< (random 10 random-state) 9) 2 4)))
      (setf (aref copy (car cell) (cdr cell)) tile)
      copy)))

(defun won-p (board)
  "Return true when BOARD contains a 2048 tile."
  (loop for row from 0 below 4
        thereis (loop for column from 0 below 4
                      thereis (= (aref board row column) 2048))))

(defun game-over-p (board)
  "Return true when no direction can change BOARD."
  (loop for direction in '(:left :right :up :down)
        always (not (third (multiple-value-list (move board direction))))))

(defun print-board (board score output)
  "Print BOARD and SCORE to OUTPUT."
  (format output "Score: ~d~%" score)
  (dotimes (row 4)
    (dotimes (column 4)
      (if (zerop (aref board row column))
          (format output "     .")
          (format output "~6d" (aref board row column))))
    (terpri output))
  (terpri output))

(defun play (&key (input *standard-input*) (output *standard-output*)
                  (random-state (make-random-state t)))
  "Run an interactive 2048 game using INPUT, OUTPUT, and RANDOM-STATE."
  (let ((board (make-array '(4 4) :initial-element 0))
        (score 0)
        (announced-win nil))
    (setf board (spawn-tile board random-state)
          board (spawn-tile board random-state))
    (loop
      (print-board board score output)
      (when (and (won-p board) (not announced-win))
        (format output "You won!~%")
        (setf announced-win t))
      (when (game-over-p board)
        (format output "Game over.~%")
        (return))
      (let ((line (read-line input nil nil)))
        (when (or (null line) (string-equal line "q"))
          (return))
        (let ((direction (cond ((string-equal line "w") :up)
                               ((string-equal line "a") :left)
                               ((string-equal line "s") :down)
                               ((string-equal line "d") :right)
                               (t nil))))
          (when direction
            (multiple-value-bind (next gained changed) (move board direction)
              (when changed
                (setf board (spawn-tile next random-state))
                (incf score gained)))))))))
