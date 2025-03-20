import logging
from flask import Flask, jsonify, render_template

class WebInterface:
    def __init__(self, device_manager):
        self.app = Flask(__name__)
        self.device_manager = device_manager

    @self.app.route('/')
    def index():
        return render_template('index.html')

    @self.app.route('/control_light', methods=['POST'])
    def control_light():
        state = request.form.get('state')
        self.device_manager.set_light(state)
        logging.info(f"灯光状态设置为：{state}")
        return jsonify({'status': 'success', 'state': state})

    @self.app.route('/status')
    def get_status():
        return jsonify({
            'temperature': self.device_manager.get_temperature(),
            'light': self.device_manager.get_light_status()
        })

    def run(self, host='0.0.0.0', port=5000):
        self.app.run(host=host, port=port)
