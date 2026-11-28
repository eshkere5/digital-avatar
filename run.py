import os
import uvicorn

if __name__ == "__main__":
    host, port = os.getenv("HOST", "127.0.0.1"), int(os.getenv("PORT", "8000"))
    print(f"Digital Avatar: http://{host}:{port}")
    uvicorn.run("app.main:app", host=host, port=port)
