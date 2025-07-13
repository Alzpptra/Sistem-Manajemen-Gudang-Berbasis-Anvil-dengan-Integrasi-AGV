from ._anvil_designer import inbound_editTemplate
from anvil import *
import anvil.users
import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables

class inbound_edit(inbound_editTemplate):
  def __init__(self, **properties):
    # Set Form properties and Data Bindings.
    self.init_components(**properties)
    # Any code you write here will run before the form opens.
    # Ambil properti item dari pemanggil
    self.item = properties.get('item', {})

    # Isi dropdown lokasi dengan nama lokasi dan row-nya
    self.in_loc.items = [(row['location'], row) for row in app_tables.lokasi_inbound.search()]

    # Set nilai awal dropdown
    self.in_loc.selected_value = self.item.get('Lokasi')

    # Tampilkan seluruh data dari tabel `data_barang` di komponen tabel
    self.show_intabel.items = app_tables.data_barang.search()

    # Pasang event handler untuk menyegarkan data tabel
    self.show_intabel.set_event_handler("x-refresh_inbound", self.refresh_inbound)


  def in_barang_change(self, **event_args):
    """Fungsi dijalankan saat teks nama barang diubah."""
    nama_barang = self.in_barang.text.strip().title()  # Merapihkan nama barang
    self.item['Nama_Barang'] = nama_barang             # Simpan ke item

    # Cek apakah barang dengan nama tersebut sudah ada di database
    row = app_tables.data_barang.get(Nama_Barang=nama_barang)
    if row:
        # Jika barang sudah ada:
        # - Set lokasi otomatis sesuai data
        # - Nonaktifkan dropdown lokasi (tidak bisa dipilih manual)
        self.in_loc.selected_value = row['Lokasi']
        self.in_loc.enabled = False
        self.item['Lokasi'] = row['Lokasi']
    else:
        # Jika barang baru:
        # - Aktifkan kembali dropdown lokasi
        # - Kosongkan nilai lokasi pada item
        self.in_loc.enabled = True
        self.in_loc.selected_value = None
        self.item['Lokasi'] = None


  def in_qty_change(self, **event_args):
    """Fungsi dijalankan saat jumlah barang diubah."""
    # Jika input hanya berisi angka, simpan ke item sebagai integer
    self.item['Qty_in'] = int(self.in_jmlh.text) if self.in_jmlh.text.isdigit() else 0

  def in_loc_change(self, **event_args):
    """Fungsi dijalankan saat dropdown lokasi diubah."""
    # Simpan lokasi yang dipilih ke item
    self.item["Lokasi"] = self.in_loc.selected_value

  def refresh_inbound(self, **event_args):
    """Memuat ulang data dari server dan menampilkannya di tabel."""
    self.show_intabel.items = anvil.server.call('get_newinbound')
