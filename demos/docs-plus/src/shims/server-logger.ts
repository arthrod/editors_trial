/**
 * Browser stand-in for the server's pino logger.
 *
 * Only `conversionLogger` is used by the conversion domain, and only to report
 * a dropped export image. The browser demo has no log sink, so the calls are
 * swallowed (the count is still reported through the metrics shim).
 */
type Level = 'fatal' | 'error' | 'warn' | 'info' | 'debug' | 'trace' | 'silent'

const noop = (): void => {}

export interface BrowserLogger {
  fatal: (...args: unknown[]) => void
  error: (...args: unknown[]) => void
  warn: (...args: unknown[]) => void
  info: (...args: unknown[]) => void
  debug: (...args: unknown[]) => void
  trace: (...args: unknown[]) => void
  silent: (...args: unknown[]) => void
  child: (bindings: Record<string, unknown>, options?: Record<string, unknown>) => BrowserLogger
}

const createLogger = (): BrowserLogger => {
  const logger: BrowserLogger = {
    fatal: noop,
    error: noop,
    warn: noop,
    info: noop,
    debug: noop,
    trace: noop,
    silent: noop,
    child: () => logger
  }
  return logger
}

export const logger = createLogger()
export const conversionLogger = createLogger()
export const storageLocalLogger = createLogger()
export const storageS3Logger = createLogger()

export type Logger = BrowserLogger
export type Level_ = Level
