import serial
import time
import struct
import serial.tools.list_ports
import logging
from typing import Optional

# -------------------------- 设备协议配置 --------------------------
BAUDRATE = 921600                    # 高速通信波特率 [cite: 276]
REQ_HEAD = b"\x55\xAA"               # 主机请求帧头 [cite: 312]
RESP_HEAD_AUTO_PUSH = b"\xAA\x56"    # 自动回传数据帧头 [cite: 329]

# 寄存器地址
AUTO_PUSH_CONF_REG = 0x0016          # 数据类型组合 (0x03=合力+分布力) [cite: 388]
AUTO_PUSH_EN_REG = 0x0017            # 自动回传使能开关 [cite: 388]
SCALE_FACTOR = 0.1                   # 精度转换因子：1 LSB = 0.1N 

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class PaxiniPhysicalSensor:
    def __init__(self, port: str):
        # 初始化串口，设置间隙超时以保证高速数据帧完整 [cite: 276]
        self.ser = serial.Serial(
            port=port, baudrate=BAUDRATE, timeout=1, 
            inter_byte_timeout=0.005
        )

    def calc_lrc(self, data: bytes) -> int:
        """计算LRC校验：所有字节累加后取反加一 [cite: 85]"""
        lrc_sum = sum(data) & 0xFF
        return ((~lrc_sum) + 1) & 0xFF

    def build_frame(self, func: int, addr: int, length: int, data: bytes = b"") -> bytes:
        """构建请求帧：Head + 预留 + 功能码 + 地址 + 长度 + 数据 + LRC [cite: 312]"""
        frame = REQ_HEAD + b"\x00" + bytes([func]) + \
                addr.to_bytes(2, "little") + length.to_bytes(2, "little") + data
        return frame + bytes([self.calc_lrc(frame)])

    def initialize(self):
        """配置传感器回传模式"""
        # 设置回传内容为：合力 + 分布力 [cite: 388]
        self.ser.write(self.build_frame(0x10, AUTO_PUSH_CONF_REG, 1, b"\x03"))
        time.sleep(0.1)
        # 开启自动回传 [cite: 336]
        self.ser.write(self.build_frame(0x10, AUTO_PUSH_EN_REG, 1, b"\x01"))
        logger.info("传感器初始化完成，开始输出实际受力值 (N)...")

    def parse_physical_data(self, frame: bytes):
        """解析原始帧并转换为实际力值 (N)"""
        if len(frame) < 7: return
        
        # 1. 输出原始 Hex 流，便于对照 [cite: 329]
        print(f"\n[{time.strftime('%H:%M:%S')}] 原始数据: {frame.hex().upper()}")

        # 提取数据负载 (跳过前6字节帧头相关信息) [cite: 329]
        payload = frame[6:-1]
        
        # 2. 解析合力 (Total Force)
        if len(payload) >= 6:
            # Fx, Fy, Fz 均为小端序 16位有符号整数 [cite: 395]
            fx_raw, fy_raw, fz_raw = struct.unpack('<hhh', payload[:6])
            fx_n = fx_raw * SCALE_FACTOR
            fy_n = fy_raw * SCALE_FACTOR
            fz_n = fz_raw * SCALE_FACTOR
            print(f"  >>> 传感器总合力: Fx={fx_n:.2f}N, Fy={fy_n:.2f}N, Fz={fz_n:.2f}N")

        # 3. 解析分布力 (Distributed Force)
        dist_data = payload[6:]
        total_points = len(dist_data) // 3  # 每个测点占 3 字节 [cite: 263]
        
        if total_points > 0:
            print(f"  >>> 各测点实际受力 (单位: Newton):")
            for i in range(total_points):
                offset = i * 3
                # fx, fy 为有符号字节(b), fz 为无符号字节(B) 
                fx_raw, fy_raw, fz_raw = struct.unpack('<bbB', dist_data[offset:offset+3])
                
                # 转换为物理量
                fx_n, fy_n, fz_n = fx_raw * SCALE_FACTOR, fy_raw * SCALE_FACTOR, fz_raw * SCALE_FACTOR
                
                # 输出格式：点位:(x, y, z)
                print(f"    P{i+1:03d}:({fx_n:>5.1f},{fy_n:>5.1f},{fz_n:>4.1f})", end=" | ")
                if (i + 1) % 4 == 0:  # 每行输出4个测点
                    print("")
            print("\n" + "-"*80)

    def run(self):
        try:
            self.initialize()
            while True:
                # 帧同步：查找 AA 56 帧头 [cite: 331]
                if self.ser.in_waiting >= 2:
                    if self.ser.read(1) == b'\xAA' and self.ser.read(1) == b'\x56':
                        self.ser.read(1) # 跳过预留 [cite: 329]
                        len_bytes = self.ser.read(2)
                        v_len = int.from_bytes(len_bytes, "little") # 有效帧长度 [cite: 329]
                        body = self.ser.read(v_len + 1) # 错误码 + 数据 + LRC [cite: 329]
                        full_frame = b'\xAA\x56\x00' + len_bytes + body
                        self.parse_physical_data(full_frame)
        except KeyboardInterrupt:
            # 停止回传 [cite: 340]
            self.ser.write(self.build_frame(0x10, AUTO_PUSH_EN_REG, 1, b"\x00"))
            logger.info("用户停止采集。")
        finally:
            self.ser.close()

if __name__ == "__main__":
    available_ports = list(serial.tools.list_ports.comports())
    if available_ports:
        for idx, p in enumerate(available_ports):
            print(f"{idx}: {p.device}")
        choice = int(input("请选择连接高速板的串口序号: "))
        sensor = PaxiniPhysicalSensor(available_ports[choice].device)
        sensor.run()
    else:
        print("未检测到串口设备。")