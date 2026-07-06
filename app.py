"""
MediRecuerda - Asistente de medicación para pacientes crónicos y de tercera edad.

Problemática: los pacientes olvidan si ya tomaron su dosis diaria, lo que genera
duplicidad dedosis o tratamientos incompletos.

Funcionalidades:
  * Perfil de paciente (con contacto familiar)
  * Recordatorios de horarios mediante notificaciones emergentes
  * Confirmación de toma de dosis
  * Detección de dosis duplicadas y omitidas
  * Notificación simulada a familiares cuando una dosis lleva 2+ horas de atraso
  * Panel de simulación de tiempo para demostrar el flujo completo

Ejecutar:  python app.py
"""

import json
import os
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, date, time, timedelta

try:
    import winsound
    def beep():
        try:
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception:
            pass
except ImportError:
    def beep():
        pass

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datos.json")

HORAS_ATRASO_FAMILIAR = 2      # horas de atraso para avisar al familiar
MINUTOS_VENTANA_RECORDATORIO = 0  # el recordatorio salta a la hora exacta

ESTADO_PENDIENTE = "pendiente"
ESTADO_TOMADA = "tomada"
ESTADO_ATRASADA = "atrasada"
ESTADO_OMITIDA = "omitida"


# ---------------------------------------------------------------- persistencia

def datos_por_defecto():
    return {
        "paciente": {
            "nombre": "",
            "edad": "",
            "enfermedades": "",
            "telefono": "",
            "familiar_nombre": "",
            "familiar_telefono": "",
        },
        "medicamentos": [],   # {id, nombre, dosis, horarios: ["08:00", ...]}
        "registros": {},      # "YYYY-MM-DD|med_id|HH:MM" -> {estado, hora_confirmacion, familiar_avisado, recordatorio_mostrado, intentos_duplicados}
        "siguiente_id": 1,
    }


def cargar_datos():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                datos = json.load(f)
            base = datos_por_defecto()
            base.update(datos)
            return base
        except (json.JSONDecodeError, OSError):
            pass
    return datos_por_defecto()


def guardar_datos(datos):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)


# ------------------------------------------------------------------- app

class MediRecuerdaApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MediRecuerda - Asistente de Medicación")
        self.geometry("980x640")
        self.minsize(860, 560)

        self.datos = cargar_datos()
        self.offset_simulacion = timedelta(0)  # para demo: adelantar el reloj

        self._construir_ui()
        self._refrescar_todo()
        self._tick()  # inicia el chequeo periódico

    # ---- reloj (real + offset de simulación)

    def ahora(self):
        return datetime.now() + self.offset_simulacion

    def hoy(self):
        return self.ahora().date()

    # ---- construcción de interfaz

    def _construir_ui(self):
        estilo = ttk.Style(self)
        estilo.configure("Titulo.TLabel", font=("Segoe UI", 16, "bold"))
        estilo.configure("Sub.TLabel", font=("Segoe UI", 10), foreground="#555")
        estilo.configure("Reloj.TLabel", font=("Consolas", 12, "bold"), foreground="#0a6")

        barra = ttk.Frame(self, padding=(12, 8))
        barra.pack(fill="x")
        ttk.Label(barra, text="💊 MediRecuerda", style="Titulo.TLabel").pack(side="left")
        self.lbl_reloj = ttk.Label(barra, text="", style="Reloj.TLabel")
        self.lbl_reloj.pack(side="right")

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.tab_hoy = ttk.Frame(self.notebook, padding=10)
        self.tab_perfil = ttk.Frame(self.notebook, padding=10)
        self.tab_meds = ttk.Frame(self.notebook, padding=10)
        self.tab_historial = ttk.Frame(self.notebook, padding=10)
        self.tab_sim = ttk.Frame(self.notebook, padding=10)

        self.notebook.add(self.tab_hoy, text="  Hoy  ")
        self.notebook.add(self.tab_perfil, text="  Perfil del paciente  ")
        self.notebook.add(self.tab_meds, text="  Medicamentos  ")
        self.notebook.add(self.tab_historial, text="  Historial y alertas  ")
        self.notebook.add(self.tab_sim, text="  Simulación (demo)  ")

        self._construir_tab_hoy()
        self._construir_tab_perfil()
        self._construir_tab_meds()
        self._construir_tab_historial()
        self._construir_tab_sim()

    # ---- pestaña HOY

    def _construir_tab_hoy(self):
        ttk.Label(self.tab_hoy,
                  text="Dosis programadas para hoy. Confirme cada toma con el botón ✔.",
                  style="Sub.TLabel").pack(anchor="w", pady=(0, 6))

        cols = ("medicamento", "dosis", "hora", "estado", "confirmada")
        self.tree_hoy = ttk.Treeview(self.tab_hoy, columns=cols, show="headings", height=14)
        encabezados = {
            "medicamento": ("Medicamento", 220),
            "dosis": ("Dosis", 140),
            "hora": ("Hora programada", 120),
            "estado": ("Estado", 160),
            "confirmada": ("Hora de confirmación", 160),
        }
        for c, (txt, ancho) in encabezados.items():
            self.tree_hoy.heading(c, text=txt)
            self.tree_hoy.column(c, width=ancho, anchor="center")
        self.tree_hoy.pack(fill="both", expand=True)

        self.tree_hoy.tag_configure("tomada", background="#d9f7d9")
        self.tree_hoy.tag_configure("atrasada", background="#fff3cd")
        self.tree_hoy.tag_configure("omitida", background="#f8d7da")

        botones = ttk.Frame(self.tab_hoy)
        botones.pack(fill="x", pady=8)
        ttk.Button(botones, text="✔  Confirmar toma seleccionada",
                   command=self._confirmar_toma).pack(side="left")
        ttk.Button(botones, text="🔄 Actualizar",
                   command=self._refrescar_todo).pack(side="left", padx=8)

        self.lbl_resumen = ttk.Label(self.tab_hoy, text="", style="Sub.TLabel")
        self.lbl_resumen.pack(anchor="w")

    # ---- pestaña PERFIL

    def _construir_tab_perfil(self):
        marco = ttk.LabelFrame(self.tab_perfil, text="Datos del paciente", padding=12)
        marco.pack(fill="x")

        campos = [
            ("nombre", "Nombre completo:"),
            ("edad", "Edad:"),
            ("enfermedades", "Enfermedades crónicas:"),
            ("telefono", "Teléfono del paciente:"),
            ("familiar_nombre", "Nombre del familiar de contacto:"),
            ("familiar_telefono", "Teléfono del familiar:"),
        ]
        self.entradas_perfil = {}
        for fila, (clave, etiqueta) in enumerate(campos):
            ttk.Label(marco, text=etiqueta).grid(row=fila, column=0, sticky="w", pady=4, padx=(0, 8))
            ent = ttk.Entry(marco, width=45)
            ent.grid(row=fila, column=1, sticky="w", pady=4)
            ent.insert(0, self.datos["paciente"].get(clave, ""))
            self.entradas_perfil[clave] = ent

        ttk.Button(marco, text="💾 Guardar perfil", command=self._guardar_perfil)\
            .grid(row=len(campos), column=1, sticky="w", pady=(10, 0))

        ttk.Label(self.tab_perfil,
                  text="El familiar de contacto recibirá una notificación (simulada) si una dosis "
                       f"lleva más de {HORAS_ATRASO_FAMILIAR} horas de atraso sin confirmarse.",
                  style="Sub.TLabel", wraplength=700).pack(anchor="w", pady=10)

    def _guardar_perfil(self):
        for clave, ent in self.entradas_perfil.items():
            self.datos["paciente"][clave] = ent.get().strip()
        guardar_datos(self.datos)
        messagebox.showinfo("Perfil", "Perfil del paciente guardado correctamente.")

    # ---- pestaña MEDICAMENTOS

    def _construir_tab_meds(self):
        marco_alta = ttk.LabelFrame(self.tab_meds, text="Agregar medicamento", padding=12)
        marco_alta.pack(fill="x")

        ttk.Label(marco_alta, text="Nombre:").grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.ent_med_nombre = ttk.Entry(marco_alta, width=25)
        self.ent_med_nombre.grid(row=0, column=1, padx=(0, 14))

        ttk.Label(marco_alta, text="Dosis (ej. 500 mg, 1 tableta):").grid(row=0, column=2, sticky="w", padx=(0, 6))
        self.ent_med_dosis = ttk.Entry(marco_alta, width=20)
        self.ent_med_dosis.grid(row=0, column=3, padx=(0, 14))

        ttk.Label(marco_alta, text="Horarios (HH:MM separados por coma):").grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self.ent_med_horarios = ttk.Entry(marco_alta, width=30)
        self.ent_med_horarios.grid(row=1, column=2, columnspan=2, sticky="w", pady=(8, 0))
        self.ent_med_horarios.insert(0, "08:00, 14:00, 20:00")

        ttk.Button(marco_alta, text="➕ Agregar", command=self._agregar_medicamento)\
            .grid(row=2, column=3, sticky="e", pady=(10, 0))

        cols = ("nombre", "dosis", "horarios")
        self.tree_meds = ttk.Treeview(self.tab_meds, columns=cols, show="headings", height=10)
        for c, txt, ancho in (("nombre", "Medicamento", 240),
                              ("dosis", "Dosis", 180),
                              ("horarios", "Horarios diarios", 300)):
            self.tree_meds.heading(c, text=txt)
            self.tree_meds.column(c, width=ancho, anchor="center")
        self.tree_meds.pack(fill="both", expand=True, pady=10)

        ttk.Button(self.tab_meds, text="🗑 Eliminar medicamento seleccionado",
                   command=self._eliminar_medicamento).pack(anchor="w")

    def _agregar_medicamento(self):
        nombre = self.ent_med_nombre.get().strip()
        dosis = self.ent_med_dosis.get().strip()
        horarios_txt = self.ent_med_horarios.get().strip()

        if not nombre or not dosis or not horarios_txt:
            messagebox.showwarning("Datos incompletos", "Complete nombre, dosis y horarios.")
            return

        horarios = []
        for parte in horarios_txt.split(","):
            parte = parte.strip()
            try:
                h = datetime.strptime(parte, "%H:%M").time()
                horarios.append(h.strftime("%H:%M"))
            except ValueError:
                messagebox.showerror("Formato inválido",
                                     f"'{parte}' no es una hora válida. Use el formato HH:MM (ej. 08:00).")
                return
        horarios = sorted(set(horarios))

        med = {
            "id": self.datos["siguiente_id"],
            "nombre": nombre,
            "dosis": dosis,
            "horarios": horarios,
        }
        self.datos["siguiente_id"] += 1
        self.datos["medicamentos"].append(med)
        guardar_datos(self.datos)

        self.ent_med_nombre.delete(0, "end")
        self.ent_med_dosis.delete(0, "end")
        self._refrescar_todo()
        messagebox.showinfo("Medicamento agregado",
                            f"{nombre} ({dosis}) programado a las: {', '.join(horarios)}")

    def _eliminar_medicamento(self):
        sel = self.tree_meds.selection()
        if not sel:
            messagebox.showwarning("Sin selección", "Seleccione un medicamento de la lista.")
            return
        med_id = int(sel[0])
        med = self._buscar_med(med_id)
        if med and messagebox.askyesno("Confirmar", f"¿Eliminar {med['nombre']} y sus horarios?"):
            self.datos["medicamentos"] = [m for m in self.datos["medicamentos"] if m["id"] != med_id]
            guardar_datos(self.datos)
            self._refrescar_todo()

    def _buscar_med(self, med_id):
        for m in self.datos["medicamentos"]:
            if m["id"] == med_id:
                return m
        return None

    # ---- pestaña HISTORIAL

    def _construir_tab_historial(self):
        ttk.Label(self.tab_historial,
                  text="Registro de eventos: tomas confirmadas, dosis omitidas, intentos duplicados "
                       "y avisos enviados a familiares.",
                  style="Sub.TLabel").pack(anchor="w", pady=(0, 6))
        self.txt_historial = tk.Text(self.tab_historial, state="disabled", wrap="word",
                                     font=("Consolas", 10))
        self.txt_historial.pack(fill="both", expand=True)
        self.txt_historial.tag_configure("ok", foreground="#0a7a0a")
        self.txt_historial.tag_configure("alerta", foreground="#b36b00")
        self.txt_historial.tag_configure("critico", foreground="#c0392b", font=("Consolas", 10, "bold"))

    def _log(self, mensaje, tag="ok"):
        marca = self.ahora().strftime("%Y-%m-%d %H:%M")
        self.txt_historial.configure(state="normal")
        self.txt_historial.insert("end", f"[{marca}]  {mensaje}\n", tag)
        self.txt_historial.see("end")
        self.txt_historial.configure(state="disabled")

    # ---- pestaña SIMULACIÓN

    def _construir_tab_sim(self):
        marco = ttk.LabelFrame(self.tab_sim, text="Simulación de tiempo (para demostración)", padding=12)
        marco.pack(fill="x")

        ttk.Label(marco, wraplength=760, text=(
            "Para demostrar la app sin esperar horas reales, puede adelantar el reloj interno. "
            "Al adelantar el tiempo se dispararán los recordatorios, la detección de dosis omitidas "
            "y, tras 2 horas de atraso, la notificación simulada al familiar de contacto."
        )).pack(anchor="w", pady=(0, 10))

        fila = ttk.Frame(marco)
        fila.pack(anchor="w")
        for etiqueta, minutos in (("+15 min", 15), ("+30 min", 30), ("+1 hora", 60),
                                  ("+2 horas", 120), ("+6 horas", 360)):
            ttk.Button(fila, text=etiqueta,
                       command=lambda m=minutos: self._avanzar_tiempo(m)).pack(side="left", padx=4)
        ttk.Button(fila, text="⏮ Restablecer reloj real",
                   command=self._reset_tiempo).pack(side="left", padx=16)

        self.lbl_offset = ttk.Label(marco, text="", style="Sub.TLabel")
        self.lbl_offset.pack(anchor="w", pady=(10, 0))

    def _avanzar_tiempo(self, minutos):
        self.offset_simulacion += timedelta(minutes=minutos)
        self._log(f"⏩ SIMULACIÓN: reloj adelantado {minutos} min "
                  f"(desfase total: {self.offset_simulacion}).", "alerta")
        self._evaluar_dosis()
        self._refrescar_todo()

    def _reset_tiempo(self):
        self.offset_simulacion = timedelta(0)
        self._log("⏮ SIMULACIÓN: reloj restablecido a la hora real.", "alerta")
        self._refrescar_todo()

    # ---- lógica principal de dosis

    def _clave_registro(self, med_id, hora, dia=None):
        dia = dia or self.hoy()
        return f"{dia.isoformat()}|{med_id}|{hora}"

    def _registro(self, med_id, hora):
        clave = self._clave_registro(med_id, hora)
        if clave not in self.datos["registros"]:
            self.datos["registros"][clave] = {
                "estado": ESTADO_PENDIENTE,
                "hora_confirmacion": None,
                "familiar_avisado": False,
                "recordatorio_mostrado": False,
                "intentos_duplicados": 0,
            }
        return self.datos["registros"][clave]

    def _dosis_de_hoy(self):
        """Lista de (med, hora_str, registro) ordenada por hora."""
        resultado = []
        for med in self.datos["medicamentos"]:
            for hora in med["horarios"]:
                resultado.append((med, hora, self._registro(med["id"], hora)))
        resultado.sort(key=lambda t: t[1])
        return resultado

    def _evaluar_dosis(self):
        """Motor de estados: recordatorios, atrasos, omisiones y aviso a familiar."""
        ahora = self.ahora()
        cambio = False

        for med, hora_str, reg in self._dosis_de_hoy():
            h, m = map(int, hora_str.split(":"))
            momento = datetime.combine(self.hoy(), time(h, m))
            if reg["estado"] == ESTADO_TOMADA:
                continue

            if ahora < momento:
                continue  # aún no toca

            atraso = ahora - momento

            # 1) recordatorio al llegar la hora
            if not reg["recordatorio_mostrado"]:
                reg["recordatorio_mostrado"] = True
                cambio = True
                self._notificar_paciente(med, hora_str)

            # 2) pasa a "atrasada" después de 15 min sin confirmar
            if reg["estado"] == ESTADO_PENDIENTE and atraso >= timedelta(minutes=15):
                reg["estado"] = ESTADO_ATRASADA
                cambio = True
                self._log(f"⚠ Dosis atrasada: {med['nombre']} ({med['dosis']}) de las {hora_str}.", "alerta")

            # 3) a las 2 horas: dosis omitida + aviso simulado al familiar
            if atraso >= timedelta(hours=HORAS_ATRASO_FAMILIAR):
                if reg["estado"] != ESTADO_OMITIDA:
                    reg["estado"] = ESTADO_OMITIDA
                    cambio = True
                    self._log(f"✖ DOSIS OMITIDA: {med['nombre']} ({med['dosis']}) de las {hora_str} "
                              f"no fue confirmada en {HORAS_ATRASO_FAMILIAR} horas.", "critico")
                if not reg["familiar_avisado"]:
                    reg["familiar_avisado"] = True
                    cambio = True
                    self._notificar_familiar(med, hora_str)

        if cambio:
            guardar_datos(self.datos)

    def _notificar_paciente(self, med, hora_str):
        beep()
        paciente = self.datos["paciente"].get("nombre") or "Paciente"
        ventana = tk.Toplevel(self)
        ventana.title("⏰ Recordatorio de medicamento")
        ventana.geometry("420x190")
        ventana.attributes("-topmost", True)
        ventana.configure(bg="#fffbe6")

        tk.Label(ventana, text="⏰ ¡Hora de su medicamento!", bg="#fffbe6",
                 font=("Segoe UI", 14, "bold")).pack(pady=(14, 4))
        tk.Label(ventana, bg="#fffbe6", font=("Segoe UI", 11),
                 text=f"{paciente}:\n{med['nombre']} — {med['dosis']}\nHora programada: {hora_str}").pack()

        def tomar_ahora():
            ventana.destroy()
            self._marcar_tomada(med["id"], hora_str)

        fila = tk.Frame(ventana, bg="#fffbe6")
        fila.pack(pady=12)
        ttk.Button(fila, text="✔ Ya la tomé", command=tomar_ahora).pack(side="left", padx=6)
        ttk.Button(fila, text="Recordar más tarde", command=ventana.destroy).pack(side="left", padx=6)

        self._log(f"⏰ Recordatorio mostrado: {med['nombre']} ({med['dosis']}) a las {hora_str}.", "alerta")

    def _notificar_familiar(self, med, hora_str):
        beep()
        familiar = self.datos["paciente"].get("familiar_nombre") or "Familiar de contacto"
        tel = self.datos["paciente"].get("familiar_telefono") or "(sin teléfono registrado)"
        paciente = self.datos["paciente"].get("nombre") or "el paciente"

        mensaje_sms = (f"📱 [SMS SIMULADO → {familiar} {tel}]  Alerta: {paciente} no ha confirmado "
                       f"la toma de {med['nombre']} ({med['dosis']}) programada a las {hora_str}. "
                       f"Lleva más de {HORAS_ATRASO_FAMILIAR} horas de atraso. "
                       "Por favor comuníquese con el paciente.")
        self._log(mensaje_sms, "critico")

        messagebox.showwarning(
            "🚨 Notificación al familiar (simulada)",
            f"Se envió una alerta simulada a {familiar} ({tel}):\n\n"
            f"\"{paciente} no ha confirmado la toma de {med['nombre']} "
            f"({med['dosis']}) de las {hora_str}. "
            f"Lleva más de {HORAS_ATRASO_FAMILIAR} horas de atraso.\"")

    # ---- confirmación de toma + detección de duplicados

    def _confirmar_toma(self):
        sel = self.tree_hoy.selection()
        if not sel:
            messagebox.showwarning("Sin selección", "Seleccione una dosis de la lista de hoy.")
            return
        med_id, hora_str = sel[0].split("|")
        self._marcar_tomada(int(med_id), hora_str)

    def _marcar_tomada(self, med_id, hora_str):
        med = self._buscar_med(med_id)
        if not med:
            return
        reg = self._registro(med_id, hora_str)

        # --- DETECCIÓN DE DOSIS DUPLICADA ---
        if reg["estado"] == ESTADO_TOMADA:
            reg["intentos_duplicados"] += 1
            guardar_datos(self.datos)
            beep()
            self._log(f"⛔ DOSIS DUPLICADA evitada: {med['nombre']} de las {hora_str} "
                      f"ya fue confirmada a las {reg['hora_confirmacion']}. "
                      f"(Intento duplicado #{reg['intentos_duplicados']})", "critico")
            messagebox.showerror(
                "⛔ ¡Dosis duplicada detectada!",
                f"Esta dosis de {med['nombre']} ({med['dosis']}) de las {hora_str} "
                f"YA FUE TOMADA hoy a las {reg['hora_confirmacion']}.\n\n"
                "NO la tome de nuevo. Tomar una dosis doble puede ser peligroso.\n"
                "Si tiene dudas, consulte a su médico.")
            return

        confirmada_omitida = reg["estado"] == ESTADO_OMITIDA
        reg["estado"] = ESTADO_TOMADA
        reg["hora_confirmacion"] = self.ahora().strftime("%H:%M")
        guardar_datos(self.datos)

        if confirmada_omitida:
            self._log(f"✔ Toma tardía confirmada: {med['nombre']} de las {hora_str} "
                      f"(confirmada a las {reg['hora_confirmacion']}).", "alerta")
        else:
            self._log(f"✔ Toma confirmada: {med['nombre']} ({med['dosis']}) de las {hora_str} "
                      f"a las {reg['hora_confirmacion']}.", "ok")
        self._refrescar_todo()

    # ---- refresco de vistas

    def _refrescar_todo(self):
        self._refrescar_hoy()
        self._refrescar_meds()
        self._refrescar_reloj()

    def _refrescar_reloj(self):
        texto = self.ahora().strftime("%A %d/%m/%Y  %H:%M")
        if self.offset_simulacion:
            texto += "  (SIMULADO)"
        self.lbl_reloj.configure(text=texto)
        if hasattr(self, "lbl_offset"):
            self.lbl_offset.configure(
                text=f"Desfase de simulación actual: {self.offset_simulacion or 'ninguno (hora real)'}")

    def _refrescar_hoy(self):
        self.tree_hoy.delete(*self.tree_hoy.get_children())
        etiquetas_estado = {
            ESTADO_PENDIENTE: "⏳ Pendiente",
            ESTADO_TOMADA: "✔ Tomada",
            ESTADO_ATRASADA: "⚠ Atrasada",
            ESTADO_OMITIDA: "✖ Omitida",
        }
        tomadas = omitidas = total = 0
        for med, hora, reg in self._dosis_de_hoy():
            total += 1
            if reg["estado"] == ESTADO_TOMADA:
                tomadas += 1
            elif reg["estado"] == ESTADO_OMITIDA:
                omitidas += 1
            tag = reg["estado"] if reg["estado"] in ("tomada", "atrasada", "omitida") else ""
            self.tree_hoy.insert(
                "", "end", iid=f"{med['id']}|{hora}",
                values=(med["nombre"], med["dosis"], hora,
                        etiquetas_estado[reg["estado"]],
                        reg["hora_confirmacion"] or "—"),
                tags=(tag,) if tag else ())
        self.lbl_resumen.configure(
            text=f"Resumen de hoy: {tomadas}/{total} dosis tomadas · {omitidas} omitidas.")

    def _refrescar_meds(self):
        self.tree_meds.delete(*self.tree_meds.get_children())
        for med in self.datos["medicamentos"]:
            self.tree_meds.insert("", "end", iid=str(med["id"]),
                                  values=(med["nombre"], med["dosis"], ", ".join(med["horarios"])))

    # ---- bucle periódico

    def _tick(self):
        self._evaluar_dosis()
        self._refrescar_hoy()
        self._refrescar_reloj()
        self.after(15000, self._tick)  # cada 15 segundos


if __name__ == "__main__":
    app = MediRecuerdaApp()
    app.mainloop()
