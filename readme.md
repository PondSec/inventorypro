# Inventarisierungssoftware für Hardwarekomponenten

## Projektbeschreibung

Diese Webanwendung dient der strukturierten Inventarisierung von Hardwarekomponenten in einer IT-Umgebung. Ziel des Projekts ist die Entwicklung eines erweiterbaren, webbasierten Systems zur Erfassung, Kategorisierung und Auswertung von Hardwaredaten. Das System ermöglicht es, über eine Weboberfläche individuelle Kategorien zu erstellen und die zugehörigen Datenfelder flexibel über JSON-Definitionen zu konfigurieren. Zusätzlich wurde ein Sicherheitsmechanismus zur Benutzerauthentifizierung mit optionaler Zwei-Faktor-Authentifizierung (TOTP) implementiert.

---

## Funktionsumfang

### 1. Kategoriebasierte Inventarisierung

* Kategorien können über die Weboberfläche erstellt, bearbeitet und gelöscht werden.
* Jede Kategorie enthält beliebig viele Geräte/Objekte.
* Pro Kategorie können individuelle Datenfelder definiert werden, welche als JSON-Struktur gespeichert sind.

**Beispielhafte JSON-Felddaten:**

```json
{
  "Status": "text",
  "Hersteller": "text",
  "Modell": "text",
  "Spezifikationen": "text",
  "Nummer": "number"
}
```

* Die Feldnamen sind frei wählbar, wobei "Status" (Großschreibung beachten) eine besondere Bedeutung für die statistische Auswertung hat.

---

### 2. Datenverwaltung

* Für jede Kategorie lassen sich neue Einträge (z. B. Hardwaregeräte) hinzufügen, bearbeiten oder löschen.
* Die Eingabe erfolgt über automatisch generierte Formulare, basierend auf den JSON-Definitionen.
* Änderungen an den Felddefinitionen wirken sich sofort auf alle zugehörigen Formulare und Datensätze aus.

---

### 3. Statistikmodul

* Basierend auf dem "Status"-Feld werden die Zustände der Geräte automatisch ausgewertet und grafisch/statistisch dargestellt.
* Unterstützte Statuswerte sind u. a.:

  * "Verwendung"
  * "Defekt"
  * "Lager"
* Die Darstellung erfolgt aggregiert je Kategorie.

---

### 4. Authentifizierung und Sicherheit

* Zugriff auf die Webanwendung erfolgt über ein Benutzerkonto (Benutzername + Passwort).
* Zusätzlich kann ein TOTP-basierter Zwei-Faktor-Authentifizierungsmechanismus (2FA) aktiviert werden.
* TOTP kann über einen QR-Code oder manuell durch einen Schlüssel in Authenticator-Apps (z. B. Google Authenticator) hinzugefügt werden.
* Bei aktivierter 2FA kann das Passwort zurückgesetzt werden, sofern ein gültiger TOTP-Code eingegeben wird.
* Alternativ ist das Zurücksetzen direkt innerhalb der Anwendung (bei bestehender Sitzung) möglich.

---

### 5. Benutzeroberfläche

* Die Webanwendung ist vollständig responsiv und im hellen, minimalistischen Stil mit abgerundeten UI-Elementen gestaltet.
* Die Benutzeroberfläche ist modern und orientiert sich an aktuellen Designstandards im Bereich UI/UX.

---

## Technische Architektur

| Komponente             | Technologie                                    |
| ---------------------- | ---------------------------------------------- |
| **Frontend**           | HTML5, CSS3, JavaScript (Vanilla), Alpine.js   |
| **Backend**            | Python 3.12 mit Flask                          |
| **Datenhaltung**       | SQLite                                         |
| **Authentifizierung**  | Passwort-Hashing (bcrypt), TOTP gemäß RFC 6238 |
| **API-Schnittstellen** | REST-konform, JSON-basiert                     |

---

## Systemanforderungen

* Python 3.12
* Webserver mit WSGI-Support (z. B. Gunicorn, uWSGI)
* Webbrowser mit aktiviertem JavaScript

---

## Projektumfang

* **Frontend-Code:** \~3000 Zeilen (inkl. Formularlogik, dynamisches Rendering, UX-Komponenten)
* **Backend-Code:** \~600 Zeilen (REST-API, Authentifizierung, Datenpersistenz)
* **Datenmodell:** dynamisch, JSON-basiert pro Kategorie
* **Sicherheitsmodul:** Integration von TOTP und Passwort-Reset-Funktionalität

---

## Einrichtung

```bash
# Voraussetzungen
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Starten der Anwendung
python app.py
```

> ⚠️ Die genaue Installationsanleitung kann je nach Hostingumgebung angepasst werden.

---

## Weiterentwicklung & Erweiterbarkeit

* Modularer Aufbau erlaubt spätere Erweiterung (z. B. Exportfunktionen, Gerätegruppen, Benutzerrollen)
* JSON-basierte Felddefinition ermöglicht individuelle Anpassung ohne Codeänderung
* Trennung von Frontend und Backend durch API-Architektur

---

## Lizenz

Dieses Projekt steht unter der GNU Affero General Public License Version 3 (AGPL-3.0).

Sie dürfen diese Software verwenden, verändern und verbreiten, solange alle Änderungen und Erweiterungen unter denselben Bedingungen (AGPL-3.0) veröffentlicht werden, insbesondere bei Nutzung über ein Netzwerk (z. B. als Webanwendung).

Für die kommerzielle Nutzung ohne Offenlegungspflicht (z. B. in geschlossenen Systemen oder als SaaS ohne Quellcodeveröffentlichung) ist eine separate Lizenzvereinbarung notwendig.

Kontakt für kommerzielle Lizenzen: [joshua@pondsec.com](mailto:joshua@pondsec.com)

Der vollständige Lizenztext ist verfügbar unter: [https://www.gnu.org/licenses/agpl-3.0.de.html](https://www.gnu.org/licenses/agpl-3.0.de.html)

---

## Autor

Joshua Pond
Fachinformatiker für Systemintegration
Stand: Juli 2025
