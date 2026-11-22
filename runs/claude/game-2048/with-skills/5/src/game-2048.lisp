(in-package :game-2048)

(defun make-empty-board ()
  "Return a fresh 4x4 board filled with 0."
  (make-array '(4 4) :initial-element 0))

(defun copy-board (board)
  "Return a fresh copy of BOARD."
  (let ((new (make-empty-board)))
    (dotimes (r 4)
      (dotimes (c 4)
        (setf (aref new r c) (aref board r c))))
    new))

(defun slide-row (row)
  "Slide ROW toward its first element, merging equal tiles once per move.
Return a fresh list of 4 integers and the points gained."
  (let ((tiles (remove 0 row))
        (merged '())
        (points 0))
    (loop while tiles
          do (let ((a (pop tiles)))
               (if (and tiles (= a (first tiles)))
                   (let ((sum (* 2 a)))
                     (pop tiles)
                     (push sum merged)
                     (incf points sum))
                   (push a merged))))
    (let ((result (nreverse merged)))
      (values (append result
                      (make-list (- (length row) (length result))
                                 :initial-element 0))
              points))))

(defun line-positions (direction line)
  "Return the (row . column) cells of LINE, listed from the side DIRECTION moves toward."
  (let ((indices '(0 1 2 3)))
    (ecase direction
      (:left (mapcar (lambda (k) (cons line k)) indices))
      (:right (mapcar (lambda (k) (cons line k)) (reverse indices)))
      (:up (mapcar (lambda (k) (cons k line)) indices))
      (:down (mapcar (lambda (k) (cons k line)) (reverse indices))))))

(defun move (board direction)
  "Slide every line of BOARD toward DIRECTION. Return a fresh board,
the points gained, and true if any cell changed."
  (let ((new (make-empty-board))
        (total 0)
        (changed nil))
    (dotimes (line 4)
      (let* ((positions (line-positions direction line))
             (cells (mapcar (lambda (p) (aref board (car p) (cdr p))) positions)))
        (multiple-value-bind (slid points) (slide-row cells)
          (incf total points)
          (loop for p in positions
                for v in slid
                do (progn
                     (when (/= v (aref board (car p) (cdr p)))
                       (setf changed t))
                     (setf (aref new (car p) (cdr p)) v))))))
    (values new total changed)))

(defun spawn-tile (board random-state)
  "Return a fresh copy of BOARD with one new tile (2 or 4) in a random empty cell.
Randomness comes only from RANDOM-STATE."
  (let ((new (copy-board board))
        (empties '()))
    (dotimes (r 4)
      (dotimes (c 4)
        (when (zerop (aref board r c))
          (push (cons r c) empties))))
    (let* ((pos (nth (random (length empties) random-state) (nreverse empties)))
           (value (if (< (random 10 random-state) 9) 2 4)))
      (setf (aref new (car pos) (cdr pos)) value)
      new)))

(defun won-p (board)
  "True if BOARD contains a 2048 tile."
  (loop for r below 4
        thereis (loop for c below 4
                      thereis (= 2048 (aref board r c)))))

(defun game-over-p (board)
  "True if no move in any direction would change BOARD."
  (notany (lambda (d) (nth-value 2 (move board d)))
          '(:left :right :up :down)))

(defun print-state (board score output)
  "Write the score and BOARD to OUTPUT."
  (format output "~%Score: ~d~%" score)
  (dotimes (r 4)
    (dotimes (c 4)
      (let ((v (aref board r c)))
        (format output "~6a" (if (zerop v) "." v))))
    (terpri output)))

(defun key-direction (key)
  "Map a trimmed input line to a direction keyword, or nil."
  (cond ((string= key "w") :up)
        ((string= key "a") :left)
        ((string= key "s") :down)
        ((string= key "d") :right)
        (t nil)))

(defun play (&key (input *standard-input*)
                  (output *standard-output*)
                  (random-state (make-random-state t)))
  "Play 2048 as a text game, reading keys from INPUT and writing to OUTPUT.
Return the final score."
  (let ((board (spawn-tile (spawn-tile (make-empty-board) random-state)
                           random-state))
        (score 0)
        (announced-win nil))
    (loop
      (print-state board score output)
      (when (game-over-p board)
        (format output "Game over! No move is possible. Final score: ~d~%" score)
        (return))
      (finish-output output)
      (let ((line (read-line input nil nil)))
        (when (null line)
          (return))
        (let* ((key (string-trim '(#\Space #\Tab #\Return) line))
               (direction (key-direction key)))
          (cond ((string= key "q")
                 (return))
                ((null direction)
                 (format output "Invalid key ~s. Use w, a, s, d, or q.~%" key))
                (t
                 (multiple-value-bind (new points changed) (move board direction)
                   (cond (changed
                          (setf board (spawn-tile new random-state))
                          (incf score points)
                          (when (and (not announced-win) (won-p board))
                            (setf announced-win t)
                            (format output "You reached 2048! You win. Keep playing or press q to quit.~%")))
                         (t
                          (format output "That move changes nothing.~%")))))))))
    score))
