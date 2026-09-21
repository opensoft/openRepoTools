/*
 * Sanitized source-level control for a user-stopped worker.  It records the
 * terminal predicate; it is not a replacement for a selected-runtime probe.
 */

function canResume(agent) {
  return agent.stoppedByUser !== true &&
    (agent.status === "running" || agent.status === "completed");
}

if (!canResume(agent)) {
  // A stoppedByUser record is terminal and must not enter the stranded resume
  // dispatcher.  The source path does not enqueue a wake or model request.
  return "stopped by the user and won't be resumed";
}
