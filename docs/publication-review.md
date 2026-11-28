# Revisión de publicación

1. Conserva el archivo definitivo localmente. No regenerarlo después de revisarlo.
2. Ejecuta `python -m bodive.cli artifact-review DOSIER archivo.xlsx`.
3. En modo live, solicita la revisión con `/notify ID` en Telegram. Comprueba el contenido local y compara el SHA-256 mostrado mediante /review ID antes de aprobar. La aprobación caduca a las 24 horas.
4. Ejecuta `python -m bodive.cli artifact-handoff DOSIER archivo.xlsx ID` con los mismos bytes. El comando consume la autorización una sola vez y devuelve un manifiesto, no publica ni envía el archivo.
5. Cualquier cambio exige una nueva revisión. La parada de emergencia bloquea la entrega.

No se almacena el archivo en la base de datos. No publicar los ZIP de revisión. La entrega no confirma una venta ni autoriza gastos. Los flujos anteriores de preparación de borradores no constituyen una aprobación del archivo definitivo.
