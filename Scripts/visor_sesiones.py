import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import filedialog, messagebox, Listbox, Menu, Toplevel, Canvas
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
import os
# Configurar la ruta de ffmpeg para pydub (usar Scripts/ffmpeg.exe si existe)
ffmpeg_path = os.path.join(os.path.dirname(__file__), "ffmpeg.exe")
if os.path.isfile(ffmpeg_path):
    AudioSegment.converter = ffmpeg_path
else:
    from pydub.utils import which
    ffmpeg_path = which("ffmpeg")
    if ffmpeg_path:
        AudioSegment.converter = ffmpeg_path
    else:
        import warnings
        warnings.warn("No se encontró ffmpeg. Coloque ffmpeg.exe en la carpeta Scripts o agréguelo al PATH. Algunas funciones de audio pueden no funcionar.")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib import style
import matplotlib.style as mstyle
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
import seaborn as sns
import numpy as np

# Configurar estilo moderno para gráficos
plt.style.use('dark_background')
sns.set_palette("husl")

# Importaciones opcionales para audio avanzado
try:
    import librosa
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False
    librosa = None

try:
    import soundfile as sf
    SOUNDFILE_AVAILABLE = True
except ImportError:
    SOUNDFILE_AVAILABLE = False

# Suprimir warnings específicos para una experiencia más limpia
import warnings
warnings.filterwarnings('ignore', category=RuntimeWarning, message='.*ffmpeg.*')
warnings.filterwarnings('ignore', category=RuntimeWarning, message='.*avconv.*')
warnings.filterwarnings('ignore', category=RuntimeWarning, message='.*ffprobe.*')
warnings.filterwarnings('ignore', category=RuntimeWarning, message='.*avprobe.*')

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Log de estado de importaciones opcionales
if not LIBROSA_AVAILABLE:
    logger.info("Librosa no disponible - usando fallback con pydub+scipy")
if not SOUNDFILE_AVAILABLE:
    logger.info("Soundfile no disponible - usando fallback con pydub")

# Inicializar mezclador de audio
mixer.init()

class ToolTip:
    """Clase simple para mostrar tooltips en widgets"""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        self.tooltip = None

    def enter(self, event=None):
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        
        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")
        
        label = tk.Label(self.tooltip, text=self.text, 
                        background="lightyellow", 
                        font=("Segoe UI", 9),
                        relief="solid", borderwidth=1)
        label.pack()

    def leave(self, event=None):
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None

class LoadingDialog:
    """Ventana de progreso para operaciones de carga"""
    def __init__(self, parent, title="Procesando...", max_value=100):
        self.parent = parent
        self.window = Toplevel(parent)
        self.window.title(title)
        self.window.geometry("500x200")
        self.window.transient(parent)
        self.window.grab_set()
        
        # Centrar ventana
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() // 2) - (500 // 2)
        y = (self.window.winfo_screenheight() // 2) - (200 // 2)
        self.window.geometry(f"500x200+{x}+{y}")
        
        # Deshabilitar redimensionamiento
        self.window.resizable(False, False)
        
        # Variables de control
        self.max_value = max_value
        self.current_value = 0
        self.cancelled = False
        
        self.create_widgets()
        
    def create_widgets(self):
        """Crear widgets de la ventana de progreso"""
        main_frame = tb.Frame(self.window)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Icono y título
        header_frame = tb.Frame(main_frame)
        header_frame.pack(fill="x", pady=(0, 20))
        
        # Icono animado (spinner)
        self.icon_label = tb.Label(header_frame, text="⏳", font=("Segoe UI", 24))
        self.icon_label.pack(pady=(0, 5))
        
        # Título principal
        self.title_label = tb.Label(header_frame, text="Procesando archivos...", 
                                   font=("Segoe UI", 14, "bold"))
        self.title_label.pack()
        
        # Mensaje de estado
        self.status_label = tb.Label(main_frame, text="Iniciando proceso...", 
                                    font=("Segoe UI", 10), foreground="gray")
        self.status_label.pack(pady=(0, 10))
        
        # Barra de progreso
        progress_frame = tb.Frame(main_frame)
        progress_frame.pack(fill="x", pady=(0, 10))
        
        self.progress_bar = tb.Progressbar(progress_frame, mode='determinate', 
                                          length=400, bootstyle="success-striped")
        self.progress_bar.pack(pady=5)
        
        # Etiqueta de progreso detallado
        progress_info_frame = tb.Frame(progress_frame)
        progress_info_frame.pack(fill="x", pady=5)
        
        self.progress_label = tb.Label(progress_info_frame, text="0%", 
                                      font=("Segoe UI", 9), foreground="cyan")
        self.progress_label.pack(side="left")
        
        self.files_label = tb.Label(progress_info_frame, text="0 / 0 archivos", 
                                   font=("Segoe UI", 9), foreground="gray")
        self.files_label.pack(side="right")
        
        # Botón cancelar (opcional)
        self.cancel_btn = tb.Button(main_frame, text="Cancelar", 
                                   command=self.cancel, bootstyle="outline-danger")
        self.cancel_btn.pack(pady=(10, 0))
        
        # Iniciar animación del icono
        self.animate_icon()
        
    def animate_icon(self):
        """Animar el icono de carga"""
        icons = ["⏳", "⏳", "⏳", "⌛", "⌛", "⌛"]
        current_icon = self.icon_label.cget("text")
        
        try:
            current_index = icons.index(current_icon)
            next_index = (current_index + 1) % len(icons)
        except ValueError:
            next_index = 0
        
        self.icon_label.config(text=icons[next_index])
        
        if not self.cancelled:
            self.window.after(500, self.animate_icon)
    
    def update_progress(self, value, status_text="", files_processed=None, total_files=None):
        """Actualizar progreso de la operación"""
        self.current_value = min(value, self.max_value)
        
        # Actualizar barra de progreso
        self.progress_bar['value'] = (self.current_value / self.max_value) * 100
        
        # Actualizar porcentaje
        percentage = int((self.current_value / self.max_value) * 100)
        self.progress_label.config(text=f"{percentage}%")
        
        # Actualizar texto de estado
        if status_text:
            self.status_label.config(text=status_text)
        
        # Actualizar contador de archivos
        if files_processed is not None and total_files is not None:
            self.files_label.config(text=f"{files_processed} / {total_files} archivos")
        
        # Actualizar ventana
        self.window.update_idletasks()
        
    def update_status(self, status_text):
        """Actualizar solo el texto de estado"""
        self.status_label.config(text=status_text)
        self.window.update_idletasks()
        
    def set_indeterminate(self, enable=True):
        """Cambiar a modo indeterminado (para operaciones sin progreso conocido)"""
        if enable:
            self.progress_bar.config(mode='indeterminate')
            self.progress_bar.start()
            self.progress_label.config(text="")
            self.files_label.config(text="")
        else:
            self.progress_bar.stop()
            self.progress_bar.config(mode='determinate')
    
    def cancel(self):
        """Cancelar operación"""
        self.cancelled = True
        self.close()
        
    def close(self):
        """Cerrar ventana de progreso"""
        try:
            self.window.grab_release()
            self.window.destroy()
        except:
            pass
    
    def is_cancelled(self):
        """Verificar si la operación fue cancelada"""
        return self.cancelled

class ProgressManager:
    """Gestor de ventanas de progreso para diferentes operaciones"""
    def __init__(self, parent):
        self.parent = parent
        self.current_dialog = None
    
    def show_zip_loading(self, zip_count=1):
        """Mostrar progreso para carga de ZIP"""
        title = f"Cargando {'archivo' if zip_count == 1 else 'archivos'} ZIP"
        self.current_dialog = LoadingDialog(self.parent, title, max_value=100)
        return self.current_dialog
    
    def show_excel_loading(self):
        """Mostrar progreso para carga de Excel"""
        self.current_dialog = LoadingDialog(self.parent, "Procesando Excel", max_value=100)
        return self.current_dialog
    
    def show_statistics_loading(self):
        """Mostrar progreso para cálculo de estadísticas"""
        self.current_dialog = LoadingDialog(self.parent, "📊 Calculando Estadísticas Avanzadas", max_value=100)
        self.current_dialog.title_label.config(text="Analizando datos del dataset...")
        self.current_dialog.status_label.config(text="Preparando análisis comprehensivo de sesiones de audio")
        return self.current_dialog
    
    def close_current(self):
        """Cerrar diálogo actual si existe"""
        if self.current_dialog:
            self.current_dialog.close()
            self.current_dialog = None

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
        self.audio_duration = 0.0
        self.audio_position = 0.0
        self.seek_enabled = True
        
        # Nuevas variables para waveform y marcadores
        self.waveform_data = None
        self.waveform_canvas = None
        self.waveform_figure = None
        self.waveform_ax = None
        self.current_markers = []
        self.marker_lines = []
        self.show_waveform = True
        
        # Gestor de progreso
        self.progress_manager = ProgressManager(self.root)
        
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
        file_menu.add_command(label="Cargar múltiples ZIPs", command=self.load_multiple_zips, accelerator="Ctrl+Shift+O")
        file_menu.add_command(label="Agregar más ZIPs", command=self.add_more_zips, accelerator="Ctrl+Alt+O")
        file_menu.add_separator()
        file_menu.add_command(label="Cargar Excel externo", command=self.load_external_excel, accelerator="Ctrl+E")
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
        view_menu.add_command(label="Mostrar/Ocultar Waveform", command=self.toggle_waveform, accelerator="Ctrl+W")
        
        # Menú Marcadores
        markers_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Marcadores", menu=markers_menu)
        markers_menu.add_command(label="Agregar Marcador", command=self.add_marker, accelerator="Ctrl+M")
        markers_menu.add_command(label="Gestionar Marcadores", command=self.show_markers_window)
        markers_menu.add_separator()
        markers_menu.add_command(label="Ir al Siguiente", command=self.next_marker, accelerator="Ctrl+→")
        markers_menu.add_command(label="Ir al Anterior", command=self.previous_marker, accelerator="Ctrl+←")
        
        # Menú Herramientas
        tools_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Herramientas", menu=tools_menu)
        tools_menu.add_command(label="Estadísticas", command=self.show_statistics)
        tools_menu.add_separator()
        tools_menu.add_command(label="Búsqueda Avanzada", command=self.show_advanced_search)
        tools_menu.add_command(label="Gestionar Favoritos", command=self.show_favorites)
    
    def bind_shortcuts(self):
        """Configurar atajos de teclado"""
        self.root.bind('<Control-o>', lambda e: self.load_zip())
        self.root.bind('<Control-Shift-O>', lambda e: self.load_multiple_zips())
        self.root.bind('<Control-Alt-o>', lambda e: self.add_more_zips())
        self.root.bind('<Control-e>', lambda e: self.load_external_excel())
        self.root.bind('<Control-q>', lambda e: self.on_closing())
        self.root.bind('<space>', lambda e: self.toggle_play_pause())
        self.root.bind('<Control-s>', lambda e: self.stop_audio())
        self.root.bind('<Up>', lambda e: self.previous_audio())
        self.root.bind('<Down>', lambda e: self.next_audio())
        self.root.bind('<Left>', lambda e: self.seek_backward())
        self.root.bind('<Right>', lambda e: self.seek_forward())
        self.root.bind('<Control-f>', lambda e: self.show_advanced_search())
        self.root.bind('<Control-m>', lambda e: self.add_marker())
        self.root.bind('<Control-Right>', lambda e: self.next_marker())
        self.root.bind('<Control-Left>', lambda e: self.previous_marker())
        self.root.bind('<Control-w>', lambda e: self.toggle_waveform())
    
    def on_closing(self):
        """Manejar cierre de la aplicación"""
        self.save_config()
        self.cleanup_matplotlib_figures()  # Limpiar figuras antes de cerrar
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
        ToolTip(self.btn_play, "Reproducir/Pausar (Espacio)")

        btn_stop = tb.Button(btn_frame, text="■", command=self.stop_audio, bootstyle="danger", width=8)
        btn_stop.pack(side="left", padx=2)
        ToolTip(btn_stop, "Detener reproducción (Ctrl+S)")
        
        # Botones de salto rápido
        btn_back15 = tb.Button(btn_frame, text="⏪15s", command=self.seek_backward_15, bootstyle="outline-info", width=8)
        btn_back15.pack(side="left", padx=2)
        ToolTip(btn_back15, "Retroceder 15 segundos")
        
        btn_forward15 = tb.Button(btn_frame, text="⏩15s", command=self.seek_forward_15, bootstyle="outline-info", width=8)
        btn_forward15.pack(side="left", padx=2)
        ToolTip(btn_forward15, "Avanzar 15 segundos")
        
        btn_prev = tb.Button(btn_frame, text="⏮", command=self.previous_audio, bootstyle="info", width=8)
        btn_prev.pack(side="left", padx=2)
        ToolTip(btn_prev, "Audio anterior (↑)")
        
        btn_next = tb.Button(btn_frame, text="⏭", command=self.next_audio, bootstyle="info", width=8)
        btn_next.pack(side="left", padx=2)
        ToolTip(btn_next, "Audio siguiente (↓)")

        # Loop toggle
        self.loop_var = tk.BooleanVar()
        self.btn_loop = tb.Checkbutton(btn_frame, text="🔁", variable=self.loop_var, bootstyle="warning")
        self.btn_loop.pack(side="left", padx=2)
        ToolTip(self.btn_loop, "Repetir audio actual")

        # Barra de progreso con información de tiempo
        progress_frame = tb.Frame(controls_frame)
        progress_frame.pack(fill="x", pady=5)

        # Tiempo actual y duración
        time_info_frame = tb.Frame(progress_frame)
        time_info_frame.pack(fill="x", pady=2)
        
        self.time_current_label = tb.Label(time_info_frame, text="00:00", font=("Segoe UI", 9))
        self.time_current_label.pack(side="left")
        
        self.time_duration_label = tb.Label(time_info_frame, text="00:00", font=("Segoe UI", 9))
        self.time_duration_label.pack(side="right")
        
        # Porcentaje de progreso
        self.progress_percent_label = tb.Label(time_info_frame, text="0%", font=("Segoe UI", 9), foreground="cyan")
        self.progress_percent_label.pack()

        self.progress = tb.Progressbar(progress_frame, orient="horizontal", mode='determinate')
        self.progress.pack(fill="x", pady=2)
        self.progress.bind("<Button-1>", self.on_progress_click)

        # Control de volumen mejorado
        volume_frame = tb.Frame(controls_frame)
        volume_frame.pack(fill="x", pady=5)
        
        volume_icon = tb.Label(volume_frame, text="🔊", font=("Segoe UI", 10))
        volume_icon.pack(side="left", padx=(0, 5))
        
        self.volume_scale = tb.Scale(volume_frame, from_=0, to=100, orient="horizontal", 
                                   command=self.set_volume, length=120)
        self.volume_scale.set(70)
        self.volume_scale.pack(side="left", fill="x", expand=True, padx=(5, 5))
        
        self.volume_label = tb.Label(volume_frame, text="70%", font=("Segoe UI", 9), width=4)
        self.volume_label.pack(side="left")
        ToolTip(self.volume_scale, "Control de volumen (0-100%)")

        # Control de velocidad mejorado
        speed_frame = tb.Frame(controls_frame)
        speed_frame.pack(fill="x", pady=5)
        
        speed_icon = tb.Label(speed_frame, text="⚡", font=("Segoe UI", 10))
        speed_icon.pack(side="left", padx=(0, 5))
        
        self.speed_var = tk.StringVar(value="1.0x")
        self.speed_label = tb.Label(speed_frame, textvariable=self.speed_var, 
                                   font=("Segoe UI", 9, "bold"), foreground="orange")
        self.speed_label.pack(side="left", padx=(5, 10))

        speed_buttons = tb.Frame(speed_frame)
        speed_buttons.pack(side="right")
        
        self.speed_buttons = {}
        for speed in [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]:
            btn = tb.Button(speed_buttons, text=f"{speed}x", 
                           command=lambda s=speed: self.set_playback_speed(s),
                           bootstyle="outline-secondary" if speed != 1.0 else "secondary", 
                           width=5)
            btn.pack(side="left", padx=1)
            self.speed_buttons[speed] = btn
            ToolTip(btn, f"Velocidad {speed}x")

        # Botones adicionales
        extra_frame = tb.Frame(controls_frame)
        extra_frame.pack(fill="x", pady=5)

        self.btn_favorite = tb.Button(extra_frame, text="⭐", command=self.toggle_favorite, 
                                     bootstyle="warning", width=8)
        self.btn_favorite.pack(side="left", padx=2)
        ToolTip(self.btn_favorite, "Marcar como favorito")

        btn_note = tb.Button(extra_frame, text="📝", command=self.add_note, bootstyle="info", width=8)
        btn_note.pack(side="left", padx=2)
        ToolTip(btn_note, "Agregar nota")
        
        btn_excel = tb.Button(extra_frame, text="📊", command=self.show_excel, bootstyle="warning", width=8)
        btn_excel.pack(side="left", padx=2)
        ToolTip(btn_excel, "Ver datos Excel")
        
        btn_marker = tb.Button(extra_frame, text="🔖", command=self.add_marker, bootstyle="secondary", width=8)
        btn_marker.pack(side="left", padx=2)
        ToolTip(btn_marker, "Agregar marcador (Ctrl+M)")

        # Estado
        self.label_status = tb.Label(controls_frame, text="Estado: Esperando...", font=("Segoe UI", 9), foreground="gray")
        self.label_status.pack(pady=(5, 0))
        
        # Waveform Display
        self.waveform_frame = tb.LabelFrame(right_panel, text="Visualización de Audio", padding=5)
        self.waveform_frame.pack(fill="both", expand=True, pady=(5, 0))
        
        # Crear figura de matplotlib para waveform
        plt.style.use('dark_background')
        self.waveform_figure = plt.Figure(figsize=(8, 3), dpi=80, facecolor='#2b2b2b')
        self.waveform_ax = self.waveform_figure.add_subplot(111)
        self.waveform_ax.set_facecolor('#1e1e1e')
        
        # Canvas para mostrar el waveform
        self.waveform_canvas = FigureCanvasTkAgg(self.waveform_figure, self.waveform_frame)
        self.waveform_canvas.get_tk_widget().pack(fill="both", expand=True)
        
        # Bind eventos del waveform
        self.waveform_canvas.mpl_connect('button_press_event', self.on_waveform_click)
        
        # Inicializar waveform vacío
        self.clear_waveform()
        
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
        
        # Mostrar ventana de progreso
        progress_dialog = self.progress_manager.show_zip_loading(1)
        
        try:
            # Limpiar datos anteriores
            progress_dialog.update_progress(10, "Limpiando datos anteriores...")
            self.audio_files.clear()
            self.listbox.delete(0, "end")
            self.favorites.clear()
            self.markers.clear()
            
            self.label_path.config(text=f"Archivo: {os.path.basename(zip_path)}")
            
            # Extraer ZIP
            progress_dialog.update_progress(25, f"Extrayendo {os.path.basename(zip_path)}...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # Obtener lista de archivos para progreso
                file_list = zip_ref.namelist()
                total_files = len(file_list)
                
                # Extraer archivo por archivo con progreso
                for i, member in enumerate(file_list):
                    if progress_dialog.is_cancelled():
                        return
                    
                    zip_ref.extract(member, self.temp_dir)
                    progress = 25 + (i / total_files) * 30  # 25-55% para extracción
                    progress_dialog.update_progress(
                        progress, 
                        f"Extrayendo: {os.path.basename(member)}...",
                        i + 1, 
                        total_files
                    )

            # Buscar archivos de audio y Excel
            progress_dialog.update_progress(60, "Buscando archivos de audio y Excel...")
            audio_count = 0
            excel_count = 0
            
            for root_dir, _, files in os.walk(self.temp_dir):
                for i, f in enumerate(files):
                    if progress_dialog.is_cancelled():
                        return
                    
                    full_path = os.path.join(root_dir, f)
                    
                    if f.lower().endswith((".mp3", ".wav", ".ogg", ".m4a")):
                        self.audio_files.append(full_path)
                        audio_count += 1
                        progress_dialog.update_progress(
                            60 + (i / len(files)) * 20,
                            f"Encontrado audio: {f}",
                            audio_count,
                            None
                        )
                    elif f.lower().endswith(".xlsx"):
                        self.excel_file = full_path
                        excel_count += 1
                        progress_dialog.update_progress(
                            60 + (i / len(files)) * 20,
                            f"Encontrado Excel: {f}"
                        )

            # Procesar Excel si existe
            if self.excel_file and excel_count > 0:
                progress_dialog.update_progress(85, "Procesando archivo Excel...")
                try:
                    self.df_excel = pd.read_excel(self.excel_file)
                    
                    # Procesar DataFrame
                    self.df_excel = self.df_excel.fillna("")
                    if 'Día/Hora de creación' in self.df_excel.columns:
                        progress_dialog.update_status("Procesando fechas en Excel...")
                        try:
                            # Mejorar parseo de fechas con formato específico
                            self.df_excel['Día/Hora de creación'] = pd.to_datetime(
                                self.df_excel['Día/Hora de creación'], 
                                format='%d/%m/%Y %H:%M:%S',
                                dayfirst=True,
                                errors='coerce'
                            )
                            self.df_excel = self.df_excel.sort_values('Día/Hora de creación', ascending=True)
                        except Exception as e:
                            logger.error(f"Error procesando fechas: {e}")
                            
                except Exception as e:
                    logger.error(f"Error leyendo Excel: {e}")
                    self.df_excel = None

            # Cargar favoritos y actualizar interfaz
            progress_dialog.update_progress(95, "Finalizando configuración...")
            self.load_favorites()
            self.populate_audio_list()
            
            progress_dialog.update_progress(100, "¡Carga completada!")
            
            # Cerrar diálogo de progreso
            progress_dialog.close()
            
            # Mensaje informativo mejorado
            excel_status = "con Excel integrado" if self.df_excel is not None else "sin Excel (solo audios)"
            self.label_status.config(text=f"Cargados {len(self.audio_files)} audios {excel_status}")
            
            # Mensaje de finalización más detallado
            if self.df_excel is not None:
                messagebox.showinfo("Carga Completa", 
                    f"✅ Archivos cargados exitosamente:\n\n"
                    f"• {len(self.audio_files)} archivos de audio\n"
                    f"• 1 archivo Excel con {len(self.df_excel)} registros\n\n"
                    f"Los audios han sido organizados según los datos del Excel.")
            else:
                result = messagebox.askyesno("Carga Completa - Sin Excel", 
                    f"✅ Se cargaron {len(self.audio_files)} archivos de audio.\n\n"
                    f"⚠️ No se encontró archivo Excel en el ZIP.\n\n"
                    f"¿Desea cargar un archivo Excel externo para organizar los audios?")
                
                if result:
                    self.load_external_excel()
            
        except Exception as e:
            progress_dialog.close()
            logger.error(f"Error cargando ZIP: {e}")
            messagebox.showerror("Error", f"Error cargando archivo ZIP: {e}")

    def load_multiple_zips(self):
        """Cargar múltiples archivos ZIP simultáneamente"""
        initial_dir = self.config.get('last_directory', '')
        zip_paths = filedialog.askopenfilenames(
            initialdir=initial_dir,
            title="Seleccionar múltiples archivos ZIP",
            filetypes=[("Archivos ZIP", "*.zip")]
        )
        
        if not zip_paths:
            return

        # Guardar directorio para próxima vez
        self.config['last_directory'] = os.path.dirname(zip_paths[0])
        
        # Mostrar ventana de progreso para múltiples ZIPs
        progress_dialog = self.progress_manager.show_zip_loading(len(zip_paths))
        
        try:
            # Limpiar datos anteriores
            progress_dialog.update_progress(5, "Limpiando datos anteriores...")
            self.audio_files.clear()
            self.listbox.delete(0, "end")
            self.favorites.clear()
            self.markers.clear()
            
            total_audios = 0
            loaded_zips = []
            excel_files = []
            
            total_zips = len(zip_paths)
            
            # Procesar cada ZIP
            for zip_index, zip_path in enumerate(zip_paths):
                if progress_dialog.is_cancelled():
                    return
                
                zip_name = os.path.basename(zip_path)
                base_progress = 10 + (zip_index / total_zips) * 70  # 10-80% para procesamiento ZIPs
                
                progress_dialog.update_progress(
                    base_progress,
                    f"Procesando ZIP {zip_index + 1}/{total_zips}: {zip_name}...",
                    zip_index,
                    total_zips
                )
                
                # Extraer ZIP actual
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    # Crear subdirectorio para este ZIP
                    zip_temp_dir = os.path.join(self.temp_dir, f"zip_{zip_index}")
                    os.makedirs(zip_temp_dir, exist_ok=True)
                    
                    # Obtener lista de archivos
                    file_list = zip_ref.namelist()
                    
                    # Extraer archivos con progreso detallado
                    for file_index, member in enumerate(file_list):
                        if progress_dialog.is_cancelled():
                            return
                        
                        zip_ref.extract(member, zip_temp_dir)
                        
                        # Actualizar progreso dentro del ZIP actual
                        file_progress = base_progress + (file_index / len(file_list)) * (70 / total_zips)
                        progress_dialog.update_progress(
                            file_progress,
                            f"Extrayendo de {zip_name}: {os.path.basename(member)}..."
                        )

                # Buscar archivos de audio y Excel en este ZIP
                zip_audios = 0
                progress_dialog.update_status(f"Analizando contenido de {zip_name}...")
                
                for root_dir, _, files in os.walk(zip_temp_dir):
                    for f in files:
                        if progress_dialog.is_cancelled():
                            return
                        
                        if f.lower().endswith((".mp3", ".wav", ".ogg", ".m4a")):
                            path = os.path.join(root_dir, f)
                            self.audio_files.append(path)
                            zip_audios += 1
                        elif f.lower().endswith(".xlsx"):
                            excel_path = os.path.join(root_dir, f)
                            excel_files.append(excel_path)

                total_audios += zip_audios
                loaded_zips.append(f"{zip_name} ({zip_audios} audios)")

            # Procesar archivos Excel (usar el primer archivo encontrado como principal)
            if excel_files:
                progress_dialog.update_progress(85, f"Procesando {len(excel_files)} archivo(s) Excel...")
                try:
                    self.excel_file = excel_files[0]
                    self.df_excel = pd.read_excel(self.excel_file)
                    
                    # Si hay múltiples Excel, combinarlos
                    if len(excel_files) > 1:
                        progress_dialog.update_status("Combinando múltiples archivos Excel...")
                        dfs_to_combine = [self.df_excel]
                        
                        for i, excel_path in enumerate(excel_files[1:]):
                            if progress_dialog.is_cancelled():
                                return
                            
                            try:
                                df_additional = pd.read_excel(excel_path)
                                dfs_to_combine.append(df_additional)
                                progress_dialog.update_status(f"Combinando Excel {i+2}/{len(excel_files)}...")
                            except Exception as e:
                                logger.warning(f"Error leyendo Excel adicional {excel_path}: {e}")
                        
                        # Combinar DataFrames
                        self.df_excel = pd.concat(dfs_to_combine, ignore_index=True)
                        
                except Exception as e:
                    logger.error(f"Error procesando archivos Excel: {e}")
                    self.df_excel = None
            else:
                self.df_excel = None

            # Procesar DataFrame si existe
            if self.df_excel is not None:
                progress_dialog.update_progress(92, "Procesando datos Excel...")
                self.df_excel = self.df_excel.fillna("")
                if 'Día/Hora de creación' in self.df_excel.columns:
                    try:
                        progress_dialog.update_status("Procesando fechas...")
                        # Mejorar parseo de fechas con formato específico
                        self.df_excel['Día/Hora de creación'] = pd.to_datetime(
                            self.df_excel['Día/Hora de creación'],
                            format='%d/%m/%Y %H:%M:%S',
                            dayfirst=True,
                            errors='coerce'
                        )
                        self.df_excel = self.df_excel.sort_values('Día/Hora de creación', ascending=True)
                    except Exception as e:
                        logger.error(f"Error procesando fechas: {e}")

            # Finalizar carga
            progress_dialog.update_progress(98, "Finalizando carga...")
            self.load_favorites()
            self.populate_audio_list()
            
            progress_dialog.update_progress(100, "¡Carga múltiple completada!")
            progress_dialog.close()
            
            # Actualizar etiquetas
            zip_names = [os.path.basename(path) for path in zip_paths]
            if len(zip_names) <= 3:
                zip_text = ", ".join(zip_names)
            else:
                zip_text = f"{', '.join(zip_names[:2])} y {len(zip_names)-2} más"
            
            self.label_path.config(text=f"ZIPs: {zip_text}")
            excel_status = "con Excel" if self.df_excel is not None else "sin Excel"
            self.label_status.config(text=f"Cargados {total_audios} audios desde {len(zip_paths)} ZIPs {excel_status}")
            
            success_msg = f"✅ Carga múltiple completada:\n\n"
            for zip_info in loaded_zips:
                success_msg += f"• {zip_info}\n"
            success_msg += f"\n📊 Total: {total_audios} archivos de audio"
            
            if self.df_excel is not None:
                success_msg += f"\n📋 Excel: {len(self.df_excel)} registros combinados"
                messagebox.showinfo("Carga Múltiple Completa", success_msg)
            else:
                success_msg += f"\n⚠️ Sin archivos Excel encontrados en los ZIPs"
                result = messagebox.askyesno("Carga Múltiple Completa", 
                    success_msg + "\n\n¿Desea cargar un archivo Excel externo?")
                
                if result:
                    self.load_external_excel()
            
        except Exception as e:
            progress_dialog.close()
            logger.error(f"Error cargando múltiples ZIPs: {e}")
            messagebox.showerror("Error", f"Error cargando archivos ZIP: {e}")

    def add_more_zips(self):
        """Agregar más archivos ZIP a los ya cargados"""
        initial_dir = self.config.get('last_directory', '')
        zip_paths = filedialog.askopenfilenames(
            initialdir=initial_dir,
            title="Agregar más archivos ZIP",
            filetypes=[("Archivos ZIP", "*.zip")]
        )
        
        if not zip_paths:
            return

        # Guardar directorio para próxima vez
        self.config['last_directory'] = os.path.dirname(zip_paths[0])
        
        # NO limpiar datos anteriores - esta es la diferencia clave
        current_audio_count = len(self.audio_files)
        new_audios = 0
        loaded_zips = []
        excel_files = []
        
        self.label_status.config(text="Agregando más archivos ZIP...")
        
        try:
            # Procesar cada ZIP nuevo
            existing_temp_dirs = len([d for d in os.listdir(self.temp_dir) if d.startswith('zip_')])
            
            for i, zip_path in enumerate(zip_paths):
                zip_name = os.path.basename(zip_path)
                self.label_status.config(text=f"Procesando: {zip_name}...")
                
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    # Crear subdirectorio único para este ZIP
                    zip_temp_dir = os.path.join(self.temp_dir, f"zip_{existing_temp_dirs + i}")
                    os.makedirs(zip_temp_dir, exist_ok=True)
                    zip_ref.extractall(zip_temp_dir)

                # Buscar archivos de audio y Excel en este ZIP
                zip_audios = 0
                for root_dir, _, files in os.walk(zip_temp_dir):
                    for f in files:
                        if f.lower().endswith((".mp3", ".wav", ".ogg", ".m4a")):
                            path = os.path.join(root_dir, f)
                            self.audio_files.append(path)
                            zip_audios += 1
                        elif f.lower().endswith(".xlsx"):
                            excel_path = os.path.join(root_dir, f)
                            excel_files.append(excel_path)

                new_audios += zip_audios
                loaded_zips.append(f"{zip_name} ({zip_audios} audios)")

            # Procesar archivos Excel adicionales si existen
            if excel_files:
                try:
                    dfs_to_add = []
                    for excel_path in excel_files:
                        try:
                            df_new = pd.read_excel(excel_path)
                            dfs_to_add.append(df_new)
                        except Exception as e:
                            logger.warning(f"Error leyendo Excel adicional {excel_path}: {e}")
                    
                    # Combinar con DataFrame existente si hay datos nuevos
                    if dfs_to_add:
                        if self.df_excel is not None:
                            all_dfs = [self.df_excel] + dfs_to_add
                            self.df_excel = pd.concat(all_dfs, ignore_index=True)
                        else:
                            self.df_excel = pd.concat(dfs_to_add, ignore_index=True)
                        
                        # Procesar DataFrame actualizado
                        self.df_excel = self.df_excel.fillna("")
                        if 'Día/Hora de creación' in self.df_excel.columns:
                            try:
                                # Mejorar parseo de fechas con formato específico
                                self.df_excel['Día/Hora de creación'] = pd.to_datetime(
                                    self.df_excel['Día/Hora de creación'],
                                    format='%d/%m/%Y %H:%M:%S',
                                    dayfirst=True,
                                    errors='coerce'
                                )
                                self.df_excel = self.df_excel.sort_values('Día/Hora de creación', ascending=True)
                            except Exception as e:
                                logger.error(f"Error procesando fechas: {e}")
                                
                except Exception as e:
                    logger.error(f"Error procesando archivos Excel adicionales: {e}")

            # Recargar favoritos (pueden haber cambiado con nuevos datos)
            self.load_favorites()
            
            # Actualizar lista de audios
            self.populate_audio_list()
            
            # Actualizar etiquetas
            current_path = self.label_path.cget("text")
            if "ZIPs:" in current_path:
                self.label_path.config(text=f"{current_path} + {len(zip_paths)} más")
            else:
                zip_names = [os.path.basename(path) for path in zip_paths]
                if len(zip_names) <= 2:
                    zip_text = ", ".join(zip_names)
                else:
                    zip_text = f"{zip_names[0]} y {len(zip_names)-1} más"
                self.label_path.config(text=f"{current_path} + {zip_text}")
            
            total_audios = len(self.audio_files)
            self.label_status.config(text=f"Total: {total_audios} audios ({new_audios} nuevos agregados)")
            
            success_msg = f"Agregados exitosamente:\n"
            for zip_info in loaded_zips:
                success_msg += f"• {zip_info}\n"
            success_msg += f"\nNuevos audios: {new_audios}"
            success_msg += f"\nTotal ahora: {total_audios} audios"
            
            messagebox.showinfo("Archivos Agregados", success_msg)
            
        except Exception as e:
            logger.error(f"Error agregando más ZIPs: {e}")
            messagebox.showerror("Error", f"Error agregando archivos ZIP: {e}")

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

    def load_external_excel(self):
        """Cargar archivo Excel desde ubicación externa"""
        initial_dir = self.config.get('last_directory', '')
        excel_path = filedialog.askopenfilename(
            initialdir=initial_dir,
            title="Seleccionar archivo Excel",
            filetypes=[
                ("Archivos Excel", "*.xlsx"),
                ("Archivos Excel antiguos", "*.xls"),
                ("Todos los archivos", "*.*")
            ]
        )
        
        if not excel_path:
            return

        # Guardar directorio para próxima vez
        self.config['last_directory'] = os.path.dirname(excel_path)
        
        # Mostrar progreso para Excel
        progress_dialog = self.progress_manager.show_excel_loading()
        
        try:
            # Cargar el archivo Excel
            filename = os.path.basename(excel_path)
            progress_dialog.update_progress(20, f"Cargando {filename}...")
            
            self.excel_file = excel_path
            self.df_excel = pd.read_excel(excel_path)
            
            progress_dialog.update_progress(60, "Procesando datos Excel...")
            
            # Procesar DataFrame
            if self.df_excel is not None:
                self.df_excel = self.df_excel.fillna("")
                
                progress_dialog.update_progress(75, "Procesando fechas y datos...")
                if 'Día/Hora de creación' in self.df_excel.columns:
                    try:
                        # Mejorar parseo de fechas con formato específico
                        self.df_excel['Día/Hora de creación'] = pd.to_datetime(
                            self.df_excel['Día/Hora de creación'],
                            format='%d/%m/%Y %H:%M:%S',
                            dayfirst=True,
                            errors='coerce'
                        )
                        self.df_excel = self.df_excel.sort_values('Día/Hora de creación', ascending=True)
                    except Exception as e:
                        logger.error(f"Error procesando fechas: {e}")

                progress_dialog.update_progress(90, "Reorganizando lista de audios...")
                # Recargar favoritos y actualizar lista
                self.load_favorites()
                self.populate_audio_list()
                
                progress_dialog.update_progress(100, "Excel cargado exitosamente!")
                progress_dialog.close()
                
                # Mostrar información sobre el Excel cargado
                filas_count = len(self.df_excel)
                
                messagebox.showinfo(
                    "Excel Cargado", 
                    f"Archivo Excel cargado exitosamente:\n\n"
                    f"• Archivo: {filename}\n"
                    f"• Registros: {filas_count}\n"
                    f"• Columnas: {', '.join(self.df_excel.columns[:3])}{'...' if len(self.df_excel.columns) > 3 else ''}\n\n"
                    f"Los audios se han reorganizado según los datos del Excel."
                )
                
                # Actualizar etiqueta de ruta para mostrar que hay Excel externo
                current_path = self.label_path.cget("text")
                if "Excel:" not in current_path:
                    self.label_path.config(text=f"{current_path} | Excel: {filename}")
            
        except Exception as e:
            progress_dialog.close()
            logger.error(f"Error cargando Excel externo: {e}")
            messagebox.showerror(
                "Error al Cargar Excel", 
                f"No se pudo cargar el archivo Excel:\n\n{str(e)}\n\n"
                f"Verifique que:\n"
                f"• El archivo no esté abierto en otra aplicación\n"
                f"• Tenga permisos de lectura\n"
                f"• Contenga datos válidos"
            )

    def show_basic_audio_info(self):
        """Mostrar información básica de archivos de audio cuando no hay Excel"""
        if not self.audio_files:
            messagebox.showwarning("Sin Datos", "No hay archivos de audio cargados.")
            return
        
        # Crear ventana de información básica
        info_window = Toplevel(self.root)
        info_window.title("Información de Archivos de Audio")
        info_window.geometry("800x600")
        info_window.transient(self.root)
        
        # Frame principal
        main_frame = tb.Frame(info_window)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Título
        title_label = tb.Label(
            main_frame, 
            text="📁 Archivos de Audio Disponibles", 
            font=("Segoe UI", 14, "bold")
        )
        title_label.pack(pady=(0, 10))
        
        # Información general
        info_frame = tb.LabelFrame(main_frame, text="Información General", padding=10)
        info_frame.pack(fill="x", pady=(0, 10))
        
        total_files = len(self.audio_files)
        audio_formats = {}
        total_size = 0
        
        # Analizar archivos
        for audio_path in self.audio_files:
            if os.path.exists(audio_path):
                # Contar formatos
                ext = os.path.splitext(audio_path)[1].lower()
                audio_formats[ext] = audio_formats.get(ext, 0) + 1
                
                # Calcular tamaño
                try:
                    total_size += os.path.getsize(audio_path)
                except:
                    pass
        
        # Mostrar estadísticas
        stats_text = f"• Total de archivos: {total_files}\n"
        stats_text += f"• Tamaño total: {self.format_file_size(total_size)}\n"
        stats_text += f"• Formatos encontrados: {', '.join(audio_formats.keys())}\n"
        
        for fmt, count in audio_formats.items():
            stats_text += f"  - {fmt.upper()}: {count} archivo{'s' if count != 1 else ''}\n"
        
        tb.Label(info_frame, text=stats_text, anchor="w", justify="left").pack(fill="x")
        
        # Lista de archivos
        list_frame = tb.LabelFrame(main_frame, text="Lista de Archivos", padding=5)
        list_frame.pack(fill="both", expand=True)
        
        # Treeview para mostrar archivos
        columns = ("Nombre", "Formato", "Tamaño")
        tree = tb.Treeview(list_frame, columns=columns, show="tree headings", height=15)
        
        # Configurar columnas
        tree.heading("#0", text="Nº")
        tree.column("#0", width=50)
        
        for col in columns:
            tree.heading(col, text=col)
        
        tree.column("Nombre", width=400)
        tree.column("Formato", width=80)
        tree.column("Tamaño", width=100)
        
        # Scrollbar para la lista
        scrollbar_tree = tb.Scrollbar(list_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar_tree.set)
        
        # Llenar la lista
        for i, audio_path in enumerate(self.audio_files, 1):
            filename = os.path.basename(audio_path)
            formato = os.path.splitext(filename)[1].upper()
            
            # Obtener tamaño
            try:
                size = os.path.getsize(audio_path) if os.path.exists(audio_path) else 0
                size_str = self.format_file_size(size)
            except:
                size_str = "N/A"
            
            tree.insert("", "end", text=str(i), values=(filename, formato, size_str))
        
        tree.pack(side="left", fill="both", expand=True)
        scrollbar_tree.pack(side="right", fill="y")
        
        # Botones
        btn_frame = tb.Frame(info_window)
        btn_frame.pack(fill="x", padx=10, pady=10)
        
        tb.Button(
            btn_frame, 
            text="Cargar Excel Externo", 
            command=lambda: [info_window.destroy(), self.load_external_excel()],
            bootstyle="success"
        ).pack(side="left", padx=5)
        
        tb.Button(
            btn_frame, 
            text="Cerrar", 
            command=info_window.destroy,
            bootstyle="secondary"
        ).pack(side="right", padx=5)

    def format_file_size(self, size_bytes):
        """Formatear tamaño de archivo en unidades legibles"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.1f} {size_names[i]}"

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
        if not self.listbox.curselection():
            return
            
        idx = self.listbox.curselection()[0]
        # Obtener el nombre del archivo sin el icono
        display_text = self.listbox.get(idx)
        nombre_audio = display_text.split(' ', 1)[1] if ' ' in display_text else display_text
        
        if self.df_excel is not None:
            # Con Excel: mostrar información completa
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
                else:
                    # Audio no encontrado en Excel
                    self.show_audio_only_info(nombre_audio)
            else:
                # No se pudo extraer ID de sesión
                self.show_audio_only_info(nombre_audio)
        else:
            # Sin Excel: mostrar solo información básica del archivo
            self.show_audio_only_info(nombre_audio)

    def show_audio_only_info(self, nombre_audio):
        """Mostrar información básica cuando no hay datos Excel"""
        # Limpiar campos de información
        self.labels_info["Id de sesión"].config(text="Id de sesión: Sin datos Excel")
        self.labels_info["Día/Hora de creación"].config(text="Día/Hora de creación: Sin datos Excel")
        self.labels_info["Nombre abonado"].config(text="Nombre abonado: Sin datos Excel")
        self.labels_info["DDR"].config(text="DDR: Sin datos Excel")
        self.labels_info["Notas"].config(text="Notas: Sin datos Excel")
        self.labels_info["Transcripción llamada"].config(text="Transcripción llamada: Sin datos Excel")
        
        # Mostrar información básica del archivo
        if self.audio_files and len(self.audio_files) > self.listbox.curselection()[0]:
            audio_path = self.audio_files[self.listbox.curselection()[0]]
            
            try:
                # Información del archivo
                file_stats = os.stat(audio_path) if os.path.exists(audio_path) else None
                
                if file_stats:
                    # Fecha de modificación del archivo
                    mod_time = datetime.fromtimestamp(file_stats.st_mtime)
                    self.labels_info["Día/Hora de creación"].config(
                        text=f"Día/Hora de creación: {mod_time.strftime('%Y-%m-%d %H:%M:%S')} (archivo)"
                    )
                    
                    # Tamaño del archivo
                    file_size = self.format_file_size(file_stats.st_size)
                    self.labels_info["Notas"].config(text=f"Notas: Tamaño: {file_size}")
                
                # Intentar extraer información del nombre del archivo
                base_name = os.path.splitext(nombre_audio)[0]
                self.labels_info["Id de sesión"].config(text=f"Id de sesión: {base_name}")
                
            except Exception as e:
                logger.error(f"Error obteniendo info del archivo: {e}")
        
        # Deshabilitar botón de favoritos sin Excel
        self.btn_favorite.config(text="⭐", bootstyle="outline-warning")
        
        # Cambiar el título del frame para indicar modo sin Excel
        self.info_frame.config(text="Información del Archivo (Sin Excel)")

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
                # Primero generar waveform para obtener duración precisa
                if self.generate_waveform(audio_path):
                    if self.waveform_data and 'duration' in self.waveform_data:
                        self.audio_duration = self.waveform_data['duration']
                        logger.info(f"Duración obtenida del waveform: {self.audio_duration:.2f}s")
                else:
                    # Fallback: intentar obtener duración con pydub
                    try:
                        self.audio_segment = AudioSegment.from_file(audio_path)
                        self.audio_duration = len(self.audio_segment) / 1000.0
                        logger.info(f"Duración obtenida con pydub: {self.audio_duration:.2f}s")
                    except Exception as e:
                        logger.warning(f"No se pudo obtener duración: {e}")
                        # Como último recurso, usar duración estimada típica
                        self.audio_duration = 120.0  # 2 minutos por defecto
                
                # Cargar y reproducir
                mixer.music.load(audio_path)
                mixer.music.set_volume(self.volume)
                mixer.music.play()
                
                self.is_playing = True
                self.btn_play.config(text="⏸")
                self.label_status.config(text="Reproduciendo...")
                
                # Configurar barra de progreso
                self.progress['maximum'] = self.audio_duration if self.audio_duration > 0 else 100
                self.progress['value'] = 0
                self.audio_position = 0.0
                self.start_time = time.time()  # Tiempo de inicio para cálculo preciso
                
                # Mostrar waveform ya generado
                if self.waveform_data:
                    self.update_waveform_display()
                
                # Cargar marcadores para esta sesión
                display_text = self.listbox.get(idx)
                nombre_audio = display_text.split(' ', 1)[1] if ' ' in display_text else display_text
                session_id = self.get_session_id_from_filename(nombre_audio)
                if session_id:
                    self.load_markers_for_session(session_id)
                    self.update_waveform_display()
                
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
            # Guardar tiempo transcurrido al pausar
            if hasattr(self, 'start_time'):
                self.paused_time = time.time() - self.start_time
        else:
            mixer.music.unpause()
            self.is_playing = True
            self.btn_play.config(text="⏸")
            self.label_status.config(text="Reproduciendo...")
            # Reanudar desde donde se pausó
            if hasattr(self, 'paused_time'):
                self.start_time = time.time() - self.paused_time
            else:
                self.start_time = time.time()

    def stop_audio(self):
        """Detener reproducción"""
        mixer.music.stop()
        self.is_playing = False
        self.btn_play.config(text="▶")
        self.label_status.config(text="Detenido")
        self.progress['value'] = 0
        self.audio_position = 0.0
        
        # Actualizar display de tiempo
        self.update_time_display()
        
        # Limpiar variables de tiempo
        if hasattr(self, 'start_time'):
            delattr(self, 'start_time')
        if hasattr(self, 'paused_time'):
            delattr(self, 'paused_time')

    def update_progress(self):
        """Actualizar barra de progreso y tiempo"""
        if self.is_playing and mixer.music.get_busy():
            # Calcular posición basada en tiempo transcurrido
            if hasattr(self, 'start_time'):
                elapsed_time = time.time() - self.start_time
                
                # Verificar que no exceda la duración total
                if elapsed_time <= self.audio_duration:
                    self.audio_position = elapsed_time
                else:
                    # El audio debería haber terminado
                    self.audio_position = self.audio_duration
                    
                self.progress['value'] = self.audio_position
                
                # Actualizar información de tiempo
                self.update_time_display()
                
                # Actualizar línea de posición en waveform
                if (self.waveform_data and hasattr(self, 'waveform_ax') and 
                    self.audio_position is not None and 
                    'duration' in self.waveform_data):
                    # Limpiar línea anterior y dibujar nueva
                    try:
                        lines = [l for l in self.waveform_ax.lines if l.get_color() == 'red']
                        for line in lines:
                            line.remove()
                        
                        if self.audio_position <= self.waveform_data['duration']:
                            self.waveform_ax.axvline(x=self.audio_position, color='red', linewidth=2, alpha=0.8)
                            self.waveform_canvas.draw_idle()
                    except:
                        pass
            
            # Continuar actualizando
            self.root.after(100, self.update_progress)
        elif not mixer.music.get_busy() and self.is_playing:
            # Audio terminó - verificar si debe hacer loop
            if self.loop_var.get():
                self.play_audio()  # Reiniciar reproducción
            else:
                self.stop_audio()
                if self.config.get('auto_play_next', False):
                    self.next_audio()

    def update_time_display(self):
        """Actualizar display de tiempo mejorado"""
        current_time = self.format_time(self.audio_position if self.audio_position is not None else 0)
        total_time = self.format_time(self.audio_duration if self.audio_duration is not None else 0)
        
        # Actualizar etiquetas individuales
        if hasattr(self, 'time_current_label'):
            self.time_current_label.config(text=current_time)
        if hasattr(self, 'time_duration_label'):
            self.time_duration_label.config(text=total_time)
        
        # Calcular y mostrar porcentaje
        if hasattr(self, 'progress_percent_label') and self.audio_duration and self.audio_duration > 0:
            percentage = (self.audio_position / self.audio_duration) * 100 if self.audio_position else 0
            self.progress_percent_label.config(text=f"{percentage:.1f}%")

    def format_time(self, seconds):
        """Formatear tiempo en MM:SS"""
        if seconds is None or seconds < 0:
            return "00:00"
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
            
            if hasattr(self, 'audio_segment') and self.audio_segment:
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
                    # Actualizar tiempo de inicio para el nuevo punto
                    self.start_time = time.time() - position
                else:
                    self.is_playing = False
                
                self.audio_position = position
                self.progress['value'] = position
            else:
                # Sin audio_segment, solo actualizar posición visual
                self.audio_position = position
                self.progress['value'] = position
                
                # Si estaba reproduciéndo, reiniciar desde el principio
                if was_playing:
                    mixer.music.load(self.current_audio)
                    mixer.music.play()
                    self.is_playing = True
                    self.start_time = time.time() - position
                
        except Exception as e:
            logger.error(f"Error en seek: {e}")
            # Fallback: al menos actualizar la posición visual
            self.audio_position = position
            self.progress['value'] = position

    def seek_forward(self):
        """Avanzar 10 segundos"""
        if self.audio_position is None or self.audio_duration is None:
            return
        new_position = min(self.audio_position + 10, self.audio_duration)
        self.seek_to_position(new_position)

    def seek_backward(self):
        """Retroceder 10 segundos"""
        if self.audio_position is None:
            return
        new_position = max(self.audio_position - 10, 0)
        self.seek_to_position(new_position)

    def seek_forward_15(self):
        """Avanzar 15 segundos"""
        if self.audio_position is None or self.audio_duration is None:
            return
        new_position = min(self.audio_position + 15, self.audio_duration)
        self.seek_to_position(new_position)

    def seek_backward_15(self):
        """Retroceder 15 segundos"""
        if self.audio_position is None:
            return
        new_position = max(self.audio_position - 15, 0)
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
        """Establecer volumen con feedback visual"""
        self.volume = float(value) / 100.0
        mixer.music.set_volume(self.volume)
        self.config['volume'] = self.volume
        
        # Actualizar etiqueta de volumen
        if hasattr(self, 'volume_label'):
            self.volume_label.config(text=f"{int(float(value))}%")

    def set_playback_speed(self, speed):
        """Establecer velocidad de reproducción con feedback visual"""
        self.playback_speed = speed
        self.speed_var.set(f"{speed}x")
        
        # Actualizar botones de velocidad para mostrar selección
        if hasattr(self, 'speed_buttons'):
            for s, btn in self.speed_buttons.items():
                if s == speed:
                    btn.configure(bootstyle="secondary")
                else:
                    btn.configure(bootstyle="outline-secondary")
        
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
        """Mostrar estadísticas avanzadas del conjunto de datos con gráficos"""
        if not self.audio_files:
            messagebox.showwarning("Advertencia", "No hay audios cargados")
            return
        
        # Mostrar progreso para cálculo de estadísticas con mensaje específico
        progress_dialog = self.progress_manager.show_statistics_loading()
        
        # Configuración especial para estadísticas
        progress_dialog.window.title("📊 Generando Estadísticas Avanzadas")
        progress_dialog.window.geometry("550x220")
        progress_dialog.title_label.config(text="Procesando datos para análisis estadístico...")
        progress_dialog.status_label.config(text="Este proceso puede tomar unos minutos dependiendo del tamaño del dataset")
        progress_dialog.window.update_idletasks()
        
        try:
            progress_dialog.update_progress(10, "Iniciando cálculo de estadísticas...")
            
            # Limpiar figuras anteriores para liberar memoria
            self.cleanup_matplotlib_figures()
            
            progress_dialog.update_progress(20, "Calculando estadísticas comprehensivas...")
            # Calcular todas las estadísticas ANTES de crear la ventana
            stats_data = self.calculate_comprehensive_stats(progress_dialog)
            
            if progress_dialog.is_cancelled():
                return
            
            progress_dialog.update_progress(70, "Creando interfaz de estadísticas...")
            
            # AHORA crear la ventana después de los cálculos
            stats_window = Toplevel(self.root)
            stats_window.title("📊 Estadísticas Avanzadas")
            stats_window.geometry("1200x800")
            
            # Centrar ventana antes de mostrar
            stats_window.withdraw()  # Ocultar temporalmente
            stats_window.update_idletasks()
            
            # Bind para limpiar memoria al cerrar
            stats_window.protocol("WM_DELETE_WINDOW", 
                                 lambda: [self.cleanup_matplotlib_figures(), stats_window.destroy()])
            
            # Notebook para múltiples pestañas
            notebook = tb.Notebook(stats_window)
            notebook.pack(fill="both", expand=True, padx=10, pady=10)
            
            progress_dialog.update_progress(80, "Generando pestañas de análisis...")
            
            # Pestaña 1: Resumen General
            self.create_general_stats_tab(notebook, stats_data)
            
            # Pestaña 2: Análisis Temporal
            self.create_temporal_stats_tab(notebook, stats_data)
            
            # Pestaña 3: Análisis de Duración
            self.create_duration_stats_tab(notebook, stats_data)
            
            # Pestaña 4: Análisis de Contenido (si hay Excel)
            if self.df_excel is not None:
                self.create_content_stats_tab(notebook, stats_data)
            
            # Pestaña 5: Análisis de Favoritos
            self.create_favorites_stats_tab(notebook, stats_data)
            
            progress_dialog.update_progress(95, "Finalizando interfaz...")
            
            # Maximizar y mostrar la ventana SOLO cuando todo esté listo
            stats_window.state('zoomed')  # Maximizar
            stats_window.deiconify()  # Mostrar la ventana
            stats_window.focus_set()  # Dar foco
            
            progress_dialog.update_progress(100, "¡Estadísticas generadas!")
            progress_dialog.close()
            
        except Exception as e:
            progress_dialog.close()
            logger.error(f"Error generando estadísticas: {e}")
            messagebox.showerror("Error", f"Error generando estadísticas: {e}")
            if 'stats_window' in locals():
                stats_window.destroy()
    
    def calculate_comprehensive_stats(self, progress_dialog=None):
        """Calcular todas las estadísticas necesarias con progreso optimizado"""
        logger.info("Calculando estadísticas comprehensivas...")
        
        if progress_dialog:
            progress_dialog.update_status("Inicializando análisis del dataset...")
        
        stats = {
            'total_audios': len(self.audio_files),
            'total_favorites': len(self.favorites),
            'duration_list': [],
            'file_sizes': [],
            'date_stats': {},
            'hour_stats': {},
            'weekday_stats': {},
            'subscriber_stats': {},
            'ddr_stats': {},
            'transcription_lengths': [],
            'notes_lengths': [],
            'audio_formats': {},
            'zip_sources': getattr(self, 'loaded_zip_files', [])
        }
        
        if progress_dialog:
            progress_dialog.update_progress(15, f"Analizando {len(self.audio_files)} archivos de audio...")
        
        # Análisis de archivos de audio con mejor manejo de errores y progreso más granular
        total_size = 0
        processed_count = 0
        error_count = 0
        missing_files = 0
        
        # Procesar en lotes para mejor feedback
        batch_size = max(1, len(self.audio_files) // 20)  # 20 actualizaciones de progreso
        
        for i, audio_path in enumerate(self.audio_files):
            if progress_dialog and progress_dialog.is_cancelled():
                return stats
            
            # Actualizar progreso cada lote
            if i % batch_size == 0 or i == len(self.audio_files) - 1:
                progress = 15 + (i / len(self.audio_files)) * 35  # 15-50%
                if progress_dialog:
                    progress_dialog.update_progress(
                        progress,
                        f"Procesando archivos: {processed_count}/{len(self.audio_files)} (errores: {error_count})",
                        processed_count,
                        len(self.audio_files)
                    )
            
            # Verificar que el archivo existe antes de procesarlo
            if not os.path.exists(audio_path):
                missing_files += 1
                error_count += 1
                if missing_files <= 5:  # Mostrar solo los primeros 5 archivos faltantes
                    logger.warning(f"Archivo no encontrado: {os.path.basename(audio_path)}")
                elif missing_files == 6:
                    logger.info(f"... y más archivos faltantes (se omiten logs individuales)")
                continue
            
            try:
                # Obtener tamaño de archivo primero (más rápido)
                file_size = os.path.getsize(audio_path)
                stats['file_sizes'].append(file_size)
                total_size += file_size
                
                # Formato de archivo
                ext = os.path.splitext(audio_path)[1].lower()
                stats['audio_formats'][ext] = stats['audio_formats'].get(ext, 0) + 1
                
                # Duración usando pydub (más lento, pero necesario para estadísticas precisas)
                try:
                    segment = AudioSegment.from_file(audio_path)
                    duration = len(segment) / 1000.0  # en segundos
                    stats['duration_list'].append(duration)
                except Exception as duration_error:
                    # Si no se puede obtener duración, usar estimación basada en tamaño
                    # Para MP3: aproximadamente 1MB = 1 minuto (bitrate promedio 128kbps)
                    if ext == '.mp3':
                        estimated_duration = (file_size / (1024 * 1024)) * 60
                        stats['duration_list'].append(estimated_duration)
                    else:
                        # Para otros formatos, usar duración promedio de los procesados exitosamente
                        avg_duration = sum(stats['duration_list']) / len(stats['duration_list']) if stats['duration_list'] else 180
                        stats['duration_list'].append(avg_duration)
                    
                    logger.debug(f"Error obteniendo duración para {os.path.basename(audio_path)}: {duration_error}")
                
                processed_count += 1
                
            except Exception as e:
                error_count += 1
                if error_count <= 5:  # Solo mostrar los primeros errores detallados
                    logger.warning(f"Error procesando {os.path.basename(audio_path)}: {str(e)[:100]}...")
                elif error_count == 6:
                    logger.info("... más errores de procesamiento (se omiten logs individuales)")
                continue
        
        stats['total_size'] = total_size
        stats['processed_count'] = processed_count
        stats['error_count'] = error_count
        stats['missing_files'] = missing_files
        
        # Registrar resumen de procesamiento
        if error_count > 0 or missing_files > 0:
            logger.info(f"Procesamiento de audio: {processed_count} exitosos, {error_count} errores, {missing_files} archivos faltantes")
        else:
            logger.info(f"Todos los {processed_count} archivos procesados exitosamente")
        
        if progress_dialog:
            progress_dialog.update_progress(55, "Analizando datos Excel...")
        
        # Análisis de datos Excel si disponible - con mejor manejo de progreso
        if self.df_excel is not None:
            try:
                total_excel_rows = len(self.df_excel)
                
                # Análisis temporal con progreso granular
                if 'Día/Hora de creación' in self.df_excel.columns:
                    if progress_dialog:
                        progress_dialog.update_status("Procesando fechas y horarios...")
                    
                    for index, (_, row) in enumerate(self.df_excel.iterrows()):
                        if progress_dialog and progress_dialog.is_cancelled():
                            return stats
                        
                        # Actualizar progreso cada 500 registros
                        if index % 500 == 0 and progress_dialog:
                            progress = 55 + (index / total_excel_rows) * 15  # 55-70%
                            progress_dialog.update_progress(
                                progress,
                                f"Analizando fechas: {index:,}/{total_excel_rows:,} registros"
                            )
                        
                        fecha = row.get('Día/Hora de creación')
                        if pd.notna(fecha):
                            try:
                                if hasattr(fecha, 'strftime'):
                                    date_obj = fecha
                                else:
                                    date_obj = pd.to_datetime(fecha, format='%d/%m/%Y %H:%M:%S', 
                                                            dayfirst=True, errors='coerce')
                                
                                if pd.notna(date_obj):
                                    # Estadísticas por fecha
                                    date_key = date_obj.strftime('%Y-%m-%d')
                                    stats['date_stats'][date_key] = stats['date_stats'].get(date_key, 0) + 1
                                    
                                    # Estadísticas por hora
                                    hour_key = date_obj.hour
                                    stats['hour_stats'][hour_key] = stats['hour_stats'].get(hour_key, 0) + 1
                                    
                                    # Estadísticas por día de la semana
                                    weekday_key = date_obj.strftime('%A')
                                    stats['weekday_stats'][weekday_key] = stats['weekday_stats'].get(weekday_key, 0) + 1
                                    
                            except Exception as e:
                                pass  # Ignorar errores de fecha individual para mejor performance
                
                if progress_dialog:
                    progress_dialog.update_progress(72, "Analizando abonados y DDR...")
                
                # Análisis de abonados (optimizado)
                if 'Nombre abonado' in self.df_excel.columns:
                    subscriber_counts = self.df_excel['Nombre abonado'].value_counts()
                    stats['subscriber_stats'] = dict(subscriber_counts.head(50))  # Limitar para performance
                
                # Análisis de DDR (optimizado)
                if 'DDR' in self.df_excel.columns:
                    ddr_counts = self.df_excel['DDR'].value_counts()
                    stats['ddr_stats'] = dict(ddr_counts.head(20))  # Limitar para performance
                
                if progress_dialog:
                    progress_dialog.update_progress(75, "Procesando transcripciones...")
                
                # Análisis de transcripciones (muestreo para mejor performance)
                if 'Transcripción llamada' in self.df_excel.columns:
                    transcription_sample = self.df_excel['Transcripción llamada'].dropna().head(1000)
                    for transcription in transcription_sample:
                        if transcription and str(transcription).strip():
                            stats['transcription_lengths'].append(len(str(transcription)))
                
                # Análisis de notas (muestreo)
                if 'Notas' in self.df_excel.columns:
                    notes_sample = self.df_excel['Notas'].dropna().head(1000)
                    for note in notes_sample:
                        if note and str(note).strip():
                            stats['notes_lengths'].append(len(str(note)))
                            
            except Exception as e:
                logger.error(f"Error en análisis Excel: {e}")
        
        if progress_dialog:
            progress_dialog.update_progress(80, "Finalizando cálculos estadísticos...")
        
        logger.info("Estadísticas calculadas exitosamente")
        return stats
    
    def create_general_stats_tab(self, notebook, stats):
        """Crear pestaña de estadísticas generales"""
        general_frame = tb.Frame(notebook)
        notebook.add(general_frame, text="📊 Resumen General")
        
        # Crear canvas con scrollbar
        canvas = tk.Canvas(general_frame)
        scrollbar = tb.Scrollbar(general_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tb.Frame(canvas)
        
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        
        # Título
        title_frame = tb.Frame(scrollable_frame)
        title_frame.pack(fill="x", padx=20, pady=10)
        tb.Label(title_frame, text="📈 Resumen General del Dataset", 
                font=("Segoe UI", 16, "bold")).pack()
        
        # Estadísticas principales en tarjetas
        cards_frame = tb.Frame(scrollable_frame)
        cards_frame.pack(fill="x", padx=20, pady=10)
        
        # Fila 1 de tarjetas
        row1 = tb.Frame(cards_frame)
        row1.pack(fill="x", pady=5)
        
        # Total de audios
        self.create_stat_card(row1, "🎵", "Total Audios", f"{stats['total_audios']:,}", 
                             "primary", 0, 0)
        
        # Favoritos
        fav_percent = (stats['total_favorites'] / stats['total_audios'] * 100) if stats['total_audios'] > 0 else 0
        self.create_stat_card(row1, "⭐", "Favoritos", f"{stats['total_favorites']:,} ({fav_percent:.1f}%)", 
                             "warning", 0, 1)
        
        # Tamaño total (mejorado con información diagnóstica)
        total_size_mb = stats['total_size'] / (1024 * 1024)
        total_size_gb = stats['total_size'] / (1024 * 1024 * 1024)
        
        if stats['total_size'] > 0:
            size_text = f"{total_size_gb:.1f} GB" if total_size_gb >= 1 else f"{total_size_mb:.1f} MB"
        else:
            # Mostrar información diagnóstica si no hay datos
            processed_count = stats.get('processed_count', 0)
            error_count = stats.get('error_count', 0)
            if processed_count == 0 and error_count > 0:
                size_text = "Error en archivos"
            else:
                size_text = "Sin datos disponibles"
        
        self.create_stat_card(row1, "💾", "Tamaño Total", size_text, "info", 0, 2)
        
        # Fila 2 de tarjetas
        row2 = tb.Frame(cards_frame)
        row2.pack(fill="x", pady=5)
        
        # Duración total (mejorada con información diagnóstica)
        total_duration = sum(stats['duration_list']) if stats['duration_list'] else 0
        total_hours = total_duration / 3600
        
        if total_duration > 0:
            duration_text = f"{total_hours:.1f} horas" if total_hours >= 1 else self.format_time(total_duration)
        else:
            # Mostrar información diagnóstica si no hay datos
            processed_count = stats.get('processed_count', 0)
            if processed_count == 0:
                duration_text = "Sin procesar"
            else:
                duration_text = "Sin duración calculada"
        
        self.create_stat_card(row2, "⏱️", "Duración Total", duration_text, "success", 0, 0)
        
        # Duración promedio (mejorada)
        if stats['duration_list']:
            avg_duration = total_duration / len(stats['duration_list'])
            avg_text = self.format_time(avg_duration)
        else:
            avg_text = "N/A"
        
        self.create_stat_card(row2, "📊", "Duración Promedio", avg_text, "secondary", 0, 1)
        
        # ZIPs cargados
        zip_count = len(stats['zip_sources'])
        self.create_stat_card(row2, "📦", "Archivos ZIP", f"{zip_count} cargados", 
                             "dark", 0, 2)
        
        # Análisis de formatos si hay variedad
        if stats['audio_formats']:
            formats_frame = tb.LabelFrame(scrollable_frame, text="🎵 Formatos de Audio", padding=15)
            formats_frame.pack(fill="x", padx=20, pady=10)
            
            formats_text = ""
            for format_ext, count in sorted(stats['audio_formats'].items(), key=lambda x: x[1], reverse=True):
                percent = (count / stats['total_audios']) * 100
                formats_text += f"{format_ext.upper()}: {count:,} archivos ({percent:.1f}%)\n"
            
            tb.Label(formats_frame, text=formats_text, font=("Consolas", 10), 
                    justify="left").pack(anchor="w")
        
        # Excel info si está disponible
        if self.df_excel is not None:
            excel_frame = tb.LabelFrame(scrollable_frame, text="📋 Información Excel", padding=15)
            excel_frame.pack(fill="x", padx=20, pady=10)
            
            excel_info = f"""
📄 Registros en Excel: {len(self.df_excel):,}
📊 Columnas disponibles: {len(self.df_excel.columns)}
✅ Sesiones con datos Excel: {len(self.df_excel):,} de {stats['total_audios']:,}

Columnas encontradas:
{', '.join(self.df_excel.columns)}
            """
            
            tb.Label(excel_frame, text=excel_info, font=("Segoe UI", 10), 
                    justify="left").pack(anchor="w")
        else:
            no_excel_frame = tb.LabelFrame(scrollable_frame, text="⚠️ Sin Datos Excel", padding=15)
            no_excel_frame.pack(fill="x", padx=20, pady=10)
            
            tb.Label(no_excel_frame, 
                    text="No se ha cargado información Excel. Las estadísticas están basadas únicamente en los archivos de audio.",
                    font=("Segoe UI", 10), justify="left").pack(anchor="w")
        
        # Información diagnóstica del procesamiento de archivos
        diagnostic_frame = tb.LabelFrame(scrollable_frame, text="🔍 Información de Procesamiento", padding=15)
        diagnostic_frame.pack(fill="x", padx=20, pady=10)
        
        processed_count = stats.get('processed_count', 0)
        error_count = stats.get('error_count', 0)
        missing_files = stats.get('missing_files', 0)
        
        diagnostic_info = f"""
✅ Archivos procesados exitosamente: {processed_count:,} de {stats['total_audios']:,}
❌ Errores de procesamiento: {error_count:,}
📂 Archivos no encontrados: {missing_files:,}
📊 Duraciones calculadas: {len(stats['duration_list']):,}
💾 Tamaños calculados: {len(stats['file_sizes']):,}
🎵 Formatos detectados: {len(stats['audio_formats'])}
        """
        
        if processed_count == 0 and stats['total_audios'] > 0:
            diagnostic_info += "\n⚠️ PROBLEMA: No se procesaron archivos. Los archivos pueden haber sido movidos o eliminados."
        elif error_count > processed_count / 2:
            diagnostic_info += f"\n⚠️ ADVERTENCIA: Alto número de errores ({error_count}/{stats['total_audios']})."
        
        tb.Label(diagnostic_frame, text=diagnostic_info, font=("Segoe UI", 10), 
                justify="left").pack(anchor="w")
        
        # Configurar scrolling
        def configure_scroll(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        
        scrollable_frame.bind("<Configure>", configure_scroll)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def create_stat_card(self, parent, icon, title, value, style, row, col):
        """Crear una tarjeta de estadística"""
        card = tb.Frame(parent, bootstyle=f"{style}")
        card.grid(row=row, column=col, padx=10, pady=5, sticky="ew")
        parent.grid_columnconfigure(col, weight=1)
        
        tb.Label(card, text=icon, font=("Segoe UI", 24)).pack(pady=(10, 0))
        tb.Label(card, text=title, font=("Segoe UI", 10, "bold")).pack()
        tb.Label(card, text=value, font=("Segoe UI", 14, "bold")).pack(pady=(0, 10))
    
    def cleanup_matplotlib_figures(self):
        """Limpiar figuras de matplotlib para liberar memoria"""
        try:
            plt.close('all')
            import gc
            gc.collect()
        except Exception as e:
            logger.warning(f"Error limpiando figuras matplotlib: {e}")
    
    def create_modern_chart(self, parent, chart_type, data, title, **kwargs):
        """Crear gráfico moderno optimizado con matplotlib y seaborn"""
        try:
            # Configurar figura con estilo oscuro moderno
            fig, ax = plt.subplots(figsize=kwargs.get('figsize', (8, 5)), facecolor='#2b2b2b')
            ax.set_facecolor('#2b2b2b')
            
            # Colores modernos optimizados
            colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FECA57', '#FF9FF3', '#54A0FF', '#5F27CD']
            
            if chart_type == 'bar':
                labels, values = data
                # Limitar cantidad de barras para evitar sobrecarga visual
                if len(labels) > 15:
                    sorted_data = sorted(zip(labels, values), key=lambda x: x[1], reverse=True)
                    labels, values = zip(*sorted_data[:15])
                    ax.text(0.5, 0.95, f'Mostrando top 15 de {len(data[0])}', 
                           transform=ax.transAxes, ha='center', va='top', 
                           color='yellow', fontsize=9, style='italic')
                
                bars = ax.bar(labels, values, color=colors[:len(labels)], alpha=0.8, 
                            edgecolor='white', linewidth=0.5)
                
                # Agregar valores en las barras
                max_val = max(values) if values else 0
                for bar, value in zip(bars, values):
                    height = bar.get_height()
                    if height > 0:  # Solo mostrar si hay valor
                        ax.text(bar.get_x() + bar.get_width()/2., height + max_val*0.01,
                               f'{int(value)}', ha='center', va='bottom', 
                               color='white', fontweight='bold', fontsize=9)
                
                # Rotar etiquetas si son muchas o muy largas
                if len(labels) > 6 or any(len(str(label)) > 10 for label in labels):
                    plt.setp(ax.get_xticklabels(), rotation=45, ha='right')
                    
            elif chart_type == 'hbar':  # Barras horizontales
                labels, values = data
                if len(labels) > 15:
                    sorted_data = sorted(zip(labels, values), key=lambda x: x[1], reverse=True)
                    labels, values = zip(*sorted_data[:15])
                
                bars = ax.barh(labels, values, color=colors[:len(labels)], alpha=0.8, 
                              edgecolor='white', linewidth=0.5)
                
                # Valores al final de barras
                max_val = max(values) if values else 0
                for bar, value in zip(bars, values):
                    width = bar.get_width()
                    if width > 0:
                        ax.text(width + max_val*0.01, bar.get_y() + bar.get_height()/2.,
                               f'{int(value)}', ha='left', va='center', 
                               color='white', fontweight='bold', fontsize=9)
                    
            elif chart_type == 'pie':
                labels, values = data
                # Limitar sectores para mejor visualización
                if len(labels) > 8:
                    sorted_data = sorted(zip(labels, values), key=lambda x: x[1], reverse=True)
                    labels, values = zip(*sorted_data[:7])
                    labels = list(labels) + ['Otros']
                    values = list(values) + [sum(data[1][7:])]
                
                wedges, texts, autotexts = ax.pie(values, labels=labels, autopct='%1.1f%%', 
                                                 colors=colors[:len(labels)], startangle=90, 
                                                 textprops={'color': 'white', 'fontweight': 'bold', 'fontsize': 9})
                
                # Mejorar las etiquetas
                for autotext in autotexts:
                    autotext.set_color('black')
                    autotext.set_fontweight('bold')
                    autotext.set_fontsize(8)
                    
            elif chart_type == 'line':
                x_data, y_data = data
                ax.plot(x_data, y_data, color=colors[0], linewidth=3, marker='o', 
                       markersize=5, markerfacecolor=colors[1], markeredgecolor='white', markeredgewidth=1)
                ax.fill_between(x_data, y_data, alpha=0.3, color=colors[0])
                
            elif chart_type == 'polar':
                # Gráfico polar para distribución circular (horas)
                angles, values = data
                theta = np.linspace(0.0, 2 * np.pi, len(angles), endpoint=False)
                
                ax.remove()  # Remover axes normal
                ax = fig.add_subplot(111, projection='polar', facecolor='#2b2b2b')
                ax.set_facecolor('#2b2b2b')
                
                bars = ax.bar(theta, values, width=2*np.pi/len(angles), bottom=0.0,
                             color=colors[0], alpha=0.7, edgecolor='white', linewidth=0.5)
                
                # Configurar etiquetas de horas
                ax.set_theta_zero_location('N')
                ax.set_theta_direction(-1)
                ax.set_thetagrids(np.degrees(theta), [f'{int(angle)}h' for angle in angles])
                ax.tick_params(colors='white', labelsize=8)
                ax.grid(True, alpha=0.3, color='gray')
                
            elif chart_type == 'histogram':
                values = data
                if isinstance(values, (list, tuple)) and len(values) > 0:
                    bins = min(kwargs.get('bins', 20), len(values)//2) if len(values) > 10 else 10
                    n, bins, patches = ax.hist(values, bins=bins, color=colors[0], 
                                              alpha=0.7, edgecolor='white', linewidth=0.5)
                    
                    # Colorear barras con gradiente
                    for i, patch in enumerate(patches):
                        patch.set_facecolor(colors[i % len(colors)])
                        
            elif chart_type == 'boxplot':
                values = data if isinstance(data, list) else [data]
                box_parts = ax.boxplot(values, patch_artist=True, 
                                      boxprops=dict(facecolor=colors[0], alpha=0.7),
                                      medianprops=dict(color='white', linewidth=2),
                                      whiskerprops=dict(color='white', linewidth=1.5),
                                      capprops=dict(color='white', linewidth=1.5))
            
            # Estilo general optimizado
            ax.set_title(title, color='white', fontsize=12, fontweight='bold', pad=15)
            ax.tick_params(colors='white', labelsize=9)
            
            # Solo mostrar spines necesarios
            for spine in ax.spines.values():
                spine.set_color('white')
                spine.set_linewidth(0.5)
            
            ax.grid(True, alpha=0.2, color='gray', linewidth=0.5)
            
            # Etiquetas de ejes con mejor formato
            if 'xlabel' in kwargs:
                ax.set_xlabel(kwargs['xlabel'], color='white', fontweight='bold', fontsize=10)
            if 'ylabel' in kwargs:
                ax.set_ylabel(kwargs['ylabel'], color='white', fontweight='bold', fontsize=10)
            
            plt.tight_layout()
            
            # Crear canvas optimizado
            canvas = FigureCanvasTkAgg(fig, master=parent)
            canvas.draw()
            widget = canvas.get_tk_widget()
            widget.pack(fill="both", expand=True, padx=10, pady=10)
            
            return fig, ax, canvas
            
        except Exception as e:
            logger.error(f"Error creando gráfico {chart_type}: {e}")
            # Crear mensaje de error simple
            error_label = tb.Label(parent, text=f"⚠️ Error generando gráfico: {title}", 
                                  foreground="orange", font=("Segoe UI", 10))
            error_label.pack(expand=True, fill="both")
            return None, None, None
    
    def create_temporal_stats_tab(self, notebook, stats):
        """Crear pestaña de análisis temporal con gráficos modernos"""
        temporal_frame = tb.Frame(notebook)
        notebook.add(temporal_frame, text="📅 Análisis Temporal")
        
        # Si no hay datos de Excel, mostrar mensaje
        if not stats['date_stats'] and not stats['hour_stats']:
            tb.Label(temporal_frame, 
                    text="⚠️ No hay datos temporales disponibles\nSe requiere archivo Excel con columna 'Día/Hora de creación'",
                    font=("Segoe UI", 14), justify="center").pack(expand=True)
            return
        
        # Crear canvas con scrollbar
        canvas = tk.Canvas(temporal_frame)
        scrollbar = tb.Scrollbar(temporal_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tb.Frame(canvas)
        
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        
        # Título
        tb.Label(scrollable_frame, text="📊 Análisis Temporal de Sesiones", 
                font=("Segoe UI", 16, "bold")).pack(pady=20)
        
        # Estadísticas por fecha con gráfico
        if stats['date_stats']:
            date_frame = tb.LabelFrame(scrollable_frame, text="📅 Distribución por Fecha", padding=15)
            date_frame.pack(fill="both", expand=True, padx=20, pady=10)
            
            # Crear gráfico de línea temporal
            sorted_dates = sorted(stats['date_stats'].items())
            if len(sorted_dates) > 1:
                import pandas as pd
                df_dates = pd.DataFrame(sorted_dates, columns=['Fecha', 'Sesiones'])
                df_dates['Fecha'] = pd.to_datetime(df_dates['Fecha'])
                
                fig, ax = plt.subplots(figsize=(12, 4), facecolor='#2b2b2b')
                ax.set_facecolor('#2b2b2b')
                
                ax.plot(df_dates['Fecha'], df_dates['Sesiones'], 
                       color='#4ECDC4', linewidth=2, marker='o', markersize=4,
                       markerfacecolor='#FF6B6B', markeredgecolor='white', markeredgewidth=1)
                ax.fill_between(df_dates['Fecha'], df_dates['Sesiones'], alpha=0.3, color='#4ECDC4')
                
                ax.set_title('Actividad de Sesiones por Fecha', color='white', fontsize=14, fontweight='bold', pad=15)
                ax.set_xlabel('Fecha', color='white', fontweight='bold')
                ax.set_ylabel('Número de Sesiones', color='white', fontweight='bold')
                ax.tick_params(colors='white', labelsize=9)
                ax.grid(True, alpha=0.3, color='gray')
                
                # Formatear fechas en el eje X
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
                ax.xaxis.set_major_locator(mdates.WeekdayLocator())
                plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
                
                # Estilizar spines
                for spine in ax.spines.values():
                    spine.set_color('white')
                
                plt.tight_layout()
                
                # Agregar al frame
                canvas_dates = FigureCanvasTkAgg(fig, master=date_frame)
                canvas_dates.draw()
                canvas_dates.get_tk_widget().pack(fill="both", expand=True, pady=10)
            
            # Estadísticas textuales
            stats_text = f"""
📈 Período analizado: {min(stats['date_stats'].keys())} a {max(stats['date_stats'].keys())}
📊 Total de días con actividad: {len(stats['date_stats'])}
🔥 Promedio diario: {sum(stats['date_stats'].values()) / len(stats['date_stats']):.1f} sesiones
🏆 Día más activo: {max(stats['date_stats'].items(), key=lambda x: x[1])[0]} ({max(stats['date_stats'].values())} sesiones)
            """
            tb.Label(date_frame, text=stats_text, font=("Segoe UI", 10), 
                    justify="left", foreground="white").pack(anchor="w", pady=10)
        
        # Estadísticas por hora del día con gráfico polar
        if stats['hour_stats']:
            hour_frame = tb.LabelFrame(scrollable_frame, text="🕐 Distribución por Hora del Día", padding=15)
            hour_frame.pack(fill="both", expand=True, padx=20, pady=10)
            
            # Preparar datos para gráfico polar (reloj de 24 horas)
            hours = list(range(24))
            values = [stats['hour_stats'].get(h, 0) for h in hours]
            
            fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(projection='polar'), facecolor='#2b2b2b')
            ax.set_facecolor('#2b2b2b')
            
            # Convertir horas a radianes
            theta = [h * 2 * np.pi / 24 for h in hours]
            
            # Crear gráfico de barras polar
            bars = ax.bar(theta, values, width=0.2, alpha=0.8)
            
            # Colorear barras con gradiente
            colors = plt.cm.plasma(np.linspace(0, 1, len(bars)))
            for bar, color in zip(bars, colors):
                bar.set_facecolor(color)
                bar.set_edgecolor('white')
                bar.set_linewidth(0.5)
            
            # Configurar etiquetas
            ax.set_theta_zero_location('N')
            ax.set_theta_direction(-1)
            ax.set_thetagrids(range(0, 360, 15), [f'{h:02d}:00' for h in range(0, 24, 1)])
            ax.set_title('Distribución de Sesiones por Hora', color='white', fontsize=14, 
                        fontweight='bold', pad=20)
            ax.tick_params(colors='white')
            ax.grid(True, alpha=0.3, color='gray')
            
            plt.tight_layout()
            
            canvas_hours = FigureCanvasTkAgg(fig, master=hour_frame)
            canvas_hours.draw()
            canvas_hours.get_tk_widget().pack(fill="both", expand=True, pady=10)
            
            # Top horas más activas
            top_hours = sorted(stats['hour_stats'].items(), key=lambda x: x[1], reverse=True)[:5]
            hours_text = "🏆 Top 5 horas más activas:\n"
            for hour, count in top_hours:
                hours_text += f"   {hour:02d}:00 - {count} sesiones\n"
            
            tb.Label(hour_frame, text=hours_text, font=("Segoe UI", 10), 
                    justify="left", foreground="white").pack(anchor="w", pady=10)
        
        # Estadísticas por día de la semana con gráfico de barras moderno
        if stats['weekday_stats']:
            weekday_frame = tb.LabelFrame(scrollable_frame, text="📅 Distribución por Día de la Semana", padding=15)
            weekday_frame.pack(fill="both", expand=True, padx=20, pady=10)
            
            # Ordenar días de la semana
            weekday_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            weekday_spanish = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
            
            weekday_data = []
            for eng_day, esp_day in zip(weekday_order, weekday_spanish):
                count = stats['weekday_stats'].get(eng_day, 0)
                weekday_data.append((esp_day, count))
            
            # Crear gráfico de barras horizontal moderno
            fig, ax = plt.subplots(figsize=(10, 6), facecolor='#2b2b2b')
            ax.set_facecolor('#2b2b2b')
            
            days, counts = zip(*weekday_data)
            colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FECA57', '#FF9FF3', '#54A0FF']
            
            bars = ax.barh(days, counts, color=colors, alpha=0.8, edgecolor='white', linewidth=1)
            
            # Agregar valores en las barras
            for bar, count in zip(bars, counts):
                if count > 0:
                    ax.text(bar.get_width() + max(counts)*0.01, bar.get_y() + bar.get_height()/2,
                           f'{count}', ha='left', va='center', color='white', fontweight='bold')
            
            ax.set_title('Distribución de Sesiones por Día de la Semana', 
                        color='white', fontsize=14, fontweight='bold', pad=15)
            ax.set_xlabel('Número de Sesiones', color='white', fontweight='bold')
            ax.tick_params(colors='white', labelsize=10)
            ax.grid(True, alpha=0.3, color='gray', axis='x')
            
            # Estilizar spines
            for spine in ax.spines.values():
                spine.set_color('white')
            
            plt.tight_layout()
            
            canvas_weekdays = FigureCanvasTkAgg(fig, master=weekday_frame)
            canvas_weekdays.draw()
            canvas_weekdays.get_tk_widget().pack(fill="both", expand=True, pady=10)
        
        # Configurar scrolling
        def configure_scroll(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        
        scrollable_frame.bind("<Configure>", configure_scroll)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def create_duration_stats_tab(self, notebook, stats):
        """Crear pestaña de análisis de duración con gráficos modernos"""
        duration_frame = tb.Frame(notebook)
        notebook.add(duration_frame, text="⏱️ Análisis de Duración")
        
        if not stats['duration_list']:
            tb.Label(duration_frame, 
                    text="⚠️ No hay datos de duración disponibles",
                    font=("Segoe UI", 14), justify="center").pack(expand=True)
            return
        
        # Crear canvas con scrollbar
        canvas = tk.Canvas(duration_frame)
        scrollbar = tb.Scrollbar(duration_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tb.Frame(canvas)
        
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        
        # Título
        tb.Label(scrollable_frame, text="⏱️ Análisis Detallado de Duración", 
                font=("Segoe UI", 16, "bold")).pack(pady=20)
        
        # Estadísticas básicas de duración
        durations = stats['duration_list']
        total_duration = sum(durations)
        avg_duration = total_duration / len(durations)
        min_duration = min(durations)
        max_duration = max(durations)
        median_duration = sorted(durations)[len(durations)//2]
        
        basic_frame = tb.LabelFrame(scrollable_frame, text="📊 Estadísticas Básicas", padding=15)
        basic_frame.pack(fill="x", padx=20, pady=10)
        
        basic_text = f"""
🎵 Total de audios procesados: {len(durations):,}
⏱️ Duración total: {self.format_time(total_duration)} ({total_duration/3600:.1f} horas)
📊 Duración promedio: {self.format_time(avg_duration)}
📈 Duración mediana: {self.format_time(median_duration)}
⏳ Duración mínima: {self.format_time(min_duration)}
⏰ Duración máxima: {self.format_time(max_duration)}
📏 Rango: {self.format_time(max_duration - min_duration)}
        """
        
        tb.Label(basic_frame, text=basic_text, font=("Consolas", 10), 
                justify="left").pack(anchor="w")
        
        # Histograma de distribución de duraciones
        hist_frame = tb.LabelFrame(scrollable_frame, text="📊 Distribución de Duraciones", padding=15)
        hist_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        fig, ax = plt.subplots(figsize=(12, 6), facecolor='#2b2b2b')
        ax.set_facecolor('#2b2b2b')
        
        # Crear histograma con colores modernos
        n, bins, patches = ax.hist(durations, bins=30, alpha=0.8, edgecolor='white', linewidth=0.5)
        
        # Colorear barras con gradiente
        colors = plt.cm.viridis(np.linspace(0, 1, len(patches)))
        for patch, color in zip(patches, colors):
            patch.set_facecolor(color)
        
        # Agregar líneas de estadísticas
        ax.axvline(avg_duration, color='#FF6B6B', linestyle='--', linewidth=2, 
                  label=f'Promedio: {self.format_time(avg_duration)}')
        ax.axvline(median_duration, color='#4ECDC4', linestyle='--', linewidth=2,
                  label=f'Mediana: {self.format_time(median_duration)}')
        
        ax.set_title('Distribución de Duraciones de Audios', color='white', fontsize=14, fontweight='bold', pad=15)
        ax.set_xlabel('Duración (segundos)', color='white', fontweight='bold')
        ax.set_ylabel('Frecuencia', color='white', fontweight='bold')
        ax.tick_params(colors='white', labelsize=10)
        ax.grid(True, alpha=0.3, color='gray')
        ax.legend(loc='upper right', facecolor='#2b2b2b', edgecolor='white')
        
        # Estilizar spines
        for spine in ax.spines.values():
            spine.set_color('white')
        
        plt.tight_layout()
        
        canvas_hist = FigureCanvasTkAgg(fig, master=hist_frame)
        canvas_hist.draw()
        canvas_hist.get_tk_widget().pack(fill="both", expand=True, pady=10)
        
        # Distribución por rangos con gráfico de barras moderno
        ranges_frame = tb.LabelFrame(scrollable_frame, text="📈 Distribución por Rangos", padding=15)
        ranges_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Definir rangos (en segundos)
        ranges = [
            (0, 30, "0-30 seg\n(Muy corto)"),
            (30, 60, "30s-1min\n(Corto)"),
            (60, 180, "1-3 min\n(Normal)"),
            (180, 300, "3-5 min\n(Medio)"),
            (300, 600, "5-10 min\n(Largo)"),
            (600, 1800, "10-30 min\n(Muy largo)"),
            (1800, float('inf'), "+30 min\n(Extremo)")
        ]
        
        range_counts = {}
        for min_dur, max_dur, label in ranges:
            count = sum(1 for d in durations if min_dur <= d < max_dur)
            range_counts[label] = count
        
        # Crear gráfico de barras de rangos
        fig2, ax2 = plt.subplots(figsize=(12, 6), facecolor='#2b2b2b')
        ax2.set_facecolor('#2b2b2b')
        
        labels = list(range_counts.keys())
        counts = list(range_counts.values())
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FECA57', '#FF9FF3', '#54A0FF']
        
        bars = ax2.bar(labels, counts, color=colors[:len(labels)], alpha=0.8, 
                      edgecolor='white', linewidth=1)
        
        # Agregar valores en las barras
        for bar, count in zip(bars, counts):
            if count > 0:
                height = bar.get_height()
                ax2.text(bar.get_x() + bar.get_width()/2., height + max(counts)*0.01,
                        f'{count}\n({count/len(durations)*100:.1f}%)', 
                        ha='center', va='bottom', color='white', fontweight='bold', fontsize=9)
        
        ax2.set_title('Distribución por Rangos de Duración', color='white', fontsize=14, fontweight='bold', pad=15)
        ax2.set_xlabel('Rangos de Duración', color='white', fontweight='bold')
        ax2.set_ylabel('Cantidad de Audios', color='white', fontweight='bold')
        ax2.tick_params(colors='white', labelsize=9)
        ax2.grid(True, alpha=0.3, color='gray', axis='y')
        
        # Rotar etiquetas para mejor lectura
        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        # Estilizar spines
        for spine in ax2.spines.values():
            spine.set_color('white')
        
        plt.tight_layout()
        
        canvas_ranges = FigureCanvasTkAgg(fig2, master=ranges_frame)
        canvas_ranges.draw()
        canvas_ranges.get_tk_widget().pack(fill="both", expand=True, pady=10)
        
        # Análisis de outliers con box plot
        outliers_frame = tb.LabelFrame(scrollable_frame, text="🔍 Análisis de Valores Atípicos", padding=15)
        outliers_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Calcular cuartiles
        sorted_durations = sorted(durations)
        q1 = sorted_durations[len(sorted_durations)//4]
        q3 = sorted_durations[3*len(sorted_durations)//4]
        iqr = q3 - q1
        
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        
        outliers_low = [d for d in durations if d < lower_bound]
        outliers_high = [d for d in durations if d > upper_bound]
        
        # Crear box plot moderno
        fig3, ax3 = plt.subplots(figsize=(12, 4), facecolor='#2b2b2b')
        ax3.set_facecolor('#2b2b2b')
        
        box = ax3.boxplot(durations, vert=False, patch_artist=True, 
                         boxprops=dict(facecolor='#4ECDC4', alpha=0.8),
                         medianprops=dict(color='#FF6B6B', linewidth=2),
                         whiskerprops=dict(color='white'),
                         capprops=dict(color='white'),
                         flierprops=dict(marker='o', markerfacecolor='#FECA57', markersize=4))
        
        ax3.set_title('Box Plot - Análisis de Valores Atípicos', color='white', fontsize=14, fontweight='bold', pad=15)
        ax3.set_xlabel('Duración (segundos)', color='white', fontweight='bold')
        ax3.tick_params(colors='white', labelsize=10)
        ax3.grid(True, alpha=0.3, color='gray', axis='x')
        
        # Agregar líneas de referencia
        ax3.axvline(q1, color='#96CEB4', linestyle=':', alpha=0.7, label=f'Q1: {self.format_time(q1)}')
        ax3.axvline(median_duration, color='#FF6B6B', linestyle=':', alpha=0.7, label=f'Mediana: {self.format_time(median_duration)}')
        ax3.axvline(q3, color='#96CEB4', linestyle=':', alpha=0.7, label=f'Q3: {self.format_time(q3)}')
        
        ax3.legend(loc='upper right', facecolor='#2b2b2b', edgecolor='white')
        
        # Estilizar spines
        for spine in ax3.spines.values():
            spine.set_color('white')
        
        plt.tight_layout()
        
        canvas_outliers = FigureCanvasTkAgg(fig3, master=outliers_frame)
        canvas_outliers.draw()
        canvas_outliers.get_tk_widget().pack(fill="both", expand=True, pady=10)
        
        # Estadísticas de outliers
        outliers_text = f"""
📊 Análisis de cuartiles:
   Q1 (25%): {self.format_time(q1)}
   Q2 (50%): {self.format_time(median_duration)}
   Q3 (75%): {self.format_time(q3)}
   IQR: {self.format_time(iqr)}

🔍 Valores atípicos:
   Límite inferior: {self.format_time(lower_bound)}
   Límite superior: {self.format_time(upper_bound)}
   Audios muy cortos: {len(outliers_low)} ({len(outliers_low)/len(durations)*100:.1f}%)
   Audios muy largos: {len(outliers_high)} ({len(outliers_high)/len(durations)*100:.1f}%)
        """
        
        if outliers_high:
            outliers_text += f"\n🎵 Top 5 audios más largos:\n"
            for i, duration in enumerate(sorted(outliers_high, reverse=True)[:5]):
                outliers_text += f"   {i+1}. {self.format_time(duration)}\n"
        
        tb.Label(outliers_frame, text=outliers_text, font=("Consolas", 10), 
                justify="left").pack(anchor="w", pady=10)
        
        # Configurar scrolling
        def configure_scroll(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        
        scrollable_frame.bind("<Configure>", configure_scroll)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def create_content_stats_tab(self, notebook, stats):
        """Crear pestaña de análisis de contenido con gráficos modernos"""
        content_frame = tb.Frame(notebook)
        notebook.add(content_frame, text="📝 Análisis de Contenido")
        
        # Crear canvas con scrollbar
        canvas = tk.Canvas(content_frame)
        scrollbar = tb.Scrollbar(content_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tb.Frame(canvas)
        
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        
        # Título
        tb.Label(scrollable_frame, text="📋 Análisis de Contenido Excel", 
                font=("Segoe UI", 16, "bold")).pack(pady=20)
        
        # Análisis de abonados con gráfico moderno
        if stats['subscriber_stats']:
            subs_frame = tb.LabelFrame(scrollable_frame, text="👥 Top Abonados por Actividad", padding=15)
            subs_frame.pack(fill="both", expand=True, padx=20, pady=10)
            
            # Top 10 abonados para el gráfico
            top_subs = sorted(stats['subscriber_stats'].items(), key=lambda x: x[1], reverse=True)[:10]
            
            if top_subs:
                # Crear gráfico de barras horizontal moderno
                fig, ax = plt.subplots(figsize=(12, 8), facecolor='#2b2b2b')
                ax.set_facecolor('#2b2b2b')
                
                subscribers, counts = zip(*top_subs)
                y_pos = range(len(subscribers))
                
                # Usar una paleta de colores moderna
                colors = plt.cm.Set3(np.linspace(0, 1, len(subscribers)))
                
                bars = ax.barh(y_pos, counts, color=colors, alpha=0.8, edgecolor='white', linewidth=1)
                
                # Agregar valores en las barras
                for i, (bar, count) in enumerate(zip(bars, counts)):
                    ax.text(bar.get_width() + max(counts)*0.01, bar.get_y() + bar.get_height()/2,
                           f'{count}', ha='left', va='center', color='white', fontweight='bold')
                
                # Truncar nombres largos para mejor visualización
                display_names = []
                for sub in subscribers:
                    if len(str(sub)) > 25:
                        display_names.append(str(sub)[:22] + "...")
                    else:
                        display_names.append(str(sub))
                
                ax.set_yticks(y_pos)
                ax.set_yticklabels(display_names)
                ax.set_title('Top 10 Abonados con Mayor Actividad', color='white', 
                           fontsize=14, fontweight='bold', pad=15)
                ax.set_xlabel('Número de Sesiones', color='white', fontweight='bold')
                ax.tick_params(colors='white', labelsize=9)
                ax.grid(True, alpha=0.3, color='gray', axis='x')
                
                # Estilizar spines
                for spine in ax.spines.values():
                    spine.set_color('white')
                
                plt.tight_layout()
                
                canvas_subs = FigureCanvasTkAgg(fig, master=subs_frame)
                canvas_subs.draw()
                canvas_subs.get_tk_widget().pack(fill="both", expand=True, pady=10)
            
            # Estadísticas textuales
            stats_text = f"Total de abonados únicos: {len(stats['subscriber_stats'])}"
            tb.Label(subs_frame, text=stats_text, font=("Segoe UI", 10), 
                    justify="left", foreground="white").pack(anchor="w", pady=5)
        
        # Análisis de DDR con gráfico de pastel
        if stats['ddr_stats']:
            ddr_frame = tb.LabelFrame(scrollable_frame, text="📞 Análisis de DDR", padding=15)
            ddr_frame.pack(fill="both", expand=True, padx=20, pady=10)
            
            # Top 8 DDRs para el gráfico de pastel
            top_ddrs = sorted(stats['ddr_stats'].items(), key=lambda x: x[1], reverse=True)[:8]
            
            if top_ddrs:
                # Calcular "Otros" si hay más de 8 DDRs
                other_count = sum(count for ddr, count in stats['ddr_stats'].items() 
                                if (ddr, count) not in top_ddrs)
                
                if other_count > 0:
                    ddrs, counts = zip(*top_ddrs)
                    ddrs = list(ddrs) + ["Otros"]
                    counts = list(counts) + [other_count]
                else:
                    ddrs, counts = zip(*top_ddrs)
                
                # Crear gráfico de pastel moderno
                fig, ax = plt.subplots(figsize=(10, 8), facecolor='#2b2b2b')
                ax.set_facecolor('#2b2b2b')
                
                colors = plt.cm.Set3(np.linspace(0, 1, len(ddrs)))
                
                # Función para mostrar porcentajes solo si son significativos
                def autopct_func(pct):
                    return f'{pct:.1f}%' if pct > 2 else ''
                
                wedges, texts, autotexts = ax.pie(counts, labels=ddrs, autopct=autopct_func,
                                                startangle=90, colors=colors,
                                                textprops={'color': 'white', 'fontsize': 9})
                
                # Mejorar las etiquetas de porcentaje
                for autotext in autotexts:
                    autotext.set_color('black')
                    autotext.set_fontweight('bold')
                    autotext.set_fontsize(10)
                
                ax.set_title('Distribución de DDRs', color='white', fontsize=14, 
                           fontweight='bold', pad=20)
                
                plt.tight_layout()
                
                canvas_ddr = FigureCanvasTkAgg(fig, master=ddr_frame)
                canvas_ddr.draw()
                canvas_ddr.get_tk_widget().pack(fill="both", expand=True, pady=10)
            
            # Estadísticas textuales
            stats_text = f"Total de DDRs únicos: {len(stats['ddr_stats'])}"
            tb.Label(ddr_frame, text=stats_text, font=("Segoe UI", 10), 
                    justify="left", foreground="white").pack(anchor="w", pady=5)
        
        # Análisis de transcripciones con histograma
        if stats['transcription_lengths']:
            trans_frame = tb.LabelFrame(scrollable_frame, text="📝 Análisis de Transcripciones", padding=15)
            trans_frame.pack(fill="both", expand=True, padx=20, pady=10)
            
            trans_lengths = stats['transcription_lengths']
            
            # Crear histograma de longitudes de transcripción
            fig, ax = plt.subplots(figsize=(12, 6), facecolor='#2b2b2b')
            ax.set_facecolor('#2b2b2b')
            
            # Calcular bins apropiados
            max_length = max(trans_lengths)
            bins = min(30, max_length // 50) if max_length > 100 else 20
            
            n, bins_edges, patches = ax.hist(trans_lengths, bins=bins, alpha=0.8, 
                                           edgecolor='white', linewidth=0.5)
            
            # Colorear barras con gradiente
            colors = plt.cm.viridis(np.linspace(0, 1, len(patches)))
            for patch, color in zip(patches, colors):
                patch.set_facecolor(color)
            
            # Agregar líneas de estadísticas
            avg_length = sum(trans_lengths) / len(trans_lengths)
            median_length = sorted(trans_lengths)[len(trans_lengths)//2]
            
            ax.axvline(avg_length, color='#FF6B6B', linestyle='--', linewidth=2,
                      label=f'Promedio: {avg_length:.0f} chars')
            ax.axvline(median_length, color='#4ECDC4', linestyle='--', linewidth=2,
                      label=f'Mediana: {median_length} chars')
            
            ax.set_title('Distribución de Longitud de Transcripciones', 
                        color='white', fontsize=14, fontweight='bold', pad=15)
            ax.set_xlabel('Longitud (caracteres)', color='white', fontweight='bold')
            ax.set_ylabel('Frecuencia', color='white', fontweight='bold')
            ax.tick_params(colors='white', labelsize=10)
            ax.grid(True, alpha=0.3, color='gray')
            ax.legend(loc='upper right', facecolor='#2b2b2b', edgecolor='white')
            
            # Estilizar spines
            for spine in ax.spines.values():
                spine.set_color('white')
            
            plt.tight_layout()
            
            canvas_trans = FigureCanvasTkAgg(fig, master=trans_frame)
            canvas_trans.draw()
            canvas_trans.get_tk_widget().pack(fill="both", expand=True, pady=10)
            
            # Estadísticas textuales
            trans_text = f"""
📊 Total con transcripción: {len(trans_lengths)}
📈 Longitud promedio: {avg_length:.0f} caracteres
📊 Rango: {min(trans_lengths)} - {max(trans_lengths)} caracteres
            """
            tb.Label(trans_frame, text=trans_text, font=("Segoe UI", 10), 
                    justify="left", foreground="white").pack(anchor="w", pady=5)
        
        # Análisis de notas
        if stats['notes_lengths']:
            notes_frame = tb.LabelFrame(scrollable_frame, text="📋 Análisis de Notas", padding=15)
            notes_frame.pack(fill="x", padx=20, pady=10)
            
            notes_lengths = stats['notes_lengths']
            avg_length = sum(notes_lengths) / len(notes_lengths)
            
            notes_text = f"""
📝 Registros con notas: {len(notes_lengths)}
📊 Longitud promedio: {avg_length:.0f} caracteres
📏 Nota más corta: {min(notes_lengths)} caracteres
📏 Nota más larga: {max(notes_lengths)} caracteres
            """
            
            tb.Label(notes_frame, text=notes_text, font=("Segoe UI", 10), 
                    justify="left", foreground="white").pack(anchor="w")
        
        # Si no hay datos de contenido
        if not any([stats['subscriber_stats'], stats['ddr_stats'], stats['transcription_lengths']]):
            tb.Label(scrollable_frame, 
                    text="⚠️ No hay datos de contenido disponibles\nSe requiere archivo Excel con datos adicionales",
                    font=("Segoe UI", 12), justify="center").pack(pady=50)
        
        # Configurar scrolling
        def configure_scroll(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        
    
    def create_favorites_stats_tab(self, notebook, stats):
        """Crear pestaña de análisis de favoritos"""
        fav_frame = tb.Frame(notebook)
        notebook.add(fav_frame, text="⭐ Análisis de Favoritos")
        
        if not self.favorites:
            tb.Label(fav_frame, 
                    text="⭐ No tienes favoritos marcados\nSelecciona audios y márcalos como favoritos para ver estadísticas",
                    font=("Segoe UI", 14), justify="center").pack(expand=True)
            return
        
        # Crear canvas con scrollbar
        canvas = tk.Canvas(fav_frame)
        scrollbar = tb.Scrollbar(fav_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tb.Frame(canvas)
        
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        
        # Título
        tb.Label(scrollable_frame, text="⭐ Análisis de Favoritos", 
                font=("Segoe UI", 16, "bold")).pack(pady=20)
        
        # Estadísticas básicas de favoritos
        basic_frame = tb.LabelFrame(scrollable_frame, text="📊 Resumen de Favoritos", padding=15)
        basic_frame.pack(fill="x", padx=20, pady=10)
        
        fav_percentage = (len(self.favorites) / len(self.audio_files)) * 100 if self.audio_files else 0
        
        basic_text = f"""
⭐ Total de favoritos: {len(self.favorites):,}
📊 Porcentaje del dataset: {fav_percentage:.1f}%
🎵 Total de audios: {len(self.audio_files):,}
📈 Ratio favoritos/total: 1 de cada {int(len(self.audio_files)/len(self.favorites)) if self.favorites else 0} audios
        """
        
        tb.Label(basic_frame, text=basic_text, font=("Consolas", 11), 
                justify="left").pack(anchor="w")
        
        # Análisis de duración de favoritos
        fav_durations = []
        fav_files = []
        
        for audio_path in self.audio_files:
            filename = os.path.basename(audio_path)
            session_id = self.get_session_id_from_filename(filename)
            if session_id in self.favorites:
                fav_files.append(filename)
                try:
                    segment = AudioSegment.from_file(audio_path)
                    duration = len(segment) / 1000.0
                    fav_durations.append(duration)
                except:
                    continue
        
        if fav_durations:
            duration_frame = tb.LabelFrame(scrollable_frame, text="⏱️ Duración de Favoritos", padding=15)
            duration_frame.pack(fill="x", padx=20, pady=10)
            
            fav_total_duration = sum(fav_durations)
            fav_avg_duration = fav_total_duration / len(fav_durations)
            all_avg_duration = sum(stats['duration_list']) / len(stats['duration_list']) if stats['duration_list'] else 0
            
            duration_text = f"""
⏱️ Duración total de favoritos: {self.format_time(fav_total_duration)}
📊 Duración promedio de favoritos: {self.format_time(fav_avg_duration)}
📈 Duración promedio general: {self.format_time(all_avg_duration)}
🔍 Diferencia: {self.format_time(abs(fav_avg_duration - all_avg_duration))} {'(más largo)' if fav_avg_duration > all_avg_duration else '(más corto)'}
            """
            
            tb.Label(duration_frame, text=duration_text, font=("Consolas", 10), 
                    justify="left").pack(anchor="w")
        
        # Lista de favoritos recientes
        list_frame = tb.LabelFrame(scrollable_frame, text="📋 Lista de Favoritos", padding=15)
        list_frame.pack(fill="x", padx=20, pady=10)
        
        # Mostrar primeros 20 favoritos
        fav_list_text = f"Últimos {min(20, len(fav_files))} favoritos marcados:\n" + "="*50 + "\n"
        
        for i, filename in enumerate(fav_files[:20]):
            session_id = self.get_session_id_from_filename(filename)
            # Obtener info adicional si hay Excel
            extra_info = ""
            if self.df_excel is not None and session_id:
                fila = self.df_excel[self.df_excel["Id de sesión"].astype(str) == session_id]
                if not fila.empty:
                    if 'Nombre abonado' in self.df_excel.columns:
                        subscriber = fila.iloc[0]['Nombre abonado']
                        if pd.notna(subscriber):
                            extra_info = f" - {str(subscriber)[:30]}"
            
            fav_list_text += f"{i+1:2d}. {session_id}{extra_info}\n"
        
        if len(fav_files) > 20:
            fav_list_text += f"\n... y {len(fav_files) - 20} favoritos más"
        
        tb.Label(list_frame, text=fav_list_text, font=("Consolas", 9), 
                justify="left").pack(anchor="w")
        
        # Configurar scrolling
        def configure_scroll(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        
        scrollable_frame.bind("<Configure>", configure_scroll)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

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
            # Mostrar diálogo más informativo con opciones
            result = messagebox.askyesnocancel(
                "Sin archivo Excel", 
                "No se ha encontrado ningún archivo Excel en los ZIPs cargados.\n\n"
                "¿Desea cargar un archivo Excel externo?\n\n"
                "• SÍ: Buscar archivo Excel en su equipo\n"
                "• NO: Ver información básica de archivos de audio\n"
                "• CANCELAR: Cerrar este diálogo"
            )
            
            if result is True:  # YES - cargar Excel externo
                self.load_external_excel()
                return
            elif result is False:  # NO - mostrar info básica
                self.show_basic_audio_info()
                return
            else:  # CANCEL
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

    # =================== FUNCIONES PARA WAVEFORM ===================
    
    def clear_waveform(self):
        """Limpiar el display del waveform"""
        self.waveform_ax.clear()
        self.waveform_ax.set_xlim(0, 100)
        self.waveform_ax.set_ylim(-1, 1)
        self.waveform_ax.set_xlabel('Tiempo', color='white')
        self.waveform_ax.set_ylabel('Amplitud', color='white')
        self.waveform_ax.set_title('Solo se muestran waveforms reales - Selecciona un audio compatible', color='white')
        self.waveform_ax.tick_params(colors='white')
        self.waveform_ax.text(50, 0, 'Solo waveforms reales (librosa/pydub)\nNo se generan waveforms sintéticos', 
                            ha='center', va='center', color='gray', fontsize=11)
        self.waveform_canvas.draw()
    
    def generate_waveform(self, audio_path):
        """Generar datos del waveform para un archivo de audio usando librosa"""
        try:
            logger.info(f"Generando waveform para: {os.path.basename(audio_path)}")
            
            # Verificar si librosa está disponible y cargar el audio
            if LIBROSA_AVAILABLE and librosa is not None:
                try:
                    # Cargar audio con librosa
                    y, sr = librosa.load(audio_path, sr=None, mono=True)
                    
                    # Calcular duración
                    duration = len(y) / sr
                    
                    # Reducir muestreo para mejor rendimiento visual
                    target_samples = 3000  # Más puntos para mejor calidad
                    if len(y) > target_samples:
                        step = len(y) // target_samples
                        samples = y[::step]
                    else:
                        samples = y
                    
                    # Normalizar
                    if len(samples) > 0:
                        max_val = np.max(np.abs(samples))
                        if max_val > 0:
                            samples = samples / max_val
                    
                    # Crear eje de tiempo
                    time_axis = np.linspace(0, duration, len(samples))
                    
                    self.waveform_data = {
                        'samples': samples,
                        'time': time_axis,
                        'duration': duration,
                        'sample_rate': sr,
                        'method': 'librosa'
                    }
                    
                    logger.info(f"Waveform generado exitosamente: {len(samples)} muestras, {duration:.2f}s")
                    return True
                    
                except Exception as e:
                    logger.warning(f"librosa falló: {e}, intentando con pydub...")
            else:
                logger.info("librosa no disponible, usando pydub...")
            
            # Fallback a pydub si librosa falla o no está disponible
            try:
                audio = AudioSegment.from_file(audio_path)
                
                # Convertir a mono si es estéreo
                if audio.channels > 1:
                    audio = audio.set_channels(1)
                
                # Obtener datos raw
                samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
                
                # Normalizar
                if len(samples) > 0:
                    max_val = np.max(np.abs(samples))
                    if max_val > 0:
                        samples = samples / max_val
                
                # Reducir muestreo para mejor rendimiento visual
                target_samples = 2000
                if len(samples) > target_samples:
                    step = len(samples) // target_samples
                    samples = samples[::step]
                
                # Crear eje de tiempo
                duration = len(audio) / 1000.0
                time_axis = np.linspace(0, duration, len(samples))
                
                self.waveform_data = {
                    'samples': samples,
                    'time': time_axis,
                    'duration': duration,
                    'method': 'pydub'
                }
                
                logger.info(f"Waveform generado con pydub: {len(samples)} muestras, {duration:.2f}s")
                return True
                
            except Exception as e2:
                logger.warning(f"pydub también falló: {e2}")
                logger.info("No se pudo generar waveform real - no se mostrará waveform sintético")
                return False
            
        except Exception as e:
            logger.error(f"Error generando waveform: {e}")
            return False
    
    def update_waveform_display(self):
        """Actualizar la visualización del waveform"""
        if not self.waveform_data:
            self.clear_waveform()
            return
        
        self.waveform_ax.clear()
        
        # Elegir color basado en el método usado
        method = self.waveform_data.get('method', 'unknown')
        if method == 'librosa':
            color = '#00ff41'  # Verde brillante para waveform real
            alpha = 0.9
            linewidth = 0.8
        elif method == 'pydub':
            color = '#41a7ff'  # Azul para pydub
            alpha = 0.8
            linewidth = 0.8
        else:
            # No mostrar waveform sintético
            self.clear_waveform()
            return
        
        # Plotear waveform
        self.waveform_ax.plot(self.waveform_data['time'], self.waveform_data['samples'], 
                            color=color, linewidth=linewidth, alpha=alpha)
        
        # Configurar ejes
        self.waveform_ax.set_xlim(0, self.waveform_data['duration'])
        self.waveform_ax.set_ylim(-1.1, 1.1)
        self.waveform_ax.set_xlabel('Tiempo (segundos)', color='white', fontsize=9)
        self.waveform_ax.set_ylabel('Amplitud', color='white', fontsize=9)
        self.waveform_ax.tick_params(colors='white', labelsize=8)
        self.waveform_ax.grid(True, alpha=0.3, color='gray')
        
        # Mostrar posición actual
        if hasattr(self, 'audio_position') and self.audio_position > 0:
            self.waveform_ax.axvline(x=self.audio_position, color='red', linewidth=2, alpha=0.8)
        
        # Mostrar marcadores
        self.update_markers_on_waveform()
        
        # Configurar el título con información del método
        filename = os.path.basename(self.current_audio) if self.current_audio else "Audio"
        
        method_info = {
            'librosa': '✓ Waveform Real (librosa)',
            'pydub': '✓ Waveform Real (pydub)'
        }
        
        title = f'{filename} ({method_info.get(method, "Waveform Real")})'
        self.waveform_ax.set_title(title, color='white', fontsize=10)
        
        self.waveform_canvas.draw()
    
    def update_markers_on_waveform(self):
        """Actualizar marcadores en el waveform"""
        # Limpiar marcadores anteriores
        for line in self.marker_lines:
            line.remove()
        self.marker_lines.clear()
        
        # Dibujar marcadores actuales
        if hasattr(self, 'current_markers'):
            for marker in self.current_markers:
                line = self.waveform_ax.axvline(x=marker['position'], color='yellow', 
                                              linewidth=1.5, alpha=0.7, linestyle='--')
                self.marker_lines.append(line)
                
                # Agregar etiqueta del marcador
                self.waveform_ax.text(marker['position'], 0.9, marker['label'], 
                                    rotation=90, color='yellow', fontsize=8, 
                                    verticalalignment='bottom')
    
    def on_waveform_click(self, event):
        """Manejar clic en el waveform para seek"""
        if event.inaxes != self.waveform_ax or not self.current_audio:
            return
        
        if self.waveform_data and event.xdata:
            # Calcular posición de tiempo basada en el clic
            clicked_time = event.xdata
            if 0 <= clicked_time <= self.waveform_data['duration']:
                self.seek_to_position(clicked_time)
                self.update_waveform_display()
    
    def toggle_waveform(self):
        """Mostrar/ocultar waveform"""
        if self.show_waveform:
            self.waveform_frame.pack_forget()
            self.show_waveform = False
        else:
            self.waveform_frame.pack(fill="both", expand=True, pady=(5, 0))
            self.show_waveform = True
    
    # =================== FUNCIONES PARA MARCADORES ===================
    
    def add_marker(self):
        """Agregar marcador en la posición actual"""
        if not self.current_audio:
            messagebox.showwarning("Advertencia", "No hay audio reproduciendo")
            return
        
        # Obtener ID de sesión
        current_idx = self.listbox.curselection()[0] if self.listbox.curselection() else None
        if current_idx is None:
            return
        
        display_text = self.listbox.get(current_idx)
        nombre_audio = display_text.split(' ', 1)[1] if ' ' in display_text else display_text
        session_id = self.get_session_id_from_filename(nombre_audio)
        
        if not session_id:
            messagebox.showwarning("Advertencia", "No se pudo identificar la sesión")
            return
        
        # Ventana para crear marcador
        marker_window = Toplevel(self.root)
        marker_window.title("Nuevo Marcador")
        marker_window.geometry("400x250")
        marker_window.transient(self.root)
        marker_window.grab_set()
        
        tb.Label(marker_window, text="Crear Marcador", font=("Segoe UI", 14, "bold")).pack(pady=10)
        
        # Mostrar posición actual
        current_time = self.format_time(self.audio_position)
        tb.Label(marker_window, text=f"Posición: {current_time}", font=("Segoe UI", 10)).pack(pady=5)
        
        # Campo para etiqueta
        tb.Label(marker_window, text="Etiqueta:").pack(anchor="w", padx=20)
        label_var = tk.StringVar()
        label_entry = tb.Entry(marker_window, textvariable=label_var, width=30)
        label_entry.pack(pady=5, padx=20, fill="x")
        label_entry.focus()
        
        # Campo para descripción
        tb.Label(marker_window, text="Descripción (opcional):").pack(anchor="w", padx=20, pady=(10, 0))
        desc_text = tb.Text(marker_window, height=4, width=30)
        desc_text.pack(pady=5, padx=20, fill="both", expand=True)
        
        # Botones
        btn_frame = tb.Frame(marker_window)
        btn_frame.pack(fill="x", padx=20, pady=10)
        
        def save_marker():
            label = label_var.get().strip()
            if not label:
                messagebox.showwarning("Advertencia", "La etiqueta es obligatoria")
                return
            
            description = desc_text.get("1.0", "end-1c").strip()
            
            # Guardar en base de datos
            self.save_marker_to_db(session_id, self.audio_position, label, description)
            
            # Actualizar marcadores actuales
            self.load_markers_for_session(session_id)
            
            # Actualizar waveform
            self.update_waveform_display()
            
            marker_window.destroy()
            messagebox.showinfo("Guardado", "Marcador creado correctamente")
        
        tb.Button(btn_frame, text="Guardar", command=save_marker, bootstyle="success").pack(side="right", padx=5)
        tb.Button(btn_frame, text="Cancelar", command=marker_window.destroy, bootstyle="secondary").pack(side="right")
    
    def save_marker_to_db(self, session_id, position, label, description):
        """Guardar marcador en la base de datos"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO audio_markers (session_id, position_seconds, label, description)
                VALUES (?, ?, ?, ?)
            ''', (session_id, position, label, description))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Error guardando marcador: {e}")
    
    def load_markers_for_session(self, session_id):
        """Cargar marcadores para una sesión específica"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT position_seconds, label, description 
                FROM audio_markers 
                WHERE session_id = ? 
                ORDER BY position_seconds
            ''', (session_id,))
            
            self.current_markers = []
            for row in cursor.fetchall():
                self.current_markers.append({
                    'position': row[0],
                    'label': row[1],
                    'description': row[2]
                })
        except Exception as e:
            logger.error(f"Error cargando marcadores: {e}")
            self.current_markers = []
    
    def next_marker(self):
        """Ir al siguiente marcador"""
        if not self.current_markers:
            return
        
        next_markers = [m for m in self.current_markers if m['position'] > self.audio_position]
        if next_markers:
            next_marker = min(next_markers, key=lambda x: x['position'])
            self.seek_to_position(next_marker['position'])
            self.update_waveform_display()
    
    def previous_marker(self):
        """Ir al marcador anterior"""
        if not self.current_markers:
            return
        
        prev_markers = [m for m in self.current_markers if m['position'] < self.audio_position]
        if prev_markers:
            prev_marker = max(prev_markers, key=lambda x: x['position'])
            self.seek_to_position(prev_marker['position'])
            self.update_waveform_display()
    
    def show_markers_window(self):
        """Mostrar ventana de gestión de marcadores"""
        if not self.current_audio:
            messagebox.showwarning("Advertencia", "Selecciona un audio primero")
            return
        
        # Obtener ID de sesión
        current_idx = self.listbox.curselection()[0] if self.listbox.curselection() else None
        if current_idx is None:
            return
        
        display_text = self.listbox.get(current_idx)
        nombre_audio = display_text.split(' ', 1)[1] if ' ' in display_text else display_text
        session_id = self.get_session_id_from_filename(nombre_audio)
        
        if not session_id:
            messagebox.showwarning("Advertencia", "No se pudo identificar la sesión")
            return
        
        markers_window = Toplevel(self.root)
        markers_window.title("Gestión de Marcadores")
        markers_window.geometry("600x400")
        
        tb.Label(markers_window, text=f"Marcadores - {nombre_audio}", 
                font=("Segoe UI", 12, "bold")).pack(pady=10)
        
        # Lista de marcadores
        list_frame = tb.Frame(markers_window)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        columns = ("Tiempo", "Etiqueta", "Descripción")
        tree = tb.Treeview(list_frame, columns=columns, show="headings", height=12)
        
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=150)
        
        # Scrollbar
        scrollbar = tb.Scrollbar(list_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Cargar marcadores
        self.load_markers_for_session(session_id)
        for marker in self.current_markers:
            tree.insert("", "end", values=(
                self.format_time(marker['position']),
                marker['label'],
                marker['description'][:50] + "..." if len(marker['description']) > 50 else marker['description']
            ))
        
        # Botones
        btn_frame = tb.Frame(markers_window)
        btn_frame.pack(fill="x", padx=10, pady=10)
        
        def go_to_marker():
            selection = tree.selection()
            if selection:
                item = tree.item(selection[0])
                marker_label = item['values'][1]
                marker = next((m for m in self.current_markers if m['label'] == marker_label), None)
                if marker:
                    self.seek_to_position(marker['position'])
                    self.update_waveform_display()
                    markers_window.destroy()
        
        def delete_marker():
            selection = tree.selection()
            if selection:
                if messagebox.askyesno("Confirmar", "¿Eliminar marcador seleccionado?"):
                    item = tree.item(selection[0])
                    marker_label = item['values'][1]
                    self.delete_marker_from_db(session_id, marker_label)
                    self.load_markers_for_session(session_id)
                    self.update_waveform_display()
                    tree.delete(selection[0])
        
        tb.Button(btn_frame, text="Ir a Marcador", command=go_to_marker, bootstyle="primary").pack(side="left", padx=5)
        tb.Button(btn_frame, text="Eliminar", command=delete_marker, bootstyle="danger").pack(side="left", padx=5)
        tb.Button(btn_frame, text="Cerrar", command=markers_window.destroy, bootstyle="secondary").pack(side="right")
        
        tree.bind("<Double-1>", lambda e: go_to_marker())
    
    def delete_marker_from_db(self, session_id, label):
        """Eliminar marcador de la base de datos"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                DELETE FROM audio_markers 
                WHERE session_id = ? AND label = ?
            ''', (session_id, label))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Error eliminando marcador: {e}")

if __name__ == '__main__':
    root = tb.Window(themename="superhero")
    app = SessionViewerApp(root)
    root.mainloop()
