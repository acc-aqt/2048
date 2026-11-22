;;;; game-2048.asd

(defsystem "game-2048"
  :description "The game 2048 as a text game."
  :serial t
  :components ((:file "package")
               (:file "game-2048")))

(defsystem "game-2048/tests"
  :description "Tests for the game-2048 system (uses Allegro's tester module)."
  :depends-on ("game-2048")
  :serial t
  :components ((:file "game-2048-tests")))
