import { DEV_CONFIG, SECURITY_CONFIG } from '@constants/config';

type LogLevel = 'debug' | 'info' | 'warn' | 'error';

interface LogContext {
  [key: string]: any;
}

// Sensitive field patterns to sanitize
const SENSITIVE_PATTERNS = [
  /password/i,
  /token/i,
  /secret/i,
  /key/i,
  /authorization/i,
  /bearer/i,
  /api[_-]?key/i,
  /credentials/i,
  /ssn/i,
  /credit[_-]?card/i,
  /cvv/i,
  /pin/i,
];

// Fields to completely redact
const REDACTED_FIELDS = [
  'password',
  'token',
  'access_token',
  'refresh_token',
  'api_key',
  'secret',
  'authorization',
  'x-api-key',
];

class Logger {
  private shouldLog(level: LogLevel): boolean {
    if (!DEV_CONFIG.ENABLE_LOGS) return false;

    const levels: LogLevel[] = ['debug', 'info', 'warn', 'error'];
    const configLevel = DEV_CONFIG.LOG_LEVEL as LogLevel;
    const configLevelIndex = levels.indexOf(configLevel);
    const messageLevelIndex = levels.indexOf(level);

    return messageLevelIndex >= configLevelIndex;
  }

  private sanitizeData(data: any): any {
    if (!data) return data;

    // Handle strings
    if (typeof data === 'string') {
      // Check if it looks like a token or key
      if (data.length > 20 && /^[A-Za-z0-9+/=._-]+$/.test(data)) {
        return this.maskString(data);
      }
      return data;
    }

    // Handle arrays
    if (Array.isArray(data)) {
      return data.map(item => this.sanitizeData(item));
    }

    // Handle objects
    if (typeof data === 'object') {
      const sanitized: any = {};

      for (const [key, value] of Object.entries(data)) {
        // Check if key is sensitive
        const lowerKey = key.toLowerCase();

        if (REDACTED_FIELDS.includes(lowerKey)) {
          sanitized[key] = '[REDACTED]';
        } else if (SENSITIVE_PATTERNS.some(pattern => pattern.test(key))) {
          sanitized[key] = this.maskValue(value);
        } else {
          sanitized[key] = this.sanitizeData(value);
        }
      }

      return sanitized;
    }

    return data;
  }

  private maskString(str: string): string {
    if (str.length <= 8) {
      return '[MASKED]';
    }
    const visibleChars = 4;
    return (
      str.substring(0, visibleChars) +
      '*'.repeat(8) +
      str.substring(str.length - visibleChars)
    );
  }

  private maskValue(value: any): any {
    if (typeof value === 'string') {
      return this.maskString(value);
    }
    if (typeof value === 'number') {
      return '[MASKED_NUMBER]';
    }
    if (value === null || value === undefined) {
      return value;
    }
    return '[MASKED]';
  }

  private formatMessage(
    level: LogLevel,
    message: string,
    context?: LogContext,
  ): string {
    const timestamp = new Date().toISOString();
    const sanitizedContext = context ? this.sanitizeData(context) : undefined;

    let formatted = `[${timestamp}] [${level.toUpperCase()}] ${message}`;

    if (sanitizedContext && Object.keys(sanitizedContext).length > 0) {
      formatted += `\n${JSON.stringify(sanitizedContext, null, 2)}`;
    }

    return formatted;
  }

  debug(message: string, context?: LogContext): void {
    if (this.shouldLog('debug')) {
      console.log(this.formatMessage('debug', message, context));
    }
  }

  info(message: string, context?: LogContext): void {
    if (this.shouldLog('info')) {
      console.log(this.formatMessage('info', message, context));
    }
  }

  warn(message: string, context?: LogContext): void {
    if (this.shouldLog('warn')) {
      console.warn(this.formatMessage('warn', message, context));
    }
  }

  error(message: string, error?: Error | any, context?: LogContext): void {
    if (this.shouldLog('error')) {
      const errorContext = {
        ...context,
        error: error
          ? {
              message: error.message,
              stack: error.stack,
              ...this.sanitizeData(error),
            }
          : undefined,
      };
      console.error(this.formatMessage('error', message, errorContext));
    }
  }

  // Special method for network requests
  logNetworkRequest(config: any): void {
    if (!DEV_CONFIG.SHOW_NETWORK_LOGS) return;

    const sanitizedConfig = {
      method: config.method,
      url: config.url,
      headers: this.sanitizeData(config.headers),
      params: this.sanitizeData(config.params),
      // Don't log request body by default
      data: SECURITY_CONFIG.LOG_SENSITIVE_DATA
        ? this.sanitizeData(config.data)
        : '[BODY_HIDDEN]',
    };

    this.debug('Network Request', sanitizedConfig);
  }

  logNetworkResponse(response: any): void {
    if (!DEV_CONFIG.SHOW_NETWORK_LOGS) return;

    const sanitizedResponse = {
      status: response.status,
      statusText: response.statusText,
      headers: this.sanitizeData(response.headers),
      // Don't log response data by default
      data: SECURITY_CONFIG.LOG_SENSITIVE_DATA
        ? this.sanitizeData(response.data)
        : '[DATA_HIDDEN]',
    };

    this.debug('Network Response', sanitizedResponse);
  }

  // Method to test if a string contains sensitive information
  containsSensitiveInfo(str: string): boolean {
    return SENSITIVE_PATTERNS.some(pattern => pattern.test(str));
  }
}

export const logger = new Logger();
