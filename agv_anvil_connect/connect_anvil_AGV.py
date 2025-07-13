import serial
import serial.rs485
import struct
import crcmod.predefined
import time
import anvil.server
import threading 
import queue
import logging
from pymodbus.client import ModbusSerialClient

# ==============================================================================
# 1. KONFIGURASI DAN KONEKSI ANVIL
# ==============================================================================
ANVIL_UPLINK_KEY = "server_JUMVMFNTWRVDAF37Y3YQGOOU-F4TF5RMEGZX26KT2" # Contoh Uplink Key
anvil.server.connect(ANVIL_UPLINK_KEY)
print("Anvil Uplink connected. Waiting for calls from Anvil...")

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AGV_Uplink")

# ==============================================================================
# 2. KONFIGURASI HARDWARE DAN PID
# ==============================================================================
# Port Serial
WHEEL_PORT = "COM15"      # Port motor dari kode manual Anda
SENSOR_PORT = "COM14"    # Port sensor dari kode autonomos Anda

# Baudrate
WHEEL_BAUDRATE = 115200
SENSOR_BAUDRATE = 9600

# Parameter Motor
MOTOR_ID_LEFT = 2        # ID motor kiri dari kode autonomos
MOTOR_ID_RIGHT = 1       # ID motor kanan dari kode autonomos
MAX_RPM = 20             # Kecepatan dasar untuk mode autonomos

# Parameter Sensor
SENSOR_ADDRESS = 1

# Logika Line Following
IDEAL_CENTER_SENSOR = 8.5 

# Konstanta PID
PID_KP = 2.0
PID_KI = 0.0
PID_KD = 0.5

# ==============================================================================
# 3. STATE MANAGEMENT (PENGELOLAAN MODE)
# ==============================================================================
motor_command_queue = queue.Queue() # Untuk mode MANUAL
current_mode = "manual" # Mode awal: 'manual' atau 'autonomous'
mode_lock = threading.Lock() # Untuk mengubah mode secara aman dari thread

# Variabel global untuk menyimpan instance kelas
motor_control_instance = None
sensor_reader_instance = None
pid_controller_instance = None

# --- Variabel untuk melacak kondisi terakhir yang dikirim ke Anvil ---
last_logged_mode = None
last_logged_keadaan = None

# ==============================================================================
# 4. FUNGSI DAN KELAS-KELAS KONTROL (GABUNGAN DARI KEDUA FILE)
# ==============================================================================

# --- Kelas MotorControl (Diadaptasi dari kedua file Anda) ---
class MotorControl:
    def __init__(self, device, baudrate):
        self.device = device
        self.baudrate = baudrate
        self.ser = None
        self.crc8 = crcmod.predefined.mkPredefinedCrcFun('crc-8-maxim')
        self.str_9bytes = ">BBBBBBBBB"
        self.current_set_rpms = {1: 0, 2: 0}
        self.connect()

    def connect(self):
        if self.ser and self.ser.is_open:
            return True
        try:
            self.ser = serial.rs485.RS485(self.device, self.baudrate, timeout=0.05)
            self.ser.rs485_mode = serial.rs485.RS485Settings()
            logger.info(f"Port motor {self.device} berhasil dibuka.")
            return True
        except serial.SerialException as e:
            logger.error(f"Gagal membuka port motor {self.device}: {e}")
            self.ser = None
            return False

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            logger.info(f"Port motor {self.device} ditutup.")

    def _int_16_to_bytes(self, data: int):
        return [(data & 0xFF00) >> 8, data & 0x00FF]

    def _crc_attach(self, data_bytes: bytes):
        crc_int = self.crc8(data_bytes)
        return data_bytes + crc_int.to_bytes(1, 'big')

    def send_rpm(self, motor_id: int, rpm: int):
        if not self.ser or not self.ser.is_open:
            if not self.connect():
                return False
        
        rpm_clamped = int(max(-MAX_RPM*3, min(rpm, MAX_RPM*3)))
        rpm_bytes = self._int_16_to_bytes(rpm_clamped)
        
        cmd_bytes = struct.pack(self.str_9bytes, motor_id, 0x64, rpm_bytes[0], rpm_bytes[1], 0, 0, 0, 0, 0)
        cmd_bytes_with_crc = self._crc_attach(cmd_bytes)

        try:
            self.ser.write(cmd_bytes_with_crc)
            return True
        except serial.SerialException as e:
            logger.error(f"Gagal menulis ke port motor untuk Motor {motor_id}: {e}")
            self.ser = None
            return False
            
    def set_velocity_mode(self, motor_id: int):
        logger.info(f"Mengatur Motor {motor_id} ke mode kecepatan (velocity)...")
        cmd_bytes = struct.pack(">BBBBBBBBBB", motor_id, 0xA0, 0, 0, 0, 0, 0, 0, 0, 2)
        cmd_bytes_with_crc = self._crc_attach(cmd_bytes)
        try:
            self.ser.write(cmd_bytes_with_crc)
            time.sleep(0.1)
        except serial.SerialException as e:
            logger.error(f"Gagal mengatur mode kecepatan untuk Motor {motor_id}: {e}")

# --- Kelas SensorReader ---
class SensorReader:
    def __init__(self, port, baudrate, address):
        self.client = ModbusSerialClient(port=port, baudrate=baudrate, parity='N', stopbits=1, bytesize=8, timeout=0.2)
        self.address = address
        self.is_connected = False

    def connect(self):
        if self.is_connected: return True
        logger.info(f"Mencoba terhubung ke sensor di {SENSOR_PORT}...")
        self.is_connected = self.client.connect()
        if not self.is_connected: logger.error(f"Gagal terhubung ke sensor.")
        return self.is_connected

    def close(self):
        if self.is_connected:
            self.client.close()
            self.is_connected = False

    def read_position(self):
        if not self.is_connected and not self.connect():
            return None
        try:
            result = self.client.read_holding_registers(address=0, count=2, slave=self.address)
            if result.isError():
                return None
            median_float = result.registers[0] / 235.0
            if 0 < median_float <= 16:
                return median_float
            return None
        except Exception:
            return None

# --- Kelas PIDController ---
class PIDController:
    def __init__(self, Kp, Ki, Kd, setpoint):
        self.Kp, self.Ki, self.Kd = Kp, Ki, Kd
        self.setpoint = setpoint
        self.last_error = 0
        self.integral = 0
        self.max_integral = MAX_RPM / 2

    def update(self, current_value, dt):
        error = self.setpoint - current_value
        P = self.Kp * error
        self.integral += error * dt
        self.integral = max(-self.max_integral, min(self.integral, self.max_integral))
        I = self.Ki * self.integral
        derivative = (error - self.last_error) / dt
        D = self.Kd * derivative
        self.last_error = error
        return P + I + D
    
    def reset(self):
        self.last_error = 0
        self.integral = 0
        logger.info("Kontroler PID direset.")

# ==============================================================================
# 5. FUNGSI-FUNGSI YANG DIPANGGIL OLEH ANVIL SERVER
# ==============================================================================
@anvil.server.callable
def switch_mode_via_uplink(mode: str):
    global current_mode, pid_controller_instance
    with mode_lock:
        if mode in ["manual", "autonomous"]:
            current_mode = mode
            logger.info(f"Mode AGV diubah menjadi: {mode.upper()}")
            if mode == 'manual':
                if pid_controller_instance:
                    pid_controller_instance.reset()
                while not motor_command_queue.empty():
                    motor_command_queue.get()
                motor_command_queue.put({"motor1_id": 1, "motor1_rpm": 0, "motor2_id": 2, "motor2_rpm": 0})
            return f"Mode switched to {mode}"
        else:
            return "Invalid mode"

@anvil.server.callable
def set_both_motor_rpms_via_uplink(motor1_id: int, motor1_rpm: int, motor2_id: int, motor2_rpm: int):
    global current_mode
    if current_mode == "manual":
        logger.info(f"MANUAL command queued: M1 RPM {motor1_rpm}, M2 RPM {motor2_rpm}")
        motor_command_queue.put({
            "motor1_id": motor1_id, "motor1_rpm": motor1_rpm,
            "motor2_id": motor2_id, "motor2_rpm": motor2_rpm
        })
        return "Manual command queued."
    else:
        logger.warning("Menerima perintah manual saat dalam mode AUTONOMOUS. Perintah diabaikan.")
        return "Command ignored, AGV in autonomous mode."

# ==============================================================================
# 6. LOOP KONTROL UTAMA (THREAD)
# ==============================================================================

def motor_control_loop(motor_ctrl, sensor_rdr, pid_ctrl):
    global last_logged_mode, last_logged_keadaan # Panggil variabel global
    logger.info("Control loop started.")
    motor_ctrl.set_velocity_mode(MOTOR_ID_LEFT)
    motor_ctrl.set_velocity_mode(MOTOR_ID_RIGHT)
    
    motor_ctrl.send_rpm(MOTOR_ID_LEFT, 0)
    motor_ctrl.send_rpm(MOTOR_ID_RIGHT, 0)
    motor_ctrl.current_set_rpms = {1: 0, 2: 0}

    last_time = time.time()
    searching_line = False
    line_lost_start_time = None

    # --- FUNGSI HELPER BARU DI DALAM LOOP ---
    def determine_agv_state(rpm_kanan, rpm_kiri, mode, is_searching):
        """Menerjemahkan RPM motor menjadi state yang mudah dibaca."""
        if is_searching:
            if pid_ctrl.last_error > 0:
                return "Mencari (Kiri)"
            else:
                return "Mencari (Kanan)"

        # Toleransi untuk dianggap berhenti
        if -1 < rpm_kanan < 1 and -1 < rpm_kiri < 1:
            return "Stop"

        if mode == "manual":
            # Logika berdasarkan perintah dari Anvil
            if rpm_kanan < 0 and rpm_kiri > 0: return "Lurus"
            if rpm_kanan > 0 and rpm_kiri < 0: return "Mundur"
            if rpm_kanan > 0 and rpm_kiri > 0: return "Belok Kanan"
            if rpm_kanan < 0 and rpm_kiri < 0: return "Belok Kiri"
        else: # Otomatis
            # Dalam mode otomatis, jika bergerak, diasumsikan selalu lurus mengikuti garis
            return "Lurus (Otomatis)"
        
        return "Tidak Diketahui"

    def log_kondisi_jika_berubah(mode_sekarang, keadaan_sekarang, rpm_ka, rpm_ki):
        """Mengirim data ke Anvil hanya jika ada perubahan mode atau keadaan."""
        global last_logged_mode, last_logged_keadaan
        if mode_sekarang != last_logged_mode or keadaan_sekarang != last_logged_keadaan:
            try:
                # Panggil fungsi server dengan parameter RPM yang baru
                anvil.server.call('log_agv_kondisi', mode_sekarang, keadaan_sekarang, rpm_ka, rpm_ki)
                last_logged_mode = mode_sekarang
                last_logged_keadaan = keadaan_sekarang
                # TAMBAHKAN LOG DI SINI UNTUK MEMASTIKAN FUNGSI DIPANGGIL
                logger.info(f"KONDISI BARU DIKIRIM KE ANVIL: Mode={mode_sekarang}, Keadaan={keadaan_sekarang}, RPM Ka={rpm_ka}, Ki={rpm_ki}")
            except Exception as e:
                logger.error(f"Gagal mengirim kondisi AGV ke Anvil: {e}")
    # --- AKHIR FUNGSI HELPER BARU ---

    while True:
        try:
            with mode_lock:
                active_mode = current_mode
            
            dt = time.time() - last_time
            if dt == 0: continue
            last_time = time.time()
            
            # Inisialisasi RPM untuk loop ini
            rpm_motor_kanan_final = 0
            rpm_motor_kiri_final = 0

            if active_mode == "manual":
                searching_line = False
                latest_command = None
                while not motor_command_queue.empty():
                    latest_command = motor_command_queue.get_nowait()
                
                if latest_command:
                    motor_ctrl.current_set_rpms[latest_command["motor1_id"]] = latest_command["motor1_rpm"]
                    motor_ctrl.current_set_rpms[latest_command["motor2_id"]] = latest_command["motor2_rpm"]
                
                rpm_motor_kanan_final = motor_ctrl.current_set_rpms.get(MOTOR_ID_RIGHT, 0)
                rpm_motor_kiri_final = motor_ctrl.current_set_rpms.get(MOTOR_ID_LEFT, 0)
                
                motor_ctrl.send_rpm(MOTOR_ID_RIGHT, rpm_motor_kanan_final)
                motor_ctrl.send_rpm(MOTOR_ID_LEFT, rpm_motor_kiri_final)

            elif active_mode == "autonomous":
                position = sensor_rdr.read_position()
                
                if position is not None:
                    searching_line = False
                    correction = pid_ctrl.update(position, dt)
                    
                    left_rpm = MAX_RPM + correction
                    right_rpm = MAX_RPM - correction
                    
                    rpm_motor_kiri_final = int(left_rpm)
                    rpm_motor_kanan_final = -int(right_rpm) # Tanda minus untuk maju

                    motor_ctrl.send_rpm(MOTOR_ID_LEFT, rpm_motor_kiri_final)
                    motor_ctrl.send_rpm(MOTOR_ID_RIGHT, rpm_motor_kanan_final)
                else:
                    if not searching_line:
                        searching_line = True
                        line_lost_start_time = time.time()
                        logger.warning("Garis hilang! Memulai pencarian garis kembali...")

                    elapsed_search_time = time.time() - line_lost_start_time

                    if elapsed_search_time <= 10.0:
                        if pid_ctrl.last_error > 0: # Belok Kiri
                            rpm_motor_kiri_final = int(MAX_RPM * 0.5)
                            rpm_motor_kanan_final = -int(MAX_RPM * 0.5)
                        else: # Belok Kanan
                            rpm_motor_kiri_final = -int(MAX_RPM * 0.5)
                            rpm_motor_kanan_final = int(MAX_RPM * 0.5)
                    else: # Berhenti
                        logger.error("Gagal menemukan garis dalam 10 detik. Menghentikan AGV.")
                        rpm_motor_kiri_final = 0
                        rpm_motor_kanan_final = 0
                        if current_mode == "autonomous":
                            switch_mode_via_uplink("manual")
                    
                    motor_ctrl.send_rpm(MOTOR_ID_LEFT, rpm_motor_kiri_final)
                    motor_ctrl.send_rpm(MOTOR_ID_RIGHT, rpm_motor_kanan_final)

            # --- BAGIAN BARU UNTUK MENCATAT KONDISI ---
            keadaan_sekarang = determine_agv_state(rpm_motor_kanan_final, rpm_motor_kiri_final, active_mode, searching_line)
            log_kondisi_jika_berubah(active_mode, keadaan_sekarang, rpm_motor_kanan_final, rpm_motor_kiri_final)
            # ----------------------------------------
            searching_line
            time.sleep(0.1) # Beri jeda sedikit agar tidak membanjiri server

        except Exception as e:
            logger.critical(f"Error dalam control loop: {e}", exc_info=True)
            motor_ctrl.connect()
            sensor_rdr.connect()
            time.sleep(1)

# ==============================================================================
# 7. EKSEKUSI PROGRAM UTAMA
# ==============================================================================
if __name__ == "__main__":
    motor_control_instance = MotorControl(WHEEL_PORT, WHEEL_BAUDRATE)
    sensor_reader_instance = SensorReader(SENSOR_PORT, SENSOR_BAUDRATE, SENSOR_ADDRESS)
    pid_controller_instance = PIDController(PID_KP, PID_KI, PID_KD, IDEAL_CENTER_SENSOR)
    
    control_thread = threading.Thread(
        target=motor_control_loop, 
        args=(motor_control_instance, sensor_reader_instance, pid_controller_instance), 
        daemon=True
    )
    control_thread.start()

    try:
        anvil.server.wait_forever()
    except KeyboardInterrupt:
        logger.info("Uplink dihentikan oleh pengguna.")
    finally:
        if motor_control_instance:
            motor_control_instance.close()
        if sensor_reader_instance:
            sensor_reader_instance.close()
        logger.info("Program dihentikan.")
