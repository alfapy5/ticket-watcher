# Ticket Watcher

Vigila los precios de reventa en Maizetix para los partidos en casa de Michigan (fútbol americano, basket y hockey masculino) y te manda un aviso al móvil con ntfy cuando aparece una entrada más barata.

## Puesta en marcha (una sola vez)

1. Instala **ntfy** en el móvil (App Store / Google Play).
2. Inventa un nombre de canal largo y aleatorio, por ejemplo `tw-k3j9x2m8q7`, y suscríbete a él en la app. Es secreto: quien lo sepa puede leer tus avisos.
3. Crea un repo **público** en GitHub y sube esta carpeta.
4. En el repo, ve a Settings → Secrets and variables → Actions → New repository secret. Crea `NTFY_TOPIC` con el nombre del canal del paso 2.
5. En la pestaña Actions, activa los workflows y ejecuta `watch` a mano (Run workflow). La primera vuelta solo apunta los precios; no avisa.

Desde ese momento corre solo cada ~15 min.

## Uso diario

Edita `config.toml` desde el móvil (en GitHub, icono del lápiz):

```toml
muted = ["hockey-2026-11-27"]      # partidos que no quieres

[max]
"hockey-2026-11-20" = 25            # avísame si algo baja de $25
```

## Cuándo avisa

- Aparece una entrada al menos $1 más barata que la más barata a la venta.
- Aparece la primera entrada en un partido que no tenía ninguna.
- Una entrada baja de tu máximo para ese partido.
- Maizetix deja de responder o cambia su web: un aviso al fallar y otro al volver.

## Local

```bash
pip install -r requirements.txt
python -m pytest -q
python -m watcher --dry-run
```
