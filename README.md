# JFinanzas

Aplicación de finanzas personales desarrollada con Flet.

## Widget de Android

La APK incluye el widget “Mis Finanzas” con dos accesos: **+ Ingreso** en verde y **− Gasto** en rojo. Al tocar uno, Android abre un formulario rápido para ingresar descripción, categoría y monto. Los movimientos del widget se guardan directamente en `finanzas.db` con medio de pago efectivo y aparecen en la app la próxima vez que se consulte o abra.

Para agregarlo, mantén presionada la pantalla de inicio del teléfono, abre **Widgets**, busca **Mis Finanzas** y arrástralo a la pantalla.

El workflow de GitHub compila con la plantilla Flet incluida en `flet_build_template`, que incorpora el widget nativo de Android.
