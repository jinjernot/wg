import pandas as pd
import pytz
from datetime import datetime

def export_to_csv(fundings, filename='bitso_deposits.csv'):
    data = []

    # Define the timezone
    mexico_tz = pytz.timezone('America/Mexico_City')

    for f in fundings:
        details = f.get('details', {})
        legal = f.get('legal_operation_entity', {})
        utc_dt_str = f.get('created_at')

        # Convert UTC to Mexico time
        try:
            utc_dt = datetime.strptime(utc_dt_str, "%Y-%m-%dT%H:%M:%S+00:00").replace(tzinfo=pytz.UTC)
            local_dt = utc_dt.astimezone(mexico_tz)
            local_dt_str = local_dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            local_dt_str = ''  # Fallback in case of format issue

        data.append({
            'Funding ID': f.get('fid'),
            'Status': f.get('status'),
            'Date (UTC)': utc_dt_str,
            'Date (Mexico City)': local_dt_str,
            'Amount': f.get('amount'),
            'Currency': f.get('currency'),
            'Asset': f.get('asset'),
            'Method': f.get('method'),
            'Method Name': f.get('method_name'),
            'Network': f.get('network'),
            'Protocol': f.get('protocol'),
            'Integration': f.get('integration'),
            'Sender Name': details.get('sender_name'),
            'Sender Ref': details.get('sender_ref'),
            'Sender CLABE': details.get('sender_clabe'),
            'Receive CLABE': details.get('receive_clabe'),
            'Sender Bank': details.get('sender_bank'),
            'CLAVE': details.get('clave'),
            'CLAVE Rastreo': details.get('clave_rastreo'),
            'Numeric Reference': details.get('numeric_reference'),
            'Concept': details.get('concepto'),
            'CEP Link': details.get('cep_link'),
            'Sender RFC/CURP': details.get('sender_rfc_curp'),
            'Deposit Type': details.get('deposit_type'),
            'Notes': details.get('notes'),
            'Emoji': details.get('emoji'),
            'Legal Entity Name': legal.get('name'),
            'Legal Country': legal.get('country_code_iso_2'),
            'Legal Image ID': legal.get('image_id')
        })

    df = pd.DataFrame(data)
    df.to_csv(filename, index=False)
    print(f"Deposit summary saved to {filename}")

def export_failed_to_csv(fundings, filename='bitso_failed_deposits.csv'):
    failed_fundings = [f for f in fundings if f.get('status') == 'failed']
    if not failed_fundings:
        print("No failed fundings to export.")
        return

    data = []
    mexico_tz = pytz.timezone('America/Mexico_City')
    for f in failed_fundings:
        details = f.get('details', {})
        legal = f.get('legal_operation_entity', {})
        utc_dt_str = f.get('created_at')

        try:
            utc_dt = datetime.strptime(utc_dt_str, "%Y-%m-%dT%H:%M:%S+00:00").replace(tzinfo=pytz.UTC)
            local_dt = utc_dt.astimezone(mexico_tz)
            local_dt_str = local_dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            local_dt_str = ''

        data.append({
            'Funding ID': f.get('fid'),
            'Status': f.get('status'),
            'Date (UTC)': utc_dt_str,
            'Date (Mexico City)': local_dt_str,
            'Amount': f.get('amount'),
            'Currency': f.get('currency'),
            'Asset': f.get('asset'),
            'Method': f.get('method'),
            'Method Name': f.get('method_name'),
            'Network': f.get('network'),
            'Protocol': f.get('protocol'),
            'Integration': f.get('integration'),
            'Sender Name': details.get('sender_name'),
            'Sender Ref': details.get('sender_ref'),
            'Sender CLABE': details.get('sender_clabe'),
            'Receive CLABE': details.get('receive_clabe'),
            'Sender Bank': details.get('sender_bank'),
            'CLAVE': details.get('clave'),
            'CLAVE Rastreo': details.get('clave_rastreo'),
            'Numeric Reference': details.get('numeric_reference'),
            'Concept': details.get('concepto'),
            'CEP Link': details.get('cep_link'),
            'Sender RFC/CURP': details.get('sender_rfc_curp'),
            'Deposit Type': details.get('deposit_type'),
            'Notes': details.get('notes'),
            'Emoji': details.get('emoji'),
            'Legal Entity Name': legal.get('name'),
            'Legal Country': legal.get('country_code_iso_2'),
            'Legal Image ID': legal.get('image_id')
        })

    df = pd.DataFrame(data)
    df.to_csv(filename, index=False)
    print(f"Failed deposit summary saved to {filename}")