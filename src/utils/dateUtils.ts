/**
 * Pure utility functions for date manipulation
 */

/**
 * Creates a Date object for today at midnight (00:00:00)
 */
export const todayLocalStart = (): Date => {
  const now = new Date()
  const start = new Date(now)
  start.setHours(0, 0, 0, 0)
  return start
}

/**
 * Checks if two dates are on the same local day
 */
export const isSameLocalDay = (left: Date, right: Date): boolean =>
  left.getFullYear() === right.getFullYear() &&
  left.getMonth() === right.getMonth() &&
  left.getDate() === right.getDate()
