(asdf:defsystem "slide-row"
  :serial t
  :components ((:file "package")
               (:file "slide-row")))

(asdf:defsystem "slide-row/tests"
  :depends-on ("slide-row" (:require "tester"))
  :components ((:file "slide-row-tests")))
