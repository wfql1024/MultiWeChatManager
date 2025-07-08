import threading
from flask import Flask, jsonify, render_template
import webview

app = Flask(__name__)
counter = {'count': 0}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/count')
def get_count():
    return jsonify(counter)

@app.route('/increment', methods=['POST'])
def increment():
    counter['count'] += 1
    return jsonify(counter)

def run_flask():
    app.run(port=5000)

if __name__ == '__main__':
    # 后台启动 Flask
    threading.Thread(target=run_flask, daemon=True).start()

    # 前台启动 Webview
    # 注意这里访问的是 Flask 提供的地址
    webview.create_window("Webview Demo", "http://127.0.0.1:5000", width=400, height=300)
    webview.start()
