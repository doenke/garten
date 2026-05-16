# GardenGlow

PWA Gartenkatalog mit OIDC-Login, Pflanzorten, Pflanzen, Fotos und Kommentaren.

## Start

```bash
docker compose up --build
```

## OIDC
Setze `OIDC_SERVER_METADATA_URL`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET` in `docker-compose.yml` oder via env.

## Features
- OIDC Login + Avatar
- Pflanzorte + Pflanzen
- Fotos mit Datum/Kommentar
- Kommentare ohne Foto
- PWA installierbar
- Hell/Dunkel Schalter (unten)
- Reverse-Proxy-tauglich via `ProxyFix`
- Healthcheck unter `/healthz`
