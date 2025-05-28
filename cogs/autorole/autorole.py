import discord
import json
import datetime
from discord.ext import commands, tasks

class Autorole(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.role : discord.Role = None
    
    async def cog_load(self):
        self.catch_missed_members.start()
    
    async def cog_unload(self):
        self.catch_missed_members.stop()

    @commands.hybrid_group()
    async def autorole(self, ctx: commands.Context) -> None:
        """Autorole group."""
        await ctx.send("This is just a group. Please supply subcommand.")

    @autorole.command(name="role")
    async def autorole_role(self, ctx: commands.Context, role: discord.Role) -> None:
        """Set which role to grant new members."""
        self._set_role(role)

        await ctx.send(f"Changed autorole to <@&{role.id}>.")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if not member.bot:  # exclude Bots
            role = self._get_role()
            await member.add_roles(role)

    @autorole.command(name="all")
    async def autorole_all(self, ctx) -> None:
        """Grants role to all members."""

        # give bot time to make API calls
        await ctx.defer()

        role = self._get_role()
        await self._grant_all_members()
        await ctx.send(f"Successfully granted all members <@&{role.id}>.")


    @tasks.loop(time=datetime.time(hour=3)) # schedule daily for 3am
    async def catch_missed_members(self):
        await self._grant_all_members()

    async def _grant_all_members(self):
        guild : discord.Guild = self.bot.guild
        members = guild.members
        role = self._get_role()

        for member in members:
            if not member.bot:  # exclude Bots
                if role not in member.roles:
                    await member.add_roles(role)

    def _set_role(self, role: discord.Role):
        # save for persistency
        data = {'role' : role.id}
        with open('cogs/autorole/data.json', 'w') as file:
            json.dump(data, file)
        
        # save to class for caching
        self.role = role
        
    def _get_role(self) -> discord.Role:
        # try to retrieve cached
        if self.role is not None:
            return self.role
        
        else: # else try to load from file
            with open('cogs/autorole/data.json', 'r') as file:
                data = json.load(file)
            
            role_id = int(data['role'])
            guild = self.bot.guild
            role = guild.get_role(role_id)

            if role is not None:
                return role
            else:
                raise self.RoleNotDefined()
                
    class RoleNotDefined(Exception):
        """Raise when role could not be retrieved."""

async def setup(bot):
    await bot.add_cog(Autorole(bot))

async def teardown(bot):
    print("Extension unloaded!")