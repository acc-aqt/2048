(in-package :game-2048)

(defun slide-row (row)
  "Slide ROW toward its first element and return the new row and score."
  (let ((tiles (remove 0 row))
        (result nil)
        (score 0))
    (loop while tiles
          for tile = (pop tiles)
          do (if (and tiles (= tile (first tiles)))
                 (let ((merged (* 2 tile)))
                   (pop tiles)
                   (incf score merged)
                   (push merged result))
                 (push tile result)))
    (setf result (nreverse result))
    (values (append result (make-list (- 4 (length result)) :initial-element 0))
            score)))

(defun copy-board (board)
  "Return a fresh copy of BOARD."
  (let ((copy (make-array '(4 4) :initial-element 0)))
    (dotimes (row 4 copy)
      (dotimes (column 4)
        (setf (aref copy row column) (aref board row column))))))

(defun move (board direction)
  "Move BOARD toward DIRECTION and return the board, score, and change flag."
  (unless (member direction '(:left :right :up :down))
    (error "Unknown direction: ~s" direction))
  (let ((result (make-array '(4 4) :initial-element 0))
        (score 0)
        (horizontal (member direction '(:left :right)))
        (reverse-order (member direction '(:right :down))))
    (dotimes (line 4)
      (let ((values (loop for index below 4
                          collect (if horizontal
                                      (aref board line index)
                                      (aref board index line)))))
        (multiple-value-bind (slid gained)
            (slide-row (if reverse-order (reverse values) values))
          (incf score gained)
          (when reverse-order
            (setf slid (reverse slid)))
          (loop for value in slid
                for index from 0
                do (if horizontal
                       (setf (aref result line index) value)
                       (setf (aref result index line) value))))))
    (values result score (not (equalp result board)))))

(defun spawn-tile (board random-state)
  "Return a fresh board with a randomly placed 2 or 4."
  (let ((empty (loop for row below 4
                     append (loop for column below 4
                                  when (zerop (aref board row column))
                                    collect (cons row column)))))
    (let* ((copy (copy-board board))
           (position (nth (random (length empty) random-state) empty))
           (tile (if (< (random 10 random-state) 9) 2 4)))
      (setf (aref copy (car position) (cdr position)) tile)
      copy)))

(defun won-p (board)
  "Return true when BOARD contains a 2048 tile."
  (loop for row below 4
        thereis (loop for column below 4
                      thereis (= (aref board row column) 2048))))

(defun game-over-p (board)
  "Return true when every direction leaves BOARD unchanged."
  (loop for direction in '(:left :right :up :down)
        always (not (third (multiple-value-list (move board direction))))))

(defun print-board (board score output)
  "Print the board and score to OUTPUT."
  (format output "Score: ~d~%" score)
  (dotimes (row 4)
    (dotimes (column 4)
      (if (zerop (aref board row column))
          (format output "    .")
          (format output "~5d" (aref board row column))))
    (terpri output)))

(defun play (&key (input *standard-input*) (output *standard-output*)
                  (random-state (make-random-state t)))
  "Run a text game using INPUT, OUTPUT, and RANDOM-STATE."
  (let ((board (make-array '(4 4) :initial-element 0))
        (score 0)
        (reported-win nil))
    (setf board (spawn-tile board random-state))
    (setf board (spawn-tile board random-state))
    (loop
      do (print-board board score output)
         (when (and (won-p board) (not reported-win))
           (format output "You won!~%")
           (setf reported-win t))
         (when (game-over-p board)
           (format output "Game over!~%")
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
               (multiple-value-bind (new-board gained changed)
                   (move board direction)
                 (when changed
                   (setf board (spawn-tile new-board random-state))
                   (incf score gained)))))))))
