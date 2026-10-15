"""Disposable realistic inventory for browser/visual QA; never opens customer data."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import tempfile
import threading

os.environ.setdefault('INVENTORY_ENV', 'test')
os.environ.setdefault('INVENTORY_SCHEDULER_ENABLED', '0')
from werkzeug.serving import make_server
import app as application

PASSWORD = 'Synthetic-Test-Only-42!'


@contextmanager
def visual_instance(count=1000):
    with tempfile.TemporaryDirectory(prefix='inventorypro-visual-') as directory:
        root = Path(directory)
        for name, value in {'DATABASE': str(root/'inventory.db'), 'UPLOADS_DIR': root/'uploads',
                'APP_INSTANCE_PATH': root/'instance', 'RUNTIME_CONFIG_PATH': root/'runtime.json',
                'INITIAL_ADMIN_CREDENTIALS_PATH': None,
                'RUNTIME_SETTINGS_CACHE': {'host':'127.0.0.1','port':0,'debug':False}}.items():
            setattr(application, name, value)
        application.init_db()
        with application.app.app_context():
            db = application.get_db()
            db.execute('UPDATE users SET password_hash=?, must_change_password=0 WHERE username=?',
                       (application.generate_password_hash(PASSWORD),'admin'))
            site = db.execute("INSERT INTO locations(name) VALUES ('QA · Büro')").lastrowid
            category = db.execute("INSERT INTO categories(name,icon,fields) VALUES ('Notebooks','monitor','[]')").lastrowid
            asset_category = db.execute("INSERT INTO asset_categories(name,fields) VALUES ('Zubehör','[]')").lastrowid
            models = [('MacBook Air 13″ M4','Apple'),('ThinkPad T14 Gen 5','Lenovo'),
                      ('Latitude 7450','Dell'),('EliteBook 840','HP'),('Surface Pro 9','Microsoft'),
                      ('Raspberry Pi 5','Raspberry Pi'),('Access Point U6','Ubiquiti'),
                      ('UltraSharp 27″','Dell'),('DiskStation DS923+','Synology'),('MX Master 3S','Logitech')]
            for i in range(count):
                model, brand = models[i % len(models)]
                db.execute('INSERT INTO devices(name,category_id,serial_number,location_id,specs) VALUES (?,?,?,?,?)',
                    (f'{model} · {i+1:04}',category,f'QA-{i+1:06}',site if i%9 else None,
                     json.dumps({'Hersteller':brand,'Modell':model,'MPN':f'QA-MODEL-{i%10}',
                                 'RAM':'16 GB','Speicher':'512 GB SSD','Betriebssystem':'QA Linux'})))
            for i in range(20):
                asset=db.execute('INSERT INTO assets(name,category_id,notes,specs) VALUES (?,?,?,?)',
                    (f'Arbeitsplatz-Set {i+1:02}',asset_category,'Synthetische Zusammenstellung',
                     json.dumps({'Hersteller':'Example','Modell':'Desk Kit','MPN':'QA-DESK'}))).lastrowid
                db.execute('INSERT INTO asset_devices(asset_id,device_id,quantity) VALUES (?,?,?)',(asset,i+1,1))
            db.execute("INSERT INTO maintenance_tasks(device_id,title,due_date,status) VALUES (1,'Jährliche Prüfung','2026-01-01','open')")
            ticket_category = db.execute('SELECT id FROM ticket_categories LIMIT 1').fetchone()[0]
            for i in range(25):
                db.execute('INSERT INTO tickets(title,description,category_id,priority,status,created_by,requester_name,requester_email) VALUES (?,?,?,?,?,?,?,?)',
                    (f'Notebook Einrichtung · {i+1:02}','Synthetischer Supportvorgang',ticket_category,
                     'high' if i%3==0 else 'normal','open','admin','QA Team','qa@example.invalid'))
            knowledge_category=db.execute("INSERT INTO knowledge_categories(name) VALUES ('Arbeitsplätze')").lastrowid
            for i in range(12):
                db.execute('INSERT INTO knowledge_entries(title,summary,content,category_id,created_by) VALUES (?,?,?,?,?)',
                    (f'Arbeitsplatz einrichten · Anleitung {i+1:02}','Schrittweise Einrichtung und bekannte Fragen.',
                     'Synthetischer Artikel für die visuelle Abnahme.',knowledge_category,'admin'))
            db.execute("INSERT INTO vendors(name,contact_name,email) VALUES ('Example IT Partner','QA Kontakt','qa@example.invalid')")
            db.execute("INSERT INTO roadmaps(title,objective,status,owner) VALUES ('Arbeitsplätze erneuern','Synthetische Planung','in_progress','QA Team')")
            db.execute("INSERT INTO services(name,description,owner) VALUES ('Inventory API','Synthetischer Service','QA Team')")
            db.commit()
        server = make_server('127.0.0.1',0,application.app,threaded=True)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            yield application, f'http://127.0.0.1:{server.server_port}'
        finally:
            server.shutdown();thread.join(timeout=5)
