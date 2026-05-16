import serial      # 导入串口通信库，用于与传感器硬件进行物理连接和数据读取
import time        # 导入时间库，用于控制循环延迟和计算时间间隔
import struct      # 导入结构体转换库，核心！用于将底层发来的“二进制字节流”翻译成Python能看懂的数字
import threading   # 导入多线程库，让“读取硬件数据”和“运行Web网页”能同时进行
import traceback   # 导入异常追踪库，如果后台报错，能打印出详细的错误行号
from flask import Flask, render_template_string   # 导入 Web 框架 Flask，用于提供网页访问服务
from flask_socketio import SocketIO               # 导入 SocketIO，建立服务器与网页之间的 WebSocket 实时数据通道
import webbrowser  # 导入浏览器控制库
from threading import Timer # 导入定时器，用于延迟打开浏览器


# 初始化 Web 服务
app = Flask(__name__)      # 创建一个 Flask 网页应用实例
socketio = SocketIO(app, cors_allowed_origins="*")    # 包装这个应用，开启全双工实时通信，并允许任何域名跨域访问

# 传感器配置
BAUDRATE = 921600                      # 波特率
AUTO_PUSH_FRAME_HEAD = b"\xAA\x56"     # 帧头
PORT_NAME = 'COM3'                     # 串口

# ==========================================
# 网页前端 HTML + JS 代码
# ==========================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>高组触觉传感器监测屏</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/renderers/CSS2DRenderer.js"></script>
    
    <style>
        body { background-color: #121212; color: #ffffff; font-family: 'Segoe UI', sans-serif; margin: 0; padding: 20px; }
        .header { text-align: center; margin-bottom: 20px; }
        .cards { display: flex; justify-content: space-around; margin-bottom: 20px; }
        .card { background-color: #1e1e1e; padding: 15px; border-radius: 10px; width: 25%; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
        .card h3 { margin: 0; color: #888; font-size: 14px; }
        .value { font-size: 2em; font-weight: bold; }
        .val-fx { color: #FF5722; } .val-fy { color: #4CAF50; } .val-fz { color: #2196F3; }
        
        #chart-container { width: 100%; height: 500px; background-color: #1e1e1e; border-radius: 10px; margin-bottom: 20px; padding-top: 10px; }
        
        .model-section { background-color: #1e1e1e; border-radius: 10px; padding: 20px; position: relative; }
        .controls { margin-bottom: 15px; display: flex; align-items: center; gap: 25px; flex-wrap: wrap; }
        
        #model-container { width: 100%; height: 600px; background-color: #000; border-radius: 8px; overflow: hidden; position: relative; }
        .point-label { color: #fff; font-size: 12px; background: rgba(0,0,0,0.5); padding: 2px 4px; border-radius: 3px; pointer-events: none; }
        
        #legend {
            position: absolute; right: 20px; top: 100px; bottom: 100px;
            width: 50px; background: rgba(30,30,30,0.8);
            border: 1px solid #444; border-radius: 5px;
            display: flex; flex-direction: column; align-items: center; padding: 10px 0;
            z-index: 10; pointer-events: none;
        }
        .legend-bar {
            width: 15px; flex-grow: 1;
            background: linear-gradient(to top, #0000ff, #00ffff, #00ff00, #ffff00, #ff0000);
            border-radius: 10px; margin: 5px 0;
        }
        .legend-text { font-size: 11px; color: #ccc; }

        input[type=range] { cursor: pointer; }
        button { padding: 6px 12px; cursor: pointer; background: #333; color: #fff; border: 1px solid #555; border-radius: 4px; transition: 0.2s; }
        button:hover { background: #555; }

        .table-section { background-color: #1e1e1e; border-radius: 10px; padding: 20px; margin-top: 20px; }
        .table-container { max-height: 400px; overflow-y: auto; border-radius: 5px; border: 1px solid #333; }
        table { width: 100%; border-collapse: collapse; text-align: center; }
        th, td { padding: 12px; border-bottom: 1px solid #333; font-size: 14px; }
        th { position: sticky; top: 0; background-color: #2c2c2c; color: #fff; z-index: 1; }
        tbody tr:hover { background-color: #2a2a2a; }
        
        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-track { background: #121212; }
        ::-webkit-scrollbar-thumb { background: #555; border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: #888; }
    </style>
</head>
<body>
    <div class="header"><h1>高组触觉传感器监控系统</h1></div>
    
    <div class="cards">
        <div class="card"><h3>X轴合力</h3><div class="value val-fx" id="fx-text">0.0 N</div></div>
        <div class="card"><h3>Y轴合力</h3><div class="value val-fy" id="fy-text">0.0 N</div></div>
        <div class="card"><h3>Z轴合力</h3><div class="value val-fz" id="fz-text">0.0 N</div></div>
    </div>
    
    <div id="chart-container"></div>

    <div class="model-section">
        <div class="controls">
            <strong style="font-size: 18px;">🌐 3D 实时分布视图</strong>
            <input type="file" id="csvFileInput" accept=".csv" style="color: #ccc;">
            <button id="btnToggleLabels">切换编号显示</button>
            <div><label>受力点大小: </label><input type="range" id="sizeSlider" min="0.1" max="5.0" step="0.1" value="1.0"></div>
        </div>

        <div id="model-container">
            <div id="legend">
                <div class="legend-text">15N</div>
                <div class="legend-bar"></div>
                <div class="legend-text">0N</div>
                <div style="font-size: 10px; margin-top: 5px; color: #888; text-align: center;">合力<br>幅值</div>
            </div>
        </div>
    </div>

    <div class="table-section">
        <h3>📊 测点实时受力明细</h3>
        <div class="table-container">
            <table id="force-table">
                <thead><tr><th>测点 ID</th><th>Fx (N)</th><th>Fy (N)</th><th>Fz (N)</th><th style="color: #ffeb3b;">合力 (N)</th></tr></thead>
                <tbody id="force-table-body"></tbody>
            </table>
        </div>
    </div>

    <script>
        // ==========================================
        // 1. 恢复：完整的 ECharts 多网格折线图初始化
        // ==========================================
        const myChart = echarts.init(document.getElementById('chart-container'), 'dark');
        const maxPoints = 160; 
        let timeData = [], fxData = [], fyData = [], fzData = [];
        let lastChartUpdate = 0; 
        let lastTableUpdate = 0; 

        const option = {
            backgroundColor: 'transparent',
            tooltip: { trigger: 'axis', axisPointer: { type: 'cross', animation: false } },
            axisPointer: { link: [{ xAxisIndex: 'all' }] },
            grid: [
                { left: 60, right: 40, top: '5%', height: '22%' },
                { left: 60, right: 40, top: '34%', height: '22%' },
                { left: 60, right: 40, top: '63%', height: '22%' }
            ],
            xAxis: [
                { type: 'category', data: timeData, gridIndex: 0, splitLine: { show: false }, axisLabel: { show: false }, axisTick: { show: false } },
                { type: 'category', data: timeData, gridIndex: 1, splitLine: { show: false }, axisLabel: { show: false }, axisTick: { show: false } },
                { 
                    type: 'category', data: timeData, gridIndex: 2, splitLine: { show: false },
                    axisTick: { show: true, interval: function (index) { return (timeData.length - 1 - index) % 20 === 0; } },
                    axisLabel: { interval: function (index) { return (timeData.length - 1 - index) % 20 === 0; }, hideOverlap: false, rotate: 45, color: '#888' }
                } 
            ],
            yAxis: [
                { type: 'value', min: -10, max: 15, name: 'Fx (N)', gridIndex: 0, nameTextStyle: { color: '#FF5722', fontWeight: 'bold' }, splitLine: { lineStyle: { color: '#333' } } },
                { type: 'value', min: -10, max: 15, name: 'Fy (N)', gridIndex: 1, nameTextStyle: { color: '#4CAF50', fontWeight: 'bold' }, splitLine: { lineStyle: { color: '#333' } } },
                { type: 'value', min: -10, max: 15, name: 'Fz (N)', gridIndex: 2, nameTextStyle: { color: '#2196F3', fontWeight: 'bold' }, splitLine: { lineStyle: { color: '#333' } } }
            ],
            series: [
                { name: 'Fx', type: 'line', xAxisIndex: 0, yAxisIndex: 0, data: fxData, lineStyle: { color: '#FF5722' }, showSymbol: false, animation: false, areaStyle: { color: 'rgba(255,87,34,0.1)' } },
                { name: 'Fy', type: 'line', xAxisIndex: 1, yAxisIndex: 1, data: fyData, lineStyle: { color: '#4CAF50' }, showSymbol: false, animation: false, areaStyle: { color: 'rgba(76,175,80,0.1)' } },
                { name: 'Fz', type: 'line', xAxisIndex: 2, yAxisIndex: 2, data: fzData, lineStyle: { color: '#2196F3' }, showSymbol: false, animation: false, areaStyle: { color: 'rgba(33,150,243,0.1)' } }
            ]
        };
        myChart.setOption(option);

        // ==========================================
        // 2. Three.js 与 标签渲染器初始化
        // ==========================================
        const container = document.getElementById('model-container');
        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 1, 1000);
        camera.position.set(50, 80, 100);

        const renderer = new THREE.WebGLRenderer({ antialias: true });
        renderer.setSize(container.clientWidth, container.clientHeight);
        container.appendChild(renderer.domElement);

        const labelRenderer = new THREE.CSS2DRenderer();
        labelRenderer.setSize(container.clientWidth, container.clientHeight);
        labelRenderer.domElement.style.position = 'absolute';
        labelRenderer.domElement.style.top = '0px';
        labelRenderer.domElement.style.pointerEvents = 'none'; 
        container.appendChild(labelRenderer.domElement);

        const controls = new THREE.OrbitControls(camera, renderer.domElement);
        scene.add(new THREE.AmbientLight(0xffffff, 0.6));
        
        const sensorNodes = new Map();
        let labelsVisible = true;

        function animate() {
            requestAnimationFrame(animate);
            controls.update();
            renderer.render(scene, camera);
            labelRenderer.render(scene, camera);
        }
        animate();

        function getForceColor(val) {
            let v = Math.max(0, Math.min(1, val / 15.0));
            return new THREE.Color().setHSL((1 - v) * 0.7, 1.0, 0.5);
        }

        // ==========================================
        // 3. UI 事件绑定
        // ==========================================
        document.getElementById('btnToggleLabels').onclick = () => {
            labelsVisible = !labelsVisible;
            sensorNodes.forEach(node => { node.label.visible = labelsVisible; });
        };

        document.getElementById('sizeSlider').oninput = (e) => {
            const scale = parseFloat(e.target.value);
            sensorNodes.forEach(node => { node.sphere.scale.set(scale, scale, scale); });
        };

        document.getElementById('csvFileInput').onchange = (e) => {
            const file = e.target.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = (event) => {
                sensorNodes.forEach(n => { scene.remove(n.sphere); scene.remove(n.arrow); scene.remove(n.label); });
                sensorNodes.clear();

                const lines = event.target.result.split(/\\r?\\n/); 
                let minX=Infinity, maxX=-Infinity, minY=Infinity, maxY=-Infinity, minZ=Infinity, maxZ=-Infinity;

                lines.slice(1).forEach(line => {
                    const cols = line.split(',');
                    if (cols.length < 4) return;
                    const id = cols[0].trim(), x = float(cols[1]), y = float(cols[2]), z = float(cols[3]);

                    if(x < minX) minX = x; if(x > maxX) maxX = x;
                    if(y < minY) minY = y; if(y > maxY) maxY = y;
                    if(z < minZ) minZ = z; if(z > maxZ) maxZ = z;

                    // 受力点建模颜色
                    const sphere = new THREE.Mesh(
                        new THREE.SphereGeometry(1, 16, 16),
                        new THREE.MeshPhongMaterial({ 
                            color: 0x00E5FF,       // 主颜色：鲜艳的亮青色
                            emissive: 0x004466,    // 自发光颜色：增加一点内部的幽光，防死黑
                            shininess: 100         // 高光泽度：让球体看起来有玻璃或金属的光泽
                        })
                    );
                    sphere.position.set(x, y, z);
                    // 初始化时应用当前的缩放滑块值
                    const initialScale = parseFloat(document.getElementById('sizeSlider').value);
                    sphere.scale.set(initialScale, initialScale, initialScale);
                    scene.add(sphere);

                    const labelDiv = document.createElement('div');
                    labelDiv.className = 'point-label';
                    labelDiv.textContent = 'P' + id;
                    const label = new THREE.CSS2DObject(labelDiv);
                    label.position.set(0, 2, 0); 
                    label.visible = labelsVisible;
                    sphere.add(label);

                    const arrow = new THREE.ArrowHelper(new THREE.Vector3(0,1,0), new THREE.Vector3(x,y,z), 0.01, 0x00ff00, 0.01, 0.01);
                    arrow.visible = false;
                    scene.add(arrow);

                    sensorNodes.set(id, { sphere, arrow, label });
                });

                // 视角居中
                const cx = (minX + maxX)/2, cy = (minY + maxY)/2, cz = (minZ + maxZ)/2;
                controls.target.set(cx, cy, cz);
                const maxDim = Math.max(maxX-minX, maxY-minY, maxZ-minZ);
                camera.position.set(cx, cy + maxDim * 1.5, cz + maxDim * 1.5);
            };
            reader.readAsText(file);
        };
        function float(v){ return parseFloat(v) || 0; }

        // ==========================================
        // 4. WebSocket 通信逻辑与数据更新
        // ==========================================
        
        // 连接到后端的 WebSocket 服务器
        const socket = io();

        // 监听后端发来的名为 'force_update' 的数据包
        socket.on('force_update', (data) => {
            const nowMs = Date.now();              // 获取当前时间的毫秒数，用于控制界面的刷新频率

            // 更新顶部卡片：找到对应的 HTML 标签，把 Fx, Fy, Fz 填进去，保留1位小数
            document.getElementById('fx-text').textContent = data.fx.toFixed(1) + " N";
            document.getElementById('fy-text').textContent = data.fy.toFixed(1) + " N";
            document.getElementById('fz-text').textContent = data.fz.toFixed(1) + " N";

            // ECharts 数据压入与更新逻辑，更新 ECharts 折线图
            const now = new Date();
            // 拼装当前时间字符串 (例如 "14:30:25:123") 作为 X 轴坐标
            const timeStr = [now.getHours(), now.getMinutes(), now.getSeconds(), now.getMilliseconds()]
                            .map(d => d.toString().padStart(2, '0')).join(':').slice(0, 12);
            
            // 将新数据推入数组末尾                
            timeData.push(timeStr); fxData.push(data.fx); fyData.push(data.fy); fzData.push(data.fz);
            
            // 如果数据点超过 maxPoints (160个)，就把最旧的一个踢掉，实现向左滚动的效果
            if (timeData.length > maxPoints) { 
                timeData.shift(); fxData.shift(); fyData.shift(); fzData.shift(); 
            }
            

            // 频率控制：每 50 毫秒才让图表重新渲染一次，防止浏览器卡死
            if (nowMs - lastChartUpdate > 50) {
                myChart.setOption({
                    xAxis: [{ data: timeData }, { data: timeData }, { data: timeData }],
                    series: [{ data: fxData }, { data: fyData }, { data: fzData }]
                });
                lastChartUpdate = nowMs;      // 更新最后一次渲染的时间
            }

            // Three.js  3D模型  底部表格 数据更新
            if (data.dist_data) {
                let tableHtml = '';          // 准备一个空字符串，用来拼接 HTML 表格行
                
                // 遍历所有测点数据 (p 代表 point)
                data.dist_data.forEach(p => {
                    // 使用勾股定理计算这个测点的“合力”大小
                    const mag = Math.sqrt(p.x**2 + p.y**2 + p.z**2);
                    // 从 3D 场景中找出与当前测点 ID 对应的小球对象
                    const node = sensorNodes.get(p.id.toString());
                    
                    if (node) {
                        // 如果这个点的受力大于 0.1 N，就显示 3D 箭头
                        if (mag > 0.1) {
                            node.arrow.visible = true;      // 显示箭头
                            const dir = new THREE.Vector3(p.x, p.y, p.z).normalize();    // 计算受力的方向向量
                            node.arrow.setDirection(dir);   // 让箭头指向受力方向
                            const len = Math.max(mag * 2.5, 0.1);    // 根据力的大小计算箭头的长度
                            node.arrow.setLength(len, len*0.3, len*0.2);   // 设置箭头长度和箭头脑袋的大小
                            node.arrow.setColor(getForceColor(mag));       // 根据力的大小给箭头涂色（蓝->红）
                        } else {
                            node.arrow.visible = false;     // 受力太小，隐藏箭头
                        }
                    }
                    // 频率控制：每 200 毫秒拼接一次表格 HTML
                    if (nowMs - lastTableUpdate > 200) {
                        tableHtml += `<tr>
                            <td style="color:#ddd; font-weight:bold;">P${p.id}</td>
                            <td class="val-fx">${p.x.toFixed(1)}</td>
                            <td class="val-fy">${p.y.toFixed(1)}</td>
                            <td class="val-fz">${p.z.toFixed(1)}</td>
                            <td style="color:#ffeb3b; font-weight:bold;">${mag.toFixed(2)} N</td>
                        </tr>`;
                    }
                });
                

                // 把拼接好的 HTML 塞进网页表格的 tbody 中
                if (nowMs - lastTableUpdate > 200) {
                    document.getElementById('force-table-body').innerHTML = tableHtml;
                    lastTableUpdate = nowMs;
                }
            }
        });

        // 窗口自适应
        window.onresize = () => {
            myChart.resize();
            camera.aspect = container.clientWidth / container.clientHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(container.clientWidth, container.clientHeight);
            labelRenderer.setSize(container.clientWidth, container.clientHeight);
        };
    </script>
</body>
</html>
"""

# ==========================================
# 后端 Python 逻辑
# ==========================================

# 定义一个打开浏览器的函数
def open_browser():
    webbrowser.open_new("http://127.0.0.1:5000")


# 数据校验函数：LRC (纵向冗余校验)，把数据加起来取反加1，用于判断数据在传输中是否损坏
def calculate_lrc(data_bytes: bytes) -> int:
    lrc_sum = 0
    for byte in data_bytes: 
        lrc_sum = (lrc_sum + byte) & 0xFF
    return ((~lrc_sum) + 1) & 0xFF


# 读取传感器的独立线程
def sensor_read_thread():
    try:
        # 1. 打开串口，设置超时时间为 0.1 秒
        ser = serial.Serial(PORT_NAME, BAUDRATE, timeout=0.1)
        time.sleep(1.5)     # 等待硬件准备好
        
        # 发送特定的十六进制指令给硬件，相当于说：“喂，醒醒，开始发数据了！”
        ser.write(bytes.fromhex("55 AA 00 10 16 00 01 00 03 D7")) 
        time.sleep(0.1)
        ser.write(bytes.fromhex("55 AA 00 10 17 00 01 00 01 D8")) 
        
        buffer = bytearray()    # 创建一个字节缓冲区，用来存放源源不断接收到的字节流
        last_push = 0           # 记录上次推送数据的时间
        

        # 2. 开启死循环，永远监听数据
        while True:
            if ser.in_waiting:    # 如果串口里有数据
                buffer.extend(ser.read(ser.in_waiting))   # 把所有数据吸入 buffer 缓冲区
                
                # 只要缓冲区里有大于 7 个字节（一个完整数据包的最小可能长度），就开始解析
                while len(buffer) >= 7:
                    # 检查前两个字节是不是帧头 0xAA 0x56
                    if buffer[0:2] == AUTO_PUSH_FRAME_HEAD:
                        # 解析第 4 和第 5 个字节，用 '<H' (小端无符号短整型) 翻译出这包数据的标称长度
                        p_len = struct.unpack('<H', buffer[3:5])[0]
                        total_len = 5 + p_len + 1    # 计算这包数据的真实总长度 (头 + 数据 + 校验位)
                        
                        # 防御性编程：如果算出来的长度大得离谱(>8192)，说明数据错乱了，删掉第一个字节重新找帧头
                        if total_len > 8192:
                            del buffer[0]
                            continue

                        # 如果缓冲区里的数据已经收齐了这完整的一包
                        if len(buffer) >= total_len:
                            # 提取校验位并进行比对，验证数据完整性
                            if calculate_lrc(buffer[:total_len-1]) == buffer[total_len-1]:
                                frame = buffer[:total_len]       # 提取这包完美的数据
                                del buffer[:total_len]           # 从缓冲区中删掉已经提取的数据
                                
                                # 开始翻译核心业务数据
                                if p_len >= 7 and len(frame) >= 13: 
                                    # 用 '<hhh' (三个小端有符号短整型) 翻译出整体的 X, Y, Z 合力
                                    fx_r, fy_r, fz_r = struct.unpack('<hhh', frame[6:12])
                                   
                                    # 把剩下直到倒数第二位的数据切出来，这就是各个测点的微观数据
                                    dist_p = frame[12:-1]
                                    dist_list = []
                                    
                                    # 每 3 个字节代表一个测点，循环提取
                                    for i in range(len(dist_p)//3):
                                        # '<bbB': 提取 2个有符号单字节(x,y) 和 1个无符号单字节(z)
                                        px, py, pz = struct.unpack('<bbB', dist_p[i*3:i*3+3])
                                        # 乘以 0.1 恢复真实物理单位，存入字典
                                        dist_list.append({'id':i+1, 'x':px*0.1, 'y':py*0.1, 'z':pz*0.1})
                                    
                                    # 3. 频率控制：最高每秒推送 30 次 (1/0.033) 到前端网页
                                    if time.time() - last_push > 0.033:
                                        socketio.emit('force_update', {
                                            'fx': fx_r*0.1, 
                                            'fy': fy_r*0.1, 
                                            'fz': fz_r*0.1, 
                                            'dist_data': dist_list
                                        })
                                        last_push = time.time()
                            else: 
                                del buffer[0]     # 校验失败，说明是坏数据，扔掉第一个字节继续往后找
                        else: 
                            break                 # 数据还没收齐，跳出内层循环，去串口接着读
                    else: 
                        del buffer[0]             # 没有找到帧头，扔掉第一个字节继续往后找
    except Exception as e:
        print(f"\n❌ 后台线程严重错误: {e}")
        traceback.print_exc()


# 定义 Web 路由：当你在浏览器输入 http://127.0.0.1:5000/ 时，执行这个函数
@app.route('/')
def index():
    # 直接把上面定义的一大长串 HTML_TEMPLATE 字符串当作网页发送给用户
    return render_template_string(HTML_TEMPLATE)


# 主程序入口
if __name__ == '__main__':
    # 启动刚才写的传感器读取线程。daemon=True 表示如果主程序关了，这个线程也会乖乖自动关闭
    threading.Thread(target=sensor_read_thread, daemon=True).start()
    print("\n🌐 Web 服务已启动！")
    print("👉 请打开浏览器访问: http://127.0.0.1:5000\n")
    
# 3. 新增：在启动服务器前，设置一个 1.5 秒后的定时任务
    # 这样可以确保 Flask 已经准备好接收连接时，浏览器才弹出
    Timer(1.5, open_browser).start()


    # 启动 Flask-SocketIO 服务器。开始监听 5000 端口，等待浏览器连接
    try:
        socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)
    except TypeError:
        # 兼容不同版本的库
        socketio.run(app, host='0.0.0.0', port=5000, debug=False)