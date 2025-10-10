# keep_alive.py
from flask import Flask
from threading import Thread

# Create a simple Flask web app
app = Flask('')

@app.route('/')
def home():
    return "✅ The Discord Shop Bot is running!"

# Function to start the web server
def run():
    app.run(host='0.0.0.0', port=8080)

# Function to launch it in a background thread
def keep_alive():
    t = Thread(target=run)
    t.start()