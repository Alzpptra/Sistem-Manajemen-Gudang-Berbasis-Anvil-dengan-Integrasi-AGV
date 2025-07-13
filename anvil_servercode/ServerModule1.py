import anvil.users
import anvil.tables as tables
import anvil.tables.query as q
import pytz
from anvil.tables import app_tables
import anvil.server
from datetime import datetime
import string

# =======================
# FUNGSI TAMBAH DATA MASUK
# =======================
@anvil.server.callable
def add_inbound(inbound_tab):
  # Validasi data wajib
  if not inbound_tab.get("Nama_Barang") or inbound_tab.get("Qty_in", 0) <= 0:
    raise Exception("Data tidak lengkap")

  nama_barang = inbound_tab["Nama_Barang"].strip().title()
  tanggal_masuk = datetime.now().date()
  tanggal_str = tanggal_masuk.strftime("%Y%m%d")  # Format tanggal jadi string: YYYYMMDD

  # Buat ID barang unik
  prefix = generate_prefix(nama_barang)
  barang_sama_hari_ini = app_tables.data_barang.search(
    Nama_Barang=nama_barang,
    Tanggal_Masuk=tanggal_masuk
  )
  urutan = len(barang_sama_hari_ini) + 1
  id_barang = f"{prefix}-{tanggal_str}-{urutan:03}"  # Contoh: BARUO7-20250429-001

  # Ambil lokasi dari barang lama atau input baru
  existing_row = app_tables.data_barang.get(Nama_Barang=nama_barang)
  if existing_row:
    lokasi_input = existing_row["Lokasi"]
  else:
    lokasi_input = inbound_tab.get("Lokasi")
    if isinstance(lokasi_input, str):
      lokasi_input = app_tables.lokasi_inbound.get(location=lokasi_input.strip())
      if not lokasi_input:
        raise Exception("Lokasi tidak ditemukan.")
    else:
      lokasi_input["location"] = lokasi_input["location"].strip()

  total_entries = len(app_tables.data_barang.search()) + 1  # Buat nomor urut

  # Tambahkan baris baru
  app_tables.data_barang.add_row(
    No=total_entries,
    ID=id_barang,
    Nama_Barang=nama_barang,
    Lokasi=lokasi_input,
    Tanggal_Masuk=tanggal_masuk,
    Qty_in=inbound_tab.get("Qty_in", 0),
    Qty=inbound_tab.get("Qty_in", 0)  # Qty awal sama dengan Qty_in
  )

# =======================
# FUNGSI GENERATE PREFIX UNIK DARI NAMA BARANG
# =======================
def generate_prefix(nama_barang):
  nama_bersih = ''.join(filter(str.isalnum, nama_barang))  # Hapus simbol dan spasi
  huruf_awal = nama_bersih[:3].upper()  # Tiga huruf pertama
  vokal = next((c for c in nama_bersih if c.lower() in 'aeiou'), 'X').upper()  # Ambil vokal pertama
  panjang = len(nama_bersih)  # Panjang nama
  return f"{huruf_awal}{vokal}{panjang}"  # Contoh: BARUO7

# =======================
# FUNGSI TAMPILKAN DATA MASUK TERBARU
# =======================
@anvil.server.callable
def get_newinbound():
  return app_tables.data_barang.search(tables.order_by("Tanggal_Masuk", ascending=False))

# =======================
# FUNGSI CARI DATA DENGAN FILTER
# =======================
@anvil.server.callable
def search_data(keyword=None, tanggal=None, lokasi=None):
  """Mencari data berdasarkan nama barang, tanggal masuk, dan lokasi"""
  query_conditions = {}
  if keyword:
    query_conditions["Nama_Barang"] = q.ilike(f"%{keyword}%")
  if tanggal:
    query_conditions["Tanggal_Masuk"] = tanggal
  if lokasi:
    query_conditions["Lokasi"] = lokasi
  return app_tables.data_barang.search(**query_conditions)

# =======================
# FUNGSI HAPUS DATA MASUK
# =======================
@anvil.server.callable
def delete_inbound(delinbound):
  if not delinbound:
    raise Exception("Data tidak lengkap")

  if app_tables.data_barang.has_row(delinbound):
    delinbound.delete()

    # Susun ulang urutan No setelah penghapusan
    rows = app_tables.data_barang.search(tables.order_by("Tanggal_Masuk"))
    for index, row in enumerate(rows, start=1):
      row["No"] = index

  return rows  # Return data terbaru

# =======================
# FUNGSI PROSES PENGELUARAN (OUTBOUND)
# =======================
@anvil.server.callable
def update_outbound(outbound_item):
  nama_barang = outbound_item.get("Nama_Barang")
  qty_keluar = int(outbound_item.get("Qty_out"))

  if not nama_barang or qty_keluar <= 0:
    raise ValueError("Data barang atau jumlah keluar tidak valid.")

    # Ambil stok barang sesuai FIFO
  stok_rows = app_tables.data_barang.search(
    tables.order_by("Tanggal_Masuk"),
    Nama_Barang=nama_barang,
    Qty=q.greater_than(0)
  )

  if not stok_rows:
    raise ValueError("Stok tidak ditemukan.")

  total_tersedia = sum(row['Qty'] for row in stok_rows)
  if total_tersedia < qty_keluar:
    raise ValueError(f"Stok tidak mencukupi. Hanya tersedia {total_tersedia}")

  sisa_keluar = qty_keluar
  for row in stok_rows:
    if sisa_keluar <= 0:
      break

    stok_saat_ini = row['Qty']
    if stok_saat_ini >= sisa_keluar:
      row['Qty'] -= sisa_keluar
      row['Qty_out'] = sisa_keluar  # Simpan jumlah keluar
      row['Tanggal_Keluar'] = datetime.now().date()  # Simpan tanggal keluar
      row.update()
      sisa_keluar = 0
    else:
      row['Qty_out'] = stok_saat_ini
      row['Tanggal_Keluar'] = datetime.now().date()
      row['Qty'] = 0
      row.update()
      sisa_keluar -= stok_saat_ini

    # Hapus baris yang Qty = 0 jika ingin, atau simpan riwayat
  kosong_rows = app_tables.data_barang.search(Qty=0)
  for row in kosong_rows:
    if app_tables.data_barang.has_row(row):
      row.delete()

    # Susun ulang Nomer
  rows = app_tables.data_barang.search(tables.order_by("Tanggal_Masuk"))
  for index, row in enumerate(rows, start=1):
    row["No"] = index

@anvil.server.callable
def log_ddsm115_data(motor_id: int, set_rpm: int, feedback_rpm: int, feedback_arus: float):
  """
    Mencatat data DDSM115 ke tabel 'data_ddsm115' di Anvil.
    Menerima 'motor_id' sebagai argumen tambahan.
    """
  # Set zona waktu ke Asia/Jakarta (WIB)
  zona_wib = pytz.timezone("Asia/Jakarta")
  now = datetime.now(zona_wib)

  app_tables.data_ddsm115.add_row(
    Waktu=now,
    Motor_ID=motor_id, # Tambahkan kolom ini jika belum ada di tabel
    Set_RPM_Motor=set_rpm,
    Feedback_RPM_Motor=feedback_rpm,
    Feedback_Arus_Motor=feedback_arus
  )

@anvil.server.callable
def get_ddsm115_data():
  return app_tables.data_ddsm115.search(tables.order_by("Waktu", ascending=False))

# ===== FUNGSI UNTUK LOG KONDISI AGV ===============

@anvil.server.callable
def log_agv_kondisi(mode: str, keadaan: str, rpm_ka: int, rpm_ki: int):
  """
  Mencatat kondisi AGV (mode, keadaan, dan RPM) ke dalam tabel kondisi_agv.
  """
  zona_wib = pytz.timezone("Asia/Jakarta")
  now = datetime.now(zona_wib)

  app_tables.kondisi_agv.add_row(
    Waktu=now,
    Mode=mode.title(),
    Keadaan=keadaan.title(),
    Rpmka=rpm_ka * -1, # BARU: Simpan RPM roda kanan
    Rpmki=rpm_ki  # BARU: Simpan RPM roda kiri
  )
  # print(f"Kondisi AGV Tercatat: Mode={mode}, Keadaan={keadaan}, RPM Ka={rpm_ka}, RPM Ki={rpm_ki}") # Opsional debug

# FUNGSI BARU: Untuk mendapatkan data tunggal terbaru
@anvil.server.callable
def get_agvrpm_status():
  """
  Mengambil HANYA SATU baris data kondisi AGV yang paling baru.
  Ini lebih efisien untuk menampilkan status real-time.
  """
  # Search, urutkan dari yang terbaru, dan ambil baris pertama [0]
  latest_rows = app_tables.kondisi_agv.search(tables.order_by("Waktu", ascending=False))

  # Ambil baris pertama jika ada
  latest_row = next(iter(latest_rows), None)
  
  if latest_row:
    print(f"Data yang ditemukan dan akan dikembalikan: Rpmka={latest_row['Rpmka']}, Rpmki={latest_row['Rpmki']}") # PRINT 2
  else:
    print("Tidak ada baris data yang ditemukan oleh search, mengembalikan None.") # PRINT 3

  return latest_row

@anvil.server.callable
def get_kondisi_agv():
  """
  Mengambil semua data kondisi AGV, diurutkan dari yang terbaru.
  Fungsi ini dipanggil oleh Form 'agv_posisi'.
  """
  return app_tables.kondisi_agv.search(
    tables.order_by("Waktu", ascending=False)
  )

# =======================
# FUNGSI UNTUK KONTROL MOTOR DDSM115 VIA ANVIL UPLINK
# =======================

MOTOR_ID_1 = 1  
MOTOR_ID_2 = 2  

def get_motor_is_on_status():
  """Mengambil status 'motor_is_on' dari tabel App_Settings."""
  setting_row = app_tables.app_settings.get(Setting_Name='motor_is_on')
  if setting_row:
    return setting_row['Setting_Value']
  print("WARNING: 'motor_is_on' setting not found. Defaulting to False.")
  return False

def set_motor_is_on_status(status: bool):
  """Mengatur status 'motor_is_on' di tabel App_Settings."""
  setting_row = app_tables.app_settings.get(Setting_Name='motor_is_on')
  if setting_row:
    setting_row.update(Setting_Value=status)
  else:
    app_tables.app_settings.add_row(Setting_Name='motor_is_on', Setting_Value=status)
  print(f"Motor status in Anvil Table set to: {status}")

# --- FUNGSI BARU UNTUK MENGATUR MODE AGV ---
@anvil.server.callable
def set_agv_mode(mode: str):
  """
  Mengatur mode operasi AGV (manual atau autonomous).
  Memanggil fungsi di uplink untuk mengubah perilaku loop kontrol.
  """
  # Periksa apakah motor ON sebelum masuk mode autonomous
  if mode == "autonomous" and not get_motor_is_on_status():
    raise Exception("Motor harus dalam keadaan ON untuk masuk mode Autonomos.")

  # Perintah yang valid adalah 'manual' atau 'autonomous'
  if mode not in ["manual", "autonomous"]:
    raise ValueError("Mode tidak valid. Gunakan 'manual' atau 'autonomous'.")

  try:
    # Panggil fungsi di uplink client untuk mengganti mode
    uplink_response = anvil.server.call("switch_mode_via_uplink", mode)
    print(f"Uplink response for mode switch: {uplink_response}")
    return f"AGV sekarang dalam mode: {mode.upper()}"
  except Exception as e:
    print(f"Error saat memanggil switch_mode_via_uplink: {e}")
    raise Exception(f"Gagal mengubah mode AGV di uplink: {e}")

@anvil.server.callable
def kontrol_motor_on_off(perintah: str, motor_id: int = None):
  try:
    if perintah == "off":
      anvil.server.call("set_agv_mode", "manual")

    if motor_id is None:
      target_rpm_motor1 = -5 if perintah == "on" else 0
      target_rpm_motor2 = 5 if perintah == "on" else 0
      anvil.server.call("set_both_motor_rpms_via_uplink", MOTOR_ID_1, target_rpm_motor1, MOTOR_ID_2, target_rpm_motor2)
      set_motor_is_on_status(perintah == "on")
      return f"Semua motor diperintah {perintah.upper()}. Status: {'ON' if (perintah == 'on') else 'OFF'}."
    else:
      target_rpm = 5 if perintah == "on" else 0
      if motor_id == MOTOR_ID_2:
        target_rpm = target_rpm
      anvil.server.call("set_motor_rpm_via_uplink", motor_id, target_rpm)
      return f"Motor {motor_id} diperintah {perintah.upper()}."
  except Exception as e:
    print(f"Error di kontrol_motor_on_off: {e}")
    if perintah == "on" and motor_id is None:
      set_motor_is_on_status(False)
    raise Exception(f"Gagal mengontrol motor: {e}")

@anvil.server.callable
def kontrol_motor_arah(arah: str, rpm_maju_mundur: int = 15,
                       rpm_belok_mka1: int = 5, rpm_belok_mki1: int = 10,
                       rpm_belok_mka2: int = 10, rpm_belok_mki2: int = 5):

  current_motor_status = get_motor_is_on_status()
  if not current_motor_status and arah != "stop":
    return "Motor masih dalam keadaan OFF. Tekan tombol ON terlebih dahulu."
  try:
    rpm_motor1 = 0
    rpm_motor2 = 0
    perintah_str = ""
    if arah == "maju":
      rpm_motor1 = -rpm_maju_mundur
      rpm_motor2 = rpm_maju_mundur
      perintah_str = "MAJU"
    elif arah == "mundur":
      rpm_motor1 = rpm_maju_mundur
      rpm_motor2 = -rpm_maju_mundur
      perintah_str = "MUNDUR"
    elif arah == "kiri":
      rpm_motor1 = -rpm_belok_mki1
      rpm_motor2 = -rpm_belok_mka1
      perintah_str = "BELOK KIRI"
    elif arah == "kanan":
      rpm_motor1 = rpm_belok_mki2
      rpm_motor2 = rpm_belok_mka2
      perintah_str = "BELOK KANAN"
    elif arah == "stop":
      rpm_motor1 = 0
      rpm_motor2 = 0
      perintah_str = "STOP"
      # Saat STOP, status motor tidak diubah menjadi OFF lagi
      set_motor_is_on_status(False)
    else:
      raise ValueError("Arah tidak dikenali: " + arah)
    anvil.server.call("set_both_motor_rpms_via_uplink", MOTOR_ID_1, rpm_motor1, MOTOR_ID_2, rpm_motor2)
    return f"Perintah: {perintah_str}"
  except Exception as e:
    print(f"Error di kontrol_motor_arah: {e}")
    raise Exception(f"Gagal mengontrol arah motor: {e}")
