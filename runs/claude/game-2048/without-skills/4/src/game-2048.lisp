;;;; game-2048.lisp

(in-package :game-2048)

(defun slide-row (row)
  "Slide ROW toward its first element, merging equal neighbours once per move.
Returns a fresh list of 4 integers and the points gained."
  (let ((tiles (remove 0 row))
        (result '())
        (points 0))
    (loop while tiles do
      (let ((value (pop tiles)))
        (if (and tiles (= value (first tiles)))
            (let ((merged (* 2 value)))
              (pop tiles)
              (push merged result)
              (incf points merged))
            (push value result))))
    (let ((cells (reverse result)))
      (values (append cells (make-list (- (length row) (length cells))
                                       :initial-element 0))
              points))))

(defun line-indices (direction index)
  "Return the list of (row . column) positions of line INDEX, ordered from the
side that DIRECTION moves toward."
  (let ((positions
          (ecase direction
            ((:left :right)
             (loop for c from 0 below 4 collect (cons index c)))
            ((:up :down)
             (loop for r from 0 below 4 collect (cons r index))))))
    (if (member direction '(:right :down))
        (reverse positions)
        positions)))

(defun move (board direction)
  "Slide every line of BOARD toward DIRECTION (:left :right :up :down).
Returns a fresh board, the points gained, and true if any cell changed."
  (let ((new (make-array '(4 4) :initial-element 0))
        (points 0)
        (changed nil))
    (dotimes (index 4)
      (let* ((positions (line-indices direction index))
             (olds (mapcar (lambda (p) (aref board (car p) (cdr p))) positions)))
        (multiple-value-bind (slid gained) (slide-row olds)
          (incf points gained)
          (loop for p in positions
                for old in olds
                for value in slid
                do (setf (aref new (car p) (cdr p)) value)
                   (unless (= old value) (setf changed t))))))
    (values new points changed)))

(defun spawn-tile (board random-state)
  "Return a fresh copy of BOARD with one new tile (2 with 90%, 4 with 10%)
in a random empty cell."
  (let* ((new (make-array '(4 4)))
         (empty '()))
    (dotimes (r 4)
      (dotimes (c 4)
        (setf (aref new r c) (aref board r c))
        (when (zerop (aref board r c))
          (push (cons r c) empty))))
    (let* ((cell (nth (random (length empty) random-state) empty))
           (value (if (< (random 10 random-state) 9) 2 4)))
      (setf (aref new (car cell) (cdr cell)) value))
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

(defun print-board (board score output)
  (format output "~%Score: ~D~%" score)
  (dotimes (r 4)
    (dotimes (c 4)
      (let ((value (aref board r c)))
        (if (zerop value)
            (format output "~6@A" ".")
            (format output "~6D" value))))
    (terpri output))
  (finish-output output))

(defun play (&key (input *standard-input*)
                  (output *standard-output*)
                  (random-state (make-random-state t)))
  "Play 2048 as a text game reading keys from INPUT and writing to OUTPUT.
Keys: w up, a left, s down, d right, q quit. Returns the final score."
  (let ((board (make-array '(4 4) :initial-element 0))
        (score 0)
        (announced-win nil))
    (setf board (spawn-tile (spawn-tile board random-state) random-state))
    (loop
      (print-board board score output)
      (when (game-over-p board)
        (format output "Game over! Final score: ~D~%" score)
        (return))
      (let ((line (read-line input nil nil)))
        (when (null line)
          (return))
        (let ((direction (cond ((string= line "w") :up)
                               ((string= line "a") :left)
                               ((string= line "s") :down)
                               ((string= line "d") :right)
                               ((string= line "q") (return))
                               (t nil))))
          (cond ((null direction)
                 (format output "Invalid key: ~S. Use w, a, s, d, or q.~%" line))
                (t
                 (multiple-value-bind (new gained changed) (move board direction)
                   (cond (changed
                          (incf score gained)
                          (setf board (spawn-tile new random-state))
                          (when (and (not announced-win) (won-p board))
                            (setf announced-win t)
                            (format output "You reached 2048! You win! Keep playing or press q to quit.~%")))
                         (t
                          (format output "That move changed nothing.~%")))))))))
    score))
