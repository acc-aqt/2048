;;;; game-2048.lisp -- the game 2048 as a text game.

(in-package :game-2048)

(defun slide-row (row)
  "Slide ROW (a list of 4 integers) toward its first element, merging tiles.
Returns a fresh list of the same length and the points gained."
  (let ((tiles (remove 0 row))
        (merged '())
        (points 0))
    (loop while tiles
          do (let ((tile (pop tiles)))
               (cond ((and tiles (= tile (first tiles)))
                      (let ((sum (* 2 tile)))
                        (pop tiles)
                        (push sum merged)
                        (incf points sum)))
                     (t (push tile merged)))))
    (let ((result (reverse merged)))
      (values (append result
                      (make-list (- (length row) (length result))
                                 :initial-element 0))
              points))))

(defun line-coordinates (direction index)
  "Cells of line INDEX as (row . column) pairs, listed from the side moved toward."
  (ecase direction
    (:left  (loop for k from 0 below 4 collect (cons index k)))
    (:right (loop for k from 3 downto 0 collect (cons index k)))
    (:up    (loop for k from 0 below 4 collect (cons k index)))
    (:down  (loop for k from 3 downto 0 collect (cons k index)))))

(defun move (board direction)
  "Slide every line of BOARD toward DIRECTION (:left :right :up :down).
Returns a fresh board, the points gained, and true if any cell changed."
  (let ((new (make-array '(4 4) :initial-element 0))
        (points 0)
        (changed nil))
    (dotimes (index 4)
      (let* ((coords (line-coordinates direction index))
             (line (mapcar (lambda (c) (aref board (car c) (cdr c))) coords)))
        (multiple-value-bind (slid gained) (slide-row line)
          (incf points gained)
          (loop for c in coords
                for v in slid
                do (setf (aref new (car c) (cdr c)) v)
                   (unless (= v (aref board (car c) (cdr c)))
                     (setf changed t))))))
    (values new points changed)))

(defun copy-board (board)
  (let ((new (make-array '(4 4) :initial-element 0)))
    (dotimes (r 4 new)
      (dotimes (c 4)
        (setf (aref new r c) (aref board r c))))))

(defun spawn-tile (board random-state)
  "Return a fresh copy of BOARD with one new tile (2 with 90%, 4 with 10%)
in a random empty cell. BOARD must have at least one empty cell."
  (let* ((new (copy-board board))
         (empties (loop for r from 0 below 4
                        nconc (loop for c from 0 below 4
                                    when (zerop (aref new r c))
                                      collect (cons r c))))
         (pos (nth (random (length empties) random-state) empties))
         (value (if (< (random 10 random-state) 9) 2 4)))
    (setf (aref new (car pos) (cdr pos)) value)
    new))

(defun won-p (board)
  "True if BOARD contains a 2048 tile."
  (loop for r from 0 below 4
        thereis (loop for c from 0 below 4
                      thereis (= 2048 (aref board r c)))))

(defun game-over-p (board)
  "True if no move in any direction would change BOARD."
  (notany (lambda (direction)
            (nth-value 2 (move board direction)))
          '(:left :right :up :down)))

(defun show-board (board score output)
  (format output "~&")
  (dotimes (r 4)
    (dotimes (c 4)
      (let ((v (aref board r c)))
        (format output "~6@A" (if (zerop v) "." v))))
    (terpri output))
  (format output "Score: ~D~%" score))

(defun play (&key (input *standard-input*)
                  (output *standard-output*)
                  (random-state (make-random-state t)))
  "Play 2048 reading moves from INPUT and writing to OUTPUT.
Keys: w up, a left, s down, d right, q quit."
  (let ((board (spawn-tile (spawn-tile (make-array '(4 4) :initial-element 0)
                                       random-state)
                           random-state))
        (score 0)
        (won-announced nil))
    (loop
      (show-board board score output)
      (when (and (not won-announced) (won-p board))
        (setf won-announced t)
        (format output "You reached 2048! You win. You can keep playing.~%"))
      (when (game-over-p board)
        (format output "Game over: no move changes the board.~%")
        (return))
      (format output "Move (w/a/s/d, q to quit): ")
      (finish-output output)
      (let ((line (read-line input nil nil)))
        (when (null line)
          (return))
        (let* ((key (string-trim '(#\Space #\Tab #\Return) line))
               (direction (cdr (assoc key '(("w" . :up)
                                            ("a" . :left)
                                            ("s" . :down)
                                            ("d" . :right))
                                      :test #'string=))))
          (cond ((string= key "q")
                 (return))
                (direction
                 (multiple-value-bind (new gained changed) (move board direction)
                   (cond (changed
                          (setf board (spawn-tile new random-state))
                          (incf score gained))
                         (t
                          (format output "That move changes nothing.~%")))))
                (t
                 (format output "Invalid key: ~S~%" key))))))
    nil))
