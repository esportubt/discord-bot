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

    @commands.hybrid_command(name="syncall")
    async def sync_all(self, ctx: commands.Context) -> None:
        """Sync all members"""
        pass
    
    @commands.hybrid_command()
    async def list_members(self, ctx: commands.Context) -> None:
        # eligible_member_ids = await self._get_eligible_members()
        eligible_member_ids = [200229833475620864]
        print(f'got {len(eligible_member_ids)} eligible members')
        
        for memberid in eligible_member_ids:
            member = ctx.message.guild.get_member(memberid)
            if member is None:
                print(f"Member {memberid} not found")
                return
            role = ctx.message.guild.get_role(1347922504269828176)
            if role is None:
                print("Role not found")
                return
            await member.add_roles(role)
            print(f"Added role to {member.name}")
            print(self.bot.eligible_role_id)

    async def _get_eligible_members(self) -> list[int]:
        club_members = await self._get_club_members()
        print(f'got {len(club_members)} club members')
        eligible_members = []
        for member in club_members:
            print(f'checking member {member}')
            discord_id = await self._get_discord_id_of_member(member)
            if discord_id:
                eligible_members.append(discord_id)
                print(f'added id {discord_id}')
        return eligible_members

    async def _get_club_members(self) -> list[int]:
        request = WEBLING_API_URL + "/membergroup/" + WEBLING_MEMBERGROUP_ID
        response = requests.get(request, headers=WEBLING_API_HEADER)

        if response.status_code != 200:
            print(f'Request failed with status code {response.status_code}')
        else:
            data = response.json()
            return data['children']['member']
        
    @DeprecationWarning
    async def _get_discord_name_of_member(self, member_id) -> str:
        request = WEBLING_API_URL + "/member/" + str(member_id)
        response = requests.get(request, headers=WEBLING_API_HEADER)

        if response.status_code != 200:
            print(f'Request failed with status code {response.status_code}')
        else:
            data = response.json()
            return data['properties']['Discord-Benutzername']
    
    async def _get_discord_id_of_member(self, member_id) -> int:
        request = WEBLING_API_URL + "/member/" + str(member_id)
        response = requests.get(request, headers=WEBLING_API_HEADER)

        if response.status_code != 200:
            print(f'Request failed with status code {response.status_code}')
        else:
            data = response.json()
            return data['properties']['Discord-ID']
        
        

async def setup(bot):
    await bot.add_cog(WeblingSync(bot))

async def teardown(bot):
    print("Extension unloaded!")