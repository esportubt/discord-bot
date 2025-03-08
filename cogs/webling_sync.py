import os
import requests
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

# load token from .env
load_dotenv(dotenv_path='../.env')

WEBLING_BASE_DOMAIN = str(os.getenv('WEBLING_BASE_DOMAIN'))
WEBLING_API_KEY = os.getenv('WEBLING_API_KEY')
WEBLING_API_URL = "https://" + WEBLING_BASE_DOMAIN + ".webling.ch/api/1"
WEBLING_API_HEADER = {'apikey':WEBLING_API_KEY}
WEBLING_MEMBERGROUP_ID = os.getenv('WEBLING_MEMBERGROUP_ID')

class WeblingSync(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @tasks.loop(minutes=60)
    async def sync_members(self):
        pass

    @commands.hybrid_command()
    async def sync_all_members(self, ctx: commands.Context) -> None:
        
        # give bot time to make API calls
        await ctx.defer()
        eligible_discord_ids = await self._get_eligible_members()
        print(eligible_discord_ids)

        if len(eligible_discord_ids) == 0:
            await ctx.send("No eligible members found", ephemeral=True)
            return
        
        for member_id in eligible_discord_ids:
            member = ctx.message.guild.get_member(member_id)
            if member is None:
                print(f"Member {member_id} not found")
                break
            role = ctx.message.guild.get_role(self.bot.eligible_role_id)
            if role is None:
                print("Role not found")
                break
            try:
                await member.add_roles(role)
            except discord.errors.Forbidden as e:
                print(f"Not allowed to add role to member {member.name}")
        
        await ctx.send(f"Synced {len(eligible_discord_ids)} members", ephemeral=True)

    async def _get_eligible_members(self) -> list[int]:
        request = WEBLING_API_URL + "/member?filter=$parents.$id = 100 AND NOT `Discord-ID` IS EMPTY&format=full"
        response = requests.get(request, headers=WEBLING_API_HEADER)

        if response.status_code != 200:
            raise RuntimeError(f'Request failed with status code {response.status_code}')
        
        data = response.json()
        
        # TODO: check if data is iterable

        discord_ids = []
        for member in data:
            discord_id = int(member['properties']['Discord-ID'])
            discord_ids.append(discord_id)
        return discord_ids

    async def _get_club_members(self) -> list[int]:
        request = WEBLING_API_URL + "/membergroup/" + WEBLING_MEMBERGROUP_ID
        response = requests.get(request, headers=WEBLING_API_HEADER)

        if response.status_code != 200:
            print(f'Request failed with status code {response.status_code}')
        else:
            data = response.json()
            return data['children']['member']
        
    async def _get_members_with_discord_id(self) -> list[int]:
        request = WEBLING_API_URL + "/member?filter=$parents.$id = 100 AND NOT `Discord-ID` IS EMPTY"
        response = requests.get(request, headers=WEBLING_API_HEADER)
        
        if response.status_code != 200:
            raise RuntimeError(f'Request failed with status code {response.status_code}')
        else:
            data = response.json()
            return data['objects']
    
    async def _get_discord_id_of_member(self, member_id) -> int:
        request = WEBLING_API_URL + "/member/" + str(member_id)
        response = requests.get(request, headers=WEBLING_API_HEADER)

        if response.status_code != 200:
            raise RuntimeError(f'Request failed with status code {response.status_code}')
        else:
            data = response.json()
            return data['properties']['Discord-ID']
            
        
        

async def setup(bot):
    await bot.add_cog(WeblingSync(bot))

async def teardown(bot):
    print("Extension unloaded!")