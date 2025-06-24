import os
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
import io
from tkinter import filedialog, Tk
import requests
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import base64
from urllib.parse import urlparse
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes
from cryptography.hazmat.primitives import padding
import nacl.secret
import nacl.utils
import json

load_dotenv("tk.env")

SCOPES = ["https://www.googleapis.com/auth/drive"]
FOLDER_MANIFEST = None
FOLDER_ADD_GAMES = None
FOLDER_UPDATE_REQUESTS = None
TEXT_FILE_ADD_GAMES = None
TEXT_FILE_UPDATE_REQUESTS = None
CONFIG_FILE = "config.txt"

def display_welcome_message():
    banner = """
    ================================================
        Steam Manifest Generator v1 (discord-roseies_)      
    ================================================
    Created by: ROSE
    """
    print(banner)

def authenticate_with_google_drive():
    try:
        SERVICE_ACCOUNT_INFO = {
            "type": os.getenv("TYPE"),
            "project_id": os.getenv("PROJECT_ID"),
            "private_key_id": os.getenv("PRIVATE_KEY_ID"),
            "private_key": os.getenv("PRIVATE_KEY").replace("\\n", "\n"),
            "client_email": os.getenv("CLIENT_EMAIL"),
            "client_id": os.getenv("CLIENT_ID"),
            "auth_uri": os.getenv("AUTH_URI"),
            "token_uri": os.getenv("TOKEN_URI"),
            "auth_provider_x509_cert_url": os.getenv("AUTH_PROVIDER_X509_CERT_URL"),
            "client_x509_cert_url": os.getenv("CLIENT_X509_CERT_URL"),
            "universe_domain": os.getenv("UNIVERSE_DOMAIN"),
        }
        creds = Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=SCOPES)
        return build("drive", "v3", credentials=creds)
    except Exception as e:
        print(f"Error authenticating with Google Drive API: {e}")
        return None

def authenticate_with_credentials(credentials_json):
    try:
        credentials_dict = json.loads(credentials_json)
        creds = Credentials.from_service_account_info(credentials_dict, scopes=SCOPES)
        return build("drive", "v3", credentials=creds)
    except Exception as e:
        print(f"Error authenticating with Google Drive API: {e}")
        return None

def authenticate_with_parsed_credentials(credentials_dict):
    try:
        private_key = credentials_dict.get("PRIVATE_KEY").replace("\\n", "\n").strip('"')
        creds = Credentials.from_service_account_info({
            "type": credentials_dict.get("TYPE"),
            "project_id": credentials_dict.get("PROJECT_ID"),
            "private_key_id": credentials_dict.get("PRIVATE_KEY_ID"),
            "private_key": private_key,
            "client_email": credentials_dict.get("CLIENT_EMAIL"),
            "client_id": credentials_dict.get("CLIENT_ID"),
            "auth_uri": credentials_dict.get("AUTH_URI"),
            "token_uri": credentials_dict.get("TOKEN_URI"),
            "auth_provider_x509_cert_url": credentials_dict.get("AUTH_PROVIDER_X509_CERT_URL"),
            "client_x509_cert_url": credentials_dict.get("CLIENT_X509_CERT_URL"),
            "universe_domain": credentials_dict.get("UNIVERSE_DOMAIN"),
        }, scopes=SCOPES)
        return build("drive", "v3", credentials=creds)
    except Exception as e:
        print(f"Error authenticating with Google Drive API: {e}")
        return None

def load_or_prompt_download_directory():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return f.readline().strip()
    else:
        return prompt_download_directory()

def prompt_download_directory():
    root = Tk()
    root.withdraw()
    download_dir = filedialog.askdirectory(title="Select Download Directory")
    root.destroy()
    if download_dir:
        with open(CONFIG_FILE, 'w') as f:
            f.write(download_dir)
        return download_dir
    else:
        print("No download directory selected. Using current working directory.")
        return os.getcwd()

def list_files_in_folder(service, folder_id):
    try:
        results = service.files().list(
            q=f"'{folder_id}' in parents",
            fields="files(id, name)"
        ).execute()
        return results.get("files", [])
    except Exception as e:
        print(f"Error listing files in folder: {e}")
        return None

def download_file(service, file_id, file_name, download_dir):
    try:
        request = service.files().get_media(fileId=file_id)
        download_path = os.path.join(download_dir, file_name)
        with open(download_path, "wb") as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                print(f"Downloading {file_name}: {int(status.progress() * 100)}%")
        print(f"Downloaded {file_name}.")
        return download_path
    except Exception as e:
        print(f"Error downloading file '{file_name}': {e}")
        return None

def write_code_snippet(service, file_id, text_to_append):
    try:
        if not file_id:
            raise ValueError("Missing file ID for appending.")
        file_content = service.files().get_media(fileId=file_id).execute()
        existing_content = file_content.decode("utf-8")
        updated_content = f"{existing_content}\n{text_to_append}"
        media_body = MediaIoBaseUpload(io.BytesIO(updated_content.encode("utf-8")), mimetype="text/plain")
        service.files().update(fileId=file_id, media_body=media_body).execute()
        print("Your request has been submitted.")
    except Exception as e:
        print(f"Error appending to file: {e}")

def download_code_snippet(service, folder_id):
    try:
        results = service.files().list(
            q=f"'{folder_id}' in parents",
            fields="files(id, name)"
        ).execute()
        return results.get("files", [])
    except Exception as e:
        print(f"Error listing files in folder: {e}")
        return None

def fetch_api_data(service, folder_id, file_name):
    try:
        results = service.files().list(
            q=f"'{folder_id}' in parents and name='{file_name}'",
            fields="files(id, name)"
        ).execute()
        files = results.get("files", [])
        if files:
            return files[0]['id']
        else:
            raise ValueError(f"File {file_name} not found in folder {folder_id}.")
    except Exception as e:
        print(f"Error retrieving file ID for {file_name}: {e}")
        return None

def get_manifest(service, download_dir):
    try:
        game_id = input("Enter a game ID (integer value only): ").strip()
        while not game_id.isdigit():
            print("Invalid input. Please enter an integer value.")
            game_id = input("Enter a game ID (integer value only): ").strip()
        folder_id = FOLDER_MANIFEST
        query = f"'{folder_id}' in parents and name='{game_id}.zip'"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get("files", [])
        if files:
            file = files[0]
            print(f"Game ID {game_id} found: {file['name']}")
            download_choice = input(f"Do you want to download {file['name']}? (y/n): ").strip().lower()
            if download_choice == "y":
                download_path = download_file(service, file["id"], file["name"], download_dir)
                if download_path:
                    print(f"File {file['name']} downloaded successfully.")
                    print(f"File downloaded at: {download_path}")
                else:
                    print(f"Failed to download {file['name']}.")
            else:
                print("Download cancelled.")
        else:
            print("ID not found.")
    except Exception as e:
        print(f"Error: {e}")

def request_game(service, download_dir):
    try:
        game_id = input("Enter a ID (integer value only): ").strip()
        while not game_id.isdigit():
            print("Invalid input. Please enter an integer value.")
            game_id = input("Enter a  ID (integer value only): ").strip()
        query = f"'{FOLDER_MANIFEST}' in parents and name='{game_id}.zip'"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get("files", [])
        if files:
            game_file = files[0]
            print(f"File {game_id}.zip already exists.")
            download_choice = input(f"Do you want to download {game_file['name']}? (y/n): ").strip().lower()
            if download_choice == "y":
                download_path = download_file(service, game_file["id"], game_file["name"], download_dir)
                if download_path:
                    print(f"File {game_file['name']} downloaded successfully.")
                    print(f"File downloaded at: {download_path}")
                else:
                    print(f"Failed to download {game_file['name']}.")
            else:
                print("Download cancelled.")
        else:
            write_code_snippet(service, TEXT_FILE_ADD_GAMES, f"Request for Game ID: {game_id}")
    except Exception as e:
        print(f"Error: {e}")

def request_update(service):
    try:
        game_id = input("Enter a  ID (integer value only): ")
        while not game_id.isdigit():
            print("Invalid input. Please enter an integer value.")
            game_id = input("Enter a  ID (integer value only): ")
        folder_id = FOLDER_MANIFEST
        query = f"'{folder_id}' in parents and name='{game_id}.zip'"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get("files", [])
        if files:
            
            write_code_snippet(service, TEXT_FILE_UPDATE_REQUESTS, f"Update request for ID: {game_id}")
        else:
            print("This File doesn't exist in our database yet. Please request using option 2. ")
    except Exception as e:
        print(f"Error: {e}")

def exit_program():
    print("Exiting the program.")
    import sys
    sys.exit()

def verify_digital_signature():
    key = nacl.utils.random(nacl.secret.SecretBox.KEY_SIZE)
    return nacl.secret.SecretBox(key)

class SecureDataTransfer:
    def __init__(self, data):
        self.data = data

    def clear(self):
        self.data = None

def fetch_http_request(repo_url, token):
    owner_repo = repo_url.split("github.com/")[-1].replace('/tree/main', '')
    api_url = 
    headers = {"Authorization": f"token {token}"}
    response = requests.get(api_url, headers=headers)
    if response.status_code == 200:
        content = response.json().get('content')
        if content:
            base64_content = base64.b64decode(content).decode('utf-8')
            key = base64.b64decode(base64_content)
            if len(key) == 32:  
                return key
    print("Key.txt not found or failed to fetch.")
    return None

def decrypt_http_response(ciphertext, key, iv):
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
    plaintext = unpadder.update(padded_plaintext) + unpadder.finalize()
    return plaintext

def verify_digital_copy(input_file, repo_url, token):
    key = fetch_http_request(repo_url, token)
    if not key:
        return None

    with open(input_file, "rb") as f:
        encrypted_data = f.read()

    iv = encrypted_data[:16]
    ciphertext = encrypted_data[16:]

    plaintext = decrypt_http_response(ciphertext, key, iv)

    credentials_str = plaintext.decode('utf-8', errors='ignore')
    credentials_lines = credentials_str.splitlines()
    credentials_dict = {}
    for line in credentials_lines:
        if '=' in line:
            key, value = line.split('=', 1)
            credentials_dict[key.strip()] = value.strip().strip('"')

    global FOLDER_MANIFEST, FOLDER_ADD_GAMES, FOLDER_UPDATE_REQUESTS
    FOLDER_MANIFEST = credentials_dict.get("FOLDER_MANIFEST")
    FOLDER_ADD_GAMES = credentials_dict.get("FOLDER_ADD_GAMES")
    FOLDER_UPDATE_REQUESTS = credentials_dict.get("FOLDER_UPDATE_REQUESTS")

    return authenticate_with_parsed_credentials(credentials_dict)

def main():
    display_welcome_message()
    print("\nWelcome User")
    print("Options:")
    print("1- Get File")
    print("2- Request File")
    print("3- Request an File")
    print("4- Exit")

    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        print("GitHub token not found. Please set it in the environment variables.")
        return

    repo_url = "Your Token Here"

    encrypted_file = "FetchInfo.env.enc"
    if not os.path.exists(encrypted_file):
        print(f"File '{encrypted_file}' not found.")
        return

    service = verify_digital_copy(encrypted_file, repo_url, github_token)

    if service:
        download_dir = load_or_prompt_download_directory()

        global TEXT_FILE_ADD_GAMES, TEXT_FILE_UPDATE_REQUESTS
        TEXT_FILE_ADD_GAMES = fetch_api_data(service, FOLDER_ADD_GAMES, "For Addition.txt")
        TEXT_FILE_UPDATE_REQUESTS = fetch_api_data(service, FOLDER_UPDATE_REQUESTS, "For Updating.txt")

        while True:
            choice = input("\nEnter your selection: ")

            if choice == "1":
                get_manifest(service, download_dir)
            elif choice == "2":
                request_game(service, download_dir)
            elif choice == "3":
                request_update(service)
            elif choice == "4":
                exit_program()
            else:
                print("Invalid selection. Please enter 1, 2, 3, or 4.")

    else:
        print("Failed to authenticate with Google Drive API.")

if __name__ == "__main__":
    main()