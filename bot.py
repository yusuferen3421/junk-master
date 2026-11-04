import discord
from discord.ext import commands
import sqlite3
import random
import uuid
import os

# --- VERİTABANI KURULUMU ---
db_file = "junkmaster_v2.db"
conn = sqlite3.connect(db_file)
cursor = conn.cursor()

# 1. Oyuncu Profilleri Tablosu
cursor.execute('''
CREATE TABLE IF NOT EXISTS players (
    user_id INTEGER PRIMARY KEY,
    money INTEGER DEFAULT 150,
    workshop_level INTEGER DEFAULT 1,
    home_level INTEGER DEFAULT 0,
    scavenge_tier INTEGER DEFAULT 1
)
''')

# 2. Eşya Veritabanı
cursor.execute('''
CREATE TABLE IF NOT EXISTS items (
    item_id TEXT PRIMARY KEY,
    name TEXT,
    tier INTEGER,
    sell_price INTEGER,
    icon TEXT
)
''')

# Başlangıç Eşyalarını Ekle
def init_items():
    cursor.execute("SELECT count(*) FROM items")
    if cursor.fetchone()[0] == 0:
        starter_items = [
            ("RUSTY_CABLE", "Paslı Kablo", 1, 15, "🧶"),
            ("BROKEN_TOASTER", "Bozuk Ekmek Kızartma Makinesi", 1, 25, "🍞"),
            ("OLD_CPU", "Eski İşlemci", 2, 75, "🖥️"),
            ("RETRO_RADIO", "Antika Radyo", 2, 120, "📻"),
            ("VINTAGE_CONSOLE", "Nostaljik Konsol", 3, 300, "🕹️"),
            ("RARE_TUBE_AMP", "Nadir Lamba Amplifikatör", 4, 750, "🔊"),
            ("ALIEN_ARTIFACT", "Uzaylı Eseri", 4, 2000, "👽")
        ]
        cursor.executemany("INSERT OR IGNORE INTO items VALUES (?, ?, ?, ?, ?)", starter_items)
        conn.commit()

init_items()

# 3. Envanter Tablosu (Benzersiz UUID ile)
cursor.execute('''
CREATE TABLE IF NOT EXISTS inventory (
    uuid TEXT PRIMARY KEY,
    user_id INTEGER,
    item_id TEXT,
    found_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (item_id) REFERENCES items(item_id)
)
''')

# 4. Sunucu Ayarları Tablosu (Prefix için)
cursor.execute('''
CREATE TABLE IF NOT EXISTS guild_settings (
    guild_id INTEGER PRIMARY KEY,
    prefix TEXT DEFAULT '!'
)
''')
conn.commit()

# --- YARDIMCI FONKSİYONLAR ---

def get_prefix(bot, message):
    if not message.guild:
        return "!"
    guild_id = message.guild.id
    cursor.execute("SELECT prefix FROM guild_settings WHERE guild_id = ?", (guild_id,))
    result = cursor.fetchone()
    if result:
        return result[0]
    return "!"

def check_player(user_id):
    cursor.execute("SELECT * FROM players WHERE user_id = ?", (user_id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO players (user_id, money, workshop_level, home_level, scavenge_tier) VALUES (?, 150, 1, 0, 1)", (user_id,))
        conn.commit()

def get_scavenge_chances(tier):
    chances = {
        1: {"tier1": 70, "tier2": 25, "tier3": 5, "tier4": 0},
        2: {"tier1": 40, "tier2": 45, "tier3": 14, "tier4": 1},
        3: {"tier1": 15, "tier2": 35, "tier3": 40, "tier4": 10},
        4: {"tier1": 0, "tier2": 10, "tier3": 50, "tier4": 40}
    }
    return chances.get(tier, chances[1])

# --- EMBED FORMATI ---

class JunkEmbed(discord.Embed):
    def __init__(self, title_text, color=discord.Color.green(), **kwargs):
        super().__init__(title="", color=color, **kwargs)
        self.description = f"## {title_text}"

    def add_field(self, name, value, inline=False):
        super().add_field(name=f"**{name}**", value=f"**{value}**", inline=inline)

    def set_header(self, user_name, user_avatar_url):
        self.set_author(name=user_name, icon_url=user_avatar_url)

# --- BOT BAŞLATMA ---
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=get_prefix, intents=intents)
bot.remove_command('help')

@bot.event
async def on_ready():
    print(f'⚙️ JunkMaster (v2.0) Atölyesi Açıldı! [{bot.user.name}]')

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        embed = JunkEmbed("⏳ Biraz Dinlen Usta!", color=discord.Color.gold())
        embed.add_field(name="Kalan Süre", value=f"{round(error.retry_after, 1)} Saniye")
        await ctx.send(embed=embed)
    else:
        raise error

# --- KOMUTLAR ---

# 1. Yardım Komutu (!yardım)
@bot.command(name="yardım", aliases=["komutlar", "help"])
async def yardim(ctx):
    check_player(ctx.author.id)
    prefix = get_prefix(bot, ctx.message)
    
    embed = JunkEmbed("🤖 Junk Master - Komut Rehberi", color=discord.Color.teal())
    embed.set_header(user_name=ctx.author.display_name, user_avatar_url=ctx.author.display_avatar.url)
    
    embed.add_field(name="🔍 Hurda Arama", value=f"Hurdalığa dalıp rastgele parça bulursun.\nKullanım: `{prefix}hurda` veya `{prefix}ara`")
    embed.add_field(name="📦 Envanter", value=f"Çantandaki eşyaları ve seri numaralarını görürsün.\nKullanım: `{prefix}envanter` veya `{prefix}çantam`")
    embed.add_field(name="🛠️ Market & Dükkan", value=f"Bakiyeni ve yükseltme fiyatlarını incelersin.\nKullanım: `{prefix}market` veya `{prefix}dükkan`")
    embed.add_field(name="💰 Eşya Satma", value=f"Envanterindeki eşyayı seri nosuyla satarsın.\nKullanım: `{prefix}sat [SeriNo]`")
    embed.add_field(name="🏢 Atölye Yükseltme", value=f"Dedektör gücünü artırıp daha iyi eşya bulursun.\nKullanım: `{prefix}yükselt atölye`")
    embed.add_field(name="🏡 Ev Yatırımı", value=f"Ev seviyeni geliştirirsin (Sergi için).\nKullanım: `{prefix}yükselt ev`")
    embed.add_field(name="👨‍🔧 Profil / Cüzdan", value=f"Bakiye ve atölye durumunu görürsün.\nKullanım: `{prefix}profil` veya `{prefix}bakiye`")
    embed.add_field(name="⚙️ Komut İşaretini Değiştir", value=f"Sunucu prefix'ini değiştirir (Yöneticiler).\nKullanım: `{prefix}isaretdegis ?`")
    
    embed.set_footer(text="Junk Master atölyesi her zaman emrinde usta!")
    await ctx.send(embed=embed)

# 2. Prefix Değiştirme (!isaretdegis)
@bot.command(name="isaretdegis", aliases=["prefix"])
@commands.has_permissions(administrator=True)
async def change_prefix(ctx, yeni_isaret: str):
    check_player(ctx.author.id)
    if len(yeni_isaret) > 1:
        await ctx.send("❌ İşaret sadece tek bir karakter olabilir! (örn: `?`)")
        return
    
    cursor.execute("INSERT OR REPLACE INTO guild_settings (guild_id, prefix) VALUES (?, ?)", (ctx.guild.id, yeni_isaret))
    conn.commit()
    
    embed = JunkEmbed("✅ Komut İşareti Değiştirildi!", color=discord.Color.blue())
    embed.add_field(name="Yeni İşaret", value=f"`{yeni_isaret}`")
    embed.add_field(name="Örnek Kullanım", value=f"{yeni_isaret}hurda")
    await ctx.send(embed=embed)

# 3. Hurda Bul (!hurda)
@bot.command(name="hurda", aliases=["ara", "scavenge"])
@commands.cooldown(1, 15, commands.BucketType.user)
async def scavenge(ctx):
    check_player(ctx.author.id)
    
    cursor.execute("SELECT scavenge_tier FROM players WHERE user_id = ?", (ctx.author.id,))
    player_tier = cursor.fetchone()[0]
    
    chances = get_scavenge_chances(player_tier)
    
    roll = random.randint(1, 100)
    selected_tier = 1
    cumulative = 0
    for tier, chance in chances.items():
        cumulative += chance
        if roll <= cumulative:
            selected_tier = int(tier.replace("tier", ""))
            break
            
    cursor.execute("SELECT item_id, name, sell_price, icon FROM items WHERE tier = ? ORDER BY RANDOM() LIMIT 1", (selected_tier,))
    item_data = cursor.fetchone()
    item_id, name, price, icon = item_data
    
    item_uuid = str(uuid.uuid4())
    
    cursor.execute("INSERT INTO inventory (uuid, user_id, item_id) VALUES (?, ?, ?)", (item_uuid, ctx.author.id, item_id))
    conn.commit()
    
    embed = JunkEmbed("🔍 Hurdalıkta Yeni Bir Şey Bulundu!", color=discord.Color.orange())
    embed.set_header(user_name=ctx.author.display_name, user_avatar_url=ctx.author.display_avatar.url)
    embed.add_field(name="Bulunan Eşya", value=f"{icon} {name}")
    embed.add_field(name="Eşya Değeri", value=f"{price} 💰")
    embed.add_field(name="Benzersiz Seri No", value=f"`{item_uuid[:8]}` (Satmak için: `!sat {item_uuid[:4]}`)")
    embed.set_footer(text="Marketten daha iyi dedektör alarak daha değerli parçalar bulabilirsin!")
    await ctx.send(embed=embed)

# 4. Envanter (!envanter)
@bot.command(name="envanter", aliases=["çantam", "inventory"])
async def inventory(ctx):
    check_player(ctx.author.id)
    
    cursor.execute('''
        SELECT i.uuid, it.name, it.sell_price, it.icon, i.found_at
        FROM inventory i
        JOIN items it ON i.item_id = it.item_id
        WHERE i.user_id = ?
        ORDER BY i.found_at DESC
    ''', (ctx.author.id,))
    items = cursor.fetchall()
    
    if not items:
        embed = JunkEmbed("📦 Hurdalığında Henüz Hiçbir Şey Yok!", color=discord.Color.red())
        await ctx.send(embed=embed)
        return

    embed = JunkEmbed(f"👨‍🔧 {ctx.author.display_name} - Atölye Envanteri")
    
    for i, item in enumerate(items):
        u_id, name, price, icon, date = item
        embed.add_field(
            name=f"{icon} {name} | Değer: {price} 💰",
            value=f"Seri No: `{u_id[:8]}`"
        )
        if i >= 9: break
        
    if len(items) > 10:
        embed.set_footer(text=f"Ve {len(items) - 10} eşya daha...")
    
    await ctx.send(embed=embed)

# 5. Market (!market)
@bot.command(name="market", aliases=["dükkan", "shop"])
async def market(ctx):
    check_player(ctx.author.id)
    
    cursor.execute("SELECT money, workshop_level, home_level, scavenge_tier FROM players WHERE user_id = ?", (ctx.author.id,))
    stats = cursor.fetchone()
    money, w_level, h_level, s_tier = stats
    
    next_workshop_cost = (w_level + 1) * 1500
    next_home_cost = (h_level + 1) * 5000
    
    embed = JunkEmbed("🛠️ Junk Master Pazarı", color=discord.Color.gold())
    embed.set_header(user_name=ctx.author.display_name, user_avatar_url=ctx.author.display_avatar.url)
    embed.add_field(name="Bakiye", value=f"{money} 💰")
    embed.add_field(name="Aktif Dedektör Seviyesi", value=f"Seviye {s_tier} 📡")
    embed.add_field(name="Eşya Sat", value="`!sat [Seri No]`")
    embed.add_field(name="Atölyeyi Geliştir", value=f"Fiyat: `{next_workshop_cost} 💰` | Komut: `!yükselt atölye`")
    embed.add_field(name="Eve Yatırım Yap", value=f"Fiyat: `{next_home_cost} 💰` | Komut: `!yükselt ev`")
    
    await ctx.send(embed=embed)

# 6. Eşya Satma (!sat)
@bot.command(name="sat", aliases=["sell"])
async def sell_item(ctx, item_uuid_full: str):
    check_player(ctx.author.id)
    
    cursor.execute('''
        SELECT i.uuid, it.sell_price, it.name, it.icon
        FROM inventory i
        JOIN items it ON i.item_id = it.item_id
        WHERE i.uuid LIKE ? AND i.user_id = ?
    ''', (f"{item_uuid_full}%", ctx.author.id))
    item_data = cursor.fetchone()
    
    if not item_data:
        embed = JunkEmbed("❌ Bu Seri Numarasına Ait Eşya Envanterinde Bulunamadı!", color=discord.Color.red())
        await ctx.send(embed=embed)
        return

    u_id, price, name, icon = item_data
    
    cursor.execute("UPDATE players SET money = money + ? WHERE user_id = ?", (price, ctx.author.id))
    cursor.execute("DELETE FROM inventory WHERE uuid = ?", (u_id,))
    conn.commit()
    
    embed = JunkEmbed("💰 Eşya Başarıyla Satıldı!", color=discord.Color.green())
    embed.add_field(name="Satılan Eşya", value=f"{icon} {name}")
    embed.add_field(name="Kazanç", value=f"+{price} 💰")
    await ctx.send(embed=embed)

# 7. Yükseltme Komutları (!yükselt)
@bot.group(name="yükselt", aliases=["upgrade"])
async def upgrade(ctx):
    check_player(ctx.author.id)
    if ctx.invoked_subcommand is None:
        await ctx.send("❌ Neyi yükseltmek istiyorsun? `!yükselt atölye` veya `!yükselt ev` kullan.")

@upgrade.command(name="atölye", aliases=["workshop"])
async def upgrade_workshop(ctx):
    check_player(ctx.author.id)
    
    cursor.execute("SELECT money, workshop_level, scavenge_tier FROM players WHERE user_id = ?", (ctx.author.id,))
    money, w_level, s_tier = cursor.fetchone()
    cost = (w_level + 1) * 1500
    
    if money < cost:
        embed = JunkEmbed("❌ Yetersiz Bakiye!", color=discord.Color.red())
        embed.add_field(name="Gerekli Tutar", value=f"{cost} 💰")
        await ctx.send(embed=embed)
        return

    new_w_level = w_level + 1
    new_s_tier = s_tier
    if new_w_level % 2 == 0 and new_s_tier < 4:
        new_s_tier += 1

    cursor.execute("UPDATE players SET money = money - ?, workshop_level = ?, scavenge_tier = ? WHERE user_id = ?", (cost, new_w_level, new_s_tier, ctx.author.id))
    conn.commit()
    
    embed = JunkEmbed("🏢 Atölye Yükseltildi!", color=discord.Color.green())
    embed.add_field(name="Yeni Seviye", value=f"{new_w_level} 🏢")
    embed.add_field(name="Dedektör Gücü", value=f"Seviye {new_s_tier} 📡")
    await ctx.send(embed=embed)

@upgrade.command(name="ev", aliases=["home"])
async def upgrade_home(ctx):
    check_player(ctx.author.id)
    
    cursor.execute("SELECT money, home_level FROM players WHERE user_id = ?", (ctx.author.id,))
    money, h_level = cursor.fetchone()
    cost = (h_level + 1) * 5000
    
    if money < cost:
        embed = JunkEmbed("❌ Yetersiz Bakiye!", color=discord.Color.red())
        embed.add_field(name="Gerekli Tutar", value=f"{cost} 💰")
        await ctx.send(embed=embed)
        return

    new_h_level = h_level + 1
    cursor.execute("UPDATE players SET money = money - ?, home_level = ? WHERE user_id = ?", (cost, new_h_level, ctx.author.id))
    conn.commit()
    
    embed = JunkEmbed("🏡 Evin Geliştirildi!", color=discord.Color.green())
    embed.add_field(name="Yeni Ev Seviyesi", value=f"{new_h_level} 🏡")
    await ctx.send(embed=embed)

# 8. Profil (!profil)
@bot.command(name="profil", aliases=["cüzdan", "bakiye"])
async def profil(ctx.author_id_param=None, *args, **kwargs):
    ctx = args[0] if args else ctx_author_id_param
    check_player(ctx.author.id)
    
    cursor.execute("SELECT money, workshop_level, home_level, scavenge_tier FROM players WHERE user_id = ?", (ctx.author.id,))
    money, w_level, h_level, s_tier = cursor.fetchone()
    
    home_titles = {0: "Evsiz Usta", 1: "Gecekondu Atölyesi", 2: "Mütevazı Garaj", 3: "Zengin Koleksiyoner"}
    title = home_titles.get(h_level, "Hurdalık Kralı")
    
    embed = JunkEmbed(f"👨‍🔧 {ctx.author.display_name} - {title}", color=discord.Color.blue())
    embed.set_header(user_name=ctx.author.display_name, user_avatar_url=ctx.author.display_avatar.url)
    embed.add_field(name="Bakiye", value=f"{money} 💰")
    embed.add_field(name="Atölye Seviyesi", value=f"{w_level} 🏢")
    embed.add_field(name="Aktif Dedektör Gücü", value=f"Seviye {s_tier} 📡")
    embed.add_field(name="Ev Seviyesi", value=f"{h_level} 🏡")
    
    await ctx.send(embed=embed)

# --- BOT TOKEN (Railway Variables'dan Okur) ---
TOKEN = os.environ.get("DISCORD_TOKEN")

if __name__ == "__main__":
    if not TOKEN:
        print("❌ HATA: DISCORD_TOKEN bulunamadı! Railway panelindeki Variables kısmına tokenini eklemelisin.")
    else:
        bot.run(TOKEN)
