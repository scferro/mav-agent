"""
MAVLink Agent Models Module
"""

from .ollama import OllamaInterface
from .tensorrt import TensorRTInterface

__all__ = [
    'OllamaInterface',
    'TensorRTInterface'
]