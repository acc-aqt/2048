(in-package :game-2048)

(defun slide-row (row)
  "Slide ROW toward its first element and return the row and merge score."
  (let* ((tiles (remove 0 row))
         (result nil)
         (score 0))
    (loop while tiles
          for tile = (pop tiles)
          do (if (and tiles (= tile (first tiles)))
                 (let ((merged (* 2 tile)))
                   (pop tiles)
                   (push merged result)
                   (incf score merged))
                 (push tile result)))
    (setf result (nreverse result))
    (values (append result (make-list (- 4 (length result)) :initial-element 0))
            score)))

(defun copy-board (board)
  "Return a fresh copy of BOARD."
  (let ((copy (make-array '(4 4) :initial-element 0)))
    (dotimes (row 4)
      (dotimes (column 4)
        (setf (aref copy row column) (aref board row column))))
    copy))

(defun move (board direction)
  "Move BOARD in DIRECTION, returning the board, score, and changed flag."
  (unless (member direction '(:left :right :up :down))
    (error "Invalid direction: ~a" direction))
  (let ((result (make-array '(4 4) :initial-element 0))
        (score 0))
    (dotimes (line 4)
      (let ((values (loop for offset from 0 below 4
                          for actual-row = (cond
                                             ((member direction '(:left :right)) line)
                                             ((eq direction :down) (- 3 offset))
                                             (t offset))
                          for actual-column = (cond
                                                ((member direction '(:up :down)) line)
                                                ((eq direction :right) (- 3 offset))
                                                (t offset))
                          collect (aref board actual-row actual-column))))
        (multiple-value-bind (slid gained) (slide-row values)
          (incf score gained)
          (dotimes (offset 4)
            (let ((actual-row (cond
                                ((member direction '(:left :right)) line)
                                ((eq direction :down) (- 3 offset))
                                (t offset)))
                  (actual-column (cond
                                   ((member direction '(:up :down)) line)
                                   ((eq direction :right) (- 3 offset))
                                   (t offset))))
              (setf (aref result actual-row actual-column)
                    (nth offset slid)))))))
    (values result score (not (equalp board result)))))

(defun spawn-tile (board random-state)
  "Return a copy of BOARD with a randomly placed 2 or 4 tile."
  (let ((empty (loop for row from 0 below 4
                     append (loop for column from 0 below 4
                                  when (zerop (aref board row column))
                                    collect (cons row column)))))
    (unless empty
      (error "Cannot spawn a tile on a full board."))
    (let* ((copy (copy-board board))
           (cell (nth (random (length empty) random-state) empty))
           (value (if (< (random 10 random-state) 9) 2 4)))
      (setf (aref copy (car cell) (cdr cell)) value)
      copy)))

(defun won-p (board)
  "Return true when BOARD contains a 2048 tile."
  (loop for row from 0 below 4
        thereis (loop for column from 0 below 4
                      thereis (= (aref board row column) 2048))))

(defun game-over-p (board)
  "Return true when no direction changes BOARD."
  (loop for direction in '(:left :right :up :down)
        never (nth-value 2 (move board direction))))

(defun print-board (board score output)
  "Print BOARD and SCORE to OUTPUT."
  (format output "Score: ~d~%" score)
  (dotimes (row 4)
    (dotimes (column 4)
      (if (zerop (aref board row column))
          (format output "   .")
          (format output "~4d" (aref board row column))))
    (terpri output))
  (terpri output))

(defun play (&key (input *standard-input*) (output *standard-output*)
                  (random-state (make-random-state t)))
  "Run a text game using INPUT, OUTPUT, and RANDOM-STATE."
  (let ((board (make-array '(4 4) :initial-element 0))
        (score 0))
    (setf board (spawn-tile board random-state))
    (setf board (spawn-tile board random-state))
    (print-board board score output)
    (loop
      (when (game-over-p board)
        (format output "Game over.~%")
        (return))
      (let ((line (read-line input nil nil)))
        (unless line (return))
        (let* ((key (string-downcase (string-trim '(#\Space #\Tab #\Return) line)))
               (direction (cond ((string= key "w") :up)
                                ((string= key "a") :left)
                                ((string= key "s") :down)
                                ((string= key "d") :right)
                                (t nil))))
          (cond
            ((string= key "q") (return))
            (direction
             (multiple-value-bind (next gained changed) (move board direction)
               (when changed
                 (setf board (spawn-tile next random-state))
                 (incf score gained))))
            (t nil))
          (when (won-p board)
            (format output "You won!~%"))
          (print-board board score output)))))
  (values))
