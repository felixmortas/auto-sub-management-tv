import os
from services.outlook_service import OutlookService
from dotenv import load_dotenv

load_dotenv()

def test_mail():
    service = OutlookService(
        client_id=os.getenv("OUTLOOK_CLIENT_ID"),
        client_secret=os.getenv("OUTLOOK_CLIENT_SECRET"),
        refresh_token=os.getenv("OUTLOOK_REFRESH_TOKEN")
    )
    
    success = service.send_plot_notification(
        recipient_email="noiset.lapin@hotmail.fr",
        first_name="Jean",
        plot_number="B-12"
    )
    
    if success:
        print("Le test a réussi !")
    else:
        print("Le test a échoué.")

if __name__ == "__main__":
    test_mail()