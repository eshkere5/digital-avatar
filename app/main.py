"""Точка входа: приложение + расширения. Запуск: uvicorn app.main:app"""
from .server import app
from . import extras

extras.install(app)
