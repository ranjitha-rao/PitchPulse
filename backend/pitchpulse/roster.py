"""Fictional clubs and players. Nothing here refers to a real club or player."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Player:
    id: str
    name: str
    short: str
    number: int
    position: str
    # Formation slot in the team's attacking frame (metres, attacking towards x=105).
    slot: tuple[float, float]
    pace: int
    passing: int
    finishing: int
    pressing: int
    club_apps: int = 0


@dataclass(frozen=True)
class Team:
    id: str
    name: str
    short: str
    formation: str
    color: str
    players: tuple[Player, ...] = field(default_factory=tuple)

    def player(self, pid: str) -> Player:
        return next(p for p in self.players if p.id == pid)


HOME = Team(
    id="hfc",
    name="Harbourside FC",
    short="HFC",
    formation="4-3-3",
    color="#2563eb",
    players=(
        Player("hfc_01", "Tom Marlowe", "Marlowe", 1, "GK", (5, 34), 50, 60, 10, 20, 140),
        Player("hfc_02", "Kofi Mensah-Hart", "Mensah-Hart", 2, "RB", (30, 60), 82, 72, 40, 70, 88),
        Player("hfc_04", "Jonas Lindqvist", "Lindqvist", 4, "CB", (22, 44), 65, 74, 35, 65, 120),
        Player("hfc_05", "Rafael Duarte", "Duarte", 5, "CB", (22, 24), 68, 70, 38, 66, 64),
        Player("hfc_03", "Callum Price", "Price", 3, "LB", (30, 8), 80, 70, 40, 68, 51),
        Player("hfc_06", "Yusuf Adeyemi", "Adeyemi", 6, "DM", (40, 34), 70, 80, 50, 80, 77),
        Player("hfc_08", "Daniel Okafor", "Okafor", 8, "CM", (52, 46), 76, 90, 68, 78, 99),
        Player("hfc_10", "Mateo Ferreira", "Ferreira", 10, "CM", (56, 22), 74, 86, 78, 66, 45),
        Player("hfc_07", "Leo Hartley", "Hartley", 7, "RW", (78, 60), 94, 76, 74, 60, 38),
        Player("hfc_09", "Samir Haddad", "Haddad", 9, "ST", (86, 34), 84, 70, 90, 62, 112),
        Player("hfc_11", "Ethan Brooks", "Brooks", 11, "LW", (78, 8), 88, 74, 72, 58, 30),
    ),
)

AWAY = Team(
    id="nga",
    name="Northgate Albion",
    short="NGA",
    formation="4-2-3-1",
    color="#dc2626",
    players=(
        Player("nga_01", "Piotr Nowak", "Nowak", 1, "GK", (5, 34), 48, 58, 10, 20, 201),
        Player("nga_02", "Aaron Whitfield", "Whitfield", 2, "RB", (30, 60), 80, 70, 38, 74, 90),
        Player("nga_04", "Marcus Bell", "Bell", 4, "CB", (22, 44), 66, 68, 34, 72, 133),
        Player("nga_05", "Ivan Petrovic", "Petrovic", 5, "CB", (22, 24), 64, 70, 36, 70, 58),
        Player("nga_03", "Diego Santos", "Santos", 3, "LB", (30, 8), 82, 72, 40, 76, 47),
        Player("nga_06", "Hugo Lambert", "Lambert", 6, "DM", (40, 42), 70, 78, 46, 88, 102),
        Player("nga_08", "Theo Grant", "Grant", 8, "DM", (42, 26), 72, 82, 54, 86, 66),
        Player("nga_10", "Kenji Sato", "Sato", 10, "AM", (64, 34), 78, 88, 76, 74, 81),
        Player("nga_07", "Andre Costa", "Costa", 7, "RW", (74, 58), 90, 74, 78, 72, 55),
        Player("nga_11", "Liam O'Rourke", "O'Rourke", 11, "LW", (74, 10), 86, 72, 70, 70, 36),
        Player("nga_09", "Noah Fischer", "Fischer", 9, "ST", (86, 34), 80, 66, 88, 76, 74),
    ),
)

TEAMS = {HOME.id: HOME, AWAY.id: AWAY}
PLAYERS = {p.id: p for t in TEAMS.values() for p in t.players}


def team_of(pid: str) -> Team:
    return TEAMS[pid.split("_")[0]]


def opponent(team_id: str) -> str:
    return AWAY.id if team_id == HOME.id else HOME.id


MATCH_META = {
    "match_id": "m_hfc_nga_01",
    "competition": "PitchPulse Synthetic League",
    "venue": "Harbourside Quay Stadium",
    "weather": "Dry, 11 C, light wind",
    "referee": "J. Okonkwo",
    "home": HOME.id,
    "away": AWAY.id,
}
