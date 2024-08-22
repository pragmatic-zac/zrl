from sanic import Sanic
from sanic.response import json

app = Sanic("zrl")

@app.route("/")
async def handle_request(request):
    return json({"message": "Hello, zrl!"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
