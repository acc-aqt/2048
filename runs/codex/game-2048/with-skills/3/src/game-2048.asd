(asdf:defsystem "game-2048"
  :description "A text version of 2048."
  :version "0.1.0"
  :serial t
  :components ((:file "package" )
               (:file "game-2048" ))
  :in-order-to ((test-op (load-op "game-2048/tests"))))

(asdf:defsystem "game-2048/tests"
  :depends-on ("game-2048" (:require "tester"))
  :components ((:file "game-2048-tests" )))
