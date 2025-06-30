import os
import asyncio
import logging
import warnings
import zipfile
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
import discord
from discord import app_commands
from discord.ext import commands
from discord.ext.commands import BucketType
import httpx
from pathlib import Path


warnings.filterwarnings("ignore", message="file_cache is only supported with oauth2client<4.0.0")


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


intents = discord.Intents.default()
intents.message_content = True  
bot = commands.Bot(command_prefix="!", intents=intents)

# Placeholder for official server IDs
OFFICIAL_SERVER_IDS = {
    
}


unauthorized_servers = set()


SERVICE_ACCOUNT_INFO = {}
    


FOLDER_MANIFEST = "" 


GITHUB_TOKEN = ""  # Add your GitHub token here if needed
GITHUB_HEADERS = {"Authorization": f"Bearer {GITHUB_TOKEN}"} if GITHUB_TOKEN else None



http_client = httpx.AsyncClient()


def authenticate_with_google_drive():
    try:
        logging.info("Authenticating with Google Drive API...")
        creds = Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=["https://www.googleapis.com/auth/drive"])
        service = build("drive", "v3", credentials=creds)
        logging.info("Successfully authenticated with Google Drive API.")
        return service
    except Exception as e:
        logging.error(f"Error authenticating with Google Drive API: {e}")
        return None

async def check_file_exists(service, game_id):
    try:
        query = f"'{FOLDER_MANIFEST}' in parents and name='{game_id}.zip'"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get("files", [])
        return bool(files)
    except Exception as e:
        logging.error(f"Error checking if file exists: {e}")
        return False


async def download_file(service, file_id, file_name):
    try:
        logging.info(f"Downloading file: {file_name} (ID: {file_id})")
        request = service.files().get_media(fileId=file_id)
        download_path = os.path.join("temp", file_name)
        os.makedirs("temp", exist_ok=True)

        with open(download_path, "wb") as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                logging.info(f"Download progress: {int(status.progress() * 100)}%")

        logging.info(f"File downloaded successfully: {download_path}")
        return download_path
    except Exception as e:
        logging.error(f"Error downloading file '{file_name}': {e}")
        return None


async def fetch_manifest_file(service, game_id):
    try:
        query = f"'{FOLDER_MANIFEST}' in parents and name='{game_id}.zip'"
        logging.info(f"Searching for file in Google Drive with query: {query}")
        results = service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get("files", [])
        logging.info(f"Files found: {files}")
        return files[0] if files else None
    except Exception as e:
        logging.error(f"Error fetching manifest file: {e}")
        return None

def split_file(file_path, game_id, chunk_size=9 * 1024 * 1024):  
    try:
        with open(file_path, "rb") as f:
            chunk_number = 1
            while True:
                chunk_data = f.read(chunk_size)
                if not chunk_data:
                    break
                chunk_path = os.path.join("temp", f"Part{chunk_number}_{game_id}.zip")
                with open(chunk_path, "wb") as chunk_file:
                    chunk_file.write(chunk_data)
                yield chunk_path
                chunk_number += 1
    except Exception as e:
        logging.error(f"Error splitting file: {e}")
        return None


async def download_from_github(sha, path, repo):
    url = f"https://raw.githubusercontent.com/{repo}/{sha}/{path}"
    try:
        r = await http_client.get(url, headers=GITHUB_HEADERS)
        if r.status_code == 200:
            return r.content
        else:
            logging.error(f"Failed to download {path} from GitHub. Status code: {r.status_code}")
            return None
    except Exception as e:
        logging.error(f"Error downloading {path} from GitHub: {e}")
        return None


async def fetch_manifest_from_github(game_id):
    try:
        for repo in REPOSITORIES:
            url = f"https://api.github.com/repos/{repo}/branches/{game_id}"
            r = await http_client.get(url, headers=GITHUB_HEADERS)
            if r.status_code == 200:
                branch_info = r.json()
                sha = branch_info["commit"]["sha"]
                tree_url = branch_info["commit"]["commit"]["tree"]["url"]
                tree_r = await http_client.get(tree_url, headers=GITHUB_HEADERS)
                if tree_r.status_code == 200:
                    tree_info = tree_r.json()
                    manifest_files = []
                    for item in tree_info["tree"]:
                        if item["path"].endswith(".manifest") or item["path"] == "Key.vdf":
                            content = await download_from_github(sha, item["path"], repo)
                            if content:
                                manifest_files.append((item["path"], content))
                    return manifest_files
        return None
    except Exception as e:
        logging.error(f"Error fetching from GitHub: {e}")
        return None

def create_zip_file(game_id, files):
    zip_path = os.path.join("temp", f"{game_id}.zip")
    with zipfile.ZipFile(zip_path, "w") as zip_file:
        for file_name, content in files:
            zip_file.writestr(file_name, content)
    return zip_path


async def upload_to_google_drive(service, file_path, file_name):
    try:
        file_metadata = {"name": file_name, "parents": [FOLDER_MANIFEST]}
        media = MediaFileUpload(file_path, resumable=True)
        file = service.files().create(body=file_metadata, media_body=media, fields="id").execute()
        logging.info(f"File uploaded to Google Drive with ID: {file.get('id')}")
        return file.get("id")
    except Exception as e:
        logging.error(f"Error uploading file to Google Drive: {e}")
        return None

@bot.tree.command(name="get_manifest", description="Get a game manifest by ID")
@app_commands.describe(game_id="The ID of the game manifest to download")
@commands.cooldown(1, 8, BucketType.user)  # 1 use per 8 seconds per user
async def get_manifest(interaction: discord.Interaction, game_id: str):
    try:

        if interaction.guild and interaction.guild.id not in OFFICIAL_SERVER_IDS:
            if interaction.guild.id not in unauthorized_servers:
                await interaction.response.send_message(
                    "This bot is only for official use. Please join one of the official servers for support:\n"
                    "https://discord.gg/3Tzh3uKzyb",
                    ephemeral=False  
                )
                unauthorized_servers.add(interaction.guild.id)  
            return 


        if interaction.guild is None:
            await interaction.response.send_message(
                "Bot was made by a single developer. Please support their work and use it in the official server:\n"
                "https://discord.gg/3Tzh3uKzyb",
                ephemeral=True,  
            )
            return 

    
        await interaction.response.defer(ephemeral=True)

        if not game_id.isdigit():
            await interaction.followup.send("Invalid input. Please enter an integer value.", ephemeral=True)
            return

        service = authenticate_with_google_drive()
        if not service:
            await interaction.followup.send("Failed to authenticate with Google Drive.", ephemeral=True)
            return

  
        file = await fetch_manifest_file(service, game_id)
        if file:

            await interaction.followup.send(f"Game ID {game_id} found: {file['name']}", ephemeral=False)
            download_path = await download_file(service, file["id"], file["name"])
            if download_path:
                file_size = os.path.getsize(download_path)
                if file_size > 9 * 1024 * 1024: 
                    await interaction.followup.send(
                        f"File {file['name']} is too large ({file_size / 1024 / 1024:.2f} MB). Splitting into chunks...",
                        ephemeral=True
                    )
                    for chunk_path in split_file(download_path, game_id):
                        await interaction.followup.send(
                            f"Uploading chunk: {os.path.basename(chunk_path)}",
                            file=discord.File(chunk_path),
                            ephemeral=True
                        )
                        os.remove(chunk_path) 
                        await asyncio.sleep(1)  
                else:
                    await interaction.followup.send(
                        f"File {file['name']} downloaded successfully. Uploading to the server...",
                        file=discord.File(download_path),
                        ephemeral=True
                    )
                os.remove(download_path)  
            else:
                await interaction.followup.send(f"Failed to download {file['name']}.", ephemeral=True)
        else:
            await interaction.followup.send(
                f"Game ID {game_id} not found in the database. Use `/add_game {game_id}` to add it.",
                ephemeral=True,
            )
    except Exception as e:
        logging.error(f"Error in get_manifest: {e}")
        await interaction.followup.send("An error occurred while processing your request.", ephemeral=True)

# Slash command to add a game
@bot.tree.command(name="add_game", description="Add a game manifest to the database")
@app_commands.describe(game_id="The ID of the game manifest to add")
@commands.cooldown(1, 8, BucketType.user)  
async def add_game(interaction: discord.Interaction, game_id: str):
    try:
      
        if interaction.guild and interaction.guild.id not in OFFICIAL_SERVER_IDS:
            if interaction.guild.id not in unauthorized_servers:
                await interaction.response.send_message(
                    "This bot is only for official use. Please join one of the official servers for support:\n"
                    "https://discord.gg/3Tzh3uKzyb",
                    ephemeral=False  
                )
                unauthorized_servers.add(interaction.guild.id)  
            return  

        if interaction.guild is None:
            await interaction.response.send_message(
                "Bot was made by a single developer. Please support their work and use it in the official server:\n"
                "",
                ephemeral=True,  
            )
            return  

      
        await interaction.response.defer(ephemeral=True)

        if not game_id.isdigit():
            await interaction.followup.send("Invalid input. Please enter an integer value.", ephemeral=True)
            return

        service = authenticate_with_google_drive()
        if not service:
            await interaction.followup.send("Failed to authenticate with Google Drive.", ephemeral=True)
            return


        if await check_file_exists(service, game_id):
            await interaction.followup.send(f"Game ID {game_id} already exists in the database.", ephemeral=True)
            return

        manifest_files = await fetch_manifest_from_github(game_id)
        if not manifest_files:
            await interaction.followup.send(f"Game ID {game_id} not found in any repository.", ephemeral=True)
            return


        zip_path = create_zip_file(game_id, manifest_files)
        if not zip_path:
            await interaction.followup.send("Failed to create a zip file.", ephemeral=True)
            return

        file_name = f"{game_id}.zip"
        file_id = await upload_to_google_drive(service, zip_path, file_name)
        if not file_id:
            await interaction.followup.send("Failed to upload the file to Google Drive.", ephemeral=True)
            return

        await interaction.followup.send(
            f"Game ID {game_id} has been added to the database. You can now use `/get_manifest {game_id}` to download it.",
            ephemeral=True,
        )


        os.remove(zip_path)

    except Exception as e:
        logging.error(f"Error in add_game: {e}")
        await interaction.followup.send("An error occurred while processing your request.", ephemeral=True)

@bot.event
async def on_message(message):
    if message.author.bot:
        return


    if message.guild is None:  
        try:
         
            await message.author.send(
                ""
            )
        except discord.errors.HTTPException as e:
    
            logging.error(f"Cannot send DM to user {message.author}: {e}")
        return  

    if message.guild.id not in OFFICIAL_SERVER_IDS:
        if message.guild.id not in unauthorized_servers:
            await message.channel.send(
                ""
            )
            unauthorized_servers.add(message.guild.id)  
        return 

    await bot.process_commands(message)


@bot.command(name="test")
async def test(ctx):

    if ctx.guild and ctx.guild.id not in OFFICIAL_SERVER_IDS:
        if ctx.guild.id not in unauthorized_servers:
            await ctx.send(
                "This bot is only for official use. "
                ""
            )
            unauthorized_servers.add(ctx.guild.id) 
        return
    await ctx.send("This command works in authorized servers only!", ephemeral=True)


@bot.event
async def on_ready():
    await bot.tree.sync()
    logging.info(f"Logged in as {bot.user.name}")

# Run the bot
if __name__ == "__main__":
    bot.run("")  # Replace with your actual bot token
