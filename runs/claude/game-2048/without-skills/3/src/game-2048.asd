;;;; game-2048.asd -- ASDF system definitions for the 2048 text game.

(asdf:defsystem "game-2048"
  :description "The game 2048 as a text game."
  :serial t
  :components ((:file "package")
               (:file "game-2048")))

(asdf:defsystem "game-2048/tests"
  :description "Tests for the game-2048 system (uses Allegro's tester module)."
  :depends-on ("game-2048")
  :serial t
  :components ((:file "game-2048-tests")))
