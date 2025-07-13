from ._anvil_designer import RowTemplate3Template
from anvil import *
import anvil.users
import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables


class RowTemplate3(RowTemplate3Template):
  def __init__(self, **properties):
    # Set Form properties and Data Bindings.
    self.init_components(**properties)

    # Any code you write here will run before the form opens.

  def in_del_click(self, **event_args):
      """Fungsi ini dijalankan saat tombol hapus ditekan."""
      # Munculkan kotak konfirmasi ke pengguna
      if confirm("Yakin ingin menghapus data ini?"):
          try:
              # Panggil fungsi server untuk menghapus data 
              anvil.server.call("delete_inbound", self.item)
              
              # Refresh tabel utama (form homepage) agar data ter-update
              get_open_form().refresh_hometabel()
              
              # Tampilkan notifikasi berhasil
              Notification("Data berhasil dihapus.", style="success").show()
              
              # Minta parent (tabel) untuk memicu event refresh agar data tampil baru
              self.parent.raise_event("x-refresh_inbound")
          
          except Exception as e:
              # Tampilkan notifikasi error jika penghapusan gagal
              Notification(f"Gagal menghapus: {e}", style="danger").show()
