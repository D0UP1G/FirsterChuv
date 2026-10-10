function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/**
 * Removes the signed-out user's local drafts and submission keys.
 * Keys look like `firsterchuv:<draft|submission-key>:v<N>:<encoded userId>:<run>:<problem>:<language>`;
 * entries of other users are kept.
 */
export function purgePrivateBrowserData(userId: string, storage?: Storage): void {
  try {
    const target = storage ?? window.localStorage
    const owned = new RegExp(`^firsterchuv:(draft|submission-key):v\\d+:${escapeRegExp(encodeURIComponent(userId))}:`)
    const doomed: string[] = []
    for (let index = 0; index < target.length; index += 1) {
      const key = target.key(index)
      if (key && owned.test(key)) doomed.push(key)
    }
    doomed.forEach((key) => target.removeItem(key))
  } catch {
    // Storage can be unavailable (private mode, blocked site data); logout must still complete.
  }
}
