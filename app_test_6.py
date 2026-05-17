import serial
import time
import serial.tools.list_ports
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from typing import Optional, Dict, List, Tuple

class HighSpeedCommBoardSimplified:
    def __init__(self, root):
        self.root = root
        self.root.title("触觉传感器核心数据采集系统")
        self.root.geometry("1100x800")
        
        self.ser = None
        self.auto_receive_running = False
        self.distribution_points_cache = {}  
        self.connected_sensors = [] 
        
        # 掌心传感器特殊配置
        self.palm_sensor_limit = 9  
        
        # UI 日志节流控制（防止高频回传卡死界面）
        self.last_log_time = 0

        # 传感器模组分布力点数地址映射
        self.distribution_points_addrs = {
            "大拇指近节": 0x0030, "大拇指中节": 0x0032, "大拇指指尖": 0x0034, "大拇指指甲": 0x0036,
            "食指近节": 0x0038, "食指中节": 0x003A, "食指指尖": 0x003C, "食指指甲": 0x003E,
            "中指近节": 0x0040, "中指中节": 0x0042, "中指指尖": 0x0044, "中指指甲": 0x0046,
            "无名指近节": 0x0048, "无名指中节": 0x004A, "无名指指尖": 0x004C, "无名指指甲": 0x004E,
            "小拇指近节": 0x0050, "小拇指中节": 0x0052, "小拇指指尖": 0x0054, "小拇指指甲": 0x0056,
            "掌心1": 0x0066, "掌心2": 0x0068, "掌心3": 0x006A, "掌心4": 0x006C,
            "掌心5": 0x006E, "掌心6": 0x0070, "掌心7": 0x0072, "掌心8": 0x0074
        }
        
        # 传感器状态地址定义
        self.sensor_status_addrs = {
            0x0010: "大拇指和食指", 0x0011: "中指和无名指",
            0x0012: "小拇指和掌心1-4", 0x0013: "掌心5-8"
        }

        self.init_ui()
        
    def init_ui(self):
        # 1. 通信配置区域
        config_frame = ttk.LabelFrame(self.root, text="通信配置")
        config_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(config_frame, text="COM口:").grid(row=0, column=0, padx=5, pady=5)
        self.com_var = tk.StringVar()
        self.com_combo = ttk.Combobox(config_frame, textvariable=self.com_var, width=10)
        self.com_combo.grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(config_frame, text="刷新COM", command=self.refresh_com_ports).grid(row=0, column=2, padx=5, pady=5)
        
        ttk.Label(config_frame, text="波特率:").grid(row=0, column=3, padx=5, pady=5)
        self.baud_var = tk.StringVar(value="921600")
        self.baud_combo = ttk.Combobox(config_frame, textvariable=self.baud_var, width=10)
        self.baud_combo['values'] = ["9600", "115200", "921600"]
        self.baud_combo.grid(row=0, column=4, padx=5, pady=5)
        
        ttk.Button(config_frame, text="连接设备", command=self.connect).grid(row=0, column=5, padx=5, pady=5)
        ttk.Button(config_frame, text="断开连接", command=self.disconnect).grid(row=0, column=6, padx=5, pady=5)
        ttk.Button(config_frame, text="清空面板", command=self.clear_log).grid(row=0, column=7, padx=5, pady=5)

        # 2. 核心功能操作区域
        op_frame = ttk.LabelFrame(self.root, text="核心控制面板")
        op_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(op_frame, text="[步骤1] 检查连接状态", command=self.check_sensor_status).grid(row=0, column=0, padx=10, pady=10)
        ttk.Button(op_frame, text="[步骤2] 查询分布力点数", command=self.check_distribution_points).grid(row=0, column=1, padx=10, pady=10)
        ttk.Button(op_frame, text="[扩展] 单次读取模组合力", command=self.read_module_forces).grid(row=0, column=2, padx=10, pady=10)
        ttk.Button(op_frame, text="▶ 开启自动回传流", command=self.start_auto_receive, style="Accent.TButton").grid(row=0, column=3, padx=10, pady=10)
        ttk.Button(op_frame, text="■ 停止自动回传流", command=self.stop_auto_receive).grid(row=0, column=4, padx=10, pady=10)

        # 3. 数据展示区域
        log_frame = ttk.LabelFrame(self.root, text="数据监控输出 (自动回传开启时每秒刷新一次)")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state=tk.DISABLED, bg="#1e1e1e", fg="#00FF00", font=("Consolas", 10))
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.style = ttk.Style()
        self.style.configure("Accent.TButton", foreground="blue", font=("", 10, "bold"))
        self.refresh_com_ports()

    def clear_log(self):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)

    def log(self, message: str, color="white"):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def refresh_com_ports(self):
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.com_combo['values'] = ports
        if ports: self.com_var.set(ports[0])

    def connect(self):
        if self.ser and self.ser.is_open: return
        try:
            self.ser = serial.Serial(self.com_var.get(), int(self.baud_var.get()), timeout=0.1)
            self.log(f"成功连接到 {self.com_var.get()}")
        except Exception as e:
            self.log(f"连接失败: {str(e)}")

    def disconnect(self):
        self.stop_auto_receive()
        if self.ser and self.ser.is_open:
            self.ser.close()
            self.log("已断开连接")

    def calculate_lrc(self, data: bytes) -> int:
        return ((~sum(data)) + 1) & 0xFF

    def build_request_frame(self, func_code: int, reg_addr: int, data: bytes = b"") -> bytes:
        frame_body = b"\x55\xAA\x00" + bytes([func_code]) + reg_addr.to_bytes(2, 'little') + len(data).to_bytes(2, 'little') + data
        return frame_body + bytes([self.calculate_lrc(frame_body)])

    # ================= 核心功能 1：连接状态检查 =================
    def check_sensor_status(self):
        if not self.ser or not self.ser.is_open: return self.log("请先连接设备")
        self.connected_sensors = []
        self.log("="*40 + "\n开始检查传感器连接状态...")
        
        for addr in self.sensor_status_addrs:
            self.ser.write(self.build_request_frame(0x03, addr, b"\x01\x00")) # 读1字节
            time.sleep(0.05)
            response = self.ser.read(128)
            if response and len(response) >= 8 and response[3] == 0x03:
                status_byte = response[8]
                self._parse_status_bits(addr, status_byte)
        
        self.log(f"检查完毕！当前共接入 {len(self.connected_sensors)} 个传感器: {', '.join(self.connected_sensors)}\n" + "="*40)

    def _parse_status_bits(self, addr, byte):
        mapping = {
            0x0010: ["大拇指近节", "大拇指中节", "大拇指指尖", "大拇指指甲", "食指近节", "食指中节", "食指指尖", "食指指甲"],
            0x0011: ["中指近节", "中指中节", "中指指尖", "中指指甲", "无名指近节", "无名指中节", "无名指指尖", "无名指指甲"],
            0x0012: ["小拇指近节", "小拇指中节", "小拇指指尖", "小拇指指甲", "掌心1", "掌心2", "掌心3", "掌心4"],
            0x0013: ["掌心5", "掌心6", "掌心7", "掌心8"]
        }
        for i, name in enumerate(mapping[addr]):
            if i < len(mapping[addr]) and (byte & (1 << i)):
                self.connected_sensors.append(name)

    # ================= 核心功能 2：分布力点数查询 =================
    def check_distribution_points(self):
        if not self.ser or not self.ser.is_open: return self.log("请先连接设备")
        if not self.connected_sensors: return self.log("请先执行[检查连接状态]！")
        
        self.distribution_points_cache.clear()
        self.log("="*40 + "\n开始查询已接入传感器的分布力点数...")
        
        for sensor in self.connected_sensors:
            addr = self.distribution_points_addrs.get(sensor)
            if addr:
                self.ser.write(self.build_request_frame(0x03, addr, b"\x02\x00")) # 读2字节
                time.sleep(0.05)
                res = self.ser.read(128)
                if res and len(res) >= 9 and res[3] == 0x03:
                    pts = int.from_bytes(res[8:10], 'little')
                    if sensor.startswith("掌心"): pts = min(pts, self.palm_sensor_limit)
                    self.distribution_points_cache[sensor] = pts
                    self.log(f" - {sensor}: 包含 {pts} 个测力点")
        self.log("查询完毕！\n" + "="*40)

    # ================= 核心功能 3：模组合力读取 (单次查询用) =================
    def read_module_forces(self):
        if not self.ser or not self.ser.is_open: return self.log("请先连接设备")
        self.ser.write(self.build_request_frame(0x03, 0x0500, (168).to_bytes(2, 'little')))
        time.sleep(0.05)
        res = self.ser.read(1024)
        if res and len(res) > 8 and res[3] == 0x03:
            data = res[8:-1]
            self.log("="*40 + "\n手动查询模组合力(前4个示例):")
            for i in range(min(len(data)//6, 4)):
                fx = data[i*6] if data[i*6] <= 127 else data[i*6] - 256
                fy = data[i*6+2] if data[i*6+2] <= 127 else data[i*6+2] - 256
                fz = data[i*6+4]
                self.log(f" 模组{i}: Fx={fx*0.1:.1f}N, Fy={fy*0.1:.1f}N, Fz={fz*0.1:.1f}N")
            self.log("="*40)

    # ================= 核心功能 4：自动回传流解析 =================
    def start_auto_receive(self):
        if not self.connected_sensors or not self.distribution_points_cache:
            return messagebox.showwarning("警告", "请先按顺序执行步骤1和步骤2！")
        
        self.ser.write(self.build_request_frame(0x10, 0x0017, b"\x01")) # 写入1开启
        self.auto_receive_running = True
        self.clear_log()
        self.log("▶ 自动回传已开启，正在解析数据流...")
        self.auto_receive_loop()

    def stop_auto_receive(self):
        self.auto_receive_running = False
        if self.ser and self.ser.is_open:
            self.ser.write(self.build_request_frame(0x10, 0x0017, b"\x00")) # 写入0关闭
            self.log("■ 自动回传已停止")

    def auto_receive_loop(self):
        if not self.auto_receive_running or not self.ser or not self.ser.is_open: return
        try:
            if self.ser.in_waiting > 0:
                response = self.ser.read(self.ser.in_waiting)
                frame_start = response.find(b"\xAA\x56")
                
                if frame_start != -1:
                    frame = response[frame_start:]
                    if len(frame) >= 5:
                        frame_len = int.from_bytes(frame[3:5], 'little')
                        total_len = 5 + frame_len + 1
                        if len(frame) >= total_len:
                            # 校验通过
                            if self.calculate_lrc(frame[:total_len-1]) == frame[total_len-1]:
                                data_payload = frame[6:total_len-1]
                                self.parse_and_format_stream(data_payload)
        except Exception as e:
            print(f"解析错误: {e}")
            
        self.root.after(10, self.auto_receive_loop)

    def parse_and_format_stream(self, data: bytes):
        # 【界面刷新节流阀】：每 1 秒仅打印一次，防止界面卡顿
        current_time = time.time()
        should_print_ui = False
        if current_time - self.last_log_time > 1.0:
            should_print_ui = True
            self.last_log_time = current_time
            self.clear_log() # 清空旧数据，保持界面整洁
            self.log(f"刷新时间: {time.strftime('%H:%M:%S')} | 当前接入传感器: [{', '.join(self.connected_sensors)}]\n" + "-"*60)

        offset = 0
        parse_order = [
            "大拇指近节", "大拇指中节", "大拇指指尖", "大拇指指甲",
            "食指近节", "食指中节", "食指指尖", "食指指甲",
            "中指近节", "中指中节", "中指指尖", "中指指甲",
            "无名指近节", "无名指中节", "无名指指尖", "无名指指甲",
            "小拇指近节", "小拇指中节", "小拇指指尖", "小拇指指甲",
            "掌心1", "掌心2", "掌心3", "掌心4", "掌心5", "掌心6", "掌心7", "掌心8"
        ]

        for sensor in parse_order:
            if sensor not in self.connected_sensors: continue
            
            # 1. 读取合力 (6字节)
            if offset + 6 > len(data): break
            fx_raw = data[offset] if data[offset] <= 127 else data[offset] - 256
            fy_raw = data[offset+2] if data[offset+2] <= 127 else data[offset+2] - 256
            fz_raw = data[offset+4]
            fx, fy, fz = fx_raw*0.1, fy_raw*0.1, fz_raw*0.1
            offset += 6

            # 2. 读取分布力 (点数 * 3字节)
            pts_count = self.distribution_points_cache.get(sensor, 0)
            dist_len = pts_count * 3
            if offset + dist_len > len(data): break
            dist_data = data[offset : offset + dist_len]
            offset += dist_len

            # 如果触发了UI打印，则格式化输出
            if should_print_ui:
                self.log(f"【{sensor}】合力数值: Fx={fx:.1f}N, Fy={fy:.1f}N, Fz={fz:.1f}N")
                
                # 格式化各个测力点
                points_str_list = []
                for i in range(pts_count):
                    px_raw = dist_data[i*3] if dist_data[i*3] <= 127 else dist_data[i*3] - 256
                    py_raw = dist_data[i*3+1] if dist_data[i*3+1] <= 127 else dist_data[i*3+1] - 256
                    pz_raw = dist_data[i*3+2]
                    
                    points_str_list.append(f"P{i+1}({px_raw*0.1:.1f}, {py_raw*0.1:.1f}, {pz_raw*0.1:.1f})")
                
                # 每 8 个点换行，排版更美观
                wrapped_points = "\n    ".join([", ".join(points_str_list[i:i+8]) for i in range(0, len(points_str_list), 8)])
                self.log(f"  各测力点数值 (Fx, Fy, Fz):\n    {wrapped_points}\n")

if __name__ == "__main__":
    root = tk.Tk()
    app = HighSpeedCommBoardSimplified(root)
    root.mainloop()