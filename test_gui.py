#!/usr/bin/env python3
"""
Test script para probar la GUI de la aplicación
"""
import sys
import os
import tkinter as tk
from tkinter import messagebox

# Agregar el directorio src al path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def test_gui():
    """Test básico para verificar que la GUI se puede inicializar"""
    print("Iniciando test de GUI...")
    
    try:
        # Crear ventana raíz de tkinter
        root = tk.Tk()
        root.title("Test de Audio y GUI - SESSIONS READER 2.0")
        root.geometry("600x400")
        
        # Intentar importar el módulo principal
        print("Importando módulo principal...")
        import visor_sesiones
        
        # Crear etiqueta de estado
        status_label = tk.Label(root, 
                               text="✓ Audio inicializado correctamente\n✓ Módulo principal importado\n\nLa aplicación está lista para usar.",
                               font=("Arial", 12),
                               fg="green",
                               justify="center")
        status_label.pack(expand=True)
        
        # Botón para intentar crear la aplicación principal
        def try_create_app():
            try:
                # Crear nueva ventana para la aplicación principal
                app_window = tk.Toplevel(root)
                app = visor_sesiones.SessionViewerApp(app_window)
                messagebox.showinfo("Éxito", "✓ Aplicación principal creada exitosamente!")
            except Exception as e:
                messagebox.showerror("Error", f"Error creando aplicación principal:\n{str(e)}")
        
        create_button = tk.Button(root,
                                 text="Crear Aplicación Principal",
                                 command=try_create_app,
                                 font=("Arial", 11),
                                 bg="lightblue")
        create_button.pack(pady=10)
        
        # Botón de cerrar
        close_button = tk.Button(root,
                                text="Cerrar",
                                command=root.quit,
                                font=("Arial", 11))
        close_button.pack(pady=5)
        
        print("✓ GUI de test iniciada")
        print("Ejecute la ventana para probar la funcionalidad")
        
        # Ejecutar la ventana de test
        root.mainloop()
        
    except Exception as e:
        print(f"✗ Error en test de GUI: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Configurar el entorno para mejor compatibilidad
    os.environ['TK_LIBRARY'] = '/usr/lib/python3.12/tkinter'
    test_gui()