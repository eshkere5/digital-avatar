import uvicorn
if __name__ == "__main__":
    print("Digital Avatar: http://127.0.0.1:8000")
    uvicorn.run("app.server:app", host="127.0.0.1", port=8000)
