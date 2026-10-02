# Tasks

- [x] T001 Restrict the focused test-runner installation to binary distributions.

## Verification

The diff changes the new focused job's install command only. CI verifies the
wheel installation and reruns the same canonical 165-check guard/hygiene suite.
