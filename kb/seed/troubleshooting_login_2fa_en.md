# Troubleshooting: Login & 2FA

This guide covers the most common login and two-factor authentication (2FA) problems reported
by Acme Cloud Suite users, and how to fix them.

## "My 2FA code says invalid" (clock skew)

The most common login issue is a 2FA code that Acme Cloud Suite rejects even though it matches
what's shown in your authenticator app. Acme Cloud Suite's 2FA is TOTP-based (time-based
one-time passwords), which means the code your device generates is only valid if your device's
clock is closely synced with real time. The usual cause is **clock drift on the device
generating the code** — phone, laptop, or hardware authenticator.

**Fix:** Enable automatic time sync on the device generating your 2FA codes.

- **iOS**: Settings > General > Date & Time > enable "Set Automatically."
- **Android**: Settings > System > Date & Time > enable "Automatic date & time" (or
  "Use network-provided time").
- **Windows**: Settings > Time & Language > Date & Time > enable "Set time automatically," then
  click "Sync now."
- **macOS**: System Settings > General > Date & Time > enable "Set time and date automatically."

After enabling automatic time sync, wait for the next code cycle (codes normally rotate every
30 seconds) and try logging in again. If the problem persists, remove and re-add Acme Cloud
Suite in your authenticator app to force a fresh time sync with the server.

2FA (TOTP-based) is available on every Acme Cloud Suite plan, from Free through Enterprise, so
this fix applies regardless of which plan you're on.

## Password reset flow

If you've forgotten your password or can't log in for another reason:

1. On the login screen, click **"Forgot password?"**
2. Enter the email address associated with your Acme Cloud Suite account.
3. Check your inbox for a password reset email (check spam/junk folders if it doesn't arrive
   within a few minutes).
4. Click the reset link in the email — it is valid for 60 minutes.
5. Choose a new password and confirm it.
6. Log in with your new password. If 2FA is enabled on your account, you will still be prompted
   for your 2FA code after entering the new password.

If you no longer have access to the email address on file, contact support for identity
verification. Response times follow your plan's support SLA: 48 hours for Free and Starter,
24 hours for Pro, and 4 hours (with phone support available) for Enterprise.

## Locked out after too many failed attempts

After repeated failed login attempts, Acme Cloud Suite temporarily locks the account for a short
period as a security measure. Wait a few minutes and try again, or use the password reset flow
above to regain access immediately.

## Still stuck?

If none of the above resolves your login issue, reach out through **Settings > Billing > Get
Help** (if you can access the app) or email support@acmecloudsuite.example.com, and include the
error message you're seeing along with your account email.
