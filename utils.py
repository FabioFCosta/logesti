import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import pandas as pd
import streamlit as st
import uuid
from dotenv import load_dotenv


load_dotenv()

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.readonly'
]

FILE_ID = os.getenv("FILE_ID") or st.secrets.get("FILE_ID")
def authenticate():
    creds = None

    # Try Streamlit Secrets (for Cloud deployment)
    try:
        if "google_sheets_credentials" in st.secrets:
            creds_dict = st.secrets["google_sheets_credentials"]
            creds = Credentials.from_authorized_user_info(creds_dict, SCOPES)
            if creds and creds.valid:
                return creds
    except:
        pass

    # Try local token.json (for local development)
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        if creds and creds.valid:
            return creds

    # Try local credentials.json (for local development)
    if os.path.exists("credentials.json"):
        flow = InstalledAppFlow.from_client_secrets_file(
            "credentials.json", SCOPES
        )
        creds = flow.run_local_server(port=0)

        with open("token.json", "w") as token:
            token.write(creds.to_json())

    return creds

def get_sheets_service():
    creds = authenticate()
    return build('sheets', 'v4', credentials=creds)

def parse_currency(col):
    normalized = (
        col.astype(str)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .replace("", "0")
    )
    return pd.to_numeric(normalized, errors="coerce").fillna(0.0)

def save_incomes(file_id, df):
    service = get_sheets_service()

    df = df.fillna("")

    body = {
        "values": [df.columns.tolist()] + df.values.tolist()
    }

    service.spreadsheets().values().update(
        spreadsheetId=file_id,
        range="INCOMES_DB!A1",
        valueInputOption="RAW",
        body=body
    ).execute()

def format_brl(value):
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def format_date_br(value):
    if pd.isna(value):
        return ""

    try:
        return pd.to_datetime(value).strftime("%d/%m/%Y")
    except Exception:
        return str(value)

def save_sheet(file_id, sheet_name, df):
    service = get_sheets_service()

    def df_to_values(df):
        clean_df = df.copy()

        clean_df = clean_df.fillna("")

        if "active" in clean_df.columns:
            clean_df["active"] = clean_df["active"].astype(bool)

        return [clean_df.columns.tolist()] + clean_df.values.tolist()

    body = {
        "valueInputOption": "RAW",
        "data": [
            {
                "range": f"{sheet_name}!A1",
                "values": df_to_values(df)
            }
        ]
    }

    service.spreadsheets().values().batchUpdate(
        spreadsheetId=file_id,
        body=body
    ).execute()


def ensure_sheet_exists(file_id, sheet_name):
    service = get_sheets_service()
    spreadsheet = service.spreadsheets().get(
        spreadsheetId=file_id,
        fields="sheets.properties.title"
    ).execute()

    titles = [sheet["properties"]["title"] for sheet in spreadsheet.get("sheets", [])]
    if sheet_name not in titles:
        service.spreadsheets().batchUpdate(
            spreadsheetId=file_id,
            body={
                "requests": [
                    {"addSheet": {"properties": {"title": sheet_name}}}
                ]
            }
        ).execute()


def load_km_rates(file_id):
    service = get_sheets_service()
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=file_id,
            range="GENERAL_SETTINGS_DB!A1:B"
        ).execute()
    except Exception:
        return {"valor_km_carro": 0.0, "valor_km_moto": 0.0}

    values = result.get("values", [])
    if not values or len(values) < 2:
        return {"valor_km_carro": 0.0, "valor_km_moto": 0.0}

    headers = [h.strip().lower() for h in values[0]]
    settings = pd.DataFrame(values[1:], columns=headers)

    if "value" not in settings.columns:
        if len(settings.columns) >= 2:
            settings = settings.rename(columns={settings.columns[1]: "value"})
        else:
            return {"valor_km_carro": 0.0, "valor_km_moto": 0.0}

    if "key" not in settings.columns:
        if len(settings.columns) >= 1:
            settings = settings.rename(columns={settings.columns[0]: "key"})
        else:
            return {"valor_km_carro": 0.0, "valor_km_moto": 0.0}

    settings["value"] = pd.to_numeric(settings["value"].astype(str).str.replace(',', '.'), errors="coerce").fillna(0.0)

    return {
        setting["key"]: setting["value"]
        for _, setting in settings.iterrows()
        if setting.get("key") in ["valor_km_carro", "valor_km_moto"]
    }


def save_km_rates(file_id, rates):
    ensure_sheet_exists(file_id, "GENERAL_SETTINGS_DB")
    settings_df = pd.DataFrame([
        {"key": "valor_km_carro", "value": rates.get("valor_km_carro", 0.0)},
        {"key": "valor_km_moto", "value": rates.get("valor_km_moto", 0.0)}
    ])
    save_sheet(file_id, "GENERAL_SETTINGS_DB", settings_df)


def normalize_df(df):
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]

    if "id" not in df.columns:
        df["id"] = None

    mask = df["id"].isna() | (df["id"] == "") | (df["id"] == "nan")

    if mask.any():
        df.loc[mask, "id"] = [str(uuid.uuid4()) for _ in range(mask.sum())]

    if "active" not in df.columns:
        df["active"] = True

    df["active"] = df["active"].fillna(True)

    return df

def load_db_sheets(file_id):
    creds = authenticate()
    service = build('drive', 'v3', credentials=creds)

    request = service.files().export_media(
        fileId=file_id,
        mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

    import io
    file_data = io.BytesIO(request.execute())

    clientes = pd.read_excel(file_data, sheet_name="CLIENTES_DB")
    file_data.seek(0)  # reset buffer
    orcamentos = pd.read_excel(file_data, sheet_name="ORCAMENTOS_DB")

    return clientes, orcamentos

def get_clientes_and_orcamentos():

    if "clientes" not in st.session_state:
        clientes, orcamentos = load_db_sheets(FILE_ID)
        required_cols = ["id", "nome", "contato", "e-mail", "endereco", "km", "active"]

        if not all(col in clientes.columns for col in required_cols):
            st.error("Estrutura inválida da tabela CLIENTES_DB")
            st.stop()

        if not all(col in orcamentos.columns for col in required_cols):
            st.error("Estrutura inválida da tabela ORCAMENTO_DB")
            st.stop()

        clientes = normalize_df(clientes)
        orcamentos = normalize_df(orcamentos)

        st.session_state.clientes = clientes
        st.session_state.orcamentos = orcamentos

    else:
        clientes = st.session_state.clientes
        orcamentos = st.session_state.orcamentos    
    return clientes, orcamentos

def load_outcome_payments(file_id):
    service = get_sheets_service()

    result = service.spreadsheets().values().get(
        spreadsheetId=file_id,
        range="PAYMENTS_OUT_DB!A1:Z"
    ).execute()

    values = result.get("values", [])

    if not values:
        return pd.DataFrame(columns=["id", "outcome_id", "data_pagamento", "valor_pago"])

    headers = values[0]
    rows = values[1:]

    normalized_rows = [
        row + [""] * (len(headers) - len(row))
        if len(row) < len(headers)
        else row[:len(headers)]
        for row in rows
    ]

    df = pd.DataFrame(normalized_rows, columns=headers)
    df.columns = [c.strip().lower() for c in df.columns]

    df["valor_pago"] = parse_currency(df["valor_pago"])

    df["data_pagamento"] = pd.to_datetime(
        df["data_pagamento"],
        format="mixed",
        dayfirst=True,
        errors="coerce"
    )

    return df

def load_income_payments(file_id):
    service = get_sheets_service()

    result = service.spreadsheets().values().get(
        spreadsheetId=file_id,
        range="INCOMES_PAYMENTS_DB!A1:Z"
    ).execute()

    values = result.get("values", [])

    if not values:
        return pd.DataFrame(columns=["id", "income_id", "data_pagamento", "valor_pago"])

    headers = values[0]
    rows = values[1:]

    normalized_rows = [
        row + [""] * (len(headers) - len(row))
        if len(row) < len(headers)
        else row[:len(headers)]
        for row in rows
    ]

    df = pd.DataFrame(normalized_rows, columns=headers)
    df.columns = [c.strip().lower() for c in df.columns]

    df["valor_pago"] = parse_currency(df["valor_pago"])

    df["data_pagamento"] = pd.to_datetime(
        df["data_pagamento"],
        format="mixed",
        dayfirst=True,
        errors="coerce"
    )

    return df

def load_incomes(file_id):
    service = get_sheets_service()

    result = service.spreadsheets().values().get(
        spreadsheetId=file_id,
        range="INCOMES_DB!A1:Z"
    ).execute()

    values = result.get("values", [])

    if not values:
        return pd.DataFrame()

    headers = values[0]
    rows = values[1:]

    normalized_rows = [
        row + [""] * (len(headers) - len(row))
        if len(row) < len(headers)
        else row[:len(headers)]
        for row in rows
    ]

    df = pd.DataFrame(normalized_rows, columns=headers)
    df.columns = [c.strip().lower() for c in df.columns]

    df["valor"] = parse_currency(df["valor"])

    df["data"] = pd.to_datetime(
        df["data"],
        format="mixed",
        dayfirst=True,
        errors="coerce"
    )

    df = df.dropna(subset=["data"])

    return df


def load_outcomes(file_id):
    service = get_sheets_service()

    result = service.spreadsheets().values().get(
        spreadsheetId=file_id,
        range="OUTCOMES_DB!A1:Z"
    ).execute()

    values = result.get("values", [])

    if not values:
        return pd.DataFrame()

    headers = values[0]
    rows = values[1:]

    normalized_rows = [
        row + [""] * (len(headers) - len(row))
        if len(row) < len(headers)
        else row[:len(headers)]
        for row in rows
    ]

    df = pd.DataFrame(normalized_rows, columns=headers)
    df.columns = [c.strip().lower() for c in df.columns]

    df["valor"] = parse_currency(df["valor"])
    df["km"] = parse_currency(df["km"])
    df["km_rate"] = parse_currency(df["km_rate"])

    df["data_vencimento"] = pd.to_datetime(
        df["data_vencimento"],
        format="mixed",
        dayfirst=True,
        errors="coerce"
    )

    df = df.dropna(subset=["data_vencimento"])

    return df
