import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp
import json
import os
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CONFIG_FILE = "server_config.json"

# Discord bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="/", intents=intents)
server_config = {}
queues = {}  # Dictionary to store song queues for each guild

def load_config():
    """Load configurations from a JSON file."""
    global server_config
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            server_config = json.load(f)

def save_config():
    """Save current configurations to a JSON file."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(server_config, f, indent=4)

load_config()

@bot.event
async def on_ready():
    print(f'The Music Bot is ready! Logged in as {bot.user}')
    await bot.tree.sync()  # Sync the slash commands globally

@bot.event
async def on_guild_join(guild):
    """Event handler for when the bot joins a new server."""
    default_channel = None
    for channel in guild.text_channels:
        if channel.permissions_for(guild.me).send_messages:
            default_channel = channel
            break

    if default_channel:
        await default_channel.send(
            f"Hello people of {guild.name}, It Is I, AMusica, Your Trusty Discord Music Playing Bot"
        )
    else:
        print(f"Could not send setup instructions to {guild.name} - no accessible channels.")

# Helper function to join a voice channel
async def handle_join(interaction: discord.Interaction):
    """Helper function to handle bot joining a voice channel."""
    user_voice_state = interaction.user.voice  # Check the voice state of the user
    print(f"User voice state: {user_voice_state}")  # Debugging info
    if user_voice_state and user_voice_state.channel:
        channel = user_voice_state.channel  # Use the channel the user is in
        print(f"User is in voice channel: {channel.name}")  # Debugging info
        if interaction.guild.voice_client is None:
            try:
                await channel.connect()
                if not interaction.response.is_done():
                    await interaction.response.send_message(f"Joined {channel.name}!")
            except Exception as e:
                print(f"Error joining voice channel: {e}")  # Debugging info
                if not interaction.response.is_done():
                    await interaction.response.send_message(f"Failed to join the voice channel: {e}")
        else:
            await interaction.guild.voice_client.move_to(channel)
            if not interaction.response.is_done():
                await interaction.response.send_message(f"Moved to {channel.name}!")
    else:
        if not interaction.response.is_done():
            await interaction.response.send_message("You must be in a voice channel to use this command.")

# Command to make the bot join a voice channel
@bot.tree.command(name="join")
async def join(interaction: discord.Interaction):
    """Command to make the bot join a voice channel."""
    await handle_join(interaction)

# Command to make the bot leave a voice channel
@bot.tree.command(name="leave")
async def leave(interaction: discord.Interaction):
    """Command to make the bot leave the voice channel."""
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("Disconnected from the voice channel!")
    else:
        await interaction.response.send_message("I'm not in a voice channel!")

# Command to play music
@bot.tree.command(name="play")
@app_commands.describe(query="The song or video to play.")
async def play(interaction: discord.Interaction, query: str):
    """Play a song from YouTube."""
    if interaction.guild.voice_client is None:
        await handle_join(interaction)

    if interaction.guild.voice_client is None:
        if not interaction.response.is_done():
            await interaction.response.send_message("I couldn't join the voice channel. Please try again.")
        return

    guild_id = interaction.guild.id
    if guild_id not in queues:
        queues[guild_id] = []

    # Search for the YouTube video
    ydl_opts = {'format': 'bestaudio/best'}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch:{query}", download=False)['entries'][0]
            url = info['url']
            title = info['title']

        # Add the song to the queue
        queues[guild_id].append((title, url))
        if not interaction.response.is_done():
            await interaction.response.send_message(f"Added to the queue: **{title}**")

        # If nothing is playing, start playback
        if not interaction.guild.voice_client.is_playing():
            await play_next_song(interaction)
    except Exception as e:
        if not interaction.response.is_done():
            await interaction.response.send_message(f"An error occurred while processing the song: {str(e)}")

async def play_next_song(interaction: discord.Interaction):
    """Play the next song in the queue."""
    guild_id = interaction.guild.id
    if guild_id not in queues or not queues[guild_id]:
        if not interaction.response.is_done():
            await interaction.followup.send("The queue is empty. Add more songs to play!")
        return

    title, url = queues[guild_id][0]  # Get the first song
    queues[guild_id] = queues[guild_id][1:]  # Remove it from the queue

    # Stream the audio
    ffmpeg_options = "-vn"
    audio_source = discord.FFmpegPCMAudio(url, options=ffmpeg_options)
    interaction.guild.voice_client.play(audio_source, after=lambda e: asyncio.run_coroutine_threadsafe(play_next_song(interaction), bot.loop))

    if not interaction.response.is_done():
        await interaction.followup.send(f"Now playing: **{title}**")

# Command to skip the current song
@bot.tree.command(name="skip")
async def skip(interaction: discord.Interaction):
    """Skip the current song."""
    if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("Skipped the current song!")
        await play_next_song(interaction)
    else:
        await interaction.response.send_message("No song is currently playing.")

# Command to show the queue
@bot.tree.command(name="queue")
async def queue(interaction: discord.Interaction):
    """Show the current song queue."""
    guild_id = interaction.guild.id
    if guild_id not in queues or not queues[guild_id]:
        await interaction.response.send_message("The queue is empty.")
        return

    queue_text = "\n".join([f"{i + 1}. {title}" for i, (title, _) in enumerate(queues[guild_id])])
    await interaction.response.send_message(f"**Current Queue:**\n{queue_text}")

bot.run(DISCORD_TOKEN)