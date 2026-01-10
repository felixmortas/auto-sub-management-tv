import gspread

class ExcelManager:
    def __init__(self, spreadsheet_id, credentials_dict):
        # Connexion avec le compte de service
        gc = gspread.service_account_from_dict(credentials_dict)
        self.sh = gc.open_by_key(spreadsheet_id)

    def find_member_in_sheet(self, email, sheet_name):
        """Cherche un adhérent par son mail dans une feuille précise."""
        try:
            worksheet = self.sh.worksheet(sheet_name)
            # On suppose que Mail 1 est à la colonne 11 (K)
            cell = worksheet.find(email, in_column=11)
            if cell:
                return worksheet.row_values(cell.row)
            return None
        except gspread.WorksheetNotFound:
            return None
        except Exception as e:
            print(f"⚠️ Recherche impossible dans '{sheet_name}': {e}")
            return None

    def get_free_plot(self):
        """Trouve la première parcelle sans occupant."""
        print(f"🔍 Recherche d'une parcelle libre...")
        ws = self.sh.worksheet("Configuration_Parcelles")
        data = ws.get_all_records()
        for i, row in enumerate(data, start=2): # start=2 pour l'index Sheets
            if not row['Occupant Actuel']:
                return row['Numéro Parcelle'], i
        return None, None

    def assign_plot(self, plot_number, row_index, name):
        """Inscrit l'occupant dans la feuille de configuration."""
        print(f"✍️ Attribution parcelle {plot_number} à {name}...")
        ws = self.sh.worksheet("Configuration_Parcelles")
        ws.update_cell(row_index, 2, name)

    def remove_plot(self, plot_number):
        """Libère une parcelle en supprimant l'occupant."""
        print(f"🗑️ Libération de la parcelle {plot_number}...")
        ws = self.sh.worksheet("Configuration_Parcelles")
        data = ws.get_all_records()
        for i, row in enumerate(data, start=2):
            if row['Numéro Parcelle'] == plot_number:
                ws.update_cell(i, 2, "")
                print(f"✅ Parcelle {plot_number} libérée.")
                return
        print(f"❌ Parcelle {plot_number} non trouvée.")

    def add_new_row(self, sheet_name, row_data):
        """Ajoute une ligne à la fin de la feuille de l'année."""
        print(f"🚀 Tentative d'ajout dans la feuille '{sheet_name}'...")
        try:
            ws = self.sh.worksheet(sheet_name)
            ws.append_row(row_data)
            print(f"✅ Ligne ajoutée avec succès dans {sheet_name}")
        except gspread.exceptions.WorksheetNotFound:
            print(f"❌ Erreur : La feuille '{sheet_name}' n'existe pas dans le document !")
        except Exception as e:
            print(f"❌ Erreur critique lors de l'ajout : {e}")