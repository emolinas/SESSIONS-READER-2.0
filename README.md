# Visor de Sesiones Avanzado

Un reproductor de audio avanzado para gestionar y analizar sesiones de audio comprimidas en archivos ZIP, con integración de datos Excel.

## Características

- 🎵 **Reproducción de audio**: Soporte para MP3, WAV, OGG, M4A
- 📊 **Integración Excel**: Carga automática de metadatos desde archivos Excel
- ⭐ **Sistema de favoritos**: Marca y gestiona sesiones importantes
- 🔍 **Búsqueda avanzada**: Filtros por múltiples criterios
- 📝 **Notas de usuario**: Agrega notas personalizadas a cada sesión
- 🎨 **Temas personalizables**: Múltiples temas de interfaz
- 📈 **Estadísticas**: Análisis de duración y distribución temporal
- 🔄 **Control de velocidad**: Reproducción a diferentes velocidades
- 📋 **Exportación**: Reportes en Excel y CSV

## Requisitos

- Python 3.8+
- Librerías Python (ver requirements.txt)

## Instalación

1. Clona este repositorio
2. Instala las dependencias: `pip install -r requirements.txt`
3. Ejecuta: `python Scripts/visor_sesiones.py`

## Uso

1. **Abrir archivo ZIP**: Usa Ctrl+O o el botón "Abrir archivo ZIP"
2. **Reproducir audio**: Selecciona un archivo y presiona Espacio
3. **Marcar favoritos**: Usa el botón ⭐ o haz clic en una sesión
4. **Buscar**: Usa Ctrl+F para búsqueda avanzada
5. **Exportar**: Genera reportes desde el menú Archivo

## Estructura del Proyecto

```
emsenvironment312/
├── Scripts/
│   └── visor_sesiones.py    # Aplicación principal
├── .gitignore               # Archivos a ignorar por Git
├── README.md               # Este archivo
└── requirements.txt        # Dependencias Python
```

## Control de Versiones

Este proyecto usa Git para control de versiones:

- `git add .` - Agregar cambios
- `git commit -m "mensaje"` - Confirmar cambios
- `git log --oneline` - Ver historial
- `git tag v1.0.0` - Crear versión

## Changelog

### v1.0.0 (2025-07-30)

- Versión inicial con todas las características principales
- Reproductor de audio con controles avanzados
- Sistema de favoritos y notas
- Búsqueda avanzada y filtros
- Múltiples temas de interfaz
- Exportación de reportes
- Integración con archivos Excel

## Autor

Desarrollado para gestión de sesiones de audio.

## Licencia

Proyecto de uso personal.

## Try it (Quick)

1. Crea un virtualenv fuera del repositorio y actívalo.
2. Instala dependencias:

   pip install -r requirements.txt

3. Asegúrate de que `ffmpeg` esté disponible (ver nota arriba).
4. Ejecuta la aplicación:

   # PowerShell

   & "C:/Users/emsin/MY PROYECTS/VISUAL ESTUDIO CODE/SESSIONS READER/Scripts/python.exe" "Scripts/visor_launcher.py"

## Notas

- No mantengas el entorno virtual dentro del repositorio; ya fue removido del control de versiones.
- Si ves avisos relacionados con ffmpeg, coloca `ffmpeg.exe` en `Scripts/` o define `FFMPEG_PATH`.

## Instalación de ffmpeg (Windows)

Algunas operaciones (p. ej. procesar ciertos archivos de audio con `pydub`) requieren `ffmpeg` en el sistema. Puedes instalarlo manualmente o usar el script incluido.

Opción A — Manual (rápido):

1. Descarga una build estática de ffmpeg para Windows (por ejemplo desde <https://www.gyan.dev/ffmpeg/builds/>).
2. Extrae `ffmpeg.exe` y colócalo en la carpeta `Scripts/` del proyecto (misma carpeta que el intérprete del virtualenv).
3. Reinicia tu terminal o VS Code para que la variable de entorno `FFMPEG_PATH` sea reconocida o define `FFMPEG_PATH` apuntando a `Scripts\ffmpeg.exe`.

Opción B — Automática (PowerShell):

Ejecuta el script incluido `Scripts/install_ffmpeg.ps1` en PowerShell con permisos de usuario: este descargará una build esencial, extraerá `ffmpeg.exe` en `Scripts/`, y configurará `FFMPEG_PATH` para el usuario.

Uso:

```powershell
# Ejecutar desde la raíz del proyecto
.\Scripts\install_ffmpeg.ps1
```

Notas:

- `setx` se usa para persistir `FFMPEG_PATH` para futuras sesiones; reinicia VS Code o abre una nueva terminal para ver el cambio reflejado.
- Si prefieres otra fuente de builds de ffmpeg, modifica el script `Scripts/install_ffmpeg.ps1`.
