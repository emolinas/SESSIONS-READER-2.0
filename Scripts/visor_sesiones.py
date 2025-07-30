import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import filedialog, messagebox, Listbox, Menu, Toplevel
import tkinter as tk
import zipfile
import re
import os
import tempfile
import json
import sqlite3
import threading
import time
import logging
import shutil
from datetime import datetime
from pygame import mixer
import pandas as pd
import pyperclip
import numpy as np
from pydub import AudioSegment

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Inicializar mezclador de audio
mixer.init()

class SessionViewerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Visor de Sesiones Avanzado")
        self.root.geometry("1400x900")
        
        # Configuración y estado
        self.config = self.load_config()
        self.temp_dir = tempfile.mkdtemp()
        self.audio_files = []
        self.excel_file = None
        self.df_excel = None
        self.current_audio = None
        self.is_playing = False
        self.canvas_spectrogram = None
        self.audio_segment = None
        self.segment_index = 0
        self.volume = 0.7
        self.playback_speed = 1.0
        self.favorites = set()
        self.markers = {}
        self.audio_duration = 0
        self.audio_position = 0
        self.seek_enabled = True
        
        # Base de datos para notas y metadatos
        self.init_database()
        
        # Crear interfaz
        self.create_menu()
        self.create_widgets()
        self.bind_shortcuts()
        
        # Aplicar tema guardado
        if self.config.get('theme'):
            try:
                self.root.style.theme_use(self.config['theme'])
            except:
                pass

    def load_config(self):
        """Cargar configuración desde archivo JSON"""
        config_file = os.path.join(os.path.expanduser("~"), ".visor_sesiones_config.json")
        default_config = {
            'theme': 'superhero',
            'volume': 0.7,
            'last_directory': '',
            'window_geometry': '1400x900',
            'auto_play_next': False
        }
        
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # Merge con configuración por defecto
                    for key, value in default_config.items():
                        if key not in config:
                            config[key] = value
                    return config
        except Exception as e:
            logger.error(f"Error cargando configuración: {e}")
        
        return default_config
    
    def save_config(self):
        """Guardar configuración a archivo JSON"""
        config_file = os.path.join(os.path.expanduser("~"), ".visor_sesiones_config.json")
        self.config['window_geometry'] = self.root.geometry()
        
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error guardando configuración: {e}")
    
    def init_database(self):
        """Inicializar base de datos SQLite para notas y metadatos"""
        self.db_path = os.path.join(os.path.expanduser("~"), ".visor_sesiones.db")
        
        try:
            self.conn = sqlite3.connect(self.db_path)
            cursor = self.conn.cursor()
            
            # Tabla para notas de usuario
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS session_notes (
                    id TEXT PRIMARY KEY,
                    notes TEXT,
                    tags TEXT,
                    is_favorite INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Tabla para marcadores de tiempo
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS audio_markers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    position_seconds REAL,
                    label TEXT,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            self.conn.commit()
        except Exception as e:
            logger.error(f"Error inicializando base de datos: {e}")
    
    def create_menu(self):
        """Crear menú de la aplicación"""
        menubar = Menu(self.root)
        self.root.config(menu=menubar)
        
        # Menú Archivo
        file_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Archivo", menu=file_menu)
        file_menu.add_command(label="Abrir ZIP", command=self.load_zip, accelerator="Ctrl+O")
        file_menu.add_separator()
        file_menu.add_command(label="Exportar Reporte", command=self.export_report)
        file_menu.add_separator()
        file_menu.add_command(label="Salir", command=self.on_closing, accelerator="Ctrl+Q")
        
        # Menú Reproducción
        play_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Reproducción", menu=play_menu)
        play_menu.add_command(label="Reproducir/Pausar", command=self.toggle_play_pause, accelerator="Space")
        play_menu.add_command(label="Detener", command=self.stop_audio, accelerator="Ctrl+S")
        play_menu.add_separator()
        play_menu.add_command(label="Velocidad 0.5x", command=lambda: self.set_playback_speed(0.5))
        play_menu.add_command(label="Velocidad 1x", command=lambda: self.set_playback_speed(1.0))
        play_menu.add_command(label="Velocidad 1.5x", command=lambda: self.set_playback_speed(1.5))
        play_menu.add_command(label="Velocidad 2x", command=lambda: self.set_playback_speed(2.0))
        
        # Menú Vista
        view_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Vista", menu=view_menu)
        
        # Submenú de temas
        theme_menu = Menu(view_menu, tearoff=0)
        view_menu.add_cascade(label="Tema", menu=theme_menu)
        themes = ['superhero', 'darkly', 'solar', 'cyborg', 'vapor', 'journal', 'sandstone', 'flatly']
        for theme in themes:
            theme_menu.add_command(label=theme.title(), command=lambda t=theme: self.change_theme(t))
        
        view_menu.add_separator()
        view_menu.add_command(label="Estadísticas", command=self.show_statistics)
        
        # Menú Herramientas
        tools_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Herramientas", menu=tools_menu)
        tools_menu.add_command(label="Búsqueda Avanzada", command=self.show_advanced_search)
        tools_menu.add_command(label="Gestionar Favoritos", command=self.show_favorites)
    
    def bind_shortcuts(self):
        """Configurar atajos de teclado"""
        self.root.bind('<Control-o>', lambda e: self.load_zip())
        self.root.bind('<Control-q>', lambda e: self.on_closing())
        self.root.bind('<space>', lambda e: self.toggle_play_pause())
        self.root.bind('<Control-s>', lambda e: self.stop_audio())
        self.root.bind('<Up>', lambda e: self.previous_audio())
        self.root.bind('<Down>', lambda e: self.next_audio())
        self.root.bind('<Left>', lambda e: self.seek_backward())
        self.root.bind('<Right>', lambda e: self.seek_forward())
        self.root.bind('<Control-f>', lambda e: self.show_advanced_search())
    
    def on_closing(self):
        """Manejar cierre de la aplicación"""
        self.save_config()
        if hasattr(self, 'conn'):
            self.conn.close()
        # Limpiar archivos temporales
        try:
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except:
            pass
        self.root.quit()
        self.root.destroy()

    def create_widgets(self):
        """Crear widgets de la interfaz"""
        # Título
        self.label_title = tb.Label(self.root, text="Explorador de Sesiones ZIP", font=("Helvetica", 16, "bold"))
        self.label_title.pack(pady=10)

        # Ruta del archivo
        self.label_path = tb.Label(self.root, text="Ningún archivo abierto", font=("Segoe UI", 9), foreground="gray")
        self.label_path.pack()

        # Botón abrir
        btn_open = tb.Button(self.root, text="📁 Abrir archivo ZIP", command=self.load_zip, bootstyle="primary")
        btn_open.pack(pady=5)

        # Frame principal con paneles
        main_frame = tb.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Panel izquierdo - Lista y filtros
        left_panel = tb.Frame(main_frame)
        left_panel.pack(side="left", fill="both", expand=True)

        # Filtros
        filter_frame = tb.LabelFrame(left_panel, text="Filtros", padding=5)
        filter_frame.pack(fill="x", pady=(0, 5))

        # Búsqueda
        search_frame = tb.Frame(filter_frame)
        search_frame.pack(fill="x", pady=2)
        tb.Label(search_frame, text="Buscar:").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.filter_audio_list)
        search_entry = tb.Entry(search_frame, textvariable=self.search_var)
        search_entry.pack(side="left", fill="x", expand=True, padx=(5, 0))

        # Filtro por favoritos
        self.show_favorites_var = tk.BooleanVar()
        self.show_favorites_var.trace('w', self.filter_audio_list)
        tb.Checkbutton(filter_frame, text="Solo favoritos", variable=self.show_favorites_var).pack(anchor="w")

        # Lista de audios con scrollbar
        listbox_frame = tb.Frame(left_panel)
        listbox_frame.pack(fill="both", expand=True)

        self.listbox = Listbox(listbox_frame, width=50, font=("Segoe UI", 10), 
                              yscrollcommand=lambda f, l: self.scrollbar.set(f, l))
        self.listbox.pack(side="left", fill="both", expand=True)
        self.listbox.bind("<<ListboxSelect>>", self.on_audio_select)
        self.listbox.bind("<Double-1>", lambda e: self.toggle_play_pause())

        self.scrollbar = tb.Scrollbar(listbox_frame, orient="vertical", command=self.listbox.yview)
        self.scrollbar.pack(side="right", fill="y")

        # Panel derecho - Información y controles
        right_panel = tb.Frame(main_frame)
        right_panel.pack(side="right", fill="both", expand=True, padx=(10, 0))

        # Información de la sesión
        self.info_frame = tb.LabelFrame(right_panel, text="Información de la Sesión", padding=10)
        self.info_frame.pack(fill="x", pady=(0, 5))

        self.labels_info = {}
        campos = [
            "Id de sesión", "Día/Hora de creación", "Nombre abonado", 
            "DDR", "Notas", "Transcripción llamada"
        ]
        for campo in campos:
            lbl = tb.Label(self.info_frame, text=f"{campo}: -", anchor="w", font=("Segoe UI", 9))
            lbl.pack(fill="x", pady=1)
            self.labels_info[campo] = lbl

        # Controles de reproducción
        controls_frame = tb.LabelFrame(right_panel, text="Controles de Audio", padding=10)
        controls_frame.pack(fill="x", pady=(0, 5))

        # Botones principales
        btn_frame = tb.Frame(controls_frame)
        btn_frame.pack(fill="x", pady=(0, 5))

        self.btn_play = tb.Button(btn_frame, text="▶", command=self.toggle_play_pause, bootstyle="success", width=8)
        self.btn_play.pack(side="left", padx=2)

        tb.Button(btn_frame, text="■", command=self.stop_audio, bootstyle="danger", width=8).pack(side="left", padx=2)
        tb.Button(btn_frame, text="⏮", command=self.previous_audio, bootstyle="info", width=8).pack(side="left", padx=2)
        tb.Button(btn_frame, text="⏭", command=self.next_audio, bootstyle="info", width=8).pack(side="left", padx=2)

        # Barra de progreso y tiempo
        progress_frame = tb.Frame(controls_frame)
        progress_frame.pack(fill="x", pady=5)

        self.time_label = tb.Label(progress_frame, text="00:00 / 00:00", font=("Segoe UI", 9))
        self.time_label.pack()

        self.progress = tb.Progressbar(progress_frame, orient="horizontal", mode='determinate')
        self.progress.pack(fill="x", pady=2)
        self.progress.bind("<Button-1>", self.on_progress_click)

        # Control de volumen
        volume_frame = tb.Frame(controls_frame)
        volume_frame.pack(fill="x", pady=5)
        tb.Label(volume_frame, text="Volumen:").pack(side="left")
        self.volume_scale = tb.Scale(volume_frame, from_=0, to=100, orient="horizontal", 
                                   command=self.set_volume, length=150)
        self.volume_scale.set(70)
        self.volume_scale.pack(side="left", fill="x", expand=True, padx=(5, 0))

        # Control de velocidad
        speed_frame = tb.Frame(controls_frame)
        speed_frame.pack(fill="x", pady=5)
        tb.Label(speed_frame, text="Velocidad:").pack(side="left")
        self.speed_var = tk.StringVar(value="1.0x")
        self.speed_label = tb.Label(speed_frame, textvariable=self.speed_var)
        self.speed_label.pack(side="left", padx=(5, 0))

        speed_buttons = tb.Frame(speed_frame)
        speed_buttons.pack(side="right")
        for speed in [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]:
            tb.Button(speed_buttons, text=f"{speed}x", 
                     command=lambda s=speed: self.set_playback_speed(s),
                     bootstyle="outline-secondary", width=5).pack(side="left", padx=1)

        # Botones adicionales
        extra_frame = tb.Frame(controls_frame)
        extra_frame.pack(fill="x", pady=5)

        self.btn_favorite = tb.Button(extra_frame, text="⭐", command=self.toggle_favorite, 
                                     bootstyle="warning", width=8)
        self.btn_favorite.pack(side="left", padx=2)

        tb.Button(extra_frame, text="📝", command=self.add_note, bootstyle="info", width=8).pack(side="left", padx=2)
        tb.Button(extra_frame, text="📊", command=self.show_excel, bootstyle="warning", width=8).pack(side="left", padx=2)

        # Estado
        self.label_status = tb.Label(controls_frame, text="Estado: Esperando...", font=("Segoe UI", 9), foreground="gray")
        self.label_status.pack(pady=(5, 0))
        
        # Configurar el protocolo de cierre
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def load_zip(self):
        initial_dir = self.config.get('last_directory', '')
        zip_path = filedialog.askopenfilename(
            initialdir=initial_dir,
            filetypes=[["Archivos ZIP", "*.zip"]]
        )
        if not zip_path:
            return

        # Guardar directorio para próxima vez
        self.config['last_directory'] = os.path.dirname(zip_path)
        
        # Limpiar datos anteriores
        self.audio_files.clear()
        self.listbox.delete(0, "end")
        self.favorites.clear()
        self.markers.clear()
        
        self.label_path.config(text=f"Archivo: {os.path.basename(zip_path)}")
        self.label_status.config(text="Cargando archivos...")

        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(self.temp_dir)

            # Buscar archivos de audio y Excel
            for root_dir, _, files in os.walk(self.temp_dir):
                for f in files:
                    if f.lower().endswith((".mp3", ".wav", ".ogg", ".m4a")):
                        path = os.path.join(root_dir, f)
                        self.audio_files.append(path)
                    elif f.lower().endswith(".xlsx"):
                        self.excel_file = os.path.join(root_dir, f)
                        try:
                            self.df_excel = pd.read_excel(self.excel_file)
                        except Exception as e:
                            logger.error(f"Error leyendo Excel: {e}")
                            self.df_excel = None

            # Procesar DataFrame si existe
            if self.df_excel is not None:
                self.df_excel = self.df_excel.fillna("")
                if 'Día/Hora de creación' in self.df_excel.columns:
                    try:
                        self.df_excel['Día/Hora de creación'] = self.df_excel['Día/Hora de creación'].apply(
                            lambda x: pd.to_datetime(x, errors='coerce') if str(x).strip() != '' else pd.NaT
                        )
                        self.df_excel = self.df_excel.sort_values('Día/Hora de creación', ascending=True)
                    except Exception as e:
                        logger.error(f"Error procesando fechas: {e}")

            # Cargar favoritos desde base de datos
            self.load_favorites()
            
            # Actualizar lista de audios
            self.populate_audio_list()
            
            self.label_status.config(text=f"Cargados {len(self.audio_files)} audios")
            messagebox.showinfo("Listo", f"Cargados {len(self.audio_files)} audios")
            
        except Exception as e:
            logger.error(f"Error cargando ZIP: {e}")
            messagebox.showerror("Error", f"Error cargando archivo ZIP: {e}")

    def populate_audio_list(self):
        """Poblar lista de audios ordenados"""
        self.listbox.delete(0, "end")
        audios_ordenados = []
        
        if self.df_excel is not None and 'Id de sesión' in self.df_excel.columns:
            ids_ordenados = self.df_excel['Id de sesión'].astype(str).tolist()
            for id_sesion in ids_ordenados:
                patron = re.compile(rf'(?<!\d){re.escape(id_sesion)}(?!\d)')
                for audio_path in self.audio_files:
                    nombre_audio = os.path.basename(audio_path)
                    if patron.search(nombre_audio):
                        audios_ordenados.append(audio_path)
                        icon = "⭐" if id_sesion in self.favorites else "🔊"
                        self.listbox.insert("end", f"{icon} {nombre_audio}")
                        break
            
            # Agregar audios no encontrados en Excel
            for audio_path in self.audio_files:
                if audio_path not in audios_ordenados:
                    audios_ordenados.append(audio_path)
                    nombre_audio = os.path.basename(audio_path)
                    self.listbox.insert("end", f"🔊 {nombre_audio}")
        else:
            # Sin Excel, mostrar todos los audios
            for audio_path in self.audio_files:
                nombre_audio = os.path.basename(audio_path)
                self.listbox.insert("end", f"🔊 {nombre_audio}")

        self.audio_files = audios_ordenados if audios_ordenados else self.audio_files

    def filter_audio_list(self, *args):
        """Filtrar lista de audios según búsqueda y favoritos"""
        search_term = self.search_var.get().lower()
        show_only_favorites = self.show_favorites_var.get()
        
        self.listbox.delete(0, "end")
        
        for i, audio_path in enumerate(self.audio_files):
            nombre_audio = os.path.basename(audio_path)
            
            # Obtener ID de sesión para verificar favoritos
            id_sesion = self.get_session_id_from_filename(nombre_audio)
            is_favorite = id_sesion in self.favorites
            
            # Aplicar filtros
            if search_term and search_term not in nombre_audio.lower():
                continue
            if show_only_favorites and not is_favorite:
                continue
                
            icon = "⭐" if is_favorite else "🔊"
            self.listbox.insert("end", f"{icon} {nombre_audio}")

    def get_session_id_from_filename(self, filename):
        """Extraer ID de sesión del nombre del archivo"""
        if self.df_excel is not None and 'Id de sesión' in self.df_excel.columns:
            ids_excel = self.df_excel['Id de sesión'].astype(str).tolist()
            for id_excel in ids_excel:
                patron = re.compile(rf'(?<!\d){re.escape(id_excel)}(?!\d)')
                if patron.search(filename):
                    return id_excel
        return None

    def on_audio_select(self, event):
        if self.df_excel is not None and self.listbox.curselection():
            idx = self.listbox.curselection()[0]
            # Obtener el nombre del archivo sin el icono
            display_text = self.listbox.get(idx)
            nombre_audio = display_text.split(' ', 1)[1] if ' ' in display_text else display_text
            
            id_sesion = self.get_session_id_from_filename(nombre_audio)
            
            if id_sesion:
                fila = self.df_excel[self.df_excel["Id de sesión"].astype(str) == id_sesion]
                if not fila.empty:
                    fila = fila.iloc[0]
                    self.labels_info["Id de sesión"].config(text=f"Id de sesión: {fila.get('Id de sesión', '-')}")
                    
                    # Mostrar fecha legible
                    fecha = fila.get('Día/Hora de creación', '-')
                    if pd.isnull(fecha) or fecha == '' or fecha == pd.NaT:
                        fecha_str = 'Sin fecha'
                    else:
                        fecha_str = str(fecha)
                    
                    self.labels_info["Día/Hora de creación"].config(text=f"Día/Hora de creación: {fecha_str}")
                    self.labels_info["Nombre abonado"].config(text=f"Nombre abonado: {fila.get('Nombre abonado', '-')}")
                    self.labels_info["DDR"].config(text=f"DDR: {fila.get('DDR', '-')}")
                    self.labels_info["Notas"].config(text=f"Notas: {fila.get('Notas', '-')}")
                    self.labels_info["Transcripción llamada"].config(text=f"Transcripción llamada: {fila.get('Transcripción llamada', '-')}")
                    
                    # Actualizar botón de favorito
                    if id_sesion in self.favorites:
                        self.btn_favorite.config(text="⭐", bootstyle="warning")
                    else:
                        self.btn_favorite.config(text="☆", bootstyle="outline-warning")

    def toggle_play_pause(self):
        """Alternar reproducción/pausa"""
        if not self.listbox.curselection():
            return
            
        if self.is_playing:
            self.pause_audio()
        else:
            self.play_audio()

    def play_audio(self):
        """Reproducir audio seleccionado"""
        if not self.listbox.curselection():
            return
            
        idx = self.listbox.curselection()[0]
        if idx < len(self.audio_files):
            audio_path = self.audio_files[idx]
            self.current_audio = audio_path
            
            try:
                # Cargar y reproducir
                mixer.music.load(audio_path)
                mixer.music.set_volume(self.volume)
                mixer.music.play()
                
                self.is_playing = True
                self.btn_play.config(text="⏸")
                self.label_status.config(text="Reproduciendo...")
                
                # Obtener duración del audio
                try:
                    self.audio_segment = AudioSegment.from_mp3(audio_path)
                    self.audio_duration = len(self.audio_segment) / 1000.0  # Convertir a segundos
                except Exception:
                    self.audio_duration = 0
                
                self.progress['maximum'] = self.audio_duration if self.audio_duration > 0 else 100
                self.progress['value'] = 0
                self.audio_position = 0
                
                # Iniciar actualización de progreso
                self.update_progress()
                
            except Exception as e:
                logger.error(f"Error reproduciendo audio: {e}")
                messagebox.showerror("Error", f"Error reproduciendo audio: {e}")

    def pause_audio(self):
        """Pausar/reanudar reproducción"""
        if self.is_playing:
            mixer.music.pause()
            self.is_playing = False
            self.btn_play.config(text="▶")
            self.label_status.config(text="Pausado")
        else:
            mixer.music.unpause()
            self.is_playing = True
            self.btn_play.config(text="⏸")
            self.label_status.config(text="Reproduciendo...")

    def stop_audio(self):
        """Detener reproducción"""
        mixer.music.stop()
        self.is_playing = False
        self.btn_play.config(text="▶")
        self.label_status.config(text="Detenido")
        self.progress['value'] = 0
        self.audio_position = 0
        self.update_time_display()

    def update_progress(self):
        """Actualizar barra de progreso y tiempo"""
        if self.is_playing and mixer.music.get_busy():
            # Estimar posición basada en pygame
            pos_ms = mixer.music.get_pos()
            if pos_ms != -1:
                self.audio_position = pos_ms / 1000.0
                self.progress['value'] = self.audio_position
                self.update_time_display()
            
            # Continuar actualizando
            self.root.after(100, self.update_progress)
        elif not mixer.music.get_busy() and self.is_playing:
            # Audio terminó
            self.stop_audio()
            if self.config.get('auto_play_next', False):
                self.next_audio()

    def update_time_display(self):
        """Actualizar display de tiempo"""
        current_time = self.format_time(self.audio_position)
        total_time = self.format_time(self.audio_duration)
        self.time_label.config(text=f"{current_time} / {total_time}")

    def format_time(self, seconds):
        """Formatear tiempo en MM:SS"""
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes:02d}:{seconds:02d}"

    def on_progress_click(self, event):
        """Manejar clic en barra de progreso para seek"""
        if not self.current_audio or self.audio_duration <= 0:
            return
            
        # Calcular posición basada en clic
        click_x = event.x
        bar_width = self.progress.winfo_width()
        if bar_width <= 0:
            return
            
        percentage = click_x / bar_width
        new_position = percentage * self.audio_duration
        
        # Implementar seek (limitado en pygame, pero podemos intentar)
        self.seek_to_position(new_position)

    def seek_to_position(self, position):
        """Buscar posición específica en el audio"""
        if not self.current_audio:
            return
            
        try:
            # Pygame no soporta seek nativo, pero podemos reiniciar desde posición
            was_playing = self.is_playing
            mixer.music.stop()
            
            if self.audio_segment:
                # Usar pydub para crear segmento desde posición
                start_ms = int(position * 1000)
                segment_from_position = self.audio_segment[start_ms:]
                
                # Guardar segmento temporal
                temp_file = os.path.join(self.temp_dir, "temp_seek.mp3")
                segment_from_position.export(temp_file, format="mp3")
                
                # Cargar y reproducir desde nueva posición
                mixer.music.load(temp_file)
                if was_playing:
                    mixer.music.play()
                    self.is_playing = True
                
                self.audio_position = position
                self.progress['value'] = position
                self.update_time_display()
                
        except Exception as e:
            logger.error(f"Error en seek: {e}")

    def seek_forward(self):
        """Avanzar 10 segundos"""
        new_position = min(self.audio_position + 10, self.audio_duration)
        self.seek_to_position(new_position)

    def seek_backward(self):
        """Retroceder 10 segundos"""
        new_position = max(self.audio_position - 10, 0)
        self.seek_to_position(new_position)

    def next_audio(self):
        """Reproducir siguiente audio"""
        if not self.listbox.curselection():
            return
            
        current_idx = self.listbox.curselection()[0]
        next_idx = (current_idx + 1) % self.listbox.size()
        
        self.listbox.selection_clear(0, 'end')
        self.listbox.selection_set(next_idx)
        self.listbox.activate(next_idx)
        self.listbox.see(next_idx)
        
        # Trigger selection event
        self.on_audio_select(None)
        
        if self.is_playing:
            self.play_audio()

    def previous_audio(self):
        """Reproducir audio anterior"""
        if not self.listbox.curselection():
            return
            
        current_idx = self.listbox.curselection()[0]
        prev_idx = (current_idx - 1) % self.listbox.size()
        
        self.listbox.selection_clear(0, 'end')
        self.listbox.selection_set(prev_idx)
        self.listbox.activate(prev_idx)
        self.listbox.see(prev_idx)
        
        # Trigger selection event
        self.on_audio_select(None)
        
        if self.is_playing:
            self.play_audio()

    def set_volume(self, value):
        """Establecer volumen"""
        self.volume = float(value) / 100.0
        mixer.music.set_volume(self.volume)
        self.config['volume'] = self.volume

    def set_playback_speed(self, speed):
        """Establecer velocidad de reproducción"""
        self.playback_speed = speed
        self.speed_var.set(f"{speed}x")
        
        # Nota: pygame no soporta cambio de velocidad nativo
        # Para implementación completa necesitaríamos usar pydub + pygame
        if self.current_audio and self.audio_segment:
            try:
                # Crear versión con velocidad modificada
                if speed != 1.0:
                    # Cambiar velocidad manteniendo pitch
                    new_sample_rate = int(self.audio_segment.frame_rate * speed)
                    speed_segment = self.audio_segment._spawn(
                        self.audio_segment.raw_data,
                        overrides={"frame_rate": new_sample_rate}
                    ).set_frame_rate(self.audio_segment.frame_rate)
                else:
                    speed_segment = self.audio_segment
                
                # Guardar y reproducir
                temp_file = os.path.join(self.temp_dir, "temp_speed.mp3")
                speed_segment.export(temp_file, format="mp3")
                
                was_playing = self.is_playing
                current_pos = self.audio_position
                
                mixer.music.load(temp_file)
                if was_playing:
                    mixer.music.play()
                
            except Exception as e:
                logger.error(f"Error cambiando velocidad: {e}")

    def toggle_favorite(self):
        """Alternar estado de favorito"""
        if not self.listbox.curselection():
            return
            
        idx = self.listbox.curselection()[0]
        display_text = self.listbox.get(idx)
        nombre_audio = display_text.split(' ', 1)[1] if ' ' in display_text else display_text
        id_sesion = self.get_session_id_from_filename(nombre_audio)
        
        if not id_sesion:
            return
            
        if id_sesion in self.favorites:
            self.favorites.remove(id_sesion)
            self.btn_favorite.config(text="☆", bootstyle="outline-warning")
            self.save_favorite(id_sesion, False)
        else:
            self.favorites.add(id_sesion)
            self.btn_favorite.config(text="⭐", bootstyle="warning")
            self.save_favorite(id_sesion, True)
        
        # Actualizar display en lista
        icon = "⭐" if id_sesion in self.favorites else "🔊"
        self.listbox.delete(idx)
        self.listbox.insert(idx, f"{icon} {nombre_audio}")
        self.listbox.selection_set(idx)

    def save_favorite(self, session_id, is_favorite):
        """Guardar estado de favorito en base de datos"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO session_notes 
                (id, is_favorite, modified_at) 
                VALUES (?, ?, ?)
            ''', (session_id, 1 if is_favorite else 0, datetime.now()))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Error guardando favorito: {e}")

    def load_favorites(self):
        """Cargar favoritos desde base de datos"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT id FROM session_notes WHERE is_favorite = 1')
            self.favorites = {row[0] for row in cursor.fetchall()}
        except Exception as e:
            logger.error(f"Error cargando favoritos: {e}")

    def add_note(self):
        """Agregar nota a la sesión actual"""
        if not self.listbox.curselection():
            messagebox.showwarning("Advertencia", "Selecciona un audio primero")
            return
            
        idx = self.listbox.curselection()[0]
        display_text = self.listbox.get(idx)
        nombre_audio = display_text.split(' ', 1)[1] if ' ' in display_text else display_text
        id_sesion = self.get_session_id_from_filename(nombre_audio)
        
        if not id_sesion:
            messagebox.showwarning("Advertencia", "No se pudo identificar el ID de sesión")
            return
        
        # Ventana para agregar nota
        note_window = Toplevel(self.root)
        note_window.title("Agregar Nota")
        note_window.geometry("500x400")
        note_window.transient(self.root)
        note_window.grab_set()
        
        # Cargar nota existente
        existing_note = self.get_session_note(id_sesion)
        
        tb.Label(note_window, text=f"Nota para sesión: {id_sesion}", font=("Segoe UI", 12, "bold")).pack(pady=10)
        
        # Área de texto
        text_frame = tb.Frame(note_window)
        text_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        text_area = tb.Text(text_frame, wrap="word", font=("Segoe UI", 10))
        text_area.pack(fill="both", expand=True)
        
        scrollbar_note = tb.Scrollbar(text_frame, orient="vertical", command=text_area.yview)
        scrollbar_note.pack(side="right", fill="y")
        text_area.config(yscrollcommand=scrollbar_note.set)
        
        if existing_note:
            text_area.insert("1.0", existing_note)
        
        # Botones
        btn_frame = tb.Frame(note_window)
        btn_frame.pack(fill="x", padx=10, pady=10)
        
        def save_note():
            note_text = text_area.get("1.0", "end-1c")
            self.save_session_note(id_sesion, note_text)
            note_window.destroy()
            messagebox.showinfo("Guardado", "Nota guardada correctamente")
        
        tb.Button(btn_frame, text="Guardar", command=save_note, bootstyle="success").pack(side="right", padx=5)
        tb.Button(btn_frame, text="Cancelar", command=note_window.destroy, bootstyle="secondary").pack(side="right")

    def get_session_note(self, session_id):
        """Obtener nota de sesión desde base de datos"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT notes FROM session_notes WHERE id = ?', (session_id,))
            result = cursor.fetchone()
            return result[0] if result else ""
        except Exception as e:
            logger.error(f"Error obteniendo nota: {e}")
            return ""

    def save_session_note(self, session_id, note_text):
        """Guardar nota de sesión en base de datos"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO session_notes 
                (id, notes, modified_at) 
                VALUES (?, ?, ?)
            ''', (session_id, note_text, datetime.now()))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Error guardando nota: {e}")

    def change_theme(self, theme_name):
        """Cambiar tema de la aplicación"""
        try:
            self.root.style.theme_use(theme_name)
            self.config['theme'] = theme_name
            self.save_config()
        except Exception as e:
            logger.error(f"Error cambiando tema: {e}")
            messagebox.showerror("Error", f"No se pudo cambiar el tema: {e}")

    def show_advanced_search(self):
        """Mostrar ventana de búsqueda avanzada"""
        search_window = Toplevel(self.root)
        search_window.title("Búsqueda Avanzada")
        search_window.geometry("600x400")
        search_window.transient(self.root)
        
        # Campos de búsqueda
        tb.Label(search_window, text="Búsqueda Avanzada", font=("Segoe UI", 14, "bold")).pack(pady=10)
        
        fields_frame = tb.LabelFrame(search_window, text="Criterios de Búsqueda", padding=10)
        fields_frame.pack(fill="x", padx=10, pady=5)
        
        # Variables de búsqueda
        search_vars = {}
        
        fields = [
            ("Nombre de archivo", "filename"),
            ("ID de sesión", "session_id"),
            ("Nombre abonado", "subscriber"),
            ("DDR", "ddr"),
            ("Transcripción", "transcription")
        ]
        
        for i, (label, key) in enumerate(fields):
            tb.Label(fields_frame, text=f"{label}:").grid(row=i, column=0, sticky="w", pady=2)
            var = tk.StringVar()
            search_vars[key] = var
            tb.Entry(fields_frame, textvariable=var, width=40).grid(row=i, column=1, sticky="ew", padx=(5, 0), pady=2)
        
        fields_frame.columnconfigure(1, weight=1)
        
        # Filtros adicionales
        filters_frame = tb.LabelFrame(search_window, text="Filtros", padding=10)
        filters_frame.pack(fill="x", padx=10, pady=5)
        
        date_frame = tb.Frame(filters_frame)
        date_frame.pack(fill="x", pady=2)
        
        tb.Label(date_frame, text="Fecha desde:").pack(side="left")
        date_from_var = tk.StringVar()
        tb.Entry(date_frame, textvariable=date_from_var, width=12).pack(side="left", padx=5)
        
        tb.Label(date_frame, text="hasta:").pack(side="left", padx=(10, 0))
        date_to_var = tk.StringVar()
        tb.Entry(date_frame, textvariable=date_to_var, width=12).pack(side="left", padx=5)
        
        favorites_only_var = tk.BooleanVar()
        tb.Checkbutton(filters_frame, text="Solo favoritos", variable=favorites_only_var).pack(anchor="w", pady=5)
        
        # Botones
        btn_frame = tb.Frame(search_window)
        btn_frame.pack(fill="x", padx=10, pady=10)
        
        def perform_search():
            # Implementar lógica de búsqueda avanzada
            results = self.advanced_search(search_vars, date_from_var.get(), date_to_var.get(), favorites_only_var.get())
            self.show_search_results(results)
            search_window.destroy()
        
        tb.Button(btn_frame, text="Buscar", command=perform_search, bootstyle="primary").pack(side="right", padx=5)
        tb.Button(btn_frame, text="Cancelar", command=search_window.destroy, bootstyle="secondary").pack(side="right")

    def advanced_search(self, search_vars, date_from, date_to, favorites_only):
        """Realizar búsqueda avanzada"""
        results = []
        
        for i, audio_path in enumerate(self.audio_files):
            filename = os.path.basename(audio_path)
            id_sesion = self.get_session_id_from_filename(filename)
            
            # Obtener datos del Excel si existe
            session_data = {}
            if self.df_excel is not None and id_sesion:
                fila = self.df_excel[self.df_excel["Id de sesión"].astype(str) == id_sesion]
                if not fila.empty:
                    session_data = fila.iloc[0].to_dict()
            
            # Aplicar filtros
            match = True
            
            # Filtro por nombre de archivo
            if search_vars["filename"].get() and search_vars["filename"].get().lower() not in filename.lower():
                match = False
            
            # Filtro por ID de sesión
            if search_vars["session_id"].get() and search_vars["session_id"].get() not in str(id_sesion or ""):
                match = False
            
            # Filtro por favoritos
            if favorites_only and id_sesion not in self.favorites:
                match = False
            
            # Filtros por datos del Excel
            if search_vars["subscriber"].get():
                subscriber = str(session_data.get("Nombre abonado", "")).lower()
                if search_vars["subscriber"].get().lower() not in subscriber:
                    match = False
            
            if search_vars["ddr"].get():
                ddr = str(session_data.get("DDR", "")).lower()
                if search_vars["ddr"].get().lower() not in ddr:
                    match = False
            
            if search_vars["transcription"].get():
                transcription = str(session_data.get("Transcripción llamada", "")).lower()
                if search_vars["transcription"].get().lower() not in transcription:
                    match = False
            
            if match:
                results.append({
                    'index': i,
                    'filename': filename,
                    'session_id': id_sesion,
                    'data': session_data
                })
        
        return results

    def show_search_results(self, results):
        """Mostrar resultados de búsqueda"""
        if not results:
            messagebox.showinfo("Búsqueda", "No se encontraron resultados")
            return
        
        results_window = Toplevel(self.root)
        results_window.title(f"Resultados de Búsqueda ({len(results)} encontrados)")
        results_window.geometry("800x500")
        
        # Lista de resultados
        list_frame = tb.Frame(results_window)
        list_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        results_listbox = Listbox(list_frame, font=("Segoe UI", 10))
        results_listbox.pack(side="left", fill="both", expand=True)
        
        scrollbar_results = tb.Scrollbar(list_frame, orient="vertical", command=results_listbox.yview)
        scrollbar_results.pack(side="right", fill="y")
        results_listbox.config(yscrollcommand=scrollbar_results.set)
        
        # Poblar resultados
        for result in results:
            session_id = result['session_id'] or "Sin ID"
            filename = result['filename']
            icon = "⭐" if result['session_id'] in self.favorites else "🔊"
            results_listbox.insert("end", f"{icon} {session_id} - {filename}")
        
        def select_result():
            selection = results_listbox.curselection()
            if selection:
                result = results[selection[0]]
                # Seleccionar en lista principal
                self.listbox.selection_clear(0, 'end')
                self.listbox.selection_set(result['index'])
                self.listbox.activate(result['index'])
                self.listbox.see(result['index'])
                self.on_audio_select(None)
                results_window.destroy()
        
        btn_frame = tb.Frame(results_window)
        btn_frame.pack(fill="x", padx=10, pady=5)
        
        tb.Button(btn_frame, text="Seleccionar", command=select_result, bootstyle="primary").pack(side="right", padx=5)
        tb.Button(btn_frame, text="Cerrar", command=results_window.destroy, bootstyle="secondary").pack(side="right")
        
        results_listbox.bind("<Double-1>", lambda e: select_result())

    def show_favorites(self):
        """Mostrar ventana de gestión de favoritos"""
        fav_window = Toplevel(self.root)
        fav_window.title("Gestión de Favoritos")
        fav_window.geometry("600x400")
        
        tb.Label(fav_window, text="Sesiones Favoritas", font=("Segoe UI", 14, "bold")).pack(pady=10)
        
        # Lista de favoritos
        list_frame = tb.Frame(fav_window)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        fav_listbox = Listbox(list_frame, font=("Segoe UI", 10))
        fav_listbox.pack(side="left", fill="both", expand=True)
        
        scrollbar_fav = tb.Scrollbar(list_frame, orient="vertical", command=fav_listbox.yview)
        scrollbar_fav.pack(side="right", fill="y")
        fav_listbox.config(yscrollcommand=scrollbar_fav.set)
        
        # Poblar favoritos
        for session_id in self.favorites:
            # Buscar información adicional
            filename = "No encontrado"
            for audio_path in self.audio_files:
                if self.get_session_id_from_filename(os.path.basename(audio_path)) == session_id:
                    filename = os.path.basename(audio_path)
                    break
            
            fav_listbox.insert("end", f"⭐ {session_id} - {filename}")
        
        # Botones
        btn_frame = tb.Frame(fav_window)
        btn_frame.pack(fill="x", padx=10, pady=10)
        
        def remove_favorite():
            selection = fav_listbox.curselection()
            if selection:
                session_id = list(self.favorites)[selection[0]]
                self.favorites.remove(session_id)
                self.save_favorite(session_id, False)
                fav_listbox.delete(selection[0])
                self.populate_audio_list()  # Actualizar lista principal
        
        tb.Button(btn_frame, text="Quitar Favorito", command=remove_favorite, bootstyle="danger").pack(side="right", padx=5)
        tb.Button(btn_frame, text="Cerrar", command=fav_window.destroy, bootstyle="secondary").pack(side="right")

    def show_statistics(self):
        """Mostrar estadísticas del conjunto de datos"""
        if not self.audio_files:
            messagebox.showwarning("Advertencia", "No hay audios cargados")
            return
        
        stats_window = Toplevel(self.root)
        stats_window.title("Estadísticas")
        stats_window.geometry("700x500")
        
        tb.Label(stats_window, text="Estadísticas de Sesiones", font=("Segoe UI", 14, "bold")).pack(pady=10)
        
        # Calcular estadísticas
        total_audios = len(self.audio_files)
        total_favorites = len(self.favorites)
        
        # Estadísticas de duración
        total_duration = 0
        duration_list = []
        
        for audio_path in self.audio_files:
            try:
                segment = AudioSegment.from_mp3(audio_path)
                duration = len(segment) / 1000.0  # en segundos
                total_duration += duration
                duration_list.append(duration)
            except:
                continue
        
        avg_duration = total_duration / len(duration_list) if duration_list else 0
        
        # Estadísticas por fecha si hay Excel
        date_stats = {}
        if self.df_excel is not None and 'Día/Hora de creación' in self.df_excel.columns:
            for _, row in self.df_excel.iterrows():
                fecha = row.get('Día/Hora de creación')
                if pd.notna(fecha):
                    date_key = fecha.strftime('%Y-%m-%d') if hasattr(fecha, 'strftime') else str(fecha)[:10]
                    date_stats[date_key] = date_stats.get(date_key, 0) + 1
        
        # Mostrar estadísticas
        stats_frame = tb.LabelFrame(stats_window, text="Resumen General", padding=10)
        stats_frame.pack(fill="x", padx=10, pady=5)
        
        stats_text = f"""
Total de audios: {total_audios}
Favoritos: {total_favorites}
Duración total: {self.format_time(total_duration)}
Duración promedio: {self.format_time(avg_duration)}
        """
        
        tb.Label(stats_frame, text=stats_text, font=("Segoe UI", 10), justify="left").pack(anchor="w")
        
        # Mostrar distribución por fecha en texto
        if date_stats:
            date_frame = tb.LabelFrame(stats_window, text="Distribución por Fecha", padding=10)
            date_frame.pack(fill="x", padx=10, pady=5)
            
            date_text = "Sesiones por fecha:\n\n"
            for date, count in sorted(date_stats.items()):
                date_text += f"{date}: {count} sesiones\n"
            
            tb.Label(date_frame, text=date_text, font=("Segoe UI", 10), justify="left").pack(anchor="w")

    def export_report(self):
        """Exportar reporte en PDF o Excel"""
        if not self.audio_files:
            messagebox.showwarning("Advertencia", "No hay datos para exportar")
            return
        
        export_window = Toplevel(self.root)
        export_window.title("Exportar Reporte")
        export_window.geometry("400x300")
        export_window.transient(self.root)
        export_window.grab_set()
        
        tb.Label(export_window, text="Exportar Reporte", font=("Segoe UI", 14, "bold")).pack(pady=20)
        
        # Opciones de exportación
        options_frame = tb.LabelFrame(export_window, text="Opciones", padding=10)
        options_frame.pack(fill="x", padx=20, pady=10)
        
        export_type = tk.StringVar(value="excel")
        tb.Radiobutton(options_frame, text="Excel (.xlsx)", variable=export_type, value="excel").pack(anchor="w")
        tb.Radiobutton(options_frame, text="CSV (.csv)", variable=export_type, value="csv").pack(anchor="w")
        
        include_favorites = tk.BooleanVar(value=True)
        tb.Checkbutton(options_frame, text="Incluir favoritos", variable=include_favorites).pack(anchor="w", pady=5)
        
        include_stats = tk.BooleanVar(value=True)
        tb.Checkbutton(options_frame, text="Incluir estadísticas", variable=include_stats).pack(anchor="w")
        
        def do_export():
            try:
                file_ext = ".xlsx" if export_type.get() == "excel" else ".csv"
                file_path = filedialog.asksaveasfilename(
                    defaultextension=file_ext,
                    filetypes=[("Excel files", "*.xlsx"), ("CSV files", "*.csv")] if export_type.get() == "excel" 
                             else [("CSV files", "*.csv"), ("Excel files", "*.xlsx")]
                )
                
                if not file_path:
                    return
                
                # Preparar datos
                export_data = []
                
                for i, audio_path in enumerate(self.audio_files):
                    filename = os.path.basename(audio_path)
                    id_sesion = self.get_session_id_from_filename(filename)
                    is_favorite = id_sesion in self.favorites if id_sesion else False
                    
                    row = {
                        'Archivo': filename,
                        'ID Sesión': id_sesion or 'N/A',
                        'Favorito': 'Sí' if is_favorite else 'No',
                        'Ruta': audio_path
                    }
                    
                    # Agregar datos del Excel si existen
                    if self.df_excel is not None and id_sesion:
                        fila = self.df_excel[self.df_excel["Id de sesión"].astype(str) == id_sesion]
                        if not fila.empty:
                            session_data = fila.iloc[0]
                            row.update({
                                'Fecha/Hora': session_data.get('Día/Hora de creación', ''),
                                'Nombre Abonado': session_data.get('Nombre abonado', ''),
                                'DDR': session_data.get('DDR', ''),
                                'Notas Excel': session_data.get('Notas', ''),
                                'Transcripción': session_data.get('Transcripción llamada', '')
                            })
                    
                    # Agregar nota del usuario si existe
                    if id_sesion:
                        user_note = self.get_session_note(id_sesion)
                        if user_note:
                            row['Nota Usuario'] = user_note
                    
                    export_data.append(row)
                
                # Crear DataFrame
                df_export = pd.DataFrame(export_data)
                
                # Exportar
                if export_type.get() == "excel":
                    with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                        df_export.to_excel(writer, sheet_name='Sesiones', index=False)
                        
                        # Agregar hoja de estadísticas si se solicita
                        if include_stats.get():
                            stats_data = {
                                'Métrica': ['Total Audios', 'Favoritos', 'Con Excel', 'Con Notas'],
                                'Valor': [
                                    len(self.audio_files),
                                    len(self.favorites),
                                    len([f for f in self.audio_files if self.get_session_id_from_filename(os.path.basename(f))]),
                                    len([s for s in self.favorites if self.get_session_note(s)])
                                ]
                            }
                            pd.DataFrame(stats_data).to_excel(writer, sheet_name='Estadísticas', index=False)
                else:
                    df_export.to_csv(file_path, index=False, encoding='utf-8-sig')
                
                export_window.destroy()
                messagebox.showinfo("Éxito", f"Reporte exportado a:\n{file_path}")
                
            except Exception as e:
                logger.error(f"Error exportando: {e}")
                messagebox.showerror("Error", f"Error exportando reporte: {e}")
        
        # Botones
        btn_frame = tb.Frame(export_window)
        btn_frame.pack(fill="x", padx=20, pady=20)
        
        tb.Button(btn_frame, text="Exportar", command=do_export, bootstyle="success").pack(side="right", padx=5)
        tb.Button(btn_frame, text="Cancelar", command=export_window.destroy, bootstyle="secondary").pack(side="right")

    def show_excel(self):
        """Mostrar vista previa del archivo Excel"""
        if self.df_excel is None:
            messagebox.showerror("Error", "No se ha cargado ningún archivo Excel.")
            return
        
        columnas_deseadas = {
            "id de sesión": "Id de sesión",
            "día/hora de creación": "Día/Hora de creación",
            "nombre abonado": "Nombre abonado",
            "ddr": "DDR",
            "notas": "Notas",
            "transcripción llamada": "Transcripción llamada"
        }

        columnas_actuales = {col.lower().strip(): col for col in self.df_excel.columns}
        columnas_encontradas = {}

        for clave, nombre_bonito in columnas_deseadas.items():
            if clave in columnas_actuales:
                columnas_encontradas[nombre_bonito] = columnas_actuales[clave]

        ventana = Toplevel(self.root)
        ventana.title("Vista previa de Excel")
        ventana.geometry("1000x700")

        # Frame principal con notebook
        notebook = tb.Notebook(ventana)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Pestaña de datos
        data_frame = tb.Frame(notebook)
        notebook.add(data_frame, text="Datos")
        
        # Botón para copiar al portapapeles
        btn_frame = tb.Frame(data_frame)
        btn_frame.pack(fill="x", pady=5)
        
        def copiar_texto():
            texto = text_area.get("1.0", "end-1c")
            pyperclip.copy(texto)
            messagebox.showinfo("Copiado", "Texto copiado al portapapeles.")

        tb.Button(btn_frame, text="📋 Copiar al portapapeles", command=copiar_texto, bootstyle="info").pack(side="right", padx=5)

        # Área de texto con scrollbar
        text_frame = tb.Frame(data_frame)
        text_frame.pack(fill="both", expand=True)

        scrollbar = tb.Scrollbar(text_frame)
        scrollbar.pack(side="right", fill="y")

        text_area = tb.Text(text_frame, wrap="word", font=("Consolas", 9), 
                           yscrollcommand=scrollbar.set, bg="#f8f8f8")
        text_area.pack(fill="both", expand=True)
        scrollbar.config(command=text_area.yview)

        # Mostrar datos
        if len(columnas_encontradas) < len(columnas_deseadas):
            texto = "⚠️ No se encontraron algunas columnas esperadas en el archivo Excel.\n\n"
            texto += f"Columnas encontradas: {', '.join(columnas_actuales.values())}\n\n"
            texto += "Datos disponibles:\n" + "="*50 + "\n"
            try:
                texto += self.df_excel.to_string(index=False)
            except Exception as e:
                texto += f"Error mostrando datos: {e}"
        else:
            try:
                texto = self.df_excel[list(columnas_encontradas.values())].to_string(index=False)
            except Exception as e:
                texto = f"Error al mostrar el Excel: {e}"

        text_area.insert("end", texto)
        
        # Pestaña de estadísticas
        stats_frame = tb.Frame(notebook)
        notebook.add(stats_frame, text="Estadísticas")
        
        stats_text = tb.Text(stats_frame, wrap="word", font=("Consolas", 10), bg="#f8f8f8")
        stats_text.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Generar estadísticas del Excel
        stats_info = f"Estadísticas del archivo Excel:\n{'='*40}\n\n"
        stats_info += f"Total de registros: {len(self.df_excel)}\n"
        stats_info += f"Columnas disponibles: {len(self.df_excel.columns)}\n\n"
        
        # Estadísticas por columna
        for col in self.df_excel.columns:
            non_null = self.df_excel[col].notna().sum()
            null_count = len(self.df_excel) - non_null
            stats_info += f"{col}:\n"
            stats_info += f"  - Registros con datos: {non_null}\n"
            stats_info += f"  - Registros vacíos: {null_count}\n"
            
            if self.df_excel[col].dtype in ['object']:
                unique_count = self.df_excel[col].nunique()
                stats_info += f"  - Valores únicos: {unique_count}\n"
            
            stats_info += "\n"
        
        stats_text.insert("end", stats_info)

if __name__ == '__main__':
    root = tb.Window(themename="superhero")
    app = SessionViewerApp(root)
    root.mainloop()
