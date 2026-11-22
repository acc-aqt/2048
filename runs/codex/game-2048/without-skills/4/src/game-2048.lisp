(in-package :game-2048)

(defun slide-row (row)
  "Slide a four-cell ROW toward its first element."
  (let* ((tiles (remove 0 row))
         (result nil)
         (score 0))
    (loop while tiles do
      (if (and (cdr tiles) (= (car tiles) (cadr tiles)))
          (let ((merged (* 2 (car tiles))))
            (push merged result)
            (incf score merged)
            (setf tiles (cddr tiles)))
          (progn
            (push (car tiles) result)
            (setf tiles (cdr tiles)))))
    (let ((slid (nreverse result)))
      (values (append slid
                      (make-list (- 4 (length slid)) :initial-element 0))
              score))))

(defun %copy-board (board)
  (let ((copy (make-array '(4 4) :initial-element 0)))
    (dotimes (row 4 copy)
      (dotimes (column 4)
        (setf (aref copy row column) (aref board row column))))))

(defun %row (board row)
  (loop for column below 4 collect (aref board row column)))

(defun %column (board column)
  (loop for row below 4 collect (aref board row column)))

(defun %write-row (board row values)
  (loop for column below 4
        for value in values
        do (setf (aref board row column) value)))

(defun %write-column (board column values)
  (loop for row below 4
        for value in values
        do (setf (aref board row column) value)))

(defun move (board direction)
  (unless (member direction '(:left :right :up :down))
    (error "Invalid move direction: ~S" direction))
  (let ((result (make-array '(4 4) :initial-element 0))
        (score 0))
    (ecase direction
      ((:left :right)
       (dotimes (row 4)
         (multiple-value-bind (values gained)
             (slide-row (%row board row))
           (incf score gained)
           (%write-row result row (if (eq direction :left)
                                      values (reverse values))))))
      ((:up :down)
       (dotimes (column 4)
         (multiple-value-bind (values gained)
             (slide-row (%column board column))
           (incf score gained)
           (%write-column result column (if (eq direction :up)
                                            values (reverse values)))))))
    (values result score
            (not (equalp board result)))))

(defun spawn-tile (board random-state)
  (let* ((empty (loop for row below 4 append
                  (loop for column below 4
                        when (zerop (aref board row column))
                          collect (cons row column))))
         (cell (nth (random (length empty) random-state) empty))
         (result (%copy-board board)))
    (setf (aref result (car cell) (cdr cell))
          (if (< (random 10 random-state) 9) 2 4))
    result))

(defun won-p (board)
  (loop for row below 4 thereis
    (loop for column below 4 thereis (= (aref board row column) 2048))))

(defun game-over-p (board)
  (every (lambda (direction)
           (not (third (multiple-value-list (move board direction)))))
         '(:left :right :up :down)))

(defun %print-board (board score output)
  (format output "Score: ~D~%" score)
  (dotimes (row 4)
    (dotimes (column 4)
      (format output "~4D" (aref board row column)))
    (terpri output))
  (terpri output))

(defun %key-direction (line)
  (when line
    (let ((key (string-downcase (string-trim '(#\Space #\Tab #\Return) line))))
      (when (= (length key) 1)
        (case (char key 0)
          (#\w :up) (#\a :left) (#\s :down) (#\d :right))))))

(defun play (&key (input *standard-input*) (output *standard-output*)
                  (random-state (make-random-state t)))
  (let ((board (make-array '(4 4) :initial-element 0))
        (score 0)
        (announced-win nil))
    (setf board (spawn-tile board random-state)
          board (spawn-tile board random-state))
    (%print-board board score output)
    (loop
      (when (game-over-p board)
        (format output "Game over.~%")
        (return))
      (let ((line (read-line input nil nil)))
        (unless line (return))
        (when (string= (string-downcase (string-trim '(#\Space #\Tab #\Return) line)) "q")
          (return))
        (let ((direction (%key-direction line)))
          (when direction
            (multiple-value-bind (next gained changed) (move board direction)
              (when changed
                (setf board (spawn-tile next random-state))
                (incf score gained))))
          (%print-board board score output)
          (when (and (not announced-win) (won-p board))
            (format output "You won!~%")
            (setf announced-win t))
          (when (game-over-p board)
            (format output "Game over.~%")
            (return)))))))
