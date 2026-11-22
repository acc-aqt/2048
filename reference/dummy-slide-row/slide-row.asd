;;;; Private reference solution for the dummy slide-row task.
;;;; Never copied into a run folder; used only to validate the hidden tests.

(asdf:defsystem "slide-row"
  :serial t
  :components ((:file "package")
               (:file "slide-row")))

(asdf:defsystem "slide-row/tests"
  :depends-on ("slide-row" (:require "tester"))
  :components ((:file "slide-row-tests")))
