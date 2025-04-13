import discord
from discord import app_commands
import random
import string
import aiosmtplib
from email.message import EmailMessage
from email_validator import validate_email, EmailNotValidError
import os

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = 1345073409461063791
ADMIN_ID = 903981607843684363
CHANNEL_ID = 1345074035054084218
ALLOWED_USER_ID = 903981607843684363

ROLE_IDS = {
    "1a": 1345089341671608423,
    "2a": 1345089443417030756,
    "3a": 1345089478913560696,
    "4a": 1345089516100259880,
    "5a": 1345089546664153220,
    "6a": 1345089575630012506,
    "7a": 1345089576754221117,
    "8a": 1345089647927361548,
    "1c": 1345089713651974264,
    "2c": 1345089746283794452,
    "3c": 1345089778911019039,
    "4c": 1345089810112708759,
    "1d": 1345089845948583986,
    "2d": 1345089880774017170,
    "3d": 1345089913397182617,
    "4d": 1345089949749215252
}

SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT"))
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

intents = discord.Intents.default()
intents.members = True
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

pending_verifications = {}

def generate_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

async def send_email(to_email, code):
    msg = EmailMessage()
    msg["From"] = EMAIL_USER
    msg["To"] = to_email
    msg["Subject"] = "Ověření účtu"
    msg.set_content(f"Tvůj ověřovací kód je: {code}. Pošli ho botovi do soukromých zpráv pro ověření tvé emailové adresy.")

    try:
        await aiosmtplib.send(msg, hostname=SMTP_SERVER, port=SMTP_PORT, username=EMAIL_USER, password=EMAIL_PASSWORD, use_tls=False, start_tls=True)
        return True
    except Exception as e:
        return False

def get_class_from_email(email):
    try:
        username = email.split('@')[0]
        year = int(username[:4])
        class_letter = username[4]
        current_year = 2025

        years_in_school = 8 if class_letter == "a" else 4
        class_number = (years_in_school - (year - current_year))
        if class_number < 1 or class_number > years_in_school:
            return None

        return ROLE_IDS.get(f"{class_number}{class_letter}", None)
    except Exception as e:
        return None

@bot.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    activity = discord.Game(name="AI učitel... skoro")
    await bot.change_presence(status=discord.Status.idle, activity=activity)
    print(f"Bot ready for use at {bot.user}")

@bot.event
async def on_member_join(member):
    try:
        await member.send("Vítej na serveru! Prosím pošli mi svůj školní email pro ověření.")
    except discord.Forbidden:
        print(f"Message not delivered to {member.name}")

@bot.event
async def on_message(message):
    if message.author == bot.user or not isinstance(message.channel, discord.DMChannel):
        return

    user_id = message.author.id
    user_input = message.content.strip()
    guild = bot.get_guild(GUILD_ID)

    try:
        email_info = validate_email(user_input, check_deliverability=True)
        email = email_info.normalized

        if not email.endswith("@ghb.cz") or len(email.split("@")[0]) < 5:
            await message.channel.send("❌ Neplatný email.")
            return

        role_id = get_class_from_email(email)
        if role_id is None:
            await message.channel.send("❌ Neplatný email.")
            return

        code = generate_code()
        pending_verifications[user_id] = {"email": email, "code": code}

        if await send_email(email, code):
            await message.channel.send(f"📩 Ověřovací kód byl odeslán na {email}. Zadej ho sem.")
        else:
            await message.channel.send("❌ Nepodařilo se odeslat email. Zkus to znovu.")
        return

    except EmailNotValidError:
        pass

    if user_id in pending_verifications and user_input.upper() == pending_verifications[user_id]["code"]:
        role_id = get_class_from_email(pending_verifications[user_id]["email"])
        role = guild.get_role(role_id)
        member = guild.get_member(user_id)

        if role and member:
            await member.add_roles(role)
            await message.channel.send("✅ Ověření proběhlo úspěšně.")
            del pending_verifications[user_id]
        else:
            await message.channel.send("❌ Nastala chyba. Pokud se chyba opakuje, prosím kontaktuj administrátora.")
    else:
        await message.channel.send("❌ Nesprávný kód.")

def is_admin(interaction: discord.Interaction):
    return interaction.user.id == ADMIN_ID

@tree.command(name="embed", description="Bot pošle embed.", guild=discord.Object(id=GUILD_ID))
async def send_embed(interaction: discord.Interaction, title: str, description: str, channel_id: str):
    if interaction.user.id != ALLOWED_USER_ID:
        await interaction.response.send_message("Tento příkaz může použít pouze administrátor.", ephemeral=True)
        return
    try:
        channel_id = int(channel_id)
    except ValueError:
        await interaction.response.send_message("Neplatné ID kanálu.", ephemeral=True)
        return
    channel = bot.get_channel(channel_id)
    if channel is None:
        return
    embed = discord.Embed(title=title, description=description, color=discord.Color.red())
    await channel.send(embed=embed)
    await interaction.response.send_message("Embed byl zaslán do kanálu.", ephemeral=True)

@tree.command(name="startnewyear", description="Každý rok něco nového.", guild=discord.Object(id=GUILD_ID))
@app_commands.check(is_admin)
async def start_new_year(interaction: discord.Interaction):
    if interaction.channel_id != CHANNEL_ID:
        await interaction.response.send_message("❌ Nastala chyba.", ephemeral=True)
        return

    guild = interaction.guild
    if not guild:
        await interaction.response.send_message("❌ Nastala chyba.", ephemeral=True)
        return

    await interaction.response.defer()

    moved_students = 0
    removed_students = 0

    for member in guild.members:
        for role in member.roles:
            role_name = next((key for key, value in ROLE_IDS.items() if value == role.id), None)
            if role_name:
                current_number = int(role_name[0])
                class_letter = role_name[1]

                if class_letter == "a" and current_number < 8:
                    new_role_name = f"{current_number + 1}{class_letter}"
                elif class_letter in ["c", "d"] and current_number < 4:
                    new_role_name = f"{current_number + 1}{class_letter}"
                else:
                    new_role_name = None

                if new_role_name:
                    new_role_id = ROLE_IDS.get(new_role_name)
                    if new_role_id:
                        await member.remove_roles(role)
                        await member.add_roles(guild.get_role(new_role_id))
                        moved_students += 1
                else:
                    await member.remove_roles(role)
                    await member.kick(reason="Dosáhl jsi nejvyššího ročníku.")
                    removed_students += 1

    await interaction.followup.send(f"✅ Posunuto {moved_students} studentů.\n❌ {removed_students} studentů ztratilo roli.", ephemeral=True)

bot.run(TOKEN)
