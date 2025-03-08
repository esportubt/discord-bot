import os
import time
import requests
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv


class WeblingSync(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # load token from .env
        load_dotenv(dotenv_path='../.env')
        base_domain = str(os.getenv('WEBLING_BASE_DOMAIN'))
        self.api_url = "https://" + base_domain + ".webling.ch/api/1"
        apikey = os.getenv('WEBLING_API_KEY')
        self.api_header = {'apikey':apikey}
        membergroup_id = int(os.getenv('WEBLING_MEMBERGROUP_ID'))
        new_membergroup_id = int(os.getenv('WEBLING_NEW_MEMBERGROUP_ID'))

        self.valid_membergroups = (membergroup_id, new_membergroup_id)
        member_discord_role_id = int(os.getenv('WEBLING_MEMBER_DISCORD_ROLE_ID'))
        self.member_role = self.bot.guild.get_role(member_discord_role_id)
        
        self.last_sync = 1  # never synced

    @tasks.loop(minutes=60)
    async def sync_members(self):
        """
        Automatically syncs member role. 

        Webling API doesn't allow filtering on a fixed set of members, e.g. "/members/440,512?filter=...". 
        Therefore this requires manual checking whether the member has the correct membergroups and a Discord-ID. A positive check results in the bot granting them the member role, otherwise it is removed.
        """
        changed_member_ids = await self._get_changed_members()

        if len(changed_member_ids) == 0:
            print("No changes")
            return

        for member_id in changed_member_ids:
            member = self._get_member_by_id(member_id)

            if member:
                membergroups = list(map(int, member['parents']))
                has_disord_id = member['properties']['Discord-ID'] is not None

                if membergroups in self.valid_membergroups and has_disord_id:
                    print(f"Adding member role to {member_id}")
                    await member.add_roles(self.member_role)
                else:
                    await member.remove_roles(self.member_role)
                    print(f"Removing member role from {member_id}")
        self.last_sync = time.time()
    
                

    @commands.hybrid_command()
    async def sync_all_members(self, ctx: commands.Context) -> None:
        
        # give bot time to make API calls
        await ctx.defer()
        
        
        eligible_discord_ids = await self._get_eligible_members()


        
        await ctx.send(f"Synced {len(eligible_discord_ids)} members", ephemeral=True)

    async def _get_eligible_members(self) -> list[int]:
        request = self.api_url + "/member?filter=$parents.$id = 100 AND NOT `Discord-ID` IS EMPTY&format=full"
        response = requests.get(request, headers=self.api_header)

        if response.status_code != 200:
            raise RuntimeError(f'Request failed with status code {response.status_code}')
        
        data = response.json()
        
        # TODO: check if data is iterable

        discord_ids = []
        for member in data:
            discord_id = int(member['properties']['Discord-ID'])
            discord_ids.append(discord_id)
        return discord_ids
    
    async def _get_member_by_id(self, member_id) -> object:
        request = self.api_url + "/member/" + str(member_id)
        response = requests.get(request, headers=self.api_header)

        if response.status_code != 200:
            raise RuntimeError(f'Request failed with status code {response.status_code}')
        else:
            data = response.json()
            return data

    async def _get_club_members(self) -> list[int]:
        request = self.api_url + "/membergroup/" + self.membergroup_id
        response = requests.get(request, headers=self.api_header)

        if response.status_code != 200:
            print(f'Request failed with status code {response.status_code}')
        else:
            data = response.json()
            return data['children']['member']
        
    async def _get_discord_id_of_member(self, member_id) -> int:
        request = self.api_url + "/member/" + str(member_id)
        response = requests.get(request, headers=self.api_header)

        if response.status_code != 200:
            raise RuntimeError(f'Request failed with status code {response.status_code}')
        else:
            data = response.json()
            return data['properties']['Discord-ID']
            
    async def _get_changes(self) -> object:
        request = self.api_url + "/changes/" + self.last_sync

        response = requests.get(request, headers=self.api_header)

        if response.status_code != 200:
            raise RuntimeError(f'Request failed with status code {response.status_code}')
        else:
            data = response.json()
            return data
    
    async def _get_changed_members(self) -> list[int]:
        changes = await self._get_changes()
        
        changed_member_ids = changes['objects']['members']

        # cast to list of integers
        return list(map(int, changed_member_ids))



async def setup(bot):
    await bot.add_cog(WeblingSync(bot))

async def teardown(bot):
    print("Extension unloaded!")