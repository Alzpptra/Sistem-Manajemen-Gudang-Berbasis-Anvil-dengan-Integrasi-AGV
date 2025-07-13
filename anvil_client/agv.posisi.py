from ._anvil_designer import agv_posisiTemplate
from anvil import *
import anvil.server
import anvil.users
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables

class agv_posisi(agv_posisiTemplate):
  def __init__(self, **properties):
    # Set Form properties and Data Bindings.
    self.init_components(**properties)

    # Any code you write here will run before the form opens.
    self.load_agv_conditions()

  # --- FUNGSI BARU UNTUK MEMUAT DATA ---
  def load_agv_conditions(self):
    """Memanggil server untuk mendapatkan data kondisi AGV dan menampilkannya di grid."""
    self.pos_tabel.items = anvil.server.call('get_kondisi_agv')

  # --- EVENT HANDLER UNTUK TIMER ---
  def timer_1_tick(self, **event_args):
    """This method is called every 5 seconds (sesuai interval timer)."""
    self.load_agv_conditions()