"""Delete ticket-owned data atomically; preserve independently useful records."""
import sqlite3


class TicketDeletionError(ValueError):
    def __init__(self,message,status=409,code='ticket_in_use'):
        super().__init__(message);self.status=status;self.code=code


def delete_ticket(db,ticket_id,*,log_activity):
    if not db.in_transaction:db.execute('BEGIN IMMEDIATE')
    db.execute('SAVEPOINT delete_inventory_ticket')
    try:
        if not db.execute('SELECT 1 FROM tickets WHERE id=?',(ticket_id,)).fetchone():
            raise TicketDeletionError('Ticket nicht gefunden.',404,'ticket_not_found')
        # Recheck under the write lock; concurrent review creation cannot race it.
        if db.execute('SELECT 1 FROM ticket_review_links WHERE change_ticket_id=? OR review_ticket_id=?',(ticket_id,ticket_id)).fetchone():
            raise TicketDeletionError('Verknüpfte Change-/Review-Tickets können nicht gelöscht werden.',409,'ticket_review_relation_locked')
        detached={}
        for table,column,entity in [('roadmaps','ticket_id','roadmap'),('knowledge_entries','related_ticket_id','knowledge_entry'),('health_incidents','ticket_id','health_incident')]:
            identifiers=[row[0] for row in db.execute(f'SELECT id FROM {table} WHERE {column}=?',(ticket_id,))]
            db.execute(f'UPDATE {table} SET {column}=NULL WHERE {column}=?',(ticket_id,))
            detached[entity]=len(identifiers)
            for identifier in identifiers:log_activity(db,'ticket_unlinked',entity,identifier,{'deleted_ticket_id':ticket_id})
        for table in ['ticket_comments','ticket_watchers','ticket_assets']:
            db.execute(f'DELETE FROM {table} WHERE ticket_id=?',(ticket_id,))
        # Retain original files for existing retention/backup workflows; make
        # their metadata inaccessible through the normal attachment routes.
        db.execute("UPDATE attachments SET deleted_at=CURRENT_TIMESTAMP WHERE entity_type='ticket' AND entity_id=? AND deleted_at IS NULL",(ticket_id,))
        db.execute('DELETE FROM tickets WHERE id=?',(ticket_id,))
        log_activity(db,'delete','ticket',ticket_id,{'detached':detached})
        db.execute('RELEASE SAVEPOINT delete_inventory_ticket')
        return detached
    except BaseException as error:
        db.execute('ROLLBACK TO SAVEPOINT delete_inventory_ticket');db.execute('RELEASE SAVEPOINT delete_inventory_ticket')
        if isinstance(error,sqlite3.IntegrityError):
            raise TicketDeletionError('Das Ticket wird noch verwendet. Es wurde nichts gelöscht. Bitte die Verknüpfungen prüfen.') from error
        raise
