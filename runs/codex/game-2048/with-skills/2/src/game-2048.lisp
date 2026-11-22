(in-package :game-2048)

(defun slide-row (row)
  "Slide ROW toward its first element and return the new row and score."
  (let* ((tiles (remove 0 row))
         (result nil)
         (score 0))
    (loop while tiles
          do (if (and (rest tiles) (= (first tiles) (second tiles)))
                 (let ((merged (* 2 (first tiles))))
                   (push merged result)
                   (incf score merged)
                   (setf tiles (cddr tiles)))
                 (progn
                   (push (first tiles) result)
                   (setf tiles (rest tiles)))))
    (setf result (nreverse result))
    (values (append result (make-list (- 4 (length result)) :initial-element 0))
            score)))

(defun copy-board (board)
  "Return a fresh copy of the 4 by 4 BOARD."
  (let ((copy (make-array '(4 4) :initial-element 0)))
    (dotimes (row 4 copy)
      (dotimes (column 4)
        (setf (aref copy row column) (aref board row column))))))

(defun move (board direction)
  "Return BOARD after moving in DIRECTION, its score, and whether it changed."
  (let ((result (make-array '(4 4) :initial-element 0))
        (score 0))
    (unless (member direction '(:left :right :up :down))
      (error "Unknown move direction: ~s" direction))
    (dotimes (line 4)
      (let* ((values (loop for offset from 0 below 4
                           for row = (if (member direction '(:left :right))
                                         line offset)
                           for column = (if (member direction '(:left :right))
                                            offset line)
                           collect (aref board row column)))
             (toward-first (if (member direction '(:left :up))
                               values
                               (reverse values))))
        (multiple-value-bind (slid gained) (slide-row toward-first)
          (incf score gained)
          (let ((oriented (if (member direction '(:left :up))
                              slid
                              (reverse slid))))
            (loop for value in oriented
                  for offset from 0
                  for row = (if (member direction '(:left :right))
                                line offset)
                  for column = (if (member direction '(:left :right))
                                   offset line)
                  do (setf (aref result row column) value))))))
    (values result score (not (equalp board result)))))

(defun spawn-tile (board random-state)
  "Return a copy of BOARD with a randomly placed 2 or 4 in an empty cell."
  (let ((empty nil))
    (dotimes (row 4)
      (dotimes (column 4)
        (when (zerop (aref board row column))
          (push (cons row column) empty))))
    (unless empty
      (error "Cannot spawn a tile on a full board."))
    (let* ((copy (copy-board board))
           (cell (nth (random (length empty) random-state) empty))
           (tile (if (zerop (random 10 random-state)) 4 2)))
      (setf (aref copy (car cell) (cdr cell)) tile)
      copy)))

(defun won-p (board)
  "Return true when BOARD contains a 2048 tile."
  (loop for value across (make-array 16 :displaced-to board)
        thereis (= value 2048)))

(defun game-over-p (board)
  "Return true when none of the four moves changes BOARD."
  (loop for direction in '(:left :right :up :down)
        always (not (nth-value 2 (move board direction)))))

(defun print-board (board score output)
  "Print BOARD and SCORE to OUTPUT."
  (format output "Score: ~d~%" score)
  (dotimes (row 4)
    (dotimes (column 4)
      (let ((value (aref board row column)))
        (if (zerop value)
            (format output "|    ")
            (format output "| ~4d" value))))
    (format output "|~%"))
  (terpri output))

(defun play (&key (input *standard-input*) (output *standard-output*)
                  (random-state (make-random-state t)))
  "Play 2048 using INPUT and OUTPUT, drawing randomness from RANDOM-STATE."
  (let ((board (make-array '(4 4) :initial-element 0))
        (score 0)
        (announced-win nil))
    (setf board (spawn-tile board random-state)
          board (spawn-tile board random-state))
    (print-board board score output)
    (loop
      (when (game-over-p board)
        (format output "Game over.~%")
        (return))
      (let ((line (read-line input nil nil)))
        (when (or (null line) (and (= (length line) 1)
                                   (char-equal (char line 0) #\q)))
          (return))
        (let ((direction (and (= (length line) 1)
                              (case (char-downcase (char line 0))
                                (#\w :up)
                                (#\a :left)
                                (#\s :down)
                                (#\d :right)))))
          (when direction
            (multiple-value-bind (moved gained changed) (move board direction)
              (when changed
                (setf board (spawn-tile moved random-state))
                (incf score gained))))
          (print-board board score output)
          (when (and (not announced-win) (won-p board))
            (format output "You won!~%")
            (setf announced-win t)))))))
