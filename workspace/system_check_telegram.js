const { exec } = require('child_process');
const fs = require('fs');

const OPENCLAW_STATUS_TIMEOUT_MS = 8000;

function truncate(text, maxLen) {
    if (!text) return '';
    if (text.length <= maxLen) return text;
    return `${text.slice(0, maxLen)}...`;
}

function logStructuredWarning(reasonCode, detail) {
    const payload = {
        timestamp: new Date().toISOString(),
        level: 'warning',
        reason_code: reasonCode,
        errorMessage: reasonCode,
        detail
    };
    console.warn(JSON.stringify(payload));
}

async function execCommand(command, timeoutMs) {
    return new Promise((resolve) => {
        exec(command, { timeout: timeoutMs }, (error, stdout, stderr) => {
            const result = {
                command,
                stdout,
                stderr,
                exitCode: 0,
                signal: null,
                timedOut: false,
                error: null
            };
            if (error) {
                result.exitCode = typeof error.code === 'number' ? error.code : null;
                result.signal = error.signal || null;
                result.timedOut = Boolean(error.killed && error.signal === 'SIGTERM');
                result.error = error;
            }
            resolve(result);
        });
    });
}

async function runOpenclawStatus() {
    const deepResult = await execCommand('openclaw status --deep', OPENCLAW_STATUS_TIMEOUT_MS);
    if (!deepResult.error) {
        return { ok: true, source: deepResult.command, stdout: deepResult.stdout };
    }

    logStructuredWarning('openclaw_status_unavailable', {
        command: deepResult.command,
        exit_code: deepResult.exitCode,
        signal: deepResult.signal,
        timed_out: deepResult.timedOut,
        stderr: truncate(deepResult.stderr, 300),
        stdout: truncate(deepResult.stdout, 300)
    });

    const shallowResult = await execCommand('openclaw status', OPENCLAW_STATUS_TIMEOUT_MS);
    if (!shallowResult.error) {
        return { ok: true, source: shallowResult.command, stdout: shallowResult.stdout };
    }

    logStructuredWarning('openclaw_status_unavailable', {
        command: shallowResult.command,
        exit_code: shallowResult.exitCode,
        signal: shallowResult.signal,
        timed_out: shallowResult.timedOut,
        stderr: truncate(shallowResult.stderr, 300),
        stdout: truncate(shallowResult.stdout, 300),
        note: 'Fallback after openclaw status --deep failed'
    });

    return { ok: false, reason_code: 'openclaw_status_unavailable' };
}

// Telegram messaging system health check
async function checkTelegramMessaging() {
    console.log(`[${new Date().toISOString()}] Running Telegram messaging system check...`);
    
    try {
        // Run OpenClaw status to check current state
        const statusResult = await runOpenclawStatus();
        if (!statusResult.ok) {
            console.log('OpenClaw status unavailable; continuing with limited checks.');
            return { status: 'warning', reason_code: statusResult.reason_code };
        }

        console.log('Status check completed');
        
        // Parse the status output to look for Telegram status
        const lines = statusResult.stdout.split('\n');
        let telegramStatus = 'unknown';
        
        for (const line of lines) {
            if (line.includes('Telegram') && line.includes('OK')) {
                telegramStatus = 'ok';
                break;
            } else if (line.includes('Telegram') && (line.includes('ERROR') || line.includes('OFF'))) {
                telegramStatus = 'error';
                break;
            }
        }
        
        console.log(`Telegram status: ${telegramStatus}`);
        
        if (telegramStatus === 'ok') {
            console.log('✓ Telegram messaging system is healthy');
            return { status: 'healthy', details: statusResult.stdout };
        } else if (telegramStatus === 'error') {
            console.log('⚠ Telegram messaging system may have issues');
            console.log('Status output:', statusResult.stdout);
            return { status: 'unhealthy', details: statusResult.stdout };
        } else {
            console.log('Telegram status unknown in OpenClaw status output.');
            return { status: 'warning', details: statusResult.stdout };
        }
        
    } catch (error) {
        console.error('Error during Telegram check:', error.message);
        return { status: 'error', error: error.message };
    }
}

// Function to restart messaging if needed
async function ensureMessagingRunning() {
    try {
        const result = await checkTelegramMessaging();
        
        if (result.status === 'unhealthy') {
            console.log('Attempting to restart messaging system...');
            
            // Try to restart the gateway to refresh connections
            await new Promise((resolve, reject) => {
                exec('openclaw gateway restart', { timeout: 10000 }, (error, stdout, stderr) => {
                    if (error) {
                        console.error('Gateway restart failed:', error);
                        reject(error);
                    } else {
                        console.log('Gateway restarted successfully');
                        resolve(stdout);
                    }
                });
            });
        }
        
        return result;
    } catch (error) {
        console.error('Error ensuring messaging is running:', error);
        throw error;
    }
}

// Run check and log results
async function runCheck() {
    try {
        const result = await checkTelegramMessaging();
        
        // Log the result to a file for tracking
        const logEntry = {
            timestamp: new Date().toISOString(),
            status: result.status,
            reason_code: result.reason_code,
            details: result.details || result.error
        };
        
        const logFile = './telegram_health_log.json';
        let logs = [];
        
        if (fs.existsSync(logFile)) {
            const existingLogs = fs.readFileSync(logFile, 'utf8');
            logs = JSON.parse(existingLogs);
        }
        
        logs.push(logEntry);
        
        // Keep only the last 100 entries
        if (logs.length > 100) {
            logs = logs.slice(-100);
        }
        
        fs.writeFileSync(logFile, JSON.stringify(logs, null, 2));
        
        console.log('Telegram system check completed and logged');
        if (result.status === 'unhealthy' || result.status === 'error') {
            process.exitCode = 1;
        }
    } catch (error) {
        console.error('Failed to run complete check:', error);
    }
}

// If running as a script
if (require.main === module) {
    runCheck().then(() => {
        console.log('System check completed');
    }).catch((error) => {
        console.error('System check failed:', error);
    });
}

module.exports = {
    checkTelegramMessaging,
    ensureMessagingRunning,
    runCheck
};
