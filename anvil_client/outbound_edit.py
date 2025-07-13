from ._anvil_designer import outbound_editTemplate
from anvil import *
import anvil.users
import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables

class outbound_edit(outbound_editTemplate):
  def __init__(self, **properties):
    # Set Form properties and Data Bindings.
    self.init_components(**properties)
    # Any code you write here will run before the form opens.

    # Ambil daftar nama barang unik dari tabel dan siapkan untuk dropdown
    nama_list = list({row['Nama_Barang'] for row in app_tables.data_barang.search()})
    self.categories = [(nama, nama) for nama in nama_list]  # Format (label, value)
    self.out_pilbar.items = self.categories  # Isi dropdown dengan nama barang

    # Tampilkan semua data barang berdasarkan urutan nomor ID
    self.out_tabel.items = app_tables.data_barang.search(tables.order_by('No'))

  def out_pilbar_change(self, **event_args):
    """Dipanggil saat user memilih nama barang dari dropdown."""
    selected_name = self.out_pilbar.selected_value  # Ambil nama barang yang dipilih
    if selected_name:
      rows = app_tables.data_barang.search(Nama_Barang=selected_name)  # Cari data berdasarkan nama
      if rows:
          # Urutkan berdasarkan tanggal masuk (FIFO)
          sorted_rows = sorted(rows, key=lambda r: r['Tanggal_Masuk'])
          earliest_row = sorted_rows[0]  # Ambil data masuk paling awal

          # Simpan data yang dipilih ke dictionary item (untuk outbound)
          self.item["ID"] = earliest_row["ID"]
          self.item["Nama_Barang"] = earliest_row["Nama_Barang"]
          self.item["Lokasi"] = earliest_row["Lokasi"]

          # Tampilkan hanya barang yang akan dikeluarkan
          self.out_tabel.items = [earliest_row]

  def out_qty_enter_pressed(self, **event_args):
    """Dipanggil saat user menekan Enter di field jumlah barang keluar."""
    self.item["Qty_out"] = self.out_qty.text  # Simpan jumlah ke dictionary item
    self.out_qty.set_event_handler('change', self.qty_changed)  # menambahkan event handler perubahan jumlah

  def qty_changed(self, **event_args):
    """Dipanggil saat nilai jumlah barang berubah."""
    self.item["Qty_out"] = self.out_qty.text  # Update nilai jumlah ke item
