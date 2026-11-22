;;;; game-2048.lisp -- the game 2048 as a text game.

(in-package :game-2048)

(defconstant +size+ 4
  "Number of rows and of columns of a board.")

(defun make-empty-board ()
  "A fresh, empty 4x4 board."
  (make-array (list +size+ +size+) :initial-element 0))

(defun slide-row (row)
  "Slide ROW toward its first element, merging tiles.
Returns a fresh list of the same length and the points gained."
  (let ((tiles (remove 0 row))
        (merged '())
        (points 0))
    (loop while tiles
          do (let ((a (pop tiles)))
               (if (and tiles (= a (first tiles)))
                   (let ((sum (+ a (pop tiles))))
                     (push sum merged)
                     (incf points sum))
                   (push a merged))))
    (setf merged (nreverse merged))
    (values (append merged
                    (make-list (- (length row) (length merged))
                               :initial-element 0))
            points)))

(defun line-positions (direction index)
  "The cells of line INDEX (a row for :left/:right, a column for :up/:down)
as (row . column) pairs, ordered from the side the move goes toward."
  (let ((ordered (loop for k below +size+ collect k)))
    (ecase direction
      (:left (mapcar (lambda (k) (cons index k)) ordered))
      (:right (mapcar (lambda (k) (cons index k)) (reverse ordered)))
      (:up (mapcar (lambda (k) (cons k index)) ordered))
      (:down (mapcar (lambda (k) (cons k index)) (reverse ordered))))))

(defun move (board direction)
  "Slide every line of BOARD toward DIRECTION (:left :right :up :down).
Returns a fresh board, the points gained, and true if any cell changed."
  (let ((new (make-empty-board))
        (points 0)
        (changed nil))
    (dotimes (index +size+)
      (let* ((positions (line-positions direction index))
             (old (mapcar (lambda (p) (aref board (car p) (cdr p))) positions)))
        (multiple-value-bind (slid gained) (slide-row old)
          (incf points gained)
          (unless (equal old slid)
            (setf changed t))
          (loop for p in positions
                for v in slid
                do (setf (aref new (car p) (cdr p)) v)))))
    (values new points changed)))

(defun spawn-tile (board random-state)
  "A fresh copy of BOARD with one new tile (2 with 90%, 4 with 10%)
in a random empty cell."
  (let ((empties '()))
    (dotimes (r +size+)
      (dotimes (c +size+)
        (when (zerop (aref board r c))
          (push (cons r c) empties))))
    (let* ((cell (nth (random (length empties) random-state) empties))
           (value (if (< (random 10 random-state) 9) 2 4))
           (new (make-empty-board)))
      (dotimes (r +size+)
        (dotimes (c +size+)
          (setf (aref new r c) (aref board r c))))
      (setf (aref new (car cell) (cdr cell)) value)
      new)))

(defun won-p (board)
  "True if BOARD contains a 2048 tile."
  (loop for r below +size+
        thereis (loop for c below +size+
                      thereis (= (aref board r c) 2048))))

(defun game-over-p (board)
  "True if no move in any direction would change BOARD."
  (notany (lambda (direction)
            (nth-value 2 (move board direction)))
          '(:left :right :up :down)))

(defun print-board (board score stream)
  "Print BOARD and SCORE to STREAM."
  (format stream "~&Score: ~D~%" score)
  (dotimes (r +size+)
    (dotimes (c +size+)
      (let ((v (aref board r c)))
        (format stream "~6@A" (if (zerop v) "." v))))
    (terpri stream))
  (terpri stream))

(defun key-direction (key)
  "Map a key line to a direction keyword, or NIL if it is not a move key."
  (cond ((string= key "w") :up)
        ((string= key "a") :left)
        ((string= key "s") :down)
        ((string= key "d") :right)
        (t nil)))

(defun play (&key (input *standard-input*)
                  (output *standard-output*)
                  (random-state (make-random-state t)))
  "Run the 2048 text game, reading keys from INPUT and writing to OUTPUT.
Returns the final score."
  (let ((board (make-empty-board))
        (score 0)
        (won-announced nil))
    (setf board (spawn-tile board random-state))
    (setf board (spawn-tile board random-state))
    (format output "~&2048. Keys: w=up a=left s=down d=right q=quit~%")
    (loop
      (print-board board score output)
      (when (game-over-p board)
        (format output "Game over! Final score: ~D~%" score)
        (return))
      (format output "Move> ")
      (finish-output output)
      (let ((line (read-line input nil nil)))
        (when (null line)
          (return))
        (let* ((key (string-trim '(#\Space #\Tab #\Return) line))
               (direction (key-direction key)))
          (cond ((string= key "q")
                 (return))
                ((null direction)
                 (format output "Invalid key: ~A~%" key))
                (t
                 (multiple-value-bind (new gained changed) (move board direction)
                   (if (not changed)
                       (format output "That move changes nothing.~%")
                       (progn
                         (setf board (spawn-tile new random-state))
                         (incf score gained)
                         (when (and (not won-announced) (won-p board))
                           (setf won-announced t)
                           (format output "You won! You reached 2048. Keep playing or press q to quit.~%"))))))))))
    score))
