from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/api/add/<int:a>/<int:b>")
def add(a: int, b: int) -> dict:
    return jsonify({"result": a + b})


@app.route("/api/multiply/<int:a>/<int:b>")
def multiply(a: int, b: int) -> dict:
    return jsonify({"result": a * b})


if __name__ == "__main__":
    app.run(port=5000)
