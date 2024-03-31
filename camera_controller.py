from PIL import Image
from io import BytesIO
from PIL import ImageFile
import os, requests, socket, cv2, time
import redis
from multiprocessing import Process
from dotenv import load_dotenv
import json
import logging
load_dotenv()
cache = None
def get_camera_urls():
    ip_list_url = os.getenv("CAM_URL",None)
    if ip_list_url is None:
        raise Exception("No camera URL!")
    # Query the cameras
    ip_list = [f"http://{ip}" for ip in requests.get(ip_list_url).json()]
    stream_urls = [f"{url}/mjpeg/1" for url in ip_list]
    return stream_urls

def get_frames(stream,index):
    start_time = time.time()
    db = redis.Redis()
    camera = cv2.VideoCapture(stream)
    camera_failed = False
    while True:
        success, frame = camera.read()  # read the camera frame
        if not success:
            logging.error("Failed to get image")
            return False
        else:
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            db.set(f'camera_{index}', frame)
            time.sleep(.1)
            duration = time.time() - start_time
            if duration > 60*30: return True

def refresh_cameras():
    streams = get_camera_urls()
    return streams

def handle_stream(stream,index):
    process = Process(target=get_frames, args=(stream, index))
    process.start()
    return process

class SyncException(Exception):
    pass

def sync_cache():
    db = redis.Redis()
    pubsub = db.pubsub()
    try:
        #db.config_set('notify-keyspace-events', 'Ex')
        pubsub.subscribe('iot-locator-cache')
        for message in pubsub.listen():
            if message['type'] == 'message':
                # Handle the received message
                data = message['data']
                print(f"Received data: {data}")
    except Exception as e:
        print(f"An error occurred: {str(e)}")

    finally:
        # Unsubscribe from the channel and close the connection
        if pubsub:
            pubsub.unsubscribe('iot-locator')
            pubsub.close()
        if db:
            db.close()

def subscribe_sync_cache():
    process = Process(target=sync_cache)
    process.start()
    return process

def init():
    processes = []
    subscription = None
    try:
        streams = refresh_cameras()
        sub_process = subscribe_sync_cache()
        print(streams)
        for i,stream in enumerate(streams):
            process = handle_stream(stream,i)
            processes.append(process)
            time.sleep(1)
        for process in processes:
            process.join()
        init()
    except SyncException as e:
        for process in processes:
            process.terminate()
        if subscription is not None:
            sub_process.terminate()
        init()
    except Exception as e:
        for process in processes:
            process.terminate()
        if subscription is not None:
            sub_process.terminate()
        logging.error(str(e))
        init()
        

if __name__ == "__main__":
    init()

    
