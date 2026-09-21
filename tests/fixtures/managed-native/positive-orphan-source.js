/*
 * Sanitized source-level control extracted from the SDK 0.2.153 /
 * bundled CLI 2.1.273 feasibility artifact.  This file is intentionally not
 * executable and is never treated as live capability evidence.
 */

// A stranded native worker is resumed through the direct `oq` callback.
const resume = (agentId, prompt) => oq({
  agentId,
  prompt,
  userInitiated: false,
});

// The print/stream startup reads the durable worker state first.
const running = state.internal?.running_background_tasks;
const restoredOrphans = Array.isArray(running) ? restore(running) : [];

// The default wake path is distinct from the model request itself.
const wake = restoredOrphans.length ? buildWake(restoredOrphans) : null;
if (wake) queue.enqueuePendingNotification(wake);
