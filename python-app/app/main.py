from flask import Flask, jsonify, request

app = Flask(__name__)


@app.get("/")
def index():
    return jsonify(service="demo-python-app", message="Hello from the DevSecOps demo")


@app.get("/health")
def health():
    return jsonify(status="ok")


@app.get("/api/greet")
def greet():
    name = request.args.get("name", "world")[:50].title()
    return jsonify(greeting=f"Hello, {name}!")
