# GardenGlow

PWA Gartenkatalog mit OIDC-Login, Pflanzorten, Pflanzen, Fotos und Kommentaren.

## Start

```bash
docker compose up --build
```

## Setup / Deployment

### Pflichtvariable `SECRET_KEY`

`SECRET_KEY` ist beim App-Start verpflichtend und wird **ohne Default** gelesen.

Anforderungen:
- gesetzt (nicht leer)
- kein offensichtlicher Placeholder (z. B. `dev-secret-change-me`, `changeme`, `secret`)
- mindestens 32 Zeichen

Beispiel (lokal):

```bash
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
```

Wenn `SECRET_KEY` fehlt oder zu schwach ist, bricht die App mit einer klaren Konfigurations-Exception beim Start ab.

### OIDC-Konfiguration

Setze `OIDC_SERVER_METADATA_URL`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET` und optional `OIDC_LOGOUT_URL` in `docker-compose.yml` oder via env.

Hinweis: Sobald eine der kritischen OIDC-Variablen gesetzt ist, müssen alle drei (`OIDC_SERVER_METADATA_URL`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`) gesetzt sein.

## Features
- OIDC Login + Avatar
- Pflanzorte + Pflanzen
- Fotos mit Datum/Kommentar
- Kommentare ohne Foto
- PWA installierbar
- Hell/Dunkel Schalter (unten)
- Reverse-Proxy-tauglich via `ProxyFix`
- Healthcheck unter `/healthz`
