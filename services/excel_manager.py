import logging

import gspread

logger = logging.getLogger(__name__)


class ExcelManager:
    def __init__(self, spreadsheet_id, credentials_dict):
        # Connexion avec le compte de service
        logger.debug("Connexion au classeur Google Sheets %s", spreadsheet_id)
        gc = gspread.service_account_from_dict(credentials_dict)
        self.sh = gc.open_by_key(spreadsheet_id)

    def find_member_in_sheet(self, sheet_name, email=None, last_name=None):
        """Cherche un adhérent par son mail dans une feuille précise."""
        try:
            worksheet = self.sh.worksheet(sheet_name)
            if email:
                # On suppose que Mail 1 est à la colonne 11 (K)
                cell = worksheet.find(email, in_column=11)
            elif last_name:
                # On suppose que Nom de famille est à la colonne 1 (A)
                cell = worksheet.find(last_name, in_column=1)
            else:
                return None

            if cell:
                logger.debug("Adhérent trouvé dans '%s', ligne %s", sheet_name, cell.row)
                return worksheet.row_values(cell.row)

            logger.debug("Aucun adhérent trouvé dans '%s'", sheet_name)
            return None
        except gspread.WorksheetNotFound:
            logger.debug("Feuille '%s' introuvable", sheet_name)
            return None
        except Exception:
            # DEBUG uniquement : reste totalement silencieux en prod.
            logger.debug(
                "Recherche impossible dans '%s'",
                sheet_name,
                exc_info=True,
            )
            return None

    def list_members_in_sheet(self, sheet_name):
        """Retourne une liste des noms complets des membres dans une feuille."""
        try:
            worksheet = self.sh.worksheet(sheet_name)
            data = worksheet.get_all_records()

            names = [f"{row['Prénom']} {row['Nom']}" for row in data]
            logger.debug("%s membre(s) trouvé(s) dans '%s'", len(names), sheet_name)
            return names
        except gspread.WorksheetNotFound:
            logger.debug("Feuille '%s' introuvable", sheet_name)
            return ""
        except Exception:
            logger.debug(
                "Impossible de lister les membres dans '%s'",
                sheet_name,
                exc_info=True,
            )
            return ""

    def get_free_plot(self):
        """Trouve la première parcelle sans occupant."""
        logger.debug("Recherche d'une parcelle libre...")
        ws = self.sh.worksheet("Configuration_Parcelles")
        data = ws.get_all_records()
        for i, row in enumerate(data, start=2):  # start=2 pour l'index Sheets
            if not row['Occupant Actuel']:
                logger.debug(
                    "Parcelle libre trouvée : %s (ligne %s)",
                    row['Numéro Parcelle'],
                    i,
                )
                return row['Numéro Parcelle'], i

        logger.debug("Aucune parcelle libre trouvée")
        return None, None

    def assign_plot(self, plot_number, row_index, email):
        """Inscrit l'occupant dans la feuille de configuration."""
        logger.debug("Attribution de la parcelle %s à %s", plot_number, email)
        ws = self.sh.worksheet("Configuration_Parcelles")
        ws.update_cell(row_index, 2, email)

    def remove_plot(self, plot_number):
        """Libère une parcelle en supprimant l'occupant."""
        logger.debug("Libération de la parcelle %s", plot_number)
        ws = self.sh.worksheet("Configuration_Parcelles")
        data = ws.get_all_records()
        for i, row in enumerate(data, start=2):
            if row['Numéro Parcelle'] == plot_number:
                ws.update_cell(i, 2, "")
                logger.debug("Parcelle %s libérée", plot_number)
                return

        logger.debug("Parcelle %s non trouvée", plot_number)

    def add_new_row(self, sheet_name, row_data):
        """Ajoute une ligne à la fin de la feuille de l'année."""
        logger.debug("Tentative d'ajout dans la feuille '%s'", sheet_name)
        try:
            ws = self.sh.worksheet(sheet_name)
            ws.append_row(row_data)
            logger.debug("Ligne ajoutée avec succès dans '%s'", sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            logger.debug("La feuille '%s' n'existe pas dans le document", sheet_name)
        except Exception:
            logger.debug(
                "Erreur lors de l'ajout dans '%s'",
                sheet_name,
                exc_info=True,
            )
