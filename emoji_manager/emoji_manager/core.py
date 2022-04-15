import json
from dataclasses import dataclass, asdict
from datetime import datetime
from imghdr import what
from logging import getLogger
from pathlib import Path
from textwrap import dedent
from typing import Optional

import discord
from discord.ext.commands import command, Cog, Context

from . import messaging

logger = getLogger(__name__)


@dataclass
class EmojiData:
    id: int
    name: str
    path: Path  # the path of original image file.
    created_at: datetime


class ImageToEmojiCog(Cog):
    """
    Helps you manage custom emojis easily.
    Registers emojis in specified path, specify and return emoji instance from path(or simply by name).

    Emoji names can differ from image.stem, emoji.user is usually None without API call.
    Therefore, you should manage custom emoji with local json file to specify emoji you exactly want.
    """
    DEFAULT_IMAGES_PATH = Path() / "images"

    def __init__(self, bot,
                 path_of_emoji_stats_json: Path = Path() / "emoji_stats.json"):
        super().__init__()
        self.bot: discord.ext.commands.Bot = bot

        self.emoji_data_list: list[EmojiData] = []
        self.emojis_json: Path = path_of_emoji_stats_json
        self._load_json()

    def _load_json(self):
        if self.emojis_json.exists():
            with self.emojis_json.open(mode="r") as f:
                self.emoji_data_list = [EmojiData(**data) for data in json.load(f)]
        else:
            return []

    def get_my_emoji(self, *, name: str = None, path: Path = None) -> Optional[discord.Emoji]:
        """
        Requires name or path of origin image file for the emoji.

        Parameters
        ----------
        name : str
            Name of emoji.
        path : Path
            Path of image file which is used as origin of emoji.
        """
        if name is path is None:
            raise TypeError(f"{self.get_my_emoji.__name__} requires name or path.")

        emoji_data = [data for data in self.emoji_data_list if name == data.name or are_equal_paths(path, data.path)]
        if emoji_data:
            emoji_data.sort(key=lambda x: x.created_at)
            emoji_id = emoji_data[0].id
            return discord.utils.get(self.bot.emojis, id=emoji_id)

        if emoji_data is None and path is not None:
            if path.exists():
                raise NotImplementedError("Emoji not found. Maybe it is not registered or deleted.")
            else:
                raise FileNotFoundError("Both of emoji and filepath are not found.")

    @command()
    async def delete_your_emojis(self, ctx, reason=None):
        """Delete all emojis created by this bot."""

        async def check(emoji):
            if emoji.id in [d.id for d in self.emoji_data_list]:
                return True
            if emoji.user is None:
                emoji = await ctx.guild.fetch_emoji(emoji.id)
            if emoji.user == self.bot.user:
                return True
            return False

        await self._delete_emojis(ctx, reason, check=check)

    @command()
    async def delete_my_emojis(self, ctx, reason=None):
        """Delete all emojis created by the user who invoked this command."""

        async def check(emoji):
            if emoji.user is None:
                emoji = await ctx.guild.fetch_emoji(emoji.id)
            return emoji.user == ctx.author

        await self._delete_emojis(ctx, reason, check=check)

    @command()
    async def delete_all_emojis(self, ctx, reason=None):
        """Delete all custom emojis in the guild invoked this command."""
        await self._delete_emojis(ctx, reason, check=None)

    async def _delete_emojis(self, ctx, reason=None, check=None):
        """
        Parameters
        ----------
        check : Callable ex. lambda emoji: emoji.user == self.bot.user
            Delete only when check returns True.
        """
        await self._validate_author(ctx)
        sent_message = await ctx.send("Searching emojis... Wait for a while.")
        deleted_emojis: list[discord.Emoji] = []
        for emoji in ctx.guild.emojis:
            if check is not None:
                if not await check(emoji):
                    continue
            if not deleted_emojis:
                await sent_message.edit(content="Deleting... Wait for a while.")
            try:
                await self._delete_emoji(emoji, reason)
            except discord.HTTPException:
                pass
            else:
                deleted_emojis.append(emoji)

        self._dump_json()

        if deleted_emojis:
            msgr = messaging.SplitMessanger(ctx, "Removed following emojis:\n")
            for emoji in deleted_emojis:
                msgr += f"{str(emoji)} : {emoji.name}\n"
            await msgr.send()
        else:
            await ctx.send("Emoji to delete was not found.")

    async def _delete_emoji(self, emoji, reason):
        await emoji.delete(reason=reason)
        hit_data = [d for d in self.emoji_data_list if d.id == emoji.id]
        if hit_data:
            self.emoji_data_list.remove(hit_data[0])

    class NotOwner(Exception):
        pass

    async def _validate_author(self, ctx: Context):  # TODO decorator
        """Check if the author owns both this bot and guild.
        Raise exception if not."""
        # if await self.bot.is_owner(ctx.author):
        #     if ctx.guild.owner is ctx.author:
        #         return
        # await ctx.send("The command is available only for owner of both this bot and the server.",
        #                delete_after=20)
        # raise self.NotOwner
        pass

    async def _validate_path(self, ctx, image_dir_path):
        if image_dir_path:
            image_dir_path: Path = Path(image_dir_path)
            if not image_dir_path.exists():
                await ctx.send("Specified dir for emoji images was not found.")
                raise FileNotFoundError
        else:
            image_dir_path = self.DEFAULT_IMAGES_PATH
            if not image_dir_path.exists():
                await ctx.send("Images dir is not found on current working directory. \n"
                               "Try either of followings. \n\n"
                               "・Specify path of images dir. ex. !setup /path/to/images/dir \n"
                               "・Change working directory to run the bot so that images dir can be found."
                               )
                raise FileNotFoundError
        return image_dir_path

    @command()
    async def setup(self, ctx: Context, image_dir_path: str = None):
        """
        Registers all images in specified path, and save info about them in a json file.
        """
        guild: discord.Guild = ctx.guild
        await self._validate_author(ctx)
        validated_path = await self._validate_path(ctx, image_dir_path)
        if validated_path.is_dir():
            images_path = get_path_of_images(validated_path)
        elif is_image_file(validated_path):
            images_path = [validated_path]
        else:
            await ctx.send("Specified file must be directory of images or image file itself. ")
            return

        def has_enough_capacity():
            return (guild.emoji_limit - len(guild.emojis)) > len(images_path)

        if not has_enough_capacity():
            from textwrap import dedent
            msgr = dedent("""
                This server has no capacity to register all emojis in the image directory.
                You can delete many emojis easily with following commands.\n\n""")
            delete_commands = [self.delete_my_emojis, self.delete_your_emojis, self.delete_all_emojis]
            for command in delete_commands:
                msgr += f"{self.bot.command_prefix}{command.name}\n"
            return await ctx.send(msgr)

        registering_message = await ctx.send("Registering emojis... This can take a few minutes.")
        registered: dict[discord.Emoji:Path] = {}
        failed: list[Path] = []
        for image in images_path:
            for _ in range(3):
                try:
                    emoji = await self._register(guild, image=image)
                except discord.errors.HTTPException:
                    pass
                else:
                    emoji_data = EmojiData(id=emoji.id, name=emoji.name,
                                           path=image, created_at=emoji.created_at)
                    self.emoji_data_list.append(emoji_data)
                    registered[emoji] = image
                    break
            else:
                failed.append(image)
        self._dump_json()

        if not registered:
            await ctx.send("Nothing was registered. Maybe because you specified empty dir or something wrong.")
            return
        msgr = messaging.SplitMessanger(ctx, "Registered following emojis.\n")
        for emoji, image_path in registered.items():
            if emoji.name != image_path.stem:
                msgr += f"\n{str(emoji)}: {emoji.name}  ⚠ The name differs from {str(image_path)}. \n"
            else:
                msgr += f"{str(emoji)}"

        if failed:
            msgr += "\n\n Failed to register followings for some reason. Try once later.:\n"
            for path in failed:
                msgr += f"{str(path)} \n"
        await registering_message.delete()
        await msgr.send()

    def _dump_json(self):
        for_json = []
        for data in self.emoji_data_list:
            data = asdict(data)
            for key, val in data.items():
                data[key] = str(val)
            for_json.append(data)
        with self.emojis_json.open(mode="w") as f:
            json.dump(for_json, f)

    async def _register(self, guild, image: Path):
        emoji = await guild.create_custom_emoji(name=image.stem, image=image.read_bytes())
        self._log_if_overwrites(emoji, image)
        new_emoji_data = EmojiData(id=emoji.id, name=emoji.name, path=image, created_at=emoji.created_at)
        self.emoji_data_list.append(new_emoji_data)
        return emoji

    def _log_if_overwrites(self, emoji: discord.Emoji, image_path: Path):
        log_msg = dedent("""
                    Newly registered emoji has same {attr} as already existing one. 
                    If you call {method_name} with it, emoji created this time will be returned.""")
        overwritten_attrs = []
        if emoji.name in [data.name for data in self.emoji_data_list]:
            overwritten_attrs.append("name")
        if [data for data in self.emoji_data_list if are_equal_paths(data.path, image_path)]:
            overwritten_attrs.append("path")
        if overwritten_attrs:
            formatted = log_msg.format(attr=" and ".join(overwritten_attrs),
                                       method_name=self.get_my_emoji.__name__)
            logger.info(formatted)


def are_equal_paths(path1: Path, path2: Path):
    if path1 == path2:
        return True
    elif path1.absolute() == path2.absolute():
        return True
    cwd = Path.cwd()
    if path1.absolute().relative_to(cwd) == path2.absolute().relative_to(cwd):
        return True
    return False


def get_path_of_images(_dir: Path):
    path_list = []
    for obj in _dir.iterdir():
        if obj.is_dir():
            child_dir = obj
            path_list += get_path_of_images(child_dir)
        elif is_image_file(obj):
            path_list.append(obj)
    return path_list


def is_image_file(path: Path):
    return bool(what(path))
