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
import warnings
# Detección robusta de ffmpeg para pydub:
# - Respeta la variable de entorno FFMPEG_PATH
# - Busca un ffmpeg.exe en la misma carpeta `Scripts/` del proyecto
# - Busca en una posible instalación local en ../ffmpeg/bin/ffmpeg.exe
# - Usa `which` (sistema) como último recurso
try:
    from pydub.utils import which
except Exception:
    which = None

ffmpeg_candidates = [
    os.environ.get('FFMPEG_PATH'),
    os.path.join(os.path.dirname(__file__), 'ffmpeg.exe'),
    os.path.join(os.path.dirname(os.path.dirname(__file__)), 'ffmpeg', 'bin', 'ffmpeg.exe')
]

selected_ffmpeg = None
for candidate in ffmpeg_candidates:
    try:
        if candidate and os.path.isfile(candidate):
            selected_ffmpeg = candidate
            break
    except Exception:
        continue

if not selected_ffmpeg and which:
    # Buscar en PATH
    selected_ffmpeg = which('ffmpeg') or which('ffmpeg.exe')

if selected_ffmpeg:
    AudioSegment.converter = selected_ffmpeg
    logger.info(f"pydub ffmpeg: usando {selected_ffmpeg}")
else:
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

# Inicializar mezclador de audio con configuración mejorada para compatibilidad
def initialize_audio():
    """Inicializar audio con múltiples estrategias de fallback"""
    # Estrategia 1: Configuración optimizada para Windows
    if os.name == 'nt':  # Windows
        try:
            os.environ['SDL_AUDIODRIVER'] = 'directsound'
            mixer.pre_init(frequency=22050, size=-16, channels=2)
            mixer.init()
            logger.info(f"Audio Windows inicializado: {mixer.get_init()}")
            return True
        except Exception as e:
            logger.warning(f"Error con DirectSound: {e}")
    
    # Estrategia 2: Pre-init con parámetros específicos (multiplataforma)
    try:
        mixer.quit()  # Limpiar estado previo
        mixer.pre_init(frequency=22050, size=-16, channels=2)
        mixer.init()
        logger.info(f"Audio pre-init inicializado: {mixer.get_init()}")
        return True
    except Exception as e:
        logger.warning(f"Error con pre-init: {e}")
    
    # Estrategia 3: Inicialización básica como fallback
    try:
        mixer.quit()  # Limpiar estado previo
        mixer.init()
        logger.info(f"Audio básico inicializado: {mixer.get_init()}")
        return True
    except Exception as e:
        logger.warning(f"Error con init básico: {e}")
    
    # Estrategia 4: Modo dummy para entornos sin audio
    try:
        os.environ['SDL_AUDIODRIVER'] = 'dummy'
        mixer.init()
        logger.info("Audio inicializado en modo dummy (sin hardware de audio)")
        return True
    except Exception as e:
        logger.error(f"No se pudo inicializar el audio en ningún modo: {e}")
        return False

# Inicializar audio
audio_initialized = initialize_audio()

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

        # ... (file continues unchanged) ...
