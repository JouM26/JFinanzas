# JFinanzas

Aplicación de finanzas personales desarrollada con Flet.

## Widget de Android

La APK incluye el widget “Mis Finanzas” con dos accesos: **+ Ingreso** en verde y **− Gasto** en rojo. Al tocar uno, Android abre un formulario rápido para ingresar descripción, categoría y monto. Los movimientos del widget se guardan directamente en `finanzas.db` con medio de pago efectivo y aparecen en la app la próxima vez que se consulte o abra.

Para agregarlo, mantén presionada la pantalla de inicio del teléfono, abre **Widgets**, busca **Mis Finanzas** y arrástralo a la pantalla.

El workflow de GitHub compila con la plantilla Flet incluida en `flet_build_template`, que incorpora el widget nativo de Android.

## Actualizaciones de Android y firma

Una vez configurados los secretos, el workflow publica APK firmadas con una clave persistente y aumenta `versionCode` usando el número de ejecución de GitHub Actions. Android conserva los datos privados al instalar una actualización cuando coinciden el identificador de paquete y el certificado de firma, y la versión nueva tiene un código mayor. Después de la transición inicial a esta firma estable, instala cada APK sobre la anterior sin desinstalarla.

Antes de compilar, crea una clave privada de publicación en un lugar seguro (no la subas al repositorio):

```powershell
keytool -genkeypair -v -keystore jfinanzas-release.jks -alias jfinanzas -keyalg RSA -keysize 2048 -validity 10000
[Convert]::ToBase64String([IO.File]::ReadAllBytes((Resolve-Path .\jfinanzas-release.jks))) | Set-Clipboard
```

En GitHub, abre **Settings → Secrets and variables → Actions** y crea estos secretos:

- `ANDROID_KEYSTORE_BASE64`: contenido Base64 copiado al portapapeles.
- `ANDROID_KEYSTORE_PASSWORD`: contraseña del archivo `.jks`.
- `ANDROID_KEY_PASSWORD`: contraseña de la clave (puede ser la misma).
- `ANDROID_KEY_ALIAS`: `jfinanzas`.

Guarda una copia segura de la clave `.jks` y sus contraseñas. Sin ellas no se podrán firmar actualizaciones compatibles. Mantén estable el identificador de paquete configurado por Flet.

La app ya instalada puede tener otro certificado por las compilaciones anteriores sin firma persistente. Si Android rechaza la primera APK firmada como actualización, esa transición requiere una sola reinstalación: exporta primero el respaldo JSON desde la app, desinstala, instala la APK firmada e importa el JSON. Después de esa transición, las actualizaciones firmadas con la misma clave conservan la base de datos automáticamente. La base se almacena en el espacio privado persistente de la app y se migra desde la ruta usada por versiones previas al abrir la versión actualizada.
