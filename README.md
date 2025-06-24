# 🔐 Encrypted  Manager

A secure file-sharing and request management system built with Python, integrating Google Drive and GitHub APIs with end-to-end encryption using AES and PyNaCl.

---

## ✨ Features

- 🔐 **End-to-End Encrypted Communication**  
  Securely decrypts credentials from an encrypted `.env.enc` file using a key fetched from GitHub.

- 🗂 **Google Drive Integration**  
  Authenticates via service account to list, download, and update manifest files stored in Drive folders.

- 📁 **Interactive Secure File Manager**  
  CLI-based tool to:
  - Retrieve Secure Files
  - Request new  additions
  - Submit update requests

- 🧪 **Forward Secrecy & Deniable Authentication**  
  Secure ephemeral key usage ensures that even intercepted files remain indecipherable.

- 📌 **Offline Configuration Support**  
  Stores download directories locally to streamline repeated use.

---

Follow the prompt-based UI to:

    Get File

    Request a File

    Request an Update 

🛡️ Security Highlights

    Encrypted Credential Handling: No plaintext credentials are ever exposed.

    GitHub Key Verification: All key fetches are securely verified and base64-decoded.

    Random IV Generation: Ensures no two ciphertexts are the same.

    AES CBC Mode: Provides strong confidentiality guarantees.

📁 Repo Structure

DriveProject.py          # Main logic
tk.env                   # Local environment variables (to be renamed `.env`)
FetchInfo.env.enc        # Encrypted credentials file
config.txt               # Stores download path config


#### THIS WAS THE INITIAL VERSION AND THE BOT  FILE  IS THE FINAL VERSION 
👤 Author

Made with 🖤 by ROSE
📄 License

This project is licensed for educational/demo purposes only. 