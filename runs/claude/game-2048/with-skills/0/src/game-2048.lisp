(in-package :game-2048)

(defun make-board ()
  "Return a fresh empty 4x4 board."
  (make-array '(4 4) :initial-element 0))

(defun copy-board (board)
  "Return a fresh copy of BOARD."
  (let ((new (make-board)))
    (dotimes (r 4 new)
      (dotimes (c 4)
        (setf (aref new r c) (aref board r c))))))

(defun slide-row (row)
  "Slide ROW toward its first element, merging equal pairs once.
Return the new row as a fresh list of 4 integers, and the points gained."
  (let ((tiles (remove 0 row))
        (result '())
        (points 0))
    (loop while tiles
          do (let ((a (pop tiles)))
               (if (and tiles (= a (first tiles)))
                   (let ((sum (* 2 a)))
                     (pop tiles)
                     (push sum result)
                     (incf points sum))
                   (push a result))))
    (values (append (reverse result)
                    (make-list (- 4 (length result)) :initial-element 0))
            points)))

(defun line-positions (index direction)
  "Return the (row . column) cells of line INDEX, in the order a slide toward DIRECTION reads them."
  (ecase direction
    (:left (loop for c from 0 to 3 collect (cons index c)))
    (:right (loop for c from 3 downto 0 collect (cons index c)))
    (:up (loop for r from 0 to 3 collect (cons r index)))
    (:down (loop for r from 3 downto 0 collect (cons r index)))))

(defun move (board direction)
  "Slide every line of BOARD toward DIRECTION (:left, :right, :up or :down).
Return a fresh board, the points gained, and true if any cell changed."
  (let ((new (make-board))
        (points 0)
        (changed nil))
    (dotimes (i 4)
      (let* ((positions (line-positions i direction))
             (row (mapcar (lambda (p) (aref board (car p) (cdr p))) positions)))
        (multiple-value-bind (slid gained) (slide-row row)
          (incf points gained)
          (loop for p in positions
                for v in slid
                do (setf (aref new (car p) (cdr p)) v)
                   (unless (= v (aref board (car p) (cdr p)))
                     (setf changed t))))))
    (values new points changed)))

(defun spawn-tile (board random-state)
  "Return a fresh copy of BOARD with one new tile (2 with 90%, 4 with 10%)
in a random empty cell. Uses RANDOM-STATE for all randomness."
  (let* ((new (copy-board board))
         (empties (loop for r from 0 to 3
                        nconc (loop for c from 0 to 3
                                    when (zerop (aref board r c))
                                      collect (cons r c))))
         (pick (nth (random (length empties) random-state) empties))
         (value (if (< (random 10 random-state) 9) 2 4)))
    (setf (aref new (car pick) (cdr pick)) value)
    new))

(defun won-p (board)
  "True if BOARD contains a 2048 tile."
  (loop for r from 0 to 3
        thereis (loop for c from 0 to 3
                      thereis (= 2048 (aref board r c)))))

(defun game-over-p (board)
  "True if no move in any direction would change BOARD."
  (notany (lambda (direction)
            (nth-value 2 (move board direction)))
          '(:left :right :up :down)))

(defun key-direction (line)
  "Return the direction for the key LINE, or nil if it is not w, a, s or d."
  (cond ((string= line "w") :up)
        ((string= line "a") :left)
        ((string= line "s") :down)
        ((string= line "d") :right)
        (t nil)))

(defun print-state (board score output)
  "Print BOARD and SCORE to OUTPUT."
  (format output "~%Score: ~d~%" score)
  (dotimes (r 4)
    (dotimes (c 4)
      (let ((v (aref board r c)))
        (format output "~6@a" (if (zerop v) "." v))))
    (format output "~%")))

(defun play (&key (input *standard-input*)
                  (output *standard-output*)
                  (random-state (make-random-state t)))
  "Play 2048 as a text game. Read keys w, a, s, d from INPUT, quit with q
or end of input, and print the board to OUTPUT. New tiles use RANDOM-STATE."
  (let ((board (spawn-tile (spawn-tile (make-board) random-state) random-state))
        (score 0)
        (announced-win nil))
    (print-state board score output)
    (loop
      (when (game-over-p board)
        (format output "~%Game over! Final score: ~d~%" score)
        (return))
      (let ((line (read-line input nil nil)))
        (when (or (null line) (string= line "q"))
          (return))
        (let ((direction (key-direction line)))
          (if (null direction)
              (format output "Invalid key ~s. Use w, a, s, d, or q.~%" line)
              (multiple-value-bind (moved gained changed) (move board direction)
                (when changed
                  (setf board (spawn-tile moved random-state))
                  (incf score gained)))))
        (when (and (not announced-win) (won-p board))
          (setf announced-win t)
          (format output "~%You reached 2048! You win. Keep playing or type q to quit.~%"))
        (print-state board score output)))))
