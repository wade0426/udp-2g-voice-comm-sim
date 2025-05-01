import numpy as np
import sounddevice as sd
from scipy import signal
import socket
import threading
import time
import binascii

# --- 常數設定 ---

CHUNK = 1024
FORMAT = np.float32
RATE = 44100
CHANNELS = 1
BIT_RATE = 1000
F0 = 1000
F1 = 2000
INTERLEAVE_BLOCK_SIZE = 8
VOLUME_SCALE = 1.0
MAX_PACKET_SIZE = 1024
UDP_MAX_SIZE = 1020
CUTOFF_FREQUENCY = 4000  # 預設截止頻率
FILTER_ORDER = 4         # 濾波器階數
# 語音量化與反量化
QUANTIZATION_LEVELS = 256 # 量化等級，使用8位元量化
XOR_KEY = b'SecretKey123' # XOR加密密鑰
USE_ENCRYPTION = False    # 是否使用加密的全局變量
USE_FSK = False           # 是否使用FSK調變的全局變量
USE_INTERLEAVING = False  # 是否使用交錯的全局變量
NOISE_THRESHOLD = 0.01    # 噪聲閾值
NOISE_REDUCTION = 0.5     # 噪聲抑制係數

# --- 訊號處理函數 ---

def process_received_signal(received_signal, fs):
    """
    接收訊號處理
    """
    try:
        if len(received_signal) < 1:
            return np.zeros(CHUNK, dtype=np.float32)
        
        print(f"接收端 - 處理接收訊號，輸入長度: {len(received_signal)}")
        
        # 確保訊號長度合適
        if len(received_signal) < CHUNK:
            received_signal = np.pad(received_signal, (0, CHUNK - len(received_signal)))
        elif len(received_signal) > CHUNK:
            received_signal = received_signal[:CHUNK]
        
        # 直接使用接收的訊號，基本處理
        output_signal = received_signal.copy()
        
        # 噪聲閾值處理
        noise_mask = np.abs(output_signal) < NOISE_THRESHOLD
        output_signal[noise_mask] *= NOISE_REDUCTION
        
        # 應用更嚴格的低通濾波器
        nyquist = fs / 2 # fs是採樣率（44100Hz）
        # 使用更低的截止頻率和更高的濾波器階數
        cutoff = min(3000, CUTOFF_FREQUENCY) / nyquist  # 降低截止頻率
        # 在濾波器設計中使用
        b, a = signal.butter(6, cutoff, btype='low')    # 提高濾波器階數
        output_signal = signal.filtfilt(b, a, output_signal)
        
        # 應用中值濾波器來去除脈衝噪聲
        output_signal = signal.medfilt(output_signal, kernel_size=3)
        
        # 音量調整前的動態範圍壓縮
        output_signal = np.sign(output_signal) * np.abs(output_signal) ** 0.8
        
        # 音量調整
        output_signal = output_signal * VOLUME_SCALE
        output_signal = np.clip(output_signal, -1.0, 1.0)
        
        print(f"接收端 - 輸出訊號長度: {len(output_signal)}, 最大值: {np.max(np.abs(output_signal))}")
        
        return output_signal.astype(np.float32)

    except Exception as e:
        print(f"接收端 - 訊號處理錯誤: {e}")
        return np.zeros(CHUNK, dtype=np.float32)


def quantize_signal(signal, levels=QUANTIZATION_LEVELS):
    """
    將輸入訊號進行量化
    """
    try:
        # 將訊號範圍縮放到 0 到 1 之間
        signal_normalized = (signal + 1) / 2
        # 量化
        quantized = np.round(signal_normalized * (levels - 1))
        return quantized.astype(np.uint8)
    except Exception as e:
        print(f"量化錯誤: {e}")
        return np.zeros_like(signal, dtype=np.uint8)


def dequantize_signal(quantized_signal, levels=QUANTIZATION_LEVELS):
    """
    將量化的訊號進行反量化
    """
    try:
        # 反量化到 0 到 1 範圍
        signal_normalized = quantized_signal / (levels - 1)
        # 還原到 -1 到 1 範圍
        return (signal_normalized * 2 - 1).astype(np.float32)
    except Exception as e:
        print(f"反量化錯誤: {e}")
        return np.zeros_like(quantized_signal, dtype=np.float32)


def xor_encrypt(data, key):
    """
    使用XOR對數據進行加密
    """
    if not isinstance(data, bytes):
        data = data.tobytes()
    
    key_bytes = key * (len(data) // len(key) + 1)
    key_bytes = key_bytes[:len(data)]
    
    encrypted = bytes(a ^ b for a, b in zip(data, key_bytes))
    return encrypted


def xor_decrypt(encrypted_data, key):
    """
    使用XOR對數據進行解密（與加密相同的操作）
    """
    return xor_encrypt(encrypted_data, key)


def fsk_modulate(data, fs):
    """
    FSK調變
    """
    try:
        t = np.arange(len(data)) / fs
        modulated = np.zeros_like(data, dtype=np.float32)
        
        # 根據信號值選擇頻率行調變
        for i in range(len(data)):
            if data[i] >= 0:
                modulated[i] = np.sin(2 * np.pi * F1 * t[i])
            else:
                modulated[i] = np.sin(2 * np.pi * F0 * t[i])
        
        return modulated
    except Exception as e:
        print(f"FSK調變錯誤: {e}")
        return data


def fsk_demodulate(modulated_signal, fs):
    """
    FSK解調
    """
    try:
        t = np.arange(len(modulated_signal)) / fs
        
        # 生成兩個載波信號
        carrier_f0 = np.sin(2 * np.pi * F0 * t)
        carrier_f1 = np.sin(2 * np.pi * F1 * t)
        
        # 相乘並通過低通濾波器
        nyquist = fs / 2
        cutoff = min(F0, F1) / 2 / nyquist
        b, a = signal.butter(4, cutoff, btype='low')
        
        demod_f0 = signal.filtfilt(b, a, modulated_signal * carrier_f0)
        demod_f1 = signal.filtfilt(b, a, modulated_signal * carrier_f1)
        
        # 比較兩個解調信號的能量
        demodulated = np.where(np.abs(demod_f1) > np.abs(demod_f0), 1, -1)
        return demodulated.astype(np.float32)
    except Exception as e:
        print(f"FSK解調錯誤: {e}")
        return modulated_signal


def interleave(data):
    """
    交錯處理
    """
    try:
        data_len = len(data)
        if data_len < INTERLEAVE_BLOCK_SIZE:
            return data
            
        # 將數據重塑為矩陣
        pad_len = (INTERLEAVE_BLOCK_SIZE - (data_len % INTERLEAVE_BLOCK_SIZE)) % INTERLEAVE_BLOCK_SIZE
        padded_data = np.pad(data, (0, pad_len))
        blocks = padded_data.reshape(-1, INTERLEAVE_BLOCK_SIZE)
        
        # 交錯處理
        interleaved = blocks.T.flatten()
        return interleaved[:data_len]
    except Exception as e:
        print(f"交錯處理錯誤: {e}")
        return data


def deinterleave(data):
    """
    解交錯處理
    """
    try:
        data_len = len(data)
        if data_len < INTERLEAVE_BLOCK_SIZE:
            return data
            
        # 將數據重塑為矩陣
        pad_len = (INTERLEAVE_BLOCK_SIZE - (data_len % INTERLEAVE_BLOCK_SIZE)) % INTERLEAVE_BLOCK_SIZE
        padded_data = np.pad(data, (0, pad_len))
        blocks = padded_data.reshape(INTERLEAVE_BLOCK_SIZE, -1)
        
        # 解交錯處理
        deinterleaved = blocks.T.flatten()
        return deinterleaved[:data_len]
    except Exception as e:
        print(f"解交錯處理錯誤: {e}")
        return data

# --- 網路相關函數 ---

def send_audio(sock, audio_stream, remote_ip, remote_port, fs):
    """
    發送訊號
    """
    sequence_number = 0
    RETRY_COUNT = 3
    
    while True:
        try:
            # 1. 音頻採集和電位檢測
            audio_data, overflowed = audio_stream.read(CHUNK)

            # 2. 緩衝溢出檢測
            if overflowed:
                print("輸入緩衝溢出")
                continue

            # 3. 音頻電位檢測
            audio_level = np.max(np.abs(audio_data))  # 峰值檢測
            rms_level = np.sqrt(np.mean(audio_data**2)) # 均方根值檢測
            
            # 4. 靜音檢測
            # 使用RMS值和峰值來判斷是否為有效音頻
            if audio_level < 0.01 or rms_level < 0.005:
                continue
            
            # 5. 預處理音頻數據
            audio_data = audio_data.flatten()
            
            # 6. 噪聲抑制
            # 使用閾值檢測來識別噪聲，去除低於閾值的噪聲
            noise_mask = np.abs(audio_data) < NOISE_THRESHOLD
            audio_data[noise_mask] *= NOISE_REDUCTION
            
            print(f"發送端 - 發送音頻數據，電位: {audio_level:.4f}, RMS: {rms_level:.4f}")
            
            # 7. FSK調變（可選）
            if USE_FSK:
                audio_data = fsk_modulate(audio_data, fs)
            
            # 8. 量化音頻數據
            quantized_data = quantize_signal(audio_data)
            
            # 9. 交錯處理（如果啟用）
            if USE_INTERLEAVING:
                quantized_data = interleave(quantized_data)
            
            # 10. 轉換量化後的數據為位元組
            data_to_send = quantized_data.tobytes()
            
            # 11. 加密（可選）
            # 在發送前加密數據
            if USE_ENCRYPTION:
                data_to_send = xor_encrypt(data_to_send, XOR_KEY)
            
            # 12. 分包發送
            for i in range(0, len(data_to_send), UDP_MAX_SIZE):
                chunk = data_to_send[i:i + UDP_MAX_SIZE]
                
                # 13. 計算前chunk的CRC校驗碼
                crc_value = binascii.crc_hqx(chunk, 0xFFFF)
                crc_bytes = crc_value.to_bytes(2, byteorder='big')
                
                packet_number = sequence_number.to_bytes(2, byteorder='big')
                chunk_index = (i // UDP_MAX_SIZE).to_bytes(2, byteorder='big')
                total_chunks = ((len(data_to_send) - 1) // UDP_MAX_SIZE + 1).to_bytes(2, byteorder='big')
                
                # 14. 裝數據包：包號 + 塊索引 + 總塊數 + CRC + 音頻數據
                packet = packet_number + chunk_index + total_chunks + crc_bytes + chunk
                
                # 15. 重試發送
                for _ in range(RETRY_COUNT):
                    try:
                        sock.sendto(packet, (remote_ip, remote_port))
                        break
                    except Exception as e:
                        print(f"重試發送數據包: {e}")
                        time.sleep(0.001)
            
            sequence_number = (sequence_number + 1) % 65536
            time.sleep(0.001)

        except Exception as e:
            print(f"發送線程錯誤: {e}")
            time.sleep(0.1)


def receive_audio(sock, audio_stream, fs):
    """
    接收訊號
    """
    buffer_dict = {}
    
    while True:
        try:
            # 1. 接收數據包
            data, addr = sock.recvfrom(MAX_PACKET_SIZE + 8)  # +8 因為增加了CRC校驗碼

            # 2. 檢查數據包長度
            if len(data) <= 8:
                continue
                
            # 3. 解析數據包
            packet_number = int.from_bytes(data[0:2], byteorder='big')
            chunk_index = int.from_bytes(data[2:4], byteorder='big')
            total_chunks = int.from_bytes(data[4:6], byteorder='big')
            received_crc = int.from_bytes(data[6:8], byteorder='big')
            audio_chunk = data[8:]
            
            # 4. 驗證CRC校驗碼
            calculated_crc = binascii.crc_hqx(audio_chunk, 0xFFFF)
            
            # 驗證CRC校驗碼
            if calculated_crc != received_crc:
                print(f"CRC校驗失敗，丟棄數據包 {packet_number}, 塊 {chunk_index}")
                print(f"接收到的CRC: {received_crc}, 計算得到的CRC: {calculated_crc}")
                continue
            
            # 5. 緩衝區處理
            if packet_number not in buffer_dict:
                buffer_dict[packet_number] = {}
            buffer_dict[packet_number][chunk_index] = audio_chunk
            
            # 6. 檢查是否到完整的數據包
            if len(buffer_dict[packet_number]) == total_chunks:
                try:
                    # 7. 組裝完整數據包
                    chunks = [buffer_dict[packet_number][i] for i in range(total_chunks)]
                    complete_audio = b''.join(chunks)
                    
                    # 8. 解密（如果啟用）
                    if USE_ENCRYPTION:
                        complete_audio = xor_decrypt(complete_audio, XOR_KEY)
                    
                    # 9. 轉換為 uint8 數組
                    quantized_signal = np.frombuffer(complete_audio, dtype=np.uint8)
                    
                    # 10. 解交錯處理（如果啟用）
                    if USE_INTERLEAVING:
                        quantized_signal = deinterleave(quantized_signal)
                    
                    # 11. 反量化
                    received_signal = dequantize_signal(quantized_signal)
                    
                    # 12. FSK解調（如果啟用）
                    if USE_FSK:
                        received_signal = fsk_demodulate(received_signal, fs)
                    
                    # 13. 處理接收到的訊號
                    processed_signal = process_received_signal(received_signal, fs)
                    
                    # 14. 輸出音頻訊號
                    if np.max(np.abs(processed_signal)) > 0:
                        print(f"接收端 - 輸出音頻訊號，最大振幅: {np.max(np.abs(processed_signal))}")
                        audio_stream.write(processed_signal)
                    
                except Exception as e:
                    print(f"接收端 - 處理音頻數據錯誤: {e}")
                
                # 清理緩衝區
                del buffer_dict[packet_number]
            
            # 清理舊的未完成的數據包
            current_time = time.time()
            old_packets = [pkt for pkt in buffer_dict.keys() if abs(pkt - packet_number) > 100]
            for pkt in old_packets:
                del buffer_dict[pkt]
                
        except socket.timeout:
            continue
        except Exception as e:
            print(f"接收端 - 線程錯誤: {e}")
            continue


def get_local_ip():
    """
    取本機IP地址
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"


def check_audio_devices():
    """
    檢查可用的輸入輸出設備
    """
    print("\n可用的輸入輸出設備:")
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        print(f"{i}: {device['name']}")
    
    # 直接獲取系統默認的輸入輸出設備
    input_device = sd.default.device[0]  
    output_device = sd.default.device[1]
    
    print(f"\n系統自動選擇:")
    print(f"輸入設備 ({input_device}): {devices[input_device]['name']}")
    print(f"輸出設備 ({output_device}): {devices[output_device]['name']}")
    
    return input_device, output_device


def apply_preset_config(preset_number):
    """
    應用預設配置
    """
    global QUANTIZATION_LEVELS, CUTOFF_FREQUENCY, FILTER_ORDER, USE_ENCRYPTION, USE_FSK, USE_INTERLEAVING
    
    if preset_number == 1:  # 高音質模式
        QUANTIZATION_LEVELS = 65536  # 16位元
        CUTOFF_FREQUENCY = 4000      # 較高的截止頻率，高音質模式
        FILTER_ORDER = 8             # 較高的濾波器階數，高音質模式
        USE_ENCRYPTION = False
        USE_FSK = False
        USE_INTERLEAVING = False
        print("\n=== 已套用預設配置 1 (高音質模式) ===")
        
    elif preset_number == 2:  # 低延遲模式
        QUANTIZATION_LEVELS = 16    # 8位元
        CUTOFF_FREQUENCY = 1000      # 較低的截止頻率
        FILTER_ORDER = 2            # 較低的濾波器階數
        USE_ENCRYPTION = False
        USE_FSK = True
        USE_INTERLEAVING = False
        print("\n=== 已套用預設配置 2 (低延遲模式) ===")
        
    else:
        print("無效的預設配置編號")
        return False
    
    # 輸出當前配置
    print(f"量化等級: {QUANTIZATION_LEVELS}")
    print(f"截止頻率: {CUTOFF_FREQUENCY} Hz")
    print(f"濾波器階數: {FILTER_ORDER}")
    print(f"加密: {'啟用' if USE_ENCRYPTION else '停用'}")
    print(f"FSK調變: {'啟用' if USE_FSK else '停用'}")
    print(f"交錯處理: {'啟用' if USE_INTERLEAVING else '停用'}")
    print("=====================\n")
    return True


def main(role="1"):
    global CHUNK, RATE, CUTOFF_FREQUENCY, FILTER_ORDER, QUANTIZATION_LEVELS, USE_ENCRYPTION, USE_FSK, USE_INTERLEAVING
    FORMAT = np.float32
    CHANNELS = 1

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    local_ip = get_local_ip()
    print(f"\n本機IP地址為: {local_ip}")

    # 根據角色設置端口
    if role == "1":
        LOCAL_PORT = 5000
        REMOTE_PORT = 5001
        REMOTE_IP = "172.20.10.2"
    else:
        LOCAL_PORT = 5001
        REMOTE_PORT = 5000
        REMOTE_IP = "172.20.10.3"

    print(f"\n=== 連接配置 ===")
    print(f"本機IP: {local_ip}")
    print(f"本機端口: {LOCAL_PORT}")
    print(f"遠程IP: {REMOTE_IP}")
    print(f"遠程端口: {REMOTE_PORT}")
    print("===============\n")

    sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 262144)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 262144)
    sock.settimeout(0.1)

    try:
        sock.bind((local_ip, LOCAL_PORT))
        print("成功綁定本機地址和端口")
    except Exception as e:
        print(f"綁定地址失敗: {e}")
        return

    input_device, output_device = check_audio_devices()
    
    audio_input_stream = sd.InputStream(
        device=input_device,
        channels=CHANNELS,
        samplerate=RATE,
        dtype=np.float32,
        blocksize=CHUNK,
        latency='low'
    )
    
    audio_output_stream = sd.OutputStream(
        device=output_device,
        channels=CHANNELS,
        samplerate=RATE,
        dtype=np.float32,
        blocksize=CHUNK,
        latency='low'
    )

    try:
        audio_input_stream.start()
        audio_output_stream.start()
        print("音頻流創建成功")

    except Exception as e:
        print(f"音頻流創建失敗: {e}")
        return

    send_thread = threading.Thread(target=send_audio,
                                 args=(sock, audio_input_stream, REMOTE_IP, REMOTE_PORT, RATE))
    receive_thread = threading.Thread(target=receive_audio,
                                    args=(sock, audio_output_stream, RATE))

    send_thread.start()
    receive_thread.start()
    print("通訊開始，按 Ctrl+C 結束程序")

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n正在關閉程式...")
        audio_input_stream.stop()
        audio_output_stream.stop()
        sock.close()


if __name__ == "__main__":
    main()