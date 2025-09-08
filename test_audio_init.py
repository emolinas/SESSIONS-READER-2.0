#!/usr/bin/env python3
"""
Test script para verificar la inicialización de audio mejorada
"""
import os
import sys
import pygame
from pygame import mixer
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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

def test_audio_initialization():
    """Test para verificar que la inicialización de audio funciona correctamente"""
    print("=" * 60)
    print("TEST DE INICIALIZACIÓN DE AUDIO MEJORADA")
    print("=" * 60)
    
    print(f"Sistema operativo: {os.name}")
    print(f"Plataforma: {sys.platform}")
    
    # Test con la función mejorada
    print("\nProbando inicialización con múltiples estrategias...")
    success = initialize_audio()
    
    if success:
        init_result = mixer.get_init()
        print(f"\n✓ AUDIO INICIALIZADO EXITOSAMENTE")
        print(f"  Configuración: {init_result}")
        if init_result:
            print(f"  - Frecuencia: {init_result[0]} Hz")
            print(f"  - Formato: {init_result[1]} bits")
            print(f"  - Canales: {init_result[2]}")
        
        # Test básico de funcionalidad del mixer
        try:
            channels = mixer.get_num_channels()
            print(f"  - Canales de mezcla disponibles: {channels}")
            print("  ✓ Mezclador funcional")
        except Exception as e:
            print(f"  ⚠ Advertencia en funcionalidad del mezclador: {e}")
    else:
        print("\n✗ NO SE PUDO INICIALIZAR EL AUDIO")
        print("  La aplicación puede tener problemas de reproducción de audio")
    
    print("\n" + "=" * 60)
    print("RESUMEN")
    print("=" * 60)
    if success:
        print("✓ La inicialización de audio ha sido exitosa.")
        print("  La aplicación debería poder reproducir audio correctamente.")
    else:
        print("⚠ La inicialización de audio falló.")
        print("  La aplicación funcionará pero sin capacidad de audio.")
    
    return success

if __name__ == "__main__":
    test_audio_initialization()