(in-package :game-2048)

(defun slide-row (row)
  "Slide ROW toward its first element, merging equal pairs once each.
Return a fresh list of the same length and the points gained."
  (let ((tiles (remove 0 row))
        (out '())
        (points 0))
    (loop while tiles
          do (let ((a (pop tiles)))
               (if (and tiles (= a (first tiles)))
                   (let ((merged (* 2 a)))
                     (pop tiles)
                     (push merged out)
                     (incf points merged))
                   (push a out))))
    (let ((result (reverse out)))
      (values (append result
                      (make-list (- (length row) (length result))
                                 :initial-element 0))
              points))))

(defun line-positions (direction index)
  "Return the (row . column) cells of line INDEX, front cell first, for DIRECTION."
  (ecase direction
    (:left (loop for c from 0 below 4 collect (cons index c)))
    (:right (loop for c from 3 downto 0 collect (cons index c)))
    (:up (loop for r from 0 below 4 collect (cons r index)))
    (:down (loop for r from 3 downto 0 collect (cons r index)))))

(defun move (board direction)
  "Slide every line of BOARD toward DIRECTION (:left :right :up :down).
Return a fresh board, the points gained and true if any cell changed."
  (let ((new (make-array '(4 4) :initial-element 0))
        (points 0)
        (changed nil))
    (dotimes (i 4)
      (let ((positions (line-positions direction i)))
        (multiple-value-bind (slid gained)
            (slide-row (mapcar (lambda (p) (aref board (car p) (cdr p)))
                               positions))
          (incf points gained)
          (loop for p in positions
                for v in slid
                do (unless (= v (aref board (car p) (cdr p)))
                     (setf changed t))
                   (setf (aref new (car p) (cdr p)) v)))))
    (values new points changed)))

(defun copy-board (board)
  "Return a fresh copy of BOARD."
  (let ((new (make-array '(4 4) :initial-element 0)))
    (dotimes (r 4 new)
      (dotimes (c 4)
        (setf (aref new r c) (aref board r c))))))

(defun spawn-tile (board random-state)
  "Return a fresh copy of BOARD with one new tile (2 or 4) in a random empty cell."
  (let* ((new (copy-board board))
         (empties '()))
    (dotimes (r 4)
      (dotimes (c 4)
        (when (zerop (aref new r c))
          (push (cons r c) empties))))
    (let* ((cell (nth (random (length empties) random-state) empties))
           (value (if (< (random 10 random-state) 9) 2 4)))
      (setf (aref new (car cell) (cdr cell)) value))
    new))

(defun won-p (board)
  "True if BOARD contains a 2048 tile."
  (if (loop for r from 0 below 4
              thereis (loop for c from 0 below 4
                              thereis (= (aref board r c) 2048)))
      t
      nil))

(defun game-over-p (board)
  "True if no move in any direction would change BOARD."
  (every (lambda (direction)
           (not (nth-value 2 (move board direction))))
         '(:left :right :up :down)))

(defun make-empty-board ()
  "Return a new board with every cell empty."
  (make-array '(4 4) :initial-element 0))

(defun print-board (board score output)
  "Write BOARD and SCORE to OUTPUT. Empty cells print as a dot."
  (format output "~&Score: ~d~%" score)
  (dotimes (r 4)
    (dotimes (c 4)
      (let ((v (aref board r c)))
        (format output "~6@a" (if (zerop v) "." v))))
    (terpri output))
  (terpri output))

(defun key->direction (key)
  "Map the trimmed line KEY to a direction keyword, or nil if it is not a move key."
  (cond ((string= key "w") :up)
        ((string= key "a") :left)
        ((string= key "s") :down)
        ((string= key "d") :right)
        (t nil)))

(defun play (&key (input *standard-input*)
                  (output *standard-output*)
                  (random-state (make-random-state t)))
  "Play 2048 reading moves from INPUT and writing to OUTPUT.
Return the final score. Keys: w a s d move, q quits."
  (let* ((board (spawn-tile (spawn-tile (make-empty-board) random-state)
                            random-state))
         (score 0)
         (won nil))
    (loop
      (print-board board score output)
      (when (and (not won) (won-p board))
        (setf won t)
        (format output "You reached 2048! You win! You can keep playing.~%"))
      (when (game-over-p board)
        (format output "Game over! No move is possible. Final score: ~d~%" score)
        (return))
      (format output "Move (w/a/s/d, q to quit): ")
      (finish-output output)
      (let ((line (read-line input nil nil)))
        (when (null line)
          (return))
        (let* ((key (string-trim '(#\Space #\Tab #\Return) line))
               (direction (key->direction key)))
          (cond ((string= key "q")
                 (return))
                ((null direction)
                 (format output "Invalid key ~s. Use w, a, s, d, or q.~%" key))
                (t
                 (multiple-value-bind (moved gained changed)
                     (move board direction)
                   (when changed
                     (setf board (spawn-tile moved random-state))
                     (incf score gained))))))))
    score))
