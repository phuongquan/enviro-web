# Enviro Urban Web Display

This web app displays readings taken using an [Enviro Urban Raspberry Pi Pico W](https://shop.pimoroni.com/products/enviro-urban) kit

## Details

Readings are stored as GitHub gists.

### Enviro Urban Pico W kit

Readings from the Enviro Urban are uploaded to the web app by specifying "[webapp_address]/enviro" as a custom HTTP endpoint, and using a recognised nickname.

A modified version of the Enviro firmware was created to allow the kit to be placed out of reach of a wifi connection, and to upload locally-stored readings on demand via a mobile hotspot. The [`upload_on_poke` branch](https://github.com/phuongquan/enviro/tree/upload_on_poke) was created off the v0.0.9 pimoroni release.

### Deployment of web app to pythonanywhere.com

Since this is a dash app, start with a flask app then update the WSGI configuration file, replacing

```
from app import app as application
```

with

```
from app import app
application = app.server
```
