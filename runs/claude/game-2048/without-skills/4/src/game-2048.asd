;;;; game-2048.asd

(asdf:defsystem "game-2048"
  :description "The game 2048 as a text game."
  :author "alexander-carrels"
  :license "MIT"
  :version "1.0.0"
  :serial t
  :components ((:file "package")
               (:file "game-2048")))

(asdf:defsystem "game-2048/tests"
  :description "Tests for the game-2048 system, using Allegro's tester module."
  :depends-on ("game-2048")
  :serial t
  :components ((:file "game-2048-tests")))
