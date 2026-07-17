import os
from flask import Flask, render_template, request

app = Flask(__name__)

# 1. ROUTE: Renders your custom frontend home page
@app.route('/')
def home():
    return render_template('index.html')

# 2. ROUTE: Handles customer booking data from the button click
@app.route('/book', methods=['POST'])
def handle_booking():
    # We will hook this up to capture names/dates next
    return "Booking route is active!"

if __name__ == '__main__':
    # Cloud hosts dynamically assign a port, so bind to environment variables
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)