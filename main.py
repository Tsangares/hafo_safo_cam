from flask import Flask, request, redirect, send_file, render_template, Response
from flask_socketio import SocketIO, emit
import base64
import eventlet
import os,random
from PIL import Image
from io import BytesIO
import requests
import logging,time
from PIL import ImageFile
import cv2
import socket
from dotenv import load_dotenv
from flask_redis import FlaskRedis
load_dotenv()
app = Flask(__name__)
socketio = SocketIO(app)
CAM_URL = os.getenv("CAM_URL",None)
if CAM_URL is None:
    raise Exception("No camera URL!")
redis_client = FlaskRedis(app)
STREAMS = [ip for ip in requests.get(CAM_URL).json()]
        

@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

@app.route('/')
def home():
    streams = STREAMS
    return render_template('index.html',streams = streams)

def gen_frames(i):
    while True:
        frame = redis_client.get(f'camera_{i}')
        if frame is not None:
            emit('frame', {'data': base64.b64encode(frame).decode('utf-8'), 'camera_id': i})
        eventlet.sleep(0.1)

@socketio.on('start_stream')
def start_stream(data):
    camera_id = data['camera_id']
    eventlet.spawn(gen_frames, camera_id)

@app.route('/stream/<int:i>')
def video_feed(i):
    return Response(gen_frames(i), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/view/<int:i>')
def get_picture(i):
    frame = redis_client.get(f'camera_{i}')
    if frame is None:
        return "No frame available", 404
    return Response(frame, mimetype='image/jpeg')

@app.route('/oracle')
def get_oracle():
    if len(STREAMS)==0:
        return "FAILED"
    else:
        index = random.randint(0,len(STREAMS)-1)
        return Response(gen_frames(index), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/cache')
def sync_cache():
    data = request.json
    redis_client.set('iot-locator-cache', json.dumps(data, indent=2))
    
    
if __name__ == '__main__':
    app.run(port=8808, debug=True)
