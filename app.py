import copy
import time

import httpx
import jwt
import redis
from sanic import Sanic, Request, response
from sanic.response import json

app = Sanic("zrl")
r = redis.Redis(host='localhost', port=6379, db=0)

# load lua script and register it
script_path = 'scripts/allow_request.lua'
with open(script_path, 'r') as file:
    lua_script = file.read()
    allow_request_script = r.register_script(lua_script)

@app.route("/<path:path>", methods=["GET", "POST"])
async def handle_request(request: Request, path: str):
    # extract user from jwt, for simplicity right now just assume email is the key
    token = request.headers.get("Authorization").split('Bearer ', )[1]
    decoded_token = jwt.decode(token, key="qwertyuiopasdfghjklzxcvbnm123456", algorithms=["HS256"], audience="www.example.com")

    # variables for script
    zset_key = path  # this is the resource the user is trying to access
    user = decoded_token["Email"]
    current_time = time.time()

    # load these from a config per resource, perhaps a yaml file
    refill_rate = 1
    capacity = 5
    tokens_needed = 1

    # are there enough tokens?
    result = allow_request_script(keys=[zset_key], args=[user, current_time, refill_rate, capacity, tokens_needed])
    if not result:
        # if no, throw 429 and reject the request
        print('blocking request')
        return json({"message": "rate limit exceeded"}, status=429)

    # if yes, proxy the request
    async with httpx.AsyncClient() as client:
        # extract the host and the remaining path
        parts = path.split('/', 1)
        host = parts[0]
        remaining_path = parts[1] if len(parts) > 1 else ''

        new_headers = copy.deepcopy(request.headers)
        new_headers['Host'] = host

        x_forwarded_for = request.headers.get('X-Forwarded-For', '')
        client_ip = request.remote_addr or '127.0.0.1'
        new_headers['X-Forwarded-For'] = f"{x_forwarded_for}, {client_ip}" if x_forwarded_for else client_ip

        proxy_request = client.build_request(
            method=request.method,
            url=f"https://{host}/{remaining_path}",
            headers=new_headers,
            content=request.body
        )

        proxy_response = await client.send(proxy_request, stream=True)

        sanic_response = await request.respond(
            status=proxy_response.status_code,
            headers=dict(proxy_response.headers)
        )

        # stream the response from the proxied request
        async for chunk in proxy_response.aiter_bytes():
            await sanic_response.send(chunk)

        await sanic_response.eof()


# simple example request: GET to localhost:8000/jsonplaceholder.typicode.com/posts/1
if __name__ == "__main__":
    # TODO: load configs - JWT key, resource details, etc
    app.run(host="0.0.0.0", port=8000)