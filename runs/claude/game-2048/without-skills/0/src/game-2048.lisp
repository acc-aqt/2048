(in-package :game-2048)

;;; Boards are 4x4 arrays of integers; 0 is an empty cell.

(defun empty-board ()
  (make-array '(4 4) :initial-element 0))

(defun copy-board (board)
  (let ((new (make-array (array-dimensions board) :initial-element 0)))
    (dotimes (r (array-dimension board 0))
      (dotimes (c (array-dimension board 1))
        (setf (aref new r c) (aref board r c))))
    new))

(defun slide-row (row)
  "Slide ROW (a list of 4 integers) toward its first element, merging tiles.
Returns a fresh list of 4 integers and the points gained."
  (let ((tiles (remove 0 row))
        (out '())
        (points 0))
    (loop while tiles
          do (let ((a (pop tiles)))
               (if (and tiles (= a (first tiles)))
                   (let ((sum (* 2 a)))
                     (pop tiles)
                     (push sum out)
                     (incf points sum))
                   (push a out))))
    (let ((result (nreverse out)))
      (values (append result
                      (make-list (- (length row) (length result))
                                 :initial-element 0))
              points))))

(defun line-position (direction line index)
  "Return the (values row column) of cell INDEX of LINE, where index 0 is
the cell on the side moved toward for DIRECTION."
  (ecase direction
    (:left (values line index))
    (:right (values line (- 3 index)))
    (:up (values index line))
    (:down (values (- 3 index) line))))

(defun move (board direction)
  "Slide every row or column of BOARD toward DIRECTION.
Returns a fresh board, the points gained, and true if any cell changed."
  (let ((new (empty-board))
        (points 0)
        (changed nil))
    (dotimes (line 4)
      (let ((values-in-line
              (loop for i below 4
                    collect (multiple-value-bind (r c)
                                (line-position direction line i)
                              (aref board r c)))))
        (multiple-value-bind (slid gained) (slide-row values-in-line)
          (incf points gained)
          (loop for v in slid
                for i from 0
                do (multiple-value-bind (r c)
                       (line-position direction line i)
                     (setf (aref new r c) v)
                     (unless (= v (aref board r c))
                       (setf changed t)))))))
    (values new points changed)))

(defun spawn-tile (board random-state)
  "Return a copy of BOARD with one new tile (2 with 90%, 4 with 10%) placed
in a random empty cell."
  (let* ((new (copy-board board))
         (empties (loop for r below (array-dimension board 0)
                        nconc (loop for c below (array-dimension board 1)
                                    when (zerop (aref board r c))
                                      collect (cons r c))))
         (pos (nth (random (length empties) random-state) empties))
         (value (if (< (random 10 random-state) 9) 2 4)))
    (setf (aref new (car pos) (cdr pos)) value)
    new))

(defun won-p (board)
  "True if BOARD contains a 2048 tile."
  (loop for r below (array-dimension board 0)
        thereis (loop for c below (array-dimension board 1)
                      thereis (= 2048 (aref board r c)))))

(defun game-over-p (board)
  "True if no move in any direction would change BOARD."
  (notany (lambda (direction)
            (nth-value 2 (move board direction)))
          '(:left :right :up :down)))

(defparameter *key-moves*
  '(("w" . :up)
    ("a" . :left)
    ("s" . :down)
    ("d" . :right)))

(defun print-board (board score output)
  (format output "~&Score: ~D~%" score)
  (dotimes (r 4)
    (dotimes (c 4)
      (let ((v (aref board r c)))
        (if (zerop v)
            (format output "~6@A" ".")
            (format output "~6D" v))))
    (terpri output))
  (terpri output))

(defun play (&key (input *standard-input*)
                  (output *standard-output*)
                  (random-state (make-random-state t)))
  "Play 2048 as a text game reading key lines from INPUT and writing to OUTPUT.
Returns when the player quits, the input ends, or the game is over."
  (let* ((board (spawn-tile (spawn-tile (empty-board) random-state)
                            random-state))
         (score 0)
         (announced-win nil))
    (loop
      (print-board board score output)
      (when (game-over-p board)
        (format output "Game over! Final score: ~D~%" score)
        (return))
      (let ((line (read-line input nil nil)))
        (when (null line)
          (return))
        (let* ((key (string-trim '(#\Space #\Tab #\Return) line))
               (entry (assoc key *key-moves* :test #'string=)))
          (cond
            ((string= key "q")
             (return))
            ((null entry)
             (format output "Unknown key ~S. Use w, a, s, d or q.~%" key))
            (t
             (multiple-value-bind (new gained changed)
                 (move board (cdr entry))
               (when changed
                 (setf board (spawn-tile new random-state))
                 (incf score gained)
                 (when (and (not announced-win) (won-p board))
                   (setf announced-win t)
                   (format output
                           "You reached 2048! You win. You can keep playing.~%"))))))))))
  nil)
