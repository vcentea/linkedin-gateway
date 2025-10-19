# backend/app/auth/__init__.py
# This file can remain empty or be used for helper functions if needed later.

# No need to import Blueprint from flask as we're using FastAPI Router
# from flask import Blueprint

# FastAPI uses Router instead of Blueprint
# auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# Import routes to register them with the Router
from . import routes 