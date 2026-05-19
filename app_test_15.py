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
# 1. 前端 HTML/JS (新增弹窗隐藏标签功能)
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
    <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/renderers/CSS2DRenderer.js"></script>
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
        
        .overlay-panel { position: absolute; top: 20px; left: 20px; width: 280px; background: rgba(30, 41, 59, 0.85); padding: 15px; border-radius: 8px; border: 1px solid #334155; backdrop-filter: blur(4px); pointer-events: none; z-index: 10; display: flex; flex-direction: column; max-height: calc(100vh - 70px);}
        .panel-header { color:#38bdf8; font-weight:bold; margin-bottom:10px; border-bottom: 1px solid #334155; padding-bottom: 8px; font-size: 1.1rem;}
        #sensorForceContainer { overflow-y: auto; flex-grow: 1; padding-right: 5px; pointer-events: auto; }
        
        #sensorForceContainer::-webkit-scrollbar { width: 6px; }
        #sensorForceContainer::-webkit-scrollbar-track { background: rgba(0,0,0,0.2); border-radius: 3px;}
        #sensorForceContainer::-webkit-scrollbar-thumb { background: #475569; border-radius: 3px; }
        #sensorForceContainer::-webkit-scrollbar-thumb:hover { background: #64748b; }

        .sensor-card { margin-bottom: 10px; padding: 10px; background: rgba(15, 23, 42, 0.6); border-radius: 6px; border-left: 3px solid #38bdf8; }
        
        .sensor-card-title { color: #facc15; font-weight: bold; font-size: 1.05rem; margin-bottom: 6px; cursor: pointer; transition: all 0.2s; display: inline-block; padding: 2px 5px; border-radius: 4px; border: 1px solid transparent; }
        .sensor-card-title:hover { background: rgba(250, 204, 21, 0.2); border: 1px solid #facc15; text-shadow: 0 0 8px rgba(250, 204, 21, 0.5); }
        .sensor-card-title::after { content: ' 📊'; font-size: 0.8rem; opacity: 0.7; }
        
        .sensor-card-data { display: flex; justify-content: space-between; font-size: 0.85rem; color: #cbd5e1; }
        .sensor-card-data span { color: #fff; font-family: monospace; font-weight: bold;}

        /* 微观分布力 3D 弹窗 */
        .modal-overlay { display: none; position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: rgba(0, 0, 0, 0.75); backdrop-filter: blur(5px); z-index: 100; justify-content: center; align-items: center; }
        .modal-box { background: #1e293b; width: 85vw; height: 85vh; border-radius: 12px; border: 1px solid #475569; display: flex; flex-direction: column; overflow: hidden; box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5); }
        .modal-header { padding: 15px 20px; background: #0f172a; border-bottom: 1px solid #475569; display: flex; justify-content: space-between; align-items: center; }
        .modal-title { color: #facc15; font-size: 1.2rem; font-weight: bold; margin: 0; }
        .close-btn { background: transparent; border: none; color: #94a3b8; font-size: 1.5rem; cursor: pointer; padding: 0; margin: 0; line-height: 1; }
        .close-btn:hover { color: #ef4444; }
        .modal-toolbar { padding: 10px 20px; background: #1e293b; border-bottom: 1px solid #334155; display: flex; gap: 20px; align-items: center; font-size: 0.9rem;}
        
        /* 弹窗内的次级按钮样式 */
        .toolbar-btn { background: #334155; color: #fff; border: 1px solid #475569; padding: 5px 12px; border-radius: 4px; cursor: pointer; font-size: 0.85rem; transition: background 0.2s; margin-top: 0; width: auto; display: inline-block;}
        .toolbar-btn:hover { background: #475569; }

        #modal-canvas { flex-grow: 1; position: relative; background: #000; }
        .point-label { color: #fff; font-size: 12px; background: rgba(0,0,0,0.5); padding: 2px 4px; border-radius: 3px; pointer-events: none; transition: opacity 0.2s; }
    </style>
</head>
<body>
    <div class="sidebar">
        <h2>Paxtini 高速数据中心</h2>
        <div class="control-group">
            <label>串口 (输入 SIM 开启脱机模拟)</label>
            <input type="text" id="comPort" value="COM3">
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
    </div>

    <div class="modal-overlay" id="drillDownModal">
        <div class="modal-box">
            <div class="modal-header">
                <h3 class="modal-title" id="modalSensorName">-- 测点分布图</h3>
                <button class="close-btn" onclick="closeSensorModal()">×</button>
            </div>
            <div class="modal-toolbar">
                <div>
                    <strong style="color:#38bdf8;">📂 导入测点坐标 (.csv): </strong>
                    <input type="file" id="csvFileInput" accept=".csv" style="width:200px; padding:0; border:none;">
                    <span id="uploadStatus" style="font-size:0.85rem; margin-left:10px;"></span>
                </div>
                <button id="btnToggleModalLabels" class="toolbar-btn">隐藏编号</button>
                <div>
                    <label>测点大小: </label>
                    <input type="range" id="sizeSlider" min="0.1" max="5.0" step="0.1" value="1.0" style="width:100px; vertical-align: middle;">
                </div>
            </div>
            <div id="modal-canvas"></div>
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
            if(data.msg.includes("开始底层物理握手") || data.msg.includes("进入前端脱机模拟测试模式")) {
                document.getElementById('sensorForceContainer').innerHTML = "";
            }
        });

        // ========================= 宏观主场景 =========================
        const container = document.getElementById('canvas-container');
        const scene = new THREE.Scene();
        scene.background = new THREE.Color(0x0f172a); 
        const gridHelper = new THREE.GridHelper(50, 50, 0x444444, 0x222222);
        gridHelper.position.y = -5;
        scene.add(gridHelper);
        scene.add(new THREE.AxesHelper(10));

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

        const layoutConfig = {
            "大拇指": { x: -7, y: -2, angleZ: 0.8, step: 3.0 },
            "食指":   { x: -3, y: 5, angleZ: 0.1, step: 3.0 },
            "中指":   { x: 0,  y: 6, angleZ: 0.0, step: 3.2 },
            "无名指": { x: 3,  y: 5.5, angleZ: -0.1, step: 3.0 },
            "小拇指": { x: 6,  y: 4, angleZ: -0.3, step: 2.6 }
        };

        ["大拇指", "食指", "中指", "无名指", "小拇指"].forEach(fName => {
            const config = layoutConfig[fName];
            let currentX = config.x, currentY = config.y;
            ["近节", "中节", "指尖", "指甲"].forEach((sName, index) => {
                const mesh = new THREE.Mesh(jointGeo, baseMat.clone());
                currentX += Math.sin(-config.angleZ) * (index === 0 ? 0 : config.step);
                currentY += Math.cos(-config.angleZ) * (index === 0 ? 0 : config.step);
                mesh.position.set(currentX, currentY, (index === 3 ? 0.3 : 0)); 
                mesh.rotation.z = config.angleZ;
                scene.add(mesh);
                moduleMeshes[fName + sName] = mesh;
            });
        });

        for(let i=1; i<=8; i++) {
            const mesh = new THREE.Mesh(palmGeo, baseMat.clone());
            mesh.position.set(-3.0 + ((i-1)%3)*3.0, -2.0 + Math.floor((i-1)/3)*3.0, 0);
            scene.add(mesh);
            moduleMeshes["掌心" + i] = mesh;
        }

        // ========================= 弹窗微观分析引擎 =========================
        let currentModalSensor = null;
        const sensorCoordinateMaps = {}; 
        
        // 新增状态控制：记录弹窗中标签的显示状态
        let modalLabelsVisible = true;
        
        const modalContainer = document.getElementById('modal-canvas');
        const modalScene = new THREE.Scene();
        modalScene.background = new THREE.Color(0x1e293b);
        modalScene.add(new THREE.AmbientLight(0xffffff, 0.7));
        
        let modalPointsGroup = new THREE.Group();
        modalScene.add(modalPointsGroup);
        
        const modalCamera = new THREE.PerspectiveCamera(45, 1, 0.1, 1000);
        modalCamera.position.set(0, 0, 100);
        
        const modalRenderer = new THREE.WebGLRenderer({ antialias: true });
        modalContainer.appendChild(modalRenderer.domElement);
        
        const modalLabelRenderer = new THREE.CSS2DRenderer();
        modalLabelRenderer.domElement.style.position = 'absolute';
        modalLabelRenderer.domElement.style.top = '0px';
        modalLabelRenderer.domElement.style.pointerEvents = 'none';
        modalContainer.appendChild(modalLabelRenderer.domElement);

        const modalControls = new THREE.OrbitControls(modalCamera, modalRenderer.domElement);
        const modalNodes = new Map(); 

        function updateUploadStatus() {
            const statusEl = document.getElementById('uploadStatus');
            if (sensorCoordinateMaps[currentModalSensor]) {
                statusEl.innerHTML = `✅ 已加载专属坐标: <b>${sensorCoordinateMaps[currentModalSensor].length}</b> 点`;
                statusEl.style.color = "#4ade80";
            } else {
                statusEl.innerHTML = `⚠️ 暂未上传该传感器的坐标文件`;
                statusEl.style.color = "#fbbf24";
            }
        }

        function openSensorModal(sensorName) {
            currentModalSensor = sensorName;
            document.getElementById('modalSensorName').innerText = sensorName + " - 测点受力分布模型";
            document.getElementById('drillDownModal').style.display = 'flex';
            document.getElementById('csvFileInput').value = ''; 
            
            updateUploadStatus();
            rebuildModalScene(); 
            
            setTimeout(() => {
                const w = modalContainer.clientWidth;
                const h = modalContainer.clientHeight;
                modalCamera.aspect = w / h;
                modalCamera.updateProjectionMatrix();
                modalRenderer.setSize(w, h);
                modalLabelRenderer.setSize(w, h);
            }, 50);
        }

        function closeSensorModal() {
            document.getElementById('drillDownModal').style.display = 'none';
            currentModalSensor = null;
        }
        
        // 绑定切换按钮的点击事件
        document.getElementById('btnToggleModalLabels').onclick = function() {
            modalLabelsVisible = !modalLabelsVisible;
            // 更新按钮文字
            this.textContent = modalLabelsVisible ? "隐藏编号" : "显示编号";
            // 实时更新当前沙盒中所有标签的可见性
            modalNodes.forEach(node => { 
                if (node.label) {
                    node.label.visible = modalLabelsVisible; 
                }
            });
        };

        function rebuildModalScene() {
            if (modalPointsGroup) {
                modalScene.remove(modalPointsGroup);
                modalPointsGroup.traverse(child => {
                    if (child.geometry) child.geometry.dispose();
                    if (child.material) child.material.dispose();
                });
            }
            
            document.querySelectorAll('#modal-canvas .point-label').forEach(el => el.remove());
            
            modalPointsGroup = new THREE.Group();
            modalScene.add(modalPointsGroup);
            modalNodes.clear();

            const coords = sensorCoordinateMaps[currentModalSensor];
            if (!coords || coords.length === 0) return;

            let minX=Infinity, maxX=-Infinity, minY=Infinity, maxY=-Infinity, minZ=Infinity, maxZ=-Infinity;

            coords.forEach(p => {
                if (modalNodes.has(p.id.toString())) {
                    const oldNode = modalNodes.get(p.id.toString());
                    modalPointsGroup.remove(oldNode.sphere);
                    modalPointsGroup.remove(oldNode.arrow);
                    if (oldNode.label && oldNode.label.element) oldNode.label.element.remove();
                }

                if(p.x < minX) minX = p.x; if(p.x > maxX) maxX = p.x;
                if(p.y < minY) minY = p.y; if(p.y > maxY) maxY = p.y;
                if(p.z < minZ) minZ = p.z; if(p.z > maxZ) maxZ = p.z;

                const sphere = new THREE.Mesh(
                    new THREE.SphereGeometry(1, 16, 16),
                    new THREE.MeshPhongMaterial({ color: 0x00E5FF, emissive: 0x004466, shininess: 100 })
                );
                sphere.position.set(p.x, p.y, p.z);
                const initialScale = parseFloat(document.getElementById('sizeSlider').value) || 1.0;
                sphere.scale.set(initialScale, initialScale, initialScale);
                
                const labelDiv = document.createElement('div');
                labelDiv.className = 'point-label';
                labelDiv.textContent = 'P' + p.id;
                const label = new THREE.CSS2DObject(labelDiv);
                label.position.set(0, 2, 0); 
                // 创建标签时，智能继承当前的隐藏/显示状态
                label.visible = modalLabelsVisible;
                sphere.add(label);

                const arrow = new THREE.ArrowHelper(new THREE.Vector3(0,1,0), new THREE.Vector3(p.x,p.y,p.z), 0.01, 0x00ff00, 0.01, 0.01);
                arrow.visible = false;
                
                modalPointsGroup.add(sphere);
                modalPointsGroup.add(arrow);

                modalNodes.set(p.id.toString(), { sphere, arrow, label });
            });

            const cx = (minX + maxX)/2, cy = (minY + maxY)/2, cz = (minZ + maxZ)/2;
            modalControls.target.set(cx, cy, cz);
            let maxDim = Math.max(maxX-minX, maxY-minY, maxZ-minZ);
            if (maxDim <= 0.1 || !isFinite(maxDim)) maxDim = 30; 
            modalCamera.position.set(cx, cy + maxDim * 1.5, cz + maxDim * 1.5);
        }

        document.getElementById('sizeSlider').oninput = (e) => {
            const scale = parseFloat(e.target.value);
            modalNodes.forEach(node => { node.sphere.scale.set(scale, scale, scale); });
        };

        document.getElementById('csvFileInput').onchange = (e) => {
            const file = e.target.files[0];
            if (!file || !currentModalSensor) return;
            
            const reader = new FileReader();
            reader.onload = (event) => {
                const lines = event.target.result.split(/\\r?\\n/); 
                const parsedCoords = [];

                lines.slice(1).forEach(line => {
                    const cols = line.split(',');
                    if (cols.length < 4) return;
                    const id = cols[0].trim(), x = parseFloat(cols[1])||0, y = parseFloat(cols[2])||0, z = parseFloat(cols[3])||0;
                    parsedCoords.push({id, x, y, z});
                });

                sensorCoordinateMaps[currentModalSensor] = parsedCoords;
                updateUploadStatus();
                rebuildModalScene(); 
            };
            reader.readAsText(file);
        };

        // ========================= 数据推送监听 =========================
        socket.on('hand_data_update', (data) => {
            const containerUI = document.getElementById('sensorForceContainer');

            data.modules.forEach(mod => {
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

                    let card = document.getElementById('card-' + mod.sensor);
                    if (!card) {
                        card = document.createElement('div');
                        card.id = 'card-' + mod.sensor;
                        card.className = 'sensor-card';
                        card.innerHTML = `
                            <div class="sensor-card-title" onclick="openSensorModal('${mod.sensor}')">${mod.sensor}</div>
                            <div class="sensor-card-data">
                                <div>Fx: <span id="fx-${mod.sensor}">0.0</span></div>
                                <div>Fy: <span id="fy-${mod.sensor}">0.0</span></div>
                                <div>Fz: <span id="fz-${mod.sensor}">0.0</span></div>
                            </div>
                        `;
                        containerUI.appendChild(card);
                    }

                    document.getElementById(`fx-${mod.sensor}`).textContent = fx.toFixed(1);
                    document.getElementById(`fy-${mod.sensor}`).textContent = fy.toFixed(1);
                    document.getElementById(`fz-${mod.sensor}`).textContent = fz.toFixed(1);
                }
                
                if (mod.sensor === currentModalSensor && document.getElementById('drillDownModal').style.display === 'flex') {
                    if(mod.dist_force && mod.dist_force.length > 0){
                        mod.dist_force.forEach(p => {
                            const node = modalNodes.get(p.id.toString());
                            if (node) {
                                const mag = Math.sqrt(p.x**2 + p.y**2 + p.z**2);
                                if (mag > 0.1) {
                                    node.arrow.visible = true;
                                    const dir = new THREE.Vector3(p.x, p.y, p.z).normalize();
                                    node.arrow.setDirection(dir);
                                    const len = Math.max(Math.min(mag * 0.8, 15), 0.1); 
                                    node.arrow.setLength(len, len*0.3, len*0.2);
                                    node.arrow.setColor(forceToColor(mag));
                                } else {
                                    node.arrow.visible = false;
                                }
                            }
                        });
                    }
                }
            });
        });

        function animate() { 
            requestAnimationFrame(animate); 
            controls.update(); 
            renderer.render(scene, camera); 
            
            if(document.getElementById('drillDownModal').style.display === 'flex') {
                modalControls.update();
                modalRenderer.render(modalScene, modalCamera);
                modalLabelRenderer.render(modalScene, modalCamera);
            }
        }
        setTimeout(() => { animate(); }, 200);
        
        window.onresize = () => { 
            camera.aspect = container.clientWidth / container.clientHeight; 
            camera.updateProjectionMatrix(); 
            renderer.setSize(container.clientWidth, container.clientHeight); 
        };
    </script>
</body>
</html>
"""

# ==========================================
# 2. 深度重构的 Python 后台 (保持不变)
# ==========================================
class WebTactileBackend:
    def __init__(self):
        self.ser = None
        self.is_running = False
        self.is_sim_mode = False
        self.palm_sensor_limit = 9
        
        self.connected_sensors = []
        self.distribution_points_cache = {}
        
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
        for byte in data: lrc = (lrc + byte) & 0xFF
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
        if self.is_sim_mode or not self.ser: 
            self.connected_sensors = ["大拇指指尖", "中指中节", "掌心1"] 
            self.distribution_points_cache = {"大拇指指尖": 52, "中指中节": 16, "掌心1": 117}
            self.emit_log(f"SIM 测试：虚拟接入 {len(self.connected_sensors)} 个传感器。")
            return
            
        self.emit_log("开始底层物理握手：正在侦测传感器连接状态...")
        self.connected_sensors = []
        self.distribution_points_cache = {}
        
        status_bytes = []
        for addr in [0x0010, 0x0011, 0x0012, 0x0013]:
            res = self._read_register_sync(addr, 1)
            status_bytes.append(res[0] if res else 0)
            
        for i, sensor in enumerate(self.sensor_flat_list):
            if status_bytes[i // 8] & (1 << (i % 8)):
                self.connected_sensors.append(sensor)
                
        self.emit_log(f"握手完成！板卡上真实插入了 {len(self.connected_sensors)} 个传感器。")

        for sensor in self.connected_sensors:
            idx = self.sensor_flat_list.index(sensor)
            addr = 0x0030 + idx * 2 if idx < 20 else 0x0066 + (idx - 20) * 2
            res = self._read_register_sync(addr, 2)
            if res and len(res) >= 2:
                pts = int.from_bytes(res[:2], byteorder='little', signed=False)
                self.distribution_points_cache[sensor] = pts
                self.emit_log(f"[{sensor}] 动态配置完成：含 {pts} 个有效受力测点")
            else:
                self.distribution_points_cache[sensor] = 16 

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
                if sensor_name not in self.connected_sensors: continue
                if current_offset + 6 > len(data): return parsed
                
                force_data = data[current_offset : current_offset+6]
                current_offset += 6
                
                fx_low, fy_low, fz_low = force_data[0], force_data[2], force_data[4]
                fx_raw = fx_low if fx_low <= 127 else fx_low - 256
                fy_raw = fy_low if fy_low <= 127 else fy_low - 256
                
                point_count = self.distribution_points_cache.get(sensor_name, 16)
                actual_points = min(point_count, self.palm_sensor_limit) if sensor_name.startswith("掌心") else point_count
                
                dist_force_list = []
                for i in range(actual_points):
                    idx = current_offset + i * 3
                    if idx + 3 > len(data): break
                    
                    px_raw = data[idx] if data[idx] <= 127 else data[idx] - 256
                    py_raw = data[idx+1] if data[idx+1] <= 127 else data[idx+1] - 256
                    pz_raw = data[idx+2]
                    
                    dist_force_list.append({
                        "id": i + 1,
                        "x": round(px_raw * 0.1, 1),
                        "y": round(py_raw * 0.1, 1),
                        "z": round(pz_raw * 0.1, 1)
                    })
                
                current_offset += actual_points * 3
                
                parsed.append({
                    "sensor": sensor_name,
                    "total_force": { "scaled": [round(fx_raw * 0.1, 1), round(fy_raw * 0.1, 1), round(fz_low * 0.1, 1)] },
                    "dist_force": dist_force_list
                })
                    
        return parsed

    def _sim_loop(self):
        t = 0
        while self.is_running:
            data_payload = []
            t += 0.1
            for idx, sensor in enumerate(self.connected_sensors):
                phase = idx * 0.2
                force_val = max(0, math.sin(t + phase) * 15 - 3) + random.uniform(0, 1.0)
                
                pts_count = self.distribution_points_cache.get(sensor, 52)
                mock_dist = []
                for p_id in range(pts_count):
                    px = math.sin(t * 2 + p_id * 0.1) * 3
                    py = math.cos(t * 1.5 + p_id * 0.1) * 3
                    pz = max(0, math.sin(t + phase + p_id*0.05) * 12)
                    mock_dist.append({"id": p_id + 1, "x": round(px,1), "y": round(py,1), "z": round(pz,1)})
                
                data_payload.append({
                    "sensor": sensor,
                    "total_force": { "scaled": [0, force_val, 0] },
                    "dist_force": mock_dist
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