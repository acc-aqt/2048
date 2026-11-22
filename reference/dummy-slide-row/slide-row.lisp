(in-package :slide-row)

(defun slide-row (row)
  "Slide ROW toward its first element, merging equal neighbours once.
Return the new row and the points gained."
  (let ((tiles (remove 0 row))
        (result '())
        (points 0))
    (loop while tiles
          do (let ((tile (pop tiles)))
               (if (and tiles (= tile (first tiles)))
                   (let ((merged (* 2 tile)))
                     (pop tiles)
                     (push merged result)
                     (incf points merged))
                   (push tile result))))
    (let ((padding (make-list (- (length row) (length result)) :initial-element 0)))
      (values (append (nreverse result) padding)
              points))))
