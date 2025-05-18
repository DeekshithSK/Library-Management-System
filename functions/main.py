import functions_framework
from flask import Flask, request
import app

@functions_framework.http
def app(request):
    return app.app(request.environ, lambda x, y: y) 