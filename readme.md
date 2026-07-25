# Inventory Pro – Inventarisierung & Helpdesk

Inventory Pro ist eine professionelle Webplattform zur Verwaltung von Hardwarebeständen und Support-Tickets. Die Anwendung kombiniert eine flexible Inventarisierung, ein integriertes Helpdesk-System und ein rollenbasiertes Sicherheitskonzept. Damit eignet sie sich sowohl für IT-Abteilungen als auch für Managed-Service-Provider, die Asset- und Ticketdaten zentral und nachvollziehbar steuern möchten.

---

## Inhaltsverzeichnis

- [Produktüberblick](#produktüberblick)
- [Hauptfunktionen](#hauptfunktionen)
- [Technischer Stack](#technischer-stack)
- [Architektur & Datenmodell](#architektur--datenmodell)
- [Installation](#installation)
- [Konfiguration](#konfiguration)
- [Betrieb & Deployment](#betrieb--deployment)
- [Sicherheit](#sicherheit)
- [Wartung & Betriebshinweise](#wartung--betriebshinweise)
- [Lizenz](#lizenz)
- [Kontakt](#kontakt)

---

## Produktüberblick

Inventory Pro bietet eine konsolidierte Oberfläche zur Inventarisierung von IT-Komponenten sowie zur Bearbeitung von Support-Anfragen. Kategorien und Felder lassen sich dynamisch definieren, sodass Sie die Datenstruktur ohne Quellcodeänderung an Ihre Umgebung anpassen können. Gleichzeitig sorgt das Ticket-System für eine strukturierte Bearbeitung mit Status, Prioritäten, Kommentaren, Watchern und SLA-Informationen.

---

## Hauptfunktionen

### Inventarisierung
- **Dynamische Kategorien**: Frei definierbare Kategorien mit eigenen Felddefinitionen pro Asset-Typ.
- **Formulargenerierung**: Eingabeformulare werden automatisch aus den JSON-Definitionen erstellt.
- **Status-Tracking**: Statusinformationen werden für Auswertungen und Berichte genutzt.

### Beschaffung & Vertraege
- **Lieferantenmanagement**: Kontakt- und Bewertungsdaten zentral verwalten.
- **Vertragssteuerung**: Laufzeiten, Renewal-Typen und Kosten mit Verantwortlichen hinterlegen.
- **Bestellungen**: Purchase Orders mit Positionen, Status, Kostenstellen und Summen.
- **Renewal-Dashboard**: Ablauftermine fuer Vertraege und Garantien im Blick behalten.

### Helpdesk / Tickets
- **Ticket-Management**: Erstellung, Priorisierung, Statuswechsel und Zuweisungen.
- **SLA-Informationen**: Tickets können mit Fälligkeits- und SLA-Daten geführt werden.
- **Kommentare & Watcher**: Interne und externe Kommentare sowie Benachrichtigungsempfänger.
- **Alerts & Benachrichtigungen**: Automationsregeln für Ereignisse (Statuswechsel, Kommentare etc.).

### Benutzer & Sicherheit
- **Authentifizierung**: Benutzername/Passwort mit Passwort-Hashing.
- **2FA (TOTP)**: Optionale Zwei-Faktor-Authentifizierung.
- **Sicheres Passwort-Reset**: Reset via TOTP oder im eingeloggten Zustand.

### UX & Bedienung
- **Responsive Oberfläche**: Optimiert für Desktop und mobile Geräte.
- **Dark Mode**: Integriertes Theme-System für helle und dunkle Darstellung.
- **Moderne UI-Komponenten**: Klar strukturierte Bereiche, schnelle Navigation und konsistente Bedienelemente.

---

## Technischer Stack

| Ebene | Technologie |
| --- | --- |
| Frontend | HTML5, CSS3, JavaScript (Vanilla), Alpine.js, Tailwind via CDN |
| Backend | Python 3.12, Flask |
| Datenhaltung | SQLite |
| Authentifizierung | bcrypt, TOTP (RFC 6238) |
| API | RESTful, JSON-basiert |

---

## Architektur & Datenmodell

- **Trennung von UI & Backend**: UI-Templates und REST-Endpunkte sind klar getrennt.
- **Dynamische Felder**: Kategorien speichern Felddefinitionen als JSON, Einträge übernehmen diese Struktur.
- **Ticket-Datenmodell**: Enthält Status, Priorität, Kategorie, SLA/Deadline, Kommentare, Watcher und Benachrichtigungsregeln.

---

## Installation

```bash
# 1) Virtuelle Umgebung erstellen
python -m venv venv
source venv/bin/activate

# 2) Abhängigkeiten installieren
pip install -r requirements.txt

# 3) Anwendung starten
python app.py
```

Nach dem Start ist die Anwendung in der Regel unter `http://localhost:5000` erreichbar.

---

## Konfiguration

- **SMTP / Benachrichtigungen**: Über das Ticket-Admin-Panel konfigurierbar.
- **2FA aktivieren**: In der Benutzerverwaltung aktivieren und TOTP-Seed in einer Authenticator-App hinterlegen.
- **JSON-Felder**: Kategorien definieren Felder über JSON, z. B.:

```json
{
  "Status": "text",
  "Hersteller": "text",
  "Modell": "text",
  "Spezifikationen": "text",
  "Nummer": "number"
}
```

Der Feldname **"Status"** hat eine besondere Bedeutung für die Auswertungslogik.

---

## Betrieb & Deployment

Empfohlene Vorgehensweise für Produktionsumgebungen:

- **WSGI-Server nutzen** (z. B. Gunicorn oder uWSGI).
- **Reverse Proxy** (z. B. Nginx) für SSL-Termination und Caching.
- **Datenbank-Backup** regelmäßig einplanen.
- **Secrets schützen** (SMTP-Credentials, TOTP-Secrets).

---

## Sicherheit

- Passwort-Hashing mit **bcrypt**.
- **TOTP-basierte Zwei-Faktor-Authentifizierung** (RFC 6238).
- Session- und Rollenlogik in der Applikationsschicht.
- Empfohlene Ergänzungen: TLS, regelmäßige Updates, Restriktionen für Admin-Zugriffe.

---

## Wartung & Betriebshinweise

- **Backups**: SQLite-Datei regelmäßig sichern (auch vor Updates).
- **Monitoring**: Verfügbarkeit, Fehlerraten und Logs überwachen.
- **Updates**: Abhängigkeiten regelmäßig prüfen und aktualisieren.

---

## Lizenz

Dieses Projekt steht unter der GNU Affero General Public License Version 3 (AGPL-3.0).

Sie dürfen diese Software verwenden, verändern und verbreiten, solange alle Änderungen und Erweiterungen unter denselben Bedingungen (AGPL-3.0) veröffentlicht werden, insbesondere bei Nutzung über ein Netzwerk (z. B. als Webanwendung).

Für die kommerzielle Nutzung ohne Offenlegungspflicht (z. B. in geschlossenen Systemen oder als SaaS ohne Quellcodeveröffentlichung) ist eine separate Lizenzvereinbarung notwendig.

Der vollständige Lizenztext: https://www.gnu.org/licenses/agpl-3.0.de.html

---

## Kontakt

Joshua Pond
Fachinformatiker für Systemintegration
E-Mail: joshua@pondsec.com
Stand: Juli 2025
