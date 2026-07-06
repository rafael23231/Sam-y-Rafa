# 💊 MediRecuerda

Asistente de medicación para pacientes con enfermedades crónicas y/o de tercera edad.

**Problemática:** los pacientes olvidan si ya tomaron su dosis diaria, lo que genera
duplicidad de dosis (riesgo de sobredosis) o tratamientos incompletos.

## Cómo ejecutar

```
python app.py
```

No requiere instalar nada: usa solo la librería estándar de Python (Tkinter). Los datos
se guardan automáticamente en `datos.json`.

## Funcionalidades

| Requisito | Dónde está |
|---|---|
| Perfil de paciente | Pestaña **Perfil del paciente** (incluye familiar de contacto) |
| Recordatorios por notificaciones | Ventana emergente con sonido a la hora programada de cada dosis |
| Confirmación de toma de dosis | Botón **✔ Ya la tomé** en la notificación, o **Confirmar toma** en la pestaña **Hoy** |
| Detección de dosis duplicadas | Si se intenta confirmar una dosis ya tomada, la app lo bloquea y advierte del peligro |
| Detección de dosis omitidas | A los 15 min sin confirmar → *Atrasada*; a las 2 horas → *Omitida* |
| Notificación a familiares (2 h de atraso) | SMS simulado al familiar de contacto, visible en **Historial y alertas** |

## Demostración rápida

1. Pestaña **Perfil del paciente**: llene los datos y el familiar de contacto → *Guardar perfil*.
2. Pestaña **Medicamentos**: agregue un medicamento con un horario cercano a la hora actual
   (por ejemplo, la hora actual + 1 minuto).
3. Espere la notificación emergente, o use la pestaña **Simulación (demo)** para adelantar
   el reloj interno:
   - **+15 min** → la dosis pasa a *Atrasada* ⚠
   - **+2 horas** → la dosis pasa a *Omitida* ✖ y se envía la alerta simulada al familiar 🚨
4. Intente confirmar dos veces la misma dosis → la app detecta y bloquea la **dosis duplicada** ⛔.

Todo el historial de eventos (tomas, omisiones, duplicados y avisos) queda en la pestaña
**Historial y alertas**.
