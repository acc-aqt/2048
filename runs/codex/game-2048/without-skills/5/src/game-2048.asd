(asdf:defsystem "game-2048"
  :serial t
  :components ((:file "package")
               (:file "game-2048")))

(asdf:defsystem "game-2048/tests"
  :depends-on ("game-2048")
  :serial t
  :components ((:file "game-2048-tests")))
