// Android's user-controlled RUN_COMMAND permission must be granted before a task is submitted.
export async function ensureTermuxPermission(bridge) {
  if (bridge.hasTermuxPermission()) return true;
  await bridge.requestTermuxPermission();
  return bridge.hasTermuxPermission();
}
