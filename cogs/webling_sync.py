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
        apikey = str(os.getenv('WEBLING_API_KEY'))
        self.api_header = {'apikey':apikey}
        membergroup_id = int(os.getenv('WEBLING_MEMBERGROUP_ID'))
        new_membergroup_id = int(os.getenv('WEBLING_NEW_MEMBERGROUP_ID'))
        self.resigned_membergroup_id = int(os.getenv('WEBLING_RESIGNED_MEMBERGROUP_ID'))
        self.valid_membergroups = (membergroup_id, new_membergroup_id)
        self.discord_member_role_id = int(os.getenv('WEBLING_DISCORD_MEMBER_ROLE_ID'))
        
        
        self.last_sync = 1  # never synced


    """@tasks.loop(minutes=60)
    async def sync_members(self):
        
        Automatically syncs member role. 

        Webling API doesn't allow filtering on a fixed set of members, e.g. "/members/440,512?filter=...". 
        Therefore this requires manual checking whether the member has the correct membergroups and a Discord-ID. A positive check results in the bot granting them the member role, otherwise it is removed.
        
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
    """
        
    @commands.hybrid_group()
    async def sync(self, ctx: commands.Context) -> None:
        """Sync group"""
        await ctx.send("This is just a group. Please supply subcommand.")

    @sync.command(name="all")
    async def sync_all_members(self, ctx: commands.Context) -> None:
        """
        Removes role from everyone and re-add it to everyone eligible.
        """

        print("Syncing all members")
        
        # give bot time to make API calls
        await ctx.defer()

        role = ctx.message.guild.get_role(self.discord_member_role_id)

        if role is None:
            await ctx.send("Error: Role-ID not found")
            return

        # remove role from everyone
        # TODO: remove only from members who arent eligible
        current_role_users = role.members 
        
        # get all eligible members
        eligible_members = await self._get_eligible_members()
        
        old_members = []
        new_members = []
        failed_members = []
        for member in eligible_members:
            member_id = member['properties']['Mitglieder ID']
            user_id = int(member['properties']['Discord-ID'])

            try:
                user = ctx.message.guild.get_member(user_id)
            except discord.errors.NotFound:
                print(f"Member with Discord-ID {user_id} not found")
                failed_members.append(member_id)
            else:
                if user not in current_role_users:
                    try:
                        await user.add_roles(role)
                        new_members.append(member_id)
                    except discord.errors.Forbidden:
                        print(f"Not allowed to add role to user {user.name}")
                        failed_members.append(member_id)
                else:
                    current_role_users.remove(user)
                    old_members.append(member_id)

        # remove role from everyone not eligable
        for user in current_role_users:
            await user.remove_roles(role)

        embed = discord.Embed(title="Sync Report", color=0x009260)
        embed.add_field(name=f"Old Members {len(old_members)}", value="")
        embed.add_field(name=f"New Members {len(new_members)}", value="")
        embed.add_field(name=f"Removed Members {len(current_role_users)}", value="")
        if len(failed_members) > 0:
            embed.add_field(name=f"Failed Members", value=f"{','.join(failed_members)}", inline=True)

        await ctx.send(embed=embed)


    async def _get_eligible_members(self) -> list[object]:
        """
        This makes one big API call to Webling and prefilters for members that have the correct membergroups and a Discord-ID. Which is a lot faster than calling each member individually.
        """
        request = f"{self.api_url}/member?filter=$parents.$id IN {str(self.valid_membergroups)} AND NOT `Discord-ID` IS EMPTY&format=full"
        response = requests.get(request, headers=self.api_header)

        if response.status_code != 200:
            # TODO: this should be a custom exception
            raise RuntimeError(f'Request failed with status code {response.status_code}')
        
        members = response.json()
        
        # TODO: check if members is iterable

        return members
    
    async def _get_resigned_members(self) -> list[int]:
        """
        Gets Discord-IDs of members that have resigned.

        This makes one big API call to Webling and prefilters for members that have the correct membergroup and a Discord-ID. Which is a lot faster than calling each member individually.
        """
        request = f"{self.api_url}/member?filter=$parents.$id = {self.resigned_membergroup_id} AND NOT `Discord-ID` IS EMPTY&format=full"
        response = requests.get(request, headers=self.api_header)

        if response.status_code != 200:
            # TODO: this should be a custom exception
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