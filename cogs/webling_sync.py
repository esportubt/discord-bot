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
        
        # never synced
        self.last_sync = 1
        self.last_results = None

    async def cog_load(self):
        # self.sync_loop.start()
        pass
    
    async def cog_unload(self):
        self.sync_loop.stop()

    @commands.hybrid_group()
    async def sync(self, ctx: commands.Context) -> None:
        """Sync group"""
        await ctx.send("This is just a group. Please supply subcommand.")

    @sync.command(name="all")
    async def sync_all_members(self, ctx: commands.Context) -> None:
        """
        Removes role from everyone and re-add it to everyone eligible.
        """
        print(f"{ctx.author} called sync changes.")

        guild = ctx.message.guild
        
        # give bot time to make API calls
        await ctx.defer()

        role = guild.get_role(self.discord_member_role_id)

        if role is None:
            await ctx.send("Error: Role-ID not found")
            return

        current_role_users = role.members
        all_users = guild.members
        
        # get all eligible members
        eligible_members = await self._get_eligible_members()

        if eligible_members is None:
            await ctx.send("No eligible members.")
            return

        old : list[str] = []
        new : list[str] = []
        not_found : list[int] = []
        removed : list[str] = []
        forbidden : list[str] = []

        for member in eligible_members:
            # TODO: these properties should be envs
            member_id = str(member['properties']['Mitglieder ID'])
            
            try:
                user = self._get_user_by_member(member)
            except self.UserNotFound:
                # if that failes, add to not_found
                print(f"Discord user of member {member_id} not found.")
                not_found.append(member_id)
            else:   # user found

                # check if user already has role
                if user not in current_role_users:
                    # if not, try to add role
                    try:
                        await user.add_roles(role)
                        new.append(user.name)
                    except discord.errors.Forbidden:
                        # if that fails, add to forbidden
                        print(f"Not allowed to add role to user {user.name}")
                        forbidden.append(user.name)
                else:   #if user already has role
                    # keep track of not eligible users with role
                    current_role_users.remove(user)
                    # add to old members
                    old.append(user.name)

        # remove role from everyone not eligible
        for user in current_role_users:
            try:
                await user.remove_roles(role)
                removed.append(user.name)
            except discord.errors.Forbidden:
                # add to forbidden
                print(f"Not allowed to remove role from user {user.name}")
                forbidden.append(user.name)

        # set last sync time for sync loop
        self.last_sync = int(time.time())

        # sent sync report
        embed = discord.Embed(title="Sync All Report", color=0x009260)
        embed.add_field(name=f"Old Members ({len(old)})", value=f"{', '.join(list(map(str, old)))}")
        embed.add_field(name=f"New Members ({len(new)})", value=f"{', '.join(list(map(str, new)))}")
        embed.add_field(name=f"Removed Members ({len(current_role_users)})", value=f"{', '.join(list(map(str, removed)))}")

        if len(not_found) > 0:
            embed.add_field(name=f"Member IDs with unmatched discord references ({len(not_found)})", value=f"{', '.join(list(map(str, not_found)))}", inline=True)

        if len(forbidden) > 0:
            embed.add_field(name=f"Discord users that could not be modifie({len(forbidden)})", value=f"{', '.join(list(map(str, forbidden)))}", inline=True)

        await ctx.send(embed=embed)


    @sync.command(name="changes")
    async def sync_changes(self, ctx: commands.Context) -> None:
        """
        Syncs all changed members since last sync. 
        """
        print(f"{ctx.author} called sync changes.")
        # give bot time to make API calls
        await ctx.defer()
        results =  await self._sync_changes()

        embed = results.make_embed()

        await ctx.send(embed=embed)

    @tasks.loop(minutes=60)
    async def sync_loop(self):
        results = await self._sync_changes()
        self.last_results = results

    @sync.command(name="results")
    async def sync_results(self, ctx : commands.Context) -> None:
        """Prints the last sync changes results."""
        print(f"{ctx.author} called sync results.")

    
    @sync.command(name="on")
    async def sync_on(self, ctx : commands.Context) -> None:
        """Turns on the sync loop."""
        print(f"{ctx.author} called sync on.")
        try:
            self.sync_loop.start()
        except RuntimeError as e:
            await ctx.send(f"{e.args[0]}")
        else:
            print("Sync task has been launched successfully.")
            await ctx.send("Task has been launched successfully.")
    
    @sync.command(name="off")
    async def sync_off(self, ctx : commands.Context) -> None:
        """Shuts the sync loop down."""
        print(f"{ctx.author} called sync off.")
        try:
            self.sync_loop.stop()
        except Exception as e:
            await ctx.send(f"{e.args[0]}")
        else:
            print("Sync task is stopping gracefully.")
            await ctx.send("Task is stopping gracefully.")

    @sync.command(name="status")
    async def sync_status(self, ctx : commands.Context) -> None:
        """Returns the current status of the sync loop."""
        print(f"{ctx.author} called sync status.")
        is_running = self.sync_loop.is_running()
        has_failed = self.sync_loop.failed()

        embed = discord.Embed()
        if has_failed:
            embed.title = "Task has failed."
            embed.colour = 0xdb1c55
        elif is_running:
            embed.title = "Task is running."
            embed.colour = 0x009260
        else:
            embed.title = "Task has stopped."
            embed.colour = 0x333438
        
        await ctx.send(embed=embed)

    async def _sync_changes(self):
        """  
        Syncs changed members. 

        Webling API doesn't allow filtering on a fixed set of members, e.g. "/members/440,512?filter=...". 
        Therefore this requires manual checking whether the member has the correct membergroups and a Discord-ID. A positive check results in the bot granting them the member role, otherwise it is removed.

        This uses many seperate API calls to fetch discord ids from webling members. If many members have changed, use `sync all` instead.
        """
        print("Syncing changes")

        new = []
        removed = []
        not_found = []
        forbidden : list[str] = []

        # fetch current members of role
        guild : discord.Guild = self.bot.guild
        role = guild.get_role(self.discord_member_role_id)
        current_role_users = role.members

        # fetch changed members
        changed_member_ids = await self._get_changed_members()

        if changed_member_ids is None:
            return self.SyncChangesResults(new, removed)
        
        print(f"Fetched {len(changed_member_ids)} changed members")

        for member_id in changed_member_ids:
            member = await self._get_member_by_id(member_id)

            if member is None:
                print(f"Member {member_id} not found.")
                continue
            
            try:
                user = self._get_user_by_member(member)
            except self.UserNotFound:
                print(f"User {member_id} not found.")
                not_found.append(member_id)
                continue
            
            if self._check_eligibility_of_member(member):
                # user is eligible, try to add role

                # check if user already has role
                if user not in current_role_users:
                    # if not, try to add role
                    try:
                        await user.add_roles(role)
                    except discord.errors.Forbidden:
                        # if that fails, add to failed members
                        forbidden.append(user.name)
                    else:
                        new.append(member_id)
            else:
                # user is not eligible, try to remove role
                try:
                    await user.remove_roles(role)
                except discord.errors.Forbidden:
                    # if that fails, add to failed members
                    forbidden.append(user.name)
                else:
                    removed.append(member_id)

        # set last sync time
        self.last_sync = int(time.time())

        
        return self.SyncChangesResults(new, removed, not_found, forbidden)
        

    def _check_eligibility_of_member(self, member: object) -> bool:
        """ Checks if member is in at least one eligible membergroup. """
        membergroups = list(map(int, member['parents']))
        return bool([i for i in membergroups if i in self.valid_membergroups])

    def _get_user_by_member(self, member: object) -> discord.Member:
        """
        Fetch discord user of a given member.
        Tries to fetch by user id first, then by username. 
        """
        guild : discord.Guild = self.bot.guild
        user = None
        # try to fetch user by ID
        user_id = member['properties']['Discord-ID']
        if user_id:
            user_id = int(user_id)
            user = guild.get_member(user_id)
        if user is None:
            # if it fails, try to fetch by name
            user_name = member['properties']['Discord-Benutzername']
            if user_name:
                user_name = str(user_name)
                all_users = guild.members
                user = next((u for u in all_users if u.name == user_name), None)
        if user is None:
            raise self.UserNotFound()
        else:
            return user

    async def _get_eligible_members(self) -> list[object]:
        """
        This makes one big API call to Webling and prefilters for members that have the correct membergroups and a Discord-ID. Which is a lot faster than calling each member individually.
        """
        request = f"{self.api_url}/member?filter=$parents.$id IN {str(self.valid_membergroups)} AND (NOT `Discord-ID` IS EMPTY OR NOT `Discord-Benutzername` IS EMPTY)&format=full"
        response = requests.get(request, headers=self.api_header)

        if response.status_code != 200:
            # TODO: this should be a custom exception
            raise RuntimeError(f'Request failed with status code {response.status_code}')
        
        members = response.json()
        
        # check if members is iterable
        try:
            iter(members)
        except TypeError:
            return None

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
        request = self.api_url + "/changes/" + str(self.last_sync)

        response = requests.get(request, headers=self.api_header)

        if response.status_code != 200:
            raise RuntimeError(f'Request failed with status code {response.status_code}')
        else:
            data = response.json()
            return data
    
    async def _get_changed_members(self) -> list[int]:
        changes = await self._get_changes()
        try:
            changed_member_ids = changes['objects']['member']
        except TypeError:
            # no new members
            return None
        else:
            # cast to list of integers
            return list(map(int, changed_member_ids))

    class UserNotFound(Exception):
        """Raise when discord user could not be fetched"""

    class SyncChangesResults():
        def __init__(self, new : list[int], removed : list[int], not_found : list[int] = [], forbidden : list[str] = []):
            self.new = new
            self.removed = removed
            self.not_found = not_found
            self.forbidden = forbidden
            self.time = time.time()
        
        def make_embed(self):
            # sent sync report
            embed = discord.Embed(title="Sync Report", color=0x009260)
            embed.add_field(name=f"Last Sync: {time.ctime(self.time)}", inline=True)
            embed.add_field(name=f"New Member IDs ({len(self.new)})", value=f"{', '.join(list(map(str, self.new)))}")
            embed.add_field(name=f"Removed Member IDs ({len(self.removed)})", value=f"{', '.join(list(map(str, self.removed)))}")
            if len(self.not_found) > 0:
                embed.add_field(name=f"Member IDs with unmatched discord references ({len(self.not_found)})", value=f"{', '.join(list(map(str, self.not_found)))}", inline=True)
            
            if len(self.forbidden) > 0:
                embed.add_field(name=f"Discord users that could not be modified ({len(self.forbidden)})", value=f"{', '.join(list(map(str, self.forbidden)))}", inline=True)

            return embed

async def setup(bot):
    await bot.add_cog(WeblingSync(bot))

async def teardown(bot):
    print("Extension unloaded!")