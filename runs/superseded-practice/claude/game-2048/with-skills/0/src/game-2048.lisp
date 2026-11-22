(in-package :game-2048)

(defun make-empty-board ()
  "Return a fresh 4x4 board with every cell 0."
  (make-array '(4 4) :initial-element 0))

(defun copy-board (board)
  "Return a fresh copy of BOARD."
  (let ((new (make-empty-board)))
    (dotimes (i 4)
      (dotimes (j 4)
        (setf (aref new i j) (aref board i j))))
    new))

(defun board-rows (board)
  "Return the rows of BOARD as a list of lists."
  (loop for i below 4
        collect (loop for j below 4 collect (aref board i j))))

(defun slide-row (row)
  "Slide ROW toward its first element, merging equal neighbours once.
Return a fresh list of 4 integers and the points gained."
  (let ((tiles (remove 0 row))
        (result '())
        (points 0))
    (loop while tiles
          do (let ((value (pop tiles)))
               (if (and tiles (= (first tiles) value))
                   (let ((merged (* 2 value)))
                     (pop tiles)
                     (push merged result)
                     (incf points merged))
                   (push value result))))
    (let ((merged (reverse result)))
      (values (append merged
                      (make-list (- 4 (length merged)) :initial-element 0))
              points))))

(defun line-positions (direction k)
  "Return the cells of line K, as (row . column), ordered from the side
DIRECTION moves toward. K is a row for :left and :right, a column otherwise."
  (let ((cells (loop for n below 4
                     collect (ecase direction
                               ((:left :right) (cons k n))
                               ((:up :down) (cons n k))))))
    (if (member direction '(:right :down))
        (reverse cells)
        cells)))

(defun move (board direction)
  "Slide every line of BOARD toward DIRECTION (:left, :right, :up or :down).
Return a fresh board, the points gained, and true if any cell changed."
  (let ((new (make-empty-board))
        (points 0)
        (changed nil))
    (dotimes (k 4)
      (let* ((positions (line-positions direction k))
             (row (mapcar (lambda (p) (aref board (car p) (cdr p))) positions)))
        (multiple-value-bind (slid gained) (slide-row row)
          (incf points gained)
          (loop for p in positions
                for value in slid
                do (setf (aref new (car p) (cdr p)) value)
                   (unless (= value (aref board (car p) (cdr p)))
                     (setf changed t))))))
    (values new points changed)))

(defun spawn-tile (board random-state)
  "Return a fresh copy of BOARD with one new tile in a random empty cell.
The tile is 2 with probability 9/10 and 4 otherwise."
  (let* ((empty (loop for i below 4
                      append (loop for j below 4
                                   when (zerop (aref board i j))
                                     collect (cons i j))))
         (cell (nth (random (length empty) random-state) empty))
         (new (copy-board board)))
    (setf (aref new (car cell) (cdr cell))
          (if (< (random 10 random-state) 9) 2 4))
    new))

(defun won-p (board)
  "True if BOARD contains a 2048 tile."
  (loop for i below 4
        thereis (loop for j below 4
                      thereis (= (aref board i j) 2048))))

(defun game-over-p (board)
  "True if no move in any direction would change BOARD."
  (notany (lambda (direction)
            (nth-value 2 (move board direction)))
          '(:left :right :up :down)))

(defun key-direction (key)
  "Return the direction for the key string KEY, or nil if it is not a move."
  (cdr (assoc key '(("w" . :up) ("a" . :left) ("s" . :down) ("d" . :right))
              :test #'string=)))

(defun print-board (board score output)
  "Write BOARD and SCORE to OUTPUT."
  (format output "~%Score: ~d~%" score)
  (dolist (row (board-rows board))
    (format output "~{~5@a~}~%"
            (mapcar (lambda (v) (if (zerop v) "." v)) row))))

(defun play (&key (input *standard-input*)
                  (output *standard-output*)
                  (random-state (make-random-state t)))
  "Play 2048 reading keys from INPUT and writing to OUTPUT.
Keys: w a s d move, q quits. Returns when the player quits, INPUT ends,
or the game is over."
  (let ((board (spawn-tile (spawn-tile (make-empty-board) random-state)
                           random-state))
        (score 0)
        (won-announced nil))
    (print-board board score output)
    (loop
      (when (game-over-p board)
        (format output "~%Game over! Final score: ~d~%" score)
        (return))
      (format output "Move (w a s d, q quits): ")
      (finish-output output)
      (let ((line (read-line input nil nil)))
        (when (null line)
          (return))
        (let* ((key (string-downcase (string-trim '(#\Space #\Tab #\Return) line)))
               (direction (key-direction key)))
          (cond ((string= key "q")
                 (return))
                ((null direction)
                 (format output "~%Invalid key: ~a. Use w, a, s, d, or q.~%" key)
                 (print-board board score output))
                (t
                 (multiple-value-bind (new gained changed) (move board direction)
                   (when changed
                     (setf board (spawn-tile new random-state))
                     (incf score gained))
                   (print-board board score output)
                   (when (and changed (not won-announced) (won-p board))
                     (setf won-announced t)
                     (format output "~%You reached 2048! You win! Keep playing or press q to quit.~%"))))))))
    score))
