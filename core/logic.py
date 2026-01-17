from datetime import datetime

class EnrollmentLogic:
    def __init__(self, excel_manager, whatsapp_service=None, outlook_service=None):
        self.excel = excel_manager
        self.whatsapp_service = whatsapp_service
        self.outlook_service = outlook_service

    def process(self, member_data):
        date = member_data['date']
        year = member_data['year']
        last_year = str(int(year) - 1)
        plot_number = ""
        attribution_date = ""

        # 0. Chercher si l'adhérent existe déjà dans l'année actuelle pour éviter les doublons
        if self.excel.find_member_in_sheet(member_data['payer_email'], year):
            return  # Adhérent déjà enregistré cette année
        
        # 1. Chercher dans l'année précédente
        old_data = self.excel.find_member_in_sheet(member_data['payer_email'], last_year)
                
        if old_data:
            # L'adhérent existe déjà : récupérer toutes ces infos dans la feuille de l'année précédente
            last_name = old_data[0]
            first_name = old_data[1]
            old_membership_type = old_data[2]
            old_members = old_data[3]
            old_plot = old_data[5] # Colonne Numéro de parcelle
            attribution_date = old_data[6] # Colonne Date d'attribution
            phone_1 = old_data[8] # Colonne Téléphone 1
            phone_2 = old_data[9] # Colonne Téléphone 2
            email_1 = old_data[10] # Colonne Mail 1
            email_2 = old_data[11] # Colonne Mail 2

            # Gestion du changement de type d'adhésion
            if member_data['membership_type'] == old_membership_type:
                membership_type = old_membership_type
                members = old_members if membership_type == 'Familiale' else ""
            else:
                membership_type = member_data['membership_type']
                members = member_data['members'] if membership_type == "Familiale" else ""

            # Gestion des changements de parcelle
            if member_data['has_plot'] and not old_plot:
                # Cas : N'a pas de parcelle et achète une parcelle supplémentaire
                plot_number, row_idx = self.excel.get_free_plot()
                if plot_number:
                    self.excel.assign_plot(plot_number, row_idx, last_name)
                    attribution_date = date

            elif member_data['has_plot'] and old_plot:
                # Cas : A une parcelle et la garde
                plot_number = old_plot

            elif not member_data['has_plot'] and old_plot:
                # Cas : A une parcelle et la libère
                self.excel.remove_plot(old_plot)
                plot_number = ""
                attribution_date = ""
            
            elif not member_data['has_plot'] and not old_plot:
                # Cas : N'a pas de parcelle et n'en veut pas
                plot_number = ""
                
        else:
            # Nouvel adhérent : récupération des données du formulaire
            last_name = member_data['last_name']
            first_name = member_data['first_name']
            membership_type = member_data['membership_type']
            members = member_data['members'] if membership_type == "Familiale" else ""
            phone_1 = ""
            phone_2 = ""
            email_1 = ""
            email_2 = ""

            if member_data['has_plot']:
                plot_number, row_idx = self.excel.get_free_plot()
                if plot_number:
                    self.excel.assign_plot(plot_number, row_idx, last_name)
                    attribution_date = date
                

        # 2. Préparation de la ligne finale (format selon vos colonnes)
        # Nom, Prénom, Type, Membres, Date Adh, Num Parcelle, Date Attr, Attente, Tél1, Tél2, Mail1, Mail2
        new_row = [
            last_name,
            first_name,
            membership_type,
            members,
            date,
            plot_number,
            attribution_date,
            "", # En attente
            phone_1, # Téléphones
            phone_2,
            email_1,
            email_2
        ]
        
        self.excel.add_new_row(year, new_row)
        
        # 3. Notification
        if self.whatsapp_service:
            if phone_1 != "":
                if plot_number and (not old_data or not old_data[5]):
                    self.whatsapp_service.send_plot_notification(
                        phone_1,
                        first_name,
                        plot_number
                    )
        elif self.outlook_service:
            if plot_number and (not old_data or not old_data[5]):
                self.outlook_service.send_plot_notification(
                    member_data['payer_email'], # Utilise l'email
                    first_name,
                    plot_number
                )
            elif not plot_number and not old_data:
                self.outlook_service.send_new_sub_notification(
                    member_data['payer_email'], # Utilise l'email
                    first_name
                )