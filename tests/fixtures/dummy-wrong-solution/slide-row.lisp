(in-package :slide-row)

(defun slide-row (row)
  "Wrong on purpose: slides tiles but never merges them."
  (let ((tiles (remove 0 row)))
    (values (append tiles (make-list (- (length row) (length tiles)) :initial-element 0))
            0)))
