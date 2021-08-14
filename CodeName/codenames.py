import asyncio
import collections  # type: ignore[import]
import functools  # type: ignore[import]
import inspect  # type: ignore[import]
import logging
import unicodedata
from collections import defaultdict
from collections.abc import Iterable
from itertools import cycle
from random import shuffle
from typing import Union, Optional, List, Dict, Tuple, Callable  # type: ignore[import]

import discord
from discord.ext import commands

import utils
from mylib import myinfo
from mylib.cogs import RegisterAvatarEmoji

if __name__ == "__main__":
    log_format = "%(levelname)s\t%(name)s\t%(message)s\tlocation:%(pathname)s(%(lineno)s)\tfn:%(funcName)s"

    logging.basicConfig(level=logging.INFO, format=log_format)

    logger = logging.getLogger(__name__)
    dpy_logger = logging.getLogger("discord")
    dpy_logger.setLevel(logging.INFO)

    async_logger = logging.getLogger("asyncio")
    async_logger.setLevel(logging.DEBUG)
    logger.setLevel(logging.DEBUG)

DEBUGGING = "DEBUGGING"  # for detecting if debugging in IDE or not

AvatarCogName = RegisterAvatarEmoji.__name__

SECONDS_OF_RESEND_MESSAGE = 890

DEFAULT_ROW_COUNT = 5
DEFAULT_COLUMN_COUNT = 5
# The discord limit of row and column is 5 at maximum. 25 buttons at maximum in 1 message.

DEFAULT_TIME_LIMITS = 7

# For cooperative mode
DEFAULT_TURNS = 8
DEFAULT_HITS_PER_TEAM = 8
GAME_OVER_PANELS_COUNT = 3

GOT_FAILED_EMOJI = "❌"
# Tried emojis = ☑☒☓✓✔☑✖❎, they look bad on discord
emoji_options = """
🔴⭕❌⛔✖📝🆚👍👎☠️🙅🙆🎊🥳💀👪⏲⏱⏰🐑🦔🐾✏️🦍❗❕‼️⚠️🆖🏴‍☠️🎲❓❔1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣8️⃣9️⃣
"""
# For ActionsView
GAME_LOG_PLACEHOLDER = "回答ログ"
GAME_LOG_ROW = 2
SUGGEST_LOG_PLACEHOLDER = "提案ログ"
SUGGEST_LOG_ROW = 3

# For button strings
SUGGESTION = "提案"
STOP_SUGGESTION = "提案を終える"
HINT = "ヒント"
CHECK = "チェック"
TURN_END = "ターンエンド"
JOIN = "参加"
SETTINGS = "設定"
SPECTATE = "感染"
SHUFFLE = "シャッフル"
START = "スタート"
END_GAME = "ゲーム終了"

with open("../default_words", encoding="utf-8") as f:
    DEFAULT_WORDS = f.readlines()

EmojiTypes = Union[discord.Emoji, discord.PartialEmoji, str]
DiscordUserTypes = Union[discord.Member, discord.User]
GameTypes = Union["GameBase", "CooperativeGame", "VSGame", "BattleRoyalGame"]
GameChannelTypes = Union[discord.TextChannel, discord.DMChannel]


class Player:
    def __init__(self, member: discord.Member, team: Optional["Team"] = None):
        self.member: discord.Member = member
        self.team: Optional[Team] = team

        self.is_on_check_mode: bool = False
        self.is_on_suggest_mode: bool = False
        self.channel: Optional[GameChannelTypes] = None
        self.suggested_hints: Optional[List] = None
        self.icon: Optional[EmojiTypes] = None
        self.game: Optional[GameTypes] = None

        self.keywords_view: Optional[KeywordsView] = None
        self.answer_actions_view: Optional[AnswerActionsView] = None
        self.hint_actions_view: Optional[HintingActionsView] = None
        self.keyword_message: Optional[discord.Message] = None
        self.action_message: Optional[discord.Message] = None

    @staticmethod
    async def get(member: discord.Member, team: Optional["Team"] = None) -> "Player":
        player = Player(member, team)
        player.channel = await player.create_channel()
        player.icon = await player.get_icon()
        return player

    def __getattr__(self, item):
        return getattr(self.member, item)

    async def create_channel(self) -> GameChannelTypes:
        return await self.create_dm()

    async def update_timer(self):
        await self.show_keyword_message()

    async def update_keywords_buttons(self):
        await self.show_keyword_message()

    async def show_keyword_message(self):
        keyword_message: discord.Message = self.keyword_message
        content = self.game.get_game_state(self)
        content += self.team.get_remaining_time_str()
        try:
            await keyword_message.edit(content=content, view=self.keywords_view)
        except (discord.errors.HTTPException, AttributeError):
            self.keyword_message = await self.channel.send(content, view=self.keywords_view)

    async def show_action_message(self):
        if self.is_on_hinter_side:
            action_view = self.hint_actions_view
        elif self in self.team.players_on_answer:
            action_view = self.answer_actions_view
        else:
            raise Exception(f"Player:{self.name} is not allocated in any team.")
        sentence = self.game.get_sentence_for_action(self)

        if self.game.open_log not in action_view.children:
            if self.game.open_log.options:
                action_view.add_item(self.game.open_log)

        try:
            await self.action_message.edit(content=sentence, view=action_view)
        except (discord.errors.HTTPException, AttributeError):
            self.action_message = await self.channel.send(sentence, view=action_view)

    async def show_game_messages(self) -> None:
        asyncio.create_task(self.show_keyword_message())
        asyncio.create_task(self.show_action_message())

    async def ask_amount(self) -> Optional[int]:  # If the player doesn't specify amount, returns None.
        message = await self.channel.send("いくつのキーワードを想定してる？")

        async def add_num_emojis():
            for emoji in utils.num_emojis[1::]:
                try:
                    await message.add_reaction(emoji=emoji)
                except discord.errors.NotFound:
                    return

        asyncio.create_task(add_num_emojis())

        def check(reaction, user):
            if user.bot:
                return False
            if reaction.message == message:
                if reaction.emoji in utils.num_emojis:
                    return True

        try:
            reaction, user = await bot.wait_for("reaction_add", check=check, timeout=20)
        except asyncio.TimeoutError:
            result = None
        else:
            result = None
            for i, emoji in enumerate(utils.num_emojis[1::]):
                if emoji == reaction.emoji:
                    result = i + 1
        finally:
            try:
                await message.delete()
            except discord.errors.HTTPException:
                pass
            return result

    def __hash__(self) -> int:
        return hash(self.member)

    async def get_icon(self) -> Optional[str]:  # This str be displayed as avatar emoji on discord.
        avatar_cog: RegisterAvatarEmoji = bot.get_cog(AvatarCogName)
        if avatar_cog:
            avatar_emoji: discord.Emoji = await avatar_cog.get_avatar_emoji(member=self.member)
            if avatar_emoji:
                return str(avatar_emoji)

    @property
    def is_on_hinter_side(self) -> bool:
        return self in self.team.players_on_hint

    @property
    def is_on_answer_side(self) -> bool:
        return self in self.team.players_on_answer

    @property
    def current_action_view(self) -> Union["HintingActionsView", "AnswerActionsView"]:
        if self.is_on_hinter_side:
            return self.hint_actions_view
        elif self.is_on_answer_side:
            return self.answer_actions_view

    @property
    def is_answerer(self) -> bool:
        team = self.team
        return team and team.on_turn and self in team.players_on_answer

    @property
    def symbol(self) -> Union[EmojiTypes, str]:  # name if emoji is None
        return self.icon or self.name

    @property
    def name(self) -> str:
        try:  # if isinstance(self.member, discord.Member):
            return self.member.nick or self.member.name
        except AttributeError:  # if isinstance(self.member, discord.User):
            return self.member.name

    def __eq__(self, other: Union["Player", DiscordUserTypes]) -> bool:
        if hasattr(other, "id"):
            return self.member.id == other.id
        return False

    async def on_success(self):

        remaining_hit_count = self.team.remaining_hit_count
        if remaining_hit_count == 0:
            await self.game.end(winner=self.team)

        await self.game.update_game_messages(for_action=False, prioritized_player=self)

    async def on_rival_button_selected(self, button: "KeywordButton"):
        x, y = button.x, button.y
        for team in self.teams:
            sample_answerer: Player = team.players_on_answer[0]
            rival_button = sample_answerer.keywords_view.get_button(x, y)
            if rival_button.is_hit:
                rival_button.style_solved()
                rival_button.opposite.style_solved()
                break
        await self.game.advance_turn()

    async def on_neutral_button_selected(self):
        await self.advance_turn()


class StrLog:
    """Manages logs. """
    hint_template = "ヒント：{keyword} {count}\n"
    hinter_intention = "    -> "
    only_turn_count = "ターン{}"
    answer_template = "    {button_label} {result_emoji}\n"
    all_players_emoji = "👪"
    all_correct_emoji = "💮"

    def __init__(self, game: "GameTypes"):
        self.game: GameTypes = game
        self.current_answer_log: defaultdict[Player:List] = defaultdict(list)
        self.current_hinter: Optional[Player] = None
        self.current_hint_log: Optional[str] = None
        self.all_history_log: List[str] = []
        self.turn_count = 1

    def output(self) -> List[str]:
        return self.all_history_log

    def on_advance_turn(self) -> None:
        self.all_history_log.append(self.current_hint_log)
        answers_summary = self.summarize_answers()
        self.all_history_log.append(answers_summary)

        self.current_answer_log = defaultdict(list)
        self.current_hint_log = None
        self.current_hinter = None

        self.turn_count += 1

    def summarize_answers(self) -> str:
        all_players_correct = True
        result = ""
        for player, logs in self.current_answer_log.items():
            all_answers_correct = True
            player_log = []
            for log in logs:
                if log[-1] == self.game.EMOJI_CORRECT:
                    player_log.append(f"{log[1]}  {self.game.EMOJI_CORRECT}")
                elif log[-1] == self.game.EMOJI_NEUTRAL:
                    player_log.append(f"{log[1]}  {self.game.EMOJI_NEUTRAL}")
                    all_answers_correct = False
                    all_players_correct = False
            if all_answers_correct:
                result += f"{player.symbol} {len(logs) * self.game.EMOJI_CORRECT}"
            else:
                result += "\n".join(player_log)

        if all_players_correct:
            if len(self.current_answer_log) > 1:  # if there are some players:
                result = f"{self.all_players_emoji} {self.all_correct_emoji}"
        return result

    def add_hint(self, player: Optional[Player], keyword: Optional[str], count: Optional[int] = None) -> None:
        self.current_hinter = player
        hint_log: str = self._make_hint_log(keyword, count, player)
        self.current_hint_log = hint_log

    def _make_hint_log(self, keyword: str, count: Optional[int], player: Optional[Player]) -> str:
        if count is None:
            count = "?"
        if player:
            return self.hint_template.format(keyword, count)
        else:
            return self.only_turn_count.format(self.turn_count)

    def add_answer(self, player: Player, answer_label: str, emoji: EmojiTypes):
        self.current_answer_log[player].append(self._make_answer_log(answer_label, emoji, player))

    def _make_answer_log(self, label: str, result_emoji: str, player: Player) -> str:
        if not self.current_hint_log:
            self.add_hint(None, None)
        if player == self.current_hinter:
            if "\n" in self.current_hint_log:
                self.current_hint_log += label
            else:
                self.current_hint_log += self.hinter_intention + label
            return self.current_hint_log
        return self.answer_template.format(button_label=label, result_emoji=result_emoji)


class SelectLog(StrLog, discord.ui.Select):
    def __init__(self, game: GameTypes, **kwargs):
        discord.ui.Select.__init__(self, **kwargs)
        StrLog.__init__(self, game)

    def add_answer(self, player: Player, answer_label: str, result_emoji: str):
        label = self._make_answer_log(answer_label, result_emoji, player)
        self.add_option_with_icon(label, player)

    def add_hint(self, player: Optional[Player], keyword: Optional[str], count: Optional[int] = None):
        super().add_hint(player, keyword, count)
        self.add_option_with_icon(self.current_hint_log, player)

    def add_option_with_icon(self, label: str, player: Optional[Player]):
        try:
            option = discord.SelectOption(label=label, emoji=player.icon)
        except (AttributeError, TypeError):
            option = discord.SelectOption(label=label)
        finally:
            self.append_option(option)


class Suggestion(discord.SelectOption):
    """Represents the amount of 👍 👎, for suggested word in discord.Select"""
    label_template = "{0} 👍:{1}, 👎:{2}"
    emoji = "❓"  # ❔ also look good

    def __init__(self, message: discord.Message, game: GameTypes, **kwargs):
        self.message = message
        self.game: "GameTypes" = game
        self.word: str = message.content
        self.player: Player = self.game.get_player(message.author.id)
        self.good: int = 0
        self.bad: int = 0
        label = self.get_label()
        super().__init__(label=label, **kwargs)

    def get_label(self) -> str:
        return self.label_template.format(self.word, self.good, self.bad)

    async def callback(self, interaction: discord.Interaction):
        interaction_author = interaction.user
        player = self.game.get_player(interaction_author.id)
        current_team = self.game.current_team
        if player in current_team:
            if player in current_team.players_on_hint:
                answer = await self.ask_if_adopt(player)
                if answer:
                    await self.game.on_hint(player, self.word)

    async def ask_if_adopt(self, player) -> Optional[bool]:
        channel = player.channel
        message = await channel.send(f"{self.word}をヒントとして採用するよ？")
        for emoji in ["👍", "👎"]:
            await message.add_reaction(emoji)

        def check(reaction: discord.Reaction, user):
            if reaction.message != message:
                return False
            elif user.id != player.id:
                return False
            elif reaction.emoji in ["👍", "👎"]:
                return True

        try:
            reaction, user = await bot.wait_for("reaction_add", check=check, timeout=20)
        except asyncio.TimeoutError:
            is_accepted = None
        else:
            if reaction == "👍":
                is_accepted = True
            elif reaction == "👎":
                is_accepted = False
        finally:
            try:
                await message.delete()
            except discord.errors.HTTPException:
                pass
        return is_accepted


class Team:
    DEFAULT_TIME_LIMITS = DEFAULT_TIME_LIMITS

    def __init__(self):
        self.players: List[Player] = []
        self.status_table = None
        self.timer = utils.AioCountdown(self.DEFAULT_TIME_LIMITS * 60, self.lose_game)
        self.on_turn = False

        self.players_on_hint = []
        self.players_on_answer = []

    def __contains__(self, user: Union[discord.User, discord.Member, Player]):
        return user.id in map(lambda x: x.id, self.players)

    def allocate_roles(self) -> None:
        for player in self.players:
            if player in self.players_on_answer or player in self.players_on_hint:
                continue
            else:
                if len(self.players_on_hint) > len(self.players_on_answer):
                    self.players_on_answer.append(player)
                else:
                    self.players_on_hint.append(player)

    @property
    def remaining_hit_count(self) -> int:
        count = 0
        buttons_of_hinter = self.get_buttons()
        buttons_of_answerer = self.get_buttons(False)
        for buttons in [buttons_of_hinter, buttons_of_answerer]:
            for button in buttons:
                if button.is_hit and not button.is_solved:
                    count += 1
        return count

    def get_remaining_time_str(self) -> str:
        minutes, seconds = divmod(self.timer.seconds, 60)
        return "⏱残り時間：{:0>2}:{:0>2}".format(minutes, seconds)

    def swap_colors(self):
        buttons_of_hinter = self.get_buttons()
        buttons_of_answerer = self.get_buttons(False)
        for button1, button2 in zip(buttons_of_hinter, buttons_of_answerer):
            button1.style, button2.style = button2.style, button1.style

    def append_player(self, player):
        player.team = self
        self.players.append(player)

    def set_view(self, game):
        for side in [self.players_on_answer, self.players_on_hint]:
            keywords_view = KeywordsView.get_prepared_view(game, *side)
            answer_actions_view = AnswerActionsView(game)
            hint_actions_view = HintingActionsView(game)
            list_for_suggestions = []
            for player in side:
                player.keywords_view = keywords_view
                player.answer_actions_view = answer_actions_view
                player.hint_actions_view = hint_actions_view
                player.suggested_hints = list_for_suggestions
        self.swap_colors()

    def get_buttons(self, targets_hint_side=True):
        if targets_hint_side:
            sample_player: Player = self.players_on_hint[0]
        else:
            sample_player: Player = self.players_on_answer[0]
        return sample_player.keywords_view.children

    async def lose_game(self):
        game = self.players[0].game
        await game.end(loser=self)


DEFAULT_SUCCESS_COLOR = discord.ButtonStyle.green
DEFAULT_GAME_OVER_COLOR = discord.ButtonStyle.gray
DEFAULT_NEUTRAL_COLOR = discord.ButtonStyle.blurple
DEFAULT_RIVAL_COLOR = discord.ButtonStyle.red


class KeywordButton(discord.ui.Button['CodeName']):
    def __init__(self, x: int, y: int, word: str, game: Optional["GameTypes"] = None,
                 success_color=None, game_over_color=None, neutral_color=None, rival_color=None):
        super().__init__(row=y)
        self.game: Optional[GameTypes] = game
        self.x = x
        self.y = y
        self.label = word
        self.__name = word  # Saves original name here, since label might change during game.
        self.is_over = False
        self.is_rival_side = False
        self.is_hit = False
        self.is_solved = False
        self.is_failed_neutral = False

        self.success_color = success_color or DEFAULT_SUCCESS_COLOR
        self.game_over_color = game_over_color or DEFAULT_GAME_OVER_COLOR
        self.neutral_color = neutral_color or DEFAULT_NEUTRAL_COLOR
        self.rival_color = rival_color or DEFAULT_RIVAL_COLOR

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        game: GameTypes = self.game
        if game.is_over:
            return

        author = interaction.user
        player = game.get_player(author.id)
        if player is None:
            spectator = await Player.get(author)
            game.spectators.append(spectator)

        team = player.team

        game.add_log(player, word=self.name, result_emoji=self.get_result_emoji())

        if not player.is_answerer:
            return

        if self.is_hit:
            self.style_solved()
            await game.on_success(player)
        elif self.is_over:
            self.style_game_over()
            await game.end(loser=team)
        elif self.is_rival_side:
            self.set_rival_style()
            await game.on_rival_button_selected(self)
        else:
            self.set_neutral(player)
            await game.on_neutral_button_selected()

    def get_result_emoji(self):
        if self.is_hit:
            return self.game.EMOJI_CORRECT
        elif self.is_over:
            return self.game.EMOJI_GAME_OVER
        elif self.is_rival_side:
            return self.game.EMOJI_RIVAL_BUTTON
        else:
            return self.game.EMOJI_NEUTRAL

    def style_solved(self):
        for button in [self, self.opposite]:
            button.disabled = True
            button.style = self.success_color
            button.is_solved = True

    def style_game_over(self):
        for button in [self, self.opposite]:
            button.disabled = True
            button.style = self.game_over_color
            button.emoji = self.game.EMOJI_GAME_OVER

    def set_rival_style(self):
        self.disabled = True
        self.style = self.rival_color

    def set_neutral(self, player):
        if self.opposite.is_failed_neutral:
            for button in [self, self.opposite]:
                button.disabled = True
                button.emoji = "🔛"
            return

        self.emoji = player.icon
        self.label = self.name + GOT_FAILED_EMOJI
        self.is_failed_neutral = True
        self.opposite.label = self.opposite.name + GOT_FAILED_EMOJI
        self.opposite.emoji = player.icon

    def set_color_for_coop(self):
        if self.is_hit:
            self.style = discord.ButtonStyle.green
        elif self.is_over:
            self.style = discord.ButtonStyle.red
        else:
            self.style = discord.ButtonStyle.blurple

    def set_color_for_VS(self):  # noqa
        if self.is_hit:
            self.style = discord.ButtonStyle.green
        elif self.is_over:
            self.style = discord.ButtonStyle.gray  # 色じゃなくてドクロでわかりやすさを出す
        elif self.is_rival_side:
            self.style = discord.ButtonStyle.red
        else:
            self.style = discord.ButtonStyle.blurple

    @property
    def width_(self) -> int:
        chars_width = 0
        if self.emoji:
            chars_width += 3
        if self.label:
            for char in self.label:
                if unicodedata.east_asian_width(char) in "FWA":  # もし全角なら, if char has 2 spaces width
                    chars_width += 2
                else:
                    chars_width += 1
        width = chars_width if chars_width < 5 else 4
        return width

    @property
    def opposite(self) -> "KeywordButton":
        players = self.view.players
        team = players[0].team
        if players == team.players_on_hint:
            opposite_players = team.players_on_answer
        elif players == team.players_on_answer:
            opposite_players = team.players_on_hint
        else:
            raise InvalidTeams("Failed to find opposite_players.")
        sample_player = opposite_players[0]
        opposite_button = sample_player.keywords_view.get_button(self.x, self.y)
        return opposite_button

    @property
    def name(self) -> str:
        return self.__name


class KeywordsView(discord.ui.View):
    children: List[KeywordButton]

    def __init__(self, words: List[str], game: "GameTypes",
                 *players: Player, row_count: Optional[int] = None, column_count: Optional[int] = None):
        super().__init__()
        self.words = words
        self.game: GameTypes = game
        self.players = list(players)
        self.row_count = row_count or DEFAULT_ROW_COUNT
        self.column_count = column_count or DEFAULT_COLUMN_COUNT

    def factory_buttons(self):
        for y in range(self.row_count):
            for x in range(self.column_count):
                button = KeywordButton(x, y, self.words[y][x])
                button.game = self.game
                self.add_item(button)

    @classmethod
    def get_prepared_view(cls, game, *players) -> "KeywordsView":
        view = cls(game.words, game, *players)
        view.factory_buttons()
        view.set_status_for_buttons()
        view.set_colors()
        return view

    def set_status_for_buttons(self, over_count=None, hit_count=None, all_panels_count=None):
        over_count = over_count or self.game.over_panel_count
        hit_count = hit_count or self.game.hit_panel_count
        all_panels_count = all_panels_count or DEFAULT_ROW_COUNT * DEFAULT_COLUMN_COUNT
        list_ = [0] * over_count + [1] * hit_count
        pudding_count = all_panels_count - len(list_)
        puddings = [2] * pudding_count
        list_ += puddings
        shuffle(list_)
        for y in range(self.row_count):
            for x in range(self.column_count):
                button = self.get_button(x, y)
                status = list_[y * 5 + x]
                if status == 0:
                    button.is_over = True
                elif status == 1:
                    button.is_hit = True

    def set_colors(self):
        buttons = self.children
        for button in buttons:
            if button.is_hit:
                button.style = discord.ButtonStyle.green
            elif button.is_over:
                button.style = discord.ButtonStyle.red
            else:
                button.style = discord.ButtonStyle.blurple

    def __getitem__(self, num: Union[int, List[int], Tuple[int]]):
        if isinstance(num, Iterable):
            num = iter(num)
            x, y = next(num), next(num)
            return self.children[y * 5 + x]
        else:
            return self.children[num]

    def get_button(self, x, y):
        # x, y = 0, 0
        return self.children[y * 5 + x]


class GameBase:
    DEFAULT_HITS_PER_TEAM = DEFAULT_HITS_PER_TEAM
    GAME_OVER_PANELS_COUNT = GAME_OVER_PANELS_COUNT
    EMOJI_CORRECT = "⭕"
    EMOJI_NEUTRAL = "❌"
    EMOJI_RIVAL_BUTTON = "😈"
    EMOJI_GAME_OVER = "☠️"

    def __init__(self, *teams: Team, words=None, **kwargs):
        super().__init__()
        self.keywords_messages: Dict[int: discord.Message] = dict()
        self.action_messages: Dict[Player: discord.Message] = dict()
        self.spectators_view = None
        self.delta_timer = None
        self.resend_task: Optional[utils.AioCountdown] = None
        self.teams: Union[List[Team]] = list(teams)
        self.spectators: Optional[List[Player]] = None

        def get_next_team():
            cycled_teams = cycle(self.teams)
            for team in cycled_teams:
                yield team

        self.next_team_generator = get_next_team()

        self.hit_panel_count = self.DEFAULT_HITS_PER_TEAM
        self.over_panel_count = self.GAME_OVER_PANELS_COUNT
        self.row_count = kwargs.get("row", None) or kwargs.get("row_count", None) or DEFAULT_ROW_COUNT
        self.column_count: int = kwargs.get("column", None) or kwargs.get("column_count", None) or DEFAULT_COLUMN_COUNT

        self.words: List[List[str]] = self.screen_words(words)
        self.hint: Optional[str] = None
        self.hint_count: Optional[int] = None

        self.open_log: Optional[SelectLog] = SelectLog(self, placeholder="ログ", row=2)
        self.log_for_review: Optional[StrLog] = StrLog(self)

        self.is_over = False

        self.wait_input_task = None
        self.wait_emoji_task = None
        self.edit_every_second_task = None

    @property
    def current_team(self) -> Team:
        for team in self.teams:
            if team.on_turn:
                return team

    async def start(self):
        next_team = next(self.next_team_generator)
        for team in self.teams:
            team.allocate_roles()
            team.set_view(self)
            if team == next_team:
                team.on_turn = True
                team.timer.start()
            for player in team.players:
                player.game = self
                await player.show_game_messages()
        self.edit_every_second_task = asyncio.create_task(self.keep_updating_timer())
        self.resend_task = asyncio.create_task(self.resend_messages())
        self.wait_input_task = asyncio.create_task(self.wait_input())

    async def wait_input(self):
        def check(message):
            if message.author.bot:
                return False
            all_players_id = [player.id for team in self.teams for player in team.players]
            if message.author.id in all_players_id:
                player = self.get_player(message.author.id)
                if message.channel == player.channel:
                    return True
            return False

        while True:
            try:
                message = await bot.wait_for("message", check=check, timeout=3600)
            except asyncio.TimeoutError:
                if self.is_over:
                    return
                else:
                    self.wait_input_task = asyncio.create_task(self.wait_input())
            else:
                await self.on_input(message)

    async def on_input(self, message: discord.Message):
        player = self.get_player(message.author.id)
        if player.is_on_suggest_mode:
            await self.on_suggest(player, message)
        else:
            await self.on_hint(player, message.content)

    async def on_suggest(self, player: Player, message_by_player):
        team = player.team
        hint_side_players = team.players_on_hint[::]  # copy to prevent bugs when the role of team members swap.
        sentence = f"「{message_by_player.content}」　が提案されました。"
        embed = discord.Embed(colour=714270)
        embed.set_author(name=player.nick or player.name, icon_url=player.icon.url)
        sample_player: Player = hint_side_players[0]

        hint_view: HintingActionsView = sample_player.hint_actions_view
        suggestion = Suggestion(message_by_player, self)
        if not sample_player.suggested_hints:  # if they still cannot see the suggestions log yet
            select_suggestion = discord.ui.Select(placeholder=SUGGEST_LOG_PLACEHOLDER, row=SUGGEST_LOG_ROW,
                                                  options=[suggestion])
            hint_view.add_item(select_suggestion)
        else:
            suggestions_log: discord.SelectMenu = hint_view.get_suggestions_log()
            suggestions_log.options.append(suggestion)
        player.suggested_hints.append(suggestion)
        asking_messages = []
        for player in hint_side_players:
            asking_message: discord.Message = await player.channel.send(sentence, embed=embed)
            for emoji in ["👍", "👎"]:
                await asking_message.add_reaction(emoji)
            asking_messages.append(asking_message)

        self.wait_emoji_task = asyncio.create_task(self.wait_for_evaluations(player, asking_messages))

    async def wait_for_evaluations(self, player, target_messages: List[discord.Message]):

        def check(reaction: discord.Reaction, user):
            if user.bot:
                return False
            if reaction.message in target_messages:
                if reaction.emoji in ["👍", "👎"]:
                    return True
            return False

        while True:
            try:
                reaction, user = await bot.wait_for("reaction_add", check=check, timeout=3600)
            except asyncio.TimeoutError:
                if self.is_over:
                    return
                else:
                    self.wait_emoji_task = asyncio.create_task(self.wait_input())
            except asyncio.CancelledError:
                return
            else:
                message_for_reaction = reaction.message
                suggestions = player.suggested_hints
                try:
                    def includes_suggestion(s):
                        return s.word in message_for_reaction.content.split(" ")[0]

                    filtered = filter(includes_suggestion, suggestions)
                    suggestion: Suggestion = list(filtered)[0]
                except (IndexError, KeyError) as e:
                    logger.warning(f"Suggestion was not found. {user.name}, {e}")
                else:
                    if reaction.emoji == "👍":
                        suggestion.good += 1
                    elif reaction.emoji == "👎":
                        suggestion.bad += 1
                    suggestion.label = suggestion.get_label()
                finally:
                    try:
                        await reaction.message.delete()
                    except discord.errors.HTTPException:
                        pass

    async def on_hint(self, player: Player, hint_str: str) -> None:

        slice_length = 1
        while len(hint_str) >= slice_length:
            # Repeat since multiple characters might represent number. ex. 12
            if self.hint_count is None:
                try:
                    translated = hint_str[-1 * slice_length:].translate(utils.for_std_num_trans)  # 漢数字なども
                    self.hint_count = int(translated)
                except ValueError:
                    break
                else:
                    self.hint = hint_str[0:-1 * slice_length]
            slice_length += 1

        if self.hint_count is None:
            self.hint = hint_str
            self.hint_count = await player.ask_amount()

        self.add_log(player, self.hint, self.hint_count)
        await self.update_game_messages(for_keywords=False)

    def add_log(self, player, word: str = None, result_emoji: str = None):
        is_answered = True if result_emoji is not None else False
        if is_answered:
            self.log_for_review.add_answer(player, word, result_emoji)
            if player.is_answerer:
                self.open_log.add_answer(player, word, result_emoji)
        else:
            hint = word or self.hint
            for log in [self.open_log, self.log_for_review]:
                log.add_hint(player, hint, self.hint_count)

    async def keep_updating_timer(self):
        with utils.AioDeltaSleeper() as delta_sleeper:
            while not self.is_over:
                await delta_sleeper.wait(2)
                for player in self.current_team.players:
                    await player.update_timer()

    async def resend_messages(self):
        while not self.is_over:
            await asyncio.sleep(SECONDS_OF_RESEND_MESSAGE)
            for messages in [self.keywords_messages.values(), self.action_messages.values()]:
                for message in messages:
                    asyncio.create_task(message.delete())
            for team in self.teams:
                for player in team.players:
                    asyncio.create_task(player.show_game_messages())

    async def update_game_messages(self, for_keywords=True, for_action=True, prioritized_player: Player = None):
        if prioritized_player:
            if for_keywords:
                await prioritized_player.show_keyword_message()
            if for_action:
                await prioritized_player.show_action_message()
        for team in self.teams:
            for player in team.players:
                if player is prioritized_player:
                    continue
                if for_keywords:
                    await player.show_keyword_message()
                if for_action:
                    await player.show_action_message()

    def get_game_state(self, player: Player) -> str:  # This method should be overwritten by each game mode.
        # remaining_hit_count = player.team.remaining_hit_count
        # return f"残りパネル数:{remaining_hit_count}\n"
        pass

    def get_sentence_for_action(self, player) -> str:
        team = player.team
        if self.is_over:
            return "Game Over\n"
        sentence = ""
        if team.on_turn:
            if player in team.players_on_hint:
                if self.hint:
                    sentence += f"**{self.hint}**  {self.hint_count}  の暗号を仲間が解読中だよ"
                elif len(team.players_on_hint) == 1:
                    sentence += "暗号を作ってね。\n狙うは緑色だよ。"
                else:
                    names = map(lambda p: p.nick or p.name, team.players_on_hint)
                    joined_names = "、".join(names)
                    sentence += f"{joined_names}の{len(list(names))}人は暗号を用意してね"
            else:
                if self.hint:
                    sentence += f"**{self.hint}** {self.hint_count} この暗号を解いてね"
                else:
                    sentence += "仲間の暗号を待ってね"
        else:
            if self.hint:
                sentence += f"相手チームが**{self.hint}** {self.hint_count} の暗号を解読中だよ" \
                            f"君の答えを入力しておけば、試合後にみんなで見返しやすくできるよ。"
            else:
                sentence += "相手チームが暗号を作成中だよ"
        return sentence

    def screen_words(self, words) -> List[List[str]]:
        unscreened_words = words or DEFAULT_WORDS
        words: List[List[str]] = [[""] * self.column_count for _ in range(self.row_count)]  # 2D_list(5*5)
        shuffle(unscreened_words)
        for y in range(self.row_count):
            for x in range(self.column_count):
                selected_word = unscreened_words.pop()
                while not self.filter_word(selected_word):
                    selected_word: str = unscreened_words.pop()
                if self.filter_word(selected_word):
                    words[y][x] = selected_word
        return words

    @staticmethod
    def filter_word(word):
        if len(word) > 5:
            return False
        else:
            return True

    @staticmethod
    def arrange_word(word):
        while len(word) < 5:
            word += "\u200b"

    async def advance_turn(self):
        self.hint = None
        self.hint_count = None
        self.current_team.timer.cancel()
        self.current_team.on_turn = False
        next_team = next(self.next_team_generator)
        next_team.on_turn = True
        self.current_team.timer.start()
        self.open_log.on_advance_turn()
        self.log_for_review.on_advance_turn()
        await self.update_game_messages()

    def get_player(self, id_: int) -> Player:
        for team in self.teams:
            for player in team.players:
                if player.id == id_:
                    return player
        for player in self.spectators:
            if player.id == id_:
                return player

    async def end(self, winner=None, loser=None):
        self.is_over = True
        for task in [self.resend_task, self.edit_every_second_task, self.wait_emoji_task, self.wait_input_task]:
            if task is not None:
                task.cancel()  # must catch some exceptions
        await self.update_game_messages()
        game_log_str = "\n".join(self.log_for_review.output())
        print(winner, loser, game_log_str)


class CooperativeGame(GameBase):
    DEFAULT_TURNS = DEFAULT_TURNS

    def __init__(self, *teams, words):
        super().__init__(*teams, words=words)
        self.remaining_turns = self.DEFAULT_TURNS

    async def advance_turn(self):
        team = self.teams[0]
        self.remaining_turns -= 1
        if self.remaining_turns < 0:
            self.is_over = True
        team.players_on_answer, team.players_on_hint = team.players_on_hint, team.players_on_answer
        await super().advance_turn()

    def get_game_state(self, player: Player) -> str:
        sentence = f"""
残りターン数:{self.remaining_turns}
当たりパネル数:{player.team.remaining_hit_count}\n\n"""
        if self.is_over:
            sentence += "GameOver"
        return sentence


class VSGame(GameBase):
    pass


class BattleRoyalGame(GameBase):
    pass


def defer_response(coro):
    async def inner(*args, **kwargs):
        try:
            interaction = args[2]
        except IndexError:
            interaction = kwargs.get("interaction", None)
            if interaction is None:
                raise TypeError(f"{coro.__name__} requires interaction argument.")
        finally:
            response = interaction.response
        try:
            await response.defer()
        except discord.errors.NotFound as e:
            logger.info(e, coro.__name__, "Unknown interaction")
        return await coro(*args, **kwargs)

    return inner


class AnswerActionsView(discord.ui.View):
    children: List[discord.Component]

    def __init__(self, game: "GameTypes", log: Optional[discord.ui.Select] = None):
        super().__init__()
        self.game: GameBase = game
        if log:
            self.add_item(log)

    @discord.ui.button(label=TURN_END, style=discord.ButtonStyle.primary)
    @defer_response
    async def end_turn(self, _, __):
        await self.game.advance_turn()

    @discord.ui.button(label=CHECK, style=discord.ButtonStyle.primary)
    @defer_response
    async def check_mode(self, _, interaction: discord.Interaction):
        author = interaction.user
        player = self.game.get_player(author.id)
        player.is_on_check_mode = not player.is_on_check_mode
        await self.game.update_game_messages()


class HintingActionsView(discord.ui.View):
    def __init__(self, game):
        super().__init__()
        self.game = game

    @discord.ui.button(label=SUGGESTION, style=discord.ButtonStyle.primary)
    @defer_response
    async def propose(self, button, interaction: discord.Interaction):
        author = interaction.user
        player = self.game.get_player(author.id)
        if button.label == SUGGESTION:
            player.is_on_suggest_mode = True
            button.label = STOP_SUGGESTION
        elif button.label == STOP_SUGGESTION:
            player.is_on_suggest_mode = False
            button.label = SUGGESTION
        await self.game.update_game_messages()

    @discord.ui.button(label=HINT, style=discord.ButtonStyle.primary)
    @defer_response
    async def hint(self, _, interaction: discord.Interaction):
        author = interaction.user
        player = self.game.get_player(author.id)
        player.is_on_suggest_mode = not player.is_on_suggest_mode

    def get_suggestions_log(self):
        for component in self.children:
            if isinstance(component, discord.SelectMenu):
                if component.placeholder == SUGGEST_LOG_PLACEHOLDER:
                    return component


class InvalidTeams(Exception):
    pass


class AfterStartView(discord.ui.View):
    def __init__(self, game):
        super().__init__()
        self.game = game

    @discord.ui.button(label=SPECTATE, style=discord.ButtonStyle.primary)
    async def spectate(self, _, interaction: discord.Interaction):
        self.game.spectators_view = KeywordsView.get_prepared_view(self.game)
        await interaction.response.send_message(view=self.game.spectators_view)

    @discord.ui.button(label=SETTINGS, style=discord.ButtonStyle.primary)
    async def settings(self, _, interaction: discord.Interaction):
        pass

    @discord.ui.button(label=END_GAME, style=discord.ButtonStyle.danger)
    async def force_end(self, _, interaction: discord.Interaction):
        pass


class OpeningView(discord.ui.View):
    def __init__(self, *players):
        super().__init__()
        self.players: List[Player] = list(players)
        self.host_member = self.players[0]
        self.teams = []
        if self.players:
            self.set_random_teams()
            for team in self.teams:
                team.allocate_roles()
        self.started = False
        self.words = None
        self.specified_mode = None

    def set_random_teams(self):
        self.teams = []
        players = self.players[::]
        shuffle(players)
        while len(players) > 1:
            team = Team()
            self.teams.append(team)
            try:
                for _ in range(2):  # At least 2 players in a team
                    player = players.pop()
                    team.append_player(player)
            except IndexError:
                logger.warning("Not enough amount of members to make a team.")
                raise InvalidTeams()
            else:
                if len(players) == 1:  # Add remaining alone player to last team.
                    player = players.pop()
                    team.append_player(player)
            finally:
                team.allocate_roles()

    def build_start_sentence(self):
        try:
            game_mode = self.current_game_mode
        except InvalidTeams:
            try:
                host_name = self.host_member.nick or self.host_member.name
            except AttributeError:
                # Host doesn't have the nick attribute, since he/she is not member, but user.
                # This can happen if invoked in GroupChannel.
                host_name = self.host_member.name
            return f"{host_name}が参加者を募集中。。。"
        if game_mode == CooperativeGame:
            displays = map(lambda p: p.symbol, self.teams[0].players)
            sentence = f"""協力モード\nプレイヤー: {' '.join(displays)}"""
        else:
            teams_str: List[str] = []
            for team in self.teams:
                answer_displays = map(lambda p: p.symbol, team.players_on_answer)
                answer_displays = "　".join(answer_displays)
                hinter_displays = map(lambda p: p.symbol, team.players_on_hint)
                hinter_displays = "　".join(hinter_displays)
                teams_str.append(
                    f"{team.players[0].symbol}チーム:\n  暗号作成班: {list(hinter_displays)}, 解読班: {list(answer_displays)}\n\n")
            sentence = "🆚".join(teams_str)
        return sentence

    @property
    def current_game_mode(self):
        if self.specified_mode:
            return self.specified_mode
        elif len(self.teams) == 1:
            return CooperativeGame
        elif len(self.teams) == 2:
            return VSGame
        elif len(self.teams) > 2:
            return BattleRoyalGame
        else:
            raise InvalidTeams("Not enough number of teams, perhaps because of not enough amount of members."
                               "This game requires more than one player.")

    @discord.ui.button(label=JOIN, style=discord.ButtonStyle.primary)
    async def join(self, _, interaction: discord.Interaction):
        guild = interaction.guild
        author = interaction.user
        member = guild.get_member(author.id)
        if member not in self.players:
            player = await Player.get(member=member)
            self.players.append(player)
            if not self.specified_mode:
                self.set_random_teams()
            sentence = self.build_start_sentence()
            await interaction.response.edit_message(content=sentence, view=self)
        else:
            await interaction.response.send_message("もう君はゲーム参加してるよ！", ephemeral=True)

    @discord.ui.button(label=START, style=discord.ButtonStyle.green)
    async def start(self, _, interaction: discord.Interaction):
        try:
            game = self.current_game_mode(*self.teams, words=self.words)
        except InvalidTeams as e:
            logger.info(e)
        else:
            await game.start()
            await interaction.response.edit_message(content="ゲーム用DMを送ったよ！", view=None)

    @discord.ui.button(label=SHUFFLE, style=discord.ButtonStyle.primary)
    async def shuffle(self, _, interaction: discord.Interaction):
        self.set_random_teams()
        sentence = self.build_start_sentence()
        await interaction.response.edit_message(content=sentence, view=self)

    @discord.ui.button(label=SETTINGS, style=discord.ButtonStyle.primary)
    async def settings(self, _, interaction: discord.Interaction):
        pass


intents = discord.Intents.all()
# intents.messages = False
bot = discord.ext.commands.Bot("$", intents=intents)
avatar_register_cog = RegisterAvatarEmoji(bot)
bot.add_cog(avatar_register_cog)

sample_view = None


@bot.command()
async def test(ctx: commands.Context):
    global sample_view
    sample_view = discord.ui.View()
    select_menu = discord.ui.Select(custom_id="カスタムID!!!", placeholder="plaaaaaaaaace" * 100)
    sample_view.add_item(select_menu)
    sample_option = discord.SelectOption(label="ラベール")
    select_menu.append_option(sample_option)
    button = discord.ui.Button(label="aaaaaaaaaaaaaaaaaaaa" * 100)
    sample_view.add_item(button)
    await ctx.send("aiueo", view=sample_view)


@bot.command()
async def debug(_):
    guild = bot.get_guild(myinfo.servers_id.実験場)
    tonkatu = guild.get_member(tonkatu_id)
    yaruzo = guild.get_member(yaruzo_id)
    players = await Player.get(tonkatu), await Player.get(yaruzo)
    startview = OpeningView(*players)
    startview.set_random_teams()
    game: GameTypes = startview.current_game_mode(*startview.teams, words=startview.words)
    await game.start()


@bot.command()
async def play(ctx: commands.Context, members=None):
    if not members and isinstance(ctx.channel, discord.DMChannel):
        await ctx.send("DM上でスタートしても他の人が参加できないよ！", delete_after=20)
        return

    host = ctx.author
    try:
        members = members or ctx.author.voice.channel.players
    except AttributeError:
        members = [ctx.author]
    else:
        def locate_host_first():
            nonlocal members, host
            for member in members:
                if member.id == host.id:
                    host = member
            members = set([host] + members)

        locate_host_first()
    players = [await Player.create(member) for member in members]
    opening = OpeningView(*players)
    if opening.players:
        for player in opening.players:
            player.icon = await player.get_icon()
    await ctx.send(opening.build_start_sentence(), view=opening)


token = myinfo.tokens.tempo_debugging
tonkatu_id = myinfo.members["とんかつ"]
yaruzo_id = myinfo.members["やるぞう"]
bot.run(token)

# yet
# 外した時にメッセージが変わらない, 自動ヒントログもない


# interaction fails!!!!!!!!!!!!
# ヒントラベル自動入力されてない done
# 謎のcomponent max length
# 当たりパネル数０になっても終わらない
# 　異常系チェック

# プレイヤー自らteamとかの設定ができるようにする
# アクション押してメッセージの編集トリガ引いた人から優先してメッセージ編集する、タイムラグ体感減らす？

# 文字数合わせる
# RealTimeBattle
# ちょうどボタンとか押してた時にタイマーきたらどうなるか検証
# VSMode検証
# 各種アクションボタン検証
# 音出す
# 認識のズレを利用して味方にだけわかるメッセージを出す(自由作文あり？)
# 専用サーバー試す？　メッセージ完全管理用に
# interaction failed系どうしよう


# done
# ログでなくなった
# ヒントのテキスト入力できなくなってる
# VC members自動ゲット(VC参加したらできる？)
# ボタン押した時に正解でも不正解
# 15分メッセージタイマー設定
# 当たりパネル数違う → keywords_viewが1種類だったときの数え方の弊害
# 名前なんども → いろんなところでteam allocateしてたのに、チェック機能がおかしかった
# 24ボタンシステム 1次元　無理だった 各次元の上限は5。つまり 5 * 5が最大で 1* 25は25が大幅超過。

# 豆知識
# 半角=1, 全角=2, 絵文字=3スペース　５スペース目からボタンの大きさは変わる。
# だいたいなんでも25lengthまで。ボタンの文字数とか、1つのviewに入るComponent(buttonとかSelectとか)の数とか。１つのSelectに入るoptionの数とか。
