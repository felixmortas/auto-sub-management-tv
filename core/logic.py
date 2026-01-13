from datetime import datetime

class EnrollmentLogic:
    def __init__(self, excel_manager, whatsapp_service=None, outlook_service=None):
        self.excel = excel_manager
        self.whatsapp_service = whatsapp_service
        self.outlook_service = outlook_service

    def process(self, member_data):
        year = member_data['year']
        last_year = str(int(year) - 1)
        last_name = member_data['last_name']
        first_name = member_data['first_name']
        full_name = f"{first_name} {last_name}"
        
        # 1. Chercher dans l'année précédente
        old_data = self.excel.find_member_in_sheet(member_data['email'], last_year)
        
        plot_number = ""
        attribution_date = ""
        
        if old_data:
            # L'adhérent existe déjà
            old_plot = old_data[5] # Colonne Numéro de parcelle
            
            if member_data['has_plot'] and not old_plot:
                # Cas : N'a pas de parcelle et achète une parcelle supplémentaire
                plot_number, row_idx = self.excel.get_free_plot()
                if plot_number:
                    self.excel.assign_plot(plot_number, row_idx, last_name)
                    attribution_date = datetime.now().strftime("%d/%m/%Y")

            elif member_data['has_plot'] and old_plot:
                # Cas : A une parcelle et la garde
                plot_number = old_plot
                attribution_date = datetime.now().strftime("%d/%m/%Y")

            elif not member_data['has_plot'] and old_plot:
                # Cas : A une parcelle et la libère
                self.excel.remove_plot(old_plot)
                plot_number = ""
                attribution_date = ""
            
            elif not member_data['has_plot'] and not old_plot:
                # Cas : N'a pas de parcelle et n'en veut pas
                plot_number = ""
                attribution_date = ""
                
        else:
            # Nouvel adhérent
            if member_data['has_plot']:
                plot_number, row_idx = self.excel.get_free_plot()
                if plot_number:
                    self.excel.assign_plot(plot_number, row_idx, last_name)
                    attribution_date = datetime.now().strftime("%d/%m/%Y")

        # 2. Préparation de la ligne finale (format selon vos colonnes)
        # Nom, Prénom, Type, Membres, Date Adh, Num Parcelle, Date Attr, Attente, Tél1, Tél2, Mail1, Mail2
        new_row = [
            last_name,
            first_name,
            member_data['membership_type'],
            "", # Membres si familiale (à remplir manuellement ou parser)
            member_data['date'],
            plot_number,
            attribution_date,
            "", # En attente
            member_data['phone'], 
            "", # Téléphones
            member_data['email'],
            ""  # Mail 2
        ]
        
        self.excel.add_new_row(year, new_row)
        
        # 3. Notification
        if self.whatsapp_service:
            if plot_number and (not old_data or not old_data[5]):
                # format phone number to french using 33 prefix
                phone = member_data['phone']
                if phone.startswith("0"):
                    phone = "33" + phone[1:]
                elif phone.startswith("+"):
                    phone = phone[1:]
                self.whatsapp_service.send_plot_notification(
                    phone,
                    first_name,
                    plot_number
                )
        elif self.outlook_service:
            if plot_number and (not old_data or not old_data[5]):
                self.outlook_service.send_plot_notification(
                    member_data['email'], # Utilise l'email
                    first_name,
                    plot_number
                )
            elif not plot_number and not old_data:
                self.outlook_service.send_new_sub_notification(
                    member_data['email'], # Utilise l'email
                    first_name
                )