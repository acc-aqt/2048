(in-package :game-2048)

(defun slide-row (row)
  "Slide and merge a four-cell ROW toward its first element."
  (let* ((tiles (remove 0 row))
         (result nil)
         (points 0))
    (loop while tiles
          for first-tile = (pop tiles)
          do (if (and tiles (= first-tile (first tiles)))
                 (let ((merged (* 2 first-tile)))
                   (pop tiles)
                   (push merged result)
                   (incf points merged))
                 (push first-tile result)))
    (values (subseq (append (nreverse result)
                            (make-list (- 4 (length result)) :initial-element 0))
                    0 4)
            points)))

(defun copy-board (board)
  "Return a fresh copy of the 4 by 4 BOARD."
  (let ((copy (make-array '(4 4) :initial-element 0)))
    (dotimes (row 4 copy)
      (dotimes (column 4)
        (setf (aref copy row column) (aref board row column))))))

(defun move (board direction)
  "Return BOARD slid in DIRECTION, its score gain, and whether it changed."
  (unless (member direction '(:left :right :up :down))
    (error "Unknown direction: ~s" direction))
  (let ((result (make-array '(4 4) :initial-element 0))
        (points 0))
    (dotimes (index 4)
      (let ((line (loop for offset below 4
                        collect (if (member direction '(:left :right))
                                    (aref board index
                                          (if (eq direction :left) offset (- 3 offset)))
                                    (aref board
                                          (if (eq direction :up) offset (- 3 offset))
                                          index)))))
        (multiple-value-bind (slid gained)
            (slide-row line)
          (incf points gained)
          (dotimes (offset 4)
            (let ((value (nth offset slid)))
              (if (member direction '(:left :right))
                  (setf (aref result index
                              (if (eq direction :left) offset (- 3 offset))) value)
                  (setf (aref result
                              (if (eq direction :up) offset (- 3 offset))
                              index) value)))))))
    (values result points
            (not (equalp board result)))))

(defun spawn-tile (board random-state)
  "Return a fresh BOARD with a random 2 or 4 in an empty cell."
  (let* ((result (copy-board board))
         (empty (loop for row below 4 append
                      (loop for column below 4
                            when (zerop (aref board row column))
                              collect (cons row column))))
         (cell (nth (random (length empty) random-state) empty))
         (value (if (< (random 10 random-state) 9) 2 4)))
    (setf (aref result (car cell) (cdr cell)) value)
    result))

(defun won-p (board)
  "Return true when BOARD contains a 2048 tile."
  (loop for row below 4
        thereis (loop for column below 4
                      thereis (= (aref board row column) 2048))))

(defun game-over-p (board)
  "Return true when BOARD cannot change in any direction."
  (loop for row below 4
        always (loop for column below 4
                     always (and (/= (aref board row column) 0)
                                 (not (and (< column 3)
                                           (= (aref board row column)
                                              (aref board row (1+ column)))))
                                 (not (and (< row 3)
                                           (= (aref board row column)
                                              (aref board (1+ row) column))))))))

(defun print-board (board score output)
  "Print BOARD and SCORE to OUTPUT."
  (format output "Score: ~d~%" score)
  (dotimes (row 4)
    (format output "|~{~5d|~}~%"
            (loop for column below 4 collect (aref board row column))))
  (terpri output))

(defun play (&key (input *standard-input*) (output *standard-output*)
                  (random-state (make-random-state t)))
  "Play a text game using INPUT, OUTPUT, and RANDOM-STATE."
  (let ((board (make-array '(4 4) :initial-element 0))
        (score 0)
        (announced-win nil))
    (setf board (spawn-tile board random-state)
          board (spawn-tile board random-state))
    (print-board board score output)
    (loop
      (when (game-over-p board)
        (format output "Game over.~%")
        (return))
      (let ((line (read-line input nil nil)))
        (unless line (return))
        (let ((direction
                (and (> (length line) 0)
                     (case (char-downcase (char line 0))
                       (#\w :up)
                       (#\a :left)
                       (#\s :down)
                       (#\d :right)
                       (otherwise nil)))))
          (cond
            ((null direction)
             (when (and (> (length line) 0)
                        (char= (char-downcase (char line 0)) #\q))
               (return)))
            (t
             (multiple-value-bind (moved gained changed)
                 (move board direction)
               (when changed
                 (setf board (spawn-tile moved random-state))
                 (incf score gained))
               (print-board board score output)
               (when (and (not announced-win) (won-p board))
                 (setf announced-win t)
                 (format output "You won!~%"))))))))
    (values)))
