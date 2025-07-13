from ._anvil_designer import homepageTemplate
from anvil import *
import anvil.users
import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
from ..inbound_edit import inbound_edit
from ..outbound_edit import outbound_edit
from ..ddsm115_edit import ddsm115_edit
from ..ddsm115_kontrol import ddsm115_kontrol
from ..agv_posisi import agv_posisi

class homepage(homepageTemplate):
  def __init__(self, **properties):
    # Set Form properties and Data Bindings.
    self.init_components(**properties)
    # Any code you write here will run before the form opens.

    # Mengisi tabel utama dengan data dari tabel `data_barang`, diurutkan berdasarkan ID
    self.homtabel.items = app_tables.data_barang.search(tables.order_by('ID'))

    # Panggil fungsi refresh untuk menampilkan data terbaru dari server
    self.refresh_hometabel()

    # Ambil semua data lokasi dari tabel `lokasi_inbound`, lalu format sebagai (nama_lokasi, row)
    self.categories = [(cat['location'], cat) for cat in app_tables.lokasi_inbound.search()]
    
    # Tampilkan data lokasi ke dropdown lokasi
    self.pilloc.items = self.categories 

    # Tampilkan form login pengguna
    anvil.users.login_with_form()
    

  def but_in_click(self, **event_args):
    # Buat dictionary kosong untuk data inbound baru
    new_inbound = {}

    # Tampilkan alert modal dengan form `inbound_edit`
    save_inclicked = alert(
      content = inbound_edit(item = new_inbound),
      title="Menu Inbound",
      large=True,
      buttons=[("Tambahkan",True),("Kembali",False)]
    )

    if save_inclicked:
        # Jika field Lokasi masih berupa string, ubah menjadi row dari tabel lokasi_inbound
        if isinstance(new_inbound.get("Lokasi"), str):
            lokasi_row = app_tables.lokasi_inbound.get(location=new_inbound["Lokasi"])
            if lokasi_row:
                new_inbound["Lokasi"] = lokasi_row

        # Kirim data inbound ke server function untuk disimpan
        anvil.server.call("add_inbound", new_inbound)

        # Perbarui isi tabel setelah penambahan
        self.refresh_hometabel()


  def refresh_hometabel(self):
      # Ambil data terbaru dari server dan tampilkan pada tabel
      self.homtabel.items = anvil.server.call('get_newinbound')
      
  def but_out_click(self, **event_args):
    # Buat dictionary kosong untuk data outbound baru
    new_outbound = {}

    # Tampilkan alert modal dengan form `outbound_edit`
    save_clicked = alert(
        content=outbound_edit(item=new_outbound),
        title="Menu Outbound",
        large=True,
        buttons=[("Tambahkan", True), ("Kembali", False)]
    )

    if save_clicked:
        # Kirim data outbound ke server function untuk diupdate
        anvil.server.call("update_outbound", new_outbound)

        # Opsional: Perbarui isi tabel setelah perubahan
        self.refresh_hometabel()


  def searchhom_pressed_enter(self, **event_args):
    """Mencari data berdasarkan input pencarian dari pengguna."""
    keyword = self.searchhom.text.strip()  # Ambil kata kunci pencarian
    tanggal = self.piltang.date            # Ambil tanggal yang dipilih
    lokasi = self.pilloc.selected_value    # Ambil lokasi yang dipilih

    # Panggil server function untuk mencari data yang cocok
    self.homtabel.items = anvil.server.call('search_data', keyword, tanggal, lokasi)

  def piltang_change(self, **event_args):
    """Update hasil pencarian saat tanggal berubah."""
    self.searchhom_pressed_enter()

  def pilloc_change(self, **event_args):
    """Update hasil pencarian saat lokasi berubah."""
    self.searchhom_pressed_enter()

  def but_klr_click(self, **event_args):
      """Keluar dari akun dan minta login ulang."""
      if confirm("Apakah Anda yakin ingin keluar?"):
          self.set_blur(True)  # Blur tampilan

          # Logout agar login ulang bisa muncul
          anvil.users.logout()

          # Munculkan form login
          user = anvil.users.login_with_form()
          
          if user:
              # Jika login berhasil, hapus blur
              self.set_blur(False)
          else:
              # Jika login ditutup atau gagal, refresh ulang halaman
              open_form('homepage')


  def set_blur(self, is_blur):
      """Menetapkan efek blur pada halaman."""
      if is_blur:
          self.role = "white_bg"  # Latar putih
          self.role = "blurred"   # Efek blur
      else:
          self.role = None        # Hapus efek blur

  def but_ddsm_click(self, **event_args):
    alert(
      content=ddsm115_edit(),  # Ini akan otomatis jalankan __init__ di dalam ddsm115_edit
      title="Menu DDSM115",
      large=True,
      buttons=[("Tutup", False)]
    )

  def but_remot_click(self, **event_args):
    alert(
      content=ddsm115_kontrol(),  # menjalankan __init__ di dalam ddsm115_edit
      title="Kontrol DDSM115",
      large=True,
      buttons=[("Tutup", False)]
    )

  def pos_agv_click(self, **event_args):
    alert(
      content=agv_posisi(),  # menjalankan __init__ di dalam ddsm115_edit
      title="Kondisi AGV",
      large=True,
      buttons=[("Tutup", False)]
    )

