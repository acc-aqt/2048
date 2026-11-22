(in-package :game-2048)

(defun slide-row (row)
  "Slide four tiles toward the start of ROW and return the score gained."
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
    (let ((merged-count (length result)))
      (values (append (nreverse result)
                      (make-list (- 4 merged-count) :initial-element 0))
              score))))

(defun copy-board (board)
  "Return a fresh copy of the four-by-four BOARD."
  (let ((copy (make-array '(4 4) :initial-element 0)))
    (dotimes (row 4 copy)
      (dotimes (column 4)
        (setf (aref copy row column) (aref board row column))))))

(defun move (board direction)
  "Return the moved board, score gained, and whether BOARD changed."
  (let ((result (make-array '(4 4) :initial-element 0))
        (score 0))
    (dotimes (line 4)
      (let* ((row-p (member direction '(:left :right)))
             (values (loop for offset from 0 below 4
                           for index = (if (member direction '(:left :right))
                                           offset
                                           (if (eq direction :down) (- 3 offset) offset))
                           collect (if row-p
                                       (aref board line index)
                                       (aref board index line))))
             (oriented (if (member direction '(:right :down))
                           (reverse values)
                           values)))
        (multiple-value-bind (slid gained) (slide-row oriented)
          (incf score gained)
          (let ((placed (if (member direction '(:right :down))
                            (reverse slid)
                            slid)))
            (dotimes (offset 4)
              (if row-p
                  (setf (aref result line offset)
                        (nth (if (eq direction :right) (- 3 offset) offset) placed))
                  (setf (aref result offset line) (nth offset placed))))))))
    (values result score
            (loop for row below 4
                  thereis (loop for column below 4
                                thereis (/= (aref board row column)
                                            (aref result row column)))))))

(defun spawn-tile (board random-state)
  "Return a fresh BOARD with a 2 or 4 in a randomly chosen empty cell."
  (let ((result (copy-board board))
        (empty nil))
    (dotimes (row 4)
      (dotimes (column 4)
        (when (zerop (aref board row column))
          (push (cons row column) empty))))
    (let* ((cell (nth (random (length empty) random-state) empty))
           (tile (if (< (random 10 random-state) 9) 2 4)))
      (setf (aref result (car cell) (cdr cell)) tile))
    result))

(defun won-p (board)
  "Return true when BOARD contains a 2048 tile."
  (loop for value across (make-array 16 :initial-contents
                                     (loop for row below 4
                                           append (loop for column below 4
                                                        collect (aref board row column))))
        thereis (= value 2048)))

(defun game-over-p (board)
  "Return true when no directional move changes BOARD."
  (loop for row below 4
        always (loop for column below 4
                     always (and (not (zerop (aref board row column)))
                                 (not (and (< column 3)
                                           (= (aref board row column)
                                              (aref board row (1+ column)))))
                                 (not (and (< row 3)
                                           (= (aref board row column)
                                              (aref board (1+ row) column))))))))

(defun print-board (board score output)
  "Print BOARD and SCORE to OUTPUT."
  (format output "Score: ~d~%" score)
  (dotimes (row 4)
    (format output "|~{~8a|~}~%"
            (loop for column below 4
                  for value = (aref board row column)
                  collect (if (zerop value) "" value))))
  (format output "~%"))

(defun play (&key (input *standard-input*) (output *standard-output*)
                  (random-state (make-random-state t)))
  "Play 2048 using INPUT, OUTPUT, and RANDOM-STATE."
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
                (incf score gained)))
            (when (and (not announced-win) (won-p board))
              (format output "You won!~%")
              (setf announced-win t))))
        (print-board board score output)))))
