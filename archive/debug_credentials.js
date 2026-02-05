console.log('Debugging environment variables...');
console.log('OCUSER:', process.env.OCUSER);
console.log('OCUSER exists:', !!process.env.OCUSER);
console.log('OCUSER length:', process.env.OCUSER ? process.env.OCUSER.length : 'undefined');

// Also try accessing via the credential loader
const CredentialLoader = require('./scripts/credential_loader.js');

console.log('\nVia CredentialLoader:');
try {
  const calendarCreds = CredentialLoader.getCalendarCredentials();
  console.log('Calendar creds:', calendarCreds);
} catch (e) {
  console.log('Error getting calendar creds:', e.message);
}

try {
  const mailCreds = CredentialLoader.getMailCredentials();
  console.log('Mail creds:', mailCreds);
} catch (e) {
  console.log('Error getting mail creds:', e.message);
}

console.log('\nAll env vars containing "OC":');
for (let key in process.env) {
  if (key.includes('OC')) {
    console.log(key + ':', process.env[key]);
  }
}