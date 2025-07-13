from ._anvil_designer import ddsm115_editTemplate
from anvil import *
import anvil.users
import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
import datetime
from anvil.tables import app_tables


class ddsm115_edit(ddsm115_editTemplate):
  def __init__(self, **properties):
    # Set Form properties and Data Bindings.
    self.init_components(**properties)
    # Any code you write here will run before the form opens.
    self.refresh_ddsm115_tabel()

  def refresh_ddsm115_tabel(self):
    data = anvil.server.call('get_ddsm115_data')
  
    # Buat salinan dictionary baru untuk setiap row
    formatted_data = []
    for row in data:
      new_row = dict(row)  # salin isi row
      if isinstance(new_row['Waktu'], datetime.datetime):
        new_row['Waktu'] = new_row['Waktu'].strftime("%H:%M:%S")
      formatted_data.append(new_row)
  
    self.ddsm_tabel.items = formatted_data


 