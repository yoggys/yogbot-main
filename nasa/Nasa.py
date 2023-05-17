import asyncio
import random
from datetime import datetime
from os import getenv

import aiohttp
import discord
from discord.ext import commands
from discord.utils import format_dt

class ApiError(Exception):
    def __init__(self, message, status):            
        super().__init__(message)
        self.status = status

class ImageView(discord.ui.View):
    def __init__(self, embed: discord.Embed):
        self.embed = embed
        super().__init__(timeout=60, disable_on_timeout=True)
        
    @discord.ui.button(label="More info", style=discord.ButtonStyle.blurple)
    async def info_callback(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_message(embed=self.embed, ephemeral=True)
        
class Nasa(commands.Cog):
    
    def __init__(self, client):
        self.client: discord.Bot = client
        self.rate_limited: bool = False
        
        self.combinations_img = "https://cdn.discordapp.com/attachments/704387250351243425/1092897819410579647/nasa_cams.png"
        self.nasa_logo_img = "https://cdn.discordapp.com/attachments/704387250351243425/1083876119180222554/nasa-logo_1.png"
        
        self.NASA_SOLS_ENDPOINT = "https://api.nasa.gov/mars-photos/api/v1/manifests/{}"
        self.ENDPOINT = "https://api.nasa.gov/mars-photos/api/v1/rovers/{}/photos"
        self.MAX_SOL = {
            "Curiosity": 3795,
            "Opportunity": 5111,
            "Spirit": 2208
        }
        
    @commands.Cog.listener()
    async def on_ready(self):
        async with aiohttp.ClientSession() as cs:
            tasks = [self.get_max_sol(cs, rover) for rover in list(self.MAX_SOL.keys())]
            await asyncio.gather(*tasks)
    
    async def rate_limit(self):
        self.rate_limited = True
        await asyncio.sleep(180)
        self.rate_limited = False
            
    async def get_max_sol(self, cs: aiohttp.ClientSession, rover: str):
        async with cs.get(
            self.NASA_SOLS_ENDPOINT.format(rover.lower()), 
            params = { "api_key": getenv("NASA_API_KEY") }
        ) as r:
            if r.status == 200:
                data = await r.json()
                if max_sol := data.get("photo_manifest", {}).get("max_sol"):
                    self.MAX_SOL[rover] = max_sol
            
    async def handle_error(self, ctx: discord.ApplicationContext, e: Exception):
        if isinstance(e, ApiError):
            if e.status == 429:
                asyncio.ensure_future(self.rate_limit())
                msg = "We are being rate limited!"
            else:
                msg = "API returned status code `{}`".format(e.status)
        else:
            msg = "Something went wrong..."
        return await ctx.respond(f"❌ {msg}\n> Please try again later...", ephemeral=True)
        
    async def get_photos(self, cs: aiohttp.ClientSession, sol: int, rover: str, camera: str):
        async with cs.get(
            self.ENDPOINT.format(rover.lower()), 
            params = {
                "api_key": getenv("NASA_API_KEY"),
                "sol": sol,
                "camera": camera,
                "rover": rover
            }
        ) as r:
            if r.status != 200:
                raise ApiError("NASA API returned status code {}".format(r.status), r.status)
            r: dict = await r.json()
            photos = r.get("photos", [])
            if len(photos) == 0: return
            photo = random.choice(photos)
            return self.photo_data(photo)
        
    def embed_data(self, data: dict):
        image_embed = discord.Embed(color=int("C9614B", 16))
        image_embed.set_author(name="Here's a random photo from Mars!", icon_url=self.nasa_logo_img)
        image_embed.set_image(url=data.get("img_src"))
        
        data_embed = discord.Embed(color=int("C9614B", 16))
        for key in data:
            if key == "img_src": continue
            name = key.replace("_", " ").title()
            value = data.get(key)
            if "_date" in key and value:
                value = datetime.strptime(data.get(key), "%Y-%m-%d")
                value = format_dt(value, "D")
            elif key == "status":
                value = value.title()
            else:
                value =  value if value else "`N/A`"
            data_embed.add_field(name=name, value=value)
        return image_embed, data_embed
            
    def photo_data(self, data: dict):
        return {
            "img_src": data.get("img_src"),
            "rover": data.get("rover", {}).get("name"),
            "landing_date": data.get("rover", {}).get("landing_date"),
            "launch_date": data.get("rover", {}).get("launch_date"),
            "camera": data.get("camera", {}).get("name"),
            "photo_earth_date": data.get("earth_date"),
            "status": data.get("rover", {}).get("status"),
        }

    def validate_choice(self, rover: str, camera: str):
        if rover == "Curiosity":
            choices = ["FHAZ", "RHAZ", "MAST", "CHEMCAM", "MAHLI", "MARDI", "NAVCAM"]
        else:
            choices = ["FHAZ", "RHAZ", "NAVCAM", "PANCAM", "MINITES"]
        return camera in choices
    
    @commands.slash_command(description="Get a random photo from Mars!")
    @commands.bot_has_permissions(send_messages=True)
    async def nasa(
        self, ctx: discord.ApplicationContext,
        rover: discord.Option(
            str, choices = ["Curiosity", "Opportunity", "Spirit"],
            description = "The rover to get the photo from."
        ),
        camera: discord.Option(
            str, description = "The camera to get the photo from.", 
            choices = ["FHAZ", "RHAZ", "MAST", "CHEMCAM", "MAHLI", "MARDI", "NAVCAM", "PANCAM", "MINITES"]
        ),
        sol: discord.Option(int, description = "The sol to get the photo from.")
    ):  
        if self.rate_limited: 
            return await ctx.respond("❌ We are being rate limited!\n> Please try again later...", 
                ephemeral=True)
        
        await ctx.defer()
        valid_combination = self.validate_choice(rover, camera)
        if not valid_combination:
            combinations_embed = discord.Embed(color=int("C9614B", 16))
            combinations_embed.set_image(url=self.combinations_img)
            return await ctx.respond("❌ Please check out the possible rover and camera combinations!", 
                embed=combinations_embed, ephemeral=True)
        
        if sol > self.MAX_SOL[rover] or sol < 0:
            return await ctx.respond("❌ Please enter a valid sol number for `{}`! (0-{})".format(
                self.MAX_SOL[rover]), ephemeral=True)
            
        async with aiohttp.ClientSession() as cs:
            try: 
                photo_data = await self.get_photos(cs, sol, rover, camera)
                if not photo_data:
                     return await ctx.respond("❌ No photos found for `{}` on sol `{}` with camera `{}`!".format(
                    rover, sol, camera), ephemeral=True)
                image_embed, data_embed = self.embed_data(photo_data)
                view = ImageView(data_embed)
                message = await ctx.respond(embed=image_embed, view=view)
                if view.message is None:
                    view.message = message
            except Exception as e:
                await self.handle_error(ctx, e)
            
def setup(client):
    client.add_cog(Nasa(client))
