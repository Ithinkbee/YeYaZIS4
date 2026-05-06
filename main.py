"""
СинтАналитик — приложение для семантико-синтаксического анализа
русскоязычных текстов в формате DOC/DOCX.

Запуск: python main.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui.app import Application

if __name__ == '__main__':
    app = Application()
    app.run()
