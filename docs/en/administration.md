# Administration and security

[Deutsch](../de/administration.md) · [Documentation](../INDEX.md)

## Accounts and permissions

First startup stores a random administrator password locally in a protected file. Initial login requires a password change. There is no public setup registration. Configure TOTP under **Account security** and store recovery codes privately.

Roles separate viewing and management permissions. Existing device and asset permissions remain in effect in the unified interface. A shared interface grants no additional permissions. Linked instances retain their own accounts and access decisions.

## Language and appearance

Under **Settings → Server → General → Interface language**, select German or English and save. The setting applies to the entire instance, including login. Inventory names, notes, custom field names and other entered content are not translated. Saving reloads the interface without restarting the server.

Switch light and dark themes in the top bar. Custom branding and colours do not replace attribution or license notices. **About Inventory Pro** identifies the original author and license.

## Operation

Automatic updates have a separate switch and maintenance window. Changes to host or port can require a restart; the interface indicates this. Backups, exports, health targets and the maintenance console have additional permissions and server options.

Keep secrets, `.env`, databases, uploads, private keys, internal hostnames and operational logs out of the public repository. Prepare security reports without personal or internal data. After confirmed exposure, revoke affected credentials and check dependent services. Do not replace persistent encryption keys without a migration and recovery plan.
