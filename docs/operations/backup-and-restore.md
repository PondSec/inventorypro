# Backup and restore

## Scope

A recoverable installation consists of the database, uploads, runtime settings
needed for operation and the corresponding encryption-key material. A database
backup alone does not restore attachments; encryption keys must never be stored
inside the backup archive.

## Backup procedure

1. Verify sufficient storage and that the service account can write only to the
   configured backup directory.
2. Create the backup through the supported backup job/API. SQLite uses its
   online backup API; do not copy a live database file with shell tools.
3. If encryption is required, configure `BACKUP_ENCRYPTION_KEY` before backup.
4. Record the timestamp, application version, database schema version, checksum
   and encryption-key identifier (never the key).
5. Copy the backup to independent, access-controlled storage and verify its
   checksum there.

## Restore procedure

1. Announce maintenance and stop application writers and scheduler jobs.
2. Capture the current database and uploads as an emergency rollback snapshot.
3. Restore into an isolated staging directory first. Decrypt only with the
   correct key and verify the checksum/schema version.
4. Run the migration status command and application smoke tests against the
   staged copy.
5. Replace the production data atomically while the application is stopped;
   restore uploads from the matching backup set.
6. Start one application/scheduler owner, log in with an administrator account,
   verify core asset/ticket data and review job status.

## Rollback

If validation fails before production cutover, discard the staged restore and
retain the existing data. If it fails after cutover, stop writers and restore the
emergency snapshot made in step 2. Never run an untested downgrade migration on
the only copy of production data.

## Restore drills

Automated tests cover backup artifact creation and restore validation. Operations
must additionally perform a documented, non-production restore drill at least
quarterly, including uploads, encrypted data and a version-compatible migration
path.
