import os

import uvicorn
from api import create_app
from auth import READ, WRITE, Principal

key_hash = os.environ["TASKS_API_KEY_HASH"]

app = create_app({key_hash: Principal(key_id="me", scopes=frozenset({READ, WRITE}))})

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
