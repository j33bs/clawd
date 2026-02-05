/**
 * credential_loader.js
 * 
 * Loads credentials from environment variables following the OCUSER/OCPASS convention
 */

class CredentialLoader {
  /**
   * Get calendar credentials from environment
   */
  static getCalendarCredentials() {
    return {
      username: process.env.OCUSER,
      password: process.env.OCPASS
    };
  }

  /**
   * Get mail credentials from environment
   */
  static getMailCredentials() {
    return {
      email: process.env.OCUSER,
      password: process.env.OCPASS
    };
  }

  /**
   * Check if calendar credentials are available
   */
  static hasCalendarCredentials() {
    return !!(process.env.OCUSER && process.env.OCPASS);
  }

  /**
   * Check if mail credentials are available
   */
  static hasMailCredentials() {
    return !!(process.env.OCUSER && process.env.OCPASS);
  }

  /**
   * Validate that required credentials exist
   */
  static validateCredentials(serviceType) {
    const hasCreds = serviceType === 'calendar' ? 
      this.hasCalendarCredentials() : 
      this.hasMailCredentials();
    
    if (!hasCreds) {
      throw new Error(`Missing credentials: Please set OCUSER and OCPASS environment variables for ${serviceType} integration`);
    }
    
    return true;
  }

  /**
   * Get credentials for a specific service
   */
  static getCredentials(serviceType) {
    this.validateCredentials(serviceType);
    
    if (serviceType === 'calendar') {
      return this.getCalendarCredentials();
    } else if (serviceType === 'mail') {
      return this.getMailCredentials();
    }
    
    throw new Error(`Unknown service type: ${serviceType}`);
  }
}

module.exports = CredentialLoader;