"""Shared short sound-effects manager for UI interactions."""

from pathlib import Path
from time import monotonic

from frontend.shared.qt import QAudioOutput, QMediaPlayer, QUrl

_CARD_DROP_VOLUME = 1.0
_CARD_DROP_PLAYBACK_RATE = 0.86
_CARD_DROP_POOL_SIZE = 4
_CARD_DROP_COOLDOWN_SECONDS = 0.06
_INVALID_MOVE_VOLUME = 0.5
_WIN_SOUND_VOLUME = 0.7


class _SoundManager:
    """Load and play cached UI sound effects from the asset folder."""

    def __init__(self):
        repo_root = Path(__file__).resolve().parents[2]
        sound_dir = repo_root / "asset" / "sound"
        self._sound_paths = {
            "card_drop": sound_dir / "card_drop.mp3",
            "invalid_move": sound_dir / "invalid_move.mp3",
            "win_sound": sound_dir / "win_sound.mp3",
        }
        self._players: dict[str, QMediaPlayer] = {}
        self._outputs: dict[str, QAudioOutput] = {}
        self._card_drop_players: list[QMediaPlayer] = []
        self._card_drop_outputs: list[QAudioOutput] = []
        self._card_drop_pool_index = 0
        self._last_card_drop_ts = 0.0

    @staticmethod
    def _create_player(sound_path: Path, volume: float, playback_rate: float = 1.0) -> tuple[QMediaPlayer, QAudioOutput]:
        audio_output = QAudioOutput()
        audio_output.setVolume(max(0.0, min(1.0, volume)))

        player = QMediaPlayer()
        player.setAudioOutput(audio_output)
        player.setSource(QUrl.fromLocalFile(str(sound_path)))
        player.setPlaybackRate(max(0.5, min(2.0, playback_rate)))
        return player, audio_output

    def _ensure_player(self, sound_key: str, volume: float) -> QMediaPlayer | None:
        player = self._players.get(sound_key)
        if player is not None:
            return player

        sound_path = self._sound_paths.get(sound_key)
        if sound_path is None or not sound_path.exists():
            return None

        player, audio_output = self._create_player(sound_path, volume)

        self._outputs[sound_key] = audio_output
        self._players[sound_key] = player
        return player

    def _ensure_card_drop_pool(self) -> bool:
        if self._card_drop_players:
            return True

        sound_path = self._sound_paths.get("card_drop")
        if sound_path is None or not sound_path.exists():
            return False

        for _ in range(_CARD_DROP_POOL_SIZE):
            player, output = self._create_player(
                sound_path,
                _CARD_DROP_VOLUME,
                playback_rate=_CARD_DROP_PLAYBACK_RATE,
            )
            self._card_drop_players.append(player)
            self._card_drop_outputs.append(output)
        return True

    @staticmethod
    def _play(player: QMediaPlayer):
        player.stop()
        player.setPosition(0)
        player.play()

    def play_card_drop(self):
        now = monotonic()
        if now - self._last_card_drop_ts < _CARD_DROP_COOLDOWN_SECONDS:
            return

        if not self._ensure_card_drop_pool():
            return

        player = self._card_drop_players[self._card_drop_pool_index]
        self._card_drop_pool_index = (self._card_drop_pool_index + 1) % len(self._card_drop_players)

        self._last_card_drop_ts = now
        self._play(player)

    def play_invalid_move(self):
        player = self._ensure_player("invalid_move", volume=_INVALID_MOVE_VOLUME)
        if player is None:
            return
        self._play(player)

    def play_win_sound(self):
        player = self._ensure_player("win_sound", volume=_WIN_SOUND_VOLUME)
        if player is None:
            return
        self._play(player)


_SOUND_MANAGER = _SoundManager()


def play_card_drop_sound() -> None:
    """Play card drop sound effect if asset exists."""
    try:
        _SOUND_MANAGER.play_card_drop()
    except Exception:
        return


def play_invalid_move_sound() -> None:
    """Play invalid move sound effect if asset exists."""
    try:
        _SOUND_MANAGER.play_invalid_move()
    except Exception:
        return


def play_win_sound() -> None:
    """Play win sound effect if asset exists."""
    try:
        _SOUND_MANAGER.play_win_sound()
    except Exception:
        return
