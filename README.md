# GardenGlow

GardenGlow ist eine Progressive Web App (PWA) zur Verwaltung eines Gartenkatalogs.
Die Anwendung verwaltet Pflanzorte, Pflanzen, Fotos und Kommentare – mit **ausschließlicher Anmeldung über OIDC (OpenID Connect)**.

## Funktionsbeschreibung

GardenGlow ist für den Betrieb in Containern ausgelegt und speichert alle Daten persistent in einem Volume.
Nach dem Start meldet sich der Benutzer über einen externen OIDC-Provider an (kein lokaler Benutzername/Passwort-Login).
Nach erfolgreicher Anmeldung können Gartenbereiche (Pflanzorte) angelegt und darin Pflanzen verwaltet werden.
Zu Pflanzen lassen sich Fotos mit Datum und Kommentar sowie reine Textkommentare hinterlegen.
Zusätzlich ist die Anwendung als installierbare PWA nutzbar und enthält einen Healthcheck-Endpunkt für Monitoring.

## Features

- OIDC-Login (OpenID Connect) als **einziger** Authentifizierungsweg
- Benutzerprofil mit Name, E-Mail und Avatar (Avatar-Download vom OIDC-Profilbild)
- Verwaltung von Pflanzorten und zugeordneten Pflanzen
- Foto-Uploads inkl. Datum und Beschreibung
- Kommentare auch ohne Foto möglich
- Installierbare PWA (inkl. Web App Manifest / Service Worker)
- Hell-/Dunkelmodus
- Reverse-Proxy-tauglich durch `ProxyFix`
- Healthcheck unter `/healthz`

## Start mit Docker Compose

### `docker-compose.yml`

```yaml
services:
  gardenglow:
    build: https://github.com/doenke/garten.git#main
    container_name: gardenglow
    restart: unless-stopped
    environment:
      SECRET_KEY: changeme
      DATABASE_URL: sqlite:////data/garden.db
      UPLOAD_FOLDER: /data/uploads
      OIDC_SERVER_METADATA_URL: https://example.com/.well-known/openid-configuration
      OIDC_CLIENT_ID: change-me
      OIDC_CLIENT_SECRET: change-me
      OIDC_LOGOUT_URL: https://example.com/logout
    volumes:
      - gardenglow_data:/data
    ports:
      - "8000:8000"
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')"]
      interval: 30s
      timeout: 3s
      retries: 3
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.gardenglow.rule=Host(`gardenglow.local`)"
      - "traefik.http.services.gardenglow.loadbalancer.server.port=8000"
volumes:
  gardenglow_data:
```

### Start

```bash
docker compose up --build
```

## Wichtige Umgebungsvariablen

### Allgemein

- `SECRET_KEY` – Flask Secret Key (Sessions/Signaturen)
- `DATABASE_URL` – SQLAlchemy-Datenbankverbindung (z. B. SQLite in `/data`)
- `UPLOAD_FOLDER` – Verzeichnis für hochgeladene Pflanzenfotos
- `AVATAR_FOLDER` – Verzeichnis für lokal gespeicherte Benutzer-Avatare
- `MAP_FOLDER` – Verzeichnis für Karten-/Lageplan-Dateien

### OIDC (Pflicht für Login)

- `OIDC_SERVER_METADATA_URL` – URL zur OIDC Discovery (`.well-known/openid-configuration`)
- `OIDC_CLIENT_ID` – OIDC Client-ID
- `OIDC_CLIENT_SECRET` – OIDC Client-Secret
- `OIDC_LOGOUT_URL` *(optional)* – Externe Logout-URL des Identity-Providers

> Hinweis: Ohne korrekt gesetzte OIDC-Variablen ist keine Anmeldung möglich, da GardenGlow keinen lokalen Passwort-Login anbietet.
