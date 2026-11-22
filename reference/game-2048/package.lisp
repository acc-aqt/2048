;;;; The package of the game-2048 system. It is the first component in
;;;; game-2048.asd, so it exists before game-2048.lisp says (in-package :game-2048).

(defpackage :game-2048
  (:use :cl)
  (:export #:slide-row
           #:move
           #:spawn-tile
           #:won-p
           #:game-over-p
           #:play))
