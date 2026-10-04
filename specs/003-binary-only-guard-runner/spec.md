# Feature: Install the focused guard test runner from wheels

Follow-up to feature `002-skip-no-lane-guard` and PR #135. A late Sonar review
flagged the new focused job's ability to execute package source build scripts.
Require binary distributions for its pinned pytest installation. Runtime guard
behavior and vendored command bytes do not change.
