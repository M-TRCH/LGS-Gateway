
import time
from arduino.app_utils import *

def loop():
    res = Bridge.call("test")
    print(f"RPC call result: {res}")
    time.sleep(2)

if __name__ == "__main__":
    print("เริ่มการทำงาน LGS-Gateway Controller...")
    App.run(user_loop=loop)