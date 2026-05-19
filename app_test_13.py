import serial
import serial.tools.list_ports
import time
import math
import random
import threading
import traceback
import webbrowser
from flask import Flask, render_template_string
from flask_socketio import SocketIO
from threading import Timer

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# ==========================================
# 1. 前端 HTML/JS (动态多模组UI面板版)
# ==========================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>高组触觉集成板 - 3D数字孪生系统</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
    <style>
        body { margin: 0; padding: 0; background-color: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; display: flex; height: 100vh; overflow: hidden; }
        .sidebar { width: 320px; background: #1e293b; padding: 20px; box-sizing: border-box; display: flex; flex-direction: column; border-right: 1px solid #334155; z-index: 10;}
        h2 { margin-top: 0; font-size: 1.2rem; color: #38bdf8; text-align: center; border-bottom: 1px solid #334155; padding-bottom: 15px;}
        .control-group { margin-bottom: 15px; }
        label { font-size: 0.85rem; color: #94a3b8; display: block; margin-bottom: 5px; }
        input, select { width: 100%; background: #0f172a; border: 1px solid #334155; color: #fff; padding: 8px; border-radius: 4px; box-sizing: border-box; }
        button { width: 100%; padding: 10px; background: #0284c7; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; margin-top: 5px; transition: background 0.3s; }
        button:hover { background: #0369a1; }
        .btn-stop { background: #dc2626; } .btn-stop:hover { background: #b91c1c; }
        .terminal { flex-grow: 1; background: #000; border: 1px solid #334155; border-radius: 4px; margin-top: 15px; padding: 10px; font-family: monospace; font-size: 0.75rem; color: #4ade80; overflow-y: auto; }
        .main-content { flex-grow: 1; position: relative; }
        #canvas-container { position: absolute; width: 100%; height: 100%; }
        
        /* 动态数据列表容器样式 */
        .overlay-panel { position: absolute; top: 20px; left: 20px; width: 280px; background: rgba(30, 41, 59, 0.85); padding: 15px; border-radius: 8px; border: 1px solid #334155; backdrop-filter: blur(4px); pointer-events: none; z-index: 10; display: flex; flex-direction: column; max-height: calc(100vh - 70px);}
        .panel-header { color:#38bdf8; font-weight:bold; margin-bottom:10px; border-bottom: 1px solid #334155; padding-bottom: 8px; font-size: 1.1rem;}
        #sensorForceContainer { overflow-y: auto; flex-grow: 1; padding-right: 5px; }
        
        /* 滚动条美化 */
        #sensorForceContainer::-webkit-scrollbar { width: 6px; }
        #sensorForceContainer::-webkit-scrollbar-track { background: rgba(0,0,0,0.2); border-radius: 3px;}
        #sensorForceContainer::-webkit-scrollbar-thumb { background: #475569; border-radius: 3px; }
        #sensorForceContainer::-webkit-scrollbar-thumb:hover { background: #64748b; }

        /* 传感器数据卡片样式 */
        .sensor-card { margin-bottom: 10px; padding: 10px; background: rgba(15, 23, 42, 0.6); border-radius: 6px; border-left: 3px solid #38bdf8; }
        .sensor-card-title { color: #facc15; font-weight: bold; font-size: 0.95rem; margin-bottom: 6px; }
        .sensor-card-data { display: flex; justify-content: space-between; font-size: 0.85rem; color: #cbd5e1; }
        .sensor-card-data span { color: #fff; font-family: monospace; font-weight: bold;}

        .legend { position: absolute; bottom: 30px; right: 30px; background: rgba(30, 41, 59, 0.8); padding: 10px 15px; border-radius: 8px; border: 1px solid #334155; text-align: center; z-index: 10;}
        .legend-bar { width: 120px; height: 10px; background: linear-gradient(to right, #3b82f6, #22c55e, #eab308, #ef4444); border-radius: 5px; margin: 5px 0; }
        .legend-labels { display: flex; justify-content: space-between; font-size: 0.7rem; color: #94a3b8; }
    </style>
</head>
<body>
    <div class="sidebar">
        <h2>Paxtini 高速数据中心</h2>
        <div class="control-group">
            <label>串口 (输入 SIM 开启脱机模拟)</label>
            <input type="text" id="comPort" value="COM3" placeholder="例如: COM3">
        </div>
        <button id="btnConnect">1. 连接硬件与底层握手</button>
        <div style="margin-top:20px;"></div>
        <button id="btnAutoStart">2. 开启高速自动回传</button>
        <button id="btnAutoStop" class="btn-stop">停止回传</button>
        <div class="terminal" id="terminal">系统初始化完成...<br>等待连接...<br></div>
    </div>
    
    <div class="main-content">
        <div id="canvas-container"></div>
        
        <div class="overlay-panel">
            <div class="panel-header">已连接模组实时受力</div>
            <div id="sensorForceContainer">
                <div style="color: #64748b; font-size: 0.85rem; text-align: center; margin-top: 10px;">等待硬件握手与数据传输...</div>
            </div>
        </div>
        
        <div class="legend">
            <div style="font-size: 0.8rem; margin-bottom:5px;">合力强度映射</div>
            <div class="legend-bar"></div>
            <div class="legend-labels"><span>0N</span><span>>15N</span></div>
        </div>
    </div>
    <script>
        const socket = io();
        function logMsg(msg) {
            const term = document.getElementById('terminal');
            term.innerHTML += `[Sys] ${msg}<br>`;
            term.scrollTop = term.scrollHeight;
        }
        
        document.getElementById('btnConnect').onclick = () => { socket.emit('cmd_connect', {port: document.getElementById('comPort').value}); };
        document.getElementById('btnAutoStart').onclick = () => { socket.emit('cmd_start'); };
        document.getElementById('btnAutoStop').onclick = () => { socket.emit('cmd_stop'); };
        
        socket.on('sys_log', (data) => { 
            logMsg(data.msg); 
            // 监听：一旦侦测到重新握手，自动清空数据面板，准备迎接新的传感器
            if(data.msg.includes("开始底层物理握手") || data.msg.includes("进入前端脱机模拟测试模式")) {
                document.getElementById('sensorForceContainer').innerHTML = "";
            }
        });

        // ========================= 3D 渲染引擎 =========================
        const container = document.getElementById('canvas-container');
        const scene = new THREE.Scene();
        scene.background = new THREE.Color(0x0f172a); 
        
        const gridHelper = new THREE.GridHelper(50, 50, 0x444444, 0x222222);
        gridHelper.position.y = -5;
        scene.add(gridHelper);
        const axesHelper = new THREE.AxesHelper(10);
        scene.add(axesHelper);

        const camera = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 0.1, 1000);
        camera.position.set(0, 0, 45); 

        const renderer = new THREE.WebGLRenderer({ antialias: true });
        renderer.setSize(container.clientWidth, container.clientHeight);
        container.appendChild(renderer.domElement);

        const controls = new THREE.OrbitControls(camera, renderer.domElement);
        controls.target.set(0, 5, 0);

        scene.add(new THREE.AmbientLight(0xffffff, 0.6)); 
        const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
        dirLight.position.set(20, 30, 20);
        scene.add(dirLight);

        const moduleMeshes = {};
        function forceToColor(val) {
            let t = Math.max(0, Math.min(1, val / 15.0)); 
            const h = (1.0 - t) * 0.6; 
            return new THREE.Color().setHSL(h, 0.8, 0.5);
        }

        const jointGeo = new THREE.CylinderGeometry(0.8, 0.8, 2.5, 16);
        const palmGeo = new THREE.BoxGeometry(2.5, 2.5, 0.5);
        const baseMat = new THREE.MeshPhongMaterial({ color: 0x4aa3df, shininess: 50 }); 

        const fingerNames = ["大拇指", "食指", "中指", "无名指", "小拇指"];
        const segmentNames = ["近节", "中节", "指尖", "指甲"];
        const layoutConfig = {
            "大拇指": { x: -7, y: -2, angleZ: 0.8, step: 3.0 },
            "食指":   { x: -3, y: 5, angleZ: 0.1, step: 3.0 },
            "中指":   { x: 0,  y: 6, angleZ: 0.0, step: 3.2 },
            "无名指": { x: 3,  y: 5.5, angleZ: -0.1, step: 3.0 },
            "小拇指": { x: 6,  y: 4, angleZ: -0.3, step: 2.6 }
        };

        fingerNames.forEach(fName => {
            const config = layoutConfig[fName];
            let currentX = config.x;
            let currentY = config.y;
            segmentNames.forEach((sName, index) => {
                const mesh = new THREE.Mesh(jointGeo, baseMat.clone());
                currentX += Math.sin(-config.angleZ) * (index === 0 ? 0 : config.step);
                currentY += Math.cos(-config.angleZ) * (index === 0 ? 0 : config.step);
                mesh.position.set(currentX, currentY, (index === 3 ? 0.3 : 0)); 
                mesh.rotation.z = config.angleZ;
                scene.add(mesh);
                moduleMeshes[fName + sName] = mesh;
            });
        });

        const palmOffsetX = -3.0;
        const palmOffsetY = -2.0;
        for(let i=1; i<=8; i++) {
            const mesh = new THREE.Mesh(palmGeo, baseMat.clone());
            const row = Math.floor((i-1) / 3);
            const col = (i-1) % 3;
            mesh.position.set(palmOffsetX + col * 3.0, palmOffsetY + row * 3.0, 0);
            scene.add(mesh);
            moduleMeshes["掌心" + i] = mesh;
        }

        // ========================= 核心：动态 UI 列表更新 =========================
        socket.on('hand_data_update', (data) => {
            const containerUI = document.getElementById('sensorForceContainer');

            data.modules.forEach(mod => {
                // 1. 更新 3D 孪生模型状态
                const mesh = moduleMeshes[mod.sensor];
                if (mesh) {
                    const fx = mod.total_force.scaled[0];
                    const fy = mod.total_force.scaled[1];
                    const fz = mod.total_force.scaled[2];
                    const mag = Math.sqrt(fx*fx + fy*fy + fz*fz);
                    
                    mesh.material.color = forceToColor(mag);
                    mesh.material.emissive = forceToColor(mag).multiplyScalar(0.2);
                    const scale = 1.0 + Math.min(mag / 15.0, 1.0) * 0.3;
                    mesh.scale.set(scale, scale, scale);

                    // 2. 动态生成或更新 UI 卡片 (防闪烁复用设计)
                    let card = document.getElementById('card-' + mod.sensor);
                    
                    if (!card) {
                        // 如果卡片不存在，动态创建它
                        card = document.createElement('div');
                        card.id = 'card-' + mod.sensor;
                        card.className = 'sensor-card';
                        card.innerHTML = `
                            <div class="sensor-card-title">${mod.sensor}</div>
                            <div class="sensor-card-data">
                                <div>Fx: <span id="fx-${mod.sensor}">0.0</span></div>
                                <div>Fy: <span id="fy-${mod.sensor}">0.0</span></div>
                                <div>Fz: <span id="fz-${mod.sensor}">0.0</span></div>
                            </div>
                        `;
                        containerUI.appendChild(card);
                    }

                    // 如果卡片已存在，精准只更新里面的数值，绝不重建 DOM，保证极致丝滑
                    document.getElementById(`fx-${mod.sensor}`).textContent = fx.toFixed(1);
                    document.getElementById(`fy-${mod.sensor}`).textContent = fy.toFixed(1);
                    document.getElementById(`fz-${mod.sensor}`).textContent = fz.toFixed(1);
                }
            });
        });

        function animate() { requestAnimationFrame(animate); controls.update(); renderer.render(scene, camera); }
        setTimeout(() => { animate(); }, 200);
        window.onresize = () => { camera.aspect = container.clientWidth / container.clientHeight; camera.updateProjectionMatrix(); renderer.setSize(container.clientWidth, container.clientHeight); };
    </script>
</body>
</html>
"""

# ==========================================
# 2. 深度重构的 Python 后台：动态拓扑握手与帧解析
# ==========================================
class WebTactileBackend:
    def __init__(self):
        self.ser = None
        self.is_running = False
        self.is_sim_mode = False
        self.palm_sensor_limit = 9
        
        # 核心缓存库
        self.connected_sensors = []
        self.distribution_points_cache = {}
        
        # 全局传感器标准排序序列 (映射至比特位)
        self.sensor_flat_list = [
            "大拇指近节", "大拇指中节", "大拇指指尖", "大拇指指甲",
            "食指近节", "食指中节", "食指指尖", "食指指甲",
            "中指近节", "中指中节", "中指指尖", "中指指甲",
            "无名指近节", "无名指中节", "无名指指尖", "无名指指甲",
            "小拇指近节", "小拇指中节", "小拇指指尖", "小拇指指甲",
            "掌心1", "掌心2", "掌心3", "掌心4",
            "掌心5", "掌心6", "掌心7", "掌心8"
        ]

        self.parse_order = [
            ["大拇指近节", "大拇指中节", "大拇指指尖", "大拇指指甲"],
            ["食指近节", "食指中节", "食指指尖", "食指指甲"],
            ["中指近节", "中指中节", "中指指尖", "中指指甲"],
            ["无名指近节", "无名指中节", "无名指指尖", "无名指指甲"],
            ["小拇指近节", "小拇指中节", "小拇指指尖", "小拇指指甲"],
            ["掌心1", "掌心2", "掌心3", "掌心4", "掌心5", "掌心6", "掌心7", "掌心8"]
        ]

    def emit_log(self, msg):
        print(f"[Log] {msg}")
        socketio.emit('sys_log', {'msg': msg})

    def calculate_lrc(self, data: bytes) -> int:
        lrc = 0
        for byte in data:
            lrc = (lrc + byte) & 0xFF
        return ((~lrc) + 1) & 0xFF

    def build_request_frame(self, func_code: int, reg_addr: int, data: bytes = b"", read_len: int = 0) -> bytes:
        head = b"\x55\xAA\x00"  
        reg_addr_bytes = reg_addr.to_bytes(2, byteorder='little', signed=False)
        if func_code == 0x03:
            data_len_bytes = read_len.to_bytes(2, byteorder='little', signed=False)
            frame_body = head + bytes([func_code]) + reg_addr_bytes + data_len_bytes
        else:
            data_len_bytes = len(data).to_bytes(2, byteorder='little', signed=False)
            frame_body = head + bytes([func_code]) + reg_addr_bytes + data_len_bytes + data
        lrc = self.calculate_lrc(frame_body)
        return frame_body + bytes([lrc])

    def _read_register_sync(self, addr, length):
        """同步读取底层寄存器的工具函数"""
        self.ser.reset_input_buffer()
        req = self.build_request_frame(0x03, addr, b"", read_len=length)
        self.ser.write(req)
        time.sleep(0.05)
        if self.ser.in_waiting:
            res = self.ser.read(self.ser.in_waiting)
            if b"\xAA\x55" in res:
                idx = res.find(b"\xAA\x55")
                if len(res) >= idx + 8:
                    d_len = int.from_bytes(res[idx+6:idx+8], byteorder='little')
                    if len(res) >= idx + 8 + d_len + 1:
                        return res[idx+8 : idx+8+d_len]
        return None

    def _hardware_handshake(self):
        """执行握手：动态侦测已连接设备与点数"""
        if self.is_sim_mode or not self.ser: 
            # SIM 模式默认虚拟几个传感器进行展示，或者全部展示
            self.connected_sensors = ["大拇指指尖", "食指中节", "中指指尖", "掌心1"] 
            self.emit_log(f"SIM 测试：虚拟接入 {len(self.connected_sensors)} 个传感器。")
            return
            
        self.emit_log("开始底层物理握手：正在侦测传感器连接状态...")
        self.connected_sensors = []
        self.distribution_points_cache = {}
        
        # 1. 扫描拓扑寄存器 (0010 - 0013)
        status_bytes = []
        for addr in [0x0010, 0x0011, 0x0012, 0x0013]:
            res = self._read_register_sync(addr, 1)
            status_bytes.append(res[0] if res else 0)
            
        for i, sensor in enumerate(self.sensor_flat_list):
            byte_idx = i // 8
            bit_idx = i % 8
            if status_bytes[byte_idx] & (1 << bit_idx):
                self.connected_sensors.append(sensor)
                
        self.emit_log(f"握手完成！板卡上真实插入了 {len(self.connected_sensors)} 个传感器。")

        # 2. 动态查询每个连接传感器的真实测点数 (0030, 0032...)
        for sensor in self.connected_sensors:
            idx = self.sensor_flat_list.index(sensor)
            if idx < 20:
                addr = 0x0030 + idx * 2
            else:
                addr = 0x0066 + (idx - 20) * 2
                
            res = self._read_register_sync(addr, 2)
            if res and len(res) >= 2:
                pts = int.from_bytes(res[:2], byteorder='little', signed=False)
                self.distribution_points_cache[sensor] = pts
                self.emit_log(f"[{sensor}] 动态配置完成：含 {pts} 个有效受力测点")
            else:
                self.distribution_points_cache[sensor] = 16 
                self.emit_log(f"[{sensor}] 警告：测点查询超时，已降级回默认 16 点模式")

    def connect(self, port):
        if port.upper() == "SIM":
            self.is_sim_mode = True
            self.emit_log("已进入前端脱机模拟测试模式！")
            self._hardware_handshake()
            return True

        self.is_sim_mode = False
        try:
            self.ser = serial.Serial(port=port, baudrate=921600, timeout=0.1)
            self.emit_log(f"硬件串口 {port} 物理通道开启成功！")
            threading.Thread(target=self._hardware_handshake, daemon=True).start()
            return True
        except Exception as e:
            self.emit_log(f"连接失败: {str(e)}")
            return False

    def start_auto_receive(self):
        if self.is_running: return
        self.is_running = True
        self.emit_log("启动高速回传引擎...")
        
        if self.is_sim_mode:
            threading.Thread(target=self._sim_loop, daemon=True).start()
        else:
            if self.ser and self.ser.is_open:
                req_frame = self.build_request_frame(0x10, 0x0017, b"\x01")
                self.ser.write(req_frame)
                threading.Thread(target=self._hardware_loop, daemon=True).start()

    def stop_auto_receive(self):
        self.is_running = False
        if not self.is_sim_mode and self.ser and self.ser.is_open:
            req_frame = self.build_request_frame(0x10, 0x0017, b"\x00")
            self.ser.write(req_frame)
        self.emit_log("已停止数据回传。")

    def parse_auto_receive_force_data(self, data: bytes):
        parsed = []
        current_offset = 0
        
        for group in self.parse_order:
            for sensor_name in group:
                if sensor_name not in self.connected_sensors:
                    continue
                
                if current_offset + 6 > len(data): return parsed
                force_data = data[current_offset : current_offset+6]
                current_offset += 6
                
                fx_low = force_data[0]
                fy_low = force_data[2]
                fz_low = force_data[4]
                
                fx_raw = fx_low if fx_low <= 127 else fx_low - 256
                fy_raw = fy_low if fy_low <= 127 else fy_low - 256
                fz_raw = fz_low
                
                parsed.append({
                    "sensor": sensor_name,
                    "total_force": {
                        "scaled": [round(fx_raw * 0.1, 1), round(fy_raw * 0.1, 1), round(fz_raw * 0.1, 1)]
                    }
                })
                
                point_count = self.distribution_points_cache.get(sensor_name, 16)
                if sensor_name.startswith("掌心"):
                    actual_points = min(point_count, self.palm_sensor_limit)
                    current_offset += actual_points * 3
                else:
                    current_offset += point_count * 3
                    
        return parsed

    def _sim_loop(self):
        t = 0
        while self.is_running:
            data_payload = []
            t += 0.1
            for idx, sensor in enumerate(self.connected_sensors):
                phase = idx * 0.2
                force_val = max(0, math.sin(t + phase) * 20 - 5) + random.uniform(0, 1.5)
                data_payload.append({
                    "sensor": sensor,
                    "total_force": { "scaled": [0, force_val, 0] }
                })
            socketio.emit('hand_data_update', {"modules": data_payload})
            socketio.sleep(0.05) 

    def _hardware_loop(self):
        buffer = bytearray()
        while self.is_running and self.ser and self.ser.is_open:
            try:
                if self.ser.in_waiting:
                    buffer.extend(self.ser.read(self.ser.in_waiting))
                    
                    while b"\xAA\x56" in buffer:
                        idx = buffer.find(b"\xAA\x56")
                        buffer = buffer[idx:] 
                        if len(buffer) < 5: break
                            
                        frame_len = int.from_bytes(buffer[3:5], byteorder='little')
                        total_len = 5 + frame_len + 1 
                        
                        if len(buffer) >= total_len:
                            frame = buffer[:total_len]
                            buffer = buffer[total_len:] 
                            
                            frame_body = frame[:-1]
                            lrc = frame[-1]
                            if self.calculate_lrc(frame_body) == lrc:
                                payload = frame[6:-1]
                                parsed_data = self.parse_auto_receive_force_data(payload)
                                if parsed_data:
                                    socketio.emit('hand_data_update', {"modules": parsed_data})
                        else:
                            break
                else:
                    socketio.sleep(0.005)
            except Exception as e:
                self.emit_log(f"读取异常: {str(e)}")
                traceback.print_exc()

# ==========================================
# 4. Flask 路由系统
# ==========================================
backend = WebTactileBackend()

@app.route('/')
def index(): return render_template_string(HTML_TEMPLATE)

@socketio.on('cmd_connect')
def handle_connect(data): backend.connect(data.get('port', 'SIM'))

@socketio.on('cmd_start')
def handle_start(): backend.start_auto_receive()

@socketio.on('cmd_stop')
def handle_stop(): backend.stop_auto_receive()

def open_browser(): webbrowser.open_new("http://127.0.0.1:5000")

if __name__ == '__main__':
    print("🌐 [Web] 启动 3D 传感器数字孪生服务器...")
    Timer(1.5, open_browser).start()
    try:
        socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)
    except TypeError:
        socketio.run(app, host='0.0.0.0', port=5000, debug=False)