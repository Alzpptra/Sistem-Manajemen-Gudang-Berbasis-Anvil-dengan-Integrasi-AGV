from ._anvil_designer import ddsm115_kontrolTemplate
from anvil import *
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.users
import anvil.server

class ddsm115_kontrol(ddsm115_kontrolTemplate):
  def __init__(self, **properties):
    # Set Form properties and Data Bindings.
    self.init_components(**properties)
    # Any code you write here will run before the form opens.
    self.status_label = self.motor_status

    self.on_auto.enabled = False
    self.off_auto.enabled = False

    self.update_rpm_display()
    self.update_status_label("Motor OFF (Siap Dihidupkan)")

  def update_rpm_display(self):
    try:
      # Menghilangkan icon loading saat refresh
      latest_status = anvil.server.call_s('get_agvrpm_status') 
      if latest_status:
        self.label_rpm_kanan.text = f"{latest_status['Rpmka']} RPM"
        self.label_rpm_kiri.text = f"{latest_status['Rpmki']} RPM"
      else:
        self.label_rpm_kanan.text = "0 RPM"
        self.label_rpm_kiri.text = "0 RPM"
    except Exception as e:
      print(f"Gagal mengambil data RPM: {e}")
      self.label_rpm_kanan.text = "Error"
      self.label_rpm_kiri.text = "Error"

  def timer_1_tick(self, **event_args):
    self.update_rpm_display()

  def update_status_label(self, message):
    if hasattr(self, 'status_label') and self.status_label:
      self.status_label.text = str(message)
    print(message)

  def mati_click(self, **event_args):
    try:
      response = anvil.server.call_s("kontrol_motor_on_off", "off")
      self.update_status_label(response)
      if "Status: OFF" in response:
        self.on_auto.enabled = False
        self.off_auto.enabled = False
    except Exception as e:
      alert(f"Gagal Mematikan Motor: {e}")
      self.update_status_label(f"Error OFF: {e}")

  def nyala_click(self, **event_args):
    try:
      response = anvil.server.call_s("kontrol_motor_on_off", "on")
      self.update_status_label(response)
      if "Status: ON" in response:
        self.on_auto.enabled = True
        self.off_auto.enabled = False
    except Exception as e:
      alert(f"Gagal Menghidupkan Motor: {e}")
      self.update_status_label(f"Error ON: {e}")

  def t_maju_click(self, **event_args):
    try:
      response = anvil.server.call_s("kontrol_motor_arah", "maju")
      self.update_status_label(response)
    except Exception as e:
      alert(f"Gagal Menggerakkan MAJU: {e}")
      self.update_status_label(f"Error MAJU: {e}")

  def t_mundur_click(self, **event_args):
    try:
      response = anvil.server.call_s("kontrol_motor_arah", "mundur")
      self.update_status_label(response)
    except Exception as e:
      alert(f"Gagal Menggerakkan MUNDUR: {e}")
      self.update_status_label(f"Error MUNDUR: {e}")

  def t_kiri_click(self, **event_args):
    try:
      response = anvil.server.call_s("kontrol_motor_arah", "kiri")
      self.update_status_label(response)
    except Exception as e:
      alert(f"Gagal Menggerakkan KIRI: {e}")
      self.update_status_label(f"Error KIRI: {e}")

  def t_kanan_click(self, **event_args):
    try:
      response = anvil.server.call_s("kontrol_motor_arah", "kanan")
      self.update_status_label(response)
    except Exception as e:
      alert(f"Gagal Menggerakkan KANAN: {e}")
      self.update_status_label(f"Error KANAN: {e}")

  def t_stop_click(self, **event_args):
    try:
      response = anvil.server.call_s("kontrol_motor_arah", "stop")
      self.update_status_label(response)
    except Exception as e:
      alert(f"Gagal Menghentikan Motor: {e}")
      self.update_status_label(f"Error STOP: {e}")

  def on_auto_click(self, **event_args):
    try:
      response = anvil.server.call_s("set_agv_mode", "autonomous")
      self.update_status_label(response)
      self.on_auto.enabled = False
      self.off_auto.enabled = True
    except Exception as e:
      alert(f"Gagal masuk mode Autonomos: {e}")
      self.update_status_label(f"Error Auto ON: {e}")

  def off_auto_click(self, **event_args):
    try:
      response = anvil.server.call_s("set_agv_mode", "manual")
      self.update_status_label(response)
      self.on_auto.enabled = True
      self.off_auto.enabled = False
    except Exception as e:
      alert(f"Gagal keluar dari mode Autonomos: {e}")
      self.update_status_label(f"Error Auto OFF: {e}")