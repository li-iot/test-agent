from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/add", methods=["GET"])
def add():
    a = int(request.args.get("a", 0))
    b = int(request.args.get("b", 0))
    # BUG：这里应该是 a + b，却写成了 a - b
    return jsonify({"result": a - b})
