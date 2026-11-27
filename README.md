# BODIVE

Agente comercial supervisado para crear y evaluar productos digitales en inglés. La primera versión genera un cuaderno de trabajo en Markdown y una ficha comercial. Ejecuta el flujo local con Python 3.12 o el flujo supervisado con GitHub Actions, Supabase y Telegram.

## Simulación local

Desde la raíz del repositorio, con Python 3.12:

```sh
python3.12 -m unittest discover -s tests -v
python3.12 -m bodive.cli plan "Client onboarding" --price 1200 --unit-cost 400
python3.12 -m bodive.cli show ID_DEL_DOSIER
python3.12 -m bodive.cli propose-publish ID_DEL_DOSIER
python3.12 -m bodive.cli simulate-decision ID_DE_APROBACION approve
python3.12 -m bodive.cli claim ID_DE_APROBACION
python3.12 -m bodive.cli complete ID_DE_APROBACION 0 https://example.invalid/product
python3.12 -m bodive.cli report
```

La simulación usa SQLite y trabaja sin credenciales ni red. Puedes aislar experimentos con `BODIVE_STATE_PATH`. Para ensayar creación con Claude, sustituye la propuesta de publicación por `propose-claude`, apruébala y ejecuta `run-claude`. El resultado simulado se guarda en el expediente de aprobación. La activación real y los pasos de revisión están en el [manual de operación](docs/operacion.md).

## Alcance

| Módulo | Función |
| --- | --- |
| Director | Coordina la investigación, el análisis y la preparación del dosier por tema. |
| Investigador | Registra hasta cinco repositorios públicos con enlaces, estrellas y fecha de actualización. Son señales de actividad, con demanda comercial pendiente de validar. |
| Analista | Calcula margen, escenarios y punto de equilibrio en EUR a partir de supuestos del operador. Identifica sustitutos y riesgos. |
| Creador | Genera un cuaderno en Markdown y permite pedir un borrador enriquecido a Claude con autorización. |
| Comercial | Prepara la ficha y un enfoque de distribución consentida. Delega la publicación y los anuncios en el operador. |
| Financiero | Registra gastos y cobros netos realizados, reserva compromisos y calcula el resultado. |
| Supervisor | Vincula la decisión al contenido, exige identidad autorizada y limita alcance y vigencia. |
| Memoria | Conserva dosieres, decisiones, borradores, apuntes, eventos y la parada. |

La contabilidad de esta versión es operativa y en EUR. Los cobros de Gumroad y los costes facturados se concilian manualmente. Para un reembolso, registra el cobro neto definitivo o reconcilia externamente si el cobro ya quedó asentado. Quedan pendientes la importación de ventas, las fuentes de demanda comercial directa y la detección automática de plagio.

## Verificación

El workflow **CI** ejecuta las pruebas en Python 3.12 con PostgreSQL desechable para comprobar la migración, la concurrencia y los permisos del rol. La suite local básica usa SQLite y simula las respuestas de proveedores. El workflow **BODIVE** ofrece una demo sin secretos y tareas supervisadas en la rama por defecto. La ejecución supervisada requiere activación explícita.
