"""ageofempires.com/aoe2.net API."""
import datetime
import io
import json
import logging
import zipfile

import requests


LOGGER = logging.getLogger(__name__)
BASE_URL_V2 = 'https://api.ageofempires.com/api/v2/AgeII/'
BASE_URL_AOE2NET = 'https://aoe2.net/api/'
MATCH_LIST_URL = BASE_URL_V2 + 'GetMPMatchList'
MATCH_LIST_URL_AOE2NET = BASE_URL_AOE2NET + 'player/matches'
MATCH_DATA_URL = BASE_URL_V2 + 'GetMPMatchDetail'
MATCH_DATA_URL_AOE2NET = BASE_URL_AOE2NET + 'match'
LADDER_URL = BASE_URL_AOE2NET + 'leaderboard'
REC_DOWNLOAD_URL = 'https://aoe.ms/replay/'
LADDER_RESULT_LIMIT = 400
USER_MATCH_LIMIT = 1000
LADDER_MATCH_LIMIT = 1000
LADDERS = {
    0: 'Unranked',
    1: '1v1 Deathmatch',
    2: 'Team Deathmatch',
    3: '1v1 RandomMap',
    4: 'Team RandomMap'
}
REF_LADDERS = {
    0: 3,
    1: 1,
    2: 1,
    3: 3,
    4: 4
}

MATCH_CACHE = dict()


class AoeApiError(Exception):
    """AoE API error."""


def lookup_ladder_id(name):
    """Lookup ladder ID."""
    for ladder_id, ladder_name in LADDERS.items():
        if name == ladder_name:
            return ladder_id
    return None


def get_ladder(ladder_id, start=0, limit=LADDER_RESULT_LIMIT):
    """Get ladder ranks."""
    resp = requests.get(LADDER_URL, headers={
        'content-type': 'application/json'
    }, params=dict(game='aoe2de', leaderboard_id=ladder_id, start=start + 1, count=limit))
    ranks = []
    for rank in resp.json()['leaderboard']:
        ranks.append(dict(
            rank=rank['rank'],
            display_name=rank['name'],
            uid=rank['profile_id'],
            rating=rank['rating'],
            streak=rank['streak'],
            wins=rank['wins'],
            losses=rank['losses']
        ))
    return ranks


def get_ladder_matches(ladder_id, from_timestamp=None,
                       limit=LADDER_MATCH_LIMIT, reference_1v1=True):
    """Get ladder matches."""
    if isinstance(ladder_id, str):
        ladder_id = lookup_ladder_id(ladder_id)
    LOGGER.info("Getting matches for %s ladder", LADDERS[ladder_id])
    profile_ids = []
    for rank in get_ladder(REF_LADDERS[ladder_id] if reference_1v1 else ladder_id):
        profile_ids.append(str(rank['uid']))
    matches = []
    step = 10
    for i in range(0, len(profile_ids), step):
        for user_match in get_user_matches(profile_ids[i:i + step], ladder_id, from_timestamp=from_timestamp):
            matches.append(user_match)
            if len(matches) == limit:
                LOGGER.info("Fetched %d matches", len(matches))
                return matches
    LOGGER.info("Fetched %d matches", len(matches))
    return matches


def get_user_matches(profile_ids, ladder_id, from_timestamp=None, limit=USER_MATCH_LIMIT):
    """Get user matches."""
    LOGGER.info("Getting matches by user ids filtered by ladder %d", ladder_id)
    out = []
    resp = requests.get(MATCH_LIST_URL_AOE2NET, params=dict(
        game='aoe2de',
        profile_ids=','.join(profile_ids),
        count=limit
    ))
    try:
        matches = resp.json()
    except json.decoder.JSONDecodeError:
        raise AoeApiError("could not get matches")
    for match in matches:
        if 'started' not in match:
            continue
        timestamp = datetime.datetime.fromtimestamp(match['started'])
        if from_timestamp and timestamp < from_timestamp:
            continue
        if limit and len(out) == limit:
            break
        if match['leaderboard_id'] != ladder_id:
            continue
        MATCH_CACHE[match['match_id']] = match
        out.append(dict(
            match_id=match['match_id'],
            timestamp=timestamp
        ))
    return out


def _format_rec_url(match_id, player):
    """Format rec download url."""
    return '{}?gameId={}&profileId={}'.format(REC_DOWNLOAD_URL, match_id, player['profile_id'])


def get_match(match_id):
    """Get match."""
    LOGGER.info("Getting match %s", match_id)
    if match_id in MATCH_CACHE:
        aoe2net_data = MATCH_CACHE[match_id]
        LOGGER.info("retrieved match %s from cache", match_id)
    else:
        try:
            aoe2net_data = requests.get(
                MATCH_DATA_URL_AOE2NET, params=dict(match_id=match_id)
            ).json()
            LOGGER.info("requested match %s from aoe2.net", match_id)
        except json.decoder.JSONDecodeError:
            raise AoeApiError("could not fetch match")
    players = []
    for player in aoe2net_data['players']:
        players.append(dict(
            id=player['profile_id'],
            url=_format_rec_url(match_id, player),
            username=player['name'],
            rate_snapshot=player['rating']
        ))
    return dict(
        match_id=match_id,
        timestamp=datetime.datetime.fromtimestamp(aoe2net_data['started']),
        ladder_id=aoe2net_data.get('leaderboard_id'),
        build=aoe2net_data.get('version'),
        players=players
    )


def download_rec(url, target):
    """Download a recorded game."""
    LOGGER.info("Downloading rec from %s", url)
    resp = requests.get(url)
    if resp.status_code == 500:
        raise AoeApiError("rec does not exist")
    try:
        downloaded = zipfile.ZipFile(io.BytesIO(resp.content))
        downloaded.extractall(target)
        return downloaded.namelist()[0]
    except zipfile.BadZipFile:
        raise AoeApiError("bad zip file")
