(in-package :game-2048)

(defparameter *key-directions*
  '(("w" . :up) ("a" . :left) ("s" . :down) ("d" . :right))
  "Map each move key to its direction.")

(defun make-empty-board ()
  "Return a fresh 4x4 board with every cell 0."
  (make-array '(4 4) :initial-element 0))

(defun copy-board (board)
  "Return a fresh copy of BOARD."
  (let ((new (make-empty-board)))
    (dotimes (r 4)
      (dotimes (c 4)
        (setf (aref new r c) (aref board r c))))
    new))

(defun slide-row (row)
  "Slide ROW toward its first element, merging pairs once. Return the new list and the points gained."
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
                    (make-list (- (length row) (length result))
                               :initial-element 0))
            points)))

(defun line-positions (index direction)
  "Return the (row . column) cells of line INDEX, in order from the side moved toward."
  (ecase direction
    (:left (loop for c below 4 collect (cons index c)))
    (:right (loop for c from 3 downto 0 collect (cons index c)))
    (:up (loop for r below 4 collect (cons r index)))
    (:down (loop for r from 3 downto 0 collect (cons r index)))))

(defun move (board direction)
  "Slide BOARD toward DIRECTION. Return a new board, the points gained, and true if anything changed."
  (let ((new (make-empty-board))
        (points 0)
        (changed nil))
    (dotimes (i 4)
      (let* ((cells (line-positions i direction))
             (cell-values (mapcar (lambda (p) (aref board (car p) (cdr p))) cells)))
        (multiple-value-bind (slid gained) (slide-row cell-values)
          (incf points gained)
          (loop for p in cells
                for v in slid
                do (setf (aref new (car p) (cdr p)) v)
                   (unless (= v (aref board (car p) (cdr p)))
                     (setf changed t))))))
    (values new points changed)))

(defun spawn-tile (board random-state)
  "Return a copy of BOARD with one new tile (2 or 4) in a random empty cell."
  (let* ((new (copy-board board))
         (empty (loop for r below 4
                      nconc (loop for c below 4
                                  when (zerop (aref new r c))
                                    collect (cons r c))))
         (pos (nth (random (length empty) random-state) empty))
         (value (if (< (random 10 random-state) 9) 2 4)))
    (setf (aref new (car pos) (cdr pos)) value)
    new))

(defun won-p (board)
  "True if BOARD contains a 2048 tile."
  (if (loop for r below 4
            thereis (loop for c below 4
                          thereis (= (aref board r c) 2048)))
      t
      nil))

(defun game-over-p (board)
  "True if no move in any direction would change BOARD."
  (every (lambda (direction)
           (not (nth-value 2 (move board direction))))
         '(:left :right :up :down)))

(defun show-state (board score output)
  "Print BOARD and SCORE to OUTPUT. Empty cells show as a dot."
  (terpri output)
  (dotimes (r 4)
    (dotimes (c 4)
      (let ((v (aref board r c)))
        (if (zerop v)
            (format output "~6a" ".")
            (format output "~6d" v))))
    (terpri output))
  (format output "Score: ~d~%" score))

(defun play (&key (input *standard-input*)
                  (output *standard-output*)
                  (random-state (make-random-state t)))
  "Play 2048 as a text game. Read moves (w a s d, q quits) from INPUT, write to OUTPUT. Return the score."
  (let ((board (spawn-tile (spawn-tile (make-empty-board) random-state) random-state))
        (score 0)
        (won-announced nil))
    (loop
      (show-state board score output)
      (when (and (not won-announced) (won-p board))
        (setf won-announced t)
        (format output "You reached 2048! You won. Keep playing or press q to quit.~%"))
      (when (game-over-p board)
        (format output "Game over. Final score: ~d~%" score)
        (return))
      (format output "Move (w a s d, q to quit): ")
      (finish-output output)
      (let* ((line (read-line input nil nil))
             (key (and line (string-trim '(#\Space #\Tab #\Return) line)))
             (direction (and key (cdr (assoc key *key-directions* :test #'string=)))))
        (cond ((null line) (return))
              ((string= key "q") (return))
              (direction
               (multiple-value-bind (new gained changed) (move board direction)
                 (if changed
                     (setf board (spawn-tile new random-state)
                           score (+ score gained))
                     (format output "That move changes nothing.~%"))))
              (t (format output "Invalid key. Use w, a, s, d or q.~%")))))
    score))
