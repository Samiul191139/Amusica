import os
import asyncio
import discord
from discord.ext import commands
from youtube_dl import YoutubeDL

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)
queues = {}

YDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    # Add these new parameters
    'forceip': 4,
    'geo-bypass': True,
    'quiet': True,
    'no_warnings': True,
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -nostdin',
    'options': '-vn -sn -dn -ignore_unknown'
}

class Song:
    def __init__(self, source, data):
        self.source = source
        self.title = data.get('title')
        self.url = data.get('url')

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')

def check_queue(ctx, guild_id):
    if queues[guild_id] != []:
        source = queues[guild_id].pop(0)
        ctx.voice_client.play(source, after=lambda x=None: check_queue(ctx, guild_id))
        asyncio.run_coroutine_threadsafe(ctx.send(f'Now playing: **{source.title}**'), bot.loop)

async def search(query):
    try:
        with YoutubeDL(YDL_OPTIONS) as ydl:
            if not query.startswith(('http://', 'https://')):
                info = ydl.extract_info(f"ytsearch:{query}", download=False)['entries'][0]
            else:
                info = ydl.extract_info(query, download=False)
            return info
    except Exception as e:
        print(f"Error searching: {e}")
        return None

@bot.command()
async def play(ctx, *, query):
    """Play music from YouTube"""
    voice_client = ctx.voice_client
    
    if not voice_client:
        if ctx.author.voice:
            await ctx.author.voice.channel.connect()
            voice_client = ctx.voice_client
        else:
            return await ctx.send("You need to be in a voice channel!")
    
    if 'youtube.com/watch?' not in query and not query.startswith('http'):
        await ctx.send(f'🔍 Searching: `{query}`')
    
    info = await search(query)
    url = info['formats'][0]['url']
    source = discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS)
    song = Song(source, info)
    
    guild_id = ctx.guild.id
    if guild_id not in queues:
        queues[guild_id] = []
    
    if voice_client.is_playing():
        queues[guild_id].append(song)
        await ctx.send(f'Added to queue: **{song.title}**')
    else:
        queues[guild_id].append(song)
        voice_client.play(song.source, after=lambda x=None: check_queue(ctx, guild_id))
        await ctx.send(f'Now playing: **{song.title}**')

@bot.command()
async def skip(ctx):
    """Skip current song"""
    voice_client = ctx.voice_client
    if voice_client and voice_client.is_playing():
        voice_client.stop()
        await ctx.send('⏭️ Skipped current song')
    else:
        await ctx.send('Nothing is playing!')

@bot.command()
async def stop(ctx):
    """Stop the bot and clear queue"""
    voice_client = ctx.voice_client
    if voice_client:
        if ctx.guild.id in queues:
            queues[ctx.guild.id] = []
        await voice_client.disconnect()
        await ctx.send('⏹️ Stopped the music')
    else:
        await ctx.send('I\'m not in a voice channel!')

@bot.command()
async def queue(ctx):
    """Show current queue"""
    guild_id = ctx.guild.id
    if guild_id in queues and len(queues[guild_id]) > 0:
        queue_list = '\n'.join([f'{i+1}. {song.title}' for i, song in enumerate(queues[guild_id])])
        await ctx.send(f'**Queue:**\n{queue_list}')
    else:
        await ctx.send('Queue is empty!')

@play.before_invoke
async def ensure_voice(ctx):  # Corrected definition
    """Ensure user is in a voice channel before playing music"""
    if not ctx.author.voice:
        await ctx.send("You need to be in a voice channel!")
        raise commands.CommandError("Author not in voice channel")

if __name__ == '__main__':
    bot.run(os.getenv('DISCORD_TOKEN'))