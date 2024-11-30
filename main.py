import cv2
import numpy as np
import time
from collections import deque
import os
import redis
import logging
# logging.basicConfig(level=logging.CRITICAL)  # Configure logging level
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
redis_host = os.environ.get("REDIS_HOST", "localhost")
r = None

try:
    r = redis.Redis(host=redis_host, port=6379, db=0)
except Exception as e:
    logging.critical("Error connecting to Redis: %s", e)

if r is None:
    raise ConnectionError("Redis connection unavailable. Please check your Redis setup.")


def get_queue():
    try:
        order = r.rpop('CTRL').decode('UTF-8')
        if (order != None):
            return True, order
        else:
            return False, ''
    except Exception as e:
        logging.critical("Order Empty")
        return False, ''

def put_response( status):
    try:
        # status = 'S0', 'E0', 'E1' , 'E2', 'E3', 'E4'  :: ('S0' : success) , ('E0' : no drop"47") , ('>
        item = r.lpush('CAMERA', status)
        return True
    except Exception as e:
        logging.critical("redis error")
        return False

# Function to calculate frame difference in the specified ROI
def frame_difference(frame1, frame2, roi_pts):
    try:
        mask1 = np.zeros(frame1.shape[:2], dtype=np.uint8)
        mask2 = np.zeros(frame2.shape[:2], dtype=np.uint8)
        cv2.fillPoly(mask1, [roi_pts], 255)
        cv2.fillPoly(mask2, [roi_pts], 255)
        roi_frame1 = cv2.bitwise_and(frame1, frame1, mask=mask1)
        roi_frame2 = cv2.bitwise_and(frame2, frame2, mask=mask2)
        diff = cv2.absdiff(roi_frame1, roi_frame2)
        gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray_diff, 30, 255, cv2.THRESH_BINARY)
        return np.sum(thresh)
    except Exception as e:
        logging.critical("Error calculating frame difference: %s", e)
        return 0

# Function to set up video capture and seek to start frame
def setup_video_capture(video_path):
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logging.critical("Error: Could not open video stream.")
            return None
        return cap
    except Exception as e:
        logging.critical("Error setting up video capture: %s", e)
        return None




# Main function to initialize parameters and start detection
def main():
    # video_path = 0
    username = "admin"
    password = "!P@ssw0rd!"
    camera_ip = "192.168.0.108"
    port = "554"
    channel = "1"
    subtype = "0"
    threshold = 1500000
    detect_frame = 25
    rtsp_url = f"rtsp://{username}:{password}@{camera_ip}:{port}/cam/realmonitor?channel={channel}&subtype={subtype}"
    roi_pts = np.array([[615, 720], [1270, 719], [1270, 570], [615, 570]], np.int32)

    try:
        while True :
            try:
                get_q_sta, order = get_queue()
                if order == 'START' :
                    cap = setup_video_capture(rtsp_url)
                    cap = setup_video_capture(0)
                    if not cap:
                        return

                    order = None
                    start_time = time.time()
                    count_detection = 0
                    ret = None

                    while((time.time()-start_time) < 300):
                        get_q_sta, order = get_queue()
                        time.sleep(0.1) # time
                        if (order == 'STOP'):
                            order = None
                            break

                        retries = 5
                        while ret == None and retries > 0:
                            ret, frame = cap.read()

                            retries -= 1
                            first_frame = frame
                        if not ret:
                            logging.critical("Error: Unable to retrieve frames after retries.")
                            break


                        ret, frame = cap.read()
                        if not ret:
                            break
                        change = frame_difference(first_frame, frame, roi_pts)
                        # logging.info("Change value: %d", change)
                        if change > threshold:
                            count_detection += 1
                            # logging.info("Item drop detected : %d", count_detection)

                        if count_detection >= detect_frame :
                            put_response('S0')
                            logging.info("Response 'S0' sent to Redis.")
                            # print("Put Response")
                            order = None
                            break
                        else:
                            pass
                    cap.release()

                time.sleep(0.5)
            except Exception as e:
                logging.critical("Error in main loop: %s", e)
    finally:
        if cap:
            cap.release()
        logging.info("Video capture released.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.critical("Unhandled exception: %s", e)
