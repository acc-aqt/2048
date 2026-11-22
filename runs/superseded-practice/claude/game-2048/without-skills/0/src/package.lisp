;;;; package.lisp

(defpackage :game-2048
  (:use :common-lisp)
  (:export #:slide-row
           #:move
           #:spawn-tile
           #:won-p
           #:game-over-p
           #:play))
