import discord
from discord.ext import commands
from discord import app_commands
import os
from dotenv import load_dotenv
import requests
import random
import string
from flask import Flask, render_template_string, request, redirect, url_for
import threading
from werkzeug.middleware.proxy_fix import ProxyFix

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = int(os.getenv('GUILD_ID'))
VERIFIED_ROLE_ID = int(os.getenv('VERIFIED_ROLE_ID'))
WEBHOOK_URL = os.getenv('LOG_WEBHOOK_URL')
VERIFICATION_SERVER_URL = os.getenv('VERIFICATION_SERVER_URL', 'http://localhost:5000')

# Initialize bot
intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# Storage for verification tokens
verification_tokens = {}

# Flask setup
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Verification</title>
    <style>
        body {
            font-family: 'Arial', sans-serif;
            background: #0f0c29;
            background: linear-gradient(to right, #0f0c29, #302b63, #24243e);
            color: white;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            overflow: hidden;
        }
        .container {
            background: rgba(0, 0, 0, 0.7);
            padding: 2rem;
            border-radius: 15px;
            box-shadow: 0 0 25px #9c27b0;
            text-align: center;
            width: 400px;
            border: 2px solid #9c27b0;
            animation: glow 2s infinite alternate;
        }
        @keyframes glow {
            from { box-shadow: 0 0 10px #9c27b0; }
            to { box-shadow: 0 0 30px #9c27b0; }
        }
        .profile-img {
            width: 100px;
            height: 100px;
            border-radius: 50%;
            margin: 0 auto 1rem;
            border: 3px solid #9c27b0;
            box-shadow: 0 0 15px #9c27b0;
        }
        .username {
            background: rgba(0, 0, 0, 0.5);
            padding: 1rem;
            border-radius: 8px;
            margin: 1rem 0;
            font-size: 1.2rem;
            animation: slide 3s infinite alternate;
        }
        @keyframes slide {
            0% { transform: translateX(-5px); }
            100% { transform: translateX(5px); }
        }
        .verify-btn {
            background: #9c27b0;
            color: white;
            border: none;
            padding: 0.8rem 2rem;
            font-size: 1rem;
            border-radius: 50px;
            cursor: pointer;
            transition: all 0.3s;
            margin-top: 1rem;
        }
        .verify-btn:hover {
            background: #7b1fa2;
            transform: scale(1.05);
            box-shadow: 0 0 15px #9c27b0;
        }
        .error {
            color: #ff5252;
            margin-top: 1rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <img src="{{ avatar_url }}" class="profile-img" alt="Profile">
        <h2>Discord Verification</h2>
        <p>Complete verification to access the server</p>
        
        <div class="username">{{ username }}</div>
        
        <form action="/verify" method="POST">
            <input type="hidden" name="token" value="{{ token }}">
            <button type="submit" class="verify-btn">VERIFY NOW</button>
        </form>
        
        {% if error %}
        <p class="error">{{ error }}</p>
        {% endif %}
    </div>
</body>
</html>
"""

SUCCESS_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Verified</title>
    <style>
        body {
            font-family: 'Arial', sans-serif;
            background: #0f0c29;
            background: linear-gradient(to right, #0f0c29, #302b63, #24243e);
            color: white;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
        }
        .success-box {
            background: rgba(0, 0, 0, 0.7);
            padding: 2rem;
            border-radius: 15px;
            text-align: center;
            width: 400px;
            border: 2px solid #4CAF50;
            box-shadow: 0 0 25px #4CAF50;
        }
        .checkmark {
            color: #4CAF50;
            font-size: 5rem;
            margin-bottom: 1rem;
        }
        .return-btn {
            background: #4CAF50;
            color: white;
            border: none;
            padding: 0.8rem 2rem;
            font-size: 1rem;
            border-radius: 50px;
            cursor: pointer;
            transition: all 0.3s;
            margin-top: 1rem;
            text-decoration: none;
            display: inline-block;
        }
        .return-btn:hover {
            background: #2E7D32;
            transform: scale(1.05);
        }
    </style>
</head>
<body>
    <div class="success-box">
        <div class="checkmark">✓</div>
        <h2>VERIFICATION COMPLETE!</h2>
        <p>You have been successfully verified.</p>
        <p>Your role will be assigned shortly.</p>
        <a href="https://discord.com" class="return-btn">RETURN TO DISCORD</a>
    </div>
</body>
</html>
"""

def get_real_ip():
    if request.headers.get('CF-Connecting-IP'):
        return request.headers['CF-Connecting-IP']
    elif request.headers.get('X-Forwarded-For'):
        return request.headers['X-Forwarded-For'].split(',')[0]
    return request.remote_addr

@app.route('/verify/<token>')
def verify_page(token):
    if token not in verification_tokens:
        return "Invalid token", 404
    
    user_data = verification_tokens[token]
    ip_address = get_real_ip()
    
    try:
        vpn_check = requests.get(f'http://ip-api.com/json/{ip_address}?fields=proxy,hosting').json()
        is_vpn = vpn_check.get('proxy', False) or vpn_check.get('hosting', False)
    except:
        is_vpn = False
    
    return render_template_string(HTML_TEMPLATE, 
                               username=user_data['username'],
                               avatar_url=user_data['avatar_url'],
                               token=token,
                               error="VPN detected! Disable it to verify." if is_vpn else None)

@app.route('/verify', methods=['POST'])
def verify_user():
    token = request.form.get('token')
    if token not in verification_tokens:
        return "Invalid token", 400
    
    user_data = verification_tokens[token]
    ip_address = get_real_ip()
    
    try:
        vpn_check = requests.get(f'http://ip-api.com/json/{ip_address}?fields=proxy,hosting').json()
        is_vpn = vpn_check.get('proxy', False) or vpn_check.get('hosting', False)
    except:
        is_vpn = False
    
    if is_vpn:
        return redirect(url_for('verify_page', token=token))
    
    del verification_tokens[token]
    
    webhook_data = {
        "embeds": [{
            "title": "✅ User Verified",
            "description": f"**Username:** {user_data['username']}\n**ID:** {user_data['user_id']}\n**IP:** `{ip_address}`",
            "color": 10181046,
            "thumbnail": {"url": user_data['avatar_url']},
            "timestamp": discord.utils.utcnow().isoformat()
        }]
    }
    
    try:
        requests.post(WEBHOOK_URL, json=webhook_data)
    except:
        pass
    
    bot.loop.create_task(assign_verified_role(user_data['user_id']))
    
    return render_template_string(SUCCESS_TEMPLATE)

def run_flask():
    app.run(host='0.0.0.0', port=5000)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')
    try:
        synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(f"Error syncing commands: {e}")

async def assign_verified_role(user_id):
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        return
    
    try:
        member = await guild.fetch_member(user_id)
        role = guild.get_role(VERIFIED_ROLE_ID)
        if member and role:
            await member.add_roles(role)
            print(f"Assigned role to {member.name}")
    except Exception as e:
        print(f"Error assigning role: {e}")

@bot.tree.command(name="verify", description="Start the verification process")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def verify(interaction: discord.Interaction):
    if any(role.id == VERIFIED_ROLE_ID for role in interaction.user.roles):
        await interaction.response.send_message("You're already verified!", ephemeral=True)
        return
    
    token = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
    verification_tokens[token] = {
        'user_id': interaction.user.id,
        'username': str(interaction.user),
        'avatar_url': interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url
    }
    
    verification_url = f"{VERIFICATION_SERVER_URL}/verify/{token}"
    
    embed = discord.Embed(
        title="🔒 VERIFICATION REQUIRED",
        description="Click the button below to complete verification",
        color=discord.Color.purple()
    )
    embed.add_field(
        name="Important",
        value="• VPNs are blocked\n• One verification per user\n• Takes less than 1 minute",
        inline=False
    )
    
    view = discord.ui.View()
    view.add_item(discord.ui.Button(
        label="START VERIFICATION", 
        url=verification_url, 
        style=discord.ButtonStyle.green,
        emoji="🔗"
    ))
    
    await interaction.response.send_message(embed=embed, view=view)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    bot.run(TOKEN)
