# Plan

Add pip's `--only-binary=:all:` flag to the focused guard job, preserving the
pinned runner version and canonical test wrapper. Validate through that focused
CI job and Sonar analysis. This is an implementation correction within the
existing guard change, so it adds no separate OpenSpec governance proposal.
