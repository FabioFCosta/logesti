import json
import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
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
print(f"Using FILE_ID: {FILE_ID}")
def authenticate():
    creds = None

    # Try Streamlit Secrets (service account)
    try:
        if "google_service_account" in st.secrets:
            service_account_info = st.secrets["google_service_account"]
            if isinstance(service_account_info, str):
                service_account_info = json.loads(service_account_info)
            creds = ServiceAccountCredentials.from_service_account_info(
                service_account_info,
                scopes=SCOPES,
            )
            return creds
    except Exception:
        pass

    # Try environment service account info
    try:
        sa_info = os.getenv("GOOGLE_SERVICE_ACCOUNT_INFO")
        if sa_info:
            service_account_info = json.loads(sa_info)
            creds = ServiceAccountCredentials.from_service_account_info(
                service_account_info,
                scopes=SCOPES,
            )
            return creds
    except Exception:
        pass

    # Try environment service account file path
    try:
        sa_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or os.getenv("SERVICE_ACCOUNT_FILE")
        if sa_file and os.path.exists(sa_file):
            creds = ServiceAccountCredentials.from_service_account_file(
                sa_file,
                scopes=SCOPES,
            )
            return creds
    except Exception:
        pass

    # Try Streamlit Secrets (for Cloud deployment)
    try:
        if "google_sheets_credentials" in st.secrets:
            creds_dict = dict(st.secrets["google_sheets_credentials"])
            creds_dict.setdefault("token_uri", "https://oauth2.googleapis.com/token")
            creds = Credentials.from_authorized_user_info(creds_dict, SCOPES)
            if creds and creds.valid:
                return creds
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                return creds
    except Exception:
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

    if creds is None:
        raise RuntimeError(
            "No Google credentials found. "
            "Add a service account as Streamlit secret 'google_service_account', "
            "or add user OAuth credentials as 'google_sheets_credentials'."
        )

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

def reassign_quote_to_client(incomes_df, outcomes_df, quote_id, client_id):
    incomes_df = incomes_df.copy()
    outcomes_df = outcomes_df.copy()

    if "quote_id" in incomes_df.columns:
        incomes_mask = incomes_df["quote_id"] == quote_id
        incomes_df.loc[incomes_mask, "client_id"] = client_id
        incomes_df.loc[incomes_mask, "quote_id"] = ""

    if "quote_id" in outcomes_df.columns:
        outcomes_mask = outcomes_df["quote_id"] == quote_id
        outcomes_df.loc[outcomes_mask, "client_id"] = client_id
        outcomes_df.loc[outcomes_mask, "quote_id"] = ""

    return incomes_df, outcomes_df

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
    settings_df = load_general_settings(file_id)

    for key in ("valor_km_carro", "valor_km_moto"):
        value = rates.get(key, 0.0)
        mask = settings_df["key"] == key
        if mask.any():
            settings_df.loc[mask, "value"] = value
            settings_df.loc[mask, "type"] = "km"
            settings_df.loc[mask, "active"] = True
        else:
            new_row = {"key": key, "value": value, "type": "km", "active": True}
            settings_df = pd.concat(
                [settings_df, pd.DataFrame([new_row])], ignore_index=True)

    save_sheet(file_id, "GENERAL_SETTINGS_DB", settings_df)


def load_general_settings(file_id):
    service = get_sheets_service()
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=file_id,
            range="GENERAL_SETTINGS_DB!A1:D"
        ).execute()
    except Exception:
        return pd.DataFrame(columns=["key", "value", "type", "active"])

    values = result.get("values", [])
    if not values or len(values) < 2:
        return pd.DataFrame(columns=["key", "value", "type", "active"])

    headers = [h.strip().lower() for h in values[0]]
    rows = values[1:]
    # Pad short rows so pandas doesn't choke on ragged data from the sheet
    rows = [row + [""] * (len(headers) - len(row)) for row in rows]
    settings = pd.DataFrame(rows, columns=headers)

    if "key" not in settings.columns:
        settings["key"] = ""
    if "value" not in settings.columns:
        settings["value"] = ""
    if "type" not in settings.columns:
        settings["type"] = ""
    if "active" not in settings.columns:
        settings["active"] = True
    else:
        settings["active"] = settings["active"].apply(
            lambda v: True if v == "" or pd.isna(v) else str(v).strip().lower() in ("true", "1", "verdadeiro")
        )

    return settings


def load_type_options(file_id, category):
    seeds = {
        "income_options": [
            "Reembolso", "Acompanhamento", "Projeto", "Administração",
            "Orçamento", "Perícia", "Juros", "Pedágio", "Outros"
        ],
        "outcomes_options": [
            "Visita", "Mão de obra", "Pro Labore", "Adquirir Ativo",
            "Fornecedor", "Impostos/Taxas", "Gasolina", "Reembolso",
            "Alimentação", "Contabilidade", "Entrega Obras", "Frete",
            "Juros", "Pedágio", "Outros"
        ],
    }

    settings = load_general_settings(file_id)
    category_rows = settings[settings["type"] == category]

    if category_rows.empty:
        ensure_sheet_exists(file_id, "GENERAL_SETTINGS_DB")
        seed_values = seeds.get(category, [])
        new_rows = pd.DataFrame([
            {"key": nome, "value": "", "type": category, "active": True}
            for nome in seed_values
        ])
        settings = pd.concat([settings, new_rows], ignore_index=True)
        save_sheet(file_id, "GENERAL_SETTINGS_DB", settings)
        return seed_values

    active_rows = category_rows[category_rows["active"] == True]
    return active_rows["key"].tolist()


def save_type_option(file_id, category, nome):
    ensure_sheet_exists(file_id, "GENERAL_SETTINGS_DB")
    settings = load_general_settings(file_id)
    mask = (settings["key"] == nome) & (settings["type"] == category)
    if mask.any():
        # Option already exists (likely deactivated) — reactivate instead of duplicating the row
        settings.loc[mask, "active"] = True
    else:
        new_row = {"key": nome, "value": "", "type": category, "active": True}
        settings = pd.concat(
            [settings, pd.DataFrame([new_row])], ignore_index=True)
    save_sheet(file_id, "GENERAL_SETTINGS_DB", settings)


def set_type_option_active(file_id, category, nome, active):
    settings = load_general_settings(file_id)
    mask = (settings["key"] == nome) & (settings["type"] == category)
    settings.loc[mask, "active"] = active
    save_sheet(file_id, "GENERAL_SETTINGS_DB", settings)


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
