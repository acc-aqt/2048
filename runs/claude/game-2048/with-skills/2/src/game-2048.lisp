(in-package :game-2048)

(defun make-empty-board ()
  "Return a fresh 4x4 board filled with 0."
  (make-array '(4 4) :initial-element 0))

(defun copy-board (board)
  "Return a fresh copy of BOARD."
  (let ((new (make-empty-board)))
    (dotimes (r 4 new)
      (dotimes (c 4)
        (setf (aref new r c) (aref board r c))))))

(defun board-cells (board)
  "Return every cell of BOARD as a flat list."
  (loop for r below 4
        nconc (loop for c below 4 collect (aref board r c))))

(defun slide-row (row)
  "Slide ROW toward its first element, merging pairs once.
Return the new row as a fresh list and the points gained."
  (let ((tiles (remove 0 row))
        (result '())
        (points 0))
    (loop while tiles
          do (let ((a (pop tiles)))
               (if (and tiles (= a (first tiles)))
                   (let ((merged (* 2 a)))
                     (pop tiles)
                     (push merged result)
                     (incf points merged))
                   (push a result))))
    (let ((out (nreverse result)))
      (values (append out (make-list (- (length row) (length out))
                                     :initial-element 0))
              points))))

(defun line-coords (direction k)
  "Return the cells of line K for DIRECTION, as (row . column), starting at the side moved toward."
  (ecase direction
    (:left (loop for j below 4 collect (cons k j)))
    (:right (loop for j from 3 downto 0 collect (cons k j)))
    (:up (loop for i below 4 collect (cons i k)))
    (:down (loop for i from 3 downto 0 collect (cons i k)))))

(defun move (board direction)
  "Slide BOARD toward DIRECTION (:left :right :up :down).
Return a fresh board, the points gained, and true if any cell changed."
  (let ((new (make-empty-board))
        (points 0)
        (changed nil))
    (dotimes (k 4)
      (let* ((coords (line-coords direction k))
             (cells (mapcar (lambda (rc) (aref board (car rc) (cdr rc))) coords)))
        (multiple-value-bind (out pts) (slide-row cells)
          (incf points pts)
          (loop for rc in coords
                for v in out
                do (setf (aref new (car rc) (cdr rc)) v)
                   (unless (= v (aref board (car rc) (cdr rc)))
                     (setf changed t))))))
    (values new points changed)))

(defun spawn-tile (board random-state)
  "Return a copy of BOARD with one new tile (2 or 4) in a random empty cell."
  (let* ((empties (loop for r below 4
                        nconc (loop for c below 4
                                    when (zerop (aref board r c))
                                      collect (cons r c))))
         (pos (nth (random (length empties) random-state) empties))
         (new (copy-board board)))
    (setf (aref new (car pos) (cdr pos))
          (if (< (random 10 random-state) 9) 2 4))
    new))

(defun won-p (board)
  "True if BOARD contains a 2048 tile."
  (some (lambda (v) (>= v 2048)) (board-cells board)))

(defun game-over-p (board)
  "True if no move in any direction would change BOARD."
  (notany (lambda (d) (nth-value 2 (move board d)))
          '(:left :right :up :down)))

(defun direction-for-key (key)
  "Return the direction for the key string KEY, or nil if it is not a move key."
  (cdr (assoc key '(("w" . :up) ("a" . :left) ("s" . :down) ("d" . :right))
              :test #'string=)))

(defun print-state (board score output)
  "Print BOARD and SCORE to OUTPUT."
  (format output "~%Score: ~d~%" score)
  (dotimes (r 4)
    (dotimes (c 4)
      (let ((v (aref board r c)))
        (if (zerop v)
            (format output "~6a" ".")
            (format output "~6d" v))))
    (terpri output))
  (finish-output output))

(defun play (&key (input *standard-input*)
                  (output *standard-output*)
                  (random-state (make-random-state t)))
  "Play 2048 reading moves from INPUT and writing the board to OUTPUT.
Keys: w a s d move, q quits. End of INPUT quits."
  (let ((board (spawn-tile (spawn-tile (make-empty-board) random-state)
                           random-state))
        (score 0)
        (won-told nil))
    (loop
      (print-state board score output)
      (when (and (not won-told) (won-p board))
        (format output "You reached 2048! You win! You can keep playing.~%")
        (setf won-told t))
      (when (game-over-p board)
        (format output "Game over! Final score: ~d~%" score)
        (return))
      (format output "Move (w/a/s/d, q to quit): ")
      (finish-output output)
      (let ((line (read-line input nil nil)))
        (unless line
          (return))
        (let* ((key (string-downcase
                     (string-trim '(#\Space #\Tab #\Return) line)))
               (direction (direction-for-key key)))
          (cond ((string= key "q")
                 (return))
                ((null direction)
                 (format output "Invalid key: ~a~%" line))
                (t
                 (multiple-value-bind (new-board points changed)
                     (move board direction)
                   (cond (changed
                          (setf board (spawn-tile new-board random-state))
                          (incf score points))
                         (t
                          (format output "That move changes nothing.~%")))))))))
    nil))
