;;;; game-2048.lisp -- the game 2048 as a text game.

(in-package :game-2048)

(defun slide-row (row)
  "Slide ROW (a list of 4 integers) toward its first element, merging tiles.
Returns a fresh list of the same length and the points gained."
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
    (setf out (nreverse out))
    (values (append out (make-list (- (length row) (length out))
                                   :initial-element 0))
            points)))

(defun line-cell (direction k idx)
  "Return the (row, column) of position IDX along line K for DIRECTION.
IDX 0 is the cell the tiles slide toward."
  (ecase direction
    (:left (values k idx))
    (:right (values k (- 3 idx)))
    (:up (values idx k))
    (:down (values (- 3 idx) k))))

(defun move (board direction)
  "Slide every line of BOARD toward DIRECTION (:left :right :up :down).
Returns a fresh board, the points gained, and true if any cell changed."
  (let ((new (make-array '(4 4) :initial-element 0))
        (points 0)
        (changed nil))
    (dotimes (k 4)
      (let ((line (loop for idx below 4
                        collect (multiple-value-bind (r c)
                                    (line-cell direction k idx)
                                  (aref board r c)))))
        (multiple-value-bind (slid pts) (slide-row line)
          (incf points pts)
          (loop for idx below 4
                for v in slid
                do (multiple-value-bind (r c) (line-cell direction k idx)
                     (setf (aref new r c) v)
                     (unless (= v (aref board r c))
                       (setf changed t)))))))
    (values new points changed)))

(defun spawn-tile (board random-state)
  "Return a fresh copy of BOARD with one new tile (2 or 4) in a random empty cell."
  (let* ((empties (loop for r below 4
                        nconc (loop for c below 4
                                    when (zerop (aref board r c))
                                      collect (cons r c))))
         (cell (nth (random (length empties) random-state) empties))
         (new (make-array '(4 4) :initial-element 0)))
    (dotimes (r 4)
      (dotimes (c 4)
        (setf (aref new r c) (aref board r c))))
    (setf (aref new (car cell) (cdr cell))
          (if (< (random 10 random-state) 9) 2 4))
    new))

(defun won-p (board)
  "True if BOARD contains a 2048 tile."
  (loop for r below 4
        thereis (loop for c below 4
                      thereis (= 2048 (aref board r c)))))

(defun game-over-p (board)
  "True if no move in any direction would change BOARD."
  (notany (lambda (direction)
            (nth-value 2 (move board direction)))
          '(:left :right :up :down)))

(defun print-board (board score stream)
  (dotimes (r 4)
    (dotimes (c 4)
      (let ((v (aref board r c)))
        (format stream "~6@A" (if (zerop v) "." v))))
    (terpri stream))
  (format stream "Score: ~D~%" score))

(defun key-direction (key)
  (cond ((string= key "w") :up)
        ((string= key "a") :left)
        ((string= key "s") :down)
        ((string= key "d") :right)
        (t nil)))

(defun play (&key (input *standard-input*)
                  (output *standard-output*)
                  (random-state (make-random-state t)))
  "Run the text game, reading keys from INPUT and writing to OUTPUT.
Keys: w a s d move, q quits. Returns at q or end of input, or when the game is over."
  (let* ((board (make-array '(4 4) :initial-element 0))
         (score 0)
         (won-announced nil))
    (setf board (spawn-tile board random-state))
    (setf board (spawn-tile board random-state))
    (print-board board score output)
    (block game
      (loop
        (let ((line (read-line input nil nil)))
          (when (null line)
            (return-from game))
          (let* ((key (string-trim '(#\Space #\Tab #\Return) line))
                 (direction (key-direction key)))
            (cond ((string= key "q")
                   (return-from game))
                  ((null direction)
                   (format output "Invalid key: ~S~%" key)
                   (print-board board score output))
                  (t
                   (multiple-value-bind (new points changed)
                       (move board direction)
                     (cond ((not changed)
                            (format output "That move changes nothing.~%")
                            (print-board board score output))
                           (t
                            (setf board (spawn-tile new random-state))
                            (incf score points)
                            (print-board board score output)
                            (when (and (not won-announced) (won-p board))
                              (setf won-announced t)
                              (format output "You reached 2048! You win! You can keep playing.~%"))
                            (when (game-over-p board)
                              (format output "Game over! No moves left. Final score: ~D~%"
                                      score)
                              (return-from game)))))))))))
    (values)))
