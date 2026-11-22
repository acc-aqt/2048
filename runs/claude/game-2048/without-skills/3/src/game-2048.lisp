;;;; game-2048.lisp -- the game of 2048 as a text game.

(in-package :game-2048)

(defun copy-board (board)
  "Return a fresh 4x4 board with the same contents as BOARD."
  (let ((new (make-array '(4 4) :initial-element 0)))
    (dotimes (r 4 new)
      (dotimes (c 4)
        (setf (aref new r c) (aref board r c))))))

(defun make-empty-board ()
  (make-array '(4 4) :initial-element 0))

(defun slide-row (row)
  "Slide ROW toward its first element, merging tiles once per move.
Returns a fresh list of the same length and the points gained."
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
    (let ((result (nreverse out)))
      (values (append result (make-list (- (length row) (length result))
                                        :initial-element 0))
              points))))

(defun line-positions (direction index)
  "Cell positions (row . column) of line INDEX, in the order of the side
moved toward for DIRECTION."
  (ecase direction
    (:left  (loop for c from 0 to 3 collect (cons index c)))
    (:right (loop for c from 3 downto 0 collect (cons index c)))
    (:up    (loop for r from 0 to 3 collect (cons r index)))
    (:down  (loop for r from 3 downto 0 collect (cons r index)))))

(defun move (board direction)
  "Slide BOARD in DIRECTION (:left :right :up :down).
Returns a fresh board, the points gained, and true if any cell changed."
  (let ((new (make-empty-board))
        (points 0)
        (changed nil))
    (dotimes (index 4)
      (let* ((positions (line-positions direction index))
             (values (mapcar (lambda (p) (aref board (car p) (cdr p))) positions)))
        (multiple-value-bind (slid gained) (slide-row values)
          (incf points gained)
          (loop for p in positions
                for old in values
                for v in slid
                do (setf (aref new (car p) (cdr p)) v)
                   (unless (= old v) (setf changed t))))))
    (values new points changed)))

(defun spawn-tile (board random-state)
  "Return a fresh board equal to BOARD plus one new tile (2 with 90%, 4 with
10%) in a random empty cell. BOARD must have at least one empty cell."
  (let* ((new (copy-board board))
         (empties '()))
    (dotimes (r 4)
      (dotimes (c 4)
        (when (zerop (aref new r c))
          (push (cons r c) empties))))
    (let* ((n (length empties))
           (pos (nth (random n random-state) empties))
           (value (if (< (random 10 random-state) 9) 2 4)))
      (setf (aref new (car pos) (cdr pos)) value)
      new)))

(defun won-p (board)
  "True if BOARD contains a 2048 tile."
  (dotimes (r 4 nil)
    (dotimes (c 4)
      (when (= (aref board r c) 2048)
        (return-from won-p t)))))

(defun game-over-p (board)
  "True if no move in any direction would change BOARD."
  (notany (lambda (direction)
            (nth-value 2 (move board direction)))
          '(:left :right :up :down)))

(defun print-board (board score output)
  (format output "~&Score: ~D~%" score)
  (dotimes (r 4)
    (dotimes (c 4)
      (let ((v (aref board r c)))
        (format output "~6@A" (if (zerop v) "." v))))
    (terpri output))
  (terpri output)
  (force-output output))

(defun key-direction (key)
  (cdr (assoc key '(("w" . :up) ("a" . :left) ("s" . :down) ("d" . :right))
              :test #'string=)))

(defun play (&key (input *standard-input*)
                  (output *standard-output*)
                  (random-state (make-random-state t)))
  "Run the 2048 text game reading moves from INPUT and writing to OUTPUT.
Returns the final score."
  (let* ((board (spawn-tile (spawn-tile (make-empty-board) random-state)
                            random-state))
         (score 0)
         (announced-win nil))
    (loop
      (print-board board score output)
      (when (and (not announced-win) (won-p board))
        (setf announced-win t)
        (format output "You reached 2048! You win! You can keep playing.~%"))
      (when (game-over-p board)
        (format output "Game over! Final score: ~D~%" score)
        (return score))
      (format output "Move (w/a/s/d, q to quit): ")
      (force-output output)
      (let ((line (read-line input nil nil)))
        (when (null line)
          (return score))
        (let* ((key (string-trim '(#\Space #\Tab #\Return) line))
               (direction (key-direction key)))
          (cond ((string= key "q")
                 (return score))
                (direction
                 (multiple-value-bind (new-board points changed)
                     (move board direction)
                   (when changed
                     (incf score points)
                     (setf board (spawn-tile new-board random-state)))))
                (t
                 (format output "Invalid key: ~S. Use w, a, s, d, or q.~%"
                         key))))))))
