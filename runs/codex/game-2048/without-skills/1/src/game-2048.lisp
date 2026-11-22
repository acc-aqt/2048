(in-package :game-2048)

(defun slide-row (row)
  "Slide ROW toward its first element, returning a fresh row and gained points."
  (let* ((tiles (remove 0 row))
         (result nil)
         (points 0))
    (loop while tiles
          do (let ((first (pop tiles)))
               (if (and tiles (= first (car tiles)))
                   (let ((merged (* 2 first)))
                     (pop tiles)
                     (push merged result)
                     (incf points merged))
                   (push first result))))
    (setf result (nreverse result))
    (values (append result
                    (make-list (- 4 (length result)) :initial-element 0))
            points)))

(defun %copy-board (board)
  (let ((copy (make-array '(4 4) :initial-element 0)))
    (dotimes (row 4 copy)
      (dotimes (column 4)
        (setf (aref copy row column) (aref board row column))))))

(defun move (board direction)
  (unless (member direction '(:left :right :up :down))
    (error "Unknown direction: ~S" direction))
  (let ((result (make-array '(4 4) :initial-element 0))
        (points 0))
    (dotimes (line 4)
      (let ((values (loop for offset below 4
                          for row = (if (member direction '(:left :right)) line offset)
                          for column = (if (member direction '(:left :right)) offset line)
                          collect (aref board row column))))
        (when (member direction '(:right :down))
          (setf values (reverse values)))
        (multiple-value-bind (slid gained) (slide-row values)
          (incf points gained)
          (when (member direction '(:right :down))
            (setf slid (reverse slid)))
          (loop for offset below 4
                for row = (if (member direction '(:left :right)) line offset)
                for column = (if (member direction '(:left :right)) offset line)
                do (setf (aref result row column) (nth offset slid))))))
    (values result points
            (loop for row below 4 thereis
              (loop for column below 4
                    thereis (/= (aref board row column)
                                (aref result row column)))))))

(defun spawn-tile (board random-state)
  (let* ((empty (loop for row below 4 append
                  (loop for column below 4
                        when (zerop (aref board row column))
                          collect (cons row column))))
         (copy (%copy-board board))
         (cell (nth (random (length empty) random-state) empty))
         (value (if (< (random 10 random-state) 9) 2 4)))
    (setf (aref copy (car cell) (cdr cell)) value)
    copy))

(defun won-p (board)
  (loop for row below 4 thereis
    (loop for column below 4 thereis (= (aref board row column) 2048))))

(defun game-over-p (board)
  (every (lambda (direction)
           (multiple-value-bind (ignored score changed) (move board direction)
             (declare (ignore ignored score))
             (not changed)))
         '(:left :right :up :down)))

(defun %print-board (board score output)
  (format output "Score: ~D~%" score)
  (dotimes (row 4)
    (format output "|~{~4A|~}~%"
            (loop for column below 4
                  collect (if (zerop (aref board row column))
                              "" (aref board row column)))))
  (terpri output))

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
        (when (null line) (return))
        (let ((direction (case (and (> (length line) 0)
                                    (char-downcase (char line 0)))
                           (#\w :up) (#\a :left) (#\s :down) (#\d :right)
                           (otherwise nil))))
          (when (and (= (length line) 1) (char= (char line 0) #\q))
            (return))
          (when direction
            (multiple-value-bind (next gained changed) (move board direction)
              (incf score gained)
              (when changed
                (setf board (spawn-tile next random-state)))
              (when (and (not announced-win) (won-p board))
                (format output "You won!~%")
                (setf announced-win t))
              (%print-board board score output))))))))
