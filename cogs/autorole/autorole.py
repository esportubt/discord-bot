import discord
import json
from discord.ext import commands

class Autorole(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.role : discord.Role = None

    @commands.hybrid_group()
    async def autorole(self, ctx: commands.Context) -> None:
        """Autorole group"""
        await ctx.send("This is just a group. Please supply subcommand.")

    @autorole.command(name="setup")
    async def autorole_setup(self, ctx: commands.Context, role: discord.Role) -> None:
        """Set which role to give new users."""

        # save for persistency
        data = {'role' : role.id}
        with open('cogs/autorole/data.json', 'w') as file:
            json.dump(data, file)
        
        # save to class for caching
        self.role = role

        await ctx.send(f"Successfully changed autorole to {role.name}")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        # try to load from cache
        role = self.role

        # if not cached, load from file
        if role is None:
            with open('cogs/autorole/data.json', 'r') as file:
                data = json.load(file)
                role_id = int(data['role'])
                guild = self.bot.guilds[0] 
                role = guild.get_role(role_id)

                self.role = role

        await member.add_roles(role)

async def setup(bot):
    await bot.add_cog(Autorole(bot))

async def teardown(bot):
    print("Extension unloaded!")