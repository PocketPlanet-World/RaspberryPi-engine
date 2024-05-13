import time #時間函示
import serial #串行通訊
import asyncio #多線程執行緒
import firebase_admin #數據上傳firebase
from firebase_admin import credentials, firestore
import tkinter as tk #GUI視窗函釋
import threading

# 初始化 Firebase_admin
account_key = "./pocketplanet-AccountKey/serviceAccountKey.json" #firebase上傳驗證金鑰路徑
cred = credentials.Certificate(account_key)
firebase_admin.initialize_app(cred)
db = firestore.client()

# 設置 Firebase 中的 Water 初始值為 False
db.collection(u'Control').document(u'change').update({'Water': False})

# 監聽器firebase文件，將在每次文件更改時調用
def on_snapshot(doc_snapshot, changes, read_time):
    for change in changes:
        if change.type.name == 'MODIFIED':
            # 檢查是否有 Water 字段並且是布林值
            if 'Water' in change.document.to_dict() and isinstance(change.document.to_dict()['Water'], bool):
                water_value = change.document.to_dict()['Water']
                print(f"收到新的 Water 布林值: {water_value}")

                # 如果上一次的值是 False 而且現在是 True，則輸出 1 並控制水泵
                if water_value:
                    print("1")
                    # 向 Arduino 發送控制水泵指令
                    ser.write("control_pump\n".encode())

                    # 在輸出 1 後將水值重新設為 False
                    doc_ref.update({'Water': False})

# 註冊監聽器，監聽firebase布林值文件
doc_ref = db.collection(u'Control').document(u'change')
doc_watch = doc_ref.on_snapshot(on_snapshot)

# 分鐘
minute = 1


# serial 讀取
ser = serial.Serial("/dev/ttyUSB0", baudrate=9600, timeout=minute)

# 解析 數據 json 格式資料
def parse_data(d):
    data_split = d.split(",")
    data = {}
    for item in data_split:
        try:
            key, value = item.strip().split(":")
            data[key] = value
        except ValueError:
            print(f"Error parsing data item: {item}")
    return data

# 讀取 serial 資料
def serial_read():
    try:
        ser.write("request_data\n".encode())
        received_data = ser.readline().decode().strip()
        if received_data:
            parsed_data = parse_data(received_data)
            print("========= Read Data =========")
            print("Received data:", parsed_data)
            print("=============================")
            return parsed_data
    except Exception as e:
        print("Error reading from serial:", e)
        return None

# 上傳 firestore 資料
async def upload_data_to_firestore(d):
    try:
        current_day = time.strftime("%Y%m%d") # 獲取當前日期
        current_time = time.strftime("%H:%M") # 使用當前時間作為資料鍵名
        doc_ref = db.collection("data").document(current_day) # 取得當前日期的文檔參考
        doc = doc_ref.get()
        # 確認文檔是否存在，如果不存在則創建新文檔
        if not doc.exists:
            doc_ref.set({})
            print("已創建新文檔：", current_day)
        d["time"] = current_time
        doc_ref.update({"data": firestore.ArrayUnion([d])})
        print("資料成功上傳到 Firestore！")
    except Exception as e:
        print("在 Firestore 中添加資料時出錯：", e)

# 視窗顯示數據
def display_window():
    window = tk.Tk()
    window.title("Arduino數據顯示")

    # 設置視窗大小為螢幕的全螢幕
    window.attributes('-fullscreen', True)

    # 按下按鈕時觸發的函數
    def control_pump():
        ser.write("control_pump\n".encode())
        print("已向 Arduino 發送控制水泵指令")

    # 控制水泵按鈕
    pump = tk.Button(window, text="控制水泵", command=control_pump, width=10, height=4, font=("Arial", 40))
    pump.pack()

    # 顯示接收到的數據的標籤
    data_label = tk.Label(window, text="", font=("Arial", 20), anchor="nw", justify="left")
    data_label.pack()

    # 更新數據標籤的函數
    def update_data_label():
        # 讀取串行數據並顯示
        data = serial_read()
        if data:
            # 根據數據項目設置不同的顏色和放大效果
            formatted_data = ""
            for key, value in data.items():
                # 添加上方分隔線
                formatted_data += "-----------------------------------------------\n"
                # 添加數據
                if key == 'airhumidity':
                    formatted_data += f"{key}: {value}% \n"
                elif key == 'airtemperature':
                    formatted_data += f"{key}: {value}*C \n"
                elif key == 'SoilMoisture':
                    formatted_data += f"{key}: {value}% \n"
                elif key == 'SoilTemperature':
                    formatted_data += f"{key}: {value}*C \n"
                elif key == 'PH':
                    formatted_data += f"{key}: {value} \n"
            # 添加最後一行的下方分隔線
            formatted_data += "-----------------------------------------------\n"
            data_label.config(text=formatted_data)
            # 檢查時間將上傳數據到 Firestore
            current_minute = int(time.strftime("%M"))
            if current_minute % minute == 0:
                upload_data_to_firestore(data)

            # 刷新 UI
            window.update()

        # 每隔一段時間調度更新函數
        window.after(60 * 1000, update_data_label)

    # 啟動更新數據標籤的函數
    update_data_label()

    window.mainloop()

# 主程式
async def main():
    try:
        while True:
            current_minute = int(time.strftime("%M"))
            if current_minute % minute == 0:  # 在時間分鐘為5的倍數時執行
                data = serial_read()
                if data:
                    await upload_data_to_firestore(data)
            await asyncio.sleep(60)  # 每60秒檢查一次時間
    except KeyboardInterrupt:
        ser.close()

if __name__ == "__main__":
    # 使用第二個線程中啟動視窗顯示函數
    display_thread = threading.Thread(target=display_window)
    display_thread.start()

    # 開始執行主程式
    asyncio.run(main())