"""
WSGI config for fooram_baced projet.

It exposes he WSGI callable as a modul-level variable amed ``application``.
https://docs.djangoproject.com/en/3.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "foodgram_backend.settings")

application = get_wsgi_application()
