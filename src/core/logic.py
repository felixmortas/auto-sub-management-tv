import os

from core.judge import Judge


class EnrollmentLogic:
    """
    Manages the enrollment process for members, including renewing memberships,
    assigning/releasing plots, updating Excel records, and sending notifications.
    """
    def __init__(self, excel_manager, whatsapp_service=None, outlook_service=None):
        self.excel = excel_manager
        self.whatsapp_service = whatsapp_service
        self.outlook_service = outlook_service

    def process(self, member_data: dict) -> None:
        """
        Main workflow orchestrator for processing a member's enrollment.
        """
        date = member_data['date']
        year = member_data['year']
        last_year = str(int(year) - 1)

        # 1. Search for existing member data
        old_data = self._find_previous_member(member_data, last_year)

        # 2. Extract and merge information
        merged_info = self._resolve_member_info(member_data, old_data)

        # 3. Handle plot assignment or release
        old_plot = old_data[5] if old_data else ""
        plot_number, attribution_date = self._handle_plot_allocation(
            wants_plot=member_data['has_plot'],
            old_plot=old_plot,
            current_date=date,
            email=merged_info['email_1']
        )

        # 4. Prepare and save the new Excel row
        new_row = self._build_excel_row(
            info=merged_info,
            date=date,
            plot_number=plot_number,
            attribution_date=attribution_date
        )
        self.excel.add_new_row(year, new_row)

        # 5. Send notifications
        is_new_plot = bool(plot_number) and (not old_data or not old_plot)
        
        self._send_notifications(
            first_name=merged_info['first_name'],
            phone=merged_info['phone_1'],
            email=merged_info['email_1'],
            plot_number=plot_number,
            is_new_plot=is_new_plot
        )

    def _find_previous_member(self, member_data: dict, last_year: str) -> list | None:
        """
        Searches for the member in the previous year's records.
        Prioritizes email search, falls back to LLM-based name matching.
        """
        if member_data.get('email'):
            return self.excel.find_member_in_sheet(last_year, email=member_data['email'])

        # Fallback: search by name using LLM to handle typos
        full_name = f"{member_data['first_name']} {member_data['last_name']}"
        members_names = self.excel.list_members_in_sheet(last_year)
        judge_response = Judge.check_names(
            full_name, 
            members_names, 
            api_key=os.environ["AI_GATEWAY_API_KEY"]
        )
        
        if judge_response.get('similarity_found'):
            last_name = judge_response.get('last_name')
            return self.excel.find_member_in_sheet(last_year, last_name=last_name)
            
        return None

    def _resolve_member_info(self, member_data: dict, old_data: list | None) -> dict:
        """
        PURE FUNCTION: Merges new form data with previous year's data.
        Returns a dictionary containing the standardized member information.
        """
        if old_data:
            old_membership_type = old_data[2]
            old_members = old_data[3]

            # Resolve membership type and family members dynamically
            if member_data['membership_type'] == old_membership_type:
                membership_type = old_membership_type
                members = old_members if membership_type == 'Familiale' else ""
            else:
                membership_type = member_data['membership_type']
                members = member_data['members'] if membership_type == "Familiale" else ""

            return {
                'last_name': old_data[0],
                'first_name': old_data[1],
                'membership_type': membership_type,
                'members': members,
                'phone_1': old_data[8],
                'phone_2': old_data[9],
                'email_1': old_data[10],
                'email_2': old_data[11]
            }
            
        # If no old data exists, initialize from new member data
        membership_type = member_data['membership_type']
        return {
            'last_name': member_data['last_name'],
            'first_name': member_data['first_name'],
            'membership_type': membership_type,
            'members': member_data['members'] if membership_type == "Familiale" else "",
            'phone_1': "",
            'phone_2': "",
            'email_1': member_data['email'],
            'email_2': ""
        }

    def _handle_plot_allocation(self, wants_plot: bool, old_plot: str, current_date: str, email: str) -> tuple[str, str]:
        """
        Handles the side effects of plot allocation and releases in Excel.
        Returns a tuple containing the (plot_number, attribution_date).
        """
        plot_number = ""
        attribution_date = ""

        if wants_plot and not old_plot:
            # Case: Did not have a plot previously, wants a new one
            new_plot_number, row_idx = self.excel.get_free_plot()
            if new_plot_number:
                self.excel.assign_plot(new_plot_number, row_idx, email)
                plot_number = new_plot_number
                attribution_date = current_date

        elif wants_plot and old_plot:
            # Case: Already has a plot and wants to keep it
            plot_number = old_plot

        elif not wants_plot and old_plot:
            # Case: Has a plot but wants to release it
            self.excel.remove_plot(old_plot)
            # Both plot_number and attribution_date naturally remain empty
            
        # Implicit final case: not wants_plot and not old_plot -> remain empty

        return plot_number, attribution_date

    def _build_excel_row(self, info: dict, date: str, plot_number: str, attribution_date: str) -> list:
        """
        PURE FUNCTION: Formats the final list representing the Excel row.
        """
        return [
            info['last_name'],
            info['first_name'],
            info['membership_type'],
            info['members'],
            date,
            plot_number,
            attribution_date,
            "",  # Pending status (En attente)
            info['phone_1'],
            info['phone_2'],
            info['email_1'],
            info['email_2']
        ]

    def _send_notifications(self, first_name: str, phone: str, email: str, plot_number: str, is_new_plot: bool) -> None:
        """
        Handles notification dispatch. 
        WhatsApp is intentionally exclusive to prevent notifying the user twice.
        """
        # Exclusivity pattern: if WhatsApp is initialized, Outlook is ignored
        if self.whatsapp_service and phone:
            # self.whatsapp_serce.send_new_sub_notification(phone, first_name)
            if is_new_plot:
                self.whatsapp_service.send_plot_notification(phone, first_name, plot_number)
                
        elif self.outlook_service and email:
            self.outlook_service.send_new_sub_notification(email, first_name)
            if is_new_plot:
                self.outlook_service.send_plot_notification(email, first_name, plot_number)
