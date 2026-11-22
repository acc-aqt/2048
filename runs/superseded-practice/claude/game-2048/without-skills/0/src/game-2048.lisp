;;;; game-2048.lisp

(in-package :game-2048)

(defun copy-board (board)
  (let ((new (make-array '(4 4) :initial-element 0)))
    (dotimes (r 4 new)
      (dotimes (c 4)
        (setf (aref new r c) (aref board r c))))))

(defun make-empty-board ()
  (make-array '(4 4) :initial-element 0))

(defun slide-row (row)
  "Slide ROW toward its first element, merging once per tile.
Returns a fresh list of the same length and the points gained."
  (let ((tiles (remove 0 row))
        (out '())
        (score 0))
    (loop while tiles
          do (let ((a (pop tiles)))
               (if (and tiles (= a (first tiles)))
                   (let ((merged (* 2 a)))
                     (pop tiles)
                     (push merged out)
                     (incf score merged))
                   (push a out))))
    (let ((result (nreverse out)))
      (values (append result
                      (make-list (- (length row) (length result))
                                 :initial-element 0))
              score))))

(defun move (board direction)
  "Slide BOARD in DIRECTION (:left :right :up :down).
Returns a fresh board, the points gained, and true if any cell changed."
  (let ((new (make-empty-board))
        (total 0)
        (changed nil))
    (dotimes (i 4)
      (let* ((coords (ecase direction
                       (:left (loop for c from 0 below 4 collect (cons i c)))
                       (:right (loop for c from 3 downto 0 collect (cons i c)))
                       (:up (loop for r from 0 below 4 collect (cons r i)))
                       (:down (loop for r from 3 downto 0 collect (cons r i)))))
             (line (mapcar (lambda (p) (aref board (car p) (cdr p))) coords)))
        (multiple-value-bind (result points) (slide-row line)
          (incf total points)
          (loop for p in coords
                for v in result
                do (setf (aref new (car p) (cdr p)) v)
                   (unless (= v (aref board (car p) (cdr p)))
                     (setf changed t))))))
    (values new total changed)))

(defun spawn-tile (board random-state)
  "Return a copy of BOARD with one new tile (2 or 4) in a random empty cell."
  (let* ((new (copy-board board))
         (empties (loop for r from 0 below 4
                        nconc (loop for c from 0 below 4
                                    when (zerop (aref board r c))
                                      collect (cons r c))))
         (cell (nth (random (length empties) random-state) empties))
         (value (if (< (random 10 random-state) 9) 2 4)))
    (setf (aref new (car cell) (cdr cell)) value)
    new))

(defun won-p (board)
  (loop for r from 0 below 4
        thereis (loop for c from 0 below 4
                      thereis (= (aref board r c) 2048))))

(defun game-over-p (board)
  (notany (lambda (direction)
            (nth-value 2 (move board direction)))
          '(:left :right :up :down)))

(defun print-board (board score output)
  (dotimes (r 4)
    (dotimes (c 4)
      (let ((v (aref board r c)))
        (if (zerop v)
            (format output "~6A" ".")
            (format output "~6D" v))))
    (terpri output))
  (format output "Score: ~D~%" score))

(defun play (&key (input *standard-input*)
                  (output *standard-output*)
                  (random-state (make-random-state t)))
  "Play 2048 as a text game reading commands from INPUT, writing to OUTPUT."
  (let* ((board (spawn-tile (spawn-tile (make-empty-board) random-state)
                            random-state))
         (score 0)
         (won nil))
    (loop
      (print-board board score output)
      (when (game-over-p board)
        (format output "Game over! Final score: ~D~%" score)
        (return))
      (let ((line (read-line input nil nil)))
        (when (or (null line) (string= line "q"))
          (return))
        (let* ((key line)
               (direction (cond ((string= key "w") :up)
                                ((string= key "a") :left)
                                ((string= key "s") :down)
                                ((string= key "d") :right)
                                (t nil))))
          (cond
            ((null direction)
             (format output "Invalid key: ~S. Use w/a/s/d to move, q to quit.~%"
                     key))
            (t
             (multiple-value-bind (new-board points changed)
                 (move board direction)
               (cond
                 ((not changed)
                  (format output "That move changed nothing.~%"))
                 (t
                  (setf board (spawn-tile new-board random-state))
                  (incf score points)
                  (when (and (not won) (won-p board))
                    (setf won t)
                    (format output "You reached 2048! You win! Keep playing if you like.~%"))))))))))
    score))
