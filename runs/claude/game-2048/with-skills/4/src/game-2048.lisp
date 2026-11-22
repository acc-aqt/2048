(in-package :game-2048)

(defun make-empty-board ()
  "Return a fresh empty 4x4 board."
  (make-array '(4 4) :initial-element 0))

(defun copy-board (board)
  "Return a fresh copy of BOARD."
  (let ((new (make-empty-board)))
    (dotimes (r 4 new)
      (dotimes (c 4)
        (setf (aref new r c) (aref board r c))))))

(defun slide-row (row)
  "Slide ROW toward its first element, merging equal neighbours once.
Return a fresh list of the same length and the points gained."
  (let ((tiles (remove 0 row))
        (merged '())
        (points 0))
    (loop while tiles
          do (let ((value (pop tiles)))
               (cond ((and tiles (= value (first tiles)))
                      (let ((sum (* 2 value)))
                        (push sum merged)
                        (incf points sum)
                        (pop tiles)))
                     (t (push value merged)))))
    (let ((result (nreverse merged)))
      (values (append result
                      (make-list (- (length row) (length result))
                                 :initial-element 0))
              points))))

(defun cell-position (direction line index)
  "Return the row and column of the INDEX-th cell of LINE, read toward DIRECTION."
  (ecase direction
    (:left (values line index))
    (:right (values line (- 3 index)))
    (:up (values index line))
    (:down (values (- 3 index) line))))

(defun move (board direction)
  "Slide every line of BOARD toward DIRECTION (:left :right :up :down).
Return a fresh board, the points gained, and true if any cell changed."
  (let ((new (make-empty-board))
        (points 0)
        (changed nil))
    (dotimes (line 4)
      (let ((cells (loop for i below 4
                         collect (multiple-value-bind (r c)
                                     (cell-position direction line i)
                                   (aref board r c)))))
        (multiple-value-bind (slid gained) (slide-row cells)
          (incf points gained)
          (loop for i below 4
                for value in slid
                do (multiple-value-bind (r c) (cell-position direction line i)
                     (setf (aref new r c) value)
                     (when (/= value (aref board r c))
                       (setf changed t)))))))
    (values new points changed)))

(defun spawn-tile (board random-state)
  "Return a fresh copy of BOARD with one new tile in a random empty cell.
The tile is 2 with probability 90% and 4 otherwise."
  (let* ((new (copy-board board))
         (empties (loop for r below 4
                        append (loop for c below 4
                                     when (zerop (aref board r c))
                                       collect (cons r c))))
         (spot (nth (random (length empties) random-state) empties))
         (value (if (< (random 10 random-state) 9) 2 4)))
    (setf (aref new (car spot) (cdr spot)) value)
    new))

(defun won-p (board)
  "True if BOARD contains a 2048 tile."
  (loop for r below 4
        thereis (loop for c below 4
                      thereis (= 2048 (aref board r c)))))

(defun game-over-p (board)
  "True if no move in any direction would change BOARD."
  (notany (lambda (direction)
            (nth-value 2 (move board direction)))
          '(:left :right :up :down)))

(defun normalize-key (line)
  "Return LINE without surrounding spaces, tabs or carriage returns."
  (string-trim '(#\Space #\Tab #\Return) line))

(defun key-direction (line)
  "Return the direction for the key in LINE, or nil if it is not a move key."
  (cdr (assoc (normalize-key line)
              '(("w" . :up) ("a" . :left) ("s" . :down) ("d" . :right))
              :test #'string=)))

(defun render-board (board score output)
  "Write BOARD and SCORE to OUTPUT."
  (format output "~%Score: ~d~%" score)
  (dotimes (r 4)
    (dotimes (c 4)
      (let ((value (aref board r c)))
        (format output "~6@a" (if (zerop value) "." value))))
    (terpri output))
  (finish-output output))

(defun play (&key (input *standard-input*)
                  (output *standard-output*)
                  (random-state (make-random-state t)))
  "Play 2048 as a text game, reading keys from INPUT and writing to OUTPUT.
Keys: w up, a left, s down, d right, q quit. Return the final score."
  (let ((board (spawn-tile (spawn-tile (make-empty-board) random-state)
                           random-state))
        (score 0)
        (won nil))
    (render-board board score output)
    (loop
      (let ((line (read-line input nil nil)))
        (when (or (null line) (string= (normalize-key line) "q"))
          (return score))
        (let ((direction (key-direction line)))
          (if (null direction)
              (format output "~%Invalid key. Use w (up), a (left), s (down), d (right) or q (quit).~%")
              (multiple-value-bind (moved gained changed) (move board direction)
                (when changed
                  (setf board (spawn-tile moved random-state))
                  (incf score gained))
                (when (and (not won) (won-p board))
                  (setf won t)
                  (format output "~%You reached 2048! You won. Keep playing or press q to quit.~%")))))
        (cond ((game-over-p board)
               (render-board board score output)
               (format output "~%Game over! Final score: ~d~%" score)
               (return score))
              (t (render-board board score output)))))))
